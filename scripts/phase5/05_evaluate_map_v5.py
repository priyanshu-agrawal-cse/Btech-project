"""
Phase 5 — Task P1.4: Map Evaluation, Zonation and Independent Testing on 2024+ NGDR Points.

1. Zonation:
   Computes 5 Jenks natural breaks via KMeans on a 1,000,000 cell random sample of valid land cells (seed=42).
   Generates data/final/mizoram_landslide_zones_v5_natural.tif.
   Computes zone area %, landslide capture %, and frequency ratios.
   Saves data/phase5/maps/zone_statistics_v5_natural.csv.

2. Independent Validation on NGDR 2024+ Points:
   Extracts NGDR points from 2024 onward, located >150 m from EVERY training pixel
   (both GSI base points and mapped polygons).
   Evaluates prediction performance (AUC, capture rates) comparing:
   - v5 natural map
   - v3 natural map
   - v3 all-factor map
   - Road distance alone (baseline)
   Saves data/phase5/maps/independent_validation_2024_v5.csv.
"""

import os
import sys
import json
import warnings
import numpy as np
import pandas as pd
import rasterio
import geopandas as gpd
from sklearn.cluster import KMeans
from scipy.spatial import cKDTree

_P3_SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "phase3"))
if _P3_SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _P3_SCRIPT_DIR)

from p3_common import (BOUNDARY, FEAT_DIR, INV_DIR, load_valid_mask, read_float,
                       write_uint8, grid_info, log, SEED)
from p3_plot import ZONE_NAMES

warnings.filterwarnings("ignore")

OUT_MAPS = "data/phase5/maps"
os.makedirs(OUT_MAPS, exist_ok=True)
os.makedirs("data/final", exist_ok=True)

tr, crs, H, W, L = grid_info()
valid = load_valid_mask()
rng = np.random.default_rng(SEED)

MAP_FINAL_V5 = "data/final/mizoram_landslide_susceptibility_v5_natural.tif"
MAP_OOF_V5 = f"{OUT_MAPS}/susceptibility_v5_natural_spatial_oof.tif"
ZONES_FINAL_V5 = "data/final/mizoram_landslide_zones_v5_natural.tif"

log(f"Reading v5 final and out-of-fold rasters...")
final = read_float(MAP_FINAL_V5, valid)
oof = read_float(MAP_OOF_V5, valid)

# Load combined training landslides target (base GSI + polygons)
df_v5 = pd.read_csv("data/phase5/modeling/FINAL_DATASET_v5.csv")
train_pos = df_v5[df_v5.landslide == 1]
target_all = np.zeros((H, W), dtype=bool)
target_all[train_pos.row.values, train_pos.col.values] = True
target_all = target_all & valid
n_ls_train = int(target_all.sum())
log(f"Total training landslide cells: {n_ls_train:,}")

# --- 1. Natural Breaks Zonation ---
log("\nComputing natural breaks on 1,000,000 land cell sample (seed 42)...")
land = final[valid & np.isfinite(final)]
sample = rng.choice(land, size=min(1_000_000, land.size), replace=False).reshape(-1, 1)
km = KMeans(n_clusters=5, n_init=4, random_state=SEED).fit(sample)
cent = np.sort(km.cluster_centers_.ravel())
breaks = (cent[:-1] + cent[1:]) / 2
edges = np.r_[0.0, breaks, 1.0001]
log(f"Natural break thresholds: {np.round(breaks, 4).tolist()}")

zone = np.zeros((H, W), dtype="uint8")
zone[valid] = np.digitize(np.nan_to_num(final[valid], nan=0.0), breaks) + 1
write_uint8(ZONES_FINAL_V5, zone, nodata=0)
log(f"Saved zonation map to {ZONES_FINAL_V5}")

zone_oof = np.zeros((H, W), dtype="uint8")
zone_oof[valid] = np.digitize(np.nan_to_num(oof[valid], nan=0.0), breaks) + 1

zrows = []
for i, nm in enumerate(ZONE_NAMES, 1):
    a = (zone[valid] == i).mean() * 100
    s_ = (zone[target_all] == i).mean() * 100
    a2 = (zone_oof[valid] == i).mean() * 100
    p_ = (zone_oof[target_all] == i).mean() * 100
    zrows.append({
        "zone": nm,
        "score_from": round(float(edges[i - 1]), 4),
        "score_to": round(float(min(edges[i], 1.0)), 4),
        "area_pct": round(float(a), 3),
        "landslide_pct_training": round(float(s_), 3),
        "FR_training": round(float(s_ / a), 3) if a > 0 else np.nan,
        "area_pct_oof": round(float(a2), 3),
        "landslide_pct_spatial_oof": round(float(p_), 3),
        "FR_spatial_oof": round(float(p_ / a2), 3) if a2 > 0 else np.nan,
    })

