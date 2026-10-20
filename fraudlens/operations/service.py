"""The operations service: one durable ledger shared by every analyst console.

Bank effects happen only after the local commit. Each concern lives in its own
module and is mixed into OperationsService, so routes and tests keep one object:

- ingest.py      payment attempts and the cases detection opens
- decisions.py   analyst decisions and the bank actions they request
- approvals.py   claiming, assigning and the L1 → L2 → Supervisor approvals
- complaints.py  1930 complaints, fund traces and golden-hour liens
- delivery.py    the job worker, bank delivery and reconciliation
- snapshot.py    case views, the console snapshot and listings
- simulation.py  the synthetic stream and scenarios

This module adds the agent triage loop and analyst presence.
"""

import threading
from datetime import datetime, timedelta, timezone

import httpx

from fraudlens.models.schemas import AnalystProfile

from .agent import auto_assign, build_brief, polish_summary, priority
from .approvals import ApprovalsMixin
from .complaints import ComplaintsMixin
from .decisions import DecisionsMixin
from .delivery import DeliveryMixin
from .errors import ConflictError, NotFoundError, OperationError
from .ingest import IngestMixin
from .simulation import SimulationMixin
from .snapshot import SnapshotMixin
from .store import Store
from .team import ONLINE_SECONDS, require, team_snapshot
from .trace import trace_view

__all__ = ["ConflictError", "NotFoundError", "OperationError", "OperationsService"]

AGENT = AnalystProfile(username="agent", display_name="FraudLens Agent", role="l1_analyst")


class OperationsService(
    IngestMixin,
    DecisionsMixin,
    ApprovalsMixin,
    ComplaintsMixin,
    DeliveryMixin,
    SnapshotMixin,
    SimulationMixin,
):
    def __init__(
        self,
        db_path,
        bank_client=None,
        *,
        bank_url="http://127.0.0.1:8002",
        bank_key="fraudlens-local-simulator",
        analysts=None,
        clock=None,
    ):
        self.store = Store(db_path)
        self.analysts = analysts
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.bank = bank_client or httpx.Client(
            base_url=bank_url, headers={"X-Bank-Key": bank_key}, timeout=2, trust_env=False
        )
        self._owns_client = bank_client is None
        self._lock = threading.RLock()
        self._bank_state = dict(
            connected=False, mode="unknown", accounts=[], last_error="Waiting for bank connection"
        )
        self._run_agent()

    def close(self):
        if self._owns_client:
            self.bank.close()

    def _save_case(self, db, case):
        score, reason = priority(case, self.clock())
        case.update(priority=score, priority_reason=reason)
        if case.get("brief_version") != case["version"]:
            actions = self.store.case_actions(db, case["case_id"])
            view = {**case}
            if case.get("case_type") == "complaint":
                view["trace"] = trace_view(case, actions)
                view["traced_total_minor"] = sum(h["traced_minor"] for h in view["trace"])
                view["held_total_minor"] = sum(h["lien_minor"] for h in view["trace"])
            case["brief"] = build_brief(view, self.store.records(db, "transactions"), actions)
            case["brief_version"] = case["version"]
            if not case.get("agent_triaged"):
                self.store.event(
                    db,
                    "agent_triaged",
                    "FraudLens Agent prioritised the case; no verdict recorded.",
                    case_id=case["case_id"],
                    actor="agent",
                    metadata={"priority": score, "reason": reason},
                )
                case["agent_triaged"] = True
            self.store.event(
                db,
                "agent_brief_drafted",
                "FraudLens Agent refreshed its factual case brief.",
                case_id=case["case_id"],
                actor="agent",
            )
        self.store.update(db, "cases", case["case_id"], case)

    def _run_agent(self):
        with self.store.connect(write=True) as db:
            cases = self.store.records(db, "cases")
            for case in cases:
                if case.get("brief_version") != case["version"]:
                    self._save_case(db, case)
            if self.store.setting(db, "agent_auto_assign", False):
                team = team_snapshot(db, cases, self.analysts, self.clock())
                pending = [{**case, "priority": priority(case, self.clock())[0]} for case in cases]
                members = {m["username"]: m for m in team}
                for case_id, username in auto_assign(pending, team):
                    case = self.store.get(db, "cases", case_id)
                    member = members[username]
                    target = AnalystProfile(
                        username=username, display_name=member["display_name"], role=member["role"]
                    )
                    self._assign_case(db, case, target, AGENT, "case_auto_assigned")

    def set_agent_settings(self, enabled, actor):
        require(actor, "agent_settings")
        with self._lock, self.store.connect(write=True) as db:
            self.store.set_setting(db, "agent_auto_assign", enabled)
            self.store.event(
                db,
                "agent_policy_updated",
                f"{actor.display_name} {'enabled' if enabled else 'disabled'} online-L1 auto-assignment.",
                actor=actor.username,
            )
        return {"auto_assign": enabled}

    def get_brief(self, case_id):
        with self._lock:
            self._run_agent()
            case = self.get_case(case_id)
        brief = case["brief"]
        # Optional wording happens outside the ledger transaction and case lock.
        summary = polish_summary(
            brief["summary"], {"amount_minor": case["amount_minor"], "verdict": case["verdict"]}
        )
        if summary != brief["summary"]:
            with self._lock, self.store.connect(write=True) as db:
                current = self.store.get(db, "cases", case_id)
                if current["version"] == case["version"]:
                    current["brief"] = {**brief, "summary": summary, "generated_by": "llm"}
                    self.store.update(db, "cases", case_id, current)
                    self.store.event(
                        db,
                        "agent_summary_polished",
                        "Optional local wording applied; recommendation and case facts unchanged.",
                        case_id=case_id,
                        actor="agent",
                    )
                    return current["brief"]
            return self.get_case(case_id)["brief"]
        return brief

    def heartbeat(self, actor, current_case_id=None):
        with self._lock, self.store.connect(write=True) as db:
            # Presence has its own table; an audit event here would move the cursor every 15 s
            # and make every open console reload its snapshot.
            if current_case_id and not self.store.get(db, "cases", current_case_id):
                raise NotFoundError("Case not found")
            self._presence(db, actor, current_case_id)

    def _presence(self, db, actor, current_case_id=None, signed_out=False):
        offline = timedelta(seconds=ONLINE_SECONDS + 1)
        seen = (self.clock() - offline if signed_out else self.clock()).isoformat()
        db.execute(
            """INSERT INTO presence VALUES(?,?,?,?,?) ON CONFLICT(username) DO UPDATE SET
                   display_name=excluded.display_name,role=excluded.role,last_seen=excluded.last_seen,
                   current_case_id=excluded.current_case_id""",
            (actor.username, actor.display_name, actor.role, seen, current_case_id),
        )

    def record_session(self, actor, signed_in):
        with self._lock, self.store.connect(write=True) as db:
            self._presence(db, actor, signed_out=not signed_in)
            self.store.event(
                db,
                "analyst_signed_in" if signed_in else "analyst_signed_out",
                f"{actor.display_name} signed {'in' if signed_in else 'out'}.",
                actor=actor.username,
            )
