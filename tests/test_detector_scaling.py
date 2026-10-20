"""Detection stays fast as the ledger grows, even when every payment omits its IP."""

import time
import unittest
from datetime import datetime, timedelta, timezone

from fraudlens.operations.detector import detect, reference_model
from fraudlens.operations.models import TransactionInput


def _payment(i, start):
    # Like the simulator: a fresh account per scenario and no ip_address, so the default applies.
    return TransactionInput(
        txn_id=f"SCALE-{i}",
        account_id=f"SIM-{i // 3}",
        channel="upi",
        amount_minor=45000,
        timestamp=start + timedelta(seconds=i),
        beneficiary_id=f"BEN-{i // 3}",
        device_id=f"DEV-{i // 3}",
    ).model_dump(mode="json")


class DetectorScalingTests(unittest.TestCase):
    def test_detect_with_a_thousand_prior_default_ip_payments_is_fast(self):
        reference_model()  # trained once per process; not part of per-payment cost
        start = datetime(2026, 10, 20, 9, tzinfo=timezone.utc)
        history = [_payment(i, start) for i in range(1000)]
        current = _payment(1000, start)
        began = time.perf_counter()
        result = detect(current, history)
        elapsed = time.perf_counter() - began
        self.assertLess(elapsed, 2.0, f"detect() took {elapsed:.1f} s")
        graph = next(s for s in result["signals"] if s["name"] == "graph_agent")
        self.assertFalse(any("127.0.0.1" in reason for reason in graph["reasons"]))


if __name__ == "__main__":
    unittest.main()
