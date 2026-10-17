"""History-aware scoring plus explicit, versioned showcase control rules.

Risk scores are prioritization scores, not calibrated fraud probabilities.
ML is a reference model trained on a separate synthetic corpus. Current
stream labels never enter inference; future events are excluded.
"""
from datetime import datetime, timedelta
from functools import lru_cache

from fraudlens.core.scoring.behavioral_agent import BehavioralAgent
from fraudlens.core.scoring.graph_agent import GraphAgent
from fraudlens.core.scoring.ml_agent import MLAgent
from fraudlens.core.scoring.rule_agent import RuleAgent
from fraudlens.core.scoring.velocity_agent import VelocityAgent
from fraudlens.data.synthetic_generator import generate_synthetic_transactions
from fraudlens.models.schemas import Transaction

VERSION = "showcase-policy-1.1"
CHANNELS = ("upi", "net_banking", "card", "atm")
COVERAGE = [
    {"channel": "upi", "scenarios": ["New-device beneficiary transfer", "Payment burst", "Shared-device network"],
     "limitations": "No intent, PIN or scam-message visibility; social-engineering detection is incomplete."},
    {"channel": "net_banking", "scenarios": ["Failed-authentication takeover", "New beneficiary transfer", "Cross-channel burst"],
     "limitations": "Authentication and device novelty are supplied test telemetry, not collected from a real bank."},
    {"channel": "card", "scenarios": ["Card-testing burst", "Credential anomalies", "Unusual spending"],
     "limitations": "Linked simulated payment instruments, not production credit-card accounts or network authorization."},
    {"channel": "atm", "scenarios": ["Rapid withdrawals", "New-device withdrawal", "Location change"],
     "limitations": "Transaction telemetry only; no ATM camera, physical-skimmer, or hardware compromise detection."},
]


@lru_cache(maxsize=1)
def reference_model():
    model = MLAgent()
    model.fit(generate_synthetic_transactions(seed=173))
    return model


def legacy(txn):
    return Transaction(txn_id=txn["txn_id"], account_id=txn["account_id"], amount=txn["amount_minor"] / 100,
                       timestamp=txn["timestamp"], merchant_id=txn["merchant_id"], merchant_category="retail",
                       device_id=txn["device_id"], ip_address=txn["ip_address"], location=txn["location"], channel=txn["channel"])


def detect(txn, history):
    current_time = datetime.fromisoformat(txn["timestamp"])
    prior = [t for t in history if datetime.fromisoformat(t["timestamp"]) <= current_time]
    # Bounded lookback is explicit; do not allow an unbounded live stream to
    # turn a per-event graph rebuild into quadratic session growth.
    prior = sorted(prior, key=lambda t: t["timestamp"])[-1000:]
    mapped = [legacy(t) for t in prior]
    current = legacy(txn)
    velocity = VelocityAgent()
    velocity.set_transactions(mapped)
    behavioral = BehavioralAgent()
    behavioral.build_profiles(mapped)
    graph = GraphAgent()
    graph.build_index(mapped + [current])
    signals = [a.score(current).model_dump() for a in (RuleAgent(), velocity, behavioral, graph, reference_model())]
    policy = 0.05
    reasons = []

    def flag(score, reason):
        nonlocal policy
        policy = max(policy, score)
        reasons.append(reason)

    recent = [t for t in prior if t["account_id"] == txn["account_id"] and
              current_time - timedelta(minutes=5) <= datetime.fromisoformat(t["timestamp"])]
    if txn["failed_auth_attempts"] >= 3 and txn["new_device"]:
        flag(0.94, "Repeated authentication failures followed by payment from a new device.")
    if txn["new_device"] and txn["new_beneficiary"] and txn["amount_minor"] >= 2_000_000:
        flag(0.91, "Large transfer to a new beneficiary from a new device.")
    if txn["channel"] == "net_banking" and txn["failed_auth_attempts"] >= 3 and txn["new_beneficiary"]:
        flag(0.95, "New beneficiary payment after repeated net-banking authentication failures.")
    shared_accounts = {t["account_id"] for t in prior if t["account_id"] != txn["account_id"] and
                       t["device_id"] == txn["device_id"]}
    if txn["channel"] == "upi" and len(shared_accounts) >= 2 and txn["new_beneficiary"] and txn["amount_minor"] >= 1_000_000:
        flag(0.90, "Large new-beneficiary payment from a device shared by three or more accounts.")
    if len(recent) >= 4:
        flag(0.87, f"{len(recent) + 1} attempted payments from this account within five minutes.")
    if len({t["channel"] for t in recent} | {txn["channel"]}) >= 3 and (txn["new_device"] or txn["failed_auth_attempts"]):
        flag(0.93, "Rapid activity across three or more channels with device or authentication anomalies.")
    if txn["channel"] == "card":
        small = [t for t in recent if t.get("instrument_id") == txn["instrument_id"] and t["amount_minor"] <= 80_000]
        if len(small) >= 3 and txn["amount_minor"] <= 80_000:
            flag(0.92, "Four or more small attempts on the same card suggest card testing.")
    if txn["channel"] == "atm":
        withdrawals = [t for t in recent if t["channel"] == "atm"]
        if any(t["location"] != txn["location"] for t in withdrawals):
            flag(0.89 if txn["amount_minor"] >= 1_000_000 else 0.62,
                 "ATM withdrawal at a changed location within five minutes; amount determines protection versus review.")
        if len(withdrawals) >= 2 and sum(t["amount_minor"] for t in withdrawals) + txn["amount_minor"] >= 3_000_000:
            flag(0.90, "Rapid ATM withdrawals exceed the showcase withdrawal-burst threshold.")
        if txn["new_device"] and txn["amount_minor"] >= 1_000_000:
            flag(0.88, "High-value withdrawal at a new test terminal/device.")
    if txn["new_device"] and txn["amount_minor"] >= 500_000 and policy < 0.8:
        flag(0.58, "New-device payment requires analyst review; protective threshold not reached.")

    signals.append({"agent_name": "channel_policy", "score": policy, "reasons": reasons or ["No supported channel-control pattern matched."]})
    score = round(max(policy, sum(s["score"] * w for s, w in zip(signals[:5], (.15, .15, .15, .1, .1)))), 4)
    display = [{"name": s["agent_name"], "score": s["score"], "reasons": s["reasons"]} for s in signals]
    if not reasons:
        reasons = [r for s in signals[:5] if s["score"] >= .5 for r in s["reasons"]][:5]
    return {"score": score, "signals": display, "reasons": reasons,
            "related_accounts": sorted({t["account_id"] for t in prior if t["account_id"] != txn["account_id"] and
                                         t["device_id"] == txn["device_id"]})[:30]}
