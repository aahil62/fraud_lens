"""FraudLens — FastAPI application.

Run with: uvicorn fraudlens.api.main:app --reload --port 8001
"""

from __future__ import annotations

import os
import asyncio
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fraudlens.api.case_cache import all_cases
from fraudlens.api.routes.auth import router as auth_router
from fraudlens.api.routes.cases import router as cases_router
from fraudlens.api.routes.console import router as console_router
from fraudlens.api.routes.copilot import router as copilot_router
from fraudlens.api.routes.decisions import router as decisions_router
from fraudlens.api.routes.health import public_status_router, router as health_router
from fraudlens.api.routes.live import router as live_router
from fraudlens.api.routes.reports import router as reports_router
from fraudlens.api.routes.stats import router as stats_router
from fraudlens.api.routes.transactions import router as transactions_router
from fraudlens.api.routes.operations import router as operations_router
from fraudlens.api.state import state
from fraudlens.runtime import build_runtime
from fraudlens.operations.service import OperationsService
from fraudlens.operations.detector import CHANNELS
from fraudlens.operations.attacks import PublicAttacks
from fraudlens.api.routes.public import mount_public_routes
from fraudlens.api.limits import LoginLimiter


def initial_simulation_config():
    """Synthetic stream on first seed. The public container starts it paused and slow."""
    return {"running": os.environ.get("FRAUDLENS_SIMULATION_RUNNING", "1") == "1",
            "interval_seconds": float(os.environ.get("FRAUDLENS_SIMULATION_INTERVAL", "5"))}


async def operation_worker(operations):
    last_tick = time.monotonic()
    tick = 0
    while True:
        try:
            await asyncio.to_thread(operations.process_jobs)
            with operations.store.connect() as db:
                config = operations.store.setting(db, "simulation", {"running": False, "interval_seconds": 5})
            if config["running"] and time.monotonic() - last_tick >= config["interval_seconds"]:
                channel = CHANNELS[tick % len(CHANNELS)]
                await asyncio.to_thread(operations.run_scenario, channel, "fraud" if tick % 7 == 6 else "normal")
                tick += 1
                last_tick = time.monotonic()
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.getLogger("fraudlens.operations").exception("Operational worker failed; durable jobs remain queued")
        await asyncio.sleep(.5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    state.runtime = build_runtime()
    # Operational screens never read the historical preloaded case cache.
    # Only explicitly requested legacy demonstrations need to warm it.
    if os.environ.get("FRAUDLENS_LEGACY_WARM_CACHE") == "1":
        all_cases(state.runtime)
    state.operations = OperationsService(os.environ.get("FRAUDLENS_OPS_DB", "var/operations.sqlite3"),
        bank_url=os.environ.get("FRAUDLENS_BANK_URL", "http://127.0.0.1:8002"),
        bank_key=os.environ.get("FRAUDLENS_BANK_KEY", "fraudlens-local-simulator"), analysts=state.runtime.analyst_store)
    if os.environ.get("FRAUDLENS_SEED_DEMO") == "1":
        await asyncio.to_thread(state.operations.seed_baseline)
        with state.operations.store.connect(write=True) as db:
            if state.operations.store.setting(db, "simulation") is None:
                state.operations.store.set_setting(db, "simulation", initial_simulation_config())
    state.attacks = PublicAttacks(state.operations)
    state.login_limiter = LoginLimiter()
    state.started_at = datetime.now(timezone.utc).isoformat()
    worker = asyncio.create_task(operation_worker(state.operations))
    try:
        yield
    finally:
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass
        state.operations.close()
        state.attacks = None
        state.started_at = None


app = FastAPI(
    title="FraudLens API",
    description="AI Fraud Intelligence & Regulatory CaseOps Platform",
    version="0.2.0",
    lifespan=lifespan,
)

# Wildcard origin + credentials is an invalid combination — pin to the
# local frontend dev origin, override via FRAUDLENS_CORS_ORIGINS (comma
# separated) once feature/frontend has a deployed URL.
_cors_origins = os.environ.get(
    "FRAUDLENS_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins if o.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(health_router)
app.include_router(public_status_router)
if os.environ.get("FRAUDLENS_LEGACY_API", "1") == "1":
    # Compatibility API for historical fixtures. The supported showcase
    # runner disables it; /ops is the only console data source.
    for legacy_router in (transactions_router, cases_router, reports_router, decisions_router,
                          copilot_router, stats_router, console_router, live_router):
        app.include_router(legacy_router)
app.include_router(operations_router)

mount_public_routes(app)
