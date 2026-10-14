"""Train XGBoost fraud detection model with SHAP explanations."""

import os
import sys
import json
import pickle
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import (
    classification_report, roc_auc_score, precision_recall_curve,
    average_precision_score, confusion_matrix
)

try:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
except NameError:
    PROJECT_ROOT = os.getcwd()
sys.path.insert(0, os.path.join(PROJECT_ROOT, "pipelines"))

from gpu_utils import gpu_info, get_xgboost_gpu_params


def _read_data(directory, name):
    """Read Parquet if available, fall back to CSV."""
    parquet_path = os.path.join(directory, f"{name}.parquet")
    if os.path.exists(parquet_path):
        return pd.read_parquet(parquet_path)
    csv_path = os.path.join(directory, f"{name}.csv")
    if os.path.exists(csv_path):
        return pd.read_csv(csv_path)
    raise FileNotFoundError(f"No data file found for {name} in {directory}")


def load_data():
    processed_dir = os.path.join(PROJECT_ROOT, "data", "processed")

    train = _read_data(processed_dir, "train_features")
    val = _read_data(processed_dir, "val_features")
    test = _read_data(processed_dir, "test_features")

    with open(os.path.join(PROJECT_ROOT, "models", "feature_names.json")) as f:
        feature_names = json.load(f)

    available = [f for f in feature_names if f in train.columns]
    print(f"Using {len(available)} features: {available[:10]}...")
    return train, val, test, available


def train_model(train, val, feature_names):
    X_train = train[feature_names].values
    y_train = train["is_fraud"].values
    X_val = val[feature_names].values
    y_val = val["is_fraud"].values

    n_neg = (y_train == 0).sum()
    n_pos = (y_train == 1).sum()
    scale_pos_weight = n_neg / max(n_pos, 1)
    print(f"Class balance: {n_neg:,} negative, {n_pos:,} positive, scale_pos_weight={scale_pos_weight:.1f}")

    # QuantileDMatrix uses ~25% memory of float DMatrix with hist tree_method
    dtrain = xgb.QuantileDMatrix(X_train, label=y_train, feature_names=feature_names)
    dval = xgb.QuantileDMatrix(X_val, label=y_val, ref=dtrain, feature_names=feature_names)

    params = {
        "objective": "binary:logistic",
        "eval_metric": ["auc", "aucpr", "logloss"],
        "max_depth": 6,
        "learning_rate": 0.2,
        "scale_pos_weight": scale_pos_weight,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "min_child_weight": 5,
        "gamma": 1,
        "reg_alpha": 0.1,
        "reg_lambda": 1.0,
        "seed": 42,
    }
    # Apply GPU-specific params if available (tree_method + device)
    params.update(get_xgboost_gpu_params())
    print(f"XGBoost device: {params.get('device', 'cpu')} | tree_method: {params['tree_method']}")

    model = xgb.train(
        params, dtrain, num_boost_round=512,
        evals=[(dtrain, "train"), (dval, "val")],
        early_stopping_rounds=50, verbose_eval=50,
    )
    return model


def evaluate_model(model, test, feature_names):
    X_test = test[feature_names].values
    y_test = test["is_fraud"].values

    dtest = xgb.DMatrix(X_test, feature_names=feature_names)
    y_pred_proba = model.predict(dtest)
    y_pred = (y_pred_proba >= 0.5).astype(int)

    print("\n" + "=" * 50)
    print("Test Set Evaluation")
    print("=" * 50)

    auc = roc_auc_score(y_test, y_pred_proba)
    ap = average_precision_score(y_test, y_pred_proba)
    print(f"ROC AUC: {auc:.4f}")
    print(f"Average Precision: {ap:.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=["Legitimate", "Fraud"]))

    cm = confusion_matrix(y_test, y_pred)
    print(f"Confusion Matrix:\n{cm}")

    precision, recall, thresholds = precision_recall_curve(y_test, y_pred_proba)
    f1_scores = 2 * (precision * recall) / (precision + recall + 1e-8)
    optimal_idx = np.argmax(f1_scores)
    optimal_threshold = thresholds[optimal_idx] if optimal_idx < len(thresholds) else 0.5
    print(f"\nOptimal threshold (max F1): {optimal_threshold:.3f}")
    print(f"At optimal: Precision={precision[optimal_idx]:.3f}, Recall={recall[optimal_idx]:.3f}, F1={f1_scores[optimal_idx]:.3f}")

    return {"roc_auc": float(auc), "avg_precision": float(ap), "optimal_threshold": float(optimal_threshold)}


def compute_shap(model, train, feature_names):
    """Compute SHAP importance using XGBoost native pred_contribs (GPU-accelerated)."""
    X_sample = train[feature_names].sample(min(5000, len(train)), random_state=42)
    dmatrix = xgb.DMatrix(X_sample.values, feature_names=feature_names)

    # Use native pred_contribs instead of shap.TreeExplainer — works on GPU too
    shap_raw = model.predict(dmatrix, pred_contribs=True)  # (n_samples, n_features+1)
    shap_values = shap_raw[:, :-1]  # drop bias column

    importance = pd.DataFrame({
        "feature": feature_names,
        "mean_abs_shap": np.abs(shap_values).mean(axis=0),
    }).sort_values("mean_abs_shap", ascending=False)

    print("\nTop 15 Features by SHAP Importance:")
    print(importance.head(15).to_string(index=False))
    return importance


def save_artifacts(model, metrics, importance, feature_names):
    models_dir = os.path.join(PROJECT_ROOT, "models")
    os.makedirs(models_dir, exist_ok=True)

    model.save_model(os.path.join(models_dir, "xgboost_fraud.json"))
    with open(os.path.join(models_dir, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)
    importance.to_csv(os.path.join(models_dir, "feature_importance.csv"), index=False)
    print(f"\nArtifacts saved to {models_dir}/")


def main():
    print(f"Training pipeline | {gpu_info()}")
    train, val, test, feature_names = load_data()
    model = train_model(train, val, feature_names)
    metrics = evaluate_model(model, test, feature_names)
    importance = compute_shap(model, train, feature_names)
    save_artifacts(model, metrics, importance, feature_names)
    print("\nTraining complete.")


if __name__ == "__main__":
    main()
