"""Controlled synthetic evaluation of the operational detector, not bank validation.

Fixtures are independent of the interactive scenario helper. Each evaluation
unit is one terminal attempted payment with its explicitly prior context.
Ground truth is evaluator metadata and is never passed into detect().
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fraudlens.operations.detector import CHANNELS, VERSION, detect, reference_model

SEEDS = (101, 211, 307, 419, 523, 631, 743, 857)
REVIEW_THRESHOLD = 0.5
PROTECTION_THRESHOLD = 0.8
DEFAULT_OUTPUT = Path("docs/verification/operations-evaluation.json")


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


def metrics(records: list[dict], threshold: float) -> dict:
    tp = sum(r["is_fraud"] and r["score"] >= threshold for r in records)
    fp = sum(not r["is_fraud"] and r["score"] >= threshold for r in records)
    tn = sum(not r["is_fraud"] and r["score"] < threshold for r in records)
    fn = sum(r["is_fraud"] and r["score"] < threshold for r in records)

    def ratio(a, b):
        return round(a / b, 4) if b else None

    return {
        "threshold": threshold,
        "samples": len(records),
        "true_positive": tp,
        "false_positive": fp,
        "true_negative": tn,
        "false_negative": fn,
        "precision": ratio(tp, tp + fp),
        "recall": ratio(tp, tp + fn),
        "false_positive_rate": ratio(fp, fp + tn),
        "f1": ratio(2 * tp, 2 * tp + fp + fn),
    }


def evaluate() -> dict:
    corpus = [u for seed in SEEDS for channel in CHANNELS for u in fixtures(seed, channel)]
    corpus_hash = hashlib.sha256(json.dumps(corpus, sort_keys=True).encode()).hexdigest()
    # Report initialization independently of per-event, warm-model scoring.
    start = time.perf_counter()
    reference_model()
    initialization_ms = (time.perf_counter() - start) * 1_000
    records = []
    for unit in corpus:
        start = time.perf_counter()
        result = detect(dict(unit["transaction"]), [dict(t) for t in unit["history"]])
        duration = (time.perf_counter() - start) * 1_000
        records.append(
            {k: unit[k] for k in ("seed", "channel", "scenario", "family", "is_fraud")}
            | {
                "score": result["score"],
                "review": result["score"] >= REVIEW_THRESHOLD,
                "protect": result["score"] >= PROTECTION_THRESHOLD,
                "latency_ms": round(duration, 3),
                "reasons": result["reasons"],
            }
        )

    def summary(rows):
        return {"review": metrics(rows, REVIEW_THRESHOLD), "protection": metrics(rows, PROTECTION_THRESHOLD)}

    durations = sorted(r["latency_ms"] for r in records)
    return {
        "schema_version": 1,
        "detector_version": VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "simulation": True,
        "method": "Independent controlled fixtures; one terminal attempted payment per incident; chronological prior context only.",
        "seeds": list(SEEDS),
        "corpus_sha256": corpus_hash,
        "reference_model": "Cached model trained by detector on separate synthetic seed 173; no evaluation labels supplied to inference.",
        "initialization_ms": round(initialization_ms, 3),
        "warm_scoring_latency_ms": {
            "mean": round(sum(durations) / len(durations), 3),
            "p95": durations[int((len(durations) - 1) * 0.95)],
        },
        "overall": summary(records),
        "channels": {c: summary([r for r in records if r["channel"] == c]) for c in CHANNELS},
        "families": {
            f: summary([r for r in records if r["family"] == f])
            for f in sorted({r["family"] for r in records})
        },
        "limitations": [
            "Constructed scenario frequencies are not real fraud prevalence; precision and recall apply only to this corpus.",
            "Supported scenarios intentionally exercise documented policy; variations are not an independent unseen-fraud benchmark.",
            "Unobservable fraud and authorized suspicious activity expose false negatives and false positives deliberately.",
            "No real customer data, bank/network authorization, monetary loss avoided, or regulatory compliance is validated.",
            "Scores prioritize review and are not calibrated fraud probabilities; latency excludes networking, persistence and UI.",
        ],
        "records": records,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = evaluate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "overall": report["overall"],
                "warm_scoring_latency_ms": report["warm_scoring_latency_ms"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
