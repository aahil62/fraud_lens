"""Synthetic test telemetry. Scenario labels never enter detector inputs."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from .models import TransactionInput


def scenario_transactions(channel, scenario):
    prefix = uuid4().hex[:10]
    account = f"SIM-{prefix}"
    common = dict(account_id=account, amount_minor=45000, instrument_id=None, beneficiary_id=f"BEN-{prefix}",
                  merchant_id="retail-demo", device_id=f"DEV-{prefix}", location="Pune")
    rows = []
    if scenario == "cross_channel":
        for i, rail in enumerate(("upi", "net_banking", "card", "atm")):
            rows.append({**common, "channel": rail, "instrument_id": f"CARD-{prefix}" if rail in {"card", "atm"} else None,
                         "new_device": i >= 2, "failed_auth_attempts": 1 if i >= 2 else 0})
    elif scenario == "normal":
        rows.append({**common, "channel": channel, "instrument_id": f"CARD-{prefix}" if channel in {"card", "atm"} else None})
    elif scenario == "false_positive":
        # An unusual but customer-authorized payment for the analyst to clear.
        rows.append({**common, "channel": channel, "instrument_id": f"CARD-{prefix}" if channel in {"card", "atm"} else None,
                     "amount_minor": 8500000, "new_device": True, "new_beneficiary": True, "failed_auth_attempts": 3})
    elif channel == "card":
        for _ in range(4):
            rows.append({**common, "channel": channel, "amount_minor": 2500, "instrument_id": f"CARD-{prefix}"})
    elif channel == "atm":
        for _ in range(3):
            rows.append({**common, "channel": channel, "amount_minor": 1500000, "instrument_id": f"CARD-{prefix}"})
    else:
        rows.append({**common, "channel": channel, "amount_minor": 8000000, "new_device": True,
                     "new_beneficiary": True, "failed_auth_attempts": 4 if channel == "net_banking" else 0})
    start = datetime.now(timezone.utc) - timedelta(seconds=len(rows))
    return [TransactionInput(**row, txn_id=f"SIM-{prefix}-{i + 1}", timestamp=start + timedelta(seconds=i))
            for i, row in enumerate(rows)]
