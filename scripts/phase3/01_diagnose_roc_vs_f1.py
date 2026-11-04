"""
Phase 3 / Step 01 — Why is ROC-AUC high while F1 is low?  (DATA-018)

Re-runs the exact Phase 2 XGBoost configuration (02b_train_advanced_models.py)
on the exact Phase 2 training table and decomposes the metrics:

  1. Reproduce the published Phase 2 numbers (random StratifiedKFold, threshold 0.5).
  2. Full metric panel: per-class precision / recall / F1, confusion matrix,
     balanced accuracy, MCC, Cohen's kappa, Brier score, PR-AUC baseline.
  3. Threshold analysis on out-of-fold probabilities (F1-optimal, Youden-J).
  4. Effect of class weighting (scale_pos_weight).
  5. Spatial leakage:
       a. distance from every test pixel to its nearest training pixel;
       b. spatial block cross-validation with 1, 2, 5, 10 and 20 km blocks;
       c. a "coordinates-only" model (row, col as the only inputs).
  6. Location-proxy ablation under 10 km spatial CV.

Outputs: data/phase3/diagnostics/
  diag_metrics.csv, threshold_curve.csv, nearest_train_distance.csv,
  diag_summary.json, fig_threshold_curve.png, fig_random_vs_spatial.png,
  fig_probability_overlap.png

Run from project root:  python scripts/phase3/01_diagnose_roc_vs_f1.py
"""

import os
import sys
import time
import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.spatial import cKDTree
from sklearn.model_selection import StratifiedKFold, StratifiedGroupKFold
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (roc_auc_score, average_precision_score, f1_score,
                             precision_score, recall_score, confusion_matrix,
                             matthews_corrcoef, cohen_kappa_score, brier_score_loss,
                             balanced_accuracy_score, accuracy_score)
from xgboost import XGBClassifier

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p3_common import P3_DIR, save_json, log, SEED

warnings.filterwarnings("ignore")
OUT = f"{P3_DIR}/diagnostics"
os.makedirs(OUT, exist_ok=True)
N_JOBS = int(os.environ.get("P3_NJOBS", "3"))
PIX = 30.3068  # metres

df = pd.read_csv("data/processed/modeling/landslide_dataset_classic.csv")
FEATS = [c for c in df.columns if c not in ("row", "col", "landslide")]
X_raw = df[FEATS].values
y = df["landslide"].values.astype(int)
rows, cols = df["row"].values, df["col"].values
log(f"Loaded Phase 2 table: {len(df):,} rows, {len(FEATS)} features, positive share={y.mean():.3f}")

# Phase 2 scaled with a scaler fitted on ALL rows before CV (kept for exact reproduction).
X = StandardScaler().fit_transform(X_raw)


def phase2_xgb(**over):
    p = dict(n_estimators=200, max_depth=6, learning_rate=0.05, random_state=SEED,
             n_jobs=N_JOBS, eval_metric="logloss", tree_method="hist")
    p.update(over)
    return XGBClassifier(**p)


def panel(yt, prob, thr=0.5):
    yhat = (prob >= thr).astype(int)
    tn, fp, fn, tp = confusion_matrix(yt, yhat, labels=[0, 1]).ravel()
    return {
        "ROC_AUC": roc_auc_score(yt, prob), "PR_AUC": average_precision_score(yt, prob),
        "PR_AUC_random_baseline": yt.mean(), "threshold": thr,
        "Accuracy": accuracy_score(yt, yhat), "Balanced_Accuracy": balanced_accuracy_score(yt, yhat),
        "Precision_LS": precision_score(yt, yhat, zero_division=0),
        "Recall_LS": recall_score(yt, yhat, zero_division=0),
        "F1_LS": f1_score(yt, yhat, zero_division=0),
        "Precision_NonLS": precision_score(1 - yt, 1 - yhat, zero_division=0),
        "Recall_NonLS": recall_score(1 - yt, 1 - yhat, zero_division=0),
        "F1_NonLS": f1_score(1 - yt, 1 - yhat, zero_division=0),
        "F1_macro": f1_score(yt, yhat, average="macro", zero_division=0),
        "MCC": matthews_corrcoef(yt, yhat), "Kappa": cohen_kappa_score(yt, yhat),
        "Brier": brier_score_loss(yt, prob), "TP": tp, "FP": fp, "TN": tn, "FN": fn,
    }


