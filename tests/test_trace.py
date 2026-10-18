"""Causal fund attribution and bank-acknowledged golden-hour holds."""
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from fraudlens.bank_simulator.main import create_app
from fraudlens.models.schemas import AnalystProfile
from fraudlens.operations.models import ComplaintInput, TransactionInput
from fraudlens.operations.service import ConflictError, OperationsService
from fraudlens.operations.trace import trace_funds


class TraceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        app = create_app(Path(self.tmp.name) / "bank.sqlite", api_key="test")
        self.bank = TestClient(app, headers={"X-Bank-Key": "test"})
        self.addCleanup(self.bank.close)
        self.ledger = app.state.ledger
        with self.ledger.connection(write=True) as db:
            for account in ("VICTIM", "M1", "M2", "M3"):
                self.ledger.ensure_account(db, account)
            db.execute("UPDATE accounts SET balance_minor=0 WHERE account_id!='VICTIM'")
        self.service = OperationsService(Path(self.tmp.name) / "ops.sqlite", bank_client=self.bank)
        self.actor = AnalystProfile(username="kmehta", display_name="K. Mehta", role="l1_analyst")
        self.t0 = datetime(2026, 10, 18, 12, tzinfo=timezone.utc)
        self.root = self.row("ROOT", "VICTIM", "M1", 5000000)

    def row(self, txn_id, sender, beneficiary, amount, minute=0, **changes):
        return dict(txn_id=txn_id, account_id=sender, beneficiary_id=beneficiary,
                    amount_minor=amount, timestamp=(self.t0 + timedelta(minutes=minute)).isoformat(),
                    channel="upi", payment_status="posted", **changes)

    def post(self, *rows):
        for row in rows:
            self.service.ingest(TransactionInput(**{k: v for k, v in row.items() if k != "payment_status"}))
            self.service.process_jobs()

    def complaint(self, **changes):
        return ComplaintInput(**{**dict(complaint_id="NCRP-123456", source="1930_helpline", victim_account_id="VICTIM",
            reported_txn_id="ROOT", reported_at=self.t0+timedelta(minutes=20)), **changes})

    def file(self, **changes):
        case = self.service.file_complaint(self.complaint(**changes), self.actor)
        for _ in range(2):
            self.service.process_jobs()
        return self.service.get_case(case["case_id"])

    def test_single_hop_full_hold(self):
        self.post(self.root)
        case = self.file()
        hop = case["trace"][0]
        self.assertEqual((hop["hop"], hop["account_id"], hop["traced_minor"], hop["lien_minor"], hop["outcome"]),
                         (1, "M1", 5000000, 5000000, "held"))
        self.assertEqual(case["held_total_minor"], 5000000)
        self.assertEqual(self.service.snapshot()["counts"]["held_total_minor"], 5000000)

    def test_fan_out_two_hops_fifo(self):
        rows = [self.root, self.row("T2", "M1", "M2", 3000000, 3), self.row("T3", "M1", "M3", 1500000, 4)]
        hops = trace_funds(rows, self.root)
        self.assertEqual([(h["hop"], h["account_id"], h["traced_minor"]) for h in hops],
                         [(1, "M1", 500000), (2, "M2", 3000000), (2, "M3", 1500000)])

    def test_atm_cashout_marks_funds_moved(self):
        cash = self.row("CASH", "M1", None, 2000000, 3)
        cash["channel"] = "atm"
        hops = trace_funds([self.root, cash], self.root)
        self.assertEqual(len(hops), 1)
        self.assertEqual(hops[0]["traced_minor"], 3000000)
        self.assertEqual(hops[0]["moved_minor"], 2000000)

    def test_partial_recovery_when_balance_spent(self):
        self.post(self.root)
        with self.ledger.connection(write=True) as db:
            db.execute("UPDATE accounts SET balance_minor=1200000 WHERE account_id='M1'")
        case = self.file()
        self.assertEqual(case["trace"][0]["outcome"], "partially_recovered")
        self.assertEqual(case["held_total_minor"], 1200000)
        self.assertEqual(case["traced_total_minor"], 5000000)

    def test_window_excludes_old_transactions(self):
        future = self.row("LATE", "M1", "M2", 3000000, 25*60)
        declined = {**self.row("DECLINE", "M1", "M2", 1000000, 1), "payment_status": "declined"}
        hops = trace_funds([self.root, future, declined], self.root)
        self.assertEqual([(h["account_id"], h["traced_minor"]) for h in hops], [("M1", 5000000)])

    def test_complaint_idempotent_and_conflict(self):
        self.post(self.root)
        first = self.file()
        again = self.file()
        self.assertEqual(first["case_id"], again["case_id"])
        self.assertEqual(len(again["actions"]), 1)
        with self.assertRaises(ConflictError):
            self.service.file_complaint(self.complaint(source="branch"), self.actor)
        with self.assertRaises(ConflictError):
            self.service.file_complaint(self.complaint(complaint_id="NCRP-654321"), self.actor)

    def test_agent_liens_are_audited_with_actor_agent(self):
        self.post(self.root)
        case = self.file()
        events = [e for e in case["timeline"] if e["event_type"] == "lien_requested"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["actor"], "agent")
        self.assertIn("Golden-hour lien on traced funds", events[0]["message"])

    def test_prearrival_outgoing_and_cycles_do_not_create_money(self):
        rows = [self.root, self.row("PREARRIVAL", "M2", "M3", 1000000, 1),
                self.row("TO-M2", "M1", "M2", 3000000, 3), self.row("BACK", "M2", "M1", 1000000, 5)]
        hops = trace_funds(rows, self.root)
        self.assertEqual({h["account_id"]: h["traced_minor"] for h in hops}, {"M1": 3000000, "M2": 2000000})
        self.assertEqual(sum(h["traced_minor"] for h in hops), 5000000)

    def test_reconverging_paths_merge_without_duplicate_spending(self):
        rows = [self.root, self.row("A", "M1", "M2", 2000000, 1), self.row("B", "M1", "M3", 2000000, 2),
                self.row("C", "M3", "M2", 2000000, 3), self.row("D", "M2", None, 3000000, 4)]
        hops = trace_funds(rows, self.root)
        self.assertEqual({h["account_id"]: h["traced_minor"] for h in hops}, {"M1": 1000000, "M2": 1000000, "M3": 0})
        self.assertEqual(sum(h["moved_minor"] for h in hops), 3000000)

    def test_pending_and_failed_bank_holds_are_not_recovered_funds(self):
        self.post(self.root)
        self.bank.post("/bank/control", json={"mode": "reject"})
        case = self.service.file_complaint(self.complaint(), self.actor)
        self.assertEqual(case["held_total_minor"], 0)
        self.service.process_jobs()
        case = self.service.get_case(case["case_id"])
        self.assertEqual(case["held_total_minor"], 0)
        self.assertEqual(case["trace"][0]["outcome"], "pending")
        self.assertEqual(case["trace"][0]["lien_status"], "failed")

    def test_bank_outage_recovers_without_refiling_complaint(self):
        self.post(self.root)
        with patch.object(self.bank, "get", side_effect=httpx.ConnectError("offline")):
            case = self.service.file_complaint(self.complaint(), self.actor)
        self.assertEqual(case["held_total_minor"], 0)
        self.service.process_jobs()
        self.service.process_jobs()
        self.assertEqual(self.service.get_case(case["case_id"])["held_total_minor"], 5000000)

    def test_report_includes_fund_trail_and_confirmed_amount(self):
        from fraudlens.operations.reports import markdown, pdf, report
        self.post(self.root)
        case = self.file()
        value = report(case)
        self.assertEqual(value["case"]["held_total_minor"], 5000000)
        self.assertIn("Fund trail", markdown(value))
        self.assertIn("50,000.00", markdown(value))
        self.assertTrue(pdf(value).startswith(b"%PDF"))

    def test_victim_account_rejected_for_all_complaint_protection(self):
        from fraudlens.operations.models import DecisionInput
        from fraudlens.operations.team import OperationError
        self.post(self.root)
        case = self.file()
        supervisor = self.actor.model_copy(update={"role": "supervisor"})
        for action in ("close_account", "restrict", "place_lien"):
            with self.subTest(action=action), self.assertRaises(OperationError) as caught:
                data = dict(action=action, expected_version=case["version"], notes="Test target", target_account_id="VICTIM")
                if action == "place_lien":
                    data["amount_minor"] = 100
                self.service.decide(case["case_id"], DecisionInput(**data), supervisor)
            self.assertEqual(caught.exception.status_code, 400)
            self.assertEqual(str(caught.exception), "This is the complainant's account.")
        self.assertEqual(self.service.get_case(case["case_id"])["version"], case["version"])

    def test_closing_hop_two_leaves_hop_one_untouched(self):
        from fraudlens.operations.models import DecisionInput
        self.post(self.root, self.row("NEXT", "M1", "M2", 3000000, 3))
        case = self.file()
        supervisor = self.actor.model_copy(update={"role": "supervisor"})
        case = self.service.decide(case["case_id"], DecisionInput(action="confirm_fraud", expected_version=case["version"], notes="Verified complaint"), supervisor)
        self.service.process_jobs()
        case = self.service.get_case(case["case_id"])
        self.service.decide(case["case_id"], DecisionInput(action="close_account", expected_version=case["version"], target_account_id="M2"), supervisor)
        self.service.process_jobs()
        bank = {a["account_id"]: a for a in self.bank.get("/bank/accounts").json()["accounts"]}
        self.assertEqual(bank["M2"]["status"], "closed")
        self.assertNotEqual(bank["M1"]["status"], "closed")
        self.assertEqual(bank["VICTIM"]["status"], "active")
        case = self.service.get_case(case["case_id"])
        closes = [a for a in case["actions"] if a["operation"] == "close"]
        self.assertEqual([a["target_id"] for a in closes], ["M2"])
        self.assertTrue(any("M2" in e["message"] and e["actor"] == "kmehta" for e in case["timeline"] if e["event_type"] == "close_requested"))
        # Closure is per traced account, so another mule can subsequently close.
        self.service.decide(case["case_id"], DecisionInput(action="close_account", expected_version=case["version"], target_account_id="M1"), supervisor)
        self.service.process_jobs()
        bank = {a["account_id"]: a for a in self.bank.get("/bank/accounts").json()["accounts"]}
        self.assertEqual(bank["M1"]["status"], "closed")

    def test_close_on_account_not_in_trace_is_rejected(self):
        from fraudlens.operations.models import DecisionInput
        from fraudlens.operations.team import OperationError
        self.post(self.root)
        case = self.file()
        with self.assertRaises(OperationError) as caught:
            self.service.decide(case["case_id"], DecisionInput(action="close_account", expected_version=case["version"], target_account_id="M3"), self.actor.model_copy(update={"role": "supervisor"}))
        self.assertEqual(caught.exception.status_code, 400)
        self.assertEqual(self.service.get_case(case["case_id"])["version"], case["version"])

    def test_returned_victim_funds_are_never_liened(self):
        self.post(self.root, self.row("RETURN", "M1", "VICTIM", 1000000, 2))
        case = self.file()
        self.assertTrue(all(a["target_id"] != "VICTIM" for a in case["actions"]))
        self.assertEqual(case["held_total_minor"], 4000000)

    def test_preexisting_pending_victim_restriction_cannot_execute_after_complaint(self):
        from fraudlens.operations.models import DecisionInput
        self.post({**self.root, "new_device": True})
        case = self.service.snapshot()["cases"][0]
        self.service.decide(case["case_id"], DecisionInput(action="restrict", expected_version=case["version"]), self.actor.model_copy(update={"role": "l2_analyst"}))
        case = self.file()
        bank = {a["account_id"]: a for a in self.bank.get("/bank/accounts").json()["accounts"]}
        self.assertEqual(bank["VICTIM"]["status"], "active")
        stale = next(a for a in case["actions"] if a["target_id"] == "VICTIM")
        self.assertEqual(stale["status"], "superseded")

    def test_selected_hop_survives_approval(self):
        from fraudlens.operations.models import ApprovalRequestInput, ApprovalDecisionInput, DecisionInput
        self.post(self.root, self.row("NEXT", "M1", "M2", 3000000, 3))
        case = self.file()
        l2 = self.actor.model_copy(update={"username": "riyer", "display_name": "R. Iyer", "role": "l2_analyst"})
        supervisor = self.actor.model_copy(update={"username": "asharma", "role": "supervisor"})
        case = self.service.decide(case["case_id"], DecisionInput(action="confirm_fraud", expected_version=case["version"], notes="Verified evidence"), l2)
        case = self.service.request_approval(case["case_id"], ApprovalRequestInput(action="close_account", expected_version=case["version"], notes="Close second-hop mule", target_account_id="M2"), l2)
        self.assertEqual(case["pending_approval"]["target_account_id"], "M2")
        case = self.service.decide_approval(case["case_id"], ApprovalDecisionInput(approve=True), supervisor)
        self.assertEqual(next(a for a in case["actions"] if a["operation"] == "close")["target_id"], "M2")

    def test_report_formats_paise_with_indian_grouping(self):
        from fraudlens.operations.reports import markdown, report
        self.post(self.root)
        case = self.file()
        case["amount_minor"] = 123456789
        self.assertIn("Amount: ₹12,34,567.89", markdown(report(case)))

    def test_explicit_victim_target_has_required_400_even_for_l1(self):
        from fraudlens.operations.models import DecisionInput
        from fraudlens.operations.team import OperationError
        self.post(self.root)
        case = self.file()
        for action in ("close_account", "restrict"):
            with self.subTest(action=action):
                with self.assertRaises(OperationError) as caught:
                    self.service.decide(case["case_id"], DecisionInput(action=action, expected_version=case["version"], target_account_id="VICTIM"), self.actor)
                self.assertEqual(caught.exception.status_code, 400)
                self.assertEqual(str(caught.exception), "This is the complainant's account.")
