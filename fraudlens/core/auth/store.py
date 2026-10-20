"""Analyst account store — persists to JSON, auto-seeded
with four fictional demonstration accounts so the console is usable
immediately, without requiring signup before anyone can log in.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Optional

from fraudlens.core.auth.security import hash_password, verify_password
from fraudlens.models.schemas import AnalystAccount


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


DEMO_ANALYSTS = {
    "asharma": ("A. Sharma", "supervisor"),
    "riyer": ("R. Iyer", "l2_analyst"),
    "kmehta": ("K. Mehta", "l1_analyst"),
    "pnair": ("P. Nair", "l1_analyst"),
}


def _seed_accounts() -> list[AnalystAccount]:
    if os.environ.get("FRAUDLENS_MODE", "demo") != "demo":
        return []
    return [
        AnalystAccount(
            username=username,
            display_name=display_name,
            role=role,
            password_hash=hash_password("fraudlens123"),
            created_at=_now_iso(),
        )
        for username, (display_name, role) in DEMO_ANALYSTS.items()
    ]


class AnalystStore:
    def __init__(self, path: str = "fraudlens/data/analysts.json") -> None:
        self._path = path
        self._accounts: dict[str, AnalystAccount] = {}
        self._load_or_seed()
        if os.environ.get("FRAUDLENS_MODE", "demo") != "demo":
            for account in self._accounts.values():
                if verify_password("fraudlens123", account.password_hash):
                    raise ValueError("Public demo credentials must be removed before non-demo startup")

    def get(self, username: str) -> Optional[AnalystAccount]:
        return self._accounts.get(username)

    def list(self) -> list[AnalystAccount]:
        return list(self._accounts.values())

    def create(self, username: str, display_name: str, password: str) -> AnalystAccount:
        if username in self._accounts:
            raise ValueError(f"Username {username!r} is already taken")
        account = AnalystAccount(
            username=username,
            display_name=display_name,
            password_hash=hash_password(password),
            created_at=_now_iso(),
        )
        self._accounts[username] = account
        self._persist()
        return account

    def verify(self, username: str, password: str) -> Optional[AnalystAccount]:
        account = self._accounts.get(username)
        if account is None:
            return None
        if not verify_password(password, account.password_hash):
            return None
        return account

    def _load_or_seed(self) -> None:
        if os.path.exists(self._path):
            try:
                with open(self._path, "r") as f:
                    data = json.load(f)
                accounts = {item["username"]: AnalystAccount(**item) for item in data}
                if accounts:
                    self._accounts = accounts
            except (json.JSONDecodeError, KeyError, TypeError):
                pass
        for seed in _seed_accounts():
            if seed.username in self._accounts:
                self._accounts[seed.username].role = seed.role
            else:
                self._accounts[seed.username] = seed
        self._persist()

    def _persist(self) -> None:
        directory = os.path.dirname(self._path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(self._path, "w") as f:
            json.dump([a.model_dump() for a in self._accounts.values()], f, indent=2, default=str)
