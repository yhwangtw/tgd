"""Behavioral contract tests for setup.sh lifecycle safety.

Each test runs a disposable minimal checkout with an isolated HOME and PATH.
No real agent installation, package manager, network, or global bin directory
is used.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest


SOURCE_ROOT = Path(__file__).resolve().parents[1]


class SetupLifecycleTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="tgd-setup-test-")
        self.root = Path(self._tmp.name)
        self.repo = self.root / "repo"
        self.home = self.root / "home"
        self.fake_bin = self.root / "bin"
        self.repo.mkdir()
        self.home.mkdir()
        self.fake_bin.mkdir()

        self._copy_fixture()
        self._write_fake("git", "exit 0")
        self._write_fake(
            "node",
            """
if [ "${1:-}" = "-p" ]; then
    printf '22.12.0\\n'
else
    printf 'v22.12.0\\n'
fi
""",
        )
        self._write_fake("codegraph", "exit 0")
        self._write_fake(
            "ln",
            """
for arg in "$@"; do
    if [ "$arg" = "/usr/local/bin/tgd" ]; then
        exit 1
    fi
done
exec /bin/ln "$@"
""",
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _copy_fixture(self) -> None:
        shutil.copy2(SOURCE_ROOT / "setup.sh", self.repo / "setup.sh")
        shutil.copy2(SOURCE_ROOT / "VERSION", self.repo / "VERSION")

        (self.repo / "bin").mkdir()
        shutil.copy2(SOURCE_ROOT / "bin" / "tgd", self.repo / "bin" / "tgd")

        (self.repo / "scripts").mkdir()
        for script_name in ("install-state.py", "merge-agent-hooks.py"):
            shutil.copy2(
                SOURCE_ROOT / "scripts" / script_name,
                self.repo / "scripts" / script_name,
            )

        skill_dir = self.repo / "skills" / "tgd-rules"
        skill_dir.mkdir(parents=True)
        shutil.copy2(
            SOURCE_ROOT / "skills" / "tgd-rules" / "SKILL.md",
            skill_dir / "SKILL.md",
        )

    def _write_fake(self, name: str, body: str) -> Path:
        path = self.fake_bin / name
        path.write_text(f"#!/bin/sh\n{body.strip()}\n", encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return path

    def _env(self) -> dict[str, str]:
        env = os.environ.copy()
        env.pop("CI", None)
        env["HOME"] = str(self.home)
        env["PATH"] = os.pathsep.join(
            (str(self.fake_bin), "/usr/bin", "/bin")
        )
        return env

    def _run_setup(
        self,
        *args: str,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["/bin/bash", str(self.repo / "setup.sh"), *args],
            cwd=self.repo,
            env=env or self._env(),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=30,
            check=False,
        )

    def _assert_success(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual(0, result.returncode, result.stdout)

    def _snapshot_checkout(self) -> dict[str, tuple[object, ...]]:
        snapshot: dict[str, tuple[object, ...]] = {}

        def visit(directory: Path) -> None:
            for entry in sorted(os.scandir(directory), key=lambda item: item.name):
                path = Path(entry.path)
                relative = path.relative_to(self.repo).as_posix()
                if entry.is_symlink():
                    snapshot[relative] = ("symlink", os.readlink(path))
                elif entry.is_dir(follow_symlinks=False):
                    snapshot[relative] = ("directory",)
                    visit(path)
                elif entry.is_file(follow_symlinks=False):
                    digest = hashlib.sha256(path.read_bytes()).hexdigest()
                    mode = stat.S_IMODE(os.lstat(path).st_mode)
                    snapshot[relative] = ("file", mode, digest)

        visit(self.repo)
        return snapshot

    def test_repeated_install_does_not_mutate_checkout(self) -> None:
        self._write_fake("hermes", "exit 0")
        before = self._snapshot_checkout()

        first = self._run_setup()
        self._assert_success(first)
        second = self._run_setup()
        self._assert_success(second)

        self.assertEqual(
            before,
            self._snapshot_checkout(),
            "installing twice must not create self-links or otherwise mutate the checkout",
        )

    def test_source_cleanup_does_not_follow_symlinked_skill_directories(self) -> None:
        external_skill = self.root / "user-managed-skill"
        external_skill.mkdir()
        foreign_link = external_skill / "legacy-helper"
        foreign_link.symlink_to(self.repo / "skills" / "legacy-helper")
        (self.repo / "skills" / "external-skill").symlink_to(
            external_skill,
            target_is_directory=True,
        )

        result = self._run_setup()

        self._assert_success(result)
        self.assertTrue(
            foreign_link.is_symlink(),
            "source cleanup must never traverse a symlinked skill directory",
        )

    def test_install_preserves_foreign_directory_on_name_collision(self) -> None:
        self._write_fake("hermes", "exit 0")
        collision = self.home / ".hermes" / "skills" / "tgd-rules"
        collision.mkdir(parents=True)
        sentinel = collision / "foreign.txt"
        sentinel.write_text("owned by the user\n", encoding="utf-8")
        installed_marker = self.home / ".tgd-installed-version"
        installed_marker.write_text("v-old\n", encoding="utf-8")

        result = self._run_setup()

        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertTrue(collision.is_dir() and not collision.is_symlink())
        self.assertEqual("owned by the user\n", sentinel.read_text(encoding="utf-8"))
        self.assertEqual("v-old\n", installed_marker.read_text(encoding="utf-8"))

    def test_existing_install_from_old_checkout_migrates_then_uninstalls(self) -> None:
        self._write_fake("hermes", "exit 0")
        old_repo = self.root / "old-tGD-checkout"
        old_skill = old_repo / "skills" / "tgd-rules"
        old_cli = old_repo / "bin" / "tgd"
        old_skill.mkdir(parents=True)
        old_cli.parent.mkdir()
        old_cli.write_text("#!/bin/bash\n", encoding="utf-8")

        installed_skill = self.home / ".hermes" / "skills" / "tgd-rules"
        installed_skill.parent.mkdir(parents=True)
        installed_skill.symlink_to(old_skill, target_is_directory=True)
        installed_cli = self.home / ".local" / "bin" / "tgd"
        installed_cli.parent.mkdir(parents=True)
        installed_cli.symlink_to(old_cli)

        installed = self._run_setup()
        self._assert_success(installed)

        self.assertEqual(
            (self.repo / "skills" / "tgd-rules").resolve(),
            installed_skill.resolve(),
        )
        self.assertEqual(
            (self.repo / "bin" / "tgd").resolve(),
            installed_cli.resolve(),
        )
        manifest = json.loads(
            (self.home / ".tgd" / "install-manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertIn(str(installed_skill), manifest["managed_paths"])
        self.assertIn(str(installed_cli), manifest["managed_paths"])

        uninstalled = self._run_setup("--uninstall")
        self._assert_success(uninstalled)
        self.assertFalse(os.path.lexists(installed_skill))
        self.assertFalse(os.path.lexists(installed_cli))

    def test_default_install_does_not_run_global_package_installs(self) -> None:
        (self.fake_bin / "codegraph").unlink()
        npm_log = self.root / "npm.log"
        self._write_fake(
            "npm",
            """
