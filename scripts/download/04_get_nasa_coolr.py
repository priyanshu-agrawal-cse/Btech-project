import requests
import json
import os

os.makedirs("data/raw/landslide_inventory", exist_ok=True)

# Mizoram bounding box
minx, miny, maxx, maxy = 92.15, 21.94, 93.44, 24.52

# Try multiple ArcGIS Online hosted feature service URLs for NASA COOLR
urls = [
    "https://services.arcgis.com/5T5nSi527N4F7luB/arcgis/rest/services/COOLR/FeatureServer/0/query",
    "https://services.arcgis.com/5T5nSi527N4F7luB/arcgis/rest/services/GlobalLandslideCatalog/FeatureServer/0/query",
    "https://services5.arcgis.com/5T5nSi527N4F7luB/arcgis/rest/services/COOLR/FeatureServer/0/query",
]

params = {
    "where": "1=1",
    "geometry": f"{minx},{miny},{maxx},{maxy}",
    "geometryType": "esriGeometryEnvelope",
    "inSR": "4326",
    "spatialRel": "esriSpatialRelIntersects",
    "outFields": "*",
    "returnGeometry": "true",
    "f": "geojson",
    "outSR": "4326"
}

for url in urls:
    print(f"Trying: {url}")
    try:
        resp = requests.get(url, params=params, timeout=30)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            if "features" in data and len(data["features"]) > 0:
                count = len(data["features"])
                print(f"  SUCCESS: {count} features found!")
                outpath = "data/raw/landslide_inventory/nasa_glc_mizoram.geojson"
                with open(outpath, "w") as f:
                    json.dump(data, f, indent=2)
                print(f"  Saved to {outpath}")
                
                # Show fields
                fields = list(data["features"][0]["properties"].keys())
                print(f"  Fields: {fields}")
                
                # Show first 5 records
                for i, feat in enumerate(data["features"][:5]):
                    p = feat["properties"]
                    print(f"\n  Record {i+1}:")
                    for k, v in p.items():
                        print(f"    {k}: {v}")
                break
            elif "error" in data:
                print(f"  Error: {data['error']}")
            else:
                print(f"  No features. Keys: {list(data.keys())}")
        else:
            print(f"  HTTP Error: {resp.text[:200]}")
    except Exception as e:
        print(f"  Error: {e}")
else:
    print("\nAll ArcGIS Online URLs failed.")
    
    # Try a broader India search on the same endpoints
    print("\n\nTrying broader India search...")
    params2 = {
        "where": "country_name='India'",
        "outFields": "*",
        "returnGeometry": "true",
        "f": "geojson",
        "outSR": "4326"
    }
    for url in urls:
        print(f"Trying: {url}")
        try:
            resp = requests.get(url, params=params2, timeout=30)
            print(f"  Status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                if "features" in data:
                    count = len(data["features"])
                    print(f"  Features for India: {count}")
                    if count > 0:
                        outpath = "data/raw/landslide_inventory/nasa_glc_india.geojson"
                        with open(outpath, "w") as f:
                            json.dump(data, f, indent=2)
                        print(f"  Saved to {outpath}")
                        fields = list(data["features"][0]["properties"].keys())
                        print(f"  Fields: {fields}")
                        break
                elif "error" in data:
                    print(f"  Error: {data['error']}")
        except Exception as e:
            print(f"  Error: {e}")
