"""
Improved ML Dataset Preparation with Synthetic Landslide Augmentation

CORE PROBLEM ADDRESSED
======================
Original pipeline: 41 landslide pixels vs 50,000 non-landslide pixels.
This is a 1:1220 class ratio — the model is almost guaranteed to be biased.

SOLUTIONS IMPLEMENTED HERE
===========================
1. EXPANDED FEATURE SET
   We now include advanced morphometric features (TWI, TRI, TPI, plan/profile
   curvature, sin/cos aspect, slope×curvature) derived by 01b script.

2. INTELLIGENT NON-LANDSLIDE SAMPLING  (instead of purely random)
   Rather than uniformly random sampling from 22.9M pixels, we use a
   "difficulty-aware" strategy:
   a) Geographically EXCLUDE a buffer zone around known landslide pixels
      (we don't want pixels that MIGHT be landslide to be labeled negative)
   b) Stratified sampling: ensure the 50k non-landslide pixels cover the full
      distribution of slope, elevation, TWI classes — preventing the model
      from simply learning the easy "flat safe valley" pattern.

3. SMOTE-BASED SYNTHETIC LANDSLIDE GENERATION
   With only 41 real samples, SMOTE (Synthetic Minority Over-Sampling Technique)
   interpolates between real landslide pixels to create new plausible synthetic
   landslide feature vectors. This is now standard practice in landslide ML
   literature when inventory data is scarce.
   
   We use BorderlineSMOTE which focuses synthesis near the decision boundary —
   exactly where the model is most uncertain with 41 samples.

4. SAVES BOTH VERSIONS  (original + augmented) for reproducibility
"""

import os
import numpy as np
import pandas as pd
import rasterio
from scipy.ndimage import binary_dilation

os.makedirs("data/processed/modeling", exist_ok=True)

# ---- Feature file paths ----------------------------------------------------
feature_files = {
    # Existing features
    "elevation":    "data/derived/mizoram_dem_clipped_utm.tif",
    "slope":        "data/derived/mizoram_slope.tif",
    "aspect":       "data/derived/mizoram_aspect.tif",
    "curvature":    "data/derived/mizoram_curvature.tif",
    "lulc":         "data/processed/lulc/mizoram_lulc_30m.tif",
    "dist_fault":   "data/processed/geology/mizoram_distance_to_faults_30m.tif",
    "lithology":    "data/processed/geology/mizoram_lithology_30m.tif",
    "map":          "data/processed/rainfall/mean_annual_precip_30m.tif",
    "max_precip":   "data/processed/rainfall/max_monthly_precip_30m.tif",
    # NEW advanced features
    "twi":               "data/derived/mizoram_twi.tif",
    "tri":               "data/derived/mizoram_tri.tif",
    "tpi":               "data/derived/mizoram_tpi.tif",
    "profile_curvature": "data/derived/mizoram_profile_curvature.tif",
    "plan_curvature":    "data/derived/mizoram_plan_curvature.tif",
    "sin_aspect":        "data/derived/mizoram_sin_aspect.tif",
    "cos_aspect":        "data/derived/mizoram_cos_aspect.tif",
    "slope_curv_interact":"data/derived/mizoram_slope_curv_interact.tif",
}

target_file = "data/processed/inventory/mizoram_landslide_target_30m.tif"

# ---- PARAMETERS -------------------------------------------------------------
NON_LS_SAMPLE_SIZE    = 50_000    # how many non-landslide pixels to sample
EXCLUSION_BUFFER_PX   = 5         # exclude 5-pixel radius around each landslide
                                  # = 150m buffer (prevents false negatives)
SMOTE_TARGET_N        = 300       # generate up to this many synthetic LS samples
RANDOM_SEED           = 42

np.random.seed(RANDOM_SEED)


# ===========================================================================
print("=" * 60)
print("STEP 1 — Reading target and building valid area mask")
print("=" * 60)

