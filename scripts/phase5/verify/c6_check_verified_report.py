"""
Phase 5 verification / C6 - test FINAL_REPORT_VERIFIED.md against the source files (DATA-046).

Each check reads a value from a result file, formats it as the report does, and looks for that
exact text in the named part of the report. A check can fail, and failures are printed.
Output: data/phase5/verification/c6_report_check.txt
"""

import json
import re
from decimal import ROUND_HALF_UP, Decimal

import pandas as pd

REPORT = open("documentation/FINAL_REPORT_VERIFIED.md", encoding="utf-8").read()
LOG = open("documentation/MIZORAM_LANDSLIDE_PROJECT_DOCUMENTATION.md", encoding="utf-8").read()
P3 = "data/phase3/modeling/results"
P4 = "data/phase4/modeling/results"
V4 = "data/phase4/verification"
V5 = "data/phase5/verification"
out, bad = [], []


def rnd(v, n=3):
    """Round half up from the stored text of the value, so 14.35 gives 14.4 and 0.9485 gives 0.949."""
    return str(Decimal(str(round(float(v), 6))).quantize(Decimal(1).scaleb(-n), rounding=ROUND_HALF_UP))


def item(n):
    """Text of report item n, or the summary when n is 0."""
    if n == 0:
        return REPORT.split("## Report items")[0]
    return re.split(r"\n### \d+\. ", REPORT)[n]


def check(label, text, where=0):
    ok = text in item(where)
    out.append(f"{'PASS' if ok else 'FAIL'}  item {where:>2}  {label}: {text}")
    if not ok:
        bad.append(out[-1])


def log_has(label, text):
    ok = text in LOG
    out.append(f"{'PASS' if ok else 'FAIL'}  main log  {label}: {text}")
    if not ok:
        bad.append(out[-1])


# Main results table
rc = pd.read_csv("data/phase3/maps/rate_curve_summary.csv")
check("road AUC, GSI", f"{rc[rc.curve.str.startswith('Baseline')].AUC.iloc[0]:.3f}")
check("natural AUC, GSI", f"{rc[rc.curve.str.startswith('natural-terrain')].AUC.iloc[0]:.3f}")
check("all-factor AUC, GSI", f"{rc[rc.curve.str.contains('all-factor map, spatial')].AUC.iloc[0]:.3f}")
iv = pd.read_csv(f"{V4}/independent_validation.csv")
p = iv[iv.test_set.str.contains("primary")].set_index("ranking")
for r in p.index:
    check(f"polygons, {r}", f"{p.loc[r, 'AUC']:.3f}")
u = pd.read_csv(f"{V5}/v5_unseen_test.csv")
o = u[u.test_set.str.contains("no training")].set_index("ranking")
check("outside sheets pixels", f"{int(o.pixels.iloc[0]):,}")
for r in o.index:
    check(f"outside sheets, {r}", f"{o.loc[r, 'AUC']:.3f}")
y = pd.read_csv("data/phase5/maps/independent_validation_2024_v5.csv").set_index("Model")
check("2024 pixels", f"{int(y.Test_Pixels.iloc[0])}")
for r in y.index:
    check(f"2024, {r}", f"{y.loc[r, 'AUC']:.3f}")

# Item 3 (exact values from the fact check)
fc = open(f"{V5}/c3_fact_check.txt", encoding="utf-8").read()
m = re.search(r"elevation: min ([\d.]+) max ([\d.]+) mean ([\d.]+)", fc)
check("elevation", f"{m[1]} to {float(m[2]):,.1f} m, mean {m[3]} m", 3)
m = re.search(r"slope: min [\d.]+ max ([\d.]+) mean ([\d.]+)", fc)
check("slope", f"0 to {m[1]}°, mean {m[2]}°", 3)
m = re.search(r"MAP: min ([\d.]+) max ([\d.]+) mean ([\d.]+)", fc)
check("rain", f"{float(m[1]):,.1f} to {float(m[2]):,.1f} mm, mean {float(m[3]):,.1f} mm", 3)
m = re.search(r"max_precip: min ([\d.]+) max ([\d.]+) mean ([\d.]+)", fc)
check("max rain", f"{float(m[1]):,.1f} to {float(m[2]):,.1f} mm, mean {float(m[3]):,.1f} mm", 3)

