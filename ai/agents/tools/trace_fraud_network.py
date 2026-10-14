"""Trace fraud relationships between merchants and customers (and back).

Given a seed merchant or user, walks one hop through the transactions graph
and returns the connected counterparties with fraud-overlap metrics so the
agent can describe the fraud network in natural language and the UI can draw
a bipartite visualization.
"""

import os
import sqlite3

try:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
except NameError:
    PROJECT_ROOT = os.getcwd()

DB_PATH = os.path.join(PROJECT_ROOT, "data", "transactions.db")

# Names of sibling tools — small LLMs occasionally pass one of these as merchant_name
# (treating the function name as the value). Catch it explicitly so the agent gets a
# self-correcting hint instead of a generic "no merchant matched" message.
_TOOL_NAME_BLOCKLIST = {
    "get_risk_dashboard", "query_transactions", "score_transaction",
    "explain_prediction", "detect_alert_patterns", "analyze_threshold",
    "monitor_drift", "trace_fraud_network",
}


def _table_columns(conn, table):
    cursor = conn.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}


def _resolve_direction(direction, merchant_name, user_id):
    # Override when direction contradicts the available arguments —
    # small LLMs frequently confuse the two directions.
    if merchant_name and user_id is None:
        return "merchant_to_users"
    if user_id is not None and not merchant_name:
        return "user_to_merchants"
    if direction and direction != "auto":
        return direction
    # Both provided or neither — default to merchant-first if merchant given
    if merchant_name:
        return "merchant_to_users"
    return "user_to_merchants"


def _fetch_seed_merchant(conn, merchant_name):
    row = conn.execute(
        """
        SELECT merchant_name,
               COUNT(*) AS total_transactions,
               SUM(is_fraud) AS fraud_transactions,
               SUM(CASE WHEN is_fraud = 1 THEN amount ELSE 0 END) AS fraud_amount,
               COUNT(DISTINCT user_id) AS unique_users,
               MIN(year * 10000 + month * 100 + day) AS first_seen,
               MAX(year * 10000 + month * 100 + day) AS last_seen
        FROM transactions
        WHERE merchant_name LIKE ?
        """,
        (f"%{merchant_name}%",),
    ).fetchone()
    if not row or not row["merchant_name"]:
        return None
    return dict(row)


