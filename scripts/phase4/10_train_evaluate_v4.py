"""
Phase 4 / Task A5 — copy of Phase 3 step 10 with the GSI geology factors added (DATA-039).
Only the inputs, the factor lists, matrix() and the output folders differ from Phase 3.

Primary protocol (decided in DATA-018): 5 folds of 10 km spatial blocks
(StratifiedGroupKFold on block10). Everything that could leak is done INSIDE the
training part of each outer fold:
  * hyper-parameters: Optuna TPE, inner 3-fold 10 km block CV (XGBoost, LightGBM)
  * decision threshold: F1-optimal on the inner out-of-fold probabilities
  * imputation and scaling for LR/SVM (sklearn Pipeline)

Models: Logistic Regression, SVM (RBF), Random Forest, XGBoost, LightGBM and the
soft-voting ensemble of RF + XGBoost + LightGBM.

Experiments (XGBoost, parameters tuned once on the whole main table, for
COMPARING designs; the unbiased score of the final model is the nested one):
  E1 incremental factor groups   E2 negative controls (coordinates, roads only)
  E3 block size + random CV      E4 road-matched negatives (survey bias)
  E5 sampling ratio 1:5          E6 without smooth regional fields
Interpretation: permutation importance on spatial test folds, SHAP (XGBoost
pred_contribs). The fold models are saved for the out-of-fold map (step 11).

IMPORTANT: F1/precision here are measured on a BALANCED evaluation set (1:1).
Real landslide pixels are 0.008 % of the land, so these numbers are not the
precision of a field alarm. Map-level validation is in step 12.

Outputs: data/phase4/modeling/results/, models/phase4/
"""

import os
import sys
import json
import time
import warnings
import numpy as np
import pandas as pd
import joblib
import optuna
import lightgbm as lgb
from xgboost import XGBClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (roc_auc_score, average_precision_score, f1_score, precision_score,
                             recall_score, confusion_matrix, matthews_corrcoef, cohen_kappa_score,
                             brier_score_loss, balanced_accuracy_score, accuracy_score, roc_curve,
                             precision_recall_curve)
from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "phase3")))
from p3_common import save_json, log, SEED
MOD_DIR, MODELS_DIR = "data/phase4/modeling", "models/phase4"
from p3_plot import style, C_POS, C_NEG, C_AQUA, C_VIOLET, C_GREY, INK2

warnings.filterwarnings("ignore")
optuna.logging.set_verbosity(optuna.logging.WARNING)
os.makedirs(MODELS_DIR, exist_ok=True)
style()
OUT = f"{MOD_DIR}/results"
os.makedirs(OUT, exist_ok=True)
NJ = int(os.environ.get("P3_NJOBS", "3"))
N_TRIALS = int(os.environ.get("P3_TRIALS", "20"))
T0 = time.time()

HAS_NDVI = False
full = pd.read_csv(f"{MOD_DIR}/FINAL_DATASET_v4.csv")

# curv_general (= profile - plan, exact) and tri (rho 0.974 with slope) removed by the unsupervised EDA rule (DATA-027)
TERRAIN = ["elevation", "slope", "aspect_sin", "aspect_cos", "curv_profile", "curv_plan", "tpi_270m"]
SCALES = ["tpi_1km", "tpi_3km", "relief_1km"]
HYDRO = ["twi", "spi_log", "dist_stream", "hand"]
PHASE1 = ["lulc", "dist_fault", "map", "max_precip"]
SOIL = ["soil_clay_pct", "soil_sand_pct", "soil_bdod_gcm3"]
RIVER = ["dist_river_osm"]
ROADS = ["dist_road_any", "dist_road_major", "road_density_1km"]
GEOLOGY = ["lith_group", "dist_lineament", "lineament_density_1km"]
ALL = TERRAIN + SCALES + HYDRO + PHASE1 + SOIL + RIVER + ROADS + GEOLOGY
LITH_CODES = [1, 2, 3, 4, 5, 6, 7]
LULC_CODES = [10, 20, 30, 40, 50, 60, 80, 90]


def matrix(df, feats):
    """Numeric design matrix; LULC is nominal, so it is one-hot encoded."""
    X = df[[f for f in feats if f not in ("lulc", "lith_group")]].copy()
    if "lulc" in feats:
        for c in LULC_CODES:
            X[f"lulc_{c}"] = (df["lulc"].values == c).astype("float32")
    if "lith_group" in feats:
        for c in LITH_CODES:
            X[f"lith_{c}"] = (df["lith_group"].values == c).astype("float32")
    return X


