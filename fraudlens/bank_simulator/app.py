"""Durable, local bank simulator: ``uvicorn fraudlens.bank_simulator.app:app --port 8002``."""

from contextlib import contextmanager
from datetime import datetime, timezone
import hmac
import json
import os
from pathlib import Path
import sqlite3
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator


Identifier = Annotated[str, Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.:@-]+$")]
Mode = Literal["normal", "reject", "timeout_after_commit"]


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)


class PaymentInput(StrictInput):
    txn_id: Identifier
    account_id: Identifier
    channel: Literal["upi", "net_banking", "card", "atm"]
    amount_minor: Annotated[int, Field(gt=0, le=9_000_000_000_000_000)]
    instrument_id: Identifier | None = None
    beneficiary_id: Identifier | None = None

    @model_validator(mode="after")
    def require_instrument(self):
        if self.channel in {"card", "atm"} and not self.instrument_id:
            raise ValueError("Card and ATM transactions require instrument_id")
        return self


class ActionInput(StrictInput):
    action_id: Identifier
    case_id: Identifier
    operation: Literal["restrict", "release", "lien", "lien_release", "close"]
    target_type: Literal["account", "card"]
    target_id: Identifier
    amount_minor: Annotated[int, Field(gt=0, le=9_000_000_000_000_000)] | None = None

    @model_validator(mode="after")
    def action_target_and_amount(self):
        if self.operation == "lien" and self.amount_minor is None:
            raise ValueError("Lien requires a positive amount_minor")
        if self.operation != "lien" and "amount_minor" in self.model_fields_set:
            raise ValueError("amount_minor is only valid for liens")
        if self.operation in {"lien", "lien_release", "close"} and self.target_type != "account":
            raise ValueError("This operation requires an account target")
        return self


class SeedAccountInput(StrictInput):
    account_id: Annotated[str, Field(max_length=80, pattern=r"^SIM-[A-Za-z0-9_.:@-]+$")]
    balance_minor: Annotated[int, Field(ge=0, le=100_000_000)]


class SeedInput(StrictInput):
    accounts: Annotated[list[SeedAccountInput], Field(min_length=1, max_length=20)]


class ControlInput(StrictInput):
    mode: Mode


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


