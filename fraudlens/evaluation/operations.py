"""Controlled synthetic evaluation of the operational detector, not bank validation.

Fixtures are independent of the interactive scenario helper. Each evaluation
unit is one terminal attempted payment with its explicitly prior context.
Ground truth is evaluator metadata and is never passed into detect().
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from fraudlens.operations.detector import CHANNELS, VERSION, detect, reference_model

from .fixtures import fixtures

SEEDS = (101, 211, 307, 419, 523, 631, 743, 857)
REVIEW_THRESHOLD = 0.5
PROTECTION_THRESHOLD = 0.8
DEFAULT_OUTPUT = Path("docs/verification/operations-evaluation.json")


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
