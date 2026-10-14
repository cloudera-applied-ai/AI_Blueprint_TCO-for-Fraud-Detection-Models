# Fraud Detection Demo Script (3 minutes)

**Audience:** Broad — finance, telco, any vertical with a fraud pipeline already in place.
**Core message:** You already have fraud detection. Cloudera makes it **explainable, governable, monitorable, and re-trainable** — at a fraction of the cost, running wherever your data lives.

**Cloudera solutions touched at each step:**
| Step | Cloudera product |
|---|---|
| Ingest & lakehouse | **Cloudera DataFlow (NiFi)** + **Open Data Lakehouse (Iceberg)** |
| Governance & lineage | **Shared Data Experience (SDX)** — Atlas + Ranger |
| Private inference | **Cloudera AI Inference Service (CAII)** on-prem |
| Monitoring & drift | **Cloudera AI Observability** |
| Retrain & promote | **Cloudera AI (CML)** experiments + **Model Registry** |

---

## 0:00 – 0:20 — Hook (before you click anything)

> "Most of you already have a fraud pipeline. The hard parts aren't detection — they're **explaining** why something fired, **governing** the data the model sees, **monitoring** drift, and **retraining** without a quarter-long project. Cloudera gives you all four on one platform. Let me show you in under three minutes."

**One sentence, then share the screen.**

---

## 0:20 – 0:45 — Dashboard + trend drill-down (1 click)

**On screen:** Risk Dashboard with monthly fraud trend + top-merchants bar chart.

> "200,000 transactions, 31 countries. In production this is landed by **Cloudera DataFlow** — NiFi moves **over a petabyte a day** at customers like T-Mobile — into an **Iceberg open lakehouse**. Same data, queryable from Spark, Impala, Flink, and the model, with no copies."

**Click the tallest peak on the Monthly Fraud Trend.**

> "One click drills into that month's fraud, ranked by dollar value. No SQL, no ticket — the agent is reading the same Iceberg tables your data scientists use."

---

## 0:45 – 1:20 — Agent-driven fraud lineage + governance (1 chat message)

**On screen:** Chat panel.

> "Type: *trace the fraud lineage from the top fraud merchant — who was affected, which transactions, and why was the biggest one flagged.*"

**Wait ~10 seconds — agent chains four tools automatically.**

> "One sentence, four tools: **dashboard → trace_fraud_network → query_transactions → explain_prediction.** Merchant → affected users → specific transactions → SHAP explanation. An afternoon of analyst work in ten seconds."

> "Now look at the response — **card number is `card_****XX`**, emails and phones show `XXX-REDACTED`. That's **Shared Data Experience — Atlas for lineage, Ranger for column-level masking** — enforced *at the prompt boundary, before the LLM ever sees PII.* Auditors love it. And every tool call is lineage-tracked in Atlas, so you can answer 'what did the model see?' in a compliance review."

---

## 1:20 – 1:45 — Cost counter (the kicker)

**On screen:** Point to the Cost Counter dropdown in the top-right.

> "That conversation used about **4,200 tokens**. On OpenAI GPT-4o, roughly **$0.04**. On **Cloudera AI Inference Service** running **Nemotron on your own H100s — effectively zero per-token cost.** Open the dropdown — that's real TCO: GPU energy, hardware amortization, PUE, maintenance. Not marketing math."

> "Because it's Cloudera, this runs **hybrid** — burst training to cloud, keep inference and regulated data on-prem. Same platform, same governance, no vendor lock-in."

---

## 1:45 – 2:15 — Threshold tuning + drift monitoring (Cloudera AI Observability)

**On screen:** Threshold Analysis panel.

**Slide the threshold.**

> "Your existing model has a threshold — probably 0.5. Drop it: false negatives fall, false positives spike. Push it up: you miss fraud. The F1 curve is live — scored in **Cloudera AI** against the same test set as production."

**Switch to the Monitor panel.**

> "And here's the other half — **Cloudera AI Observability** watching for feature drift between training and live traffic. When your customer mix shifts or fraud patterns evolve, this panel lights up *before* your detection rate silently degrades. That's the difference between running a model and **operating** one."

---

## 2:15 – 2:45 — Experiment Lab — retrain + promote (1 click)

**On screen:** Experiment Lab panel.

> "Last piece. Your analyst finds a batch of mislabeled transactions. In most shops that's a Jira ticket and a six-week retrain cycle. Here —"

**Click Retrain.**

> "— corrections applied, optional synthetic data augmentation, **XGBoost retrained in Cloudera AI**, evaluated against the same holdout, deltas shown versus production. If it's better, one click **promotes it through the Cloudera AI Model Registry** — previous model auto-backed up, inference cache cleared, CAII serves the new weights. Full MLOps loop, inside the same UI."

---

## 2:45 – 3:00 — Close

> "Same fraud data, same XGBoost model. What Cloudera adds:
> 1. **Explainability + governance** — SDX masks PII at the prompt boundary, Atlas tracks lineage.
> 2. **Economics** — CAII private inference at effectively $0 per token, hybrid by default.
> 3. **Observability + retraining** — drift monitoring and a one-click retrain-and-promote loop through the Model Registry.
>
> One platform, from ingest to inference to retrain. Let's talk about your fraud pipeline."

---

## Click count: 4 clicks + 1 chat message
1. Peak on Monthly Fraud Trend (drills to that month)
2. One chat message — *"trace the fraud lineage from the top merchant…"*
3. Threshold slider
4. Monitor tab
5. Experiment Lab → Retrain

## The lineage chain (what the agent does on that one prompt)
1. `get_risk_dashboard(group_by="merchant")` → top fraud merchant
2. `trace_fraud_network(merchant_name=X)` → affected users + sample tx ids
3. `query_transactions(user_id=Y, merchant_name=X, is_fraud=true)`
4. `explain_prediction(transaction_id=T)` → SHAP

All four run inside the agent's ReAct loop. Right panel updates to the final SHAP chart.

## Cloudera soundbites (one per beat)
- **NiFi** — petabyte/day ingest reliability
- **Iceberg open lakehouse** — one copy, every engine
- **SDX (Atlas + Ranger)** — governance-at-prompt, PII masking, lineage
- **Cloudera AI Inference Service (CAII)** — $0/token vs. OpenAI on your own GPUs
- **Cloudera AI Observability** — live drift detection
- **Cloudera AI + Model Registry** — experiment, compare, promote, one-click
- **Hybrid** — burst train to cloud, serve on-prem, same governance everywhere

## Things deliberately NOT shown
- Synthetic data generation UI (mentioned verbally only)
- Full transaction list (noise)
- Settings panel / GPU toggle (technical rabbit hole)
- Pipeline panel (save for deep-dive follow-up)

## Governance talking point — verbatim option
> "Watch closely — `card_****87`, not a real PAN. That's **Ranger** column-level masking stripping PII out of every tool response before it reaches the model, and **Atlas** recording lineage for every call. You can run generative AI on regulated data without a compliance review every sprint."

## Cost talking point — verbatim option
> "The dropdown shows **three** cost lines: energy at your `$/kWh`, hardware amortization across the H100s, and maintenance. That's the real number your CFO wants — not 'it's free because it's local.' Change the GPU preset in Settings and the math re-runs live."
