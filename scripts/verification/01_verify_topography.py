import os
import rasterio
import numpy as np

def print_raster_stats(filepath, name):
    print(f"--- Verification for {name} ---")
    if not os.path.exists(filepath):
        print(f"ERROR: File not found: {filepath}")
        return None
    
    with rasterio.open(filepath) as src:
        data = src.read(1)
        nodata = src.nodata
        
        # Mask out nodata and NaNs
        if nodata is not None:
            valid_data = data[(data != nodata) & ~np.isnan(data)]
        else:
            valid_data = data[~np.isnan(data)]
            
        print(f"File: {filepath}")
        print(f"CRS: {src.crs.to_string() if src.crs else 'None'}")
        print(f"Resolution (pixel size): {src.res}")
        print(f"Dimensions: width={src.width}, height={src.height}")
        print(f"Bounds: {src.bounds}")
        print(f"NoData Value: {nodata}")
        
        if valid_data.size > 0:
            print(f"Min: {np.min(valid_data):.2f}")
            print(f"Max: {np.max(valid_data):.2f}")
            print(f"Mean: {np.mean(valid_data):.2f}")
        else:
            print("ERROR: No valid data found in raster.")
    print("\n")
    
    return {
        "crs": src.crs.to_string() if src.crs else "None",
        "res": src.res,
        "width": src.width,
        "height": src.height,
        "bounds": src.bounds,
        "nodata": nodata
    }

os.makedirs("scripts/verification", exist_ok=True)
os.makedirs("data/processed", exist_ok=True)

report_file = "data/processed/verification_report.txt"
import sys
sys.stdout = open(report_file, "w")

print("TOPOGRAPHIC PIPELINE VERIFICATION REPORT\n")

# 1. Check raw tiles
tile_dir = "data/raw/dem_tiles"
print("--- Verification for Original 8 Copernicus Tiles ---")
tiles = [f for f in os.listdir(tile_dir) if f.endswith('.tif')]
for t in sorted(tiles):
    print(f"Tile found: {t} (AWS Path: https://copernicus-dem-30m.s3.amazonaws.com/{t.replace('.tif','')}/{t})")
print("\n")

# 2. Check merged DEM
merged_dem = "data/raw/mizoram_dem_copernicus_30m.tif"
print_raster_stats(merged_dem, "Merged DEM (WGS84)")

# 3. Check clipped UTM DEM
clipped_dem = "data/derived/mizoram_dem_clipped_utm.tif"
meta_dem = print_raster_stats(clipped_dem, "Clipped DEM (UTM46N)")

# 4. Check derived products
slope = "data/derived/mizoram_slope.tif"
meta_slope = print_raster_stats(slope, "Slope")

aspect = "data/derived/mizoram_aspect.tif"
meta_aspect = print_raster_stats(aspect, "Aspect")

curvature = "data/derived/mizoram_curvature.tif"
meta_curv = print_raster_stats(curvature, "Curvature")

# 5. Verify alignment
print("--- Alignment Verification ---")
if meta_dem and meta_slope and meta_aspect and meta_curv:
    if (meta_dem['crs'] == meta_slope['crs'] == meta_aspect['crs'] == meta_curv['crs'] and
        meta_dem['res'] == meta_slope['res'] == meta_aspect['res'] == meta_curv['res'] and
        meta_dem['width'] == meta_slope['width'] == meta_aspect['width'] == meta_curv['width'] and
        meta_dem['height'] == meta_slope['height'] == meta_aspect['height'] == meta_curv['height'] and
        meta_dem['bounds'] == meta_slope['bounds'] == meta_aspect['bounds'] == meta_curv['bounds']):
        print("SUCCESS: Elevation, Slope, Aspect, and Curvature have perfectly identical CRS, extent, dimensions, and pixel alignment.")
    else:
        print("ERROR: Mismatch found in metadata between derived products!")
        
sys.stdout.close()
