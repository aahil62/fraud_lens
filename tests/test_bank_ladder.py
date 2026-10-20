"""Bank-side money conservation, holds, closure and replay guarantees."""

import json
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient
from fraudlens.bank_simulator.main import create_app


class BankLadderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "bank.sqlite"
        self.app = create_app(self.path, api_key="test")
        self.client = TestClient(self.app, headers={"X-Bank-Key": "test"})
        self.addCleanup(self.client.close)
        with self.app.state.ledger.connection(write=True) as db:
            self.app.state.ledger.ensure_account(db, "A")
            self.app.state.ledger.ensure_account(db, "B")
            db.execute("UPDATE accounts SET balance_minor=1000000")

    def action(self, operation="lien", **changes):
        value = dict(
            action_id="ACT-1", case_id="CASE-1", operation=operation, target_type="account", target_id="A"
        )
        if operation == "lien":
            value["amount_minor"] = 800000
        return self.client.post("/bank/actions", json={**value, **changes})

    def pay(self, amount=300000, **changes):
        return self.client.post(
            "/bank/transactions",
            json={"txn_id": "TX-1", "account_id": "A", "channel": "upi", "amount_minor": amount, **changes},
        )

    def account(self, account="A"):
        return next(
            a for a in self.client.get("/bank/accounts").json()["accounts"] if a["account_id"] == account
        )

    def test_lien_blocks_debit_above_available(self):
        self.assertEqual(self.action().status_code, 200)
        self.assertEqual(self.account()["available_minor"], 200000)
        self.assertEqual(self.pay().json()["reason"], "lien_hold")
        self.assertEqual(self.pay(150000, txn_id="TX-2").json()["status"], "posted")
        self.assertEqual(self.account()["available_minor"], 50000)

    def test_lien_release_restores_available(self):
        self.action()
        self.assertEqual(self.action("lien_release", action_id="RELEASE").status_code, 200)
        self.assertEqual(self.account()["available_minor"], 1000000)
        self.assertEqual(self.account()["liens"], [])

    def test_credit_posts_to_known_beneficiary(self):
        response = self.pay(200000, beneficiary_id="B")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.account()["balance_minor"], 800000)
        self.assertEqual(self.account("B")["balance_minor"], 1200000)
        self.assertEqual(self.pay(200000, beneficiary_id="B").json(), response.json())
        self.assertEqual(self.account("B")["balance_minor"], 1200000)

    def test_credit_into_liened_account_posts(self):
        self.action(target_id="B")
        self.assertEqual(self.pay(200000, beneficiary_id="B").json()["status"], "posted")
        self.assertEqual(self.account("B")["available_minor"], 400000)

    def test_close_blocks_debits_and_incoming(self):
        self.assertEqual(self.action("close", target_id="B").status_code, 200)
        self.assertEqual(self.pay(100, account_id="B").json()["reason"], "account_closed")
        self.assertEqual(
            self.pay(200000, txn_id="INCOMING", beneficiary_id="B").json()["reason"], "beneficiary_closed"
        )
        self.assertEqual(self.account()["balance_minor"], 1000000)
        self.assertEqual(self.account("B")["balance_minor"], 1000000)
        self.assertEqual(self.account("B")["status"], "closed")
        self.action("release", action_id="REOPEN", target_id="B")
        self.assertEqual(self.account("B")["status"], "closed")

    def test_lien_requires_amount(self):
        self.assertEqual(self.action(amount_minor=None).status_code, 422)
        for amount in (0, -1, True, 1.5, "100"):
            with self.subTest(amount=amount):
                self.assertEqual(self.action(amount_minor=amount).status_code, 422)
        self.assertEqual(self.action("restrict", amount_minor=1).status_code, 422)

    def test_close_requires_account_target(self):
        for operation in ("close", "lien", "lien_release"):
            self.assertEqual(self.action(operation, target_type="card").status_code, 422)

    def test_action_idempotent_same_id(self):
        first = self.action()
        self.assertEqual(first.status_code, 200)
        self.assertEqual(self.action().json(), first.json())
        self.assertEqual(len(self.account()["liens"]), 1)
        self.assertEqual(self.action(amount_minor=700000).status_code, 409)

    def test_competing_liens_cannot_overdraw_available(self):
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(lambda n: self.action(action_id=f"ACT-{n}", case_id=f"CASE-{n}"), [1, 2]))
        self.assertEqual(sorted(r.status_code for r in results), [200, 409])
        self.assertEqual(self.account()["available_minor"], 200000)

    def test_release_preserves_other_cases_lien(self):
        self.action(amount_minor=300000)
        self.action(action_id="OTHER", case_id="CASE-2", amount_minor=400000)
        self.action("lien_release", action_id="RELEASE")
        self.assertEqual(self.account()["available_minor"], 600000)
        self.assertEqual(self.account()["liens"][0]["case_id"], "CASE-2")

    def test_existing_accounts_migrate_and_legacy_payment_replays(self):
        old = Path(self.tmp.name) / "legacy.sqlite"
        with sqlite3.connect(old) as db:
            db.executescript(
                'CREATE TABLE accounts(account_id TEXT PRIMARY KEY,balance_minor INTEGER NOT NULL); INSERT INTO accounts VALUES("OLD",500000);'
            )
        migrated = create_app(old, api_key="test")
        with TestClient(migrated, headers={"X-Bank-Key": "test"}) as client:
            account = client.get("/bank/accounts").json()["accounts"][0]
            self.assertEqual(account["status"], "active")
            self.assertEqual(account["available_minor"], 500000)
            payload = dict(
                txn_id="LEGACY", account_id="OLD", channel="upi", amount_minor=100, instrument_id=None
            )
            response = dict(
                txn_id="LEGACY",
                status="posted",
                reason="posted",
                balance_minor=499900,
                bank_reference="old-ref",
            )
            with migrated.state.ledger.connection(write=True) as db:
                db.execute(
                    "INSERT INTO payments VALUES(?,?,?)",
                    (
                        "LEGACY",
                        json.dumps(payload, sort_keys=True, separators=(",", ":")),
                        json.dumps(response),
                    ),
                )
            self.assertEqual(client.post("/bank/transactions", json=payload).json(), response)


