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
LEGACY_PI_INSTRUCTIONS = """\

<!-- tGD rules — https://github.com/openclawyhwang-hub/tGD -->
# tGD — Agent Instructions

## Verification Iron Law

**NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE.**

Before claiming any work is complete, fixed, or passing:

1. **RUN** the verification command (tests, build, linter)
2. **READ** the full output (check exit code, count failures)
3. **SHOW** the output as evidence
4. **ONLY THEN** claim the result

## Anti-Rationalization

These thoughts are WRONG:
- "Should work now" → RUN the verification
- "I'm confident" → Confidence ≠ evidence
- "Just this once" → No exceptions
- "Looks correct to me" → Visual inspection ≠ verification
- "Tests passed last time" → Run them again, fresh

Never use "should", "probably", "seems to" when describing code state.

## tGD Lifecycle Commands

Use slash commands for each phase: /tgd-map → /tgd-define → /tgd-plan → /tgd-develop → /tgd-verify → /tgd-review → /tgd-simplify → /tgd-ship

Each command has pre-flight checks. Do not skip phases.
"""


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
        for script_name in (
            "install-state.py",
            "merge-agent-hooks.py",
            "ua-build-state.py",
        ):
            shutil.copy2(
                SOURCE_ROOT / "scripts" / script_name,
                self.repo / "scripts" / script_name,
            )

        (self.repo / "hooks").mkdir()
        shutil.copy2(
            SOURCE_ROOT / "hooks" / "session-preamble.enabled",
            self.repo / "hooks" / "session-preamble.enabled",
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

    def _mark_tgd_checkout(self, checkout: Path) -> None:
        checkout.mkdir(parents=True, exist_ok=True)
        (checkout / "setup.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
        (checkout / "VERSION").write_text("v2026.01.01\n", encoding="utf-8")
        rules = checkout / "skills" / "tgd-rules"
        rules.mkdir(parents=True, exist_ok=True)
        (rules / "SKILL.md").write_text("# tGD rules\n", encoding="utf-8")

    def _env(self) -> dict[str, str]:
        env = os.environ.copy()
        env.pop("CI", None)
        env["HOME"] = str(self.home)
        env["TGD_DISABLE_GLOBAL_MIGRATION_FOR_TESTS"] = "1"
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

    def _write_ua_build_stamp(self, ua_root: Path) -> None:
        stamp = self.home / ".tgd" / "ua-build-state.json"
        result = subprocess.run(
            [
                sys.executable,
                str(self.repo / "scripts" / "ua-build-state.py"),
                "write",
                "--ua-root",
                str(ua_root),
                "--stamp",
                str(stamp),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
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
        # This exactly matches the name/target pattern of an old generated
        # link. It must still be preserved because its parent skill directory
        # is itself a user-owned symlink outside the checkout.
        foreign_link = external_skill / "external"
        foreign_link.symlink_to(self.repo / "skills" / "external")
        (self.repo / "skills" / "tgd-external").symlink_to(
            external_skill,
            target_is_directory=True,
        )

        result = self._run_setup()

        self._assert_success(result)
        self.assertTrue(
            foreign_link.is_symlink(),
            "source cleanup must never traverse a symlinked skill directory",
        )

    def test_gemini_skills_are_direct_children_and_legacy_bundle_is_retired(
        self,
    ) -> None:
        router = self.repo / "skills" / "tgd-router"
        router.mkdir()
        (router / "SKILL.md").write_text("# router\n", encoding="utf-8")
        gemini_skills = self.home / ".gemini" / "skills"
        gemini_skills.mkdir(parents=True)
        legacy_bundle = gemini_skills / "tGD"
        legacy_bundle.symlink_to(
            self.repo / "skills",
            target_is_directory=True,
        )

        result = self._run_setup("--no-deps")

        self._assert_success(result)
        self.assertFalse(os.path.lexists(legacy_bundle))
        for skill_name in ("tgd-rules", "tgd-router"):
            installed = gemini_skills / skill_name
            self.assertTrue(installed.is_symlink())
            self.assertEqual(
                (self.repo / "skills" / skill_name).resolve(),
                installed.resolve(),
            )

    def test_source_cleanup_removes_exact_legacy_hermes_plugin_self_link(
        self,
    ) -> None:
        plugin_dir = self.repo / ".hermes" / "plugins" / "tgd"
        plugin_dir.mkdir(parents=True)
        self_link = plugin_dir / "tgd"
        self_link.symlink_to(plugin_dir.resolve(), target_is_directory=True)

        result = self._run_setup()

        self._assert_success(result)
        self.assertFalse(
            os.path.lexists(self_link),
            "the historical Hermes plugin self-link must be removed",
        )

    def test_source_cleanup_removes_only_known_generated_skill_links(self) -> None:
        skill_dir = self.repo / "skills" / "tgd-rules"
        self_link = skill_dir / "tgd-rules"
        self_link.symlink_to(skill_dir.resolve(), target_is_directory=True)
        broken_legacy = skill_dir / "rules"
        broken_legacy.symlink_to(self.repo.resolve() / "skills" / "rules")
        user_target = self.root / "user-helper"
        user_target.write_text("user owned\n", encoding="utf-8")
        foreign_link = skill_dir / "company-helper"
        foreign_link.symlink_to(user_target)

        result = self._run_setup()

        self._assert_success(result)
        self.assertFalse(os.path.lexists(self_link))
        self.assertFalse(os.path.lexists(broken_legacy))
        self.assertTrue(foreign_link.is_symlink())
        self.assertEqual(user_target.resolve(), foreign_link.resolve())

    def test_install_preserves_foreign_directory_on_name_collision(self) -> None:
        self._write_fake("hermes", "exit 0")
        collision = self.home / ".hermes" / "skills" / "tgd-rules"
        collision.mkdir(parents=True)
        sentinel = collision / "foreign.txt"
        sentinel.write_text("owned by the user\n", encoding="utf-8")
        installed_marker = self.home / ".tgd-installed-version"
        installed_marker.write_text("v2026.01.01\n", encoding="utf-8")

        result = self._run_setup()

        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertTrue(collision.is_dir() and not collision.is_symlink())
        self.assertEqual("owned by the user\n", sentinel.read_text(encoding="utf-8"))
        self.assertEqual(
            "v2026.01.01\n",
            installed_marker.read_text(encoding="utf-8"),
        )

    def test_install_preserves_foreign_same_suffix_symlink(self) -> None:
        self._write_fake("codex", "exit 0")
        foreign_root = self.root / "company"
        foreign_skills = foreign_root / "skills"
        foreign_skills.mkdir(parents=True)
        destination = self.home / ".codex" / "skills" / "tGD"
        destination.parent.mkdir(parents=True)
        destination.symlink_to(foreign_skills, target_is_directory=True)

        result = self._run_setup("--no-deps")

        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertTrue(destination.is_symlink())
        self.assertEqual(foreign_skills.resolve(), destination.resolve())

    def test_upgrade_preserves_foreign_legacy_skill_symlink(self) -> None:
        foreign_skill = self.root / "company" / "skills" / "rules"
        foreign_skill.mkdir(parents=True)
        destination = self.home / ".codex" / "skills" / "rules"
        destination.parent.mkdir(parents=True)
        destination.symlink_to(foreign_skill, target_is_directory=True)
        (self.home / ".tgd-installed-version").write_text(
            (self.repo / "VERSION").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        result = self._run_setup("--no-deps")

        self._assert_success(result)
        self.assertTrue(destination.is_symlink())
        self.assertEqual(foreign_skill.resolve(), destination.resolve())

    def test_existing_install_from_old_checkout_migrates_then_uninstalls(self) -> None:
        self._write_fake("hermes", "exit 0")
        old_repo = self.root / "old-tGD-checkout"
        old_skill = old_repo / "skills" / "tgd-rules"
        old_cli = old_repo / "bin" / "tgd"
        old_skill.mkdir(parents=True)
        old_cli.parent.mkdir()
        old_cli.write_text("#!/bin/bash\n", encoding="utf-8")
        self._mark_tgd_checkout(old_repo)

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
        self.assertFalse((self.home / ".tgd-installed-version").exists())

    def test_exact_historical_pi_instructions_retire_idempotently(self) -> None:
        installed_instructions = self.home / ".pi" / "agent" / "instructions.md"
        installed_instructions.parent.mkdir(parents=True)
        installed_instructions.write_text(
            LEGACY_PI_INSTRUCTIONS,
            encoding="utf-8",
        )
        self.assertEqual(
            "4f9be9f0faa5371b95fb5062a00c11b4b9ee22ee8e243fdd7cedc840eb0af689",
            hashlib.sha256(installed_instructions.read_bytes()).hexdigest(),
        )

        first = self._run_setup("--no-deps")
        self._assert_success(first)
        second = self._run_setup("--no-deps")
        self._assert_success(second)

        self.assertFalse(os.path.lexists(installed_instructions))
        manifest = json.loads(
            (self.home / ".tgd" / "install-manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertNotIn(str(installed_instructions), manifest["managed_paths"])

        uninstalled = self._run_setup("--uninstall")
        self._assert_success(uninstalled)
        self.assertFalse(os.path.lexists(installed_instructions))

    def test_historical_cleanup_supports_a_home_path_containing_pipe(self) -> None:
        pipe_home = self.root / "home|company"
        installed_instructions = pipe_home / ".pi" / "agent" / "instructions.md"
        installed_instructions.parent.mkdir(parents=True)
        installed_instructions.write_text(
            LEGACY_PI_INSTRUCTIONS,
            encoding="utf-8",
        )
        env = self._env()
        env["HOME"] = str(pipe_home)

        result = self._run_setup("--no-deps", env=env)

        self._assert_success(result)
        self.assertFalse(os.path.lexists(installed_instructions))

    def test_modified_historical_pi_instructions_are_preserved(self) -> None:
        installed_instructions = self.home / ".pi" / "agent" / "instructions.md"
        installed_instructions.parent.mkdir(parents=True)
        modified = LEGACY_PI_INSTRUCTIONS + "\nUser addition.\n"
        installed_instructions.write_text(modified, encoding="utf-8")

        result = self._run_setup("--no-deps")

        self._assert_success(result)
        self.assertIn("Preserved modified historical-looking file", result.stdout)
        self.assertFalse(installed_instructions.is_symlink())
        self.assertEqual(modified, installed_instructions.read_text(encoding="utf-8"))

    def test_verified_legacy_ua_repo_link_migrates_then_uninstalls(self) -> None:
        old_repo = self.root / "old-tGD-checkout"
        self._mark_tgd_checkout(old_repo)
        old_plugin = (
            old_repo
            / "vendor"
            / "understand-anything"
            / "understand-anything-plugin"
        )
        old_plugin.mkdir(parents=True)
        legacy_link = self.home / ".understand-anything" / "repo"
        legacy_link.parent.mkdir()
        legacy_link.symlink_to(old_plugin, target_is_directory=True)

        current_skill = (
            self.repo
            / "vendor"
            / "understand-anything"
            / "understand-anything-plugin"
            / "skills"
            / "understand"
        )
        current_skill.mkdir(parents=True)
        (current_skill / "SKILL.md").write_text(
            "# Understand\n",
            encoding="utf-8",
        )

        installed = self._run_setup("--no-deps")
        self._assert_success(installed)
        self.assertFalse(os.path.lexists(legacy_link))
        plugin_root = self.home / ".understand-anything-plugin"
        self.assertTrue(plugin_root.is_symlink())

        uninstalled = self._run_setup("--uninstall")
        self._assert_success(uninstalled)
        self.assertFalse(os.path.lexists(plugin_root))
        self.assertFalse(
            os.path.lexists(self.home / ".agents" / "skills" / "understand")
        )

    def test_foreign_legacy_ua_repo_link_is_preserved(self) -> None:
        foreign_plugin = (
            self.root
            / "company"
            / "vendor"
            / "understand-anything"
            / "understand-anything-plugin"
        )
        foreign_plugin.mkdir(parents=True)
        legacy_link = self.home / ".understand-anything" / "repo"
        legacy_link.parent.mkdir()
        legacy_link.symlink_to(foreign_plugin, target_is_directory=True)
        current_skill = (
            self.repo
            / "vendor"
            / "understand-anything"
            / "understand-anything-plugin"
            / "skills"
            / "understand"
        )
        current_skill.mkdir(parents=True)
        (current_skill / "SKILL.md").write_text(
            "# Understand\n",
            encoding="utf-8",
        )

        installed = self._run_setup("--no-deps")
        self._assert_success(installed)
        self.assertTrue(legacy_link.is_symlink())
        self.assertEqual(foreign_plugin.resolve(), legacy_link.resolve())

        uninstalled = self._run_setup("--uninstall")
        self._assert_success(uninstalled)
        self.assertTrue(legacy_link.is_symlink())
        self.assertEqual(foreign_plugin.resolve(), legacy_link.resolve())

    def test_setup_removes_only_verified_retired_integrations(self) -> None:
        old_repo = self.root / "retired-tGD-checkout"
        self._mark_tgd_checkout(old_repo)
        old_rule = old_repo / "skills" / "tgd-rules" / "SKILL.md"
        old_extension = old_repo / ".pi" / "extensions" / "tgd-commands.ts"
        old_extension.parent.mkdir(parents=True)
        old_extension.write_text("// retired\n", encoding="utf-8")

        installed_rule = self.home / ".claude" / "rules" / "tgd.md"
        installed_rule.parent.mkdir(parents=True)
        installed_rule.symlink_to(old_rule)
        installed_extension = (
            self.home / ".pi" / "agent" / "extensions" / "tgd-commands.ts"
        )
        installed_extension.parent.mkdir(parents=True)
        installed_extension.symlink_to(old_extension)

        result = self._run_setup("--no-deps")

        self._assert_success(result)
        self.assertFalse(os.path.lexists(installed_rule))
        self.assertFalse(os.path.lexists(installed_extension))

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

    def test_existing_ua_artifacts_do_not_require_a_new_node_runtime(self) -> None:
        ua_root = self.repo / "vendor" / "understand-anything"
        ua_skill = (
            ua_root
            / "understand-anything-plugin"
            / "skills"
            / "understand"
        )
        ua_skill.mkdir(parents=True)
        (ua_skill / "SKILL.md").write_text("# Understand\n", encoding="utf-8")
        modules_manifest = ua_root / "node_modules" / ".modules.yaml"
        modules_manifest.parent.mkdir()
        modules_manifest.write_text("packageManager: pnpm\n", encoding="utf-8")
        core_output = (
            ua_root
            / "understand-anything-plugin"
            / "packages"
            / "core"
            / "dist"
            / "index.js"
        )
        core_output.parent.mkdir(parents=True)
        core_output.write_text("// built\n", encoding="utf-8")
        self._write_ua_build_stamp(ua_root)
        self._write_fake(
            "node",
            """
if [ "${1:-}" = "-p" ]; then
    printf '20.19.0\\n'
else
    printf 'v20.19.0\\n'
fi
""",
        )

        result = self._run_setup()

        self._assert_success(result)
        self.assertIn("UA dependencies already installed", result.stdout)
        self.assertNotIn("requires Node.js", result.stdout)

    def test_changed_ua_source_requires_rebuild_before_old_node_can_skip(self) -> None:
        ua_root = self.repo / "vendor" / "understand-anything"
        ua_skill = (
            ua_root
            / "understand-anything-plugin"
            / "skills"
            / "understand"
        )
        ua_skill.mkdir(parents=True)
        (ua_skill / "SKILL.md").write_text("# Understand\n", encoding="utf-8")
        source = (
            ua_root
            / "understand-anything-plugin"
            / "packages"
            / "core"
            / "src"
            / "index.ts"
        )
        source.parent.mkdir(parents=True)
        source.write_text("export const version = 1;\n", encoding="utf-8")
        (ua_root / "pnpm-lock.yaml").write_text(
            "lockfileVersion: '9.0'\n",
            encoding="utf-8",
        )
        modules_manifest = ua_root / "node_modules" / ".modules.yaml"
        modules_manifest.parent.mkdir()
        modules_manifest.write_text("packageManager: pnpm\n", encoding="utf-8")
        core_output = (
            ua_root
            / "understand-anything-plugin"
            / "packages"
            / "core"
            / "dist"
            / "index.js"
        )
        core_output.parent.mkdir(parents=True)
        core_output.write_text("// built\n", encoding="utf-8")
        self._write_ua_build_stamp(ua_root)
        source.write_text("export const version = 2;\n", encoding="utf-8")
        self._write_fake(
            "node",
            """
if [ "${1:-}" = "-p" ]; then
    printf '20.19.0\\n'
else
    printf 'v20.19.0\\n'
fi
""",
        )

        result = self._run_setup()

        self._assert_success(result)
        self.assertIn("UA build inputs changed", result.stdout)
        self.assertIn("Node.js >= 22.12.0", result.stdout)
        self.assertIn("Setup Complete (degraded)", result.stdout)

    def test_old_node_degrades_only_ua_dependency_install(self) -> None:
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
        self._write_fake(
            "node",
            """
if [ "${1:-}" = "-p" ]; then
    printf '20.19.0\\n'
else
    printf 'v20.19.0\\n'
fi
""",
        )

        result = self._run_setup()

        self._assert_success(result)
        self.assertIn("Node.js >= 22.12.0", result.stdout)
        self.assertIn("Setup Complete (degraded)", result.stdout)
        self.assertTrue((self.home / ".local" / "bin" / "tgd").is_symlink())

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

    def test_successful_ua_build_records_stamp_and_is_not_repeated(self) -> None:
        ua_root = self.repo / "vendor" / "understand-anything"
        ua_skill = (
            ua_root
            / "understand-anything-plugin"
            / "skills"
            / "understand"
        )
        ua_skill.mkdir(parents=True)
        (ua_skill / "SKILL.md").write_text("# Understand\n", encoding="utf-8")
        source = (
            ua_root
            / "understand-anything-plugin"
            / "packages"
            / "core"
            / "src"
            / "index.ts"
        )
        source.parent.mkdir(parents=True)
        source.write_text("export const ready = true;\n", encoding="utf-8")
        (ua_root / "pnpm-lock.yaml").write_text(
            "lockfileVersion: '9.0'\n",
            encoding="utf-8",
        )
        command_log = self.root / "ua-commands.log"
        self._write_fake(
            "corepack",
            """
printf '%s\\n' "$*" >> "$UA_COMMAND_LOG"
if [ "${1:-}" = "pnpm" ] && [ "${2:-}" = "install" ]; then
    mkdir -p node_modules
    printf 'packageManager: pnpm\\n' > node_modules/.modules.yaml
elif [ "${1:-}" = "pnpm" ] && [ "${2:-}" = "build" ]; then
    mkdir -p understand-anything-plugin/packages/core/dist
    printf '// built\\n' > \
        understand-anything-plugin/packages/core/dist/index.js
fi
""",
        )
        env = self._env()
        env["UA_COMMAND_LOG"] = str(command_log)

        first = self._run_setup(env=env)
        self._assert_success(first)
        second = self._run_setup(env=env)
        self._assert_success(second)

        self.assertEqual(
            [
                "pnpm install --frozen-lockfile",
                "pnpm build",
            ],
            command_log.read_text(encoding="utf-8").splitlines(),
        )
        stamp = self.home / ".tgd" / "ua-build-state.json"
        self.assertTrue(stamp.is_file())
        current = subprocess.run(
            [
                sys.executable,
                str(self.repo / "scripts" / "ua-build-state.py"),
                "is-current",
                "--ua-root",
                str(ua_root),
                "--stamp",
                str(stamp),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(0, current.returncode, current.stdout)

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

    def test_all_ua_skills_use_universal_canonical_links(self) -> None:
        ua_skills = (
            self.repo
            / "vendor"
            / "understand-anything"
            / "understand-anything-plugin"
            / "skills"
        )
        for skill_name in (
            "understand",
            "understand-chat",
            "understand-dashboard",
        ):
            skill = ua_skills / skill_name
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                f"---\nname: {skill_name}\n---\n",
                encoding="utf-8",
            )
        (self.home / ".gemini").mkdir()

        result = self._run_setup("--no-deps")

        self._assert_success(result)
        plugin_root = self.home / ".understand-anything-plugin"
        self.assertTrue(plugin_root.is_symlink())
        self.assertEqual(
            (ua_skills.parent).resolve(),
            plugin_root.resolve(),
        )
        for skill_name in (
            "understand",
            "understand-chat",
            "understand-dashboard",
        ):
            with self.subTest(skill_name=skill_name):
                universal = self.home / ".agents" / "skills" / skill_name
                self.assertTrue(universal.is_symlink())
                self.assertEqual((ua_skills / skill_name).resolve(), universal.resolve())
                self.assertFalse(
                    os.path.lexists(self.home / ".gemini" / "skills" / skill_name)
                )
                self.assertFalse(
                    os.path.lexists(
                        self.home
                        / ".gemini"
                        / "skills"
                        / f"understand-{skill_name}"
                    )
                )

    def test_gemini_gets_direct_fallback_only_for_universal_collision(self) -> None:
        ua_skills = (
            self.repo
            / "vendor"
            / "understand-anything"
            / "understand-anything-plugin"
            / "skills"
        )
        for skill_name in ("understand", "understand-chat"):
            skill = ua_skills / skill_name
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                f"---\nname: {skill_name}\n---\n",
                encoding="utf-8",
            )

        collision = self.home / ".agents" / "skills" / "understand-chat"
        collision.mkdir(parents=True)
        sentinel = collision / "user-owned.txt"
        sentinel.write_text("keep\n", encoding="utf-8")
        (self.home / ".gemini").mkdir()

        result = self._run_setup("--no-deps")

        self._assert_success(result)
        self.assertEqual("keep\n", sentinel.read_text(encoding="utf-8"))
        self.assertTrue(
            (self.home / ".agents" / "skills" / "understand").is_symlink()
        )
        fallback = self.home / ".gemini" / "skills" / "understand-chat"
        self.assertTrue(fallback.is_symlink())
        self.assertEqual((ua_skills / "understand-chat").resolve(), fallback.resolve())
        self.assertFalse(
            os.path.lexists(self.home / ".gemini" / "skills" / "understand")
        )

    def test_no_deps_does_not_require_node(self) -> None:
        (self.fake_bin / "node").unlink()

        result = self._run_setup("--no-deps")

        self._assert_success(result)
        self.assertTrue((self.home / ".local" / "bin" / "tgd").is_symlink())

    def test_no_deps_rejects_dependency_install_flags(self) -> None:
        result = self._run_setup("--no-deps", "--with-tools")

        self.assertEqual(2, result.returncode, result.stdout)
        self.assertIn("Conflicting dependency options", result.stdout)

    def test_non_install_modes_reject_install_options(self) -> None:
        for args in (
            ("--uninstall", "--with-tools"),
            ("--version", "--no-deps"),
        ):
            with self.subTest(args=args):
                result = self._run_setup(*args)
                self.assertEqual(2, result.returncode, result.stdout)
                self.assertIn("only valid for install or upgrade", result.stdout)

    def test_installed_cli_forwards_upgrade_options(self) -> None:
        (self.fake_bin / "node").unlink()
        cli = self.repo / "bin" / "tgd"

        result = subprocess.run(
            [str(cli), "--upgrade", "--no-deps"],
            cwd=self.repo,
            env=self._env(),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=30,
            check=False,
        )

        self._assert_success(result)
        self.assertTrue((self.home / ".local" / "bin" / "tgd").is_symlink())

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
        installed = self._run_setup("--no-deps")
        self._assert_success(installed)
        self.assertTrue(installed_marker.is_file())

        result = self._run_setup("--uninstall")
        self._assert_success(result)

        version_file = self.repo / "VERSION"
        self.assertTrue(version_file.is_file(), "uninstall must not delete VERSION")
        self.assertEqual(
            original_version,
            version_file.read_text(encoding="utf-8"),
        )
        self.assertFalse(installed_marker.exists())

    def test_install_adopts_and_updates_a_legacy_micro_version_marker(self) -> None:
        installed_marker = self.home / ".tgd-installed-version"
        installed_marker.write_text("v2026.07.11.3\n", encoding="utf-8")
        (self.repo / "VERSION").write_text(
            "v2026.07.26.1\n",
            encoding="utf-8",
        )

        result = self._run_setup("--no-deps")

        self._assert_success(result)
        self.assertEqual(
            "v2026.07.26.1\n",
            installed_marker.read_text(encoding="utf-8"),
        )
        manifest = json.loads(
            (self.home / ".tgd" / "install-manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            "v2026.07.26.1",
            manifest["managed_files"][str(installed_marker)]["version"],
        )

    def test_install_rejects_foreign_version_marker_without_overwriting_it(
        self,
    ) -> None:
        installed_marker = self.home / ".tgd-installed-version"
        installed_marker.write_text("owned by another tool\n", encoding="utf-8")

        result = self._run_setup("--no-deps")

        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertEqual(
            "owned by another tool\n",
            installed_marker.read_text(encoding="utf-8"),
        )
        self.assertFalse(os.path.lexists(self.home / ".local" / "bin" / "tgd"))

    def test_uninstall_without_manifest_preserves_unknown_version_marker(self) -> None:
        installed_marker = self.home / ".tgd-installed-version"
        installed_marker.write_text("owned by another tool\n", encoding="utf-8")

        result = self._run_setup("--uninstall")

        self._assert_success(result)
        self.assertEqual(
            "owned by another tool\n",
            installed_marker.read_text(encoding="utf-8"),
        )

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

    def test_unknown_flag_exits_with_usage_error(self) -> None:
        result = self._run_setup("--definitely-not-a-real-option")

        self.assertEqual(2, result.returncode, result.stdout)

    def test_uninstall_does_not_require_node(self) -> None:
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

    def test_uninstall_reports_legacy_suffix_helper_failure(self) -> None:
        instructions = self.home / ".pi" / "agent" / "instructions.md"
        instructions.parent.mkdir(parents=True)
        instructions.write_text(LEGACY_PI_INSTRUCTIONS, encoding="utf-8")
        helper = self.repo / "scripts" / "install-state.py"
        real_helper = self.repo / "scripts" / "install-state-real.py"
        helper.rename(real_helper)
        helper.write_text(
            """\
import os
import sys

if len(sys.argv) > 1 and sys.argv[1] == "remove-legacy-suffix":
    raise SystemExit(23)
os.execv(sys.executable, [sys.executable, {!r}, *sys.argv[1:]])
""".format(str(real_helper)),
            encoding="utf-8",
        )

        result = self._run_setup("--uninstall")

        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertIn("uninstall finished with errors", result.stdout)
        self.assertEqual(
            LEGACY_PI_INSTRUCTIONS,
            instructions.read_text(encoding="utf-8"),
        )

    def test_python_older_than_3_9_is_rejected_before_installation(self) -> None:
        self._write_fake(
            "python3",
            """
if [ "${1:-}" = "--version" ]; then
    printf 'Python 3.8.18\\n'
    exit 0
fi
exit 1
""",
        )

        result = self._run_setup("--no-deps")

        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertIn("python3 >= 3.9", result.stdout)
        self.assertFalse(os.path.lexists(self.home / ".local" / "bin" / "tgd"))

    def test_command_verification_requires_each_canonical_source_target(self) -> None:
        self._write_fake("codex", "exit 0")
        skills = self.repo / ".codex" / "skills"
        skills.mkdir(parents=True)
        for index in range(6):
            skill = skills / f"tgd-{index}"
            skill.mkdir()
            (skill / "SKILL.md").write_text(
                f"---\nname: tgd-{index}\ndescription: command {index}\n---\n",
                encoding="utf-8",
            )
        foreign = self.home / ".codex" / "prompts" / "tgd-custom.md"
        foreign.parent.mkdir(parents=True)
        foreign.write_text("# foreign\n", encoding="utf-8")

        result = self._run_setup("--no-deps")

        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertIn("6/7 canonical commands", result.stdout)

    def test_codex_uses_on_demand_skills_not_deprecated_prompts(self) -> None:
        self._write_fake("codex", "exit 0")
        lifecycle_skills = self.repo / ".codex" / "skills"
        lifecycle_skills.mkdir(parents=True)
        for name in (
            "tgd-map",
            "tgd-define",
            "tgd-plan",
            "tgd-develop",
            "tgd-verify",
            "tgd-review",
            "tgd-release",
        ):
            skill = lifecycle_skills / name
            skill.mkdir()
            (skill / "SKILL.md").write_text(
                f"---\nname: {name}\ndescription: {name}\n---\n",
                encoding="utf-8",
            )

        result = self._run_setup("--no-deps")

        self._assert_success(result)
        for source in lifecycle_skills.iterdir():
            installed = self.home / ".agents" / "skills" / source.name
            self.assertTrue(installed.is_symlink(), str(installed))
            self.assertEqual(source.resolve(), installed.resolve())
        self.assertFalse(os.path.lexists(self.home / ".codex" / "skills" / "tGD"))
        self.assertFalse(os.path.lexists(self.home / ".codex" / "prompts"))

    def test_session_preamble_is_opt_in_and_plain_setup_removes_it(self) -> None:
        hook = self.repo / "hooks" / "codex" / "session-start.sh"
        hook.parent.mkdir(parents=True)
        shutil.copy2(SOURCE_ROOT / "hooks" / "codex" / "session-start.sh", hook)
        preamble = self.repo / "hooks" / "session-preamble.md"
        shutil.copy2(SOURCE_ROOT / "hooks" / "session-preamble.md", preamble)
        codex_config = self.home / ".codex"
        codex_config.mkdir()

        enabled = self._run_setup("--with-session-preamble", "--no-deps")
        self._assert_success(enabled)
        hook_config = codex_config / "hooks.json"
        self.assertTrue(hook_config.is_file())
        self.assertIn(
            str(hook.resolve()),
            hook_config.read_text(encoding="utf-8"),
        )

        disabled = self._run_setup("--no-deps")
        self._assert_success(disabled)
        if hook_config.exists():
            self.assertNotIn(
                str(hook.resolve()),
                hook_config.read_text(encoding="utf-8"),
            )

    def test_pi_append_system_is_opt_in_and_legacy_instructions_retire(self) -> None:
        pi_source = self.repo / ".pi" / "APPEND_SYSTEM.md"
        pi_source.parent.mkdir()
        pi_source.write_text("Use tGD on demand.\n", encoding="utf-8")
        pi_home = self.home / ".pi" / "agent"
        pi_home.mkdir(parents=True)
        legacy_source = self.repo / ".pi" / "instructions.md"
        legacy_source.write_text("legacy\n", encoding="utf-8")
        legacy_install = pi_home / "instructions.md"
        legacy_install.symlink_to(legacy_source)

        enabled = self._run_setup("--with-session-preamble", "--no-deps")
        self._assert_success(enabled)
        append_system = pi_home / "APPEND_SYSTEM.md"
        self.assertTrue(append_system.is_symlink())
        self.assertEqual(pi_source.resolve(), append_system.resolve())
        self.assertFalse(os.path.lexists(legacy_install))

        disabled = self._run_setup("--no-deps")
        self._assert_success(disabled)
        self.assertFalse(os.path.lexists(append_system))

    def test_plain_setup_clears_manifest_for_a_retired_dangling_link(self) -> None:
        retired_source = self.repo / ".pi" / "instructions.md"
        retired_source.parent.mkdir()
        retired_source.write_text("retired tGD source\n", encoding="utf-8")
        installed = self.home / ".pi" / "agent" / "instructions.md"
        linked = subprocess.run(
            [
                sys.executable,
                str(self.repo / "scripts" / "install-state.py"),
                "link",
                "--manifest",
                str(self.home / ".tgd" / "install-manifest.json"),
                "--path",
                str(installed),
                "--target",
                str(retired_source),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(0, linked.returncode, linked.stdout)
        retired_source.unlink()
        self.assertTrue(installed.is_symlink())
        self.assertFalse(installed.exists())

        result = self._run_setup("--no-deps")

        self._assert_success(result)
        self.assertFalse(os.path.lexists(installed))
        manifest = json.loads(
            (self.home / ".tgd" / "install-manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertNotIn(str(installed), manifest["managed_paths"])

    def test_opencode_skills_are_direct_children(self) -> None:
        opencode_home = self.home / ".config" / "opencode"
        opencode_home.mkdir(parents=True)
        router = self.repo / "skills" / "tgd-router"
        router.mkdir()
        (router / "SKILL.md").write_text("# router\n", encoding="utf-8")

        result = self._run_setup("--no-deps")

        self._assert_success(result)
        for name in ("tgd-rules", "tgd-router"):
            installed = opencode_home / "skills" / name
            self.assertTrue(installed.is_symlink(), str(installed))
            self.assertEqual((self.repo / "skills" / name).resolve(), installed.resolve())
        self.assertFalse(os.path.lexists(opencode_home / "skills" / "tGD"))


if __name__ == "__main__":
    unittest.main()
