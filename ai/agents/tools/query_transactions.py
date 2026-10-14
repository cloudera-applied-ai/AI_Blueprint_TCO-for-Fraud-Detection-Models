"""Query transactions from SQLite database."""

import os
import sqlite3

try:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
except NameError:
    PROJECT_ROOT = os.getcwd()
DB_PATH = os.path.join(PROJECT_ROOT, "data", "transactions.db")


def _table_columns(conn):
    """Return the set of column names in the transactions table."""
    cursor = conn.execute("PRAGMA table_info(transactions)")
    return {row[1] for row in cursor.fetchall()}


def _parse_ymd(date_str):
    """Parse 'YYYY-MM-DD' into (year, month, day) ints, or None if malformed."""
    try:
        parts = str(date_str).split("-")
        if len(parts) != 3:
            return None
        return int(parts[0]), int(parts[1]), int(parts[2])
    except (ValueError, TypeError):
        return None


def query_transactions(
    transaction_id=None,
    user_id=None,
    merchant_name=None,
    merchant_state=None,
    merchant_country=None,
    min_amount=None,
    max_amount=None,
    is_fraud=None,
    start_date=None,
    end_date=None,
    limit=20,
    order_by=None,
):
    # Coerce types — LLMs may pass strings instead of proper types
    if isinstance(transaction_id, str) and transaction_id.isdigit():
        transaction_id = int(transaction_id)
    if isinstance(user_id, str) and user_id.isdigit():
        user_id = int(user_id)
    try:
        if isinstance(min_amount, str):
            min_amount = float(min_amount)
        if isinstance(max_amount, str):
            max_amount = float(max_amount)
        if isinstance(limit, str):
            limit = int(limit)
    except ValueError:
        return {"error": "min_amount, max_amount, and limit must be numeric"}
    if isinstance(is_fraud, str):
        is_fraud = is_fraud.lower() in ("true", "1", "yes")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    db_columns = _table_columns(conn)
    has_country = "merchant_country" in db_columns

    conditions = []
    params = []

    if transaction_id is not None:
        conditions.append("transaction_id = ?")
        params.append(transaction_id)
    if user_id is not None:
        conditions.append("user_id = ?")
        params.append(user_id)
    if merchant_name is not None:
        conditions.append("merchant_name LIKE ?")
        params.append(f"%{merchant_name}%")
    if merchant_state is not None:
        conditions.append("merchant_state = ?")
        params.append(merchant_state.upper())
    if merchant_country is not None and has_country:
        conditions.append("merchant_country = ?")
        params.append(merchant_country.upper())
    if min_amount is not None:
        conditions.append("amount >= ?")
        params.append(min_amount)
    if max_amount is not None:
        conditions.append("amount <= ?")
        params.append(max_amount)
    if is_fraud is not None:
        conditions.append("is_fraud = ?")
        params.append(1 if is_fraud else 0)
    if start_date:
        ymd = _parse_ymd(start_date)
        if ymd:
            y, m, d = ymd
            conditions.append("(year > ? OR (year = ? AND month > ?) OR (year = ? AND month = ? AND day >= ?))")
            params.extend([y, y, m, y, m, d])
    if end_date:
        ymd = _parse_ymd(end_date)
        if ymd:
            y, m, d = ymd
            conditions.append("(year < ? OR (year = ? AND month < ?) OR (year = ? AND month = ? AND day <= ?))")
            params.extend([y, y, m, y, m, d])

    where = " WHERE " + " AND ".join(conditions) if conditions else ""

    order_clause = "ORDER BY transaction_id DESC"
    if order_by == "amount_desc":
        order_clause = "ORDER BY amount DESC"
    elif order_by == "amount_asc":
        order_clause = "ORDER BY amount ASC"
    elif order_by == "date_desc":
        order_clause = "ORDER BY year DESC, month DESC, day DESC, hour DESC"
    elif order_by == "date_asc":
        order_clause = "ORDER BY year ASC, month ASC, day ASC, hour ASC"

    limit = min(limit or 20, 100)

    country_col = ", merchant_country" if has_country else ""
    query = f"""
        SELECT transaction_id, user_id, card_id, merchant_name, merchant_city,
               merchant_state{country_col}, mcc, amount, hour, minute, day, month, year,
               use_chip, errors, is_fraud
        FROM transactions
        {where}
        {order_clause}
        LIMIT ?
    """
    params.append(limit)

    try:
        cursor = conn.execute(query, params)
        rows = [dict(row) for row in cursor.fetchall()]
        count_query = f"SELECT COUNT(*) FROM transactions {where}"
        total = conn.execute(count_query, params[:-1]).fetchone()[0]
    finally:
        conn.close()

    return {
        "transactions": rows,
        "total_matching": total,
        "showing": len(rows),
    }
