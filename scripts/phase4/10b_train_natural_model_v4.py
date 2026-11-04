"""
Phase 4 / Task A5 — copy of Phase 3 step 10b with the GSI geology factors added (DATA-039).
Only the inputs, the factor list and the output folders differ from Phase 3.

Why: the all-factor model (step 10) scores ROC-AUC 0.945, but distance to a road
alone scores 0.914 and the model scores only 0.681 against negatives at the same
road distance. Its map mostly follows road corridors, which mixes real cut-slope
failures with the fact that GSI surveyed along roads.

This model answers a different question: how unstable is the TERRAIN itself?
  Factors: terrain, relief, hydrology, soil, rain, rivers, faults.
  Removed: all road layers, and LULC (built-up cells are largely roads and towns).

Three negative designs are compared with 10 km spatial CV, each tested on BOTH
kinds of negatives. Selection rule, fixed before seeing the results: choose the
design with the highest WORST-CASE AUC over the two test sets, because the map
must work both state-wide and within road corridors.
  N1 landslides vs random negatives
  N2 landslides vs road-matched negatives
  N3 landslides vs both (negatives weighted so the classes balance)

The chosen design then gets nested spatial CV (tuning and threshold inside the
training folds), fold models for the out-of-fold map, and a final model.

Outputs: data/phase4/modeling/results/natural_design_comparison.csv,
         natural_nested_metrics.csv, natural_feature_importance.csv;
         models/phase4/final_natural.pkl, fold_models_natural.pkl,
         feature_list_natural.json, block10_fold_natural.csv
"""

import os
import sys
import time
import warnings
import numpy as np
import pandas as pd
import joblib
import optuna
from xgboost import XGBClassifier
from sklearn.metrics import (roc_auc_score, average_precision_score, f1_score, precision_score,
                             recall_score, confusion_matrix, matthews_corrcoef)
from sklearn.model_selection import StratifiedGroupKFold

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "phase3")))
from p3_common import save_json, log, SEED
MOD_DIR, MODELS_DIR = "data/phase4/modeling", "models/phase4"
os.makedirs(MODELS_DIR, exist_ok=True)

warnings.filterwarnings("ignore")
optuna.logging.set_verbosity(optuna.logging.WARNING)
OUT = f"{MOD_DIR}/results"
NJ = int(os.environ.get("P3_NJOBS", "3"))
N_TRIALS = int(os.environ.get("P3_TRIALS", "25"))
T0 = time.time()

full = pd.read_csv(f"{MOD_DIR}/FINAL_DATASET_v4.csv")
LITH_CODES = [1, 2, 3, 4, 5, 6, 7]
for c_ in LITH_CODES:
    full[f"lith_{c_}"] = (full["lith_group"].values == c_).astype("float32")
NATURAL = ["elevation", "slope", "aspect_sin", "aspect_cos", "curv_profile", "curv_plan", "tpi_270m",
           "tpi_1km", "tpi_3km", "relief_1km", "twi", "spi_log", "dist_stream", "hand",
           "dist_fault", "map", "max_precip", "soil_clay_pct", "soil_sand_pct", "soil_bdod_gcm3",
           "dist_river_osm", "dist_lineament", "lineament_density_1km"] + [f"lith_{c_}" for c_ in LITH_CODES]


def sub(*sets):
    return full[full.set.isin(sets)].reset_index(drop=True)


def model(**p):
    d = dict(n_estimators=300, max_depth=4, learning_rate=0.03, subsample=0.8, colsample_bytree=0.7,
             tree_method="hist", n_jobs=NJ, random_state=SEED, eval_metric="logloss")
    d.update(p)
    return XGBClassifier(**d)


def folds(y, g, seed=SEED, k=5):
    return list(StratifiedGroupKFold(n_splits=k, shuffle=True, random_state=seed).split(np.zeros(len(y)), y, g))


def weights(df):
    """Weight negatives so that total negative weight equals total positive weight."""
    y = df.landslide.values
    return np.where(y == 1, 1.0, (y == 1).sum() / (y == 0).sum())


