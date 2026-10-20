"""Read models: one case with its evidence, the console snapshot, and paged listings.

A snapshot builds up to 200 case views. The tables are read once and shared,
so its cost grows with the ledger, not with the ledger times the case count.
"""

import json
from collections import Counter

from .agent import priority
from .detector import CHANNELS, COVERAGE, VERSION
from .errors import NotFoundError
from .store import now
from .team import team_snapshot
from .trace import trace_view

# Actors that are not analysts; they never count as having handled a case.
AUTOMATED_ACTORS = {"system", "agent", "simulation", "attack-simulator"}
SNAPSHOT_LIMIT = 200
RELATED_LIMIT = 100
DEFAULT_SIMULATION = {"running": False, "interval_seconds": 5}
AGENT_EVENT_COUNTS = (
    "SELECT json_extract(data,'$.event_type'),COUNT(*) FROM events "
    "WHERE json_extract(data,'$.actor')='agent' GROUP BY json_extract(data,'$.event_type')"
)
AGENT_LIENS = (
    "SELECT json_extract(data,'$.metadata.action_id') FROM events "
    "WHERE json_extract(data,'$.event_type')='lien_requested' AND json_extract(data,'$.actor')='agent'"
)


def _by_key(rows, key):
    grouped = {}
    for row in rows:
        grouped.setdefault(row[key], []).append(row)
    return grouped


def _index_by_account(transactions):
    """Account id → [(position, transaction)], keeping the ledger's newest-first order."""
    index = {}
    for position, txn in enumerate(transactions):
        index.setdefault(txn["account_id"], []).append((position, txn))
    return index


def _related_transactions(case, by_account):
    accounts = {case["account_id"], *case["related_accounts"]}
    rows = sorted((row for account in accounts for row in by_account.get(account, [])), key=lambda r: r[0])
    return [txn for _, txn in rows[:RELATED_LIMIT]]


def _events_for(db, case_ids):
    """Each case's audit events, oldest first."""
    if not case_ids:
        return {}
    marks = ",".join("?" * len(case_ids))
    rows = db.execute(
        f"SELECT id,data FROM events WHERE json_extract(data,'$.case_id') IN ({marks}) ORDER BY id",
        list(case_ids),
    )
    return _by_key([{"id": r[0], **json.loads(r[1])} for r in rows], "case_id")


def _add_trace(case, actions, bank_state):
    """Fund-trace view of a complaint case, with live available balances and totals."""
    case["trace"] = trace_view(case, actions)
    if bank_state["connected"]:
        available = {a["account_id"]: a["available_minor"] for a in bank_state["accounts"]}
        for hop in case["trace"]:
            hop["available_minor"] = available.get(hop["account_id"], 0)
    victim = case["complaint"]["victim_account_id"]
    case["default_target_account_id"] = next(
        (h["account_id"] for h in case["trace"] if h["account_id"] != victim), None
    )
    case["traced_total_minor"] = sum(h["traced_minor"] for h in case["trace"])
    case["held_total_minor"] = sum(h["lien_minor"] for h in case["trace"])
    case["funds_moved_total_minor"] = sum(h["moved_minor"] for h in case["trace"])


def case_view(case, *, actions, events, by_account, bank_state, clock):
    """The full case the console shows: evidence, ownership, priority, actions and timeline."""
    case["related_transactions"] = _related_transactions(case, by_account)
    case.setdefault("assignee", None)
    case.setdefault("assigned_at", None)
    case.setdefault("pending_approval", None)
    case["handled_by"] = list(dict.fromkeys(e["actor"] for e in events if e["actor"] not in AUTOMATED_ACTORS))
    case["priority"], case["priority_reason"] = priority(case, clock)
    case["actions"] = actions
    case["timeline"] = events
    if case.get("case_type") == "complaint":
        _add_trace(case, actions, bank_state)
    return case


def _active_restrictions(actions):
    """(case, target type, target id) for confirmed restrictions not yet released, replayed oldest first."""
    active = set()
    for action in reversed(actions):
        if action["status"] != "confirmed":
            continue
        key = (action["case_id"], action["target_type"], action["target_id"])
        if action["operation"] == "restrict":
            active.add(key)
        elif action["operation"] == "release":
            active.discard(key)
    return active


def _counts(txns, cases, actions, actions_by_case):
    payments = Counter(t["payment_status"] for t in txns)
    statuses = Counter(c["status"] for c in cases)
    verdicts = Counter(c["verdict"] for c in cases)
    deliveries = Counter(a["status"] for a in actions)
    active = _active_restrictions(actions)
    held = sum(
        hop["lien_minor"] for c in cases for hop in trace_view(c, actions_by_case.get(c["case_id"], []))
    )
    return dict(
        transactions=len(txns),
        pending_payments=payments["pending"],
        posted=payments["posted"],
        declined=payments["declined"],
        cases=len(cases),
        pending_review=statuses["new"],
        investigating=statuses["investigating"],
        escalated=statuses["escalated"],
        resolved=statuses["resolved"],
        confirmed_fraud=verdicts["fraud"],
        false_positives=verdicts["false_positive"],
        pending_actions=deliveries["pending"],
        failed_actions=deliveries["failed"],
        traced_total_minor=sum(h["traced_minor"] for c in cases for h in c.get("trace", [])),
        held_total_minor=held,
        complaints=sum(c.get("case_type") == "complaint" for c in cases),
        restricted_accounts=len({target for _, kind, target in active if kind == "account"}),
        restricted_cards=len({target for _, kind, target in active if kind == "card"}),
    )


