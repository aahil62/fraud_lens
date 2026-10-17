"""Small transactional document store with durable action delivery and audit cursor.

JSON payloads preserve the API contract; SQL enforces unique identities and
foreign keys. The showcase supports a single operational API worker.
"""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


def dump(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class Store:
    TABLES = {"transactions", "cases", "actions"}

    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect(write=None) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS cases (
                    id TEXT PRIMARY KEY, txn_id TEXT UNIQUE NOT NULL REFERENCES transactions(id), data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS actions (
                    id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id), data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, kind TEXT NOT NULL, resource_id TEXT NOT NULL,
                    done INTEGER NOT NULL DEFAULT 0, next_at REAL NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, data TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS pending_jobs ON jobs(done, next_at);
                CREATE INDEX IF NOT EXISTS case_actions ON actions(case_id);
            """)

    @contextmanager
    def connect(self, write=False):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        if write is not None:
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def get(self, db, table, identifier):
        assert table in self.TABLES
        row = db.execute(f"SELECT data FROM {table} WHERE id=?", (identifier,)).fetchone()
        return json.loads(row[0]) if row else None

    def records(self, db, table):
        assert table in self.TABLES
        return [json.loads(r[0]) for r in db.execute(f"SELECT data FROM {table} ORDER BY rowid DESC")]

    def update(self, db, table, identifier, value):
        assert table in self.TABLES
        db.execute(f"UPDATE {table} SET data=? WHERE id=?", (dump(value), identifier))

    def event(self, db, event_type, message, *, case_id=None, txn_id=None, actor="system", metadata=None):
        value = dict(event_type=event_type, message=message, case_id=case_id, txn_id=txn_id,
                     actor=actor, occurred_at=now(), metadata=metadata or {})
        cursor = db.execute("INSERT INTO events(data) VALUES(?)", (dump(value),)).lastrowid
        return {"id": cursor, **value}

    def events(self, db, limit=200):
        return [{"id": row[0], **json.loads(row[1])}
                for row in db.execute("SELECT id,data FROM events ORDER BY id DESC LIMIT ?", (limit,))]

    def setting(self, db, key, default=None):
        row = db.execute("SELECT data FROM settings WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set_setting(self, db, key, value):
        db.execute("INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET data=excluded.data", (key, dump(value)))
