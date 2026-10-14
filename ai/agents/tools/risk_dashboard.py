"""Aggregate fraud analytics for the risk dashboard."""

import os
import sqlite3
from datetime import datetime, timedelta

try:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
except NameError:
    PROJECT_ROOT = os.getcwd()
DB_PATH = os.path.join(PROJECT_ROOT, "data", "transactions.db")


def _has_column(conn, column_name):
    """Check if a column exists in the transactions table."""
    cursor = conn.execute("PRAGMA table_info(transactions)")
    return any(row[1] == column_name for row in cursor.fetchall())


def _date_num(date_str):
    """Parse 'YYYY-MM-DD' into year*10000 + month*100 + day, or None if malformed."""
    try:
        parts = str(date_str).split("-")
        if len(parts) != 3:
            return None
        return int(parts[0]) * 10000 + int(parts[1]) * 100 + int(parts[2])
    except (ValueError, TypeError):
        return None


def _build_date_filter(start_date=None, end_date=None, time_period="all"):
    """Build SQL WHERE clause for date filtering.

    Uses year*10000 + month*100 + day as a numeric date for range comparison.
    Falls back to year-only filtering via time_period for backward compat.
    Malformed dates and non-numeric time periods are ignored rather than raising.
    """
    conditions = []
    params = []

    start_num = _date_num(start_date) if start_date else None
    if start_num is not None:
        conditions.append("(year * 10000 + month * 100 + day) >= ?")
        params.append(start_num)

    end_num = _date_num(end_date) if end_date else None
    if end_num is not None:
        conditions.append("(year * 10000 + month * 100 + day) <= ?")
        params.append(end_num)

    if not conditions and time_period and time_period != "all":
        try:
            params.append(int(time_period))
            conditions.append("year = ?")
        except (ValueError, TypeError):
            pass

    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    return where, params


def _get_comparison_period(start_date, end_date):
    """Calculate the previous period of equal length for comparison.

    Returns (None, None) when either date is malformed.
    """
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None, None
    duration = (end - start).days + 1
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=duration - 1)
    return prev_start.strftime("%Y-%m-%d"), prev_end.strftime("%Y-%m-%d")


def _compute_kpis(conn, where, params):
    """Compute KPI metrics for a given filter."""
    query = f"""
        SELECT
            COUNT(*) as total_transactions,
            SUM(is_fraud) as total_fraud,
            ROUND(AVG(is_fraud) * 100, 2) as fraud_rate_pct,
            ROUND(SUM(CASE WHEN is_fraud = 1 THEN amount ELSE 0 END), 2) as total_fraud_amount,
            ROUND(AVG(CASE WHEN is_fraud = 1 THEN amount END), 2) as avg_fraud_amount,
            ROUND(SUM(amount), 2) as total_amount,
            COUNT(DISTINCT user_id) as unique_users,
            COUNT(DISTINCT merchant_name) as unique_merchants
        FROM transactions
        {where}
    """
    row = conn.execute(query, params).fetchone()
    return dict(row) if row else {}


