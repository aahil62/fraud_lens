"""Durable operational lifecycle. Bank effects occur only after local commit."""
import hashlib
import json
import threading
import time
from uuid import uuid4

import httpx

from .detector import CHANNELS, COVERAGE, VERSION, detect
from .models import DecisionInput, TransactionInput
from .store import Store, dump, now


class ConflictError(ValueError):
    pass


class NotFoundError(ValueError):
    pass


class OperationsService:
    def __init__(self, db_path, bank_client=None, *, bank_url="http://127.0.0.1:8002", bank_key="fraudlens-local-simulator"):
        self.store = Store(db_path)
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
                            assigned_to=None, notes="", signals=result["signals"], reasons=result["reasons"],
                            related_accounts=result["related_accounts"], policy_version=VERSION)
                db.execute("INSERT INTO cases VALUES(?,?,?)", (case_id, request.txn_id, dump(case)))
                self.store.event(db, "case_opened", "Detection opened an investigation; analyst verdict pending.",
                                 case_id=case_id, txn_id=request.txn_id, metadata={"score": result["score"], "policy_version": VERSION})
                if result["score"] >= .8:
                    self._queue_action(db, case, "restrict")
            db.execute("INSERT INTO jobs(id,kind,resource_id) VALUES(?,?,?)", (f"payment-{request.txn_id}", "payment", request.txn_id))
            case = self._case(db, case_id) if case_id else None
            return {"transaction": txn, "case": case, "duplicate": False}

    def _queue_action(self, db, case, operation, actor="system"):
        txn = self.store.get(db, "transactions", case["txn_id"])
        target_type = "card" if txn["channel"] in {"card", "atm"} else "account"
        target_id = txn["instrument_id"] if target_type == "card" else txn["account_id"]
        action_id = f"ACT-{uuid4().hex}"
        action = dict(action_id=action_id, case_id=case["case_id"], operation=operation, target_type=target_type,
                      target_id=target_id, status="pending", attempts=0, bank_reference=None, last_error=None,
                      created_at=now(), updated_at=now())
        db.execute("INSERT INTO actions VALUES(?,?,?)", (action_id, case["case_id"], dump(action)))
        db.execute("INSERT INTO jobs(id,kind,resource_id) VALUES(?,?,?)", (action_id, "action", action_id))
        self.store.event(db, f"{operation}_requested", f"{operation.capitalize()} requested for simulated {target_type} {target_id}.",
                         case_id=case["case_id"], txn_id=case["txn_id"], actor=actor, metadata={"action_id": action_id})
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
        case["actions"] = actions
        case["timeline"] = events
        return case

    def get_case(self, case_id):
        with self.store.connect() as db:
            return self._case(db, case_id)

    def decide(self, case_id, request: DecisionInput, actor):
        with self._lock, self.store.connect(write=True) as db:
            case = self.store.get(db, "cases", case_id)
            if not case:
                raise NotFoundError("Case not found")
            if case["version"] != request.expected_version:
                raise ConflictError("Case changed since you opened it. Refresh and review the latest version.")
            if case["verdict"] == "false_positive":
                raise ConflictError("A false-positive verdict is already recorded; its release must finish without a contradictory decision.")
            if case["status"] == "resolved" and not (request.action == "false_positive" and case["verdict"] == "fraud"):
                raise ConflictError("This case is resolved; its final verdict is already recorded.")
            case.update(version=case["version"] + 1, updated_at=now(), assigned_to=actor, notes=request.notes)
            if request.action in {"investigate", "escalate"}:
                case["status"] = "investigating" if request.action == "investigate" else "escalated"
            elif request.action == "confirm_fraud":
                case.update(verdict="fraud", status="investigating")
                actions = [a for a in self.store.records(db, "actions") if a["case_id"] == case_id and a["operation"] == "restrict"]
                if not actions:
                    self._queue_action(db, case, "restrict", actor)
                elif any(a["status"] == "confirmed" for a in actions):
                    case["status"] = "resolved"
            else:
                case.update(verdict="false_positive", status="investigating")
                restricted = False
                for action in self.store.records(db, "actions"):
                    if action["case_id"] == case_id and action["operation"] == "restrict":
                        restricted = True
                        if action["status"] in {"pending", "failed"}:
                            action.update(status="superseded", updated_at=now())
                            self.store.update(db, "actions", action["action_id"], action)
                            db.execute("UPDATE jobs SET done=1 WHERE id=?", (action["action_id"],))
                # Release is sent even for uncertain previous delivery. Bank
                # restriction ownership makes this safe for other open cases.
                if restricted:
                    self._queue_action(db, case, "release", actor)
                else:
                    case["status"] = "resolved"
            self.store.update(db, "cases", case_id, case)
            self.store.event(db, "analyst_decision", f"{actor}: {request.action.replace('_', ' ')}. {request.notes}",
                             case_id=case_id, txn_id=case["txn_id"], actor=actor, metadata={"action": request.action, "version": case["version"]})
            return self._case(db, case_id)

    def retry_action(self, action_id, actor):
        with self._lock, self.store.connect(write=True) as db:
            action = self.store.get(db, "actions", action_id)
            if not action:
                raise NotFoundError("Bank action not found")
            if action["status"] in {"confirmed", "superseded"}:
                raise ConflictError("This action is already final and cannot be retried")
            action.update(status="pending", last_error=None, updated_at=now())
            self.store.update(db, "actions", action_id, action)
            db.execute("UPDATE jobs SET done=0,next_at=0 WHERE id=?", (action_id,))
            self.store.event(db, "action_retry", "Analyst requested retry of the same idempotent bank action.",
                             case_id=action["case_id"], actor=actor, metadata={"action_id": action_id})
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
            action.update(attempts=action["attempts"] + 1, updated_at=now())
            self.store.update(db, "actions", action["action_id"], action)
        # Commit attempt BEFORE making the network call, so a crash after bank
        # commit always causes a lookup/replay of the same id, never a new id.
        try:
            response = self.bank.get(f"/bank/actions/{action['action_id']}")
            if response.status_code == 404:
                payload = {k: action[k] for k in ("action_id", "case_id", "operation", "target_type", "target_id")}
                response = self.bank.post("/bank/actions", json=payload)
            response.raise_for_status()
            ack = response.json()
            if ack.get("action_id") != action["action_id"] or ack.get("status") != "confirmed" or not ack.get("bank_reference"):
                raise ValueError("Bank returned an invalid acknowledgement")
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
            if (action["operation"] == "release" and case["verdict"] == "false_positive") or (action["operation"] == "restrict" and case["verdict"] == "fraud"):
                case["status"] = "resolved"
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
                    else:
                        active.pop(key, None)
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

    def run_scenario(self, channel, scenario, actor="simulation"):
        from .scenarios import scenario_transactions
        results = [self.ingest(t, actor) for t in scenario_transactions(channel, scenario)]
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
