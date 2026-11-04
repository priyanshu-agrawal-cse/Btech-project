"""
Phase 4 — Task C1: Optuna Hyperparameter Tuning for Baseline Models (LR, SVM, RF).

Phase 3 left Logistic Regression, Support Vector Machine (RBF), and Random Forest
untuned with default/fixed parameters in the 10 km spatial block CV.
This script performs nested Optuna hyperparameter tuning inside each of the 5 spatial folds,
selecting hyperparameters strictly on the training folds using 3-fold inner spatial CV,
and evaluates each tuned model on the held-out test fold.

Results are compared against the untuned Phase 3 baseline numbers.
Outputs saved to data/phase4/modeling/results/.
"""

import os
import sys
import json
import time
import warnings
import numpy as np
import pandas as pd
import optuna
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import SVC
from sklearn.metrics import (
    roc_auc_score,
    average_precision_score,
    accuracy_score,
    balanced_accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    matthews_corrcoef,
    cohen_kappa_score,
    brier_score_loss,
    confusion_matrix,
)

warnings.filterwarnings("ignore")
optuna.logging.set_verbosity(optuna.logging.WARNING)

_P3_SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "phase3"))
if _P3_SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _P3_SCRIPT_DIR)

from p3_common import SEED, log, save_json

OUT = "data/phase4/modeling/results"
os.makedirs(OUT, exist_ok=True)

NJ = int(os.environ.get("P3_NJOBS", "2"))
N_TRIALS_LR = int(os.environ.get("P4_TRIALS_LR", "12"))
N_TRIALS_RF = int(os.environ.get("P4_TRIALS_RF", "12"))
N_TRIALS_SVM = int(os.environ.get("P4_TRIALS_SVM", "8"))

LULC_CODES = [10, 20, 30, 40, 50, 60, 80, 90]


def matrix(df, feats):
    X = df[[f for f in feats if f != "lulc"]].copy()
    if "lulc" in feats:
        for c in LULC_CODES:
            X[f"lulc_{c}"] = (df["lulc"].values == c).astype("float32")
    return X


def panel(y, p, thr):
    yh = (p >= thr).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, yh, labels=[0, 1]).ravel()
    return {
        "ROC_AUC": roc_auc_score(y, p),
        "PR_AUC": average_precision_score(y, p),
        "threshold": thr,
        "Accuracy": accuracy_score(y, yh),
        "Balanced_Accuracy": balanced_accuracy_score(y, yh),
        "Precision_LS": precision_score(y, yh, zero_division=0),
        "Recall_LS": recall_score(y, yh, zero_division=0),
        "F1_LS": f1_score(y, yh, zero_division=0),
        "Precision_NonLS": precision_score(1 - y, 1 - yh, zero_division=0),
        "Recall_NonLS": recall_score(1 - y, 1 - yh, zero_division=0),
        "F1_NonLS": f1_score(1 - y, 1 - yh, zero_division=0),
        "F1_macro": f1_score(y, yh, average="macro", zero_division=0),
        "MCC": matthews_corrcoef(y, yh),
        "Kappa": cohen_kappa_score(y, yh),
        "Brier": brier_score_loss(y, p),
        "TP": int(tp),
        "FP": int(fp),
        "TN": int(tn),
        "FN": int(fn),
    }


def best_threshold(y, p):
    grid = np.round(np.arange(0.20, 0.81, 0.01), 2)
    scores = [f1_score(y, (p >= t).astype(int), average="macro", zero_division=0) for t in grid]
    return float(grid[int(np.argmax(scores))])


def folds(y, groups, seed=SEED, k=5):
    return list(StratifiedGroupKFold(n_splits=k, shuffle=True, random_state=seed).split(np.zeros(len(y)), y, groups))


def tune_lr(X, y, g, n_trials):
    inner = folds(y, g, seed=SEED + 1, k=3)
    def objective(t):
        c = t.suggest_float("C", 1e-3, 100.0, log=True)
        penalty = t.suggest_categorical("penalty", ["l2"])
        solver = "lbfgs"
        scores = []
        for a, b in inner:
            pipe = Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                ("clf", LogisticRegression(C=c, penalty=penalty, solver=solver, max_iter=1000, random_state=SEED))
            ])
            pipe.fit(X[a], y[a])
            scores.append(roc_auc_score(y[b], pipe.predict_proba(X[b])[:, 1]))
        return float(np.mean(scores))

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=SEED))
    study.optimize(objective, n_trials=n_trials)
    return study.best_params, study.best_value


