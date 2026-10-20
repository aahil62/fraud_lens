"""Bounded FIFO attribution, in causal time order, without duplicating funds."""

from collections import defaultdict, deque
from datetime import datetime, timedelta


def trace_funds(transactions, reported_txn, *, max_hops=4, window_hours=24):
    beneficiary = reported_txn.get("beneficiary_id")
    if not beneficiary or reported_txn.get("payment_status") != "posted":
        return []
    start = datetime.fromisoformat(reported_txn["timestamp"])
    end = start + timedelta(hours=window_hours)
    lots = defaultdict(deque)
    reached = {}

    def arrive(account, amount, hop, txn_id):
        row = reached.setdefault(
            account, dict(hop=hop, account_id=account, inbound_txn_ids=[], traced_minor=0, moved_minor=0)
        )
        row["hop"] = min(row["hop"], hop)
        if txn_id not in row["inbound_txn_ids"]:
            row["inbound_txn_ids"].append(txn_id)
        lots[account].append([amount, hop])

    arrive(beneficiary, reported_txn["amount_minor"], 1, reported_txn["txn_id"])
    outgoing = [
        t
        for t in transactions
        if t["txn_id"] != reported_txn["txn_id"]
        and t.get("payment_status") == "posted"
        and start <= datetime.fromisoformat(t["timestamp"]) < end
    ]
    for txn in sorted(outgoing, key=lambda t: (datetime.fromisoformat(t["timestamp"]), t["txn_id"])):
        sender, receiver = txn["account_id"], txn.get("beneficiary_id")
        if sender == receiver:
            continue
        remaining = txn["amount_minor"]
        while remaining and lots[sender]:
            lot = lots[sender][0]
            attributed = min(remaining, lot[0])
            lot[0] -= attributed
            remaining -= attributed
            hop = lot[1]
            if lot[0] == 0:
                lots[sender].popleft()
            if receiver and hop < max_hops:
                arrive(receiver, attributed, hop + 1, txn["txn_id"])
            else:
                reached[sender]["moved_minor"] += attributed
    for account, row in reached.items():
        row["traced_minor"] = sum(lot[0] for lot in lots[account])
    return sorted(reached.values(), key=lambda row: row["hop"])


def trace_view(case, actions):
    """Only a confirmed, unreleased lien contributes to recovered funds."""
    result = []
    for stored in case.get("trace", []):
        hop = {**stored, "lien_minor": 0}
        action = next((a for a in actions if a["action_id"] == hop.get("lien_action_id")), None)
        if action:
            hop["lien_status"] = action["status"]
            if action["status"] == "superseded":
                hop["outcome"] = "released"
            if action["status"] == "confirmed":
                hop["lien_minor"] = action["amount_minor"]
                hop["outcome"] = "held" if hop["lien_minor"] == hop["traced_minor"] else "partially_recovered"
                released = any(
                    a["operation"] == "lien_release"
                    and a["target_id"] == hop["account_id"]
                    and a["status"] == "confirmed"
                    and a["created_at"] >= action["created_at"]
                    for a in actions
                )
                if released:
                    hop.update(lien_minor=0, lien_status="released", outcome="released")
        result.append(hop)
    return result
