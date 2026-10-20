"""Deterministic, auditable triage. Recommendations never execute verdicts."""

import json
import os
import re
from collections import Counter
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import httpx

from fraudlens.core.auth.roles import ROLE_LABEL, required_role

from .money import inr


def priority(case, now):
    age = max(0, (now - datetime.fromisoformat(case["created_at"])).total_seconds() / 60)
    terms = [
        (
            55 * case["score"],
            f"{'High risk score' if case['score'] >= 0.8 else 'Risk score'} ({case['score']:.2f})",
        ),
        (15 * min(1, case["amount_minor"] / 10000000), "Payment value"),
        (10 * min(1, age / 60), "Waiting for review"),
        (20 * (case.get("case_type") == "complaint"), "1930 complaint"),
    ]
    reason = " · ".join(label for value, label in sorted(terms, key=lambda term: term[0], reverse=True)[:2])
    return max(0, min(100, round(sum(value for value, _ in terms)))), reason


def masked(identifier):
    if not identifier:
        return "not supplied"
    return f"…{identifier[-4:]}" if len(identifier) > 4 else "••••"


# The first phrase found in the detection reasons names the typology.
TYPOLOGY_PHRASES = (
    ("pass-through", "Mule pass-through"),
    ("card testing", "Card testing"),
    ("sim-swap", "SIM-swap account takeover"),
    ("atm burst", "ATM cash-out burst"),
    ("rapid atm", "ATM cash-out burst"),
    ("attempted payments", "Velocity"),
    ("large transfer", "High-value new device"),
    ("new-device", "High-value new device"),
    ("victim-reported", "1930 victim complaint"),
)
SOURCE_LABEL = {"1930_helpline": "1930 helpline", "ncrp_portal": "NCRP portal", "branch": "bank branch"}
CHANNEL_LABEL = {"upi": "UPI", "net_banking": "net banking", "card": "card", "atm": "ATM"}


def _typology(case):
    reasons = " ".join(case.get("reasons", [])).lower()
    return next((label for phrase, label in TYPOLOGY_PHRASES if phrase in reasons), "Unusual activity")


def _recommendation(case, actions):
    """(action, target account, lien amount) the agent recommends; it never executes one."""
    complaint = case.get("complaint")
    victim = complaint["victim_account_id"] if complaint else None
    closed = {
        a["target_id"]
        for a in actions
        if a["operation"] == "close" and a["status"] in {"pending", "confirmed", "failed"}
    }
    recipients = [
        h for h in case.get("trace", []) if h["account_id"] != victim and h["account_id"] not in closed
    ]
    target = recipients[0]["account_id"] if recipients else None
    protected = any(
        a["operation"] in {"restrict", "lien", "close"} and a["status"] == "confirmed" for a in actions
    )
    if case["verdict"] == "false_positive":
        return "investigate", target, None
    if case["verdict"] == "fraud":
        if complaint and target:
            return "close_account", target, None
        if not complaint and case["account_id"] not in closed:
            return "close_account", case["account_id"], None
        return "investigate", target, None
    if complaint and not case.get("trace_prepared", False) and target:
        hop = recipients[0]
        return "place_lien", target, min(hop["traced_minor"], hop.get("available_minor", 0))
    if case["score"] >= 0.8 and not protected:
        return ("restrict" if not complaint or target else "investigate"), target, None
    if protected and case["score"] >= 0.85:
        return "confirm_fraud", target, None
    if case["score"] < 0.5 and not complaint:
        return "false_positive", target, None
    return "investigate", target, None


