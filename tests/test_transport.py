import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from connector.tunnel_mgr import TunnelManager
from mac_agent.config import load_config, save_config


class TransportTests(unittest.TestCase):
    def test_quick_tunnel_remains_default(self):
        with patch("connector.tunnel_mgr.load_config", return_value={"transport_mode": "quick_tunnel"}), \
             patch.object(TunnelManager, "cloudflared_path", return_value="/tmp/cloudflared"):
            manager = TunnelManager.__new__(TunnelManager)
            command = manager._command()
        self.assertEqual(
            command,
            ["/tmp/cloudflared", "tunnel", "--url", "http://127.0.0.1:8899"],
        )

    def test_vps_relay_uses_restricted_reverse_ssh(self):
        with tempfile.TemporaryDirectory() as tmp:
            identity = Path(tmp) / "relay-key"
            identity.write_text("test")
            settings = {
                "transport_mode": "vps_relay",
                "relay_host": "203.0.113.10",
                "relay_user": "lifeos-relay",
                "relay_ssh_port": 22,
                "relay_remote_port": 18899,
                "relay_public_url": "https://mac.example.com",
                "relay_identity_file": str(identity),
            }
            with patch("connector.tunnel_mgr.load_config", return_value=settings), \
                 patch.object(TunnelManager, "ssh_path", return_value="/usr/bin/ssh"):
                manager = TunnelManager.__new__(TunnelManager)
                command = manager._command()

        self.assertIn("BatchMode=yes", command)
        self.assertIn("StrictHostKeyChecking=yes", command)
        self.assertIn("127.0.0.1:18899:127.0.0.1:8899", command)
        self.assertEqual(command[-1], "lifeos-relay@203.0.113.10")

    def test_config_persists_relay_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = Path(tmp) / "config.yaml"
            cfg = load_config(str(cfg_path))
            cfg.update({
                "transport_mode": "vps_relay",
                "relay_host": "203.0.113.10",
                "relay_public_url": "https://mac.example.com/",
                "relay_remote_port": 18899,
            })
            save_config(cfg, str(cfg_path))
            loaded = load_config(str(cfg_path))

        self.assertEqual(loaded["transport_mode"], "vps_relay")
        self.assertEqual(loaded["relay_host"], "203.0.113.10")
        self.assertEqual(loaded["relay_public_url"], "https://mac.example.com")
        self.assertEqual(loaded["relay_remote_port"], 18899)


if __name__ == "__main__":
    unittest.main()
