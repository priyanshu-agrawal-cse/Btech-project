"""
Phase 4 / Task A2 - geology features from the NGDR 1:50,000 data (DATA-038).

Rock groups come from the GSI unit description alone, by the fixed rule in rock_group().
The rule was written from the unit list before any landslide data was compared with
geology, and no polygon or map-sheet ID is used.

Structural lines, also fixed in advance: 1:50,000 faults and shear zones plus the
1:250,000 lineaments classed "Structural lineaments". "Geomorphic Lineaments" are left
out because they follow ridges and drainage, which the terrain factors already describe.

Outputs on the master grid, masked to land, in data/phase4/features/:
  lith_group.tif (UInt8, 0 = no data), dist_lineament.tif (m), lineament_density_1km.tif
  (km of line per km2, 33 x 33 cells), lith_group_mapping.csv
"""

import json
import os
import sys
import warnings

import geopandas as gpd
import numpy as np
import pandas as pd
from rasterio.features import rasterize
from scipy.ndimage import uniform_filter
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "phase3")))
from p3_common import BOUNDARY, grid_info, load_valid_mask, log, write_float, write_uint8

warnings.filterwarnings("ignore")
OUT = "data/phase4/features"
os.makedirs(OUT, exist_ok=True)
GEO = "data/raw/geology/ngdr/extracted"
LITH = f"{GEO}/FAULT_LITHOLOGY_STATE_MIZORAM_1793521648/LITHOLOGY_STATE_MIZORAM/LITHOLOGY_STATE_MIZORAM.shp"
FAULT = f"{GEO}/FAULT_LITHOLOGY_STATE_MIZORAM_1793521648/FAULT_STATE_MIZORAM/FAULT_STATE_MIZORAM.shp"
SHEAR = f"{GEO}/FOLD_SHEAR_ZONE_STATE_MIZORAM_1793522079/SHEAR_ZONE_STATE_MIZORAM/SHEAR_ZONE_STATE_MIZORAM.shp"
LINE = f"{GEO}/GEOMORPHOLOGY_250K_LINEAMENT_250K_STATE_MIZORAM_1793521967/LINEAMENT_250K_STATE_MIZORAM/LINEAMENT_250K_STATE_MIZORAM.shp"

GROUPS = {1: "alluvium", 2: "sandstone_dominant", 3: "shale_dominant", 4: "interbedded",
          5: "conglomeratic", 6: "coal_bearing", 7: "calcareous"}


def rock_group(desc):
    """Group from the description text. Distinctive beds first, then the leading rock type."""
    d = " ".join(str(desc).upper().split())
    if "UNMAPPED" in d:
        return 0
    if "FLUVIAL" in d:
        return 1
    if "CONGLOMERATE" in d or "GRIT" in d:
        return 5
    if "COAL" in d:
        return 6
    if "LIMESTONE" in d:
        return 7
    if d.startswith(("SST WITH", "FLAGGY SANDSTONE", "FERRUGINOUS SANDSTONE", "SANDSTONE WITH")):
        return 2
    if "SHALE" in d.split(",")[0].split(" WITH ")[0] and not d.startswith(("SANDSTONE", "SILTSTONE", "SEQUENCE", "RHYTHMIC")):
        return 3
    return 4


tr, crs, H, W, L = grid_info()
valid = load_valid_mask()
bnd = gpd.read_file(BOUNDARY).to_crs(crs)

lith = gpd.read_file(LITH).to_crs(crs)
lith["geometry"] = lith.buffer(0)
lith["group_id"] = lith["lithologic"].map(rock_group)
clip = gpd.clip(lith, bnd)
clip["km2"] = clip.area / 1e6
m = clip.groupby(["lithologic", "group_name", "formation", "age", "group_id"], dropna=False).km2.sum().reset_index()
m["rock_group"] = m.group_id.map(GROUPS).fillna("no_data")
m.sort_values(["group_id", "km2"], ascending=[True, False]).round(2).to_csv(f"{OUT}/lith_group_mapping.csv", index=False)
log(m.groupby("rock_group").km2.sum().div(m.km2.sum()).mul(100).round(2).to_string())

shapes = ((g, int(v)) for g, v in zip(lith.geometry, lith.group_id) if v > 0)
grid = rasterize(shapes, out_shape=(H, W), transform=tr, fill=0, dtype="uint8")
grid[~valid] = 0
write_uint8(f"{OUT}/lith_group.tif", grid, nodata=0)
vals, cnt = np.unique(grid[valid], return_counts=True)
shares = {GROUPS.get(int(v), "no_data"): round(int(c) / int(valid.sum()) * 100, 3) for v, c in zip(vals, cnt)}
log(f"lith_group land share %: {shares}")
major = sum(1 for k, v in shares.items() if k != "no_data" and v >= 1)
covered = 100 - shares.get("no_data", 0)
log(f"A1 gate: covered {covered:.2f} % (needs >= 95), groups with >= 1 %: {major} (needs >= 2)")
assert covered >= 95 and major >= 2
del grid

parts = [gpd.read_file(FAULT).to_crs(crs).geometry, gpd.read_file(SHEAR).to_crs(crs).geometry]
ln = gpd.read_file(LINE).to_crs(crs)
parts.append(ln[ln.l1descript == "Structural lineaments"].geometry)
lines = pd.concat(parts, ignore_index=True)
log(f"structural lines: faults {len(parts[0])}, shear zones {len(parts[1])}, 1:250k structural {len(parts[2])}")
cells = rasterize(((g, 1) for g in lines), out_shape=(H, W), transform=tr, fill=0, dtype="uint8", all_touched=True).astype(bool)

dens = uniform_filter(cells.astype("float32"), size=33, mode="constant") / (L / 1000)
write_float(f"{OUT}/lineament_density_1km.tif", dens, valid)
log(f"density km/km2 on land: mean {dens[valid].mean():.3f}, max {dens[valid].max():.3f}")
del dens

tree = cKDTree(np.argwhere(cells))
del cells
dist = np.full((H, W), np.nan, "float32")
for r0 in range(0, H, 400):
    rr, cc = np.nonzero(valid[r0:r0 + 400])
    if rr.size:
        d, _ = tree.query(np.c_[rr + r0, cc], k=1, workers=-1)
        dist[rr + r0, cc] = (d * L).astype("float32")
write_float(f"{OUT}/dist_lineament.tif", dist, valid)
log(f"dist_lineament m on land: median {np.nanmedian(dist[valid]):.0f}, max {np.nanmax(dist):.0f}")

with open(f"{OUT}/geology_feature_summary.json", "w") as f:
    json.dump({"groups": GROUPS, "land_share_pct": shares, "n_lines": [int(len(p)) for p in parts]}, f, indent=2)
log("Step 02 complete.")
