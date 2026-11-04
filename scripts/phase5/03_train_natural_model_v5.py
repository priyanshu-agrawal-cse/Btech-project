"""
Phase 5 — Task P1.4: Train Natural Model v5 with Mapped Polygons.

Trains the v5 natural model on all available natural-terrain rows:
- GSI landslides (pos, neg_random, neg_roadmatched)
- NGDR mapped polygons (pos_polygon, neg_random_v5)
Total rows: 8,445. Features: 21 natural terrain factors (no road/LULC factors).
Sample weights balance the positive and negative classes.

Outer 5-fold spatial CV on 10 km blocks.
Tuning: Optuna TPE with 25 trials (inner 3-fold spatial CV) for hyper-parameters.
Threshold: optimal macro-F1 on inner out-of-fold predictions.
Permutation feature importance calculated on held-out folds.
Final model trained on all 8,445 rows.

Outputs:
- models/phase5/final_natural_v5.pkl
- models/phase5/fold_models_natural_v5.pkl
- models/phase5/block10_fold_natural_v5.csv
- models/phase5/feature_list_natural_v5.json
- data/phase5/modeling/results/natural_v5_nested_metrics.csv
- data/phase5/modeling/results/natural_v5_feature_importance.csv
"""

import os
import sys
import time
import json
import warnings
import numpy as np
import pandas as pd
import joblib
import optuna
from xgboost import XGBClassifier
from sklearn.metrics import (roc_auc_score, average_precision_score, f1_score,
                             precision_score, recall_score, confusion_matrix, matthews_corrcoef)
from sklearn.model_selection import StratifiedGroupKFold

_P3_SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "phase3"))
if _P3_SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _P3_SCRIPT_DIR)

from p3_common import log, SEED, save_json

warnings.filterwarnings("ignore")
optuna.logging.set_verbosity(optuna.logging.WARNING)

MOD_DIR = "data/phase5/modeling"
OUT_RES = f"{MOD_DIR}/results"
MODELS_DIR = "models/phase5"
os.makedirs(OUT_RES, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)

NJ = int(os.environ.get("P3_NJOBS", "3"))
N_TRIALS = int(os.environ.get("P3_TRIALS", "25"))
T0 = time.time()

log("Loading FINAL_DATASET_v5.csv...")
full = pd.read_csv(f"{MOD_DIR}/FINAL_DATASET_v5.csv")

FEAT_JSON_P3 = "models/phase3/feature_list_natural.json"
nat_info = json.load(open(FEAT_JSON_P3))
NATURAL = nat_info["columns"]
log(f"Features ({len(NATURAL)} natural factors): {NATURAL}")

# Training pool: all 5 sets
TRAIN_SETS = ["pos", "neg_random", "neg_roadmatched", "pos_polygon", "neg_random_v5"]
data = full[full.set.isin(TRAIN_SETS)].copy().reset_index(drop=True)
log(f"Training dataset size: {len(data):,} rows")
log(f"Set composition:\n{data['set'].value_counts().to_string()}")

def model(**p):
    d = dict(n_estimators=300, max_depth=4, learning_rate=0.03, subsample=0.8, colsample_bytree=0.7,
             tree_method="hist", n_jobs=NJ, random_state=SEED, eval_metric="logloss")
    d.update(p)
    return XGBClassifier(**d)

def folds(y, g, seed=SEED, k=5):
    return list(StratifiedGroupKFold(n_splits=k, shuffle=True, random_state=seed).split(np.zeros(len(y)), y, g))

def weights(df):
    y = df.landslide.values
    return np.where(y == 1, 1.0, (y == 1).sum() / (y == 0).sum())

# Establish 5 outer spatial folds on 10 km blocks
pos_all = data[data.landslide == 1].reset_index(drop=True)
pos_folds = folds(np.arange(len(pos_all)) % 2, pos_all.block10.values, seed=SEED, k=5)
fold_of = {}
for k, (_, te) in enumerate(pos_folds):
    for b in pos_all.block10.values[te]:
        fold_of[int(b)] = k

blocks = np.sort(data.block10.unique())
rng = np.random.default_rng(SEED)
for b in blocks:
    fold_of.setdefault(int(b), int(rng.integers(0, 5)))

data["fold"] = data.block10.map(fold_of)
log(f"Assigned {len(blocks)} blocks into 5 spatial folds.")

X = data[NATURAL].values.astype("float32")
y = data.landslide.values
g = data.block10.values
w = weights(data)
fk = data.fold.values

def tune(idx):
    inner = folds(y[idx], g[idx], seed=SEED + 1, k=3)
    def obj(t):
        p = dict(n_estimators=t.suggest_int("n_estimators", 150, 500, step=50),
                 max_depth=t.suggest_int("max_depth", 2, 6),
                 learning_rate=t.suggest_float("learning_rate", 0.01, 0.1, log=True),
                 subsample=t.suggest_float("subsample", 0.6, 1.0),
                 colsample_bytree=t.suggest_float("colsample_bytree", 0.5, 1.0),
                 reg_lambda=t.suggest_float("reg_lambda", 0.5, 20.0, log=True),
                 min_child_weight=t.suggest_int("min_child_weight", 1, 15))
        s = []
        for a, b in inner:
            ia, ib = idx[a], idx[b]
            m = model(**p).fit(X[ia], y[ia], sample_weight=w[ia])
            s.append(roc_auc_score(y[ib], m.predict_proba(X[ib])[:, 1], sample_weight=w[ib]))
        return float(np.mean(s))

    st = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=SEED))
    st.optimize(obj, n_trials=N_TRIALS)
    return st.best_params

