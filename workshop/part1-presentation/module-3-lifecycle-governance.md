# Module 3 — Model Lifecycle & Governance on Cloudera AI (15 min)

**Goal:** attendees can narrate the human-in-the-loop retraining loop — *correct labels
→ generate data → retrain → compare → promote* — and map every step to the Cloudera
governance primitive it demonstrates.

---

## Slide 3.1 — One-click AMP: six declarative tasks (3 min)

**On the slide**

`.project-metadata.yaml` — "Fraud Detection AI", Python 3.11 runtime:

| # | Task | Script |
| --- | --- | --- |
| 1 | Install Dependencies | `deploy/install.py` (auto-detects NVIDIA GPU → installs RAPIDS) |
| 2 | Generate Synthetic Data | `pipelines/data_generation/generate_synthetic_data.py` |
| 3 | Preprocess Data | `pipelines/data_pipeline/preprocess.py` |
| 4 | Feature Engineering | `pipelines/data_pipeline/feature_engineering.py` |
| 5 | Train Model | `pipelines/model_training/train_xgboost.py` |
| 6 | Fraud Detection AI (application) | `app/start_frontend.py` — public UI on `CDSW_APP_PORT`, FastAPI co-located on private `127.0.0.1:7078` |

**Speaker notes**

- The single-application pattern is a reusable CML lesson: one public port, the SPA
  reverse-proxies `/api/*` to a private in-container backend — no cross-app networking,
  no JWT proxying. Same pattern as the TFM sibling accelerator.
- Tasks 2–5 are exactly the four scripts an SE runs locally — the AMP *is* the
  quickstart, declared.

---

## Slide 3.2 — The Experiment Lab: human-in-the-loop retraining (5 min)

**On the slide**

Three steps in the UI, all in-app:

1. **Review Data** — surface false positives ("labeled fraud, model disagrees"),
   correct labels; corrections persist in a `label_corrections` table.
2. **Prepare & Train** — optionally generate 10K additional synthetic transactions,
   then train a candidate model (one experiment at a time, async with live status).
3. **Compare Results** — candidate vs. incumbent: ROC-AUC / precision / recall / F1
   with deltas, side-by-side confusion matrices, side-by-side top features.

Then **Promote**: the candidate replaces the production model — after the incumbent is
backed up (`xgboost_fraud.json.bak` + metrics), with a `promoted_at` stamp in the
experiment history.

**Speaker notes**

- This is the analyst-feedback flywheel every fraud team wants: their corrections become
  training signal without a data-science ticket.
- The backup-then-promote step is deliberately the **Model Registry pattern in
  miniature** — `docs/architecture/cloudera_deployment_blueprint.md` maps it explicitly
  to registry-governed promotion in production CML (versioned artifacts, rollback,
  audit stamp). Say it that way: "what you just clicked is what the registry does with
  full lineage at enterprise scale."
- Hot-swap detail: the serving layer caches the model in-process; promotion updates the
  artifact the cache reloads from — the next scored transaction uses the promoted model.
- Code anchor: `pipelines/model_training/experiment_runner.py` (908 lines — the whole
  loop, including the `experiments` history table).

---

## Slide 3.3 — Watching the model age: threshold & drift (4 min)

**On the slide**

- **Threshold analysis** (`/api/model/threshold-analysis`): 19-point sweep (0.05–0.95),
  balanced 5,000-row sample, score histogram — pick the operating point that matches
  analyst capacity and fraud cost.
- **Drift monitoring** (`/api/model/drift`): PSI per feature between a reference year
  and a current year (bands: <0.1 stable · ≤0.25 moderate · >0.25 significant), plus
  performance-over-time and score-distribution reports.
- The estate spans 2018–2026 by design, so drift is *demonstrable*, not hypothetical:
  the shipped model trains on the early years and is evaluated on later ones.

**Speaker notes**

- Drift is where fraud models die in production — spending patterns shift, fraudsters
  adapt. PSI-per-feature answers "*which* inputs moved", which is the first question a
  monitoring runbook asks.
- Both views are also agent tools (`analyze_threshold`, `monitor_drift`) — "has my model
  drifted since 2018?" is a chat message.
- Code anchors: `ai/agents/tools/threshold_analysis.py`, `ai/agents/tools/drift_monitor.py`.

---

## Slide 3.4 — Governance as shipped artifacts (3 min)

**On the slide**

- **Model card** — `governance/model-cards/xgboost_fraud.md`: intended use, data,
  metrics, limitations (+ a blank template for the next model).
- **PII masking at the LLM boundary** — masked payloads carry a `_governance` note;
  operators keep full fidelity, the model never sees raw identifiers.
- **Stage gates** — `docs/GATES.md`: six definition-of-done checklists with accountable
  owners; the Harden gate is literally `GET /api/health` returning database + model
  status.
- **Business case** — `docs/business-case/scorecard.md`: weighted score **4.65 / 5**,
  greenlight (≥4.0 advances) — the sourcing-and-scoring discipline behind choosing this
  use case at all.
- **CML Model endpoint wrapper** — `app/backend/model_serving/predict.py`: the 22-line
  `predict(args)` function ready to deploy as a governed CML Model REST endpoint.

**Speaker notes**

- The point of this slide: governance here isn't a slide, it's *files in the repo* you
  can open live. That lands hard with model-risk and platform teams.
- The scorecard doubles as a sales methodology exhibit — show customers how Cloudera
  Forge decides what to build before writing code.
- Transition: "Last module: where each demo layer lands in a production Cloudera
  deployment, what the GPUs do, and what you'll drive in the lab."
