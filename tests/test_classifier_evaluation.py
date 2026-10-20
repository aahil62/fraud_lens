"""The published classifier metrics must come from the production model on unseen seeds."""

import json
import unittest
from pathlib import Path

from fraudlens.evaluation.classifier import TEST_SEEDS, TRAINING_SEED, evaluate

ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "docs/verification/classifier-evaluation.json"
DOC_PATH = ROOT / "docs/OPERATIONS_EVALUATION.md"


class ClassifierEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = evaluate()

    def test_test_seeds_never_include_the_training_seed(self):
        self.assertNotIn(TRAINING_SEED, TEST_SEEDS)
        self.assertEqual(self.report["training_seed"], 173)

    def test_published_json_matches_a_fresh_run(self):
        stored = json.loads(JSON_PATH.read_text())
        self.assertEqual(stored["metrics"], self.report["metrics"])
        self.assertEqual(stored["test_seeds"], list(TEST_SEEDS))

    def test_docs_quote_the_json(self):
        m = json.loads(JSON_PATH.read_text())["metrics"]
        doc = DOC_PATH.read_text()
        for key in ("precision", "recall", "f1", "roc_auc", "average_precision"):
            self.assertIn(f"{m[key]:.4f}", doc, key)
        self.assertIn(f"{m['samples']:,}", doc)


if __name__ == "__main__":
    unittest.main()
