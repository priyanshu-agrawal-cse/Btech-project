"""
Phase 3 / Step 00 — Quantitative audit of the Phase 2 pipeline (DATA-017).

Every claim made in the Phase 2 README / presentation notes is re-checked
against the actual rasters, inventory and training CSV. Nothing is modified;
the script only reads Phase 1/2 artefacts and writes an audit report.

Outputs (data/phase3/audit/):
  audit_report.txt              human-readable findings
  audit_summary.json            machine-readable numbers used in the docs
  feature_stats_inside_state.csv verified min/max/mean of every Phase 2 feature
                                 computed ONLY inside the Mizoram land mask
  boundary_artifacts.csv        feature extremes in the 3-pixel state-edge ring
                                 versus the interior
  v2_map_zone_areas.csv         % of state area in each v2 susceptibility zone

Run from project root:  python scripts/phase3/00_audit_phase2_pipeline.py
"""

import os
import sys
import numpy as np
import pandas as pd
import rasterio
from scipy import ndimage
from scipy.stats import spearmanr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p3_common import (MASTER_DEM, AUDIT_DIR, ensure_dirs, load_valid_mask,
                       read_float, save_json, log, SEED)

ensure_dirs()
rng = np.random.default_rng(SEED)
report = []
summary = {}


def say(msg=""):
    log(msg)
    report.append(msg)


PHASE2_FEATURES = {
    "elevation":           "data/derived/mizoram_dem_clipped_utm.tif",
    "slope":               "data/derived/mizoram_slope.tif",
    "aspect":              "data/derived/mizoram_aspect.tif",
    "curvature":           "data/derived/mizoram_curvature.tif",
    "lulc":                "data/processed/lulc/mizoram_lulc_30m.tif",
    "dist_fault":          "data/processed/geology/mizoram_distance_to_faults_30m.tif",
    "lithology":           "data/processed/geology/mizoram_lithology_30m.tif",
    "map":                 "data/processed/rainfall/mean_annual_precip_30m.tif",
    "max_precip":          "data/processed/rainfall/max_monthly_precip_30m.tif",
    "twi":                 "data/derived/mizoram_twi.tif",
    "tri":                 "data/derived/mizoram_tri.tif",
    "tpi":                 "data/derived/mizoram_tpi.tif",
    "profile_curvature":   "data/derived/mizoram_profile_curvature.tif",
    "plan_curvature":      "data/derived/mizoram_plan_curvature.tif",
    "sin_aspect":          "data/derived/mizoram_sin_aspect.tif",
    "cos_aspect":          "data/derived/mizoram_cos_aspect.tif",
    "slope_curv_interact": "data/derived/mizoram_slope_curv_interact.tif",
}

# ===========================================================================
say("=" * 78)
say("A. MASTER DEM NODATA AUDIT")
say("=" * 78)
with rasterio.open(MASTER_DEM) as src:
    dem = src.read(1)
    say(f"  File            : {MASTER_DEM}")
    say(f"  dtype / nodata  : {src.dtypes[0]} / {src.nodata}   (None = no NoData declared)")
    H, W = src.height, src.width
valid = load_valid_mask()
n_total = H * W
n_zero = int((dem == 0).sum())
n_valid = int(valid.sum())
say(f"  Grid cells      : {n_total:,}")
say(f"  Cells == 0.0 m  : {n_zero:,} ({100 * n_zero / n_total:.2f} %)  <- out-of-state fill")
say(f"  Valid land cells: {n_valid:,} (DEM > 0)")
say("  Phase 1/2 scripts used `nodata if not None else -9999`, so the 0.0 m fill")
say("  was treated as VALID terrain in 01d_prepare_expanded_dataset.py, 01b, 11, ...")
summary["dem_nodata_declared"] = None
summary["grid_cells"] = n_total
summary["zero_fill_cells"] = n_zero
summary["valid_land_cells"] = n_valid

