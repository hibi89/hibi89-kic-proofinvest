"""P177 native localhost launcher boundaries, plus real HTTP CI smoke."""
from __future__ import annotations

import os
from unittest import TestCase
from unittest.mock import patch

from scripts import local_ui_launcher as launch


class LocalNativeLauncherTests(TestCase):
    def test_safe_default_loopback_streamlit_command(self):
        args = launch.command(18571)
        self.assertIn("--server.address=127.0.0.1", args)
        self.assertIn("--server.port=18571", args)
        self.assertIn("--server.enableXsrfProtection=true", args)
        self.assertIn("--server.enableStaticServing=false", args)
        self.assertIn("--browser.gatherUsageStats=false", args)
        self.assertNotIn("0.0.0.0", " ".join(args))

    def test_existing_port_and_privileged_ports_are_rejected(self):
        for p in (0, 80, 1023, 65536, -1, True, "18651"):
            with self.subTest(port=p):
                with self.assertRaises(ValueError):
                    launch.command(p)

    def test_environment_drops_provider_tokens_and_live_toggle(self):
        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "secret",
            "ALPHAVANTAGE_API_KEY": "secret",
            "KUODRA_ENABLE_SEC_FETCH_UI": "1",
            "KUODRA_ENABLE_LOCAL_SOURCE_UI": "1",
            "HTTP_PROXY": "http://unapproved-proxy",
            "PATH": "trusted-path",
        }):
            clean = launch.child_environment()
            self.assertEqual(clean["PATH"], "trusted-path")
            self.assertNotIn("OPENAI_API_KEY", clean)
            self.assertNotIn("ALPHAVANTAGE_API_KEY", clean)
            self.assertNotIn("HTTP_PROXY", clean)
            self.assertEqual(clean["KUODRA_ENABLE_SEC_FETCH_UI"], "0")
            self.assertEqual(clean["KUODRA_ENABLE_LOCAL_SOURCE_UI"], "0")
            self.assertEqual(
                launch.child_environment(local_review=True)[
                    "KUODRA_ENABLE_LOCAL_SOURCE_UI"], "1"
            )

    def test_denies_already_occupied_local_port_without_starting(self):
        with patch.object(launch, "_port_free", return_value=False):
            with patch.object(launch.subprocess, "Popen",
                              side_effect=AssertionError("MUST_NOT_START")):
                result = launch.run(port=18571, smoke=True)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "LOCAL_PORT_OCCUPIED")

    def test_default_mode_avoids_network_permission_escalation(self):
        with patch.object(launch, "APP", launch.APP):
            result = launch.child_environment(local_review=False)
        self.assertEqual(result["KUODRA_ENABLE_SEC_FETCH_UI"], "0")
        self.assertEqual(result["KUODRA_ENABLE_LOCAL_SOURCE_UI"], "0")
