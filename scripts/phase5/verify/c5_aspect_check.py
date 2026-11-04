"""
Phase 5 verification / C5 - which way do the landslide groups face? (DATA-045)

aspect_cos alone separates mapped polygons from same-area negatives with AUC 0.78 when flipped.
A preference that strong is unusual, so this compares compass quadrants for each group.
Output: data/phase5/verification/aspect_by_group.csv
"""

import os
import sys
import warnings

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "phase3")))
from p3_common import BOUNDARY, FEAT_DIR, grid_info, load_valid_mask, log, read_float

warnings.filterwarnings("ignore")
ROOT = "data/raw/landslide_inventory/ngdr/extracted/LANDSLIDE_POINT_LANDSLIDE_POLYGON_STATE_MIZORAM_1793521854"
tr, crs, H, W, L = grid_info()
valid = load_valid_mask()
region = gpd.read_file(BOUNDARY).to_crs(crs).union_all()
sn = read_float(f"{FEAT_DIR}/aspect_sin.tif", valid)
cs = read_float(f"{FEAT_DIR}/aspect_cos.tif", valid)
sl = read_float(f"{FEAT_DIR}/slope.tif", valid)


def rc(x, y):
    c, r = ((x - tr.c) / tr.a).astype(int), ((y - tr.f) / tr.e).astype(int)
    u = np.unique(np.c_[r, c], axis=0)
    u = u[(u[:, 0] >= 0) & (u[:, 0] < H) & (u[:, 1] >= 0) & (u[:, 1] < W)]
    return u[valid[u[:, 0], u[:, 1]]]


df = pd.read_csv("data/phase5/modeling/FINAL_DATASET_v5.csv")
pol = gpd.read_file(f"{ROOT}/LANDSLIDE_POLYGON_STATE_MIZORAM/LANDSLIDE_POLYGON_STATE_MIZORAM.shp").to_crs(crs)
rep = pol.representative_point()
pol, rep = pol[rep.within(region)], rep[rep.within(region)]
dt = pol["data_type"].fillna("blank")
pts = gpd.read_file(f"{ROOT}/LANDSLIDE_POINT_STATE_MIZORAM/LANDSLIDE_POINT_STATE_MIZORAM.shp").to_crs(crs)
pts = pts[pts.within(region)]
yr = pd.to_numeric(pts["history"].astype(str).str.extract(r"((?:19|20)\d{2})")[0], errors="coerce")
p24 = pts[yr >= 2024].geometry

groups = {"All land (1 in 97 cells)": None,
          "GSI training points": df.loc[df.set == "pos", ["row", "col"]].values,
          "Mapped polygons (v5 training)": df.loc[df.set == "pos_polygon", ["row", "col"]].values,
          "Polygons: point buffered": rc(rep[dt.str.startswith("Mapped as point")].x.values, rep[dt.str.startswith("Mapped as point")].y.values),
          "Polygons: blank data_type": rc(rep[dt == "blank"].x.values, rep[dt == "blank"].y.values),
          "NGDR points 2024 onward": rc(p24.x.values, p24.y.values)}
out = []
for n, u in groups.items():
    if u is None:
        s, c, b = sn[valid][::97], cs[valid][::97], sl[valid][::97]
    else:
        s, c, b = sn[u[:, 0], u[:, 1]], cs[u[:, 0], u[:, 1]], sl[u[:, 0], u[:, 1]]
    az = (np.degrees(np.arctan2(s, c)) + 360) % 360
    q = pd.cut((az + 45) % 360, [0, 90, 180, 270, 360], labels=["N", "E", "S", "W"], include_lowest=True)
    v = pd.Series(q).value_counts(normalize=True).mul(100).round(1)
    out.append({"group": n, "pixels": len(s), "north_pct": v["N"], "east_pct": v["E"], "south_pct": v["S"], "west_pct": v["W"],
                "mean_aspect_cos": round(float(np.nanmean(c)), 3), "median_slope": round(float(np.nanmedian(b)), 1)})
t = pd.DataFrame(out)
t.to_csv("data/phase5/verification/aspect_by_group.csv", index=False)
pd.set_option("display.width", 150)
log(t.to_string(index=False))
