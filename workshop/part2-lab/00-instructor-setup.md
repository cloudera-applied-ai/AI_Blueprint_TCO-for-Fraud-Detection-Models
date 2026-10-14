# Lab 0 — Instructor Setup (complete BEFORE the session)

Budget ~60 minutes the day before. Unlike the TFM workshop, this accelerator has **no
external data or GPU prerequisites** — everything is generated locally — but the agent
needs a reachable LLM endpoint, and that is the one thing you must verify in advance.

## 1. Choose the deployment mode

Per attendee (or pair), one of:

- **Cloudera AI (recommended for the platform story):** deploy the repo as an AMP —
  `.project-metadata.yaml` runs the six tasks (install → generate → preprocess →
  features → train → application). Runtime: JupyterLab / Python 3.11. GPU optional
  (RAPIDS auto-installs when detected).
- **Docker (works on any laptop):** `docker compose up -d --build` → http://localhost:8100.
  Attendees can even run this themselves if the venue network allows.
- **Bare local:** `python deploy/install.py`, then the four pipeline scripts, then
  `python app/start_app.py` (see `docs/EXAMPLE.md`).

Ports: UI **8100** (or `CDSW_APP_PORT` in CML), backend private on **7078**.

## 2. Wire the LLM endpoint (critical path)

The agent needs one of: **Cloudera AI Inference (CAII)**, **vLLM**, or **Ollama**.

1. Copy `config/config.yaml.example` → `config/config.yaml` and fill the `llm:` block,
   or configure it live in the app's **Settings → LLM** panel (provider, endpoint,
   model, key).
2. In CML, the CAII key resolves automatically from the session JWT — no key to paste.
3. Click **Test** in the Settings panel; then send one real chat message end-to-end.

⚠️ Never distribute your own `config/config.yaml` — it may hold live credentials. Point
attendees at `config.yaml.example` and the Settings panel.

Fallback if no shared endpoint is available: a laptop-local Ollama with a small model
per instance. Exercises 1, 3, 4 don't need the LLM at all; only Exercise 2 does.

## 3. Verify the estate and model

On each instance:

```bash
curl -s localhost:7078/api/health        # {"status":"ok","database":true,"model":true}
```

- Dashboard tab shows ~200,000 transactions at a ~3% fraud rate, 2018–2026.
- `GET /api/experiments/original-metrics` returns ROC-AUC ≈ 0.9995 / AP ≈ 0.9909.
- Run one throwaway experiment in the **Retrain** tab to confirm the loop works and to
  time it on your hardware (expect ~1 min); do **not** promote it.

## 4. Dry-run timings on YOUR hardware

| Step | Expected | Yours |
| --- | --- | --- |
| Full pipeline (generate → train), CPU | ~5–10 min | |
| Experiment retrain (Exercise 3) | ~1 min | |
| Agent investigation turn (Exercise 2) | 10–30 s | |

## 5. Fallback plan

- **LLM endpoint down:** run Exercises 1, 3, 4 (no LLM needed); demo Exercise 2 from
  your own instance when it recovers, using the Trace tab to narrate tool calls.
- **An instance breaks:** `docker compose up` a fresh one in ~3 minutes, or pair up.
- **Model file missing/corrupt:** re-run `python pipelines/model_training/train_xgboost.py`;
  a bad promote is reversible — restore `models/xgboost_fraud.json.bak`.

## 6. Handouts / links to circulate

- Lab guide: `workshop/part2-lab/lab-guide.md`
- Glossary: `workshop/glossary.md`
- Each attendee's app URL + which LLM provider is configured
