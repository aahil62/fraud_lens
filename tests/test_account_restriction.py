import os
import tempfile
import unittest

from fraudlens.core.cases.account_restriction import AccountRestrictionStore
from fraudlens.core.scoring.velocity_agent import VelocityAgent
from fraudlens.models.schemas import Transaction

_now = "2026-09-04T10:00:00+00:00"


def _txn(txn_id: str, account_id: str = "ACC-RESTRICT-1", timestamp: str = _now) -> Transaction:
    return Transaction(
        txn_id=txn_id,
        account_id=account_id,
        amount=5000.0,
        merchant_id="M1",
        merchant_category="electronics",
        device_id="D1",
        ip_address="1.2.3.4",
        timestamp=timestamp,
    )


class AccountRestrictionStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self._tmp.close()
        os.remove(self._tmp.name)
        self.addCleanup(lambda: os.path.exists(self._tmp.name) and os.remove(self._tmp.name))
        self.store = AccountRestrictionStore(path=self._tmp.name)

    def test_account_starts_unrestricted(self) -> None:
        self.assertFalse(self.store.is_restricted("ACC-1"))

    def test_restrict_then_is_restricted(self) -> None:
        self.store.restrict("ACC-1", "TXN-1", "CASE-TXN-1")
        self.assertTrue(self.store.is_restricted("ACC-1"))

    def test_restrict_is_idempotent(self) -> None:
        first = self.store.restrict("ACC-1", "TXN-1", "CASE-TXN-1")
        second = self.store.restrict("ACC-1", "TXN-2", "CASE-TXN-2")
        # Same restriction record — a later trigger doesn't overwrite the
        # original reason while the account is still actively restricted.
        self.assertEqual(first.applied_at, second.applied_at)
        self.assertEqual(second.reason_txn_id, "TXN-1")

    def test_release_clears_restriction(self) -> None:
        self.store.restrict("ACC-1", "TXN-1", "CASE-TXN-1")
        released = self.store.release("ACC-1", "A. Sharma")
        self.assertIsNotNone(released)
        self.assertFalse(self.store.is_restricted("ACC-1"))
        self.assertEqual(released.released_by, "A. Sharma")

    def test_release_of_unrestricted_account_is_a_noop(self) -> None:
        self.assertIsNone(self.store.release("ACC-NEVER-RESTRICTED", "A. Sharma"))

    def test_restrict_again_after_release_creates_a_new_active_restriction(self) -> None:
        self.store.restrict("ACC-1", "TXN-1", "CASE-TXN-1")
        self.store.release("ACC-1", "A. Sharma")
        self.assertFalse(self.store.is_restricted("ACC-1"))
        self.store.restrict("ACC-1", "TXN-2", "CASE-TXN-2")
        self.assertTrue(self.store.is_restricted("ACC-1"))
        self.assertEqual(self.store.get("ACC-1").reason_txn_id, "TXN-2")

    def test_persists_across_store_instances(self) -> None:
        self.store.restrict("ACC-1", "TXN-1", "CASE-TXN-1")
        reloaded = AccountRestrictionStore(path=self._tmp.name)
        self.assertTrue(reloaded.is_restricted("ACC-1"))


class VelocityAgentRestrictedModeTests(unittest.TestCase):
    """The actual mechanism: a restricted account trips the velocity
    agent's burst thresholds at a lower transaction count than normal."""

    def _history_with_two_recent_txns(self, account_id: str) -> list[Transaction]:
        return [
            _txn("TXN-HIST-1", account_id, "2026-09-04T09:50:00+00:00"),
            _txn("TXN-HIST-2", account_id, "2026-09-04T09:55:00+00:00"),
        ]

    def test_same_burst_scores_higher_when_account_is_restricted(self) -> None:
        account_id = "ACC-RESTRICTED"
        # Exactly 2 transactions in the last hour (2 history + this one = 3
        # total) — below the normal minor threshold's *trigger* point is
        # subtle, so compare the same fixture scored two ways instead of
        # reasoning about absolute thresholds.
        history = self._history_with_two_recent_txns(account_id)
        current = _txn("TXN-CURRENT", account_id)

        unrestricted_store = AccountRestrictionStore(path=tempfile.mktemp(suffix=".json"))
        unrestricted_agent = VelocityAgent(restriction_store=unrestricted_store)
        unrestricted_agent.set_transactions(history + [current])
        unrestricted_score = unrestricted_agent.score(current)

        restricted_store = AccountRestrictionStore(path=tempfile.mktemp(suffix=".json"))
        restricted_store.restrict(account_id, "TXN-TRIGGER", "CASE-TXN-TRIGGER")
        restricted_agent = VelocityAgent(restriction_store=restricted_store)
        restricted_agent.set_transactions(history + [current])
        restricted_score = restricted_agent.score(current)

        self.assertGreater(restricted_score.score, unrestricted_score.score)
        self.assertTrue(
            any("restriction" in r.lower() for r in restricted_score.reasons),
            restricted_score.reasons,
        )
        self.assertFalse(any("restriction" in r.lower() for r in unrestricted_score.reasons))

    def test_unrestricted_account_never_mentions_a_restriction(self) -> None:
        account_id = "ACC-NEVER-RESTRICTED"
        store = AccountRestrictionStore(path=tempfile.mktemp(suffix=".json"))
        agent = VelocityAgent(restriction_store=store)
        txn = _txn("TXN-SOLO", account_id)
        agent.set_transactions([txn])
        score = agent.score(txn)
        self.assertFalse(any("restriction" in r.lower() for r in score.reasons))


if __name__ == "__main__":
    unittest.main()
