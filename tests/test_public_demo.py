"""Task 16: cold-start safety and public-demo hardening for the hosted container."""
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from fraudlens.testing import use_isolated_data_dir

use_isolated_data_dir()

from fastapi import FastAPI
from fastapi.testclient import TestClient

from fraudlens.api.limits import LoginLimiter
from fraudlens.api.main import app, initial_simulation_config
from fraudlens.api.state import state

ROOT = Path(__file__).resolve().parents[1]


def load_serve():
    spec = importlib.util.spec_from_file_location("fraudlens_serve", ROOT / "scripts/serve.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PublicStatusTests(unittest.TestCase):
    def test_public_status_needs_no_auth_while_other_ops_routes_do(self):
        with TestClient(app) as client:
            response = client.get("/ops/public-status")
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual({"ready": True, "mode": "demo"}, {k: body[k] for k in ("ready", "mode")})
            self.assertTrue(body["started_at"])
            self.assertEqual(client.get("/ops/snapshot").status_code, 401)


class SimulationDefaultsTests(unittest.TestCase):
    def test_dev_default_runs_every_five_seconds(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("FRAUDLENS_SIMULATION_RUNNING", None)
            os.environ.pop("FRAUDLENS_SIMULATION_INTERVAL", None)
            self.assertEqual(initial_simulation_config(), {"running": True, "interval_seconds": 5.0})

    def test_public_container_starts_paused_at_eight_seconds(self):
        with mock.patch.dict(os.environ, {"FRAUDLENS_SIMULATION_RUNNING": "0", "FRAUDLENS_SIMULATION_INTERVAL": "8"}):
            self.assertEqual(initial_simulation_config(), {"running": False, "interval_seconds": 8.0})


class LoginRateLimitTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000.0
        self.old_limiter = state.login_limiter
        self.addCleanup(setattr, state, "login_limiter", self.old_limiter)
        self.client = TestClient(app)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        state.login_limiter = LoginLimiter(clock=lambda: self.now)

    def attempt(self, client=None, **headers):
        return (client or self.client).post("/auth/login", json={"username": "asharma", "password": "wrong"}, headers=headers)

    def test_twenty_first_attempt_in_five_minutes_is_429_then_window_expires(self):
        for _ in range(20):
            self.assertEqual(self.attempt().status_code, 401)
        self.assertEqual(self.attempt().status_code, 429)
        ok = self.client.post("/auth/login", json={"username": "asharma", "password": "fraudlens123"})
        self.assertEqual(ok.status_code, 429, "correct passwords count against the same limit")
        self.now += 301
        self.assertEqual(self.attempt().status_code, 401)

    def test_limit_is_per_client_behind_the_console_proxy(self):
        proxied = TestClient(app, client=("127.0.0.1", 40000))
        for _ in range(20):
            self.attempt(proxied, **{"X-Forwarded-For": "203.0.113.7"})
        self.assertEqual(self.attempt(proxied, **{"X-Forwarded-For": "203.0.113.7"}).status_code, 429)
        self.assertEqual(self.attempt(proxied, **{"X-Forwarded-For": "203.0.113.8"}).status_code, 401)
        # A forged left-most entry does not buy a fresh bucket: the proxy-appended address wins.
        self.assertEqual(self.attempt(proxied, **{"X-Forwarded-For": "198.51.100.1, 203.0.113.7"}).status_code, 429)

    def test_configured_client_ip_header_wins_behind_the_console_proxy(self):
        # Render sits behind Cloudflare, whose CF-Connecting-IP is the visitor; X-Forwarded-For
        # there ends in rotating proxy addresses, so it cannot key a per-visitor limit.
        proxied = TestClient(app, client=("127.0.0.1", 40000))
        with mock.patch.dict(os.environ, {"FRAUDLENS_CLIENT_IP_HEADER": "cf-connecting-ip"}):
            for index in range(20):
                self.attempt(proxied, **{"CF-Connecting-IP": "203.0.113.7", "X-Forwarded-For": f"10.0.0.{index}"})
            self.assertEqual(self.attempt(proxied, **{"CF-Connecting-IP": "203.0.113.7", "X-Forwarded-For": "10.0.0.99"}).status_code, 429)
            self.assertEqual(self.attempt(proxied, **{"CF-Connecting-IP": "203.0.113.8"}).status_code, 401)
            # Without the header (e.g. a local container) the X-Forwarded-For rule still applies.
            self.assertEqual(self.attempt(proxied, **{"X-Forwarded-For": "198.51.100.5"}).status_code, 401)

    def test_configured_header_is_ignored_from_untrusted_peers(self):
        with mock.patch.dict(os.environ, {"FRAUDLENS_CLIENT_IP_HEADER": "cf-connecting-ip"}):
            for index in range(20):
                self.attempt(**{"CF-Connecting-IP": f"203.0.113.{index}"})
            self.assertEqual(self.attempt(**{"CF-Connecting-IP": "203.0.113.99"}).status_code, 429)

    def test_forwarded_header_is_ignored_from_untrusted_peers(self):
        for index in range(20):
            self.attempt(**{"X-Forwarded-For": f"203.0.113.{index}"})
        self.assertEqual(self.attempt(**{"X-Forwarded-For": "203.0.113.99"}).status_code, 429)


class SignupAndDemoPasswordTests(unittest.TestCase):
    def test_signup_disabled_in_public_demo(self):
        with mock.patch.dict(os.environ, {"FRAUDLENS_PUBLIC_DEMO": "1"}), TestClient(app) as client:
            response = client.post("/auth/signup", json={"username": "stranger", "display_name": "S", "password": "longenough"})
            self.assertEqual(response.status_code, 403)
            self.assertIn("demo role", response.json()["detail"])
            self.assertEqual(client.post("/auth/login", json={"username": "stranger", "password": "longenough"}).status_code, 401)

    def test_no_route_changes_a_password_and_signup_cannot_overwrite_a_demo_account(self):
        paths = [getattr(route, "path", "") for route in app.routes]
        self.assertFalse([path for path in paths if "password" in path.lower()])
        with TestClient(app) as client:
            response = client.post("/auth/signup", json={"username": "kmehta", "display_name": "K", "password": "takeover1"})
            self.assertEqual(response.status_code, 409)
            self.assertEqual(client.post("/auth/login", json={"username": "kmehta", "password": "fraudlens123"}).status_code, 200)


class ServeEntrypointTests(unittest.TestCase):
    def run_serve(self, data_dir, environ=None):
        serve = load_serve()
        calls = []
        process = SimpleNamespace(poll=lambda: 0, returncode=0)

        def start(command, cwd, env):
            calls.append(("start", command, env))
            return process

        def wait(url, proc, timeout):
            calls.append(("wait", url))

        with mock.patch.object(serve, "start_process", start), mock.patch.object(serve, "wait_ready", wait), \
                mock.patch.object(serve, "stop_processes", lambda processes: None), \
                mock.patch.object(serve.signal, "signal", lambda *args: None), \
                mock.patch.dict(os.environ, {"FRAUDLENS_DATA_DIR": str(data_dir), "PORT": "7860", **(environ or {})}):
            serve.main()
        return calls

    def test_each_service_is_ready_before_the_next_starts_and_console_is_last(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls = self.run_serve(tmp)
        self.assertEqual([call[0] for call in calls], ["start", "wait"] * 3)
        self.assertEqual([call[1] for call in calls if call[0] == "wait"],
                         ["http://127.0.0.1:8002/health", "http://127.0.0.1:8001/health", "http://127.0.0.1:7860/"])

    def test_bank_and_api_bind_loopback_and_stream_starts_paused_at_eight_seconds(self):
        with tempfile.TemporaryDirectory() as tmp:
            starts = [call for call in self.run_serve(tmp) if call[0] == "start"]
        bank, api, console = (call[1] for call in starts)
        for command in (bank, api):
            self.assertEqual(command[command.index("--host") + 1], "127.0.0.1")
        self.assertIn("fraudlens.bank_simulator.main:app", bank)
        env = starts[1][2]
        self.assertEqual((env["FRAUDLENS_SEED_DEMO"], env["FRAUDLENS_MODE"]), ("1", "demo"))
        self.assertEqual((env["FRAUDLENS_SIMULATION_RUNNING"], env["FRAUDLENS_SIMULATION_INTERVAL"]), ("0", "8"))
        self.assertEqual(starts[2][2]["HOSTNAME"], "0.0.0.0")

    def test_boot_clears_previous_demo_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("operations.sqlite3", "operations.sqlite3-wal", "bank.sqlite3", "analysts.json", "session.key"):
                (Path(tmp) / name).write_text("old")
            (Path(tmp) / "unrelated.txt").write_text("keep")
            self.run_serve(tmp)
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), ["unrelated.txt"])

    def test_dockerfile_enables_public_demo_and_exposes_only_the_console_port(self):
        dockerfile = (ROOT / "Dockerfile").read_text()
        self.assertRegex(dockerfile, r"ENV [^\n]*FRAUDLENS_PUBLIC_DEMO=1")
        self.assertEqual([line for line in dockerfile.splitlines() if line.startswith("EXPOSE")], ["EXPOSE 7860"])

    def test_container_trusts_cloudflare_client_header_and_streams_uncompressed(self):
        self.assertRegex((ROOT / "Dockerfile").read_text(), r"ENV [^\n]*FRAUDLENS_CLIENT_IP_HEADER=cf-connecting-ip")
        # Next's gzip buffers /ops/events behind the /backend rewrite, so live updates never arrive.
        self.assertRegex((ROOT / "frontend/next.config.ts").read_text(), r"compress:\s*false")


if __name__ == "__main__":
    unittest.main()
