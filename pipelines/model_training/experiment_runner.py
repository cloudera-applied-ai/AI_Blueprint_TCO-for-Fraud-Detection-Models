"""Run model experiments: retrain XGBoost on corrected/expanded data and compare."""

import os
import sys
import json
import time
import uuid
import sqlite3
import threading
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import (
    roc_auc_score, average_precision_score, precision_score,
    recall_score, f1_score, confusion_matrix,
)

try:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
except NameError:
    PROJECT_ROOT = os.getcwd()
sys.path.insert(0, os.path.join(PROJECT_ROOT, "pipelines"))

from gpu_utils import gpu_info, get_xgboost_gpu_params

DB_PATH = os.path.join(PROJECT_ROOT, "data", "transactions.db")
EXPERIMENTS_DIR = os.path.join(PROJECT_ROOT, "models", "experiments")
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")

# In-memory live status of the currently-running / last-finished experiment.
# Persistent history lives in the SQLite `experiments` table.
_current_run: dict | None = None
_run_lock = threading.Lock()


def _ensure_experiments_table(conn):
    """Create the experiments history table if missing."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS experiments (
            experiment_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            description TEXT,
            started_at REAL NOT NULL,
            finished_at REAL,
            train_rows INTEGER,
            corrections_applied INTEGER,
            generated_added INTEGER,
            roc_auc REAL,
            avg_precision REAL,
            precision_val REAL,
            recall_val REAL,
            f1_val REAL,
            delta_roc_auc REAL,
            delta_avg_precision REAL,
            result_json TEXT,
            error TEXT,
            promoted_at REAL
        )
    """)


def _persist_experiment(status, experiment_id, started_at, description,
                        result=None, error=None, finished_at=None):
    """Upsert an experiment row into the SQLite history table."""
    conn = sqlite3.connect(DB_PATH)
    try:
        _ensure_experiments_table(conn)
        fields = {
            "experiment_id": experiment_id,
            "status": status,
            "description": description,
            "started_at": started_at,
            "finished_at": finished_at,
            "error": error,
        }
        if result:
            metrics = result.get("new_model", {}).get("metrics", {})
            deltas = result.get("deltas", {})
            data_summary = result.get("data_summary", {})
            fields.update({
                "train_rows": data_summary.get("train_rows"),
                "corrections_applied": data_summary.get("corrections_applied"),
                "generated_added": data_summary.get("generated_data_added"),
                "roc_auc": metrics.get("roc_auc"),
                "avg_precision": metrics.get("avg_precision"),
                "precision_val": metrics.get("precision"),
                "recall_val": metrics.get("recall"),
                "f1_val": metrics.get("f1"),
                "delta_roc_auc": deltas.get("roc_auc"),
                "delta_avg_precision": deltas.get("avg_precision"),
                "result_json": json.dumps(result, default=str),
            })

        columns = ", ".join(fields.keys())
        placeholders = ", ".join("?" for _ in fields)
        updates = ", ".join(f"{k}=excluded.{k}" for k in fields.keys() if k != "experiment_id")
        conn.execute(
            f"""
            INSERT INTO experiments ({columns}) VALUES ({placeholders})
            ON CONFLICT(experiment_id) DO UPDATE SET {updates}
            """,
            list(fields.values()),
        )
        conn.commit()
    finally:
        conn.close()


def _read_data(directory, name):
    parquet_path = os.path.join(directory, f"{name}.parquet")
    if os.path.exists(parquet_path):
        return pd.read_parquet(parquet_path)
    csv_path = os.path.join(directory, f"{name}.csv")
    if os.path.exists(csv_path):
        return pd.read_csv(csv_path)
    raise FileNotFoundError(f"No data file found for {name} in {directory}")