# ---- the same landslide folds for every design, so the designs are comparable --------
pos = sub("pos")
pos_folds = folds(np.ones(len(pos), int) * 0 + (np.arange(len(pos)) % 2), pos.block10.values)
fold_of = {}
for k, (_, te) in enumerate(pos_folds):
    for b in pos.block10.values[te]:
        fold_of[int(b)] = k
blocks = np.sort(full.block10.unique())
rng = np.random.default_rng(SEED)
for b in blocks:                      # blocks without landslides still need a fold
    fold_of.setdefault(int(b), int(rng.integers(0, 5)))
full["fold"] = full.block10.map(fold_of)

designs = {"N1 random negatives": ["pos", "neg_random"], "N2 road-matched negatives": ["pos", "neg_roadmatched"],
           "N3 both": ["pos", "neg_random", "neg_roadmatched"]}
tests = {"test on random negatives": ["pos", "neg_random"], "test on road-matched negatives": ["pos", "neg_roadmatched"]}
rows = []
for nm, sets in designs.items():
    tr = full[full.set.isin(sets)]
    scores = {t: [] for t in tests}
    for k in range(5):
        a = tr[tr.fold != k]
        m = model().fit(a[NATURAL].values, a.landslide.values, sample_weight=weights(a))
        for t, ts in tests.items():
            b = full[full.set.isin(ts) & (full.fold == k)]
            scores[t].append(roc_auc_score(b.landslide.values, m.predict_proba(b[NATURAL].values)[:, 1]))
    r = {"design": nm, **{t: np.mean(v) for t, v in scores.items()}, **{t + " SD": np.std(v) for t, v in scores.items()}}
    r["worst_case_AUC"] = min(np.mean(v) for v in scores.values())
    rows.append(r)
    log(f"{nm:30s} " + "  ".join(f"{t}={np.mean(v):.3f}" for t, v in scores.items()))
dc = pd.DataFrame(rows).sort_values("worst_case_AUC", ascending=False)
dc.round(4).to_csv(f"{OUT}/natural_design_comparison.csv", index=False)
best = dc.iloc[0].design
log(f"Selected by worst-case AUC: {best}")

# ---- nested spatial CV of the chosen design -------------------------------------------
train_sets = designs[best]
data = full[full.set.isin(train_sets)].reset_index(drop=True)
X, y, g, w, fk = (data[NATURAL].values.astype("float32"), data.landslide.values, data.block10.values,
                  weights(data), data.fold.values)


def tune(idx):
    inner = folds(y[idx], g[idx], seed=SEED + 1, k=3)

    def obj(t):
        p = dict(n_estimators=t.suggest_int("n_estimators", 150, 500, step=50),
                 max_depth=t.suggest_int("max_depth", 2, 6),
                 learning_rate=t.suggest_float("learning_rate", 0.01, 0.1, log=True),
                 subsample=t.suggest_float("subsample", 0.6, 1.0),
                 colsample_bytree=t.suggest_float("colsample_bytree", 0.5, 1.0),
                 reg_lambda=t.suggest_float("reg_lambda", 0.5, 20, log=True),
                 min_child_weight=t.suggest_int("min_child_weight", 1, 15))
        s = []
        for a, b in inner:
            ia, ib = idx[a], idx[b]
            s.append(roc_auc_score(y[ib], model(**p).fit(X[ia], y[ia], sample_weight=w[ia]).predict_proba(X[ib])[:, 1],
                                   sample_weight=w[ib]))
        return float(np.mean(s))

    st = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=SEED))
    st.optimize(obj, n_trials=N_TRIALS)
    return st.best_params


def threshold(yt, p, wt):
    grid = np.round(np.arange(0.2, 0.81, 0.01), 2)
    s = [f1_score(yt, (p >= t).astype(int), average="macro", sample_weight=wt, zero_division=0) for t in grid]
    return float(grid[int(np.argmax(s))])


