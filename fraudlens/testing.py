"""Test-only helper: redirect the analyst file and operations database to a throwaway
temp directory instead of the files the live demo server reads from.

Must be called before `from fraudlens.api.main import app` in any test
module that builds a real app/TestClient — RuntimeConfig's path defaults
are read from these env vars at FraudLensRuntime construction time (see
runtime.py), which happens inside the FastAPI lifespan, triggered the
moment a TestClient enters its context.

Deliberately NOT done via tests/__init__.py: `python -m unittest discover
-s tests` imports test_*.py as bare top-level modules rather than as
`tests.test_*`, so the package's __init__.py never runs before them —
verified empirically, not assumed. A plain function in the fraudlens
package itself sidesteps that import-order quirk entirely.
"""

from __future__ import annotations

import os
import tempfile


def use_isolated_data_dir() -> None:
    if "FRAUDLENS_ANALYSTS_PATH" in os.environ:
        return  # already isolated (e.g. called from more than one test module)
    data_dir = tempfile.mkdtemp(prefix="fraudlens-test-data-")
    os.environ["FRAUDLENS_ANALYSTS_PATH"] = os.path.join(data_dir, "analysts.json")
    os.environ["FRAUDLENS_OPS_DB"] = os.path.join(data_dir, "operations.sqlite3")
    os.environ["FRAUDLENS_SEED_DEMO"] = "0"
