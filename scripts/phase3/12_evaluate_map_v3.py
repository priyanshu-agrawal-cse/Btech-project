"""
Phase 3 / Step 12 — Zonation and map-level validation (DATA-030).

* Zones: natural breaks (Jenks; equivalent to 1-D k-means, fitted on a 1,000,000
  cell random sample of the final map) instead of Phase 2's fixed 0.2 bins, which
  assume calibrated probabilities.
* Success-rate curve: final map vs all landslide pixels (they were used in training).
* Prediction-rate curve: spatial out-of-fold map vs all landslide pixels (Chung &
  Fabbri 2003). This is the honest map-level result.
* Baseline: ranking the land only by distance to the nearest road. A useful map
  must beat this, otherwise it is only a road buffer.

Outputs: data/final/mizoram_landslide_zones_v3.tif, susceptibility_map_v3_preview.png
         data/phase3/maps/zone_statistics.csv, rate_curves.csv, rate_curve_summary.csv,
         fig_rate_curves.png; gis/styles/susceptibility_zones_v3.qml
"""

import os
import sys
import numpy as np
import pandas as pd
import rasterio
import geopandas as gpd
from sklearn.cluster import KMeans
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
import matplotlib.patches as mpatches

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p3_common import P3_DIR, FEAT_DIR, INV_DIR, load_valid_mask, read_float, write_uint8, grid_info, save_json, log, SEED
from p3_plot import style, C_POS, C_NEG, C_GREY, C_AQUA, INK2, ZONE_COLORS, ZONE_NAMES

style()
SUFFIX = os.environ.get("P3_MODEL_SUFFIX", "xgboost")   # "xgboost" = all factors; "natural" = terrain only
TAG = "" if SUFFIX == "xgboost" else f"_{SUFFIX}"
TITLE = "all-factor map" if SUFFIX == "xgboost" else "natural-terrain map"
OUT = f"{P3_DIR}/maps"
os.makedirs(OUT, exist_ok=True)
os.makedirs("gis/styles", exist_ok=True)
rng = np.random.default_rng(SEED)
valid = load_valid_mask()
tr, crs, H, W, L = grid_info()
with rasterio.open(f"{INV_DIR}/landslide_target_v3_30m.tif") as s:
    target = (s.read(1) == 1) & valid
n_ls = int(target.sum())

final = read_float(f"data/final/mizoram_landslide_susceptibility_v3{TAG}.tif", valid)
oof = read_float(f"{OUT}/susceptibility_v3{TAG}_spatial_oof.tif", valid)

# ---- natural breaks ---------------------------------------------------------------
land = final[valid & np.isfinite(final)]
sample = rng.choice(land, size=min(1_000_000, land.size), replace=False).reshape(-1, 1)
km = KMeans(n_clusters=5, n_init=4, random_state=SEED).fit(sample)
cent = np.sort(km.cluster_centers_.ravel())
breaks = (cent[:-1] + cent[1:]) / 2
edges = np.r_[0.0, breaks, 1.0001]
log(f"Natural breaks: {np.round(breaks, 4).tolist()}")
zone = np.zeros((H, W), "uint8")
zone[valid] = np.digitize(np.nan_to_num(final[valid], nan=0.0), breaks) + 1
write_uint8(f"data/final/mizoram_landslide_zones_v3{TAG}.tif", zone, nodata=0)
zone_oof = np.digitize(np.nan_to_num(oof, nan=0.0), breaks) + 1

rows = []
for i, nm in enumerate(ZONE_NAMES, 1):
    a = (zone[valid] == i).mean() * 100
    s_ = (zone[target] == i).mean() * 100
    a2 = (zone_oof[valid] == i).mean() * 100
    p_ = (zone_oof[target] == i).mean() * 100
    rows.append({"zone": nm, "score_from": edges[i - 1], "score_to": min(edges[i], 1.0), "area_pct": a,
                 "landslide_pct_training": s_, "FR_training": s_ / a,
                 "area_pct_oof": a2, "landslide_pct_spatial_oof": p_, "FR_spatial_oof": p_ / a2,
                 "landslides_per_100km2_spatial_oof": (p_ / 100 * n_ls) / (a2 / 100 * valid.sum() * (L / 1000) ** 2) * 100})
zt = pd.DataFrame(rows)
zt.round(3).to_csv(f"{OUT}/zone_statistics{TAG}.csv", index=False)
log(zt.round(3).to_string(index=False))


# ---- rate curves --------------------------------------------------------------------
def curve(score, name, mask=None):
    """Share of landslides captured in the top-x % of the land, ranking by score."""
    mask = valid if mask is None else mask
    v = score[mask]
    v = np.nan_to_num(v, nan=np.nanmin(v))
    t = v[target[mask]]
    sv, st = np.sort(v), np.sort(t)
    q = sv[np.round(np.linspace(v.size - 1, 0, 1001)).astype(int)]
    area = (1 - np.searchsorted(sv, q, side="left") / v.size) * 100
    cap = (1 - np.searchsorted(st, q, side="left") / t.size) * 100
    # Start at the origin. Without this, a score with many tied cells (all road cells
    # have distance 0 = 2.42 % of the land) would begin at (2.42 %, 58.58 %), which
    # overstated its early capture and understated its AUC (fixed 2026-10-30).
    area, cap = np.r_[0.0, area], np.r_[0.0, cap]
    return pd.DataFrame({"curve": name, "area_pct": area, "landslide_pct": cap})


