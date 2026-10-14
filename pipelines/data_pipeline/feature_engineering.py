"""Feature engineering: velocity, z-scores, cyclical time, graph features."""

import os
import sys
import json
import sqlite3
import numpy as np
import pandas as pd

try:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
except NameError:
    PROJECT_ROOT = os.getcwd()
sys.path.insert(0, os.path.join(PROJECT_ROOT, "pipelines"))

from gpu_utils import (
    GPU_ENABLED, gpu_info, read_csv, to_pandas, to_gpu,
    sin as gpu_sin, cos as gpu_cos,
)


def add_velocity_features(df):
    """Compute transaction velocity using vectorized rolling windows.

    This replaces the original O(n*m) nested Python loop with pandas
    time-based rolling, which is dramatically faster on both CPU and GPU.
    """
    # Need pandas for time-based rolling (cuDF rolling is limited)
    df_pd = to_pandas(df) if GPU_ENABLED else df

    df_pd = df_pd.sort_values(["user_id", "year", "month", "day", "hour", "minute"]).copy()
    df_pd["datetime"] = pd.to_datetime(
        df_pd[["year", "month", "day", "hour", "minute"]].assign(second=0)
    )
    df_pd = df_pd.set_index("datetime").sort_index()

    grouped = df_pd.groupby("user_id")

    df_pd["tx_count_last_1h"] = grouped["amount"].transform(
        lambda x: x.rolling("1h", closed="left").count()
    ).fillna(0).astype(int)

    df_pd["tx_count_last_24h"] = grouped["amount"].transform(
        lambda x: x.rolling("24h", closed="left").count()
    ).fillna(0).astype(int)

    df_pd["amount_last_24h"] = grouped["amount"].transform(
        lambda x: x.rolling("24h", closed="left").sum()
    ).fillna(0)

    df_pd = df_pd.reset_index()
    df_pd.drop(columns=["datetime"], inplace=True)

    tag = " [vectorized]" if not GPU_ENABLED else " [GPU-assisted, vectorized]"
    print(f"Added velocity features{tag}")

    return to_gpu(df_pd) if GPU_ENABLED else df_pd


def add_zscore_features(df):
    # groupby().agg() and merge() work identically in cuDF and pandas
    user_stats = df.groupby("user_id")["amount"].agg(["mean", "std"]).reset_index()
    user_stats.columns = ["user_id", "user_amount_mean", "user_amount_std"]
    user_stats["user_amount_std"] = user_stats["user_amount_std"].fillna(1.0).replace(0, 1.0)

    df = df.merge(user_stats, on="user_id", how="left")
    df["tx_amount_zscore_user"] = (df["amount"] - df["user_amount_mean"]) / df["user_amount_std"]

    merch_stats = df.groupby("merchant_name_encoded")["amount"].agg(["mean", "std"]).reset_index()
    merch_stats.columns = ["merchant_name_encoded", "merch_amount_mean", "merch_amount_std"]
    merch_stats["merch_amount_std"] = merch_stats["merch_amount_std"].fillna(1.0).replace(0, 1.0)

    df = df.merge(merch_stats, on="merchant_name_encoded", how="left")
    df["tx_amount_zscore_merchant"] = (df["amount"] - df["merch_amount_mean"]) / df["merch_amount_std"]

    df.drop(columns=["user_amount_mean", "user_amount_std", "merch_amount_mean", "merch_amount_std"], inplace=True)
    print("Added z-score features")
    return df


def add_cyclical_time(df):
    pi2 = 2 * np.pi
    df["tx_hour_sin"] = gpu_sin(df["hour"] * pi2 / 24)
    df["tx_hour_cos"] = gpu_cos(df["hour"] * pi2 / 24)
    df["tx_day_of_week_sin"] = gpu_sin(df["day"] * pi2 / 31)
    df["tx_day_of_week_cos"] = gpu_cos(df["day"] * pi2 / 31)
    print("Added cyclical time features")
    return df


def add_spending_pattern_features(df):
    user_avg = df.groupby("user_id")["amount"].mean().reset_index()
    user_avg.columns = ["user_id", "user_avg_amount"]

    df = df.merge(user_avg, on="user_id", how="left")
    df["amount_to_avg_ratio"] = df["amount"] / df["user_avg_amount"].replace(0, 1)
    df.drop(columns=["user_avg_amount"], inplace=True)
    print("Added spending pattern features")
    return df


def add_geographic_features(df):
    users_path = os.path.join(PROJECT_ROOT, "data", "raw", "users.csv")
    if os.path.exists(users_path):
        users = read_csv(users_path)
        merge_cols = ["user_id", "home_state"]
        if "home_country" in users.columns:
            merge_cols.append("home_country")
        df = df.merge(users[merge_cols], on="user_id", how="left")
        df["is_out_of_state"] = (df["merchant_state"] != df["home_state"]).astype(int)
        if "home_country" in df.columns and "merchant_country" in df.columns:
            df["is_cross_border"] = (df["merchant_country"] != df["home_country"]).astype(int)
            df.drop(columns=["home_country"], inplace=True)
        else:
            df["is_cross_border"] = 0
        df.drop(columns=["home_state"], inplace=True)
    else:
        df["is_out_of_state"] = 0
        df["is_cross_border"] = 0
    print("Added geographic features")
    return df


