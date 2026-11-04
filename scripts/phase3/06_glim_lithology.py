"""
Phase 3 / Step 06 — Lithology from the Global Lithological Map GLiM (DATA-023).

Why: Phase 1/2 lithology (Macrostrat, tiny scale) has ONE class over 100 % of
Mizoram (audit DATA-017 E). The Phase 1 attempt to download GLiM
(07_get_geology.py) left data/raw/geology/GLiM.zip, which is NOT a valid zip
archive ("File is not a zip file", checked 2026-10-28) — it is kept untouched.

Source : Hartmann & Moosdorf (2012), GLiM v1.0 ("LiMW_GIS 2015.gdb"), the same
         Dropbox URL that 07_get_geology.py intended to use.
Steps  : 1. download the archive to data/raw/geology/GLiM_LiMW_GIS_2015.gdb.zip
         2. read only the polygons intersecting the padded study area
         3. report the classes present (level 1 = xx, level 2 = Litho)
         4. rasterise the most informative level onto the master grid
Outputs: data/raw/geology/glim_mizoram.gpkg
         data/phase3/features/glim_class.tif (UInt8 codes, 0 = no data)
         data/phase3/features/glim_class_mapping.csv, glim_summary.json
"""

import os
import sys
import zipfile
import requests
import numpy as np
import pandas as pd
import geopandas as gpd
import pyogrio
from rasterio.features import rasterize

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p3_common import FEAT_DIR, ensure_dirs, load_valid_mask, grid_info, write_uint8, save_json, log

ensure_dirs()
URL = "https://www.dropbox.com/s/9vuowtebp9f1iud/LiMW_GIS%202015.gdb.zip?dl=1"
ZIP = "data/raw/geology/GLiM_LiMW_GIS_2015.gdb.zip"

if not os.path.exists(ZIP):
    log(f"Downloading GLiM from {URL}")
    with requests.get(URL, stream=True, timeout=1800) as r:
        r.raise_for_status()
        with open(ZIP + ".part", "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    os.replace(ZIP + ".part", ZIP)
log(f"GLiM archive: {os.path.getsize(ZIP) / 1e6:.1f} MB, valid zip = {zipfile.is_zipfile(ZIP)}")

names = zipfile.ZipFile(ZIP).namelist()
gdb = sorted({n.split(".gdb/")[0] + ".gdb" for n in names if ".gdb/" in n})[0]
src = f"/vsizip/{ZIP}/{gdb}"
layers = pyogrio.list_layers(src)
log(f"GDB inside zip: {gdb}; layers: {layers.tolist()}")
layer = layers[0][0]
info = pyogrio.read_info(src, layer=layer)
log(f"layer '{layer}': {info['features']:,} features, CRS={info['crs']}, fields={list(info['fields'])}")

tr, crs, H, W, L = grid_info()
bnd = gpd.read_file("data/raw/mizoram_boundary.geojson").to_crs(crs)
area = bnd.buffer(10_000).to_crs(info["crs"]).total_bounds
g = pyogrio.read_dataframe(src, layer=layer, bbox=tuple(area))
g = g.set_crs(info["crs"], allow_override=True).to_crs(crs)
g = g[g.intersects(bnd.buffer(10_000).union_all())]
g.to_file("data/raw/geology/glim_mizoram.gpkg", driver="GPKG")
log(f"polygons intersecting Mizoram + 10 km: {len(g)}")

inside = g.clip(bnd.union_all())
summary = {"archive": os.path.basename(ZIP), "layer": layer, "n_polygons": int(len(g))}
for col in [c for c in ("xx", "Litho", "IDENTITY_") if c in g.columns]:
    share = (inside.area.groupby(inside[col]).sum() / inside.area.sum() * 100).sort_values(ascending=False)
    summary[f"area_share_pct_{col}"] = share.round(3).to_dict()
    log(f"  area share by {col} (% of state): {share.round(2).to_dict()}")

# choose the finest level whose 2nd most common class covers >= 1 % of the state
level = None
for col in ("Litho", "xx"):
    sh = summary.get(f"area_share_pct_{col}", {})
    if len(sh) >= 2 and sorted(sh.values(), reverse=True)[1] >= 1.0:
        level = col
        break
summary["level_used"] = level
if level is None:
    log("GLiM has a single dominant class over Mizoram -> no informative lithology layer.")
else:
    classes = sorted(g[level].astype(str).unique())
    mapping = {c: i + 1 for i, c in enumerate(classes)}
    pd.DataFrame({"glim_" + level: classes, "code": [mapping[c] for c in classes]}).to_csv(
        f"{FEAT_DIR}/glim_class_mapping.csv", index=False)
    ras = rasterize(((geom, mapping[str(v)]) for geom, v in zip(g.geometry, g[level])),
                    out_shape=(H, W), transform=tr, fill=0, dtype="uint8")
    valid = load_valid_mask()
    ras[~valid] = 0
    write_uint8(f"{FEAT_DIR}/glim_class.tif", ras, nodata=0)
    vals, cnt = np.unique(ras[valid], return_counts=True)
    summary["raster_class_cells"] = {int(v): int(c) for v, c in zip(vals, cnt)}
    log(f"  rasterised level '{level}' -> {summary['raster_class_cells']}")
save_json(summary, f"{FEAT_DIR}/glim_summary.json")
log("GLiM step complete.")
