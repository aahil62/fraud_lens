"""The console's copy of the permission table must match the API's."""

import re
import unittest
from pathlib import Path

from fraudlens.core.auth.roles import ACTION_MIN_ROLE, ROLE_LABEL

ROLES_TS = Path(__file__).resolve().parents[1] / "frontend" / "lib" / "roles.ts"


def frontend_table(name):
    """Read `export const <name>: Record<…> = { key: "value", … };` from roles.ts."""
    source = ROLES_TS.read_text()
    body = re.search(rf"export const {name}\b[^=]*=\s*\{{(.*?)\}};", source, re.S)
    if not body:
        raise AssertionError(f"{name} not found in {ROLES_TS}")
    return dict(re.findall(r'(\w+):\s*"([^"]+)"', body.group(1)))


class RoleParityTests(unittest.TestCase):
    def test_frontend_action_min_role_matches_roles_py(self):
        self.assertEqual(frontend_table("ACTION_MIN_ROLE"), ACTION_MIN_ROLE)

    def test_frontend_role_labels_match_roles_py(self):
        self.assertEqual(frontend_table("ROLE_LABEL"), ROLE_LABEL)


if __name__ == "__main__":
    unittest.main()