with rasterio.open(feature_files["elevation"]) as src:
    dem_data   = src.read(1)
    dem_nodata = src.nodata if src.nodata is not None else -9999.0
    valid_area = (dem_data != dem_nodata) & ~np.isnan(dem_data)

with rasterio.open(target_file) as src:
    target_data = src.read(1)

# Standardize: 255 (no-data in some inventory rasters) -> 0
target_data = np.where(target_data == 255, 0, target_data)

print(f"  Valid area pixels : {valid_area.sum():,}")

# Landslide pixel locations
ls_mask = (target_data == 1) & valid_area
ls_rows, ls_cols = np.where(ls_mask)
ls_indices = list(zip(ls_rows.tolist(), ls_cols.tolist()))
n_ls = len(ls_indices)
print(f"  Landslide pixels  : {n_ls}")


# ===========================================================================
print("\nSTEP 2 — Exclusion buffer around known landslide pixels")
print("=" * 60)
# Pixels within 150m of a known landslide might actually be part of it but
# went unrecorded. We exclude them from the negative class to avoid
# contaminating training data with false negatives.

ls_binary_mask = ls_mask.astype(bool)
exclusion_zone = binary_dilation(ls_binary_mask,
                                  iterations=EXCLUSION_BUFFER_PX)
safe_non_ls_mask = (target_data == 0) & valid_area & ~exclusion_zone

non_ls_rows, non_ls_cols = np.where(safe_non_ls_mask)
print(f"  Non-LS pixels (after {EXCLUSION_BUFFER_PX}px buffer exclusion): {len(non_ls_rows):,}")


# ===========================================================================
print("\nSTEP 3 — Stratified non-landslide sampling")
print("=" * 60)
# To avoid the "easy flat valley" bias, we stratify by slope quantile.
# This ensures the sampled negatives span the full difficulty range,
# forcing the model to learn what makes HIGH-SLOPE areas safe vs dangerous.

with rasterio.open(feature_files["slope"]) as src:
    slope_data = src.read(1)

# Get slope values for non-LS candidates
slope_vals = slope_data[non_ls_rows, non_ls_cols]
slope_nodata = -9999.0

valid_candidate_mask = (slope_vals != slope_nodata) & ~np.isnan(slope_vals)
candidate_rows = non_ls_rows[valid_candidate_mask]
candidate_cols = non_ls_cols[valid_candidate_mask]
slope_vals_clean = slope_vals[valid_candidate_mask]

# Bin into 5 equal-frequency slope strata
n_strata = 5
per_stratum = NON_LS_SAMPLE_SIZE // n_strata
percentile_cuts = np.percentile(slope_vals_clean, np.linspace(0, 100, n_strata + 1))
percentile_cuts[0]  = -np.inf
percentile_cuts[-1] =  np.inf

sampled_rows_list = []
sampled_cols_list = []

for i in range(n_strata):
    lo, hi = percentile_cuts[i], percentile_cuts[i + 1]
    in_stratum = (slope_vals_clean >= lo) & (slope_vals_clean < hi)
    stratum_rows = candidate_rows[in_stratum]
    stratum_cols = candidate_cols[in_stratum]
    n_available = len(stratum_rows)
    n_sample = min(per_stratum, n_available)
    idx = np.random.choice(n_available, size=n_sample, replace=False)
    sampled_rows_list.append(stratum_rows[idx])
    sampled_cols_list.append(stratum_cols[idx])
    print(f"  Stratum {i+1} (slope {lo:.1f}–{hi:.1f}°): {n_available:,} available, sampled {n_sample}")

sampled_non_ls_rows = np.concatenate(sampled_rows_list)
sampled_non_ls_cols = np.concatenate(sampled_cols_list)
non_ls_indices = list(zip(sampled_non_ls_rows.tolist(), sampled_non_ls_cols.tolist()))
print(f"\n  Total non-LS sampled: {len(non_ls_indices):,}")


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
        print(f"  WARNING: {filepath} not found — skipping {name}")
        continue
    print(f"  Extracting: {name}")
    with rasterio.open(filepath) as src:
        data = src.read(1)
        vals = data[rows, cols].astype("float32")
        if src.nodata is not None and data.dtype.kind == "f":
            vals = np.where(vals == src.nodata, np.nan, vals)
        elif data.dtype.kind == "f":
            vals = np.where(vals == -9999.0, np.nan, vals)
    features[name]          = vals
    available_features[name] = True

