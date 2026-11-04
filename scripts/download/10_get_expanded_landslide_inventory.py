"""
Multi-Source Landslide Inventory Downloader and Merger

This script finds and downloads landslide data from EVERY available public
source, then merges them into a single comprehensive GeoJSON for Mizoram
and its neighbouring states (geologic region).

SOURCES COVERED
===============
1. NASA COOLR (existing) — already downloaded, 44 events (2007-2023)
2. GSI Landslide Inventory (BharAtlas) — 30,842 pan-India events, CC0 licence
3. NASA EONET API — ongoing/recent significant landslides
4. NASA GLC via Socrata open API — extended NASA Global Landslide Catalog
5. NESDR (NESAC) WFS — NE India specialised repository (if accessible)

GEOGRAPHIC SCOPE
================
Primary target:   Mizoram         (21.94-24.52N, 92.15-93.44E)
Extended buffer:  NE India states  (20.0-28.0N,  88.0-97.5E)
  — Mizoram, Manipur, Meghalaya, Nagaland, Tripura, Assam,
    Arunachal Pradesh, Sikkim
    
WHY NE INDIA?
=============
Mizoram has almost identical geology, climate, and terrain characteristics
as neighbouring states. Landslides from Manipur and Meghalaya teach the
model about the same rock-water-slope dynamics. This is standard practice
in transfer-learning for data-scarce hazard mapping.

OUTPUT
======
data/raw/landslide_inventory/combined_ne_india_landslides.geojson
data/raw/landslide_inventory/combined_summary.txt
"""

import os
import json
import requests
import time
from datetime import datetime

os.makedirs("data/raw/landslide_inventory", exist_ok=True)

# Mizoram bounding box
MIZ_BBOX   = (92.15, 21.94, 93.44, 24.52)
# Greater NE India bounding box (study + transfer region)
NE_BBOX    = (88.0, 20.0, 97.5, 28.0)

NE_STATES  = {"mizoram", "manipur", "meghalaya", "nagaland", "tripura",
               "assam", "arunachal", "sikkim"}

def in_bbox(lon, lat, bbox):
    minx, miny, maxx, maxy = bbox
    return minx <= lon <= maxx and miny <= lat <= maxy

def text_matches_ne(text):
    t = str(text).lower()
    return any(s in t for s in NE_STATES)

collected_features = []   # GeoJSON Feature dicts
source_counts = {}

# ============================================================================
# SOURCE 1 — Existing NASA COOLR (already downloaded, all years)
# ============================================================================
print("=" * 65)
print("SOURCE 1 — Existing NASA COOLR GeoJSON (all years)")
print("=" * 65)

coolr_path = "data/raw/landslide_inventory/mizoram_landslides_coolr.geojson"
if os.path.exists(coolr_path):
    with open(coolr_path, encoding="utf-8", errors="replace") as f:
        coolr_data = json.load(f)
    feats = coolr_data.get("features", [])
    # Take ALL years (original pipeline filtered to 2007-2017 — we now use all)
    for feat in feats:
        feat["properties"]["_source"] = "NASA_COOLR"
    collected_features.extend(feats)
    source_counts["NASA_COOLR"] = len(feats)
    print(f"  Loaded {len(feats)} events (all years, no date filter)")
else:
    print(f"  NOT FOUND: {coolr_path}")
    source_counts["NASA_COOLR"] = 0


# ============================================================================
# SOURCE 2 — GSI Landslide Inventory via BharAtlas (CC0, 30,842 records)
# ============================================================================
print("\n" + "=" * 65)
print("SOURCE 2 — GSI Landslide Inventory (BharAtlas / CC0)")
print("=" * 65)

gsi_local = "data/raw/landslide_inventory/GSI_Landslide_Inventory.geojson"
gsi_url   = ("https://pub-0429b8e3b5a946e69ea007df844a6f1c.r2.dev/"
             "environment/gsi-landslide-inventory/GSI_Landslide_Inventory.geojson")

