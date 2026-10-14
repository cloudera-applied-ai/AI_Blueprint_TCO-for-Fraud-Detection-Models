# tests/ — data quality · AI eval

The verification that gates **Phase 5 — Harden**. This accelerator's live verification is
built into the pipeline and app; this folder documents that harness and is where standalone
suites go as they are added.

## What verifies this accelerator today

| Check | Where | What it asserts |
|-------|-------|-----------------|
| Health endpoint | `GET /api/health` (`app/backend/api.py`) | The app is up **and** `data/transactions.db` + `models/xgboost_fraud.json` are present and loadable — `{"status":"ok","database":true,"model":true}`. |
| Training metrics | `pipelines/model_training/train_xgboost.py` → `models/metrics.json` | ROC-AUC / average precision / optimal threshold recorded on a held-out split for every (re)train. |
| Experiment compare-before-promote | `pipelines/model_training/experiment_runner.py` | A retrained candidate is evaluated against the production model's metrics before promotion; promotion backs up the prior artifact (`.bak`). |
| Pipeline prerequisites | `app/start_app.py` | Warns at startup when the DB or model is missing and prints the exact rebuild commands. |

## What goes here (as suites are added)

| Path | Contents |
|------|----------|
| `data-quality/` *(add as needed)* | Checks on the generated estate — schema conformance against `pipelines/data_generation/schema.py`, null/range checks, fraud-rate bounds, row-count reconciliation across raw → processed → SQLite. |
| `ai-eval/` *(add as needed)* | Assertions on `models/metrics.json` vs. explicit gates (e.g. ROC-AUC ≥ 0.99 on the synthetic split), plus agent-tool regression prompts with expected tool-call sequences. |

## Conventions

- Evals assert on the artifacts the pipeline already writes (`models/metrics.json`,
  `models/experiments/*/metrics.json`) — don't re-run training inside a test.
- New suites must be runnable headless (plain `pytest tests/`) and offline — the LLM-touching
  agent paths need a configured endpoint and are exercised manually via the app.

There is no `make test`; the bar before shipping a change is: `/api/health` fully green +
training metrics recorded.
