"""
Phase 3 / Step 09 — Exploratory analysis of FINAL_DATASET_v3 BEFORE any training (DATA-027).

Required by the project specification (section 13): data quality, feature
distributions, correlation, missing values, class balance, spatial distribution
and leakage analysis.

Analysis table = landslides + neg_random (the balanced main design). Collinearity
uses landslides + neg_random + neg_pool, so that it describes the landscape.

Outputs: data/phase3/eda/
  data_quality.csv, class_balance.json, univariate_auc.csv, correlation_spearman.csv,
  high_correlation_pairs.csv, vif.csv, frequency_ratio.csv, leakage_check.csv,
  fig_feature_distributions.png, fig_correlation.png, fig_frequency_ratio.png,
  fig_univariate_auc.png, fig_spatial_distribution.png
"""

import os
import sys
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from scipy.spatial import cKDTree
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold, StratifiedGroupKFold
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p3_common import (P3_DIR, MOD_DIR, FEAT_DIR, INV_DIR, load_valid_mask, read_float,
                       grid_info, save_json, log, SEED)
from p3_plot import style, C_POS, C_NEG, C_GREY, INK2, GRID, DIVERGING

style()
OUT = f"{P3_DIR}/eda"
os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(SEED)
tr, crs, H, W, L = grid_info()

path = f"{MOD_DIR}/FINAL_DATASET_v3_ndvi.csv"
if not os.path.exists(path):
    path = f"{MOD_DIR}/FINAL_DATASET_v3.csv"
full = pd.read_csv(path)
ID_COLS = {"sample_id", "set", "landslide", "row", "col", "event_ids", "district", "x_utm", "y_utm",
           "lon", "lat", "block1", "block5", "block10", "block20"}
FEATS = [c for c in full.columns if c not in ID_COLS]
NUM = [f for f in FEATS if f != "lulc"]
main = full[full.set.isin(["pos", "neg_random"])].reset_index(drop=True)
y = main.landslide.values
log(f"Table {path}: {len(full):,} rows; main design {len(main):,} rows; {len(FEATS)} features")

# ---- A. data quality ------------------------------------------------------------
q = []
for f in FEATS:
    v = main[f]
    q.append({"feature": f, "missing_main": int(v.isna().sum()), "missing_all_sets": int(full[f].isna().sum()),
              "min": v.min(), "p01": v.quantile(.01), "median_nonLS": main.loc[y == 0, f].median(),
              "median_LS": main.loc[y == 1, f].median(), "p99": v.quantile(.99), "max": v.max(),
              "n_unique": int(v.nunique())})
pd.DataFrame(q).round(4).to_csv(f"{OUT}/data_quality.csv", index=False)
dup = int(full.duplicated(["row", "col", "set"]).sum())
pos_xy = main.loc[y == 1, ["x_utm", "y_utm"]].values
neg_d, _ = cKDTree(pos_xy).query(main.loc[y == 0, ["x_utm", "y_utm"]].values, k=1)
log(f"A. duplicates within a set={dup}; min distance negative->landslide={neg_d.min():.1f} m")

# ---- B. class balance -----------------------------------------------------------
blk = main.groupby("block10").landslide.agg(["sum", "count"])
pos_blk = blk["sum"][blk["sum"] > 0].sort_values(ascending=False)
share_top10 = float(pos_blk.head(10).sum() / pos_blk.sum())
bal = {"rows_by_set": full.set.value_counts().to_dict(), "positive_share_main": float(y.mean()),
       "blocks10_total": int(len(blk)), "blocks10_with_landslides": int(len(pos_blk)),
       "landslides_per_block_median": float(pos_blk.median()), "landslides_per_block_max": int(pos_blk.max()),
       "share_of_landslides_in_top10_blocks": share_top10,
       "landslide_pixels_by_district": main[y == 1].district.astype(str).str.strip().value_counts().to_dict(),
       "min_distance_negative_to_landslide_m": float(neg_d.min()), "duplicates_within_set": dup}
save_json(bal, f"{OUT}/class_balance.json")
log(f"B. {bal['blocks10_with_landslides']} blocks with landslides; top-10 blocks hold {share_top10:.1%}")

# ---- C. univariate discrimination with block-bootstrap interval -------------------
blocks = main.block10.values
ublocks = np.unique(blocks)
idx_by_block = [np.flatnonzero(blocks == b) for b in ublocks]
rows = []
B = 300
draws = [rng.integers(0, len(ublocks), len(ublocks)) for _ in range(B)]
for f in NUM:
    ok = main[f].notna().values
    x = main[f].values
    auc = roc_auc_score(y[ok], x[ok])
    boots = []
    for d in draws:
        ii = np.concatenate([idx_by_block[j] for j in d])
        ii = ii[ok[ii]]
        if 0 < y[ii].sum() < ii.size:
            boots.append(roc_auc_score(y[ii], x[ii]))
    rows.append({"feature": f, "auc": auc, "ci_low": np.percentile(boots, 2.5), "ci_high": np.percentile(boots, 97.5),
                 "strength": abs(auc - 0.5)})
