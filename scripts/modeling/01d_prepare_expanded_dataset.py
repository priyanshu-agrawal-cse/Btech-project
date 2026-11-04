"""
Updated ML Dataset Preparation Script (uses expanded inventory)

This is an updated version of 01c_prepare_improved_dataset.py that:
- Uses the EXPANDED landslide inventory (multi-source, all years)
- Allows switching between Mizoram-only and NE India (transfer learning) mode
- Points to the new rasterized target file from 11_rasterize_expanded_inventory.py

Run this AFTER:
  python scripts/download/10_get_expanded_landslide_inventory.py
  python scripts/download/11_rasterize_expanded_inventory.py
  python scripts/modeling/01b_derive_advanced_features.py

Then continue with:
  python scripts/modeling/02b_train_advanced_models.py
  python scripts/modeling/03b_predict_map_improved.py
"""

import os
import numpy as np
import pandas as pd
import rasterio
from scipy.ndimage import binary_dilation

os.makedirs("data/processed/modeling", exist_ok=True)

# ============================================================
# CONFIGURATION — toggle between inventory versions
# ============================================================
USE_EXPANDED_TARGET = True   # True = use expanded multi-source inventory
                              # False = use original COOLR-only inventory

if USE_EXPANDED_TARGET:
    # Expanded: all years, multi-source, 90m buffer
    TARGET_FILE = "data/processed/inventory/mizoram_landslide_target_expanded_30m.tif"
    # Fall back to original if not yet rasterized
    if not os.path.exists(TARGET_FILE):
        print(f"WARNING: Expanded target not found. Run 11_rasterize_expanded_inventory.py first.")
        print("Falling back to original target.")
        TARGET_FILE = "data/processed/inventory/mizoram_landslide_target_30m.tif"
else:
    TARGET_FILE = "data/processed/inventory/mizoram_landslide_target_30m.tif"

print(f"Target file: {TARGET_FILE}")

# ---- Feature file paths -----------------------------------------------
feature_files = {
    # Original 9 features
    "elevation":    "data/derived/mizoram_dem_clipped_utm.tif",
    "slope":        "data/derived/mizoram_slope.tif",
    "aspect":       "data/derived/mizoram_aspect.tif",
    "curvature":    "data/derived/mizoram_curvature.tif",
    "lulc":         "data/processed/lulc/mizoram_lulc_30m.tif",
    "dist_fault":   "data/processed/geology/mizoram_distance_to_faults_30m.tif",
    "lithology":    "data/processed/geology/mizoram_lithology_30m.tif",
    "map":          "data/processed/rainfall/mean_annual_precip_30m.tif",
    "max_precip":   "data/processed/rainfall/max_monthly_precip_30m.tif",
    # Advanced morphometric (from 01b_derive_advanced_features.py)
    "twi":               "data/derived/mizoram_twi.tif",
    "tri":               "data/derived/mizoram_tri.tif",
    "tpi":               "data/derived/mizoram_tpi.tif",
    "profile_curvature": "data/derived/mizoram_profile_curvature.tif",
    "plan_curvature":    "data/derived/mizoram_plan_curvature.tif",
    "sin_aspect":        "data/derived/mizoram_sin_aspect.tif",
    "cos_aspect":        "data/derived/mizoram_cos_aspect.tif",
    "slope_curv_interact":"data/derived/mizoram_slope_curv_interact.tif",
}

NON_LS_SAMPLE_SIZE  = 50_000
EXCLUSION_BUFFER_PX = 5        # 150m around known landslide pixels
SMOTE_TARGET_N      = 500      # higher target now that we may have more real samples
RANDOM_SEED         = 42
np.random.seed(RANDOM_SEED)

# ===========================================================================
print("=" * 60)
print("STEP 1 — Reading target raster")
print("=" * 60)

with rasterio.open(feature_files["elevation"]) as src:
    dem_data   = src.read(1)
    dem_nodata = src.nodata if src.nodata is not None else -9999.0
    valid_area = (dem_data != dem_nodata) & ~np.isnan(dem_data)

with rasterio.open(TARGET_FILE) as src:
    target_data = src.read(1)

target_data = np.where(target_data == 255, 0, target_data)  # 255 = nodata -> 0

ls_mask = (target_data == 1) & valid_area
ls_rows, ls_cols = np.where(ls_mask)
ls_indices = list(zip(ls_rows.tolist(), ls_cols.tolist()))
n_ls = len(ls_indices)

print(f"  Valid pixels      : {valid_area.sum():,}")
print(f"  Landslide pixels  : {n_ls:,}  (original was 41)")

if n_ls == 0:
    raise ValueError("No landslide pixels found! Check target raster path.")

# ===========================================================================
print("\nSTEP 2 — Exclusion buffer around landslide pixels")
print("=" * 60)

exclusion_zone = binary_dilation(ls_mask.astype(bool), iterations=EXCLUSION_BUFFER_PX)
safe_non_ls    = (target_data == 0) & valid_area & ~exclusion_zone
non_ls_rows, non_ls_cols = np.where(safe_non_ls)
print(f"  Available non-LS after {EXCLUSION_BUFFER_PX}px buffer: {len(non_ls_rows):,}")

# ===========================================================================
print("\nSTEP 3 — Stratified slope-based non-LS sampling")
print("=" * 60)

with rasterio.open(feature_files["slope"]) as src:
    slope_data = src.read(1)