def panel(y, p, thr):
    yh = (p >= thr).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, yh, labels=[0, 1]).ravel()
    return {"ROC_AUC": roc_auc_score(y, p), "PR_AUC": average_precision_score(y, p), "threshold": thr,
            "Accuracy": accuracy_score(y, yh), "Balanced_Accuracy": balanced_accuracy_score(y, yh),
            "Precision_LS": precision_score(y, yh, zero_division=0), "Recall_LS": recall_score(y, yh, zero_division=0),
            "F1_LS": f1_score(y, yh, zero_division=0), "Precision_NonLS": precision_score(1 - y, 1 - yh, zero_division=0),
            "Recall_NonLS": recall_score(1 - y, 1 - yh, zero_division=0), "F1_NonLS": f1_score(1 - y, 1 - yh, zero_division=0),
            "F1_macro": f1_score(y, yh, average="macro", zero_division=0), "MCC": matthews_corrcoef(y, yh),
            "Kappa": cohen_kappa_score(y, yh), "Brier": brier_score_loss(y, p),
            "TP": int(tp), "FP": int(fp), "TN": int(tn), "FN": int(fn)}


def best_threshold(y, p):
    grid = np.round(np.arange(0.20, 0.81, 0.01), 2)
    scores = [f1_score(y, (p >= t).astype(int), average="macro", zero_division=0) for t in grid]
    return float(grid[int(np.argmax(scores))])


def folds(y, groups, seed=SEED, k=5):
    return list(StratifiedGroupKFold(n_splits=k, shuffle=True, random_state=seed).split(np.zeros(len(y)), y, groups))


def xgb_model(**p):
    d = dict(n_estimators=300, max_depth=4, learning_rate=0.05, tree_method="hist", n_jobs=NJ,
             random_state=SEED, eval_metric="logloss")
    d.update(p)
    return XGBClassifier(**d)


def lgb_model(**p):
    d = dict(n_estimators=300, max_depth=4, learning_rate=0.05, n_jobs=NJ, random_state=SEED, verbosity=-1)
    d.update(p)
    return lgb.LGBMClassifier(**d)


def rf_model():
    return RandomForestClassifier(n_estimators=400, min_samples_leaf=3, max_features="sqrt", n_jobs=NJ, random_state=SEED)


def lr_model():
    return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                         LogisticRegression(C=1.0, max_iter=2000, random_state=SEED))


def svm_model():
    return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                         SVC(C=1.0, kernel="rbf", gamma="scale", probability=True, random_state=SEED))


def tune(kind, X, y, g, n_trials):
    inner = folds(y, g, seed=SEED + 1, k=3)

    def objective(t):
        p = dict(n_estimators=t.suggest_int("n_estimators", 150, 500, step=50),
                 max_depth=t.suggest_int("max_depth", 2, 6),
                 learning_rate=t.suggest_float("learning_rate", 0.01, 0.1, log=True),
                 subsample=t.suggest_float("subsample", 0.6, 1.0),
                 colsample_bytree=t.suggest_float("colsample_bytree", 0.5, 1.0),
                 reg_lambda=t.suggest_float("reg_lambda", 0.5, 20, log=True))
        if kind == "xgb":
            p["min_child_weight"] = t.suggest_int("min_child_weight", 1, 15)
            mk = xgb_model
        else:
            p["min_child_samples"] = t.suggest_int("min_child_samples", 5, 60)
            p["subsample_freq"] = 1
            mk = lgb_model
        s = []
        for a, b in inner:
            m = mk(**p).fit(X[a], y[a])
            s.append(roc_auc_score(y[b], m.predict_proba(X[b])[:, 1]))
        return float(np.mean(s))

    st = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=SEED))
    st.optimize(objective, n_trials=n_trials)
    bp = dict(st.best_params)
    if kind == "lgb":
        bp["subsample_freq"] = 1
    return bp, st.best_value


def inner_oof(make, X, y, g):
    oof = np.zeros(len(y))
    for a, b in folds(y, g, seed=SEED + 2, k=3):
        oof[b] = make().fit(X[a], y[a]).predict_proba(X[b])[:, 1]
    return oof


