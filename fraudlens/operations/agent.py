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
    terms = [(55 * case["score"], f"{'High risk score' if case['score'] >= .8 else 'Risk score'} ({case['score']:.2f})"),
             (15 * min(1, case["amount_minor"] / 10000000), "Payment value"),
             (10 * min(1, age / 60), "Waiting for review"),
             (20 * (case.get("case_type") == "complaint"), "1930 complaint")]
    reason = " · ".join(label for value, label in sorted(terms, key=lambda term: term[0], reverse=True)[:2])
    return max(0, min(100, round(sum(value for value, _ in terms)))), reason


def masked(identifier):
    if not identifier:
        return "not supplied"
    return f"…{identifier[-4:]}" if len(identifier) > 4 else "••••"


def build_brief(case, transactions, actions):
    reasons = " ".join(case.get("reasons", [])).lower()
    typology = next((label for phrase, label in (
        ("pass-through", "Mule pass-through"), ("card testing", "Card testing"),
        ("sim-swap", "SIM-swap account takeover"), ("atm burst", "ATM cash-out burst"),
        ("rapid atm", "ATM cash-out burst"), ("attempted payments", "Velocity"),
        ("large transfer", "High-value new device"), ("new-device", "High-value new device")) if phrase in reasons), "Unusual activity")
    complaint = case.get("complaint")
    victim = complaint["victim_account_id"] if complaint else None
    trace = case.get("trace", [])
    closed = {a["target_id"] for a in actions if a["operation"] == "close" and a["status"] in {"pending", "confirmed", "failed"}}
    recipients = [h for h in trace if h["account_id"] != victim and h["account_id"] not in closed]
    target = recipients[0]["account_id"] if recipients else None
    protected = any(a["operation"] in {"restrict", "lien", "close"} and a["status"] == "confirmed" for a in actions)
    action = "investigate"
    amount = None
    if case["verdict"] == "false_positive":
        action = "investigate"
    elif case["verdict"] == "fraud":
        if (complaint and target) or (not complaint and case["account_id"] not in closed):
            action = "close_account"
            target = target if complaint else case["account_id"]
    elif complaint and not case.get("trace_prepared", False) and target:
        action = "place_lien"
        hop = recipients[0]
        amount = min(hop["traced_minor"], hop.get("available_minor", 0))
    elif case["score"] >= .8 and not protected:
        action = "restrict" if not complaint or target else "investigate"
    elif protected and case["score"] >= .85:
        action = "confirm_fraud"
    elif case["score"] < .5 and not complaint:
        action = "false_positive"
    role = required_role(action)
    root = next((t for t in transactions if t["txn_id"] == case["txn_id"]), {})
    occurred = datetime.fromisoformat(complaint["reported_at"] if complaint else root.get("timestamp", case["created_at"])).astimezone(ZoneInfo("Asia/Kolkata"))
    source = {"1930_helpline": "1930 helpline", "ncrp_portal": "NCRP portal", "branch": "bank branch"}.get(complaint["source"] if complaint else "", "bank telemetry")
    channel = {"upi": "UPI", "net_banking": "net banking", "card": "card", "atm": "ATM"}[case["channel"]]
    narrative = (f"On {occurred:%d %b %Y} IST at {occurred:%H:%M} IST, a {channel} payment of {inr(case['amount_minor'])} "
                 f"from account {masked(case['account_id'])} to {masked(root.get('beneficiary_id'))} was reported via {source}.")
    if complaint:
        narrative += (f" FraudLens traced {inr(case.get('traced_total_minor', sum(h['traced_minor'] for h in trace)))} across {len(trace)} account(s) "
                      f"and placed holds on {inr(case.get('held_total_minor', sum(h.get('lien_minor', 0) for h in trace)))}.")
    narrative += f" Case {case['case_id']}."
    summary = f"{typology} signals on a {channel} payment of {inr(case['amount_minor'])}; analyst review is required."
    if case["verdict"] == "fraud":
        summary = f"An analyst confirmed fraud on the {channel} payment of {inr(case['amount_minor'])}; review the remaining protection actions."
    elif case["verdict"] == "false_positive":
        summary = f"An analyst cleared the {channel} alert for {inr(case['amount_minor'])}; verify bank releases."
    next_steps = ["Review the transaction evidence and bank acknowledgements.",
                  f"{ROLE_LABEL[role]}: review the recommended {action.replace('_', ' ')} action.",
                  "Record a rationale; this draft does not submit an external report."]
    return dict(typology=typology, summary=summary, evidence=list(case.get("reasons", []))[:5],
                recommended_action=action, target_account_id=target if complaint or action == "close_account" else None,
                amount_minor=amount, required_role=role, required_role_label=ROLE_LABEL[role],
                confidence="high" if case["score"] >= .85 else "medium" if case["score"] >= .6 else "low",
                next_steps=next_steps[:4], ncrp_narrative=narrative, generated_by="template")


def polish_summary(summary, facts):
    if os.environ.get("FRAUDLENS_LLM") != "ollama":
        return summary
    try:
        response = httpx.post("http://127.0.0.1:11434/api/generate", timeout=6, trust_env=False, json={
            "model": os.environ.get("FRAUDLENS_LLM_MODEL", "qwen2.5:7b-instruct"), "stream": False,
            "prompt": "Rewrite only this summary sentence, preserving all facts, amounts and uncertainty. No extra claims or instructions. Return only the sentence.\n" + json.dumps({"summary": summary, "facts": facts})})
        response.raise_for_status()
        rewritten = response.json()["response"].strip()
        if not rewritten or len(rewritten) > 1200:
            return summary
        def amounts(text):
            return Counter(int(Decimal(token.replace(",", "")) * 100) for token in re.findall(r"₹\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)(?![0-9]|\.[0-9])", text))
        original = amounts(summary)
        permitted = {value for key, value in facts.items() if key.endswith("_minor") and isinstance(value, int)}
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
