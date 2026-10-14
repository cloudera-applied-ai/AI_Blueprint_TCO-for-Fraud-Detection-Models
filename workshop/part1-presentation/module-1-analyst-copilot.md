# Module 1 — From Black Box to Analyst Copilot (10 min)

**Goal:** the audience can explain why fraud detection needs *both* an explainable
classical model and an agentic AI layer — and knows this accelerator runs end-to-end on
a laptop or a single CML session, with zero external data dependencies.

---

## Slide 1.1 — The fraud analyst's two problems (3 min)

**On the slide**

| Problem | What it looks like | What fixes it |
| --- | --- | --- |
| **Opacity** | "The model flagged it. Score: 0.94. Good luck." | Per-transaction SHAP explanations — every score decomposes into named feature contributions |
| **Toil** | Pivoting between dashboards, SQL, and case notes to trace one fraud ring | A ReAct LLM agent with fraud tools that investigates conversationally and drives the visuals |

**Speaker notes**

- Fraud teams don't reject ML because it underperforms — they reject it when they can't
  defend a decision to a customer, an auditor, or a model-risk committee. Explainability
  is a *deployment requirement*, not a nice-to-have.
- The second problem is workflow: even with a good model, an analyst triages a queue by
  hand. The agent turns "show me the merchant with the most fraud and who it hit" into
  one sentence — and the right-hand panel updates with the evidence.
- Position: this accelerator demonstrates both fixes in one running app, deployable
  one-click on Cloudera AI.

---

## Slide 1.2 — A fully synthetic, fully reproducible estate (4 min)

**On the slide**

- **200,000 card transactions**, **2,000 users**, **500 merchants**, **3.0% fraud rate**,
  spanning **2018–2026** — generated deterministically (seed 42), nothing to procure.
- **Five injected fraud patterns** the model must learn: velocity bursts, geographic
  anomalies, late-night spends, online bursts, cross-border hits.
- International texture: 32 countries, 20 merchant category codes, locale-aware merchant
  names.
- The whole estate lives in a **47.5 MB SQLite database** — the demo's "lakehouse
  snapshot"; the production mapping is Iceberg + Impala on Cloudera (Module 4).

**Speaker notes**

- Why synthetic? Zero procurement, zero PII risk, instant rebuild — and the fraud
  patterns are *known*, so you can show the model catching exactly what was injected.
  `pipelines/data_generation/generate_synthetic_data.py` names each injection function.
- The 2018–2026 span is deliberate: the shipped model trains on early years and is
  evaluated on later ones, which powers the **drift monitoring** story in the lab
  (reference year vs. current year, PSI-based).
- Contrast with the sibling TFM accelerator (real TabFormer data, GPU foundation model):
  this one is the classical, runs-anywhere member of the family.

---

## Slide 1.3 — What "good" looks like, measured (3 min)

**On the slide**

- Single XGBoost classifier on **30 engineered features**:
  **ROC-AUC 0.9995 · Average Precision 0.9909 · optimal threshold 0.927**
- Best recorded retrain experiment: precision **0.951**, recall **0.965**, F1 **0.958**
  on a 155K-row held-out set.
- Every one of those numbers is reproduced by running four pipeline scripts — minutes on
  CPU; RAPIDS-accelerated on an NVIDIA GPU.

**Speaker notes**

- Be transparent that these are synthetic-data numbers — the point is not "0.9995 AUC in
  production" but that the *methodology* (temporal evaluation, threshold optimization on
  the PR curve, per-feature SHAP attribution, experiment tracking) is production-shaped.
- The "trains in minutes on CPU" line is a Gate 5 requirement in `docs/GATES.md` — this
  accelerator is deliberately runnable by any SE on any hardware, with the GPU path as
  an upgrade, not a prerequisite.
- Transition: "Let's open the box: the features, the model, the explanations, and the
  agent. Module 2."
