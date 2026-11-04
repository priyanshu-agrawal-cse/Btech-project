"""
Phase 5 verification / C4 - Test P with location removed (DATA-045).

Test P compares polygons, 91 % of which sit in 3 map sheets, with negatives from the whole
state, so a model can score well by knowing the place. Here the negatives come from the same
10 km blocks as the polygons, so the score reflects terrain, not location. Folds are the same
design as 02_compare_v5.py. New negatives are used for testing only, never for training.

Also measures how much of each map's Very High zone falls inside the polygon blocks.
Outputs: data/phase5/verification/same_area_test.csv, map_footprint_check.csv
"""

import json
import os
import sys
import warnings

import numpy as np
import pandas as pd
import rasterio
from scipy import ndimage
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold
from xgboost import XGBClassifier

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "phase3")))
from p3_common import FEAT_DIR, grid_info, load_valid_mask, log, read_float

warnings.filterwarnings("ignore")
OUT = "data/phase5/verification"
NJ = int(os.environ.get("P3_NJOBS", "3"))
tr, crs, H, W, L = grid_info()
valid = load_valid_mask()
df = pd.read_csv("data/phase5/modeling/FINAL_DATASET_v5.csv")
nat = json.load(open("models/phase3/feature_list_natural.json"))
FEATS, PARAMS = nat["columns"], nat["params"]
REGIONAL = ["map", "max_precip", "soil_clay_pct", "soil_sand_pct", "soil_bdod_gcm3", "dist_fault", "dist_river_osm"]
LOCAL = [f for f in FEATS if f not in REGIONAL]

b = int(round(10 * 1000 / L))
poly = df[df.set == "pos_polygon"]
blocks = set(poly.block10.unique())
counts = poly.block10.value_counts()
log(f"Polygons fall in {len(blocks)} of {df.block10.nunique()} sampled 10 km blocks; top 5 blocks hold {counts.iloc[:5].sum() / len(poly):.1%}")

rr, cc = np.indices((H, W), dtype="int32")
in_blocks = np.isin(rr // b * 10_000 + cc // b, list(blocks)) & valid
del rr, cc
pos = df[df.landslide == 1]
mark = np.zeros((H, W), bool)
mark[pos.row.values, pos.col.values] = True
cand = in_blocks & ~ndimage.binary_dilation(mark, iterations=5)
del mark
idx = np.flatnonzero(cand.ravel())
rng = np.random.default_rng(43)
pick = rng.choice(idx, size=min(4000, idx.size), replace=False)
neg = pd.DataFrame({"row": pick // W, "col": pick % W})
neg["block10"] = neg.row // b * 10_000 + neg.col // b
neg["landslide"] = 0
log(f"Same-area negatives: {len(neg)} from {idx.size:,} candidate cells")
P1 = {"map": "data/processed/rainfall/mean_annual_precip_30m.tif", "max_precip": "data/processed/rainfall/max_monthly_precip_30m.tif",
      "dist_fault": "data/processed/geology/mizoram_distance_to_faults_30m.tif"}
for f in FEATS:
    a = read_float(P1.get(f, f"{FEAT_DIR}/{f}.tif"), valid)
    neg[f] = a[neg.row.values, neg.col.values]
    del a
test = pd.concat([poly[["row", "col", "block10", "landslide"] + FEATS], neg], ignore_index=True)

sets = ["pos", "neg_random", "neg_roadmatched", "pos_polygon", "neg_random_v5"]
v5 = df[df.set.isin(sets)].reset_index(drop=True)
gsi = v5[v5.set.isin(["pos", "neg_random", "neg_roadmatched"])].reset_index(drop=True)


def fit(d, feats):
    y = d.landslide.values
    w = np.where(y == 1, 1.0, (y == 1).sum() / (y == 0).sum())
    return XGBClassifier(tree_method="hist", n_jobs=NJ, random_state=42, eval_metric="logloss", **PARAMS).fit(d[feats].values, y, sample_weight=w)


rows = []
for name, feats in (("full 21 factors", FEATS), ("local terrain only", LOCAL), ("coordinates only", ["row", "col"])):
    pv, pg = [], []
    for seed in (1, 2, 3):
        a, c = np.full(len(test), np.nan), np.full(len(test), np.nan)
        for t, te in StratifiedGroupKFold(5, shuffle=True, random_state=seed).split(v5[FEATS].values, v5.landslide.values, v5.block10.values):
            tb, vb = set(v5.block10.values[t]), set(v5.block10.values[te])
            m = test.block10.isin(vb).values
            if m.any():
                a[m] = fit(v5[v5.block10.isin(tb)], feats).predict_proba(test.loc[m, feats].values)[:, 1]
                c[m] = fit(gsi[gsi.block10.isin(tb)], feats).predict_proba(test.loc[m, feats].values)[:, 1]
        ok = np.isfinite(a)
        pv.append(roc_auc_score(test.landslide.values[ok], a[ok]))
        pg.append(roc_auc_score(test.landslide.values[ok], c[ok]))
    rows.append({"features": name, "gsi_only": round(np.mean(pg), 4), "with_polygons": round(np.mean(pv), 4), "gain": round(np.mean(pv) - np.mean(pg), 4)})
    log(str(rows[-1]))
for f in ("slope", "elevation", "aspect_cos", "relief_1km"):
    s = roc_auc_score(test.landslide.values, test[f].fillna(test[f].median()).values)
    rows.append({"features": f"{f} alone, no model", "gsi_only": np.nan, "with_polygons": round(s, 4), "gain": np.nan})
pd.DataFrame(rows).to_csv(f"{OUT}/same_area_test.csv", index=False)
log(pd.DataFrame(rows).to_string(index=False))

m = []
share = in_blocks.sum() / valid.sum() * 100
for nm, p in (("Natural v5", "data/final/mizoram_landslide_zones_v5_natural.tif"), ("Natural v3", "data/final/mizoram_landslide_zones_v3_natural.tif")):
    with rasterio.open(p) as s:
        z = s.read(1)
    vh = z == 5
    m.append({"map": nm, "polygon_blocks_share_of_land_pct": round(share, 2),
              "very_high_share_of_land_pct": round(vh[valid].mean() * 100, 2),
              "very_high_inside_polygon_blocks_pct": round(vh[in_blocks].sum() / vh[valid].sum() * 100, 2),
              "very_high_rate_inside_blocks_pct": round(vh[in_blocks].mean() * 100, 2),
              "very_high_rate_outside_blocks_pct": round(vh[valid & ~in_blocks].mean() * 100, 2)})
pd.DataFrame(m).to_csv(f"{OUT}/map_footprint_check.csv", index=False)
log(pd.DataFrame(m).T.to_string())
log("C4 finished.")