# ===========================================================================
say("\n" + "=" * 78)
say("B. DOCUMENTED STATISTICS vs INSIDE-STATE STATISTICS")
say("=" * 78)
say("  (DATA-005 / README quote: slope mean 14.14 deg, aspect mean 110.43 deg)")
for name in ("elevation", "slope", "aspect", "curvature"):
    with rasterio.open(PHASE2_FEATURES[name]) as src:
        a = src.read(1).astype("float64")
        nd = src.nodata
    allpix = a[(a != -9999.0) & np.isfinite(a)] if nd is not None else a[np.isfinite(a)]
    inside = a[valid & (a != -9999.0) & np.isfinite(a)]
    say(f"  {name:10s} whole-rectangle mean={allpix.mean():9.3f}   inside-state mean={inside.mean():9.3f}"
        f"   (n_whole={allpix.size:,}, n_inside={inside.size:,})")
    summary[f"{name}_mean_whole_rectangle"] = float(allpix.mean())
    summary[f"{name}_mean_inside_state"] = float(inside.mean())
    del a, allpix, inside

# ===========================================================================
say("\n" + "=" * 78)
say("C. STATE-EDGE ARTEFACTS (0 m fill -> 600 m terrain 'cliff')")
say("=" * 78)
interior = ndimage.binary_erosion(valid, iterations=3)
ring = valid & ~interior
say(f"  Edge ring (valid cells within 3 px of the boundary): {int(ring.sum()):,}")
rows = []
for name in ("slope", "curvature", "tri", "tpi", "profile_curvature", "plan_curvature",
             "slope_curv_interact"):
    a = read_float(PHASE2_FEATURES[name], valid)
    r_vals = a[ring & np.isfinite(a)]
    i_vals = a[interior & np.isfinite(a)]
    row = {"feature": name,
           "ring_p99": np.percentile(np.abs(r_vals), 99), "ring_max": np.abs(r_vals).max(),
           "interior_p99": np.percentile(np.abs(i_vals), 99), "interior_max": np.abs(i_vals).max(),
           "ring_mean_abs": np.abs(r_vals).mean(), "interior_mean_abs": np.abs(i_vals).mean()}
    rows.append(row)
    say(f"  {name:20s} |x| mean ring={row['ring_mean_abs']:9.2f} interior={row['interior_mean_abs']:9.2f}"
        f"   max ring={row['ring_max']:9.1f} interior={row['interior_max']:9.1f}")
    del a, r_vals, i_vals
pd.DataFrame(rows).round(3).to_csv(f"{AUDIT_DIR}/boundary_artifacts.csv", index=False)
del interior, ring

# ===========================================================================
say("\n" + "=" * 78)
say("D. 'TWI' IS A MONOTONIC FUNCTION OF SLOPE")
say("=" * 78)
slope = read_float(PHASE2_FEATURES["slope"], valid)
twi = read_float(PHASE2_FEATURES["twi"], valid)
ok = np.isfinite(slope) & np.isfinite(twi)
idx = np.flatnonzero(ok.ravel())
pick = rng.choice(idx, size=min(1_000_000, idx.size), replace=False)
rho = spearmanr(slope.ravel()[pick], twi.ravel()[pick]).statistic
say(f"  Spearman rho(slope, twi) on 1,000,000 random land cells = {rho:.10f}")
say("  01b_derive_advanced_features.py: sca = dx*dy / tan(b);  twi = ln(sca / tan(b))")
say("  => twi = ln(dx*dy) - 2 ln(tan b): no upslope contributing area is used at all.")
summary["spearman_slope_twi"] = float(rho)
del slope, twi, ok, idx, pick

# ===========================================================================
say("\n" + "=" * 78)
say("E. LITHOLOGY RASTER CONTENT")
say("=" * 78)
with rasterio.open(PHASE2_FEATURES["lithology"]) as src:
    lith = src.read(1)
vals, cnts = np.unique(lith[valid], return_counts=True)
for v, c in zip(vals, cnts):
    say(f"  class {int(v):3d}: {int(c):,} cells ({100 * c / n_valid:.2f} % of land)")
summary["lithology_classes_inside_state"] = {int(v): int(c) for v, c in zip(vals, cnts)}
del lith

