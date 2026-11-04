"""
Phase 3 — shared figure style.

One colour job per figure: two fixed class colours (landslide / non-landslide),
a blue-to-red diverging ramp with a grey midpoint for correlations, and a
single-hue ordered ramp for susceptibility zones. Axes and grid stay recessive
so the data carries the figure.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
GRID = "#e4e3df"
C_NEG = "#2a78d6"     # non-landslide
C_POS = "#eb6834"     # landslide
C_AQUA = "#1baf7a"
C_VIOLET = "#6250d6"
C_GREY = "#9b9a94"

DIVERGING = LinearSegmentedColormap.from_list("p3_div", ["#104281", "#6da7ec", "#f0efec", "#ef9a8f", "#a82626"])
# ordered susceptibility zones, Very Low -> Very High (one hue, light to dark)
ZONE_COLORS = ["#fbe3d0", "#f6b68c", "#eb6834", "#b8431c", "#6f2108"]
ZONE_NAMES = ["Very Low", "Low", "Moderate", "High", "Very High"]


def style():
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": GRID, "axes.labelcolor": INK2, "axes.titlecolor": INK,
        "xtick.color": INK2, "ytick.color": INK2, "text.color": INK,
        "font.size": 9, "axes.titlesize": 10, "axes.titleweight": "bold",
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
        "legend.frameon": False, "figure.dpi": 150, "savefig.dpi": 200,
    })
