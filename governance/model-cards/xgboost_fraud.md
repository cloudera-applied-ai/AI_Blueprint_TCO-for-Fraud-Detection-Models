# Model card — Transaction Fraud Detection (xgboost_fraud)

- **Accelerator:** `cloudera-forge-fsi-fraud-detection`
- **Serving:** in-process via `app/backend/model_serving/model_utils.py` (dashboard + agent
  tools); `app/backend/model_serving/predict.py` wraps the same scorer as a standalone CML
  model endpoint if deployed
- **Artifacts:** `models/xgboost_fraud.json` (booster) · `models/preprocessor.pkl` ·
  `models/feature_names.json` · `models/metrics.json` (all pipeline outputs, gitignored)
- **Model:** XGBoost binary classifier trained with `QuantileDMatrix`; explanations via
  native `pred_contribs` (SHAP values, GPU-capable)
- **NIM model ID:** _n/a (custom XGBoost model)_ — the **agent's** LLM is a separate,
  configurable endpoint (Cloudera AI Inference / vLLM / Ollama via `config/config.yaml`).

## Intended use

Binary **transaction fraud scoring** with a fraud probability and per-feature SHAP
explanation, used to triage transactions and power the analyst agent's investigation tools.
Demo/accelerator use on synthetic data. Not for production adjudication, credit, or
adverse-action decisions without retraining and validation on the deploying institution's
real estate.

## Training / source data

- **Fully synthetic**: `pipelines/data_generation/generate_synthetic_data.py` creates
  ~200K transactions across 31 countries with seeded fraud patterns (cross-border,
  high-velocity, unusual-amount).
- Features: `pipelines/data_pipeline/feature_engineering.py` — velocity windows,
  cross-border indicators, country fraud rates; preprocessor fitted in training and
  persisted (`preprocessor.pkl`), reused transform-only at scoring time.
- Retraining: the experiment lab (`pipelines/model_training/experiment_runner.py`) supports
  label corrections + additional generated data, with compare-then-promote semantics
  (promotion backs up the prior model as `.bak`).

## Evaluation

From `models/metrics.json` (held-out split, current trained artifact):

| Metric | Value |
|--------|-------|
| ROC-AUC | 0.9995 |
| Average precision | 0.9909 |
| Optimal threshold | 0.9272 |

> Synthetic-data caveat: the seeded fraud patterns are learnable by construction — these
> numbers demonstrate the pipeline, not expected real-world performance.

## Limitations & risks

- **Synthetic estate only** — no validation on any real transaction population, fraud mix,
  or adversarial drift; expect materially lower separability on real data.
- Threshold (0.927) is optimized on the synthetic distribution; re-derive per deployment
  (the dashboard's threshold-analysis view exists for exactly this).
- Drift monitoring is a point-in-time agent tool (`ai/agents/tools/drift_monitor.py`), not a
  scheduled job.
- SHAP values come from `pred_contribs` on the trained booster — they explain the model,
  not ground-truth causality; PII is masked before agent/LLM exposure but the underlying
  SQLite estate is unencrypted.

## Owner

- Forge Engineering · <team-contact>
