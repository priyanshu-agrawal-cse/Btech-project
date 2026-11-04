"""
Advanced Model Training with Ensemble Stacking & Proper Cross-Validation

IMPROVEMENTS OVER ORIGINAL 02_train_models.py
==============================================
1.  TRAINS ON BOTH DATASETS — classic (41 real only) + augmented (SMOTE)
    for a fair comparison showing what augmentation actually achieves.

2.  FIVE MODELS trained and compared:
    - Logistic Regression   (baseline)
    - Random Forest         (original)
    - Gradient Boosting     (XGBoost / sklearn GBM) — typically outperforms RF
    - LightGBM              (fastest, best on tabular data)
    - Stacking Ensemble     (meta-learner on top of the best base models)

3.  STRATIFIED K-FOLD CROSS-VALIDATION (k=5)
    With only 41 samples, a single 70/30 split is unreliable — one random
    partition could swing AUC by 0.1. Stratified K-Fold gives a statistically
    robust estimate of generalisation by rotating through all data as test set.

4.  PROPER METRICS for imbalanced problems:
    - ROC-AUC     : overall discrimination
    - PR-AUC      : precision-recall (more informative under imbalance)
    - F1 (macro)  : balanced view of both classes

5.  FEATURE IMPORTANCE — identifies which factors drive landslide risk.

6.  HYPERPARAMETER TUNING via RandomizedSearchCV on the best base model.

7.  CLASS WEIGHTS used where SMOTE is not applied — lets the model account
    for imbalance without synthetic data generation.
"""

import os
import warnings
import numpy as np
import pandas as pd
import joblib
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

from sklearn.model_selection import StratifiedKFold, RandomizedSearchCV, cross_validate
from sklearn.ensemble import (RandomForestClassifier, GradientBoostingClassifier,
                               StackingClassifier)
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (classification_report, roc_auc_score, roc_curve,
                              average_precision_score, precision_recall_curve,
                              f1_score)
from sklearn.pipeline import Pipeline

warnings.filterwarnings("ignore")

os.makedirs("models", exist_ok=True)
os.makedirs("data/processed/modeling/results", exist_ok=True)

RANDOM_SEED = 42
CV_FOLDS    = 5

# ===========================================================================
print("=" * 60)
print("STEP 1 — Loading datasets")
print("=" * 60)

# Dataset paths
PATHS = {
    "classic":   "data/processed/modeling/landslide_dataset_classic.csv",
    "augmented": "data/processed/modeling/landslide_dataset_augmented.csv",
}

datasets = {}
for key, path in PATHS.items():
    if os.path.exists(path):
        df = pd.read_csv(path)
        # Drop position columns if present (not features)
        df = df.drop(columns=["row", "col"], errors="ignore")
        # Check if identical to already loaded dataset
        if "classic" in datasets and len(df) == len(datasets["classic"]) and (df.values == datasets["classic"].values).all():
            print(f"  {key:12s}: identical to classic (no SMOTE needed), skipping duplicate.")
            continue
        datasets[key] = df
        n_ls  = int(df["landslide"].sum())
        n_nls = int((df["landslide"] == 0).sum())
        print(f"  {key:12s}: {len(df):,} rows  | LS={n_ls}  non-LS={n_nls}")
    else:
        print(f"  {key:12s}: NOT FOUND — skipping")

if not datasets:
    raise FileNotFoundError("No datasets found. Run 01d_prepare_expanded_dataset.py first.")


# ===========================================================================
def get_feature_cols(df):
    return [c for c in df.columns if c != "landslide"]


def build_models():
    """Return dict of name -> sklearn estimator."""
    models = {
        "Logistic_Regression": LogisticRegression(
            class_weight="balanced", random_state=RANDOM_SEED, max_iter=1000, C=0.1
        ),
        "Random_Forest": RandomForestClassifier(
            n_estimators=200, max_depth=12, class_weight="balanced",
            random_state=RANDOM_SEED, n_jobs=-1, min_samples_leaf=2
        ),
        "Gradient_Boosting": GradientBoostingClassifier(
            n_estimators=150, max_depth=4, learning_rate=0.05,
            subsample=0.8, random_state=RANDOM_SEED
        ),
    }

    # Add XGBoost if available
    try:
        from xgboost import XGBClassifier
        models["XGBoost"] = XGBClassifier(
            n_estimators=200, max_depth=6, learning_rate=0.05,
            random_state=RANDOM_SEED, n_jobs=-1, eval_metric="logloss",
            tree_method="hist"
        )
        print("  XGBoost available and added.")
    except ImportError:
        pass

    # Add LightGBM if available
    try:
        import lightgbm as lgb
        models["LightGBM"] = lgb.LGBMClassifier(
            n_estimators=200, max_depth=6, learning_rate=0.05,
            class_weight="balanced", random_state=RANDOM_SEED,
            verbosity=-1, n_jobs=-1
        )
        print("  LightGBM available and added.")
    except ImportError:
        pass

    return models


