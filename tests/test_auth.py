import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fraudlens.testing import use_isolated_data_dir

use_isolated_data_dir()

from fastapi.testclient import TestClient
from fraudlens.api.main import app
from fraudlens.core.auth.store import AnalystStore


class AuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)

    def test_login_with_seeded_account_succeeds(self) -> None:
        resp = self.client.post("/auth/login", json={"username": "asharma", "password": "fraudlens123"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["access_token"])
        self.assertEqual(data["analyst"]["username"], "asharma")
        self.assertEqual(data["analyst"]["display_name"], "A. Sharma")
        self.assertEqual(data["analyst"]["role"], "supervisor")

    def test_login_with_wrong_password_rejected(self) -> None:
        resp = self.client.post("/auth/login", json={"username": "asharma", "password": "wrong"})
        self.assertEqual(resp.status_code, 401)

    def test_login_with_unknown_username_rejected(self) -> None:
        resp = self.client.post("/auth/login", json={"username": "nobody", "password": "whatever"})
        self.assertEqual(resp.status_code, 401)

    def test_signup_creates_a_real_account_that_can_then_log_in(self) -> None:
        signup = self.client.post(
            "/auth/signup",
            json={
                "username": "newanalyst",
                "display_name": "N. Verma",
                "password": "supersecret1",
                "role": "supervisor",
            },
        )
        self.assertEqual(signup.status_code, 200)
        self.assertEqual(signup.json()["analyst"]["display_name"], "N. Verma")
        self.assertEqual(signup.json()["analyst"]["role"], "l1_analyst")

        login = self.client.post("/auth/login", json={"username": "newanalyst", "password": "supersecret1"})
        self.assertEqual(login.status_code, 200)

    def test_signup_with_taken_username_rejected(self) -> None:
        resp = self.client.post(
            "/auth/signup",
            json={"username": "asharma", "display_name": "Someone Else", "password": "whatever1"},
        )
        self.assertEqual(resp.status_code, 409)

    def test_signup_with_short_password_rejected(self) -> None:
        resp = self.client.post(
            "/auth/signup", json={"username": "shortpw", "display_name": "X", "password": "abc"}
        )
        self.assertEqual(resp.status_code, 400)

    def test_me_requires_a_valid_token(self) -> None:
        resp = self.client.get("/auth/me")
        self.assertEqual(resp.status_code, 401)

        resp = self.client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
        self.assertEqual(resp.status_code, 401)

    def test_me_returns_the_logged_in_analyst(self) -> None:
        login = self.client.post("/auth/login", json={"username": "riyer", "password": "fraudlens123"})
        token = login.json()["access_token"]

        resp = self.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["username"], "riyer")
        self.assertEqual(resp.json()["role"], "l2_analyst")


if __name__ == "__main__":
    unittest.main()


class AnalystStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "analysts.json"

    def test_unreadable_account_file_stops_startup_instead_of_being_overwritten(self) -> None:
        self.path.write_text('[{"username": "new-analyst", ')
        with self.assertRaisesRegex(ValueError, "analysts.json"):
            AnalystStore(str(self.path))
        self.assertEqual(self.path.read_text(), '[{"username": "new-analyst", ')

    def test_unknown_username_still_runs_the_password_hash(self) -> None:
        store = AnalystStore(str(self.path))
        with patch("fraudlens.core.auth.store.verify_password", return_value=False) as verify:
            self.assertIsNone(store.verify("nobody", "fraudlens123"))
        verify.assert_called_once()