vrank = read_float(f"{FEAT_DIR}/dist_road_any.tif", valid)
corridor = valid & (vrank <= 60)
curves = {f"{TITLE}, spatial out-of-fold (prediction rate)": oof,
          f"{TITLE}, final model (success rate, training data)": final,
          "Map v2 (in-sample for most of these landslides)": read_float("data/final/mizoram_landslide_susceptibility_v2.tif", valid),
          "Baseline: nearest to a road first": -vrank}
other = f"{OUT}/susceptibility_v3_natural_spatial_oof.tif"
if not TAG and os.path.exists(other):
    curves["natural-terrain map, spatial out-of-fold"] = read_float(other, valid)
res, summ = [], []
for nm, sc in curves.items():
    c = curve(sc, nm)
    res.append(c)
    a = np.trapezoid(c.landslide_pct / 100, c.area_pct / 100)
    cc = curve(sc, nm, corridor)
    r = {"curve": nm, "AUC": a, "AUC_within_60m_of_road": np.trapezoid(cc.landslide_pct / 100, cc.area_pct / 100)}
    for top in (1, 5, 10, 20, 30):
        r[f"captured_in_top_{top}pct_area"] = float(np.interp(top, c.area_pct, c.landslide_pct))
    summ.append(r)
    log({k: (round(v, 3) if not isinstance(v, str) else v) for k, v in r.items()})
pd.concat(res).round(3).to_csv(f"{OUT}/rate_curves{TAG}.csv", index=False)
sm = pd.DataFrame(summ)
sm.round(3).to_csv(f"{OUT}/rate_curve_summary{TAG}.csv", index=False)

fig, ax = plt.subplots(figsize=(6.6, 5.2))
for (nm, _), col, ls in zip(curves.items(), [C_POS, C_NEG, C_GREY, C_AQUA, "#6250d6"], ["-", "-", "-", "--", "-"]):
    c = pd.concat(res).query("curve == @nm")
    auc = sm.loc[sm.curve == nm, "AUC"].iloc[0]
    ax.plot(c.area_pct, c.landslide_pct, color=col, ls=ls, lw=1.7, label=f"{nm} — AUC {auc:.3f}")
ax.plot([0, 100], [0, 100], ls=":", lw=0.8, color=INK2)
ax.set_xlabel("Share of Mizoram's land, highest score first (%)")
ax.set_ylabel("Landslide pixels captured (%)")
ax.set_title("How much of the land must be flagged to capture the landslides")
ax.legend(fontsize=7.3, loc="lower right")
fig.tight_layout(); fig.savefig(f"{OUT}/fig_rate_curves{TAG}.png"); plt.close(fig)

# ---- preview ---------------------------------------------------------------------------
bnd = gpd.read_file("data/raw/mizoram_boundary.geojson").to_crs(crs)
sub = zone[::4, ::4].astype(float)
sub[sub == 0] = np.nan
ext = (tr.c, tr.c + W * tr.a, tr.f + H * tr.e, tr.f)
cmap = ListedColormap(ZONE_COLORS)
fig, (a1, a2) = plt.subplots(1, 2, figsize=(10.5, 9), gridspec_kw={"width_ratios": [1.5, 1]})
a1.imshow(sub, cmap=cmap, norm=BoundaryNorm(np.arange(0.5, 6), 5), extent=ext, interpolation="nearest")
bnd.boundary.plot(ax=a1, color=INK2, lw=0.5)
a1.set_title(f"Landslide susceptibility zones, v3 {TITLE}"); a1.grid(False); a1.tick_params(labelsize=7)
a1.legend(handles=[mpatches.Patch(color=c, label=n) for c, n in zip(ZONE_COLORS, ZONE_NAMES)], loc="upper right", fontsize=8)
y_ = np.arange(5)
a2.barh(y_ - 0.19, zt.area_pct, height=0.36, color=C_GREY, label="% of land")
a2.barh(y_ + 0.19, zt.landslide_pct_spatial_oof, height=0.36, color=C_POS, label="% of landslides (spatial out-of-fold)")
a2.set_yticks(y_); a2.set_yticklabels(ZONE_NAMES); a2.grid(axis="y", visible=False)
for i, r in zt.iterrows():
    a2.text(r.area_pct + 0.8, i - 0.19, f"{r.area_pct:.1f}", va="center", fontsize=8, color=INK2)
    a2.text(r.landslide_pct_spatial_oof + 0.8, i + 0.19, f"{r.landslide_pct_spatial_oof:.1f}", va="center", fontsize=8, color=INK2)
a2.set_xlabel("%"); a2.legend(fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.07), ncol=2); a2.set_title("Land vs landslides per zone")
fig.tight_layout(); fig.savefig(f"data/final/susceptibility_map_v3{TAG}_preview.png"); plt.close(fig)

# ---- QGIS style ---------------------------------------------------------------------------
entries = "\n".join(f'      <paletteEntry value="{i}" color="{c}" alpha="255" label="{n}"/>'
                    for i, (c, n) in enumerate(zip(ZONE_COLORS, ZONE_NAMES), 1))
qml = f"""<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.34" styleCategories="Symbology">
  <pipe>
    <rasterrenderer type="paletted" band="1" opacity="1" nodataColor="">
      <colorPalette>
{entries}
      </colorPalette>
    </rasterrenderer>
  </pipe>
</qgis>
"""
with open("gis/styles/susceptibility_zones_v3.qml", "w", encoding="utf-8") as f:
    f.write(qml)
save_json({"breaks": breaks.tolist(), "n_landslide_pixels": n_ls}, f"{OUT}/zone_breaks{TAG}.json")
log("Step 12 complete.")
