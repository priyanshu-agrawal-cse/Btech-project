"""
Phase 3 / Step 07 — Landslide inventory v3 (DATA-024).

Fixes relative to Phase 2 (DATA-012/013; audit DATA-017 F/G):
  * Spatial filter = the Mizoram boundary POLYGON (not a bounding box).
  * No 500 m grid de-duplication (it discarded 20.4 % of the unique GSI locations).
    Only records with identical coordinates (re-surveys of the same site) are merged.
  * No 90 m buffer. GSI records median landslide length 11 m and width 10 m
    (90th percentile 40 m x 30 m; runout median 0 m), so ONE 30 m pixel per
    landslide matches the recorded size; a 90 m buffer (~25,000 m2, ~41 px) is
    ~200x larger and creates pseudo-replicated, near-identical training rows.
  * NASA COOLR points are used only when location_accuracy == "exact"
    (31 of the 44 COOLR points are uncertain by 5–100 km, i.e. town centroids)
    and when they are farther than 150 m from every GSI record.
  * All GSI attributes are kept for the inventory analysis (trigger, material,
    movement type, activity, district, road section).

Outputs (data/phase3/inventory/):
  inventory_v3_points.gpkg     one row per landslide location (EPSG:32646)
  landslide_pixels_v3.csv      one row per positive pixel (row, col, n_records, event_ids)
  landslide_target_v3_30m.tif  UInt8: 1 = landslide pixel, 0 = other land, 255 = outside
  inventory_v3_summary.json
"""

import os
import sys
import numpy as np
import pandas as pd
import geopandas as gpd
from rasterio.transform import rowcol

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p3_common import INV_DIR, ensure_dirs, load_valid_mask, grid_info, write_uint8, save_json, log

ensure_dirs()
tr, crs, H, W, L = grid_info()
valid = load_valid_mask()
bnd = gpd.read_file("data/raw/mizoram_boundary.geojson")

# ---- GSI -------------------------------------------------------------------------------
gsi = gpd.read_file("data/raw/landslide_inventory/GSI_Landslide_Inventory.geojson")
bnd_g = bnd.to_crs(gsi.crs).union_all()
gsi = gsi[gsi.within(bnd_g)].copy()
n_gsi_inside = len(gsi)
gsi["coord_key"] = gsi.geometry.x.round(7).astype(str) + "_" + gsi.geometry.y.round(7).astype(str)
keep_cols = ["OBJECTID", "SLIDE_NO", "SLIDE_NAME", "DISTRICT", "TRIGGERING", "MATERIAL_TYPE",
             "MOVEMENT_TYPE", "ACTIVITY", "NH_SH_LOCATION", "LANDUSE_LANDCOVER", "LS_AREA",
             "LENGTH", "WIDTH", "HEIGHT", "DEPTH", "TOPOSHEET", "CITATION"]
agg = gsi.groupby("coord_key").agg(
    geometry=("geometry", "first"), n_records=("OBJECTID", "size"),
    **{c.lower(): (c, "first") for c in keep_cols})
gsi_u = gpd.GeoDataFrame(agg.reset_index(), geometry="geometry", crs=gsi.crs).to_crs(crs)
gsi_u["source"] = "GSI"
n_dup = n_gsi_inside - len(gsi_u)
log(f"GSI records inside Mizoram: {n_gsi_inside:,}; identical-coordinate duplicates merged: {n_dup}; "
    f"unique locations: {len(gsi_u):,}")

# ---- COOLR -------------------------------------------------------------------------------
coolr = gpd.read_file("data/raw/landslide_inventory/mizoram_landslides_coolr.geojson")
coolr = coolr[coolr.within(bnd.to_crs(coolr.crs).union_all())].to_crs(crs)
acc = coolr["location_accuracy"].astype(str).value_counts().to_dict()
exact = coolr[coolr["location_accuracy"].astype(str) == "exact"].copy()
if len(exact):
    d = exact.geometry.apply(lambda p: gsi_u.distance(p).min())
    exact = exact[d > 150]
exact = exact.assign(source="COOLR", n_records=1, district=exact.get("admin_division_name"),
                     triggering=exact.get("landslide_trigger"))