class BankOperationsLadderTests(unittest.TestCase):
    def setUp(self):
        from datetime import datetime, timezone

        from fraudlens.models.schemas import AnalystProfile
        from fraudlens.operations.models import TransactionInput
        from fraudlens.operations.service import OperationsService

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        app = create_app(Path(self.tmp.name) / "bank.sqlite", api_key="test")
        self.bank = TestClient(app, headers={"X-Bank-Key": "test"})
        self.addCleanup(self.bank.close)
        self.ledger = app.state.ledger
        self.service = OperationsService(Path(self.tmp.name) / "ops.sqlite", bank_client=self.bank)
        self.actor = AnalystProfile(username="asharma", display_name="A. Sharma", role="supervisor")
        self.txn = TransactionInput(
            txn_id="CARD-FRAUD",
            account_id="A",
            channel="card",
            instrument_id="CARD-A",
            amount_minor=8000000,
            timestamp=datetime.now(timezone.utc),
            new_device=True,
            failed_auth_attempts=4,
        )
        self.case = self.service.ingest(self.txn)["case"]
        self.service.process_jobs()

    def decide(self, action, **fields):
        from fraudlens.operations.models import DecisionInput

        case = self.service.get_case(self.case["case_id"])
        return self.service.decide(
            case["case_id"],
            DecisionInput(
                action=action, expected_version=case["version"], notes="Verified test evidence", **fields
            ),
            self.actor,
        )

    def test_close_of_card_case_targets_account_and_remains_final(self):
        from fraudlens.operations.service import ConflictError

        self.decide("confirm_fraud")
        requested = self.decide("close_account")
        close = next(a for a in requested["actions"] if a["operation"] == "close")
        self.assertEqual(close["target_type"], "account")
        self.assertEqual(close["target_id"], "A")
        self.assertEqual(close["status"], "pending")
        self.service.process_jobs()
        case = self.service.get_case(self.case["case_id"])
        self.assertEqual(next(a for a in case["actions"] if a["operation"] == "close")["status"], "confirmed")
        self.assertEqual(case["status"], "resolved")
        self.assertEqual(self.service.snapshot()["bank"]["accounts"][0]["status"], "closed")
        with self.assertRaises(ConflictError):
            self.decide("false_positive")

    def test_lien_amount_is_delivered_and_false_positive_releases_it(self):
        self.decide("place_lien", amount_minor=100000)
        self.service.process_jobs()
        bank = self.service.snapshot()["bank"]["accounts"][0]
        self.assertEqual(bank["available_minor"], 99900000)
        self.assertEqual(bank["liens"][0]["amount_minor"], 100000)
        self.decide("false_positive")
        self.service.process_jobs()
        self.assertEqual(self.service.snapshot()["bank"]["accounts"][0]["liens"], [])

    def test_ops_forwards_beneficiary_for_credit_posting(self):
        with self.ledger.connection(write=True) as db:
            self.ledger.ensure_account(db, "B")
        self.service.ingest(
            self.txn.model_copy(
                update={
                    "txn_id": "CREDIT",
                    "account_id": "C",
                    "channel": "upi",
                    "instrument_id": None,
                    "new_device": False,
                    "failed_auth_attempts": 0,
                    "beneficiary_id": "B",
                    "amount_minor": 200000,
                }
            )
        )
        self.service.process_jobs()
        bank = self.service.snapshot()["bank"]["accounts"]
        self.assertEqual(next(a for a in bank if a["account_id"] == "B")["balance_minor"], 100200000)

    def test_pending_lien_prevents_premature_fraud_resolution(self):
        self.decide("place_lien", amount_minor=100000)
        case = self.decide("confirm_fraud")
        self.assertEqual(case["status"], "investigating")
        self.service.process_jobs()
        self.assertEqual(self.service.get_case(case["case_id"])["status"], "resolved")
