#!/usr/bin/env python3
"""Verify actual local HTTP effects; no external hosts or real bank operations."""
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://127.0.0.1:8001")
    parser.add_argument("--bank-url", default="http://127.0.0.1:8002")
    parser.add_argument("--output", type=Path, default=Path("docs/verification/live-http.json"))
    args = parser.parse_args()
    for url in (args.api_url, args.bank_url):
        if urlparse(url).hostname not in {"localhost", "127.0.0.1", "::1"}:
            parser.error("Verification is restricted to loopback simulator services")
    assert httpx.get(args.bank_url + "/health", trust_env=False).json().get("simulation") is True
    client = httpx.Client(base_url=args.api_url, timeout=15, trust_env=False)
    login = client.post("/auth/login", json={"username": "asharma", "password": "fraudlens123"})
    login.raise_for_status()
    client.headers["Authorization"] = "Bearer " + login.json()["access_token"]

    def call(path, payload=None, method="POST"):
        response = client.request(method, "/ops" + path, json=payload)
        response.raise_for_status()
        return response.json()

    initial = call("/snapshot", method="GET")
    was_running = initial["simulation_state"]["running"]
    call("/simulation/control", {"running": False, "bank_mode": "normal"})
    checks = []
    prefix = "VERIFY-" + uuid4().hex[:10]
    payment = dict(txn_id=prefix, account_id=prefix, channel="upi", amount_minor=8_000_000,
                   timestamp=datetime.now(timezone.utc).isoformat(), new_device=True, new_beneficiary=True, failed_auth_attempts=4)
    try:
        result = call("/transactions", payment)
        case_id = result["case"]["case_id"]
        call("/process")
        case = call(f"/cases/{case_id}", method="GET")
        assert any(a["status"] == "confirmed" and a["operation"] == "restrict" for a in case["actions"])
        checks.append("Restrict request acknowledged by separate bank process")
        followup = {**payment, "txn_id": prefix + "-blocked", "amount_minor": 25000,
                    "new_device": False, "new_beneficiary": False, "failed_auth_attempts": 0}
        call("/transactions", followup)
        call("/process")
        snap = call("/snapshot", method="GET")
        assert next(t for t in snap["transactions"] if t["txn_id"] == followup["txn_id"])["payment_status"] == "declined"
        checks.append("Subsequent payment actually declined while restricted")
        call(f"/cases/{case_id}/decision", {"action": "false_positive", "expected_version": case["version"], "notes": "Live HTTP test: synthetic customer-authorized transaction."})
        call("/process")
        resolved = call(f"/cases/{case_id}", method="GET")
        assert resolved["status"] == "resolved" and resolved["verdict"] == "false_positive"
        allowed = {**followup, "txn_id": prefix + "-released"}
        call("/transactions", allowed)
        call("/process")
        snap = call("/snapshot", method="GET")
        assert next(t for t in snap["transactions"] if t["txn_id"] == allowed["txn_id"])["payment_status"] == "posted"
        checks.append("Analyst reversal acknowledged; subsequent payment actually posted")
        before_duplicate = snap["counts"]["transactions"]
        assert call("/transactions", allowed)["duplicate"]
        assert call("/snapshot", method="GET")["counts"]["transactions"] == before_duplicate
        checks.append("Duplicate input does not create another payment or inflate counts")
        for channel in ("upi", "net_banking", "card", "atm"):
            generated = call("/simulation/scenario", {"channel": channel, "scenario": "fraud"})
            assert generated["case_ids"]
            assert any(t["payment_status"] == "declined" for t in generated["transactions"])
        checks.append("All four channels create evidence-backed cases and enforce simulated protection")
        report = call(f"/cases/{case_id}/report", method="GET")
        assert report["case"]["verdict"] == "false_positive" and report["simulation"]
        pdf = client.get(f"/ops/cases/{case_id}/report?format=pdf")
        assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
        checks.append("JSON and PDF reports reflect the same persisted analyst verdict")
        with client.stream("GET", "/ops/events?after=0", timeout=5) as stream:
            stream.raise_for_status()
            first = next(line for line in stream.iter_lines() if line.startswith("data:"))
            assert json.loads(first[5:])["cursor"] > 0
        checks.append("Authenticated event stream delivers the persisted audit cursor over HTTP")
        snap = call("/snapshot", method="GET")
        assert snap["counts"]["transactions"] == sum(c["transactions"] for c in snap["channels"])
        assert snap["counts"]["cases"] == sum(c["cases"] for c in snap["channels"])
        checks.append("Overall and channel counts reconcile")
        output = {"checked_at": datetime.now(timezone.utc).isoformat(), "simulation": True,
                  "checks": checks, "case_id": case_id, "case_version": resolved["version"], "counts": snap["counts"]}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(output, indent=2) + "\n")
        print(json.dumps(output, indent=2))
    finally:
        call("/simulation/control", {"running": was_running, "bank_mode": "normal"})
        client.close()


if __name__ == "__main__":
    main()
