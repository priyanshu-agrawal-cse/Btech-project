"""
Advanced Feature Engineering for Landslide Susceptibility

This script derives additional morphometric features from the DEM that are
highly relevant to landslide occurrence:

  - TWI   : Topographic Wetness Index  — identifies water accumulation zones
  - TRI   : Terrain Ruggedness Index   — quantifies terrain heterogeneity
  - TPI   : Topographic Position Index — ridge vs valley classification
  - Plan/Profile Curvature             — directional curvature types
  - Sine/Cosine of Aspect              — circular encoding (avoids 0=360 artifact)
  - Slope x Curvature interaction      — non-linear instability signal

These features are written as new 30m GeoTIFFs aligned to the master DEM grid.

WHY THESE FEATURES?
-------------------
With only 41 positive samples, every additional discriminative feature is
precious. Literature consistently shows TWI, TRI, and curvature components
to be among the top predictors in data-scarce landslide studies.
"""

import numpy as np
import rasterio
from scipy.ndimage import uniform_filter
import os

# ---- paths ----------------------------------------------------------------
DEM_PATH       = "data/derived/mizoram_dem_clipped_utm.tif"
SLOPE_PATH     = "data/derived/mizoram_slope.tif"
ASPECT_PATH    = "data/derived/mizoram_aspect.tif"
CURVATURE_PATH = "data/derived/mizoram_curvature.tif"

OUT_DIR = "data/derived"
os.makedirs(OUT_DIR, exist_ok=True)

NODATA = -9999.0

# ---- helpers ---------------------------------------------------------------

def read_raster(path):
    with rasterio.open(path) as src:
        data = src.read(1).astype("float32")
        meta = src.meta.copy()
        nd   = src.nodata if src.nodata is not None else NODATA
        dx   = abs(src.transform[0])
        dy   = abs(src.transform[4])
    return data, meta, nd, dx, dy

def save_raster(arr, meta, path, nodata=NODATA):
    m = meta.copy()
    m.update({"dtype": "float32", "nodata": nodata, "compress": "lzw"})
    with rasterio.open(path, "w", **m) as dst:
        dst.write(arr.astype("float32"), 1)
    print(f"  Saved -> {path}")


# ===========================================================================
print("=" * 60)
print("STEP 1 - Loading DEM and existing derivatives")
print("=" * 60)

dem,    meta, dem_nd, dx, dy = read_raster(DEM_PATH)
slope,  _,    slp_nd, _,  _  = read_raster(SLOPE_PATH)
aspect, _,    asp_nd, _,  _  = read_raster(ASPECT_PATH)
curv,   _,    cur_nd, _,  _  = read_raster(CURVATURE_PATH)

# Build a shared valid mask
valid = (
    (dem   != dem_nd) & ~np.isnan(dem)  &
    (slope != slp_nd) & ~np.isnan(slope)
)

# Convert slope to radians once
slope_rad = np.where(valid, np.deg2rad(slope), np.nan)


# ===========================================================================
print("\nSTEP 2 - Topographic Wetness Index (TWI)")
twi_path = f"{OUT_DIR}/mizoram_twi.tif"
if not os.path.exists(twi_path):
    tan_slope = np.tan(slope_rad)
    tan_slope_safe = np.where((tan_slope < 1e-5) | ~valid, 1e-5, tan_slope)
    cell_area = dx * dy                         # m^2
    sca = cell_area / tan_slope_safe            # simplified SCA
    twi = np.log(sca / tan_slope_safe)
    twi = np.clip(twi, NODATA, 30.0)
    twi[~valid] = NODATA
    save_raster(twi.astype("float32"), meta, twi_path)
    del twi, tan_slope, tan_slope_safe, sca
    import gc; gc.collect()
else:
    print("  Already generated, skipping.")


# ===========================================================================
print("\nSTEP 3 - Terrain Ruggedness Index (TRI)")
tri_path = f"{OUT_DIR}/mizoram_tri.tif"
if not os.path.exists(tri_path):
    dem_safe = np.where(valid, dem, np.nan)
    dem_pad  = np.pad(dem_safe, 1, mode="edge")
    neighbors = np.stack([
        dem_pad[:-2, :-2], dem_pad[:-2, 1:-1], dem_pad[:-2, 2:],
        dem_pad[1:-1, :-2],                    dem_pad[1:-1, 2:],
        dem_pad[2:, :-2],  dem_pad[2:, 1:-1],  dem_pad[2:, 2:]
    ], axis=0)  # shape (8, H, W)
    center = dem_safe[np.newaxis, :, :]
    tri = np.sqrt(np.nansum((neighbors - center) ** 2, axis=0))
    tri = np.where(valid, tri, NODATA)
    save_raster(tri.astype("float32"), meta, tri_path)
    del tri, dem_safe, dem_pad, neighbors, center
    import gc; gc.collect()
else:
    print("  Already generated, skipping.")