main = full[full.set.isin(["pos", "neg_random"])].reset_index(drop=True)
y = main.landslide.values
g10 = main.block10.values
Xdf = matrix(main, ALL)
COLS = list(Xdf.columns)
X = Xdf.values.astype("float32")
outer = folds(y, g10)
log(f"Main table {X.shape}, positives {y.sum()}, blocks {len(np.unique(g10))}, trials per tuning {N_TRIALS}")

# ---- nested spatial CV --------------------------------------------------------------
names = ["Logistic_Regression", "SVM_RBF", "Random_Forest", "XGBoost", "LightGBM", "Ensemble_RF_XGB_LGBM"]
oof = {n: np.full(len(y), np.nan) for n in names}
rows, fold_params = [], []
for k, (tr, te) in enumerate(outer):
    t = time.time()
    Xtr, ytr, gtr, Xte, yte = X[tr], y[tr], g10[tr], X[te], y[te]
    bx, sx = tune("xgb", Xtr, ytr, gtr, N_TRIALS)
    bl, sl = tune("lgb", Xtr, ytr, gtr, N_TRIALS)
    fold_params.append({"fold": k, "xgb": bx, "xgb_inner_auc": sx, "lgb": bl, "lgb_inner_auc": sl})
    makers = {"Logistic_Regression": lr_model, "SVM_RBF": svm_model, "Random_Forest": rf_model,
              "XGBoost": lambda: xgb_model(**bx), "LightGBM": lambda: lgb_model(**bl)}
    inner_p, test_p = {}, {}
    for n, mk in makers.items():
        inner_p[n] = inner_oof(mk, Xtr, ytr, gtr)
        test_p[n] = mk().fit(Xtr, ytr).predict_proba(Xte)[:, 1]
    trio = ["Random_Forest", "XGBoost", "LightGBM"]
    inner_p[names[-1]] = np.mean([inner_p[n] for n in trio], axis=0)
    test_p[names[-1]] = np.mean([test_p[n] for n in trio], axis=0)
    for n in names:
        oof[n][te] = test_p[n]
        thr = best_threshold(ytr, inner_p[n])
        rows.append({"model": n, "fold": k, "n_test": len(te), **panel(yte, test_p[n], thr)})
    log(f"fold {k}: " + "  ".join(f"{n[:4]}={roc_auc_score(yte, test_p[n]):.3f}" for n in names)
        + f"  [{time.time() - t:.0f}s]")

byfold = pd.DataFrame(rows)
byfold.round(4).to_csv(f"{OUT}/nested_metrics_by_fold.csv", index=False)
METRICS = ["ROC_AUC", "PR_AUC", "Accuracy", "Balanced_Accuracy", "Precision_LS", "Recall_LS", "F1_LS",
           "Precision_NonLS", "Recall_NonLS", "F1_NonLS", "F1_macro", "MCC", "Kappa", "Brier", "threshold"]
s = byfold.groupby("model")[METRICS].agg(["mean", "std"])
s.columns = [f"{a}_{b}" for a, b in s.columns]
s = s.reset_index().sort_values("ROC_AUC_mean", ascending=False)
s.round(4).to_csv(f"{OUT}/nested_metrics_summary.csv", index=False)
log("\nNested 10 km spatial CV (fold mean +/- SD):\n" +
    s[["model", "ROC_AUC_mean", "ROC_AUC_std", "PR_AUC_mean", "F1_macro_mean", "F1_macro_std", "F1_LS_mean",
       "F1_NonLS_mean", "MCC_mean", "threshold_mean"]].round(3).to_string(index=False))
cm = byfold.groupby("model")[["TP", "FP", "TN", "FN"]].sum().reset_index()
cm.to_csv(f"{OUT}/confusion_matrices_pooled.csv", index=False)
pd.DataFrame(oof).assign(sample_id=main.sample_id.values, landslide=y, block10=g10).round(5).to_csv(
    f"{OUT}/oof_predictions.csv", index=False)

# block-bootstrap interval of the pooled ROC-AUC
rng = np.random.default_rng(SEED)
ub = np.unique(g10)
ibb = {b: np.flatnonzero(g10 == b) for b in ub}
ci = []
for n in names:
    b = []
    for _ in range(500):
        ii = np.concatenate([ibb[x] for x in rng.choice(ub, len(ub))])
        b.append(roc_auc_score(y[ii], oof[n][ii]))
    ci.append({"model": n, "pooled_ROC_AUC": roc_auc_score(y, oof[n]), "ci95_low": np.percentile(b, 2.5),
               "ci95_high": np.percentile(b, 97.5)})
