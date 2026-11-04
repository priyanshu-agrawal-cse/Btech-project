"""
Phase 3 / Step 04 — Road and river proximity from OpenStreetMap (DATA-021).

Why: road cutting is the most frequently recorded trigger/setting of landslides
in Mizoram. In the GSI inventory at least 1,222 of the 2,041 Mizoram records name a road
section in NH_SH_LOCATION, ~20 % list an anthropogenic trigger and ~260 describe
"extensive slope cut". Phase 1/2 had no road layer at all.

Source : Geofabrik extract "India — North-Eastern Zone" of OpenStreetMap
         https://download.geofabrik.de/asia/india/north-eastern-zone-latest.osm.pbf
         (c) OpenStreetMap contributors, ODbL 1.0
Steps  : 1. download the PBF to data/raw/osm/ (kept untouched)
         2. pyosmium: keep ways with a vehicular highway=* class or waterway=river
            whose bounding box touches the padded study grid (master + 10 km)
         3. save the extracted vectors (EPSG:4326) as GeoPackages
         4. rasterise (all_touched) on the padded grid, Euclidean distance in metres,
            crop to the master grid, mask to land
Outputs: data/raw/osm/<pbf>, mizoram_osm_roads.gpkg, mizoram_osm_rivers.gpkg
         data/phase3/features/dist_road_major.tif  (motorway/trunk/primary/secondary)
         data/phase3/features/dist_road_any.tif    (all vehicular classes incl. tracks)
         data/phase3/features/road_density_1km.tif (approx. km of road per km2, 33x33 window)
         data/phase3/features/dist_river_osm.tif   (waterway=river)
         data/phase3/features/osm_summary.json
"""

import os
import sys
import json
import requests
import numpy as np
import rasterio
import geopandas as gpd
import osmium
from shapely.geometry import LineString
from rasterio.features import rasterize
from rasterio.warp import transform_bounds
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p3_common import FEAT_DIR, ensure_dirs, load_valid_mask, write_float, save_json, log

ensure_dirs()
RAW = "data/raw/osm"
os.makedirs(RAW, exist_ok=True)
URL = "https://download.geofabrik.de/asia/india/north-eastern-zone-latest.osm.pbf"
PADDED = "data/processed/mizoram_dem_utm46n_master_plus10km.tif"
M = 330

MAJOR = {"motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link",
         "secondary", "secondary_link"}
MINOR = {"tertiary", "tertiary_link", "unclassified", "residential", "service", "track",
         "living_street", "road", "construction"}
ROADS = MAJOR | MINOR

# ---- 1. download ----------------------------------------------------------------
# If the extracts saved on 2026-10-28 exist, they are re-used so that a re-run
# reproduces exactly the same features (Geofabrik "latest" changes every day).
ROADS_GPKG = os.path.join(RAW, "mizoram_osm_roads.gpkg")
RIVERS_GPKG = os.path.join(RAW, "mizoram_osm_rivers.gpkg")
REUSE = os.path.exists(ROADS_GPKG) and os.path.exists(RIVERS_GPKG)
if REUSE:
    real_url = "https://download.geofabrik.de/asia/india/north-eastern-zone-261027.osm.pbf"
    log(f"Re-using saved extracts {ROADS_GPKG} and {RIVERS_GPKG} (from {real_url})")
else:
    head = requests.head(URL, allow_redirects=False, timeout=30)
    real_url = head.headers.get("Location", URL)
    if real_url.startswith("/"):
        real_url = "https://download.geofabrik.de" + real_url
