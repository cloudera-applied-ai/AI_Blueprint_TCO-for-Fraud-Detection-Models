"""Generate synthetic credit card transaction data with realistic fraud patterns.

Supports international transactions across the US, Canada, Europe, South America,
Japan, China, and Russia.
"""

import os
import sys
import random
import re
import numpy as np
import pandas as pd
from faker import Faker
from datetime import datetime, timedelta

try:
    _this_dir = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(os.path.dirname(_this_dir))
except NameError:
    _this_dir = os.path.join(os.getcwd(), "pipelines", "data_generation")
    PROJECT_ROOT = os.getcwd()

sys.path.insert(0, _this_dir)
from schema import (
    N_USERS, N_MERCHANTS, N_TRANSACTIONS, FRAUD_RATE,
    MCC_CODES, COUNTRIES, ALL_COUNTRIES, USE_CHIP_VALUES, ERROR_VALUES,
)

# Pre-build Faker instances per locale (deduplicated)
_faker_cache: dict[str, Faker] = {}


def _get_faker(locale: str) -> Faker:
    if locale not in _faker_cache:
        _faker_cache[locale] = Faker(locale)
        _faker_cache[locale].seed_instance(42)
    return _faker_cache[locale]


# Seed everything for reproducibility
fake = Faker()
Faker.seed(42)
np.random.seed(42)
random.seed(42)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _country_weights():
    """Return (country_codes, weights) arrays normalised to sum to 1."""
    codes = list(COUNTRIES.keys())
    weights = [COUNTRIES[c]["weight"] for c in codes]
    total = sum(weights)
    weights = [w / total for w in weights]
    return codes, weights


def _pick_country(codes, weights):
    return random.choices(codes, weights=weights, k=1)[0]


def _pick_region(country_code):
    regions = list(COUNTRIES[country_code]["regions"].keys())
    return random.choice(regions)


def _pick_city(country_code, region):
    cities = COUNTRIES[country_code]["regions"][region]
    return random.choice(cities)