log(f"COOLR inside boundary: {len(coolr)} (accuracy {acc}); kept 'exact' & >150 m from GSI: {len(exact)}")

cols = ["source", "n_records", "district", "triggering", "geometry"]
pts = pd.concat([gsi_u, exact[[c for c in cols if c in exact.columns]]], ignore_index=True)
pts = gpd.GeoDataFrame(pts, geometry="geometry", crs=crs)
pts["event_id"] = np.arange(1, len(pts) + 1)

# ---- pixels -------------------------------------------------------------------------------
r, c = rowcol(tr, pts.geometry.x.values, pts.geometry.y.values)
pts["row"], pts["col"] = np.asarray(r), np.asarray(c)
inside_grid = (pts.row >= 0) & (pts.row < H) & (pts.col >= 0) & (pts.col < W)
pts = pts[inside_grid].copy()
pts["on_land"] = valid[pts.row.values, pts.col.values]
n_off = int((~pts.on_land).sum())
pts = pts[pts.on_land].drop(columns="on_land")
for col in pts.columns:
    if col != "geometry" and pts[col].dtype == object:
        pts[col] = pts[col].astype(str)       # GPKG needs one type per column
pts.to_file(f"{INV_DIR}/inventory_v3_points.gpkg", driver="GPKG")

pix = (pts.groupby(["row", "col"])
          .agg(n_locations=("event_id", "size"), n_records=("n_records", "sum"),
               event_ids=("event_id", lambda s: ";".join(map(str, s))),
               source=("source", lambda s: "+".join(sorted(set(s)))),
               district=("district", "first"))
          .reset_index())
pix.to_csv(f"{INV_DIR}/landslide_pixels_v3.csv", index=False)

target = np.where(valid, 0, 255).astype("uint8")
target[pix.row.values, pix.col.values] = 1
write_uint8(f"{INV_DIR}/landslide_target_v3_30m.tif", target)

summary = {
    "gsi_records_inside_boundary": n_gsi_inside, "gsi_identical_coordinate_duplicates": n_dup,
    "gsi_unique_locations": int(len(gsi_u)), "coolr_inside_boundary": int(len(coolr)),
    "coolr_location_accuracy_counts": acc, "coolr_exact_kept": int(len(exact)),
    "locations_off_land_mask": n_off, "locations_used": int(len(pts)),
    "positive_pixels": int(len(pix)), "pixels_with_more_than_one_location": int((pix.n_locations > 1).sum()),
    "positive_share_of_land": float(len(pix) / valid.sum()),
    "by_district": pts["district"].astype(str).value_counts().to_dict(),
    "gsi_triggering": gsi["TRIGGERING"].astype(str).str.strip().str.lower().value_counts().head(10).to_dict(),
    "gsi_material_type": gsi["MATERIAL_TYPE"].astype(str).value_counts().to_dict(),
    "gsi_movement_type": gsi["MOVEMENT_TYPE"].astype(str).value_counts().to_dict(),
    "gsi_activity": gsi["ACTIVITY"].astype(str).value_counts().to_dict(),
    "gsi_length_m_median": float(pd.to_numeric(gsi.LENGTH, errors="coerce").median()),
    "gsi_width_m_median": float(pd.to_numeric(gsi.WIDTH, errors="coerce").median()),
    "gsi_length_m_p90": float(pd.to_numeric(gsi.LENGTH, errors="coerce").quantile(.9)),
    "gsi_width_m_p90": float(pd.to_numeric(gsi.WIDTH, errors="coerce").quantile(.9)),
    "gsi_depth_m_median": float(pd.to_numeric(gsi.DEPTH, errors="coerce").median()),
    "gsi_runout_m_median": float(pd.to_numeric(gsi.RUNOUT_DISTANCE, errors="coerce").median()),
    "gsi_citations_top": gsi["CITATION"].astype(str).str[:120].value_counts().head(8).to_dict(),
}
save_json(summary, f"{INV_DIR}/inventory_v3_summary.json")
for k, v in summary.items():
    if not isinstance(v, dict):
        log(f"  {k:40s}: {v}")
log("Inventory v3 complete.")
