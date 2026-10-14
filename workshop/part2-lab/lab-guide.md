# Hands-On Lab: Explainable Scoring, Agent Investigation & In-App Retraining (60 min)

You are driving a full-stack fraud-detection application on Cloudera: a 200K-transaction
synthetic card estate, an XGBoost model with per-decision SHAP explanations, and a ReAct
LLM agent with fraud tools wired into the analyst cockpit.

**Your instance URL:** ______________________ (provided by the instructor)

| Exercise | Time | You will |
| --- | --- | --- |
| 1. Score & explain | 12 min | Read the dashboard, score transactions, decode SHAP explanations |
| 2. Investigate with the agent | 15 min | Trace a fraud ring conversationally; inspect tools, PII masking, cost |
| 3. Retrain & promote | 15 min | Correct labels, train a candidate, compare, promote to production |
| 4. Threshold & drift | 10 min | Pick an operating point; measure feature drift 2018 → later years |
| 5. Stretch goals | spare | Raw API, TCO calculator, export, docker internals |

> ✅ **Checkpoint** boxes mark what you should see before moving on. If one fails, flag
> the instructor rather than debugging solo.

---

## Exercise 1 — Score & explain (12 min)

### 1.1 Read the estate

Open your instance. On the **Dashboard** tab:

> ✅ ~200,000 transactions at a ~3% fraud rate. Use the date-range picker to narrow to
> a single year and watch the aggregates recompute.

### 1.2 Find fraud in the table

Switch to **Transactions**. Filter/sort to surface high-amount or flagged rows and open
one transaction's detail.

### 1.3 Decode a SHAP explanation

Open the explanation view for a fraud-scored transaction (via the transaction detail or
by asking the agent later). Read the panel:

- **base value** — the model's prior before seeing this transaction
- **top features** — up to 10 signed contributions pushing toward fraud or legit

> ✅ For a typical injected fraud, expect drivers like `amount_to_avg_ratio`,
> `is_out_of_state` / `is_cross_border`, `tx_amount_zscore_*`, velocity counts, or the
> late-night time features — the five injected patterns, visible in the attribution.

**Question for the room:** the global top feature is `amount_to_avg_ratio`
(mean |SHAP| 2.67) — why is *ratio to the user's own average* stronger than raw
`amount`? What does that say about behavioral features vs. point features?

---

## Exercise 2 — Investigate with the agent (15 min)

### 2.1 Ask for an investigation

In the chat panel, try one of the suggested prompts or type:

> *"Trace fraud from the merchant with the most fraudulent transactions — show me which
> customers were affected."*

Watch the right-hand panel switch as the agent works: it drives the same views you just
used by hand.

> ✅ The agent answers with concrete numbers (merchant, counts, amounts) and the fraud
> network / investigation panel renders the ring it traced.

### 2.2 Open the Trace tab

Every claim has a paper trail. The **Trace** tab lists the tool calls the agent made
(`query_transactions`, `investigate_merchant`, `trace_fraud_network`, …), with
arguments and results — up to 5 tool rounds per turn.

> ✅ You can match each sentence of the agent's answer to a specific tool call. That's
> the anti-hallucination story: the agent reports what the tools returned.

### 2.3 Check the governance boundary

Look at a tool result in the trace that involves customer/card data.

> ✅ Card identifiers reach the LLM masked (`card_****XX`); emails/phones/SSNs are
> redacted, with a `_governance` note naming the policy. The UI itself shows operators
> full values — only the LLM payload is masked.

### 2.4 Read the cost counter

Find the session cost widget. It tracks the tokens your conversation used and compares
cloud-API pricing against on-prem NVIDIA GPU serving (TCO presets configurable in
Settings).

**Try two more prompts:** *"Explain why transaction <id from Exercise 1> was flagged"*
(watch it call `explain_prediction`) and *"Has the model drifted since 2018?"* (watch
`monitor_drift` — a preview of Exercise 4).

---

## Exercise 3 — Retrain & promote (15 min)