ua = pd.DataFrame(rows).sort_values("strength", ascending=False)
ua.round(4).to_csv(f"{OUT}/univariate_auc.csv", index=False)
log("C. strongest single features:\n" + ua.head(10).round(3).to_string(index=False))

fig, ax = plt.subplots(figsize=(7, 6.4))
u = ua.sort_values("strength")
yy = np.arange(len(u))
ax.hlines(yy, u.ci_low, u.ci_high, color=C_GREY, lw=1.6)
ax.plot(u.auc, yy, "o", ms=5, color=C_NEG)
ax.axvline(0.5, color=INK2, lw=0.9, ls="--")
ax.set_yticks(yy); ax.set_yticklabels(u.feature); ax.grid(axis="y", visible=False)
ax.set_xlabel("ROC-AUC of the raw feature (below 0.5 = lower values at landslides)")
ax.set_title("Single-feature discrimination, 95 % block-bootstrap interval")
fig.tight_layout(); fig.savefig(f"{OUT}/fig_univariate_auc.png"); plt.close(fig)

# ---- D. distributions -----------------------------------------------------------------
ncol = 5
nrow = int(np.ceil(len(NUM) / ncol))
fig, axes = plt.subplots(nrow, ncol, figsize=(12, 2.05 * nrow))
for ax, f in zip(axes.ravel(), NUM):
    lo, hi = main[f].quantile([.005, .995])
    bins = np.linspace(lo, hi, 31)
    ax.hist(main.loc[y == 0, f].dropna(), bins=bins, density=True, histtype="step", lw=1.3, color=C_NEG)
    ax.hist(main.loc[y == 1, f].dropna(), bins=bins, density=True, histtype="step", lw=1.3, color=C_POS)
    ax.set_title(f, fontsize=8.5); ax.set_yticks([]); ax.tick_params(labelsize=7); ax.grid(False)
for ax in axes.ravel()[len(NUM):]:
    ax.axis("off")
fig.legend(handles=[plt.Line2D([], [], color=C_POS, lw=1.6, label="landslide pixels"),
                    plt.Line2D([], [], color=C_NEG, lw=1.6, label="random non-landslide pixels")],
           loc="upper center", ncol=2, fontsize=9)
fig.tight_layout(rect=(0, 0, 1, 0.965)); fig.savefig(f"{OUT}/fig_feature_distributions.png"); plt.close(fig)

# ---- E. collinearity (unsupervised: no labels used) --------------------------------------
land = full[full.set.isin(["pos", "neg_random", "neg_pool"])]
R = land[NUM].corr(method="spearman")
R.round(3).to_csv(f"{OUT}/correlation_spearman.csv")
pairs = []
for i, a in enumerate(NUM):
    for b in NUM[i + 1:]:
        if abs(R.loc[a, b]) >= 0.7:
            pairs.append({"a": a, "b": b, "spearman": R.loc[a, b]})
pairs = pd.DataFrame(pairs).sort_values("spearman", key=np.abs, ascending=False)
pairs.round(3).to_csv(f"{OUT}/high_correlation_pairs.csv", index=False)
log("E. pairs with |rho|>=0.7:\n" + pairs.round(3).to_string(index=False))
X = land[NUM].dropna()
X = (X - X.mean()) / X.std()
vif = pd.Series(np.diag(np.linalg.inv(np.corrcoef(X.values, rowvar=False))), index=NUM).sort_values(ascending=False)
vif.round(2).rename("vif").to_csv(f"{OUT}/vif.csv")
log("E. VIF:\n" + vif.round(2).to_string())

fig, ax = plt.subplots(figsize=(9, 8))
im = ax.imshow(R.values, cmap=DIVERGING, vmin=-1, vmax=1)
ax.set_xticks(range(len(NUM))); ax.set_xticklabels(NUM, rotation=90, fontsize=7.5)
ax.set_yticks(range(len(NUM))); ax.set_yticklabels(NUM, fontsize=7.5); ax.grid(False)
fig.colorbar(im, shrink=0.75, label="Spearman correlation")
ax.set_title("Collinearity of the candidate factors")
fig.tight_layout(); fig.savefig(f"{OUT}/fig_correlation.png"); plt.close(fig)

# ---- F. frequency ratio on the full rasters ---------------------------------------------
valid = load_valid_mask()
with rasterio.open(f"{INV_DIR}/landslide_target_v3_30m.tif") as s:
    target = s.read(1) == 1