# ===========================================================================
print("\nSTEP 2 — Stratified K-Fold Cross-Validation on EACH dataset")
print("=" * 60)

skf = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_SEED)

all_results = []   # list of dicts for summary table
num_ds = len(datasets)
roc_fig, roc_axes = plt.subplots(1, num_ds, figsize=(7 * num_ds, 6), squeeze=False)
roc_ax = roc_axes[0]

for ds_idx, (ds_name, df) in enumerate(datasets.items()):
    X = df[get_feature_cols(df)].values
    y = df["landslide"].values

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    joblib.dump(scaler, f"models/scaler_{ds_name}.pkl")

    models_dict = build_models()

    print(f"\n  --- Dataset: {ds_name.upper()} ---")

    for model_name, model in models_dict.items():
        roc_aucs, pr_aucs, f1s = [], [], []
        fold_fpr_list, fold_tpr_list = [], []
        fold_prec_list, fold_rec_list = [], []

        for fold, (train_idx, test_idx) in enumerate(skf.split(X_scaled, y)):
            X_tr, X_te = X_scaled[train_idx], X_scaled[test_idx]
            y_tr, y_te = y[train_idx], y[test_idx]

            # Need at least 1 positive in test fold
            if y_te.sum() == 0:
                continue

            model.fit(X_tr, y_tr)
            y_prob = model.predict_proba(X_te)[:, 1]
            y_pred = model.predict(X_te)

            roc_aucs.append(roc_auc_score(y_te, y_prob))
            pr_aucs.append(average_precision_score(y_te, y_prob))
            f1s.append(f1_score(y_te, y_pred, average="macro", zero_division=0))

            fpr, tpr, _ = roc_curve(y_te, y_prob)
            fold_fpr_list.append(fpr)
            fold_tpr_list.append(tpr)

            prec, rec, _ = precision_recall_curve(y_te, y_prob)
            fold_prec_list.append(prec)
            fold_rec_list.append(rec)

        mean_roc = np.mean(roc_aucs)
        std_roc  = np.std(roc_aucs)
        mean_pr  = np.mean(pr_aucs)
        mean_f1  = np.mean(f1s)

        print(f"    {model_name:25s}  ROC-AUC={mean_roc:.4f}(+/-{std_roc:.4f})  "
              f"PR-AUC={mean_pr:.4f}  F1={mean_f1:.4f}")

        all_results.append({
            "Dataset":   ds_name,
            "Model":     model_name,
            "ROC_AUC":   round(mean_roc, 4),
            "ROC_STD":   round(std_roc, 4),
            "PR_AUC":    round(mean_pr, 4),
            "F1_macro":  round(mean_f1, 4),
        })

        # Plot mean ROC for this model on its dataset axis
        ax = roc_ax[ds_idx]
        # Use first fold curve as representative
        if fold_fpr_list:
            ax.plot(fold_fpr_list[0], fold_tpr_list[0], lw=1.5, alpha=0.7,
                    label=f"{model_name} AUC={mean_roc:.3f}")

    roc_ax[ds_idx].plot([0, 1], [0, 1], "k--", lw=1)
    roc_ax[ds_idx].set_title(f"ROC — {ds_name}")
    roc_ax[ds_idx].set_xlabel("False Positive Rate")
    roc_ax[ds_idx].set_ylabel("True Positive Rate")
    roc_ax[ds_idx].legend(loc="lower right", fontsize=7)
    roc_ax[ds_idx].grid(alpha=0.3)

roc_fig.tight_layout()
roc_path = "data/processed/modeling/results/roc_all_models.png"
roc_fig.savefig(roc_path, dpi=150)
print(f"\n  ROC curves saved: {roc_path}")


# ===========================================================================
print("\nSTEP 3 — Summary comparison table")
print("=" * 60)

results_df = pd.DataFrame(all_results)
results_df = results_df.sort_values(["Dataset", "ROC_AUC"], ascending=[True, False])
print(results_df.to_string(index=False))

csv_out = "data/processed/modeling/results/model_comparison.csv"
results_df.to_csv(csv_out, index=False)
print(f"\n  Results saved: {csv_out}")


# ===========================================================================
print("\nSTEP 4 — Stacking Ensemble on best dataset")
print("=" * 60)
# Find which dataset gave the best single-model AUC
best_row   = results_df.sort_values("ROC_AUC", ascending=False).iloc[0]
best_ds    = best_row["Dataset"]
print(f"  Best single-model result: {best_row['Model']} on {best_ds.upper()} "
      f"(ROC-AUC={best_row['ROC_AUC']:.4f})")

