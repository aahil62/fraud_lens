"""History-aware scoring plus explicit, versioned showcase control rules.

Risk scores are prioritization scores, not calibrated fraud probabilities.
ML is a reference model trained on a separate synthetic corpus. Current
stream labels never enter inference; future events are excluded.
"""

from datetime import datetime
from functools import lru_cache

from fraudlens.core.scoring.behavioral_agent import BehavioralAgent
from fraudlens.core.scoring.graph_agent import GraphAgent
from fraudlens.core.scoring.ml_agent import MLAgent
from fraudlens.core.scoring.rule_agent import RuleAgent
from fraudlens.core.scoring.velocity_agent import VelocityAgent
from fraudlens.data.synthetic_generator import generate_synthetic_transactions
from fraudlens.models.schemas import Transaction

from .rules import History, channel_policy, shared_device_accounts

VERSION = "showcase-policy-1.2"
CHANNELS = ("upi", "net_banking", "card", "atm")
COVERAGE = [
    {
        "channel": "upi",
        "scenarios": [
            "New-device beneficiary transfer",
            "Payment burst",
            "Shared-device network",
            "Mule pass-through",
        ],
        "limitations": "No intent, PIN or scam-message visibility; social-engineering detection is incomplete.",
    },
    {
        "channel": "net_banking",
        "scenarios": [
            "Failed-authentication takeover",
            "New beneficiary transfer",
            "Cross-channel burst",
            "SIM-swap takeover pattern",
        ],
        "limitations": "Authentication and device novelty are supplied test telemetry, not collected from a real bank.",
    },
    {
        "channel": "card",
        "scenarios": [
            "Card-testing burst",
            "Credential anomalies",
            "Unusual spending",
            "Small tests followed by larger payment",
        ],
        "limitations": "Linked simulated payment instruments, not production credit-card accounts or network authorization.",
    },
    {
        "channel": "atm",
        "scenarios": [
            "Rapid withdrawals",
            "New-device withdrawal",
            "Location change",
            "Burst across terminals",
        ],
        "limitations": "Transaction telemetry only; no ATM camera, physical-skimmer, or hardware compromise detection.",
    },
]


@lru_cache(maxsize=1)
def reference_model():
    model = MLAgent()
    model.fit(generate_synthetic_transactions(seed=173))
    return model


def legacy(txn):
    return Transaction(
        txn_id=txn["txn_id"],
        account_id=txn["account_id"],
        amount=txn["amount_minor"] / 100,
        timestamp=txn["timestamp"],
        merchant_id=txn["merchant_id"],
        merchant_category="retail",
        device_id=txn["device_id"],
        ip_address=txn["ip_address"],
        location=txn["location"],
        channel=txn["channel"],
    )


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
    signals = [
        a.score(current).model_dump() for a in (RuleAgent(), velocity, behavioral, graph, reference_model())
    ]
    policy, reasons = channel_policy(txn, prior)

    signals.append(
        {
            "agent_name": "channel_policy",
            "score": policy,
            "reasons": reasons or ["No supported channel-control pattern matched."],
        }
    )
    score = round(
        max(policy, sum(s["score"] * w for s, w in zip(signals[:5], (0.15, 0.15, 0.15, 0.1, 0.1)))), 4
    )
    display = [{"name": s["agent_name"], "score": s["score"], "reasons": s["reasons"]} for s in signals]
    if not reasons:
        reasons = [r for s in signals[:5] if s["score"] >= 0.5 for r in s["reasons"]][:5]
    return {
        "score": score,
        "signals": display,
        "reasons": reasons,
        "related_accounts": sorted(shared_device_accounts(History.build(txn, prior)))[:30],
    }
