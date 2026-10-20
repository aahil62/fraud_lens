#!/usr/bin/env python3
"""Production entrypoint for the single-container demo (Dockerfile / HF Spaces).

Starts the bank simulator and API on 127.0.0.1 with the same uvicorn commands
and environment as scripts/dev.py, then the standalone Next.js server on
0.0.0.0:$PORT. Data lives under /tmp/fraudlens and resets on every boot; the
synthetic stream starts paused at one scenario every 8 s.
"""

import os
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dev import start_process, stop_processes, uvicorn_command, wait_ready  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA_FILES = ("bank.sqlite3*", "operations.sqlite3*", "analysts.json", "session.key")


def reset_data(data):
    """Remove the previous boot's demo state so every start reseeds."""
    for pattern in DATA_FILES:
        for path in data.glob(pattern):
            path.unlink()


def main():
    port = int(os.environ.get("PORT", "7860"))
    data = Path(os.environ.get("FRAUDLENS_DATA_DIR", "/tmp/fraudlens"))
    data.mkdir(parents=True, exist_ok=True)
    reset_data(data)
    env = os.environ.copy()
    env.update(
        {
            "FRAUDLENS_SEED_DEMO": "1",
            "FRAUDLENS_MODE": "demo",
            "PYTHONUNBUFFERED": "1",
            "FRAUDLENS_SIMULATION_RUNNING": "0",
            "FRAUDLENS_SIMULATION_INTERVAL": "8",
            "FRAUDLENS_BANK_URL": "http://127.0.0.1:8002",
            "FRAUDLENS_CORS_ORIGINS": f"http://127.0.0.1:{port},http://localhost:{port}",
        }
    )
    env.setdefault("FRAUDLENS_BANK_KEY", "fraudlens-local-simulator")
    env.setdefault("FRAUDLENS_BANK_DB", str(data / "bank.sqlite3"))
    env.setdefault("FRAUDLENS_OPS_DB", str(data / "operations.sqlite3"))
    env.setdefault("FRAUDLENS_SESSION_SECRET_PATH", str(data / "session.key"))
    env.setdefault("FRAUDLENS_ANALYSTS_PATH", str(data / "analysts.json"))
    node_env = {**env, "PORT": str(port), "HOSTNAME": "0.0.0.0", "NODE_ENV": "production"}
    python = sys.executable
    services = [
        (
            "Bank simulator",
            uvicorn_command(python, "fraudlens.bank_simulator.main:app", 8002),
            ROOT,
            env,
            "http://127.0.0.1:8002/health",
        ),
        (
            "API",
            uvicorn_command(python, "fraudlens.api.main:app", 8001),
            ROOT,
            env,
            "http://127.0.0.1:8001/health",
        ),
        (
            "Console",
            ["node", "server.js"],
            ROOT / "frontend/.next/standalone",
            node_env,
            f"http://127.0.0.1:{port}/",
        ),
    ]
    processes = []

    def interrupt(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupt)
    try:
        for label, command, cwd, service_env, url in services:
            print(f"Starting {label}: {url}", flush=True)
            process = start_process(command, cwd, service_env)
            processes.append(process)
            wait_ready(url, process, int(os.environ.get("FRAUDLENS_STARTUP_TIMEOUT", "180")))
        print(f"FraudLens ready on port {port}", flush=True)
        while True:
            for process in processes:
                if process.poll() is not None:
                    print(f"A service exited with code {process.returncode}; stopping", flush=True)
                    return 1
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("Stopping FraudLens services...", flush=True)
        return 0
    except RuntimeError as error:
        print(f"FraudLens could not start: {error}", flush=True)
        return 1
    finally:
        stop_processes(processes)


if __name__ == "__main__":
    sys.exit(main())
