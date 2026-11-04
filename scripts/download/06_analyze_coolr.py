"""
Filter NASA COOLR for Mizoram and NE India events, and perform full attribute inspection.
"""
import geopandas as gpd
import pandas as pd
import os

gdb_path = "data/raw/landslide_inventory/COOLR_extracted/COOLR.gdb"
boundary_path = "data/raw/mizoram_boundary.geojson"

# Load Mizoram boundary
boundary = gpd.read_file(boundary_path)

# Load all COOLR layers and combine events
print("Loading COOLR event layers...")
events_pt = gpd.read_file(gdb_path, layer="nasa_coolr_events_point")
events_poly = gpd.read_file(gdb_path, layer="nasa_coolr_events_poly")
reports_pt = gpd.read_file(gdb_path, layer="nasa_coolr_reports_point")

print(f"Events (point): {len(events_pt)}")
print(f"Events (poly): {len(events_poly)}")
print(f"Reports (point): {len(reports_pt)}")

# ============================================================
# Filter for India
# ============================================================
print("\n" + "=" * 60)
print("INDIA FILTER")
print("=" * 60)

india_events_pt = events_pt[events_pt["country_name"] == "India"]
india_events_poly = events_poly[events_poly["country_name"] == "India"]
india_reports_pt = reports_pt[reports_pt["country_name"] == "India"]

print(f"India events (point): {len(india_events_pt)}")
print(f"India events (poly): {len(india_events_poly)}")
print(f"India reports (point): {len(india_reports_pt)}")

# ============================================================
# Spatial filter for Mizoram
# ============================================================
print("\n" + "=" * 60)
print("MIZORAM SPATIAL FILTER")
print("=" * 60)

# Points within Mizoram
miz_events_pt = gpd.sjoin(events_pt, boundary, how="inner", predicate="within")
miz_reports_pt = gpd.sjoin(reports_pt, boundary, how="inner", predicate="within")

# For polygons, use intersects
miz_events_poly = gpd.sjoin(events_poly, boundary, how="inner", predicate="intersects")

print(f"Mizoram events (point): {len(miz_events_pt)}")
print(f"Mizoram events (poly): {len(miz_events_poly)}")
print(f"Mizoram reports (point): {len(miz_reports_pt)}")

# Also text search
text_miz_events = events_pt[events_pt["location_description"].astype(str).str.contains("Mizoram|mizoram", na=False)]
text_miz_reports = reports_pt[reports_pt.apply(
    lambda r: "mizoram" in str(r.get("location_description", "")).lower() or 
              "mizoram" in str(r.get("admin_division_name", "")).lower(), axis=1
)]
print(f"Text match events: {len(text_miz_events)}")
print(f"Text match reports: {len(text_miz_reports)}")

# Combine all Mizoram results
all_mizoram = []
for df in [miz_events_pt, miz_events_poly, miz_reports_pt, text_miz_events, text_miz_reports]:
    if len(df) > 0:
        all_mizoram.append(df)

if all_mizoram:
    # Concatenate
    combined = pd.concat(all_mizoram, ignore_index=True)
    # Deduplicate by event_id
    combined = combined.drop_duplicates(subset=["event_id"])
    print(f"\nTotal unique Mizoram events (after dedup): {len(combined)}")
else:
    combined = pd.DataFrame()
    print("\nNo Mizoram events found.")

# ============================================================
# NE India as fallback
# ============================================================
print("\n" + "=" * 60)
print("NE INDIA FALLBACK")
print("=" * 60)

ne_states = ["Mizoram", "Manipur", "Meghalaya", "Nagaland", "Tripura", "Assam", "Arunachal", "Sikkim"]

# Search in reports which have admin_division_name
ne_reports = reports_pt[reports_pt["admin_division_name"].astype(str).apply(
    lambda x: any(s.lower() in str(x).lower() for s in ne_states)
)]
print(f"NE India reports (by admin_division_name): {len(ne_reports)}")
if len(ne_reports) > 0:
    print(f"  By state: {ne_reports['admin_division_name'].value_counts().to_dict()}")

