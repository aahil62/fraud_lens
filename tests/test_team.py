"""Ownership and approval invariants against the transactional operations store."""

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from fraudlens.bank_simulator.main import create_app
from fraudlens.core.auth.store import AnalystStore
from fraudlens.models.schemas import AnalystProfile
from fraudlens.operations.models import (
    ApprovalDecisionInput,
    ApprovalRequestInput,
    AssignInput,
    ClaimInput,
    DecisionInput,
    TransactionInput,
)
from fraudlens.operations.service import ConflictError, OperationsService
from fraudlens.operations.team import OperationError
from pydantic import ValidationError


class TeamTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        with patch.dict("os.environ", {"FRAUDLENS_MODE": "demo"}):
            self.analysts = AnalystStore(str(root / "analysts.json"))
        self.l1 = self.profile("kmehta")
        self.l2 = self.profile("riyer")
        self.supervisor = self.profile("asharma")
        self.t = datetime(2026, 10, 18, 12, tzinfo=timezone.utc)
        self.path = root / "ops.sqlite"
        self.bank = TestClient(
            create_app(root / "bank.sqlite", api_key="test"), headers={"X-Bank-Key": "test"}
        )
        self.addCleanup(self.bank.close)
        self.service = OperationsService(
            self.path, bank_client=self.bank, analysts=self.analysts, clock=lambda: self.t
        )
        self.case = self.service.ingest(
            TransactionInput(
                txn_id="TEAM-TX",
                account_id="TEAM-ACCOUNT",
                channel="upi",
                amount_minor=8000000,
                timestamp=self.t,
                new_device=True,
                new_beneficiary=True,
                failed_auth_attempts=4,
            )
        )["case"]
        self.cid = self.case["case_id"]

    def profile(self, username):
        account = self.analysts.get(username)
        return AnalystProfile(username=account.username, display_name=account.display_name, role=account.role)

    def request(self, action, actor=None):
        return self.service.request_approval(
            self.cid,
            ApprovalRequestInput(
                action=action,
                expected_version=self.service.get_case(self.cid)["version"],
                notes="Review bank evidence",
            ),
            actor or self.l1,
        )

    def test_l1_cannot_confirm_fraud_directly(self):
        before = self.service.get_case(self.cid)
        with self.assertRaises(OperationError) as caught:
            self.service.decide(
                self.cid,
                DecisionInput(action="confirm_fraud", expected_version=before["version"], notes="Confirmed"),
                self.l1,
            )
        self.assertEqual(caught.exception.status_code, 403)
        self.assertEqual(caught.exception.payload["required_role"], "l2_analyst")
        after = self.service.get_case(self.cid)
        self.assertEqual(after["version"], before["version"])
        self.assertEqual(len(after["actions"]), len(before["actions"]))
        self.assertEqual(after["verdict"], "unreviewed")

    def test_l1_requests_approval_l2_approves(self):
        self.request("confirm_fraud")
        result = self.service.decide_approval(self.cid, ApprovalDecisionInput(approve=True), self.l2)
        self.assertEqual(result["verdict"], "fraud")
        self.assertIsNone(result["pending_approval"])
        self.assertTrue(
            any("Approved by R. Iyer (requested by K. Mehta)" in e["message"] for e in result["timeline"])
        )

    def test_requester_cannot_approve_own_request(self):
        self.request("confirm_fraud")
        with self.assertRaises(OperationError) as caught:
            self.service.decide_approval(self.cid, ApprovalDecisionInput(approve=True), self.l1)
        self.assertEqual(caught.exception.status_code, 403)
        self.assertIsNotNone(self.service.get_case(self.cid)["pending_approval"])

    def test_close_account_requires_supervisor(self):
        self.service.decide(
            self.cid,
            DecisionInput(
                action="confirm_fraud", expected_version=self.case["version"], notes="Verified fraud"
            ),
            self.l2,
        )
        self.request("close_account", self.l2)
        with self.assertRaises(OperationError) as caught:
            self.service.decide_approval(
                self.cid,
                ApprovalDecisionInput(approve=True),
                self.profile("riyer").model_copy(update={"username": "another-l2"}),
            )
        self.assertEqual(caught.exception.payload["required_role"], "supervisor")
        result = self.service.decide_approval(self.cid, ApprovalDecisionInput(approve=True), self.supervisor)
        self.assertEqual([a["operation"] for a in result["actions"]].count("close"), 1)
        self.assertEqual(next(a for a in result["actions"] if a["operation"] == "close")["status"], "pending")

    def test_concurrent_claims_one_wins(self):
        second = OperationsService(self.path, bank_client=self.bank, analysts=self.analysts)
        barrier = Barrier(2)

        def claim(service, actor):
            barrier.wait()
            try:
                service.claim(self.cid, ClaimInput(expected_version=self.case["version"]), actor)
                return 200
            except ConflictError:
                return 409

        with ThreadPoolExecutor(2) as pool:
            a = pool.submit(claim, self.service, self.l1)
            b = pool.submit(claim, second, self.profile("pnair"))
            self.assertEqual(sorted([a.result(), b.result()]), [200, 409])

    def test_claim_assigned_to_other_is_409(self):
        case = self.service.claim(self.cid, ClaimInput(expected_version=self.case["version"]), self.l1)
        with self.assertRaises(ConflictError) as caught:
            self.service.claim(self.cid, ClaimInput(expected_version=case["version"]), self.l2)
        self.assertEqual(caught.exception.payload["assignee"], "kmehta")
        self.assertIn("K. Mehta", str(caught.exception))

    def test_presence_online_window(self):
        self.service.heartbeat(self.l1, self.cid)
        self.t += timedelta(seconds=44)
        member = next(t for t in self.service.snapshot()["team"] if t["username"] == "kmehta")
        self.assertTrue(member["online"])
        self.assertEqual(member["current_case_id"], self.cid)
        self.t += timedelta(seconds=2)
        self.assertFalse(
            next(t for t in self.service.snapshot()["team"] if t["username"] == "kmehta")["online"]
        )

    def test_handled_by_lists_distinct_actors_in_order(self):
        case = self.service.claim(self.cid, ClaimInput(expected_version=self.case["version"]), self.l1)
        case = self.service.decide(
            self.cid, DecisionInput(action="investigate", expected_version=case["version"]), self.l1
        )
        self.request("confirm_fraud")
        case = self.service.decide_approval(self.cid, ApprovalDecisionInput(approve=True), self.l2)
        self.assertEqual(case["handled_by"], ["kmehta", "riyer"])

    def test_rejection_requires_notes_and_clears_approval(self):
        self.request("confirm_fraud")
        with self.assertRaises(ValidationError):
            ApprovalDecisionInput(approve=False, notes=" ")
        result = self.service.decide_approval(
            self.cid, ApprovalDecisionInput(approve=False, notes="Need customer evidence"), self.l2
        )
        self.assertIsNone(result["pending_approval"])
        self.assertEqual(result["verdict"], "unreviewed")
        self.assertIn("Need customer evidence", result["timeline"][-1]["message"])

    def test_approval_request_cannot_be_duplicated_or_requested_by_authorized_actor(self):
        with self.assertRaises(OperationError) as caught:
            self.request("confirm_fraud", self.l2)
        self.assertEqual(caught.exception.status_code, 400)
        self.request("confirm_fraud")
        with self.assertRaises(ConflictError):
            self.request("false_positive")

    def test_assignment_requires_l2_and_existing_target(self):
        with self.assertRaises(OperationError):
            self.service.assign(
                self.cid, AssignInput(username="pnair", expected_version=self.case["version"]), self.l1
            )
        case = self.service.assign(
            self.cid, AssignInput(username="pnair", expected_version=self.case["version"]), self.l2
        )
        self.assertEqual(case["assignee"], "pnair")
        member = next(t for t in self.service.snapshot()["team"] if t["username"] == "pnair")
        self.assertEqual(member["open_assigned"], 1)
        with self.assertRaises(OperationError):
            self.service.assign(
                self.cid, AssignInput(username="missing", expected_version=case["version"]), self.l2
            )

    def test_http_role_denial_shape_and_no_body_role_escalation(self):
        from fraudlens.api.deps import get_current_analyst
        from fraudlens.api.routes.operations import router
        from fraudlens.api.state import state

        old = state.operations
        state.operations = self.service
        self.addCleanup(setattr, state, "operations", old)
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_current_analyst] = lambda: self.l1
        with TestClient(app) as client:
            for action, role in (("confirm_fraud", "l2_analyst"), ("close_account", "supervisor")):
                response = client.post(
                    f"/ops/cases/{self.cid}/decision",
                    json=dict(action=action, expected_version=self.case["version"], notes="Crafted request"),
                )
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json()["required_role"], role)
            response = client.post(
                f"/ops/cases/{self.cid}/decision",
                json=dict(action="confirm_fraud", expected_version=1, notes="Crafted", role="supervisor"),
            )
            self.assertEqual(response.status_code, 422)
        self.assertEqual(self.service.get_case(self.cid)["version"], self.case["version"])

    def test_invalid_approval_execution_rolls_back_atomically(self):
        self.request("close_account", self.l2)
        # The request is invalid until fraud is confirmed; failed execution must
        # roll back clearing the approval and any case/job mutations.
        before = self.service.get_case(self.cid)
        with self.assertRaises(ConflictError):
            self.service.decide_approval(self.cid, ApprovalDecisionInput(approve=True), self.supervisor)
        self.assertEqual(self.service.get_case(self.cid)["pending_approval"], before["pending_approval"])
        self.assertEqual(self.service.get_case(self.cid)["version"], before["version"])

    def test_l1_cannot_bypass_role_by_retrying_restriction(self):
        action = self.service.get_case(self.cid)["actions"][0]
        with self.assertRaises(OperationError) as caught:
            self.service.retry_action(action["action_id"], self.l1)
        self.assertEqual(caught.exception.status_code, 403)

    def test_report_can_be_recorded_after_resolution(self):
        self.service.process_jobs()
        case = self.service.get_case(self.cid)
        case = self.service.decide(
            self.cid,
            DecisionInput(action="confirm_fraud", expected_version=case["version"], notes="Verified fraud"),
            self.l2,
        )
        self.assertEqual(case["status"], "resolved")
        case = self.service.decide(
            self.cid,
            DecisionInput(action="file_ncrp_report", expected_version=case["version"]),
            self.supervisor,
        )
        self.assertEqual(case["status"], "resolved")
        self.assertEqual(case["ncrp_report"]["status"], "recorded_in_simulation")
