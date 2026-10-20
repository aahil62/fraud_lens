"""Analyst decisions and the bank actions they request.

Which account a protective action may target is decided here, in one place: a
complaint case may act only on accounts its fund trace reached, never on the
complainant's own account; any other case only on its own account.
"""

from uuid import uuid4

from fraudlens.models.schemas import AnalystProfile

from .errors import ConflictError, NotFoundError, OperationError
from .models import DecisionInput
from .store import dump, now
from .team import require

# The analyst action whose permission each bank operation needs.
OPERATION_ACTION = {
    "restrict": "restrict",
    "release": "false_positive",
    "lien": "place_lien",
    "lien_release": "release_lien",
    "close": "close_account",
}
# Operations that hold or stop money, and so need a valid target.
PROTECTIVE_OPERATIONS = {"restrict", "lien", "close"}
TARGETED_ACTIONS = {"restrict", "place_lien", "release_lien", "close_account"}


def reject_victim_target(case, target):
    if target == case["complaint"]["victim_account_id"]:
        raise OperationError("This is the complainant's account.")


def protection_target(case, action, target=None):
    """The account an action targets, or None for actions that take no target."""
    if action not in TARGETED_ACTIONS:
        return None
    if case.get("case_type") == "complaint":
        reject_victim_target(case, target)
        victim = case["complaint"]["victim_account_id"]
        recipients = [h["account_id"] for h in case["trace"] if h["account_id"] != victim]
        target = target or next(iter(recipients), None)
        if not target or target not in recipients:
            raise OperationError("Select an account reached by this fund trace")
    elif target and target != case["account_id"]:
        raise OperationError("Account is not linked to this case")
    return target


def _default_target_type(operation, target_id, txn):
    """Account-only operations and explicit targets act on the account; otherwise card rails act on the card."""
    if operation in {"lien", "lien_release", "close"} or target_id:
        return "account"
    return "card" if txn["channel"] in {"card", "atm"} else "account"


