"""Tests for deterministic Understand-Anything build freshness state."""

from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "ua-build-state.py"


class UaBuildStateTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="tgd-ua-build-state-")
        self.ua_root = Path(self._tmp.name) / "understand-anything"
        self.stamp = Path(self._tmp.name) / "state" / "ua-build-state.json"
        source = (
            self.ua_root
            / "understand-anything-plugin"
            / "packages"
            / "core"
            / "src"
            / "index.ts"
        )
        source.parent.mkdir(parents=True)
        source.write_text("export const version = 1;\n", encoding="utf-8")
        (self.ua_root / "pnpm-lock.yaml").write_text(
            "lockfileVersion: '9.0'\n",
            encoding="utf-8",
        )
        (self.ua_root / "package.json").write_text(
            '{"scripts":{"build":"pnpm -r build"}}\n',
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _run(self, command: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(HELPER),
                command,
                "--ua-root",
                str(self.ua_root),
                "--stamp",
                str(self.stamp),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def _create_artifacts(self) -> None:
        modules = self.ua_root / "node_modules" / ".modules.yaml"
        modules.parent.mkdir(parents=True, exist_ok=True)
        modules.write_text("packageManager: pnpm\n", encoding="utf-8")
        core = (
            self.ua_root
            / "understand-anything-plugin"
            / "packages"
            / "core"
            / "dist"
            / "index.js"
        )
        core.parent.mkdir(parents=True, exist_ok=True)
        core.write_text("// built\n", encoding="utf-8")

    def test_source_and_lockfile_changes_invalidate_the_stamp(self) -> None:
        self._create_artifacts()
        written = self._run("write")
        self.assertEqual(0, written.returncode, written.stderr)
        self.assertEqual(0, self._run("is-current").returncode)

        source = (
            self.ua_root
            / "understand-anything-plugin"
            / "packages"
            / "core"
            / "src"
            / "index.ts"
        )
        source.write_text("export const version = 2;\n", encoding="utf-8")
        self.assertNotEqual(0, self._run("is-current").returncode)

        source.write_text("export const version = 1;\n", encoding="utf-8")
        self.assertEqual(0, self._run("is-current").returncode)
        (self.ua_root / "pnpm-lock.yaml").write_text(
            "lockfileVersion: '9.1'\n",
            encoding="utf-8",
        )
        self.assertNotEqual(0, self._run("is-current").returncode)

    def test_generated_artifact_changes_do_not_change_the_fingerprint(self) -> None:
        first = self._run("fingerprint")
        self.assertEqual(0, first.returncode, first.stderr)

        self._create_artifacts()
        generated = (
            self.ua_root
            / "understand-anything-plugin"
            / "packages"
            / "core"
            / "dist"
            / "index.js"
        )
        generated.write_text("// rebuilt differently\n", encoding="utf-8")
        second = self._run("fingerprint")

        self.assertEqual(0, second.returncode, second.stderr)
        self.assertEqual(first.stdout, second.stdout)

    def test_current_requires_both_artifacts_and_a_matching_stamp(self) -> None:
        self.assertNotEqual(0, self._run("is-current").returncode)
        self._create_artifacts()
        self.assertNotEqual(0, self._run("is-current").returncode)

        self.assertEqual(0, self._run("write").returncode)
        self.assertEqual(0, self._run("is-current").returncode)

        (
            self.ua_root
            / "understand-anything-plugin"
            / "packages"
            / "core"
            / "dist"
            / "index.js"
        ).unlink()
        self.assertNotEqual(0, self._run("is-current").returncode)

    def test_write_refuses_a_symlinked_stamp_without_touching_its_target(self) -> None:
        self._create_artifacts()
        foreign = Path(self._tmp.name) / "foreign-state.json"
        foreign.write_text("user owned\n", encoding="utf-8")
        self.stamp.parent.mkdir(parents=True)
        self.stamp.symlink_to(foreign)

        written = self._run("write")

        self.assertEqual(2, written.returncode, written.stderr)
        self.assertIn("refusing to replace symlinked state file", written.stderr)
        self.assertEqual("user owned\n", foreign.read_text(encoding="utf-8"))
        self.assertTrue(self.stamp.is_symlink())

    def test_helper_is_importable_on_the_supported_python_baseline(self) -> None:
        source = HELPER.read_text(encoding="utf-8")
        ast.parse(source, filename=str(HELPER), feature_version=(3, 9))


if __name__ == "__main__":
    unittest.main()
