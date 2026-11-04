"""
Phase 4 / Task B - test the v3 maps on landslides they never saw (DATA-040).

No model is retrained here. The test data are the GSI polygons from NGDR, fixed in advance:

  primary:  data_type "Mapped as polygon"
  others:   "Mapped as point bufferred to polygon", polygons with a blank data_type, all
            polygons together, and NGDR points (the larger, later release of the road-based
            survey the models were trained on, included for comparison and by year)

Steps follow Section 6 of the Phase 4 work plan: inside the boundary, exact duplicates
removed, one pixel per landslide (representative_point), anything within 150 m of a training
pixel removed, road bias measured, and each ranking scored. curve() is the Phase 3 method, so
curves start at the origin. Mizoram land = data/phase3/features/valid_mask_30m.tif.

These records are unseen, but they are GSI records rather than an outside survey, and their
mapping method is not stated in the download.

Outputs: data/phase4/verification/independent_validation.csv, _zones.csv, _by_year.csv,
         fig_independent_validation.png
"""

import os
import sys
import warnings

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "phase3")))
from p3_common import BOUNDARY, grid_info, load_valid_mask, log, read_float
from p3_plot import C_AQUA, C_NEG, C_POS, INK2, ZONE_NAMES

warnings.filterwarnings("ignore")
OUT = "data/phase4/verification"
os.makedirs(OUT, exist_ok=True)
ROOT = "data/raw/landslide_inventory/ngdr/extracted/LANDSLIDE_POINT_LANDSLIDE_POLYGON_STATE_MIZORAM_1793521854"
EX = 150.0
tr, crs, H, W, L = grid_info()
valid = load_valid_mask()
region = gpd.read_file(BOUNDARY).to_crs(crs).union_all()
base = pd.read_csv("data/phase3/inventory/landslide_pixels_v3.csv")
tree = cKDTree(np.c_[tr.c + (base["col"].values + 0.5) * tr.a, tr.f + (base["row"].values + 0.5) * tr.e])


def prepare(x, y, name):
    """Unique land pixels, more than 150 m from every training pixel."""
    near, _ = tree.query(np.c_[x, y], k=1)
    keep = near > EX
    c = ((x - tr.c) / tr.a).astype(int)
    r = ((y - tr.f) / tr.e).astype(int)
    ok = keep & (r >= 0) & (r < H) & (c >= 0) & (c < W)
    rc = np.unique(np.c_[r[ok], c[ok]], axis=0)
    rc = rc[valid[rc[:, 0], rc[:, 1]]]
    log(f"{name}: {len(x)} records, {int(keep.sum())} beyond {EX:.0f} m, {len(rc)} unique land pixels")
    return rc, len(x), int(keep.sum())


def curve(sv, t):
    """Phase 3 curve() for a test set: sv = sorted land scores, t = sorted test scores."""
    q = sv[np.round(np.linspace(sv.size - 1, 0, 1001)).astype(int)]
    area = (1 - np.searchsorted(sv, q, side="left") / sv.size) * 100
    cap = (1 - np.searchsorted(t, q, side="left") / t.size) * 100
    return np.r_[0.0, area], np.r_[0.0, cap]


pol = gpd.read_file(f"{ROOT}/LANDSLIDE_POLYGON_STATE_MIZORAM/LANDSLIDE_POLYGON_STATE_MIZORAM.shp").to_crs(crs)
pol = pol[~pol.geometry.duplicated()]
rep = pol.representative_point()
inside = rep.within(region)
pol, rep = pol[inside], rep[inside]
pts = gpd.read_file(f"{ROOT}/LANDSLIDE_POINT_STATE_MIZORAM/LANDSLIDE_POINT_STATE_MIZORAM.shp").to_crs(crs)
pts = pts[~pts.geometry.duplicated()]
pts = pts[pts.within(region)]
years = pts["history"].astype(str).str.extract(r"((?:19|20)\d{2})")[0]
dt = pol["data_type"].fillna("blank")

SETS = {"Polygons: mapped as polygon (primary)": rep[dt == "Mapped as polygon"],
        "Polygons: point buffered to polygon": rep[dt == "Mapped as point bufferred to polygon"],
        "Polygons: blank data_type": rep[dt == "blank"],
        "Polygons: all": rep,
        "Points: all NGDR": pts.geometry}
tests = {k: prepare(v.x.values, v.y.values, k) for k, v in SETS.items()}

road = read_float("data/phase3/features/dist_road_any.tif", valid)
RANK = {"All-factor map v3": "data/final/mizoram_landslide_susceptibility_v3.tif",
        "Natural-terrain map v3": "data/final/mizoram_landslide_susceptibility_v3_natural.tif",
        "Baseline: nearest to a road first": None}
ZONES = {"All-factor map v3": "data/final/mizoram_landslide_zones_v3.tif",
         "Natural-terrain map v3": "data/final/mizoram_landslide_zones_v3_natural.tif"}
