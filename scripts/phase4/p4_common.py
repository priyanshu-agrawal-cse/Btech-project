"""
Phase 4 — shared configuration and raster helpers.

Extends Phase 3 configuration with Phase 4 output paths, while keeping
the valid land mask and master grid references intact.
"""

import os
import sys

# Ensure scripts/phase3 is importable
_P3_SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "phase3"))
if _P3_SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _P3_SCRIPT_DIR)

from p3_common import (
    MASTER_DEM,
    BOUNDARY,
    NODATA,
    SEED,
    master_profile,
    grid_info,
    load_valid_mask,
    read_float,
    write_float,
    write_uint8,
    save_json,
    log,
)

# ---------------------------------------------------------------------------
# Phase 4 Paths & Overrides
# ---------------------------------------------------------------------------
P4_DIR     = "data/phase4"
FEAT_DIR   = f"{P4_DIR}/features"
INV_DIR    = f"{P4_DIR}/inventory"
MOD_DIR    = f"{P4_DIR}/modeling"
EDA_DIR    = f"{P4_DIR}/eda"
FIG_DIR    = f"{P4_DIR}/figures"
AUDIT_DIR  = f"{P4_DIR}/audit"
MAPS_DIR   = f"{P4_DIR}/maps"
LOGS_DIR   = f"{P4_DIR}/logs"
RESULTS_DIR= f"{MOD_DIR}/results"
MODELS_DIR = "models/phase4"

# VALID_MASK must keep pointing to data/phase3/features/valid_mask_30m.tif
VALID_MASK = "data/phase3/features/valid_mask_30m.tif"


def ensure_dirs():
    for d in (P4_DIR, FEAT_DIR, INV_DIR, MOD_DIR, EDA_DIR, FIG_DIR, AUDIT_DIR, MAPS_DIR, LOGS_DIR, RESULTS_DIR, MODELS_DIR):
        os.makedirs(d, exist_ok=True)
