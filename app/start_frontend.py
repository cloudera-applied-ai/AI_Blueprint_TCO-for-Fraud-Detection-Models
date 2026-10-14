"""Launch the React frontend dev server or serve the production build.

Both services run inside this single application: the FastAPI backend is
started as a co-located child process bound to localhost:BACKEND_PORT (7078
by default), and the frontend reverse-proxies /api requests to it.  Keeping
both services in one app avoids the cross-app network hop (and CML app
discovery / JWT proxying) that previously caused networking issues.
"""

import os
import sys
import time
import atexit
import subprocess
import shutil

try:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")
except NameError:
    PROJECT_ROOT = os.getcwd()
    FRONTEND_DIR = os.path.join(PROJECT_ROOT, "app", "frontend")
DIST_DIR = os.path.join(FRONTEND_DIR, "dist")

def _env_int(*names: str, default: int) -> int:
    """Read the first env var that is set to a non-blank value, as an int.

    CML often exports port variables as an empty string rather than leaving them
    unset, so ``os.environ.get(name, default)`` returns ``''`` and ``int('')``
    blows up.  Treat blank/whitespace-only values as absent and fall back.
    """
    for name in names:
        raw = os.environ.get(name)
        if raw is not None and raw.strip():
            return int(raw.strip())
    return default


# Cached environment info — served via /frontend/config/environment for the UI
_discovery_cache: dict | None = None

# Handle to the co-located backend child process
_backend_proc: subprocess.Popen | None = None


def _stop_backend():
    """Terminate the co-located backend child process on shutdown."""
    global _backend_proc
    if _backend_proc and _backend_proc.poll() is None:
        _backend_proc.terminate()
        try:
            _backend_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _backend_proc.kill()


def _wait_for_backend(port: int, timeout: float = 30.0):
    """Block until the backend answers /api/health, or the timeout elapses."""
    import urllib.request

    url = f"http://127.0.0.1:{port}/api/health"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    print("[backend] ready")
                    return
        except Exception:
            pass
        time.sleep(0.5)
    print("[backend] WARNING: readiness check timed out — continuing anyway")


def _start_backend(port: int):
    """Start the FastAPI backend as a child process bound to localhost:<port>."""
    global _backend_proc
    env = os.environ.copy()
    env["BACKEND_PORT"] = str(port)
    # The backend must bind to its OWN localhost port, not the app's public
    # CDSW_APP_PORT (that one belongs to this frontend process).
    env.pop("CDSW_APP_PORT", None)
    backend_script = os.path.join(PROJECT_ROOT, "app", "backend", "start_backend.py")
    print(f"Starting co-located backend on 127.0.0.1:{port} ...")
    _backend_proc = subprocess.Popen(
        [sys.executable, backend_script], env=env, cwd=PROJECT_ROOT,
    )
    atexit.register(_stop_backend)
    _wait_for_backend(port)


