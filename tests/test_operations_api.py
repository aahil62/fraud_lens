import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from fraudlens.api.routes.operations import router
from fraudlens.api.routes.auth import router as auth_router
from fraudlens.api.state import state
from fraudlens.bank_simulator.main import create_app
from fraudlens.core.auth.security import create_access_token
from fraudlens.core.auth.store import AnalystStore
from fraudlens.operations.service import OperationsService


class OperationsApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.old_runtime = state.runtime
        self.old_operations = getattr(state, "operations", None)
        state.runtime = SimpleNamespace(analyst_store=AnalystStore(str(Path(self.tmp.name) / "analysts.json")))
        bank = TestClient(create_app(db_path=Path(self.tmp.name) / "bank.db", api_key="test"), headers={"X-Bank-Key": "test"})
        self.addCleanup(bank.close)
        state.operations = OperationsService(Path(self.tmp.name) / "ops.db", bank_client=bank, analysts=state.runtime.analyst_store)
        app = FastAPI()
        app.include_router(router)
        app.include_router(auth_router)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.headers = {"Authorization": f"Bearer {create_access_token('asharma')}"}
        self.addCleanup(self.restore_state)

    def restore_state(self):
        state.runtime = self.old_runtime
        state.operations = self.old_operations

    def test_authentication_required_for_reads_writes_and_stream(self):
        for path in ("/ops/snapshot", "/ops/events", "/ops/guidance", "/ops/cases", "/ops/transactions"):
            self.assertEqual(self.client.get(path).status_code, 401, path)
        self.assertEqual(self.client.post("/ops/simulation/scenario", json={"channel": "upi", "scenario": "fraud"}).status_code, 401)

    def test_scenario_decision_report_and_all_channel_counts(self):
        for channel in ("upi", "net_banking", "card", "atm"):
            result = self.client.post("/ops/simulation/scenario", headers=self.headers, json={"channel": channel, "scenario": "fraud"})
            self.assertEqual(result.status_code, 200, result.text)
            self.assertTrue(result.json()["case_ids"])
        snap = self.client.get("/ops/snapshot", headers=self.headers).json()
        self.assertEqual(snap["counts"]["cases"], sum(c["cases"] for c in snap["channels"]))
        case = snap["cases"][0]
        decision = self.client.post(f"/ops/cases/{case['case_id']}/decision", headers=self.headers,
                                   json={"action": "false_positive", "expected_version": case["version"], "notes": "Verified with test customer"})
        self.assertEqual(decision.status_code, 200, decision.text)
        self.client.post("/ops/process", headers=self.headers)
        for fmt in ("json", "markdown", "pdf"):
            report = self.client.get(f"/ops/cases/{case['case_id']}/report?format={fmt}", headers=self.headers)
            self.assertEqual(report.status_code, 200, report.text[:100] if fmt != "pdf" else "PDF error")
            if fmt == "pdf":
                self.assertTrue(report.content.startswith(b"%PDF"))
            elif fmt == "json":
                self.assertEqual(report.json()["case"]["verdict"], "false_positive")
        timeline = self.client.get(f"/ops/cases/{case['case_id']}", headers=self.headers).json()["timeline"]
        self.assertTrue(any(e["actor"] == "asharma" and "A. Sharma" in e["message"] for e in timeline))

    def test_duplicate_conflict_and_paging(self):
        txn = dict(txn_id="API-1", account_id="SIM-API", channel="upi", amount_minor=25000,
                   timestamp=datetime.now(timezone.utc).isoformat())
        self.assertEqual(self.client.post("/ops/transactions", json=txn, headers=self.headers).status_code, 201)
        self.assertEqual(self.client.post("/ops/transactions", json=txn, headers=self.headers).status_code, 200)
        self.assertEqual(self.client.post("/ops/transactions", json={**txn, "amount_minor": 26000}, headers=self.headers).status_code, 409)
        self.assertEqual(self.client.get("/ops/transactions?limit=1&offset=0", headers=self.headers).json()["total"], 1)
        self.assertEqual(self.client.get("/ops/transactions?limit=99999", headers=self.headers).status_code, 422)
        self.assertEqual(self.client.get("/ops/cases/missing", headers=self.headers).status_code, 404)

    def test_claim_approval_presence_and_session_routes_share_snapshot(self):
        login = self.client.post("/auth/login", json={"username": "kmehta", "password": "fraudlens123"})
        l1 = {"Authorization": f"Bearer {login.json()['access_token']}"}
        l2 = {"Authorization": f"Bearer {create_access_token('riyer')}"}
        case_id = self.client.post("/ops/simulation/scenario", headers=self.headers,
                                  json={"channel": "upi", "scenario": "fraud"}).json()["case_ids"][-1]
        case = self.client.get(f"/ops/cases/{case_id}", headers=l1).json()
        claim = self.client.post(f"/ops/cases/{case_id}/claim", headers=l1, json={"expected_version": case["version"]})
        self.assertEqual(claim.status_code, 200, claim.text)
        self.assertEqual(claim.json()["assignee"], "kmehta")
        approval = self.client.post(f"/ops/cases/{case_id}/approval-request", headers=l1,
                                   json={"action": "confirm_fraud", "expected_version": claim.json()["version"], "notes": "Verified evidence"})
        self.assertEqual(approval.status_code, 200, approval.text)
        pending = self.client.get("/ops/snapshot", headers=l2).json()["approvals"]
        self.assertEqual(pending[0]["case_id"], case_id)
        result = self.client.post(f"/ops/cases/{case_id}/approval", headers=l2, json={"approve": True})
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["verdict"], "fraud")
        self.assertEqual(self.client.post("/ops/presence/heartbeat", headers=l1, json={"current_case_id": case_id}).status_code, 200)
        self.assertEqual(self.client.post("/auth/logout", headers=l1).status_code, 200)
        snap = self.client.get("/ops/snapshot", headers=l2).json()
        self.assertFalse(next(m for m in snap["team"] if m["username"] == "kmehta")["online"])
        self.assertTrue(any(e["event_type"] == "analyst_signed_in" and e["actor"] == "kmehta" for e in snap["events"]))
        self.assertTrue(any(e["event_type"] == "analyst_signed_out" and e["actor"] == "kmehta" for e in snap["events"]))
        self.assertEqual(self.client.post("/auth/logout").status_code, 401)


