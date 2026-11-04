import rasterio
import numpy as np
import geopandas as gpd
from rasterio.mask import mask

print("Verifying 0m elevation pixels and Copernicus metadata...")

dem_path = "data/derived/mizoram_dem_clipped_utm.tif"
boundary_path = "data/raw/mizoram_boundary.geojson"

# Load boundary to get exact polygon
boundary = gpd.read_file(boundary_path)

with rasterio.open(dem_path) as src:
    data = src.read(1)
    nodata = src.nodata
    
    # 1. Count 0m pixels
    zero_mask = (data == 0)
    zero_count = np.sum(zero_mask)
    total_pixels = data.size
    print(f"Total pixels: {total_pixels}")
    print(f"Pixels with exactly 0.00m elevation: {zero_count} ({(zero_count/total_pixels)*100:.2f}%)")
    
    # 2. Re-mask strictly with the boundary to see if 0s are inside or outside
    boundary_utm = boundary.to_crs(src.crs)
    # create a boolean mask of the polygon
    out_image, _ = mask(src, boundary_utm.geometry, crop=False, filled=False)
    # out_image is a masked array where True means OUTSIDE the polygon
    polygon_mask = out_image.mask[0] # True for outside, False for inside
    
    zeros_outside = np.sum(zero_mask & polygon_mask)
    zeros_inside = np.sum(zero_mask & ~polygon_mask)
    
    print(f"0m pixels outside state boundary (artifact of masking): {zeros_outside}")
    print(f"0m pixels INSIDE state boundary (true elevation anomaly): {zeros_inside}")
    
    # 3. Calculate true min/max/mean ignoring 0s outside boundary
    valid_data = data[~polygon_mask]
    if nodata is not None:
        valid_data = valid_data[valid_data != nodata]
    
    print(f"True Elevation Inside Mizoram -> Min: {np.min(valid_data):.2f}m, Max: {np.max(valid_data):.2f}m, Mean: {np.mean(valid_data):.2f}m")

print("\nCopernicus Metadata:")
print("Product: Copernicus DEM GLO-30 (Global 30m)")
print("Source: AWS Open Data Registry (s3://copernicus-dem-30m/)")
print("Type: DSM (Digital Surface Model). Note: Like SRTM, Copernicus is a surface model. While it includes canopy heights, it is the highest quality global 30m dataset available and is standard for regional landslide susceptibility.")
