# Facilitator Guide — Run of Show, Checkpoints & Q&A

## Run of show (2h00)

| Clock | Segment | Facilitator cues |
| --- | --- | --- |
| 0:00 | Welcome + Module 1 (10') | Open on the two analyst problems (opacity, toil); promise both fixed live by 1:30 |
| 0:10 | Module 2 (15') | Whiteboard the path once: features → XGBoost → SHAP → agent. The `closed="left"` and `pred_contribs` details buy credibility with DS audiences |
| 0:25 | Module 3 (15') | The Experiment Lab slide is the heart — rehearse the "registry pattern in miniature" line verbatim |
| 0:40 | Module 4 (10') | End on the demo→production mapping table + lab logistics (URLs, LLM provider) |
| 0:50 | **Break (10')** | Sanity-check every instance: `/api/health` + one chat message |
| 1:00 | Lab Ex 1 — score & explain (12') | Everyone reads one SHAP panel by 1:08; ask the `amount_to_avg_ratio` question aloud |
| 1:12 | Lab Ex 2 — agent (15') | If the LLM endpoint chokes, demo from your instance and move the room to Ex 3 — it has no LLM dependency |
| 1:27 | Lab Ex 3 — retrain & promote (15') | Get every training run launched by 1:33 (~1 min each); narrate compare/promote over the room |
| 1:42 | Lab Ex 4 — threshold & drift (10') | Run the 200-alerts/day scenario as a group discussion |
| 1:52 | Wrap (8') | The three customer sentences; where the materials live; pitch the sibling TFM workshop as the sequel |

## Hard checkpoints

1. **0:50** — every instance: `/api/health` returns `database: true, model: true`, and
   one agent message round-trips.
2. **1:33** — every attendee has an experiment *running*. Later than that, they still
   finish compare/promote by 1:42.
3. **Any time** — a bad promote is reversible (`models/xgboost_fraud.json.bak`); never
   let an attendee stay stuck on a degraded model.

## Numbers to have memorized

- Estate: 200,000 transactions · 2,000 users · 500 merchants · 3.0% fraud · 2018–2026 ·
  32 countries · 20 MCCs · all seeded (42), fully synthetic.
- Five injected fraud patterns: velocity, geo-anomaly, late-night, online burst,
  cross-border.
- Model: XGBoost, 30 features, 512 rounds (early stop 50), `scale_pos_weight` ≈ 32:1.
- Headline metrics: **ROC-AUC 0.9995 · AP 0.9909 · optimal threshold 0.927**; best
  experiment precision 0.951 / recall 0.965 / F1 0.958.
- Top SHAP features: `amount_to_avg_ratio` 2.67 · `is_out_of_state` 2.06 ·
  `amount` 1.34 · `tx_amount_zscore_merchant` 1.34.
- Agent: ReAct, max 5 tool rounds, 11 registered tools, PII mask at the LLM boundary,
  live cost counter (LiteLLM price list + NVIDIA GPU TCO presets).
- Platform: 6 AMP tasks; UI on 8100 / `CDSW_APP_PORT`, backend private on 7078;
  drift PSI bands <0.1 / ≤0.25 / >0.25; business-case score 4.65/5 greenlight.

## Anticipated Q&A / objection handling

**"0.9995 AUC — really?"**
On synthetic data with known injected patterns — say so before they ask. The takeaway is
the *methodology*: temporal evaluation, PR-curve threshold choice, SHAP attribution,
experiment tracking. On real data the numbers drop; the workflow is what transfers.

**"Is the agent just wrapping GPT? What stops hallucination?"**
The agent can only act through 11 registered tools that hit the real database and model;
the Trace tab exposes every call. `ai/agents/agent.py` additionally sanitizes arguments
and strips hallucinated tool-call text. And the LLM is served *your* way — CAII, vLLM,
or Ollama — never a hardcoded cloud API.

**"What about PII going to the LLM?"**
Masked at the prompt boundary (`card_****XX`, redacted emails/phones/SSNs) with a
`_governance` stamp; operators keep full fidelity in the UI. Show `ai/agents/pii_mask.py`.

**"SQLite? Seriously?"**
For the demo estate, yes — 47.5 MB, zero setup. The deployment blueprint maps it to
Iceberg + Impala; the promote-with-backup maps to Model Registry; the pipelines map to
CDE. Every demo shortcut names its production replacement.

**"Where do NVIDIA GPUs actually matter here?"**
Three places: RAPIDS pipeline acceleration (same code path scales to billions of rows),
XGBoost GPU training, and LLM serving behind CAII. The honest line: this 200K-row
problem trains in minutes on CPU — GPUs are the scale and LLM-economics story, and the
in-app TCO calculator makes that case with the customer's own numbers.

**"How does retraining reach production safely?"**
In-app: backup-then-promote with an audited history table. In production CML: the same
flow through the Model Registry — versioned, approvable, rollbackable. The demo is the
pattern; the registry is the enforcement.

**"Can we do this for AML / claims / disputes?"**
Same skeleton, different tools — the tool registry is the extension point. And the Forge
operating model (scorecard → gates → standard layout) is the repeatable path from idea
to accelerator.

## Failure playbook

| Symptom | Move |
| --- | --- |
| Agent errors / timeouts | Settings → LLM → Test; switch provider (Ollama fallback). Ex 1/3/4 need no LLM |
| `/api/health` shows `model: false` | Re-run `python pipelines/model_training/train_xgboost.py` |
| Promote made things worse | Restore `models/xgboost_fraud.json.bak` (and `metrics.json.bak`) |
| Instance dead | `docker compose up -d --build` a fresh one (~3 min) or pair attendees |
| Experiment stuck "running" | Only one runs at a time — check `/api/experiments/status`; restart backend if truly wedged |

## After the session

- Share `workshop/`, `docs/EXAMPLE.md`, and `docs/presentations/demo_script.md` (the
  3-minute, 4-click customer demo — assign each SE to run it solo within a week).
- Suggested follow-up: the sibling **TFM workshop** (`demo-foundational-model/workshop/`)
  — same platform, foundation-model embeddings story. Position this one as "explainable
  classical + agentic AI", that one as "GPU foundation-model lift".
