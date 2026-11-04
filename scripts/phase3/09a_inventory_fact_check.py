"""
Phase 3 / Step 09a — Fact-check of inventory statements made in Session 1 (DATA-026).

Several Session 1 statements were approximate or inferred from a preview of the
attribute table. This script computes the exact numbers so that the documentation
can be corrected with evidence:
  a. Are ALL 30,842 GSI records in India points, or only those in Mizoram?
  b. Does NH_SH_LOCATION really name a road in almost every Mizoram record?
  c. Exactly how many GSI locations did the Phase 2 500 m de-duplication remove?
  d. Exact COOLR location-accuracy counts (including missing values).
  e. How large are the recorded landslides relative to one 30 m pixel?

Output: data/phase3/inventory/inventory_fact_check.json
"""

import os
import re
import sys
import numpy as np
import pandas as pd
import geopandas as gpd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p3_common import INV_DIR, save_json, log

PIXEL_M2 = 30.3068 ** 2
gsi = gpd.read_file("data/raw/landslide_inventory/GSI_Landslide_Inventory.geojson")
bnd = gpd.read_file("data/raw/mizoram_boundary.geojson").to_crs(gsi.crs).union_all()
miz = gsi[gsi.within(bnd)].copy()
out = {"a_geometry_types_all_india": gsi.geom_type.value_counts().to_dict(),
       "a_records_all_india": int(len(gsi)), "records_inside_mizoram": int(len(miz))}

# b. road wording in the location field
loc = miz["NH_SH_LOCATION"].astype("object").where(miz["NH_SH_LOCATION"].notna(), "").astype(str).str.strip()
road_re = re.compile(r"\b(rd|road|roads|nh|n\.h|sh|s\.h|highway|hwy|bypass|by-pass|multi-?\s?modal|section|bridge|bpr|pmgsy|br\.?)\b",
                     re.IGNORECASE)
filled = loc != ""
roadlike = loc.apply(lambda s: bool(road_re.search(s)))
out["b_location_field_filled"] = int(filled.sum())
out["b_location_mentions_road_terms"] = int(roadlike.sum())
out["b_location_examples_without_road_terms"] = loc[filled & ~roadlike].value_counts().head(12).to_dict()
lulc = miz["LANDUSE_LANDCOVER"].astype("object").where(miz["LANDUSE_LANDCOVER"].notna(), "").astype(str).str.lower()
out["b_landuse_mentions_cut_or_road"] = int(lulc.str.contains(r"cut|road|excavat").sum())
out["b_landuse_mentions_settlement"] = int(lulc.str.contains(r"settlement|habitation|urban").sum())

# c. Phase 2 de-duplication loss
combined = gpd.read_file("data/raw/landslide_inventory/combined_mizoram_landslides.geojson")
key = lambda g: g.geometry.x.round(5).astype(str) + "_" + g.geometry.y.round(5).astype(str)
miz["k"] = key(miz)
combined["k"] = key(combined)
kept = miz["k"].isin(set(combined["k"]))
uniq = miz.drop_duplicates("k")
out["c_gsi_unique_locations_in_state"] = int(len(uniq))
out["c_unique_locations_kept_in_phase2"] = int(uniq["k"].isin(set(combined["k"])).sum())
out["c_unique_locations_lost_in_phase2"] = int((~uniq["k"].isin(set(combined["k"]))).sum())
out["c_lost_share_of_unique_locations"] = float((~uniq["k"].isin(set(combined["k"]))).mean())
out["c_records_kept_of_2041"] = int(kept.sum())

# d. COOLR accuracy
coolr = gpd.read_file("data/raw/landslide_inventory/mizoram_landslides_coolr.geojson")
inside = coolr[coolr.within(bnd)]
out["d_coolr_accuracy_all_44"] = coolr["location_accuracy"].astype("object").fillna("missing").astype(str).value_counts().to_dict()
out["d_coolr_accuracy_inside_boundary"] = inside["location_accuracy"].astype("object").fillna("missing").astype(str).value_counts().to_dict()

# e. landslide size
ln = pd.to_numeric(miz.LENGTH, errors="coerce")
wd = pd.to_numeric(miz.WIDTH, errors="coerce")
fp = (ln * wd).replace(0, np.nan).dropna()
out["e_footprint_m2_median"] = float(fp.median())
out["e_footprint_m2_p90"] = float(fp.quantile(.9))
out["e_footprint_m2_max"] = float(fp.max())
out["e_share_records_with_footprint_at_most_one_pixel"] = float((fp <= PIXEL_M2).mean())
out["e_records_with_footprint"] = int(fp.size)

save_json(out, f"{INV_DIR}/inventory_fact_check.json")
for k, v in out.items():
    log(f"{k}: {v}")
