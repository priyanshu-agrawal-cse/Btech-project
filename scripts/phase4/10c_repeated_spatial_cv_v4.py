"""
Phase 4 / Task A5-A6 — repeated spatial CV with the geology factors, and the A6 decision (DATA-039).

Copied from scripts/phase4/10c_repeated_spatial_cv.py. Inputs and outputs are all Phase 4.
A6, fixed in advance: adopt geology only if the natural model tested on road-matched
negatives gains at least 0.010 of mean ROC-AUC over the 0.702 baseline.
"""

import os
import sys
import json
import warnings
import numpy as np
import pandas as pd
from xgboost import XGBClassifier
from sklearn.metrics import roc_auc_score, f1_score, matthews_corrcoef
from sklearn.model_selection import StratifiedGroupKFold

_P3_SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "phase3"))
if _P3_SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _P3_SCRIPT_DIR)
from p3_common import log, SEED
MOD_DIR, MODELS_DIR = "data/phase4/modeling", "models/phase4"

warnings.filterwarnings("ignore")
OUT = f"{MOD_DIR}/results"
OUT_P4 = OUT
NJ = int(os.environ.get("P3_NJOBS", "3"))
full = pd.read_csv(f"{MOD_DIR}/FINAL_DATASET_v4.csv")
all_cols = json.load(open(f"{MODELS_DIR}/feature_list.json"))
nat = json.load(open(f"{MODELS_DIR}/feature_list_natural.json"))
BX = json.load(open(f"{OUT}/best_params.json"))["xgb"]
LULC = all_cols["lulc_codes"]
LITH = all_cols["lith_codes"]
ROADS = ["dist_road_any", "dist_road_major", "road_density_1km"]


def matrix(df, feats):
    X = df[[f for f in feats if f not in ("lulc", "lith_group")]].copy()
    if "lulc" in feats:
        for c in LULC:
            X[f"lulc_{c}"] = (df["lulc"].values == c).astype("float32")
    if "lith_group" in feats:
        for c in LITH:
            X[f"lith_{c}"] = (df["lith_group"].values == c).astype("float32")
    return X.values.astype("float32")


def model(p):
    return XGBClassifier(tree_method="hist", n_jobs=NJ, random_state=SEED, eval_metric="logloss", **p)


main = full[full.set.isin(["pos", "neg_random"])].reset_index(drop=True)
both = full[full.set.isin(["pos", "neg_random", "neg_roadmatched"])].reset_index(drop=True)
rm = full[full.set.isin(["pos", "neg_roadmatched"])].reset_index(drop=True)
A = all_cols["raster_features"]
CONFIGS = [("All 28 factors, random negatives", main, A, BX, main),
           ("All except roads, random negatives", main, [f for f in A if f not in ROADS], BX, main),
           ("Distance to road only", main, ["dist_road_any"], BX, main),
           ("Natural 24 factors, tested on random negatives", both, nat["raster_features"], nat["params"], main),
           ("Natural 24 factors, tested on road-matched negatives", both, nat["raster_features"], nat["params"], rm)]

rows = []
for name, train, feats, params, test in CONFIGS:
    Xtr, ytr, gtr = matrix(train, feats), train.landslide.values, train.block10.values
    w = np.where(ytr == 1, 1.0, (ytr == 1).sum() / (ytr == 0).sum())
    Xte, yte, gte = matrix(test, feats), test.landslide.values, test.block10.values
    for seed in range(1, 11):
        p = np.full(len(yte), np.nan)
        for a, b in StratifiedGroupKFold(5, shuffle=True, random_state=seed).split(Xtr, ytr, gtr):
            m = model(params).fit(Xtr[a], ytr[a], sample_weight=w[a])
            mask = np.isin(gte, np.unique(gtr[b]))
            p[mask] = m.predict_proba(Xte[mask])[:, 1]
        ok = np.isfinite(p)
        yh = (p[ok] >= 0.5).astype(int)
        rows.append({"config": name, "seed": seed, "ROC_AUC": roc_auc_score(yte[ok], p[ok]),
                     "F1_macro": f1_score(yte[ok], yh, average="macro"), "MCC": matthews_corrcoef(yte[ok], yh)})
    d = pd.DataFrame(rows).query("config == @name")
    log(f"{name:55s} ROC {d.ROC_AUC.mean():.3f} (SD {d.ROC_AUC.std():.3f}, {d.ROC_AUC.min():.3f}-{d.ROC_AUC.max():.3f})  "
        f"F1m {d.F1_macro.mean():.3f} (SD {d.F1_macro.std():.3f})  MCC {d.MCC.mean():.3f}")
r = pd.DataFrame(rows)
os.makedirs(OUT_P4, exist_ok=True)
r.round(4).to_csv(f"{OUT_P4}/repeated_spatial_cv_v4.csv", index=False)
s = r.groupby("config", sort=False)[["ROC_AUC", "F1_macro", "MCC"]].agg(["mean", "std", "min", "max"]).round(4)
s.to_csv(f"{OUT_P4}/repeated_spatial_cv_v4_summary.csv")
base = pd.read_csv("data/phase3/modeling/results/repeated_spatial_cv.csv")
b = base[base.config == "Natural 21 factors, tested on road-matched negatives"].sort_values("seed")
v = r[r.config == "Natural 24 factors, tested on road-matched negatives"].sort_values("seed")
gain_rule = v.ROC_AUC.mean() - 0.702
decision = {"baseline_rule": 0.702, "baseline_stored_mean": round(float(b.ROC_AUC.mean()), 4),
            "v4_mean": round(float(v.ROC_AUC.mean()), 4), "v4_sd": round(float(v.ROC_AUC.std()), 4),
            "gain_over_0.702": round(float(gain_rule), 4),
            "paired_gain_mean": round(float((v.ROC_AUC.values - b.ROC_AUC.values).mean()), 4),
            "seeds_better": int((v.ROC_AUC.values > b.ROC_AUC.values).sum()),
            "required_gain": 0.010, "adopt_geology": bool(gain_rule >= 0.010)}
with open(f"{OUT_P4}/a6_decision.json", "w") as f:
    json.dump(decision, f, indent=2)
log(f"A6 decision: {decision}")
log("Repeated spatial CV complete.")