def _generate_postal_code(country_code):
    """Generate a plausible postal code matching the country's format."""
    fmt = COUNTRIES[country_code].get("postal_format", "#####")
    result = []
    for ch in fmt:
        if ch == "#":
            result.append(str(random.randint(0, 9)))
        elif ch == "A":
            result.append(random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
        else:
            result.append(ch)
    return "".join(result)


def _generate_company_name(country_code):
    """Generate a company name using the appropriate locale."""
    locale = COUNTRIES[country_code]["locale"]
    return _get_faker(locale).company()


# ---------------------------------------------------------------------------
# User generation
# ---------------------------------------------------------------------------

def generate_users(n_users):
    codes, weights = _country_weights()
    users = []
    for uid in range(1, n_users + 1):
        country = _pick_country(codes, weights)
        region = _pick_region(country)
        avg_amount = np.random.lognormal(mean=3.5, sigma=0.8)
        users.append({
            "user_id": uid,
            "card_id": f"card_{uid:05d}",
            "home_country": country,
            "home_state": region,
            "home_zip": _generate_postal_code(country),
            "avg_amount": avg_amount,
        })
    return pd.DataFrame(users)


# ---------------------------------------------------------------------------
# Merchant generation
# ---------------------------------------------------------------------------

def generate_merchants(n_merchants):
    codes, weights = _country_weights()
    merchants = []
    for mid in range(1, n_merchants + 1):
        country = _pick_country(codes, weights)
        region = _pick_region(country)
        city = _pick_city(country, region)
        mcc = random.choice(list(MCC_CODES.keys()))
        merchants.append({
            "merchant_id": mid,
            "merchant_name": _generate_company_name(country),
            "merchant_city": city,
            "merchant_state": region,
            "merchant_country": country,
            "mcc": mcc,
            "merchant_zip": _generate_postal_code(country),
        })
    return pd.DataFrame(merchants)


# ---------------------------------------------------------------------------
# Transaction generation
# ---------------------------------------------------------------------------

def _make_tx_dict(user, merchant, ts, amount, use_chip, errors, is_fraud):
    """Build a transaction dict from components.

    Every transaction carries explicit foreign keys to both the user
    (`user_id`) and the merchant (`merchant_id`) so the three entity tables
    stay relationally linked. Merchant attributes are kept denormalised as
    well to preserve query performance on the hot paths.
    """
    return {
        "user_id": user["user_id"],
        "card_id": user["card_id"],
        "merchant_id": merchant["merchant_id"],
        "merchant_name": merchant["merchant_name"],
        "merchant_city": merchant["merchant_city"],
        "merchant_state": merchant["merchant_state"],
        "merchant_country": merchant["merchant_country"],
        "mcc": merchant["mcc"],
        "amount": round(amount, 2),
        "hour": ts.hour,
        "minute": ts.minute,
        "day": ts.day,
        "month": ts.month,
        "year": ts.year,
        "zip_code": merchant["merchant_zip"],
        "use_chip": use_chip,
        "errors": errors,
        "is_fraud": is_fraud,
    }


def generate_legitimate_transaction(user, merchants, ts):
    # 70% chance of transacting with a merchant in the user's home country+region
    if random.random() < 0.7:
        home = merchants[
            (merchants["merchant_country"] == user["home_country"])
            & (merchants["merchant_state"] == user["home_state"])
        ]
        if len(home) > 0:
            merchant = home.sample(1).iloc[0]
        else:
            # fallback: same country, any region
            same_country = merchants[merchants["merchant_country"] == user["home_country"]]
            merchant = same_country.sample(1).iloc[0] if len(same_country) > 0 else merchants.sample(1).iloc[0]
    else:
        merchant = merchants.sample(1).iloc[0]

    amount = max(0.50, np.random.lognormal(mean=np.log(user["avg_amount"]), sigma=0.6))
    use_chip = random.choices(USE_CHIP_VALUES, weights=[0.55, 0.25, 0.20], k=1)[0]
    errors = random.choices(ERROR_VALUES, weights=[0.95, 0.02, 0.01, 0.01, 0.01], k=1)[0]

    return _make_tx_dict(user, merchant, ts, amount, use_chip, errors, 0)


# --- Fraud injection patterns ---

def inject_velocity_fraud(user, merchants, base_ts):
    """Multiple rapid transactions from different merchants."""
    n_tx = random.randint(3, 5)
    txns = []
    for _ in range(n_tx):
        merchant = merchants.sample(1).iloc[0]
        ts = base_ts + timedelta(minutes=random.randint(0, 10))
        amount = round(np.random.uniform(100, 2000), 2)
        use_chip = random.choice(["Online Transaction", "Swipe Transaction"])
        errors = random.choices(ERROR_VALUES, weights=[0.7, 0.1, 0.1, 0.05, 0.05], k=1)[0]
        txns.append(_make_tx_dict(user, merchant, ts, amount, use_chip, errors, 1))
    return txns


def inject_geo_anomaly_fraud(user, merchants, base_ts):
    """Transaction in a different country or far-away region from the user's home."""
    # Prefer a merchant in a different country for maximum anomaly
    cross_border = merchants[merchants["merchant_country"] != user["home_country"]]
    if len(cross_border) == 0:
        cross_border = merchants[merchants["merchant_state"] != user["home_state"]]
    if len(cross_border) == 0:
        cross_border = merchants
    merchant = cross_border.sample(1).iloc[0]
    amount = round(np.random.uniform(500, 5000), 2)
    errors = random.choices(ERROR_VALUES, weights=[0.6, 0.15, 0.1, 0.1, 0.05], k=1)[0]
    return _make_tx_dict(user, merchant, base_ts, amount, "Swipe Transaction", errors, 1)


def inject_late_night_fraud(user, merchants, base_ts):
    """Transaction between 0-4 AM."""
    merchant = merchants.sample(1).iloc[0]
    hour = random.randint(0, 4)
    ts = base_ts.replace(hour=hour, minute=random.randint(0, 59))
    amount = round(np.random.uniform(500, 3000), 2)
    use_chip = random.choice(["Online Transaction", "Swipe Transaction"])
    errors = random.choices(ERROR_VALUES, weights=[0.7, 0.1, 0.1, 0.05, 0.05], k=1)[0]
    return _make_tx_dict(user, merchant, ts, amount, use_chip, errors, 1)


def inject_online_burst_fraud(user, merchants, base_ts):
    """Multiple rapid online transactions."""
    n_tx = random.randint(3, 6)
    txns = []
    for _ in range(n_tx):
        merchant = merchants.sample(1).iloc[0]
        ts = base_ts + timedelta(seconds=random.randint(10, 300))
        amount = round(np.random.uniform(50, 800), 2)
        errors = random.choices(ERROR_VALUES, weights=[0.65, 0.15, 0.1, 0.05, 0.05], k=1)[0]
        txns.append(_make_tx_dict(user, merchant, ts, amount, "Online Transaction", errors, 1))
    return txns


def inject_cross_border_fraud(user, merchants, base_ts):
    """Fraudulent transaction in a completely different continent/region."""
    # Pick a merchant from a country that is far from user's home
    home = user["home_country"]
    # Group countries by rough region
    region_map = {
        "americas": ["US", "CA", "BR", "AR", "CO", "CL", "PE", "EC", "UY"],
        "europe": ["GB", "DE", "FR", "ES", "IT", "NL", "SE", "PL", "CH", "AT",
                    "PT", "IE", "NO", "DK", "FI", "CZ", "GR", "RO", "HU", "BE"],
        "asia": ["JP", "CN"],
        "russia": ["RU"],
    }
    home_region = None
    for rname, codes in region_map.items():
        if home in codes:
            home_region = rname
            break
    # Pick from a different macro-region
    other_countries = [c for rname, codes in region_map.items() if rname != home_region for c in codes]
    if other_countries:
        far_merchants = merchants[merchants["merchant_country"].isin(other_countries)]
        if len(far_merchants) > 0:
            merchant = far_merchants.sample(1).iloc[0]
        else:
            merchant = merchants.sample(1).iloc[0]
    else:
        merchant = merchants.sample(1).iloc[0]
    amount = round(np.random.uniform(800, 5000), 2)
    errors = random.choices(ERROR_VALUES, weights=[0.6, 0.15, 0.1, 0.1, 0.05], k=1)[0]
    return _make_tx_dict(user, merchant, base_ts, amount, "Online Transaction", errors, 1)


# ---------------------------------------------------------------------------
# Main generation
# ---------------------------------------------------------------------------

def generate_dataset():
    print("Generating user profiles...")
    users = generate_users(N_USERS)

    print("Generating merchant profiles...")
    merchants = generate_merchants(N_MERCHANTS)

    print(f"Generating {N_TRANSACTIONS:,} transactions...")
    n_fraud = int(N_TRANSACTIONS * FRAUD_RATE)
    n_legit = N_TRANSACTIONS - n_fraud

    start_date = datetime(2018, 1, 1)
    end_date = datetime.now().replace(month=12, day=31)
    date_range_days = (end_date - start_date).days

    # --- Legitimate transactions ---
    transactions = []
    for _ in range(n_legit):
        user = users.sample(1).iloc[0]
        days_offset = random.randint(0, date_range_days)
        ts = start_date + timedelta(
            days=days_offset,
            hours=random.choices(range(24), weights=[
                2, 1, 1, 1, 1, 2, 4, 7, 9, 10, 10, 9,
                10, 9, 8, 7, 7, 8, 8, 7, 6, 5, 4, 3
            ], k=1)[0],
            minutes=random.randint(0, 59),
        )
        transactions.append(generate_legitimate_transaction(user, merchants, ts))

    # --- Fraud injection ---
    print(f"Injecting {n_fraud:,} fraud transactions...")
    fraud_injected = 0
    fraud_types = ["velocity", "geo_anomaly", "late_night", "online_burst", "cross_border"]

    while fraud_injected < n_fraud:
        user = users.sample(1).iloc[0]
        days_offset = random.randint(0, date_range_days)
        base_ts = start_date + timedelta(
            days=days_offset,
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
        )
        fraud_type = random.choice(fraud_types)

        if fraud_type == "velocity":
            new_txns = inject_velocity_fraud(user, merchants, base_ts)
        elif fraud_type == "geo_anomaly":
            new_txns = [inject_geo_anomaly_fraud(user, merchants, base_ts)]
        elif fraud_type == "late_night":
            new_txns = [inject_late_night_fraud(user, merchants, base_ts)]
        elif fraud_type == "online_burst":
            new_txns = inject_online_burst_fraud(user, merchants, base_ts)
        elif fraud_type == "cross_border":
            new_txns = [inject_cross_border_fraud(user, merchants, base_ts)]

        remaining = n_fraud - fraud_injected
        new_txns = new_txns[:remaining]
        transactions.extend(new_txns)
        fraud_injected += len(new_txns)

    # --- Assemble DataFrame ---
    df = pd.DataFrame(transactions)
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)
    df["transaction_id"] = range(1, len(df) + 1)

    cols = ["transaction_id"] + [c for c in df.columns if c != "transaction_id"]
    df = df[cols]

    # --- Save ---
    out_dir = os.path.join(PROJECT_ROOT, "data", "raw")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "card_transactions.csv")
    df.to_csv(out_path, index=False)

    users.to_csv(os.path.join(out_dir, "users.csv"), index=False)
    merchants.to_csv(os.path.join(out_dir, "merchants.csv"), index=False)

    print(f"\nDataset generated: {out_path}")
    print(f"Total transactions: {len(df):,}")
    print(f"Fraud transactions: {df['is_fraud'].sum():,} ({df['is_fraud'].mean()*100:.1f}%)")
    print(f"Date range: {df['year'].min()}-{df['year'].max()}")
    print(f"Unique users: {df['user_id'].nunique()}")
    print(f"Unique merchants: {df['merchant_name'].nunique()}")
    print(f"Countries: {df['merchant_country'].nunique()} ({', '.join(sorted(df['merchant_country'].unique()))})")

    return df


if __name__ == "__main__":
    generate_dataset()
