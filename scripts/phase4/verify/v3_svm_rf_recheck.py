"""
Phase 4 verification / V3 - two suspected defects in 10_tune_baselines_cv.py (DATA-035).

1. SVM: the script sets SVC(max_iter=2000). Phase 3 used no limit, and the script hides
   warnings. For each outer fold, the saved tuned parameters are fitted with the limit and
   without it, reporting the solver status and iterations. fit_status_ 1 means stopped early.
2. RF: study.best_params holds only the searched values, so the final
   RandomForestClassifier(**p_rf) has no random_state. Each fold is refitted with three
   seeds to measure how much the score moves for that reason alone.

Reads the saved parameters only; no tuning is repeated here.
Output: data/phase4/verification/svm_rf_recheck.csv
"""

import json
import os
import sys
import time
import warnings

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "phase3")))
from p3_common import SEED, log

warnings.filterwarnings("ignore")
OUT = "data/phase4/verification"
os.makedirs(OUT, exist_ok=True)
LULC_CODES = [10, 20, 30, 40, 50, 60, 80, 90]


def matrix(df, feats):
    X = df[[f for f in feats if f != "lulc"]].copy()
    if "lulc" in feats:
        for c in LULC_CODES:
            X[f"lulc_{c}"] = (df["lulc"].values == c).astype("float32")
    return X


full = pd.read_csv("data/phase3/modeling/FINAL_DATASET_v3.csv")
with open("models/phase3/feature_list.json") as f:
    ALL = json.load(f)["raster_features"]
with open("data/phase4/modeling/results/tuned_baselines_best_params.json") as f:
    best = json.load(f)

main = full[full.set.isin(["pos", "neg_random"])].reset_index(drop=True)
y = main.landslide.values
g = main.block10.values
X = matrix(main, ALL).values.astype("float32")
outer = list(StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEED).split(np.zeros(len(y)), y, g))

rows = []
for k, (tr, te) in enumerate(outer):
    imp = SimpleImputer(strategy="median").fit(X[tr])
    sc = StandardScaler().fit(imp.transform(X[tr]))
    Xtr, Xte = sc.transform(imp.transform(X[tr])), sc.transform(imp.transform(X[te]))
    ps = best[k]["svm"]["params"]
    for cap in (2000, -1):
        t = time.time()
        m = SVC(**ps, kernel="rbf", random_state=SEED, max_iter=cap).fit(Xtr, y[tr])
        auc = roc_auc_score(y[te], m.decision_function(Xte))
        rec = {"check": "svm", "fold": k, "setting": f"max_iter={cap}", "C": ps["C"], "gamma": ps["gamma"],
               "iterations": int(np.sum(m.n_iter_)), "fit_status": int(m.fit_status_),
               "ROC_AUC": round(auc, 4), "seconds": round(time.time() - t, 1)}
        rows.append(rec)
        log(str(rec))
    for s in (SEED, SEED + 1, SEED + 2):
        pr = dict(best[k]["rf"]["params"])
        m = RandomForestClassifier(**pr, n_jobs=3, random_state=s).fit(X[tr], y[tr])
        rec = {"check": "rf", "fold": k, "setting": f"random_state={s}",
               "ROC_AUC": round(roc_auc_score(y[te], m.predict_proba(X[te])[:, 1]), 4)}
        rows.append(rec)
        log(str(rec))
    pd.DataFrame(rows).to_csv(f"{OUT}/svm_rf_recheck.csv", index=False)

log("V3 finished.")
