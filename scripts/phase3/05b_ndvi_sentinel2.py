"""
Phase 3 / Step 05b — Dry-season vegetation index from Sentinel-2 (DATA-026).

Why: ESA WorldCover gives classes only; NDVI adds continuous vegetation density
(mature forest vs jhum fallow vs cut slope).

Source : Copernicus Sentinel-2 L2A, Microsoft Planetary Computer STAC
         collection "sentinel-2-l2a" (anonymous signed access).
Period : 2021-11-01 to 2022-01-20 — the dry season of the ESA WorldCover 2021 year.
         Scenes with processing baseline >= 04.00 (from 25 Jan 2022) are excluded
         because they carry a +1000 DN radiometric offset that would bias NDVI.
Method : for every MGRS tile keep the MAX_PER_TILE least-cloudy scenes
         (eo:cloud_cover < 20 %), load B04, B08 and SCL directly on the 30 m master
         grid, keep clear land/vegetation pixels (SCL 4, 5, 6, 7), compute NDVI per
         date and take the per-pixel MEDIAN over all clear dates.

CAVEAT : NDVI is observed AFTER most GSI surveys (2016-2020), so at a landslide
         pixel a low value may be the EFFECT of the failure or of the road bench,
         not its cause. The same caveat applies to LULC. Its contribution is
         therefore reported separately in the modelling step.

Outputs: data/phase3/features/ndvi_dry2021.tif, ndvi_clear_obs.tif (UInt8 count),
         data/phase3/features/ndvi_summary.json
"""

import os
import sys
import numpy as np
import dask
import planetary_computer
import pystac_client
from odc.geo.geobox import GeoBox
from odc.stac import load as odc_load

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p3_common import (FEAT_DIR, ensure_dirs, load_valid_mask, master_profile, grid_info,
                       write_float, write_uint8, save_json, log)

ensure_dirs()
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
PERIOD = "2021-11-01/2022-01-20"
MAX_PER_TILE = 6
BBOX = [92.15, 21.90, 93.47, 24.56]
CLEAR_SCL = (4, 5, 6, 7)

valid = load_valid_mask()
tr, crs, H, W, L = grid_info()

cat = pystac_client.Client.open(STAC, modifier=planetary_computer.sign_inplace)
items = list(cat.search(collections=["sentinel-2-l2a"], bbox=BBOX, datetime=PERIOD,
                        query={"eo:cloud_cover": {"lt": 20}}).items())
log(f"Scenes found: {len(items)}")
items = [i for i in items if str(i.properties.get("s2:processing_baseline", "0")) < "04.00"]
by_tile = {}
for it in items:
    by_tile.setdefault(it.properties.get("s2:mgrs_tile"), []).append(it)
keep = []
for tile, its in sorted(by_tile.items()):
    its.sort(key=lambda i: i.properties.get("eo:cloud_cover", 100))
    keep += its[:MAX_PER_TILE]
    log(f"  tile {tile}: {len(its)} scenes, kept {min(len(its), MAX_PER_TILE)}, "
        f"cloud {its[0].properties['eo:cloud_cover']:.1f}-"
        f"{its[min(len(its), MAX_PER_TILE) - 1].properties['eo:cloud_cover']:.1f} %")
log(f"Scenes used: {len(keep)} from {len(by_tile)} tiles")

gbox = GeoBox((H, W), tr, str(crs))
ds = odc_load(keep, bands=["B04", "B08", "SCL"], geobox=gbox, chunks={"x": 1024, "y": 1024},
              groupby="solar_day", resampling={"B04": "average", "B08": "average", "SCL": "nearest"},
              dtype="uint16", nodata=0)
log(f"Lazy dataset: {dict(ds.sizes)} dates")

red = ds["B04"].astype("float32")
nir = ds["B08"].astype("float32")
scl = ds["SCL"]
clear = scl.isin(CLEAR_SCL) & (red > 0) & (nir > 0)
ndvi = ((nir - red) / (nir + red)).where(clear).astype("float32")
ndvi = ndvi.chunk({"time": -1, "x": 1024, "y": 1024})
med = ndvi.median(dim="time", skipna=True)
cnt = ndvi.notnull().sum(dim="time").astype("uint8")

with dask.config.set(scheduler="threads", num_workers=int(os.environ.get("P3_NJOBS", "3"))):
    log("Computing median NDVI...")
    med_v, cnt_v = dask.compute(med, cnt)

arr = med_v.values.astype("float32")
c = cnt_v.values.astype("uint8")
write_float(f"{FEAT_DIR}/ndvi_dry2021.tif", arr, valid)
write_uint8(f"{FEAT_DIR}/ndvi_clear_obs.tif", np.where(valid, c, 255))
v = arr[valid & np.isfinite(arr)]
summary = {"collection": "sentinel-2-l2a", "period": PERIOD, "scenes_used": len(keep),
           "tiles": sorted(k for k in by_tile if k), "scene_ids": [i.id for i in keep],
           "ndvi_min": float(v.min()), "ndvi_mean": float(v.mean()), "ndvi_max": float(v.max()),
           "land_share_without_clear_obs": float(1 - v.size / valid.sum()),
           "clear_obs_median": float(np.median(c[valid]))}
save_json(summary, f"{FEAT_DIR}/ndvi_summary.json")
log({k: w for k, w in summary.items() if k not in ("scene_ids",)})
log("NDVI complete.")
