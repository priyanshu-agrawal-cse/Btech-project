"""
Download ESA WorldCover 2021 (10m) for Mizoram via STAC API.
"""
import os
import geopandas as gpd
from pystac_client import Client
import planetary_computer
import rasterio
from rasterio.merge import merge
from rasterio.warp import reproject, Resampling, calculate_default_transform
from rasterio.mask import mask
import numpy as np
import warnings
warnings.filterwarnings('ignore')

os.makedirs("data/raw/lulc", exist_ok=True)
os.makedirs("data/processed/lulc", exist_ok=True)

# 1. Load Mizoram Boundary
boundary_path = "data/raw/mizoram_boundary.geojson"
boundary = gpd.read_file(boundary_path)
boundary_wgs = boundary.to_crs(epsg=4326)
bbox = tuple(boundary_wgs.total_bounds)

# 2. Search STAC for ESA WorldCover 2021
print(f"Searching ESA WorldCover 2021 for bbox: {bbox}")
catalog = Client.open(
    "https://planetarycomputer.microsoft.com/api/stac/v1",
    modifier=planetary_computer.sign_inplace,
)

search = catalog.search(
    collections=["esa-worldcover"],
    bbox=bbox,
)
items = list(search.items())
print(f"Found {len(items)} WorldCover tiles.")

# 3. Download tiles
downloaded_tiles = []
for i, item in enumerate(items):
    # WorldCover has 2020 (v100) and 2021 (v200). 
    # STAC query returns all. Filter for 2021 (v200)
    if "v200" not in item.id:
        continue
        
    url = item.assets["map"].href
    tile_name = item.id + ".tif"
    out_path = os.path.join("data/raw/lulc", tile_name)
    
    if not os.path.exists(out_path):
        print(f"Downloading {tile_name} ({i+1}/{len(items)})...")
        import urllib.request
        try:
            urllib.request.urlretrieve(url, out_path)
        except Exception as e:
            print(f"Failed to download {url}: {e}")
            continue
    else:
        print(f"Tile {tile_name} already downloaded.")
        
    downloaded_tiles.append(out_path)

if not downloaded_tiles:
    print("No 2021 tiles found or downloaded.")
    exit(1)

# 4. Merge, Reproject, and Clip to Master Grid
print("\nProcessing LULC to match master DEM grid...")
master_dem_path = "data/derived/mizoram_dem_clipped_utm.tif"

# First, merge the downloaded raw WGS84 tiles
src_files_to_mosaic = []
for fp in downloaded_tiles:
    src = rasterio.open(fp)
    src_files_to_mosaic.append(src)

mosaic, out_trans = merge(src_files_to_mosaic)
out_meta = src_files_to_mosaic[0].meta.copy()
out_meta.update({
    "driver": "GTiff",
    "height": mosaic.shape[1],
    "width": mosaic.shape[2],
    "transform": out_trans,
    "crs": src_files_to_mosaic[0].crs
})

merged_path = "data/raw/lulc/mizoram_worldcover_merged.tif"
with rasterio.open(merged_path, "w", **out_meta) as dest:
    dest.write(mosaic)

for src in src_files_to_mosaic:
    src.close()

# Now reproject and resample to match master DEM perfectly
with rasterio.open(master_dem_path) as master:
    master_profile = master.profile
    master_transform = master.transform
    master_crs = master.crs
    master_width = master.width
    master_height = master.height

final_out_path = "data/processed/lulc/mizoram_lulc_30m.tif"
print(f"Reprojecting and resampling (Nearest) to {final_out_path}...")

with rasterio.open(merged_path) as src:
    # We use Nearest resampling because LULC is categorical
    reprojected_data = np.zeros((1, master_height, master_width), dtype=master_profile['dtype'])
    reproject(
        source=rasterio.band(src, 1),
        destination=reprojected_data[0],
        src_transform=src.transform,
        src_crs=src.crs,
        dst_transform=master_transform,
        dst_crs=master_crs,
        resampling=Resampling.nearest
    )

# Clip to exactly match the boundary polygon mask (set outside to NoData)
import tempfile
import os

tmp_out_path = final_out_path + ".tmp.tif"
with rasterio.open(tmp_out_path, 'w', **master_profile) as dst:
    dst.write(reprojected_data)

print("Applying standard geometry mask...")
boundary_utm = gpd.read_file('data/raw/mizoram_boundary.geojson').to_crs(epsg=32646)

with rasterio.open(tmp_out_path) as src:
    out_img, out_transform = mask(src, boundary_utm.geometry, crop=False, nodata=-9999.0)
    out_meta = src.meta.copy()
    out_meta.update({'nodata': -9999.0})

with rasterio.open(final_out_path, 'w', **out_meta) as dst:
    dst.write(out_img)

os.remove(tmp_out_path)
print("LULC processing complete.")
