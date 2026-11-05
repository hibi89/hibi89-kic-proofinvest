"""P243 masked local-only Massive launcher never invokes network on its own."""
from __future__ import annotations

import io
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts import p243_massive_local_ui as launcher

KEY = "SYNTHETICLOCALKEYONLY123"


class MassiveLauncherTests(unittest.TestCase):
    def test_noninteractive_does_not_request_key_or_start_app(self):
        with patch.object(launcher.sys.stdin,"isatty",return_value=False),(
            patch.object(launcher.getpass,"getpass",side_effect=AssertionError("KEY"))),(
            patch.object(launcher.subprocess,"run",side_effect=AssertionError("SUBPROC"))):
            self.assertEqual(launcher.main(),2)

    def test_decline_and_bad_key_never_start(self):
        with patch.object(launcher.sys.stdin,"isatty",return_value=True), (
            patch.object(launcher.sys.stdout,"isatty",return_value=True)), (
            patch("builtins.input",return_value="NO")), (
            patch.object(launcher.subprocess,"run",side_effect=AssertionError("SUBPROC"))):
            self.assertEqual(launcher.main(),2)
        with patch.object(launcher.sys.stdin,"isatty",return_value=True), (
            patch.object(launcher.sys.stdout,"isatty",return_value=True)), (
            patch("builtins.input",return_value=launcher._CONFIRM)), (
            patch.object(launcher.getpass,"getpass",return_value="x&evil")), (
            patch.object(launcher.subprocess,"run",side_effect=AssertionError("SUBPROC"))):
            self.assertEqual(launcher.main(),2)

    def test_masked_key_is_only_in_local_child_environment(self):
        called=[]
        def fake_run(argv,*,cwd,env,check):
            self.assertEqual(argv[:4],[
                launcher.sys.executable,"-m","streamlit","run"])
            self.assertEqual(argv[5:7],["--server.address","127.0.0.1"])
            self.assertEqual(env["MASSIVE_API_KEY"],KEY)
            self.assertEqual(env["KUODRA_ENABLE_MASSIVE_PAIR"],"1")
            self.assertNotIn(KEY,repr(argv))
            called.append((str(cwd),check))
            return SimpleNamespace(returncode=0)
        with patch.object(launcher.sys.stdin,"isatty",return_value=True), (
            patch.object(launcher.sys.stdout,"isatty",return_value=True)), (
            patch("builtins.input",return_value=launcher._CONFIRM)), (
            patch.object(launcher.getpass,"getpass",return_value=KEY)), (
            patch.object(launcher.subprocess,"run",side_effect=fake_run)):
            self.assertEqual(launcher.main(),0)
        self.assertEqual(len(called),1)
        self.assertNotEqual(os.environ.get("MASSIVE_API_KEY"), KEY)

if __name__=="__main__":
    unittest.main()
