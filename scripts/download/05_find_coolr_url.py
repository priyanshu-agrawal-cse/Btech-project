"""
Inspect NASA Landslide Viewer HTML and linked JS for ArcGIS service URLs.
"""
import requests
import re

print("Fetching NASA Landslide Viewer page...")
resp = requests.get("https://landslides.nasa.gov", timeout=15)
if resp.status_code != 200:
    print(f"Failed: {resp.status_code}")
    exit(1)

html = resp.text

# Find all script sources
js_files = re.findall(r'src="([^"]+)"', html)
js_files = [f for f in js_files if ".js" in f]
print(f"Found {len(js_files)} JS file references")
for js in js_files:
    print(f"  {js}")

# Check for iframes
iframes = re.findall(r'<iframe[^>]*src="([^"]+)"', html, re.IGNORECASE)
print(f"\nIframes: {iframes}")

# Check for ArcGIS references anywhere
arcgis = re.findall(r'(https?://[^"\s]*arcgis[^"\s]*)', html)
print(f"\nArcGIS references: {sorted(set(arcgis))}")

# Check for embedded JSON configs containing URLs
urls_in_page = re.findall(r'(https?://[^"\s<>]+)', html)
service_urls = [u for u in urls_in_page if any(kw in u.lower() for kw in 
    ["featureserver", "mapserver", "landslide", "coolr", "glc"])]
print(f"\nService/landslide URLs: {sorted(set(service_urls))}")

# Also fetch the HTML and look for the actual viewer app URL
experience = re.findall(r'(https?://[^"\s]*experience[^"\s]*)', html, re.IGNORECASE)
dashboard = re.findall(r'(https?://[^"\s]*dashboard[^"\s]*)', html, re.IGNORECASE)
webapp = re.findall(r'(https?://[^"\s]*webapp[^"\s]*)', html, re.IGNORECASE)
print(f"\nExperience URLs: {experience}")
print(f"Dashboard URLs: {dashboard}")
print(f"WebApp URLs: {webapp}")

# Try to find any download-related content
download_refs = re.findall(r'(?:download|export|csv|shapefile)[^<"]*', html, re.IGNORECASE)
print(f"\nDownload references: {download_refs[:10]}")
