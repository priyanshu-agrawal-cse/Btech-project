import rasterio
import os
import sys

master_dem = "data/derived/mizoram_dem_clipped_utm.tif"

test_files = [
    "data/derived/mizoram_slope.tif",
    "data/derived/mizoram_aspect.tif",
    "data/derived/mizoram_curvature.tif",
    "data/processed/lulc/mizoram_lulc_30m.tif",
    "data/processed/geology/mizoram_distance_to_faults_30m.tif",
    "data/processed/geology/mizoram_lithology_30m.tif",
    "data/processed/inventory/mizoram_landslide_target_30m.tif",
    "data/processed/rainfall/mean_annual_precip_30m.tif",
    "data/processed/rainfall/max_monthly_precip_30m.tif"
]

print(f"--- Verification for Master DEM ---")
with rasterio.open(master_dem) as src:
    master_crs = src.crs
    master_transform = src.transform
    master_shape = (src.height, src.width)
    master_bounds = src.bounds
    print(f"File: {master_dem}")
    print(f"CRS: {master_crs}")
    print(f"Dimensions: {master_shape}")
    print(f"Bounds: {master_bounds}")
    print("\n")

all_match = True

for file in test_files:
    print(f"--- Verification for {os.path.basename(file)} ---")
    if not os.path.exists(file):
        print(f"ERROR: File not found: {file}\n")
        all_match = False
        continue
        
    with rasterio.open(file) as src:
        crs = src.crs
        transform = src.transform
        shape = (src.height, src.width)
        bounds = src.bounds
        
        print(f"CRS: {crs}")
        print(f"Dimensions: {shape}")
        print(f"Bounds: {bounds}")
        
        if crs != master_crs:
            print(f"  -> MISMATCH: CRS {crs} != {master_crs}")
            all_match = False
        if shape != master_shape:
            print(f"  -> MISMATCH: Dimensions {shape} != {master_shape}")
            all_match = False
        if bounds != master_bounds:
            print(f"  -> MISMATCH: Bounds {bounds} != {master_bounds}")
            all_match = False
        print("\n")

if all_match:
    print("SUCCESS: All layers are perfectly aligned with the master DEM!")
    sys.exit(0)
else:
    print("FAILED: One or more layers do not match the master DEM.")
    sys.exit(1)
