"""
Phase 3 / Step 08 — Build FINAL_DATASET_v3.csv (DATA-025).

Sampling design (changes vs Phase 2 are documented in DATA-025):
  Positives : one 30 m pixel per landslide location (inventory v3, DATA-024).
  Exclusion : no negative within 150 m (5 px) of any landslide pixel.
  Negatives :
    set "neg_random"      — simple random sample of land cells outside the
                            exclusion zone, 1 negative per positive (1:1, the
                            balanced design of the professor's protocol).
                            Equal-allocation slope "strata" (Phase 2) are not
                            used: with quantile strata they are equivalent to
                            simple random sampling (DATA-017 H).
    set "neg_pool"        — 4 further random negatives per positive, kept for
                            the sampling-ratio sensitivity test.
    set "neg_roadmatched" — 1:1 negatives drawn so that their distance-to-road
                            distribution equals that of the landslides
                            (target-group background; Phillips et al. 2009).
                            Used only for the survey-bias sensitivity test.
  Blocks    : spatial block IDs of 1, 5, 10 and 20 km (row//b, col//b on the
              master grid) for spatial cross-validation.
Output: data/phase3/modeling/FINAL_DATASET_v3.csv, dataset_v3_summary.json
"""

import os
import sys
import numpy as np
import pandas as pd
import rasterio
from scipy import ndimage
from pyproj import Transformer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p3_common import (FEAT_DIR, INV_DIR, MOD_DIR, ensure_dirs, load_valid_mask, grid_info,
                       read_float, save_json, log, SEED)

ensure_dirs()
rng = np.random.default_rng(SEED)
tr, crs, H, W, L = grid_info()
valid = load_valid_mask()

FEATURES = {
    # terrain (DATA-019)
    "elevation": f"{FEAT_DIR}/elevation.tif", "slope": f"{FEAT_DIR}/slope.tif",
    "aspect_sin": f"{FEAT_DIR}/aspect_sin.tif", "aspect_cos": f"{FEAT_DIR}/aspect_cos.tif",
    "curv_general": f"{FEAT_DIR}/curv_general.tif", "curv_profile": f"{FEAT_DIR}/curv_profile.tif",
    "curv_plan": f"{FEAT_DIR}/curv_plan.tif", "tri": f"{FEAT_DIR}/tri.tif",
    "tpi_270m": f"{FEAT_DIR}/tpi_270m.tif", "tpi_1km": f"{FEAT_DIR}/tpi_1km.tif",
    "tpi_3km": f"{FEAT_DIR}/tpi_3km.tif", "relief_1km": f"{FEAT_DIR}/relief_1km.tif",
    # hydrology (DATA-020)
    "twi": f"{FEAT_DIR}/twi.tif", "spi_log": f"{FEAT_DIR}/spi_log.tif",
    "dist_stream": f"{FEAT_DIR}/dist_stream.tif", "hand": f"{FEAT_DIR}/hand.tif",
    # OpenStreetMap (DATA-021)
    "dist_road_any": f"{FEAT_DIR}/dist_road_any.tif", "dist_road_major": f"{FEAT_DIR}/dist_road_major.tif",
    "road_density_1km": f"{FEAT_DIR}/road_density_1km.tif", "dist_river_osm": f"{FEAT_DIR}/dist_river_osm.tif",
    # SoilGrids (DATA-022)
    "soil_clay_pct": f"{FEAT_DIR}/soil_clay_pct.tif", "soil_sand_pct": f"{FEAT_DIR}/soil_sand_pct.tif",
    "soil_bdod_gcm3": f"{FEAT_DIR}/soil_bdod_gcm3.tif",
    # Phase 1 layers that were correct and are re-used
    "lulc": "data/processed/lulc/mizoram_lulc_30m.tif",
    "map": "data/processed/rainfall/mean_annual_precip_30m.tif",
    "max_precip": "data/processed/rainfall/max_monthly_precip_30m.tif",
    "dist_fault": "data/processed/geology/mizoram_distance_to_faults_30m.tif",
}

# ---- positives -------------------------------------------------------------------
pix = pd.read_csv(f"{INV_DIR}/landslide_pixels_v3.csv")
pos_r, pos_c = pix.row.values, pix.col.values
n_pos = len(pix)
target = np.zeros((H, W), bool)
target[pos_r, pos_c] = True
excl = ndimage.binary_dilation(target, iterations=5)          # 150 m
cand = valid & ~excl
cand_idx = np.flatnonzero(cand.ravel())
log(f"positives={n_pos:,}; candidate negative cells={cand_idx.size:,} "
    f"(land {valid.sum():,} minus 150 m exclusion {int((excl & valid).sum()):,})")