def serve_production():
    """Serve the production build via a simple static file server."""
    port = _env_int("FRONTEND_PORT", "CDSW_APP_PORT", default=8100)

    import asyncio
    import uvicorn
    from fastapi import FastAPI, Request
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse, Response
    from fastapi.middleware.cors import CORSMiddleware

    app = FastAPI(title="Fraud Detection AI")
    # The UI is served same-origin and /api is proxied, so CORS is only needed
    # when an external origin is explicitly allowed via ALLOWED_ORIGINS.
    _origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]
    if _origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=_origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    import httpx
    from fastapi.responses import JSONResponse

    global _discovery_cache

    # Start the backend in this same app, bound to localhost:<backend_port>.
    # Both services live in one process tree, so there is no cross-app network
    # hop to discover or authenticate against.
    backend_port = _env_int("BACKEND_PORT", default=7078)
    backend_url = f"http://127.0.0.1:{backend_port}"
    _start_backend(backend_port)

    _discovery_cache = {
        "is_cml": bool(os.environ.get("CDSW_PROJECT_ID")),
        "resolved_backend_url": backend_url,
        "backend_port": backend_port,
    }

    # Mutable state so the proxy target can be inspected at runtime.
    # The backend is co-located in this same app on localhost with a fixed URL
    # (see set_backend_url, which rejects runtime changes), so the UI runs in
    # "embedded" mode — there is no external backend to discover or configure.
    _proxy_state = {"url": backend_url, "client": None, "embedded": True}
    _proxy_state["client"] = httpx.AsyncClient(
        base_url=backend_url, timeout=120.0, follow_redirects=True,
    )
    print(f"Proxying /api/* -> {backend_url}")

    @app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    async def proxy_api(path: str, request: Request):
        client = _proxy_state["client"]
        if not client:
            # No proxy configured and not embedded — nothing to forward to
            if not _proxy_state["embedded"]:
                return JSONResponse(
                    {"error": "No backend URL configured. Set it in Settings."},
                    status_code=502,
                )
            # If embedded, FastAPI already handled it via the included router
            # This route won't match because the router takes precedence
            return JSONResponse({"error": "unexpected"}, status_code=500)

        url = f"/api/{path}"
        if request.url.query:
            url = f"{url}?{request.url.query}"
        body = await request.body()
        headers = {k: v for k, v in request.headers.items()
                   if k.lower() not in ("host", "content-length")}
        resp = await client.request(
            request.method, url, content=body, headers=headers,
        )
        # Drop hop-by-hop / framing headers: the body is re-encoded by Starlette,
        # so upstream content-length / transfer-encoding would conflict.
        _hop_by_hop = {
            "content-length", "transfer-encoding", "connection", "keep-alive",
            "content-encoding", "upgrade", "proxy-authenticate", "proxy-authorization",
            "te", "trailers",
        }
        response_headers = {
            k: v for k, v in resp.headers.items() if k.lower() not in _hop_by_hop
        }
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=response_headers,
        )

    # --- Frontend-only config endpoints (not proxied) ---
    @app.get("/frontend/config/environment")
    async def frontend_environment():
        # Always return the full shape the UI expects (see EnvConfig in the
        # frontend). The co-located backend does no app discovery, but the keys
        # must still be present so the UI never dereferences an absent array.
        return {
            "is_cml": False,
            "cml_env": {},
            "discovered_apps": [],
            "discovery_error": None,
            "backend_url_env": None,
            **(_discovery_cache or {}),
            "resolved_backend_url": _proxy_state["url"],
            "mode": "embedded" if _proxy_state["embedded"] else
                    ("proxy" if _proxy_state["url"] else "disconnected"),
        }

    @app.put("/frontend/config/backend-url")
    async def set_backend_url(request: Request):
        # The backend is co-located in this same app (localhost:BACKEND_PORT),
        # so there is no external backend URL to configure.
        return JSONResponse(
            {"error": "Backend runs inside this app on localhost — its URL is fixed and "
                      "cannot be changed at runtime."},
            status_code=400,
        )

    @app.get("/frontend/config/backend-test")
    async def test_backend():
        client = _proxy_state["client"]
        if not client:
            return {"status": "error", "error": "No backend URL configured"}
        try:
            resp = await client.get("/api/health", timeout=10.0)
            if resp.status_code == 200:
                return {"status": "ok", "detail": resp.json()}
            return {"status": "error", "error": f"Backend returned {resp.status_code}"}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    # --- Static files ---
    assets_dir = os.path.join(DIST_DIR, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    dist_root = os.path.realpath(DIST_DIR)

    @app.get("/{full_path:path}")
    async def serve_react(full_path: str):
        # Resolve and contain the path: percent-encoded ../ sequences must not
        # escape the dist directory.
        file_path = os.path.realpath(os.path.join(dist_root, full_path))
        if file_path.startswith(dist_root + os.sep) and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(dist_root, "index.html"))

    host = "127.0.0.1" if os.path.expanduser("~") == "/home/cdsw" else "0.0.0.0"
    print(f"Serving production build on {host}:{port}...")

    config = uvicorn.Config(app, host=host, port=port)
    server = uvicorn.Server(config)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        loop.create_task(server.serve())
    else:
        uvicorn.run(app, host=host, port=port)


def serve_dev():
    """Start the Vite dev server."""
    port = _env_int("FRONTEND_PORT", "CDSW_APP_PORT", default=8100)
    host = "127.0.0.1" if os.path.expanduser("~") == "/home/cdsw" else "0.0.0.0"
    print(f"Starting Vite dev server on {host}:{port}...")
    subprocess.run(
        ["npx", "vite", "--port", str(port), "--host", host],
        cwd=FRONTEND_DIR,
    )


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "auto"

    if mode == "dev":
        serve_dev()
    elif mode == "prod":
        serve_production()
    else:
        # Auto: use production build if it exists, otherwise dev
        if os.path.isdir(DIST_DIR) and os.path.isfile(os.path.join(DIST_DIR, "index.html")):
            serve_production()
        else:
            serve_dev()


if __name__ == "__main__":
    main()
else:
    # CML runs scripts via Jupyter kernel where __name__ != "__main__"
    main()