# ===========================================================================
print("\nSTEP 4 - Topographic Position Index (TPI)")
tpi_path = f"{OUT_DIR}/mizoram_tpi.tif"
if not os.path.exists(tpi_path):
    WINDOW = 9  # cells = 270m neighbourhood
    dem_filled  = np.where(valid, dem, 0.0)
    count_arr   = np.where(valid, 1.0, 0.0)
    sum_neighbourhood   = uniform_filter(dem_filled, size=WINDOW, mode="nearest") * (WINDOW * WINDOW)
    count_neighbourhood = uniform_filter(count_arr,  size=WINDOW, mode="nearest") * (WINDOW * WINDOW)
    count_neighbourhood = np.where(count_neighbourhood < 1, 1, count_neighbourhood)
    mean_neighbourhood = sum_neighbourhood / count_neighbourhood
    dem_float = np.where(valid, dem, np.nan)
    tpi = dem_float - mean_neighbourhood
    tpi = np.where(valid, tpi, NODATA)
    save_raster(tpi.astype("float32"), meta, tpi_path)
    del tpi, dem_filled, count_arr, sum_neighbourhood, count_neighbourhood, mean_neighbourhood, dem_float
    import gc; gc.collect()
else:
    print("  Already generated, skipping.")


# ===========================================================================
print("\nSTEP 5 - Plan Curvature and Profile Curvature")
prof_path = f"{OUT_DIR}/mizoram_profile_curvature.tif"
plan_path = f"{OUT_DIR}/mizoram_plan_curvature.tif"

if not os.path.exists(prof_path) or not os.path.exists(plan_path):
    dem_p = np.pad(dem_safe, 1, mode="edge")
    z1 = dem_p[:-2, :-2]; z2 = dem_p[:-2, 1:-1]; z3 = dem_p[:-2, 2:]
    z4 = dem_p[1:-1, :-2]; z5 = dem_p[1:-1, 1:-1]; z6 = dem_p[1:-1, 2:]
    z7 = dem_p[2:, :-2];  z8 = dem_p[2:, 1:-1];  z9 = dem_p[2:, 2:]

    D = ((z4 + z6) / 2.0 - z5) / (dx ** 2)    # d2z/dx2
    E = ((z2 + z8) / 2.0 - z5) / (dy ** 2)    # d2z/dy2
    F = ((-z1 + z3 + z7 - z9) / 4.0) / (dx * dy)  # cross term
    G = (z6 - z4) / (2.0 * dx)                # dz/dx
    H_ = (z2 - z8) / (2.0 * dy)               # dz/dy
    del dem_p, z1, z2, z3, z4, z5, z6, z7, z8, z9
    import gc; gc.collect()

    p2q2 = G**2 + H_**2
    p2q2_safe = np.where(p2q2 < 1e-10, 1e-10, p2q2)

    # Profile curvature (along slope direction)
    prof_curv = -2.0 * (D * G**2 + E * H_**2 + F * G * H_) / p2q2_safe
    prof_curv = np.where(valid, prof_curv * 100, NODATA).astype("float32")
    save_raster(prof_curv, meta, prof_path)
    del prof_curv

    # Plan curvature (perpendicular to slope direction)
    plan_curv = 2.0 * (D * H_**2 + E * G**2 - F * G * H_) / p2q2_safe
    plan_curv = np.where(valid, plan_curv * 100, NODATA).astype("float32")
    save_raster(plan_curv, meta, plan_path)
    del plan_curv, D, E, F, G, H_, p2q2, p2q2_safe
    gc.collect()
else:
    print("  Already generated, skipping.")

import gc
gc.collect()

# ===========================================================================
print("\nSTEP 6 - Circular Encoding of Aspect (sin/cos)")
sin_path = f"{OUT_DIR}/mizoram_sin_aspect.tif"
cos_path = f"{OUT_DIR}/mizoram_cos_aspect.tif"

# Aspect is circular: 0 and 360 degrees are the same direction.
aspect_safe = np.where(valid & (aspect != asp_nd), aspect, np.nan)
aspect_rad  = np.deg2rad(aspect_safe)
del aspect_safe
gc.collect()

sin_aspect = np.where(valid, np.where(np.isnan(aspect_rad), NODATA, np.sin(aspect_rad)), NODATA).astype("float32")
save_raster(sin_aspect, meta, sin_path)
del sin_aspect
gc.collect()

cos_aspect = np.where(valid, np.where(np.isnan(aspect_rad), NODATA, np.cos(aspect_rad)), NODATA).astype("float32")
del aspect_rad
gc.collect()
save_raster(cos_aspect, meta, cos_path)
del cos_aspect
gc.collect()


# ===========================================================================
print("\nSTEP 7 - Slope x |Curvature| Interaction Feature")
curv_safe  = np.where(valid & (curv != cur_nd), curv, np.nan)
slope_safe = np.where(valid, slope, np.nan)

interact = slope_safe * np.abs(curv_safe)
del curv_safe, slope_safe
gc.collect()

interact = np.where(valid, np.where(np.isnan(interact), NODATA, interact), NODATA).astype("float32")
save_raster(interact, meta, f"{OUT_DIR}/mizoram_slope_curv_interact.tif")
del interact
gc.collect()


# ===========================================================================
print("\n" + "=" * 60)
print("ALL ADVANCED FEATURES DERIVED SUCCESSFULLY")
print("=" * 60)
new_files = [
    "mizoram_twi.tif",
    "mizoram_tri.tif",
    "mizoram_tpi.tif",
    "mizoram_profile_curvature.tif",
    "mizoram_plan_curvature.tif",
    "mizoram_sin_aspect.tif",
    "mizoram_cos_aspect.tif",
    "mizoram_slope_curv_interact.tif",
]
for f in new_files:
    full = os.path.join(OUT_DIR, f)
    size = os.path.getsize(full) / 1e6 if os.path.exists(full) else "N/A"
    if isinstance(size, float):
        print(f"  OK {f:50s} ({size:.1f} MB)")
    else:
        print(f"  MISSING {f}")