printf "%s\\n" "$*" >> "$NPM_LOG"
printf '#!/bin/sh\\nexit 0\\n' > "$FAKE_BIN/codegraph"
chmod +x "$FAKE_BIN/codegraph"
""",
        )
        env = self._env()
        env["NPM_LOG"] = str(npm_log)
        env["FAKE_BIN"] = str(self.fake_bin)

        result = self._run_setup(env=env)

        self._assert_success(result)
        self.assertFalse(
            npm_log.exists(),
            "default setup must not run npm install -g",
        )

    def test_with_tools_installs_a_pinned_codegraph_version(self) -> None:
        (self.fake_bin / "codegraph").unlink()
        npm_log = self.root / "npm.log"
        self._write_fake(
            "npm",
            """
printf "%s\\n" "$*" >> "$NPM_LOG"
printf '#!/bin/sh\\nexit 0\\n' > "$FAKE_BIN/codegraph"
chmod +x "$FAKE_BIN/codegraph"
""",
        )
        env = self._env()
        env["NPM_LOG"] = str(npm_log)
        env["FAKE_BIN"] = str(self.fake_bin)

        result = self._run_setup("--with-tools", env=env)

        self._assert_success(result)
        self.assertEqual(
            "install -g @colbymchenry/codegraph@0.9.8\n",
            npm_log.read_text(encoding="utf-8"),
        )

    def test_missing_ua_dependencies_is_reported_without_partial_failure(self) -> None:
        ua_skill = (
            self.repo
            / "vendor"
            / "understand-anything"
            / "understand-anything-plugin"
            / "skills"
            / "understand"
        )
        ua_skill.mkdir(parents=True)
        (ua_skill / "SKILL.md").write_text("# Understand\n", encoding="utf-8")

        result = self._run_setup()

        self._assert_success(result)
        self.assertIn("degraded", result.stdout.lower())
        self.assertEqual(
            (self.repo / "VERSION").read_text(encoding="utf-8").strip(),
            (self.home / ".tgd-installed-version")
            .read_text(encoding="utf-8")
            .strip(),
        )

    def test_successful_dependency_command_without_artifacts_is_degraded(self) -> None:
        ua_skill = (
            self.repo
            / "vendor"
            / "understand-anything"
            / "understand-anything-plugin"
            / "skills"
            / "understand"
        )
        ua_skill.mkdir(parents=True)
        (ua_skill / "SKILL.md").write_text("# Understand\n", encoding="utf-8")
        self._write_fake("corepack", "exit 0")

        result = self._run_setup()

        self._assert_success(result)
        self.assertIn("Setup Complete (degraded)", result.stdout)
        self.assertNotIn("✅ Setup Complete!", result.stdout)

    def test_no_deps_skips_all_dependency_commands(self) -> None:
        ua_skill = (
            self.repo
            / "vendor"
            / "understand-anything"
            / "understand-anything-plugin"
            / "skills"
            / "understand"
        )
        ua_skill.mkdir(parents=True)
        (ua_skill / "SKILL.md").write_text("# Understand\n", encoding="utf-8")
        dependency_log = self.root / "dependencies.log"
        for command in ("corepack", "npm", "pnpm"):
            self._write_fake(
                command,
                'printf "%s\\n" "$0 $*" >> "$DEPENDENCY_LOG"',
            )
        env = self._env()
        env["DEPENDENCY_LOG"] = str(dependency_log)

        result = self._run_setup("--no-deps", env=env)

        self._assert_success(result)
        self.assertIn("skipped by --no-deps", result.stdout)
        self.assertFalse(
            dependency_log.exists(),
            "--no-deps must not invoke package/dependency commands",
        )
        self.assertTrue((self.home / ".local" / "bin" / "tgd").is_symlink())

    def test_no_deps_rejects_dependency_install_flags(self) -> None:
        result = self._run_setup("--no-deps", "--with-tools")

        self.assertEqual(2, result.returncode, result.stdout)
        self.assertIn("Conflicting dependency options", result.stdout)

    def test_default_install_does_not_change_agent_browser_config(self) -> None:
        browser_skill = self.repo / "skills" / "tgd-agent-browser"
        browser_skill.mkdir()
        (browser_skill / "SKILL.md").write_text(
            "# Agent Browser\n",
            encoding="utf-8",
        )
        self._write_fake("agent-browser", "exit 0")
        self._write_fake("npm", "exit 0")
        config = self.home / ".agent-browser" / "config.json"
        config.parent.mkdir()
        original = {"theme": "dark"}
        config.write_text(json.dumps(original), encoding="utf-8")

        result = self._run_setup()

        self._assert_success(result)
        self.assertEqual(
            original,
            json.loads(config.read_text(encoding="utf-8")),
        )

    def test_with_browser_preserves_existing_config_and_enables_auto_connect(self) -> None:
        browser_skill = self.repo / "skills" / "tgd-agent-browser"
        browser_skill.mkdir()
        (browser_skill / "SKILL.md").write_text(
            "# Agent Browser\n",
            encoding="utf-8",
        )
        self._write_fake("agent-browser", "exit 0")
        config = self.home / ".agent-browser" / "config.json"
        config.parent.mkdir()
        config.write_text(json.dumps({"theme": "dark"}), encoding="utf-8")

        result = self._run_setup("--with-browser")

        self._assert_success(result)
        updated = json.loads(config.read_text(encoding="utf-8"))
        self.assertEqual("dark", updated["theme"])
        self.assertIs(True, updated["autoConnect"])

    def test_uninstall_preserves_version(self) -> None:
        original_version = (self.repo / "VERSION").read_text(encoding="utf-8")
        installed_marker = self.home / ".tgd-installed-version"
        installed_marker.write_text("old\n", encoding="utf-8")

        result = self._run_setup("--uninstall")
        self._assert_success(result)

        version_file = self.repo / "VERSION"
        self.assertTrue(version_file.is_file(), "uninstall must not delete VERSION")
        self.assertEqual(
            original_version,
            version_file.read_text(encoding="utf-8"),
        )
        self.assertFalse(installed_marker.exists())

    def test_uninstall_preserves_foreign_files(self) -> None:
        foreign_note = self.home / ".claude" / "commands" / "my-tgd-notes.md"
        foreign_note.parent.mkdir(parents=True)
        foreign_note.write_text("keep me\n", encoding="utf-8")

        foreign_hooks = {
            "hooks": {
                "SessionStart": [
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": "bash /opt/foreign/hooks/start.sh",
                            }
                        ]
                    }
                ]
            }
        }
        codex_hooks = self.home / ".codex" / "hooks.json"
        codex_hooks.parent.mkdir(parents=True)
        codex_hooks.write_text(json.dumps(foreign_hooks), encoding="utf-8")

        foreign_instructions = self.root / "foreign-instructions.md"
        foreign_instructions.write_text("foreign instructions\n", encoding="utf-8")
        pi_instructions = self.home / ".pi" / "agent" / "instructions.md"
        pi_instructions.parent.mkdir(parents=True)
        pi_instructions.symlink_to(foreign_instructions)

        installed_marker = self.home / ".tgd-installed-version"
        installed_marker.write_text("old\n", encoding="utf-8")

        result = self._run_setup("--uninstall")
        self._assert_success(result)

        lost = []
        if not foreign_note.is_file():
            lost.append(str(foreign_note))
        if not codex_hooks.is_file():
            lost.append(str(codex_hooks))
        if not pi_instructions.is_symlink():
            lost.append(str(pi_instructions))
        self.assertEqual([], lost, f"uninstall removed foreign paths: {lost}")

        self.assertEqual("keep me\n", foreign_note.read_text(encoding="utf-8"))
        self.assertEqual(
            foreign_hooks,
            json.loads(codex_hooks.read_text(encoding="utf-8")),
        )
        self.assertEqual(foreign_instructions.resolve(), pi_instructions.resolve())
        self.assertFalse(installed_marker.exists())

    def test_unknown_flag_exits_with_usage_error(self) -> None:
        result = self._run_setup("--definitely-not-a-real-option")

        self.assertEqual(2, result.returncode, result.stdout)

    def test_uninstall_does_not_require_node(self) -> None:
        installed_marker = self.home / ".tgd-installed-version"
        installed_marker.write_text("old\n", encoding="utf-8")

        restricted_bin = self.root / "no-node-bin"
        restricted_bin.mkdir()
        for command in (
            "basename",
            "cat",
            "dirname",
            "grep",
            "mkdir",
            "readlink",
            "rm",
            "sed",
        ):
            resolved = shutil.which(command)
            if resolved is not None:
                (restricted_bin / command).symlink_to(resolved)
        (restricted_bin / "python3").symlink_to(Path(sys.executable).resolve())
        git = restricted_bin / "git"
        git.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        git.chmod(git.stat().st_mode | stat.S_IXUSR)

        env = os.environ.copy()
        env.pop("CI", None)
        env["HOME"] = str(self.home)
        env["PATH"] = str(restricted_bin)

        result = self._run_setup("--uninstall", env=env)

        self.assertEqual(0, result.returncode, result.stdout)
        self.assertFalse(installed_marker.exists())


if __name__ == "__main__":
    unittest.main()
