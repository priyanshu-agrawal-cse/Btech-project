import os
import urllib.request
import rasterio
from rasterio.merge import merge
import time

print("Starting Copernicus DEM 30m local download and merge...")

os.makedirs("data/raw/dem_tiles", exist_ok=True)

# Mizoram bounds: South=21.89, North=24.57, West=92.21, East=93.49
tiles = []
for lat in range(21, 25):
    for lon in range(92, 94):
        lat_str = f"N{lat:02d}_00"
        lon_str = f"E{lon:03d}_00"
        tile_id = f"Copernicus_DSM_COG_10_{lat_str}_{lon_str}_DEM"
        url = f"https://copernicus-dem-30m.s3.amazonaws.com/{tile_id}/{tile_id}.tif"
        tiles.append((tile_id, url))

print(f"Identified {len(tiles)} tiles covering Mizoram.")

local_files = []
for tile_id, url in tiles:
    local_path = f"data/raw/dem_tiles/{tile_id}.tif"
    local_files.append(local_path)
    if os.path.exists(local_path) and os.path.getsize(local_path) > 1000000:
        print(f"Tile {tile_id} already exists locally. Skipping download.")
        continue
    
    print(f"Downloading {tile_id}...")
    success = False
    for attempt in range(3):
        try:
            urllib.request.urlretrieve(url, local_path)
            success = True
            break
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            time.sleep(2)
            
    if not success:
        print(f"Failed to download {tile_id} after 3 attempts.")
        # If over ocean/border it might not exist, but for Mizoram they all exist.

print("Merging local DEM tiles...")
dem_datasets = []
for f in local_files:
    if os.path.exists(f):
        dem_datasets.append(rasterio.open(f))

if not dem_datasets:
    print("No valid DEM tiles found to merge.")
    exit(1)

mosaic, out_trans = merge(dem_datasets)

out_meta = dem_datasets[0].meta.copy()
out_meta.update({
    "driver": "GTiff",
    "height": mosaic.shape[1],
    "width": mosaic.shape[2],
    "transform": out_trans,
    "compress": "lzw"
})

output_path = "data/raw/mizoram_dem_copernicus_30m.tif"
with rasterio.open(output_path, "w", **out_meta) as dest:
    dest.write(mosaic)

for src in dem_datasets:
    src.close()

print(f"SUCCESS: Merged DEM saved to {output_path}")
