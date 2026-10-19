import os

from fastapi import APIRouter

from fraudlens.api.state import state

router = APIRouter(prefix="/health", tags=["health"])
# Kept off the authenticated /ops router so uptime checks need no token.
public_status_router = APIRouter(prefix="/ops", tags=["health"])


@router.get("")
def health() -> dict:
    return {"status": "ok"}


@public_status_router.get("/public-status")
def public_status() -> dict:
    return {"ready": state.started_at is not None, "mode": os.environ.get("FRAUDLENS_MODE", "demo"),
            "started_at": state.started_at}
