"""Unauthenticated, rate-limited fiction only; absent outside demo mode."""
import os

from fastapi import APIRouter, HTTPException, Request

from fraudlens.api.routes.operations import OperationsRoute
from fraudlens.api.state import state
from fraudlens.operations.attacks import AttackInput

router = APIRouter(prefix="/public", tags=["public simulation"], route_class=OperationsRoute)


def attacks():
    if state.attacks is None:
        raise HTTPException(503, "Simulation is starting")
    return state.attacks


@router.post("/attacks")
def launch(payload: AttackInput, request: Request):
    service = attacks()
    service.limit(request.client.host if request.client else "unknown")
    return service.launch(payload)


@router.get("/attacks/{attack_id}")
def status(attack_id: str):
    return attacks().status(attack_id)


@router.post("/attacks/{attack_id}/report-1930")
def report(attack_id: str, request: Request):
    service = attacks()
    service.limit(request.client.host if request.client else "unknown")
    return service.report_1930(attack_id)


def mount_public_routes(app, *, mode=None):
    if (mode or os.environ.get("FRAUDLENS_MODE", "demo")) == "demo":
        app.include_router(router)