pbf = os.path.join(RAW, os.path.basename(real_url))
if not REUSE and not os.path.exists(pbf):
    log(f"Downloading {real_url}")
    with requests.get(real_url, stream=True, timeout=600) as r:
        r.raise_for_status()
        with open(pbf + ".part", "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    os.replace(pbf + ".part", pbf)
if not REUSE:
    log(f"PBF: {pbf} ({os.path.getsize(pbf) / 1e6:.1f} MB)")

# ---- 2. extract ways ---------------------------------------------------------------
with rasterio.open(PADDED) as src:
    ptr, pcrs, PH, PW = src.transform, src.crs, src.height, src.width
    pb = src.bounds
lon0, lat0, lon1, lat1 = transform_bounds(pcrs, "EPSG:4326", *pb, densify_pts=21)
log(f"Padded grid bbox (lon/lat): {lon0:.3f} {lat0:.3f} {lon1:.3f} {lat1:.3f}")


class Collector(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.roads, self.rivers = [], []

    def way(self, w):
        hw = w.tags.get("highway")
        ww = w.tags.get("waterway")
        if hw not in ROADS and ww != "river":
            return
        try:
            pts = [(n.lon, n.lat) for n in w.nodes]
        except osmium.InvalidLocationError:
            return
        if len(pts) < 2:
            return
        xs, ys = zip(*pts)
        if max(xs) < lon0 or min(xs) > lon1 or max(ys) < lat0 or min(ys) > lat1:
            return
        rec = {"osm_id": w.id, "name": w.tags.get("name"), "geometry": LineString(pts)}
        if hw in ROADS:
            rec.update(highway=hw, ref=w.tags.get("ref"), surface=w.tags.get("surface"),
                       road_class="major" if hw in MAJOR else "minor")
            self.roads.append(rec)
        if ww == "river":
            self.rivers.append(rec)


if REUSE:
    roads = gpd.read_file(ROADS_GPKG)
    rivers = gpd.read_file(RIVERS_GPKG)
else:
    h = Collector()
    h.apply_file(pbf, locations=True, idx="flex_mem")
    roads = gpd.GeoDataFrame(h.roads, crs="EPSG:4326")
    rivers = gpd.GeoDataFrame(h.rivers, crs="EPSG:4326")
    roads.to_file(ROADS_GPKG, driver="GPKG")
    rivers.to_file(RIVERS_GPKG, driver="GPKG")
log(f"Extracted {len(roads):,} road ways and {len(rivers):,} river ways")

# ---- 3. rasterise + distance --------------------------------------------------------
valid = load_valid_mask()
H, W = valid.shape
L = abs(ptr[0])
roads_u = roads.to_crs(pcrs)
rivers_u = rivers.to_crs(pcrs)
bnd = gpd.read_file("data/raw/mizoram_boundary.geojson").to_crs(pcrs).union_all()


def burn(gdf):
    if len(gdf) == 0:
        return np.zeros((PH, PW), bool)
    return rasterize(((g, 1) for g in gdf.geometry), out_shape=(PH, PW), transform=ptr,
                     fill=0, dtype="uint8", all_touched=True).astype(bool)


def dist_layer(mask, name):
    d = ndimage.distance_transform_edt(~mask, sampling=(L, L))[M:M + H, M:M + W]
    write_float(f"{FEAT_DIR}/{name}.tif", d.astype("float32"), valid)
    v = d[valid]
    log(f"  {name:16s} min={v.min():8.1f} median={np.median(v):8.1f} mean={v.mean():8.1f} max={v.max():9.1f} m")
    return {"min": float(v.min()), "median": float(np.median(v)), "mean": float(v.mean()), "max": float(v.max())}


summary = {"pbf": os.path.basename(pbf), "pbf_url": real_url,
           "road_ways": int(len(roads)), "river_ways": int(len(rivers))}
inside = roads_u.clip(bnd)
summary["road_km_inside_state_by_class"] = (inside.length.groupby(inside.highway).sum() / 1000).round(1).to_dict()
summary["road_km_inside_state_total"] = float(round(inside.length.sum() / 1000, 1))
log(f"  road length inside Mizoram: {summary['road_km_inside_state_total']:,} km")

any_mask = burn(roads_u)
summary["dist_road_any"] = dist_layer(any_mask, "dist_road_any")
summary["dist_road_major"] = dist_layer(burn(roads_u[roads_u.road_class == "major"]), "dist_road_major")
dens = ndimage.uniform_filter(any_mask.astype("float32"), size=33, mode="nearest")
dens = dens * (1000.0 / L)          # fraction of road cells -> approx. km per km2
write_float(f"{FEAT_DIR}/road_density_1km.tif", dens[M:M + H, M:M + W], valid)
del any_mask, dens
summary["dist_river_osm"] = dist_layer(burn(rivers_u), "dist_river_osm")
save_json(summary, f"{FEAT_DIR}/osm_summary.json")
log("OSM features complete.")
