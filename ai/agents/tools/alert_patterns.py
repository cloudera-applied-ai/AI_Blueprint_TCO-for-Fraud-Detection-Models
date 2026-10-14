"""Detect fraud alert patterns: velocity, geo-anomaly, amount spikes."""

import os
import sqlite3

try:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
except NameError:
    PROJECT_ROOT = os.getcwd()
DB_PATH = os.path.join(PROJECT_ROOT, "data", "transactions.db")


# A short merchant filter can match a large fraction of the table; cap what we
# pull into memory (the detectors below run nested passes over this list).
MAX_ANALYZED_TRANSACTIONS = 5000


def _get_user_transactions(conn, user_id):
    rows = conn.execute("""
        SELECT * FROM transactions WHERE user_id = ?
        ORDER BY year, month, day, hour, minute
        LIMIT ?
    """, (user_id, MAX_ANALYZED_TRANSACTIONS)).fetchall()
    return [dict(r) for r in rows]


def _get_merchant_transactions(conn, merchant_name):
    rows = conn.execute("""
        SELECT * FROM transactions WHERE merchant_name LIKE ?
        ORDER BY year, month, day, hour, minute
        LIMIT ?
    """, (f"%{merchant_name}%", MAX_ANALYZED_TRANSACTIONS)).fetchall()
    return [dict(r) for r in rows]


def _detect_velocity(transactions):
    alerts = []
    for i in range(len(transactions)):
        cluster = [transactions[i]]
        t1 = transactions[i]
        t1_mins = t1["hour"] * 60 + t1["minute"]
        for j in range(i + 1, min(i + 10, len(transactions))):
            t2 = transactions[j]
            if t1["year"] == t2["year"] and t1["month"] == t2["month"] and t1["day"] == t2["day"]:
                t2_mins = t2["hour"] * 60 + t2["minute"]
                if abs(t2_mins - t1_mins) <= 15:
                    cluster.append(t2)
        if len(cluster) >= 3:
            total = sum(t["amount"] for t in cluster)
            alerts.append({
                "type": "velocity",
                "severity": "HIGH" if len(cluster) >= 4 else "MEDIUM",
                "description": f"{len(cluster)} transactions within 15 minutes",
                "date": f"{t1['year']}-{t1['month']:02d}-{t1['day']:02d}",
                "total_amount": round(total, 2),
                "transaction_ids": [t["transaction_id"] for t in cluster],
                "fraud_in_cluster": sum(1 for t in cluster if t.get("is_fraud")),
            })
    seen_ids = set()
    unique_alerts = []
    for a in alerts:
        key = frozenset(a["transaction_ids"])
        if key not in seen_ids:
            seen_ids.add(key)
            unique_alerts.append(a)
    return unique_alerts


def _detect_geo_anomaly(transactions):
    if not transactions:
        return []
    # Determine home country and home state (most frequent)
    country_counts = {}
    state_counts = {}
    for t in transactions:
        c = t.get("merchant_country", "")
        s = t.get("merchant_state", "")
        country_counts[c] = country_counts.get(c, 0) + 1
        state_counts[s] = state_counts.get(s, 0) + 1
    home_country = max(country_counts, key=country_counts.get) if country_counts else ""
    home_state = max(state_counts, key=state_counts.get)
    alerts = []
    for t in transactions:
        tx_country = t.get("merchant_country", "")
        tx_state = t.get("merchant_state", "")
        is_cross_border = tx_country and home_country and tx_country != home_country
        is_out_of_state = tx_state != home_state

        if (is_cross_border or is_out_of_state) and t["amount"] > 200:
            if is_cross_border:
                severity = "HIGH"
                desc = f"Cross-border transaction in {tx_country}/{tx_state} (home: {home_country}/{home_state}), amount ${t['amount']:.2f}"
            else:
                severity = "HIGH" if t["amount"] > 1000 else "MEDIUM"
                desc = f"Out-of-state transaction in {tx_state} (home: {home_state}), amount ${t['amount']:.2f}"
            alerts.append({
                "type": "geo_anomaly",
                "severity": severity,
                "description": desc,
                "transaction_id": t["transaction_id"],
                "amount": t["amount"],
                "country": tx_country,
                "state": tx_state,
                "home_country": home_country,
                "home_state": home_state,
                "is_fraud": bool(t.get("is_fraud")),
            })
    return alerts[:20]


def _detect_amount_spike(transactions):
    if len(transactions) < 5:
        return []
    amounts = [t["amount"] for t in transactions]
    mean_amt = sum(amounts) / len(amounts)
    std_amt = (sum((a - mean_amt) ** 2 for a in amounts) / len(amounts)) ** 0.5
    if std_amt == 0:
        return []
    alerts = []
    for t in transactions:
        zscore = (t["amount"] - mean_amt) / std_amt
        if zscore > 3:
            alerts.append({
                "type": "amount_spike",
                "severity": "HIGH" if zscore > 5 else "MEDIUM",
                "description": f"Amount ${t['amount']:.2f} is {zscore:.1f}x standard deviations above average (${mean_amt:.2f})",
                "transaction_id": t["transaction_id"],
                "amount": t["amount"],
                "zscore": round(zscore, 2),
                "user_avg": round(mean_amt, 2),
                "is_fraud": bool(t.get("is_fraud")),
            })
    return sorted(alerts, key=lambda x: x["zscore"], reverse=True)[:10]


def _detect_late_night(transactions):
    alerts = []
    for t in transactions:
        if t["hour"] < 5 and t["amount"] > 100:
            alerts.append({
                "type": "late_night",
                "severity": "MEDIUM" if t["amount"] < 500 else "HIGH",
                "description": f"Late-night transaction at {t['hour']:02d}:{t.get('minute', 0):02d}, amount ${t['amount']:.2f}",
                "transaction_id": t["transaction_id"],
                "amount": t["amount"],
                "hour": t["hour"],
                "is_fraud": bool(t.get("is_fraud")),
            })
    return sorted(alerts, key=lambda x: x["amount"], reverse=True)[:10]


def detect_alert_patterns(user_id=None, merchant_name=None, pattern_type="all"):
    if isinstance(user_id, str) and user_id.isdigit():
        user_id = int(user_id)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    if user_id is not None:
        transactions = _get_user_transactions(conn, user_id)
        entity = f"User {user_id}"
    elif merchant_name:
        transactions = _get_merchant_transactions(conn, merchant_name)
        entity = f"Merchant '{merchant_name}'"
    else:
        conn.close()
        return {"error": "Provide either user_id or merchant_name"}
    conn.close()
    if not transactions:
        return {"entity": entity, "alerts": [], "message": "No transactions found"}

    alerts = []
    if pattern_type in ("velocity", "all"):
        alerts.extend(_detect_velocity(transactions))
    if pattern_type in ("geo_anomaly", "all"):
        alerts.extend(_detect_geo_anomaly(transactions))
    if pattern_type in ("amount_spike", "all"):
        alerts.extend(_detect_amount_spike(transactions))
    if pattern_type in ("late_night", "all"):
        alerts.extend(_detect_late_night(transactions))

    severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    alerts.sort(key=lambda x: severity_order.get(x.get("severity", "LOW"), 2))

    summary = {
        "high": sum(1 for a in alerts if a.get("severity") == "HIGH"),
        "medium": sum(1 for a in alerts if a.get("severity") == "MEDIUM"),
        "total_transactions_analyzed": len(transactions),
    }
    return {"entity": entity, "summary": summary, "alerts": alerts[:25]}
