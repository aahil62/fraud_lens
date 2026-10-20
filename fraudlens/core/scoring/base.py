"""The contract every scoring agent implements.

A Protocol rather than a base class, so each agent stays independent of the others.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from fraudlens.models.schemas import AgentScore, Transaction


@runtime_checkable
class ScoringAgent(Protocol):
    name: str

    def score(self, txn: Transaction) -> AgentScore:
        """Score a single transaction. Must not raise for a well-formed Transaction."""
        ...
