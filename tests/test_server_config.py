import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from server import server_bind_settings


class ServerBindSettingsTest(unittest.TestCase):
    def test_defaults_to_localhost(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(server_bind_settings(), ("127.0.0.1", 8765))

    def test_public_bind_requires_demo_mode(self):
        with patch.dict(os.environ, {"HOST": "0.0.0.0", "PORT": "10000"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "DEMO_MODE=1"):
                server_bind_settings()

    def test_public_demo_bind_is_allowed(self):
        environment = {"HOST": "0.0.0.0", "PORT": "10000", "DEMO_MODE": "1"}
        with patch.dict(os.environ, environment, clear=True):
            self.assertEqual(server_bind_settings(), ("0.0.0.0", 10000))


if __name__ == "__main__":
    unittest.main()
