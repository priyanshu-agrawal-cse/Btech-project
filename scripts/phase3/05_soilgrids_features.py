"""
Phase 3 / Step 05 — Soil properties from SoilGrids 2.0 (DATA-022).

Why: soil texture and bulk density control shear strength, permeability and
pore-pressure build-up. GSI records Mizoram landslides as shallow (DEPTH median
0.5 m, 90th percentile 1.0 m), so the 30–60 cm layer is used.

Source : ISRIC — World Soil Information, SoilGrids 2.0 (Poggio et al., 2021),
         250 m, Interrupted Goode Homolosine, CC-BY 4.0
         https://files.isric.org/soilgrids/latest/data/<var>/<var>_30-60cm_mean.vrt
Mapped units (ISRIC): clay, sand = g/kg (÷10 -> %); bdod = cg/cm3 (÷100 -> g/cm3)
Steps  : 1. read the window covering the padded study grid (+ 2 km) at native
            250 m through GDAL /vsicurl/, save it untouched to data/raw/soilgrids/
         2. bilinear reprojection onto the 30 m master grid, unit conversion,
            land mask
Outputs: data/raw/soilgrids/<var>_30-60cm_mean_mizoram_igh.tif
         data/phase3/features/soil_clay_pct.tif, soil_sand_pct.tif, soil_bdod_gcm3.tif
"""

import os
import sys
import numpy as np
import rasterio
from rasterio.windows import from_bounds
from rasterio.warp import reproject, transform_bounds, Resampling

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p3_common import FEAT_DIR, ensure_dirs, load_valid_mask, master_profile, write_float, save_json, log

ensure_dirs()
RAW = "data/raw/soilgrids"
os.makedirs(RAW, exist_ok=True)
BASE = "https://files.isric.org/soilgrids/latest/data"
DEPTH = "30-60cm"
VARS = {"clay": ("soil_clay_pct", 0.1), "sand": ("soil_sand_pct", 0.1), "bdod": ("soil_bdod_gcm3", 0.01)}
PADDED = "data/processed/mizoram_dem_utm46n_master_plus10km.tif"

GDAL_ENV = dict(GDAL_HTTP_MAX_RETRY="5", GDAL_HTTP_RETRY_DELAY="3", VSI_CACHE="TRUE",
                GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
                CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".vrt,.tif")

valid = load_valid_mask()
prof = master_profile()
H, W = valid.shape
with rasterio.open(PADDED) as s:
    pb, pcrs = s.bounds, s.crs
summary = {}

with rasterio.Env(**GDAL_ENV):
    for var, (out_name, factor) in VARS.items():
        url = f"/vsicurl/{BASE}/{var}/{var}_{DEPTH}_mean.vrt"
        raw_path = f"{RAW}/{var}_{DEPTH}_mean_mizoram_igh.tif"
        if os.path.exists(raw_path):
            # re-use the clip saved on 2026-10-28 (identical input on re-runs)
            with rasterio.open(raw_path) as s:
                arr, wtr, sprof, nd = s.read(1), s.transform, s.profile.copy(), s.nodata
            log(f"{var}: re-using saved clip {raw_path}")
        else:
            with rasterio.open(url) as src:
                l, b, r, t = transform_bounds(pcrs, src.crs, pb.left - 2000, pb.bottom - 2000,
                                              pb.right + 2000, pb.top + 2000, densify_pts=41)
                win = from_bounds(l, b, r, t, src.transform).round_offsets().round_lengths()
                arr = src.read(1, window=win)
                wtr = src.window_transform(win)
                sprof = src.profile.copy()
                nd = src.nodata
            sprof.update(driver="GTiff", width=arr.shape[1], height=arr.shape[0], transform=wtr,
                         compress="deflate", tiled=False)
            for k in ("blockxsize", "blockysize"):
                sprof.pop(k, None)
            with rasterio.open(raw_path, "w", **sprof) as dst:   # raw clip written once, never overwritten
                dst.write(arr, 1)
            log(f"{var}: native clip {arr.shape} saved -> {raw_path} (nodata={nd})")

        out = np.full((H, W), np.nan, dtype="float32")
        reproject(source=arr.astype("float32"), destination=out, src_transform=wtr,
                  src_crs=sprof["crs"], src_nodata=nd, dst_transform=prof["transform"],
                  dst_crs=prof["crs"], dst_nodata=np.nan, resampling=Resampling.bilinear,
                  num_threads=2)
        out *= factor
        write_float(f"{FEAT_DIR}/{out_name}.tif", out, valid)
        v = out[valid & np.isfinite(out)]
        miss = 1 - v.size / valid.sum()
        summary[out_name] = {"min": float(v.min()), "mean": float(v.mean()), "max": float(v.max()),
                             "missing_share_of_land": float(miss), "source": url.replace("/vsicurl/", "")}
        log(f"  {out_name:16s} min={v.min():8.3f} mean={v.mean():8.3f} max={v.max():8.3f}  missing={miss:.4%}")

save_json(summary, f"{FEAT_DIR}/soilgrids_summary.json")
log("SoilGrids features complete.")
