import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from fraudlens.api.routes.operations import router
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
        state.operations = OperationsService(Path(self.tmp.name) / "ops.db", bank_client=bank)
        app = FastAPI()
        app.include_router(router)
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
        self.assertTrue(any(e["actor"] == "A. Sharma" for e in self.client.get(f"/ops/cases/{case['case_id']}", headers=self.headers).json()["timeline"]))

    def test_duplicate_conflict_and_paging(self):
        txn = dict(txn_id="API-1", account_id="SIM-API", channel="upi", amount_minor=25000,
                   timestamp=datetime.now(timezone.utc).isoformat())
        self.assertEqual(self.client.post("/ops/transactions", json=txn, headers=self.headers).status_code, 201)
        self.assertEqual(self.client.post("/ops/transactions", json=txn, headers=self.headers).status_code, 200)
        self.assertEqual(self.client.post("/ops/transactions", json={**txn, "amount_minor": 26000}, headers=self.headers).status_code, 409)
        self.assertEqual(self.client.get("/ops/transactions?limit=1&offset=0", headers=self.headers).json()["total"], 1)
        self.assertEqual(self.client.get("/ops/transactions?limit=99999", headers=self.headers).status_code, 422)
        self.assertEqual(self.client.get("/ops/cases/missing", headers=self.headers).status_code, 404)


if __name__ == "__main__":
    unittest.main()
