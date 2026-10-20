"""The published evaluation table must match the generated JSON exactly."""

import json
import re
import unittest
from collections import Counter
from pathlib import Path

from fraudlens.evaluation.operations import CHANNELS, SEEDS, fixtures
from fraudlens.operations.detector import VERSION

ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "docs/verification/operations-evaluation.json"
DOC_PATH = ROOT / "docs/OPERATIONS_EVALUATION.md"
TYPOLOGIES = ("mule_layering", "sim_swap_takeover", "card_testing", "atm_cashout")


class EvaluationSnapshotTests(unittest.TestCase):
    def test_corpus_contains_new_typologies_with_controls(self):
        corpus = [u for seed in SEEDS for channel in CHANNELS for u in fixtures(seed, channel)]
        counts = Counter(
            (u["scenario"], u["is_fraud"]) for u in corpus if u["family"].startswith("typology_")
        )
        for typology in TYPOLOGIES:
            self.assertEqual(counts[(typology, True)], len(SEEDS), typology)
            self.assertEqual(counts[(f"{typology}_control", False)], len(SEEDS), typology)

    def test_docs_match_json(self):
        report = json.loads(JSON_PATH.read_text())
        doc = DOC_PATH.read_text()
        self.assertEqual(report["detector_version"], VERSION)
        self.assertIn(f"`{VERSION}`", doc)
        self.assertIn(f"**{report['overall']['review']['samples']} terminal payment attempts**", doc)
        for label, key in (
            ("Review, score ≥0.5", "review"),
            ("Automatic protection, score ≥0.8", "protection"),
        ):
            row = re.search(rf"^\| {re.escape(label)} \|(.+)\|$", doc, re.MULTILINE)
            self.assertIsNotNone(row, label)
            cells = [c.strip() for c in row.group(1).split("|")]
            expected = report["overall"][key]
            self.assertEqual(
                [int(c) for c in cells[:4]],
                [expected[k] for k in ("true_positive", "false_positive", "true_negative", "false_negative")],
            )
            self.assertEqual([f"{expected['precision']:.4f}", f"{expected['recall']:.4f}"], cells[4:6])


if __name__ == "__main__":
    unittest.main()