target &= valid
n_land, n_ls = int(valid.sum()), int(target.sum())
PHASE1 = {"lulc": "data/processed/lulc/mizoram_lulc_30m.tif",
          "map": "data/processed/rainfall/mean_annual_precip_30m.tif",
          "max_precip": "data/processed/rainfall/max_monthly_precip_30m.tif",
          "dist_fault": "data/processed/geology/mizoram_distance_to_faults_30m.tif"}
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
    if name not in FEATS:
        continue
    a = read_float(PHASE1.get(name, f"{FEAT_DIR}/{name}.tif"), valid)
    land_v, ls_v = a[valid], a[target]
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        al, sl = ((land_v >= lo) & (land_v < hi)).mean() * 100, ((ls_v >= lo) & (ls_v < hi)).mean() * 100
        fr.append({"factor": name, "class": f"{lo:g} to {hi:g}", "order": i, "area_pct": al, "landslide_pct": sl,
                   "frequency_ratio": sl / al if al > 0 else np.nan})
    del a, land_v, ls_v
a = read_float(PHASE1["lulc"], valid)
names = {10: "tree", 20: "shrub", 30: "grass", 40: "crop", 50: "built-up", 60: "bare", 80: "water", 90: "wetland"}
for i, code in enumerate(sorted(names)):
    al, sl = (a[valid] == code).mean() * 100, (a[target] == code).mean() * 100
    fr.append({"factor": "lulc", "class": names[code], "order": i, "area_pct": al, "landslide_pct": sl,
               "frequency_ratio": sl / al if al > 0 else np.nan})
del a
fr = pd.DataFrame(fr)
fr.round(3).to_csv(f"{OUT}/frequency_ratio.csv", index=False)
log("F. frequency ratios:\n" + fr[["factor", "class", "area_pct", "landslide_pct", "frequency_ratio"]].round(2).to_string(index=False))

show = [f for f in ["dist_road_any", "lulc", "slope", "elevation", "dist_stream", "relief_1km"] if f in set(fr.factor)]
fig, axes = plt.subplots(2, 3, figsize=(11, 6))
for ax, f in zip(axes.ravel(), show):
    t = fr[fr.factor == f].sort_values("order")
    ax.barh(np.arange(len(t)), t.frequency_ratio, color=C_NEG, height=0.62)
    ax.axvline(1, color=INK2, ls="--", lw=0.9)
    ax.set_yticks(np.arange(len(t))); ax.set_yticklabels(t["class"], fontsize=7.5)
    ax.set_title(f); ax.invert_yaxis(); ax.grid(axis="y", visible=False)
    ax.set_xlabel("Frequency ratio (1 = as expected by area)", fontsize=8)
fig.tight_layout(); fig.savefig(f"{OUT}/fig_frequency_ratio.png"); plt.close(fig)

# ---- G. spatial distribution ------------------------------------------------------------
bnd = gpd.read_file("data/raw/mizoram_boundary.geojson").to_crs(crs)
fig, ax = plt.subplots(figsize=(5.2, 9))
bnd.boundary.plot(ax=ax, color=INK2, lw=0.7)
ax.scatter(main.x_utm[y == 0], main.y_utm[y == 0], s=3, color=C_NEG, label="random non-landslide", linewidths=0)
ax.scatter(main.x_utm[y == 1], main.y_utm[y == 1], s=4, color=C_POS, label="landslide", linewidths=0)
ax.set_aspect("equal"); ax.legend(loc="lower left", markerscale=3, fontsize=8)
ax.set_title("Samples of the main design"); ax.set_xlabel("UTM 46N easting (m)"); ax.set_ylabel("northing (m)")
ax.grid(False); ax.tick_params(labelsize=7)
fig.tight_layout(); fig.savefig(f"{OUT}/fig_spatial_distribution.png"); plt.close(fig)

# ---- H. leakage check ---------------------------------------------------------------------
xy = main[["x_utm", "y_utm"]].values
res = []
designs = {"random 5-fold": list(StratifiedKFold(5, shuffle=True, random_state=SEED).split(xy, y))}
for km in (1, 5, 10, 20):
    designs[f"{km} km blocks"] = list(StratifiedGroupKFold(5, shuffle=True, random_state=SEED).split(xy, y, main[f"block{km}"]))
for nm, splits in designs.items():
    d_all, d_ls = [], []
    for trn, tst in splits:
        d_all.append(cKDTree(xy[trn]).query(xy[tst], k=1)[0])
        p_tr, p_te = trn[y[trn] == 1], tst[y[tst] == 1]
        d_ls.append(cKDTree(xy[p_tr]).query(xy[p_te], k=1)[0])
    d_all, d_ls = np.concatenate(d_all), np.concatenate(d_ls)
    res.append({"design": nm, "median_m_test_to_train": np.median(d_all),
                "median_m_testLS_to_trainLS": np.median(d_ls),
                "share_testLS_within_100m_of_trainLS": (d_ls <= 100).mean(),
                "share_testLS_within_1km_of_trainLS": (d_ls <= 1000).mean()})
res = pd.DataFrame(res)
res.round(3).to_csv(f"{OUT}/leakage_check.csv", index=False)
log("H. leakage check:\n" + res.round(3).to_string(index=False))
nn = cKDTree(pos_xy).query(pos_xy, k=2)[0][:, 1]
log(f"H. landslide nearest-neighbour distance: median {np.median(nn):.0f} m, p90 {np.percentile(nn, 90):.0f} m")
log("EDA complete.")
