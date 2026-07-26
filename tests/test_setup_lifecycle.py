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
                    mode = stat.S_IMODE(path.stat(follow_symlinks=False).st_mode)
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

    def test_install_preserves_foreign_directory_on_name_collision(self) -> None:
        self._write_fake("hermes", "exit 0")
        collision = self.home / ".hermes" / "skills" / "tgd-rules"
        collision.mkdir(parents=True)
        sentinel = collision / "foreign.txt"
        sentinel.write_text("owned by the user\n", encoding="utf-8")

        self._run_setup()

        self.assertTrue(collision.is_dir() and not collision.is_symlink())
        self.assertEqual("owned by the user\n", sentinel.read_text(encoding="utf-8"))

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
