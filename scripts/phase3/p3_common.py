"""
Phase 3 — shared configuration and raster helpers.

All Phase 3 scripts are run from the project root (MIZORAM_LANDSLIDE/), exactly
like the Phase 1/2 scripts:

    python scripts/phase3/<script_name>.py

Design rules for Phase 3 (see documentation, DATA-017 onwards):
  * Nothing produced in Phase 1/2 is overwritten. Every new artefact is written
    under data/phase3/, models/phase3/ or data/final/*_v3*.
  * The real Mizoram land mask is DEM > 0. The master DEM
    (data/derived/mizoram_dem_clipped_utm.tif) was saved with nodata=None, so the
    ~14.4 M out-of-state cells are stored as 0.0 m instead of NoData. Phase 1/2
    scripts compared against -9999 and therefore treated those cells as valid.
  * Every float raster written here uses NoData = -9999 and is masked to the
    valid land area, DEFLATE-compressed and 512x512 tiled.
"""

import os
import json
import numpy as np
import rasterio

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
MASTER_DEM = "data/derived/mizoram_dem_clipped_utm.tif"
BOUNDARY   = "data/raw/mizoram_boundary.geojson"

P3_DIR     = "data/phase3"
FEAT_DIR   = f"{P3_DIR}/features"
INV_DIR    = f"{P3_DIR}/inventory"
MOD_DIR    = f"{P3_DIR}/modeling"
AUDIT_DIR  = f"{P3_DIR}/audit"
FIG_DIR    = f"{P3_DIR}/figures"
MODELS_DIR = "models/phase3"
VALID_MASK = f"{FEAT_DIR}/valid_mask_30m.tif"

NODATA = -9999.0
SEED   = 42


def ensure_dirs():
    for d in (P3_DIR, FEAT_DIR, INV_DIR, MOD_DIR, AUDIT_DIR, FIG_DIR, MODELS_DIR):
        os.makedirs(d, exist_ok=True)


def master_profile():
    with rasterio.open(MASTER_DEM) as src:
        return src.profile.copy()


def grid_info():
    """Return (transform, crs, height, width, pixel_size_m)."""
    with rasterio.open(MASTER_DEM) as src:
        return src.transform, src.crs, src.height, src.width, abs(src.transform[0])


def load_valid_mask():
    """Boolean mask (H, W) of real Mizoram land pixels (DEM > 0 and finite)."""
    if os.path.exists(VALID_MASK):
        with rasterio.open(VALID_MASK) as src:
            return src.read(1).astype(bool)
    ensure_dirs()
    with rasterio.open(MASTER_DEM) as src:
        dem = src.read(1)
        prof = src.profile.copy()
    valid = np.isfinite(dem) & (dem > 0)
    prof.update(dtype="uint8", nodata=None, compress="deflate", tiled=True,
                blockxsize=512, blockysize=512, predictor=1)
    with rasterio.open(VALID_MASK, "w", **prof) as dst:
        dst.write(valid.astype("uint8"), 1)
    return valid


def read_float(path, valid=None):
    """Read band 1 as float32; NoData (declared or -9999) and non-finite -> NaN.
    If `valid` is given, cells outside the land mask are also set to NaN."""
    with rasterio.open(path) as src:
        arr = src.read(1).astype("float32")
        nd = src.nodata
    if nd is not None and np.isfinite(nd):
        arr[arr == nd] = np.nan
    arr[arr == NODATA] = np.nan
    arr[~np.isfinite(arr)] = np.nan
    if valid is not None:
        arr[~valid] = np.nan
    return arr


def write_float(path, arr, valid=None, profile=None):
    """Write a float32 GeoTIFF on the master grid (NaN / outside mask -> -9999)."""
    prof = (profile or master_profile()).copy()
    prof.update(dtype="float32", nodata=NODATA, count=1, compress="deflate",
                predictor=3, tiled=True, blockxsize=512, blockysize=512,
                BIGTIFF="IF_SAFER")
    out = np.where(np.isfinite(arr), arr, NODATA).astype("float32")
    if valid is not None:
        out[~valid] = NODATA
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with rasterio.open(path, "w", **prof) as dst:
        dst.write(out, 1)
    return path


def write_uint8(path, arr, nodata=255, profile=None):
    prof = (profile or master_profile()).copy()
    prof.update(dtype="uint8", nodata=nodata, count=1, compress="deflate",
                predictor=1, tiled=True, blockxsize=512, blockysize=512)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with rasterio.open(path, "w", **prof) as dst:
        dst.write(arr.astype("uint8"), 1)
    return path


def save_json(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, default=lambda o: o.item() if hasattr(o, "item") else str(o))


def log(msg=""):
    print(msg, flush=True)
