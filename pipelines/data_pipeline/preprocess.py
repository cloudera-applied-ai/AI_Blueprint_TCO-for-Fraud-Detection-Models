"""Preprocess raw transaction data: clean, encode, scale."""

import os
import sys
import json
import pickle
import numpy as np
import pandas as pd
from sklearn.preprocessing import RobustScaler, LabelEncoder

try:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
except NameError:
    PROJECT_ROOT = os.getcwd()
sys.path.insert(0, os.path.join(PROJECT_ROOT, "pipelines"))

from gpu_utils import (
    GPU_ENABLED, gpu_info, read_csv, get_dummies, to_pandas,
    get_label_encoder, get_robust_scaler,
    label_encoder_to_sklearn, robust_scaler_to_sklearn,
)


def load_raw_data():
    path = os.path.join(PROJECT_ROOT, "data", "raw", "card_transactions.csv")
    df = read_csv(path)
    tag = " [GPU]" if GPU_ENABLED else ""
    print(f"Loaded {len(df):,} transactions{tag}")
    return df


def clean_data(df):
    if df["amount"].dtype == object:
        df["amount"] = df["amount"].str.replace("$", "", regex=False).astype(float)
    else:
        df["amount"] = df["amount"].astype(float)

    df["time_minutes"] = df["hour"] * 60 + df["minute"]

    if df["is_fraud"].dtype == object:
        df["is_fraud"] = df["is_fraud"].map({"Yes": 1, "No": 0}).fillna(0).astype(int)
    else:
        df["is_fraud"] = df["is_fraud"].astype(int)

    df["errors"] = df["errors"].fillna("None")
    print(f"Cleaned data: {len(df):,} rows, fraud rate: {df['is_fraud'].mean()*100:.2f}%")
    return df


def encode_features(df):
    encoders = {}
    df = get_dummies(df, columns=["use_chip"], prefix="chip")
    df = get_dummies(df, columns=["errors"], prefix="error")

    for col in ["merchant_state", "merchant_name", "merchant_country"]:
        if col not in df.columns:
            continue
        le = get_label_encoder()
        df[f"{col}_encoded"] = le.fit_transform(df[col].astype(str))
        # Always store sklearn-compatible encoder for serving
        encoders[col] = label_encoder_to_sklearn(le)

    df["mcc"] = df["mcc"].astype(int)

    merchant_fraud = df.groupby("merchant_name_encoded")["is_fraud"].mean()
    df["merchant_fraud_rate"] = df["merchant_name_encoded"].map(merchant_fraud)

    mcc_fraud = df.groupby("mcc")["is_fraud"].mean()
    df["mcc_fraud_rate"] = df["mcc"].map(mcc_fraud)

    state_fraud = df.groupby("merchant_state_encoded")["is_fraud"].mean()
    df["state_fraud_rate"] = df["merchant_state_encoded"].map(state_fraud)

    if "merchant_country_encoded" in df.columns:
        country_fraud = df.groupby("merchant_country_encoded")["is_fraud"].mean()
        df["country_fraud_rate"] = df["merchant_country_encoded"].map(country_fraud)

    return df, encoders


def scale_features(df):
    scaler = get_robust_scaler()
    df["amount_scaled"] = scaler.fit_transform(df[["amount"]])
    # Always store sklearn-compatible scaler for serving
    sklearn_scaler = robust_scaler_to_sklearn(scaler)
    return df, sklearn_scaler


def split_data(df):
    unique_years = df["year"].unique()
    # cuDF Series aren't iterable — convert to host values first
    if hasattr(unique_years, 'values_host'):
        unique_years = unique_years.values_host
    years = sorted(unique_years)
    # Use first 60% of years for train, next 20% for val, last 20% for test
    n = len(years)
    train_end = years[max(int(n * 0.6), 1) - 1]
    val_end = years[max(int(n * 0.8), 2) - 1]
    train = df[df["year"] <= train_end].copy()
    val = df[(df["year"] > train_end) & (df["year"] <= val_end)].copy()
    test = df[df["year"] > val_end].copy()
    print(f"Split: train={len(train):,} (≤{train_end}), val={len(val):,} ({train_end+1}-{val_end}), test={len(test):,} (>{val_end})")
    return train, val, test


def get_feature_columns(df):
    exclude = [
        "transaction_id", "user_id", "card_id", "merchant_id", "merchant_name",
        "merchant_city", "merchant_state", "merchant_country", "zip_code",
        "is_fraud", "day", "month", "year",
    ]
    # Convert to pandas for dtype checking if needed
    df_check = to_pandas(df) if GPU_ENABLED else df
    features = [c for c in df_check.columns if c not in exclude and df_check[c].dtype in [np.float64, np.int64, np.int32, np.uint8, np.bool_]]
    return features


def main():
    print(f"Preprocessing pipeline | {gpu_info()}")
    df = load_raw_data()
    df = clean_data(df)
    df, encoders = encode_features(df)
    df, scaler = scale_features(df)
    train, val, test = split_data(df)

    features = get_feature_columns(train)
    print(f"Feature columns ({len(features)}): {features}")

    out_dir = os.path.join(PROJECT_ROOT, "data", "processed")
    os.makedirs(out_dir, exist_ok=True)

    # Convert to pandas for CSV/pickle I/O (cuDF DataFrames can't be pickled with sklearn)
    to_pandas(train).to_csv(os.path.join(out_dir, "train.csv"), index=False)
    to_pandas(val).to_csv(os.path.join(out_dir, "val.csv"), index=False)
    to_pandas(test).to_csv(os.path.join(out_dir, "test.csv"), index=False)
    to_pandas(df).to_csv(os.path.join(out_dir, "all_processed.csv"), index=False)

    models_dir = os.path.join(PROJECT_ROOT, "models")
    os.makedirs(models_dir, exist_ok=True)
    with open(os.path.join(models_dir, "preprocessor.pkl"), "wb") as f:
        pickle.dump({"encoders": encoders, "scaler": scaler}, f)
    with open(os.path.join(models_dir, "feature_names.json"), "w") as f:
        json.dump(features, f, indent=2)

    print(f"\nPreprocessed data saved to {out_dir}")
    print(f"Preprocessor artifacts saved to {models_dir}")


if __name__ == "__main__":
    main()