def get_original_model_metrics() -> dict:
    """Load metrics for the current production model."""
    metrics_path = os.path.join(MODELS_DIR, "metrics.json")
    if not os.path.exists(metrics_path):
        return {"error": "No production model metrics found"}
    with open(metrics_path) as f:
        metrics = json.load(f)

    # Also get feature importance
    importance_path = os.path.join(MODELS_DIR, "feature_importance.csv")
    top_features = []
    if os.path.exists(importance_path):
        imp = pd.read_csv(importance_path)
        top_features = imp.head(10).to_dict(orient="records")

    return {
        "model": "production",
        "model_path": os.path.join(MODELS_DIR, "xgboost_fraud.json"),
        "metrics": metrics,
        "top_features": top_features,
        "gpu_info": gpu_info(),
    }


def get_label_corrections() -> dict:
    """Get current label corrections from the corrections table."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Check if corrections table exists
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='label_corrections'"
    ).fetchall()
    if not tables:
        conn.close()
        return {"corrections": [], "total": 0}

    rows = conn.execute("""
        SELECT c.transaction_id, c.original_label, c.corrected_label, c.corrected_at,
               t.user_id, t.merchant_name, t.amount, t.hour, t.is_fraud
        FROM label_corrections c
        JOIN transactions t ON c.transaction_id = t.transaction_id
        ORDER BY c.corrected_at DESC
    """).fetchall()
    conn.close()

    return {
        "corrections": [dict(r) for r in rows],
        "total": len(rows),
    }


def apply_label_correction(transaction_id: int, corrected_label: int) -> dict:
    """Record a label correction for a transaction."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Create corrections table if it doesn't exist
    conn.execute("""
        CREATE TABLE IF NOT EXISTS label_corrections (
            transaction_id INTEGER PRIMARY KEY,
            original_label INTEGER NOT NULL,
            corrected_label INTEGER NOT NULL,
            corrected_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # Get original label
    row = conn.execute(
        "SELECT is_fraud FROM transactions WHERE transaction_id = ?",
        (transaction_id,)
    ).fetchone()
    if not row:
        conn.close()
        return {"error": f"Transaction {transaction_id} not found"}

    original = row["is_fraud"]

    # Upsert correction
    conn.execute("""
        INSERT INTO label_corrections (transaction_id, original_label, corrected_label)
        VALUES (?, ?, ?)
        ON CONFLICT(transaction_id) DO UPDATE SET
            corrected_label = excluded.corrected_label,
            corrected_at = datetime('now')
    """, (transaction_id, original, corrected_label))
    conn.commit()
    conn.close()

    return {
        "transaction_id": transaction_id,
        "original_label": original,
        "corrected_label": corrected_label,
    }


def remove_label_correction(transaction_id: int) -> dict:
    """Remove a label correction."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM label_corrections WHERE transaction_id = ?", (transaction_id,))
    conn.commit()
    conn.close()
    return {"removed": transaction_id}


def get_false_positives(limit: int = 50) -> dict:
    """Find transactions the model scores as fraud but labeled is_fraud=1.

    These are candidates for analyst review -- some may actually be legitimate
    transactions that were mislabeled in the training data.
    """
    model_path = os.path.join(MODELS_DIR, "xgboost_fraud.json")
    if not os.path.exists(model_path):
        return {"error": "No production model found"}

    model = xgb.Booster()
    model.load_model(model_path)

    with open(os.path.join(MODELS_DIR, "feature_names.json")) as f:
        feature_names = json.load(f)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Get fraud-labeled transactions to review
    rows = conn.execute("""
        SELECT * FROM transactions WHERE is_fraud = 1
        ORDER BY amount DESC LIMIT ?
    """, (limit * 3,)).fetchall()
    conn.close()

    # Score them with the model
    candidates = []
    for row in rows:
        row_dict = dict(row)
        features = [row_dict.get(f, 0.0) for f in feature_names]
        dmatrix = xgb.DMatrix(np.array([features], dtype=np.float32), feature_names=feature_names)
        score = float(model.predict(dmatrix)[0])

        # Lower model score on fraud-labeled transactions = potential false positive in data
        candidates.append({
            **row_dict,
            "fraud_score": round(score, 4),
            "confidence": "LOW" if score < 0.3 else "MEDIUM" if score < 0.7 else "HIGH",
        })

    # Sort by fraud_score ascending -- lowest scores are most likely mislabeled
    candidates.sort(key=lambda x: x["fraud_score"])

    return {
        "candidates": candidates[:limit],
        "total_fraud_in_db": len(rows),
    }


