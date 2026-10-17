# Controlled scenario evaluation

This evaluation exercises **312 terminal payment attempts** across four channels and eight fixed seeds. Fixtures are constructed independently of the interactive scenario helper. Every incident has its own chronological prior history; evaluator labels are never detector inputs. The reference ML model uses a different synthetic training seed (173).

Reproduce from the repository root:

```bash
.venv/bin/python -m fraudlens.evaluation.operations
```

Full records, corpus SHA-256, seeds, timing and per-channel breakdown are stored in [operations-evaluation.json](verification/operations-evaluation.json). The checked policy is `showcase-policy-1.1`.

## Results in this constructed corpus

| Decision threshold | True positives | False positives | True negatives | False negatives | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|
| Review, score ≥0.5 | 152 | 64 | 64 | 32 | 0.7037 | 0.8261 |
| Automatic protection, score ≥0.8 | 144 | 32 | 96 | 40 | 0.8182 | 0.7826 |

All **152 supported-pattern incidents** reached review. Eight lower-value ATM location-change incidents remained review-only; 144 reached automatic protection. All 64 ordinary benign controls remained clear.

The evaluation deliberately includes **64 authorized unusual payments**. All reached review and 32 reached protection: these are false positives, despite matching the configured telemetry rules. The analyst correction/release path is therefore a core part of the product, not a claim that automation is infallible.

It also contains **32 fraudulent payments indistinguishable from ordinary activity in the available telemetry**. All were missed. Scam-message context, customer intent, stolen credentials without observable anomalies, ATM cameras and skimmer hardware evidence are not available to the detector.

## Evidence boundary

- Constructed frequencies are not real fraud prevalence. These precision/recall figures apply only to this fixed corpus.
- Cases intentionally exercise documented rules. Parameter variation is not an unseen-fraud benchmark or proof of generalization.
- No real customer data, production bank controls, loss avoidance, or regulatory compliance is validated.
- Scores are prioritization scores, not calibrated probabilities.
- Reported warm scoring latency excludes persistence, queueing, networking and interface rendering. Initialization is measured separately.
- Historical synthetic/ULB results in the old evaluation modules describe a different pipeline and must not be substituted for these results.
