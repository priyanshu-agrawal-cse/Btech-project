"""
Phase 3 / Step 11 — State-wide prediction (DATA-029).

Produces two rasters from the models saved by step 10:
  data/final/mizoram_landslide_susceptibility_v3.tif
      final XGBoost trained on ALL landslides and negatives. This is the deliverable.
  data/phase3/maps/susceptibility_v3_spatial_oof.tif
      VALIDATION map: every 10 km block is predicted by the fold model that never
      saw that block. Blocks without samples are predicted by fold model 0.
      Used only to measure how the map performs on landslides it did not train on.

Values are a RELATIVE susceptibility score in [0, 1], not a probability of failure:
the model was trained on a 1:1 sample while real landslide pixels are 0.008 % of
the land. Values are rounded to 4 decimals. NoData = -9999.
"""

import os
import sys
import json
import time
import joblib
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import Window

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p3_common import FEAT_DIR, P3_DIR, MODELS_DIR, NODATA, load_valid_mask, master_profile, log

os.makedirs("data/final", exist_ok=True)
os.makedirs(f"{P3_DIR}/maps", exist_ok=True)
SUFFIX = os.environ.get("P3_MODEL_SUFFIX", "xgboost")     # "xgboost" = all factors; "natural" = no road/LULC factors
TAG = "" if SUFFIX == "xgboost" else f"_{SUFFIX}"
info = json.load(open(f"{MODELS_DIR}/feature_list{TAG}.json"))
COLS, FEATS, CODES = info["columns"], info["raster_features"], info["lulc_codes"]
final = joblib.load(f"{MODELS_DIR}/final_{SUFFIX}.pkl").get_booster()
fold_models = [m.get_booster() for m in joblib.load(f"{MODELS_DIR}/fold_models_{SUFFIX}.pkl")]
fold_df = pd.read_csv(f"{MODELS_DIR}/block10_fold{TAG}.csv")

PHASE1 = {"lulc": "data/processed/lulc/mizoram_lulc_30m.tif",
          "map": "data/processed/rainfall/mean_annual_precip_30m.tif",
          "max_precip": "data/processed/rainfall/max_monthly_precip_30m.tif",
          "dist_fault": "data/processed/geology/mizoram_distance_to_faults_30m.tif"}
srcs = {f: rasterio.open(PHASE1.get(f, f"{FEAT_DIR}/{f}.tif")) for f in FEATS}
valid = load_valid_mask()
H, W = valid.shape
BLK = 330
block_fold = np.zeros((H // BLK + 2, W // BLK + 2), dtype="int8")
for b, k in zip(fold_df.block10.values, fold_df.fold.values):
    block_fold[b // 10_000, b % 10_000] = k

prof = master_profile()
prof.update(dtype="float32", nodata=NODATA, count=1, compress="deflate", predictor=3,
            tiled=True, blockxsize=512, blockysize=512, BIGTIFF="IF_SAFER")
out_final = f"data/final/mizoram_landslide_susceptibility_v3{TAG}.tif"
out_oof = f"{P3_DIR}/maps/susceptibility_v3{TAG}_spatial_oof.tif"
SIZE = 1024
t0 = time.time()
done = 0
with rasterio.open(out_final, "w", **prof) as d1, rasterio.open(out_oof, "w", **prof) as d2:
    for r0 in range(0, H, SIZE):
        for c0 in range(0, W, SIZE):
            win = Window(c0, r0, min(SIZE, W - c0), min(SIZE, H - r0))
            m = valid[r0:r0 + win.height, c0:c0 + win.width]
            a = np.full(m.shape, NODATA, "float32")
            b = a.copy()
            if m.any():
                n = int(m.sum())
                data = {}
                for f in FEATS:
                    v = srcs[f].read(1, window=win)[m].astype("float32")
                    nd = srcs[f].nodata
                    if nd is not None:
                        v[v == nd] = np.nan
                    v[v == NODATA] = np.nan
                    data[f] = v
                X = np.empty((n, len(COLS)), "float32")
                for j, c in enumerate(COLS):
                    X[:, j] = (data["lulc"] == int(c[5:])).astype("float32") if c.startswith("lulc_") else data[c]
                a[m] = np.round(final.inplace_predict(X), 4)
                rr, cc = np.nonzero(m)
                fk = block_fold[(rr + r0) // BLK, (cc + c0) // BLK]
                pb = np.empty(n, "float32")
                for k, bst in enumerate(fold_models):
                    sel = fk == k
                    if sel.any():
                        pb[sel] = bst.inplace_predict(X[sel])
                b[m] = np.round(pb, 4)
                done += n
            d1.write(a, 1, window=win)
            d2.write(b, 1, window=win)
        log(f"  row {r0 + SIZE:5d}/{H}: {done:,} land cells, {time.time() - t0:.0f}s")
for s in srcs.values():
    s.close()
log(f"Saved {out_final} ({os.path.getsize(out_final) / 1e6:.1f} MB) and {out_oof} ({os.path.getsize(out_oof) / 1e6:.1f} MB)")
