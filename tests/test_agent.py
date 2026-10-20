"""Agent recommendations are factual, role-aware drafts, never final actions."""

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
from fraudlens.bank_simulator.main import create_app
from fraudlens.models.schemas import AnalystProfile
from fraudlens.operations.agent import auto_assign, build_brief, polish_summary, priority
from fraudlens.operations.models import TransactionInput
from fraudlens.operations.service import OperationsService
from fraudlens.operations.team import OperationError

T = datetime(2026, 10, 18, 12, tzinfo=timezone.utc)


def case(**changes):
    return {
        **dict(
            case_id="CASE-TEST",
            txn_id="TX-TEST",
            account_id="SIM-VICTIM-PRIVATE-1234",
            channel="upi",
            amount_minor=4800000,
            score=0.92,
            created_at=(T - timedelta(minutes=30)).isoformat(),
            status="new",
            verdict="unreviewed",
            reasons=["Pass-through: suspicious outgoing transfer"],
            assignee=None,
            version=1,
        ),
        **changes,
    }


def protection(**changes):
    return {
        **dict(
            action_id="ACT-TEST",
            operation="restrict",
            status="confirmed",
            target_id="SIM-VICTIM-PRIVATE-1234",
            target_type="account",
            created_at=T.isoformat(),
        ),
        **changes,
    }