# ---- random negatives (1:1 main + 4:1 pool) ---------------------------------------
draw = rng.choice(cand_idx, size=5 * n_pos, replace=False)
neg_main, neg_pool = draw[:n_pos], draw[n_pos:]

# ---- road-matched negatives ---------------------------------------------------------
droad = read_float(FEATURES["dist_road_any"], valid)
bins = np.array([0, 15, 30, 60, 120, 250, 500, 1000, 2000, np.inf])
pos_bin = np.digitize(droad[pos_r, pos_c], bins) - 1
cand_bin = np.digitize(droad.ravel()[cand_idx], bins) - 1
rm = []
for b in range(len(bins) - 1):
    need = int((pos_bin == b).sum())
    pool = cand_idx[cand_bin == b]
    if need:
        rm.append(rng.choice(pool, size=min(need, pool.size), replace=False))
neg_road = np.concatenate(rm)
road_bins_table = pd.DataFrame({
    "dist_road_bin_m": [f"{bins[i]:.0f}-{bins[i + 1]:.0f}" for i in range(len(bins) - 1)],
    "landslides": [int((pos_bin == i).sum()) for i in range(len(bins) - 1)],
    "land_cells": [int(((np.digitize(droad[valid], bins) - 1) == i).sum()) for i in range(len(bins) - 1)]})
road_bins_table["landslide_pct"] = 100 * road_bins_table.landslides / n_pos
road_bins_table["land_pct"] = 100 * road_bins_table.land_cells / valid.sum()
road_bins_table.round(3).to_csv(f"{MOD_DIR}/landslides_vs_road_distance.csv", index=False)
log(road_bins_table.round(2).to_string(index=False))
del droad

# ---- assemble rows ----------------------------------------------------------------------
def rc(idx):
    return idx // W, idx % W

parts = []
for name, (r, c), lab in [("pos", (pos_r, pos_c), 1), ("neg_random", rc(neg_main), 0),
                          ("neg_pool", rc(neg_pool), 0), ("neg_roadmatched", rc(neg_road), 0)]:
    parts.append(pd.DataFrame({"set": name, "landslide": lab, "row": r, "col": c}))
df = pd.concat(parts, ignore_index=True)
df["event_ids"] = ""
df.loc[df.set == "pos", "event_ids"] = pix.event_ids.values
df["district"] = ""
df.loc[df.set == "pos", "district"] = pix.district.astype(str).values
df["x_utm"] = tr.c + (df.col + 0.5) * tr.a
df["y_utm"] = tr.f + (df.row + 0.5) * tr.e
lon, lat = Transformer.from_crs(crs, "EPSG:4326", always_xy=True).transform(df.x_utm.values, df.y_utm.values)
df["lon"], df["lat"] = np.round(lon, 6), np.round(lat, 6)
for km in (1, 5, 10, 20):
    b = int(round(km * 1000 / L))
    df[f"block{km}"] = (df.row // b) * 10_000 + (df.col // b)

for name, path in FEATURES.items():
    a = read_float(path, valid)
    df[name] = a[df.row.values, df.col.values]
    del a
    log(f"  sampled {name}")

df.insert(0, "sample_id", np.arange(1, len(df) + 1))
out = f"{MOD_DIR}/FINAL_DATASET_v3.csv"
df.to_csv(out, index=False)
miss = df[list(FEATURES)].isna().sum()
summary = {"rows": int(len(df)), "rows_by_set": df.set.value_counts().to_dict(),
           "n_features": len(FEATURES), "features": list(FEATURES),
           "missing_values_per_feature": {k: int(v) for k, v in miss.items() if v},
           "exclusion_buffer_m": 150, "candidate_negative_cells": int(cand_idx.size),
           "blocks_10km_with_samples": int(df.block10.nunique()),
           "blocks_10km_with_landslides": int(df[df.landslide == 1].block10.nunique())}
save_json(summary, f"{MOD_DIR}/dataset_v3_summary.json")
log(f"Saved {out}: {len(df):,} rows; sets {summary['rows_by_set']}; missing {summary['missing_values_per_feature']}")
