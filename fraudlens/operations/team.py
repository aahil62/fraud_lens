"""Permission and presence helpers; mutations stay in the service transaction."""

from datetime import datetime

from fraudlens.core.auth.roles import ROLE_LABEL, can, required_role
from fraudlens.models.schemas import AnalystProfile


class OperationError(ValueError):
    def __init__(self, detail, *, status_code=400, **fields):
        super().__init__(detail)
        self.status_code = status_code
        self.payload = {"detail": detail, **fields}


def require(actor, action):
    if not isinstance(actor, AnalystProfile) or not can(actor.role, action):
        raise OperationError(
            "This action requires a higher analyst role", status_code=403, required_role=required_role(action)
        )


def team_snapshot(db, cases, analysts, clock):
    presence = {row["username"]: dict(row) for row in db.execute("SELECT * FROM presence")}
    roster = (
        {a.username: a.model_dump(include={"username", "display_name", "role"}) for a in analysts.list()}
        if analysts
        else {}
    )
    roster.update(
        {
            name: {k: value[k] for k in ("username", "display_name", "role")}
            for name, value in presence.items()
        }
    )
    result = []
    for username, member in sorted(roster.items()):
        seen = presence.get(username, {})
        online = bool(
            seen.get("last_seen")
            and 0 <= (clock - datetime.fromisoformat(seen["last_seen"])).total_seconds() <= 45
        )
        result.append(
            {
                **member,
                "role_label": ROLE_LABEL[member["role"]],
                "online": online,
                "last_seen": seen.get("last_seen"),
                "current_case_id": seen.get("current_case_id") if online else None,
                "open_assigned": sum(
                    c.get("assignee") == username and c["status"] != "resolved" for c in cases
                ),
                "resolved_today": sum(
                    c.get("assignee") == username
                    and c["status"] == "resolved"
                    and c.get("resolved_at", c["updated_at"])[:10] == clock.date().isoformat()
                    for c in cases
                ),
            }
        )
    return result
