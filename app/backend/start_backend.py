"""Launch the FastAPI backend server."""

import os
import sys

# Set up paths
try:
    _dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _dir = os.path.join(os.getcwd(), "app", "backend")
PROJECT_ROOT = os.path.dirname(os.path.dirname(_dir))
sys.path.insert(0, _dir)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "ai", "agents"))

import asyncio
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

try:
    from fastapi.responses import ORJSONResponse
    default_response = ORJSONResponse
except ImportError:
    default_response = None

from api import router as api_router

app = FastAPI(
    title="Fraud Detection AI - Backend",
    default_response_class=default_response or None,
)

# All browser traffic arrives same-origin through the frontend proxy, so CORS
# is only enabled when an external origin is explicitly allowed.
_origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]
if _origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix="/api")


@app.get("/")
def root():
    return {"status": "ok", "service": "Fraud Detection API"}


def main():
    # CML may export these as an empty string rather than leaving them unset, so
    # os.environ.get(name, default) yields '' and int('') raises. Treat blank as absent.
    port = next(
        (int(v.strip()) for v in (os.environ.get("CDSW_APP_PORT"), os.environ.get("BACKEND_PORT"))
         if v and v.strip()),
        7078,
    )
    host = "127.0.0.1" if os.path.expanduser("~") == "/home/cdsw" else "0.0.0.0"
    print(f"Starting backend on {host}:{port}...")

    config = uvicorn.Config(app, host=host, port=port)
    server = uvicorn.Server(config)

    # CML runs scripts inside a Jupyter kernel that already has an event loop.
    # uvicorn.run() tries to create a new loop and fails.  Instead, schedule
    # server.serve() on the existing loop when one is running.
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        loop.create_task(server.serve())
    else:
        uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
else:
    # CML runs scripts via Jupyter kernel where __name__ != "__main__"
    main()
