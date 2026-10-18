"""New typologies must be explained by telemetry, not scenario labels."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from fraudlens.bank_simulator.main import create_app
from fraudlens.operations.detector import detect
from fraudlens.operations.models import ScenarioInput
from fraudlens.operations.scenarios import scenario_transactions
from fraudlens.operations.service import OperationsService


class DetectorTypologyTests(unittest.TestCase):
    def score(self, rows, index=-1):
        if index < 0:
            index += len(rows)
        payloads = [{**row.model_dump(mode="json"), "payment_status": "posted"} for row in rows]
        return detect(payloads[index], payloads[:index])

    def assert_detected(self, typology, phrase, *, index=-1):
        ScenarioInput(channel="upi", scenario=typology)
        rows = scenario_transactions("upi", typology)
        result = self.score(rows, index)
        self.assertGreaterEqual(result["score"], .8, result)
        self.assertIn(phrase.lower(), " ".join(result["reasons"]).lower())
        return rows

    def test_mule_layering_pass_through_and_known_beneficiary_control(self):
        # M1's second outgoing transfer completes the pass-through pattern;
        # the final M2 ATM leg is a later cash-out, not an 80% pass-through.
        rows = self.assert_detected("mule_layering", "Pass-through", index=2)
        self.assertEqual([r.channel for r in rows], ["upi", "net_banking", "upi", "atm"])
        self.assertEqual([r.amount_minor for r in rows], [4800000, 3000000, 1500000, 2000000])
        rows[2] = rows[2].model_copy(update={"new_beneficiary": False})
        self.assertLess(self.score(rows, 2)["score"], .5)

    def test_sim_swap_takeover_and_known_device_control(self):
        rows = self.assert_detected("sim_swap_takeover", "SIM-swap")
        self.assertEqual(rows[-1].channel, "net_banking")
        self.assertEqual(rows[-1].amount_minor, 18500000)
        rows[-1] = rows[-1].model_copy(update={"new_device": False, "new_beneficiary": False, "failed_auth_attempts": 0})
        self.assertLess(self.score(rows)["score"], .5)

    def test_card_testing_and_single_small_payment_control(self):
        rows = self.assert_detected("card_testing", "Card testing")
        self.assertTrue(all(r.channel == "card" for r in rows))
        self.assertEqual(len(rows), 7)
        self.assertEqual(rows[-1].amount_minor, 1850000)
        self.assertEqual(len({r.merchant_id for r in rows[:6]}), 6)
        self.assertLess(self.score(rows[:1])["score"], .5)

    def test_atm_cashout_across_terminals_and_single_withdrawal_control(self):
        rows = self.assert_detected("atm_cashout", "ATM burst across terminals")
        self.assertTrue(all(r.channel == "atm" for r in rows))
        self.assertEqual(len(rows), 4)
        self.assertEqual(len({r.device_id for r in rows}), 3)
        self.assertTrue(all(r.amount_minor == 1000000 for r in rows))
        self.assertLess(self.score(rows[:1])["score"], .5)

    def test_new_typologies_run_through_real_bank_balances(self):
        with tempfile.TemporaryDirectory() as folder:
            bank = TestClient(create_app(Path(folder) / "bank.sqlite", api_key="test"), headers={"X-Bank-Key": "test"})
            self.addCleanup(bank.close)
            service = OperationsService(Path(folder) / "ops.sqlite", bank_client=bank)
            result = service.run_scenario("upi", "mule_layering")
            rows = result["transactions"]
            root, outgoing, blocked, cash = rows
            self.assertEqual([t["payment_status"] for t in rows], ["posted", "posted", "declined", "posted"])
            accounts = {a["account_id"]: a for a in service.snapshot()["bank"]["accounts"]}
            self.assertEqual(accounts[root["beneficiary_id"]]["balance_minor"], 1800000)
            self.assertEqual(accounts[outgoing["beneficiary_id"]]["balance_minor"], 1000000)
            self.assertEqual(accounts[blocked["beneficiary_id"]]["balance_minor"], 0)
            self.assertTrue(result["case_ids"])
            self.assertIsNone(cash["beneficiary_id"])

    def test_demo_account_seed_is_idempotent_and_authenticated(self):
        with tempfile.TemporaryDirectory() as folder:
            with TestClient(create_app(Path(folder) / "bank.sqlite", api_key="test"), headers={"X-Bank-Key": "test"}) as bank:
                payload = {"accounts": [{"account_id": "SIM-SEED", "balance_minor": 500000}]}
                self.assertEqual(bank.post("/bank/accounts/seed", json=payload, headers={"X-Bank-Key": "wrong"}).status_code, 401)
                self.assertEqual(bank.post("/bank/accounts/seed", json=payload).status_code, 200)
                bank.post("/bank/transactions", json=dict(txn_id="DEBIT", account_id="SIM-SEED", amount_minor=100000, channel="upi"))
                self.assertEqual(bank.post("/bank/accounts/seed", json=payload).status_code, 200)
                self.assertEqual(bank.get("/bank/accounts").json()["accounts"][0]["balance_minor"], 400000)

    def test_account_seeding_disabled_outside_demo(self):
        with tempfile.TemporaryDirectory() as folder:
            with TestClient(create_app(Path(folder) / "bank.sqlite", api_key="test"), headers={"X-Bank-Key": "test"}) as bank:
                with patch.dict("os.environ", {"FRAUDLENS_MODE": "production"}):
                    response = bank.post("/bank/accounts/seed", json={"accounts": [{"account_id": "SIM-SEED", "balance_minor": 1}]})
                self.assertEqual(response.status_code, 404)
                self.assertEqual(bank.get("/bank/accounts").json()["accounts"], [])
