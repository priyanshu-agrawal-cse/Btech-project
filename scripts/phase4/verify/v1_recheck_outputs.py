"""
Phase 4 verification / V1 - recompute the Phase 4 summary's numbers from saved files (DATA-035).

Read-only. Output: data/phase4/verification/v1_recheck_outputs.txt
"""

import csv
import json
import os
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
import rasterio

OUT = "data/phase4/verification/v1_recheck_outputs.txt"
pd.set_option("display.width", 170, "display.max_columns", 30)
lines = []


def say(s=""):
    print(s)
    lines.append(str(s))


say("== 1. Reproduction gate, recomputed from the 50 rows")
p3 = pd.read_csv("data/phase3/modeling/results/repeated_spatial_cv.csv")
p4 = pd.read_csv("data/phase4/modeling/results/repeated_spatial_cv.csv")
a = p3.groupby("config", sort=False)[["ROC_AUC", "F1_macro", "MCC"]].agg(["mean", "std"])
b = p4.groupby("config", sort=False)[["ROC_AUC", "F1_macro", "MCC"]].agg(["mean", "std"])
d = pd.DataFrame({"P3_ROC": a[("ROC_AUC", "mean")], "P4_ROC": b[("ROC_AUC", "mean")]})
d["abs_diff"] = (d.P3_ROC - d.P4_ROC).abs()
d["P3_F1"], d["P4_F1"] = a[("F1_macro", "mean")], b[("F1_macro", "mean")]
d["P3_MCC_SD"], d["P4_MCC_SD"] = a[("MCC", "std")], b[("MCC", "std")]
say(d.round(4).to_string())
say(f"largest ROC difference {d.abs_diff.max():.4f}; gate limit 0.005: {'PASS' if d.abs_diff.max() <= 0.005 else 'FAIL'}")

say("\n== 2. MCC SD quoted in README line 699 and Slide 10 as 0.006")
r = "All except roads, random negatives"
say(f"stored Phase 3 SD {a.loc[r, ('MCC', 'std')]:.4f}; Phase 4 re-run SD {b.loc[r, ('MCC', 'std')]:.4f}")

say("\n== 3. Tuning table, recomputed from the fold rows")
f = pd.read_csv("data/phase4/modeling/results/tuned_baselines_by_fold.csv")
s = pd.read_csv("data/phase3/modeling/results/nested_metrics_summary.csv").set_index("model")
for tn, n in (("Tuned_Random_Forest", "Random_Forest"), ("Tuned_SVM_RBF", "SVM_RBF"), ("Tuned_Logistic_Regression", "Logistic_Regression")):
    t = f[f.model == tn]
    say(f"{n}: tuned AUC {t.ROC_AUC.mean():.4f} (delta {t.ROC_AUC.mean() - s.loc[n, 'ROC_AUC_mean']:+.4f}), "
        f"F1 {t.F1_macro.mean():.4f} (delta {t.F1_macro.mean() - s.loc[n, 'F1_macro_mean']:+.4f}), "
        f"fold SD {t.ROC_AUC.std():.4f}")

say("\n== 4. Best parameters saved per fold")
bp = json.load(open("data/phase4/modeling/results/tuned_baselines_best_params.json"))
say("RF: " + "; ".join(str(x["rf"]["params"]) for x in bp))
say("SVM distinct parameter sets across 5 folds: " + str(len({json.dumps(x["svm"]["params"], sort_keys=True) for x in bp})))

say("\n== 5. Frequency ratios: Phase 4 table against Phase 3 (labels aside)")
x = pd.read_csv("data/phase3/eda/frequency_ratio.csv")
y = pd.read_csv("data/phase4/eda/frequency_ratio_v4.csv")
m = x.merge(y, on=["factor", "order"], suffixes=("_p3", "_p4"))
say(f"rows {len(x)} vs {len(y)}, matched {len(m)}, largest FR difference {(m.frequency_ratio_p3 - m.frequency_ratio_p4).abs().max():.4f}")
say("labels changed: " + str(sorted(set(m.loc[m.class_p3 != m.class_p4, 'class_p4']))))

say("\n== 6. Zone statistics behind the new previews")
z = pd.read_csv("data/phase3/maps/zone_statistics.csv")
say(z[["zone", "area_pct", "area_pct_oof", "landslide_pct_spatial_oof"]].round(2).to_string(index=False))

say("\n== 7. QGIS style")
root = ET.parse("gis/styles/susceptibility_zones_v3.qml").getroot()
e = root.findall(".//paletteEntry")
say(f"root <{root.tag}> version {root.get('version')}; palette entries {[(i.get('value'), i.get('label')) for i in e]}")

say("\n== 8. Rasters on the master grid")
with rasterio.open("data/derived/mizoram_dem_clipped_utm.tif") as s0:
    tr0, crs0, shape0 = s0.transform, s0.crs, (s0.height, s0.width)
with rasterio.open("data/phase3/features/valid_mask_30m.tif") as s0:
    valid = s0.read(1).astype(bool)
say(f"master {shape0} {crs0}; land cells {int(valid.sum()):,}")
for p in ("data/final/mizoram_landslide_susceptibility_v3.tif", "data/final/mizoram_landslide_susceptibility_v3_natural.tif",
          "data/final/mizoram_landslide_zones_v3.tif", "data/final/mizoram_landslide_zones_v3_natural.tif",
          "data/phase4/features/lith_group.tif", "data/phase4/features/dist_lineament.tif",
          "data/phase4/features/lineament_density_1km.tif"):
    with rasterio.open(p) as s0:
        v = s0.read(1)[valid]
        ok = (s0.transform == tr0) and (s0.crs == crs0) and ((s0.height, s0.width) == shape0)
        nd = s0.nodata
    good = v[v != nd] if nd is not None else v
    say(f"{os.path.basename(p):52s} grid {'OK' if ok else 'DIFFERENT'}  valid {good.size:>11,}  range {float(good.min()):.4f} to {float(good.max()):.4f}")
    del v, good

say("\n== 9. DATA_INVENTORY.csv")
with open("documentation/DATA_INVENTORY.csv", encoding="utf-8", newline="") as fh:
    rows = list(csv.reader(fh))
say(f"rows {len(rows)}; column counts {sorted({len(r_) for r_ in rows})}")

with open(OUT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines))