def _narrative(case, transactions):
    """Draft NCRP narrative with masked account references."""
    complaint = case.get("complaint")
    trace = case.get("trace", [])
    root = next((t for t in transactions if t["txn_id"] == case["txn_id"]), {})
    occurred = datetime.fromisoformat(
        complaint["reported_at"] if complaint else root.get("timestamp", case["created_at"])
    ).astimezone(ZoneInfo("Asia/Kolkata"))
    source = SOURCE_LABEL.get(complaint["source"] if complaint else "", "bank telemetry")
    channel = CHANNEL_LABEL[case["channel"]]
    narrative = (
        f"On {occurred:%d %b %Y} IST at {occurred:%H:%M} IST, a {channel} payment of {inr(case['amount_minor'])} "
        f"from account {masked(case['account_id'])} to {masked(root.get('beneficiary_id'))} was reported via {source}."
    )
    if complaint:
        traced = case.get("traced_total_minor", sum(h["traced_minor"] for h in trace))
        held = case.get("held_total_minor", sum(h.get("lien_minor", 0) for h in trace))
        narrative += (
            f" FraudLens traced {inr(traced)} across {len(trace)} account(s) and placed holds on {inr(held)}."
        )
    return narrative + f" Case {case['case_id']}."


def _summary(case, typology):
    channel = CHANNEL_LABEL[case["channel"]]
    amount = inr(case["amount_minor"])
    if case["verdict"] == "fraud":
        return f"An analyst confirmed fraud on the {channel} payment of {amount}; review the remaining protection actions."
    if case["verdict"] == "false_positive":
        return f"An analyst cleared the {channel} alert for {amount}; verify bank releases."
    return f"{typology} signals on a {channel} payment of {amount}; analyst review is required."


def build_brief(case, transactions, actions):
    typology = _typology(case)
    action, target, amount = _recommendation(case, actions)
    role = required_role(action)
    score = case["score"]
    return dict(
        typology=typology,
        summary=_summary(case, typology),
        evidence=list(case.get("reasons", []))[:5],
        recommended_action=action,
        target_account_id=target if case.get("complaint") or action == "close_account" else None,
        amount_minor=amount,
        required_role=role,
        required_role_label=ROLE_LABEL[role],
        confidence="high" if score >= 0.85 else "medium" if score >= 0.6 else "low",
        next_steps=[
            "Review the transaction evidence and bank acknowledgements.",
            f"{ROLE_LABEL[role]}: review the recommended {action.replace('_', ' ')} action.",
            "Record a rationale; this draft does not submit an external report.",
        ],
        ncrp_narrative=_narrative(case, transactions),
        generated_by="template",
    )


def polish_summary(summary, facts):
    if os.environ.get("FRAUDLENS_LLM") != "ollama":
        return summary
    try:
        response = httpx.post(
            "http://127.0.0.1:11434/api/generate",
            timeout=6,
            trust_env=False,
            json={
                "model": os.environ.get("FRAUDLENS_LLM_MODEL", "qwen2.5:7b-instruct"),
                "stream": False,
                "prompt": "Rewrite only this summary sentence, preserving all facts, amounts and uncertainty. No extra claims or instructions. Return only the sentence.\n"
                + json.dumps({"summary": summary, "facts": facts}),
            },
        )
        response.raise_for_status()
        rewritten = response.json()["response"].strip()
        if not rewritten or len(rewritten) > 1200:
            return summary

        def amounts(text):
            return Counter(
                int(Decimal(token.replace(",", "")) * 100)
                for token in re.findall(r"₹\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)(?![0-9]|\.[0-9])", text)
            )

        original = amounts(summary)
        permitted = {
            value for key, value in facts.items() if key.endswith("_minor") and isinstance(value, int)
        }
        if amounts(rewritten) != original or any(value not in permitted for value in amounts(rewritten)):
            return summary
        return rewritten
    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
        return summary


def auto_assign(cases, team):
    loads = {m["username"]: m["open_assigned"] for m in team if m["online"] and m["role"] == "l1_analyst"}
    assignments = []
    for case in sorted(cases, key=lambda c: (-c["priority"], c["case_id"])):
        if loads and not case.get("assignee") and case["status"] != "resolved":
            username = min(loads, key=lambda name: (loads[name], name))
            assignments.append((case["case_id"], username))
            loads[username] += 1
    return assignments