res, fold_models = [], []
for k in range(5):
    tr, te = np.flatnonzero(fk != k), np.flatnonzero(fk == k)
    bp = tune(tr)
    ip = np.zeros(len(tr))
    for a, b in folds(y[tr], g[tr], seed=SEED + 2, k=3):
        ip[b] = model(**bp).fit(X[tr[a]], y[tr[a]], sample_weight=w[tr[a]]).predict_proba(X[tr[b]])[:, 1]
    thr = threshold(y[tr], ip, w[tr])
    m = model(**bp).fit(X[tr], y[tr], sample_weight=w[tr])
    fold_models.append(m)
    p = m.predict_proba(X[te])[:, 1]
    for t_name, ts in tests.items():
        b = full[full.set.isin(ts) & (full.fold == k)]
        pp = m.predict_proba(b[NATURAL].values)[:, 1]
        yy = b.landslide.values
        yh = (pp >= thr).astype(int)
        tn, fp, fn, tp = confusion_matrix(yy, yh, labels=[0, 1]).ravel()
        res.append({"fold": k, "test": t_name, "threshold": thr, "ROC_AUC": roc_auc_score(yy, pp),
                    "PR_AUC": average_precision_score(yy, pp), "F1_macro": f1_score(yy, yh, average="macro"),
                    "F1_LS": f1_score(yy, yh), "F1_NonLS": f1_score(1 - yy, 1 - yh),
                    "Precision_LS": precision_score(yy, yh, zero_division=0), "Recall_LS": recall_score(yy, yh),
                    "Recall_NonLS": recall_score(1 - yy, 1 - yh), "MCC": matthews_corrcoef(yy, yh),
                    "TP": int(tp), "FP": int(fp), "TN": int(tn), "FN": int(fn)})
    log(f"fold {k}: threshold {thr:.2f} [{time.time() - T0:.0f}s]")
rs = pd.DataFrame(res)
rs.round(4).to_csv(f"{OUT}/natural_nested_metrics.csv", index=False)
log(rs.groupby("test")[["ROC_AUC", "PR_AUC", "F1_macro", "F1_LS", "F1_NonLS", "MCC", "threshold"]].agg(["mean", "std"]).round(3).T.to_string())

# ---- importance, final model --------------------------------------------------------------
rng2 = np.random.default_rng(SEED)
drop = {f: [] for f in NATURAL}
for k, m in enumerate(fold_models):
    b = full[full.set.isin(tests["test on road-matched negatives"]) & (full.fold == k)]
    Xt, yt = b[NATURAL].values.astype("float32"), b.landslide.values
    base = roc_auc_score(yt, m.predict_proba(Xt)[:, 1])
    for j, f in enumerate(NATURAL):
        d = []
        for _ in range(5):
            Xp = Xt.copy()
            Xp[:, j] = Xp[rng2.permutation(len(Xt)), j]
            d.append(base - roc_auc_score(yt, m.predict_proba(Xp)[:, 1]))
        drop[f].append(np.mean(d))
imp = pd.DataFrame({"feature": NATURAL, "perm_auc_drop_mean": [np.mean(drop[f]) for f in NATURAL],
                    "perm_auc_drop_sd": [np.std(drop[f]) for f in NATURAL]}).sort_values("perm_auc_drop_mean", ascending=False)
imp.round(5).to_csv(f"{OUT}/natural_feature_importance.csv", index=False)
log(imp.head(10).round(4).to_string(index=False))

bp = tune(np.arange(len(y)))
final = model(**bp).fit(X, y, sample_weight=w)
joblib.dump(final, f"{MODELS_DIR}/final_natural.pkl")
joblib.dump(fold_models, f"{MODELS_DIR}/fold_models_natural.pkl")
pd.Series(fold_of, name="fold").rename_axis("block10").reset_index().to_csv(f"{MODELS_DIR}/block10_fold_natural.csv", index=False)
save_json({"columns": NATURAL, "raster_features": [f for f in NATURAL if not f.startswith("lith_")] + ["lith_group"],
           "lulc_codes": [], "lith_codes": LITH_CODES, "design": best,
           "threshold_macroF1": float(rs.threshold.median()), "params": bp}, f"{MODELS_DIR}/feature_list_natural.json")
log(f"Natural model complete [{time.time() - T0:.0f}s]")