def run_cv(splits, make_model, Xm, label):
    """Return pooled OOF probabilities and fold-mean of the Phase 2 metrics."""
    t0 = time.time()
    oof = np.full(len(y), np.nan)
    fold_roc, fold_pr, fold_f1 = [], [], []
    for tr, te in splits:
        m = make_model()
        m.fit(Xm[tr], y[tr])
        pr = m.predict_proba(Xm[te])[:, 1]
        oof[te] = pr
        fold_roc.append(roc_auc_score(y[te], pr))
        fold_pr.append(average_precision_score(y[te], pr))
        fold_f1.append(f1_score(y[te], (pr >= 0.5).astype(int), average="macro"))
    log(f"  {label:48s} foldmean ROC={np.mean(fold_roc):.4f}(+/-{np.std(fold_roc):.4f}) "
        f"PR={np.mean(fold_pr):.4f} F1m={np.mean(fold_f1):.4f}  [{time.time() - t0:.0f}s]")
    return oof, {"fold_mean_ROC_AUC": np.mean(fold_roc), "fold_std_ROC_AUC": np.std(fold_roc),
                 "fold_mean_PR_AUC": np.mean(fold_pr), "fold_mean_F1_macro@0.5": np.mean(fold_f1)}


random_splits = list(StratifiedKFold(5, shuffle=True, random_state=SEED).split(X, y))


def block_splits(block_km):
    b = max(1, int(round(block_km * 1000 / PIX)))
    groups = (rows // b) * 100_000 + (cols // b)
    sgkf = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEED)
    return list(sgkf.split(X, y, groups)), int(np.unique(groups).size)


records, summary = [], {}

# ---------------------------------------------------------------------------
log("\n1-2. Reproduce Phase 2 (random 5-fold, threshold 0.5) + full metric panel")
oof_rand, fm = run_cv(random_splits, phase2_xgb, X, "XGB Phase-2 config | random CV")
rec = {"experiment": "Phase2 XGB | random 5-fold", **fm, **panel(y, oof_rand, 0.5)}
records.append(rec)
summary["phase2_reproduced"] = rec

# ---------------------------------------------------------------------------
log("\n3. Threshold analysis on pooled out-of-fold probabilities")
thr_grid = np.round(np.arange(0.02, 0.99, 0.01), 2)
curve = []
for t in thr_grid:
    yhat = (oof_rand >= t).astype(int)
    tpr = recall_score(y, yhat); tnr = recall_score(1 - y, 1 - yhat)
    curve.append({"threshold": t, "F1_LS": f1_score(y, yhat), "F1_NonLS": f1_score(1 - y, 1 - yhat),
                  "F1_macro": f1_score(y, yhat, average="macro"), "Youden_J": tpr + tnr - 1,
                  "Recall_LS": tpr, "Recall_NonLS": tnr})
curve = pd.DataFrame(curve)
curve.round(4).to_csv(f"{OUT}/threshold_curve.csv", index=False)
t_f1 = float(curve.loc[curve.F1_macro.idxmax(), "threshold"])
t_j = float(curve.loc[curve.Youden_J.idxmax(), "threshold"])
log(f"  macro-F1-optimal threshold = {t_f1:.2f}  | Youden-J-optimal threshold = {t_j:.2f}")
for t, nm in [(t_f1, "macro-F1-optimal"), (t_j, "Youden-J-optimal")]:
    records.append({"experiment": f"Phase2 XGB | random 5-fold | {nm} threshold", **panel(y, oof_rand, t)})
summary["thr_macroF1_opt"] = t_f1
summary["thr_youden_opt"] = t_j