def generate_additional_data(n_transactions: int = 10000) -> dict:
    """Generate additional synthetic transactions and merge into the dataset."""
    sys.path.insert(0, os.path.join(PROJECT_ROOT, "pipelines", "data_generation"))
    from generate_synthetic_data import generate_users, generate_merchants, generate_legitimate_transaction
    from generate_synthetic_data import (
        inject_velocity_fraud, inject_geo_anomaly_fraud,
        inject_late_night_fraud, inject_online_burst_fraud,
        inject_cross_border_fraud,
    )
    from schema import N_USERS, N_MERCHANTS, FRAUD_RATE
    import random
    from datetime import datetime, timedelta

    # Generate fresh users/merchants for variety
    users = generate_users(min(N_USERS, 500))
    merchants = generate_merchants(min(N_MERCHANTS, 200))

    n_fraud = int(n_transactions * FRAUD_RATE)
    n_legit = n_transactions - n_fraud

    start_date = datetime(2018, 1, 1)
    end_date = datetime.now().replace(month=12, day=31)
    date_range_days = (end_date - start_date).days

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

    fraud_injected = 0
    fraud_types = ["velocity", "geo_anomaly", "late_night", "online_burst", "cross_border"]
    while fraud_injected < n_fraud:
        user = users.sample(1).iloc[0]
        days_offset = random.randint(0, date_range_days)
        base_ts = start_date + timedelta(
            days=days_offset, hours=random.randint(0, 23), minutes=random.randint(0, 59),
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
        else:
            new_txns = [inject_cross_border_fraud(user, merchants, base_ts)]

        remaining = n_fraud - fraud_injected
        new_txns = new_txns[:remaining]
        transactions.extend(new_txns)
        fraud_injected += len(new_txns)

    new_df = pd.DataFrame(transactions)

    # Assign transaction IDs that don't collide with existing data
    conn = sqlite3.connect(DB_PATH)
    max_id = conn.execute("SELECT MAX(transaction_id) FROM transactions").fetchone()[0] or 0
    conn.close()
    new_df["transaction_id"] = range(max_id + 1, max_id + 1 + len(new_df))

    # Save as a separate file for the experiment
    generated_dir = os.path.join(PROJECT_ROOT, "data", "generated")
    os.makedirs(generated_dir, exist_ok=True)
    out_path = os.path.join(generated_dir, "additional_transactions.csv")
    new_df.to_csv(out_path, index=False)

    return {
        "generated": len(new_df),
        "fraud": int(new_df["is_fraud"].sum()),
        "legitimate": int((new_df["is_fraud"] == 0).sum()),
        "fraud_rate": round(new_df["is_fraud"].mean() * 100, 1),
        "path": out_path,
    }


def _run_experiment_core(
    experiment_id: str,
    started_at: float,
    use_corrections: bool,
    use_generated_data: bool,
    hyperparams: dict | None,
    description: str,
) -> dict:
    """Blocking body of an experiment run. Updates `_current_run` as it progresses.

    Returns the structured result dict. The public `run_experiment()` wraps this
    for synchronous callers; `run_experiment_async()` dispatches it to a thread.
    """
    global _current_run

    def set_phase(phase):
        with _run_lock:
            _current_run = {
                "id": experiment_id,
                "status": "running",
                "phase": phase,
                "description": description,
                "started_at": started_at,
            }
            return _current_run

    set_phase("loading_data")

    t_start = time.perf_counter()
    processed_dir = os.path.join(PROJECT_ROOT, "data", "processed")

    # Load base training data
    train = _read_data(processed_dir, "train_features")
    val = _read_data(processed_dir, "val_features")
    test = _read_data(processed_dir, "test_features")

    with open(os.path.join(MODELS_DIR, "feature_names.json")) as f:
        feature_names = json.load(f)

    available = [f for f in feature_names if f in train.columns]
    t_load = time.perf_counter()
    set_phase("applying_corrections")

    corrections_applied = 0
    # Apply label corrections to the training data
    if use_corrections:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='label_corrections'"
        ).fetchall()
        if tables:
            corrections = conn.execute("SELECT transaction_id, corrected_label FROM label_corrections").fetchall()
            correction_map = {r["transaction_id"]: r["corrected_label"] for r in corrections}
            if correction_map:
                mask = train["transaction_id"].isin(correction_map.keys())
                for tx_id, new_label in correction_map.items():
                    train.loc[train["transaction_id"] == tx_id, "is_fraud"] = new_label
                corrections_applied = int(mask.sum())
        conn.close()

    t_corrections = time.perf_counter()
    set_phase("merging_generated_data")

    generated_added = 0
    # Merge generated data if available
    if use_generated_data:
        generated_path = os.path.join(PROJECT_ROOT, "data", "generated", "additional_transactions.csv")
        if os.path.exists(generated_path):
            gen_df = pd.read_csv(generated_path)
            # We need to add features to this data -- use a minimal feature set
            # Map available columns from generated data
            gen_available = [f for f in available if f in gen_df.columns]
            missing = [f for f in available if f not in gen_df.columns]
            for col in missing:
                gen_df[col] = 0.0
            train = pd.concat([train, gen_df], ignore_index=True)
            generated_added = len(gen_df)

    t_merge = time.perf_counter()
    set_phase("training")

    # Train new model
    X_train = train[available].values
    y_train = train["is_fraud"].values
    X_val = val[available].values
    y_val = val["is_fraud"].values

    n_neg = (y_train == 0).sum()
    n_pos = (y_train == 1).sum()
    scale_pos_weight = n_neg / max(n_pos, 1)

    dtrain = xgb.QuantileDMatrix(X_train, label=y_train, feature_names=available)
    dval = xgb.QuantileDMatrix(X_val, label=y_val, ref=dtrain, feature_names=available)

    params = {
        "objective": "binary:logistic",
        "eval_metric": ["auc", "aucpr", "logloss"],
        "max_depth": 6,
        "learning_rate": 0.2,
        "scale_pos_weight": scale_pos_weight,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "min_child_weight": 5,
        "gamma": 1,
        "reg_alpha": 0.1,
        "reg_lambda": 1.0,
        "seed": 42,
    }
    if hyperparams:
        params.update(hyperparams)
    params.update(get_xgboost_gpu_params())

    model = xgb.train(
        params, dtrain, num_boost_round=512,
        evals=[(dtrain, "train"), (dval, "val")],
        early_stopping_rounds=50, verbose_eval=0,
    )
    t_train = time.perf_counter()
    set_phase("evaluating")

    # Evaluate new model
    X_test = test[available].values
    y_test = test["is_fraud"].values
    dtest = xgb.DMatrix(X_test, feature_names=available)
    y_pred_proba = model.predict(dtest)
    y_pred = (y_pred_proba >= 0.5).astype(int)

    cm = confusion_matrix(y_test, y_pred)
    new_metrics = {
        "roc_auc": round(float(roc_auc_score(y_test, y_pred_proba)), 4),
        "avg_precision": round(float(average_precision_score(y_test, y_pred_proba)), 4),
        "precision": round(float(precision_score(y_test, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_test, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_test, y_pred, zero_division=0)), 4),
        "confusion_matrix": {
            "tn": int(cm[0][0]), "fp": int(cm[0][1]),
            "fn": int(cm[1][0]), "tp": int(cm[1][1]),
        },
    }

    # SHAP importance for new model
    X_sample = test[available].sample(min(2000, len(test)), random_state=42)
    d_sample = xgb.DMatrix(X_sample.values, feature_names=available)
    shap_raw = model.predict(d_sample, pred_contribs=True)
    shap_values = shap_raw[:, :-1]
    new_top_features = pd.DataFrame({
        "feature": available,
        "mean_abs_shap": np.abs(shap_values).mean(axis=0),
    }).sort_values("mean_abs_shap", ascending=False).head(10).to_dict(orient="records")

    t_eval = time.perf_counter()

    # Save experiment model
    exp_dir = os.path.join(EXPERIMENTS_DIR, experiment_id)
    os.makedirs(exp_dir, exist_ok=True)
    model.save_model(os.path.join(exp_dir, "model.json"))
    with open(os.path.join(exp_dir, "metrics.json"), "w") as f:
        json.dump(new_metrics, f, indent=2)

    # Load original model metrics for comparison
    original = get_original_model_metrics()
    orig_metrics = original.get("metrics", {})

    # Compute deltas
    deltas = {}
    for key in ["roc_auc", "avg_precision"]:
        if key in orig_metrics and key in new_metrics:
            deltas[key] = round(new_metrics[key] - orig_metrics[key], 4)

    # Also evaluate original model on test set for full comparison
    orig_model_path = os.path.join(MODELS_DIR, "xgboost_fraud.json")
    if os.path.exists(orig_model_path):
        orig_model = xgb.Booster()
        orig_model.load_model(orig_model_path)
        orig_pred_proba = orig_model.predict(dtest)
        orig_pred = (orig_pred_proba >= 0.5).astype(int)
        orig_cm = confusion_matrix(y_test, orig_pred)
        orig_full_metrics = {
            "roc_auc": round(float(roc_auc_score(y_test, orig_pred_proba)), 4),
            "avg_precision": round(float(average_precision_score(y_test, orig_pred_proba)), 4),
            "precision": round(float(precision_score(y_test, orig_pred, zero_division=0)), 4),
            "recall": round(float(recall_score(y_test, orig_pred, zero_division=0)), 4),
            "f1": round(float(f1_score(y_test, orig_pred, zero_division=0)), 4),
            "confusion_matrix": {
                "tn": int(orig_cm[0][0]), "fp": int(orig_cm[0][1]),
                "fn": int(orig_cm[1][0]), "tp": int(orig_cm[1][1]),
            },
        }

        # Compute full deltas
        for key in ["roc_auc", "avg_precision", "precision", "recall", "f1"]:
            deltas[key] = round(new_metrics[key] - orig_full_metrics[key], 4)
    else:
        orig_full_metrics = orig_metrics

    result = {
        "experiment_id": experiment_id,
        "status": "completed",
        "description": description,
        "gpu_info": gpu_info(),
        "data_summary": {
            "train_rows": len(train),
            "val_rows": len(val),
            "test_rows": len(test),
            "corrections_applied": corrections_applied,
            "generated_data_added": generated_added,
            "features": len(available),
        },
        "timing": {
            "data_load_s": round(t_load - t_start, 2),
            "corrections_s": round(t_corrections - t_load, 2),
            "merge_s": round(t_merge - t_corrections, 2),
            "training_s": round(t_train - t_merge, 2),
            "evaluation_s": round(t_eval - t_train, 2),
            "total_s": round(t_eval - t_start, 2),
        },
        "original_model": {
            "metrics": orig_full_metrics,
            "top_features": original.get("top_features", []),
        },
        "new_model": {
            "metrics": new_metrics,
            "top_features": new_top_features,
            "model_path": os.path.join(exp_dir, "model.json"),
        },
        "deltas": deltas,
    }

    with _run_lock:
        _current_run = {
            "id": experiment_id,
            "status": "completed",
            "phase": "done",
            "started_at": started_at,
            "finished_at": time.time(),
            "description": description,
            "result": result,
        }
    return result


