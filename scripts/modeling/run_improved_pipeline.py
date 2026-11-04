"""
Master Runner — Improved Landslide Susceptibility Pipeline

Run this script from the MIZORAM_LANDSLIDE/ root directory to execute the
full improved pipeline end-to-end:

  Step 1b  : Derive advanced topographic features (TWI, TRI, TPI, etc.)
  Step 1c  : Prepare improved dataset (stratified sampling + BorderlineSMOTE)
  Step 2b  : Train advanced models with stratified K-fold CV
  Step 3b  : Generate improved susceptibility map

Usage:
  cd MIZORAM_LANDSLIDE
  python scripts/modeling/run_improved_pipeline.py

Pre-requisites (install if missing):
  pip install scikit-learn imbalanced-learn lightgbm scipy rasterio numpy pandas joblib matplotlib
"""

import subprocess
import sys
import os
import time

SCRIPTS = [
    ("1b", "scripts/modeling/01b_derive_advanced_features.py",
     "Deriving advanced topographic features (TWI, TRI, TPI, curvatures...)"),
    ("1c", "scripts/modeling/01c_prepare_improved_dataset.py",
     "Preparing improved ML dataset with stratified sampling & BorderlineSMOTE"),
    ("2b", "scripts/modeling/02b_train_advanced_models.py",
     "Training advanced models with stratified K-fold cross-validation"),
    ("3b", "scripts/modeling/03b_predict_map_improved.py",
     "Generating improved landslide susceptibility map"),
]

def run_step(step_id, script_path, description):
    print("\n" + "=" * 70)
    print(f"STEP {step_id} — {description}")
    print("=" * 70)
    t_start = time.time()
    result = subprocess.run(
        [sys.executable, script_path],
        capture_output=False,   # let output stream to console
    )
    elapsed = time.time() - t_start
    if result.returncode == 0:
        print(f"\n  Step {step_id} completed in {elapsed:.1f}s")
        return True
    else:
        print(f"\n  Step {step_id} FAILED (return code {result.returncode})")
        return False


if __name__ == "__main__":
    print("=" * 70)
    print("MIZORAM LANDSLIDE — IMPROVED PIPELINE")
    print("=" * 70)
    print(f"Working directory: {os.getcwd()}")

    # Optional: allow skipping steps via command-line args
    # e.g. python run_improved_pipeline.py --skip 1b
    skip = set()
    if "--skip" in sys.argv:
        idx = sys.argv.index("--skip")
        for s in sys.argv[idx + 1:]:
            skip.add(s)

    failed = False
    for step_id, script_path, description in SCRIPTS:
        if step_id in skip:
            print(f"\n  Skipping step {step_id} (--skip {step_id})")
            continue
        if not os.path.exists(script_path):
            print(f"\n  ERROR: Script not found: {script_path}")
            failed = True
            break
        success = run_step(step_id, script_path, description)
        if not success:
            failed = True
            print(f"\n  Pipeline stopped at step {step_id}.")
            break

    print("\n" + "=" * 70)
    if failed:
        print("PIPELINE FAILED — see errors above.")
    else:
        print("PIPELINE COMPLETE!")
        print("Outputs:")
        outputs = [
            "data/derived/mizoram_twi.tif",
            "data/derived/mizoram_tri.tif",
            "data/derived/mizoram_tpi.tif",
            "data/processed/modeling/landslide_dataset_classic.csv",
            "data/processed/modeling/landslide_dataset_augmented.csv",
            "data/processed/modeling/results/model_comparison.csv",
            "data/processed/modeling/results/roc_all_models.png",
            "data/processed/modeling/results/feature_importance.png",
            "models/best_model.pkl",
            "data/final/mizoram_landslide_susceptibility_v2.tif",
        ]
        for path in outputs:
            exists = os.path.exists(path)
            status = "OK" if exists else "MISSING"
            print(f"  [{status:7s}] {path}")
    print("=" * 70)
