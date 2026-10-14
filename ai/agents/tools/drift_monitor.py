"""Compute drift metrics comparing feature distributions and model performance across time periods."""

import os
import sys
import json
import re
import sqlite3
import math

import numpy as np
import xgboost as xgb
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score

try:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
except NameError:
    PROJECT_ROOT = os.getcwd()
DB_PATH = os.path.join(PROJECT_ROOT, "data", "transactions.db")
FEATURE_NAMES_PATH = os.path.join(PROJECT_ROOT, "models", "feature_names.json")
MODEL_PATH = os.path.join(PROJECT_ROOT, "models", "xgboost_fraud.json")
METRICS_PATH = os.path.join(PROJECT_ROOT, "models", "metrics.json")

_model = None
_feature_names = None


def _get_model():
    global _model
    if _model is None:
        _model = xgb.Booster()
        _model.load_model(MODEL_PATH)
    return _model


def _get_feature_names():
    global _feature_names
    if _feature_names is None:
        with open(FEATURE_NAMES_PATH) as f:
            _feature_names = json.load(f)
    return _feature_names


def _get_db_columns():
    """Return the set of column names in the transactions table."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("PRAGMA table_info(transactions)")
    columns = {row[1] for row in cursor.fetchall()}
    conn.close()
    return columns


def _get_driftable_features():
    """Return the list of model features that exist as columns in the DB."""
    feature_names = _get_feature_names()
    db_columns = _get_db_columns()
    return [f for f in feature_names if f in db_columns]


_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _load_feature_data(year, features):
    """Load numeric feature data for a given year from the database."""
    # Defense-in-depth: features come from a JSON file that model promotion can
    # rewrite, so refuse anything that isn't a plain SQL identifier.
    bad = [f for f in features if not _IDENTIFIER_RE.match(f)]
    if bad:
        raise ValueError(f"Invalid feature name(s) in feature_names.json: {bad}")
    conn = sqlite3.connect(DB_PATH)
    cols = ", ".join(f'"{f}"' for f in features)
    query = f"SELECT {cols} FROM transactions WHERE year = ?"
    cursor = conn.execute(query, (year,))
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        return np.empty((0, len(features)))
    return np.array(rows, dtype=np.float64)


def _compute_psi(reference, current, n_bins=10, epsilon=1e-6):
    """Compute Population Stability Index between two 1-D arrays.

    Buckets are quantile-based, derived from the reference distribution.
    """
    # Compute quantile bin edges from the reference distribution
    quantiles = np.linspace(0, 100, n_bins + 1)
    bin_edges = np.percentile(reference, quantiles)
    # Ensure unique, monotonically increasing edges
    bin_edges = np.unique(bin_edges)
    if len(bin_edges) < 2:
        # Constant feature -- no drift measurable
        return 0.0

    ref_counts = np.histogram(reference, bins=bin_edges)[0]
    cur_counts = np.histogram(current, bins=bin_edges)[0]

    ref_pct = ref_counts / max(len(reference), 1) + epsilon
    cur_pct = cur_counts / max(len(current), 1) + epsilon

    psi = float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))
    return psi


def _classify_drift(psi_value):
    if psi_value < 0.1:
        return "no_drift"
    elif psi_value <= 0.25:
        return "moderate"
    else:
        return "significant"


def compute_drift_report(reference_year=2018, current_year=2020):
    """Compare feature distributions between two year windows.

    For each model feature that exists in the DB, computes Population Stability
    Index (PSI) and basic distribution statistics.
    """
    driftable_features = _get_driftable_features()

    ref_data = _load_feature_data(reference_year, driftable_features)
    cur_data = _load_feature_data(current_year, driftable_features)

    reference_count = ref_data.shape[0]
    current_count = cur_data.shape[0]
    if reference_count == 0 or current_count == 0:
        empty = reference_year if reference_count == 0 else current_year
        return {
            "error": f"No transactions found for year {empty} — "
                     f"pick years that exist in the data (see /api/dashboard/date-range).",
        }

    feature_reports = []
    for i, feature in enumerate(driftable_features):
        ref_col = ref_data[:, i]
        cur_col = cur_data[:, i]

        psi = _compute_psi(ref_col, cur_col)
        drift_level = _classify_drift(psi)

        feature_reports.append({
            "feature": feature,
            "psi": round(psi, 6),
            "drift_level": drift_level,
            "ref_mean": round(float(np.mean(ref_col)), 6),
            "ref_std": round(float(np.std(ref_col)), 6),
            "cur_mean": round(float(np.mean(cur_col)), 6),
            "cur_std": round(float(np.std(cur_col)), 6),
        })

    # Sort by PSI descending
    feature_reports.sort(key=lambda x: x["psi"], reverse=True)

    # Compute summary
    total_features = len(feature_reports)
    counts = {"no_drift": 0, "moderate": 0, "significant": 0}
    for fr in feature_reports:
        counts[fr["drift_level"]] += 1

    if counts["significant"] > 0:
        overall_status = "critical"
    elif counts["moderate"] > 0:
        overall_status = "warning"
    else:
        overall_status = "healthy"

    return {
        "reference_year": reference_year,
        "current_year": current_year,
        "reference_count": reference_count,
        "current_count": current_count,
        "features": feature_reports,
        "summary": {
            "total_features": total_features,
            "no_drift": counts["no_drift"],
            "moderate": counts["moderate"],
            "significant": counts["significant"],
            "overall_status": overall_status,
        },
    }


def _score_year(year):
    """Load all transactions for a year, score them with the XGBoost model.

    Returns (labels, scores) as numpy arrays.
    """
    feature_names = _get_feature_names()
    model = _get_model()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM transactions WHERE year = ?", (year,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return np.array([]), np.array([])

    labels = np.array([row["is_fraud"] for row in rows], dtype=np.int32)

    # Build feature matrix, defaulting missing features to 0.0
    matrix = np.zeros((len(rows), len(feature_names)), dtype=np.float32)
    for i, row in enumerate(rows):
        row_dict = dict(row)
        for j, fname in enumerate(feature_names):
            matrix[i, j] = float(row_dict.get(fname, 0.0))

    dmatrix = xgb.DMatrix(matrix, feature_names=feature_names)
    scores = model.predict(dmatrix)

    return labels, scores


def _get_available_years():
    """Return sorted list of distinct years in the database."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT DISTINCT year FROM transactions ORDER BY year").fetchall()
    conn.close()
    return [r[0] for r in rows]


