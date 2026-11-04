import requests
import json
import os
import geopandas as gpd

os.makedirs("data/raw/geology", exist_ok=True)
boundary_path = "data/raw/mizoram_boundary.geojson"
boundary = gpd.read_file(boundary_path)

print("=" * 50)
print("Downloading GEM Global Active Faults Database...")
print("=" * 50)
faults_url = "https://raw.githubusercontent.com/cossatot/gem-global-active-faults/master/geojson/gem_active_faults.geojson"
faults_path = "data/raw/geology/global_faults.geojson"

if not os.path.exists(faults_path):
    print("Downloading...")
    resp = requests.get(faults_url, timeout=60)
    with open(faults_path, "wb") as f:
        f.write(resp.content)
    print("Saved global faults.")
else:
    print("Global faults already downloaded.")

print("Clipping faults to Mizoram (plus 50km buffer)...")
faults_gdf = gpd.read_file(faults_path)
# Create a 50km buffer (in a projected CRS) to ensure we get faults that might influence the region
boundary_utm = boundary.to_crs(epsg=32646)
buffer_utm = boundary_utm.geometry.buffer(50000)
buffer_wgs = gpd.GeoDataFrame(geometry=buffer_utm).set_crs(epsg=32646).to_crs(epsg=4326)

mizoram_faults = gpd.sjoin(faults_gdf, buffer_wgs, how="inner", predicate="intersects")
if len(mizoram_faults) > 0:
    out_faults = "data/raw/geology/mizoram_faults.geojson"
    mizoram_faults = mizoram_faults.drop_duplicates(subset=["catalog_name", "average_dip", "geometry"])
    
    # Drop index_right if it exists
    if "index_right" in mizoram_faults.columns:
        mizoram_faults = mizoram_faults.drop(columns=["index_right"])
        
    mizoram_faults.to_file(out_faults, driver="GeoJSON")
    print(f"Saved {len(mizoram_faults)} faults to {out_faults}")
else:
    print("No active faults found within 50km of Mizoram in GEM database.")

print("\n" + "=" * 50)
print("Downloading Lithology (GLiM)...")
print("=" * 50)
glim_url = "https://www.dropbox.com/s/9vuowtebp9f1iud/LiMW_GIS%202015.gdb.zip?dl=1"
glim_zip_path = "data/raw/geology/GLiM.zip"

print("\n" + "=" * 50)
print("Downloading Lithology (Macrostrat Grid Search)...")
print("=" * 50)

# Macrostrat map API only supports lat/lng point queries.
# We will create a grid of points across Mizoram's bounding box
# and query each point, merging the resulting polygons.
import numpy as np
import time

minx, miny, maxx, maxy = buffer_wgs.total_bounds
lng_steps = np.arange(minx, maxx, 0.2)
lat_steps = np.arange(miny, maxy, 0.2)

print(f"Querying {len(lng_steps) * len(lat_steps)} points across Mizoram bbox...")

all_features = []
seen_map_ids = set()

for lat in lat_steps:
    for lng in lng_steps:
        url = f"https://macrostrat.org/api/v2/geologic_units/map?scale=tiny&shape=true&format=geojson&lat={lat}&lng={lng}"
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                features_data = data.get("success", data)
                features = features_data.get("data", {}).get("features", []) if isinstance(features_data, dict) and "data" in features_data else []
                    
                if isinstance(features, list):
                    for feat in features:
                        if isinstance(feat, dict):
                            props = feat.get("properties", {})
                            map_id = props.get("map_id")
                            if map_id and map_id not in seen_map_ids:
                                seen_map_ids.add(map_id)
                                all_features.append(feat)
        except Exception as e:
            print(f"Failed at {lat}, {lng}: {e}")
        time.sleep(0.1) # Be nice to API

if all_features:
    out_litho = "data/raw/geology/mizoram_lithology.geojson"
    fc = {"type": "FeatureCollection", "features": all_features}
    with open(out_litho, "w") as f:
        json.dump(fc, f)
    
    litho_gdf = gpd.read_file(out_litho)
    print(f"Saved {len(litho_gdf)} unique lithology polygons to {out_litho}")
    if "lith" in litho_gdf.columns:
        print(f"Rock types found: {litho_gdf['lith'].unique()}")
else:
    print("No lithology data found via Macrostrat grid search.")


