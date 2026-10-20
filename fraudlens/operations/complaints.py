"""1930 / NCRP complaints: open a complaint case, trace the money and request golden-hour liens."""

import hashlib
from datetime import datetime

from .errors import ConflictError, NotFoundError, OperationError
from .ingest import new_case, new_case_id
from .store import dump, now
from .team import require
from .trace import trace_funds


class ComplaintsMixin:
    """Complaints on OperationsService; uses its store, lock, bank state, _queue_action and _save_case."""

    def file_complaint(self, request, actor):
        require(actor, "place_lien")
        payload = request.model_dump(mode="json")
        fingerprint = hashlib.sha256(dump(payload).encode()).hexdigest()
        self._refresh_bank()
        with self._lock, self.store.connect(write=True) as db:
            old = db.execute(
                "SELECT fingerprint,case_id FROM complaints WHERE id=?", (request.complaint_id,)
            ).fetchone()
            if old:
                if old["fingerprint"] != fingerprint:
                    raise ConflictError("Complaint id already belongs to a different report")
                return self._case(db, old["case_id"])
            txn = self._reported_payment(db, request)
            case = self._complaint_case(db, txn)
            case_id = case["case_id"]
            hops = trace_funds(self.store.records(db, "transactions"), txn)
            case.update(
                case_type="complaint",
                complaint=payload,
                trace_prepared=False,
                trace=[
                    {
                        **h,
                        "available_minor": 0,
                        "lien_minor": 0,
                        "lien_status": "waiting_bank",
                        "outcome": "pending" if h["traced_minor"] else "funds_moved",
                    }
                    for h in hops
                ],
                related_accounts=[h["account_id"] for h in hops],
            )
            self._save_case(db, case)
            db.execute(
                "INSERT INTO complaints VALUES(?,?,?,?)",
                (request.complaint_id, fingerprint, txn["txn_id"], case_id),
            )
            self.store.event(
                db,
                "complaint_received",
                f"{actor.display_name} recorded simulated {request.source} complaint {request.complaint_id}.",
                case_id=case_id,
                txn_id=txn["txn_id"],
                actor=actor.username,
                metadata=payload,
            )
            if self._bank_state["connected"]:
                self._prepare_traces(db, self._bank_state["accounts"])
            return self._case(db, case_id)

    def _prepare_traces(self, db, accounts):
        available = {a["account_id"]: a["available_minor"] for a in accounts}
        statuses = {a["account_id"]: a["status"] for a in accounts}
        for action in self.store.records(db, "actions"):
            if action["operation"] == "lien" and action["status"] in {"pending", "failed"}:
                available[action["target_id"]] = max(
                    0, available.get(action["target_id"], 0) - action["amount_minor"]
                )
        for case in self.store.records(db, "cases"):
            if case.get("case_type") != "complaint" or case.get("trace_prepared"):
                continue
            for hop in case["trace"]:
                account = hop["account_id"]
                hop.update(
                    available_minor=available.get(account, 0),
                    lien_status="not_requested",
                    outcome="funds_moved",
                )
                if account == case["complaint"]["victim_account_id"]:
                    hop["outcome"] = "returned_to_victim"
                elif statuses.get(account) == "closed":
                    hop["outcome"] = "account_closed"
                else:
                    amount = min(hop["traced_minor"], available.get(account, 0))
                    if amount:
                        action = self._queue_action(
                            db,
                            case,
                            "lien",
                            "agent",
                            amount_minor=amount,
                            target_id=account,
                            reason="Golden-hour lien on traced funds",
                        )
                        hop.update(
                            lien_action_id=action["action_id"], lien_status="pending", outcome="pending"
                        )
                        available[account] -= amount
            case.update(trace_prepared=True, version=case["version"] + 1, updated_at=now())
            self._save_case(db, case)
            self.store.event(
                db,
                "trace_prepared",
                "Golden-hour trace prepared against bank-reported available funds.",
                case_id=case["case_id"],
                actor="agent",
            )

    def _reported_payment(self, db, request):
        """The posted victim-to-beneficiary payment the complaint names, if it may take a complaint."""
        txn = self.store.get(db, "transactions", request.reported_txn_id)
        if not txn:
            raise NotFoundError("Reported transaction not found")
        if db.execute("SELECT 1 FROM complaints WHERE txn_id=?", (txn["txn_id"],)).fetchone():
            raise ConflictError("This payment already has a complaint; use the existing case")
        if (
            txn["account_id"] != request.victim_account_id
            or txn["payment_status"] != "posted"
            or not txn.get("beneficiary_id")
        ):
            raise OperationError(
                "Complaint requires a posted transfer from the stated victim to a beneficiary"
            )
        if request.reported_at < datetime.fromisoformat(txn["timestamp"]):
            raise OperationError("The complaint cannot precede the reported payment")
        return txn

    def _complaint_case(self, db, txn):
        """The payment's existing case, reopened, or a new one linked to the payment."""
        case_id = txn["case_id"] or new_case_id()
        case = self.store.get(db, "cases", case_id)
        if case:
            if case["verdict"] == "false_positive":
                raise ConflictError("A final false-positive case requires separate supervisor review")
            case.update(version=case["version"] + 1, updated_at=now(), status="investigating")
            return case
        case = new_case(
            case_id,
            txn,
            score=txn["score"],
            severity="high",
            signals=[],
            reasons=["Victim-reported transfer; fund trace requested."],
            related_accounts=[],
        )
        db.execute("INSERT INTO cases VALUES(?,?,?)", (case_id, txn["txn_id"], dump(case)))
        txn["case_id"] = case_id
        self.store.update(db, "transactions", txn["txn_id"], txn)
        return case