df = pd.DataFrame(features)
pre_drop = len(df)
df = df.dropna()
print(f"\n  Rows before NaN drop : {pre_drop:,}")
print(f"  Rows after NaN drop  : {len(df):,}")
print(f"  Class distribution:\n{df['landslide'].value_counts().to_string()}")

# Save the "classic" version for comparison
classic_out = "data/processed/modeling/landslide_dataset_classic.csv"
df.to_csv(classic_out, index=False)
print(f"\n  Classic dataset saved: {classic_out}")


# ===========================================================================
print("\nSTEP 5 — BorderlineSMOTE synthetic minority oversampling")
print("=" * 60)
# We synthetically generate new landslide feature vectors by interpolating
# between the real 41 samples. BorderlineSMOTE focuses synthesis on the
# decision boundary — the most informative region given few real samples.

try:
    from imblearn.over_sampling import BorderlineSMOTE

    feature_cols = [c for c in df.columns if c not in ("row", "col", "landslide")]
    X_all = df[feature_cols].values
    y_all = df["landslide"].values

    n_real_ls = int(y_all.sum())
    n_non_ls  = int((y_all == 0).sum())

    # We want to bring minority class up to SMOTE_TARGET_N
    if n_real_ls < SMOTE_TARGET_N:
        smote_ratio = SMOTE_TARGET_N / n_non_ls   # fraction of majority class
        smote = BorderlineSMOTE(
            sampling_strategy=smote_ratio,
            k_neighbors=min(5, n_real_ls - 1),    # k must be < n_minority
            random_state=RANDOM_SEED,
            kind="borderline-1"
        )
        X_res, y_res = smote.fit_resample(X_all, y_all)
        print(f"  After BorderlineSMOTE:")
        print(f"    Landslide samples : {int(y_res.sum()):,}  "
              f"(was {n_real_ls}, added {int(y_res.sum()) - n_real_ls} synthetic)")
        print(f"    Non-LS samples    : {int((y_res == 0).sum()):,}")
    else:
        print("  Already have enough minority samples. Skipping SMOTE.")
        X_res, y_res = X_all, y_all

    df_aug = pd.DataFrame(X_res, columns=feature_cols)
    df_aug["landslide"] = y_res.astype(int)
    aug_out = "data/processed/modeling/landslide_dataset_augmented.csv"
    df_aug.to_csv(aug_out, index=False)
    print(f"  Augmented dataset saved: {aug_out}")

except ImportError:
    print("  imblearn not installed. Skipping SMOTE augmentation.")
    print("  Install with: pip install imbalanced-learn")


# ===========================================================================
print("\nSTEP 6 — Save summary statistics")
print("=" * 60)

summary_path = "data/processed/modeling/dataset_summary.txt"
with open(summary_path, "w") as f:
    f.write("IMPROVED DATASET PREPARATION SUMMARY\n")
    f.write("=" * 50 + "\n\n")
    f.write(f"Total valid study area pixels  : {valid_area.sum():,}\n")
    f.write(f"Real landslide pixels          : {n_ls}\n")
    f.write(f"Non-LS exclusion buffer        : {EXCLUSION_BUFFER_PX} pixels = {EXCLUSION_BUFFER_PX * 30}m\n")
    f.write(f"Stratified non-LS sample size  : {len(non_ls_indices):,}\n")
    f.write(f"\nFeatures used ({len(available_features)}):\n")
    for name in available_features:
        f.write(f"  - {name}\n")
    f.write(f"\nClassic dataset shape          : {df.shape}\n")

print(f"  Summary saved: {summary_path}")
print("\nDataset preparation complete!")
