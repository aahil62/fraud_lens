"""Roles are persisted, fail closed, and cannot be chosen at registration."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fraudlens.core.auth.roles import can, required_role
from fraudlens.core.auth.store import AnalystStore


class RoleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "analysts.json"
        self.mode = patch.dict("os.environ", {"FRAUDLENS_MODE": "demo"})
        self.mode.start()
        self.addCleanup(self.mode.stop)

    def test_can_respects_rank(self):
        for role, action, allowed in [
            ("l1_analyst", "place_lien", True),
            ("l1_analyst", "restrict", False),
            ("l2_analyst", "close_account", False),
            ("supervisor", "close_account", True),
            ("l2_analyst", "release_lien", True),
            ("l1_analyst", "confirm_fraud", False),
            ("supervisor", "agent_settings", True),
            ("unknown", "claim", False),
        ]:
            with self.subTest(role=role, action=action):
                self.assertEqual(can(role, action), allowed)

    def test_unknown_action_is_denied(self):
        self.assertFalse(can("supervisor", "drop_tables"))
        with self.assertRaises(ValueError):
            required_role("drop_tables")

    def test_seed_roles(self):
        store = AnalystStore(str(self.path))
        for username, role in [
            ("asharma", "supervisor"),
            ("riyer", "l2_analyst"),
            ("kmehta", "l1_analyst"),
            ("pnair", "l1_analyst"),
        ]:
            self.assertEqual(store.get(username).role, role)
        AnalystStore(str(self.path))
        self.assertEqual(len(json.loads(self.path.read_text())), 4)

    def test_legacy_json_without_role_loads_as_l1(self):
        self.path.write_text(
            json.dumps(
                [
                    dict(
                        username=name, display_name=name, password_hash="legacy-hash", created_at="2026-10-18"
                    )
                    for name in ("legacy", "asharma")
                ]
            )
        )
        store = AnalystStore(str(self.path))
        self.assertEqual(store.get("legacy").role, "l1_analyst")
        self.assertEqual(store.get("asharma").role, "supervisor")
        self.assertEqual(store.get("asharma").password_hash, "legacy-hash")
        self.assertIsNotNone(store.get("pnair"))
        self.assertEqual(len(json.loads(self.path.read_text())), 5)

    def test_signup_creates_l1(self):
        store = AnalystStore(str(self.path))
        self.assertEqual(store.create("newbie", "N. Ewbie", "pw12345678").role, "l1_analyst")
        self.assertEqual(AnalystStore(str(self.path)).get("newbie").role, "l1_analyst")
