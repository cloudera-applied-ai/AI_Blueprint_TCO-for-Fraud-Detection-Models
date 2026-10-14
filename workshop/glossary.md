# Glossary — Explainable Fraud Detection with Agentic AI (handout)

**Synthetic estate** — the app's self-generated dataset: 200,000 card transactions,
2,000 users, 500 merchants, 3.0% fraud, 2018–2026, 32 countries, 20 MCC codes; seeded
(42) and rebuilt deterministically. Stored in a 47.5 MB SQLite "lakehouse snapshot".

**Injected fraud patterns** — five named generators the model must learn: velocity
bursts, geographic anomalies, late-night spends, online bursts, cross-border hits.

**Feature engineering (30 features)** — velocity windows (`tx_count_last_1h/24h`,
`amount_last_24h`, computed `closed="left"` so the current row never leaks), user- and
merchant-level amount z-scores, target-encoded fraud rates (merchant/MCC/state/country),
cyclical hour/day encodings (sin/cos), channel one-hots, `is_out_of_state`,
`is_cross_border`.

**XGBoost fraud model** — single binary classifier: 512 boosting rounds (early stop 50),
`scale_pos_weight` from the ~32:1 class ratio, `QuantileDMatrix` for memory efficiency.
Headline: **ROC-AUC 0.9995 · Average Precision 0.9909** (synthetic data).

**Optimal threshold (0.927)** — the F1-maximizing point on the precision–recall curve.
The Threshold view re-picks it per business cost: 19-point sweep, score histograms.

**SHAP explanation** — per-transaction decomposition of a score into base value + signed
feature contributions, via XGBoost's native `pred_contribs` (GPU-capable, no extra
dependency). Global top signals: `amount_to_avg_ratio` (2.67), `is_out_of_state` (2.06).

**ReAct agent** — the LLM analyst copilot: reason → call a tool → observe → repeat (max
5 rounds). It can only act through registered tools hitting the real database and model;
the **Trace tab** shows every call.

**Agent tools (11)** — `query_transactions`, `score_transaction`, `explain_prediction`,
`get_risk_dashboard`, `detect_alert_patterns`, `analyze_threshold`, `monitor_drift`,
`investigate_merchant`, `trace_fraud_network`, `generate_training_data`, `retrain_model`.

**PII masking** — applied at the LLM boundary: `card_id → card_****XX`; emails, phones,
SSNs, addresses redacted; masked payloads carry a `_governance` policy note. Operators
see full values in the UI — only the model's view is masked.

**LLM serving options** — Cloudera AI Inference (CAII, NVIDIA-GPU-served), self-hosted
vLLM, or local Ollama — one OpenAI-compatible client, switched in Settings.

**Cost counter / TCO calculator** — live per-session token accounting priced against
cloud APIs (LiteLLM price list, 24 h cache) and against on-prem NVIDIA GPUs (H100 SXM →
RTX 4090 presets): energy × PUE + amortization + maintenance.

**Experiment Lab** — the in-app retraining loop: Review Data (correct labels →
`label_corrections` table) → Prepare & Train (optional +10K synthetic rows, one async
experiment at a time) → Compare Results (metrics deltas, confusion matrices, top
features) → **Promote**.

**Promote with backup** — promotion copies the candidate over the production model after
backing up the incumbent (`xgboost_fraud.json.bak`) and stamps `promoted_at` — the
**Model Registry promotion pattern in miniature**; production CML does the same through
the registry with versioning and approvals.

**Drift monitoring (PSI)** — Population Stability Index per feature between a reference
year and a current year: <0.1 stable · ≤0.25 moderate · >0.25 significant; plus
performance-over-time and score-distribution reports.

**Single-application pattern** — one public CML port: the React SPA binds
`CDSW_APP_PORT` (8100) and reverse-proxies `/api/*` to a private FastAPI backend on
`127.0.0.1:7078` in the same container.

**AMP (six tasks)** — install deps (auto-detects GPU → RAPIDS) → generate data →
preprocess → feature engineering → train → start application.

**RAPIDS (optional)** — cuDF/cuML/CuPy acceleration behind one import point
(`pipelines/gpu_utils.py`), identical outputs on CPU; escape hatch
`FRAUD_DETECTION_FORCE_CPU=1`.

**Deployment blueprint** — the demo→production mapping: SQLite → Iceberg + Impala;
pandas/cuDF → CDE pipelines; in-process model + `.bak` promote → CML Models + Model
Registry; Settings LLM → Cloudera AI Inference; SPA → CML Application.

**Stage gates & scorecard** — the Cloudera Forge operating model: weighted use-case
scorecard (this one: **4.65/5**, greenlight) and six definition-of-done gates; the
Harden gate is `GET /api/health` reporting database + model status.
