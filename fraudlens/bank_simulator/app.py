"""Durable, local bank simulator: ``uvicorn fraudlens.bank_simulator.app:app --port 8002``."""

import hmac
import json
import os
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException

from .inputs import ActionInput, ControlInput, PaymentInput, SeedInput
from .ledger import Ledger

__all__ = ["Ledger", "app", "create_app"]


def create_app(db_path=None, api_key=None):
    key = (
        api_key if api_key is not None else os.environ.get("FRAUDLENS_BANK_KEY", "fraudlens-local-simulator")
    )
    if os.environ.get("FRAUDLENS_MODE", "demo") != "demo" and (
        key == "fraudlens-local-simulator" or len(key) < 32
    ):
        raise ValueError("A private simulator key of at least 32 characters is required outside demo mode")
    ledger = Ledger(db_path or os.environ.get("FRAUDLENS_BANK_DB", "var/bank.sqlite3"))
    if not key:
        raise ValueError("Bank simulator API key must not be empty")
    app = FastAPI(title="FraudLens simulated bank", version="1.0.0")
    app.state.ledger = ledger

    def authenticate(x_bank_key: Annotated[str | None, Header()] = None):
        if x_bank_key is None or not hmac.compare_digest(x_bank_key.encode(), key.encode()):
            raise HTTPException(401, "Invalid simulator key")

    bank = APIRouter(prefix="/bank", dependencies=[Depends(authenticate)])

    @app.get("/health")
    def health():
        return {"status": "ok", "simulation": True}

    @bank.post("/transactions")
    def payment(request: PaymentInput):
        return ledger.payment(request)

    @bank.post("/actions")
    def action(request: ActionInput):
        return ledger.action(request)

    @bank.get("/actions/{action_id}")
    def get_action(action_id: str):
        with ledger.connection() as db:
            row = db.execute("SELECT response FROM actions WHERE action_id=?", (action_id,)).fetchone()
            if row is None:
                raise HTTPException(404, "Bank action not found")
            return json.loads(row[0])

    @bank.get("/accounts")
    def accounts():
        return ledger.accounts()

    @bank.post("/accounts/seed")
    def seed(request: SeedInput):
        if os.environ.get("FRAUDLENS_MODE", "demo") != "demo":
            raise HTTPException(404, "Not found")
        with ledger.connection(write=True) as db:
            for account in request.accounts:
                db.execute(
                    "INSERT OR IGNORE INTO accounts(account_id,balance_minor) VALUES(?,?)",
                    (account.account_id, account.balance_minor),
                )
        return {"simulation": True, "accounts": [a.account_id for a in request.accounts]}

    @bank.post("/control")
    def control(request: ControlInput):
        with ledger.connection(write=True) as db:
            db.execute("UPDATE settings SET value=? WHERE key='mode'", (request.mode,))
        return {"mode": request.mode}

    @bank.get("/status")
    def status():
        with ledger.connection() as db:
            return {"simulation": True, "mode": ledger.mode(db)}

    app.include_router(bank)
    return app


app = create_app()
