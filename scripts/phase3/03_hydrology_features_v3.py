"""
Phase 3 / Step 03 — Hydrological features from real flow routing (DATA-020).

Replaces the Phase 2 "TWI" (01b_derive_advanced_features.py), which used
sca = cell_area / tan(b) and was therefore a monotonic function of slope
(Spearman rho = -1.0, audit DATA-017 D). Here the upslope contributing area
comes from flow routing over the hydrologically-conditioned DEM.

Tool: WhiteboxTools v2.4.0 (Lindsay, 2016) through the `whitebox` Python package.
All routing runs on the padded DEM (master grid + 10 km, step 02a) so that
catchments crossing the state border keep their real upstream area.

  1. BreachDepressionsLeastCost (Lindsay & Dhun 2015; dist=100 cells, fill=True)
  2. D-infinity flow accumulation, specific contributing area SCA [m2/m]
     (Tarboton 1997)
       TWI     = ln( SCA / tan b )           (Beven & Kirkby 1979), tan b >= 0.001
       SPI_log = ln( 1 + SCA * tan b )       (Moore et al. 1991)
  3. D8 pointer + D8 flow accumulation [cells]; stream network = cells with a
     contributing area >= 1 km^2 (1,089 cells of 918.5 m^2)
       dist_stream = Euclidean distance to the nearest stream cell [m]
       hand        = ElevationAboveStream (height above nearest drainage) [m]

Outputs (master grid, NoData -9999 outside the state): data/phase3/features/
   twi.tif, spi_log.tif, dist_stream.tif, hand.tif, streams_1km2.tif (uint8)
Intermediates: data/phase3/work/hydro/ (not needed after this step)
"""

import os
import sys
import gc
import numpy as np
import rasterio
from scipy import ndimage
import whitebox

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p3_common import (FEAT_DIR, P3_DIR, ensure_dirs, load_valid_mask, read_float,
                       write_float, write_uint8, log)

ensure_dirs()
WORK = os.path.abspath(f"{P3_DIR}/work/hydro")
os.makedirs(WORK, exist_ok=True)
PADDED = os.path.abspath("data/processed/mizoram_dem_utm46n_master_plus10km.tif")
M = 330
STREAM_AREA_M2 = 1.0e6

valid = load_valid_mask()
H, W = valid.shape
with rasterio.open(PADDED) as src:
    L = abs(src.transform[0])
cell_area = L * L
stream_cells = int(round(STREAM_AREA_M2 / cell_area))
log(f"Cell {L:.4f} m ({cell_area:.1f} m2); stream threshold = {stream_cells} cells (1 km2)")

wbt = whitebox.WhiteboxTools()
wbt.set_verbose_mode(False)
wbt.set_max_procs(int(os.environ.get("P3_NJOBS", "3")))
wbt.set_working_dir(WORK)


def run(tool, *a, output=None, **k):
    """Run a WBT tool and verify its output file exists.
    Attempt 1 (2026-10-28) showed the `whitebox` wrapper returns 0 even when the
    Rust binary panics, so the return code alone cannot be trusted."""
    ret = getattr(wbt, tool)(*a, **k)
    out = output or (a[-1] if a else None)
    if ret != 0 or (out and not os.path.exists(os.path.join(WORK, out))):
        raise RuntimeError(f"WhiteboxTools {tool} failed (code {ret}, output {out} missing)")
    log(f"  WBT {tool}: OK -> {out}")


def crop(a):
    return a[M:M + H, M:M + W]


def read_padded(name):
    with rasterio.open(os.path.join(WORK, name)) as s:
        a = s.read(1).astype("float64")
        nd = s.nodata
    if nd is not None:
        a[a == nd] = np.nan
    return a


# 0. WhiteboxTools cannot read GeoTIFFs written with the floating-point predictor
#    (PREDICTOR=3, used by 02a). Attempt 1 failed with:
#    "The GeoTIFF reader does not currently support floating-point predictors".
#    -> write an uncompressed working copy for WBT.
WBT_DEM = "dem_padded_uncompressed.tif"
with rasterio.open(PADDED) as src:
    prof = src.profile.copy()
    prof.update(compress=None, predictor=None, tiled=False, nodata=-9999.0)
    prof.pop("blockxsize", None); prof.pop("blockysize", None)
    with rasterio.open(os.path.join(WORK, WBT_DEM), "w", **prof) as dst:
        dst.write(src.read(1), 1)