slope_vals = slope_data[non_ls_rows, non_ls_cols]
valid_cand = (slope_vals != -9999.0) & ~np.isnan(slope_vals)
candidate_rows = non_ls_rows[valid_cand]
candidate_cols = non_ls_cols[valid_cand]
slope_vals_c   = slope_vals[valid_cand]

n_strata   = 5
per_stratum = NON_LS_SAMPLE_SIZE // n_strata
pct_cuts    = np.percentile(slope_vals_c, np.linspace(0, 100, n_strata + 1))
pct_cuts[0]  = -np.inf
pct_cuts[-1] =  np.inf

sampled_rows, sampled_cols = [], []
for i in range(n_strata):
    lo, hi    = pct_cuts[i], pct_cuts[i + 1]
    in_st     = (slope_vals_c >= lo) & (slope_vals_c < hi)
    st_r, st_c = candidate_rows[in_st], candidate_cols[in_st]
    n         = min(per_stratum, len(st_r))
    idx       = np.random.choice(len(st_r), size=n, replace=False)
    sampled_rows.append(st_r[idx])
    sampled_cols.append(st_c[idx])
    print(f"  Stratum {i+1} ({lo:.1f}-{hi:.1f}deg): {len(st_r):,} avail, sampled {n}")

sampled_non_ls_rows = np.concatenate(sampled_rows)
sampled_non_ls_cols = np.concatenate(sampled_cols)
non_ls_indices      = list(zip(sampled_non_ls_rows.tolist(), sampled_non_ls_cols.tolist()))
print(f"  Total non-LS: {len(non_ls_indices):,}")

# ===========================================================================
print("\nSTEP 4 — Extracting feature values")
print("=" * 60)

all_indices = ls_indices + non_ls_indices
rows = [r for r, c in all_indices]
cols = [c for r, c in all_indices]

features = {
    "row":       rows,
    "col":       cols,
    "landslide": [1] * n_ls + [0] * len(non_ls_indices),
}
available_features = {}
for name, filepath in feature_files.items():
    if not os.path.exists(filepath):
        print(f"  SKIP (not found): {name}")
        continue
    with rasterio.open(filepath) as src:
        data = src.read(1)
        vals = data[rows, cols].astype("float32")
        nd   = src.nodata
        if nd is not None and data.dtype.kind == "f":
            vals = np.where(vals == nd, np.nan, vals)
        elif data.dtype.kind == "f":
            vals = np.where(vals == -9999.0, np.nan, vals)
    features[name]          = vals
    available_features[name] = True
    print(f"  Extracted: {name}")

df = pd.DataFrame(features)
pre = len(df)
df  = df.dropna()
print(f"\n  Rows before NaN drop : {pre:,}")
print(f"  Rows after  NaN drop : {len(df):,}")
print(f"  Class distribution:\n{df['landslide'].value_counts()}")

# Save classic (no SMOTE)
classic_out = "data/processed/modeling/landslide_dataset_classic.csv"
df.to_csv(classic_out, index=False)
print(f"\n  Classic dataset: {classic_out}")

# ===========================================================================
print("\nSTEP 5 — BorderlineSMOTE augmentation")
print("=" * 60)

try:
    from imblearn.over_sampling import BorderlineSMOTE

    feature_cols = [c for c in df.columns if c not in ("row", "col", "landslide")]
    X_all = df[feature_cols].values
    y_all = df["landslide"].values
    n_ls_real = int(y_all.sum())
    n_nls     = int((y_all == 0).sum())

    print(f"  Real LS samples: {n_ls_real}")

    if n_ls_real >= 6 and n_ls_real < SMOTE_TARGET_N:
        # sampling_strategy = desired_minority_N / majority_N
        sampling_strategy = SMOTE_TARGET_N / n_nls
        smote = BorderlineSMOTE(
            sampling_strategy=sampling_strategy,
            k_neighbors=min(5, n_ls_real - 1),
            random_state=RANDOM_SEED,
            kind="borderline-1"
        )
        X_res, y_res = smote.fit_resample(X_all, y_all)
        n_synth = int(y_res.sum()) - n_ls_real
        print(f"  Synthetic LS added: {n_synth} (total LS: {int(y_res.sum())})")
    elif n_ls_real >= SMOTE_TARGET_N:
        print(f"  Enough real samples ({n_ls_real}), skipping SMOTE.")
        X_res, y_res = X_all, y_all
    else:
        print(f"  Too few samples ({n_ls_real}) for SMOTE (need >=6). Skipping.")
        X_res, y_res = X_all, y_all

    df_aug = pd.DataFrame(X_res, columns=feature_cols)
    df_aug["landslide"] = y_res.astype(int)
    aug_out = "data/processed/modeling/landslide_dataset_augmented.csv"
    df_aug.to_csv(aug_out, index=False)
    print(f"  Augmented dataset: {aug_out}")
    print(f"  Final distribution:\n{df_aug['landslide'].value_counts()}")

except ImportError:
    print("  imbalanced-learn not installed. pip install imbalanced-learn")

# ===========================================================================
summary_path = "data/processed/modeling/dataset_summary.txt"
with open(summary_path, "w") as f:
    f.write("EXPANDED DATASET SUMMARY\n")
    f.write("=" * 50 + "\n\n")
    f.write(f"Target raster       : {TARGET_FILE}\n")
    f.write(f"Landslide pixels    : {n_ls}\n")
    f.write(f"Non-LS sampled      : {len(non_ls_indices):,}\n")
    f.write(f"Features ({len(available_features)}): {list(available_features.keys())}\n")
    f.write(f"Dataset shape       : {df.shape}\n")

print(f"\nSummary: {summary_path}")
print("Dataset preparation complete!")