def _fetch_seed_user(conn, user_id):
    row = conn.execute(
        """
        SELECT user_id,
               COUNT(*) AS total_transactions,
               SUM(is_fraud) AS fraud_transactions,
               SUM(CASE WHEN is_fraud = 1 THEN amount ELSE 0 END) AS fraud_amount,
               COUNT(DISTINCT merchant_name) AS unique_merchants,
               MIN(year * 10000 + month * 100 + day) AS first_seen,
               MAX(year * 10000 + month * 100 + day) AS last_seen
        FROM transactions
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()
    if not row or row["total_transactions"] == 0:
        return None
    return dict(row)


def _users_touched_by_merchant(conn, merchant_name, fraud_only, limit):
    fraud_filter = "AND is_fraud = 1" if fraud_only else ""
    rows = conn.execute(
        f"""
        SELECT user_id,
               COUNT(*) AS shared_transactions,
               SUM(is_fraud) AS shared_fraud,
               SUM(CASE WHEN is_fraud = 1 THEN amount ELSE 0 END) AS shared_fraud_amount,
               SUM(amount) AS shared_amount,
               MAX(year * 10000 + month * 100 + day) AS last_shared
        FROM transactions
        WHERE merchant_name LIKE ? {fraud_filter}
        GROUP BY user_id
        ORDER BY shared_fraud DESC, shared_transactions DESC
        LIMIT ?
        """,
        (f"%{merchant_name}%", limit),
    ).fetchall()

    counterparties = []
    for r in rows:
        # Pull the user's overall fraud footprint for context.
        profile = conn.execute(
            """
            SELECT COUNT(*) AS total_transactions,
                   SUM(is_fraud) AS total_fraud,
                   COUNT(DISTINCT merchant_name) AS unique_merchants
            FROM transactions
            WHERE user_id = ?
            """,
            (r["user_id"],),
        ).fetchone()
        # Sample up to 3 shared fraud transaction IDs so downstream tools can drill in directly.
        sample_ids = conn.execute(
            """
            SELECT transaction_id, amount, year, month, day
            FROM transactions
            WHERE merchant_name LIKE ? AND user_id = ? AND is_fraud = 1
            ORDER BY amount DESC
            LIMIT 3
            """,
            (f"%{merchant_name}%", r["user_id"]),
        ).fetchall()
        counterparties.append({
            "user_id": r["user_id"],
            "shared_transactions": r["shared_transactions"],
            "shared_fraud": r["shared_fraud"] or 0,
            "shared_fraud_amount": round(float(r["shared_fraud_amount"] or 0), 2),
            "shared_amount": round(float(r["shared_amount"] or 0), 2),
            "last_shared": r["last_shared"],
            "user_total_transactions": profile["total_transactions"] if profile else 0,
            "user_total_fraud": (profile["total_fraud"] or 0) if profile else 0,
            "user_unique_merchants": profile["unique_merchants"] if profile else 0,
            "sample_fraud_transactions": [
                {"transaction_id": s["transaction_id"], "amount": s["amount"],
                 "date": f"{s['year']}-{s['month']:02d}-{s['day']:02d}"}
                for s in sample_ids
            ],
        })
    return counterparties


def _merchants_touched_by_user(conn, user_id, fraud_only, limit):
    fraud_filter = "AND is_fraud = 1" if fraud_only else ""
    has_country = "merchant_country" in _table_columns(conn, "transactions")
    country_col = ", merchant_country" if has_country else ""

    rows = conn.execute(
        f"""
        SELECT merchant_name, merchant_state{country_col},
               COUNT(*) AS shared_transactions,
               SUM(is_fraud) AS shared_fraud,
               SUM(CASE WHEN is_fraud = 1 THEN amount ELSE 0 END) AS shared_fraud_amount,
               SUM(amount) AS shared_amount,
               MAX(year * 10000 + month * 100 + day) AS last_shared
        FROM transactions
        WHERE user_id = ? {fraud_filter}
        GROUP BY merchant_name
        ORDER BY shared_fraud DESC, shared_transactions DESC
        LIMIT ?
        """,
        (user_id, limit),
    ).fetchall()

    counterparties = []
    for r in rows:
        profile = conn.execute(
            """
            SELECT COUNT(*) AS total_transactions,
                   SUM(is_fraud) AS total_fraud,
                   COUNT(DISTINCT user_id) AS unique_users
            FROM transactions
            WHERE merchant_name = ?
            """,
            (r["merchant_name"],),
        ).fetchone()
        sample_ids = conn.execute(
            """
            SELECT transaction_id, amount, year, month, day
            FROM transactions
            WHERE user_id = ? AND merchant_name = ? AND is_fraud = 1
            ORDER BY amount DESC
            LIMIT 3
            """,
            (user_id, r["merchant_name"]),
        ).fetchall()
        rec = {
            "merchant_name": r["merchant_name"],
            "merchant_state": r["merchant_state"],
            "shared_transactions": r["shared_transactions"],
            "shared_fraud": r["shared_fraud"] or 0,
            "shared_fraud_amount": round(float(r["shared_fraud_amount"] or 0), 2),
            "shared_amount": round(float(r["shared_amount"] or 0), 2),
            "last_shared": r["last_shared"],
            "merchant_total_transactions": profile["total_transactions"] if profile else 0,
            "merchant_total_fraud": (profile["total_fraud"] or 0) if profile else 0,
            "merchant_unique_users": profile["unique_users"] if profile else 0,
            "sample_fraud_transactions": [
                {"transaction_id": s["transaction_id"], "amount": s["amount"],
                 "date": f"{s['year']}-{s['month']:02d}-{s['day']:02d}"}
                for s in sample_ids
            ],
        }
        if has_country:
            rec["merchant_country"] = r["merchant_country"]
        counterparties.append(rec)
    return counterparties


def _shared_patterns(counterparties, key):
    """Summarise the shared-fraud counts across the counterparty list."""
    total_shared_fraud = sum(c["shared_fraud"] for c in counterparties)
    fraud_heavy = sum(1 for c in counterparties if c["shared_fraud"] > 0)
    total_shared_fraud_amount = round(
        sum(c.get("shared_fraud_amount", 0) for c in counterparties), 2
    )
    return {
        "counterparties_returned": len(counterparties),
        "fraud_heavy_counterparties": fraud_heavy,
        "total_shared_fraud_transactions": int(total_shared_fraud or 0),
        "total_shared_fraud_amount": total_shared_fraud_amount,
        "seed_role": key,
    }


def trace_fraud_network(
    merchant_name=None,
    user_id=None,
    direction="auto",
    fraud_only=True,
    max_counterparties=25,
):
    """Walk one hop from a merchant or user and return connected counterparties."""
    # Coerce types — LLMs often pass strings.
    if isinstance(user_id, str) and user_id.isdigit():
        user_id = int(user_id)
    if isinstance(fraud_only, str):
        fraud_only = fraud_only.lower() in ("true", "1", "yes")
    if isinstance(max_counterparties, str) and max_counterparties.isdigit():
        max_counterparties = int(max_counterparties)
    max_counterparties = max(1, min(int(max_counterparties or 25), 100))

    if not merchant_name and user_id is None:
        return {"error": "Provide either merchant_name or user_id to trace from."}

    if isinstance(merchant_name, str) and merchant_name.strip().lower() in _TOOL_NAME_BLOCKLIST:
        return {
            "error": (
                f"'{merchant_name}' is a tool name, not a merchant. "
                "Call get_risk_dashboard(group_by='merchant') first, then pass one of the "
                "merchant_name values from the by_merchant list into trace_fraud_network."
            )
        }

    resolved = _resolve_direction(direction, merchant_name, user_id)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        if resolved == "merchant_to_users":
            if not merchant_name:
                return {"error": "merchant_to_users direction requires merchant_name."}
            seed = _fetch_seed_merchant(conn, merchant_name)
            if not seed:
                return {
                    "error": (
                        f"No merchant matched '{merchant_name}'. Don't guess a merchant name — "
                        "call get_risk_dashboard(group_by='merchant') and use a merchant_name "
                        "from the by_merchant list."
                    )
                }
            counterparties = _users_touched_by_merchant(
                conn, merchant_name, fraud_only, max_counterparties
            )
            summary = _shared_patterns(counterparties, key="merchant")
            return {
                "direction": "merchant_to_users",
                "seed": {"type": "merchant", **seed},
                "counterparties": counterparties,
                "summary": summary,
                "fraud_only": fraud_only,
            }

        # user_to_merchants
        if user_id is None:
            return {"error": "user_to_merchants direction requires user_id."}
        seed = _fetch_seed_user(conn, user_id)
        if not seed:
            return {"error": f"No transactions found for user_id={user_id}."}
        counterparties = _merchants_touched_by_user(
            conn, user_id, fraud_only, max_counterparties
        )
        summary = _shared_patterns(counterparties, key="user")
        return {
            "direction": "user_to_merchants",
            "seed": {"type": "user", **seed},
            "counterparties": counterparties,
            "summary": summary,
            "fraud_only": fraud_only,
        }
    finally:
        conn.close()
