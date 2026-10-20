"""Delivering bank actions and payments, and reconciling what the bank acknowledged.

Each attempt is committed locally before the network call, so a crash after the
bank commits always replays the same action id; the bank treats that id as
idempotent. A timeout leaves the action pending (its outcome is unknown); an
explicit rejection marks it failed and retryable.
"""

import time

import httpx

from .decisions import OPERATION_ACTION, PROTECTIVE_OPERATIONS, protection_target
from .errors import ConflictError, NotFoundError, OperationError
from .store import now
from .team import require

FINAL_STATUSES = {"confirmed", "superseded"}
OPEN_STATUSES = {"pending", "failed"}
JOB_QUERY = (
    "SELECT * FROM jobs WHERE done=0 AND next_at<=? "
    "ORDER BY CASE kind WHEN 'action' THEN 0 ELSE 1 END,rowid LIMIT 100"
)


def _retry_delay(action, timeout):
    """Reconcile an uncertain outcome at once; back off on explicit failures (2, 4, … 30 s)."""
    return 0 if timeout else min(30, 2 ** min(action["attempts"], 5))


def _is_timeout(exc):
    return isinstance(exc, httpx.TimeoutException) or (
        isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 504
    )


def _check_acknowledgement(action, ack):
    if (
        ack.get("action_id") != action["action_id"]
        or ack.get("status") != "confirmed"
        or not ack.get("bank_reference")
    ):
        raise ValueError("Bank returned an invalid acknowledgement")
    if action["operation"] == "lien" and ack.get("amount_minor") != action["amount_minor"]:
        raise ValueError("Bank acknowledged a different lien amount")


def _resolves_case(action, case):
    releases_clear = (
        action["operation"] in {"release", "lien_release"} and case["verdict"] == "false_positive"
    )
    protection_holds = action["operation"] in PROTECTIVE_OPERATIONS and case["verdict"] == "fraud"
    return releases_clear or protection_holds


