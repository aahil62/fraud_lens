"""Durable operational lifecycle. Bank effects occur only after local commit."""
import hashlib
import json
import threading
import time
from uuid import uuid4
from datetime import datetime, timedelta, timezone

from fraudlens.core.auth.roles import can, required_role
from fraudlens.models.schemas import AnalystProfile

import httpx

from .detector import CHANNELS, COVERAGE, VERSION, detect
from .models import DecisionInput, TransactionInput
from .store import Store, dump, now
from .team import OperationError, require, team_snapshot
from .trace import trace_funds, trace_view


class ConflictError(OperationError):
    def __init__(self, detail, **fields):
        super().__init__(detail, status_code=409, **fields)


class NotFoundError(ValueError):
    pass


class OperationsService:
    def __init__(self, db_path, bank_client=None, *, bank_url="http://127.0.0.1:8002", bank_key="fraudlens-local-simulator", analysts=None, clock=None):
        self.store = Store(db_path)
        self.analysts = analysts
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.bank = bank_client or httpx.Client(base_url=bank_url, headers={"X-Bank-Key": bank_key}, timeout=2, trust_env=False)
        self._owns_client = bank_client is None
        self._lock = threading.RLock()
        self._bank_state = dict(connected=False, mode="unknown", accounts=[], last_error="Waiting for bank connection")

    def close(self):
        if self._owns_client:
            self.bank.close()

    def ingest(self, request: TransactionInput, actor="system"):
        payload = request.model_dump(mode="json")
        fingerprint = hashlib.sha256(dump(payload).encode()).hexdigest()
        with self._lock, self.store.connect(write=True) as db:
            old = db.execute("SELECT fingerprint,data FROM transactions WHERE id=?", (request.txn_id,)).fetchone()
            if old:
                if old[0] != fingerprint:
                    raise ConflictError("Transaction id already belongs to a different payload")
                txn = self.store.get(db, "transactions", request.txn_id)
                case = self._case(db, txn["case_id"]) if txn["case_id"] else None
                return {"transaction": txn, "case": case, "duplicate": True}
            result = detect(payload, self.store.records(db, "transactions"))
            case_id = f"CASE-{uuid4().hex[:12].upper()}" if result["score"] >= .5 else None
            txn = {**payload, "score": result["score"], "payment_status": "pending", "bank_reason": None, "case_id": case_id}
            db.execute("INSERT INTO transactions VALUES(?,?,?)", (request.txn_id, fingerprint, dump(txn)))
            self.store.event(db, "transaction_received", f"{request.channel} payment attempt received.", txn_id=request.txn_id, actor=actor)
            if case_id:
                case = dict(case_id=case_id, txn_id=request.txn_id, account_id=request.account_id, channel=request.channel,
                            amount_minor=request.amount_minor, score=result["score"], severity="critical" if result["score"] >= .9 else "high" if result["score"] >= .8 else "medium",
                            status="new", verdict="unreviewed", version=1, created_at=now(), updated_at=now(),
                            assigned_to=None, assignee=None, assigned_at=None, pending_approval=None, notes="", signals=result["signals"], reasons=result["reasons"],
                            related_accounts=result["related_accounts"], policy_version=VERSION)
                db.execute("INSERT INTO cases VALUES(?,?,?)", (case_id, request.txn_id, dump(case)))
                self.store.event(db, "case_opened", "Detection opened an investigation; analyst verdict pending.",
                                 case_id=case_id, txn_id=request.txn_id, metadata={"score": result["score"], "policy_version": VERSION})
                if result["score"] >= .8:
                    self._queue_action(db, case, "restrict")
            db.execute("INSERT INTO jobs(id,kind,resource_id) VALUES(?,?,?)", (f"payment-{request.txn_id}", "payment", request.txn_id))
            case = self._case(db, case_id) if case_id else None
            return {"transaction": txn, "case": case, "duplicate": False}

    def _protection_target(self, case, action, target=None):
        if action not in {"restrict", "place_lien", "release_lien", "close_account"}:
            return None
        if case.get("case_type") == "complaint":
            victim = case["complaint"]["victim_account_id"]
            if target == victim:
                raise OperationError("This is the complainant's account.")
            recipients = [h["account_id"] for h in case["trace"] if h["account_id"] != victim]
            target = target or next(iter(recipients), None)
            if not target or target not in recipients:
                raise OperationError("Select an account reached by this fund trace")
        elif target and target != case["account_id"]:
            raise OperationError("Account is not linked to this case")
        return target

    def _queue_action(self, db, case, operation, actor="system", *, amount_minor=None, target_id=None, target_type=None, reason=None):
        txn = self.store.get(db, "transactions", case["txn_id"])
        if case.get("case_type") == "complaint" and operation in {"restrict", "lien", "close"}:
            target_id = self._protection_target(case, {"restrict": "restrict", "lien": "place_lien", "close": "close_account"}[operation], target_id)
            target_type = "account"
        if target_type is None:
            target_type = "account" if operation in {"lien", "lien_release", "close"} or target_id else "card" if txn["channel"] in {"card", "atm"} else "account"
        if target_id is None:
            target_id = txn["instrument_id"] if target_type == "card" else txn["account_id"]
        action_id = f"ACT-{uuid4().hex}"
        action = dict(action_id=action_id, case_id=case["case_id"], operation=operation, target_type=target_type,
                      target_id=target_id, status="pending", attempts=0, bank_reference=None, last_error=None,
                      created_at=now(), updated_at=now())
        if operation == "lien":
            action["amount_minor"] = amount_minor
        db.execute("INSERT INTO actions VALUES(?,?,?)", (action_id, case["case_id"], dump(action)))
        db.execute("INSERT INTO jobs(id,kind,resource_id) VALUES(?,?,?)", (action_id, "action", action_id))
        message = f"{operation.capitalize()} requested for simulated {target_type} {target_id}."
        if reason:
            message = f"{reason}. {message}"
        self.store.event(db, f"{operation}_requested", message,
                         case_id=case["case_id"], txn_id=case["txn_id"], actor=actor,
                         metadata={"action_id": action_id, "target_account_id": target_id if target_type == "account" else None})
        return action

    def _case(self, db, case_id):
        case = self.store.get(db, "cases", case_id)
        if not case:
            raise NotFoundError("Case not found")
        actions = [a for a in self.store.records(db, "actions") if a["case_id"] == case_id]
        events = [{"id": r[0], **json.loads(r[1])} for r in db.execute(
            "SELECT id,data FROM events WHERE json_extract(data,'$.case_id')=? ORDER BY id", (case_id,))]
        txns = self.store.records(db, "transactions")
        case["related_transactions"] = [t for t in txns if t["account_id"] == case["account_id"] or
                                         t["account_id"] in case["related_accounts"]][:100]
        case.setdefault("assignee", None)
        case.setdefault("assigned_at", None)
        case.setdefault("pending_approval", None)
        case["handled_by"] = list(dict.fromkeys(e["actor"] for e in events if e["actor"] not in
                                  {"system", "agent", "simulation", "attack-simulator"}))
        case["actions"] = actions
        case["timeline"] = events
        if case.get("case_type") == "complaint":
            case["trace"] = trace_view(case, actions)
            bank_state = self.store.setting(db, "bank_state", self._bank_state)
            if bank_state["connected"]:
                available = {a["account_id"]: a["available_minor"] for a in bank_state["accounts"]}
                for hop in case["trace"]:
                    hop["available_minor"] = available.get(hop["account_id"], 0)
            case["default_target_account_id"] = next((h["account_id"] for h in case["trace"]
                                                     if h["account_id"] != case["complaint"]["victim_account_id"]), None)
            case["traced_total_minor"] = sum(h["traced_minor"] for h in case["trace"])
            case["held_total_minor"] = sum(h["lien_minor"] for h in case["trace"])
            case["funds_moved_total_minor"] = sum(h["moved_minor"] for h in case["trace"])
        return case

    def get_case(self, case_id):
        with self.store.connect() as db:
            return self._case(db, case_id)

    def _editable(self, db, case_id, expected_version):
        case = self.store.get(db, "cases", case_id)
        if not case:
            raise NotFoundError("Case not found")
        if case["version"] != expected_version:
            raise ConflictError("Case changed since you opened it. Refresh and review the latest version.",
                                version=case["version"], assignee=case.get("assignee"))
        return case

    def decide(self, case_id, request: DecisionInput, actor: AnalystProfile):
        with self._lock, self.store.connect(write=True) as db:
            existing = self.store.get(db, "cases", case_id)
            if existing and existing.get("case_type") == "complaint" and request.action in {"close_account", "restrict", "place_lien"}:
                if request.target_account_id == existing["complaint"]["victim_account_id"]:
                    raise OperationError("This is the complainant's account.")
            require(actor, request.action)
            case = self._editable(db, case_id, request.expected_version)
            return self._apply_decision(db, case, request, actor)

    def _apply_decision(self, db, case, request, actor):
        case_id = case["case_id"]
        target = self._protection_target(case, request.action, request.target_account_id)
        closes = [a for a in self.store.records(db, "actions") if a["case_id"] == case_id and
                  a["operation"] == "close" and a["status"] != "superseded"]
        if (request.action == "false_positive" and closes) or (request.action == "close_account" and
                any(a["target_id"] == (target or case["account_id"]) for a in closes)):
            raise ConflictError("Final account closure has already been requested; reconcile its bank result")
        if case["verdict"] == "false_positive" and request.action != "file_ncrp_report":
            raise ConflictError("A false-positive verdict is already recorded; its release must finish without a contradictory decision.")
        if case["status"] == "resolved" and request.action != "file_ncrp_report" and not (request.action in {"false_positive", "close_account"} and case["verdict"] == "fraud"):
            raise ConflictError("This case is resolved; its final verdict is already recorded.")
        case.update(version=case["version"] + 1, updated_at=now(), assigned_to=case.get("assigned_to") or actor.display_name, notes=request.notes)
        if request.action in {"investigate", "escalate"}:
            case["status"] = "investigating" if request.action == "investigate" else "escalated"
        elif request.action == "confirm_fraud":
            case.update(verdict="fraud", status="investigating")
            case_actions = [a for a in self.store.records(db, "actions") if a["case_id"] == case_id]
            default_target = self._protection_target(case, "restrict") if case.get("case_type") == "complaint" else None
            restrictions = [a for a in case_actions if a["operation"] == "restrict" and
                            (default_target is None or a["target_id"] == default_target)]
            if not restrictions:
                self._queue_action(db, case, "restrict", actor.username, target_id=default_target)
            elif any(a["status"] == "confirmed" for a in restrictions) and not any(
                    a["status"] in {"pending", "failed"} for a in case_actions):
                case["status"] = "resolved"
        elif request.action == "false_positive":
            case.update(verdict="false_positive", status="investigating")
            protections = [a for a in self.store.records(db, "actions") if a["case_id"] == case_id
                           and a["operation"] in {"restrict", "lien"}]
            releases = set()
            for action in protections:
                if action["status"] in {"pending", "failed"}:
                    action.update(status="superseded", updated_at=now())
                    self.store.update(db, "actions", action["action_id"], action)
                    db.execute("UPDATE jobs SET done=1 WHERE id=?", (action["action_id"],))
                releases.add(("release" if action["operation"] == "restrict" else "lien_release",
                              action["target_type"], action["target_id"]))
            # Release uncertain deliveries too; bank ownership protects other cases.
            for operation, target_type, target_id in sorted(releases):
                self._queue_action(db, case, operation, actor.username, target_type=target_type, target_id=target_id)
            if not releases:
                case["status"] = "resolved"
        elif request.action == "close_account":
            if case["verdict"] != "fraud":
                raise ConflictError("Confirm fraud before requesting final account closure")
            self._queue_action(db, case, "close", actor.username, target_id=target)
            case["status"] = "investigating"
        elif request.action == "place_lien":
            self._queue_action(db, case, "lien", actor.username, amount_minor=request.amount_minor, target_id=target)
        elif request.action in {"restrict", "release_lien"}:
            self._queue_action(db, case, "restrict" if request.action == "restrict" else "lien_release", actor.username, target_id=target)
        elif request.action == "file_ncrp_report":
            case["ncrp_report"] = {"status": "recorded_in_simulation", "recorded_by": actor.username, "recorded_at": now()}
        if case["status"] == "resolved":
            case.setdefault("resolved_at", now())
        self.store.update(db, "cases", case_id, case)
        self.store.event(db, "analyst_decision", f"{actor.display_name}: {request.action.replace('_', ' ')}. {request.notes}",
                         case_id=case_id, txn_id=case["txn_id"], actor=actor.username, metadata={"action": request.action, "version": case["version"], "target_account_id": target})
        return self._case(db, case_id)

    def claim(self, case_id, request, actor):
        require(actor, "claim")
        with self._lock, self.store.connect(write=True) as db:
            case = self._editable(db, case_id, request.expected_version)
            owner = case.get("assignee")
            if owner and owner != actor.username:
                account = self.analysts.get(owner) if self.analysts else None
                raise ConflictError(f"Case is assigned to {account.display_name if account else owner}",
                                    assignee=owner, version=case["version"])
            self._assign_case(db, case, actor, actor, "case_claimed")
            return self._case(db, case_id)

    def _assign_case(self, db, case, target, actor, event_type):
        case.update(assignee=target.username, assigned_to=target.display_name, assigned_at=now(),
                    updated_at=now(), version=case["version"] + 1)
        self.store.update(db, "cases", case["case_id"], case)
        self.store.event(db, event_type, f"{actor.display_name} assigned the case to {target.display_name}.",
                         case_id=case["case_id"], actor=actor.username)

    def assign(self, case_id, request, actor):
        require(actor, "assign")
        target = self.analysts.get(request.username) if self.analysts else None
        if not target:
            raise OperationError("Target analyst does not exist", status_code=404)
        with self._lock, self.store.connect(write=True) as db:
            case = self._editable(db, case_id, request.expected_version)
            self._assign_case(db, case, target, actor, "case_assigned")
            return self._case(db, case_id)

    def request_approval(self, case_id, request, actor):
        if can(actor.role, request.action):
            raise OperationError("You can perform this action directly")
        with self._lock, self.store.connect(write=True) as db:
            case = self._editable(db, case_id, request.expected_version)
            if case.get("pending_approval"):
                raise ConflictError("An approval is already pending for this case")
            target = self._protection_target(case, request.action, request.target_account_id)
            case["pending_approval"] = dict(approval_id=f"APR-{uuid4().hex}", action=request.action,
                requested_by=actor.username, required_role=required_role(request.action), notes=request.notes, requested_at=now(), target_account_id=target)
            case.update(version=case["version"] + 1, updated_at=now())
            self.store.update(db, "cases", case_id, case)
            self.store.event(db, "approval_requested", f"{actor.display_name} requested {request.action}: {request.notes}",
                             case_id=case_id, actor=actor.username, metadata=case["pending_approval"])
            return self._case(db, case_id)

    def decide_approval(self, case_id, request, actor):
        with self._lock, self.store.connect(write=True) as db:
            case = self.store.get(db, "cases", case_id)
            if not case:
                raise NotFoundError("Case not found")
            approval = case.get("pending_approval")
            if not approval:
                raise ConflictError("No approval is pending")
            if actor.username == approval["requested_by"]:
                raise OperationError("You cannot approve your own request", status_code=403)
            require(actor, approval["action"])
            requester = self.analysts.get(approval["requested_by"]) if self.analysts else None
            name = requester.display_name if requester else approval["requested_by"]
            case["pending_approval"] = None
            if request.approve:
                decision = DecisionInput(action=approval["action"], expected_version=case["version"], notes=approval["notes"],
                                         target_account_id=approval.get("target_account_id"))
                self._apply_decision(db, case, decision, actor)
                message = f"Approved by {actor.display_name} (requested by {name})"
            else:
                case.update(version=case["version"] + 1, updated_at=now())
                self.store.update(db, "cases", case_id, case)
                message = f"Rejected by {actor.display_name} (requested by {name}): {request.notes}"
            self.store.event(db, "approval_approved" if request.approve else "approval_rejected", message,
                             case_id=case_id, actor=actor.username, metadata={**approval, "decision_notes": request.notes})
            return self._case(db, case_id)

    def heartbeat(self, actor, current_case_id=None):
        with self._lock, self.store.connect(write=True) as db:
            if current_case_id:
                self._case(db, current_case_id)
            self._presence(db, actor, current_case_id)
            self.store.event(db, "analyst_presence", f"{actor.display_name} is online.", actor=actor.username)

    def _presence(self, db, actor, current_case_id=None, signed_out=False):
        seen = (self.clock() - timedelta(seconds=46) if signed_out else self.clock()).isoformat()
        db.execute("""INSERT INTO presence VALUES(?,?,?,?,?) ON CONFLICT(username) DO UPDATE SET
                   display_name=excluded.display_name,role=excluded.role,last_seen=excluded.last_seen,
                   current_case_id=excluded.current_case_id""",
                   (actor.username, actor.display_name, actor.role, seen, current_case_id))

    def record_session(self, actor, signed_in):
        with self._lock, self.store.connect(write=True) as db:
            self._presence(db, actor, signed_out=not signed_in)
            self.store.event(db, "analyst_signed_in" if signed_in else "analyst_signed_out",
                             f"{actor.display_name} signed {'in' if signed_in else 'out'}.", actor=actor.username)

    def file_complaint(self, request, actor):
        require(actor, "place_lien")
        payload = request.model_dump(mode="json")
        fingerprint = hashlib.sha256(dump(payload).encode()).hexdigest()
        self._refresh_bank()
        with self._lock, self.store.connect(write=True) as db:
            old = db.execute("SELECT fingerprint,case_id FROM complaints WHERE id=?", (request.complaint_id,)).fetchone()
            if old:
                if old["fingerprint"] != fingerprint:
                    raise ConflictError("Complaint id already belongs to a different report")
                return self._case(db, old["case_id"])
            txn = self.store.get(db, "transactions", request.reported_txn_id)
            if not txn:
                raise NotFoundError("Reported transaction not found")
            if db.execute("SELECT 1 FROM complaints WHERE txn_id=?", (txn["txn_id"],)).fetchone():
                raise ConflictError("This payment already has a complaint; use the existing case")
            if txn["account_id"] != request.victim_account_id or txn["payment_status"] != "posted" or not txn.get("beneficiary_id"):
                raise OperationError("Complaint requires a posted transfer from the stated victim to a beneficiary")
            if request.reported_at < datetime.fromisoformat(txn["timestamp"]):
                raise OperationError("The complaint cannot precede the reported payment")
            case_id = txn["case_id"] or f"CASE-{uuid4().hex[:12].upper()}"
            case = self.store.get(db, "cases", case_id)
            if case:
                if case["verdict"] == "false_positive":
                    raise ConflictError("A final false-positive case requires separate supervisor review")
                case.update(version=case["version"] + 1, updated_at=now(), status="investigating")
            else:
                case = dict(case_id=case_id, txn_id=txn["txn_id"], account_id=txn["account_id"], channel=txn["channel"],
                            amount_minor=txn["amount_minor"], score=txn["score"], severity="high", status="new", verdict="unreviewed",
                            version=1, created_at=now(), updated_at=now(), assigned_to=None, assignee=None, assigned_at=None,
                            pending_approval=None, notes="", signals=[], reasons=["Victim-reported transfer; fund trace requested."],
                            related_accounts=[], policy_version=VERSION)
                db.execute("INSERT INTO cases VALUES(?,?,?)", (case_id, txn["txn_id"], dump(case)))
                txn["case_id"] = case_id
                self.store.update(db, "transactions", txn["txn_id"], txn)
            hops = trace_funds(self.store.records(db, "transactions"), txn)
            case.update(case_type="complaint", complaint=payload, trace_prepared=False,
                        trace=[{**h, "available_minor": 0, "lien_minor": 0, "lien_status": "waiting_bank",
                                "outcome": "pending" if h["traced_minor"] else "funds_moved"} for h in hops],
                        related_accounts=[h["account_id"] for h in hops])
            self.store.update(db, "cases", case_id, case)
            db.execute("INSERT INTO complaints VALUES(?,?,?,?)", (request.complaint_id, fingerprint, txn["txn_id"], case_id))
            self.store.event(db, "complaint_received", f"{actor.display_name} recorded simulated {request.source} complaint {request.complaint_id}.",
                             case_id=case_id, txn_id=txn["txn_id"], actor=actor.username, metadata=payload)
            if self._bank_state["connected"]:
                self._prepare_traces(db, self._bank_state["accounts"])
            return self._case(db, case_id)

    def _prepare_traces(self, db, accounts):
        available = {a["account_id"]: a["available_minor"] for a in accounts}
        statuses = {a["account_id"]: a["status"] for a in accounts}
        for action in self.store.records(db, "actions"):
            if action["operation"] == "lien" and action["status"] in {"pending", "failed"}:
                available[action["target_id"]] = max(0, available.get(action["target_id"], 0) - action["amount_minor"])
        for case in self.store.records(db, "cases"):
            if case.get("case_type") != "complaint" or case.get("trace_prepared"):
                continue
            for hop in case["trace"]:
                account = hop["account_id"]
                hop.update(available_minor=available.get(account, 0), lien_status="not_requested", outcome="funds_moved")
                if account == case["complaint"]["victim_account_id"]:
                    hop["outcome"] = "returned_to_victim"
                elif statuses.get(account) == "closed":
                    hop["outcome"] = "account_closed"
                else:
                    amount = min(hop["traced_minor"], available.get(account, 0))
                    if amount:
                        action = self._queue_action(db, case, "lien", "agent", amount_minor=amount, target_id=account,
                                                    reason="Golden-hour lien on traced funds")
                        hop.update(lien_action_id=action["action_id"], lien_status="pending", outcome="pending")
                        available[account] -= amount
            case.update(trace_prepared=True, version=case["version"] + 1, updated_at=now())
            self.store.update(db, "cases", case["case_id"], case)
            self.store.event(db, "trace_prepared", "Golden-hour trace prepared against bank-reported available funds.",
                             case_id=case["case_id"], actor="agent")

    def retry_action(self, action_id, actor):
        with self._lock, self.store.connect(write=True) as db:
            action = self.store.get(db, "actions", action_id)
            if not action:
                raise NotFoundError("Bank action not found")
            require(actor, {"restrict": "restrict", "release": "false_positive", "lien": "place_lien",
                            "lien_release": "release_lien", "close": "close_account"}[action["operation"]])
            if action["operation"] in {"restrict", "lien", "close"}:
                case = self.store.get(db, "cases", action["case_id"])
                self._protection_target(case, {"restrict": "restrict", "lien": "place_lien", "close": "close_account"}[action["operation"]],
                                        action["target_id"] if action["target_type"] == "account" else None)
            if action["status"] in {"confirmed", "superseded"}:
                raise ConflictError("This action is already final and cannot be retried")
            action.update(status="pending", last_error=None, updated_at=now())
            self.store.update(db, "actions", action_id, action)
            db.execute("UPDATE jobs SET done=0,next_at=0 WHERE id=?", (action_id,))
            self.store.event(db, "action_retry", "Analyst requested retry of the same idempotent bank action.",
                             case_id=action["case_id"], actor=actor.username, metadata={"action_id": action_id})
            return action

    def _refresh_bank(self):
        try:
            status = self.bank.get("/bank/status")
            status.raise_for_status()
            accounts = self.bank.get("/bank/accounts")
            accounts.raise_for_status()
            state = dict(connected=True, mode=status.json()["mode"], accounts=accounts.json()["accounts"], last_error=None)
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            state = {**self._bank_state, "connected": False, "last_error": f"Bank simulator unavailable ({type(exc).__name__})."}
        with self.store.connect(write=True) as db:
            previous = self.store.setting(db, "bank_state")
            if previous != state:
                self.store.set_setting(db, "bank_state", state)
                self.store.event(db, "bank_connection", "Bank simulator connected." if state["connected"] else state["last_error"])
            if state["connected"]:
                self._prepare_traces(db, state["accounts"])
        self._bank_state = state

    def process_jobs(self):
        with self._lock:
            with self.store.connect() as db:
                jobs = [dict(r) for r in db.execute(
                    "SELECT * FROM jobs WHERE done=0 AND next_at<=? ORDER BY CASE kind WHEN 'action' THEN 0 ELSE 1 END,rowid LIMIT 100", (time.time(),))]
            for job in jobs:
                if job["kind"] == "action":
                    self._deliver_action(job)
                else:
                    self._deliver_payment(job)
            self._refresh_bank()

    def _deliver_action(self, job):
        with self.store.connect(write=True) as db:
            action = self.store.get(db, "actions", job["resource_id"])
            if action["status"] in {"confirmed", "superseded"}:
                db.execute("UPDATE jobs SET done=1 WHERE id=?", (job["id"],))
                return
            invalid_target = None
            case = self.store.get(db, "cases", action["case_id"])
            if case.get("case_type") == "complaint" and action["operation"] in {"restrict", "lien", "close"}:
                try:
                    self._protection_target(case, {"restrict": "restrict", "lien": "place_lien", "close": "close_account"}[action["operation"]], action["target_id"])
                except OperationError as exc:
                    invalid_target = str(exc)
            action.update(attempts=action["attempts"] + 1, updated_at=now())
            self.store.update(db, "actions", action["action_id"], action)
        # Commit attempt BEFORE making the network call, so a crash after bank
        # commit always causes a lookup/replay of the same id, never a new id.
        try:
            response = self.bank.get(f"/bank/actions/{action['action_id']}")
            if response.status_code == 404:
                if invalid_target:
                    with self.store.connect(write=True) as db:
                        action.update(status="superseded", last_error=invalid_target, updated_at=now())
                        self.store.update(db, "actions", action["action_id"], action)
                        db.execute("UPDATE jobs SET done=1 WHERE id=?", (job["id"],))
                        case = self.store.get(db, "cases", action["case_id"])
                        case.update(version=case["version"] + 1, updated_at=now())
                        self.store.update(db, "cases", case["case_id"], case)
                        self.store.event(db, "unsafe_target_cancelled", f"Undelivered action cancelled: {invalid_target}",
                                         case_id=case["case_id"], metadata={"action_id": action["action_id"], "target_account_id": action["target_id"]})
                    return
                payload = {k: action[k] for k in ("action_id", "case_id", "operation", "target_type", "target_id")}
                if action["operation"] == "lien":
                    payload["amount_minor"] = action["amount_minor"]
                response = self.bank.post("/bank/actions", json=payload)
            response.raise_for_status()
            ack = response.json()
            if ack.get("action_id") != action["action_id"] or ack.get("status") != "confirmed" or not ack.get("bank_reference"):
                raise ValueError("Bank returned an invalid acknowledgement")
            if action["operation"] == "lien" and ack.get("amount_minor") != action["amount_minor"]:
                raise ValueError("Bank acknowledged a different lien amount")
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            # Timeout means unknown outcome. Reconciliation remains pending;
            # explicit rejection is visible as failed while still retryable.
            timeout = isinstance(exc, httpx.TimeoutException) or (isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 504)
            action.update(status="pending" if timeout else "failed", last_error="Acknowledgement uncertain; reconciling by action id." if timeout else f"Bank request failed ({type(exc).__name__}).", updated_at=now())
            with self.store.connect(write=True) as db:
                self.store.update(db, "actions", action["action_id"], action)
                db.execute("UPDATE jobs SET next_at=? WHERE id=?", (time.time() + (0 if timeout else min(30, 2 ** min(action["attempts"], 5))), job["id"]))
                self.store.event(db, "bank_action_pending" if timeout else "bank_action_failed", action["last_error"], case_id=action["case_id"], metadata={"action_id": action["action_id"]})
            return
        with self.store.connect(write=True) as db:
            action.update(status="confirmed", bank_reference=ack["bank_reference"], last_error=None, updated_at=now())
            self.store.update(db, "actions", action["action_id"], action)
            db.execute("UPDATE jobs SET done=1 WHERE id=?", (job["id"],))
            case = self.store.get(db, "cases", action["case_id"])
            outstanding = any(a["case_id"] == case["case_id"] and a["status"] in {"pending", "failed"}
                              for a in self.store.records(db, "actions"))
            if not outstanding and ((action["operation"] in {"release", "lien_release"} and case["verdict"] == "false_positive")
                                    or (action["operation"] in {"restrict", "close", "lien"} and case["verdict"] == "fraud")):
                case["status"] = "resolved"
            if case["status"] == "resolved":
                case.setdefault("resolved_at", now())
            case.update(updated_at=now(), version=case["version"] + 1)
            self.store.update(db, "cases", case["case_id"], case)
            self.store.event(db, f"{action['operation']}_confirmed", f"Bank confirmed {action['operation']} for simulated {action['target_type']} {action['target_id']}.",
                             case_id=case["case_id"], txn_id=case["txn_id"], metadata={"action_id": action["action_id"], "bank_reference": ack["bank_reference"]})

    def _deliver_payment(self, job):
        with self.store.connect() as db:
            txn = self.store.get(db, "transactions", job["resource_id"])
            if txn["case_id"]:
                # The payment cannot race ahead of unresolved protection.
                for action in self.store.records(db, "actions"):
                    if action["case_id"] == txn["case_id"] and action["status"] in {"pending", "failed"}:
                        return
        payload = {k: txn[k] for k in ("txn_id", "account_id", "channel", "amount_minor", "instrument_id")}
        if txn.get("beneficiary_id"):
            payload["beneficiary_id"] = txn["beneficiary_id"]
        try:
            response = self.bank.post("/bank/transactions", json=payload)
            response.raise_for_status()
            result = response.json()
            if result.get("txn_id") != txn["txn_id"] or result.get("status") not in {"posted", "declined"}:
                raise ValueError("Bank returned an invalid payment result")
        except (httpx.HTTPError, ValueError, KeyError):
            with self.store.connect(write=True) as db:
                txn["bank_reason"] = "Bank result unavailable; awaiting idempotent reconciliation."
                self.store.update(db, "transactions", txn["txn_id"], txn)
                db.execute("UPDATE jobs SET next_at=? WHERE id=?", (time.time() + 2, job["id"]))
            return
        with self.store.connect(write=True) as db:
            txn.update(payment_status=result["status"], bank_reason=result["reason"])
            self.store.update(db, "transactions", txn["txn_id"], txn)
            db.execute("UPDATE jobs SET done=1 WHERE id=?", (job["id"],))
            self.store.event(db, f"payment_{result['status']}", f"Simulated payment {result['status']}: {result['reason']}.",
                             case_id=txn["case_id"], txn_id=txn["txn_id"], metadata={"bank_reference": result.get("bank_reference")})

    def cursor(self):
        with self.store.connect() as db:
            return db.execute("SELECT COALESCE(MAX(id),0) FROM events").fetchone()[0]

    def snapshot(self):
        with self.store.connect() as db:
            txns = self.store.records(db, "transactions")
            cases = self.store.records(db, "cases")
            actions = self.store.records(db, "actions")
            counts = dict(transactions=len(txns), pending_payments=sum(t["payment_status"] == "pending" for t in txns),
                          posted=sum(t["payment_status"] == "posted" for t in txns), declined=sum(t["payment_status"] == "declined" for t in txns),
                          cases=len(cases), pending_review=sum(c["status"] == "new" for c in cases),
                          investigating=sum(c["status"] == "investigating" for c in cases), escalated=sum(c["status"] == "escalated" for c in cases),
                          resolved=sum(c["status"] == "resolved" for c in cases), confirmed_fraud=sum(c["verdict"] == "fraud" for c in cases),
                          false_positives=sum(c["verdict"] == "false_positive" for c in cases),
                          pending_actions=sum(a["status"] == "pending" for a in actions), failed_actions=sum(a["status"] == "failed" for a in actions))
            active = {}
            for action in reversed(actions):
                if action["status"] == "confirmed":
                    key = (action["case_id"], action["target_type"], action["target_id"])
                    if action["operation"] == "restrict":
                        active[key] = True
                    elif action["operation"] == "release":
                        active.pop(key, None)
            counts["traced_total_minor"] = sum(sum(h["traced_minor"] for h in c.get("trace", [])) for c in cases)
            counts["held_total_minor"] = sum(sum(h["lien_minor"] for h in trace_view(c, [a for a in actions if a["case_id"] == c["case_id"]])) for c in cases)
            counts["complaints"] = sum(c.get("case_type") == "complaint" for c in cases)
            counts["restricted_accounts"] = len({k[2] for k in active if k[1] == "account"})
            counts["restricted_cards"] = len({k[2] for k in active if k[1] == "card"})
            channels = []
            for channel in CHANNELS:
                ct = [t for t in txns if t["channel"] == channel]
                cc = [c for c in cases if c["channel"] == channel]
                channels.append(dict(channel=channel, transactions=len(ct), cases=len(cc),
                                     pending_review=sum(c["status"] == "new" for c in cc), confirmed_fraud=sum(c["verdict"] == "fraud" for c in cc),
                                     resolved=sum(c["status"] == "resolved" for c in cc), declined=sum(t["payment_status"] == "declined" for t in ct)))
            cursor = db.execute("SELECT COALESCE(MAX(id),0) FROM events").fetchone()[0]
            return dict(cursor=cursor, as_of=now(), simulation=True, counts=counts, channels=channels,
                        transactions=txns[:200], cases=[self._case(db, c["case_id"]) for c in cases[:200]],
                        actions=actions[:200], events=self.store.events(db),
                        team=team_snapshot(db, cases, self.analysts, self.clock()),
                        approvals=[{"case_id": c["case_id"], **c["pending_approval"]} for c in cases if c.get("pending_approval")],
                        bank=self.store.setting(db, "bank_state", self._bank_state),
                        simulation_state=self.store.setting(db, "simulation", {"running": False, "interval_seconds": 5}),
                        detection={"version": VERSION, "coverage": COVERAGE})

    def listing(self, kind, limit=50, offset=0, channel=None, status=None):
        with self.store.connect() as db:
            items = self.store.records(db, kind)
            if channel:
                items = [v for v in items if v["channel"] == channel]
            if status:
                items = [v for v in items if v.get("status") == status]
            return {"items": items[offset:offset + limit], "total": len(items)}

    def control(self, request, actor):
        if request.bank_mode:
            response = self.bank.post("/bank/control", json={"mode": request.bank_mode})
            response.raise_for_status()
        with self._lock, self.store.connect(write=True) as db:
            config = self.store.setting(db, "simulation", {"running": False, "interval_seconds": 5})
            if request.running is not None:
                config["running"] = request.running
            if request.interval_seconds is not None:
                config["interval_seconds"] = request.interval_seconds
            self.store.set_setting(db, "simulation", config)
            self.store.event(db, "simulation_control", "Simulation controls updated.", actor=actor, metadata=request.model_dump(exclude_none=True))
        self._refresh_bank()
        return self.snapshot()

    def run_scenario(self, channel, scenario, actor="simulation", *, victim_amount_minor=None):
        from .scenarios import TYPOLOGIES, scenario_transactions, typology_accounts
        rows = scenario_transactions(channel, scenario)
        if scenario == "mule_layering" and victim_amount_minor is not None:
            amounts = [victim_amount_minor, victim_amount_minor * 30 // 48, victim_amount_minor * 15 // 48, victim_amount_minor * 20 // 48]
            rows = [row.model_copy(update={"amount_minor": amount}) for row, amount in zip(rows, amounts)]
        if scenario in TYPOLOGIES:
            response = self.bank.post("/bank/accounts/seed", json={"accounts": typology_accounts(rows)})
            response.raise_for_status()
            with self.store.connect(write=True) as db:
                self.store.event(db, "scenario_accounts_seeded", "Fictional typology accounts provisioned before payment posting.", actor=actor)
        results = []
        for txn in rows:
            results.append(self.ingest(txn, actor))
            self.process_jobs()
        ids = [r["transaction"]["txn_id"] for r in results]
        with self.store.connect() as db:
            return {"transactions": [self.store.get(db, "transactions", identifier) for identifier in ids],
                    "case_ids": [r["case"]["case_id"] for r in results if r["case"]]}

    def seed_baseline(self):
        from .scenarios import scenario_transactions
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
                        plan.extend(t.model_dump(mode="json") for t in scenario_transactions(channel, scenario))
                self.store.set_setting(db, "baseline_plan", plan)
        # Stable ids and timestamps are persisted before the first ingest.
        # Restart resumes the same plan through ordinary idempotent delivery.
        for payload in plan:
            self.ingest(TransactionInput(**payload), "simulation")
            self.process_jobs()
        with self.store.connect(write=True) as db:
            self.store.set_setting(db, "seeded", True)
