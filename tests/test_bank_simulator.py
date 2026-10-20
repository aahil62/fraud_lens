"""Behavioral tests against a real, isolated simulator database."""

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient
from fraudlens.bank_simulator.main import create_app


class BankSimulatorTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.db_path = Path(self.directory.name) / "bank.sqlite3"
        self.client = TestClient(create_app(db_path=self.db_path, api_key="test-bank-key"))
        self.client.headers["X-Bank-Key"] = "test-bank-key"
        self.addCleanup(self.client.close)

    def payment(self, txn_id="payment-1", **changes):
        return {"txn_id": txn_id, "account_id": "account-1", "channel": "upi", "amount_minor": 125, **changes}

    def action(self, action_id="restrict-1", **changes):
        return {
            "action_id": action_id,
            "case_id": "case-1",
            "operation": "restrict",
            "target_type": "account",
            "target_id": "account-1",
            **changes,
        }

    def test_auth_protects_every_bank_route_but_health_is_public(self):
        self.assertEqual(self.client.get("/health").json(), {"status": "ok", "simulation": True})
        for method, route, payload in [
            ("get", "/bank/accounts", None),
            ("get", "/bank/status", None),
            ("get", "/bank/actions/missing", None),
            ("post", "/bank/control", {"mode": "reject"}),
            ("post", "/bank/actions", self.action()),
            ("post", "/bank/transactions", self.payment()),
        ]:
            with self.subTest(route=route):
                response = self.client.request(method, route, json=payload, headers={"X-Bank-Key": "wrong"})
                self.assertEqual(response.status_code, 401)
        self.assertEqual(self.client.get("/bank/accounts").json()["accounts"], [])

    def test_all_channels_debit_integer_paise_once_across_restart(self):
        for channel in ["upi", "net_banking", "card", "atm"]:
            payload = self.payment(
                channel, channel=channel, instrument_id="card-1" if channel in ["card", "atm"] else None
            )
            response = self.client.post("/bank/transactions", json=payload)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "posted")
            self.assertEqual(self.client.post("/bank/transactions", json=payload).json(), response.json())
        restarted = TestClient(create_app(db_path=self.db_path, api_key="test-bank-key"))
        self.addCleanup(restarted.close)
        restarted.headers["X-Bank-Key"] = "test-bank-key"
        self.assertEqual(restarted.get("/bank/accounts").json()["accounts"][0]["balance_minor"], 99999500)
        self.assertEqual(
            restarted.post("/bank/transactions", json=self.payment("upi", instrument_id=None)).json()[
                "balance_minor"
            ],
            99999875,
        )
        self.assertEqual(restarted.get("/bank/accounts").json()["accounts"][0]["balance_minor"], 99999500)

    def test_conflicting_payment_and_action_ids_are_rejected(self):
        self.client.post("/bank/transactions", json=self.payment())
        self.assertEqual(
            self.client.post("/bank/transactions", json=self.payment(amount_minor=126)).status_code, 409
        )
        self.client.post("/bank/actions", json=self.action())
        self.assertEqual(
            self.client.post("/bank/actions", json=self.action(case_id="case-2")).status_code, 409
        )
        self.assertEqual(self.client.get("/bank/accounts").json()["accounts"][0]["balance_minor"], 99999875)

    def test_case_owned_releases_preserve_other_case_and_persist_declines(self):
        first = self.client.post("/bank/actions", json=self.action()).json()
        self.assertEqual(first["status"], "confirmed")
        self.assertTrue(first["restriction_active"])
        self.client.post("/bank/actions", json=self.action("restrict-2", case_id="case-2"))
        self.client.post("/bank/actions", json=self.action("release-1", operation="release"))
        ledger = self.client.get("/bank/accounts").json()
        self.assertEqual(ledger["accounts"][0]["active_restrictions"], 1)
        declined = self.client.post("/bank/transactions", json=self.payment()).json()
        self.assertEqual(declined["status"], "declined")
        self.assertEqual(declined["reason"], "account_restricted")
        self.client.post(
            "/bank/actions", json=self.action("release-2", case_id="case-2", operation="release")
        )
        self.assertEqual(self.client.post("/bank/transactions", json=self.payment()).json(), declined)
        self.assertEqual(
            self.client.post("/bank/transactions", json=self.payment("fresh")).json()["status"], "posted"
        )

    def test_card_restrictions_only_affect_matching_instrument(self):
        self.client.post("/bank/actions", json=self.action(target_type="card", target_id="card-1"))
        for channel in ["card", "atm"]:
            blocked = self.client.post(
                "/bank/transactions", json=self.payment(channel, channel=channel, instrument_id="card-1")
            )
            self.assertEqual(blocked.json()["reason"], "card_restricted")
        self.assertEqual(
            self.client.post(
                "/bank/transactions", json=self.payment("other-card", channel="card", instrument_id="card-2")
            ).json()["status"],
            "posted",
        )
        self.assertEqual(
            self.client.post("/bank/transactions", json=self.payment("upi")).json()["status"], "posted"
        )

    def test_insufficient_balance_decline_is_durable(self):
        declined = self.client.post("/bank/transactions", json=self.payment(amount_minor=100000001)).json()
        self.assertEqual(declined["status"], "declined")
        self.assertEqual(declined["reason"], "insufficient_funds")
        self.assertEqual(declined["balance_minor"], 100000000)
        self.assertEqual(
            self.client.post("/bank/transactions", json=self.payment(amount_minor=100000001)).json(), declined
        )

    def test_reject_mode_preserves_existing_results_and_rejects_new_mutations(self):
        posted = self.client.post("/bank/transactions", json=self.payment()).json()
        action = self.client.post("/bank/actions", json=self.action()).json()
        self.assertEqual(
            self.client.post("/bank/control", json={"mode": "reject"}).json(), {"mode": "reject"}
        )
        self.assertEqual(self.client.get("/bank/status").json(), {"simulation": True, "mode": "reject"})
        self.assertEqual(self.client.post("/bank/transactions", json=self.payment()).json(), posted)
        self.assertEqual(self.client.post("/bank/actions", json=self.action()).json(), action)
        self.assertEqual(self.client.get("/bank/actions/restrict-1").json(), action)
        self.assertEqual(self.client.post("/bank/transactions", json=self.payment("fresh")).status_code, 503)
        self.assertEqual(self.client.post("/bank/actions", json=self.action("fresh")).status_code, 503)
        self.assertEqual(
            self.client.post("/bank/actions", json=self.action(case_id="conflict")).status_code, 409
        )

    def test_timeout_commits_action_and_replay_recovers_acknowledgement(self):
        self.client.post("/bank/control", json={"mode": "timeout_after_commit"})
        self.assertEqual(self.client.post("/bank/actions", json=self.action()).status_code, 504)
        retrieved = self.client.get("/bank/actions/restrict-1")
        self.assertEqual(retrieved.status_code, 200)
        self.assertTrue(retrieved.json()["restriction_active"])
        self.assertEqual(self.client.post("/bank/actions", json=self.action()).json(), retrieved.json())
        self.assertEqual(
            self.client.post("/bank/transactions", json=self.payment()).json()["status"], "declined"
        )
        self.assertEqual(self.client.get("/bank/accounts").json()["accounts"][0]["active_restrictions"], 1)

    def test_input_validation_rejects_lossy_amounts_missing_instruments_and_unknown_fields(self):
        for changes in [
            {"amount_minor": 0},
            {"amount_minor": -1},
            {"amount_minor": 1.5},
            {"amount_minor": True},
            {"amount_minor": "125"},
            {"channel": "cash"},
            {"txn_id": ""},
            {"account_id": " "},
            {"txn_id": "a" * 129},
            {"channel": "atm"},
            {"channel": "card"},
            {"unexpected": "field"},
        ]:
            with self.subTest(changes=changes):
                self.assertEqual(
                    self.client.post("/bank/transactions", json=self.payment(**changes)).status_code, 422
                )
        self.assertEqual(self.client.post("/bank/actions", json=self.action(target_id=" ")).status_code, 422)
        self.assertEqual(self.client.post("/bank/control", json={"mode": "offline"}).status_code, 422)
        self.assertEqual(self.client.get("/bank/accounts").json()["accounts"], [])
        self.assertEqual(self.client.get("/bank/actions/missing").status_code, 404)

    def test_concurrent_duplicate_payments_do_not_double_debit(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            responses = list(
                pool.map(lambda _: self.client.post("/bank/transactions", json=self.payment()), range(16))
            )
        self.assertTrue(all(response.status_code == 200 for response in responses))
        self.assertEqual(len({response.json()["bank_reference"] for response in responses}), 1)
        self.assertEqual(self.client.get("/bank/accounts").json()["accounts"][0]["balance_minor"], 99999875)


if __name__ == "__main__":
    unittest.main()
