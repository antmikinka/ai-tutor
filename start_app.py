#!/usr/bin/env python3
"""
Development launcher for AI Math Tutor.

Starts the FastAPI backend, waits until it is healthy, then starts the Electron
app in development mode (React dev server + Electron). Ctrl+C stops everything.

    python start_app.py                 # backend + desktop app
    python start_app.py --backend-only  # just the API, e.g. for curl / tests
    python start_app.py --port 8010

The Python interpreter used for the backend is, in order: --python, a ``venv``
or ``.venv`` folder next to this file, or the interpreter running this script.
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "src" / "backend"
HOST = "127.0.0.1"


def find_python(explicit: str | None) -> str:
    if explicit:
        return explicit
    for venv in (ROOT / "venv", ROOT / ".venv"):
        candidate = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        if candidate.exists():
            return str(candidate)
    return sys.executable


def check_python_deps(python: str) -> bool:
    result = subprocess.run(
        [python, "-c", "import fastapi, uvicorn, sympy, PIL"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"[!] Backend dependencies are missing for {python}:")
        print("    " + result.stderr.strip().splitlines()[-1])
        print(f"    Install them with: {python} -m pip install -r src/backend/requirements.txt")
        return False
    return True


def backend_healthy(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://{HOST}:{port}/health", timeout=2) as response:
            return response.status == 200
    except (urllib.error.URLError, OSError):
        return False


def start_backend(python: str, port: int) -> subprocess.Popen:
    env = {**os.environ, "HOST": HOST, "PORT": str(port), "PYTHONUNBUFFERED": "1"}
    return subprocess.Popen([python, "main.py"], cwd=BACKEND_DIR, env=env)


def start_frontend(port: int) -> subprocess.Popen | None:
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if npm is None:
        print("[!] npm not found on PATH; start the desktop app manually with `npm run dev`.")
        return None
    if not (ROOT / "node_modules").exists():
        print("[!] node_modules missing; run `npm install` first.")
        return None
    env = {**os.environ, "MATH_TUTOR_BACKEND_PORT": str(port), "MATH_TUTOR_SKIP_BACKEND": "1"}
    return subprocess.Popen([npm, "run", "dev"], cwd=ROOT, env=env)


def terminate(processes: list[subprocess.Popen]) -> None:
    for process in processes:
        if process.poll() is None:
            process.terminate()
    deadline = time.time() + 8
    for process in processes:
        try:
            process.wait(timeout=max(0.1, deadline - time.time()))
        except subprocess.TimeoutExpired:
            process.kill()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run AI Math Tutor in development mode")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)))
    parser.add_argument("--python", help="Interpreter to run the backend with")
    parser.add_argument("--backend-only", action="store_true", help="Do not start the Electron app")
    parser.add_argument("--timeout", type=int, default=60, help="Seconds to wait for the backend health check")
    args = parser.parse_args()

    python = find_python(args.python)
    print(f"Backend interpreter: {python}")
    if not check_python_deps(python):
        return 1

    processes: list[subprocess.Popen] = []

    def shutdown(*_: object) -> None:
        print("\nStopping…")
        terminate(processes)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    if backend_healthy(args.port):
        print(f"Backend already running at http://{HOST}:{args.port}; reusing it.")
    else:
        print(f"Starting backend on http://{HOST}:{args.port} …")
        backend = start_backend(python, args.port)
        processes.append(backend)
        deadline = time.time() + args.timeout
        while time.time() < deadline:
            if backend.poll() is not None:
                print(f"[!] Backend exited early with code {backend.returncode}.")
                return 1
            if backend_healthy(args.port):
                break
            time.sleep(0.5)
        else:
            print("[!] Backend did not become healthy in time.")
            terminate(processes)
            return 1
        print(f"Backend ready. API docs: http://{HOST}:{args.port}/api/docs")

    if not args.backend_only:
        frontend = start_frontend(args.port)
        if frontend is not None:
            processes.append(frontend)

    print("Press Ctrl+C to stop.")
    try:
        while True:
            for process in processes:
                if process.poll() is not None:
                    print(f"A child process exited (code {process.returncode}); shutting down.")
                    terminate(processes)
                    return process.returncode or 0
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