if __name__ == "__main__":
    unittest.main()

    def test_agent_brief_and_settings_routes(self):
        self.assertEqual(self.client.get("/ops/cases/missing/brief").status_code, 401)
        self.assertEqual(self.client.post("/ops/agent/settings", json={"auto_assign": True}).status_code, 401)
        self.client.post("/ops/simulation/scenario", headers=self.headers, json={"channel": "upi", "scenario": "fraud"})
        case = self.client.get("/ops/snapshot", headers=self.headers).json()["cases"][0]
        brief = self.client.get(f"/ops/cases/{case['case_id']}/brief", headers=self.headers)
        self.assertEqual(brief.status_code, 200, brief.text)
        self.assertEqual(brief.json()["generated_by"], "template")
        self.assertEqual(self.client.get("/ops/cases/missing/brief", headers=self.headers).status_code, 404)
        login = self.client.post("/auth/login", json={"username": "kmehta", "password": "fraudlens123"})
        l1 = {"Authorization": f"Bearer {login.json()['access_token']}"}
        denied = self.client.post("/ops/agent/settings", headers=l1, json={"auto_assign": True})
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.json()["required_role"], "supervisor")
        enabled = self.client.post("/ops/agent/settings", headers=self.headers, json={"auto_assign": True})
        self.assertEqual(enabled.json(), {"auto_assign": True})
        self.assertTrue(self.client.get("/ops/snapshot", headers=self.headers).json()["agent"]["auto_assign"])