def _run_and_track(
    experiment_id: str,
    started_at: float,
    use_corrections: bool,
    use_generated_data: bool,
    hyperparams: dict | None,
    description: str,
):
    """Wrapper used by the background thread. Captures success + failure into
    both the in-memory status and the persistent history table."""
    global _current_run
    _persist_experiment(
        status="running",
        experiment_id=experiment_id,
        started_at=started_at,
        description=description,
    )
    try:
        result = _run_experiment_core(
            experiment_id, started_at,
            use_corrections, use_generated_data, hyperparams, description,
        )
        _persist_experiment(
            status="completed",
            experiment_id=experiment_id,
            started_at=started_at,
            description=description,
            result=result,
            finished_at=time.time(),
        )
    except Exception as e:
        err_str = f"{type(e).__name__}: {e}"
        with _run_lock:
            _current_run = {
                "id": experiment_id,
                "status": "failed",
                "phase": "error",
                "started_at": started_at,
                "finished_at": time.time(),
                "description": description,
                "error": err_str,
            }
        _persist_experiment(
            status="failed",
            experiment_id=experiment_id,
            started_at=started_at,
            description=description,
            error=err_str,
            finished_at=time.time(),
        )


def run_experiment(
    use_corrections: bool = True,
    use_generated_data: bool = True,
    hyperparams: dict | None = None,
    description: str = "",
) -> dict:
    """Synchronous wrapper — blocks until the experiment finishes.

    Preserved for CLI / tool-call use; the REST endpoint uses the async variant.
    """
    experiment_id = str(uuid.uuid4())[:8]
    started_at = time.time()
    _persist_experiment(
        status="running",
        experiment_id=experiment_id,
        started_at=started_at,
        description=description,
    )
    try:
        result = _run_experiment_core(
            experiment_id, started_at,
            use_corrections, use_generated_data, hyperparams, description,
        )
        _persist_experiment(
            status="completed",
            experiment_id=experiment_id,
            started_at=started_at,
            description=description,
            result=result,
            finished_at=time.time(),
        )
        return result
    except Exception as e:
        err_str = f"{type(e).__name__}: {e}"
        _persist_experiment(
            status="failed",
            experiment_id=experiment_id,
            started_at=started_at,
            description=description,
            error=err_str,
            finished_at=time.time(),
        )
        raise