# ===========================================================================
say("\n" + "=" * 78)
say("F. LANDSLIDE TARGET RASTERS — PIXELS vs INDEPENDENT EVENTS")
say("=" * 78)
for label, path in [("COOLR only (Phase 1)", "data/processed/inventory/mizoram_landslide_target_30m.tif"),
                    ("Expanded, no buffer", "data/processed/inventory/mizoram_landslide_target_nobuffer_30m.tif"),
                    ("Expanded, 90 m buffer (Phase 2)", "data/processed/inventory/mizoram_landslide_target_expanded_30m.tif")]:
    with rasterio.open(path) as src:
        t = src.read(1)
    pos = (t == 1)
    pos_in = pos & valid
    lab, n_comp = ndimage.label(pos_in, structure=np.ones((3, 3)))
    sizes = np.bincount(lab.ravel())[1:] if n_comp else np.array([0])
    say(f"  {label:34s} positive px={int(pos.sum()):7,} (inside land={int(pos_in.sum()):7,})"
        f"  connected blobs={n_comp:6,}  median px/blob={np.median(sizes):5.0f}  max={sizes.max():6,}")
    key = label.split(" (")[0].replace(",", "").replace(" ", "_").lower()
    summary[f"target_{key}_pixels"] = int(pos.sum())
    summary[f"target_{key}_blobs"] = int(n_comp)
    del t, pos, pos_in, lab

# ===========================================================================
say("\n" + "=" * 78)
say("G. GSI INVENTORY — GEOMETRY TYPES INSIDE MIZORAM")
say("=" * 78)
try:
    import geopandas as gpd
    gsi = gpd.read_file("data/raw/landslide_inventory/GSI_Landslide_Inventory.geojson")
    bnd = gpd.read_file("data/raw/mizoram_boundary.geojson").to_crs(gsi.crs)
    say(f"  Total GSI records (India): {len(gsi):,}   CRS: {gsi.crs}")
    say(f"  Columns: {list(gsi.columns)}")
    miz = gsi[gsi.intersects(bnd.union_all())]
    say(f"  Records intersecting the Mizoram boundary: {len(miz):,}")
    say(f"  Geometry types in Mizoram: {miz.geom_type.value_counts().to_dict()}")
    if len(miz) and miz.geom_type.isin(["Polygon", "MultiPolygon"]).any():
        polys = miz[miz.geom_type.isin(["Polygon", "MultiPolygon"])].to_crs(32646)
        area = polys.area
        say(f"  Polygon area (m2): median={area.median():,.0f}  p10={area.quantile(.1):,.0f}"
            f"  p90={area.quantile(.9):,.0f}  max={area.max():,.0f}")
        # distance between the first vertex (what script 10 used) and the centroid
        def first_vertex(g):
            g0 = g.geoms[0] if g.geom_type == "MultiPolygon" else g
            return gpd.points_from_xy([g0.exterior.coords[0][0]], [g0.exterior.coords[0][1]])[0]
        fv = gpd.GeoSeries([first_vertex(g) for g in polys.geometry], crs=32646)
        shift = fv.distance(polys.centroid.reset_index(drop=True))
        say(f"  Script 10 kept only the FIRST VERTEX of each polygon. Shift from centroid (m):"
            f" median={shift.median():.0f}  p90={shift.quantile(.9):.0f}  max={shift.max():.0f}")
        summary["gsi_mizoram_polygon_area_median_m2"] = float(area.median())
        summary["gsi_first_vertex_shift_median_m"] = float(shift.median())
    summary["gsi_records_india"] = int(len(gsi))
    summary["gsi_records_mizoram"] = int(len(miz))
    summary["gsi_geom_types_mizoram"] = miz.geom_type.value_counts().to_dict()
    del gsi
except Exception as ex:  # keep audit running even if vector IO fails
    say(f"  GSI audit failed: {ex}")

# ===========================================================================
say("\n" + "=" * 78)
say("H. PHASE 2 TRAINING TABLE (landslide_dataset_classic.csv)")
say("=" * 78)
df = pd.read_csv("data/processed/modeling/landslide_dataset_classic.csv")
n1, n0 = int((df.landslide == 1).sum()), int((df.landslide == 0).sum())
say(f"  Rows={len(df):,}   positives={n1:,}   negatives={n0:,}   positive share={n1 / len(df):.3f}")
say(f"  README/presentation claim: 65,711 positives + 40,000 negatives = 91,944 rows")
say(f"  => {65711 - n1:,} positives and {40000 - n0:,} negatives were silently dropped as NaN")
say(f"  PR-AUC of a random classifier on this table = positive share = {n1 / len(df):.3f}")
summary.update({"csv_rows": len(df), "csv_pos": n1, "csv_neg": n0,
                "csv_pos_share": n1 / len(df)})
# reproduce the 01d candidate pool to show what the slope strata really were
with rasterio.open(PHASE2_FEATURES["slope"]) as src:
    slope_raw = src.read(1)
