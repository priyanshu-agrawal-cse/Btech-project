"""
Updated Susceptibility Map Generator

This script is a drop-in replacement for 03_predict_map.py that:
  - Loads the BEST model saved by 02b_train_advanced_models.py
  - Reads the feature order from models/feature_order.csv to guarantee
    features are fed in the exact same column order as training
  - Supports the EXPANDED feature set (TWI, TRI, TPI, etc.)
  - Falls back to models/random_forest.pkl if best_model.pkl not found

The block-by-block processing logic is identical to the original.
"""

import os
import numpy as np
import rasterio
import pandas as pd
import joblib
from rasterio.windows import Window
import warnings
warnings.filterwarnings("ignore")

os.makedirs("data/final", exist_ok=True)

# ---- Load model and scaler --------------------------------------------------
print("Loading best model and scaler...")

if os.path.exists("models/best_model.pkl"):
    model = joblib.load("models/best_model.pkl")
    print("  Loaded: models/best_model.pkl")
else:
    model = joblib.load("models/random_forest.pkl")
    print("  Loaded: models/random_forest.pkl (fallback)")

scaler = joblib.load("models/scaler.pkl")

# ---- Load feature order from training ---------------------------------------
feature_order_path = "models/feature_order.csv"
if os.path.exists(feature_order_path):
    feature_names = pd.read_csv(feature_order_path).iloc[:, 0].tolist()
    print(f"  Feature order loaded: {len(feature_names)} features")
else:
    # Fallback to original 9 features if no feature_order.csv found
    feature_names = [
        "elevation", "slope", "aspect", "curvature", "lulc",
        "dist_fault", "lithology", "map", "max_precip"
    ]
    print("  WARNING: feature_order.csv not found. Using original 9 features.")

print(f"  Features: {feature_names}")

# ---- Feature file map -------------------------------------------------------
# Maps feature name -> raster path.
# Add any new features derived by 01b script here.
FEATURE_FILE_MAP = {
    "elevation":         "data/derived/mizoram_dem_clipped_utm.tif",
    "slope":             "data/derived/mizoram_slope.tif",
    "aspect":            "data/derived/mizoram_aspect.tif",
    "curvature":         "data/derived/mizoram_curvature.tif",
    "lulc":              "data/processed/lulc/mizoram_lulc_30m.tif",
    "dist_fault":        "data/processed/geology/mizoram_distance_to_faults_30m.tif",
    "lithology":         "data/processed/geology/mizoram_lithology_30m.tif",
    "map":               "data/processed/rainfall/mean_annual_precip_30m.tif",
    "max_precip":        "data/processed/rainfall/max_monthly_precip_30m.tif",
    # Advanced morphometric features
    "twi":               "data/derived/mizoram_twi.tif",
    "tri":               "data/derived/mizoram_tri.tif",
    "tpi":               "data/derived/mizoram_tpi.tif",
    "profile_curvature": "data/derived/mizoram_profile_curvature.tif",
    "plan_curvature":    "data/derived/mizoram_plan_curvature.tif",
    "sin_aspect":        "data/derived/mizoram_sin_aspect.tif",
    "cos_aspect":        "data/derived/mizoram_cos_aspect.tif",
    "slope_curv_interact":"data/derived/mizoram_slope_curv_interact.tif",
}

# Only keep features that are in both feature_names AND have a known file path
feature_files = {}
missing = []
for name in feature_names:
    if name in FEATURE_FILE_MAP:
        path = FEATURE_FILE_MAP[name]
        if os.path.exists(path):
            feature_files[name] = path
        else:
            missing.append(f"{name} (file missing: {path})")
    else:
        missing.append(f"{name} (no path mapping)")

if missing:
    print("\nWARNING — Some features could not be located:")
    for m in missing:
        print(f"  - {m}")

# Final list of features that we can actually provide
available_features = [n for n in feature_names if n in feature_files]
print(f"\n  Features available for prediction: {len(available_features)}/{len(feature_names)}")

# ===========================================================================
# Setup output raster
# ===========================================================================
out_path = "data/final/mizoram_landslide_susceptibility_v2.tif"
print(f"\nCreating output raster: {out_path}")

# Open all feature sources
srcs = {name: rasterio.open(path) for name, path in feature_files.items()}
master = srcs["elevation"]

out_meta = master.meta.copy()
out_meta.update(dtype=rasterio.float32, nodata=-9999.0, compress="lzw")

dem_nodata = master.nodata if master.nodata is not None else -9999.0

blocks_done = 0
total_blocks = sum(1 for _ in master.block_windows(1))

with rasterio.open(out_path, "w", **out_meta) as dst:
    for ji, window in master.block_windows(1):
        blocks_done += 1
        if blocks_done % 500 == 0 or blocks_done == total_blocks:
            print(f"  Block {blocks_done}/{total_blocks} ({100*blocks_done/total_blocks:.1f}%)")

        # Read block for all available features
        block_data = {}
        for name in available_features:
            block_data[name] = srcs[name].read(1, window=window)

        h, w = block_data["elevation"].shape

        # Stack features in the correct order
        X_block = np.column_stack([
            block_data[name].ravel() for name in available_features
        ])

        # Valid pixel mask: not nodata in DEM, no NaN in any feature
        valid_mask = (block_data["elevation"].ravel() != dem_nodata)
        valid_mask &= ~np.isnan(block_data["elevation"].ravel())

        for i, name in enumerate(available_features):
            nodata_val = srcs[name].nodata
            if nodata_val is not None and srcs[name].dtypes[0] == "float32":
                valid_mask &= (X_block[:, i] != nodata_val)
            valid_mask &= ~np.isnan(X_block[:, i])

        out_block = np.full(h * w, -9999.0, dtype=np.float32)

        if np.any(valid_mask):
            X_valid = X_block[valid_mask]
            X_valid_scaled = scaler.transform(X_valid)
            probs = model.predict_proba(X_valid_scaled)[:, 1]
            out_block[valid_mask] = probs

        dst.write(out_block.reshape(h, w), 1, window=window)

for src in srcs.values():
    src.close()

print(f"\nSusceptibility map saved: {out_path}")
size_mb = os.path.getsize(out_path) / 1e6 if os.path.exists(out_path) else 0
print(f"File size: {size_mb:.1f} MB")
