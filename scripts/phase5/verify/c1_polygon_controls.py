"""
Phase 5 verification / C1 - is the +0.25 Test P gain real, or does it come from location? (DATA-044)

Test P rose from 0.672 to 0.923 when polygons were added to training, yet the v5 map scores
below v3 on unseen 2024 records. Polygons may be concentrated in a few map sheets, so a model
could learn "this region" instead of landslide conditions. Rainfall and soil fields are smooth
and can act as location codes. Controls, same model and parameters as 02_compare_v5.py:

  full        the 21 natural factors (should reproduce about 0.923 at 10 km)
  coords      row and column only: skill here is location, not landslide science
  regional    rain, soil, fault and river distance: smooth fields
  local       terrain and hydrology only, with no smooth regional field

Each set is repeated with wider blocks. Real terrain signal should survive wider blocks;
a location effect should fall as the test moves further from training polygons.

Output: data/phase5/verification/polygon_controls.csv
"""

import json
import os
import sys
import warnings

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold
from xgboost import XGBClassifier

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "phase3")))
from p3_common import grid_info, log

warnings.filterwarnings("ignore")
OUT = "data/phase5/verification"
os.makedirs(OUT, exist_ok=True)
NJ = int(os.environ.get("P3_NJOBS", "3"))
SEEDS = (1, 2, 3)

df = pd.read_csv("data/phase5/modeling/FINAL_DATASET_v5.csv")
nat = json.load(open("models/phase3/feature_list_natural.json"))
FEATS, PARAMS = nat["columns"], nat["params"]
REGIONAL = ["map", "max_precip", "soil_clay_pct", "soil_sand_pct", "soil_bdod_gcm3", "dist_fault", "dist_river_osm"]
LOCAL = [f for f in FEATS if f not in REGIONAL]
SETS = {"full": FEATS, "coords": ["row", "col"], "regional": REGIONAL, "local": LOCAL}

_, _, _, _, L = grid_info()
for km in (20, 30, 50):
    b = int(round(km * 1000 / L))
    df[f"blk{km}"] = (df.row // b) * 10_000 + (df.col // b)
df["blk10"] = df.block10

train_sets = ["pos", "neg_random", "neg_roadmatched", "pos_polygon", "neg_random_v5"]
v5 = df[df.set.isin(train_sets)].reset_index(drop=True)
gsi = v5[v5.set.isin(["pos", "neg_random", "neg_roadmatched"])].reset_index(drop=True)
tp = v5[v5.set.isin(["pos_polygon", "neg_random_v5"])].reset_index(drop=True)


def model():
    return XGBClassifier(tree_method="hist", n_jobs=NJ, random_state=42, eval_metric="logloss", **PARAMS)


def fit(d, feats):
    y = d.landslide.values
    w = np.where(y == 1, 1.0, (y == 1).sum() / (y == 0).sum())
    return model().fit(d[feats].values, y, sample_weight=w)


rows = []
for km in (10, 20, 30, 50):
    col = f"blk{km}"
    for name, feats in SETS.items():
        v, g = [], []
        for seed in SEEDS:
            sp = StratifiedGroupKFold(5, shuffle=True, random_state=seed)
            pv, pg = np.full(len(tp), np.nan), np.full(len(tp), np.nan)
            for tr, te in sp.split(v5[feats].values, v5.landslide.values, v5[col].values):
                tb, vb = set(v5[col].values[tr]), set(v5[col].values[te])
                mask = tp[col].isin(vb).values
                if not mask.any():
                    continue
                pv[mask] = fit(v5[v5[col].isin(tb)], feats).predict_proba(tp.loc[mask, feats].values)[:, 1]
                pg[mask] = fit(gsi[gsi[col].isin(tb)], feats).predict_proba(tp.loc[mask, feats].values)[:, 1]
            ok = np.isfinite(pv)
            v.append(roc_auc_score(tp.landslide.values[ok], pv[ok]))
            g.append(roc_auc_score(tp.landslide.values[ok], pg[ok]))
        rows.append({"block_km": km, "features": name, "n_features": len(feats), "test_p_gsi_only": round(np.mean(g), 4),
                     "test_p_with_polygons": round(np.mean(v), 4), "gain": round(np.mean(v) - np.mean(g), 4)})
        log(str(rows[-1]))
        pd.DataFrame(rows).to_csv(f"{OUT}/polygon_controls.csv", index=False)
log("C1 finished.")