def _channel_rows(txns, cases):
    rows = []
    for channel in CHANNELS:
        channel_txns = [t for t in txns if t["channel"] == channel]
        channel_cases = [c for c in cases if c["channel"] == channel]
        rows.append(
            dict(
                channel=channel,
                transactions=len(channel_txns),
                cases=len(channel_cases),
                pending_review=sum(c["status"] == "new" for c in channel_cases),
                confirmed_fraud=sum(c["verdict"] == "fraud" for c in channel_cases),
                resolved=sum(c["status"] == "resolved" for c in channel_cases),
                declined=sum(t["payment_status"] == "declined" for t in channel_txns),
            )
        )
    return rows


def _queue_filter(view, username):
    return {
        "all": lambda c: True,
        "mine": lambda c: username is not None and c.get("assignee") == username,
        "unassigned": lambda c: not c.get("assignee"),
        "awaiting_approval": lambda c: bool(c.get("pending_approval")),
        "complaints": lambda c: c.get("case_type") == "complaint",
    }[view]


class SnapshotMixin:
    """Read models on OperationsService; uses its store, clock, analysts and bank state."""

    def _case(self, db, case_id):
        case = self.store.get(db, "cases", case_id)
        if not case:
            raise NotFoundError("Case not found")
        return case_view(
            case,
            actions=self.store.case_actions(db, case_id),
            events=_events_for(db, [case_id]).get(case_id, []),
            by_account=_index_by_account(self.store.records(db, "transactions")),
            bank_state=self.store.setting(db, "bank_state", self._bank_state),
            clock=self.clock(),
        )

    def get_case(self, case_id):
        with self.store.connect() as db:
            return self._case(db, case_id)

    def cursor(self):
        with self.store.connect() as db:
            return self.store.cursor(db)

    def _agent_state(self, db, actions):
        event_counts = dict(db.execute(AGENT_EVENT_COUNTS).fetchall())
        agent_liens = {r[0] for r in db.execute(AGENT_LIENS)}
        return dict(
            auto_assign=self.store.setting(db, "agent_auto_assign", False),
            briefs_drafted=event_counts.get("agent_brief_drafted", 0),
            cases_triaged=event_counts.get("agent_triaged", 0),
            cases_auto_assigned=event_counts.get("case_auto_assigned", 0),
            liens_placed=sum(
                a["operation"] == "lien" and a["status"] == "confirmed" and a["action_id"] in agent_liens
                for a in actions
            ),
        )

    def snapshot(self):
        with self.store.connect() as db:
            txns = self.store.records(db, "transactions")
            cases = self.store.records(db, "cases")
            actions = self.store.records(db, "actions")
            actions_by_case = _by_key(actions, "case_id")
            recent = cases[:SNAPSHOT_LIMIT]
            events = _events_for(db, [c["case_id"] for c in recent])
            by_account = _index_by_account(txns)
            bank_state = self.store.setting(db, "bank_state", self._bank_state)
            views = [
                case_view(
                    dict(c),
                    actions=actions_by_case.get(c["case_id"], []),
                    events=events.get(c["case_id"], []),
                    by_account=by_account,
                    bank_state=bank_state,
                    clock=self.clock(),
                )
                for c in recent
            ]
            return dict(
                cursor=self.store.cursor(db),
                as_of=now(),
                simulation=True,
                counts=_counts(txns, cases, actions, actions_by_case),
                channels=_channel_rows(txns, cases),
                agent=self._agent_state(db, actions),
                transactions=txns[:SNAPSHOT_LIMIT],
                cases=views,
                actions=actions[:SNAPSHOT_LIMIT],
                events=self.store.events(db),
                team=team_snapshot(db, cases, self.analysts, self.clock()),
                approvals=[
                    {"case_id": c["case_id"], **c["pending_approval"]}
                    for c in cases
                    if c.get("pending_approval")
                ],
                bank=bank_state,
                simulation_state=self.store.setting(db, "simulation", DEFAULT_SIMULATION),
                detection={"version": VERSION, "coverage": COVERAGE},
            )

    def listing(self, kind, limit=50, offset=0, channel=None, status=None, view="all", username=None):
        with self.store.connect() as db:
            items = self.store.records(db, kind)
            if channel:
                items = [v for v in items if v["channel"] == channel]
            if status:
                items = [v for v in items if v.get("status") == status]
            if kind == "cases":
                keep = _queue_filter(view, username)
                items = [
                    {**c, **dict(zip(("priority", "priority_reason"), priority(c, self.clock())))}
                    for c in items
                    if keep(c)
                ]
                items.sort(key=lambda c: -c["priority"])
            return {"items": items[offset : offset + limit], "total": len(items)}
