"""The simulated bank's durable ledger: accounts, liens, restrictions and idempotent replies.

Every payment and action id is stored with its exact request and reply, so a
retried id returns the original reply and a reused id with a different body
is refused.
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException


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
                db.execute(
                    "ALTER TABLE accounts ADD COLUMN status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','closed'))"
                )

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
        db.execute(
            "INSERT OR IGNORE INTO accounts(account_id,balance_minor) VALUES (?,100000000)", (account_id,)
        )

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
        payload = _json(
            request.model_dump(exclude={"beneficiary_id"} if request.beneficiary_id is None else set())
        )
        with self.connection(write=True) as db:
            existing = self.existing(db, "payments", "txn_id", request.txn_id, payload)
            if existing is not None:
                return existing
            if self.mode(db) == "reject":
                raise HTTPException(503, "Simulator rejected the request")
            self.ensure_account(db, request.account_id)
            reason = self._decline_reason(db, request)
            if reason is None:
                reason = "posted"
                self._transfer(db, request)
            balance = db.execute(
                "SELECT balance_minor FROM accounts WHERE account_id=?", (request.account_id,)
            ).fetchone()[0]
            response = {
                "txn_id": request.txn_id,
                "status": "posted" if reason == "posted" else "declined",
                "reason": reason,
                "balance_minor": balance,
                "bank_reference": f"sim-payment-{uuid4().hex}",
            }
            db.execute("INSERT INTO payments VALUES (?,?,?)", (request.txn_id, payload, _json(response)))
            return response

    def action(self, request):
        payload = _json(
            request.model_dump(exclude={"amount_minor"} if request.amount_minor is None else set())
        )
        with self.connection(write=True) as db:
            existing = self.existing(db, "actions", "action_id", request.action_id, payload)
            if existing is not None:
                return existing
            mode = self.mode(db)
            if mode == "reject":
                raise HTTPException(503, "Simulator rejected the request")
            if request.target_type == "account":
                self.ensure_account(db, request.target_id)
            self._apply_action(db, request)
            active = self._restricted(db, request.target_type, request.target_id)
            response = {
                "action_id": request.action_id,
                "status": "confirmed",
                "restriction_active": active,
                "bank_reference": f"sim-action-{uuid4().hex}",
            }
            if request.operation == "lien":
                response["amount_minor"] = request.amount_minor
            db.execute("INSERT INTO actions VALUES (?,?,?)", (request.action_id, payload, _json(response)))
        # Deliberately outside the transaction: represent a lost acknowledgement,
        # while GET/replay still reconciles the durable bank action.
        if mode == "timeout_after_commit":
            raise HTTPException(504, "Simulated acknowledgement timeout after commit; reconcile action id")
        return response

    @staticmethod
    def _held(db, account_id):
        return db.execute(
            "SELECT COALESCE(SUM(amount_minor),0) FROM liens WHERE account_id=?", (account_id,)
        ).fetchone()[0]

    @staticmethod
    def _restricted(db, target_type, target_id):
        return (
            db.execute(
                "SELECT 1 FROM restrictions WHERE target_type=? AND target_id=? LIMIT 1",
                (target_type, target_id),
            ).fetchone()
            is not None
        )

    def _decline_reason(self, db, request):
        """Why the bank declines this payment, checked in order; None if it can post."""
        account = db.execute(
            "SELECT balance_minor,status FROM accounts WHERE account_id=?", (request.account_id,)
        ).fetchone()
        balance, held = account["balance_minor"], self._held(db, request.account_id)
        if account["status"] == "closed":
            return "account_closed"
        if self._restricted(db, "account", request.account_id):
            return "account_restricted"
        if request.channel in {"card", "atm"} and self._restricted(db, "card", request.instrument_id):
            return "card_restricted"
        if request.amount_minor > balance - held:
            return "lien_hold" if held and request.amount_minor <= balance else "insufficient_funds"
        beneficiary = self._account_status(db, request.beneficiary_id)
        if beneficiary == "closed":
            return "beneficiary_closed"
        return None

    @staticmethod
    def _account_status(db, account_id):
        if not account_id:
            return None
        row = db.execute("SELECT status FROM accounts WHERE account_id=?", (account_id,)).fetchone()
        return row["status"] if row else None

    def _transfer(self, db, request):
        """Debit the payer and, when the beneficiary banks here, credit it."""
        db.execute(
            "UPDATE accounts SET balance_minor=balance_minor-? WHERE account_id=?",
            (request.amount_minor, request.account_id),
        )
        if self._account_status(db, request.beneficiary_id):
            db.execute(
                "UPDATE accounts SET balance_minor=balance_minor+? WHERE account_id=?",
                (request.amount_minor, request.beneficiary_id),
            )

    def _apply_action(self, db, request):
        target = (request.case_id, request.target_type, request.target_id)
        if request.operation == "restrict":
            db.execute("INSERT OR IGNORE INTO restrictions VALUES (?,?,?)", target)
        elif request.operation == "release":
            db.execute("DELETE FROM restrictions WHERE case_id=? AND target_type=? AND target_id=?", target)
        elif request.operation == "lien":
            self._place_lien(db, request)
        elif request.operation == "lien_release":
            db.execute(
                "DELETE FROM liens WHERE case_id=? AND account_id=?", (request.case_id, request.target_id)
            )
        elif request.operation == "close":
            db.execute("UPDATE accounts SET status='closed' WHERE account_id=?", (request.target_id,))

    def _place_lien(self, db, request):
        account = db.execute(
            "SELECT balance_minor,status FROM accounts WHERE account_id=?", (request.target_id,)
        ).fetchone()
        available = account["balance_minor"] - self._held(db, request.target_id)
        if account["status"] == "closed" or request.amount_minor > available:
            raise HTTPException(409, "Account is closed or has insufficient available funds for this lien")
        created_at = datetime.now(timezone.utc).isoformat()
        db.execute(
            "INSERT INTO liens VALUES(?,?,?,?,?)",
            (request.action_id, request.case_id, request.target_id, request.amount_minor, created_at),
        )

    def accounts(self):
        with self.connection() as db:
            accounts = [
                dict(row)
                for row in db.execute("""
                SELECT a.account_id,a.balance_minor,a.status,
                    (SELECT COUNT(*) FROM restrictions r WHERE r.target_type='account'
                        AND r.target_id=a.account_id) AS active_restrictions
                FROM accounts a ORDER BY a.account_id
            """)
            ]
            for account in accounts:
                account["restricted"] = account["active_restrictions"] > 0
                account["liens"] = [
                    dict(row)
                    for row in db.execute(
                        "SELECT lien_id,case_id,amount_minor FROM liens WHERE account_id=? ORDER BY created_at,lien_id",
                        (account["account_id"],),
                    )
                ]
                account["available_minor"] = account["balance_minor"] - sum(
                    lien["amount_minor"] for lien in account["liens"]
                )
                if account["status"] != "closed" and account["restricted"]:
                    account["status"] = "frozen"
            restrictions = [
                dict(row)
                for row in db.execute("SELECT * FROM restrictions ORDER BY case_id,target_type,target_id")
            ]
            return {"accounts": accounts, "restrictions": restrictions}
