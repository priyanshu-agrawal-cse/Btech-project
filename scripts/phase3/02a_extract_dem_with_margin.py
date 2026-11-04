"""
Phase 3 / Step 02a — Cut the master grid + 10 km margin out of the UNCLIPPED DEM.

Why: the master DEM (data/derived/mizoram_dem_clipped_utm.tif) stores the area
outside Mizoram as 0.0 m. Any moving-window derivative (slope, TRI, TPI,
curvature) or flow routing computed on it sees an artificial 0 m -> 600 m cliff
along the whole state border, and rivers entering from Myanmar lose their
upstream catchment. The Phase 1 unclipped reprojected DEM
(data/processed/mizoram_dem_utm46n.tif) holds the real terrain around the state
on exactly the same pixel lattice (master grid = integer offset col 943,
row 1754; values identical inside the state, verified on 2026-10-28).

Output: data/processed/mizoram_dem_utm46n_master_plus10km.tif
        (4,619 x 10,097 px, master grid padded by MARGIN_PX on every side)
"""

import rasterio
from rasterio.windows import Window

SRC = "data/processed/mizoram_dem_utm46n.tif"
MASTER = "data/derived/mizoram_dem_clipped_utm.tif"
OUT = "data/processed/mizoram_dem_utm46n_master_plus10km.tif"
MARGIN_PX = 330  # 330 x 30.3068 m = 10.0 km

with rasterio.open(SRC) as a, rasterio.open(MASTER) as m:
    col_off = round((m.transform.c - a.transform.c) / a.transform.a)
    row_off = round((m.transform.f - a.transform.f) / a.transform.e)
    w = Window(col_off - MARGIN_PX, row_off - MARGIN_PX,
               m.width + 2 * MARGIN_PX, m.height + 2 * MARGIN_PX)
    arr = a.read(1, window=w)
    prof = a.profile.copy()
    prof.update(width=arr.shape[1], height=arr.shape[0], transform=a.window_transform(w),
                compress="deflate", predictor=3, zlevel=6, tiled=True,
                blockxsize=512, blockysize=512)
print(f"master offset in unclipped DEM: col={col_off}, row={row_off}; window={w}")
print(f"min elevation in window = {arr.min():.2f} m (no 0 m fill)")
with rasterio.open(OUT, "w", **prof) as dst:
    dst.write(arr, 1)
print(f"Saved {OUT}")
