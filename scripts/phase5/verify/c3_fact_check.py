"""
Phase 5 verification / C3 - check FINAL_REPORT.md facts against the source files (DATA-044).

Read-only. Output: data/phase5/verification/c3_fact_check.txt
"""

import glob
import json
import os
import re
import sys

import numpy as np
import pandas as pd
import rasterio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "phase3")))
from p3_common import grid_info, load_valid_mask, read_float

pd.set_option("display.width", 170, "display.max_columns", 30, "display.max_rows", 60)
OUT = "data/phase5/verification/c3_fact_check.txt"
L = []


def say(s=""):
    t = str(s).encode("ascii", "replace").decode()
    print(t)
    L.append(t)


tr, crs, H, W, px = grid_info()
valid = load_valid_mask()
say(f"GRID rows {H} cols {W} px {px:.4f}; land cells {int(valid.sum()):,}; land km2 {valid.sum() * px * px / 1e6:,.1f}")
rows, cols = np.nonzero(valid)
from pyproj import Transformer
t = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
xs = tr.c + np.array([cols.min(), cols.max() + 1]) * tr.a
ys = tr.f + np.array([rows.max() + 1, rows.min()]) * tr.e
say(f"land bounds lon/lat: {[round(float(v), 3) for v in t.transform(xs, ys)[0]]} {[round(float(v), 3) for v in t.transform(xs, ys)[1]]}")
for n, p in (("elevation", "data/phase3/features/elevation.tif"), ("slope", "data/phase3/features/slope.tif"),
             ("MAP", "data/processed/rainfall/mean_annual_precip_30m.tif"), ("max_precip", "data/processed/rainfall/max_monthly_precip_30m.tif"),
             ("dist_fault", "data/processed/geology/mizoram_distance_to_faults_30m.tif")):
    a = read_float(p, valid)[valid]
    say(f"{n}: min {np.nanmin(a):.1f} max {np.nanmax(a):.1f} mean {np.nanmean(a):.1f} sd {np.nanstd(a):.1f}")
    del a

say("\nUNIVARIATE AUC (top)")
u = pd.read_csv("data/phase3/eda/univariate_auc.csv")
say(u.head(10).to_string(index=False))
v = pd.read_csv("data/phase3/eda/vif.csv")
say("\nVIF top: " + v.sort_values(v.columns[1], ascending=False).head(3).to_string(index=False))

say("\nTUNED SUMMARY (real)")
s = pd.read_csv("data/phase4/modeling/results/tuned_baselines_v2_summary.csv")
say(s[["model", "ROC_AUC_mean", "PR_AUC_mean", "F1_macro_mean", "F1_LS_mean", "MCC_mean"]].to_string(index=False))
say("PHASE 3 SUMMARY")
s3 = pd.read_csv("data/phase3/modeling/results/nested_metrics_summary.csv")
say(s3[["model", "ROC_AUC_mean", "PR_AUC_mean", "F1_macro_mean", "F1_LS_mean", "MCC_mean"]].to_string(index=False))
say("BOOTSTRAP CI (real, Phase 3 only)")
say(pd.read_csv("data/phase3/modeling/results/pooled_auc_block_bootstrap.csv").to_string(index=False))

say("\nREPEATED CV max SD: " + str(pd.read_csv("data/phase3/modeling/results/repeated_spatial_cv.csv").groupby("config").ROC_AUC.std().round(4).to_dict()))

say("\nV5 PARAMS: " + json.dumps(json.load(open("models/phase5/feature_list_natural_v5.json"))["params"]))
say("V5 IMPORTANCE\n" + pd.read_csv("data/phase5/modeling/results/natural_v5_feature_importance.csv").head(10).to_string(index=False))
n = pd.read_csv("data/phase5/modeling/results/natural_v5_nested_metrics.csv")
say("V5 NESTED means: " + n[["ROC_AUC", "PR_AUC", "F1_macro", "MCC"]].mean().round(4).to_string().replace("\n", "; "))

say("\nFILES")
fc = "data/phase3/inventory/inventory_fact_check.json"
say(f"{fc} exists {os.path.exists(fc)}")
if os.path.exists(fc):
    say(open(fc, encoding="utf-8").read()[:900])
say("DEM tiles: " + str(sorted(glob.glob("data/raw/dem/**/*.tif", recursive=True))[:12]))
say("boundary shp: " + str(os.path.exists("data/processed/boundary/mizoram_boundary_utm.shp")))
for f in sorted(glob.glob("data/raw/osm/*")):
    say(f"osm: {f} {os.path.getsize(f)}")
for j in glob.glob("data/phase3/features/*summary*.json") + glob.glob("data/phase3/inventory/*summary*.json"):
    say(f"{j}: {open(j, encoding='utf-8').read()[:500]}")

say("\nCITED PATHS IN FINAL_REPORT.md THAT DO NOT EXIST")
txt = open("documentation/FINAL_REPORT.md", encoding="utf-8").read()
links = set(re.findall(r"file:///c:/Users/priya/OneDrive/Desktop/4th%20year%20project/MIZORAM_LANDSLIDE/([^)#\s]+)", txt))
ticks = set(re.findall(r"`((?:data|scripts|models|documentation|gis)/[^`\s]+)`", txt))
missing = sorted({p.replace("%20", " ") for p in links | ticks if not os.path.exists(p.replace("%20", " ").rstrip("/"))})
say(f"checked {len(links | ticks)}; missing {len(missing)}")
for m in missing:
    say("  " + m)

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(L))
