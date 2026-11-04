"""
Generate Final Landslide Susceptibility Map

This script uses the trained Random Forest model to predict
susceptibility probability for every pixel in the study area.
It processes the rasters block-by-block to avoid MemoryErrors.
"""
import os
import numpy as np
import rasterio
import joblib
from rasterio.windows import Window
import warnings
warnings.filterwarnings('ignore')

os.makedirs("data/final", exist_ok=True)

# 1. Load Model and Scaler
print("Loading model and scaler...")
model = joblib.load("models/random_forest.pkl")
scaler = joblib.load("models/scaler.pkl")

# 2. Define Features (MUST match training order!)
# In training, X was created by df.drop(columns=['landslide', 'row', 'col'])
# The columns were: elevation, slope, aspect, curvature, lulc, dist_fault, lithology, map, max_precip
feature_names = [
    "elevation", "slope", "aspect", "curvature", "lulc",
    "dist_fault", "lithology", "map", "max_precip"
]

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

# 3. Setup output raster
out_path = "data/final/mizoram_landslide_susceptibility.tif"
print(f"Creating output raster: {out_path}")

# Open all sources
srcs = {name: rasterio.open(path) for name, path in feature_files.items()}
master = srcs["elevation"]

out_meta = master.meta.copy()
out_meta.update(
    dtype=rasterio.float32,
    nodata=-9999.0,
    compress='lzw'
)

with rasterio.open(out_path, 'w', **out_meta) as dst:
    # Process block-by-block based on master DEM's blocks
    for ji, window in master.block_windows(1):
        # Read the block for all features
        block_data = {}
        for name in feature_names:
            data = srcs[name].read(1, window=window)
            block_data[name] = data
            
        # Get shape
        h, w = block_data["elevation"].shape
        
        # Flatten and stack features for prediction
        # Shape will be (n_pixels, n_features)
        X_block = np.column_stack([block_data[name].ravel() for name in feature_names])
        
        # Identify valid pixels (no NaNs, and not NoData in DEM)
        # Assuming DEM nodata is -9999.0 or None
        dem_nodata = master.nodata if master.nodata is not None else -9999.0
        
        # A pixel is valid if it doesn't contain NaN in any feature and isn't DEM nodata
        valid_mask = (block_data["elevation"].ravel() != dem_nodata)
        
        # Also check for NaNs in all features
        for name in feature_names:
            nodata_val = srcs[name].nodata
            if nodata_val is not None and srcs[name].dtypes[0] == 'float32':
                valid_mask &= (block_data[name].ravel() != nodata_val)
            valid_mask &= ~np.isnan(X_block[:, feature_names.index(name)])
            
        # Initialize output block with NoData
        out_block = np.full((h * w), -9999.0, dtype=np.float32)
        
        if np.any(valid_mask):
            # Extract valid pixels
            X_valid = X_block[valid_mask]
            
            # Scale
            X_valid_scaled = scaler.transform(X_valid)
            
            # Predict probability of class 1 (landslide)
            probs = model.predict_proba(X_valid_scaled)[:, 1]
            
            # Place back into output block
            out_block[valid_mask] = probs
            
        # Reshape and write
        out_block = out_block.reshape((h, w))
        dst.write(out_block, 1, window=window)
        
    print("Finished predicting all blocks.")

for src in srcs.values():
    src.close()

print(f"Final Susceptibility Map saved to {out_path}!")
