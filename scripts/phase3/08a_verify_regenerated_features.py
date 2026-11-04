"""
Phase 3 / Step 08a — Check that regenerated rasters reproduce the dataset (DATA-026).

The large 30 m feature rasters were not stored after Session 1. They were
regenerated with scripts 02-05. Re-sampling them at every row/col of
FINAL_DATASET_v3.csv must return the stored values; any difference would mean
the map (made from rasters) and the model (trained on the CSV) use different data.

If an NDVI raster exists, it is sampled here and written to a NEW table
(FINAL_DATASET_v3_ndvi.csv); FINAL_DATASET_v3.csv is never modified.

Output: data/phase3/modeling/regeneration_check.csv, FINAL_DATASET_v3_ndvi.csv
"""

import os
import sys
import json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p3_common import FEAT_DIR, MOD_DIR, load_valid_mask, read_float, log

valid = load_valid_mask()
df = pd.read_csv(f"{MOD_DIR}/FINAL_DATASET_v3.csv")
feats = json.load(open(f"{MOD_DIR}/dataset_v3_summary.json"))["features"]
PHASE1 = {"lulc": "data/processed/lulc/mizoram_lulc_30m.tif",
          "map": "data/processed/rainfall/mean_annual_precip_30m.tif",
          "max_precip": "data/processed/rainfall/max_monthly_precip_30m.tif",
          "dist_fault": "data/processed/geology/mizoram_distance_to_faults_30m.tif"}

rows = []
for f in feats:
    path = PHASE1.get(f, f"{FEAT_DIR}/{f}.tif")
    a = read_float(path, valid)[df.row.values, df.col.values]
    b = df[f].values.astype("float32")
    both = np.isfinite(a) & np.isfinite(b)
    rows.append({"feature": f, "n": int(both.sum()), "max_abs_diff": float(np.abs(a[both] - b[both]).max()),
                 "nan_mismatch": int((np.isfinite(a) != np.isfinite(b)).sum())})
    log(f"  {rows[-1]}")
chk = pd.DataFrame(rows)
chk.to_csv(f"{MOD_DIR}/regeneration_check.csv", index=False)
log(f"Worst difference: {chk.max_abs_diff.max():.6g}; NaN mismatches: {chk.nan_mismatch.sum()}")
# Session 2 found that a regenerated stream network differs slightly between runs
# (dist_stream: 4 of 13,013 rows, max 12.6 m; hand: 1 row, 0.32 m; all other layers
# identical). Tolerance: under one cell for distance layers.
tol = {"dist_stream": 30.31, "hand": 1.0}
bad = [r["feature"] for r in rows if r["max_abs_diff"] > tol.get(r["feature"], 1e-3)]
if bad or chk.nan_mismatch.sum():
    raise SystemExit(f"Regenerated rasters do NOT reproduce FINAL_DATASET_v3.csv: {bad}")
log("Regeneration accepted within the documented tolerance.")

ndvi_path = f"{FEAT_DIR}/ndvi_dry2021.tif"
if os.path.exists(ndvi_path):
    out = df.copy()
    out["ndvi_dry2021"] = read_float(ndvi_path, valid)[df.row.values, df.col.values]
    out.to_csv(f"{MOD_DIR}/FINAL_DATASET_v3_ndvi.csv", index=False)
    log(f"NDVI added: missing={int(out.ndvi_dry2021.isna().sum())}; "
        f"mean landslide={out[out.landslide == 1].ndvi_dry2021.mean():.3f}; "
        f"mean random negative={out[out.set == 'neg_random'].ndvi_dry2021.mean():.3f}")