def tune_rf(X, y, g, n_trials):
    inner = folds(y, g, seed=SEED + 1, k=3)
    def objective(t):
        p = dict(
            n_estimators=t.suggest_categorical("n_estimators", [200, 300, 400]),
            max_depth=t.suggest_int("max_depth", 6, 16),
            min_samples_leaf=t.suggest_int("min_samples_leaf", 1, 8),
            max_features=t.suggest_categorical("max_features", ["sqrt", "log2", 0.4]),
            n_jobs=NJ,
            random_state=SEED
        )
        scores = []
        for a, b in inner:
            m = RandomForestClassifier(**p).fit(X[a], y[a])
            scores.append(roc_auc_score(y[b], m.predict_proba(X[b])[:, 1]))
        return float(np.mean(scores))

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=SEED))
    study.optimize(objective, n_trials=n_trials)
    return study.best_params, study.best_value


def tune_svm(X, y, g, n_trials):
    inner = folds(y, g, seed=SEED + 1, k=3)
    def objective(t):
        c = t.suggest_float("C", 0.1, 20.0, log=True)
        gamma = t.suggest_float("gamma", 1e-3, 0.5, log=True)
        scores = []
        for a, b in inner:
            pipe = Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                ("clf", SVC(C=c, gamma=gamma, kernel="rbf", probability=True, random_state=SEED, max_iter=2000))
            ])
            pipe.fit(X[a], y[a])
            scores.append(roc_auc_score(y[b], pipe.predict_proba(X[b])[:, 1]))
        return float(np.mean(scores))

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=SEED))
    study.optimize(objective, n_trials=n_trials)
    return study.best_params, study.best_value


def inner_oof(make_fn, X, y, g):
    oof_preds = np.zeros(len(y))
    for a, b in folds(y, g, seed=SEED + 2, k=3):
        m = make_fn()
        m.fit(X[a], y[a])
        oof_preds[b] = m.predict_proba(X[b])[:, 1]
    return oof_preds