Switch to the **Retrain** tab (Experiment Lab). Three steps, left to right.

### 3.1 Review Data — correct labels

The false-positive review lists transactions where the label and the model disagree.
Pick 3–5 rows, review their details, and correct labels where you judge the label wrong.
Corrections persist in the `label_corrections` table.

### 3.2 Prepare & Train

Optionally generate 10,000 additional synthetic transactions, then launch the training
run. One experiment runs at a time; status streams live (~1 minute).

> ✅ The run completes and appears in the experiment history with an 8-character id.

### 3.3 Compare Results

Candidate vs. incumbent, side by side: ROC-AUC / precision / recall / F1 with deltas,
confusion matrices, and top-feature lists.

**Read it critically:** did your corrections + extra data move recall? At what precision
cost? The best recorded experiment reached precision 0.951 / recall 0.965 / F1 0.958 —
where did yours land?

### 3.4 Promote

If the candidate wins, click **Promote**.

> ✅ The candidate becomes `models/xgboost_fraud.json`; the incumbent is backed up as
> `xgboost_fraud.json.bak` and the experiment history stamps `promoted_at`. Re-score a
> transaction from Exercise 1 — the score now comes from *your* model.
>
> This backup-then-promote step is the Model Registry promotion pattern in miniature —
> in production CML this is a registry-governed, versioned, auditable operation.

*(Made it worse? Restoring the `.bak` file is the rollback — ask the instructor.)*

---

## Exercise 4 — Threshold & drift (10 min)

### 4.1 Pick the operating point

Open the **Threshold** tab: a 19-point sweep (0.05 → 0.95) over a balanced sample, with
score distributions.

**Scenario:** your fraud-ops team can review 200 alerts/day. Move along the curve and
decide: which threshold balances catching fraud against that capacity? Note the shipped
"optimal" (F1-argmax) threshold is **0.927** — is F1 the right objective for *your*
scenario?

### 4.2 Measure drift

Ask the agent *"How has the model drifted between 2018 and 2024?"* or call the drift
view directly. PSI per feature, banded: <0.1 stable · ≤0.25 moderate · >0.25
significant, plus performance-over-time.

> ✅ You can name which features moved most since the 2018 training window — the
> monitoring conversation ("when do we retrain?") now has data behind it, and you just
> practiced the retrain in Exercise 3.

---

## Exercise 5 — Stretch goals (spare time)

- **Raw API:** from a terminal:
  `curl -s localhost:7078/api/health`,
  `curl -s "localhost:7078/api/transactions/<id>/score?explain=true"`,
  `POST /api/transactions/query`. Interactive docs at the backend's `/api/docs`.
  Everything the UI and agent do is a governed API call.
- **CML Model endpoint wrapper:** open `app/backend/model_serving/predict.py` — 22
  lines that make this model a deployable CML Model REST endpoint
  (`{"transaction": {...}, "explain": true}` → score + SHAP).
- **TCO deep-dive:** Settings → On-Prem TCO. Switch GPU presets (H100 SXM → L40S →
  RTX 4090) and watch the per-token economics shift; adjust PUE and utilization.
- **Export:** `GET /api/export/transactions` — CSV download for downstream analysis.
- **GPU check:** Settings → GPU/RAPIDS shows whether the pipeline ran cuDF/cuML or CPU;
  `FRAUD_DETECTION_FORCE_CPU=1` is the escape hatch.

---

## Wrap-up: what you can now say to a customer

1. "Every fraud score comes with a **signed, per-feature explanation** your analysts and
   auditors can read — and an agent that investigates in plain English, with a visible
   tool-call trace."
2. "Analyst corrections become a **retrained, compared, and promoted model** without a
   data-science ticket — the Model Registry pattern, demonstrated live."
3. "It runs end-to-end on **Cloudera AI** today — synthetic data, minutes to train —
   and every layer names its production service: Iceberg + Impala, CDE pipelines,
   CML Models + Registry, and NVIDIA-GPU-served LLMs behind Cloudera AI Inference."
