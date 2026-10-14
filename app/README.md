# app/ — the fraud dashboard (Serve layer)

The user-facing application, run as a **single CML Application**: the frontend server binds
`CDSW_APP_PORT` and reverse-proxies `/api` to a co-located FastAPI backend child process on
`localhost:7078` — no cross-app networking. FastAPI backend + React 19 frontend.

## What goes here

| Path | Contents |
|------|----------|
| `start_frontend.py` | The CML Application entry point (AMP task 6) — serves the production build, spawns + health-checks the backend, proxies `/api/*`; `dev` mode runs Vite instead. |
| `start_app.py` / `stop_app.py` | Local convenience launchers — start/stop backend (:7078) + frontend (:8100) together. |
| `backend/` | FastAPI app: `start_backend.py` (uvicorn around CML's IPython event loop) → `api.py` (all routes: transactions, dashboard, SHAP, thresholds, experiments, agent chat via SSE) → `model_serving/` (XGBoost scoring + SHAP `pred_contribs`, the in-process AI serving path). |
| `frontend/` | React 19 + TypeScript + Tailwind + Vite: risk dashboard, transaction table, SHAP charts, threshold analysis, fraud-network panel, experiment lab, agent chat with live token-cost counter. `dist/` is the production build (built by `deploy/install.py`; gitignored). |

## Run it

```bash
python app/start_app.py                # backend :7078 + frontend :8100 → http://localhost:8100
python app/stop_app.py                 # stop both
cd app/frontend && npx vite            # frontend dev server (proxies /api → :7078)
docker compose up -d --build           # containerized → http://localhost:8100
```

In CML it runs as the Application (AMP task 6, subdomain `fraud-app`); interactive API docs
at `/api/docs` on the backend.

## Conventions

- The frontend binds the public port; the backend stays on localhost — keep new services
  inside this one-Application pattern (CML app discovery/JWT proxying is what it avoids).
- The agent, experiment lab, and scoring routes **import** from `ai/agents/` and
  `pipelines/model_training/` — business logic lives in those layers, `api.py` only routes.
- `config/config.yaml` (LLM provider) is read at request time — the Settings panel writes
  it; it is gitignored (credentials).
- Design system: the app keeps its own dark theme — deviation recorded in
  [ADR-001](../docs/architecture/ADR-001-dashboard-design-system.md).

Full operational guide: [`../docs/APP_GUIDE.md`](../docs/APP_GUIDE.md).
