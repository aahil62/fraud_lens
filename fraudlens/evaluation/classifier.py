"""Held-out evaluation of the ML scoring agent on its own, not of the full detector.

The model is the production reference model (trained by the detector on
synthetic seed 173). It is scored on transactions generated from ten other
seeds it never saw. Labels come from the synthetic generator.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from sklearn.metrics import average_precision_score, f1_score, precision_score, recall_score, roc_auc_score

from fraudlens.data.synthetic_generator import generate_synthetic_transactions
from fraudlens.operations.detector import reference_model

TRAINING_SEED = 173  # the seed reference_model() trains on
TEST_SEEDS = tuple(range(1, 11))
THRESHOLD = 0.5
DEFAULT_OUTPUT = Path("docs/verification/classifier-evaluation.json")


def evaluate() -> dict:
    model = reference_model()
    test = [t for seed in TEST_SEEDS for t in generate_synthetic_transactions(seed=seed)]
    labels = [int(t.is_fraud_demo_label) for t in test]
    scores = [model.score(t).score for t in test]
    predicted = [int(s >= THRESHOLD) for s in scores]
    tp = sum(p and y for p, y in zip(predicted, labels, strict=True))
    fp = sum(p and not y for p, y in zip(predicted, labels, strict=True))
    fn = sum(y and not p for p, y in zip(predicted, labels, strict=True))
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "simulation": True,
        "model": "GradientBoostingClassifier (fraudlens.core.scoring.ml_agent.MLAgent)",
        "training_seed": TRAINING_SEED,
        "test_seeds": list(TEST_SEEDS),
        "threshold": THRESHOLD,
        "metrics": {
            "samples": len(test),
            "fraud": sum(labels),
            "true_positive": tp,
            "false_positive": fp,
            "false_negative": fn,
            "true_negative": len(test) - tp - fp - fn,
            "precision": round(precision_score(labels, predicted), 4),
            "recall": round(recall_score(labels, predicted), 4),
            "f1": round(f1_score(labels, predicted), 4),
            "roc_auc": round(roc_auc_score(labels, scores), 4),
            "average_precision": round(average_precision_score(labels, scores), 4),
        },
        "limitations": [
            "Training and test data come from the same synthetic generator, so these figures measure how well the model "
            "learns the generator's patterns, not real-world fraud detection.",
            "This is the classifier alone; the operational detector combines it with rules, velocity, behavioral and "
            "graph signals (see operations-evaluation.json).",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = evaluate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "metrics": report["metrics"]}, indent=2))


if __name__ == "__main__":
    main()