with rasterio.open("data/processed/inventory/mizoram_landslide_target_expanded_30m.tif") as src:
    tgt = src.read(1)
tgt = np.where(tgt == 255, 0, tgt)
old_valid = (dem != -9999.0) & ~np.isnan(dem)            # what 01d actually used
ls = (tgt == 1) & old_valid
excl = ndimage.binary_dilation(ls, iterations=5)
cand = (tgt == 0) & old_valid & ~excl & (slope_raw != -9999.0) & np.isfinite(slope_raw)
cand_out = cand & ~valid
say(f"  01d candidate pool: {int(cand.sum()):,} cells, of which {int(cand_out.sum()):,}"
    f" ({100 * cand_out.sum() / cand.sum():.1f} %) lie OUTSIDE Mizoram")
cuts = np.percentile(slope_raw[cand], np.linspace(0, 100, 6))
say(f"  Slope quintile cuts actually used (deg): {np.round(cuts, 2).tolist()}")
say(f"  README stated cuts: [0, 4.2, 9.8, 15.6, 23.4, 78.5]")
summary["phase2_candidate_cells"] = int(cand.sum())
summary["phase2_candidate_cells_outside_state"] = int(cand_out.sum())
summary["phase2_slope_quintile_cuts"] = np.round(cuts, 3).tolist()
del slope_raw, tgt, ls, excl, cand, cand_out

# LULC cross-tab (survey-bias indicator)
ct = pd.crosstab(df.lulc, df.landslide)
say("  LULC class x label (ESA codes; 50 = built-up):")
for code, r in ct.iterrows():
    say(f"     {int(code):3d}: non-LS={int(r.get(0, 0)):6,}  LS={int(r.get(1, 0)):6,}")

# ===========================================================================
say("\n" + "=" * 78)
say("I. VERIFIED FEATURE STATISTICS INSIDE THE STATE (for README correction)")
say("=" * 78)
rows = []
for name, path in PHASE2_FEATURES.items():
    a = read_float(path, valid)
    v = a[np.isfinite(a)]
    rows.append({"feature": name, "n": v.size, "min": v.min(), "p01": np.percentile(v, 1),
                 "mean": v.mean(), "median": np.median(v), "p99": np.percentile(v, 99),
                 "max": v.max(), "std": v.std()})
    say(f"  {name:20s} min={v.min():10.3f} mean={v.mean():10.3f} max={v.max():10.3f}")
    del a, v
pd.DataFrame(rows).round(4).to_csv(f"{AUDIT_DIR}/feature_stats_inside_state.csv", index=False)

# ===========================================================================
say("\n" + "=" * 78)
say("J. VERSION 2 MAP — ZONE AREAS (fixed 0.2 probability bins)")
say("=" * 78)
p = read_float("data/final/mizoram_landslide_susceptibility_v2.tif", valid)
pv = p[np.isfinite(p)]
bins = [0, .2, .4, .6, .8, 1.0001]
names = ["Very Low", "Low", "Moderate", "High", "Very High"]
zone_rows = []
for i, nm in enumerate(names):
    share = ((pv >= bins[i]) & (pv < bins[i + 1])).mean() * 100
    zone_rows.append({"zone": nm, "p_from": bins[i], "p_to": min(bins[i + 1], 1.0), "area_pct": share})
    say(f"  {nm:10s} [{bins[i]:.1f}, {min(bins[i + 1], 1):.1f}) : {share:6.2f} % of land")
say(f"  Mean predicted probability over the state = {pv.mean():.3f}")
say(f"  Share of state with P >= 0.5 = {(pv >= 0.5).mean() * 100:.2f} %")
pd.DataFrame(zone_rows).round(3).to_csv(f"{AUDIT_DIR}/v2_map_zone_areas.csv", index=False)
summary["v2_mean_prob"] = float(pv.mean())
summary["v2_share_p_ge_0_5"] = float((pv >= 0.5).mean())
summary["v2_zone_area_pct"] = {r["zone"]: r["area_pct"] for r in zone_rows}

with open(f"{AUDIT_DIR}/audit_report.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(report))
save_json(summary, f"{AUDIT_DIR}/audit_summary.json")
say(f"\nSaved: {AUDIT_DIR}/audit_report.txt and audit_summary.json")
