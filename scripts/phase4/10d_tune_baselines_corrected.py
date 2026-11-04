"""
Phase 4 / Step 10d - corrected tuning of LR, SVM and RF (DATA-036).

Replaces the numbers of 10_tune_baselines_cv.py, which stays in place unchanged. Fixes:
  * RF final fit now has random_state and n_jobs. study.best_params holds only the
    searched values, so the earlier final fit was unseeded.
  * SVC has no iteration limit, as in Phase 3. The earlier limit of 2000 stopped the
    solver before convergence in all five folds (data/phase4/verification/svm_rf_recheck.csv).
  * LR max_iter is 2000, as in Phase 3.
  * 15 trials for all three models, as in step 10. TPE needs 10 random start-up trials,
    so the earlier 8 SVM trials were the same 8 random candidates in every fold.
  * The comparison uses unrounded means and shows the road-only baseline beside the scores.

The outer folds, inner folds, threshold search and metrics are those of Phase 3 step 10.
Outputs: data/phase4/modeling/results/tuned_baselines_v2_*
"""

import json
import os
import sys
import time
import warnings

import numpy as np
import optuna
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, average_precision_score, balanced_accuracy_score,
                             brier_score_loss, cohen_kappa_score, confusion_matrix, f1_score,
                             matthews_corrcoef, precision_score, recall_score, roc_auc_score)
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "phase3")))
from p3_common import SEED, log, save_json

warnings.filterwarnings("ignore")
optuna.logging.set_verbosity(optuna.logging.WARNING)

OUT = "data/phase4/modeling/results"
NJ = int(os.environ.get("P3_NJOBS", "3"))
N_TRIALS = int(os.environ.get("P3_TRIALS", "15"))
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
    return {"ROC_AUC": roc_auc_score(y, p), "PR_AUC": average_precision_score(y, p), "threshold": thr,
            "Accuracy": accuracy_score(y, yh), "Balanced_Accuracy": balanced_accuracy_score(y, yh),
            "Precision_LS": precision_score(y, yh, zero_division=0), "Recall_LS": recall_score(y, yh, zero_division=0),
            "F1_LS": f1_score(y, yh, zero_division=0),
            "Precision_NonLS": precision_score(1 - y, 1 - yh, zero_division=0),
            "Recall_NonLS": recall_score(1 - y, 1 - yh, zero_division=0),
            "F1_NonLS": f1_score(1 - y, 1 - yh, zero_division=0),
            "F1_macro": f1_score(y, yh, average="macro", zero_division=0), "MCC": matthews_corrcoef(y, yh),
            "Kappa": cohen_kappa_score(y, yh), "Brier": brier_score_loss(y, p),
            "TP": int(tp), "FP": int(fp), "TN": int(tn), "FN": int(fn)}


def best_threshold(y, p):
    grid = np.round(np.arange(0.20, 0.81, 0.01), 2)
    scores = [f1_score(y, (p >= t).astype(int), average="macro", zero_division=0) for t in grid]
    return float(grid[int(np.argmax(scores))])


def folds(y, groups, seed=SEED, k=5):
    return list(StratifiedGroupKFold(n_splits=k, shuffle=True, random_state=seed).split(np.zeros(len(y)), y, groups))


def lr_model(**p):
    return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                         LogisticRegression(max_iter=2000, random_state=SEED, **p))


def svm_model(**p):
    return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                         SVC(kernel="rbf", probability=True, random_state=SEED, **p))


def rf_model(**p):
    return RandomForestClassifier(n_jobs=NJ, random_state=SEED, **p)


def suggest(kind, t):
    if kind == "lr":
        return dict(C=t.suggest_float("C", 1e-3, 100.0, log=True))
    if kind == "svm":
        return dict(C=t.suggest_float("C", 0.1, 20.0, log=True), gamma=t.suggest_float("gamma", 1e-3, 0.5, log=True))
    return dict(n_estimators=t.suggest_categorical("n_estimators", [200, 300, 400]),
                max_depth=t.suggest_int("max_depth", 6, 16),
                min_samples_leaf=t.suggest_int("min_samples_leaf", 1, 8),
                max_features=t.suggest_categorical("max_features", ["sqrt", "log2", 0.4]))


MAKE = {"lr": lr_model, "svm": svm_model, "rf": rf_model}
NAME = {"lr": "Logistic_Regression", "svm": "SVM_RBF", "rf": "Random_Forest"}


def tune(kind, X, y, g):
    inner = folds(y, g, seed=SEED + 1, k=3)

    def objective(t):
        p = suggest(kind, t)
        s = []
        for a, b in inner:
            m = MAKE[kind](**p).fit(X[a], y[a])
            s.append(roc_auc_score(y[b], m.predict_proba(X[b])[:, 1]))
        return float(np.mean(s))

    st = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=SEED))
    st.optimize(objective, n_trials=N_TRIALS)
    return dict(st.best_params), st.best_value