def run_experiment_async(
    use_corrections: bool = True,
    use_generated_data: bool = True,
    hyperparams: dict | None = None,
    description: str = "",
) -> dict:
    """Kick off an experiment in a background thread and return immediately.

    Returns an acknowledgement with the new experiment_id so the caller can
    poll /experiments/status for progress.
    """
    global _current_run
    # Reject overlapping runs so the UI can't accidentally kick off two trainings.
    with _run_lock:
        if _current_run and _current_run.get("status") == "running":
            return {
                "status": "busy",
                "running_experiment_id": _current_run.get("id"),
                "phase": _current_run.get("phase"),
                "message": "An experiment is already running. Wait for it to finish or refresh status.",
            }
        experiment_id = str(uuid.uuid4())[:8]
        started_at = time.time()
        _current_run = {
            "id": experiment_id,
            "status": "running",
            "phase": "queued",
            "started_at": started_at,
            "description": description,
        }

    thread = threading.Thread(
        target=_run_and_track,
        args=(experiment_id, started_at, use_corrections, use_generated_data,
              hyperparams, description),
        daemon=True,
        name=f"experiment-{experiment_id}",
    )
    thread.start()

    return {
        "status": "started",
        "experiment_id": experiment_id,
        "started_at": started_at,
    }


def promote_experiment(experiment_id: str) -> dict:
    """Promote an experiment model to production."""
    exp_model = os.path.join(EXPERIMENTS_DIR, experiment_id, "model.json")
    exp_metrics = os.path.join(EXPERIMENTS_DIR, experiment_id, "metrics.json")

    if not os.path.exists(exp_model):
        return {"error": f"Experiment {experiment_id} model not found"}

    import shutil
    # Backup current production model
    prod_model = os.path.join(MODELS_DIR, "xgboost_fraud.json")
    prod_metrics = os.path.join(MODELS_DIR, "metrics.json")
    if os.path.exists(prod_model):
        shutil.copy2(prod_model, os.path.join(MODELS_DIR, "xgboost_fraud.json.bak"))
    if os.path.exists(prod_metrics):
        shutil.copy2(prod_metrics, os.path.join(MODELS_DIR, "metrics.json.bak"))

    # Copy experiment model to production
    shutil.copy2(exp_model, prod_model)
    if os.path.exists(exp_metrics):
        shutil.copy2(exp_metrics, prod_metrics)

    # Clear the cached model so next inference picks up the new one
    from model_serving.model_utils import get_model
    import model_serving.model_utils as mu
    mu._model = None

    # Record promotion in the history table so the UI can show a badge.
    conn = sqlite3.connect(DB_PATH)
    try:
        _ensure_experiments_table(conn)
        conn.execute(
            "UPDATE experiments SET promoted_at = ? WHERE experiment_id = ?",
            (time.time(), experiment_id),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "promoted": experiment_id,
        "message": f"Experiment {experiment_id} is now the production model.",
    }