def main_tuning():
    t0 = time.time()
    log("Loading Phase 3 dataset for baseline tuning...")
    full = pd.read_csv("data/phase3/modeling/FINAL_DATASET_v3.csv")
    with open("models/phase3/feature_list.json", "r") as f:
        meta = json.load(f)
        ALL = meta["raster_features"]

    main = full[full.set.isin(["pos", "neg_random"])].reset_index(drop=True)
    y = main.landslide.values
    g10 = main.block10.values
    Xdf = matrix(main, ALL)
    X = Xdf.values.astype("float32")
    outer = folds(y, g10)

    log(f"Dataset: {X.shape}, Positives: {y.sum()}, 10km Blocks: {len(np.unique(g10))}")
    log(f"Trials: LR={N_TRIALS_LR}, RF={N_TRIALS_RF}, SVM={N_TRIALS_SVM}")

    models = ["Tuned_Logistic_Regression", "Tuned_Random_Forest", "Tuned_SVM_RBF"]
    rows = []
    best_fold_params = []

    for k, (tr, te) in enumerate(outer):
        fk_t0 = time.time()
        Xtr, ytr, gtr, Xte, yte = X[tr], y[tr], g10[tr], X[te], y[te]
        log(f"--- FOLD {k+1}/5 ---")

        # 1. Tune LR
        t_lr = time.time()
        p_lr, auc_lr = tune_lr(Xtr, ytr, gtr, N_TRIALS_LR)
        log(f"  Fold {k}: LR tuned in {time.time()-t_lr:.1f}s | Inner AUC: {auc_lr:.4f} | {p_lr}")

        # 2. Tune RF
        t_rf = time.time()
        p_rf, auc_rf = tune_rf(Xtr, ytr, gtr, N_TRIALS_RF)
        log(f"  Fold {k}: RF tuned in {time.time()-t_rf:.1f}s | Inner AUC: {auc_rf:.4f} | {p_rf}")

        # 3. Tune SVM
        t_svm = time.time()
        p_svm, auc_svm = tune_svm(Xtr, ytr, gtr, N_TRIALS_SVM)
        log(f"  Fold {k}: SVM tuned in {time.time()-t_svm:.1f}s | Inner AUC: {auc_svm:.4f} | {p_svm}")

        best_fold_params.append({
            "fold": k,
            "lr": {"params": p_lr, "inner_auc": auc_lr},
            "rf": {"params": p_rf, "inner_auc": auc_rf},
            "svm": {"params": p_svm, "inner_auc": auc_svm},
        })

        makers = {
            "Tuned_Logistic_Regression": lambda: Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                ("clf", LogisticRegression(**p_lr, solver="lbfgs", max_iter=1000, random_state=SEED))
            ]),
            "Tuned_Random_Forest": lambda: RandomForestClassifier(**p_rf),
            "Tuned_SVM_RBF": lambda: Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                ("clf", SVC(**p_svm, kernel="rbf", probability=True, random_state=SEED, max_iter=2000))
            ]),
        }

        for m_name in models:
            mk = makers[m_name]
            inner_p = inner_oof(mk, Xtr, ytr, gtr)
            thr = best_threshold(ytr, inner_p)
            
            fit_m = mk().fit(Xtr, ytr)
            test_p = fit_m.predict_proba(Xte)[:, 1]

            res = panel(yte, test_p, thr)
            rows.append({"model": m_name, "fold": k, "n_test": len(te), **res})
            log(f"  {m_name} (Fold {k}): Test ROC-AUC = {res['ROC_AUC']:.4f}, Macro-F1 = {res['F1_macro']:.4f}, MCC = {res['MCC']:.4f}")

        log(f"Fold {k+1} complete in {time.time()-fk_t0:.1f}s")

    byfold = pd.DataFrame(rows)
    byfold.round(4).to_csv(f"{OUT}/tuned_baselines_by_fold.csv", index=False)

    METRICS = ["ROC_AUC", "PR_AUC", "Accuracy", "Balanced_Accuracy", "Precision_LS", "Recall_LS", "F1_LS",
               "Precision_NonLS", "Recall_NonLS", "F1_NonLS", "F1_macro", "MCC", "Kappa", "Brier", "threshold"]
    summary = byfold.groupby("model")[METRICS].agg(["mean", "std"])
    summary.columns = [f"{a}_{b}" for a, b in summary.columns]
    summary = summary.reset_index().sort_values("ROC_AUC_mean", ascending=False)
    summary.round(4).to_csv(f"{OUT}/tuned_baselines_summary.csv", index=False)

    save_json(best_fold_params, f"{OUT}/tuned_baselines_best_params.json")

    log("\n" + "="*80)
    log("TUNED BASELINE MODELS: Nested 10 km Spatial CV Summary (Mean +/- SD):")
    log(summary[["model", "ROC_AUC_mean", "ROC_AUC_std", "PR_AUC_mean", "F1_macro_mean", "F1_macro_std", "MCC_mean"]].round(3).to_string(index=False))

    # Compare with Phase 3 untuned baselines
    p3_path = "data/phase3/modeling/results/nested_metrics_summary.csv"
    if os.path.exists(p3_path):
        p3_summary = pd.read_csv(p3_path)
        log("\nPhase 3 Reference Models:")
        log(p3_summary[["model", "ROC_AUC_mean", "ROC_AUC_std", "PR_AUC_mean", "F1_macro_mean", "F1_macro_std", "MCC_mean"]].round(3).to_string(index=False))

        # Build comparison table
        comp_rows = []
        model_mapping = [
            ("Logistic_Regression", "Tuned_Logistic_Regression", "Logistic Regression"),
            ("SVM_RBF", "Tuned_SVM_RBF", "SVM (RBF)"),
            ("Random_Forest", "Tuned_Random_Forest", "Random Forest"),
        ]
        for untuned_name, tuned_name, disp in model_mapping:
            u_row = p3_summary[p3_summary.model == untuned_name]
            t_row = summary[summary.model == tuned_name]
            if len(u_row) > 0 and len(t_row) > 0:
                u_auc = u_row["ROC_AUC_mean"].iloc[0]
                t_auc = t_row["ROC_AUC_mean"].iloc[0]
                u_f1 = u_row["F1_macro_mean"].iloc[0]
                t_f1 = t_row["F1_macro_mean"].iloc[0]
                u_mcc = u_row["MCC_mean"].iloc[0]
                t_mcc = t_row["MCC_mean"].iloc[0]
                comp_rows.append({
                    "Architecture": disp,
                    "Untuned_ROC_AUC": round(u_auc, 3),
                    "Tuned_ROC_AUC": round(t_auc, 3),
                    "Delta_ROC_AUC": round(t_auc - u_auc, 3),
                    "Untuned_F1_macro": round(u_f1, 3),
                    "Tuned_F1_macro": round(t_f1, 3),
                    "Delta_F1_macro": round(t_f1 - u_f1, 3),
                    "Untuned_MCC": round(u_mcc, 3),
                    "Tuned_MCC": round(t_mcc, 3),
                })
        comp_df = pd.DataFrame(comp_rows)
        comp_df.to_csv(f"{OUT}/tuned_vs_untuned_comparison.csv", index=False)
        log("\n" + "="*80)
        log("DIRECT COMPARISON: Untuned (Phase 3) vs Tuned (Phase 4):")
        log(comp_df.to_string(index=False))

    log(f"\nTuning and evaluation complete in {time.time()-t0:.1f}s.")


if __name__ == "__main__":
    main_tuning()