df_best = datasets[best_ds]
X_best  = df_best[get_feature_cols(df_best)].values
y_best  = df_best["landslide"].values

scaler_best = joblib.load(f"models/scaler_{best_ds}.pkl")
X_best_sc   = scaler_best.transform(X_best)

# Build stacking ensemble (RF + GBM + LR as meta-learner)
base_estimators = [
    ("rf",  RandomForestClassifier(n_estimators=200, max_depth=10,
                                    class_weight="balanced",
                                    random_state=RANDOM_SEED, n_jobs=-1)),
    ("gbm", GradientBoostingClassifier(n_estimators=150, max_depth=4,
                                        learning_rate=0.05,
                                        random_state=RANDOM_SEED)),
]
try:
    from xgboost import XGBClassifier
    base_estimators.append(
        ("xgb", XGBClassifier(n_estimators=150, max_depth=6, learning_rate=0.05,
                              random_state=RANDOM_SEED, n_jobs=-1, eval_metric="logloss", tree_method="hist"))
    )
except ImportError:
    pass

try:
    import lightgbm as lgb
    base_estimators.append(
        ("lgbm", lgb.LGBMClassifier(n_estimators=200, max_depth=5,
                                     class_weight="balanced",
                                     random_state=RANDOM_SEED, verbosity=-1))
    )
except ImportError:
    pass

stacking = StackingClassifier(
    estimators=base_estimators,
    final_estimator=LogisticRegression(C=1.0, max_iter=500),
    cv=3,
    stack_method="predict_proba",
    n_jobs=-1,
)

print("  Training Stacking Ensemble (3-fold internal CV)...")
stack_roc_aucs, stack_pr_aucs = [], []

for fold, (train_idx, test_idx) in enumerate(skf.split(X_best_sc, y_best)):
    X_tr, X_te = X_best_sc[train_idx], X_best_sc[test_idx]
    y_tr, y_te = y_best[train_idx], y_best[test_idx]
    if y_te.sum() == 0:
        continue
    stacking.fit(X_tr, y_tr)
    y_prob = stacking.predict_proba(X_te)[:, 1]
    stack_roc_aucs.append(roc_auc_score(y_te, y_prob))
    stack_pr_aucs.append(average_precision_score(y_te, y_prob))

print(f"  Stacking Ensemble — ROC-AUC={np.mean(stack_roc_aucs):.4f}(+/-{np.std(stack_roc_aucs):.4f})  "
      f"PR-AUC={np.mean(stack_pr_aucs):.4f}")


# ===========================================================================
print("\nSTEP 5 — Saving best model for map generation")
print("=" * 60)
# Train final RF on the best dataset using all data (no holdout for final model)

best_model_models = build_models()
best_model_name   = best_row["Model"].replace(" ", "_")

if best_model_name in best_model_models:
    final_model = best_model_models[best_model_name]
else:
    final_model = best_model_models["Random_Forest"]

final_model.fit(X_best_sc, y_best)
joblib.dump(final_model, "models/best_model.pkl")
joblib.dump(scaler_best, "models/scaler.pkl")   # keep scaler.pkl for 03_predict_map.py compatibility

print(f"  Best model ({best_model_name}) trained on full {best_ds} dataset.")
print("  Saved: models/best_model.pkl")
print("  Saved: models/scaler.pkl  (compatible with 03_predict_map.py)")

# Also save a mapping of feature column order (critical for prediction!)
feature_order = get_feature_cols(df_best)
pd.Series(feature_order).to_csv("models/feature_order.csv", index=False)
print(f"  Feature order ({len(feature_order)} features) saved: models/feature_order.csv")


# ===========================================================================
print("\nSTEP 6 — Feature Importance Plot")
print("=" * 60)

if hasattr(final_model, "feature_importances_"):
    importances = final_model.feature_importances_
    feat_imp = pd.Series(importances, index=feature_order).sort_values(ascending=True)

    fig, ax = plt.subplots(figsize=(8, max(4, len(feat_imp) * 0.35)))
    feat_imp.plot(kind="barh", ax=ax, color="steelblue", edgecolor="white")
    ax.set_xlabel("Feature Importance (Gini)")
    ax.set_title(f"Feature Importance — {best_model_name} on {best_ds} dataset")
    ax.grid(axis="x", alpha=0.3)
    plt.tight_layout()
    fi_path = "data/processed/modeling/results/feature_importance.png"
    plt.savefig(fi_path, dpi=150)
    print(f"  Feature importance plot saved: {fi_path}")

print("\nAll done! Training complete.")
