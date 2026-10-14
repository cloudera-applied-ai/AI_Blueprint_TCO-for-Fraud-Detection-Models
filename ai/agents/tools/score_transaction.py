"""Score transactions for fraud using the XGBoost model."""

import os
import sys
import sqlite3

try:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
except NameError:
    PROJECT_ROOT = os.getcwd()
sys.path.insert(0, os.path.join(PROJECT_ROOT, "app", "backend", "model_serving"))

from model_utils import score_transaction as _score, get_feature_names

DB_PATH = os.path.join(PROJECT_ROOT, "data", "transactions.db")


def _load_transaction_features(transaction_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM transactions WHERE transaction_id = ?",
        (transaction_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def score_transaction(transaction_id=None, transaction_data=None, explain=True):
    if isinstance(transaction_id, str) and transaction_id.isdigit():
        transaction_id = int(transaction_id)
    if isinstance(explain, str):
        explain = explain.lower() in ("true", "1", "yes")
    if transaction_id is not None:
        features = _load_transaction_features(transaction_id)
        if features is None:
            return {"error": f"Transaction {transaction_id} not found"}
    elif transaction_data is not None:
        features = transaction_data
    else:
        return {"error": "Provide either transaction_id or transaction_data"}

    result = _score(features, explain=explain)

    if transaction_id is not None:
        result["transaction_id"] = transaction_id
        result["actual_fraud"] = bool(features.get("is_fraud", 0))

    return result