pd.DataFrame(ci).round(4).to_csv(f"{OUT}/pooled_auc_block_bootstrap.csv", index=False)
log(pd.DataFrame(ci).round(3).to_string(index=False))
log(f"[elapsed {time.time() - T0:.0f}s]")

# ---- parameters tuned on the whole main table ----------------------------------------
BX, bxs = tune("xgb", X, y, g10, N_TRIALS * 2)
BL, bls = tune("lgb", X, y, g10, N_TRIALS * 2)
save_json({"xgb": BX, "xgb_cv_auc": bxs, "lgb": BL, "lgb_cv_auc": bls, "by_fold": fold_params}, f"{OUT}/best_params.json")
log(f"Whole-table tuning: XGB {bxs:.4f} {BX}\n                    LGB {bls:.4f} {BL}")


# ---- experiments ------------------------------------------------------------------------
def run(label, tr_df, te_df, feats, groups_tr, group="E", splits=None, make=None):
    """Train on tr_df, test on te_df with folds defined on tr_df's block column."""
    make = make or (lambda: xgb_model(**BX))
    Xa = matrix(tr_df, feats).values.astype("float32")
    Xb = matrix(te_df, feats).values.astype("float32")
    ya, yb = tr_df.landslide.values, te_df.landslide.values
    splits = splits or folds(ya, tr_df[groups_tr].values)
    assign = {}
    for k, (_, tst) in enumerate(splits):
        for bk in tr_df[groups_tr].values[tst]:
            assign[bk] = k
    p = np.full(len(te_df), np.nan)
    aucs = []
    for k, (trn, tst) in enumerate(splits):
        m = make().fit(Xa[trn], ya[trn])
        mask = np.array([assign.get(b, -1) == k for b in te_df[groups_tr].values])
        if mask.sum() and 0 < yb[mask].sum() < mask.sum():
            p[mask] = m.predict_proba(Xb[mask])[:, 1]
            aucs.append(roc_auc_score(yb[mask], p[mask]))
    ok = np.isfinite(p)
    r = panel(yb[ok], p[ok], 0.5)
    rec = {"group": group, "experiment": label, "n_features": Xa.shape[1], "n_test": int(ok.sum()),
           "pos_share_test": float(yb[ok].mean()), "fold_mean_AUC": np.mean(aucs), "fold_sd_AUC": np.std(aucs),
           **{k: r[k] for k in ("ROC_AUC", "PR_AUC", "F1_macro", "F1_LS", "F1_NonLS", "MCC")}}
    log(f"  {group} {label:62s} AUC={rec['fold_mean_AUC']:.3f}+/-{rec['fold_sd_AUC']:.3f} F1m={rec['F1_macro']:.3f} MCC={rec['MCC']:.3f}")
    return rec


exp = []
log("\nE1 incremental factor groups (10 km blocks)")
c = TERRAIN + PHASE1
exp.append(run("corrected Phase 2 factors (terrain, LULC, faults, rain)", main, main, c, "block10", "E1"))
c = c + HYDRO
exp.append(run("+ real hydrology", main, main, c, "block10", "E1"))
c = c + SCALES
exp.append(run("+ multi-scale relief", main, main, c, "block10", "E1"))
c = c + SOIL
exp.append(run("+ soil", main, main, c, "block10", "E1"))
c = c + RIVER
exp.append(run("+ rivers", main, main, c, "block10", "E1"))
c = c + ROADS
exp.append(run("+ roads (all 25 factors)", main, main, c, "block10", "E1"))
c = c + GEOLOGY
exp.append(run("+ geology (all 28 factors)", main, main, c, "block10", "E1"))
if HAS_NDVI:
    exp.append(run("+ NDVI (26 factors)", main, main, c + ["ndvi_dry2021"], "block10", "E1"))

log("E2 negative controls and single groups (10 km blocks)")
main_xy = main.assign(px=main.row, py=main.col)
exp.append(run("coordinates only (row, col)", main_xy, main_xy, ["px", "py"], "block10", "E2"))
exp.append(run("distance to any road only", main, main, ["dist_road_any"], "block10", "E2"))
exp.append(run("roads only (3 layers)", main, main, ROADS, "block10", "E2"))
exp.append(run("all factors except roads", main, main, [f for f in ALL if f not in ROADS], "block10", "E2"))
exp.append(run("all factors except smooth regional fields", main, main,
               [f for f in ALL if f not in ("map", "max_precip", "dist_fault", *SOIL)], "block10", "E6"))
