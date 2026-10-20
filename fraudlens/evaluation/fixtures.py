"""Independent evaluation fixtures: one terminal attempted payment per incident, with prior context only.

Ground truth (is_fraud, family) is evaluator metadata and never reaches detect().
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from fraudlens.operations.detector import CHANNELS


def fixtures(seed: int, channel: str):
    """Vary amount, account, device and timing; hold each incident independent."""
    rng = random.Random(seed)
    now = datetime(2026, 10, 17, 12, tzinfo=timezone.utc) + timedelta(seconds=seed)
    account = f"SYNTH-{channel}-{seed}"
    device = f"device-{seed}"
    instrument = f"instrument-{seed}" if channel in {"card", "atm"} else None

    def payment(name, seconds=0, **changes):
        txn = {
            "txn_id": f"EVAL-{channel}-{seed}-{name}",
            "account_id": account,
            "channel": channel,
            "amount_minor": rng.randint(5_000, 45_000),
            "timestamp": (now + timedelta(seconds=seconds)).isoformat(),
            "instrument_id": instrument,
            "beneficiary_id": "beneficiary-known",
            "merchant_id": "synthetic-retail",
            "device_id": device,
            "ip_address": "192.0.2.10",
            "location": "Pune",
            "new_device": False,
            "new_beneficiary": False,
            "failed_auth_attempts": 0,
        }
        txn.update(changes)
        return txn

    baseline = [payment(f"baseline-{i}", seconds=-(i + 1) * 3_600) for i in range(8)]

    def unit(name, family, truth, txn, extra=()):
        history = sorted([*baseline, *extra], key=lambda t: t["timestamp"])
        assert all(t["timestamp"] < txn["timestamp"] for t in history)
        return {
            "seed": seed,
            "channel": channel,
            "scenario": name,
            "family": family,
            "is_fraud": truth,
            "transaction": txn,
            "history": history,
        }

    yield unit("routine_payment", "ordinary_benign", False, payment("routine"))
    yield unit(
        "known_device_new_payee",
        "ordinary_benign",
        False,
        payment("new-payee", new_beneficiary=True, amount_minor=rng.randint(50_000, 150_000)),
    )
    yield unit(
        "credential_takeover",
        "supported_fraud",
        True,
        payment("takeover", new_device=True, failed_auth_attempts=rng.randint(3, 6)),
    )
    burst = [payment(f"burst-{i}", seconds=-rng.randint(20, 45) * (i + 1)) for i in range(4)]
    yield unit("account_payment_burst", "supported_fraud", True, payment("burst-terminal"), burst)
    other = [c for c in CHANNELS if c != channel]
    cross = [
        payment(
            f"cross-{i}",
            seconds=-(i + 1) * 40,
            channel=c,
            instrument_id=f"cross-instrument-{seed}" if c in {"card", "atm"} else None,
        )
        for i, c in enumerate(other[:2])
    ]
    yield unit(
        "cross_channel_anomaly", "supported_fraud", True, payment("cross-terminal", new_device=True), cross
    )

    if channel == "upi":
        yield unit(
            "new_device_large_beneficiary",
            "supported_fraud",
            True,
            payment(
                "upi-beneficiary",
                new_device=True,
                new_beneficiary=True,
                amount_minor=rng.randint(2_000_000, 3_000_000),
            ),
        )
        shared = [
            payment(f"shared-{i}", seconds=-(i + 1) * 60, account_id=f"SYNTH-OTHER-{seed}-{i}")
            for i in range(3)
        ]
        yield unit(
            "shared_device_beneficiary_transfer",
            "supported_fraud",
            True,
            payment("shared-terminal", new_beneficiary=True, amount_minor=3_000_000),
            shared,
        )
    elif channel == "net_banking":
        yield unit(
            "beneficiary_after_auth_failures",
            "supported_fraud",
            True,
            payment("net-beneficiary", new_beneficiary=True, failed_auth_attempts=4),
        )
    elif channel == "card":
        small = [
            payment(f"card-test-{i}", seconds=-(i + 1) * 25, amount_minor=rng.randint(100, 5_000))
            for i in range(3)
        ]
        yield unit(
            "card_testing",
            "supported_fraud",
            True,
            payment("card-test-terminal", amount_minor=rng.randint(100, 5_000)),
            small,
        )
    else:
        withdrawals = [
            payment(f"withdrawal-{i}", seconds=-(i + 1) * 35, amount_minor=rng.randint(1_000_000, 1_200_000))
            for i in range(2)
        ]
        yield unit(
            "withdrawal_burst",
            "supported_fraud",
            True,
            payment("withdrawal-terminal", amount_minor=1_100_000),
            withdrawals,
        )
        yield unit(
            "new_terminal_withdrawal",
            "supported_fraud",
            True,
            payment("new-terminal", new_device=True, amount_minor=rng.randint(1_000_000, 1_500_000)),
        )
        yield unit(
            "rapid_location_change",
            "supported_fraud",
            True,
            payment("location-terminal", location="Delhi", amount_minor=300_000),
            [payment("location-prior", seconds=-60, location="Pune", amount_minor=200_000)],
        )

    # These authorized payments deliberately share suspicious telemetry. They
    # expose uncertainty and overblocking instead of promising perfect results.
    yield unit(
        "authorized_new_device",
        "authorized_unusual",
        False,
        payment("authorized-review", new_device=True, amount_minor=600_000),
    )
    yield unit(
        "authorized_large_new_beneficiary",
        "authorized_unusual",
        False,
        payment(
            "authorized-protect",
            new_device=True,
            new_beneficiary=True,
            amount_minor=rng.randint(2_000_000, 3_000_000),
        ),
    )
    # A scam or stolen authorized credential can look identical to routine use.
    # No scam-message, owner-intent, camera or skimmer telemetry is available.
    yield unit(
        "telemetry_invisible_fraud",
        "unobservable_fraud",
        True,
        payment("invisible", amount_minor=rng.randint(5_000, 45_000)),
    )

    # v3 typologies: one fraud and one same-shape benign control per seed,
    # each placed under the channel of its terminal attempt.
    if channel == "upi":
        received = rng.randint(1_000_000, 5_000_000)
        credit = payment(
            "mule-credit",
            seconds=-240,
            account_id=f"SYNTH-VICTIM-{seed}",
            beneficiary_id=account,
            amount_minor=received,
            new_beneficiary=True,
        )
        first = payment(
            "mule-out-1",
            seconds=-60,
            beneficiary_id=f"SYNTH-M2-{seed}",
            new_beneficiary=True,
            amount_minor=received * 5 // 8,
        )
        last = dict(beneficiary_id=f"SYNTH-M3-{seed}", amount_minor=received * 5 // 16)
        yield unit(
            "mule_layering",
            "typology_fraud",
            True,
            payment("mule-out-2", new_beneficiary=True, **last),
            [credit, first],
        )
        yield unit(
            "mule_layering_control",
            "typology_control",
            False,
            payment("mule-control", new_beneficiary=False, **last),
            [credit, {**first, "new_beneficiary": False}],
        )
    elif channel == "net_banking":
        large = rng.randint(15_000_000, 20_000_000)
        yield unit(
            "sim_swap_takeover",
            "typology_fraud",
            True,
            payment(
                "sim-swap",
                new_device=True,
                new_beneficiary=True,
                failed_auth_attempts=rng.randint(3, 5),
                amount_minor=large,
            ),
        )
        yield unit(
            "sim_swap_takeover_control",
            "typology_control",
            False,
            payment("sim-swap-control", amount_minor=large),
        )
    elif channel == "card":
        probes = [
            payment(
                f"card-probe-{i}",
                seconds=-(6 - i) * 60,
                merchant_id=f"synthetic-merchant-{i}",
                amount_minor=rng.randint(4_900, 19_900),
            )
            for i in range(6)
        ]
        large = rng.randint(1_000_000, 2_500_000)
        yield unit("card_testing", "typology_fraud", True, payment("card-large", amount_minor=large), probes)
        yield unit(
            "card_testing_control",
            "typology_control",
            False,
            payment("card-large-control", amount_minor=large),
            probes[-1:],
        )
    else:
        cash = [
            payment(
                f"atm-cash-{i}",
                seconds=-(4 - i) * 240,
                device_id=f"terminal-{seed}-{i % 3}",
                amount_minor=1_000_000,
            )
            for i in range(3)
        ]
        yield unit(
            "atm_cashout",
            "typology_fraud",
            True,
            payment("atm-cash-terminal", device_id=f"terminal-{seed}-2", amount_minor=1_000_000),
            cash,
        )
        yield unit(
            "atm_cashout_control",
            "typology_control",
            False,
            payment("atm-cash-control", device_id=f"terminal-{seed}-0", amount_minor=1_000_000),
            cash[:1],
        )
