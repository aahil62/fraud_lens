"""Payment attempts entering the ledger, and the cases detection opens for them."""

import hashlib
from uuid import uuid4

from .detector import VERSION, detect
from .errors import ConflictError
from .models import TransactionInput
from .store import dump, now

REVIEW_SCORE = 0.5  # opens a case
PROTECT_SCORE = 0.8  # also requests a restriction straight away
CRITICAL_SCORE = 0.9


def severity(score):
    if score >= CRITICAL_SCORE:
        return "critical"
    return "high" if score >= PROTECT_SCORE else "medium"


def new_case(case_id, txn, *, score, severity, signals, reasons, related_accounts):
    """A fresh, unassigned, unreviewed case for one payment."""
    return dict(
        case_id=case_id,
        txn_id=txn["txn_id"],
        account_id=txn["account_id"],
        channel=txn["channel"],
        amount_minor=txn["amount_minor"],
        score=score,
        severity=severity,
        status="new",
        verdict="unreviewed",
        version=1,
        created_at=now(),
        updated_at=now(),
        assigned_to=None,
        assignee=None,
        assigned_at=None,
        pending_approval=None,
        notes="",
        signals=signals,
        reasons=reasons,
        related_accounts=related_accounts,
        policy_version=VERSION,
    )


def new_case_id():
    return f"CASE-{uuid4().hex[:12].upper()}"


class IngestMixin:
    """Ingest on OperationsService; uses its store, lock, _queue_action, _save_case and _case."""

    def ingest(self, request: TransactionInput, actor="system"):
        payload = request.model_dump(mode="json")
        fingerprint = hashlib.sha256(dump(payload).encode()).hexdigest()
        with self._lock, self.store.connect(write=True) as db:
            old = db.execute(
                "SELECT fingerprint,data FROM transactions WHERE id=?", (request.txn_id,)
            ).fetchone()
            if old:
                if old[0] != fingerprint:
                    raise ConflictError("Transaction id already belongs to a different payload")
                txn = self.store.get(db, "transactions", request.txn_id)
                case = self._case(db, txn["case_id"]) if txn["case_id"] else None
                return {"transaction": txn, "case": case, "duplicate": True}
            result = detect(payload, self.store.records(db, "transactions"))
            case_id = new_case_id() if result["score"] >= REVIEW_SCORE else None
            txn = {
                **payload,
                "score": result["score"],
                "payment_status": "pending",
                "bank_reason": None,
                "case_id": case_id,
            }
            db.execute("INSERT INTO transactions VALUES(?,?,?)", (request.txn_id, fingerprint, dump(txn)))
            self.store.event(
                db,
                "transaction_received",
                f"{request.channel} payment attempt received.",
                txn_id=request.txn_id,
                actor=actor,
            )
            if case_id:
                case = self._open_case(db, case_id, txn, result)
            db.execute(
                "INSERT INTO jobs(id,kind,resource_id) VALUES(?,?,?)",
                (f"payment-{request.txn_id}", "payment", request.txn_id),
            )
            if case_id:
                self._save_case(db, case)
            case = self._case(db, case_id) if case_id else None
            return {"transaction": txn, "case": case, "duplicate": False}

    def _open_case(self, db, case_id, txn, result):
        case = new_case(
            case_id,
            txn,
            score=result["score"],
            severity=severity(result["score"]),
            signals=result["signals"],
            reasons=result["reasons"],
            related_accounts=result["related_accounts"],
        )
        db.execute("INSERT INTO cases VALUES(?,?,?)", (case_id, txn["txn_id"], dump(case)))
        self.store.event(
            db,
            "case_opened",
            "Detection opened an investigation; analyst verdict pending.",
            case_id=case_id,
            txn_id=txn["txn_id"],
            metadata={"score": result["score"], "policy_version": VERSION},
        )
        if result["score"] >= PROTECT_SCORE:
            self._queue_action(db, case, "restrict")
        return case