# Items 19, 20, 22
inv = json.load(open("data/phase3/inventory/inventory_v3_summary.json"))
check("GSI records", f"{inv['gsi_records_inside_boundary']:,}", 19)
check("duplicates", f"{inv['gsi_identical_coordinate_duplicates']}", 19)
check("unique locations", f"{inv['gsi_unique_locations']:,}", 19)
check("locations used", f"{inv['locations_used']:,}", 19)
check("pixels", f"{inv['positive_pixels']:,}", 19)
d3 = pd.read_csv("data/phase3/modeling/FINAL_DATASET_v3.csv")
check("neg_pool", f"{(d3.set == 'neg_pool').sum():,}", 20)
check("table shape", f"{len(d3):,} rows and {d3.shape[1]} columns", 22)

# Item 24
ua = pd.read_csv("data/phase3/eda/univariate_auc.csv").set_index("feature")
check("road density", f"{ua.loc['road_density_1km', 'auc']:.3f}", 24)
check("elevation / slope", f"{ua.loc['elevation', 'auc']:.3f} / {ua.loc['slope', 'auc']:.3f}", 24)
fr = pd.read_csv("data/phase3/eda/frequency_ratio.csv")
s = fr[fr.factor == "slope"].sort_values("order").frequency_ratio.values
check("FR slope low", f"below 10°: {s[0]:.2f}", 24)
check("FR slope high", f"above 40°: {s[-1]:.2f}", 24)
r = fr[fr.factor == "dist_road_any"].sort_values("order").frequency_ratio.values
check("FR road", f"0 to 30 m: {r[0]:.1f}", 24)
g = pd.read_csv("data/phase4/eda/geology_frequency_ratio.csv").set_index("class")
check("FR shale", f"shale-dominant {g.loc['shale_dominant', 'frequency_ratio']:.2f}", 24)
check("FR coal", f"coal-bearing {g.loc['coal_bearing', 'frequency_ratio']:.2f}", 24)

# Item 28
b = json.load(open(f"{P3}/best_params.json"))["xgb"]
check("XGB params", f"| {b['n_estimators']} | {b['max_depth']} | {b['learning_rate']:.4f} | {b['subsample']:.3f} | {b['colsample_bytree']:.3f} | {b['reg_lambda']:.2f} | {b['min_child_weight']} |", 28)
n = json.load(open("models/phase3/feature_list_natural.json"))
q = n["params"]
check("natural params", f"| {q['n_estimators']} | {q['max_depth']} | {q['learning_rate']:.4f} | {q['subsample']:.3f} | {q['colsample_bytree']:.3f} | {q['reg_lambda']:.2f} | {q['min_child_weight']} |", 28)
check("threshold", f"{n['threshold_macroF1']:.2f}", 28)

# Item 30
s3 = pd.read_csv(f"{P3}/nested_metrics_summary.csv").set_index("model")
ci = pd.read_csv(f"{P3}/pooled_auc_block_bootstrap.csv").set_index("model")
for name, key in (("XGBoost", "XGBoost"), ("LightGBM", "LightGBM"), ("Ensemble", "Ensemble_RF_XGB_LGBM")):
    a = s3.loc[key]
    c = ci.loc[key]
    check(name, f"| {name} | {rnd(a.ROC_AUC_mean)} | {rnd(c.ci95_low)} to {rnd(c.ci95_high)} | {rnd(a.PR_AUC_mean)} | {rnd(a.F1_macro_mean)} | {rnd(a.MCC_mean)} |", 30)
t = pd.read_csv(f"{P4}/tuned_baselines_v2_summary.csv").set_index("model")
for name, key in (("Random Forest, tuned", "Random_Forest"), ("SVM (RBF), tuned", "SVM_RBF"), ("Logistic Regression, tuned", "Logistic_Regression")):
    a = t.loc[key]
    check(name, f"| {name} | {a.ROC_AUC_mean:.3f} | Not computed | {a.PR_AUC_mean:.3f} | {a.F1_macro_mean:.3f} | {a.MCC_mean:.3f} |", 30)
