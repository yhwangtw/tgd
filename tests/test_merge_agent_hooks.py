#!/usr/bin/env python3
"""Contract tests for the cross-platform tGD hook lifecycle CLI."""

from contextlib import contextmanager
import importlib.util
import json
import os
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "merge-agent-hooks.py"
LEGACY_SCRIPT = REPO_ROOT / "scripts" / "merge-codex-hooks.py"


class MergeAgentHooksTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.repo = self.root / "repo with ' quote $(touch PWNED)"
        self.old_repo = self.root / "old tGD checkout"
        for relative in (
            "hooks/session-start.sh",
            "hooks/codex/session-start.sh",
            "hooks/gemini/session-start.sh",
        ):
            path = self.repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("#!/bin/bash\n", encoding="utf-8")
            old_path = self.old_repo / relative
            old_path.parent.mkdir(parents=True, exist_ok=True)
            old_path.write_text("#!/bin/bash\n", encoding="utf-8")
        for checkout in (self.repo, self.old_repo):
            (checkout / "setup.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
            (checkout / "VERSION").write_text("v2026.01.01\n", encoding="utf-8")
            rules = checkout / "skills" / "tgd-core-rules"
            rules.mkdir(parents=True)
            (rules / "SKILL.md").write_text("# rules\n", encoding="utf-8")

    def run_cli(
        self,
        action,
        platform,
        destination,
        *,
        repo=None,
        state=None,
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
        if state is not None:
            command.extend(["--state", str(state)])
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

    @staticmethod
    def load_module():
        spec = importlib.util.spec_from_file_location("merge_agent_hooks", SCRIPT)
        if spec is None or spec.loader is None:
            raise AssertionError(f"cannot load {SCRIPT}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_claude_install_preserves_foreign_hooks_removes_legacy_and_is_idempotent(
        self,
    ):
        destination = self.root / "claude" / "settings.json"
        foreign = "bash /opt/company/hooks/session-start.sh"
        foreign_tgd_prefix = "bash /opt/tgd-monitor/hooks/session-start.sh"
        foreign_tgd_component = "bash /opt/company/tGD/hooks/session-start.sh"
        foreign_named = {
            "name": "tgd-session-start",
            "type": "command",
            "command": "bash /opt/company/named-start.sh",
        }
        old_command = "bash " + shlex.quote(
            str(self.old_repo / "hooks" / "session-start.sh")
        )
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
                                "command": old_command,
                            },
                            {"type": "command", "command": foreign},
                            {"type": "command", "command": foreign_tgd_prefix},
                            {
                                "type": "command",
                                "command": foreign_tgd_component,
                            },
                            foreign_named,
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
        self.assertIn(foreign_tgd_component, self.commands(installed))
        self.assertIn(foreign_named["command"], self.commands(installed))
        self.assertNotIn(old_command, self.commands(installed))
        self.assertIn(
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
        old_codex_command = "bash " + shlex.quote(
            str(self.old_repo / "hooks" / "codex" / "session-start.sh")
        )
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
                                    "command": old_codex_command,
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
        self.assertNotIn(old_codex_command, self.commands(installed))
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
        self.assertEqual(
            "startup|resume|clear|compact",
            canonical_entries[0]["matcher"],
        )
        self.assertEqual(
            "Loading tGD session guidance",
            canonical_entries[0]["hooks"][0]["statusMessage"],
        )

    def test_gemini_install_preserves_foreign_hook_with_same_matcher(self):
        destination = self.root / "gemini" / "settings.json"
        foreign = {
            "name": "company-session-start",
            "type": "command",
            "command": "bash /opt/company/gemini-start.sh",
        }
        old_gemini_command = "bash " + shlex.quote(
            str(self.old_repo / "hooks" / "gemini" / "session-start.sh")
        )
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
                                    "command": old_gemini_command,
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
        canonical_entries = [
            entry
            for entry in installed["hooks"]["SessionStart"]
            if any(
                shlex.split(command)
                == [
                    "bash",
                    str(
                        (
                            self.repo
                            / "hooks"
                            / "gemini"
                            / "session-start.sh"
                        ).resolve()
                    ),
                ]
                for command in self.commands(entry)
            )
        ]
        self.assertNotIn("matcher", canonical_entries[0])
        tgd_named_hooks = []
        for entry in installed["hooks"]["SessionStart"]:
            for hook in entry.get("hooks", []):
                if hook.get("name") == "tgd-session-start":
                    tgd_named_hooks.append(hook)
        self.assertEqual(1, len(tgd_named_hooks))

    def test_gemini_install_removes_only_named_historical_relative_command(self):
        destination = self.root / "gemini-relative" / "settings.json"
        historical = {
            "name": "tgd-session-start",
            "type": "command",
            "command": "bash hooks/gemini/session-start.sh",
        }
        foreign_same_command = {
            "name": "company-session-start",
            "type": "command",
            "command": "bash hooks/gemini/session-start.sh",
        }
        foreign_name_only = {
            "name": "tgd-session-start",
            "type": "command",
            "command": "bash hooks/company/session-start.sh",
        }
        self.write_json(
            destination,
            {
                "hooks": {
                    "SessionStart": [
                        {
                            "hooks": [
                                historical,
                                foreign_same_command,
                                foreign_name_only,
                            ]
                        }
                    ]
                }
            },
        )

        self.run_cli("install", "gemini", destination)

        installed = self.read_json(destination)
        commands = self.commands(installed)
        self.assertEqual(1, commands.count(historical["command"]))
        self.assertIn(foreign_name_only["command"], commands)
        self.assert_one_canonical_command(
            installed, self.repo / "hooks" / "gemini" / "session-start.sh"
        )
        relative_hooks = [
            hook
            for entry in installed["hooks"]["SessionStart"]
            for hook in entry.get("hooks", [])
            if hook.get("command") == historical["command"]
        ]
        self.assertEqual([foreign_same_command], relative_hooks)

    def test_install_recovers_only_recognized_unquoted_absolute_paths_with_spaces(
        self,
    ):
        destination = self.root / "historical-unquoted" / "settings.json"
        historical_bash = f"bash {self.old_repo}/hooks/session-start.sh"
        historical_sh = f"sh {self.old_repo}/hooks/codex/session-start.sh"
        foreign_checkout = self.root / "foreign tGD checkout"
        foreign_script = foreign_checkout / "hooks" / "session-start.sh"
        foreign_script.parent.mkdir(parents=True)
        foreign_script.write_text("#!/bin/bash\n", encoding="utf-8")
        foreign_lookalike = f"bash {foreign_script}"
        foreign_name_only = {
            "name": "tgd-session-start",
            "type": "command",
            "command": "bash /opt/company/session-start.sh",
        }
        self.write_json(
            destination,
            {
                "hooks": {
                    "SessionStart": [
                        {
                            "hooks": [
                                {"type": "command", "command": historical_bash},
                                {"type": "command", "command": historical_sh},
                                {
                                    "type": "command",
                                    "command": foreign_lookalike,
                                },
                                foreign_name_only,
                            ]
                        }
                    ]
                }
            },
        )

        self.run_cli("install", "claude", destination)

        installed = self.read_json(destination)
        commands = self.commands(installed)
        self.assertNotIn(historical_bash, commands)
        self.assertNotIn(historical_sh, commands)
        self.assertIn(foreign_lookalike, commands)
        self.assertIn(foreign_name_only["command"], commands)
        self.assert_one_canonical_command(
            installed, self.repo / "hooks" / "session-start.sh"
        )

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
                old_command = "bash " + shlex.quote(
                    str(self.old_repo / relative_script)
                )
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
                                            "command": old_command,
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

    def test_state_migrates_exact_hook_after_old_checkout_is_deleted(self):
        destination = self.root / "state-migration" / "settings.json"
        state = self.root / "state" / "hook-ownership.json"
        old_script = self.old_repo / "hooks" / "session-start.sh"
        old_command = "bash " + shlex.quote(str(old_script.resolve()))
        foreign = "bash /deleted/company/hooks/session-start.sh"

        self.run_cli(
            "install",
            "claude",
            destination,
            repo=self.old_repo,
            state=state,
        )
        installed = self.read_json(destination)
        installed["hooks"]["SessionStart"][0]["hooks"].append(
            {"type": "command", "command": foreign}
        )
        self.write_json(destination, installed)
        shutil.rmtree(self.old_repo)

        self.run_cli(
            "install",
            "claude",
            destination,
            repo=self.repo,
            state=state,
        )

        migrated = self.read_json(destination)
        self.assertNotIn(old_command, self.commands(migrated))
        self.assertIn(foreign, self.commands(migrated))
        self.assert_one_canonical_command(
            migrated, self.repo / "hooks" / "session-start.sh"
        )
        state_data = self.read_json(state)
        recorded = state_data["managed_hooks"]["claude"][str(destination)]
        self.assertIn(old_command, recorded["commands"])

    def test_state_preserves_tampered_and_unrecorded_foreign_commands(self):
        destination = self.root / "state-tamper" / "settings.json"
        state = self.root / "state" / "hook-ownership.json"

        self.run_cli(
            "install",
            "claude",
            destination,
            repo=self.old_repo,
            state=state,
        )
        installed = self.read_json(destination)
        old_command = self.commands(installed)[0]
        tampered = old_command + " --company-wrapper"
        foreign = "bash /missing/foreign/hooks/session-start.sh"
        installed["hooks"]["SessionStart"][0]["hooks"][0]["command"] = tampered
        installed["hooks"]["SessionStart"][0]["hooks"].append(
            {"type": "command", "command": foreign}
        )
        self.write_json(destination, installed)
        shutil.rmtree(self.old_repo)

        self.run_cli(
            "install",
            "claude",
            destination,
            repo=self.repo,
            state=state,
        )

        migrated = self.read_json(destination)
        self.assertIn(tampered, self.commands(migrated))
        self.assertIn(foreign, self.commands(migrated))
        self.assert_one_canonical_command(
            migrated, self.repo / "hooks" / "session-start.sh"
        )

    def test_state_remove_cleans_exact_hook_after_checkout_is_deleted(self):
        destination = self.root / "state-remove" / "settings.json"
        state = self.root / "state" / "hook-ownership.json"
        foreign = "bash /opt/company/keep.sh"

        self.run_cli(
            "install",
            "codex",
            destination,
            repo=self.old_repo,
            state=state,
        )
        installed = self.read_json(destination)
        installed["hooks"]["SessionStart"][0]["hooks"].append(
            {"type": "command", "command": foreign}
        )
        self.write_json(destination, installed)
        shutil.rmtree(self.old_repo)

        self.run_cli(
            "remove",
            "codex",
            destination,
            repo=self.repo,
            state=state,
        )

        self.assertEqual([foreign], self.commands(self.read_json(destination)))
        self.assertFalse(
            state.exists(),
            "the last managed hook removal should clear the ownership state",
        )

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

    def test_optimistic_recheck_rejects_non_cooperating_foreign_update(self):
        module = self.load_module()

        destination = self.root / "concurrent" / "settings.json"
        self.write_json(destination, {"theme": "before"})
        _config, mode, original, identity = module._load_destination(destination)
        self.write_json(destination, {"theme": "foreign-newer"})

        with self.assertRaises(module.HookConfigError):
            module._write_atomic(
                destination,
                {"theme": "tgd-update"},
                mode,
                original,
                identity,
            )

        self.assertEqual(
            {"theme": "foreign-newer"},
            self.read_json(destination),
        )

    def test_atomic_write_rejects_same_content_new_inode(self):
        module = self.load_module()
        destination = self.root / "same-content-write" / "settings.json"
        self.write_json(destination, {"theme": "before"})
        _config, mode, original, identity = module._load_destination(destination)

        replacement = destination.with_name("settings.replacement.json")
        self.write_json(replacement, {"theme": "before"})
        replacement_identity = (
            replacement.stat().st_dev,
            replacement.stat().st_ino,
        )
        self.assertNotEqual(identity, replacement_identity)
        os.replace(replacement, destination)

        with self.assertRaises(module.HookConfigError):
            module._write_atomic(
                destination,
                {"theme": "tgd-update"},
                mode,
                original,
                identity,
            )

        self.assertEqual(
            replacement_identity,
            (destination.stat().st_dev, destination.stat().st_ino),
        )
        self.assertEqual({"theme": "before"}, self.read_json(destination))

    def test_atomic_write_preserves_foreign_swap_at_quarantine_boundary(self):
        module = self.load_module()
        destination = self.root / "write-swap" / "settings.json"
        self.write_json(destination, {"theme": "before"})
        _config, mode, original, identity = module._load_destination(destination)
        original_replace = module.os.replace
        swapped = False

        def swap_before_quarantine(source, replacement):
            nonlocal swapped
            if (
                not swapped
                and Path(source) == destination
                and ".tgd-quarantine." in Path(replacement).name
            ):
                swapped = True
                destination.unlink()
                self.write_json(destination, {"theme": "foreign-newer"})
            return original_replace(source, replacement)

        with mock.patch.object(
            module.os,
            "replace",
            side_effect=swap_before_quarantine,
        ):
            with self.assertRaises(module.HookConfigError):
                module._write_atomic(
                    destination,
                    {"theme": "tgd-update"},
                    mode,
                    original,
                    identity,
                )

        self.assertTrue(swapped)
        self.assertEqual({"theme": "foreign-newer"}, self.read_json(destination))
        self.assertEqual(
            [],
            list(destination.parent.glob(".settings.json.tgd-quarantine.*")),
        )

    def test_atomic_write_never_clobbers_foreign_insert_after_quarantine(self):
        module = self.load_module()
        destination = self.root / "write-insert" / "settings.json"
        self.write_json(destination, {"theme": "before"})
        _config, mode, original, identity = module._load_destination(destination)
        original_link = module.os.link
        inserted = False

        def insert_before_new_link(source, target, *args, **kwargs):
            nonlocal inserted
            if not inserted and Path(target) == destination:
                inserted = True
                self.write_json(destination, {"theme": "foreign-newer"})
            return original_link(source, target, *args, **kwargs)

        with mock.patch.object(
            module.os,
            "link",
            side_effect=insert_before_new_link,
        ):
            with self.assertRaisesRegex(
                module.HookConfigError,
                "prior data was preserved at",
            ):
                module._write_atomic(
                    destination,
                    {"theme": "tgd-update"},
                    mode,
                    original,
                    identity,
                )

        self.assertTrue(inserted)
        self.assertEqual({"theme": "foreign-newer"}, self.read_json(destination))
        quarantines = list(
            destination.parent.glob(".settings.json.tgd-quarantine.*")
        )
        self.assertEqual(1, len(quarantines))
        self.assertEqual(original, quarantines[0].read_bytes())

    def test_atomic_remove_rejects_same_content_new_inode(self):
        module = self.load_module()
        state = self.root / "same-content-remove" / "hook-ownership.json"
        self.write_json(state, {"version": 1, "managed_hooks": {}})
        _config, _mode, original, identity = module._load_destination(state)

        replacement = state.with_name("hook-ownership.replacement.json")
        self.write_json(replacement, {"version": 1, "managed_hooks": {}})
        replacement_identity = (replacement.stat().st_dev, replacement.stat().st_ino)
        self.assertNotEqual(identity, replacement_identity)
        os.replace(replacement, state)

        with self.assertRaises(module.HookConfigError):
            module._remove_atomic(state, original, identity)

        self.assertEqual(
            replacement_identity,
            (state.stat().st_dev, state.stat().st_ino),
        )
        self.assertTrue(state.is_file())

    def test_atomic_remove_preserves_foreign_swap_at_quarantine_boundary(self):
        module = self.load_module()
        state = self.root / "remove-swap" / "hook-ownership.json"
        self.write_json(state, {"version": 1, "managed_hooks": {}})
        _config, _mode, original, identity = module._load_destination(state)
        original_replace = module.os.replace
        swapped = False

        def swap_before_quarantine(source, replacement):
            nonlocal swapped
            if (
                not swapped
                and Path(source) == state
                and ".tgd-quarantine." in Path(replacement).name
            ):
                swapped = True
                state.unlink()
                self.write_json(state, {"foreign": True})
            return original_replace(source, replacement)

        with mock.patch.object(
            module.os,
            "replace",
            side_effect=swap_before_quarantine,
        ):
            with self.assertRaises(module.HookConfigError):
                module._remove_atomic(state, original, identity)

        self.assertTrue(swapped)
        self.assertEqual({"foreign": True}, self.read_json(state))
        self.assertEqual(
            [],
            list(state.parent.glob(".hook-ownership.json.tgd-quarantine.*")),
        )

    def test_two_tgd_writers_serialize_the_full_read_modify_write(self):
        module = self.load_module()
        destination = self.root / "serialized" / "settings.json"
        self.write_json(destination, {"foreign": {"keep": True}})

        first_acquired = threading.Event()
        allow_first_to_finish = threading.Event()
        second_attempting = threading.Event()
        second_acquired = threading.Event()
        acquisition_order = []
        failures = []
        original_lock = module._destination_lock

        @contextmanager
        def observed_lock(path):
            thread_name = threading.current_thread().name
            if thread_name == "second-tgd-writer":
                second_attempting.set()
            with original_lock(path):
                acquisition_order.append(thread_name)
                if thread_name == "first-tgd-writer":
                    first_acquired.set()
                    if not allow_first_to_finish.wait(timeout=5):
                        raise AssertionError("timed out releasing first tGD writer")
                elif thread_name == "second-tgd-writer":
                    second_acquired.set()
                yield

        module._destination_lock = observed_lock

        def writer():
            args = module.parse_args(
                [
                    "install",
                    "--platform",
                    "claude",
                    "--repo-root",
                    str(self.repo),
                    "--destination",
                    str(destination),
                ]
            )
            try:
                module.run(args)
            except BaseException as error:
                failures.append(error)

        first = threading.Thread(target=writer, name="first-tgd-writer")
        second = threading.Thread(target=writer, name="second-tgd-writer")
        first.start()
        self.assertTrue(first_acquired.wait(timeout=2))
        second.start()
        try:
            self.assertTrue(second_attempting.wait(timeout=2))
            self.assertFalse(
                second_acquired.wait(timeout=0.2),
                "second tGD writer entered while the first held the lock",
            )
        finally:
            allow_first_to_finish.set()
            first.join(timeout=5)
            second.join(timeout=5)

        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual([], failures)
        self.assertEqual(
            ["first-tgd-writer", "second-tgd-writer"],
            acquisition_order,
        )
        self.assertTrue(
            destination.with_name(f".{destination.name}.tgd.lock").is_file()
        )
        installed = self.read_json(destination)
        self.assertEqual({"keep": True}, installed["foreign"])
        self.assert_one_canonical_command(
            installed, self.repo / "hooks" / "session-start.sh"
        )

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

    def test_legacy_codex_merger_delegates_to_safe_current_helper(self):
        destination = self.root / "legacy-shim" / "hooks.json"
        foreign = "bash /opt/company/keep.sh"
        self.write_json(
            destination,
            {
                "hooks": {
                    "SessionStart": [
                        {
                            "hooks": [
                                {"type": "command", "command": foreign},
                            ]
                        }
                    ]
                }
            },
        )
        env = os.environ.copy()
        env["TGD_ABS"] = str(self.repo)
        env["HOOKS_DST"] = str(destination)

        result = subprocess.run(
            [sys.executable, str(LEGACY_SCRIPT)],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        installed = self.read_json(destination)
        self.assertIn(foreign, self.commands(installed))
        self.assert_one_canonical_command(
            installed,
            self.repo / "hooks" / "codex" / "session-start.sh",
        )


if __name__ == "__main__":
    unittest.main()
