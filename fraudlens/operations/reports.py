"""Timestamped operational reports; exports never claim an actual bank filing."""
from fpdf import FPDF
from fpdf.enums import XPos, YPos

from .store import now


def report(case):
    return {"case_id": case["case_id"], "generated_at": now(), "case_version": case["version"], "simulation": True,
            "case": case, "disclaimer": "Simulated transactions and bank actions. Analyst verdict is not a regulatory classification or filing. Risk scores are not calibrated probabilities."}


def markdown(value):
    case = value["case"]
    lines = [f"# FraudLens investigation report: {case['case_id']}", "", value["disclaimer"], "",
             f"Generated: {value['generated_at']} | Case version: {value['case_version']}", "",
             f"Channel: {case['channel']} | Account reference: {case['account_id']}",
             f"Amount: INR {case['amount_minor'] / 100:,.2f} | Risk score: {case['score']:.3f}",
             f"Case status: {case['status']} | Analyst verdict: {case['verdict']}",
             f"Analyst: {case['assigned_to'] or 'Unassigned'}", f"Notes: {case['notes'] or 'No analyst notes yet.'}", "",
             "## Detection evidence", ""]
    for signal in case["signals"]:
        lines.append(f"- {signal['name']} ({signal['score']:.3f}): {'; '.join(signal['reasons'])}")
    lines.extend(["", "## Bank actions", ""])
    for action in reversed(case["actions"]):
        lines.append(f"- {action['created_at']}: {action['operation']} {action['target_type']} {action['target_id']}; {action['status']}; bank reference {action['bank_reference'] or 'not acknowledged'}")
    lines.extend(["", "## Audit timeline", ""])
    for event in case["timeline"]:
        lines.append(f"- {event['occurred_at']} | {event['actor']} | {event['message']}")
    return "\n".join(lines) + "\n"


def pdf(value):
    doc = FPDF()
    doc.set_auto_page_break(auto=True, margin=18)
    doc.add_page()
    doc.set_font("Helvetica", size=10)
    # Preserve unsupported characters reversibly instead of dropping them.
    # JSON/Markdown exports carry the original Unicode text.
    text = markdown(value).replace("₹", "INR ")
    escaped = "".join(c if ord(c) < 128 else c.encode("unicode_escape").decode("ascii") for c in text)
    for line in escaped.splitlines():
        doc.multi_cell(0, 5, line or " ", new_x=XPos.LMARGIN, new_y=YPos.NEXT, wrapmode="CHAR")
    return bytes(doc.output())