def threshold(yt, p, wt):
    grid = np.round(np.arange(0.2, 0.81, 0.01), 2)
    s = [f1_score(yt, (p >= t).astype(int), average="macro", sample_weight=wt, zero_division=0) for t in grid]
    return float(grid[int(np.argmax(s))])

log("\nRunning nested 5-fold spatial CV with tuning...")
res = []
fold_models = []

for k in range(5):
    t_f0 = time.time()
    tr, te = np.flatnonzero(fk != k), np.flatnonzero(fk == k)
    bp = tune(tr)
    
    # Inner out-of-fold predictions to find optimal threshold
    ip = np.zeros(len(tr))
    for a, b in folds(y[tr], g[tr], seed=SEED + 2, k=3):
        m_inner = model(**bp).fit(X[tr[a]], y[tr[a]], sample_weight=w[tr[a]])
        ip[b] = m_inner.predict_proba(X[tr[b]])[:, 1]
    
    thr = threshold(y[tr], ip, w[tr])
    m_outer = model(**bp).fit(X[tr], y[tr], sample_weight=w[tr])
    fold_models.append(m_outer)
    
    # Test on held-out fold
    pp = m_outer.predict_proba(X[te])[:, 1]
    yy = y[te]
    yh = (pp >= thr).astype(int)
    tn, fp, fn, tp = confusion_matrix(yy, yh, labels=[0, 1]).ravel()
    
    fold_res = {
        "fold": k,
        "threshold": thr,
        "ROC_AUC": roc_auc_score(yy, pp),
        "PR_AUC": average_precision_score(yy, pp),
        "F1_macro": f1_score(yy, yh, average="macro"),
        "F1_LS": f1_score(yy, yh),
        "F1_NonLS": f1_score(1 - yy, 1 - yh),
        "Precision_LS": precision_score(yy, yh, zero_division=0),
        "Recall_LS": recall_score(yy, yh),
        "Recall_NonLS": recall_score(1 - yy, 1 - yh),
        "MCC": matthews_corrcoef(yy, yh),
        "TP": int(tp), "FP": int(fp), "TN": int(tn), "FN": int(fn)
    }
    res.append(fold_res)
    log(f"Fold {k}: ROC-AUC={fold_res['ROC_AUC']:.4f}, Macro-F1={fold_res['F1_macro']:.4f}, "
        f"thr={thr:.2f} [{time.time() - t_f0:.1f}s]")

rs = pd.DataFrame(res)
rs.round(4).to_csv(f"{OUT_RES}/natural_v5_nested_metrics.csv", index=False)
log(f"\nNested CV Metrics Summary:")
log(rs[["ROC_AUC", "PR_AUC", "F1_macro", "F1_LS", "F1_NonLS", "MCC", "threshold"]].agg(["mean", "std"]).round(4).to_string())

# Permutation feature importance across outer folds
log("\nComputing permutation feature importance...")
rng2 = np.random.default_rng(SEED)
drop = {f: [] for f in NATURAL}
for k, m in enumerate(fold_models):
    te = np.flatnonzero(fk == k)
    Xt, yt = X[te], y[te]
    base = roc_auc_score(yt, m.predict_proba(Xt)[:, 1])
    for j, f in enumerate(NATURAL):
        d_perm = []
        for _ in range(5):
            Xp = Xt.copy()
            Xp[:, j] = Xp[rng2.permutation(len(Xt)), j]
            d_perm.append(base - roc_auc_score(yt, m.predict_proba(Xp)[:, 1]))
        drop[f].append(np.mean(d_perm))

imp = pd.DataFrame({
    "feature": NATURAL,
    "perm_auc_drop_mean": [np.mean(drop[f]) for f in NATURAL],
    "perm_auc_drop_sd": [np.std(drop[f]) for f in NATURAL]
}).sort_values("perm_auc_drop_mean", ascending=False)

imp.round(5).to_csv(f"{OUT_RES}/natural_v5_feature_importance.csv", index=False)
log("Top 10 features by permutation importance:")
log(imp.head(10).round(4).to_string(index=False))

# Final model tuning on all training rows
log(f"\nTraining final model on all {len(data):,} rows with {N_TRIALS} Optuna trials...")
bp_final = tune(np.arange(len(y)))
log(f"Best hyperparameters: {bp_final}")
final_model = model(**bp_final).fit(X, y, sample_weight=w)

joblib.dump(final_model, f"{MODELS_DIR}/final_natural_v5.pkl")
joblib.dump(fold_models, f"{MODELS_DIR}/fold_models_natural_v5.pkl")
pd.Series(fold_of, name="fold").rename_axis("block10").reset_index().to_csv(f"{MODELS_DIR}/block10_fold_natural_v5.csv", index=False)

save_json({
    "columns": NATURAL,
    "raster_features": NATURAL,
    "lulc_codes": [],
    "design": "GSI + Polygons v5 natural",
    "threshold_macroF1": float(rs.threshold.median()),
    "params": bp_final
}, f"{MODELS_DIR}/feature_list_natural_v5.json")

log(f"\nFinal model saved to {MODELS_DIR}/final_natural_v5.pkl")
log(f"Step 03 complete in {time.time() - T0:.1f}s.")