# Search in events by location_description
ne_events = events_pt[events_pt["location_description"].astype(str).apply(
    lambda x: any(s.lower() in str(x).lower() for s in ne_states)
)]
print(f"NE India events (by location text): {len(ne_events)}")

# ============================================================
# Detailed attribute inspection
# ============================================================
print("\n" + "=" * 60)
print("TEMPORAL ATTRIBUTE INSPECTION")
print("=" * 60)

# Use whatever Mizoram data we have, or NE India as fallback
inspect_df = combined if len(combined) > 0 else pd.concat([ne_reports, ne_events], ignore_index=True).drop_duplicates(subset=["event_id"])
inspect_label = "Mizoram" if len(combined) > 0 else "NE India"

print(f"\nInspecting {len(inspect_df)} {inspect_label} records:")

# Date analysis
print(f"\n  event_date column:")
print(f"    dtype: {inspect_df['event_date'].dtype}")
print(f"    non-null: {inspect_df['event_date'].notna().sum()}/{len(inspect_df)}")
dates = pd.to_datetime(inspect_df["event_date"], errors="coerce")
print(f"    parsed dates: {dates.notna().sum()}")
if dates.notna().any():
    print(f"    date range: {dates.min()} to {dates.max()}")
    print(f"    year distribution: {dates.dt.year.value_counts().sort_index().to_dict()}")
    
    # Check date precision
    has_exact_day = (dates.dt.day != 1).sum()
    all_first_of_month = (dates.dt.day == 1).sum()
    print(f"    events with day != 1st: {has_exact_day}")
    print(f"    events on 1st of month: {all_first_of_month}")
    print(f"    => Date precision: {'EXACT DAY available' if has_exact_day > all_first_of_month else 'Mostly month-level only'}")

# Event time
if "event_time" in inspect_df.columns:
    print(f"\n  event_time column:")
    print(f"    non-null/non-empty: {(inspect_df['event_time'].astype(str).str.strip() != '').sum()}")
    print(f"    sample: {inspect_df['event_time'].head(10).tolist()}")

# Other key fields
for col in ["landslide_category", "landslide_trigger", "source_name", "method"]:
    if col in inspect_df.columns:
        print(f"\n  {col}: {inspect_df[col].value_counts().head(10).to_dict()}")

# Geometry types
if "geometry" in inspect_df.columns:
    print(f"\n  Geometry types: {inspect_df.geometry.type.value_counts().to_dict()}")

# ============================================================
# Print all records
# ============================================================
print("\n" + "=" * 60)
print(f"ALL {inspect_label} RECORDS")
print("=" * 60)

for idx, row in inspect_df.iterrows():
    print(f"\n--- Event ID: {row.get('event_id', 'N/A')} ---")
    for col in inspect_df.columns:
        if col not in ["geometry", "index_right"]:
            val = row[col]
            if pd.notna(val) and str(val).strip():
                print(f"  {col}: {val}")
    if "geometry" in inspect_df.columns and row.geometry is not None:
        print(f"  geometry: {row.geometry.wkt[:100]}")

# ============================================================
# Save results
# ============================================================
if len(inspect_df) > 0:
    # Save as GeoJSON
    cols_to_save = [c for c in inspect_df.columns if c not in ["index_right"]]
    save_df = gpd.GeoDataFrame(inspect_df[cols_to_save], geometry="geometry", crs="EPSG:4326")
    outpath = f"data/raw/landslide_inventory/{inspect_label.lower().replace(' ', '_')}_landslides_coolr.geojson"
    save_df.to_file(outpath, driver="GeoJSON")
    print(f"\nSaved to {outpath}")

print("\n" + "=" * 60)
print("ANALYSIS COMPLETE")
print("=" * 60)
