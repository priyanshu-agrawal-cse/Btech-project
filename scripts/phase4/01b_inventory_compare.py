"""
Phase 4 / Task B preparation - how do the NGDR landslide layers relate to the training data? (DATA-038)

Task B needs landslides that were not collected along roads and that the models never saw.
Before scoring anything, this measures for each NGDR layer: how much of it duplicates the
GSI pixels used in training (within 150 m), how much lies within 60 m of a road, and what
source, year and size fields say. GSI training share within 60 m is 76.06 %; land is 6.26 %.

Output: data/phase4/verification/ngdr_inventory_compare.csv
"""

import os
import warnings

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from scipy.spatial import cKDTree

warnings.filterwarnings("ignore")
ROOT = "data/raw/landslide_inventory/ngdr/extracted/LANDSLIDE_POINT_LANDSLIDE_POLYGON_STATE_MIZORAM_1793521854"
bnd = gpd.read_file("data/raw/mizoram_boundary.geojson").to_crs(32646)
region = bnd.union_all()

with rasterio.open("data/phase3/features/dist_road_any.tif") as s:
    road = s.read(1)
    tr = s.transform
    H, W = s.shape
    nod = s.nodata
train = pd.read_csv("data/phase3/inventory/landslide_pixels_v3.csv")
print("training pixel columns:", list(train.columns)[:12], len(train))
tx = tr.c + (train["col"].values + 0.5) * tr.a
ty = tr.f + (train["row"].values + 0.5) * tr.e
tree = cKDTree(np.c_[tx, ty])


def road_dist(x, y):
    c = ((x - tr.c) / tr.a).astype(int)
    r = ((y - tr.f) / tr.e).astype(int)
    ok = (r >= 0) & (r < H) & (c >= 0) & (c < W)
    v = np.full(len(x), np.nan, "float64")
    v[ok] = road[r[ok], c[ok]]
    v[v == nod] = np.nan
    return v


rows = []
pts = gpd.read_file(f"{ROOT}/LANDSLIDE_POINT_STATE_MIZORAM/LANDSLIDE_POINT_STATE_MIZORAM.shp").to_crs(32646)
pts = pts[pts.within(region)]
pol = gpd.read_file(f"{ROOT}/LANDSLIDE_POLYGON_STATE_MIZORAM/LANDSLIDE_POLYGON_STATE_MIZORAM.shp").to_crs(32646)
rep = pol.representative_point()
keep = rep.within(region)
pol, rep = pol[keep], rep[keep]

groups = [("NGDR points, all", pts.geometry.x.values, pts.geometry.y.values)]
for dt, sub in pol.groupby(pol["data_type"].astype(str)):
    r = rep.loc[sub.index]
    groups.append((f"NGDR polygons, data_type={dt}", r.x.values, r.y.values))
groups.append(("NGDR polygons, all", rep.x.values, rep.y.values))

for name, x, y in groups:
    d = road_dist(x, y)
    near, _ = tree.query(np.c_[x, y], k=1)
    rows.append({"layer": name, "n": len(x), "within_60m_of_road_pct": round(float(np.nanmean(d <= 60) * 100), 2),
                 "median_road_dist_m": round(float(np.nanmedian(d)), 0),
                 "within_150m_of_training_pct": round(float((near <= 150).mean() * 100), 2),
                 "unseen_beyond_150m": int((near > 150).sum())})

t = pd.DataFrame(rows)
os.makedirs("data/phase4/verification", exist_ok=True)
t.to_csv("data/phase4/verification/ngdr_inventory_compare.csv", index=False)
print(t.to_string(index=False))

print("\nPolygon area m2:", pol.area.describe().round(0).to_dict())
for c in ("data_type", "landslide_", "material_t", "lulc"):
    print(c, dict(pol[c].astype(str).value_counts().head(10)))
y = pts["history"].astype(str).str.extract(r"((?:19|20)\d{2})")[0]
print("\nPoint records with a year in `history`:", int(y.notna().sum()), "of", len(pts))
print(y.value_counts().sort_index().to_dict())