def get_experiment_status() -> dict | None:
    """Return current experiment run status for polling."""
    with _run_lock:
        return dict(_current_run) if _current_run else None


def list_experiments() -> list[dict]:
    """List all experiments from the persistent history table.

    Falls back to scanning the filesystem for experiments that predate the
    history table (e.g. created before this commit).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        _ensure_experiments_table(conn)
        rows = conn.execute("""
            SELECT experiment_id, status, description, started_at, finished_at,
                   train_rows, corrections_applied, generated_added,
                   roc_auc, avg_precision, precision_val, recall_val, f1_val,
                   delta_roc_auc, delta_avg_precision,
                   error, promoted_at
            FROM experiments
            ORDER BY started_at DESC
        """).fetchall()
    finally:
        conn.close()

    seen_ids = set()
    experiments = []
    for r in rows:
        d = dict(r)
        seen_ids.add(d["experiment_id"])
        experiments.append({
            "experiment_id": d["experiment_id"],
            "status": d["status"],
            "description": d["description"],
            "started_at": d["started_at"],
            "finished_at": d["finished_at"],
            "promoted_at": d["promoted_at"],
            "error": d["error"],
            "data_summary": {
                "train_rows": d["train_rows"],
                "corrections_applied": d["corrections_applied"],
                "generated_data_added": d["generated_added"],
            },
            "metrics": {
                "roc_auc": d["roc_auc"],
                "avg_precision": d["avg_precision"],
                "precision": d["precision_val"],
                "recall": d["recall_val"],
                "f1": d["f1_val"],
            },
            "deltas": {
                "roc_auc": d["delta_roc_auc"],
                "avg_precision": d["delta_avg_precision"],
            },
        })

    # Fallback: surface filesystem-only experiments that predate the DB table.
    if os.path.exists(EXPERIMENTS_DIR):
        for eid in os.listdir(EXPERIMENTS_DIR):
            if eid in seen_ids:
                continue
            metrics_path = os.path.join(EXPERIMENTS_DIR, eid, "metrics.json")
            if os.path.exists(metrics_path):
                with open(metrics_path) as f:
                    metrics = json.load(f)
                experiments.append({
                    "experiment_id": eid,
                    "status": "completed",
                    "description": None,
                    "metrics": metrics,
                    "data_summary": {},
                    "deltas": {},
                })

    return experiments


def get_experiment_detail(experiment_id: str) -> dict | None:
    """Return the full stored result payload for a single experiment."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        _ensure_experiments_table(conn)
        row = conn.execute(
            "SELECT * FROM experiments WHERE experiment_id = ?",
            (experiment_id,),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        # Fall back to disk for legacy experiments.
        metrics_path = os.path.join(EXPERIMENTS_DIR, experiment_id, "metrics.json")
        if os.path.exists(metrics_path):
            with open(metrics_path) as f:
                return {"experiment_id": experiment_id, "metrics": json.load(f)}
        return None

    d = dict(row)
    result = None
    if d.get("result_json"):
        try:
            result = json.loads(d["result_json"])
        except json.JSONDecodeError:
            result = None
    return {
        "experiment_id": d["experiment_id"],
        "status": d["status"],
        "description": d["description"],
        "started_at": d["started_at"],
        "finished_at": d["finished_at"],
        "promoted_at": d["promoted_at"],
        "error": d["error"],
        "result": result,
    }
