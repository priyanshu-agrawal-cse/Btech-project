"""
Rasterize Expanded Landslide Inventory onto Master Grid

This script takes the combined multi-source landslide GeoJSON and burns it
onto the 30m master grid. It creates TWO target rasters:

1. mizoram_landslide_target_expanded_30m.tif
   - Same format as original (1 = landslide, 0 = no landslide)
   - But sourced from ALL years and ALL sources (much more events)

2. mizoram_landslide_target_ne_india_30m.tif
   - Extended target including neighbouring state events
   - Used for transfer-learning / spatial CV experiments

The script also prints a diagnostic count of how many pixels are
labelled positive in each version so you can compare with original 41.

WHY POLYGON BUFFERING?
======================
Point data (COOLR, EONET) places an event at a single GPS coordinate.
At 30m resolution, one landslide point = 1 pixel = 900 m2.

In reality, most landslides affect hundreds to thousands of square metres.
We apply a 90m buffer (3 pixels) around each point location based on
typical Mizoram landslide runout distances documented in GSI reports.
This creates a 7-pixel landslide 'footprint' instead of 1 pixel,
better matching the actual disturbed area.

For GSI polygon data, we use the actual polygon geometry directly.
"""

import os
import json
import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.transform import from_bounds
from shapely.geometry import shape, mapping, Point, MultiPoint
from shapely.ops import unary_union
import warnings
warnings.filterwarnings("ignore")

os.makedirs("data/processed/inventory", exist_ok=True)

# ---- Reference grid from existing master DEM ----------------------------
MASTER_DEM = "data/derived/mizoram_dem_clipped_utm.tif"
NODATA     = 255

BUFFER_M   = 90   # 90m buffer around point events (= 3 pixels at 30m)

# Input inventories
NE_GEOJSON  = "data/raw/landslide_inventory/combined_ne_india_landslides.geojson"
MIZ_GEOJSON = "data/raw/landslide_inventory/combined_mizoram_landslides.geojson"

# Fall back to original COOLR if combined not yet downloaded
FALLBACK    = "data/raw/landslide_inventory/mizoram_landslides_coolr.geojson"

