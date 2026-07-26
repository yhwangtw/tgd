"""Runtime contracts for the installed SessionStart hook payloads."""

from __future__ import annotations

import json
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


class HookOutputContractTests(unittest.TestCase):
    def run_hook(self, relative: str) -> dict[str, object]:
        result = subprocess.run(
            ["/bin/bash", str(ROOT / relative)],
            input='{"hook_event_name":"SessionStart","source":"startup"}\n',
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=10,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(result.stdout.strip(), relative)
        return json.loads(result.stdout)

    def assert_bounded_preamble(self, payload: dict[str, object]) -> None:
        specific = payload.get("hookSpecificOutput")
        self.assertIsInstance(specific, dict)
        context = specific.get("additionalContext")
        self.assertIsInstance(context, str)
        self.assertIn("Load the `tgd-router` skill", context)
        self.assertLess(len(context), 10_000)
        self.assertNotIn("priority", payload)
        self.assertNotIn("message", payload)

    def test_claude_session_start_schema(self) -> None:
        payload = self.run_hook("hooks/session-start.sh")
        self.assert_bounded_preamble(payload)
        self.assertEqual(
            "SessionStart",
            payload["hookSpecificOutput"]["hookEventName"],
        )

    def test_codex_session_start_schema(self) -> None:
        payload = self.run_hook("hooks/codex/session-start.sh")
        self.assert_bounded_preamble(payload)
        self.assertEqual(
            "SessionStart",
            payload["hookSpecificOutput"]["hookEventName"],
        )

    def test_gemini_session_start_schema(self) -> None:
        payload = self.run_hook("hooks/gemini/session-start.sh")
        self.assert_bounded_preamble(payload)
        self.assertNotIn("hookEventName", payload["hookSpecificOutput"])

    def test_hermes_preamble_is_dormant_by_default_and_once_per_session(self) -> None:
        plugin_path = ROOT / ".hermes" / "plugins" / "tgd" / "__init__.py"
        spec = importlib.util.spec_from_file_location("tgd_hermes_test", plugin_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.TGD_DIR = ROOT
        module._INJECTED_SESSIONS.clear()

        with mock.patch.object(module, "_session_preamble_enabled", return_value=False):
            self.assertIsNone(module._pre_llm_call(session_id="default"))

        with mock.patch.object(module, "_session_preamble_enabled", return_value=True):
            first = module._pre_llm_call(session_id="enabled")
            self.assertIn("Verification Iron Law", first["context"])
            self.assertIsNone(module._pre_llm_call(session_id="enabled"))
            module._on_session_end(session_id="enabled")
            self.assertIsNotNone(module._pre_llm_call(session_id="enabled"))


if __name__ == "__main__":
    unittest.main()
