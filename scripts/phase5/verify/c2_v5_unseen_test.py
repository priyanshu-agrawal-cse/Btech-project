"""
Phase 5 verification / C2 - v5 against v3 on landslides neither map trained on (DATA-044).

The Phase 5 plan tested v5 only on 2024 road-based points, which favour a road-trained model.
This adds the two polygon groups never used in training: "point buffered" and blank data_type,
all more than 150 m from every v5 training pixel. Each is also split by whether its map sheet
held any training polygon, because inside those sheets v5 may simply recognise the region.

Also reports how concentrated the training polygons are, and the land-wide map agreement.
Outputs: data/phase5/verification/v5_unseen_test.csv, polygon_sheet_counts.csv
"""

import os
import sys
import warnings

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "phase3")))
from p3_common import BOUNDARY, grid_info, load_valid_mask, log, read_float

warnings.filterwarnings("ignore")
OUT = "data/phase5/verification"
os.makedirs(OUT, exist_ok=True)
ROOT = "data/raw/landslide_inventory/ngdr/extracted/LANDSLIDE_POINT_LANDSLIDE_POLYGON_STATE_MIZORAM_1793521854"
tr, crs, H, W, L = grid_info()
valid = load_valid_mask()
region = gpd.read_file(BOUNDARY).to_crs(crs).union_all()

pol = gpd.read_file(f"{ROOT}/LANDSLIDE_POLYGON_STATE_MIZORAM/LANDSLIDE_POLYGON_STATE_MIZORAM.shp").to_crs(crs)
pol = pol[~pol.geometry.duplicated()]
rep = pol.representative_point()
keep = rep.within(region)
pol, rep = pol[keep].copy(), rep[keep]
pol["dt"] = pol["data_type"].fillna("blank")
pol["px"], pol["py"] = rep.x.values, rep.y.values

mapped = pol[pol.dt == "Mapped as polygon"]
sheets = pol.groupby(["toposheet", "dt"]).size().unstack(fill_value=0).sort_values("Mapped as polygon", ascending=False)
sheets.to_csv(f"{OUT}/polygon_sheet_counts.csv")
c = mapped.toposheet.value_counts()
log(f"Mapped polygons by map sheet: {len(c)} sheets; top 1 {c.iloc[0] / len(mapped):.1%}, top 3 {c.iloc[:3].sum() / len(mapped):.1%}, top 5 {c.iloc[:5].sum() / len(mapped):.1%}")
log(sheets.head(10).to_string())

df = pd.read_csv("data/phase5/modeling/FINAL_DATASET_v5.csv")
pos = df[df.landslide == 1]
tree = cKDTree(np.c_[tr.c + (pos["col"].values + 0.5) * tr.a, tr.f + (pos["row"].values + 0.5) * tr.e])
trained_sheets = set(c.index)


def pixels(sub):
    x, y = sub.px.values, sub.py.values
    near, _ = tree.query(np.c_[x, y], k=1)
    ok = near > 150
    rc = np.unique(np.c_[((y[ok] - tr.f) / tr.e).astype(int), ((x[ok] - tr.c) / tr.a).astype(int)], axis=0)
    return rc[valid[rc[:, 0], rc[:, 1]]]


other = pol[pol.dt != "Mapped as polygon"]
TESTS = {"point buffered": other[other.dt.str.startswith("Mapped as point")],
         "blank data_type": other[other.dt == "blank"],
         "all unused polygons": other,
         "unused, in sheets with training polygons": other[other.toposheet.isin(trained_sheets)],
         "unused, in sheets with no training polygons": other[~other.toposheet.isin(trained_sheets)]}
tests = {k: pixels(v) for k, v in TESTS.items()}


def auc(sv, t):
    q = sv[np.round(np.linspace(sv.size - 1, 0, 1001)).astype(int)]
    a = np.r_[0.0, (1 - np.searchsorted(sv, q, side="left") / sv.size) * 100]
    c_ = np.r_[0.0, (1 - np.searchsorted(t, q, side="left") / t.size) * 100]
    return float(np.trapezoid(c_ / 100, a / 100)), float(np.interp(20, a, c_))


road = read_float("data/phase3/features/dist_road_any.tif", valid)
RANK = {"Natural map v5": "data/final/mizoram_landslide_susceptibility_v5_natural.tif",
        "Natural map v3": "data/final/mizoram_landslide_susceptibility_v3_natural.tif",
        "All-factor map v3": "data/final/mizoram_landslide_susceptibility_v3.tif",
        "Road distance": None}
rows, keep_scores = [], {}
for rn, p in RANK.items():
    sc = -road if p is None else read_float(p, valid)
    vmin = np.nanmin(sc[valid])
    land = np.sort(np.nan_to_num(sc[valid], nan=vmin))
    if rn.startswith("Natural"):
        keep_scores[rn] = sc[valid][::97].copy()
    for tn, rc in tests.items():
        if len(rc) < 20:
            continue
        a, t20 = auc(land, np.sort(np.nan_to_num(sc[rc[:, 0], rc[:, 1]], nan=vmin)))
        rows.append({"ranking": rn, "test_set": tn, "pixels": len(rc), "AUC": round(a, 4), "captured_top_20pct": round(t20, 2)})
    del sc, land
t = pd.DataFrame(rows)
t.to_csv(f"{OUT}/v5_unseen_test.csv", index=False)
log(t.pivot(index="test_set", columns="ranking", values="AUC").join(t.groupby("test_set").pixels.first()).to_string())
rho = spearmanr(keep_scores["Natural map v5"], keep_scores["Natural map v3"], nan_policy="omit")[0]
log(f"Land-wide Spearman, v5 map against v3 map: {rho:.3f}")
