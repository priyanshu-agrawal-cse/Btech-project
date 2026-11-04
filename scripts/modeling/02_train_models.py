"""
Train Machine Learning Models for Landslide Susceptibility

This script trains a Random Forest and Logistic Regression model
using the extracted pixel dataset. It addresses class imbalance
by under-sampling the majority class (non-landslide pixels).
"""
import os
import pandas as pd
import numpy as np
import joblib
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, roc_auc_score, roc_curve, auc
from sklearn.preprocessing import StandardScaler
from imblearn.under_sampling import RandomUnderSampler
import matplotlib.pyplot as plt

os.makedirs("models", exist_ok=True)
os.makedirs("data/processed/modeling/results", exist_ok=True)

# 1. Load Data
data_path = "data/processed/modeling/landslide_dataset.csv"
print(f"Loading dataset from {data_path}...")
df = pd.read_csv(data_path)

print(f"Original Dataset Shape: {df.shape}")
print(f"Original Class Distribution:\n{df['landslide'].value_counts()}")

# 2. Prepare X and y
X = df.drop(columns=['landslide', 'row', 'col'], errors='ignore')
y = df['landslide']

# Check for NaNs and drop if any somehow made it through
if X.isnull().sum().sum() > 0:
    print("Warning: NaNs found in features. Dropping rows with NaNs.")
    valid_idx = ~X.isnull().any(axis=1)
    X = X[valid_idx]
    y = y[valid_idx]

# 3. Handle Imbalance (Undersampling)
print("\nPerforming Random Under-Sampling to balance classes...")
rus = RandomUnderSampler(random_state=42)
X_res, y_res = rus.fit_resample(X, y)

print(f"Resampled Dataset Shape: {X_res.shape}")
print(f"Resampled Class Distribution:\n{y_res.value_counts()}")

# 4. Train-Test Split
X_train, X_test, y_train, y_test = train_test_split(
    X_res, y_res, test_size=0.3, random_state=42, stratify=y_res
)
print(f"\nTrain set: {X_train.shape[0]} samples")
print(f"Test set: {X_test.shape[0]} samples")

# 5. Feature Scaling
print("\nScaling features...")
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# Save scaler for future predictions
joblib.dump(scaler, "models/scaler.pkl")

# 6. Model Training & Evaluation
models = {
    "Logistic_Regression": LogisticRegression(random_state=42, max_iter=1000),
    "Random_Forest": RandomForestClassifier(random_state=42, n_estimators=100, max_depth=10)
}

plt.figure(figsize=(8, 6))

for name, model in models.items():
    print(f"\n--- Training {name} ---")
    model.fit(X_train_scaled, y_train)
    
    # Save model
    joblib.dump(model, f"models/{name.lower()}.pkl")
    
    # Predict
    y_pred = model.predict(X_test_scaled)
    y_prob = model.predict_proba(X_test_scaled)[:, 1]
    
    # Metrics
    print(f"Classification Report for {name}:")
    print(classification_report(y_test, y_pred))
    
    roc_auc = roc_auc_score(y_test, y_prob)
    print(f"ROC-AUC Score: {roc_auc:.4f}")
    
    # ROC Curve
    fpr, tpr, _ = roc_curve(y_test, y_prob)
    plt.plot(fpr, tpr, lw=2, label=f'{name} (AUC = {roc_auc:.3f})')

# 7. Plot Formatting
plt.plot([0, 1], [0, 1], color='gray', lw=2, linestyle='--')
plt.xlim([0.0, 1.0])
plt.ylim([0.0, 1.05])
plt.xlabel('False Positive Rate')
plt.ylabel('True Positive Rate')
plt.title('Receiver Operating Characteristic (ROC)')
plt.legend(loc="lower right")
plt.grid(alpha=0.3)

plot_path = "data/processed/modeling/results/roc_curves.png"
plt.savefig(plot_path, dpi=300, bbox_inches='tight')
print(f"\nSaved ROC curves to {plot_path}")

print("\nModel training and evaluation complete!")
