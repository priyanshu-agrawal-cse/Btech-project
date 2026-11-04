"""
Phase 5 — Task P1.2 & P1.3: Compare GSI-only vs GSI + Polygons across 10 spatial block CV seeds.

Uses the 21 natural factors, feature_list_natural.json parameters, and StratifiedGroupKFold(5, shuffle=True)
on block10 for seeds 1 to 10. Negatives are weighted to balance positive class (sample_weight).

For each seed and fold:
- Trains GSI-only model (pos, neg_random, neg_roadmatched) on training blocks
- Trains GSI + polygons model (pos, neg_random, neg_roadmatched, pos_polygon, neg_random_v5) on the same training blocks
- Evaluates both models out-of-fold on held-out blocks:
  - Test P: pos_polygon against neg_random_v5
  - Test R: pos against neg_roadmatched

Applies fixed decision rule in P1.3:
Adopt v5 model iff Test P gains >= 0.020 and Test R drops <= 0.010.

Outputs:
- data/phase5/modeling/results/compare_v5.csv
- data/phase5/modeling/results/p1_decision.json
"""

import os
import sys
import json
import warnings
import numpy as np
import pandas as pd
from xgboost import XGBClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold

_P3_SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "phase3"))
if _P3_SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _P3_SCRIPT_DIR)

from p3_common import log

warnings.filterwarnings("ignore")

OUT_DIR = "data/phase5/modeling/results"
os.makedirs(OUT_DIR, exist_ok=True)
CSV_OUT = f"{OUT_DIR}/compare_v5.csv"
DECISION_OUT = f"{OUT_DIR}/p1_decision.json"

DATA_V5 = "data/phase5/modeling/FINAL_DATASET_v5.csv"
FEAT_JSON = "models/phase3/feature_list_natural.json"

log("Loading FINAL_DATASET_v5.csv and feature_list_natural.json...")
df = pd.read_csv(DATA_V5)
nat = json.load(open(FEAT_JSON))
feats = nat["columns"]
params = nat["params"]

log(f"Features (21 natural): {feats}")
log(f"Model params: {params}")

# Subsets
gsi = df[df.set.isin(["pos", "neg_random", "neg_roadmatched"])].copy().reset_index(drop=True)
v5 = df[df.set.isin(["pos", "neg_random", "neg_roadmatched", "pos_polygon", "neg_random_v5"])].copy().reset_index(drop=True)
test_p = df[df.set.isin(["pos_polygon", "neg_random_v5"])].copy().reset_index(drop=True)
test_r = df[df.set.isin(["pos", "neg_roadmatched"])].copy().reset_index(drop=True)

log(f"Row counts — GSI train: {len(gsi):,}, V5 train: {len(v5):,}, Test P: {len(test_p):,}, Test R: {len(test_r):,}")

NJ = int(os.environ.get("P3_NJOBS", "3"))

rows = []
log("\nStarting 10-seed repeated spatial CV comparison...")

