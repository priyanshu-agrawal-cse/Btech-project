"""
Phase 5 — Task P1.4: State-wide Prediction for v5 Natural Model.

Generates:
1. data/final/mizoram_landslide_susceptibility_v5_natural.tif
   Final model trained on all 8,445 rows.
2. data/phase5/maps/susceptibility_v5_natural_spatial_oof.tif
   Spatial out-of-fold validation map (each block predicted by model that never saw it).

Checks:
- Exactly 22,918,792 valid land cells
- Susceptibility values strictly within [0, 1]
- Exact alignment with master grid profile and CRS
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

_P3_SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "phase3"))
if _P3_SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _P3_SCRIPT_DIR)

from p3_common import FEAT_DIR, NODATA, load_valid_mask, master_profile, log

MODELS_DIR = "models/phase5"
OUT_FINAL = "data/final/mizoram_landslide_susceptibility_v5_natural.tif"
OUT_OOF = "data/phase5/maps/susceptibility_v5_natural_spatial_oof.tif"
os.makedirs("data/final", exist_ok=True)
os.makedirs("data/phase5/maps", exist_ok=True)

info = json.load(open(f"{MODELS_DIR}/feature_list_natural_v5.json"))
FEATS = info["raster_features"]
final = joblib.load(f"{MODELS_DIR}/final_natural_v5.pkl").get_booster()
fold_models = [m.get_booster() for m in joblib.load(f"{MODELS_DIR}/fold_models_natural_v5.pkl")]
fold_df = pd.read_csv(f"{MODELS_DIR}/block10_fold_natural_v5.csv")

PHASE1 = {
    "map": "data/processed/rainfall/mean_annual_precip_30m.tif",
    "max_precip": "data/processed/rainfall/max_monthly_precip_30m.tif",
    "dist_fault": "data/processed/geology/mizoram_distance_to_faults_30m.tif"
}

log("Opening feature raster sources...")
srcs = {f: rasterio.open(PHASE1.get(f, f"{FEAT_DIR}/{f}.tif")) for f in FEATS}
valid = load_valid_mask()
H, W = valid.shape
BLK = 330
block_fold = np.zeros((H // BLK + 2, W // BLK + 2), dtype="int8")
for b, k in zip(fold_df.block10.values, fold_df.fold.values):
    block_fold[b // 10_000, b % 10_000] = k

prof = master_profile()
prof.update(
    dtype="float32",
    nodata=NODATA,
    count=1,
    compress="deflate",
    predictor=3,
    tiled=True,
    blockxsize=512,
    blockysize=512,
    BIGTIFF="IF_SAFER"
)

SIZE = 1024
t0 = time.time()
done = 0
min_val_final, max_val_final = float("inf"), float("-inf")
min_val_oof, max_val_oof = float("inf"), float("-inf")

log("Starting windowed prediction across Mizoram...")
with rasterio.open(OUT_FINAL, "w", **prof) as d1, rasterio.open(OUT_OOF, "w", **prof) as d2:
    for r0 in range(0, H, SIZE):
        for c0 in range(0, W, SIZE):
            win = Window(c0, r0, min(SIZE, W - c0), min(SIZE, H - r0))
            m = valid[r0:r0 + win.height, c0:c0 + win.width]
            a = np.full(m.shape, NODATA, "float32")
            b = a.copy()
            if m.any():
                n = int(m.sum())
                X = np.empty((n, len(FEATS)), "float32")
                for j, f in enumerate(FEATS):
                    v = srcs[f].read(1, window=win)[m].astype("float32")
                    nd = srcs[f].nodata
                    if nd is not None:
                        v[v == nd] = np.nan
                    v[v == NODATA] = np.nan
                    X[:, j] = v

                pred_final = np.round(final.inplace_predict(X), 4)
                a[m] = pred_final
                min_val_final = min(min_val_final, float(np.nanmin(pred_final)))
                max_val_final = max(max_val_final, float(np.nanmax(pred_final)))

                rr, cc = np.nonzero(m)
                fk = block_fold[(rr + r0) // BLK, (cc + c0) // BLK]
                pb = np.empty(n, "float32")
                for k, bst in enumerate(fold_models):
                    sel = (fk == k)
                    if sel.any():
                        pb[sel] = bst.inplace_predict(X[sel])
                pred_oof = np.round(pb, 4)
                b[m] = pred_oof
                min_val_oof = min(min_val_oof, float(np.nanmin(pred_oof)))
                max_val_oof = max(max_val_oof, float(np.nanmax(pred_oof)))

                done += n
            d1.write(a, 1, window=win)
            d2.write(b, 1, window=win)
        log(f"  row {r0 + SIZE:5d}/{H}: {done:,} land cells, {time.time() - t0:.0f}s")

for s in srcs.values():
    s.close()

log(f"\nFinal map saved to {OUT_FINAL} ({os.path.getsize(OUT_FINAL) / 1e6:.1f} MB)")
log(f"OOF map saved to {OUT_OOF} ({os.path.getsize(OUT_OOF) / 1e6:.1f} MB)")

# Verification checks required by Section 4 (P1.4):
log("\n--- Verification Checks ---")
log(f"Land cells predicted: {done:,} (Expected: 22,918,792)")
assert done == 22918792, f"Cell count mismatch: got {done:,}, expected 22,918,792"
log("Check 1 PASSED: Exactly 22,918,792 land cells predicted.")

log(f"Final map value range: [{min_val_final:.4f}, {max_val_final:.4f}]")
assert min_val_final >= 0.0 and max_val_final <= 1.0, f"Final map value out of [0, 1] range!"
log("Check 2 PASSED: Final map values strictly within [0, 1].")

log(f"OOF map value range: [{min_val_oof:.4f}, {max_val_oof:.4f}]")
assert min_val_oof >= 0.0 and max_val_oof <= 1.0, f"OOF map value out of [0, 1] range!"
log("Check 3 PASSED: OOF map values strictly within [0, 1].")

# Master grid profile check
with rasterio.open(OUT_FINAL) as r:
    assert r.crs == prof["crs"], f"CRS mismatch: {r.crs} vs {prof['crs']}"
    assert r.transform == prof["transform"], f"Transform mismatch"
    assert (r.height, r.width) == (prof["height"], prof["width"]), f"Shape mismatch"
log("Check 4 PASSED: Master grid profile and CRS verified.")
log(f"Prediction completed in {time.time() - t0:.1f}s.")
