import urllib.request
import urllib.parse
import json
import os

# Create data directories
os.makedirs("data/raw", exist_ok=True)
os.makedirs("data/processed", exist_ok=True)
os.makedirs("data/derived", exist_ok=True)
os.makedirs("scripts/download", exist_ok=True)

print("Fetching Mizoram boundary from Nominatim API...")

# Nominatim API endpoint with User-Agent header (required by Nominatim)
url = "https://nominatim.openstreetmap.org/search?state=Mizoram&country=India&format=json&polygon_geojson=1"
req = urllib.request.Request(url, headers={'User-Agent': 'MizoramLandslideResearchProject/1.0'})

try:
    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode('utf-8'))
        
    if not result:
        print("Error: No data returned from Nominatim.")
        exit(1)
        
    # The first result is usually the best match
    best_match = result[0]
    geojson_geom = best_match.get('geojson')
    
    if not geojson_geom:
        print("Error: No GeoJSON geometry found in the response.")
        exit(1)
        
    # Wrap it in a FeatureCollection
    feature_collection = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "name": "Mizoram",
                    "admin_level": "4",
                    "source": "OpenStreetMap Nominatim"
                },
                "geometry": geojson_geom
            }
        ]
    }
    
    output_path = "data/raw/mizoram_boundary.geojson"
    with open(output_path, "w") as f:
        json.dump(feature_collection, f, indent=2)
        
    print(f"SUCCESS: Mizoram boundary saved to {output_path}")
    
except Exception as e:
    print(f"Error during API request: {e}")
    exit(1)
