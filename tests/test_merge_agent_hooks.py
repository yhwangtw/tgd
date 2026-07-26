#!/usr/bin/env python3
"""Contract tests for the cross-platform tGD hook lifecycle CLI."""

import json
import os
import shlex
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "merge-agent-hooks.py"


class MergeAgentHooksTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.repo = self.root / "repo with ' quote $(touch PWNED)"
        for relative in (
            "hooks/session-start.sh",
            "hooks/codex/session-start.sh",
            "hooks/gemini/session-start.sh",
        ):
            path = self.repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("#!/bin/bash\n", encoding="utf-8")

    def run_cli(
        self,
        action,
        platform,
        destination,
        *,
        repo=None,
        env=None,
        expected_returncode=0,
    ):
        command = [
            sys.executable,
            str(SCRIPT),
            action,
            "--platform",
            platform,
            "--repo-root",
            str(repo or self.repo),
            "--destination",
            str(destination),
        ]
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(
            expected_returncode,
            result.returncode,
            msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        return result

    @staticmethod
    def write_json(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def read_json(path):
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def commands(value):
        found = []
        if isinstance(value, dict):
            command = value.get("command")
            if isinstance(command, str):
                found.append(command)
            for child in value.values():
                found.extend(MergeAgentHooksTests.commands(child))
        elif isinstance(value, list):
            for child in value:
                found.extend(MergeAgentHooksTests.commands(child))
        return found

    def assert_one_canonical_command(self, config, expected_script):
        commands = self.commands(config)
        canonical = [
            command
            for command in commands
            if shlex.split(command) == ["bash", str(expected_script.resolve())]
        ]
        self.assertEqual(1, len(canonical), commands)

    def test_claude_install_preserves_foreign_hooks_removes_legacy_and_is_idempotent(
        self,
    ):
        destination = self.root / "claude" / "settings.json"
        foreign = "bash /opt/company/hooks/session-start.sh"
        foreign_tgd_prefix = "bash /opt/tgd-monitor/hooks/session-start.sh"
        config = {
            "permissions": {"allow": ["Read"]},
            "hooks": {
                "PostToolUse": [],
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [{"type": "command", "command": "foreign-pre"}],
                    }
                ],
                "SessionStart": [
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": "bash /Users/old/tGD/hooks/session-start.sh",
                            },
                            {"type": "command", "command": foreign},
                            {"type": "command", "command": foreign_tgd_prefix},
                        ]
                    },
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": (
                                    "bash ${CLAUDE_PLUGIN_ROOT}/hooks/session-start.sh"
                                ),
                            }
                        ]
                    },
                ],
            },
        }
        self.write_json(destination, config)

        self.run_cli("install", "claude", destination)
        installed = self.read_json(destination)
        self.assertEqual(config["permissions"], installed["permissions"])
        self.assertEqual([], installed["hooks"]["PostToolUse"])
        self.assertIn("foreign-pre", self.commands(installed))
        self.assertIn(foreign, self.commands(installed))
        self.assertIn(foreign_tgd_prefix, self.commands(installed))
        self.assertNotIn(
            "bash /Users/old/tGD/hooks/session-start.sh", self.commands(installed)
        )
        self.assertNotIn(
            "bash ${CLAUDE_PLUGIN_ROOT}/hooks/session-start.sh",
            self.commands(installed),
        )
        self.assert_one_canonical_command(
            installed, self.repo / "hooks" / "session-start.sh"
        )

        first_install = destination.read_bytes()
        self.run_cli("install", "claude", destination)
        self.assertEqual(first_install, destination.read_bytes())

    def test_codex_install_keeps_foreign_hook_and_installs_only_codex_contract(self):
        destination = self.root / "codex" / "hooks.json"
        foreign = "bash /opt/company/codex-start.sh"
        self.write_json(
            destination,
            {
                "other": {"keep": True},
                "hooks": {
                    "SessionStart": [
                        {
                            "matcher": "startup|resume",
                            "hooks": [
                                {"type": "command", "command": foreign},
                                {
                                    "type": "command",
                                    "command": (
                                        "bash /Users/old/tGD/hooks/codex/session-start.sh"
                                    ),
                                },
                            ],
                        },
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": (
                                        "bash /Users/old/tGD/hooks/session-start.sh"
                                    ),
                                }
                            ]
                        },
                    ]
                },
            },
        )

        self.run_cli("install", "codex", destination)
        installed = self.read_json(destination)
        self.assertEqual({"keep": True}, installed["other"])
        self.assertIn(foreign, self.commands(installed))
        self.assertNotIn(
            "bash /Users/old/tGD/hooks/session-start.sh", self.commands(installed)
        )
        self.assert_one_canonical_command(
            installed, self.repo / "hooks" / "codex" / "session-start.sh"
        )
        canonical_entries = [
            entry
            for entry in installed["hooks"]["SessionStart"]
            if any(
                shlex.split(command)
                == [
                    "bash",
                    str((self.repo / "hooks" / "codex" / "session-start.sh").resolve()),
                ]
                for command in self.commands(entry)
            )
        ]
        self.assertEqual("startup|resume", canonical_entries[0]["matcher"])
        self.assertEqual(
            "Loading tGD meta-skill",
            canonical_entries[0]["hooks"][0]["statusMessage"],
        )

    def test_gemini_install_preserves_foreign_hook_with_same_matcher(self):
        destination = self.root / "gemini" / "settings.json"
        foreign = {
            "name": "company-session-start",
            "type": "command",
            "command": "bash /opt/company/gemini-start.sh",
        }
        self.write_json(
            destination,
            {
                "theme": "dark",
                "hooks": {
                    "SessionStart": [
                        {
                            "matcher": "*",
                            "hooks": [
                                foreign,
                                {
                                    "name": "tgd-session-start",
                                    "type": "command",
                                    "command": (
                                        "bash /Users/old/tGD/hooks/gemini/session-start.sh"
                                    ),
                                },
                            ],
                        }
                    ]
                },
            },
        )

        self.run_cli("install", "gemini", destination)
        installed = self.read_json(destination)
        self.assertEqual("dark", installed["theme"])
        self.assertIn(foreign["command"], self.commands(installed))
        self.assert_one_canonical_command(
            installed, self.repo / "hooks" / "gemini" / "session-start.sh"
        )
        tgd_named_hooks = []
        for entry in installed["hooks"]["SessionStart"]:
            for hook in entry.get("hooks", []):
                if hook.get("name") == "tgd-session-start":
                    tgd_named_hooks.append(hook)
        self.assertEqual(1, len(tgd_named_hooks))

    def test_remove_cleans_legacy_and_canonical_hooks_but_preserves_foreign_hooks(self):
        platform_scripts = {
            "claude": "hooks/session-start.sh",
            "codex": "hooks/codex/session-start.sh",
            "gemini": "hooks/gemini/session-start.sh",
        }
        for platform, relative_script in platform_scripts.items():
            with self.subTest(platform=platform):
                destination = self.root / platform / "settings.json"
                foreign = f"bash /opt/company/{platform}-start.sh"
                self.write_json(
                    destination,
                    {
                        "keep": platform,
                        "hooks": {
                            "SessionStart": [
                                {
                                    "matcher": "*",
                                    "hooks": [
                                        {"type": "command", "command": foreign},
                                        {
                                            "name": "tgd-session-start",
                                            "type": "command",
                                            "command": (
                                                "bash /Users/old/tGD/hooks/"
                                                f"{platform}/session-start.sh"
                                            ),
                                        },
                                    ],
                                }
                            ]
                        },
                    },
                )
                self.run_cli("install", platform, destination)
                self.assert_one_canonical_command(
                    self.read_json(destination), self.repo / relative_script
                )

                self.run_cli("remove", platform, destination)
                removed = self.read_json(destination)
                self.assertEqual(platform, removed["keep"])
                self.assertEqual([foreign], self.commands(removed))

    def test_remove_missing_destination_is_a_noop(self):
        destination = self.root / "missing" / "settings.json"
        self.run_cli("remove", "claude", destination)
        self.assertFalse(destination.exists())

    def test_invalid_json_fails_without_changing_destination(self):
        destination = self.root / "invalid" / "settings.json"
        destination.parent.mkdir(parents=True)
        destination.write_text('{"hooks": ', encoding="utf-8")
        before = destination.read_bytes()

        self.run_cli("install", "claude", destination, expected_returncode=1)
        self.assertEqual(before, destination.read_bytes())

    def test_symlink_destination_is_rejected_without_touching_target(self):
        target = self.root / "dotfiles" / "settings.json"
        self.write_json(target, {"foreign": True})
        destination = self.root / "claude" / "settings.json"
        destination.parent.mkdir(parents=True)
        destination.symlink_to(target)
        before = target.read_bytes()

        self.run_cli("install", "claude", destination, expected_returncode=1)
        self.assertTrue(destination.is_symlink())
        self.assertEqual(before, target.read_bytes())

    def test_paths_come_from_argv_and_are_shell_quoted(self):
        destination = self.root / "argv" / "settings.json"
        ignored_destination = self.root / "environment" / "hooks.json"
        env = os.environ.copy()
        env["TGD_ABS"] = "/ignored/repository"
        env["HOOKS_DST"] = str(ignored_destination)

        self.run_cli("install", "claude", destination, env=env)
        installed = self.read_json(destination)
        self.assert_one_canonical_command(
            installed, self.repo / "hooks" / "session-start.sh"
        )
        self.assertFalse(ignored_destination.exists())
        self.assertFalse((self.root / "PWNED").exists())

    def test_atomic_replacement_preserves_existing_file_mode(self):
        destination = self.root / "mode" / "settings.json"
        self.write_json(destination, {"hooks": {}})
        destination.chmod(0o640)

        self.run_cli("install", "gemini", destination)

        self.assertEqual(0o640, stat.S_IMODE(destination.stat().st_mode))

    def test_missing_hook_script_fails_before_creating_destination(self):
        incomplete_repo = self.root / "incomplete-repo"
        incomplete_repo.mkdir()
        destination = self.root / "missing-script" / "settings.json"

        self.run_cli(
            "install",
            "codex",
            destination,
            repo=incomplete_repo,
            expected_returncode=1,
        )
        self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
