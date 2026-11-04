"""
Inspect raw WFS capabilities XML to find the actual layer names.
The previous script found 0 layers because the XML namespace wasn't handled.
Also try alternate Bhuvan OGC endpoints.
"""

import requests
import re
import json
import os
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

os.makedirs("data/raw/landslide_inventory", exist_ok=True)

minx, miny, maxx, maxy = 92.15, 21.94, 93.44, 24.52

# ============================================================
# STEP 1: Inspect Bhuvan WFS raw XML
# ============================================================
print("=" * 60)
print("STEP 1: Bhuvan WFS - Raw XML inspection")
print("=" * 60)

wfs_url = "https://bhuvan-vec2.nrsc.gov.in/bhuvan/wfs"
try:
    resp = requests.get(wfs_url, params={
        "service": "WFS", "version": "1.1.0", "request": "GetCapabilities"
    }, timeout=20)
    
    if resp.status_code == 200:
        text = resp.text
        # Save raw XML for inspection
        with open("data/raw/landslide_inventory/bhuvan_wfs_capabilities.xml", "w", encoding="utf-8") as f:
            f.write(text)
        print(f"Saved raw XML ({len(text)} chars)")
        
        # Try namespace-aware pattern
        names = re.findall(r'[<:]Name[^>]*>([^<]+)</', text)
        print(f"Found {len(names)} layer names (namespace-aware)")
        
        # Filter for relevant layers
        geo_keywords = ['geo', 'fault', 'litho', 'lulc', 'land', 'soil', 'slope', 
                       'hazard', 'risk', 'slide', 'disaster', 'mizoram', 'northeast']
        relevant = [n for n in names if any(k in n.lower() for k in geo_keywords)]
        print(f"Geologically relevant: {relevant[:30]}")
        
        if not relevant:
            # Print first 50 unique names to understand what's available
            unique_names = list(dict.fromkeys(names))
            print(f"\nAll unique names ({len(unique_names)} total):")
            for n in unique_names[:50]:
                print(f"  - {n}")
            
            # Also print last 500 chars of XML to see structure
            print(f"\nLast 1000 chars of XML:")
            print(text[-1000:])
except Exception as e:
    print(f"Error: {e}")

# ============================================================
# STEP 2: Try Bhuvan OWS and other OGC endpoints
# ============================================================
print("\n" + "=" * 60)
print("STEP 2: Bhuvan alternate OGC endpoints")
print("=" * 60)

alt_endpoints = [
    "https://bhuvan-vec2.nrsc.gov.in/bhuvan/ows",
    "https://bhuvan-vec2.nrsc.gov.in/bhuvan/wms",
    "https://bhuvan-app1.nrsc.gov.in/geoserver/wfs",
    "https://bhuvan-app1.nrsc.gov.in/geoserver/ows",
    "https://bhuvan-ras2.nrsc.gov.in/bhuvan/wms",
]

for url in alt_endpoints:
    print(f"\nTrying: {url}")
    try:
        resp = requests.get(url, params={
            "service": "WFS", "version": "1.1.0", "request": "GetCapabilities"
        }, timeout=15)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200 and len(resp.text) > 500:
            names = re.findall(r'[<:]Name[^>]*>([^<]+)</', resp.text)
            relevant = [n for n in names if any(k in n.lower() for k in geo_keywords)]
            print(f"  Layers found: {len(names)}, Relevant: {len(relevant)}")
            if relevant:
                print(f"  Relevant layers: {relevant[:20]}")
            elif names:
                print(f"  First 10: {names[:10]}")
    except Exception as e:
        print(f"  Error: {e}")

# ============================================================
# STEP 3: Try NESDR raw XML
# ============================================================
print("\n" + "=" * 60)
print("STEP 3: NESDR raw XML inspection")
print("=" * 60)

try:
    resp = requests.get("https://nesdr.gov.in/geoserver/wfs", params={
        "service": "WFS", "version": "1.1.0", "request": "GetCapabilities"
    }, timeout=20, verify=False)
    
    if resp.status_code == 200:
        text = resp.text
        with open("data/raw/landslide_inventory/nesdr_wfs_capabilities.xml", "w", encoding="utf-8") as f:
            f.write(text)
        print(f"Saved raw XML ({len(text)} chars)")
        
        names = re.findall(r'[<:]Name[^>]*>([^<]+)</', text)
        print(f"Found {len(names)} layer names")
        relevant = [n for n in names if any(k in n.lower() for k in geo_keywords)]
        print(f"Geologically relevant: {relevant[:30]}")
        if not relevant and names:
            unique_names = list(dict.fromkeys(names))
            print(f"First 50: ")
            for n in unique_names[:50]:
                print(f"  - {n}")
except Exception as e:
    print(f"Error: {e}")

# ============================================================
# STEP 4: Try NASA COOLR CSV download (alternate approach)
# ============================================================
print("\n" + "=" * 60)
print("STEP 4: NASA COOLR CSV (alternate download)")
print("=" * 60)

# The NASA GLC data is also available as a CSV on their data page
csv_urls = [
    "https://data.nasa.gov/api/views/dd9e-wu2v/rows.csv?accessType=DOWNLOAD",
]
for csv_url in csv_urls:
    print(f"Trying CSV download: {csv_url}")
    try:
        resp = requests.get(csv_url, timeout=30, stream=True)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            outpath = "data/raw/landslide_inventory/nasa_glc_full.csv"
            with open(outpath, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"  SUCCESS: Saved to {outpath}")
            
            # Quick inspection
            import csv
            with open(outpath, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f)
                headers = next(reader)
                print(f"  Columns: {headers}")
                
                # Count Mizoram/northeast India rows
                mizoram_rows = []
                for row in reader:
                    row_text = " ".join(row).lower()
                    if "mizoram" in row_text:
                        mizoram_rows.append(row)
                
                print(f"  Rows mentioning 'Mizoram': {len(mizoram_rows)}")
                if mizoram_rows:
                    print(f"  First 3 Mizoram rows:")
                    for r in mizoram_rows[:3]:
                        print(f"    {dict(zip(headers, r))}")
        else:
            print(f"  Failed: {resp.text[:300]}")
    except Exception as e:
        print(f"  Error: {e}")

print("\n" + "=" * 60)
print("DONE.")
print("=" * 60)
