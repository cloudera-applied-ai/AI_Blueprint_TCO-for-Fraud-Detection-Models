#!/usr/bin/env bash
# Container entrypoint: make the mounted volumes usable, then hand off to CMD.
#
# data/, models/ and config/config.yaml are deliberately NOT in the image
# (gitignored / dockerignored — they hold generated artifacts and credentials),
# so a first run has to produce them or the API answers 503 and the agent
# crashes on a missing config.
set -euo pipefail

cd /app

# On the ROCm image, report how the XGBoost HIP build went — the image build
# log is not reachable through the deployment UI, so it is replayed here.
if [ -f /opt/rocm-xgboost/BUILD_STATUS ]; then
    echo "[entrypoint] --- XGBoost ROCm build ---"
    cat /opt/rocm-xgboost/BUILD_STATUS
    echo "[entrypoint] --- end ---"
fi

mkdir -p data/raw data/processed models

if [ ! -f config/config.yaml ]; then
    echo "[entrypoint] config/config.yaml missing — seeding from config.yaml.example"
    cp config/config.yaml.example config/config.yaml
    echo "[entrypoint] set LLM_PROVIDER / VLLM_ENDPOINT / CAII_ENDPOINT etc. in .env to point the agent at a real endpoint"
fi

if [ "${FRAUD_DETECTION_SKIP_BOOTSTRAP:-0}" != "1" ] \
   && { [ ! -f data/transactions.db ] || [ ! -f models/xgboost_fraud.json ]; }; then
    echo "[entrypoint] no dataset/model found — running the pipeline chain (several minutes)"
    python pipelines/data_generation/generate_synthetic_data.py
    python pipelines/data_pipeline/preprocess.py
    python pipelines/data_pipeline/feature_engineering.py
    python pipelines/model_training/train_xgboost.py
    echo "[entrypoint] bootstrap complete"
fi

exec "$@"
