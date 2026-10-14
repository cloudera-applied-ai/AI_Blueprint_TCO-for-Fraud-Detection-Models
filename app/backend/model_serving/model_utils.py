"""Load model and compute SHAP explanations.

Uses XGBoost's built-in pred_contribs for GPU-accelerated SHAP values
instead of the shap library's TreeExplainer (which is CPU-only).
"""

import os
import json
import numpy as np
import xgboost as xgb

try:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
except NameError:
    PROJECT_ROOT = os.getcwd()

_model = None
_feature_names = None


def get_model():
    global _model
    if _model is None:
        model_path = os.path.join(PROJECT_ROOT, "models", "xgboost_fraud.json")
        _model = xgb.Booster()
        _model.load_model(model_path)
    return _model


def get_feature_names():
    global _feature_names
    if _feature_names is None:
        path = os.path.join(PROJECT_ROOT, "models", "feature_names.json")
        with open(path) as f:
            _feature_names = json.load(f)
    return _feature_names


def score_transaction(features_dict, explain=False):
    model = get_model()
    feature_names = get_feature_names()

    values = []
    for f in feature_names:
        values.append(features_dict.get(f, 0.0))
    values = np.array([values], dtype=np.float32)

    dmatrix = xgb.DMatrix(values, feature_names=feature_names)
    fraud_score = float(model.predict(dmatrix)[0])

    result = {
        "fraud_score": round(fraud_score, 4),
        "is_fraud": fraud_score >= 0.5,
        "risk_level": "HIGH" if fraud_score >= 0.7 else "MEDIUM" if fraud_score >= 0.3 else "LOW",
    }

    if explain:
        # Use XGBoost native pred_contribs — works on both GPU and CPU,
        # and is faster than shap.TreeExplainer (no pickle dependency)
        shap_raw = model.predict(dmatrix, pred_contribs=True)  # shape: (1, n_features+1)
        shap_values = shap_raw[0, :-1]  # feature contributions
        base_value = float(shap_raw[0, -1])  # bias term

        feature_contributions = []
        for i, fname in enumerate(feature_names):
            sv = float(shap_values[i])
            if abs(sv) > 0.001:
                feature_contributions.append({
                    "feature": fname,
                    "value": float(values[0][i]),
                    "shap_value": round(sv, 4),
                    "direction": "increases fraud risk" if sv > 0 else "decreases fraud risk",
                })
        feature_contributions.sort(key=lambda x: abs(x["shap_value"]), reverse=True)

        result["explanation"] = {
            "base_value": round(base_value, 4),
            "top_features": feature_contributions[:10],
            "shap_values_all": {
                fname: round(float(shap_values[i]), 4)
                for i, fname in enumerate(feature_names)
            },
        }

    return result