def load_to_sqlite(df):
    db_path = os.path.join(PROJECT_ROOT, "data", "transactions.db")
    conn = sqlite3.connect(db_path)

    # SQLite requires pandas DataFrames
    df_pd = to_pandas(df)

    raw_path = os.path.join(PROJECT_ROOT, "data", "raw", "card_transactions.csv")
    if os.path.exists(raw_path):
        raw_cols = ["transaction_id", "use_chip", "errors"]
        # Pull merchant_id in from the raw file if the processed frame dropped it.
        try:
            raw_head = pd.read_csv(raw_path, nrows=0)
            if "merchant_id" in raw_head.columns:
                raw_cols.append("merchant_id")
        except Exception:
            pass
        raw = pd.read_csv(raw_path, usecols=raw_cols)
        merge_cols = [c for c in raw.columns if c != "transaction_id" and c not in df_pd.columns]
        if merge_cols:
            df_pd = df_pd.merge(
                raw[["transaction_id"] + merge_cols], on="transaction_id", how="left",
            )

    query_cols = [
        "transaction_id", "user_id", "card_id", "merchant_id", "merchant_name",
        "merchant_city", "merchant_state", "merchant_country", "mcc",
        "amount", "hour", "minute", "day", "month", "year",
        "zip_code", "use_chip", "errors", "is_fraud",
        "tx_count_last_1h", "tx_count_last_24h", "tx_amount_zscore_user",
        "is_out_of_state", "is_cross_border", "amount_to_avg_ratio",
        "merchant_fraud_rate", "mcc_fraud_rate", "country_fraud_rate",
    ]
    available_cols = [c for c in query_cols if c in df_pd.columns]
    query_df = df_pd[available_cols].copy()

    query_df.to_sql("transactions", conn, if_exists="replace", index=False)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON transactions(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_merchant ON transactions(merchant_name)")
    if "merchant_id" in query_df.columns:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_merchant_id ON transactions(merchant_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_fraud ON transactions(is_fraud)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_amount ON transactions(amount)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_date ON transactions(year, month, day)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tx_id ON transactions(transaction_id)")

    # Load the users and merchants reference tables so the database is a
    # self-contained relational model (user_id / merchant_id FKs resolvable
    # inside SQL). Without these, the transactions table points to ids that
    # don't exist anywhere in the DB.
    raw_dir = os.path.join(PROJECT_ROOT, "data", "raw")
    users_csv = os.path.join(raw_dir, "users.csv")
    if os.path.exists(users_csv):
        users_df = pd.read_csv(users_csv)
        users_df.to_sql("users", conn, if_exists="replace", index=False)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_users_id ON users(user_id)")
        print(f"Loaded {len(users_df):,} users into SQLite")

    merchants_csv = os.path.join(raw_dir, "merchants.csv")
    if os.path.exists(merchants_csv):
        merchants_df = pd.read_csv(merchants_csv)
        merchants_df.to_sql("merchants", conn, if_exists="replace", index=False)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_merchants_id ON merchants(merchant_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_merchants_name ON merchants(merchant_name)")
        print(f"Loaded {len(merchants_df):,} merchants into SQLite")

    conn.commit()
    conn.close()
    print(f"Loaded {len(query_df):,} transactions into SQLite: {db_path}")


def main():
    print(f"Feature engineering pipeline | {gpu_info()}")

    processed_dir = os.path.join(PROJECT_ROOT, "data", "processed")
    df = read_csv(os.path.join(processed_dir, "all_processed.csv"))
    print(f"Loaded {len(df):,} processed transactions")

    df = add_velocity_features(df)
    df = add_zscore_features(df)
    df = add_cyclical_time(df)
    df = add_spending_pattern_features(df)
    df = add_geographic_features(df)

    # Convert to pandas for CSV output
    df_pd = to_pandas(df)

    df_pd.to_parquet(os.path.join(processed_dir, "all_features.parquet"), index=False)

    train = df_pd[df_pd["year"] < 2019]
    val = df_pd[df_pd["year"] == 2019]
    test = df_pd[df_pd["year"] >= 2020]

    train.to_parquet(os.path.join(processed_dir, "train_features.parquet"), index=False)
    val.to_parquet(os.path.join(processed_dir, "val_features.parquet"), index=False)
    test.to_parquet(os.path.join(processed_dir, "test_features.parquet"), index=False)

    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    except NameError:
        sys.path.insert(0, os.path.join(PROJECT_ROOT, "pipelines", "data_pipeline"))
    from preprocess import get_feature_columns
    features = get_feature_columns(df_pd)
    with open(os.path.join(PROJECT_ROOT, "models", "feature_names.json"), "w") as f:
        json.dump(features, f, indent=2)

    print(f"Feature columns ({len(features)}): {features}")
    load_to_sqlite(df_pd)
    print("\nFeature engineering complete.")


if __name__ == "__main__":
    main()
