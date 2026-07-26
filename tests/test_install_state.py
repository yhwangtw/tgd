import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "install-state.py"


class InstallStateCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(prefix="tGD install O'Brien ")
        self.root = Path(self.temp_dir.name)
        self.home = self.root / "Home O'Brien"
        self.repo = self.root / "repo with spaces O'Brien"
        self.home.mkdir()
        self.repo.mkdir()
        self.manifest = self.home / ".tgd" / "install-state.json"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def run_cli(self, *args: str) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env["HOME"] = str(self.home)
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=str(self.repo),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def link(self, path: Path, target: Path, *extra: str) -> subprocess.CompletedProcess:
        return self.run_cli(
            "link",
            "--manifest",
            str(self.manifest),
            "--path",
            str(path),
            "--target",
            str(target),
            *extra,
        )

    def read_manifest(self) -> dict:
        return json.loads(self.manifest.read_text(encoding="utf-8"))

    def test_link_creates_symlink_records_exact_path_and_verifies_target(self) -> None:
        target = self.repo / "skills" / "tgd-rules"
        destination = self.home / ".codex" / "skills" / "tGD rules"
        target.mkdir(parents=True)

        linked = self.link(destination, target)
        verified = self.run_cli(
            "verify",
            "--manifest",
            str(self.manifest),
            "--path",
            str(destination),
            "--target",
            str(target),
        )

        self.assertEqual(linked.returncode, 0, linked.stderr)
        self.assertEqual(verified.returncode, 0, verified.stderr)
        self.assertTrue(destination.is_symlink())
        self.assertEqual(os.readlink(destination), str(target))
        self.assertEqual(
            self.read_manifest(),
            {
                "managed_paths": {
                    str(destination): {
                        "kind": "symlink",
                        "target": str(target),
                    }
                },
                "version": 1,
            },
        )

    def test_link_replaces_an_owned_symlink_and_updates_manifest(self) -> None:
        first_target = self.repo / "skills" / "first"
        next_target = self.repo / "skills" / "next"
        destination = self.home / ".codex" / "skills" / "tGD"
        first_target.mkdir(parents=True)
        next_target.mkdir(parents=True)
        self.assertEqual(self.link(destination, first_target).returncode, 0)

        result = self.link(destination, next_target)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(os.readlink(destination), str(next_target))
        self.assertEqual(
            self.read_manifest()["managed_paths"][str(destination)]["target"],
            str(next_target),
        )

    def test_verify_rejects_a_target_that_does_not_match_the_manifest(self) -> None:
        target = self.repo / "skills"
        other_target = self.repo / "other"
        destination = self.home / ".codex" / "skills" / "tGD"
        target.mkdir()
        other_target.mkdir()
        self.assertEqual(self.link(destination, target).returncode, 0)

        result = self.run_cli(
            "verify",
            "--manifest",
            str(self.manifest),
            "--path",
            str(destination),
            "--target",
            str(other_target),
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("target mismatch", result.stderr.lower())

    def test_link_replaces_only_an_explicit_exact_legacy_target(self) -> None:
        legacy_target = self.repo / "legacy skills"
        new_target = self.repo / "skills"
        destination = self.home / ".codex" / "skills" / "tGD"
        legacy_target.mkdir()
        new_target.mkdir()
        destination.parent.mkdir(parents=True)
        destination.symlink_to(legacy_target)

        result = self.link(
            destination,
            new_target,
            "--legacy-target",
            str(legacy_target),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(os.readlink(destination), str(new_target))
        self.assertIn(str(destination), self.read_manifest()["managed_paths"])

    def test_link_refuses_foreign_file_directory_and_symlink_collisions(self) -> None:
        target = self.repo / "skills"
        foreign_target = self.repo / "foreign"
        target.mkdir()
        foreign_target.mkdir()

        for kind in ("file", "directory", "symlink"):
            with self.subTest(kind=kind):
                destination = self.home / kind / "tGD"
                destination.parent.mkdir(parents=True)
                if kind == "file":
                    destination.write_text("keep me", encoding="utf-8")
                elif kind == "directory":
                    destination.mkdir()
                else:
                    destination.symlink_to(foreign_target)

                result = self.link(destination, target)

                self.assertNotEqual(result.returncode, 0)
                self.assertIn("collision", result.stderr.lower())
                if kind == "file":
                    self.assertEqual(destination.read_text(encoding="utf-8"), "keep me")
                elif kind == "directory":
                    self.assertTrue(destination.is_dir())
                else:
                    self.assertEqual(os.readlink(destination), str(foreign_target))

    def test_link_refuses_a_tampered_managed_symlink(self) -> None:
        recorded_target = self.repo / "recorded"
        foreign_target = self.repo / "foreign"
        next_target = self.repo / "next"
        destination = self.home / ".codex" / "skills" / "tGD"
        for path in (recorded_target, foreign_target, next_target):
            path.mkdir()
        self.assertEqual(self.link(destination, recorded_target).returncode, 0)
        destination.unlink()
        destination.symlink_to(foreign_target)

        result = self.link(destination, next_target)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("changed since it was recorded", result.stderr.lower())
        self.assertEqual(os.readlink(destination), str(foreign_target))
        self.assertEqual(
            self.read_manifest()["managed_paths"][str(destination)]["target"],
            str(recorded_target),
        )

    def test_remove_deletes_only_an_owned_untampered_symlink(self) -> None:
        target = self.repo / "skills"
        destination = self.home / ".codex" / "skills" / "tGD"
        target.mkdir()
        self.assertEqual(self.link(destination, target).returncode, 0)

        result = self.run_cli(
            "remove",
            "--manifest",
            str(self.manifest),
            "--path",
            str(destination),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(os.path.lexists(destination))
        self.assertEqual(self.read_manifest()["managed_paths"], {})

    def test_remove_refuses_unowned_and_tampered_symlinks(self) -> None:
        owned_target = self.repo / "owned"
        foreign_target = self.repo / "foreign"
        owned_target.mkdir()
        foreign_target.mkdir()

        unowned = self.home / "unowned"
        unowned.symlink_to(foreign_target)
        unowned_result = self.run_cli(
            "remove",
            "--manifest",
            str(self.manifest),
            "--path",
            str(unowned),
        )

        managed = self.home / "managed"
        self.assertEqual(self.link(managed, owned_target).returncode, 0)
        managed.unlink()
        managed.symlink_to(foreign_target)
        tampered_result = self.run_cli(
            "remove",
            "--manifest",
            str(self.manifest),
            "--path",
            str(managed),
        )

        self.assertNotEqual(unowned_result.returncode, 0)
        self.assertNotEqual(tampered_result.returncode, 0)
        self.assertIn("not managed", unowned_result.stderr.lower())
        self.assertIn("changed since it was recorded", tampered_result.stderr.lower())
        self.assertEqual(os.readlink(unowned), str(foreign_target))
        self.assertEqual(os.readlink(managed), str(foreign_target))
        self.assertIn(str(managed), self.read_manifest()["managed_paths"])

    def test_remove_all_removes_matches_keeps_foreign_paths_and_clears_manifest(self) -> None:
        owned_target = self.repo / "owned"
        replaced_target = self.repo / "replaced"
        owned_target.mkdir()
        replaced_target.mkdir()
        removable = self.home / ".codex" / "skills" / "owned"
        replaced = self.home / ".codex" / "skills" / "replaced"
        self.assertEqual(self.link(removable, owned_target).returncode, 0)
        self.assertEqual(self.link(replaced, owned_target).returncode, 0)
        replaced.unlink()
        replaced.symlink_to(replaced_target)

        result = self.run_cli(
            "remove-all",
            "--manifest",
            str(self.manifest),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("removed=1", result.stdout)
        self.assertIn("kept=1", result.stdout)
        self.assertFalse(os.path.lexists(removable))
        self.assertEqual(os.readlink(replaced), str(replaced_target))
        self.assertFalse(self.manifest.exists())

    def test_tilde_paths_work_with_spaces_and_single_quotes_in_home_and_repo(self) -> None:
        target = self.repo / "skill's source"
        target.mkdir()

        result = self.run_cli(
            "link",
            "--manifest",
            "~/.tgd/state file.json",
            "--path",
            "~/.codex/skills/tGD link",
            "--target",
            str(target),
        )

        destination = self.home / ".codex" / "skills" / "tGD link"
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(os.readlink(destination), str(target))
        self.assertTrue((self.home / ".tgd" / "state file.json").is_file())

    def test_invalid_manifest_is_not_overwritten(self) -> None:
        target = self.repo / "skills"
        destination = self.home / ".codex" / "skills" / "tGD"
        target.mkdir()
        self.manifest.parent.mkdir(parents=True)
        self.manifest.write_text("{broken", encoding="utf-8")

        result = self.link(destination, target)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid manifest", result.stderr.lower())
        self.assertEqual(self.manifest.read_text(encoding="utf-8"), "{broken")
        self.assertFalse(os.path.lexists(destination))

    def test_manifest_write_is_atomic_when_serialization_fails(self) -> None:
        spec = importlib.util.spec_from_file_location("install_state", SCRIPT)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.manifest.parent.mkdir(parents=True)
        self.manifest.write_text('{"sentinel": true}\n', encoding="utf-8")

        def fail_after_partial_write(data, stream, **kwargs):
            stream.write('{"partial":')
            raise RuntimeError("serialization failed")

        with mock.patch.object(module.json, "dump", side_effect=fail_after_partial_write):
            with self.assertRaises(RuntimeError):
                module.write_json_atomic(self.manifest, {"version": 1})

        self.assertEqual(
            self.manifest.read_text(encoding="utf-8"),
            '{"sentinel": true}\n',
        )


if __name__ == "__main__":
    unittest.main()
