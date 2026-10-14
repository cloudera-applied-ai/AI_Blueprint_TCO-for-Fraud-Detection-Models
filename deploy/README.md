# deploy/ — CML AMP provisioning (in place of CDP CLI / Terraform)

Stands up the environment this accelerator runs in. There is no IaC here: the platform is an
existing **CML workspace**, and provisioning is an idempotent Python setup executed as the
AMP's first task — so the solution still deploys clean from the repo alone.

## What goes here

| Path | Contents | Automated by |
|------|----------|--------------|
| `install.py` | The full environment setup: resource validation, `data/`+`models/` directory creation, Python deps from `requirements.txt` (auto-detects a GPU and adds `requirements-gpu.txt` RAPIDS packages), Node.js (via nvm if absent), and the production React frontend build. | CML AMP task 1 (`run_session`, 2 vCPU / 4 GB / 1 GPU) |
| *(repo root)* `requirements.txt` · `requirements-gpu.txt` | Python dependency manifests. Stay at root: consumed by both `install.py` and the `Dockerfile`. | — |
| *(repo root)* `Dockerfile` · `docker-compose.yml` · `.dockerignore` | The on-prem/local container path — same app, LLM endpoint stays remote. One self-contained compose file with no overrides or profiles, so it deploys through an orchestration UI as-is. It targets the `runtime-rocm` stage (AMD's HIP fork of XGBoost, `/dev/kfd` + `/dev/dri` passed through); the `runtime` (CPU) and `runtime-gpu` (NVIDIA + RAPIDS) stages are swapped in per the instructions at the foot of the file. Root: Docker build-context convention. | `docker compose up -d --build` |
| `docker-entrypoint.sh` | Container first-run bootstrap: seeds `config/config.yaml` from the example, then runs the pipeline chain if `data/transactions.db` or `models/xgboost_fraud.json` is missing. | The image's `ENTRYPOINT` |

## Environment variables

- `FRAUD_DETECTION_FORCE_CPU=1` — force CPU mode even when a GPU is present.
- `FRAUD_DETECTION_SKIP_BOOTSTRAP=1` — skip the container's first-run data generation and
  model training (Docker path only).
- Llama Guard (`GUARD_ENABLED`, `GUARD_MODEL`, `GUARD_ENDPOINT`, `GUARD_API_KEY`) — screens
  each question before the agent runs and each answer before it reaches the UI. Off unless
  `GUARD_ENABLED=1`; a blank `GUARD_ENDPOINT` reuses the chat provider's connection, and an
  unreachable guard fails open so the demo keeps working.
- `BACKEND_PORT` (default 7078) / `FRONTEND_PORT` (default 8100) — local ports; in CML the
  Application binds `CDSW_APP_PORT`.
- LLM provider settings (`LLM_PROVIDER`, `CAII_ENDPOINT`, `CDP_TOKEN`, `VLLM_ENDPOINT`,
  `VLLM_API_KEY`, `OLLAMA_ENDPOINT`) — override `config/config.yaml` per-deployment via a
  local `.env` (see `config/.env.example`); **never** committed.

## Conventions

- Provisioning is **idempotent** — `install.py` reruns safely.
- GPU is optional everywhere: `install.py` detects it, `pipelines/gpu_utils.py` abstracts
  the RAPIDS/CPU choice for every pipeline consumer. On AMD there is no RAPIDS, so
  `xgboost_gpu_available()` probes whether XGBoost itself can use the card — XGBoost warns
  and silently downgrades to CPU rather than raising, so the probe watches for that warning.
- Never put accelerator *logic* here — only the environment it runs on.

`python deploy/install.py` stands the environment up; everything after that is
[`../pipelines/`](../pipelines/).
