# syntax=docker/dockerfile:1

# ---------- Stage 1: build the React frontend ----------
FROM node:22-slim AS frontend-build
WORKDIR /app/frontend

# Install deps first (cached unless lockfile changes)
COPY app/frontend/package.json app/frontend/package-lock.json ./
RUN npm ci

# Build the production bundle -> /app/frontend/dist
COPY app/frontend/ ./
RUN npm run build


# ---------- Stage 2: Python runtime (serves frontend + co-located backend) ----------
FROM python:3.12-slim AS runtime
WORKDIR /app

# libgomp1 is required by xgboost; curl is handy for healthchecks
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

# Python deps (cached unless requirements.txt changes)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Application source (data/ and models/ are excluded via .dockerignore and
# mounted as volumes at runtime so the generated DB / trained model persist)
COPY . .

# Drop in the built frontend from stage 1
COPY --from=frontend-build /app/frontend/dist ./app/frontend/dist

RUN chmod +x deploy/docker-entrypoint.sh

# The frontend serves the UI on 8100 and starts the backend on 7078 internally.
ENV BACKEND_PORT=7078 \
    FRONTEND_PORT=8100 \
    PYTHONUNBUFFERED=1
EXPOSE 8100

# The entrypoint seeds config.yaml and builds the dataset + model on first run;
# "prod" forces serve_production(): builds nothing, serves dist/, spawns the backend.
ENTRYPOINT ["/app/deploy/docker-entrypoint.sh"]
CMD ["python", "app/start_frontend.py", "prod"]


# ---------- Stage 3 (opt-in): same runtime + NVIDIA RAPIDS ----------
# Only usable on a CUDA 12.x host with the NVIDIA container toolkit — the
# wheels are CUDA-only, so this stage is useless on AMD/ROCm or CPU-only hosts.
# Build it with docker-compose.gpu.yml; gpu_utils.py picks RAPIDS up
# automatically and the /api/config/gpu endpoint then reports the GPU.
FROM runtime AS runtime-gpu

COPY requirements-gpu.txt ./
RUN pip install --no-cache-dir --extra-index-url https://pypi.nvidia.com \
    -r requirements-gpu.txt


# ---------- Stage 4 (opt-in): build AMD's HIP fork of XGBoost ----------
# There is no ROCm XGBoost wheel on PyPI, so it is compiled here. AMD supports
# this fork on Instinct (gfx942/gfx950) only; gfx1201 (Radeon AI PRO R9700) is
# an unsupported target, so the compile may fail or produce a binary the card
# rejects at train time. gpu_utils.xgboost_gpu_available() probes for exactly
# that and drops the pipelines back to CPU, so a failed GPU is not a failed app.
# RAPIDS is NOT part of this stage: cuDF/cuML have no AMD build, so dataframes
# stay on the CPU and only XGBoost training is accelerated.
FROM rocm/dev-ubuntu-24.04:7.2.1-complete AS rocm-xgboost-build

ARG AMDGPU_TARGETS=gfx1201

ENV ROCM_PATH=/opt/rocm \
    HIP_PATH=/opt/rocm

# rocthrust/hipcub/rocprim are what the HIP backend actually compiles against.
# The -complete tag should already carry them; installing explicitly means a
# missing one fails here, by name, instead of surfacing as a header-not-found
# error thousands of lines into the ninja output.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       git cmake ninja-build build-essential python3-dev python3-pip \
       rocthrust-dev hipcub-dev rocprim-dev \
    && rm -rf /var/lib/apt/lists/*

# A failed HIP build still produces a usable image, so its layer caches like any
# other and would never be retried. Bump this (compose: build.args) to force a
# fresh clone and rebuild without needing --no-cache from a CLI.
ARG BUILD_ATTEMPT=1
RUN echo "ROCm XGBoost build attempt ${BUILD_ATTEMPT}"

WORKDIR /src
RUN git clone --recursive --depth 1 https://github.com/ROCm/xgboost.git

# The build is allowed to fail. gfx1201 is not a target AMD supports for this
# fork, and a broken GPU build must not cost the whole image — the runtime
# stage falls back to the CPU wheel. Everything needed to diagnose a failure is
# written to /out, which the entrypoint prints on startup, because the build
# log itself is not visible through the deployment UI.
#
# find_package(hip) needs hip-config.cmake, and cmake does not locate it on its
# own even though the HIP compiler is detected fine — that is what failed the
# first build here. The path is discovered rather than assumed: ROCm installs
# under a versioned prefix (/opt/rocm-7.2.1) with /opt/rocm as a symlink, and
# the cmake directory has moved between releases.
WORKDIR /src/xgboost/build
RUN set +e; \
    mkdir -p /out; \
    HIP_CONFIG="$(find /opt -name hip-config.cmake -print -quit 2>/dev/null)"; \
    HIP_DIR="$(dirname "${HIP_CONFIG:-/nonexistent/x}")"; \
    { \
      echo "hip-config.cmake: ${HIP_CONFIG:-NOT FOUND}"; \
      echo "hip_DIR: ${HIP_DIR}"; \
      cmake .. -GNinja \
        -DUSE_HIP=ON \
        -DUSE_RCCL=OFF \
        -DAMDGPU_TARGETS=${AMDGPU_TARGETS} \
        -DCMAKE_HIP_ARCHITECTURES=${AMDGPU_TARGETS} \
        -DCMAKE_PREFIX_PATH="${ROCM_PATH};${HIP_DIR}" \
        -Dhip_DIR="${HIP_DIR}" \
        -DCMAKE_BUILD_TYPE=Release \
      && ninja; \
    } > /out/build.log 2>&1; \
    if [ $? -eq 0 ]; then \
      cd /src/xgboost/python-package \
      && pip3 wheel --no-deps --wheel-dir /out . --break-system-packages >> /out/build.log 2>&1 \
      && echo "XGBoost ROCm/HIP build SUCCEEDED for AMDGPU_TARGETS=${AMDGPU_TARGETS}" > /out/BUILD_STATUS; \
    fi; \
    if [ ! -f /out/BUILD_STATUS ]; then \
      { \
        echo "XGBoost ROCm/HIP build FAILED for AMDGPU_TARGETS=${AMDGPU_TARGETS} — the image"; \
        echo "falls back to the CPU wheel and the app still works. Last 40 lines:"; \
        echo "---"; \
        tail -40 /out/build.log; \
      } > /out/BUILD_STATUS; \
    fi; \
    exit 0


# ---------- Stage 5 (opt-in): ROCm runtime ----------
FROM rocm/dev-ubuntu-24.04:7.2.1-complete AS runtime-rocm
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

# Ubuntu 24.04 marks its Python as externally managed, so install into a venv.
RUN python3 -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Replace the stock CPU wheel from requirements.txt with the HIP build, if one
# was produced. No wheel means the HIP build failed; BUILD_STATUS says why and
# the CPU wheel stays in place.
COPY --from=rocm-xgboost-build /out /opt/rocm-xgboost
RUN if ls /opt/rocm-xgboost/xgboost-*.whl >/dev/null 2>&1; then \
      pip install --no-cache-dir --force-reinstall --no-deps /opt/rocm-xgboost/xgboost-*.whl; \
    fi

COPY . .
COPY --from=frontend-build /app/frontend/dist ./app/frontend/dist
RUN chmod +x deploy/docker-entrypoint.sh

ENV BACKEND_PORT=7078 \
    FRONTEND_PORT=8100 \
    PYTHONUNBUFFERED=1
EXPOSE 8100

ENTRYPOINT ["/app/deploy/docker-entrypoint.sh"]
CMD ["python", "app/start_frontend.py", "prod"]
