"""Runtime assembly for FraudLens.

Holds the analyst account store the API authenticates against. The
operations service, detector and bank client are built separately in
fraudlens/api/main.py's lifespan.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from fraudlens.core.auth.store import AnalystStore


@dataclass(frozen=True)
class RuntimeConfig:
    """Env-overridable so the test suite can point the analyst file at a
    throwaway temp directory (see fraudlens/testing.py) instead of the file
    the live demo server reads from."""

    analysts_path: str = field(
        default_factory=lambda: os.environ.get("FRAUDLENS_ANALYSTS_PATH", "fraudlens/data/analysts.json")
    )


@dataclass
class FraudLensRuntime:
    analyst_store: AnalystStore = field(repr=False)


def build_runtime(config: RuntimeConfig | None = None) -> FraudLensRuntime:
    config = config or RuntimeConfig()
    return FraudLensRuntime(analyst_store=AnalystStore(path=config.analysts_path))
