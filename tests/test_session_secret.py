import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fraudlens.bank_simulator.main import create_app
from fraudlens.core.auth.security import load_session_secret
from fraudlens.core.auth.store import AnalystStore


class SessionSecretTests(unittest.TestCase):
    def test_local_secret_is_random_persistent_and_private(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.key"
            one = load_session_secret(path, configured=None, mode="demo")
            self.assertGreaterEqual(len(one), 32)
            self.assertEqual(one, load_session_secret(path, configured=None, mode="demo"))
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_production_requires_explicit_strong_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            for configured in (None, "short"):
                with self.assertRaises(ValueError):
                    load_session_secret(Path(directory) / "key", configured=configured, mode="production")
            self.assertEqual(
                load_session_secret(Path(directory) / "key", configured="z" * 48, mode="production"), "z" * 48
            )

    def test_non_demo_rejects_existing_public_demo_accounts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "analysts.json"
            AnalystStore(str(path))
            with patch.dict(os.environ, {"FRAUDLENS_MODE": "production"}):
                with self.assertRaises(ValueError):
                    AnalystStore(str(path))

    def test_non_demo_rejects_public_simulator_key(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(
                os.environ,
                {"FRAUDLENS_MODE": "production", "FRAUDLENS_BANK_KEY": "fraudlens-local-simulator"},
            ):
                with self.assertRaises(ValueError):
                    create_app(db_path=Path(directory) / "bank.db")


if __name__ == "__main__":
    unittest.main()
