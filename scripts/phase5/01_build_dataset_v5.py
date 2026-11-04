"""
Phase 5 — Task P1.1: Build Dataset v5 with Mapped Polygons.

Constructs data/phase5/modeling/FINAL_DATASET_v5.csv by augmenting
FINAL_DATASET_v3.csv with 1,434 unseen GSI mapped polygons (set="pos_polygon", landslide=1)
and 1,434 random negative cells (set="neg_random_v5", landslide=0, seed=42) located >150 m
from all positives.

Samples the 21 natural factors for all new rows.
Outputs: data/phase5/modeling/FINAL_DATASET_v5.csv
"""

import os
import sys
import numpy as np
import pandas as pd
import geopandas as gpd
from scipy import ndimage
from scipy.spatial import cKDTree
import rasterio
from pyproj import Transformer

_P3_SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "phase3"))
if _P3_SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _P3_SCRIPT_DIR)

from p3_common import (
    BOUNDARY,
    FEAT_DIR,
    MOD_DIR,
    grid_info,
    load_valid_mask,
    read_float,
    log,
)

OUT_DIR = "data/phase5/modeling"
os.makedirs(OUT_DIR, exist_ok=True)
OUT_CSV = f"{OUT_DIR}/FINAL_DATASET_v5.csv"

# 1. Load Phase 3 dataset
log("Loading Phase 3 dataset...")
df_v3 = pd.read_csv(f"{MOD_DIR}/FINAL_DATASET_v3.csv")
assert len(df_v3) == 13013, f"Expected 13,013 rows in v3, got {len(df_v3)}"

tr, crs, H, W, L = grid_info()
valid = load_valid_mask()