class DeliveryMixin:
    """Delivery on OperationsService; uses its store, lock, bank client, _save_case and _run_agent."""

    def retry_action(self, action_id, actor):
        with self._lock, self.store.connect(write=True) as db:
            action = self.store.get(db, "actions", action_id)
            if not action:
                raise NotFoundError("Bank action not found")
            require(actor, OPERATION_ACTION[action["operation"]])
            if action["operation"] in PROTECTIVE_OPERATIONS:
                case = self.store.get(db, "cases", action["case_id"])
                account = action["target_id"] if action["target_type"] == "account" else None
                protection_target(case, OPERATION_ACTION[action["operation"]], account)
            if action["status"] in FINAL_STATUSES:
                raise ConflictError("This action is already final and cannot be retried")
            action.update(status="pending", last_error=None, updated_at=now())
            self.store.update(db, "actions", action_id, action)
            db.execute("UPDATE jobs SET done=0,next_at=0 WHERE id=?", (action_id,))
            self.store.event(
                db,
                "action_retry",
                "Analyst requested retry of the same idempotent bank action.",
                case_id=action["case_id"],
                actor=actor.username,
                metadata={"action_id": action_id},
            )
            return action

    def _refresh_bank(self):
        try:
            status = self.bank.get("/bank/status")
            status.raise_for_status()
            accounts = self.bank.get("/bank/accounts")
            accounts.raise_for_status()
            state = dict(
                connected=True,
                mode=status.json()["mode"],
                accounts=accounts.json()["accounts"],
                last_error=None,
            )
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            state = {
                **self._bank_state,
                "connected": False,
                "last_error": f"Bank simulator unavailable ({type(exc).__name__}).",
            }
        with self.store.connect(write=True) as db:
            previous = self.store.setting(db, "bank_state")
            if previous != state:
                self.store.set_setting(db, "bank_state", state)
                message = "Bank simulator connected." if state["connected"] else state["last_error"]
                self.store.event(db, "bank_connection", message)
            if state["connected"]:
                self._prepare_traces(db, state["accounts"])
        self._bank_state = state

    def process_jobs(self):
        with self._lock:
            with self.store.connect() as db:
                jobs = [dict(r) for r in db.execute(JOB_QUERY, (time.time(),))]
            for job in jobs:
                if job["kind"] == "action":
                    self._deliver_action(job)
                else:
                    self._deliver_payment(job)
            self._refresh_bank()
            self._run_agent()

    def _deliver_action(self, job):
        attempt = self._start_attempt(job)
        if attempt is None:
            return
        action, invalid_target = attempt
        try:
            response = self.bank.get(f"/bank/actions/{action['action_id']}")
            if response.status_code == 404:
                if invalid_target:
                    self._cancel_unsafe_action(job, action, invalid_target)
                    return
                response = self.bank.post("/bank/actions", json=self._action_payload(action))
            response.raise_for_status()
            ack = response.json()
            _check_acknowledgement(action, ack)
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            self._record_delivery_failure(job, action, exc)
            return
        self._record_confirmation(job, action, ack)

    def _start_attempt(self, job):
        """Count the attempt and note an unsafe target; None if the action is already final."""
        with self.store.connect(write=True) as db:
            action = self.store.get(db, "actions", job["resource_id"])
            if action["status"] in FINAL_STATUSES:
                db.execute("UPDATE jobs SET done=1 WHERE id=?", (job["id"],))
                return None
            invalid_target = None
            case = self.store.get(db, "cases", action["case_id"])
            if case.get("case_type") == "complaint" and action["operation"] in PROTECTIVE_OPERATIONS:
                try:
                    protection_target(case, OPERATION_ACTION[action["operation"]], action["target_id"])
                except OperationError as exc:
                    invalid_target = str(exc)
            action.update(attempts=action["attempts"] + 1, updated_at=now())
            self.store.update(db, "actions", action["action_id"], action)
        return action, invalid_target

    @staticmethod
    def _action_payload(action):
        payload = {k: action[k] for k in ("action_id", "case_id", "operation", "target_type", "target_id")}
        if action["operation"] == "lien":
            payload["amount_minor"] = action["amount_minor"]
        return payload

    def _cancel_unsafe_action(self, job, action, reason):
        """The bank never received it and its target is no longer allowed: cancel instead of sending."""
        with self.store.connect(write=True) as db:
            action.update(status="superseded", last_error=reason, updated_at=now())
            self.store.update(db, "actions", action["action_id"], action)
            db.execute("UPDATE jobs SET done=1 WHERE id=?", (job["id"],))
            case = self.store.get(db, "cases", action["case_id"])
            case.update(version=case["version"] + 1, updated_at=now())
            self._save_case(db, case)
            self.store.event(
                db,
                "unsafe_target_cancelled",
                f"Undelivered action cancelled: {reason}",
                case_id=case["case_id"],
                metadata={"action_id": action["action_id"], "target_account_id": action["target_id"]},
            )

    def _record_delivery_failure(self, job, action, exc):
        timeout = _is_timeout(exc)
        if timeout:
            error = "Acknowledgement uncertain; reconciling by action id."
        else:
            error = f"Bank request failed ({type(exc).__name__})."
        action.update(status="pending" if timeout else "failed", last_error=error, updated_at=now())
        with self.store.connect(write=True) as db:
            self.store.update(db, "actions", action["action_id"], action)
            next_at = time.time() + _retry_delay(action, timeout)
            db.execute("UPDATE jobs SET next_at=? WHERE id=?", (next_at, job["id"]))
            self.store.event(
                db,
                "bank_action_pending" if timeout else "bank_action_failed",
                action["last_error"],
                case_id=action["case_id"],
                metadata={"action_id": action["action_id"]},
            )

    def _record_confirmation(self, job, action, ack):
        with self.store.connect(write=True) as db:
            action.update(
                status="confirmed", bank_reference=ack["bank_reference"], last_error=None, updated_at=now()
            )
            self.store.update(db, "actions", action["action_id"], action)
            db.execute("UPDATE jobs SET done=1 WHERE id=?", (job["id"],))
            case = self.store.get(db, "cases", action["case_id"])
            outstanding = any(
                a["status"] in OPEN_STATUSES for a in self.store.case_actions(db, case["case_id"])
            )
            if not outstanding and _resolves_case(action, case):
                case["status"] = "resolved"
            if case["status"] == "resolved":
                case.setdefault("resolved_at", now())
            case.update(updated_at=now(), version=case["version"] + 1)
            self._save_case(db, case)
            self.store.event(
                db,
                f"{action['operation']}_confirmed",
                f"Bank confirmed {action['operation']} for simulated {action['target_type']} {action['target_id']}.",
                case_id=case["case_id"],
                txn_id=case["txn_id"],
                metadata={"action_id": action["action_id"], "bank_reference": ack["bank_reference"]},
            )

    def _deliver_payment(self, job):
        with self.store.connect() as db:
            txn = self.store.get(db, "transactions", job["resource_id"])
            # The payment cannot race ahead of unresolved protection.
            if txn["case_id"] and any(
                a["status"] in OPEN_STATUSES for a in self.store.case_actions(db, txn["case_id"])
            ):
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
            self.store.event(
                db,
                f"payment_{result['status']}",
                f"Simulated payment {result['status']}: {result['reason']}.",
                case_id=txn["case_id"],
                txn_id=txn["txn_id"],
                metadata={"bank_reference": result.get("bank_reference")},
            )