zt = pd.DataFrame(zrows)
zt_path = f"{OUT_MAPS}/zone_statistics_v5_natural.csv"
zt.to_csv(zt_path, index=False)
log(f"\nZone Statistics (v5 Natural):\n{zt.to_string(index=False)}")


# --- 2. Independent Validation on 2024+ NGDR Points ---
log("\nExtracting NGDR points from 2024 onward...")
ROOT_NGDR = "data/raw/landslide_inventory/ngdr/extracted/LANDSLIDE_POINT_LANDSLIDE_POLYGON_STATE_MIZORAM_1793521854"
shp_pts = f"{ROOT_NGDR}/LANDSLIDE_POINT_STATE_MIZORAM/LANDSLIDE_POINT_STATE_MIZORAM.shp"

region = gpd.read_file(BOUNDARY).to_crs(crs).union_all()
pts = gpd.read_file(shp_pts).to_crs(crs)
pts = pts[~pts.geometry.duplicated()]
pts = pts[pts.within(region)]

years = pts["history"].astype(str).str.extract(r"((?:19|20)\d{2})")[0]
yr = pd.to_numeric(years, errors="coerce")
pts_2024 = pts[(yr >= 2024) & (yr <= 2099)]
log(f"Total NGDR points from 2024 onward inside region: {len(pts_2024):,}")

# Tree of ALL training pixels (GSI base + polygon positives)
tree_all_train = cKDTree(np.c_[
    tr.c + (train_pos["col"].values + 0.5) * tr.a,
    tr.f + (train_pos["row"].values + 0.5) * tr.e
])

near_train, _ = tree_all_train.query(np.c_[pts_2024.geometry.x.values, pts_2024.geometry.y.values], k=1)
keep_2024 = near_train > 150.0
c_2024 = ((pts_2024.geometry.x.values - tr.c) / tr.a).astype(int)
r_2024 = ((pts_2024.geometry.y.values - tr.f) / tr.e).astype(int)
ok_2024 = keep_2024 & (r_2024 >= 0) & (r_2024 < H) & (c_2024 >= 0) & (c_2024 < W)
rc_2024 = np.unique(np.c_[r_2024[ok_2024], c_2024[ok_2024]], axis=0)
rc_2024 = rc_2024[valid[rc_2024[:, 0], rc_2024[:, 1]]]

log(f"NGDR 2024+ test set: {len(pts_2024)} records, {int(keep_2024.sum())} >150m from training, {len(rc_2024)} unique land pixels")

# Define curve function matching Phase 3/4
def calc_curve(sv, t):
    q = sv[np.round(np.linspace(sv.size - 1, 0, 1001)).astype(int)]
    area = (1 - np.searchsorted(sv, q, side="left") / sv.size) * 100
    cap = (1 - np.searchsorted(t, q, side="left") / t.size) * 100
    return np.r_[0.0, area], np.r_[0.0, cap]

road = read_float("data/phase3/features/dist_road_any.tif", valid)

MODELS_EVAL = {
    "Natural-terrain map v5 (GSI + Polygons)": MAP_FINAL_V5,
    "Natural-terrain map v3 (GSI only)": "data/final/mizoram_landslide_susceptibility_v3_natural.tif",
    "All-factor map v3": "data/final/mizoram_landslide_susceptibility_v3.tif",
    "Road distance alone (baseline)": None,
}

eval_rows = []
for m_name, path in MODELS_EVAL.items():
    if path is None:
        sc = -road
    else:
        sc = read_float(path, valid)
    vmin = np.nanmin(sc[valid])
    land_sorted = np.sort(np.nan_to_num(sc[valid], nan=vmin))
    test_scores = np.sort(np.nan_to_num(sc[rc_2024[:, 0], rc_2024[:, 1]], nan=vmin))

    a_curve, c_curve = calc_curve(land_sorted, test_scores)
    auc = float(np.trapezoid(c_curve / 100, a_curve / 100))
    top5 = float(c_curve[np.searchsorted(a_curve, 5.0, side="left")])
    top20 = float(c_curve[np.searchsorted(a_curve, 20.0, side="left")])

    eval_rows.append({
        "Model": m_name,
        "Test_Set": "NGDR 2024 onward (>150m from all training)",
        "Test_Pixels": len(rc_2024),
        "AUC": round(auc, 4),
        "Top_5pct_land_captured": round(top5, 2),
        "Top_20pct_land_captured": round(top20, 2),
    })

eval_df = pd.DataFrame(eval_rows)
csv_eval_path = f"{OUT_MAPS}/independent_validation_2024_v5.csv"
eval_df.to_csv(csv_eval_path, index=False)
log(f"\nIndependent Test Results on 2024+ NGDR Points:\n{eval_df.to_string(index=False)}")
log(f"\nSaved {csv_eval_path}")
log("Step 05 complete.")