# 2. Verify block10 formula reproduction on existing rows
b10_size = int(round(10 * 1000 / L))
b10_check = (df_v3.row // b10_size) * 10_000 + (df_v3.col // b10_size)
assert (df_v3.block10 - b10_check).abs().max() == 0, "block10 formula mismatch on v3 data!"
log("block10 formula verified on v3 rows.")

# 3. Extract the 1,434 polygon pixels exactly as in scripts/phase4/05_independent_validation.py
log("Extracting mapped polygon pixels from NGDR...")
ROOT_NGDR = "data/raw/landslide_inventory/ngdr/extracted/LANDSLIDE_POINT_LANDSLIDE_POLYGON_STATE_MIZORAM_1793521854"
shp_poly = f"{ROOT_NGDR}/LANDSLIDE_POLYGON_STATE_MIZORAM/LANDSLIDE_POLYGON_STATE_MIZORAM.shp"

region = gpd.read_file(BOUNDARY).to_crs(crs).union_all()
base_pix = pd.read_csv("data/phase3/inventory/landslide_pixels_v3.csv")
tree_train = cKDTree(np.c_[tr.c + (base_pix["col"].values + 0.5) * tr.a, tr.f + (base_pix["row"].values + 0.5) * tr.e])

pol = gpd.read_file(shp_poly).to_crs(crs)
pol = pol[~pol.geometry.duplicated()]
rep = pol.representative_point()
inside = rep.within(region)
pol, rep = pol[inside], rep[inside]
dt = pol["data_type"].fillna("blank")
v = rep[dt == "Mapped as polygon"]

x_poly, y_poly = v.x.values, v.y.values
near_train, _ = tree_train.query(np.c_[x_poly, y_poly], k=1)
keep_poly = near_train > 150.0
c_poly = ((x_poly - tr.c) / tr.a).astype(int)
r_poly = ((y_poly - tr.f) / tr.e).astype(int)
ok_poly = keep_poly & (r_poly >= 0) & (r_poly < H) & (c_poly >= 0) & (c_poly < W)
rc_poly = np.unique(np.c_[r_poly[ok_poly], c_poly[ok_poly]], axis=0)
rc_poly = rc_poly[valid[rc_poly[:, 0], rc_poly[:, 1]]]

n_poly = len(rc_poly)
log(f"Extracted {n_poly} unique land pixels from polygons.")
assert n_poly == 1434, f"Expected exactly 1,434 polygon pixels, got {n_poly}!"

# 4. Generate random negatives (seed 42), >150m from ALL positives (both GSI train and mapped polygons)
log("Sampling 1,434 random negatives (seed 42) >150m from all positives...")
target_all = np.zeros((H, W), dtype=bool)
target_all[base_pix.row.values, base_pix.col.values] = True
target_all[rc_poly[:, 0], rc_poly[:, 1]] = True

# 5 iterations of binary dilation on 30m grid = 150 m buffer
excl_all = ndimage.binary_dilation(target_all, iterations=5)
cand_neg = valid & ~excl_all
cand_neg_idx = np.flatnonzero(cand_neg.ravel())
log(f"Candidate negative cells: {cand_neg_idx.size:,} (outside 150m buffer of all {target_all.sum():,} positives)")

rng = np.random.default_rng(42)
neg_chosen_idx = rng.choice(cand_neg_idx, size=n_poly, replace=False)
rc_neg = np.c_[neg_chosen_idx // W, neg_chosen_idx % W]
assert len(rc_neg) == n_poly

# 5. Assemble new rows
log("Assembling new dataframe rows...")
new_rows = []
# (a) pos_polygon
df_poly = pd.DataFrame({
    "set": "pos_polygon",
    "landslide": 1,
    "row": rc_poly[:, 0],
    "col": rc_poly[:, 1],
})
# (b) neg_random_v5
df_neg = pd.DataFrame({
    "set": "neg_random_v5",
    "landslide": 0,
    "row": rc_neg[:, 0],
    "col": rc_neg[:, 1],
})
df_new = pd.concat([df_poly, df_neg], ignore_index=True)

df_new["event_ids"] = ""
df_new["district"] = ""
df_new["x_utm"] = tr.c + (df_new.col + 0.5) * tr.a
df_new["y_utm"] = tr.f + (df_new.row + 0.5) * tr.e
lon, lat = Transformer.from_crs(crs, "EPSG:4326", always_xy=True).transform(df_new.x_utm.values, df_new.y_utm.values)
df_new["lon"] = np.round(lon, 6)
df_new["lat"] = np.round(lat, 6)

for km in (1, 5, 10, 20):
    b = int(round(km * 1000 / L))
    df_new[f"block{km}"] = (df_new.row // b) * 10_000 + (df_new.col // b)

# 6. Sample the 21 natural factors from stored rasters
NATURAL_21 = [
    "elevation", "slope", "aspect_sin", "aspect_cos", "curv_profile", "curv_plan",
    "tpi_270m", "tpi_1km", "tpi_3km", "relief_1km", "twi", "spi_log", "dist_stream",
    "hand", "dist_fault", "map", "max_precip", "soil_clay_pct", "soil_sand_pct",
    "soil_bdod_gcm3", "dist_river_osm"
]

PHASE1_PATHS = {
    "map": "data/processed/rainfall/mean_annual_precip_30m.tif",
    "max_precip": "data/processed/rainfall/max_monthly_precip_30m.tif",
    "dist_fault": "data/processed/geology/mizoram_distance_to_faults_30m.tif",
}

for feat in NATURAL_21:
    path = PHASE1_PATHS.get(feat, f"{FEAT_DIR}/{feat}.tif")
    assert os.path.exists(path), f"Missing feature raster: {path}"
    arr = read_float(path, valid)
    df_new[feat] = arr[df_new.row.values, df_new.col.values]
    del arr
    log(f"  sampled natural factor: {feat}")

# Combine with df_v3 while aligning columns
# Road, LULC, curv_general, tri columns are set to NaN for new rows (do not add road or land-cover factors)
cols_all = list(df_v3.columns)
for col in cols_all:
    if col not in df_new.columns:
        df_new[col] = np.nan

df_new = df_new[cols_all]

df_v5 = pd.concat([df_v3, df_new], ignore_index=True)
df_v5["sample_id"] = np.arange(1, len(df_v5) + 1)

assert len(df_v5) == 13013 + 1434 * 2, f"Unexpected row count: {len(df_v5)}"
# Verify first 13,013 rows identical
pd.testing.assert_frame_equal(df_v5.iloc[:13013].drop(columns=["sample_id"]), df_v3.drop(columns=["sample_id"]))
log("Verified: original 13,013 rows perfectly preserved.")

df_v5.to_csv(OUT_CSV, index=False)
log(f"SUCCESS: Saved {OUT_CSV} with {len(df_v5):,} rows and {len(df_v5.columns)} columns.")
log(f"Set counts:\n{df_v5['set'].value_counts().to_string()}")
