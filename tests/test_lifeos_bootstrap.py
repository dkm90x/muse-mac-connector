import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from connector import config
from connector.app import ConnectorApp


class LifeOSBootstrapTests(unittest.TestCase):
    def test_source_prefers_environment_setting(self):
        with tempfile.TemporaryDirectory() as root:
            source_file = Path(root) / "source"
            source_file.write_text("file:///fallback")
            with patch.object(config, "LIFEOS_BOOTSTRAP_SOURCE_FILE", source_file):
                with patch.dict(
                    os.environ,
                    {"LIFEOS_BOOTSTRAP_SOURCE": "github:owner/repo/AGENT_BOOTSTRAP.md"},
                ):
                    self.assertEqual(
                        config.lifeos_bootstrap_source(),
                        "github:owner/repo/AGENT_BOOTSTRAP.md",
                    )

    def test_source_falls_back_to_local_setting_file(self):
        with tempfile.TemporaryDirectory() as root:
            source_file = Path(root) / "source"
            source_file.write_text(
                "file:///LifeOS/chief-of-staff/AGENT_BOOTSTRAP.md\n"
            )
            with patch.object(config, "LIFEOS_BOOTSTRAP_SOURCE_FILE", source_file):
                with patch.dict(os.environ, {}, clear=False):
                    os.environ.pop("LIFEOS_BOOTSTRAP_SOURCE", None)
                    self.assertEqual(
                        config.lifeos_bootstrap_source(),
                        "file:///LifeOS/chief-of-staff/AGENT_BOOTSTRAP.md",
                    )

    def test_connection_prompt_points_to_lifeos_without_copying_rules(self):
        connector = ConnectorApp.__new__(ConnectorApp)
        connector.tunnel = SimpleNamespace(public_url="https://example.test")
        with patch.object(
            config,
            "lifeos_bootstrap_source",
            return_value="github:owner/repo/chief-of-staff/AGENT_BOOTSTRAP.md",
        ):
            prompt = ConnectorApp._connection_prompt(connector)

        self.assertIn("LifeOS Chief-of-Staff bootstrap", prompt)
        self.assertIn(
            "github:owner/repo/chief-of-staff/AGENT_BOOTSTRAP.md",
            prompt,
        )
        self.assertIn("Treat LifeOS as canonical", prompt)
        self.assertIn("Do not maintain a separate copy", prompt)


if __name__ == "__main__":
    unittest.main()
