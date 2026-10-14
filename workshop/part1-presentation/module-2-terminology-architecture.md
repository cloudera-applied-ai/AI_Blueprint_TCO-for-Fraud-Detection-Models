# Module 2 — Core Terminology & Architecture (15 min)

**Goal:** attendees can whiteboard the full path — *raw transaction → 30 engineered
features → XGBoost score → SHAP explanation → agent investigation* — and name the
engineering choices that make each stage credible.

---

## Slide 2.1 — Feature engineering: where the signal lives (4 min)

**On the slide**

30 features in four families (`pipelines/data_pipeline/`):

| Family | Examples |
| --- | --- |
| **Velocity** | `tx_count_last_1h`, `tx_count_last_24h`, `amount_last_24h` — time-based rolling windows, `closed="left"` (no peeking at the current row) |
| **Behavioral deviation** | `tx_amount_zscore_user`, `tx_amount_zscore_merchant`, `amount_to_avg_ratio` |
| **Risk encodings** | target-encoded `merchant_fraud_rate`, `mcc_fraud_rate`, `state_fraud_rate`, `country_fraud_rate` |
| **Time & context** | cyclical `tx_hour_sin/cos`, `tx_day_of_week_sin/cos`, `is_out_of_state`, `is_cross_border`, chip/online/swipe one-hots |

**Speaker notes**

- This is the classical answer to "behavioral context": you *engineer* what a foundation
  model would learn. Velocity windows and z-scores are the analyst's intuition, encoded.
- Call out the `closed="left"` detail — the rolling windows exclude the current
  transaction, so there's no label leakage through the features. Data scientists in the
  room will check.
- Cyclical encodings (sin/cos) let trees see that 23:00 and 01:00 are neighbors —
  exactly the late-night fraud pattern injected into the data.
- GPU note: the whole pipeline runs through `pipelines/gpu_utils.py` — cuDF/cuML
  (RAPIDS) when an NVIDIA GPU is present, pandas/sklearn otherwise, same outputs either
  way. One import point, one escape hatch (`FRAUD_DETECTION_FORCE_CPU=1`).

---

## Slide 2.2 — The model: XGBoost, tuned for imbalance (3 min)

**On the slide**

- Binary XGBoost, `scale_pos_weight` computed from the actual class ratio (~32:1),
  512 boosting rounds with early stopping (50), eval on AUC + AUC-PR + logloss.
- `QuantileDMatrix` — ~25% of the memory of a float DMatrix with hist trees.
- GPU-optional: `gpu_utils.get_xgboost_gpu_params()` flips `tree_method`/`device` when
  RAPIDS is present.
- **Operating point is a choice, not a default:** the optimal threshold (0.927) is the
  F1-argmax on the precision–recall curve; the app ships a threshold-analysis view to
  re-pick it per business cost.

**Speaker notes**

- The threshold slide-within-a-slide matters commercially: precision vs. recall is a
  *business* trade (analyst capacity vs. fraud losses), and the app makes it a visual,
  interactive decision — 19-point sweep, score histograms, per-threshold confusion
  matrices. That's the lab's Exercise 4.
- Code anchor: `pipelines/model_training/train_xgboost.py` (hyperparameters at lines
  65–87, all seeded).

---

## Slide 2.3 — Explainability: SHAP on every score (4 min)

**On the slide**

- Every scored transaction returns its **SHAP decomposition**: base value + top-10
  feature contributions, each signed (pushes toward fraud / toward legit).
- Implementation detail that matters: XGBoost's **native `pred_contribs`** — GPU-capable
  and dependency-free — not the CPU-only `shap` TreeExplainer package.
- Global view: mean-|SHAP| feature importance. Top signals in the shipped model:
  `amount_to_avg_ratio` (2.67), `is_out_of_state` (2.06), `amount` (1.34),
  `tx_amount_zscore_merchant` (1.34).
- Surfaced three ways: the score API (`?explain=true`), the SHAP panel in the UI, and
  the agent's `explain_prediction` tool.

**Speaker notes**

- The top-features list is the model audit in one glance: the model learned *behavioral
  deviation* and *geography* — exactly the injected fraud patterns — not just "big
  amount = fraud".
- For model-risk audiences: per-decision attribution + a model card
  (`governance/model-cards/xgboost_fraud.md`) is the explainability package they ask
  for.
- Code anchor: `compute_shap()` in `train_xgboost.py` (5,000-row sample);
  `app/backend/model_serving/model_utils.py` for the serving-time path.

---

## Slide 2.4 — The agentic layer: a ReAct analyst with fraud tools (4 min)

**On the slide**

- A **ReAct-style LLM agent** (up to 5 tool rounds) drives the right-hand panel of the
  cockpit. Tool registry (11 tools): `query_transactions`, `score_transaction`,
  `explain_prediction`, `get_risk_dashboard`, `detect_alert_patterns`,
  `analyze_threshold`, `monitor_drift`, `investigate_merchant`, `trace_fraud_network`,
  `generate_training_data`, `retrain_model`.
- **LLM served your way:** Cloudera AI Inference (CAII), self-hosted vLLM, or local
  Ollama — an OpenAI-compatible client, switchable in the Settings panel.
- **Governance at the prompt boundary:** PII masking (`card_id → card_****XX`,
  emails/phones/SSNs → redacted) before anything reaches the LLM; analysts still see
  full values in the UI.
- **Cost accountability:** a live per-session token counter with cloud-API price
  comparison and an on-prem GPU TCO calculator (NVIDIA H100/A100/L40S presets).

**Speaker notes**

- The agent is not a chatbot bolted on: its tools are the *same functions* the API and
  UI use, so every claim it makes is backed by a real query, a real score, a real SHAP
  vector — and the Trace tab shows the tool calls.
- Production-hardening details worth naming (they're in `ai/agents/agent.py`): argument
  sanitization/auto-correction, hallucinated-tool-call stripping, reasoning-marker
  cleanup. This is what "agent" means outside a demo notebook.
- The PII mask stamps a `_governance` note on masked payloads — the pattern to show
  compliance teams.
- The cost counter is a sales weapon: it prices the *conversation you just had* against
  cloud APIs and against amortized NVIDIA hardware. TCO inputs: energy × PUE, hardware
  amortization, maintenance.
- Transition: "A model and an agent are assets only if you can retrain, compare,
  promote, and govern them. Module 3."
