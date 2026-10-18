"""Public demo attacks expose their own progress, never the private ledger."""
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from fraudlens.api.state import state
from fraudlens.api.routes.public import mount_public_routes
from fraudlens.bank_simulator.main import create_app
from fraudlens.operations.attacks import PublicAttacks
from fraudlens.operations.service import OperationsService


class AttackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.bank = TestClient(create_app(Path(self.tmp.name) / "bank.sqlite", api_key="test"), headers={"X-Bank-Key": "test"})
        self.addCleanup(self.bank.close)
        self.service = OperationsService(Path(self.tmp.name) / "ops.sqlite", bank_client=self.bank)
        self.clock = 1000.0
        self.attacks = PublicAttacks(self.service, clock=lambda: self.clock)
        old = getattr(state, "attacks", None)
        state.attacks = self.attacks
        self.addCleanup(setattr, state, "attacks", old)
        app = FastAPI()
        mount_public_routes(app, mode="demo")
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def launch(self, typology="mule_layering", **changes):
        return self.client.post("/public/attacks", json={"typology": typology, **changes})

    def test_each_typology_flags_from_real_ledger(self):
        labels = ["Scam payment sent", "FraudLens flagged it", "Bank protection requested", "Bank confirmed protection", "Analyst picked it up", "Verdict recorded"]
        for typology in ("mule_layering", "sim_swap_takeover", "card_testing", "atm_cashout"):
            with self.subTest(typology=typology):
                launch = self.launch(typology)
                self.assertEqual(launch.status_code, 200, launch.text)
                self.assertRegex(launch.json()["attack_id"], r"^ATK-[a-f0-9]{12}$")
                self.service.process_jobs()
                status = self.client.get(launch.json()["status_url"]).json()
                self.assertEqual([s["label"] for s in status["steps"]], labels)
                self.assertEqual(status["steps"][1]["status"], "done")
                self.assertEqual(status["steps"][3]["status"], "done")
                self.assertEqual(status["steps"][5]["status"], "pending")

    def test_eleventh_post_rate_limited_and_window_expires(self):
        for _ in range(10):
            self.assertEqual(self.launch("sim_swap_takeover").status_code, 200)
        response = self.launch("sim_swap_takeover")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["detail"], "Too many simulated attacks. Try again in a few minutes.")
        self.clock += 301
        self.assertEqual(self.launch("sim_swap_takeover").status_code, 200)

    def test_non_demo_has_no_public_routes(self):
        app = FastAPI()
        mount_public_routes(app, mode="production")
        with TestClient(app) as client:
            self.assertEqual(client.post("/public/attacks", json={"typology": "atm_cashout"}).status_code, 404)
            self.assertEqual(client.get("/public/attacks/ATK-123456789abc").status_code, 404)
            self.assertFalse(any(route.startswith("/public/") for route in client.get("/openapi.json").json()["paths"]))

    def test_public_status_and_report_do_not_leak_private_fields(self):
        launch = self.launch().json()
        report = self.client.post(launch["status_url"] + "/report-1930")
        self.assertEqual(report.status_code, 200, report.text)
        self.service.process_jobs()
        status = self.client.get(launch["status_url"]).json()
        def inspect(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    self.assertNotIn(key, {"display_name", "balance_minor", "available_minor", "case_id", "account_id", "username"})
                    inspect(item)
            elif isinstance(value, list):
                for item in value:
                    inspect(item)
            elif isinstance(value, str):
                for case in self.service.snapshot()["cases"]:
                    self.assertNotIn(case["case_id"], value)
        inspect(status)
        inspect(report.json())

    def test_1930_report_is_idempotent_and_recovers_remaining_funds(self):
        launch = self.launch().json()
        first = self.client.post(launch["status_url"] + "/report-1930")
        self.assertEqual(first.status_code, 200, first.text)
        self.service.process_jobs()
        again = self.client.post(launch["status_url"] + "/report-1930").json()
        self.assertRegex(again["complaint_id"], r"^NCRP-[0-9]{14}$")
        self.assertEqual(first.json()["complaint_id"], again["complaint_id"])
        self.assertEqual(again["held_total_minor"], 2800000)
        self.assertEqual(self.service.snapshot()["counts"]["complaints"], 1)

    def test_mule_amount_scales_legs_without_creating_money(self):
        launch = self.launch(victim_amount_minor=100000).json()
        self.assertIn("attack_id", launch)
        self.client.post(launch["status_url"] + "/report-1930")
        self.service.process_jobs()
        status = self.client.get(launch["status_url"]).json()
        self.assertLessEqual(status["held_total_minor"], 100000)
        self.assertEqual(self.service.snapshot()["counts"]["posted"], 3)

    def test_input_rejects_lossy_money_and_unknown_typology(self):
        for amount in (True, 1.5, 99999, 20000001, "100000"):
            self.assertEqual(self.launch(victim_amount_minor=amount).status_code, 422)
        self.assertEqual(self.launch("unknown").status_code, 422)

    def test_report_on_other_typology_and_unknown_attack_are_rejected(self):
        launch = self.launch("atm_cashout").json()
        self.assertEqual(self.client.post(launch["status_url"] + "/report-1930").status_code, 400)
        self.assertEqual(self.client.get("/public/attacks/ATK-000000000000").status_code, 404)

    def test_human_claim_and_verdict_update_public_progress(self):
        from fraudlens.models.schemas import AnalystProfile
        from fraudlens.operations.models import ClaimInput, DecisionInput
        launch = self.launch("sim_swap_takeover").json()
        before = self.client.get(launch["status_url"]).json()
        self.assertEqual(before["outcome"], "in_progress")
        case = self.service.snapshot()["cases"][0]
        l1 = AnalystProfile(username="kmehta", display_name="K. Mehta", role="l1_analyst")
        case = self.service.claim(case["case_id"], ClaimInput(expected_version=case["version"]), l1)
        picked = self.client.get(launch["status_url"]).json()
        self.assertEqual(picked["steps"][4]["status"], "done")
        self.assertEqual(picked["steps"][5]["status"], "pending")
        self.service.decide(case["case_id"], DecisionInput(action="confirm_fraud", expected_version=case["version"], notes="Verified attack"),
                            AnalystProfile(username="riyer", display_name="R. Iyer", role="l2_analyst"))
        final = self.client.get(launch["status_url"]).json()
        self.assertEqual(final["steps"][5]["status"], "done")
        self.assertEqual(final["outcome"], "caught")
        self.assertIsNotNone(final["steps"][5]["at"])

    def test_attack_and_report_survive_service_restart(self):
        launch = self.launch().json()
        first = self.client.post(launch["status_url"] + "/report-1930").json()
        self.service.process_jobs()
        restarted = OperationsService(self.service.store.path, bank_client=self.bank)
        state.attacks = PublicAttacks(restarted)
        status = self.client.get(launch["status_url"]).json()
        self.assertEqual(status["held_total_minor"], 2800000)
        again = self.client.post(launch["status_url"] + "/report-1930").json()
        self.assertEqual(again["complaint_id"], first["complaint_id"])
        self.assertEqual(restarted.snapshot()["counts"]["complaints"], 1)