rp = pd.read_csv(f"{P3}/repeated_spatial_cv.csv")
rr = rp[rp.config == "Distance to road only"]
check("road row", f"| **{rr.ROC_AUC.mean():.3f}** | | | **{rr.F1_macro.mean():.3f}** | **{rr.MCC.mean():.3f}** |", 30)

# Item 31
ff = pd.read_csv(f"{P3}/feature_family_importance.csv").set_index("family")
check("roads importance", f"about {ff.loc['roads', 'perm_auc_drop_mean']:.2f}", 31)
ni = pd.read_csv(f"{P3}/natural_feature_importance.csv").set_index("feature").perm_auc_drop_mean
check("natural importance", f"slope {ni['slope']:.3f}, mean annual rainfall {ni['map']:.3f}, profile curvature {ni['curv_profile']:.3f}, TWI {ni['twi']:.3f}", 31)

# Item 32
dd = json.load(open("data/phase5/modeling/results/p1_decision.json"))
check("Test P", f"{dd['mean_auc_gsi_test_p']:.3f} to {dd['mean_auc_v5_test_p']:.3f}", 32)
check("Test R", f"{dd['mean_change_test_r']:.3f}".replace("-", "−"), 32)
pc = pd.read_csv(f"{V5}/polygon_controls.csv")
check("coords", f"{pc[(pc.block_km == 10) & (pc.features == 'coords')].test_p_with_polygons.iloc[0]:.3f}", 32)
sa = pd.read_csv(f"{V5}/same_area_test.csv").set_index("features")
check("slope alone", f"{sa.loc['slope alone, no model', 'with_polygons']:.3f}", 32)
ag = pd.read_csv(f"{V5}/aspect_by_group.csv").set_index("group")
m_ = ag.loc["Mapped polygons (v5 training)"]
la = ag.loc["All land (1 in 97 cells)"]
check("direction", f"{m_.north_pct} % face north, {m_.south_pct} % south; all land is {la.north_pct} % and {la.south_pct} %", 32)
fp = pd.read_csv(f"{V5}/map_footprint_check.csv").set_index("map")
check("footprint v5", f"v5: {rnd(fp.loc['Natural v5', 'very_high_rate_inside_blocks_pct'], 1)} % and {rnd(fp.loc['Natural v5', 'very_high_rate_outside_blocks_pct'], 1)} %", 32)
check("footprint v3", f"v3: {fp.loc['Natural v3', 'very_high_rate_inside_blocks_pct']:.1f} % and {fp.loc['Natural v3', 'very_high_rate_outside_blocks_pct']:.1f} %", 32)
sh = pd.read_csv(f"{V5}/polygon_sheet_counts.csv")
tot = sh["Mapped as polygon"].sum()
check("3 sheets", f"{sh['Mapped as polygon'].nlargest(3).sum() / tot * 100:.1f} % lie in 3 map sheets", 32)

# Item 33
z = pd.read_csv("data/phase3/maps/zone_statistics_natural.csv").set_index("zone")
zv = pd.read_csv(f"{V4}/independent_validation_zones.csv")
pr = zv[zv.test_set.str.contains("primary")]
for zn in z.index:
    a = pr[(pr.ranking.str.startswith("Natural")) & (pr.zone == zn)].iloc[0]
    b_ = pr[(pr.ranking.str.startswith("All-factor")) & (pr.zone == zn)].iloc[0]
    check(f"zone {zn}", f"| {zn} | {rnd(z.loc[zn, 'area_pct_oof'], 1)} / {rnd(z.loc[zn, 'landslide_pct_spatial_oof'], 1)} | {rnd(a.area_pct, 1)} / {rnd(a.landslide_pct, 1)} | {rnd(b_.area_pct, 1)} / {rnd(b_.landslide_pct, 1)} |", 33)

# Facts that live only in the main log
for label, text in (("Phase 1 RF", "0.7276"), ("Phase 1 LR", "0.7051"), ("coordinates, Phase 2", "0.8956"), ("median distance", "3,738 m"),
                    ("closest negative", "135.5 m"), ("breaching", "~15 min")):
    log_has(label, text)

with open(f"{V5}/c6_report_check.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print(f"{len(out)} checks, {len(out) - len(bad)} passed, {len(bad)} failed")
for b_ in bad:
    print(b_[:170])
