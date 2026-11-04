"""
Phase 4 — Task C3: Updated Preview Bar Charts.
Generates cartographic preview figures using out-of-fold shares for BOTH land
and landslides (e.g. 59.4% land vs 3.7% landslides for Very Low zone in all-factor model),
ensuring consistency between the preview bar chart and the zone statistics table.
Saves new previews under data/phase4/maps/ and data/phase4/figures/.
"""

import os
import sys
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import ListedColormap, BoundaryNorm

_P3_SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "phase3"))
if _P3_SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _P3_SCRIPT_DIR)

from p3_common import log
from p3_plot import C_POS, C_GREY, INK2, ZONE_NAMES, ZONE_COLORS

os.makedirs("data/phase4/maps", exist_ok=True)
os.makedirs("data/phase4/figures", exist_ok=True)

CONFIGS = [
    {
        "tag": "",
        "title": "(all 25 factors)",
        "zone_tif": "data/final/mizoram_landslide_zones_v3.tif",
        "stats_csv": "data/phase3/maps/zone_statistics.csv",
        "out_base": "susceptibility_map_v3_preview.png",
    },
    {
        "tag": "_natural",
        "title": "(natural terrain, 21 factors)",
        "zone_tif": "data/final/mizoram_landslide_zones_v3_natural.tif",
        "stats_csv": "data/phase3/maps/zone_statistics_natural.csv",
        "out_base": "susceptibility_map_v3_natural_preview.png",
    },
]

bnd_path = "data/raw/mizoram_boundary.geojson"

for cfg in CONFIGS:
    tag = cfg["tag"]
    title = cfg["title"]
    zone_path = cfg["zone_tif"]
    stats_path = cfg["stats_csv"]
    
    if not os.path.exists(zone_path) or not os.path.exists(stats_path):
        log(f"Skipping {cfg['out_base']} — missing {zone_path} or {stats_path}")
        continue

    with rasterio.open(zone_path) as s:
        zone = s.read(1)
        tr = s.transform
        H, W = s.shape
        crs = s.crs

    zt = pd.read_csv(stats_path)
    bnd = gpd.read_file(bnd_path).to_crs(crs)

    # Subsample for fast preview display (every 4th pixel)
    sub = zone[::4, ::4].astype(float)
    sub[sub == 0] = np.nan
    ext = (tr.c, tr.c + W * tr.a, tr.f + H * tr.e, tr.f)
    cmap = ListedColormap(ZONE_COLORS)

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10.5, 9), gridspec_kw={"width_ratios": [1.5, 1]})

    # Map display
    a1.imshow(sub, cmap=cmap, norm=BoundaryNorm(np.arange(0.5, 6), 5), extent=ext, interpolation="nearest")
    bnd.boundary.plot(ax=a1, color=INK2, lw=0.5)
    a1.set_title(f"Landslide susceptibility zones, v3 {title}", fontsize=10, fontweight="bold")
    a1.grid(False)
    a1.tick_params(labelsize=7)
    a1.legend(handles=[mpatches.Patch(color=c, label=n) for c, n in zip(ZONE_COLORS, ZONE_NAMES)],
              loc="upper right", fontsize=8)

    # Bar chart using out-of-fold for both land and landslides
    y_ = np.arange(5)
    # Both use spatial out-of-fold shares
    a2.barh(y_ - 0.19, zt.area_pct_oof, height=0.36, color=C_GREY, label="% of land (spatial out-of-fold)")
    a2.barh(y_ + 0.19, zt.landslide_pct_spatial_oof, height=0.36, color=C_POS, label="% of landslides (spatial out-of-fold)")
    a2.set_yticks(y_)
    a2.set_yticklabels(ZONE_NAMES, fontsize=9)
    a2.grid(axis="y", visible=False)

    max_val = max(zt.area_pct_oof.max(), zt.landslide_pct_spatial_oof.max())
    a2.set_xlim(0, max_val * 1.15)

    for i, r in zt.iterrows():
        a2.text(r.area_pct_oof + 0.8, i - 0.19, f"{r.area_pct_oof:.1f}", va="center", fontsize=8, color=INK2)
        a2.text(r.landslide_pct_spatial_oof + 0.8, i + 0.19, f"{r.landslide_pct_spatial_oof:.1f}", va="center", fontsize=8, color=INK2)

    a2.set_xlabel("% of total", fontsize=8.5)
    a2.legend(fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.07), ncol=2)
    a2.set_title("Land vs Landslides per Zone\n(Out-of-Fold Spatial Validation)", fontsize=9.5, fontweight="bold")

    fig.tight_layout()

    out_p1 = f"data/phase4/maps/{cfg['out_base']}"
    out_p2 = f"data/phase4/figures/{cfg['out_base']}"
    fig.savefig(out_p1, dpi=200)
    fig.savefig(out_p2, dpi=200)
    plt.close(fig)
    log(f"Saved: {out_p1} and {out_p2}")

print("SUCCESS: Task C3 updated preview bar charts generated.")
