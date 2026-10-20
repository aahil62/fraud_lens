#!/usr/bin/env python3
"""Start the three local-only FraudLens services; Ctrl-C stops owned children."""

import argparse
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def port_free(port):
    # SO_REUSEADDR matches how uvicorn binds, so connections left in TIME_WAIT by a
    # just-stopped launch do not count as busy; a live listener still does.
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def ensure_ports_available(ports, wait=5):
    """Fail on a port that stays busy for `wait` seconds (a previous launch may still be exiting)."""
    if len(set(ports.values())) != len(ports):
        raise RuntimeError("BANK_PORT, API_PORT, and FRONTEND_PORT must be distinct")
    for name, port in ports.items():
        if not 1 <= port <= 65535:
            raise RuntimeError(f"Invalid {name} port: {port}")
    deadline = time.monotonic() + wait
    for name, port in ports.items():
        while not port_free(port):
            if time.monotonic() >= deadline:
                raise RuntimeError(f"{name} port {port} is unavailable. Stop its owner or choose another port in .env.")
            time.sleep(.25)


def uvicorn_command(python, app, port):
    # Open SSE streams (/ops/events) never finish on their own; without a graceful
    # timeout uvicorn waits on them forever and ignores SIGTERM. Keep it short:
    # Docker Desktop's default `docker stop` deadline measured ~3.3 s, and clients
    # reconnect to the stream on their own.
    # --no-proxy-headers: uvicorn would otherwise replace the loopback peer with the
    # X-Forwarded-For value, bypassing fraudlens.api.limits.client_ip's trust rules.
    return [str(python), "-m", "uvicorn", app, "--host", "127.0.0.1", "--port", str(port),
            "--timeout-graceful-shutdown", "1", "--no-proxy-headers"]


def start_process(command, cwd, env):
    return subprocess.Popen(command, cwd=cwd, env=env, start_new_session=os.name != "nt")


def stop_processes(processes):
    for process in reversed(processes):
        try:
            if os.name != "nt":
                os.killpg(process.pid, signal.SIGTERM)
            elif process.poll() is None:
                process.terminate()
        except ProcessLookupError:
            pass
    for process in reversed(processes):
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if os.name != "nt":
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            else:
                process.kill()
            process.wait(timeout=5)


def wait_ready(url, process, timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Service exited with code {process.returncode} while waiting for {url}")
        try:
            with urlopen(url, timeout=min(2, max(.1, deadline - time.monotonic()))) as response:
                if response.status == 200:
                    return
        except (URLError, TimeoutError, OSError):
            pass
        time.sleep(.25)
    raise RuntimeError(f"Service did not become ready within {timeout}s: {url}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--startup-timeout", type=int, default=120, help="Seconds per service (default 120)")
    args = parser.parse_args()
    if args.startup_timeout < 1:
        parser.error("--startup-timeout must be positive")
    if not PYTHON.is_file():
        raise RuntimeError("Create .venv with Python 3.12 and install requirements.lock first; see README.md")
    # Re-exec within the project environment so dotenv and all child dependencies
    # resolve consistently even when launched with the system Python.
    if Path(sys.prefix).resolve() != (ROOT / ".venv").resolve():
        os.execv(str(PYTHON), [str(PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]])
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError("This showcase supports Python 3.12; recreate .venv using Python 3.12")
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)
    npm = shutil.which("npm")
    if not npm or not (ROOT / "frontend/node_modules/next").is_dir():
        raise RuntimeError("Install Node.js 24+ and run npm ci in frontend/ before starting")
    try:
        ports = {"bank": int(os.getenv("BANK_PORT", "8002")), "api": int(os.getenv("API_PORT", "8001")),
                 "frontend": int(os.getenv("FRONTEND_PORT", "3000"))}
    except ValueError as error:
        raise RuntimeError("BANK_PORT, API_PORT, and FRONTEND_PORT must be integer ports") from error
    ensure_ports_available(ports)
    env = os.environ.copy()
    env.update({"FRAUDLENS_SEED_DEMO": "1",
                "FRAUDLENS_MODE": "demo", "PYTHONUNBUFFERED": "1",
                "FRAUDLENS_BANK_URL": f"http://127.0.0.1:{ports['bank']}",
                "NEXT_PUBLIC_API_BASE": f"http://127.0.0.1:{ports['api']}",
                "NEXT_PUBLIC_DEMO_MODE": "1",
                "FRAUDLENS_CORS_ORIGINS": f"http://127.0.0.1:{ports['frontend']},http://localhost:{ports['frontend']}"})
    env.setdefault("FRAUDLENS_BANK_KEY", "fraudlens-local-simulator")
    env.setdefault("FRAUDLENS_BANK_DB", str(ROOT / "var/bank.sqlite3"))
    env.setdefault("FRAUDLENS_OPS_DB", str(ROOT / "var/operations.sqlite3"))
    print("Local simulated banking only. No external bank services are used.", flush=True)
    processes = []

    def interrupt(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupt)
    services = [
        ("Bank simulator", uvicorn_command(PYTHON, "fraudlens.bank_simulator.main:app", ports["bank"]), ROOT, f"http://127.0.0.1:{ports['bank']}/health"),
        ("API", uvicorn_command(PYTHON, "fraudlens.api.main:app", ports["api"]), ROOT, f"http://127.0.0.1:{ports['api']}/health"),
        ("Console", [npm, "run", "dev", "--", "--hostname", "127.0.0.1", "--port", str(ports["frontend"])], ROOT / "frontend", f"http://127.0.0.1:{ports['frontend']}")]
    try:
        for label, command, cwd, url in services:
            print(f"Starting {label}: {url}", flush=True)
            process = start_process(command, cwd, env)
            processes.append(process)
            wait_ready(url, process, args.startup_timeout)
        print(f"FraudLens ready: http://127.0.0.1:{ports['frontend']} (Ctrl-C to stop)", flush=True)
        while True:
            for process in processes:
                if process.poll() is not None:
                    raise RuntimeError(f"A service exited with code {process.returncode}; stopping this launch")
            time.sleep(.5)
    except KeyboardInterrupt:
        print("\nStopping FraudLens services...", flush=True)
    finally:
        stop_processes(processes)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError) as error:
        print(f"FraudLens could not start: {error}", file=sys.stderr)
        raise SystemExit(1)
