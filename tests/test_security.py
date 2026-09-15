import os
import tempfile
import unittest
from pathlib import Path

from mac_agent import config
from mac_agent.actions import _within_roots, shell_script, system_open_url


class SecurityTests(unittest.TestCase):
    def test_defaults_have_no_user_specific_account(self):
        serialized = repr(config.DEFAULTS).lower()
        self.assertNotIn("@gmail", serialized)
        self.assertNotIn("@icloud", serialized)
        self.assertNotIn("jordan", serialized)
        self.assertNotIn("jmac", serialized)

    def test_all_default_actions_require_confirmation(self):
        self.assertEqual(set(config.DEFAULTS["allowed_actions"]),
                         set(config.DEFAULTS["confirm_actions"]))

    def test_path_guard_blocks_outside_root(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as outside:
            allowed_file = Path(root) / "file.txt"
            outside_file = Path(outside) / "file.txt"
            self.assertTrue(_within_roots(str(allowed_file), [root]))
            self.assertFalse(_within_roots(str(outside_file), [root]))

    def test_open_url_rejects_non_http(self):
        self.assertFalse(system_open_url("file:///etc/passwd")["ok"])

    def test_script_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as scripts:
            result = shell_script("../escape.sh", scripts)
            self.assertFalse(result["ok"])


if __name__ == "__main__":
    unittest.main()
