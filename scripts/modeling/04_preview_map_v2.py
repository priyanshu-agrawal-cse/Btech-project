"""
Generate publication-quality preview for Landslide Susceptibility Map V2
"""

import os
import rasterio
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
import matplotlib.patches as mpatches

os.makedirs("data/final", exist_ok=True)

TIF_PATH = "data/final/mizoram_landslide_susceptibility_v2.tif"
OUT_PNG  = "data/final/susceptibility_map_v2_preview.png"

print(f"Reading {TIF_PATH}...")
with rasterio.open(TIF_PATH) as src:
    data = src.read(1)
    nodata = src.nodata if src.nodata is not None else -9999.0
    bounds = src.bounds

# Downsample by factor of 4 for crisp high-res preview without excessive RAM
sub = data[::4, ::4].astype(float)
sub[sub == nodata] = np.nan
sub[(sub < 0) | (sub > 1)] = np.nan

# 5 Susceptibility Classes (standard GSI / NDMA classification)
# 0.0 - 0.2: Very Low (Dark Green)
# 0.2 - 0.4: Low (Light Green)
# 0.4 - 0.6: Moderate (Yellow)
# 0.6 - 0.8: High (Orange)
# 0.8 - 1.0: Very High (Red)

colors = ["#2b83ba", "#abdda4", "#ffffbf", "#fdae61", "#d7191c"]
cmap = ListedColormap(colors)
bounds_list = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
norm = BoundaryNorm(bounds_list, cmap.N)

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 10), gridspec_kw={'width_ratios': [2.2, 1]})

# Map plot
im = ax1.imshow(sub, cmap=cmap, norm=norm, interpolation="nearest")
ax1.set_title("Mizoram Landslide Susceptibility Map (v2)\nPowered by Multi-Source GSI Ground Truth & XGBoost (ROC-AUC: 0.893)", fontsize=13, fontweight="bold", pad=12)
ax1.set_xlabel("Easting (UTM Zone 46N, 120m res display)", fontsize=10)
ax1.set_ylabel("Northing (UTM Zone 46N, 120m res display)", fontsize=10)

# Legend patches
labels = [
    "Very Low (0.0 - 0.2)",
    "Low (0.2 - 0.4)",
    "Moderate (0.4 - 0.6)",
    "High (0.6 - 0.8)",
    "Very High (0.8 - 1.0)"
]
patches = [mpatches.Patch(color=colors[i], label=labels[i]) for i in range(5)]
ax1.legend(handles=patches, loc="lower right", framealpha=0.9, fontsize=9, title="Susceptibility Level")

# Class area breakdown in ax2
valid_pixels = sub[~np.isnan(sub)]
total_valid = len(valid_pixels)

class_counts = [
    np.sum((valid_pixels >= 0.0) & (valid_pixels < 0.2)),
    np.sum((valid_pixels >= 0.2) & (valid_pixels < 0.4)),
    np.sum((valid_pixels >= 0.4) & (valid_pixels < 0.6)),
    np.sum((valid_pixels >= 0.6) & (valid_pixels < 0.8)),
    np.sum((valid_pixels >= 0.8) & (valid_pixels <= 1.0)),
]
class_pcts = [100.0 * c / total_valid for c in class_counts]

bars = ax2.barh(labels[::-1], class_pcts[::-1], color=colors[::-1], edgecolor="black", linewidth=0.5, height=0.6)
ax2.set_xlabel("Percentage of Mizoram Land Area (%)", fontsize=10, fontweight="bold")
ax2.set_title("Zonal Distribution of Risk", fontsize=12, fontweight="bold")
ax2.set_xlim(0, max(class_pcts) * 1.25)
ax2.grid(axis="x", linestyle="--", alpha=0.5)

for bar in bars:
    w = bar.get_width()
    ax2.text(w + 0.8, bar.get_y() + bar.get_height() / 2, f"{w:.1f}%", va="center", ha="left", fontsize=10, fontweight="bold")

plt.tight_layout()
plt.savefig(OUT_PNG, dpi=200, bbox_inches="tight")
plt.close()
print(f"Preview map saved: {OUT_PNG}")