def inner_oof(make, X, y, g):
    oof = np.zeros(len(y))
    for a, b in folds(y, g, seed=SEED + 2, k=3):
        oof[b] = make().fit(X[a], y[a]).predict_proba(X[b])[:, 1]
    return oof


t0 = time.time()
full = pd.read_csv("data/phase3/modeling/FINAL_DATASET_v3.csv")
with open("models/phase3/feature_list.json") as f:
    ALL = json.load(f)["raster_features"]
main = full[full.set.isin(["pos", "neg_random"])].reset_index(drop=True)
y = main.landslide.values
g10 = main.block10.values
X = matrix(main, ALL).values.astype("float32")
outer = folds(y, g10)
log(f"Main table {X.shape}, positives {y.sum()}, blocks {len(np.unique(g10))}, trials per tuning {N_TRIALS}")

rows, params = [], []
for k, (tr, te) in enumerate(outer):
    t = time.time()
    Xtr, ytr, gtr, Xte, yte = X[tr], y[tr], g10[tr], X[te], y[te]
    rec = {"fold": k}
    for kind in ("lr", "svm", "rf"):
        bp, score = tune(kind, Xtr, ytr, gtr)
        rec[kind] = {"params": bp, "inner_auc": score}
        mk = lambda: MAKE[kind](**bp)
        thr = best_threshold(ytr, inner_oof(mk, Xtr, ytr, gtr))
        rows.append({"model": NAME[kind], "fold": k, "n_test": len(te),
                     **panel(yte, mk().fit(Xtr, ytr).predict_proba(Xte)[:, 1], thr)})
        log(f"  fold {k} {kind}: inner AUC {score:.4f}, test AUC {rows[-1]['ROC_AUC']:.4f}, {bp}")
    params.append(rec)
    log(f"fold {k} done in {time.time() - t:.0f}s")

byfold = pd.DataFrame(rows)
byfold.round(4).to_csv(f"{OUT}/tuned_baselines_v2_by_fold.csv", index=False)
METRICS = ["ROC_AUC", "PR_AUC", "Accuracy", "Balanced_Accuracy", "Precision_LS", "Recall_LS", "F1_LS",
           "Precision_NonLS", "Recall_NonLS", "F1_NonLS", "F1_macro", "MCC", "Kappa", "Brier", "threshold"]
s = byfold.groupby("model")[METRICS].agg(["mean", "std"])
s.columns = [f"{a}_{b}" for a, b in s.columns]
s = s.reset_index().sort_values("ROC_AUC_mean", ascending=False)
s.round(4).to_csv(f"{OUT}/tuned_baselines_v2_summary.csv", index=False)
save_json(params, f"{OUT}/tuned_baselines_v2_best_params.json")

p3 = pd.read_csv("data/phase3/modeling/results/nested_metrics_summary.csv").set_index("model")
p3f = pd.read_csv("data/phase3/modeling/results/nested_metrics_by_fold.csv")
comp = []
for n in NAME.values():
    a = p3f[p3f.model == n].sort_values("fold")
    b = byfold[byfold.model == n].sort_values("fold")
    r = s[s.model == n].iloc[0]
    comp.append({"model": n, "untuned_ROC_AUC": p3.loc[n, "ROC_AUC_mean"], "tuned_ROC_AUC": round(r.ROC_AUC_mean, 4),
                 "delta_ROC_AUC": round(r.ROC_AUC_mean - p3.loc[n, "ROC_AUC_mean"], 4),
                 "folds_better_AUC": int((b.ROC_AUC.values > a.ROC_AUC.values).sum()),
                 "untuned_F1_macro": p3.loc[n, "F1_macro_mean"], "tuned_F1_macro": round(r.F1_macro_mean, 4),
                 "delta_F1_macro": round(r.F1_macro_mean - p3.loc[n, "F1_macro_mean"], 4),
                 "untuned_MCC": p3.loc[n, "MCC_mean"], "tuned_MCC": round(r.MCC_mean, 4), "fold_SD_AUC": round(r.ROC_AUC_std, 4)})
comp = pd.DataFrame(comp)
comp.to_csv(f"{OUT}/tuned_baselines_v2_comparison.csv", index=False)
log("\n" + comp.to_string(index=False))
log(f"Reference: XGBoost {p3.loc['XGBoost', 'ROC_AUC_mean']}, distance to road only 0.912 (repeated CV).")
log(f"Done in {time.time() - t0:.0f}s")
