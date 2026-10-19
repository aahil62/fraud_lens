#!/usr/bin/env python3
"""Run focused operational checks and frontend verification; --full adds legacy tests."""

import argparse
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import unittest

from dev import ensure_ports_available, start_process, stop_processes, wait_ready


ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


class LauncherChecks(unittest.TestCase):
    """Exercise local process safety without starting application services."""

    def test_port_collision_preserves_existing_listener(self):
        with socket.socket() as occupied:
            try:
                occupied.bind(("127.0.0.1", 0))
            except PermissionError:
                self.skipTest("Sandbox blocks loopback sockets; rerun outside the sandbox")
            occupied.listen()
            port = occupied.getsockname()[1]
            with self.assertRaisesRegex(RuntimeError, str(port)):
                ensure_ports_available({"bank": port}, wait=0)
            self.assertEqual(occupied.getsockname()[1], port)

    def test_duplicate_ports_are_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "distinct"):
            ensure_ports_available({"bank": 40001, "api": 40001})

    def test_cleanup_terminates_owned_child(self):
        process = start_process([str(PYTHON), "-c", "import time; time.sleep(60)"], ROOT, os.environ.copy())
        try:
            self.assertIsNone(process.poll())
            stop_processes([process])
            self.assertIsNotNone(process.poll())
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()

    def test_readiness_exits_promptly_when_service_dies(self):
        process = start_process([str(PYTHON), "-c", "raise SystemExit(7)"], ROOT, os.environ.copy())
        process.wait(timeout=5)
        started = time.monotonic()
        with self.assertRaisesRegex(RuntimeError, "exited"):
            wait_ready("http://127.0.0.1:1/health", process, timeout=1)
        self.assertLess(time.monotonic() - started, .5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="Also run the complete historical backend suite")
    parser.add_argument("--skip-frontend", action="store_true", help="Only backend and launcher checks (safe while Next dev is running)")
    args = parser.parse_args()
    npm = shutil.which("npm")
    if not PYTHON.is_file() or not npm:
        parser.error("Install .venv Python dependencies and Node.js dependencies first; see README.md")
    launcher_checks = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(LauncherChecks))
    if not launcher_checks.wasSuccessful():
        return 1
    commands = [([str(PYTHON), "-m", "unittest", "tests.test_bank_simulator", "tests.test_operations", "tests.test_operations_api", "tests.test_session_secret", "-v"], ROOT)]
    if args.full:
        commands.append(([str(PYTHON), "-m", "unittest", "discover", "-s", "tests", "-v"], ROOT))
    if not args.skip_frontend:
        commands.extend(([npm, "run", task], ROOT / "frontend") for task in ("test", "lint", "build"))
    failures = []
    for command, cwd in commands:
        print(f"\nChecking: {' '.join(command)}", flush=True)
        result = subprocess.run(command, cwd=cwd)
        if result.returncode:
            failures.append((command, result.returncode))
    if failures:
        for command, code in failures:
            print(f"FAILED ({code}): {' '.join(command)}", file=sys.stderr)
        return 1
    print("All requested checks passed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
