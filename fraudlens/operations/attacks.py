"""Public demo orchestration with a deliberately small, redacted read model."""

import time
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from fraudlens.core.rate_limit import SlidingWindowLimiter
from fraudlens.models.schemas import AnalystProfile

from .errors import NotFoundError, OperationError
from .models import ComplaintInput
from .snapshot import AUTOMATED_ACTORS
from .store import dump, now


class AttackInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    typology: Literal["mule_layering", "sim_swap_takeover", "card_testing", "atm_cashout"]
    victim_amount_minor: Annotated[StrictInt, Field(ge=100000, le=20000000)] = 4800000


class PublicAttacks:
    def __init__(self, service, *, clock=None):
        self.service = service
        # Ten simulated attacks per visitor every five minutes.
        self.limiter = SlidingWindowLimiter(10, 300, clock or time.monotonic)

    def limit(self, client_ip):
        if not self.limiter.allow(client_ip):
            raise OperationError("Too many simulated attacks. Try again in a few minutes.", status_code=429)

    def _get(self, db, attack_id):
        attack = self.service.store.get(db, "attacks", attack_id)
        if not attack:
            raise NotFoundError("Simulated attack not found")
        return attack

    def launch(self, request):
        result = self.service.run_scenario(
            "upi", request.typology, "attack-simulator", victim_amount_minor=request.victim_amount_minor
        )
        attack_id = f"ATK-{uuid4().hex[:12]}"
        attack = dict(
            attack_id=attack_id,
            typology=request.typology,
            created_at=now(),
            txn_ids=[t["txn_id"] for t in result["transactions"]],
            case_ids=result["case_ids"],
            report_input=None,
            complaint_case_id=None,
        )
        with self.service.store.connect(write=True) as db:
            db.execute("INSERT INTO attacks VALUES(?,?)", (attack_id, dump(attack)))
            self.service.store.event(
                db,
                "public_attack_launched",
                "A fictional public attack reached the operational ledger.",
                actor="attack-simulator",
                metadata={"attack_id": attack_id, "typology": request.typology},
            )
        return {"attack_id": attack_id, "status_url": f"/public/attacks/{attack_id}"}

    def status(self, attack_id):
        with self.service.store.connect() as db:
            attack = self._get(db, attack_id)
            transactions = [
                self.service.store.get(db, "transactions", identifier) for identifier in attack["txn_ids"]
            ]
            cases = [self.service._case(db, identifier) for identifier in attack["case_ids"]]
            primary_id = attack["complaint_case_id"] or next(iter(reversed(attack["case_ids"])), None)
            primary = self.service._case(db, primary_id) if primary_id else None
            if attack["complaint_case_id"]:
                cases.append(primary)
            actions = [a for case in cases for a in case["actions"]]
            protection = [a for a in actions if a["operation"] in {"restrict", "lien", "close"}]
            confirmed = [a for a in protection if a["status"] == "confirmed"]
            human = [
                e for e in (primary["timeline"] if primary else []) if e["actor"] not in AUTOMATED_ACTORS
            ]
            picked = next((e for e in human if e["event_type"] in {"case_claimed", "analyst_decision"}), None)
            verdict = next(
                (
                    e
                    for e in reversed(human)
                    if e["event_type"] == "analyst_decision"
                    and e["metadata"].get("action") in {"confirm_fraud", "false_positive"}
                ),
                None,
            )

            def step(label, done, at=None, blocked=False):
                return {
                    "label": label,
                    "status": "blocked" if blocked else "done" if done else "pending",
                    "at": at,
                }

            first = transactions[0]
            steps = [
                step(
                    "Scam payment sent",
                    first["payment_status"] == "posted",
                    first["timestamp"],
                    first["payment_status"] == "declined",
                ),
                step(
                    "FraudLens flagged it",
                    bool(attack["case_ids"]),
                    cases[0]["created_at"] if attack["case_ids"] else None,
                ),
                step(
                    "Bank protection requested",
                    bool(protection),
                    min((a["created_at"] for a in protection), default=None),
                ),
                step(
                    "Bank confirmed protection",
                    bool(confirmed),
                    min((a["updated_at"] for a in confirmed), default=None),
                ),
                step("Analyst picked it up", bool(picked), picked["occurred_at"] if picked else None),
                step("Verdict recorded", bool(verdict), verdict["occurred_at"] if verdict else None),
            ]
            moved = sum(
                t["amount_minor"]
                for t in transactions
                if t["payment_status"] == "posted"
                and (attack["typology"] != "mule_layering" or t["channel"] == "atm")
            )
            outcome = "in_progress"
            if verdict and confirmed and primary["verdict"] == "fraud":
                outcome = "partially_caught" if moved else "caught"
            elif verdict and primary["verdict"] == "false_positive":
                outcome = "missed"
            elif not cases and all(t["payment_status"] != "pending" for t in transactions):
                outcome = "missed"
            trace = primary.get("trace", []) if primary else []
            return dict(
                attack_id=attack_id,
                typology=attack["typology"],
                steps=steps,
                outcome=outcome,
                case_id_masked=f"…{primary_id[-4:]}" if primary_id else None,
                complaint_id=attack["report_input"]["complaint_id"] if attack["report_input"] else None,
                traced_total_minor=primary.get("traced_total_minor", 0) if primary else 0,
                held_total_minor=primary.get("held_total_minor", 0) if primary else 0,
                funds_moved_total_minor=moved,
                trace=[
                    {
                        "hop": h["hop"],
                        "account_ref": f"…{h['account_id'][-4:]}",
                        "traced_minor": h["traced_minor"],
                        "lien_minor": h["lien_minor"],
                        "outcome": h["outcome"],
                    }
                    for h in trace
                ],
            )

    def report_1930(self, attack_id):
        with self.service._lock:
            with self.service.store.connect(write=True) as db:
                attack = self._get(db, attack_id)
                if attack["typology"] != "mule_layering":
                    raise OperationError("1930 fund tracing is available for the mule-layering simulation")
                if attack["report_input"] is None:
                    root = self.service.store.get(db, "transactions", attack["txn_ids"][0])
                    sequence = max(
                        time.time_ns() // 1000 % 100000000000000,
                        self.service.store.setting(db, "complaint_sequence", 0) + 1,
                    )
                    self.service.store.set_setting(db, "complaint_sequence", sequence)
                    attack["report_input"] = dict(
                        complaint_id=f"NCRP-{sequence:014d}",
                        source="1930_helpline",
                        victim_account_id=root["account_id"],
                        reported_txn_id=root["txn_id"],
                        reported_at=now(),
                    )
                    self.service.store.update(db, "attacks", attack_id, attack)
                    self.service.store.event(
                        db,
                        "public_complaint_requested",
                        "A simulated 1930 report was requested.",
                        actor="attack-simulator",
                        metadata={"attack_id": attack_id},
                    )
            actor = AnalystProfile(
                username="attack-simulator", display_name="Simulated 1930 report", role="l1_analyst"
            )
            case = self.service.file_complaint(ComplaintInput(**attack["report_input"]), actor)
            if attack["complaint_case_id"] != case["case_id"]:
                with self.service.store.connect(write=True) as db:
                    attack["complaint_case_id"] = case["case_id"]
                    self.service.store.update(db, "attacks", attack_id, attack)
                    self.service.store.event(
                        db,
                        "public_complaint_linked",
                        "Simulated report linked to its investigation.",
                        case_id=case["case_id"],
                        actor="attack-simulator",
                        metadata={"attack_id": attack_id},
                    )
            return self.status(attack_id)
