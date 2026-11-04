import numpy as np
import rasterio
import os

input_dem = "data/derived/mizoram_dem_clipped_utm.tif"
slope_out = "data/derived/mizoram_slope.tif"
aspect_out = "data/derived/mizoram_aspect.tif"
curvature_out = "data/derived/mizoram_curvature.tif"

print("Deriving Topographic features (Slope, Aspect, Curvature)...")

if not os.path.exists(input_dem):
    print(f"Error: {input_dem} not found. Run previous preprocessing step first.")
    exit(1)

with rasterio.open(input_dem) as src:
    dem = src.read(1).astype('float32')
    meta = src.meta.copy()
    nodata = src.nodata
    # get pixel size
    dx = src.transform[0]
    dy = -src.transform[4] # Usually negative

# Handle nodata
mask = (dem == nodata) | np.isnan(dem)
dem[mask] = np.nan

print("Calculating derivatives...")
z = dem
# Pad to handle edges (replicate borders)
z_pad = np.pad(z, 1, mode='edge')

z1, z2, z3 = z_pad[:-2, :-2], z_pad[:-2, 1:-1], z_pad[:-2, 2:]
z4, z5, z6 = z_pad[1:-1, :-2], z_pad[1:-1, 1:-1], z_pad[1:-1, 2:]
z7, z8, z9 = z_pad[2:, :-2], z_pad[2:, 1:-1], z_pad[2:, 2:]

# Horn's Method for Slope & Aspect
dz_dx = ((z3 + 2*z6 + z9) - (z1 + 2*z4 + z7)) / (8.0 * dx)
dz_dy = ((z7 + 2*z8 + z9) - (z1 + 2*z2 + z3)) / (8.0 * dy)

# Slope in degrees
slope = np.arctan(np.sqrt(dz_dx**2 + dz_dy**2)) * (180.0 / np.pi)

# Aspect in compass degrees (0=North, 90=East)
aspect = np.arctan2(dz_dx, dz_dy) * (180.0 / np.pi)
aspect[aspect < 0] += 360.0
# Flat areas (slope == 0) usually have aspect -1
aspect[slope < 0.001] = -1

# Zevenbergen & Thorne Method for Curvature
D = ((z4 + z6) / 2 - z5) / (dx**2)
E = ((z2 + z8) / 2 - z5) / (dy**2)
curvature = -2 * (D + E) * 100 # General curvature multiplied by 100 for better scale

# Apply masks
slope[mask] = -9999
aspect[mask] = -9999
curvature[mask] = -9999

meta.update({'nodata': -9999, 'dtype': 'float32'})

print("Saving derived layers to data/derived/ ...")
with rasterio.open(slope_out, 'w', **meta) as dst:
    dst.write(slope.astype('float32'), 1)
print(f"SUCCESS: Slope saved to {slope_out}")

with rasterio.open(aspect_out, 'w', **meta) as dst:
    dst.write(aspect.astype('float32'), 1)
print(f"SUCCESS: Aspect saved to {aspect_out}")

with rasterio.open(curvature_out, 'w', **meta) as dst:
    dst.write(curvature.astype('float32'), 1)
print(f"SUCCESS: Curvature saved to {curvature_out}")
