"""Runtime contracts for the installed SessionStart hook payloads."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import unittest


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


if __name__ == "__main__":
    unittest.main()
