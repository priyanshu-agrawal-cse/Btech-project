"""
Phase 4 / Task A3 - add the geology factors to the modelling table (DATA-038).

Samples the new rasters at the rows and columns of FINAL_DATASET_v3.csv. Every row, the
sample_id order and every existing column must stay exactly as they were.

Output: data/phase4/modeling/FINAL_DATASET_v4.csv
"""

import os
import sys

import numpy as np
import pandas as pd
import rasterio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "phase3")))
from p3_common import log

SRC = "data/phase3/modeling/FINAL_DATASET_v3.csv"
DST = "data/phase4/modeling/FINAL_DATASET_v4.csv"
NEW = ["lith_group", "dist_lineament", "lineament_density_1km"]
os.makedirs(os.path.dirname(DST), exist_ok=True)

v3 = pd.read_csv(SRC)
v4 = v3.copy()
for f in NEW:
    with rasterio.open(f"data/phase4/features/{f}.tif") as s:
        a = s.read(1)
        nd = s.nodata
    v = a[v3.row.values, v3.col.values].astype("float32")
    if f != "lith_group":
        v[v == nd] = np.nan
    v4[f] = v

assert len(v4) == 13013
assert (v4.sample_id.values == v3.sample_id.values).all()
pd.testing.assert_frame_equal(v4[v3.columns], v3)
v4["lith_group"] = v4.lith_group.astype("int16")
v4.to_csv(DST, index=False)
log(f"{DST}: {v4.shape}; missing {v4[NEW].isna().sum().to_dict()}; lith_group 0 rows {(v4.lith_group == 0).sum()}")
