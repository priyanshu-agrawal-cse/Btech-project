"""
Finalize Best Model (XGBoost) and Feature Importance

Trained on the expanded 91,944-sample multi-source GSI/NASA dataset.
Saves models/best_model.pkl, models/scaler.pkl, models/feature_order.csv,
and generates data/processed/modeling/results/feature_importance.png.
"""

import os
import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier
from sklearn.ensemble import RandomForestClassifier

os.makedirs("models", exist_ok=True)
os.makedirs("data/processed/modeling/results", exist_ok=True)

DATASET_PATH = "data/processed/modeling/landslide_dataset_classic.csv"
print(f"Loading dataset: {DATASET_PATH}...")
df = pd.read_csv(DATASET_PATH)
df = df.drop(columns=["row", "col"], errors="ignore")

feature_cols = [c for c in df.columns if c != "landslide"]
X = df[feature_cols].values
y = df["landslide"].values

print(f"Dataset: {len(df):,} samples | {len(feature_cols)} features")
print(f"  Landslide samples: {int(y.sum()):,}")
print(f"  Non-landslide samples: {int((y == 0).sum()):,}")

# Fit and save scaler
print("\nFitting StandardScaler...")
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)
joblib.dump(scaler, "models/scaler.pkl")
print("  Saved: models/scaler.pkl")

# Save feature order
pd.Series(feature_cols).to_csv("models/feature_order.csv", index=False)
print("  Saved: models/feature_order.csv")

# Train final XGBoost model (Best model from 5-fold CV: 0.8932 ROC-AUC)
print("\nTraining final XGBoost model on full dataset...")
xgb = XGBClassifier(
    n_estimators=300,
    max_depth=6,
    learning_rate=0.05,
    random_state=42,
    n_jobs=-1,
    eval_metric="logloss",
    tree_method="hist",
)
xgb.fit(X_scaled, y)
joblib.dump(xgb, "models/best_model.pkl")
joblib.dump(xgb, "models/xgboost_best.pkl")
print("  Saved: models/best_model.pkl")

# Also train Random Forest
print("\nTraining final Random Forest model...")
rf = RandomForestClassifier(
    n_estimators=200,
    max_depth=12,
    class_weight="balanced",
    random_state=42,
    n_jobs=-1,
    min_samples_leaf=2,
)
rf.fit(X_scaled, y)
joblib.dump(rf, "models/random_forest.pkl")
print("  Saved: models/random_forest.pkl")

# Feature Importance Plot
print("\nGenerating Feature Importance Plot...")
importances = xgb.feature_importances_
feat_imp = pd.Series(importances, index=feature_cols).sort_values(ascending=True)

plt.figure(figsize=(10, 7))
bars = plt.barh(feat_imp.index, feat_imp.values, color="#1f77b4", edgecolor="none", height=0.65)
plt.xlabel("Relative Feature Importance (Gain / Information Ratio)", fontsize=11, fontweight="bold")
plt.title("Landslide Susceptibility — Feature Importance Rankings (XGBoost)\nMizoram 30m Multi-Source Model (91,944 ground-truth observations)", fontsize=12, fontweight="bold", pad=15)
plt.grid(axis="x", linestyle="--", alpha=0.5)

# Annotate values on bars
for bar in bars:
    w = bar.get_width()
    plt.text(w + 0.003, bar.get_y() + bar.get_height() / 2, f"{w:.3f}", va="center", ha="left", fontsize=9, color="#333333")

plt.xlim(0, max(feat_imp.values) * 1.15)
plt.tight_layout()
out_fi = "data/processed/modeling/results/feature_importance.png"
plt.savefig(out_fi, dpi=200)
plt.close()
print(f"  Saved: {out_fi}")

print("\nFinal models and feature importance complete!")