def get_risk_dashboard(time_period="all", group_by=None, start_date=None, end_date=None):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    has_country = _has_column(conn, "merchant_country")

    where, params = _build_date_filter(start_date, end_date, time_period)

    kpis = _compute_kpis(conn, where, params)
    result = {"kpis": kpis, "time_period": time_period}

    # Period-over-period comparison when date range is specified
    prev_start = prev_end = None
    if start_date and end_date:
        result["date_range"] = {"start": start_date, "end": end_date}
        prev_start, prev_end = _get_comparison_period(start_date, end_date)
    if prev_start and prev_end:
        prev_where, prev_params = _build_date_filter(prev_start, prev_end)
        prev_kpis = _compute_kpis(conn, prev_where, prev_params)

        if prev_kpis.get("total_transactions") and prev_kpis["total_transactions"] > 0:
            comparison = {}
            for key in ["total_transactions", "total_fraud", "fraud_rate_pct",
                        "total_fraud_amount", "avg_fraud_amount"]:
                curr = kpis.get(key, 0) or 0
                prev = prev_kpis.get(key, 0) or 0
                if prev > 0:
                    comparison[key] = {
                        "previous": prev,
                        "change_pct": round((curr - prev) / prev * 100, 1),
                    }
                else:
                    comparison[key] = {"previous": 0, "change_pct": None}
            result["comparison"] = comparison
            result["comparison_period"] = {"start": prev_start, "end": prev_end}

    if group_by == "country" and has_country:
        rows = conn.execute(f"""
            SELECT merchant_country as country, COUNT(*) as total, SUM(is_fraud) as fraud_count,
                   ROUND(AVG(is_fraud) * 100, 2) as fraud_rate_pct,
                   ROUND(SUM(CASE WHEN is_fraud=1 THEN amount ELSE 0 END), 2) as fraud_amount
            FROM transactions {where} GROUP BY merchant_country ORDER BY fraud_count DESC LIMIT 30
        """, params).fetchall()
        result["by_country"] = [dict(r) for r in rows]
    elif group_by == "state":
        rows = conn.execute(f"""
            SELECT merchant_state as state, COUNT(*) as total, SUM(is_fraud) as fraud_count,
                   ROUND(AVG(is_fraud) * 100, 2) as fraud_rate_pct,
                   ROUND(SUM(CASE WHEN is_fraud=1 THEN amount ELSE 0 END), 2) as fraud_amount
            FROM transactions {where} GROUP BY merchant_state ORDER BY fraud_count DESC LIMIT 20
        """, params).fetchall()
        result["by_state"] = [dict(r) for r in rows]
    elif group_by == "mcc":
        rows = conn.execute(f"""
            SELECT mcc, COUNT(*) as total, SUM(is_fraud) as fraud_count,
                   ROUND(AVG(is_fraud) * 100, 2) as fraud_rate_pct,
                   ROUND(SUM(CASE WHEN is_fraud=1 THEN amount ELSE 0 END), 2) as fraud_amount
            FROM transactions {where} GROUP BY mcc ORDER BY fraud_count DESC LIMIT 20
        """, params).fetchall()
        result["by_mcc"] = [dict(r) for r in rows]
    elif group_by == "hour":
        rows = conn.execute(f"""
            SELECT hour, COUNT(*) as total, SUM(is_fraud) as fraud_count,
                   ROUND(AVG(is_fraud) * 100, 2) as fraud_rate_pct
            FROM transactions {where} GROUP BY hour ORDER BY hour
        """, params).fetchall()
        result["by_hour"] = [dict(r) for r in rows]
    elif group_by == "merchant":
        rows = conn.execute(f"""
            SELECT merchant_name, COUNT(*) as total, SUM(is_fraud) as fraud_count,
                   ROUND(AVG(is_fraud) * 100, 2) as fraud_rate_pct,
                   ROUND(SUM(CASE WHEN is_fraud=1 THEN amount ELSE 0 END), 2) as fraud_amount
            FROM transactions {where} GROUP BY merchant_name ORDER BY fraud_count DESC LIMIT 20
        """, params).fetchall()
        result["by_merchant"] = [dict(r) for r in rows]
    elif group_by == "user":
        rows = conn.execute(f"""
            SELECT user_id, COUNT(*) as total, SUM(is_fraud) as fraud_count,
                   ROUND(AVG(is_fraud) * 100, 2) as fraud_rate_pct,
                   ROUND(SUM(CASE WHEN is_fraud=1 THEN amount ELSE 0 END), 2) as fraud_amount
            FROM transactions {where} GROUP BY user_id ORDER BY fraud_count DESC LIMIT 20
        """, params).fetchall()
        result["by_user"] = [dict(r) for r in rows]
    else:
        # Default overview: top countries, states, hourly, MCCs + monthly trend
        if has_country:
            rows = conn.execute(f"""
                SELECT merchant_country as country, SUM(is_fraud) as fraud_count,
                       ROUND(AVG(is_fraud)*100, 2) as fraud_rate_pct
                FROM transactions {where} GROUP BY merchant_country ORDER BY fraud_count DESC LIMIT 10
            """, params).fetchall()
            result["top_fraud_countries"] = [dict(r) for r in rows]

        rows = conn.execute(f"""
            SELECT merchant_state as state, SUM(is_fraud) as fraud_count,
                   ROUND(AVG(is_fraud)*100, 2) as fraud_rate_pct
            FROM transactions {where} GROUP BY merchant_state ORDER BY fraud_count DESC LIMIT 5
        """, params).fetchall()
        result["top_fraud_states"] = [dict(r) for r in rows]

        rows = conn.execute(f"""
            SELECT hour, SUM(is_fraud) as fraud_count,
                   ROUND(AVG(is_fraud)*100, 2) as fraud_rate_pct
            FROM transactions {where} GROUP BY hour ORDER BY hour
        """, params).fetchall()
        result["hourly_pattern"] = [dict(r) for r in rows]

        rows = conn.execute(f"""
            SELECT mcc, SUM(is_fraud) as fraud_count,
                   ROUND(AVG(is_fraud)*100, 2) as fraud_rate_pct
            FROM transactions {where} GROUP BY mcc ORDER BY fraud_count DESC LIMIT 5
        """, params).fetchall()
        result["top_fraud_mccs"] = [dict(r) for r in rows]

        rows = conn.execute(f"""
            SELECT merchant_name, SUM(is_fraud) as fraud_count,
                   ROUND(AVG(is_fraud)*100, 2) as fraud_rate_pct,
                   ROUND(SUM(CASE WHEN is_fraud=1 THEN amount ELSE 0 END), 2) as fraud_amount
            FROM transactions {where}
            GROUP BY merchant_name
            HAVING fraud_count > 0
            ORDER BY fraud_count DESC LIMIT 10
        """, params).fetchall()
        result["top_fraud_merchants"] = [dict(r) for r in rows]

        rows = conn.execute(f"""
            SELECT user_id, SUM(is_fraud) as fraud_count,
                   ROUND(AVG(is_fraud)*100, 2) as fraud_rate_pct,
                   ROUND(SUM(CASE WHEN is_fraud=1 THEN amount ELSE 0 END), 2) as fraud_amount
            FROM transactions {where}
            GROUP BY user_id
            HAVING fraud_count > 0
            ORDER BY fraud_count DESC LIMIT 10
        """, params).fetchall()
        result["top_fraud_users"] = [dict(r) for r in rows]

        # Monthly fraud trend
        rows = conn.execute(f"""
            SELECT year, month, COUNT(*) as total, SUM(is_fraud) as fraud_count,
                   ROUND(AVG(is_fraud) * 100, 2) as fraud_rate_pct,
                   ROUND(SUM(CASE WHEN is_fraud=1 THEN amount ELSE 0 END), 2) as fraud_amount
            FROM transactions
            {where}
            GROUP BY year, month
            ORDER BY year, month
        """, params).fetchall()
        result["monthly_trend"] = [dict(r) for r in rows]

    conn.close()
    return result


def get_date_range():
    """Return the min and max dates available in the dataset."""
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("""
        SELECT
            MIN(year * 10000 + month * 100 + day) as min_date_num,
            MAX(year * 10000 + month * 100 + day) as max_date_num
        FROM transactions
    """).fetchone()
    conn.close()

    if not row or not row[0]:
        return {"min_date": None, "max_date": None}

    min_num, max_num = row[0], row[1]
    min_y, min_m, min_d = min_num // 10000, (min_num % 10000) // 100, min_num % 100
    max_y, max_m, max_d = max_num // 10000, (max_num % 10000) // 100, max_num % 100

    return {
        "min_date": f"{min_y}-{min_m:02d}-{min_d:02d}",
        "max_date": f"{max_y}-{max_m:02d}-{max_d:02d}",
    }