exp.append(run("all factors except LULC", main, main, [f for f in ALL if f != "lulc"], "block10", "E6"))

log("E3 validation design (all 25 factors)")
for km in (1, 5, 10, 20):
    exp.append(run(f"spatial blocks {km} km", main, main, ALL, f"block{km}", "E3"))
rs = list(StratifiedKFold(5, shuffle=True, random_state=SEED).split(X, y))
pr = np.zeros(len(y))
for a, b in rs:
    pr[b] = xgb_model(**BX).fit(X[a], y[a]).predict_proba(X[b])[:, 1]
r = panel(y, pr, 0.5)
exp.append({"group": "E3", "experiment": "random 5-fold (Phase 2 protocol; leaky, for comparison only)", "n_features": X.shape[1],
            "n_test": len(y), "pos_share_test": float(y.mean()), "fold_mean_AUC": r["ROC_AUC"], "fold_sd_AUC": np.nan,
            **{k: r[k] for k in ("ROC_AUC", "PR_AUC", "F1_macro", "F1_LS", "F1_NonLS", "MCC")}})
log(f"  E3 random 5-fold AUC={r['ROC_AUC']:.3f} F1m={r['F1_macro']:.3f}")

log("E4 road-matched negatives (survey-bias test)")
rm = full[full.set.isin(["pos", "neg_roadmatched"])].reset_index(drop=True)
NOROAD = [f for f in ALL if f not in ROADS]
exp.append(run("train+test road-matched, all factors", rm, rm, ALL, "block10", "E4"))
exp.append(run("train+test road-matched, no road factors", rm, rm, NOROAD, "block10", "E4"))
exp.append(run("train on random negatives, test on road-matched", main, rm, ALL, "block10", "E4"))
exp.append(run("train on random negatives (no roads), test on road-matched", main, rm, NOROAD, "block10", "E4"))

log("E5 sampling ratio (train 1:5)")
r15 = full[full.set.isin(["pos", "neg_random", "neg_pool"])].reset_index(drop=True)
spw = (r15.landslide == 0).sum() / (r15.landslide == 1).sum()
mk15 = lambda: xgb_model(**BX, scale_pos_weight=spw)
exp.append(run("train 1:5, test 1:5", r15, r15, ALL, "block10", "E5", make=mk15))
exp.append(run("train 1:5, test balanced 1:1", r15, r15[r15.set != "neg_pool"].reset_index(drop=True), ALL, "block10", "E5", make=mk15))
ex = pd.DataFrame(exp)
ex.round(4).to_csv(f"{OUT}/experiments.csv", index=False)
log(f"[elapsed {time.time() - T0:.0f}s]")

# ---- importance -----------------------------------------------------------------------------
perm, shap_abs = {c: [] for c in COLS}, np.zeros(X.shape[1])
FAM = {"roads": ROADS, "terrain": TERRAIN, "relief scales": SCALES, "hydrology": HYDRO, "land cover": [c for c in COLS if c.startswith("lulc")],
       "rain": ["map", "max_precip"], "faults": ["dist_fault"], "soil": SOIL, "rivers": RIVER,
       "geology": [c for c in COLS if c.startswith("lith_")] + ["dist_lineament", "lineament_density_1km"]}
fam_drop = {k: [] for k in FAM}
rng2 = np.random.default_rng(SEED)
import xgboost as xgbmod
fold_models = []
for k, (tr, te) in enumerate(outer):
    m = xgb_model(**BX).fit(X[tr], y[tr])
    fold_models.append(m)
    base = roc_auc_score(y[te], m.predict_proba(X[te])[:, 1])
    for j, c_ in enumerate(COLS):
        d = []
        for _ in range(5):
            Xp = X[te].copy()
            Xp[:, j] = Xp[rng2.permutation(len(te)), j]
            d.append(base - roc_auc_score(y[te], m.predict_proba(Xp)[:, 1]))
        perm[c_].append(np.mean(d))
    for fam, cols in FAM.items():
        idx = [COLS.index(c_) for c_ in cols]
        d = []
        for _ in range(5):
            Xp = X[te].copy()
            pm = rng2.permutation(len(te))
            Xp[:, idx] = Xp[pm][:, idx]
            d.append(base - roc_auc_score(y[te], m.predict_proba(Xp)[:, 1]))
        fam_drop[fam].append(np.mean(d))
    con = m.get_booster().predict(xgbmod.DMatrix(X[te], feature_names=None), pred_contribs=True)
    shap_abs += np.abs(con[:, :-1]).sum(axis=0)
