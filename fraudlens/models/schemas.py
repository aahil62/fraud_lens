"""Shared data contracts for FraudLens.

Every branch builds against these models — they don't change per branch.
Field names and semantics match the team's Level 1 prototype so results
stay comparable across the rebuild.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from fraudlens.core.auth.roles import Role


# ── Enums ─────────────────────────────────────────────────────────────────

class Decision(str, Enum):
    CLEAR = "clear"
    REVIEW = "review"
    BLOCK = "block"
    BLOCK_AND_REPORT = "block_and_report"


# ── Transaction ───────────────────────────────────────────────────────────

class Transaction(BaseModel):
    txn_id: str
    account_id: str
    amount: float
    merchant_id: str
    merchant_category: str
    device_id: str
    ip_address: str
    timestamp: str
    location: str = ""
    channel: str = "online"
    # Ground truth from the synthetic generator — never used by scoring
    # agents at inference time, only for benchmarking and demo labeling.
    is_fraud_demo_label: bool = False
    fraud_pattern_type: str = "normal"


# ── Scoring ───────────────────────────────────────────────────────────────

class AgentScore(BaseModel):
    """Output from a single scoring agent — the contract every agent implements."""
    agent_name: str
    score: float                        # 0.0 - 1.0
    confidence: float = 0.8             # 0.0 - 1.0
    reasons: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ScoringResult(BaseModel):
    """Combined output from the ensemble scorer."""
    final_score: float
    decision: Decision
    confidence: float
    agent_scores: list[AgentScore]
    explanation_reasons: list[str]


class GraphEvidence(BaseModel):
    connected_accounts: list[str] = Field(default_factory=list)
    shared_devices: list[str] = Field(default_factory=list)
    shared_ips: list[str] = Field(default_factory=list)
    shared_merchants: list[str] = Field(default_factory=list)
    ring_size: int = 0
    ring_id: Optional[str] = None
    suspicious_cluster: bool = False
    graph_density: float = 0.0
    evidence_summary: str = ""


# ── Autonomous account restriction ───────────────────────────────────────
#
# The second half of "bounded autonomous action": alongside auto-holding a
# single case, the system can tighten an account's velocity thresholds
# going forward — a real, measurable consequence, not just another label.
# See fraudlens/core/cases/account_restriction.py.

class AccountRestriction(BaseModel):
    account_id: str
    reason_txn_id: str
    reason_case_id: str
    applied_at: str
    released_at: Optional[str] = None
    released_by: Optional[str] = None

    @property
    def is_active(self) -> bool:
        return self.released_at is None


# ── Analyst authentication ───────────────────────────────────────────────

class AnalystAccount(BaseModel):
    """Internal record — password_hash never leaves the backend. See
    AnalystProfile for what an API response is allowed to expose."""
    username: str
    display_name: str
    password_hash: str
    created_at: str
    role: Role = "l1_analyst"


class AnalystProfile(BaseModel):
    """The public-safe view of an AnalystAccount — no password_hash."""
    username: str
    display_name: str
    role: Role


class SignupRequest(BaseModel):
    username: str
    display_name: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    analyst: AnalystProfile
