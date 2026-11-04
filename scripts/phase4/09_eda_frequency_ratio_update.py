"""
Phase 4 — Task C2: Updated Frequency Ratio Figure.
Generates the frequency-ratio chart with clean labels for open-ended classes
(e.g. '> 2000' instead of '2000 to 1e+06' and '< -50' for lower bounds).
Saves output under data/phase4/.
"""

import os
import sys
import numpy as np
import pandas as pd
import rasterio
import matplotlib.pyplot as plt

_P3_SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "phase3"))
if _P3_SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _P3_SCRIPT_DIR)

from p3_common import load_valid_mask, read_float, log
from p3_plot import C_NEG, INK2

OUT_EDA = "data/phase4/eda"
OUT_FIG = "data/phase4/figures"
os.makedirs(OUT_EDA, exist_ok=True)
os.makedirs(OUT_FIG, exist_ok=True)

FEAT_DIR = "data/phase3/features"
INV_DIR = "data/phase3/inventory"

valid = load_valid_mask()
with rasterio.open(f"{INV_DIR}/landslide_target_v3_30m.tif") as s:
    target = s.read(1) == 1
target &= valid
n_land, n_ls = int(valid.sum()), int(target.sum())

PHASE1 = {
    "lulc": "data/processed/lulc/mizoram_lulc_30m.tif",
    "map": "data/processed/rainfall/mean_annual_precip_30m.tif",
    "max_precip": "data/processed/rainfall/max_monthly_precip_30m.tif",
    "dist_fault": "data/processed/geology/mizoram_distance_to_faults_30m.tif",
}

CLASSES = {
    "slope": [0, 10, 20, 30, 40, 90],
    "elevation": [0, 300, 600, 900, 1200, 1500, 2300],
    "dist_road_any": [0, 30, 60, 120, 250, 500, 1000, 2000, 1e6],
    "dist_stream": [0, 100, 250, 500, 1000, 1e6],
    "relief_1km": [0, 150, 250, 350, 450, 2000],
    "twi": [0, 4, 5, 6, 7, 8, 30],
    "hand": [0, 25, 50, 100, 200, 400, 2000],
    "tpi_1km": [-1000, -50, -15, 15, 50, 1000],
    "dist_fault": [0, 2500, 5000, 10000, 20000, 1e6],
    "dist_river_osm": [0, 500, 1000, 2000, 4000, 1e6],
    "ndvi_dry2021": [-1, 0.3, 0.45, 0.55, 0.65, 0.75, 1],
}

fr = []
for name, edges in CLASSES.items():
    path = PHASE1.get(name, f"{FEAT_DIR}/{name}.tif")
    if not os.path.exists(path):
        continue
    a = read_float(path, valid)
    land_v, ls_v = a[valid], a[target]
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        al = ((land_v >= lo) & (land_v < hi)).mean() * 100
        sl = ((ls_v >= lo) & (ls_v < hi)).mean() * 100
        
        # Format label cleanly: replace open-ended intervals like 2000 to 1e+06 with > 2000
        if hi >= 1e5:
            lbl = f"> {lo:g}"
        elif lo <= -999:
            lbl = f"< {hi:g}"
        else:
            lbl = f"{lo:g} to {hi:g}"
            
        fr.append({
            "factor": name,
            "class": lbl,
            "order": i,
            "area_pct": al,
            "landslide_pct": sl,
            "frequency_ratio": sl / al if al > 0 else np.nan
        })
    del a, land_v, ls_v

if os.path.exists(PHASE1["lulc"]):
    a = read_float(PHASE1["lulc"], valid)
    names = {10: "tree", 20: "shrub", 30: "grass", 40: "crop", 50: "built-up", 60: "bare", 80: "water", 90: "wetland"}
    for i, code in enumerate(sorted(names)):
        al = (a[valid] == code).mean() * 100
        sl = (a[target] == code).mean() * 100
        fr.append({
            "factor": "lulc",
            "class": names[code],
            "order": i,
            "area_pct": al,
            "landslide_pct": sl,
            "frequency_ratio": sl / al if al > 0 else np.nan
        })
    del a

fr = pd.DataFrame(fr)
fr.round(3).to_csv(f"{OUT_EDA}/frequency_ratio_v4.csv", index=False)
log("Frequency ratio table exported to " + f"{OUT_EDA}/frequency_ratio_v4.csv")

show = [f for f in ["dist_road_any", "lulc", "slope", "elevation", "dist_stream", "relief_1km"] if f in set(fr.factor)]
fig, axes = plt.subplots(2, 3, figsize=(11, 6))
for ax, f in zip(axes.ravel(), show):
    t = fr[fr.factor == f].sort_values("order")
    ax.barh(np.arange(len(t)), t.frequency_ratio, color=C_NEG, height=0.62)
    ax.axvline(1, color=INK2, ls="--", lw=0.9)
    ax.set_yticks(np.arange(len(t)))
    ax.set_yticklabels(t["class"], fontsize=8)
    ax.set_title(f, fontsize=9.5, fontweight="bold")
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Frequency ratio (1 = as expected by area)", fontsize=8)

fig.suptitle("Landslide Frequency Ratios across Key Factors (Phase 4 Cleaned Labels)", fontsize=11, y=0.99)
fig.tight_layout()

for out_path in [f"{OUT_EDA}/fig_frequency_ratio.png", f"{OUT_FIG}/fig_frequency_ratio.png"]:
    fig.savefig(out_path, dpi=200)
    log(f"Saved: {out_path}")
plt.close(fig)

print("SUCCESS: Task C2 frequency ratio figure generated.")
