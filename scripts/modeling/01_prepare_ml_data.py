"""
Prepare Machine Learning Dataset

This script reads the aligned 30m rasters and extracts a sample
of pixels to create a training dataset. Since the full raster contains
over 22 million valid pixels, we extract all landslide pixels and a 
random sample of non-landslide pixels to avoid memory issues.
"""
import os
import numpy as np
import pandas as pd
import rasterio
import random

os.makedirs("data/processed/modeling", exist_ok=True)

feature_files = {
    "elevation": "data/derived/mizoram_dem_clipped_utm.tif",
    "slope": "data/derived/mizoram_slope.tif",
    "aspect": "data/derived/mizoram_aspect.tif",
    "curvature": "data/derived/mizoram_curvature.tif",
    "lulc": "data/processed/lulc/mizoram_lulc_30m.tif",
    "dist_fault": "data/processed/geology/mizoram_distance_to_faults_30m.tif",
    "lithology": "data/processed/geology/mizoram_lithology_30m.tif",
    "map": "data/processed/rainfall/mean_annual_precip_30m.tif",
    "max_precip": "data/processed/rainfall/max_monthly_precip_30m.tif"
}

target_file = "data/processed/inventory/mizoram_landslide_target_30m.tif"

print("Reading target raster and DEM mask...")
# First, get the valid study area mask from the DEM
with rasterio.open(feature_files["elevation"]) as src:
    dem_data = src.read(1)
    if src.nodata is not None:
        valid_area = (dem_data != src.nodata)
    else:
        valid_area = (dem_data != -9999.0) & ~np.isnan(dem_data)

with rasterio.open(target_file) as src:
    target_data = src.read(1)

# Ensure target_data only has 1s and 0s in the valid area
target_data = np.where(target_data == 255, 0, target_data)

# Find row, col indices of all landslide pixels
ls_rows, ls_cols = np.where((target_data == 1) & valid_area)
ls_indices = list(zip(ls_rows, ls_cols))
print(f"Total landslide pixels found: {len(ls_indices)}")

# Find row, col indices of non-landslide pixels (sample 50,000 to save memory and balance)
non_ls_rows, non_ls_cols = np.where((target_data == 0) & valid_area)
print(f"Total non-landslide pixels found: {len(non_ls_rows)}")

np.random.seed(42)
sample_size = min(50000, len(non_ls_rows))
print(f"Sampling {sample_size} non-landslide pixels...")

sample_idx = np.random.choice(len(non_ls_rows), size=sample_size, replace=False)
sampled_non_ls_rows = non_ls_rows[sample_idx]
sampled_non_ls_cols = non_ls_cols[sample_idx]

non_ls_indices = list(zip(sampled_non_ls_rows, sampled_non_ls_cols))

# Combine all indices we want to extract
all_indices = ls_indices + non_ls_indices
rows = [r for r, c in all_indices]
cols = [c for r, c in all_indices]

# Extract feature values for these specific pixels
features = {}
features['row'] = rows
features['col'] = cols
features['landslide'] = [1]*len(ls_indices) + [0]*len(non_ls_indices)

for name, filepath in feature_files.items():
    print(f"Extracting {name}...")
    if not os.path.exists(filepath):
        print(f"  WARNING: File not found: {filepath}. Skipping.")
        continue
    with rasterio.open(filepath) as src:
        data = src.read(1)
        # Extract values at our sampled rows/cols
        vals = data[rows, cols]
        
        # Handle nodata
        if src.nodata is not None and data.dtype.kind == 'f':
            vals = np.where(vals == src.nodata, np.nan, vals)
        elif data.dtype.kind == 'f':
            vals = np.where(vals == -9999.0, np.nan, vals)
            
        features[name] = vals

print("Creating DataFrame...")
df = pd.DataFrame(features)

initial_len = len(df)
df = df.dropna()
print(f"Dropped {initial_len - len(df)} rows containing NaN values.")

print(f"Final Dataset Shape: {df.shape}")
print(f"Landslide Class Distribution:\n{df['landslide'].value_counts()}")

out_csv = "data/processed/modeling/landslide_dataset.csv"
print(f"Saving to {out_csv}...")
df.to_csv(out_csv, index=False)

print("Dataset preparation complete!")
