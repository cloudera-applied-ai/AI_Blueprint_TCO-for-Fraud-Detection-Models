# pipelines/ — the Process layer (data + training chain as AMP tasks)

The scripts that build this accelerator's estate and model. Every step is a standalone
script **run from the project root** (CML sessions/AMP tasks start with cwd = project root;
`data/`, `models/`, `config/` paths are root-relative) and is declared as a task in
`.project-metadata.yaml`.

## What goes here

| Path | Contents | AMP task |
|------|----------|----------|
| `data_generation/generate_synthetic_data.py` | Ingest: synthesizes users, merchants, and 200K transactions across 31 countries with seeded fraud patterns → `data/raw/`. | 2 — Generate Synthetic Data |
| `data_generation/schema.py` | The transaction schema — the single owner of column definitions. | (imported) |
| `data_pipeline/preprocess.py` | Cleaning + type conversions → `data/processed/` parquet. | 3 — Preprocess Data |
| `data_pipeline/feature_engineering.py` | Velocity windows, cross-border indicators, country fraud rates → processed parquet + `data/transactions.db`. | 4 — Feature Engineering |
| `model_training/train_xgboost.py` | Trains the XGBoost classifier (QuantileDMatrix for memory efficiency) → `models/xgboost_fraud.json` + `metrics.json`. | 5 — Train Model |
| `model_training/evaluate_model.py` | Held-out evaluation utilities. | (imported) |
| `model_training/experiment_runner.py` | The experiment-lab engine: label corrections, additional-data generation, retrain-compare-promote — used by the dashboard and the agent's retrain tool. | (imported by `app/backend/api.py`) |
| `gpu_utils.py` | Single import point for GPU (NVIDIA RAPIDS — cudf/cuml/cupy) vs. CPU (pandas/sklearn) libraries; every pipeline script imports from here instead of doing its own try/except. | (imported) |

## Task chain (declared in `.project-metadata.yaml` — run in this order)

```
1 deploy/install.py                                  install deps · build frontend
2 pipelines/data_generation/generate_synthetic_data.py
3 pipelines/data_pipeline/preprocess.py
4 pipelines/data_pipeline/feature_engineering.py
5 pipelines/model_training/train_xgboost.py
6 app/start_frontend.py                             start_application (dashboard)
```

## Conventions

- Scripts are **runnable from the project root** and also directly importable — each one
  guards `__file__` with a `try/except NameError` → `os.getcwd()` fallback (CML runs
  scripts in an IPython kernel where `__file__` may be undefined).
- GPU never required: import `gpu_utils` for the pandas/cudf choice;
  `FRAUD_DETECTION_FORCE_CPU=1` forces the CPU path.
- Retraining lives here (`experiment_runner.py`), even though it is *triggered* from the
  Serve layer — the dashboard and agent import it, they don't reimplement it.

Run in order from the project root: `python pipelines/data_generation/generate_synthetic_data.py`
… then start the app. Full guide: [`../docs/APP_GUIDE.md`](../docs/APP_GUIDE.md).