# ---------------------------------------------------------------------------
log("\n4. Class weighting (scale_pos_weight = n_neg / n_pos)")
spw = (y == 0).sum() / (y == 1).sum()
oof_w, fm = run_cv(random_splits, lambda: phase2_xgb(scale_pos_weight=spw), X,
                   f"XGB scale_pos_weight={spw:.2f} | random CV")
records.append({"experiment": "XGB class-weighted | random 5-fold", **fm, **panel(y, oof_w, 0.5)})

# ---------------------------------------------------------------------------
log("\n5a. Spatial proximity of test pixels to training pixels (random CV, fold 1)")
coords = np.c_[rows, cols] * PIX
dist_rows = []
for nm, splits in [("random 5-fold", random_splits), ("10 km blocks", block_splits(10)[0])]:
    tr, te = splits[0]
    d_any, _ = cKDTree(coords[tr]).query(coords[te], k=1)
    tr_pos = tr[y[tr] == 1]
    te_pos = te[y[te] == 1]
    d_pos, _ = cKDTree(coords[tr_pos]).query(coords[te_pos], k=1)
    dist_rows.append({"cv": nm, "median_m_any": np.median(d_any), "p90_m_any": np.percentile(d_any, 90),
                      "median_m_LS_to_trainLS": np.median(d_pos),
                      "share_LS_test_within_100m_of_train_LS": (d_pos <= 100).mean()})
    log(f"  {nm:14s} median dist to nearest TRAIN pixel = {np.median(d_any):7.0f} m ; "
        f"test landslide -> nearest TRAIN landslide median {np.median(d_pos):7.0f} m ; "
        f"{100 * (d_pos <= 100).mean():5.1f} % within 100 m")
pd.DataFrame(dist_rows).round(3).to_csv(f"{OUT}/nearest_train_distance.csv", index=False)
summary["nearest_train_distance"] = dist_rows

# ---------------------------------------------------------------------------
log("\n5b. Spatial block cross-validation (same model, same data)")
spatial_oof = {}
for km in (1, 2, 5, 10, 20):
    splits, n_blocks = block_splits(km)
    oof_s, fm = run_cv(splits, phase2_xgb, X, f"XGB Phase-2 config | {km:>2d} km blocks ({n_blocks} blocks)")
    spatial_oof[km] = oof_s
    records.append({"experiment": f"Phase2 XGB | spatial {km} km blocks", **fm, **panel(y, oof_s, 0.5)})

# ---------------------------------------------------------------------------
log("\n5c. Coordinates-only model (inputs = row, col only)")
XY = np.c_[rows, cols].astype(float)
oof_xy, fm = run_cv(random_splits, phase2_xgb, XY, "XGB coords-only | random CV")
records.append({"experiment": "XGB coordinates-only | random 5-fold", **fm, **panel(y, oof_xy, 0.5)})
oof_xy_s, fm = run_cv(block_splits(10)[0], phase2_xgb, XY, "XGB coords-only | 10 km blocks")
records.append({"experiment": "XGB coordinates-only | spatial 10 km blocks", **fm, **panel(y, oof_xy_s, 0.5)})

# ---------------------------------------------------------------------------
log("\n6. Location-proxy ablation under 10 km spatial CV")
proxies = ["elevation", "map", "max_precip", "dist_fault"]
keep = [i for i, f in enumerate(FEATS) if f not in proxies]
only = [i for i, f in enumerate(FEATS) if f in proxies]
s10 = block_splits(10)[0]
oof_np, fm = run_cv(s10, phase2_xgb, X[:, keep], "XGB without location proxies | 10 km")
records.append({"experiment": "XGB without elevation/rainfall/fault-distance | spatial 10 km", **fm, **panel(y, oof_np, 0.5)})
oof_op, fm = run_cv(s10, phase2_xgb, X[:, only], "XGB ONLY location proxies | 10 km")
records.append({"experiment": "XGB only elevation/rainfall/fault-distance | spatial 10 km", **fm, **panel(y, oof_op, 0.5)})
oof_op_r, fm = run_cv(random_splits, phase2_xgb, X[:, only], "XGB ONLY location proxies | random")
records.append({"experiment": "XGB only elevation/rainfall/fault-distance | random 5-fold", **fm, **panel(y, oof_op_r, 0.5)})