pi = pd.DataFrame({"feature": COLS, "perm_auc_drop_mean": [np.mean(perm[c_]) for c_ in COLS],
                   "perm_auc_drop_sd": [np.std(perm[c_]) for c_ in COLS], "mean_abs_shap": shap_abs / len(y)})
pi = pi.sort_values("perm_auc_drop_mean", ascending=False)
pi.round(5).to_csv(f"{OUT}/feature_importance.csv", index=False)
pf = pd.DataFrame({"family": list(FAM), "perm_auc_drop_mean": [np.mean(v) for v in fam_drop.values()],
                   "perm_auc_drop_sd": [np.std(v) for v in fam_drop.values()]}).sort_values("perm_auc_drop_mean", ascending=False)
pf.round(4).to_csv(f"{OUT}/feature_family_importance.csv", index=False)
log("Permutation importance (AUC drop on spatial test folds):\n" + pi.head(12).round(4).to_string(index=False))
log(pf.round(4).to_string(index=False))

# ---- save fold models and final model --------------------------------------------------------
fold_of = {}
for k, (_, te) in enumerate(outer):
    for b in g10[te]:
        fold_of[int(b)] = k
pd.Series(fold_of, name="fold").rename_axis("block10").reset_index().to_csv(f"{MODELS_DIR}/block10_fold.csv", index=False)
final = xgb_model(**BX).fit(X, y)
thr_final = float(byfold[byfold.model == "XGBoost"].threshold.median())
joblib.dump(final, f"{MODELS_DIR}/final_xgboost.pkl")
joblib.dump(fold_models, f"{MODELS_DIR}/fold_models_xgboost.pkl")
save_json({"columns": COLS, "raster_features": ALL, "lulc_codes": LULC_CODES, "lith_codes": LITH_CODES, "threshold_macroF1": thr_final},
          f"{MODELS_DIR}/feature_list.json")

# ---- figures -----------------------------------------------------------------------------------
fig, axes = plt.subplots(1, 2, figsize=(10, 4.6))
cols = {"Logistic_Regression": C_GREY, "SVM_RBF": C_VIOLET, "Random_Forest": C_AQUA, "XGBoost": C_NEG, "LightGBM": "#eda100", names[-1]: C_POS}
for n in names:
    fpr, tpr, _ = roc_curve(y, oof[n])
    pp, rr, _ = precision_recall_curve(y, oof[n])
    axes[0].plot(fpr, tpr, lw=1.5, color=cols[n], label=f"{n.replace('_', ' ')} ({roc_auc_score(y, oof[n]):.3f})")
    axes[1].plot(rr, pp, lw=1.5, color=cols[n], label=n.replace("_", " "))
axes[0].plot([0, 1], [0, 1], ls="--", lw=0.8, color=INK2)
axes[1].axhline(y.mean(), ls="--", lw=0.8, color=INK2)
axes[0].set_xlabel("False positive rate"); axes[0].set_ylabel("True positive rate"); axes[0].set_title("ROC, pooled 10 km spatial out-of-fold")
axes[1].set_xlabel("Recall"); axes[1].set_ylabel("Precision (balanced set)"); axes[1].set_title("Precision-recall")
axes[0].legend(fontsize=7.5, loc="lower right")
fig.tight_layout(); fig.savefig(f"{OUT}/fig_roc_pr_nested.png"); plt.close(fig)

t = pi.head(15).iloc[::-1]
fig, ax = plt.subplots(figsize=(7, 5))
ax.barh(t.feature, t.perm_auc_drop_mean, xerr=t.perm_auc_drop_sd, color=C_NEG, height=0.6,
        error_kw={"ecolor": C_GREY, "lw": 1})
ax.set_xlabel("Loss of ROC-AUC when the factor is shuffled (spatial test folds)")
ax.set_title("What the model relies on outside its training blocks"); ax.grid(axis="y", visible=False)
fig.tight_layout(); fig.savefig(f"{OUT}/fig_permutation_importance.png"); plt.close(fig)
log(f"Step 10 complete [{time.time() - T0:.0f}s]")
