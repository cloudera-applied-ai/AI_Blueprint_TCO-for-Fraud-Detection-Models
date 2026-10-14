"""Composite merchant investigation: stitches trace + patterns + transactions + geo into a single report payload.

This intentionally calls the existing tool functions instead of re-implementing the SQL,
so improvements to the underlying tools flow through automatically.
"""

import os
import sqlite3

from .trace_fraud_network import trace_fraud_network
from .alert_patterns import detect_alert_patterns
from .query_transactions import query_transactions

try:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
except NameError:
    PROJECT_ROOT = os.getcwd()
DB_PATH = os.path.join(PROJECT_ROOT, "data", "transactions.db")


def _table_columns(conn, table):
    cursor = conn.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}


def _resolve_canonical_name(conn, merchant_name):
    """Find the merchant_name with the most fraud transactions matching the LIKE pattern.

    Lets the agent pass a partial / fuzzy name and still pin to a real merchant.
    """
    row = conn.execute(
        """
        SELECT merchant_name
        FROM transactions
        WHERE merchant_name LIKE ?
        GROUP BY merchant_name
        ORDER BY SUM(is_fraud) DESC, COUNT(*) DESC
        LIMIT 1
        """,
        (f"%{merchant_name}%",),
    ).fetchone()
    return row[0] if row else None


def _kpis(conn, merchant_name):
    row = conn.execute(
        """
        SELECT COUNT(*) AS total_transactions,
               SUM(is_fraud) AS fraud_transactions,
               ROUND(AVG(is_fraud) * 100, 2) AS fraud_rate_pct,
               ROUND(SUM(CASE WHEN is_fraud=1 THEN amount ELSE 0 END), 2) AS fraud_amount,
               ROUND(SUM(amount), 2) AS total_amount,
               COUNT(DISTINCT user_id) AS unique_users,
               COUNT(DISTINCT CASE WHEN is_fraud=1 THEN user_id END) AS fraud_users,
               MIN(year * 10000 + month * 100 + day) AS first_seen,
               MAX(year * 10000 + month * 100 + day) AS last_seen
        FROM transactions
        WHERE merchant_name = ?
        """,
        (merchant_name,),
    ).fetchone()
    return {k: row[k] for k in row.keys()} if row else {}


def _geographic_spread(conn, merchant_name):
    has_country = "merchant_country" in _table_columns(conn, "transactions")
    country_col = ", merchant_country" if has_country else ""
    rows = conn.execute(
        f"""
        SELECT merchant_state{country_col},
               COUNT(*) AS total,
               SUM(is_fraud) AS fraud_count,
               ROUND(SUM(CASE WHEN is_fraud=1 THEN amount ELSE 0 END), 2) AS fraud_amount
        FROM transactions
        WHERE merchant_name = ?
        GROUP BY merchant_state{country_col}
        ORDER BY fraud_count DESC, total DESC
        LIMIT 20
        """,
        (merchant_name,),
    ).fetchall()
    return [dict(r) for r in rows]


def _time_series(conn, merchant_name):
    rows = conn.execute(
        """
        SELECT year, month,
               COUNT(*) AS total,
               SUM(is_fraud) AS fraud_count,
               ROUND(SUM(CASE WHEN is_fraud=1 THEN amount ELSE 0 END), 2) AS fraud_amount
        FROM transactions
        WHERE merchant_name = ?
        GROUP BY year, month
        ORDER BY year, month
        """,
        (merchant_name,),
    ).fetchall()
    return [dict(r) for r in rows]


def investigate_merchant(merchant_name=None, max_counterparties=25, max_transactions=20):
    if not merchant_name or not isinstance(merchant_name, str):
        return {"error": "Provide a merchant_name to investigate."}

    if isinstance(max_counterparties, str) and max_counterparties.isdigit():
        max_counterparties = int(max_counterparties)
    if isinstance(max_transactions, str) and max_transactions.isdigit():
        max_transactions = int(max_transactions)
    max_counterparties = max(1, min(int(max_counterparties or 25), 100))
    max_transactions = max(1, min(int(max_transactions or 20), 100))

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        canonical = _resolve_canonical_name(conn, merchant_name)
        if not canonical:
            return {
                "error": (
                    f"No merchant matched '{merchant_name}'. Call "
                    "get_risk_dashboard(group_by='merchant') and use a real merchant_name."
                )
            }
        kpis = _kpis(conn, canonical)
        geo = _geographic_spread(conn, canonical)
        timeline = _time_series(conn, canonical)
    finally:
        conn.close()

    trace = trace_fraud_network(
        merchant_name=canonical,
        direction="merchant_to_users",
        fraud_only=True,
        max_counterparties=max_counterparties,
    )
    patterns = detect_alert_patterns(merchant_name=canonical, pattern_type="all")
    top_fraud = query_transactions(
        merchant_name=canonical, is_fraud=True, limit=max_transactions, order_by="amount_desc",
    )

    return {
        "merchant_name": canonical,
        "kpis": kpis,
        "geographic_spread": geo,
        "time_series": timeline,
        "trace": trace if "error" not in trace else {"error": trace["error"]},
        "patterns": patterns,
        "top_fraud_transactions": top_fraud.get("transactions", []),
        "top_fraud_count": top_fraud.get("total_matching", 0),
    }