class AgentTests(unittest.TestCase):
    def test_priority_two_hand_computed_cases(self):
        high, reason = priority(case(case_type="complaint"), T)
        self.assertEqual(high, 83)  # 50.6 risk + 7.2 value + 5 age + 20 complaint
        self.assertIn("0.92", reason)
        self.assertIn("complaint", reason.lower())
        low, _ = priority(
            case(score=0.2, amount_minor=2000000, created_at=(T - timedelta(hours=2)).isoformat()), T
        )
        self.assertEqual(low, 24)  # 11 risk + 3 value + 10 age

    def test_untraced_complaint_recommends_lien_on_first_mule(self):
        c = case(
            case_type="complaint",
            complaint={
                "victim_account_id": "SIM-VICTIM-PRIVATE-1234",
                "source": "1930_helpline",
                "reported_at": T.isoformat(),
            },
            trace=[
                dict(
                    hop=1,
                    account_id="SIM-MULE-PRIVATE-5678",
                    traced_minor=4800000,
                    available_minor=4800000,
                    lien_minor=0,
                )
            ],
            trace_prepared=False,
        )
        brief = build_brief({**c, "reasons": ["Victim-reported transfer; fund trace requested."]}, [], [])
        self.assertEqual(brief["typology"], "1930 victim complaint")
        self.assertEqual(brief["recommended_action"], "place_lien")
        self.assertEqual(brief["target_account_id"], "SIM-MULE-PRIVATE-5678")
        self.assertEqual(brief["amount_minor"], 4800000)

    def test_high_score_without_protection_recommends_restrict(self):
        self.assertEqual(build_brief(case(), [], [])["recommended_action"], "restrict")

    def test_confirmed_protection_recommends_analyst_verdict(self):
        brief = build_brief(case(), [], [protection()])
        self.assertEqual(brief["recommended_action"], "confirm_fraud")
        self.assertEqual(brief["required_role"], "l2_analyst")

    def test_fraud_verdict_recommends_supervisor_closure(self):
        brief = build_brief(case(verdict="fraud"), [], [protection()])
        self.assertEqual(brief["recommended_action"], "close_account")
        self.assertEqual(brief["required_role"], "supervisor")

    def test_low_score_detector_case_recommends_false_positive(self):
        self.assertEqual(build_brief(case(score=0.3), [], [])["recommended_action"], "false_positive")

    def test_middle_score_recommends_investigation(self):
        self.assertEqual(build_brief(case(score=0.65), [], [])["recommended_action"], "investigate")

    def test_complaint_low_detector_score_does_not_clear_a_victim_report(self):
        c = case(
            score=0.05,
            case_type="complaint",
            complaint={
                "victim_account_id": "SIM-VICTIM-PRIVATE-1234",
                "source": "1930_helpline",
                "reported_at": T.isoformat(),
            },
            trace=[
                dict(
                    hop=1,
                    account_id="SIM-MULE-PRIVATE-5678",
                    traced_minor=4800000,
                    available_minor=0,
                    lien_minor=4800000,
                    lien_status="confirmed",
                )
            ],
            trace_prepared=True,
        )
        self.assertEqual(
            build_brief(c, [], [protection(target_id="SIM-MULE-PRIVATE-5678")])["recommended_action"],
            "investigate",
        )
        c["verdict"] = "fraud"
        brief = build_brief(c, [], [])
        self.assertEqual(brief["recommended_action"], "close_account")
        self.assertEqual(brief["target_account_id"], "SIM-MULE-PRIVATE-5678")

    def test_narrative_masks_account_ids_and_uses_ist(self):
        transaction = dict(
            txn_id="TX-TEST", beneficiary_id="SIM-BENEFICIARY-PRIVATE-9876", timestamp=T.isoformat()
        )
        brief = build_brief(case(), [transaction], [])
        self.assertNotIn("SIM-VICTIM-PRIVATE-1234", brief["ncrp_narrative"])
        self.assertNotIn("SIM-BENEFICIARY-PRIVATE-9876", brief["ncrp_narrative"])
        self.assertIn("1234", brief["ncrp_narrative"])
        self.assertIn("17:30", brief["ncrp_narrative"])
        self.assertIn("₹48,000.00", brief["ncrp_narrative"])
        self.assertLessEqual(len(brief["evidence"]), 5)
        self.assertLessEqual(len(brief["next_steps"]), 4)

    def test_llm_cannot_change_rupee_facts(self):
        response = httpx.Response(
            200,
            json={"response": "Payment of ₹84,000 needs review."},
            request=httpx.Request("POST", "http://localhost"),
        )
        with (
            patch.dict("os.environ", {"FRAUDLENS_LLM": "ollama"}),
            patch("fraudlens.operations.agent.httpx.post", return_value=response),
        ):
            self.assertEqual(
                polish_summary("Payment of ₹48,000 needs review.", {"amount_minor": 4800000}),
                "Payment of ₹48,000 needs review.",
            )

    def test_llm_offline_falls_back(self):
        with (
            patch.dict("os.environ", {"FRAUDLENS_LLM": "ollama"}),
            patch("fraudlens.operations.agent.httpx.post", side_effect=httpx.ConnectError("offline")),
        ):
            self.assertEqual(polish_summary("Review this payment.", {}), "Review this payment.")

    def test_llm_accepts_rewording_with_the_same_amount(self):
        rewritten = "Review the suspicious payment of ₹48,000.00."
        response = httpx.Response(
            200, json={"response": rewritten}, request=httpx.Request("POST", "http://localhost")
        )
        with (
            patch.dict("os.environ", {"FRAUDLENS_LLM": "ollama"}),
            patch("fraudlens.operations.agent.httpx.post", return_value=response),
        ):
            self.assertEqual(
                polish_summary("Payment of ₹48,000 needs review.", {"amount_minor": 4800000}), rewritten
            )

    def test_auto_assign_skips_offline_and_balances_load(self):
        cases = [
            case(case_id="C1", priority=90),
            case(case_id="C2", priority=80),
            case(case_id="C3", priority=70),
            case(case_id="ASSIGNED", priority=100, assignee="someone"),
            case(case_id="RESOLVED", status="resolved", priority=100),
        ]
        team = [
            dict(username="offline", role="l1_analyst", online=False, open_assigned=0),
            dict(username="l2", role="l2_analyst", online=True, open_assigned=0),
            dict(username="kmehta", role="l1_analyst", online=True, open_assigned=1),
            dict(username="pnair", role="l1_analyst", online=True, open_assigned=0),
        ]
        self.assertEqual(auto_assign(cases, team), [("C1", "pnair"), ("C2", "kmehta"), ("C3", "pnair")])


class AgentServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.bank = TestClient(
            create_app(Path(self.tmp.name) / "bank.sqlite", api_key="test"), headers={"X-Bank-Key": "test"}
        )
        self.addCleanup(self.bank.close)
        self.service = OperationsService(Path(self.tmp.name) / "ops.sqlite", bank_client=self.bank)
        self.l1 = AnalystProfile(username="kmehta", display_name="K. Mehta", role="l1_analyst")
        self.supervisor = AnalystProfile(username="asharma", display_name="A. Sharma", role="supervisor")

    def test_agent_counters_and_briefs_come_from_actual_events(self):
        txn = TransactionInput(
            txn_id="AGENT-TX",
            account_id="SIM-AGENT",
            channel="upi",
            amount_minor=8000000,
            timestamp=T,
            new_device=True,
            new_beneficiary=True,
        )
        result = self.service.ingest(txn)
        self.service.process_jobs()
        snapshot = self.service.snapshot()
        self.assertIn("priority", snapshot["cases"][0])
        brief = self.service.get_brief(result["case"]["case_id"])
        self.assertEqual(brief["recommended_action"], "confirm_fraud")
        events = snapshot["events"]
        self.assertEqual(snapshot["agent"]["cases_triaged"], 1)
        self.assertEqual(
            snapshot["agent"]["briefs_drafted"],
            sum(e["event_type"] == "agent_brief_drafted" and e["actor"] == "agent" for e in events),
        )
        self.assertEqual(snapshot["agent"]["liens_placed"], 0)
        self.assertEqual(snapshot["cases"][0]["verdict"], "unreviewed")

    def test_only_supervisor_enables_auto_assignment_and_agent_never_decides(self):
        with self.assertRaises(OperationError) as caught:
            self.service.set_agent_settings(True, self.l1)
        self.assertEqual(caught.exception.status_code, 403)
        self.service.heartbeat(self.l1)
        self.service.set_agent_settings(True, self.supervisor)
        result = self.service.ingest(
            TransactionInput(
                txn_id="AUTO-TX",
                account_id="SIM-AUTO",
                channel="upi",
                amount_minor=8000000,
                timestamp=T,
                new_device=True,
                new_beneficiary=True,
            )
        )
        self.service.process_jobs()
        snapshot = self.service.snapshot()
        current = self.service.get_case(result["case"]["case_id"])
        self.assertEqual(current["assignee"], "kmehta")
        self.assertEqual(current["verdict"], "unreviewed")
        self.assertEqual(snapshot["agent"]["cases_auto_assigned"], 1)
        self.assertTrue(
            any(
                e["event_type"] == "case_auto_assigned" and e["actor"] == "agent" for e in current["timeline"]
            )
        )

    def test_agent_lien_counter_waits_for_bank_acknowledgement(self):
        result = self.service.ingest(
            TransactionInput(
                txn_id="LIEN-TX",
                account_id="SIM-LIEN",
                channel="upi",
                amount_minor=8000000,
                timestamp=T,
                new_device=True,
                new_beneficiary=True,
            )
        )
        with self.service.store.connect(write=True) as db:
            current = self.service.store.get(db, "cases", result["case"]["case_id"])
            self.service._queue_action(db, current, "lien", "agent", amount_minor=100000)
        self.assertEqual(self.service.snapshot()["agent"]["liens_placed"], 0)
        self.service.process_jobs()
        self.assertEqual(self.service.snapshot()["agent"]["liens_placed"], 1)


class QueueViewTests(unittest.TestCase):
    setUp = AgentServiceTests.setUp

    def test_case_queue_views_and_priority_sort(self):
        low = self.service.ingest(
            TransactionInput(
                txn_id="Q-LOW",
                account_id="SIM-Q1",
                channel="upi",
                amount_minor=600000,
                timestamp=T,
                new_device=True,
            )
        )["case"]
        high = self.service.ingest(
            TransactionInput(
                txn_id="Q-HIGH",
                account_id="SIM-Q2",
                channel="upi",
                amount_minor=8000000,
                timestamp=T,
                new_device=True,
                new_beneficiary=True,
            )
        )["case"]
        listing = self.service.listing("cases")
        self.assertEqual([c["case_id"] for c in listing["items"]], [high["case_id"], low["case_id"]])
        self.assertGreater(listing["items"][0]["priority"], listing["items"][1]["priority"])
        from fraudlens.operations.models import ClaimInput

        self.service.claim(
            low["case_id"],
            ClaimInput(expected_version=self.service.get_case(low["case_id"])["version"]),
            self.l1,
        )
        self.assertEqual(
            [c["case_id"] for c in self.service.listing("cases", view="mine", username="kmehta")["items"]],
            [low["case_id"]],
        )
        self.assertEqual(
            [c["case_id"] for c in self.service.listing("cases", view="unassigned")["items"]],
            [high["case_id"]],
        )
        self.assertEqual(self.service.listing("cases", view="complaints")["total"], 0)
        self.assertEqual(self.service.listing("cases", view="awaiting_approval")["total"], 0)