if not os.path.exists(gsi_local):
    print(f"  Downloading GSI inventory (~54 MB) from BharAtlas CDN...")
    try:
        resp = requests.get(gsi_url, timeout=120, stream=True)
        if resp.status_code == 200:
            total = 0
            with open(gsi_local, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    f.write(chunk)
                    total += len(chunk)
                    if total % (5 * 1024 * 1024) < 65536:
                        print(f"    Downloaded {total / 1e6:.0f} MB...")
            print(f"  SUCCESS: Saved {total / 1e6:.1f} MB -> {gsi_local}")
        else:
            print(f"  FAILED: HTTP {resp.status_code}")
    except Exception as ex:
        print(f"  ERROR: {ex}")
else:
    print(f"  Already downloaded: {gsi_local}")

# Filter for NE India
if os.path.exists(gsi_local):
    print("  Filtering for NE India region...")
    gsi_ne_feats = []
    with open(gsi_local, encoding="utf-8", errors="replace") as f:
        gsi_data = json.load(f)
    
    all_gsi = gsi_data.get("features", [])
    print(f"  Total GSI records: {len(all_gsi):,}")
    
    for feat in all_gsi:
        geom = feat.get("geometry", {})
        if not geom:
            continue
        coords = geom.get("coordinates", [])
        lon, lat = None, None
        if geom.get("type") == "Point" and len(coords) >= 2:
            lon, lat = coords[0], coords[1]
        elif geom.get("type") in ("Polygon", "MultiPolygon"):
            # Use centroid proxy: first coordinate of first ring
            try:
                if geom["type"] == "Polygon":
                    lon, lat = coords[0][0][0], coords[0][0][1]
                else:
                    lon, lat = coords[0][0][0][0], coords[0][0][0][1]
            except (IndexError, TypeError):
                pass

        if lon is not None and lat is not None:
            props = feat.get("properties", {})
            in_ne = in_bbox(lon, lat, NE_BBOX)
            # Also check text fields for NE state names
            text_ne = any(text_matches_ne(props.get(col, ""))
                          for col in ["State", "state", "District", "district",
                                      "Location", "location", "LOCATION",
                                      "STATE", "DISTRICT"])
            if in_ne or text_ne:
                feat["properties"]["_source"] = "GSI_BharAtlas"
                feat["properties"]["_lon"] = lon
                feat["properties"]["_lat"] = lat
                gsi_ne_feats.append(feat)

    source_counts["GSI_BharAtlas"] = len(gsi_ne_feats)
    collected_features.extend(gsi_ne_feats)
    print(f"  NE India GSI events found: {len(gsi_ne_feats):,}")
    
    # Save NE India subset separately
    ne_gsi_path = "data/raw/landslide_inventory/gsi_ne_india_landslides.geojson"
    with open(ne_gsi_path, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": gsi_ne_feats}, f)
    print(f"  NE India subset saved: {ne_gsi_path}")
else:
    source_counts["GSI_BharAtlas"] = 0


# ============================================================================
# SOURCE 3 — NASA EONET API (ongoing/recent significant events)
# ============================================================================
print("\n" + "=" * 65)
print("SOURCE 3 — NASA EONET API (recent significant events)")
print("=" * 65)

try:
    eonet_url = "https://eonet.gsfc.nasa.gov/api/v3/categories/landslides"
    resp = requests.get(eonet_url, params={"status": "all", "limit": 1000}, timeout=20)
    if resp.status_code == 200:
        eonet_data = resp.json()
        events = eonet_data.get("events", [])
        print(f"  Total EONET landslide events: {len(events)}")
        
        eonet_ne = []
        for ev in events:
            for geom in ev.get("geometry", []):
                coords = geom.get("coordinates", [])
                if len(coords) >= 2:
                    lon, lat = coords[0], coords[1]
                    if in_bbox(lon, lat, NE_BBOX):
                        feat = {
                            "type": "Feature",
                            "geometry": {
                                "type": "Point",
                                "coordinates": [lon, lat]
                            },
                            "properties": {
                                "event_id": ev.get("id"),
                                "event_title": ev.get("title"),
                                "event_date": geom.get("date", ""),
                                "source": "NASA_EONET",
                                "_source": "NASA_EONET",
                                "latitude": lat,
                                "longitude": lon,
                            }
                        }
                        eonet_ne.append(feat)
        
        source_counts["NASA_EONET"] = len(eonet_ne)
        collected_features.extend(eonet_ne)
        print(f"  EONET events in NE India: {len(eonet_ne)}")
        if eonet_ne:
            for e in eonet_ne[:5]:
                p = e["properties"]
                print(f"    {p.get('event_date','?')[:10]} | {p.get('event_title','?')}")
    else:
        print(f"  FAILED: HTTP {resp.status_code}")
        source_counts["NASA_EONET"] = 0
except Exception as ex:
    print(f"  ERROR: {ex}")
    source_counts["NASA_EONET"] = 0


# ============================================================================
# SOURCE 4 — NASA GLC via data.nasa.gov CSV download (extended catalog)
# ============================================================================
print("\n" + "=" * 65)
print("SOURCE 4 — NASA Global Landslide Catalog (data.nasa.gov CSV)")
print("=" * 65)

glc_local = "data/raw/landslide_inventory/nasa_glc_full.csv"
glc_url   = "https://data.nasa.gov/api/views/dd9e-wu2v/rows.csv?accessType=DOWNLOAD"

if not os.path.exists(glc_local):
    print(f"  Downloading NASA GLC CSV (~large) from data.nasa.gov...")
    try:
        resp = requests.get(glc_url, timeout=120, stream=True,
                            headers={"User-Agent": "Mozilla/5.0 (Research Project)"})
        if resp.status_code == 200:
            total = 0
            with open(glc_local, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    f.write(chunk)
                    total += len(chunk)
            print(f"  SUCCESS: Saved {total / 1e6:.1f} MB -> {glc_local}")
        else:
            print(f"  FAILED: HTTP {resp.status_code}")
    except Exception as ex:
        print(f"  ERROR: {ex}")
else:
    print(f"  Already downloaded: {glc_local}")

if os.path.exists(glc_local):
    import csv
    glc_ne_feats = []
    try:
        with open(glc_local, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                lat_str = row.get("latitude", "") or row.get("Latitude", "")
                lon_str = row.get("longitude","") or row.get("Longitude","")
                try:
                    lat = float(lat_str)
                    lon = float(lon_str)
                except (ValueError, TypeError):
                    continue
                
                in_ne = in_bbox(lon, lat, NE_BBOX)
                text_ne = any(text_matches_ne(row.get(col, ""))
                              for col in list(row.keys()))
                
                if in_ne or text_ne:
                    # Skip if already in COOLR (same source, avoid duplicates)
                    event_id = row.get("event_id", "")
                    feat = {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [lon, lat]},
                        "properties": {
                            "event_id": event_id,
                            "event_date": row.get("event_date", ""),
                            "location_description": row.get("location_description",""),
                            "country_name": row.get("country_name",""),
                            "landslide_category": row.get("landslide_category",""),
                            "landslide_trigger": row.get("landslide_trigger",""),
                            "latitude": lat,
                            "longitude": lon,
                            "_source": "NASA_GLC_CSV"
                        }
                    }
                    glc_ne_feats.append(feat)
        
        source_counts["NASA_GLC_CSV"] = len(glc_ne_feats)
        collected_features.extend(glc_ne_feats)
        print(f"  NASA GLC CSV NE India events: {len(glc_ne_feats)}")
    except Exception as ex:
        print(f"  ERROR reading CSV: {ex}")
        source_counts["NASA_GLC_CSV"] = 0
else:
    source_counts["NASA_GLC_CSV"] = 0


# ============================================================================
# SOURCE 5 — NESDR / NESAC GeoServer WFS (NE India specialist)
# ============================================================================
print("\n" + "=" * 65)
print("SOURCE 5 — NESDR / NESAC GeoServer WFS")
print("=" * 65)

nesdr_endpoints = [
    "https://nesdr.gov.in/geoserver/wfs",
    "https://nesdr.nesac.gov.in/geoserver/wfs",
    "https://nesac.gov.in/geoserver/wfs",
]
nesdr_found = False
for url in nesdr_endpoints:
    try:
        resp = requests.get(url, params={
            "service": "WFS", "version": "2.0.0", "request": "GetCapabilities"
        }, timeout=15, verify=False)
        if resp.status_code == 200 and len(resp.text) > 1000:
            print(f"  NESDR accessible: {url}")
            # Save capabilities
            with open("data/raw/landslide_inventory/nesdr_capabilities.xml", "w") as f:
                f.write(resp.text)
            # Try to find landslide layer names
            import re
            names = re.findall(r'<Name>([^<]+)</Name>', resp.text)
            ls_layers = [n for n in names if any(k in n.lower()
                         for k in ["landslide","hazard","land_slide","ls_","disaster"])]
            print(f"  Landslide-relevant layers: {ls_layers[:10]}")
            
            # Try to fetch from each layer
            for layer in ls_layers[:3]:
                try:
                    feat_resp = requests.get(url, params={
                        "service": "WFS", "version": "2.0.0",
                        "request": "GetFeature", "typeName": layer,
                        "outputFormat": "application/json",
                        "BBOX": f"{NE_BBOX[1]},{NE_BBOX[0]},{NE_BBOX[3]},{NE_BBOX[2]},EPSG:4326"
                    }, timeout=30, verify=False)
                    if feat_resp.status_code == 200:
                        fd = feat_resp.json()
                        feats = fd.get("features", [])
                        if feats:
                            for feat in feats:
                                feat["properties"]["_source"] = "NESDR_WFS"
                            collected_features.extend(feats)
                            print(f"    Layer '{layer}': {len(feats)} features")
                            source_counts["NESDR_WFS"] = source_counts.get("NESDR_WFS", 0) + len(feats)
                except Exception as layer_ex:
                    print(f"    Layer '{layer}' error: {layer_ex}")
            nesdr_found = True
            break
    except Exception as ex:
        print(f"  {url}: {type(ex).__name__} - {str(ex)[:80]}")

if not nesdr_found:
    print("  NESDR WFS not accessible (requires registration or VPN).")
    source_counts["NESDR_WFS"] = 0


# ============================================================================
# MERGE AND DEDUPLICATE
# ============================================================================
print("\n" + "=" * 65)
print("MERGING AND DEDUPLICATING ALL SOURCES")
print("=" * 65)

print(f"\nRaw counts by source:")
total_raw = 0
for src, cnt in source_counts.items():
    print(f"  {src:20s}: {cnt:6,}")
    total_raw += cnt
print(f"  {'TOTAL RAW':20s}: {total_raw:6,}")

# Deduplicate: events within 500m of each other and same approximate date
# are considered duplicates. Use a simple grid-cell approach.
def approx_grid_key(lon, lat, date_str, resolution=0.005):
    # 0.005 degrees ~ 500m
    glon = round(lon / resolution) * resolution
    glat = round(lat / resolution) * resolution
    # Date to year-month
    try:
        d = datetime.fromisoformat(date_str[:10])
        dkey = f"{d.year}-{d.month:02d}"
    except (ValueError, TypeError, IndexError):
        dkey = "unknown"
    return (round(glon, 4), round(glat, 4), dkey)

seen_keys = set()
deduped_features = []

for feat in collected_features:
    geom = feat.get("geometry", {})
    if not geom:
        continue
    coords = geom.get("coordinates", [])
    if not coords:
        continue
    
    try:
        if geom["type"] == "Point":
            lon, lat = coords[0], coords[1]
        elif geom["type"] in ("Polygon", "MultiPolygon"):
            lon = feat["properties"].get("_lon", coords[0][0][0] if geom["type"] == "Polygon" else coords[0][0][0][0])
            lat = feat["properties"].get("_lat", coords[0][0][1] if geom["type"] == "Polygon" else coords[0][0][0][1])
        else:
            continue
    except (IndexError, TypeError, KeyError):
        continue
    
    props = feat.get("properties", {})
    date_str = (props.get("event_date", "") or 
                props.get("Date", "") or 
                props.get("date", "") or "unknown")
    
    key = approx_grid_key(lon, lat, str(date_str))
    if key not in seen_keys:
        seen_keys.add(key)
        # Standardize geometry to Point for simplicity
        feat["geometry"] = {"type": "Point", "coordinates": [lon, lat]}
        deduped_features.append(feat)

print(f"\nAfter deduplication: {len(deduped_features):,} unique events")


# ============================================================================
# SPATIAL FILTERS — save two versions
# ============================================================================

# Version A: Mizoram only (strict bbox)
miz_feats = []
ne_feats  = []
for feat in deduped_features:
    lon, lat = feat["geometry"]["coordinates"]
    if in_bbox(lon, lat, MIZ_BBOX):
        miz_feats.append(feat)
    if in_bbox(lon, lat, NE_BBOX):
        ne_feats.append(feat)

print(f"\nMizoram-only events   : {len(miz_feats):,}")
print(f"NE India total events : {len(ne_feats):,}")


# ============================================================================
# SAVE OUTPUTS
# ============================================================================
print("\n" + "=" * 65)
print("SAVING OUTPUTS")
print("=" * 65)

# Full NE India combined
ne_out = "data/raw/landslide_inventory/combined_ne_india_landslides.geojson"
with open(ne_out, "w", encoding="utf-8") as f:
    json.dump({"type": "FeatureCollection", "features": ne_feats}, f)
size_mb = os.path.getsize(ne_out) / 1e6
print(f"  NE India combined: {ne_out}  ({size_mb:.1f} MB, {len(ne_feats)} events)")

# Mizoram only
miz_out = "data/raw/landslide_inventory/combined_mizoram_landslides.geojson"
with open(miz_out, "w", encoding="utf-8") as f:
    json.dump({"type": "FeatureCollection", "features": miz_feats}, f)
print(f"  Mizoram only:      {miz_out}  ({len(miz_feats)} events)")

# Summary
summary_path = "data/raw/landslide_inventory/combined_summary.txt"
with open(summary_path, "w", encoding="utf-8") as f:
    f.write("LANDSLIDE INVENTORY — MULTI-SOURCE COMBINATION SUMMARY\n")
    f.write("=" * 60 + "\n\n")
    f.write(f"Generated: {datetime.now().isoformat()}\n\n")
    f.write("Source breakdown (raw):\n")
    for src, cnt in source_counts.items():
        f.write(f"  {src:25s}: {cnt:,}\n")
    f.write(f"\nTotal raw              : {total_raw:,}\n")
    f.write(f"After deduplication    : {len(deduped_features):,}\n")
    f.write(f"Mizoram bbox only      : {len(miz_feats):,}\n")
    f.write(f"NE India (study zone)  : {len(ne_feats):,}\n")
    f.write("\nFiles saved:\n")
    f.write(f"  {ne_out}\n")
    f.write(f"  {miz_out}\n")

print(f"  Summary: {summary_path}")

print("\n" + "=" * 65)
print("DONE. Next step: run 04_rasterize_expanded_inventory.py")
print("=" * 65)