log(f"  wrote {WBT_DEM} (uncompressed copy for WhiteboxTools)")

# 1. hydrological conditioning --------------------------------------------------
#    Attempt 2 used BreachDepressionsLeastCost (dist=100, fill=True). It is
#    single-threaded and had not finished after ~15 min on the 46.6 M-cell padded
#    DSM, so it was stopped. Attempt 3 (default) uses FillDepressions
#    (Wang & Liu 2006 priority-flood) with flat fixing. The output keeps the name
#    dem_breached.tif so the rest of the chain is unchanged.
CONDITION = os.environ.get("P3_HYDRO_CONDITION", "fill")
if CONDITION == "breach_lc":
    run("breach_depressions_least_cost", WBT_DEM, "dem_breached.tif", dist=100, fill=True)
else:
    run("fill_depressions", WBT_DEM, "dem_breached.tif", fix_flats=True)
log(f"  conditioning method: {CONDITION}")

# 2. D-infinity specific contributing area ---------------------------------------
run("d_inf_flow_accumulation", "dem_breached.tif", "dinf_sca.tif", out_type="sca")

# 3. D8 network ------------------------------------------------------------------
run("d8_pointer", "dem_breached.tif", "d8_pntr.tif")
run("d8_flow_accumulation", "d8_pntr.tif", "d8_cells.tif", out_type="cells", pntr=True)
run("extract_streams", "d8_cells.tif", "streams.tif", threshold=stream_cells, zero_background=True)
run("elevation_above_stream", "dem_breached.tif", "streams.tif", "hand.tif")

# ---- TWI / SPI on the master grid -------------------------------------------------
slope = read_float(f"{FEAT_DIR}/slope.tif", valid)            # degrees, from step 02
tanb = np.maximum(np.tan(np.radians(slope.astype("float64"))), 0.001)
sca = crop(read_padded("dinf_sca.tif"))
sca = np.maximum(sca, L)                                         # at least one cell width
twi = np.log(sca / tanb)
spi = np.log1p(sca * tanb)
write_float(f"{FEAT_DIR}/twi.tif", twi.astype("float32"), valid)
write_float(f"{FEAT_DIR}/spi_log.tif", spi.astype("float32"), valid)
v = twi[valid & np.isfinite(twi)]
log(f"  twi      min={v.min():.3f} mean={v.mean():.3f} max={v.max():.3f}")
v = spi[valid & np.isfinite(spi)]
log(f"  spi_log  min={v.min():.3f} mean={v.mean():.3f} max={v.max():.3f}")
del sca, twi, spi, v, tanb
gc.collect()

# ---- distance to stream (computed on padded grid, then cropped) --------------------
streams = read_padded("streams.tif")
is_stream = np.nan_to_num(streams, nan=0) > 0
log(f"  stream cells (padded grid) = {int(is_stream.sum()):,}")
dist = ndimage.distance_transform_edt(~is_stream, sampling=(L, L))
write_float(f"{FEAT_DIR}/dist_stream.tif", crop(dist).astype("float32"), valid)
st = np.where(valid, crop(is_stream).astype("uint8"), 255)
write_uint8(f"{FEAT_DIR}/streams_1km2.tif", st)
v = crop(dist)[valid]
log(f"  dist_stream min={v.min():.1f} mean={v.mean():.1f} max={v.max():.1f} m;"
    f" stream cells inside state = {int((st == 1).sum()):,}")
del streams, is_stream, dist, st, v
gc.collect()

# ---- HAND ----------------------------------------------------------------------------
hand = crop(read_padded("hand.tif"))
write_float(f"{FEAT_DIR}/hand.tif", hand.astype("float32"), valid)
v = hand[valid & np.isfinite(hand)]
log(f"  hand     min={v.min():.2f} mean={v.mean():.2f} max={v.max():.2f} m")
log("Hydrology features complete.")