class Ledger:
    def __init__(self, db_path):
        self.path = str(db_path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connection(write=True) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS accounts (
                    account_id TEXT PRIMARY KEY,
                    balance_minor INTEGER NOT NULL CHECK (balance_minor >= 0)
                );
                CREATE TABLE IF NOT EXISTS liens (
                    lien_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, account_id TEXT NOT NULL,
                    amount_minor INTEGER NOT NULL CHECK(amount_minor > 0), created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS restrictions (
                    case_id TEXT NOT NULL,
                    target_type TEXT NOT NULL CHECK (target_type IN ('account','card')),
                    target_id TEXT NOT NULL,
                    PRIMARY KEY (case_id,target_type,target_id)
                );
                CREATE INDEX IF NOT EXISTS restriction_target
                    ON restrictions(target_type,target_id);
                CREATE TABLE IF NOT EXISTS payments (
                    txn_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    response TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS actions (
                    action_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    response TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                INSERT OR IGNORE INTO settings VALUES ('mode','normal');
            """)
            if "status" not in {row["name"] for row in db.execute("PRAGMA table_info(accounts)")}:
                db.execute("ALTER TABLE accounts ADD COLUMN status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','closed'))")

    @contextmanager
    def connection(self, write=False):
        db = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA foreign_keys=ON")
        try:
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def mode(db):
        return db.execute("SELECT value FROM settings WHERE key='mode'").fetchone()[0]

    @staticmethod
    def ensure_account(db, account_id):
        db.execute("INSERT OR IGNORE INTO accounts(account_id,balance_minor) VALUES (?,100000000)", (account_id,))

    @staticmethod
    def existing(db, table, column, identifier, payload):
        # table and column are internal constants, never request values.
        row = db.execute(f"SELECT payload,response FROM {table} WHERE {column}=?", (identifier,)).fetchone()
        if row is None:
            return None
        if row["payload"] != payload:
            raise HTTPException(409, "Identifier already belongs to a different request")
        return json.loads(row["response"])

    def payment(self, request):
        payload = _json(request.model_dump(exclude={"beneficiary_id"} if request.beneficiary_id is None else set()))
        with self.connection(write=True) as db:
            existing = self.existing(db, "payments", "txn_id", request.txn_id, payload)
            if existing is not None:
                return existing
            if self.mode(db) == "reject":
                raise HTTPException(503, "Simulator rejected the request")
            self.ensure_account(db, request.account_id)
            account = db.execute("SELECT balance_minor,status FROM accounts WHERE account_id=?", (request.account_id,)).fetchone()
            balance = account["balance_minor"]
            lien = db.execute("SELECT COALESCE(SUM(amount_minor),0) FROM liens WHERE account_id=?", (request.account_id,)).fetchone()[0]
            beneficiary = db.execute("SELECT status FROM accounts WHERE account_id=?", (request.beneficiary_id,)).fetchone() if request.beneficiary_id else None
            restricted = db.execute("SELECT 1 FROM restrictions WHERE target_type='account' AND target_id=? LIMIT 1", (request.account_id,)).fetchone()
            card_restricted = db.execute("SELECT 1 FROM restrictions WHERE target_type='card' AND target_id=? LIMIT 1", (request.instrument_id,)).fetchone() if request.channel in {"card", "atm"} else None
            if account["status"] == "closed":
                reason = "account_closed"
            elif restricted:
                reason = "account_restricted"
            elif card_restricted:
                reason = "card_restricted"
            elif request.amount_minor > balance - lien:
                reason = "lien_hold" if lien and request.amount_minor <= balance else "insufficient_funds"
            elif beneficiary and beneficiary["status"] == "closed":
                reason = "beneficiary_closed"
            else:
                reason = "posted"
                balance -= request.amount_minor
                db.execute("UPDATE accounts SET balance_minor=? WHERE account_id=?", (balance, request.account_id))
                if beneficiary:
                    db.execute("UPDATE accounts SET balance_minor=balance_minor+? WHERE account_id=?", (request.amount_minor, request.beneficiary_id))
                balance = db.execute("SELECT balance_minor FROM accounts WHERE account_id=?", (request.account_id,)).fetchone()[0]
            response = {"txn_id": request.txn_id, "status": "posted" if reason == "posted" else "declined",
                        "reason": reason, "balance_minor": balance, "bank_reference": f"sim-payment-{uuid4().hex}"}
            db.execute("INSERT INTO payments VALUES (?,?,?)", (request.txn_id, payload, _json(response)))
            return response

    def action(self, request):
        payload = _json(request.model_dump(exclude={"amount_minor"} if request.amount_minor is None else set()))
        with self.connection(write=True) as db:
            existing = self.existing(db, "actions", "action_id", request.action_id, payload)
            if existing is not None:
                return existing
            mode = self.mode(db)
            if mode == "reject":
                raise HTTPException(503, "Simulator rejected the request")
            if request.target_type == "account":
                self.ensure_account(db, request.target_id)
            target = (request.case_id, request.target_type, request.target_id)
            if request.operation == "restrict":
                db.execute("INSERT OR IGNORE INTO restrictions VALUES (?,?,?)", target)
            elif request.operation == "release":
                db.execute("DELETE FROM restrictions WHERE case_id=? AND target_type=? AND target_id=?", target)
            elif request.operation == "lien":
                account = db.execute("SELECT balance_minor,status FROM accounts WHERE account_id=?", (request.target_id,)).fetchone()
                held = db.execute("SELECT COALESCE(SUM(amount_minor),0) FROM liens WHERE account_id=?", (request.target_id,)).fetchone()[0]
                if account["status"] == "closed" or request.amount_minor > account["balance_minor"] - held:
                    raise HTTPException(409, "Account is closed or has insufficient available funds for this lien")
                db.execute("INSERT INTO liens VALUES(?,?,?,?,?)", (request.action_id, request.case_id, request.target_id,
                           request.amount_minor, datetime.now(timezone.utc).isoformat()))
            elif request.operation == "lien_release":
                db.execute("DELETE FROM liens WHERE case_id=? AND account_id=?", (request.case_id, request.target_id))
            elif request.operation == "close":
                db.execute("UPDATE accounts SET status='closed' WHERE account_id=?", (request.target_id,))
            active = db.execute("SELECT 1 FROM restrictions WHERE target_type=? AND target_id=? LIMIT 1", (request.target_type, request.target_id)).fetchone() is not None
            response = {"action_id": request.action_id, "status": "confirmed", "restriction_active": active,
                        "bank_reference": f"sim-action-{uuid4().hex}"}
            if request.operation == "lien":
                response["amount_minor"] = request.amount_minor
            db.execute("INSERT INTO actions VALUES (?,?,?)", (request.action_id, payload, _json(response)))
        # Deliberately outside the transaction: represent a lost acknowledgement,
        # while GET/replay still reconciles the durable bank action.
        if mode == "timeout_after_commit":
            raise HTTPException(504, "Simulated acknowledgement timeout after commit; reconcile action id")
        return response

    def accounts(self):
        with self.connection() as db:
            accounts = [dict(row) for row in db.execute("""
                SELECT a.account_id,a.balance_minor,a.status,
                    (SELECT COUNT(*) FROM restrictions r WHERE r.target_type='account'
                        AND r.target_id=a.account_id) AS active_restrictions
                FROM accounts a ORDER BY a.account_id
            """)]
            for account in accounts:
                account["restricted"] = account["active_restrictions"] > 0
                account["liens"] = [dict(row) for row in db.execute(
                    "SELECT lien_id,case_id,amount_minor FROM liens WHERE account_id=? ORDER BY created_at,lien_id", (account["account_id"],))]
                account["available_minor"] = account["balance_minor"] - sum(lien["amount_minor"] for lien in account["liens"])
                if account["status"] != "closed" and account["restricted"]:
                    account["status"] = "frozen"
            restrictions = [dict(row) for row in db.execute("SELECT * FROM restrictions ORDER BY case_id,target_type,target_id")]
            return {"accounts": accounts, "restrictions": restrictions}


def create_app(db_path=None, api_key=None):
    key = api_key if api_key is not None else os.environ.get("FRAUDLENS_BANK_KEY", "fraudlens-local-simulator")
    if os.environ.get("FRAUDLENS_MODE", "demo") != "demo" and (key == "fraudlens-local-simulator" or len(key) < 32):
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
                db.execute("INSERT OR IGNORE INTO accounts(account_id,balance_minor) VALUES(?,?)",
                           (account.account_id, account.balance_minor))
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