res = pd.DataFrame(records)
res.round(4).to_csv(f"{OUT}/diag_metrics.csv", index=False)
save_json(summary, f"{OUT}/diag_summary.json")

# ---------------------------------------------------------------------------
# Figures
fig, ax = plt.subplots(figsize=(8, 5))
ax.plot(curve.threshold, curve.F1_LS, label="F1 landslide class")
ax.plot(curve.threshold, curve.F1_NonLS, label="F1 non-landslide class")
ax.plot(curve.threshold, curve.F1_macro, lw=2.5, label="Macro F1 (reported metric)")
ax.axvline(0.5, ls="--", c="grey", label="Phase 2 threshold = 0.50")
ax.axvline(t_f1, ls=":", c="k", label=f"Macro-F1 optimum = {t_f1:.2f}")
ax.set_xlabel("Decision threshold on P(landslide)"); ax.set_ylabel("F1")
ax.set_title("Phase 2 XGBoost, random 5-fold OOF predictions\nF1 depends on the threshold; ROC-AUC does not")
ax.legend(fontsize=8); ax.grid(alpha=.3)
fig.tight_layout(); fig.savefig(f"{OUT}/fig_threshold_curve.png", dpi=160); plt.close(fig)

fig, ax = plt.subplots(figsize=(8, 5))
bins = np.linspace(0, 1, 51)
ax.hist(oof_rand[y == 0], bins=bins, alpha=.6, density=True, label="true non-landslide")
ax.hist(oof_rand[y == 1], bins=bins, alpha=.6, density=True, label="true landslide")
ax.axvline(0.5, ls="--", c="k")
ax.set_xlabel("Out-of-fold P(landslide)"); ax.set_ylabel("density")
ax.set_title("Probability overlap of the two classes (Phase 2 model, random CV)")
ax.legend(); fig.tight_layout(); fig.savefig(f"{OUT}/fig_probability_overlap.png", dpi=160); plt.close(fig)

sel = res[res.experiment.str.startswith("Phase2 XGB | random 5-fold") & ~res.experiment.str.contains("threshold")]
sel = pd.concat([sel, res[res.experiment.str.contains("spatial") & res.experiment.str.startswith("Phase2")]])
fig, ax = plt.subplots(figsize=(9, 5))
lab = ["random"] + [e.split("spatial ")[1].replace(" blocks", "") for e in sel.experiment[1:]]
xpos = np.arange(len(sel))
ax.bar(xpos - .2, sel.ROC_AUC, .4, label="ROC-AUC (pooled OOF)")
ax.bar(xpos + .2, sel.F1_macro, .4, label="Macro F1 @0.5")
for i, (a, b) in enumerate(zip(sel.ROC_AUC, sel.F1_macro)):
    ax.text(i - .2, a + .01, f"{a:.3f}", ha="center", fontsize=8)
    ax.text(i + .2, b + .01, f"{b:.3f}", ha="center", fontsize=8)
ax.set_xticks(xpos); ax.set_xticklabels(lab); ax.set_ylim(0.4, 1.0)
ax.set_xlabel("Cross-validation design"); ax.set_title("Same model, same data: random vs spatial-block CV")
ax.legend(); ax.grid(axis="y", alpha=.3)
fig.tight_layout(); fig.savefig(f"{OUT}/fig_random_vs_spatial.png", dpi=160); plt.close(fig)

log(f"\nSaved diagnostics to {OUT}/")
pd.set_option("display.width", 220)
log(res[["experiment", "ROC_AUC", "PR_AUC", "PR_AUC_random_baseline", "threshold", "F1_LS",
         "F1_NonLS", "F1_macro", "Recall_NonLS", "MCC"]].round(4).to_string(index=False))
