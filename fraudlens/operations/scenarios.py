"""Synthetic test telemetry. Scenario labels never enter detector inputs."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from .models import TransactionInput


TYPOLOGIES = ("mule_layering", "sim_swap_takeover", "card_testing", "atm_cashout")


def scenario_transactions(channel, scenario):
    """channel is required; named typologies define their own payment channels."""
    if scenario in TYPOLOGIES:
        return typology_transactions(scenario)
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


def typology_transactions(scenario):
    prefix = f"SIM-{uuid4().hex[:10]}"
    common = dict(account_id=f"{prefix}-V", amount_minor=45000, channel="upi", device_id=f"{prefix}-KNOWN",
                  merchant_id=f"{prefix}-RETAIL", location="Pune")
    if scenario == "mule_layering":
        rows = [(0, dict(amount_minor=4800000, beneficiary_id=f"{prefix}-M1", new_beneficiary=True)),
                (3, dict(account_id=f"{prefix}-M1", channel="net_banking", amount_minor=3000000,
                         beneficiary_id=f"{prefix}-M2", new_beneficiary=True)),
                (4, dict(account_id=f"{prefix}-M1", amount_minor=1500000, beneficiary_id=f"{prefix}-M3", new_beneficiary=True)),
                (9, dict(account_id=f"{prefix}-M2", channel="atm", amount_minor=2000000,
                         instrument_id=f"{prefix}-CARD-M2", device_id=f"{prefix}-ATM"))]
    elif scenario == "sim_swap_takeover":
        rows = [(0, dict(channel="net_banking", amount_minor=18500000, beneficiary_id=f"{prefix}-PAYEE",
                         device_id=f"{prefix}-NEW", new_device=True, new_beneficiary=True, failed_auth_attempts=3))]
    elif scenario == "card_testing":
        rows = [(i, dict(channel="card", amount_minor=amount, instrument_id=f"{prefix}-CARD",
                         merchant_id=f"{prefix}-MERCHANT-{i}")) for i, amount in enumerate((4900, 7900, 9900, 12900, 15900, 19900))]
        rows.append((6, dict(channel="card", amount_minor=1850000, instrument_id=f"{prefix}-CARD")))
    else:
        rows = [(i * 4, dict(channel="atm", amount_minor=1000000, instrument_id=f"{prefix}-CARD",
                            device_id=f"{prefix}-ATM-{i % 3}")) for i in range(4)]
    start = datetime.now(timezone.utc) - timedelta(minutes=rows[-1][0])
    return [TransactionInput(**{**common, **changes}, txn_id=f"{prefix}-TX-{i}", timestamp=start+timedelta(minutes=minute))
            for i, (minute, changes) in enumerate(rows)]


def typology_accounts(rows):
    """Provision all fictional recipients before the first transfer can credit them."""
    accounts = {row.account_id: 100000000 for row in rows}
    for row in rows:
        if row.beneficiary_id:
            accounts[row.beneficiary_id] = 0
    return [{"account_id": account, "balance_minor": amount} for account, amount in accounts.items()]
