"""
Download CHIRPS v2.0 monthly climatology for Mizoram.
Computes mean annual precipitation and max monthly precipitation
over a 10-year baseline (2007-2017) matching the landslide inventory window.
"""
import os
import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling
import requests
import warnings
warnings.filterwarnings('ignore')

os.makedirs("data/raw/rainfall", exist_ok=True)
os.makedirs("data/processed/rainfall", exist_ok=True)

# Master DEM for grid alignment
master_dem_path = "data/derived/mizoram_dem_clipped_utm.tif"

# CHIRPS monthly data - download year-by-year for 2007-2017
base_url = "https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_monthly/tifs/"

years = list(range(2007, 2018))  # 2007 to 2017 inclusive

all_monthly_arrays = []

for year in years:
    for month in range(1, 13):
        fname = f"chirps-v2.0.{year}.{month:02d}.tif.gz"
        url = base_url + fname
        local_gz = os.path.join("data/raw/rainfall", fname)
        local_tif = local_gz.replace(".gz", "")
        
        if not os.path.exists(local_tif):
            if not os.path.exists(local_gz):
                print(f"Downloading {fname}...")
                try:
                    resp = requests.get(url, timeout=60)
                    if resp.status_code == 200:
                        with open(local_gz, "wb") as f:
                            f.write(resp.content)
                    else:
                        print(f"  Failed: {resp.status_code}")
                        continue
                except Exception as e:
                    print(f"  Error: {e}")
                    continue
            
            # Decompress
            import gzip
            import shutil
            print(f"  Decompressing {fname}...")
            with gzip.open(local_gz, 'rb') as f_in:
                with open(local_tif, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
        
        # Read and crop to Mizoram bbox (in WGS84 first)
        # Mizoram bbox: ~92.15, 21.94, 93.44, 24.53
        try:
            with rasterio.open(local_tif) as src:
                # CHIRPS is global 0.05 degree. We read a window around Mizoram.
                from rasterio.windows import from_bounds
                window = from_bounds(92.0, 21.5, 94.0, 25.0, src.transform)
                data = src.read(1, window=window)
                transform = src.window_transform(window)
                
                # Replace nodata
                data = np.where(data < 0, np.nan, data)
                all_monthly_arrays.append(data)
        except Exception as e:
            print(f"  Error reading {local_tif}: {e}")

print(f"\nLoaded {len(all_monthly_arrays)} monthly grids ({len(all_monthly_arrays)//12} years).")

if len(all_monthly_arrays) == 0:
    print("ERROR: No rainfall data loaded!")
    exit(1)

# Stack into 3D array: (months, lat, lon)
monthly_stack = np.array(all_monthly_arrays)

# Calculate climatological features
# 1. Mean Annual Precipitation (sum each year, then average across years)
n_years = len(years)
annual_sums = []
for i in range(n_years):
    start_idx = i * 12
    end_idx = start_idx + 12
    if end_idx <= len(all_monthly_arrays):
        year_sum = np.nansum(monthly_stack[start_idx:end_idx], axis=0)
        annual_sums.append(year_sum)

annual_stack = np.array(annual_sums)
mean_annual_precip = np.nanmean(annual_stack, axis=0)

# 2. Max Monthly Precipitation (across entire period)
max_monthly_precip = np.nanmax(monthly_stack, axis=0)

print(f"Mean Annual Precip - Min: {np.nanmin(mean_annual_precip):.1f}, Max: {np.nanmax(mean_annual_precip):.1f}, Mean: {np.nanmean(mean_annual_precip):.1f} mm")
print(f"Max Monthly Precip - Min: {np.nanmin(max_monthly_precip):.1f}, Max: {np.nanmax(max_monthly_precip):.1f}, Mean: {np.nanmean(max_monthly_precip):.1f} mm")

# Save as intermediate WGS84 GeoTIFFs
# Get transform from last opened file
with rasterio.open(local_tif) as src:
    window = from_bounds(92.0, 21.5, 94.0, 25.0, src.transform)
    chirps_transform = src.window_transform(window)
    chirps_crs = src.crs

for arr, name in [(mean_annual_precip, "mean_annual_precip"), (max_monthly_precip, "max_monthly_precip")]:
    tmp_path = f"data/raw/rainfall/{name}_wgs84.tif"
    profile = {
        "driver": "GTiff",
        "height": arr.shape[0],
        "width": arr.shape[1],
        "count": 1,
        "dtype": "float32",
        "crs": chirps_crs,
        "transform": chirps_transform,
        "nodata": -9999.0,
    }
    arr_out = np.where(np.isnan(arr), -9999.0, arr).astype(np.float32)
    with rasterio.open(tmp_path, "w", **profile) as dst:
        dst.write(arr_out, 1)
    print(f"Saved intermediate: {tmp_path}")

# Reproject to match master DEM grid
with rasterio.open(master_dem_path) as master:
    master_profile = master.profile.copy()
    master_transform = master.transform
    master_crs = master.crs
    master_width = master.width
    master_height = master.height

for name in ["mean_annual_precip", "max_monthly_precip"]:
    src_path = f"data/raw/rainfall/{name}_wgs84.tif"
    dst_path = f"data/processed/rainfall/{name}_30m.tif"
    
    with rasterio.open(src_path) as src:
        dst_data = np.zeros((1, master_height, master_width), dtype=np.float32)
        reproject(
            source=rasterio.band(src, 1),
            destination=dst_data[0],
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=master_transform,
            dst_crs=master_crs,
            resampling=Resampling.bilinear,
            src_nodata=-9999.0,
            dst_nodata=-9999.0,
        )
    
    out_profile = master_profile.copy()
    out_profile.update(dtype="float32", nodata=-9999.0, count=1)
    with rasterio.open(dst_path, "w", **out_profile) as dst:
        dst.write(dst_data)
    
    print(f"Saved: {dst_path}")

print("\nRainfall processing complete!")
