"""
Phase 3 / Step 02 — Edge-correct terrain features (DATA-019).

Computes every DEM derivative on the padded DEM (real terrain outside the
border, see 02a) and then crops to the master grid and masks to the land area.
This removes the state-edge artefacts found in the audit (DATA-017 C).

Input : data/processed/mizoram_dem_utm46n_master_plus10km.tif
        data/derived/mizoram_dem_clipped_utm.tif (land mask: DEM > 0)
Output: data/phase3/features/
   elevation.tif      metres
   slope.tif          degrees, Horn (1981) 3x3
   aspect_sin.tif     sin(aspect) = eastness   (0 on flat cells, slope < 1 deg)
   aspect_cos.tif     cos(aspect) = northness  (0 on flat cells)
   curv_general.tif   Zevenbergen & Thorne (1987), -2(D+E)*100 (ArcGIS convention)
   curv_profile.tif   -2(DG^2+EH^2+FGH)/(G^2+H^2)*100
   curv_plan.tif      2(DH^2+EG^2-FGH)/(G^2+H^2)*100
   tri.tif            Riley et al. (1999): sqrt(sum (z_i - z_0)^2) over 8 neighbours, m
   tpi_270m.tif       z - mean(z) in 9x9 window   (Phase 2 scale)
   tpi_1km.tif        z - mean(z) in 33x33 window
   tpi_3km.tif        z - mean(z) in 99x99 window
   relief_1km.tif     max(z) - min(z) in 33x33 window (relative relief, m)
"""

import os
import sys
import gc
import numpy as np
import rasterio
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p3_common import FEAT_DIR, ensure_dirs, load_valid_mask, write_float, log

ensure_dirs()
PADDED = "data/processed/mizoram_dem_utm46n_master_plus10km.tif"
M = 330  # margin in pixels (must match 02a)

valid = load_valid_mask()
H, W = valid.shape
with rasterio.open(PADDED) as src:
    z = src.read(1).astype("float64")
    L = abs(src.transform[0])
assert z.shape == (H + 2 * M, W + 2 * M), z.shape
log(f"Padded DEM {z.shape}, cell size {L:.4f} m, land cells {valid.sum():,}")


def crop(a):
    return a[M:M + H, M:M + W]


def save(name, arr):
    write_float(f"{FEAT_DIR}/{name}.tif", crop(arr).astype("float32"), valid)
    v = crop(arr)[valid]
    log(f"  {name:14s} min={np.nanmin(v):10.3f} mean={np.nanmean(v):10.3f} max={np.nanmax(v):10.3f}")


# elevation (inside the state this equals the master DEM exactly)
save("elevation", z)

# 3x3 neighbourhood (edge rows/cols of the PADDED array are never used after cropping)
zp = np.pad(z, 1, mode="edge")
z1, z2, z3 = zp[:-2, :-2], zp[:-2, 1:-1], zp[:-2, 2:]
z4, z5, z6 = zp[1:-1, :-2], zp[1:-1, 1:-1], zp[1:-1, 2:]
z7, z8, z9 = zp[2:, :-2], zp[2:, 1:-1], zp[2:, 2:]

# --- Horn slope / aspect -----------------------------------------------------
dzdx = ((z3 + 2 * z6 + z9) - (z1 + 2 * z4 + z7)) / (8 * L)       # +east
dzdn = ((z1 + 2 * z2 + z3) - (z7 + 2 * z8 + z9)) / (8 * L)       # +north (row 0 = north)
slope = np.degrees(np.arctan(np.hypot(dzdx, dzdn)))
save("slope", slope)
aspect = np.degrees(np.arctan2(-dzdx, -dzdn)) % 360.0            # downslope azimuth, 0 = N
flat = slope < 1.0
a_sin = np.where(flat, 0.0, np.sin(np.radians(aspect)))
a_cos = np.where(flat, 0.0, np.cos(np.radians(aspect)))
save("aspect_sin", a_sin)
save("aspect_cos", a_cos)
del dzdx, dzdn, aspect, a_sin, a_cos, flat, slope
gc.collect()

# --- Zevenbergen & Thorne curvatures ------------------------------------------
D = ((z4 + z6) / 2 - z5) / L ** 2
E = ((z2 + z8) / 2 - z5) / L ** 2
F = (-z1 + z3 + z7 - z9) / (4 * L ** 2)
G = (z6 - z4) / (2 * L)
Hh = (z2 - z8) / (2 * L)
save("curv_general", -2 * (D + E) * 100)
g2h2 = G ** 2 + Hh ** 2
ok = g2h2 > 1e-10
prof = np.where(ok, -2 * (D * G ** 2 + E * Hh ** 2 + F * G * Hh) / np.where(ok, g2h2, 1), 0) * 100
save("curv_profile", prof)
del prof
plan = np.where(ok, 2 * (D * Hh ** 2 + E * G ** 2 - F * G * Hh) / np.where(ok, g2h2, 1), 0) * 100
save("curv_plan", plan)
del plan, D, E, F, G, Hh, g2h2, ok
gc.collect()

# --- TRI (Riley 1999) ------------------------------------------------------------
tri = np.sqrt(sum((n - z5) ** 2 for n in (z1, z2, z3, z4, z6, z7, z8, z9)))
save("tri", tri)
del tri, zp, z1, z2, z3, z4, z5, z6, z7, z8, z9
gc.collect()

# --- Multi-scale TPI and relative relief -----------------------------------------
for size, name in [(9, "tpi_270m"), (33, "tpi_1km"), (99, "tpi_3km")]:
    save(name, z - ndimage.uniform_filter(z, size=size, mode="nearest"))
    gc.collect()
relief = ndimage.maximum_filter(z, size=33, mode="nearest") - ndimage.minimum_filter(z, size=33, mode="nearest")
save("relief_1km", relief)
log("Terrain features complete.")
