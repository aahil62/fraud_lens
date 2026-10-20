"""One permission table shared by authenticated operational actions."""

from typing import Literal

Role = Literal["l1_analyst", "l2_analyst", "supervisor"]
ROLE_RANK: dict[Role, int] = {"l1_analyst": 1, "l2_analyst": 2, "supervisor": 3}
ROLE_LABEL: dict[Role, str] = {
    "l1_analyst": "L1 Analyst",
    "l2_analyst": "L2 Senior Analyst",
    "supervisor": "Fraud Supervisor",
}
ACTION_MIN_ROLE: dict[str, Role] = {
    "claim": "l1_analyst",
    "investigate": "l1_analyst",
    "escalate": "l1_analyst",
    "place_lien": "l1_analyst",
    "release_lien": "l2_analyst",
    "restrict": "l2_analyst",
    "confirm_fraud": "l2_analyst",
    "false_positive": "l2_analyst",
    "assign": "l2_analyst",
    "approve_l2": "l2_analyst",
    "close_account": "supervisor",
    "file_ncrp_report": "supervisor",
    "approve_supervisor": "supervisor",
    "agent_settings": "supervisor",
}


def can(role: Role, action: str) -> bool:
    minimum = ACTION_MIN_ROLE.get(action)
    return minimum is not None and ROLE_RANK.get(role, 0) >= ROLE_RANK[minimum]


def required_role(action: str) -> Role:
    try:
        return ACTION_MIN_ROLE[action]
    except KeyError as exc:
        raise ValueError("Unknown operational action") from exc
