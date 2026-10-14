"""Stop all fraud detection services (backend API and frontend)."""

import os
import signal
import subprocess
import sys


BACKEND_PORT = int(os.environ.get("BACKEND_PORT", 7078))
FRONTEND_PORT = int(os.environ.get("FRONTEND_PORT", 8100))


def find_pids_on_port(port):
    """Return list of PIDs listening on the given port."""
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True, text=True
        )
        if result.stdout.strip():
            return [int(pid) for pid in result.stdout.strip().split("\n")]
    except FileNotFoundError:
        # lsof not available, try ss + /proc
        try:
            result = subprocess.run(
                ["ss", "-tlnp", f"sport = :{port}"],
                capture_output=True, text=True
            )
            pids = []
            for line in result.stdout.split("\n"):
                if f":{port}" in line and "pid=" in line:
                    for part in line.split(","):
                        if part.startswith("pid="):
                            pids.append(int(part.split("=")[1]))
            return pids
        except FileNotFoundError:
            pass
    return []


def kill_pids(pids, label):
    """Terminate a list of PIDs, falling back to SIGKILL."""
    for pid in pids:
        try:
            print(f"  Stopping {label} (PID {pid})...")
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except PermissionError:
            print(f"  Permission denied for PID {pid} — try running with sudo")


def main():
    stopped_any = False

    for port, label in [(BACKEND_PORT, "backend"), (FRONTEND_PORT, "frontend")]:
        pids = find_pids_on_port(port)
        if pids:
            kill_pids(pids, f"{label} (port {port})")
            stopped_any = True
        else:
            print(f"  No process found on port {port} ({label})")

    if stopped_any:
        print("\nAll services stopped.")
    else:
        print("\nNo running services found.")


if __name__ == "__main__":
    main()
