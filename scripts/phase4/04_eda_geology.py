"""
Phase 4 / Task A4 - explore the geology factors (DATA-038).

Missing values, frequency ratio by rock group and by lineament-distance class, and Spearman
correlation with the existing factors. The method is that of scripts/phase3/09_eda_v3.py.

Outputs: data/phase4/eda/geology_frequency_ratio.csv, geology_correlation.csv,
         geology_missing.csv, fig_geology_frequency_ratio.png
"""

import json
import os
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "phase3")))
from p3_common import load_valid_mask, log, read_float
from p3_plot import C_NEG, INK2

OUT = "data/phase4/eda"
os.makedirs(OUT, exist_ok=True)
FEAT = "data/phase4/features"
GROUPS = {int(k): v for k, v in json.load(open(f"{FEAT}/geology_feature_summary.json"))["groups"].items()}

valid = load_valid_mask()
with rasterio.open("data/phase3/inventory/landslide_target_v3_30m.tif") as s:
    target = (s.read(1) == 1) & valid

fr = []
with rasterio.open(f"{FEAT}/lith_group.tif") as s:
    g = s.read(1)
for i, (code, name) in enumerate(GROUPS.items()):
    al, sl = (g[valid] == code).mean() * 100, (g[target] == code).mean() * 100
    fr.append({"factor": "lith_group", "class": name, "order": i, "area_pct": al, "landslide_pct": sl,
               "frequency_ratio": sl / al if al > 0 else np.nan})
miss = {"lith_group": float((g[valid] == 0).mean() * 100)}
del g

CLASSES = {"dist_lineament": [0, 250, 500, 1000, 2000, 4000, 1e6],
           "lineament_density_1km": [0, 0.01, 0.25, 0.5, 1, 2, 100]}
for name, edges in CLASSES.items():
    a = read_float(f"{FEAT}/{name}.tif", valid)
    miss[name] = float(np.isnan(a[valid]).mean() * 100)
    land_v, ls_v = a[valid], a[target]
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        al, sl = ((land_v >= lo) & (land_v < hi)).mean() * 100, ((ls_v >= lo) & (ls_v < hi)).mean() * 100
        lbl = f"> {lo:g}" if i == len(edges) - 2 else f"{lo:g} to {hi:g}"
        fr.append({"factor": name, "class": lbl, "order": i, "area_pct": al, "landslide_pct": sl,
                   "frequency_ratio": sl / al if al > 0 else np.nan})
    del a, land_v, ls_v
fr = pd.DataFrame(fr)
fr.round(3).to_csv(f"{OUT}/geology_frequency_ratio.csv", index=False)
log(fr[["factor", "class", "area_pct", "landslide_pct", "frequency_ratio"]].round(2).to_string(index=False))
pd.Series(miss, name="missing_land_pct").round(4).to_csv(f"{OUT}/geology_missing.csv")
log(f"Missing share of land %: {miss}")

d = pd.read_csv("data/phase4/modeling/FINAL_DATASET_v4.csv")
others = ["elevation", "slope", "relief_1km", "tpi_1km", "twi", "hand", "dist_stream", "dist_fault", "map",
          "max_precip", "soil_clay_pct", "soil_sand_pct", "dist_river_osm", "dist_road_any"]
R = d[["dist_lineament", "lineament_density_1km"] + others].corr("spearman").iloc[:2, 2:].T
R["max_abs"] = R.abs().max(axis=1)
R.round(3).to_csv(f"{OUT}/geology_correlation.csv")
log("Spearman with existing factors:\n" + R.round(3).sort_values("max_abs", ascending=False).head(6).to_string())

fig, axes = plt.subplots(1, 3, figsize=(12, 3.8))
for ax, f in zip(axes, ["lith_group", "dist_lineament", "lineament_density_1km"]):
    t = fr[fr.factor == f].sort_values("order")
    ax.barh(np.arange(len(t)), t.frequency_ratio, color=C_NEG, height=0.62)
    ax.axvline(1, color=INK2, ls="--", lw=0.9)
    ax.set_yticks(np.arange(len(t)))
    ax.set_yticklabels(t["class"], fontsize=8)
    ax.invert_yaxis()
    ax.set_title(f, fontsize=9.5, fontweight="bold")
    ax.set_xlabel("Frequency ratio (1 = as expected by area)", fontsize=8)
fig.tight_layout()
fig.savefig(f"{OUT}/fig_geology_frequency_ratio.png", dpi=180)
log("Step 04 complete.")