def compute_performance_over_time():
    """Compute model performance metrics per year.

    For each year computes fraud rate, average fraud score, precision, recall,
    F1 (at threshold 0.5), and AUC-ROC.
    """
    periods = []
    for year in _get_available_years():
        labels, scores = _score_year(year)

        if len(labels) == 0:
            periods.append({
                "year": year,
                "count": 0,
                "fraud_rate": 0.0,
                "avg_score": 0.0,
                "precision": 0.0,
                "recall": 0.0,
                "f1": 0.0,
                "auc": 0.0,
            })
            continue

        predictions = (scores >= 0.5).astype(int)
        fraud_rate = float(np.mean(labels))
        avg_score = float(np.mean(scores))

        # Guard against edge cases where only one class is present
        unique_labels = np.unique(labels)
        if len(unique_labels) < 2:
            auc = 0.0
        else:
            auc = float(roc_auc_score(labels, scores))

        periods.append({
            "year": year,
            "count": int(len(labels)),
            "fraud_rate": round(fraud_rate, 6),
            "avg_score": round(avg_score, 6),
            "precision": round(float(precision_score(labels, predictions, zero_division=0)), 6),
            "recall": round(float(recall_score(labels, predictions, zero_division=0)), 6),
            "f1": round(float(f1_score(labels, predictions, zero_division=0)), 6),
            "auc": round(auc, 6),
        })

    return {"periods": periods}


def compute_score_distribution(reference_year=2018, current_year=2020):
    """Get prediction score distribution for reference and current periods.

    Returns histogram data (10 bins from 0 to 1) along with per-bin fraud rates.
    """
    bin_edges = np.linspace(0.0, 1.0, 11)  # 10 bins, 11 edges

    ref_labels, ref_scores = _score_year(reference_year)
    cur_labels, cur_scores = _score_year(current_year)

    ref_counts = np.histogram(ref_scores, bins=bin_edges)[0]
    cur_counts = np.histogram(cur_scores, bins=bin_edges)[0]

    # Compute fraud rate per score bin
    ref_fraud_rate_per_bin = []
    cur_fraud_rate_per_bin = []

    ref_bin_indices = np.digitize(ref_scores, bin_edges) - 1
    cur_bin_indices = np.digitize(cur_scores, bin_edges) - 1

    for b in range(10):
        # Reference
        mask_ref = ref_bin_indices == b
        if mask_ref.sum() > 0:
            ref_fraud_rate_per_bin.append(round(float(np.mean(ref_labels[mask_ref])), 6))
        else:
            ref_fraud_rate_per_bin.append(0.0)

        # Current
        mask_cur = cur_bin_indices == b
        if mask_cur.sum() > 0:
            cur_fraud_rate_per_bin.append(round(float(np.mean(cur_labels[mask_cur])), 6))
        else:
            cur_fraud_rate_per_bin.append(0.0)

    return {
        "reference_year": reference_year,
        "current_year": current_year,
        "bins": [round(float(e), 1) for e in bin_edges],
        "reference_counts": [int(c) for c in ref_counts],
        "current_counts": [int(c) for c in cur_counts],
        "reference_fraud_rate_per_bin": ref_fraud_rate_per_bin,
        "current_fraud_rate_per_bin": cur_fraud_rate_per_bin,
    }
