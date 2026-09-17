import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mac_agent.actions import execute
from mac_agent.capabilities import ACCESS_REQUEST, FULL_OPERATOR_PACKS, actions_for_packs, capability_index
from mac_agent.config import load_config
from mac_agent.operator_actions import command_requires_confirmation, files_read, files_write, shell_exec
from mac_agent.ui_actions import ui_key


class OperatorTests(unittest.TestCase):
    def test_full_operator_contains_core_build_actions(self):
        actions = set(actions_for_packs(FULL_OPERATOR_PACKS))
        for expected in {
            "files.list", "files.read", "files.write", "files.mkdir",
            "shell.exec", "process.start", "process.output", "app.open", "clipboard.write",
            "screen.capture", "ui.frontmost", "ui.click", "ui.type", "ui.key",
        }:
            self.assertIn(expected, actions)

    def test_file_write_and_read_stay_inside_root(self):
        with tempfile.TemporaryDirectory() as root:
            target = str(Path(root) / "project" / "hello.txt")
            written = files_write(target, "hello Muse", [root])
            self.assertTrue(written["ok"])
            read = files_read(target, [root])
            self.assertTrue(read["ok"])
            self.assertEqual(read["content"], "hello Muse")

    def test_file_write_rejects_outside_root(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as outside:
            result = files_write(str(Path(outside) / "nope.txt"), "x", [root])
            self.assertFalse(result["ok"])

    def test_shell_exec_rejects_shell_chaining(self):
        with tempfile.TemporaryDirectory() as root:
            result = shell_exec("echo hello; echo nope", root, [root])
            self.assertFalse(result["ok"])
            self.assertIn("shell operators", result["error"])

    def test_shell_exec_rejects_sensitive_executable(self):
        with tempfile.TemporaryDirectory() as root:
            result = shell_exec(["sudo", "echo", "nope"], root, [root])
            self.assertFalse(result["ok"])
            self.assertIn("blocked", result["error"])

    def test_shell_exec_rejects_outside_working_root(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as outside:
            result = shell_exec(["echo", "hello"], outside, [root])
            self.assertFalse(result["ok"])

    def test_full_file_write_allows_path_outside_configured_root(self):
        with tempfile.TemporaryDirectory() as configured, tempfile.TemporaryDirectory() as outside:
            target = str(Path(outside) / "full-mode.txt")
            result = files_write(target, "full access", None)
            self.assertTrue(result["ok"])
            self.assertEqual(files_read(target, None)["content"], "full access")
            self.assertFalse(str(target).startswith(str(configured)))

    def test_full_shell_allows_chaining_and_redirection(self):
        with tempfile.TemporaryDirectory() as work:
            result = shell_exec("printf 'hello' | tr a-z A-Z > result.txt && cat result.txt", work, None)
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["stdout"], "HELLO")
            self.assertEqual((Path(work) / "result.txt").read_text(), "HELLO")

    def test_high_risk_command_detector_requires_confirmation(self):
        for command in ["rm -rf ./build", "sudo installer -pkg x -target /", "security find-generic-password -s x", "diskutil eraseDisk APFS Test disk9"]:
            self.assertTrue(command_requires_confirmation(command), command)
        self.assertFalse(command_requires_confirmation("npm install && npm test"))
        self.assertFalse(command_requires_confirmation("python3 -m unittest discover -s tests"))

    def test_capability_index_describes_real_authority(self):
        restricted = {"mode": "restricted", "enabled_packs": [], "allowed_actions": [], "confirm_actions": [], "allowed_roots": ["/tmp/work"]}
        r = capability_index(restricted)
        self.assertEqual(r["filesystem_scope"], "configured_roots")
        self.assertEqual(r["command_execution"], "restricted")
        self.assertEqual(r["working_roots"], ["/tmp/work"])
        self.assertIn(ACCESS_REQUEST, r["actions"])

        full = {**restricted, "mode": "full", "enabled_packs": list(FULL_OPERATOR_PACKS)}
        f = capability_index(full)
        self.assertEqual(f["filesystem_scope"], "user_accessible")
        self.assertEqual(f["command_execution"], "general")
        self.assertNotIn("working_roots", f)
        self.assertIn("shell.exec", f["actions"])

    def test_access_request_enables_live_config_without_restart(self):
        with tempfile.TemporaryDirectory() as root:
            config_path = str(Path(root) / "config.yaml")
            cfg = load_config(config_path)
            self.assertEqual(cfg["mode"], "restricted")
            with patch("mac_agent.actions._confirm_action", return_value=True):
                result = execute(ACCESS_REQUEST, {}, cfg)
            self.assertTrue(result["ok"])
            self.assertFalse(result["restart_required"])
            self.assertEqual(cfg["mode"], "full")
            self.assertEqual(capability_index(cfg)["filesystem_scope"], "user_accessible")
            self.assertEqual(load_config(config_path)["mode"], "full")

    def test_access_request_denial_keeps_restricted_mode(self):
        with tempfile.TemporaryDirectory() as root:
            cfg = load_config(str(Path(root) / "config.yaml"))
            with patch("mac_agent.actions._confirm_action", return_value=False):
                result = execute(ACCESS_REQUEST, {}, cfg)
            self.assertFalse(result["ok"])
            self.assertEqual(cfg["mode"], "restricted")

    def test_access_request_is_idempotent_when_already_full(self):
        with tempfile.TemporaryDirectory() as root:
            cfg = load_config(str(Path(root) / "config.yaml"))
            cfg["mode"] = "full"
            with patch("mac_agent.actions._confirm_action") as confirm:
                result = execute(ACCESS_REQUEST, {}, cfg)
            self.assertTrue(result["ok"])
            self.assertTrue(result["already_enabled"])
            confirm.assert_not_called()

    def test_ui_key_rejects_unknown_named_key_without_touching_os(self):
        result = ui_key("definitely-not-a-key")
        self.assertFalse(result["ok"])
        self.assertIn("supported", result["error"])

    def test_ui_key_rejects_unknown_modifier_without_touching_os(self):
        result = ui_key("x", ["superpower"])
        self.assertFalse(result["ok"])
        self.assertIn("modifier", result["error"])


if __name__ == "__main__":
    unittest.main()
