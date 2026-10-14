"""Threshold analysis: batch score transactions and compute precision/recall curves."""

import os
import sys
import sqlite3
import numpy as np
import xgboost as xgb

try:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
except NameError:
    PROJECT_ROOT = os.getcwd()
sys.path.insert(0, os.path.join(PROJECT_ROOT, "app", "backend", "model_serving"))

from model_utils import get_model, get_feature_names

DB_PATH = os.path.join(PROJECT_ROOT, "data", "transactions.db")


def get_threshold_analysis(sample_size=5000):
    """Score a sample of transactions and compute precision/recall at various thresholds."""
    model = get_model()
    feature_names = get_feature_names()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Get a balanced sample: half fraud, half legitimate
    fraud_rows = conn.execute(
        "SELECT * FROM transactions WHERE is_fraud = 1 ORDER BY RANDOM() LIMIT ?",
        (sample_size // 2,),
    ).fetchall()

    legit_rows = conn.execute(
        "SELECT * FROM transactions WHERE is_fraud = 0 ORDER BY RANDOM() LIMIT ?",
        (sample_size // 2,),
    ).fetchall()

    conn.close()

    all_rows = fraud_rows + legit_rows
    if not all_rows:
        return {"error": "No transactions found"}

    # Build feature matrix
    X = np.zeros((len(all_rows), len(feature_names)), dtype=np.float32)
    y_true = np.zeros(len(all_rows), dtype=np.int32)

    for i, row in enumerate(all_rows):
        d = dict(row)
        for j, f in enumerate(feature_names):
            val = d.get(f, 0.0)
            X[i, j] = float(val) if val is not None else 0.0
        y_true[i] = int(d.get("is_fraud", 0))

    # Batch score
    dmatrix = xgb.DMatrix(X, feature_names=feature_names)
    y_scores = model.predict(dmatrix)

    # Compute metrics at various thresholds
    thresholds = [i / 100 for i in range(5, 96, 5)]
    curve = []

    for t in thresholds:
        y_pred = (y_scores >= t).astype(int)
        tp = int(((y_pred == 1) & (y_true == 1)).sum())
        fp = int(((y_pred == 1) & (y_true == 0)).sum())
        tn = int(((y_pred == 0) & (y_true == 0)).sum())
        fn = int(((y_pred == 0) & (y_true == 1)).sum())

        precision = tp / max(tp + fp, 1)
        recall = tp / max(tp + fn, 1)
        f1 = 2 * precision * recall / max(precision + recall, 1e-8)

        curve.append({
            "threshold": round(t, 2),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "tp": tp,
            "fp": fp,
            "tn": tn,
            "fn": fn,
            "flagged": tp + fp,
            "missed": fn,
            "total": len(all_rows),
        })

    # Score distribution histogram
    bins = [i / 20 for i in range(21)]  # 0.0, 0.05, ..., 1.0
    fraud_hist = np.histogram(y_scores[y_true == 1], bins=bins)[0].tolist()
    legit_hist = np.histogram(y_scores[y_true == 0], bins=bins)[0].tolist()

    distribution = []
    for i in range(len(bins) - 1):
        distribution.append({
            "bin": f"{bins[i]:.2f}-{bins[i+1]:.2f}",
            "bin_start": round(bins[i], 2),
            "fraud": fraud_hist[i],
            "legitimate": legit_hist[i],
        })

    return {
        "curve": curve,
        "distribution": distribution,
        "sample_size": len(all_rows),
        "fraud_count": int(y_true.sum()),
        "legit_count": int((y_true == 0).sum()),
        "current_threshold": 0.5,
    }
