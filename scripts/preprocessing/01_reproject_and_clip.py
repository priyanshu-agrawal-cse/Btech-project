import os
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.mask import mask
import geopandas as gpd

os.makedirs("data/processed", exist_ok=True)
os.makedirs("data/derived", exist_ok=True)
os.makedirs("scripts/preprocessing", exist_ok=True)

input_dem = "data/raw/mizoram_dem_copernicus_30m.tif"
output_dem = "data/processed/mizoram_dem_utm46n.tif"
dst_crs = 'EPSG:32646' # UTM Zone 46N for Mizoram

print(f"Reprojecting DEM to {dst_crs}...")

if not os.path.exists(input_dem):
    print(f"Error: Input DEM {input_dem} not found. Run download script first.")
    exit(1)

with rasterio.open(input_dem) as src:
    transform, width, height = calculate_default_transform(
        src.crs, dst_crs, src.width, src.height, *src.bounds)
    kwargs = src.meta.copy()
    kwargs.update({
        'crs': dst_crs,
        'transform': transform,
        'width': width,
        'height': height
    })

    with rasterio.open(output_dem, 'w', **kwargs) as dst:
        for i in range(1, src.count + 1):
            reproject(
                source=rasterio.band(src, i),
                destination=rasterio.band(dst, i),
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=transform,
                dst_crs=dst_crs,
                resampling=Resampling.bilinear)

print("Reprojection complete. Now clipping to Mizoram boundary...")

# Read boundary and reproject to UTM Zone 46N
boundary = gpd.read_file("data/raw/mizoram_boundary.geojson")
boundary_utm = boundary.to_crs(dst_crs)

with rasterio.open(output_dem) as src:
    out_image, out_transform = mask(src, boundary_utm.geometry, crop=True)
    out_meta = src.meta.copy()
    
out_meta.update({"driver": "GTiff",
                 "height": out_image.shape[1],
                 "width": out_image.shape[2],
                 "transform": out_transform})

clipped_dem = "data/derived/mizoram_dem_clipped_utm.tif"
with rasterio.open(clipped_dem, "w", **out_meta) as dest:
    dest.write(out_image)

print(f"SUCCESS: Clipped UTM DEM saved to {clipped_dem}")