corridor = valid & (road <= 60)
rows, zrows, ycurves = [], [], {}
for rn, path in RANK.items():
    sc = -road if path is None else read_float(path, valid)
    vmin = np.nanmin(sc[valid])
    land = np.sort(np.nan_to_num(sc[valid], nan=vmin))
    cland = np.sort(np.nan_to_num(sc[corridor], nan=vmin))
    for tn, (rc, n0, n1) in tests.items():
        v = np.sort(np.nan_to_num(sc[rc[:, 0], rc[:, 1]], nan=vmin))
        a, c = curve(land, v)
        rec = {"ranking": rn, "test_set": tn, "records": n0, "beyond_150m": n1, "test_pixels": len(v),
               "AUC": np.trapezoid(c / 100, a / 100)}
        for top in (1, 5, 10, 20):
            rec[f"captured_top_{top}pct"] = float(np.interp(top, a, c))
        m = corridor[rc[:, 0], rc[:, 1]]
        if m.sum() >= 20:
            a2, c2 = curve(cland, np.sort(np.nan_to_num(sc[rc[m, 0], rc[m, 1]], nan=vmin)))
            rec["AUC_within_60m_of_road"] = np.trapezoid(c2 / 100, a2 / 100)
            rec["n_within_60m"] = int(m.sum())
        rows.append(rec)
        if tn.endswith("(primary)"):
            ycurves[rn] = (a, c, rec["AUC"])
    if path is not None:
        with rasterio.open(ZONES[rn]) as s:
            z = s.read(1)
        for tn, (rc, _, _) in tests.items():
            vals = z[rc[:, 0], rc[:, 1]]
            for i, nm in enumerate(ZONE_NAMES, 1):
                al, sl = (z[valid] == i).mean() * 100, (vals == i).mean() * 100
                zrows.append({"ranking": rn, "test_set": tn, "zone": nm, "area_pct": al, "landslide_pct": sl,
                              "frequency_ratio": sl / al if al else np.nan})
    for y0, y1, lab in [(0, 2015, "to 2015"), (2016, 2019, "2016-2019"), (2020, 2023, "2020-2023"), (2024, 2099, "2024 onward")]:
        yr = pd.to_numeric(years, errors="coerce")
        g = pts.geometry[(yr >= y0) & (yr <= y1)]
        if not len(g):
            continue
        rc, n0, n1 = prepare(g.x.values, g.y.values, f"Points {lab}")
        v = np.sort(np.nan_to_num(sc[rc[:, 0], rc[:, 1]], nan=vmin))
        if len(v) >= 20:
            a, c = curve(land, v)
            zrows.append({"ranking": rn, "test_set": f"BYYEAR {lab}", "zone": "all", "area_pct": n0,
                          "landslide_pct": len(v), "frequency_ratio": np.trapezoid(c / 100, a / 100)})
    del sc, land, cland

t = pd.DataFrame(rows)
for tn, (rc, _, _) in tests.items():
    d = road[rc[:, 0], rc[:, 1]]
    t.loc[t.test_set == tn, "within_60m_of_road_pct"] = float(np.nanmean(d <= 60) * 100)
t.round(3).to_csv(f"{OUT}/independent_validation.csv", index=False)
z = pd.DataFrame(zrows)
z[~z.test_set.str.startswith("BYYEAR")].round(3).to_csv(f"{OUT}/independent_validation_zones.csv", index=False)
by = z[z.test_set.str.startswith("BYYEAR")].rename(columns={"area_pct": "records", "landslide_pct": "test_pixels", "frequency_ratio": "AUC"})
by.drop(columns="zone").round(3).to_csv(f"{OUT}/independent_validation_by_year.csv", index=False)
pd.set_option("display.width", 190, "display.max_columns", 30)
log(t.round(3).drop(columns=["records", "beyond_150m"]).to_string(index=False))
log(z[z.test_set.str.endswith("(primary)")].round(2).to_string(index=False))
log(by.drop(columns="zone").round(3).to_string(index=False))

fig, ax = plt.subplots(figsize=(6.6, 5.2))
for (n, (a, c, auc)), col in zip(ycurves.items(), [C_POS, C_NEG, C_AQUA]):
    ax.plot(a, c, color=col, lw=1.8, label=f"{n} (AUC {auc:.3f})")
ax.plot([0, 100], [0, 100], ls=":", lw=0.8, color=INK2)
ax.set_xlabel("Share of Mizoram's land, highest score first (%)")
ax.set_ylabel("Unseen mapped landslides captured (%)")
ax.set_title("Prediction of GSI mapped polygons not used in training")
ax.legend(fontsize=8, loc="lower right")
fig.tight_layout()
fig.savefig(f"{OUT}/fig_independent_validation.png", dpi=180)
log("Step 05 complete.")