def load_geojson(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8", errors="replace") as f:
        data = json.load(f)
    return data.get("features", [])


# ===========================================================================
print("=" * 65)
print("STEP 1 — Loading master grid metadata")
print("=" * 65)

with rasterio.open(MASTER_DEM) as src:
    dem_crs    = src.crs
    dem_meta   = src.meta.copy()
    dem_trans  = src.transform
    dem_nodata = src.nodata if src.nodata is not None else -9999.0
    height, width = src.height, src.width
    bounds = src.bounds

print(f"  CRS    : {dem_crs}")
print(f"  Size   : {width} x {height} pixels")
print(f"  Bounds : {bounds}")
print(f"  Pixel  : {dem_trans[0]:.1f}m x {abs(dem_trans[4]):.1f}m")

pixel_size_m = abs(dem_trans[0])   # e.g. 30.0
buffer_px    = max(1, round(BUFFER_M / pixel_size_m))
print(f"  Buffer : {BUFFER_M}m = {buffer_px} pixels")


# ===========================================================================
print("\nSTEP 2 — Projecting inventory to UTM")
print("=" * 65)

from pyproj import Transformer
transformer = Transformer.from_crs("EPSG:4326", str(dem_crs), always_xy=True)

def project_feature(feat):
    """Project a GeoJSON feature from WGS84 to the DEM CRS."""
    geom = shape(feat.get("geometry", {}))
    if geom is None or geom.is_empty:
        return None
    try:
        from shapely.ops import transform as shp_transform
        projected = shp_transform(transformer.transform, geom)
        return projected
    except Exception:
        return None

def burn_features(features_geojson, raster_shape, transform, buffer_m=0):
    """
    Convert GeoJSON features to a binary numpy array burned onto the raster grid.
    Points are buffered by buffer_m metres. Polygons are used directly.
    Returns a uint8 array with 1 = landslide, 0 = background.
    """
    shapes_to_burn = []
    
    for feat in features_geojson:
        geom = project_feature(feat)
        if geom is None:
            continue
        
        if geom.geom_type == "Point":
            if buffer_m > 0:
                geom = geom.buffer(buffer_m)
        elif geom.geom_type == "MultiPoint":
            geom = geom.buffer(buffer_m)
        # Polygon/MultiPolygon are used as-is
        
        if not geom.is_empty:
            shapes_to_burn.append((mapping(geom), 1))
    
    if not shapes_to_burn:
        return np.zeros(raster_shape, dtype=np.uint8)
    
    burned = rasterize(
        shapes_to_burn,
        out_shape=raster_shape,
        transform=transform,
        fill=0,
        dtype=np.uint8,
        all_touched=True,   # include pixels touched by polygon edge
    )
    return burned


# ===========================================================================
print("\nSTEP 3 — Building rasters for each inventory version")
print("=" * 65)

out_meta = dem_meta.copy()
out_meta.update({
    "dtype": "uint8",
    "nodata": NODATA,
    "compress": "lzw",
    "count": 1,
})


def make_raster(geojson_path, fallback_path, out_path, label, buffer_m=BUFFER_M):
    feats = load_geojson(geojson_path)
    if not feats:
        print(f"  No features in {geojson_path}, trying fallback...")
        feats = load_geojson(fallback_path)
    
    if not feats:
        print(f"  ERROR: No features found for {label}")
        return 0
    
    print(f"  Burning {len(feats)} features for [{label}]...")
    burned = burn_features(feats, (height, width), dem_trans, buffer_m=buffer_m)
    
    # Apply DEM nodata mask
    with rasterio.open(MASTER_DEM) as src:
        dem = src.read(1)
    invalid = (dem == dem_nodata) | np.isnan(dem.astype(float))
    burned[invalid] = NODATA
    
    ls_px = int((burned == 1).sum())
    print(f"  Landslide pixels (value=1): {ls_px:,}")
    print(f"  Saving -> {out_path}")
    
    with rasterio.open(out_path, "w", **out_meta) as dst:
        dst.write(burned, 1)
    
    return ls_px


# A: Mizoram only (strict spatial filter)
miz_out = "data/processed/inventory/mizoram_landslide_target_expanded_30m.tif"
n_miz = make_raster(MIZ_GEOJSON, FALLBACK, miz_out, "Mizoram_Expanded")

# B: No buffer version (for comparison with original 41 pixels)
miz_nobuf_out = "data/processed/inventory/mizoram_landslide_target_nobuffer_30m.tif"
n_nobuf = make_raster(MIZ_GEOJSON, FALLBACK, miz_nobuf_out, "Mizoram_NoBuffer", buffer_m=0)

print(f"\nOriginal pipeline pixel count  : 41")
print(f"New (no buffer, Mizoram only)  : {n_nobuf}")
print(f"New (90m buffer, Mizoram only) : {n_miz}")


# ===========================================================================
print("\nSTEP 4 — Year-wise breakdown of collected events")
print("=" * 65)

all_feats = load_geojson(MIZ_GEOJSON)
if not all_feats:
    all_feats = load_geojson(FALLBACK)

from collections import Counter
years = []
sources = []
for feat in all_feats:
    p = feat.get("properties", {})
    date_str = (p.get("event_date", "") or p.get("Date", "") or "")
    try:
        years.append(str(date_str)[:4])
    except Exception:
        years.append("unknown")
    sources.append(p.get("_source", p.get("source", "unknown")))

print("Year distribution:")
for y, cnt in sorted(Counter(years).items()):
    print(f"  {y}: {cnt}")

print("\nSource distribution:")
for s, cnt in Counter(sources).most_common():
    print(f"  {s}: {cnt}")

print("\nRasterization complete!")
print(f"Use '{miz_out}' as the target_file in 01c_prepare_improved_dataset.py")
