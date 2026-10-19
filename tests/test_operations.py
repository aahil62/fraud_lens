"""Operational lifecycle against the real simulator API and isolated databases."""
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import ValidationError

from fraudlens.bank_simulator.main import create_app
from fraudlens.operations.models import DecisionInput, TransactionInput
from fraudlens.models.schemas import AnalystProfile
from fraudlens.operations.service import ConflictError, OperationsService


class OperationsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "operations.sqlite"
        self.bank = TestClient(create_app(db_path=Path(self.tmp.name) / "bank.sqlite", api_key="test-key"),
                               headers={"X-Bank-Key": "test-key"})
        self.addCleanup(self.bank.close)
        self.service = OperationsService(self.path, bank_client=self.bank)

    def transaction(self, channel="upi", txn_id="TX-1", account="ACC-1", risky=False, **changes):
        data = dict(txn_id=txn_id, account_id=account, channel=channel, amount_minor=8000000 if risky else 25000,
                    timestamp=datetime.now(timezone.utc).isoformat(), instrument_id="CARD-1" if channel in {"card", "atm"} else None,
                    new_device=risky, new_beneficiary=risky, failed_auth_attempts=4 if risky else 0)
        data.update(changes)
        return TransactionInput(**data)

    def test_all_channels_detect_protect_and_decline(self):
        for i, channel in enumerate(("upi", "net_banking", "card", "atm")):
            result = self.service.ingest(self.transaction(channel, f"F-{i}", f"ACC-{i}", True,
                                                         instrument_id=f"CARD-{i}" if channel in {"card", "atm"} else None))
            self.assertIsNotNone(result["case"])
            self.service.process_jobs()
            case = self.service.get_case(result["case"]["case_id"])
            self.assertEqual(case["actions"][0]["status"], "confirmed")
        snapshot = self.service.snapshot()
        self.assertEqual(snapshot["counts"]["transactions"], 4)
        self.assertEqual(snapshot["counts"]["declined"], 4)
        self.assertEqual(sum(c["transactions"] for c in snapshot["channels"]), 4)
        self.assertEqual(snapshot["counts"]["restricted_accounts"] + snapshot["counts"]["restricted_cards"], 4)

    def test_false_positive_release_and_fraud_resolution(self):
        result = self.service.ingest(self.transaction(risky=True))
        self.service.process_jobs()
        case = self.service.get_case(result["case"]["case_id"])
        decided = self.service.decide(case["case_id"], DecisionInput(action="false_positive", expected_version=case["version"],
                                        notes="Customer confirmed legitimate purchase."), AnalystProfile(username="analyst-one", display_name="analyst-one", role="l2_analyst"))
        self.assertNotEqual(decided["status"], "resolved")
        self.service.process_jobs()
        case = self.service.get_case(case["case_id"])
        self.assertEqual(case["status"], "resolved")
        self.assertEqual(case["verdict"], "false_positive")
        followup = self.service.ingest(self.transaction(txn_id="TX-2"))
        self.service.process_jobs()
        self.assertEqual(self.service.snapshot()["counts"]["posted"], 1)
        self.assertIsNone(followup["case"])
        self.assertTrue(any(e["actor"] == "analyst-one" for e in case["timeline"]))

    def test_idempotent_ingest_and_conflicting_reuse(self):
        txn = self.transaction()
        self.service.ingest(txn)
        self.assertTrue(self.service.ingest(txn)["duplicate"])
        with self.assertRaises(ConflictError):
            self.service.ingest(txn.model_copy(update={"amount_minor": 26000}))
        self.service.process_jobs()
        self.assertEqual(self.service.snapshot()["counts"]["transactions"], 1)

    def test_optimistic_decisions_reject_stale_version(self):
        case = self.service.ingest(self.transaction(risky=True))["case"]
        self.service.decide(case["case_id"], DecisionInput(action="investigate", expected_version=case["version"], notes="Reviewing"), AnalystProfile(username="first", display_name="first", role="l2_analyst"))
        with self.assertRaises(ConflictError):
            self.service.decide(case["case_id"], DecisionInput(action="escalate", expected_version=case["version"], notes="Stale"), AnalystProfile(username="second", display_name="second", role="l2_analyst"))

    def test_one_reversal_does_not_release_other_case(self):
        one = self.service.ingest(self.transaction(risky=True))["case"]
        two = self.service.ingest(self.transaction(txn_id="TX-2", risky=True))["case"]
        self.service.process_jobs()
        one = self.service.get_case(one["case_id"])
        self.service.decide(one["case_id"], DecisionInput(action="false_positive", expected_version=one["version"], notes="Legitimate"), AnalystProfile(username="analyst", display_name="analyst", role="l2_analyst"))
        self.service.process_jobs()
        self.assertEqual(self.service.snapshot()["counts"]["restricted_accounts"], 1)
        self.assertEqual(self.service.get_case(two["case_id"])["verdict"], "unreviewed")
        self.service.ingest(self.transaction(txn_id="TX-3"))
        self.service.process_jobs()
        self.assertEqual(self.service.snapshot()["transactions"][0]["payment_status"], "declined")

    def test_rejected_actions_are_visible_and_recoverable(self):
        self.bank.post("/bank/control", json={"mode": "reject"})
        case = self.service.ingest(self.transaction(risky=True))["case"]
        self.service.process_jobs()
        snap = self.service.snapshot()
        self.assertEqual(snap["counts"]["restricted_accounts"], 0)
        self.assertEqual(snap["counts"]["failed_actions"], 1)
        self.assertEqual(snap["counts"]["pending_payments"], 1)
        self.bank.post("/bank/control", json={"mode": "normal"})
        action = self.service.get_case(case["case_id"])["actions"][0]
        self.service.retry_action(action["action_id"], AnalystProfile(username="analyst", display_name="analyst", role="l2_analyst"))
        self.service.process_jobs()
        self.assertEqual(self.service.snapshot()["counts"]["restricted_accounts"], 1)

    def test_timeout_reconciles_and_state_survives_restart(self):
        self.bank.post("/bank/control", json={"mode": "timeout_after_commit"})
        case = self.service.ingest(self.transaction(risky=True))["case"]
        self.service.process_jobs()
        restarted = OperationsService(self.path, bank_client=self.bank)
        restarted.process_jobs()
        self.assertEqual(restarted.get_case(case["case_id"])["actions"][0]["status"], "confirmed")
        self.assertEqual(restarted.snapshot()["counts"]["declined"], 1)

    def test_pending_restriction_reversed_before_delivery_does_not_resurrect(self):
        case = self.service.ingest(self.transaction(risky=True))["case"]
        self.service.decide(case["case_id"], DecisionInput(action="false_positive", expected_version=case["version"], notes="Verified customer"), AnalystProfile(username="analyst", display_name="analyst", role="l2_analyst"))
        self.service.process_jobs()
        self.assertEqual(self.service.snapshot()["counts"]["restricted_accounts"], 0)
        self.assertEqual(self.service.get_case(case["case_id"])["status"], "resolved")

    def test_pending_release_cannot_be_overwritten_by_contradictory_verdict(self):
        case = self.service.ingest(self.transaction(risky=True))["case"]
        self.service.process_jobs()
        case = self.service.get_case(case["case_id"])
        case = self.service.decide(case["case_id"], DecisionInput(action="false_positive", expected_version=case["version"], notes="Legitimate"), AnalystProfile(username="analyst", display_name="analyst", role="l2_analyst"))
        with self.assertRaises(ConflictError):
            self.service.decide(case["case_id"], DecisionInput(action="confirm_fraud", expected_version=case["version"], notes="Conflicting action"), AnalystProfile(username="other", display_name="other", role="l2_analyst"))
        self.service.process_jobs()
        self.assertEqual(self.service.get_case(case["case_id"])["verdict"], "false_positive")

    def test_strict_money_channel_timestamp_and_decision_validation(self):
        for changes in ({"amount_minor": -1}, {"amount_minor": 1.5}, {"amount_minor": True},
                        {"timestamp": "yesterday"}, {"channel": "cash"}, {"instrument_id": ""}):
            with self.assertRaises(ValidationError):
                self.transaction(**{"channel": "card", **changes})
        with self.assertRaises(ValidationError):
            DecisionInput(action="false_positive", expected_version=1, notes=" ")

    def test_future_history_does_not_influence_past_transaction(self):
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        self.service.ingest(self.transaction(txn_id="FUTURE", timestamp=future.isoformat()))
        normal = self.service.ingest(self.transaction(txn_id="PAST"))
        self.assertIsNone(normal["case"])

    def test_interrupted_seed_resumes_without_duplicate_activity(self):
        original = self.service.ingest
        calls = 0

        def interrupted(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise RuntimeError("Simulated crash")
            return original(*args, **kwargs)

        self.service.ingest = interrupted
        with self.assertRaises(RuntimeError):
            self.service.seed_baseline()
        self.assertEqual(self.service.snapshot()["counts"]["transactions"], 2)
        restarted = OperationsService(self.path, bank_client=self.bank)
        restarted.seed_baseline()
        self.assertEqual(restarted.snapshot()["counts"]["transactions"], 21)
        restarted.seed_baseline()
        self.assertEqual(restarted.snapshot()["counts"]["transactions"], 21)

    def test_baseline_does_not_inject_into_existing_user_ledger(self):
        self.service.ingest(self.transaction())
        self.service.seed_baseline()
        self.assertEqual(self.service.snapshot()["counts"]["transactions"], 1)

    def test_shared_device_beneficiary_network_is_detected(self):
        for i in range(2):
            self.service.ingest(self.transaction(txn_id=f"H-{i}", account=f"OTHER-{i}", device_id="DEV-SHARED"))
        result = self.service.ingest(self.transaction(txn_id="MULE", account="NEW-ACCOUNT", device_id="DEV-SHARED",
                                    new_beneficiary=True, amount_minor=1500000))
        self.assertIsNotNone(result["case"])
        self.assertGreaterEqual(result["case"]["score"], .8)
        self.assertEqual(len(result["case"]["related_accounts"]), 2)

    def test_atm_location_change_with_large_withdrawal_is_detected(self):
        self.service.ingest(self.transaction(channel="atm", location="Pune"))
        result = self.service.ingest(self.transaction(channel="atm", txn_id="ATM-NEW-LOCATION", location="Delhi", amount_minor=1200000))
        self.assertIsNotNone(result["case"])
        self.assertGreaterEqual(result["case"]["score"], .8)


if __name__ == "__main__":
    unittest.main()
