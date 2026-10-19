import http.client
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import threading  # noqa: E402
import time  # noqa: E402

from dev import ensure_ports_available, start_process, stop_processes, uvicorn_command, wait_ready  # noqa: E402


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@unittest.skipIf(os.name == "nt", "POSIX signals only")
class ApiShutdownTests(unittest.TestCase):
    def test_api_exits_promptly_on_sigterm_with_open_event_stream(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        port = free_port()
        env = {**os.environ, "FRAUDLENS_LEGACY_API": "0", "FRAUDLENS_SEED_DEMO": "1", "FRAUDLENS_MODE": "demo",
               "FRAUDLENS_BANK_URL": f"http://127.0.0.1:{free_port()}", "FRAUDLENS_BANK_KEY": "test",
               "FRAUDLENS_BANK_DB": f"{tmp.name}/bank.sqlite3", "FRAUDLENS_OPS_DB": f"{tmp.name}/ops.sqlite3",
               "FRAUDLENS_SESSION_SECRET_PATH": f"{tmp.name}/session.key",
               "FRAUDLENS_ANALYSTS_PATH": f"{tmp.name}/analysts.json"}
        log = open(Path(tmp.name) / "api.log", "w+")
        self.addCleanup(log.close)
        process = subprocess.Popen(uvicorn_command(sys.executable, "fraudlens.api.main:app", port), cwd=ROOT, env=env,
                                   stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        self.addCleanup(stop_processes, [process])
        wait_ready(f"http://127.0.0.1:{port}/health", process, 60)

        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        self.addCleanup(conn.close)
        conn.request("POST", "/auth/login", json.dumps({"username": "kmehta", "password": "fraudlens123"}),
                     {"Content-Type": "application/json"})
        token = json.loads(conn.getresponse().read())["access_token"]
        stream = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        self.addCleanup(stream.close)
        stream.request("GET", "/ops/events", headers={"Authorization": f"Bearer {token}"})
        response = stream.getresponse()
        self.assertEqual(response.status, 200)
        response.fp.readline()  # first event or heartbeat: the stream is live

        process.send_signal(signal.SIGTERM)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.fail("API did not exit within 10s of SIGTERM while an event stream was open")
        log.seek(0)
        output = log.read()
        # Cutting an open stream on shutdown is expected; it must not be logged as an application error.
        self.assertNotIn("Traceback", output)
        self.assertNotIn("CancelledError", output)


class PortProbeTests(unittest.TestCase):
    def listener(self):
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        return sock

    def test_port_released_during_wait_is_accepted(self):
        sock = self.listener()
        port = sock.getsockname()[1]
        threading.Timer(.5, sock.close).start()
        ensure_ports_available({"bank": port}, wait=5)

    def test_port_still_held_after_wait_is_rejected(self):
        sock = self.listener()
        self.addCleanup(sock.close)
        port = sock.getsockname()[1]
        started = time.monotonic()
        with self.assertRaisesRegex(RuntimeError, str(port)):
            ensure_ports_available({"bank": port}, wait=1)
        self.assertGreaterEqual(time.monotonic() - started, .9)

    def test_recently_closed_connection_does_not_block_restart(self):
        sock = self.listener()
        port = sock.getsockname()[1]
        client = socket.create_connection(("127.0.0.1", port))
        server_side, _ = sock.accept()
        server_side.close()  # server closes first, leaving TIME_WAIT on the service port
        client.close()
        sock.close()
        ensure_ports_available({"bank": port}, wait=0)


if __name__ == "__main__":
    unittest.main()
