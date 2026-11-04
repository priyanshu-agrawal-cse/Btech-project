"""
Rasterize vector features to match the master DEM grid (30m, EPSG:32646).
This script creates:
1. Distance to Faults raster
2. Lithology class raster
3. Landslide Inventory target raster (binary 0/1)
"""
import os
import numpy as np
import geopandas as gpd
import rasterio
from rasterio.features import rasterize
from scipy.ndimage import distance_transform_edt
import pandas as pd

os.makedirs("data/processed/geology", exist_ok=True)
os.makedirs("data/processed/inventory", exist_ok=True)

master_dem_path = "data/derived/mizoram_dem_clipped_utm.tif"

print("Loading master grid...")
with rasterio.open(master_dem_path) as src:
    master_meta = src.meta.copy()
    master_transform = src.transform
    master_shape = (src.height, src.width)
    master_crs = src.crs

# 1. Distance to Faults
print("Processing Faults...")
faults_path = "data/raw/geology/mizoram_faults.geojson"
if os.path.exists(faults_path):
    faults = gpd.read_file(faults_path)
    if len(faults) > 0:
        faults_utm = faults.to_crs(master_crs)
        
        # Rasterize faults as 1s, background as 0s
        shapes = [(geom, 1) for geom in faults_utm.geometry]
        faults_raster = rasterize(
            shapes,
            out_shape=master_shape,
            transform=master_transform,
            fill=0,
            dtype='uint8'
        )
        
        # Calculate Euclidean distance to faults in pixels, then convert to meters
        print("Calculating distance transform...")
        # distance_transform_edt computes distance to 0, so we invert the binary raster
        distance_pixels = distance_transform_edt(faults_raster == 0)
        
        # Pixel size is 30m, so multiply by 30 to get meters
        distance_meters = distance_pixels * master_transform[0] 
        
        dist_meta = master_meta.copy()
        dist_meta.update(dtype='float32', nodata=-9999.0)
        
        # Apply NoData mask from DEM
        with rasterio.open(master_dem_path) as src:
            dem_data = src.read(1)
            distance_meters = np.where(dem_data == src.nodata, -9999.0, distance_meters).astype(np.float32)
            
        out_dist_path = "data/processed/geology/mizoram_distance_to_faults_30m.tif"
        with rasterio.open(out_dist_path, "w", **dist_meta) as dst:
            dst.write(distance_meters, 1)
        print(f"Saved {out_dist_path}")
    else:
        print("No faults found in GeoJSON.")
else:
    print(f"File not found: {faults_path}")


# 2. Lithology
print("\nProcessing Lithology...")
lith_path = "data/raw/geology/mizoram_lithology.geojson"
if os.path.exists(lith_path):
    lith = gpd.read_file(lith_path)
    if len(lith) > 0:
        lith_utm = lith.to_crs(master_crs)
        
        # Create a mapping of lithology classes to integers
        lith_classes = lith['lith'].unique()
        class_mapping = {name: i+1 for i, name in enumerate(lith_classes)}
        print(f"Lithology Mapping: {class_mapping}")
        
        # Save mapping for reference
        mapping_df = pd.DataFrame(list(class_mapping.items()), columns=["Lithology", "Class_ID"])
        mapping_df.to_csv("data/processed/geology/lithology_mapping.csv", index=False)
        
        shapes = [(geom, class_mapping[lith_name]) for geom, lith_name in zip(lith_utm.geometry, lith_utm['lith'])]
        
        lith_raster = rasterize(
            shapes,
            out_shape=master_shape,
            transform=master_transform,
            fill=0, # 0 will be nodata/unclassified
            dtype='uint8'
        )
        
        lith_meta = master_meta.copy()
        lith_meta.update(dtype='uint8', nodata=0)
        
        # Apply NoData mask from DEM
        with rasterio.open(master_dem_path) as src:
            dem_data = src.read(1)
            lith_raster = np.where(dem_data == src.nodata, 0, lith_raster).astype(np.uint8)
            
        out_lith_path = "data/processed/geology/mizoram_lithology_30m.tif"
        with rasterio.open(out_lith_path, "w", **lith_meta) as dst:
            dst.write(lith_raster, 1)
        print(f"Saved {out_lith_path}")
    else:
        print("No lithology polygons found in GeoJSON.")
else:
    print(f"File not found: {lith_path}")


# 3. Landslide Inventory
print("\nProcessing Landslide Inventory...")
inv_path = "data/raw/landslide_inventory/mizoram_landslides_coolr.geojson"
if os.path.exists(inv_path):
    inv = gpd.read_file(inv_path)
    if len(inv) > 0:
        inv_utm = inv.to_crs(master_crs)
        
        # Rasterize points. A point is infinitely small, so we buffer it slightly (e.g. 15m) to ensure it hits a pixel
        # Or we can just rasterize the point geometries directly, rasterize handles Points by burning the pixel they fall in.
        shapes = [(geom, 1) for geom in inv_utm.geometry]
        
        inv_raster = rasterize(
            shapes,
            out_shape=master_shape,
            transform=master_transform,
            fill=0,
            dtype='uint8'
        )
        
        inv_meta = master_meta.copy()
        inv_meta.update(dtype='uint8', nodata=255) # 255 for nodata to save space, 0 for no landslide, 1 for landslide
        
        # Apply NoData mask from DEM
        with rasterio.open(master_dem_path) as src:
            dem_data = src.read(1)
            inv_raster = np.where(dem_data == src.nodata, 255, inv_raster).astype(np.uint8)
            
        out_inv_path = "data/processed/inventory/mizoram_landslide_target_30m.tif"
        with rasterio.open(out_inv_path, "w", **inv_meta) as dst:
            dst.write(inv_raster, 1)
        print(f"Saved {out_inv_path}")
        print(f"Total landslide pixels: {np.sum(inv_raster == 1)}")
    else:
        print("No landslide points found in GeoJSON.")
else:
    print(f"File not found: {inv_path}")

print("\nVector rasterization complete!")
