"""Start both the backend API server and the frontend application."""

import os
import sys
import subprocess
import signal
import time

try:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
except NameError:
    PROJECT_ROOT = os.getcwd()

BACKEND_PORT = int(os.environ.get("BACKEND_PORT", 7078))
FRONTEND_PORT = int(os.environ.get("FRONTEND_PORT", 8100))

processes = []


def cleanup(signum=None, frame=None):
    print("\nShutting down...")
    for proc in processes:
        if proc.poll() is None:
            proc.terminate()
    for proc in processes:
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    sys.exit(0)


signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)


def main():
    # Check prerequisites — warn but don't block (pipeline can be run from the UI)
    db_path = os.path.join(PROJECT_ROOT, "data", "transactions.db")
    model_path = os.path.join(PROJECT_ROOT, "models", "xgboost_fraud.json")

    if not os.path.exists(db_path) or not os.path.exists(model_path):
        print("WARNING: Database or model not found.")
        print("  Build them first by running, in order:")
        print("    python3 pipelines/data_generation/generate_synthetic_data.py")
        print("    python3 pipelines/data_pipeline/preprocess.py")
        print("    python3 pipelines/data_pipeline/feature_engineering.py")
        print("    python3 pipelines/model_training/train_xgboost.py")
        print()

    env = os.environ.copy()
    env["BACKEND_PORT"] = str(BACKEND_PORT)
    env["FRONTEND_PORT"] = str(FRONTEND_PORT)

    # Start backend
    print(f"Starting backend on port {BACKEND_PORT}...")
    backend = subprocess.Popen(
        [sys.executable, os.path.join(PROJECT_ROOT, "app", "backend", "start_backend.py")],
        env=env,
        cwd=PROJECT_ROOT,
    )
    processes.append(backend)

    # Give backend a moment to start
    time.sleep(2)

    # Check if production build exists
    dist_dir = os.path.join(PROJECT_ROOT, "app", "frontend", "dist")
    if os.path.isdir(dist_dir):
        # In production mode, start the frontend server that also proxies to backend
        print(f"Starting frontend (production) on port {FRONTEND_PORT}...")
        frontend = subprocess.Popen(
            [sys.executable, os.path.join(PROJECT_ROOT, "app", "start_frontend.py"), "prod"],
            env=env,
            cwd=PROJECT_ROOT,
        )
    else:
        # Dev mode: start Vite dev server
        print(f"Starting frontend (dev) on port {FRONTEND_PORT}...")
        frontend = subprocess.Popen(
            [sys.executable, os.path.join(PROJECT_ROOT, "app", "start_frontend.py"), "dev"],
            env=env,
            cwd=PROJECT_ROOT,
        )
    processes.append(frontend)

    print()
    print("=" * 50)
    print(f"  Backend API:  http://localhost:{BACKEND_PORT}/api")
    print(f"  Frontend App: http://localhost:{FRONTEND_PORT}")
    print("=" * 50)
    print("Press Ctrl+C to stop both services.")
    print()

    # Wait for either process to exit
    while True:
        for proc in processes:
            ret = proc.poll()
            if ret is not None:
                print(f"Process exited with code {ret}")
                cleanup()
        time.sleep(1)


if __name__ == "__main__":
    main()
