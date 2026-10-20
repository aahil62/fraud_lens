"""Case ownership (claim, assign) and the L1 → L2 → Supervisor approval flow."""

from uuid import uuid4

from fraudlens.core.auth.roles import can, required_role

from .decisions import protection_target
from .errors import ConflictError, NotFoundError, OperationError
from .models import DecisionInput
from .store import now
from .team import require


class ApprovalsMixin:
    """Ownership and approvals on OperationsService; uses its store, lock, analysts and decisions."""

    def claim(self, case_id, request, actor):
        require(actor, "claim")
        with self._lock, self.store.connect(write=True) as db:
            case = self._editable(db, case_id, request.expected_version)
            owner = case.get("assignee")
            if owner and owner != actor.username:
                account = self.analysts.get(owner) if self.analysts else None
                raise ConflictError(
                    f"Case is assigned to {account.display_name if account else owner}",
                    assignee=owner,
                    version=case["version"],
                )
            self._assign_case(db, case, actor, actor, "case_claimed")
            return self._case(db, case_id)

    def _assign_case(self, db, case, target, actor, event_type):
        case.update(
            assignee=target.username,
            assigned_to=target.display_name,
            assigned_at=now(),
            updated_at=now(),
            version=case["version"] + 1,
        )
        self._save_case(db, case)
        self.store.event(
            db,
            event_type,
            f"{actor.display_name} assigned the case to {target.display_name}.",
            case_id=case["case_id"],
            actor=actor.username,
        )

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
            target = protection_target(case, request.action, request.target_account_id)
            case["pending_approval"] = dict(
                approval_id=f"APR-{uuid4().hex}",
                action=request.action,
                requested_by=actor.username,
                required_role=required_role(request.action),
                notes=request.notes,
                requested_at=now(),
                target_account_id=target,
            )
            case.update(version=case["version"] + 1, updated_at=now())
            self._save_case(db, case)
            self.store.event(
                db,
                "approval_requested",
                f"{actor.display_name} requested {request.action}: {request.notes}",
                case_id=case_id,
                actor=actor.username,
                metadata=case["pending_approval"],
            )
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
                decision = DecisionInput(
                    action=approval["action"],
                    expected_version=case["version"],
                    notes=approval["notes"],
                    target_account_id=approval.get("target_account_id"),
                )
                self._apply_decision(db, case, decision, actor)
                message = f"Approved by {actor.display_name} (requested by {name})"
            else:
                case.update(version=case["version"] + 1, updated_at=now())
                self._save_case(db, case)
                message = f"Rejected by {actor.display_name} (requested by {name}): {request.notes}"
            self.store.event(
                db,
                "approval_approved" if request.approve else "approval_rejected",
                message,
                case_id=case_id,
                actor=actor.username,
                metadata={**approval, "decision_notes": request.notes},
            )
            return self._case(db, case_id)