for seed in range(1, 11):
    sgkf = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
    splits = list(sgkf.split(v5[feats].values, v5.landslide.values, v5.block10.values))

    p_gsi_P = np.full(len(test_p), np.nan)
    p_v5_P = np.full(len(test_p), np.nan)
    p_gsi_R = np.full(len(test_r), np.nan)
    p_v5_R = np.full(len(test_r), np.nan)

    for fold_i, (tr_idx, val_idx) in enumerate(splits, 1):
        tr_blocks = set(v5.iloc[tr_idx].block10.unique())
        val_blocks = set(v5.iloc[val_idx].block10.unique())

        # 1. Model GSI-only on training blocks
        tr_gsi = gsi[gsi.block10.isin(tr_blocks)]
        w_gsi = np.where(tr_gsi.landslide == 1, 1.0, (tr_gsi.landslide == 1).sum() / (tr_gsi.landslide == 0).sum())
        m_gsi = XGBClassifier(tree_method="hist", n_jobs=NJ, random_state=42, eval_metric="logloss", **params)
        m_gsi.fit(tr_gsi[feats].values, tr_gsi.landslide.values, sample_weight=w_gsi)

        # 2. Model GSI + polygons (V5) on the same training blocks
        tr_v5 = v5[v5.block10.isin(tr_blocks)]
        w_v5 = np.where(tr_v5.landslide == 1, 1.0, (tr_v5.landslide == 1).sum() / (tr_v5.landslide == 0).sum())
        m_v5 = XGBClassifier(tree_method="hist", n_jobs=NJ, random_state=42, eval_metric="logloss", **params)
        m_v5.fit(tr_v5[feats].values, tr_v5.landslide.values, sample_weight=w_v5)

        # 3. Score out-of-fold on held-out blocks
        mask_p = test_p.block10.isin(val_blocks)
        mask_r = test_r.block10.isin(val_blocks)

        if mask_p.any():
            p_gsi_P[mask_p] = m_gsi.predict_proba(test_p.loc[mask_p, feats].values)[:, 1]
            p_v5_P[mask_p] = m_v5.predict_proba(test_p.loc[mask_p, feats].values)[:, 1]

        if mask_r.any():
            p_gsi_R[mask_r] = m_gsi.predict_proba(test_r.loc[mask_r, feats].values)[:, 1]
            p_v5_R[mask_r] = m_v5.predict_proba(test_r.loc[mask_r, feats].values)[:, 1]

    ok_p = np.isfinite(p_gsi_P) & np.isfinite(p_v5_P)
    ok_r = np.isfinite(p_gsi_R) & np.isfinite(p_v5_R)

    auc_gsi_P = roc_auc_score(test_p.landslide.values[ok_p], p_gsi_P[ok_p])
    auc_v5_P = roc_auc_score(test_p.landslide.values[ok_p], p_v5_P[ok_p])
    auc_gsi_R = roc_auc_score(test_r.landslide.values[ok_r], p_gsi_R[ok_r])
    auc_v5_R = roc_auc_score(test_r.landslide.values[ok_r], p_v5_R[ok_r])

    diff_P = auc_v5_P - auc_gsi_P
    diff_R = auc_v5_R - auc_gsi_R

    row = {
        "seed": seed,
        "auc_gsi_test_p": round(float(auc_gsi_P), 4),
        "auc_v5_test_p": round(float(auc_v5_P), 4),
        "gain_test_p": round(float(diff_P), 4),
        "auc_gsi_test_r": round(float(auc_gsi_R), 4),
        "auc_v5_test_r": round(float(auc_v5_R), 4),
        "change_test_r": round(float(diff_R), 4),
    }
    rows.append(row)
    log(f"Seed {seed:2d}: Test P GSI={auc_gsi_P:.4f} -> V5={auc_v5_P:.4f} ({diff_P:+.4f}) | "
        f"Test R GSI={auc_gsi_R:.4f} -> V5={auc_v5_R:.4f} ({diff_R:+.4f})")

res_df = pd.DataFrame(rows)
res_df.to_csv(CSV_OUT, index=False)
log(f"\nSaved {CSV_OUT}")

means = res_df.mean()
mean_gain_p = float(means["gain_test_p"])
mean_change_r = float(means["change_test_r"])
mean_gsi_p = float(means["auc_gsi_test_p"])
mean_v5_p = float(means["auc_v5_test_p"])
mean_gsi_r = float(means["auc_gsi_test_r"])
mean_v5_r = float(means["auc_v5_test_r"])

log("\n=== 10-SEED MEANS ===")
log(f"Test P (mapped polygons vs random negatives):")
log(f"  GSI-only mean ROC-AUC: {mean_gsi_p:.4f}")
log(f"  V5 (GSI+poly) mean ROC-AUC: {mean_v5_p:.4f}")
log(f"  Mean Gain: {mean_gain_p:+.4f} (Threshold: >= +0.020)")

log(f"\nTest R (GSI roadside landslides vs road-matched negatives):")
log(f"  GSI-only mean ROC-AUC: {mean_gsi_r:.4f}")
log(f"  V5 (GSI+poly) mean ROC-AUC: {mean_v5_r:.4f}")
log(f"  Mean Change: {mean_change_r:+.4f} (Threshold: >= -0.010)")

rule_p = mean_gain_p >= 0.020
rule_r = mean_change_r >= -0.010
adopted = bool(rule_p and rule_r)

decision_data = {
    "task": "P1.3 Decision Rule",
    "threshold_test_p_gain_min": 0.020,
    "threshold_test_r_change_min": -0.010,
    "mean_auc_gsi_test_p": round(mean_gsi_p, 4),
    "mean_auc_v5_test_p": round(mean_v5_p, 4),
    "mean_gain_test_p": round(mean_gain_p, 4),
    "test_p_passed": rule_p,
    "mean_auc_gsi_test_r": round(mean_gsi_r, 4),
    "mean_auc_v5_test_r": round(mean_v5_r, 4),
    "mean_change_test_r": round(mean_change_r, 4),
    "test_r_passed": rule_r,
    "v5_model_adopted": adopted,
    "decision": "ADOPTED" if adopted else "NOT_ADOPTED",
    "summary": (
        f"v5 model ADOPTED: Test P gained {mean_gain_p:+.4f} (>= 0.020) and "
        f"Test R changed by {mean_change_r:+.4f} (>= -0.010)."
        if adopted else
        f"v5 model NOT ADOPTED: conditions not met."
    )
}

with open(DECISION_OUT, "w") as f:
    json.dump(decision_data, f, indent=2)

log(f"\nDecision saved to {DECISION_OUT}:")
log(json.dumps(decision_data, indent=2))
log("\nComparison complete.")
