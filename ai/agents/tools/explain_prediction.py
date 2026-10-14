"""Generate natural language SHAP explanations for fraud predictions."""

import os
import sys
import sqlite3

try:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
except NameError:
    PROJECT_ROOT = os.getcwd()
sys.path.insert(0, os.path.join(PROJECT_ROOT, "app", "backend", "model_serving"))

from model_utils import score_transaction as _score

DB_PATH = os.path.join(PROJECT_ROOT, "data", "transactions.db")

FEATURE_LABELS = {
    "amount": "Transaction Amount",
    "amount_scaled": "Transaction Amount (scaled)",
    "hour": "Hour of Day",
    "minute": "Minute",
    "mcc": "Merchant Category",
    "merchant_state_encoded": "Merchant State",
    "merchant_name_encoded": "Merchant",
    "merchant_fraud_rate": "Merchant's Historical Fraud Rate",
    "mcc_fraud_rate": "Category Fraud Rate",
    "state_fraud_rate": "State Fraud Rate",
    "merchant_country_encoded": "Merchant Country",
    "country_fraud_rate": "Country Fraud Rate",
    "is_cross_border": "Cross-Border Transaction",
    "tx_count_last_1h": "Transactions in Last Hour",
    "tx_count_last_24h": "Transactions in Last 24h",
    "amount_last_24h": "Amount Spent in Last 24h",
    "tx_amount_zscore_user": "Amount vs User's Average (z-score)",
    "tx_amount_zscore_merchant": "Amount vs Merchant's Average (z-score)",
    "tx_hour_sin": "Time of Day (cyclical)",
    "tx_hour_cos": "Time of Day (cyclical)",
    "amount_to_avg_ratio": "Amount / User's Average",
    "is_out_of_state": "Out-of-State Transaction",
    "chip_Chip Transaction": "Used Chip Reader",
    "chip_Online Transaction": "Online Transaction",
    "chip_Swipe Transaction": "Swiped Card",
    "time_minutes": "Time of Day (minutes)",
}


def explain_prediction(transaction_id):
    if isinstance(transaction_id, str) and transaction_id.isdigit():
        transaction_id = int(transaction_id)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM transactions WHERE transaction_id = ?",
        (transaction_id,)
    ).fetchone()
    conn.close()

    if row is None:
        return {"error": f"Transaction {transaction_id} not found"}

    features = dict(row)
    result = _score(features, explain=True)

    if "explanation" not in result:
        return {"error": "Could not generate explanation"}

    explanation = result["explanation"]
    top_features = explanation["top_features"]

    risk_level = result["risk_level"]
    score = result["fraud_score"]

    narrative_parts = []
    narrative_parts.append(
        f"Transaction #{transaction_id} received a fraud score of {score:.1%} ({risk_level} risk)."
    )

    if top_features:
        narrative_parts.append("\nKey factors influencing this prediction:")
        for i, feat in enumerate(top_features[:7], 1):
            label = FEATURE_LABELS.get(feat["feature"], feat["feature"])
            direction = "+" if feat["shap_value"] > 0 else "-"
            impact = "increasing" if feat["shap_value"] > 0 else "decreasing"
            narrative_parts.append(
                f"  {i}. {label} = {feat['value']:.2f} "
                f"({direction}{abs(feat['shap_value']):.3f}, {impact} fraud risk)"
            )

    narrative = "\n".join(narrative_parts)

    return {
        "transaction_id": transaction_id,
        "fraud_score": result["fraud_score"],
        "risk_level": risk_level,
        "actual_fraud": bool(features.get("is_fraud", 0)),
        "narrative": narrative,
        "top_features": top_features[:10],
        "base_value": explanation["base_value"],
        "transaction_summary": {
            "amount": features.get("amount"),
            "merchant": features.get("merchant_name"),
            "country": features.get("merchant_country"),
            "state": features.get("merchant_state"),
            "hour": features.get("hour"),
            "use_chip": features.get("use_chip"),
        },
    }
