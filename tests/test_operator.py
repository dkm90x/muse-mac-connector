import tempfile
import unittest
from pathlib import Path

from mac_agent.capabilities import FULL_OPERATOR_PACKS, actions_for_packs
from mac_agent.operator_actions import files_read, files_write, shell_exec
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
