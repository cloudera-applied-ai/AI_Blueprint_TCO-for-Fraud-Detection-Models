"""Standalone model evaluation with detailed metrics."""

import os
import json
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import (
    classification_report, roc_auc_score,
    average_precision_score,
)

try:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
except NameError:
    PROJECT_ROOT = os.getcwd()


def main():
    models_dir = os.path.join(PROJECT_ROOT, "models")
    model = xgb.Booster()
    model.load_model(os.path.join(models_dir, "xgboost_fraud.json"))

    with open(os.path.join(models_dir, "feature_names.json")) as f:
        feature_names = json.load(f)

    test = pd.read_csv(os.path.join(PROJECT_ROOT, "data", "processed", "test_features.csv"))
    available = [f for f in feature_names if f in test.columns]

    X_test = test[available].values
    y_test = test["is_fraud"].values
    dtest = xgb.DMatrix(X_test, feature_names=available)
    y_proba = model.predict(dtest)

    print("=" * 60)
    print("Model Evaluation Report")
    print("=" * 60)

    for threshold in [0.3, 0.5, 0.7]:
        y_pred = (y_proba >= threshold).astype(int)
        print(f"\n--- Threshold: {threshold} ---")
        print(classification_report(y_test, y_pred, target_names=["Legitimate", "Fraud"]))

    auc = roc_auc_score(y_test, y_proba)
    ap = average_precision_score(y_test, y_proba)
    print(f"\nROC AUC: {auc:.4f}")
    print(f"Average Precision (PR AUC): {ap:.4f}")

    results = {
        "roc_auc": float(auc),
        "avg_precision": float(ap),
        "n_test_samples": len(y_test),
        "n_test_fraud": int(y_test.sum()),
        "fraud_rate": float(y_test.mean()),
    }

    with open(os.path.join(models_dir, "evaluation_results.json"), "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nEvaluation results saved to {models_dir}/evaluation_results.json")


if __name__ == "__main__":
    main()
