"""The synthetic payment stream: simulation controls, scenarios and the first-boot baseline."""

from .detector import CHANNELS
from .models import TransactionInput
from .scenarios import TYPOLOGIES, scenario_transactions, typology_accounts
from .snapshot import DEFAULT_SIMULATION

# The mule-layering fixture moves ₹48,000 as 48 parts: 30 and 15 onward from the first
# mule, then 20 withdrawn at an ATM. A chosen victim amount keeps the same proportions.
MULE_PARTS = (48, 30, 15, 20)


def scale_mule_layering(rows, victim_amount_minor):
    amounts = [victim_amount_minor * part // MULE_PARTS[0] for part in MULE_PARTS]
    return [row.model_copy(update={"amount_minor": amount}) for row, amount in zip(rows, amounts)]


class SimulationMixin:
    """Simulation on OperationsService; uses its store, lock, bank client, ingest and process_jobs."""

    def control(self, request, actor):
        if request.bank_mode:
            response = self.bank.post("/bank/control", json={"mode": request.bank_mode})
            response.raise_for_status()
        with self._lock, self.store.connect(write=True) as db:
            config = self.store.setting(db, "simulation", DEFAULT_SIMULATION)
            if request.running is not None:
                config["running"] = request.running
            if request.interval_seconds is not None:
                config["interval_seconds"] = request.interval_seconds
            self.store.set_setting(db, "simulation", config)
            self.store.event(
                db,
                "simulation_control",
                "Simulation controls updated.",
                actor=actor,
                metadata=request.model_dump(exclude_none=True),
            )
        self._refresh_bank()
        return self.snapshot()

    def run_scenario(self, channel, scenario, actor="simulation", *, victim_amount_minor=None):
        rows = scenario_transactions(channel, scenario)
        if scenario == "mule_layering" and victim_amount_minor is not None:
            rows = scale_mule_layering(rows, victim_amount_minor)
        if scenario in TYPOLOGIES:
            response = self.bank.post("/bank/accounts/seed", json={"accounts": typology_accounts(rows)})
            response.raise_for_status()
            with self.store.connect(write=True) as db:
                self.store.event(
                    db,
                    "scenario_accounts_seeded",
                    "Fictional typology accounts provisioned before payment posting.",
                    actor=actor,
                )
        results = []
        for txn in rows:
            results.append(self.ingest(txn, actor))
            self.process_jobs()
        ids = [r["transaction"]["txn_id"] for r in results]
        with self.store.connect() as db:
            return {
                "transactions": [self.store.get(db, "transactions", identifier) for identifier in ids],
                "case_ids": [r["case"]["case_id"] for r in results if r["case"]],
            }

    def seed_baseline(self):
        with self.store.connect(write=True) as db:
            if self.store.setting(db, "seeded", False):
                return
            plan = self.store.setting(db, "baseline_plan")
            if plan is None:
                if db.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]:
                    self.store.set_setting(db, "seeded", True)
                    return
                plan = []
                for channel in CHANNELS:
                    for scenario in ("normal", "normal", "normal", "fraud"):
                        plan.extend(
                            t.model_dump(mode="json") for t in scenario_transactions(channel, scenario)
                        )
                self.store.set_setting(db, "baseline_plan", plan)
        # Stable ids and timestamps are persisted before the first ingest.
        # Restart resumes the same plan through ordinary idempotent delivery.
        for payload in plan:
            self.ingest(TransactionInput(**payload), "simulation")
            self.process_jobs()
        with self.store.connect(write=True) as db:
            self.store.set_setting(db, "seeded", True)
