# Controlled scenario evaluation

This evaluation exercises **376 terminal payment attempts** across four channels and eight fixed seeds. Fixtures are constructed independently of the interactive scenario helper. Every incident has its own chronological prior history; evaluator labels are never detector inputs. The reference ML model uses a different synthetic training seed (173).

Reproduce from the repository root:

```bash
.venv/bin/python -m fraudlens.evaluation.operations
```

Full records, corpus SHA-256, seeds, timing and per-channel breakdown are stored in [operations-evaluation.json](verification/operations-evaluation.json). The checked policy is `showcase-policy-1.2`.

## Results in this constructed corpus

| Decision threshold | True positives | False positives | True negatives | False negatives | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|
| Review, score ≥0.5 | 184 | 64 | 96 | 32 | 0.7419 | 0.8519 |
| Automatic protection, score ≥0.8 | 176 | 32 | 128 | 40 | 0.8462 | 0.8148 |

All **152 supported-pattern incidents** reached review. Eight lower-value ATM location-change incidents remained review-only; 144 reached automatic protection. All 64 ordinary benign controls remained clear.

Version 1.2 adds four v3 typologies with **64 more incidents** (one fraud and one same-shape benign control per typology per seed): mule pass-through (UPI), SIM-swap takeover (net banking), card testing (card) and ATM burst across terminals (ATM). All 32 typology frauds reached automatic protection and all 32 controls stayed below review. Each control keeps the shape of its fraud but removes the decisive signal (known beneficiary; known device with no failed logins; one small probe instead of six; one prior withdrawal at the same terminal). Perfect separation here shows the rules fire as written; it is not evidence that real mule or SIM-swap fraud would be caught, because these rules were designed alongside the fixtures.

The evaluation deliberately includes **64 authorized unusual payments**. All reached review and 32 reached protection: these are false positives, despite matching the configured telemetry rules. The analyst correction/release path is therefore a core part of the product, not a claim that automation is infallible.

It also contains **32 fraudulent payments indistinguishable from ordinary activity in the available telemetry**. All were missed. Scam-message context, customer intent, stolen credentials without observable anomalies, ATM cameras and skimmer hardware evidence are not available to the detector.

## The ML classifier on its own

The detector's gradient-boosted classifier (`MLAgent`) is one of its signals. Its own held-out quality, measured on the production reference model (trained on synthetic seed 173) against **10,399 transactions** (3,399 fraud) from ten other seeds it never saw:

```bash
.venv/bin/python -m fraudlens.evaluation.classifier
```

| Threshold | True positives | False positives | True negatives | False negatives | Precision | Recall | F1 | ROC-AUC | Average precision |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| score ≥0.5 | 2987 | 160 | 6840 | 412 | 0.9492 | 0.8788 | 0.9126 | 0.9463 | 0.9451 |

Training and test data come from the same synthetic generator, so this measures how well the model learns the generator's patterns, not real-world fraud detection. Full output: [classifier-evaluation.json](verification/classifier-evaluation.json).

## Evidence boundary

- Constructed frequencies are not real fraud prevalence. These precision/recall figures apply only to this fixed corpus.
- Cases intentionally exercise documented rules. Parameter variation is not an unseen-fraud benchmark or proof of generalization.
- No real customer data, production bank controls, loss avoidance, or regulatory compliance is validated.
- Scores are prioritization scores, not calibrated probabilities.
- Reported warm scoring latency excludes persistence, queueing, networking and interface rendering. Initialization is measured separately.
- Historical synthetic/ULB results in the old evaluation modules describe a different pipeline and must not be substituted for these results.