class DecisionsMixin:
    """Decisions on OperationsService; uses its store, lock, _save_case and _case."""

    def _protection_target(self, case, action, target=None):
        return protection_target(case, action, target)

    def _queue_action(
        self,
        db,
        case,
        operation,
        actor="system",
        *,
        amount_minor=None,
        target_id=None,
        target_type=None,
        reason=None,
    ):
        txn = self.store.get(db, "transactions", case["txn_id"])
        if case.get("case_type") == "complaint" and operation in PROTECTIVE_OPERATIONS:
            target_id = protection_target(case, OPERATION_ACTION[operation], target_id)
            target_type = "account"
        if target_type is None:
            target_type = _default_target_type(operation, target_id, txn)
        if target_id is None:
            target_id = txn["instrument_id"] if target_type == "card" else txn["account_id"]
        action_id = f"ACT-{uuid4().hex}"
        action = dict(
            action_id=action_id,
            case_id=case["case_id"],
            operation=operation,
            target_type=target_type,
            target_id=target_id,
            status="pending",
            attempts=0,
            bank_reference=None,
            last_error=None,
            created_at=now(),
            updated_at=now(),
        )
        if operation == "lien":
            action["amount_minor"] = amount_minor
        db.execute("INSERT INTO actions VALUES(?,?,?)", (action_id, case["case_id"], dump(action)))
        db.execute("INSERT INTO jobs(id,kind,resource_id) VALUES(?,?,?)", (action_id, "action", action_id))
        message = f"{operation.capitalize()} requested for simulated {target_type} {target_id}."
        if reason:
            message = f"{reason}. {message}"
        self.store.event(
            db,
            f"{operation}_requested",
            message,
            case_id=case["case_id"],
            txn_id=case["txn_id"],
            actor=actor,
            metadata={
                "action_id": action_id,
                "target_account_id": target_id if target_type == "account" else None,
            },
        )
        return action

    def _editable(self, db, case_id, expected_version):
        case = self.store.get(db, "cases", case_id)
        if not case:
            raise NotFoundError("Case not found")
        if case["version"] != expected_version:
            raise ConflictError(
                "Case changed since you opened it. Refresh and review the latest version.",
                version=case["version"],
                assignee=case.get("assignee"),
            )
        return case

    def decide(self, case_id, request: DecisionInput, actor: AnalystProfile):
        with self._lock, self.store.connect(write=True) as db:
            existing = self.store.get(db, "cases", case_id)
            # Checked before the role, so acting on the complainant is refused for every role.
            if (
                existing
                and existing.get("case_type") == "complaint"
                and request.action in {"close_account", "restrict", "place_lien"}
            ):
                reject_victim_target(existing, request.target_account_id)
            require(actor, request.action)
            case = self._editable(db, case_id, request.expected_version)
            return self._apply_decision(db, case, request, actor)

    def _check_decision_allowed(self, db, case, action, target):
        closes = [
            a
            for a in self.store.case_actions(db, case["case_id"])
            if a["operation"] == "close" and a["status"] != "superseded"
        ]
        if (action == "false_positive" and closes) or (
            action == "close_account"
            and any(a["target_id"] == (target or case["account_id"]) for a in closes)
        ):
            raise ConflictError("Final account closure has already been requested; reconcile its bank result")
        if case["verdict"] == "false_positive" and action != "file_ncrp_report":
            raise ConflictError(
                "A false-positive verdict is already recorded; its release must finish without a contradictory decision."
            )
        reversing_fraud = action in {"false_positive", "close_account"} and case["verdict"] == "fraud"
        if case["status"] == "resolved" and action != "file_ncrp_report" and not reversing_fraud:
            raise ConflictError("This case is resolved; its final verdict is already recorded.")

    def _confirm_fraud(self, db, case, actor):
        case.update(verdict="fraud", status="investigating")
        case_actions = self.store.case_actions(db, case["case_id"])
        default_target = protection_target(case, "restrict") if case.get("case_type") == "complaint" else None
        restrictions = [
            a
            for a in case_actions
            if a["operation"] == "restrict" and (default_target is None or a["target_id"] == default_target)
        ]
        if not restrictions:
            self._queue_action(db, case, "restrict", actor.username, target_id=default_target)
        elif any(a["status"] == "confirmed" for a in restrictions) and not any(
            a["status"] in {"pending", "failed"} for a in case_actions
        ):
            case["status"] = "resolved"

    def _clear_false_positive(self, db, case, actor):
        case.update(verdict="false_positive", status="investigating")
        protections = [
            a for a in self.store.case_actions(db, case["case_id"]) if a["operation"] in {"restrict", "lien"}
        ]
        releases = set()
        for action in protections:
            if action["status"] in {"pending", "failed"}:
                action.update(status="superseded", updated_at=now())
                self.store.update(db, "actions", action["action_id"], action)
                db.execute("UPDATE jobs SET done=1 WHERE id=?", (action["action_id"],))
            release = "release" if action["operation"] == "restrict" else "lien_release"
            releases.add((release, action["target_type"], action["target_id"]))
        # Release uncertain deliveries too; bank ownership protects other cases.
        for operation, target_type, target_id in sorted(releases):
            self._queue_action(
                db, case, operation, actor.username, target_type=target_type, target_id=target_id
            )
        if not releases:
            case["status"] = "resolved"

    def _apply_decision(self, db, case, request, actor):
        case_id = case["case_id"]
        action = request.action
        target = protection_target(case, action, request.target_account_id)
        self._check_decision_allowed(db, case, action, target)
        case.update(
            version=case["version"] + 1,
            updated_at=now(),
            assigned_to=case.get("assigned_to") or actor.display_name,
            notes=request.notes,
        )
        if action in {"investigate", "escalate"}:
            case["status"] = "investigating" if action == "investigate" else "escalated"
        elif action == "confirm_fraud":
            self._confirm_fraud(db, case, actor)
        elif action == "false_positive":
            self._clear_false_positive(db, case, actor)
        elif action == "close_account":
            if case["verdict"] != "fraud":
                raise ConflictError("Confirm fraud before requesting final account closure")
            self._queue_action(db, case, "close", actor.username, target_id=target)
            case["status"] = "investigating"
        elif action == "place_lien":
            self._queue_action(
                db, case, "lien", actor.username, amount_minor=request.amount_minor, target_id=target
            )
        elif action in {"restrict", "release_lien"}:
            operation = "restrict" if action == "restrict" else "lien_release"
            self._queue_action(db, case, operation, actor.username, target_id=target)
        elif action == "file_ncrp_report":
            case["ncrp_report"] = {
                "status": "recorded_in_simulation",
                "recorded_by": actor.username,
                "recorded_at": now(),
            }
        if case["status"] == "resolved":
            case.setdefault("resolved_at", now())
        self._save_case(db, case)
        self.store.event(
            db,
            "analyst_decision",
            f"{actor.display_name}: {action.replace('_', ' ')}. {request.notes}",
            case_id=case_id,
            txn_id=case["txn_id"],
            actor=actor.username,
            metadata={"action": action, "version": case["version"], "target_account_id": target},
        )
        return self._case(db, case_id)
