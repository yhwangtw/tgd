import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
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
        target = self.repo / "skills" / "tgd-core-rules"
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

    def test_link_replaces_only_an_exact_generated_legacy_file(self) -> None:
        target = self.repo / "instructions.md"
        target.write_text("current instructions\n", encoding="utf-8")
        destination = self.home / ".pi" / "agent" / "instructions.md"
        destination.parent.mkdir(parents=True)
        legacy_content = b"exact generated legacy content\n"
        destination.write_bytes(legacy_content)
        legacy_hash = hashlib.sha256(legacy_content).hexdigest()

        result = self.link(
            destination,
            target,
            "--legacy-file-sha256",
            legacy_hash,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(destination.is_symlink())
        self.assertEqual(target.resolve(), destination.resolve())
        self.assertIn(str(destination), self.read_manifest()["managed_paths"])

    def test_link_preserves_a_modified_legacy_looking_file(self) -> None:
        target = self.repo / "instructions.md"
        target.write_text("current instructions\n", encoding="utf-8")
        destination = self.home / ".pi" / "agent" / "instructions.md"
        destination.parent.mkdir(parents=True)
        exact_content = b"exact generated legacy content\n"
        modified_content = exact_content + b"user addition\n"
        destination.write_bytes(modified_content)

        result = self.link(
            destination,
            target,
            "--legacy-file-sha256",
            hashlib.sha256(exact_content).hexdigest(),
        )

        self.assertNotEqual(0, result.returncode)
        self.assertEqual(modified_content, destination.read_bytes())
        self.assertFalse(destination.is_symlink())

    def test_legacy_file_rollback_restores_the_exact_original(self) -> None:
        spec = importlib.util.spec_from_file_location("install_state_legacy", SCRIPT)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        target = self.repo / "instructions.md"
        target.write_text("current instructions\n", encoding="utf-8")
        destination = self.home / ".pi" / "agent" / "instructions.md"
        destination.parent.mkdir(parents=True)
        legacy_content = b"exact generated legacy content\n"
        destination.write_bytes(legacy_content)

        with mock.patch.object(
            module,
            "write_json_atomic",
            side_effect=OSError("simulated manifest failure"),
        ):
            with self.assertRaises(OSError):
                module.link_path(
                    self.manifest,
                    destination,
                    target,
                    [],
                    [hashlib.sha256(legacy_content).hexdigest()],
                )

        self.assertFalse(destination.is_symlink())
        self.assertEqual(legacy_content, destination.read_bytes())

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

    def test_link_rollback_preserves_a_concurrent_foreign_replacement(self) -> None:
        spec = importlib.util.spec_from_file_location("install_state_link", SCRIPT)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        target = self.repo / "owned"
        foreign_target = self.repo / "foreign"
        destination = self.home / ".codex" / "skills" / "tGD"
        target.mkdir()
        foreign_target.mkdir()

        def replace_link_then_fail(*args, **kwargs):
            destination.unlink()
            destination.symlink_to(foreign_target)
            raise OSError("simulated manifest failure")

        with mock.patch.object(
            module,
            "write_json_atomic",
            side_effect=replace_link_then_fail,
        ):
            with self.assertRaises(module.InstallStateError):
                module.link_path(self.manifest, destination, target, [])

        self.assertTrue(destination.is_symlink())
        self.assertEqual(foreign_target.resolve(), destination.resolve())

    def test_link_restores_previous_symlink_when_new_symlink_creation_fails(
        self,
    ) -> None:
        spec = importlib.util.spec_from_file_location(
            "install_state_link_failure",
            SCRIPT,
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        old_target = self.repo / "old"
        new_target = self.repo / "new"
        destination = self.home / ".codex" / "skills" / "tGD"
        old_target.mkdir()
        new_target.mkdir()
        destination.parent.mkdir(parents=True)
        destination.symlink_to(old_target)
        original_symlink = module.os.symlink

        def fail_new_symlink(target, link_name, *args, **kwargs):
            if Path(target) == new_target and Path(link_name) == destination:
                raise OSError("simulated symlink creation failure")
            return original_symlink(target, link_name, *args, **kwargs)

        with mock.patch.object(
            module.os,
            "symlink",
            side_effect=fail_new_symlink,
        ):
            with self.assertRaises(OSError):
                module.link_path(
                    self.manifest,
                    destination,
                    new_target,
                    [old_target],
                )

        self.assertTrue(destination.is_symlink())
        self.assertEqual(old_target.resolve(), destination.resolve())
        self.assertFalse(self.manifest.exists())
        self.assertEqual(
            [],
            list(destination.parent.glob(".tGD.tgd-quarantine.*")),
        )

    def test_link_reports_committed_state_when_old_quarantine_discard_fails(
        self,
    ) -> None:
        spec = importlib.util.spec_from_file_location(
            "install_state_link_cleanup_failure",
            SCRIPT,
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        old_target = self.repo / "old"
        new_target = self.repo / "new"
        destination = self.home / ".codex" / "skills" / "tGD"
        old_target.mkdir()
        new_target.mkdir()
        destination.parent.mkdir(parents=True)
        destination.symlink_to(old_target)
        original_unlink = Path.unlink
        failed_once = False

        def fail_quarantine_discard(path, *args, **kwargs):
            nonlocal failed_once
            if ".tgd-quarantine." in path.name and not failed_once:
                failed_once = True
                raise PermissionError("simulated quarantine discard failure")
            return original_unlink(path, *args, **kwargs)

        with mock.patch.object(Path, "unlink", fail_quarantine_discard):
            with self.assertRaises(module.InstallStateError) as raised:
                module.link_path(
                    self.manifest,
                    destination,
                    new_target,
                    [old_target],
                )

        self.assertTrue(failed_once)
        self.assertIn("update committed", str(raised.exception))
        self.assertIn("preserved at", str(raised.exception))
        self.assertTrue(destination.is_symlink())
        self.assertEqual(new_target.resolve(), destination.resolve())
        self.assertEqual(
            str(new_target),
            self.read_manifest()["managed_paths"][str(destination)]["target"],
        )
        quarantines = list(
            destination.parent.glob(".tGD.tgd-quarantine.*")
        )
        self.assertEqual(1, len(quarantines))
        self.assertTrue(quarantines[0].is_symlink())
        self.assertEqual(str(old_target), os.readlink(quarantines[0]))

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

    def test_retire_owned_link_allows_a_deleted_source_target(self) -> None:
        target = self.repo / "retired" / "instructions.md"
        target.parent.mkdir()
        target.write_text("old tGD integration\n", encoding="utf-8")
        destination = self.home / ".pi" / "agent" / "instructions.md"
        self.assertEqual(self.link(destination, target).returncode, 0)
        target.unlink()

        result = self.run_cli(
            "retire-owned-link",
            "--manifest",
            str(self.manifest),
            "--path",
            str(destination),
            "--target",
            str(target),
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse(os.path.lexists(destination))
        self.assertEqual({}, self.read_manifest()["managed_paths"])

    def test_retire_owned_link_preserves_a_different_recorded_target(self) -> None:
        target = self.repo / "installed"
        other = self.repo / "expected"
        target.mkdir()
        other.mkdir()
        destination = self.home / ".config" / "tool" / "tgd"
        self.assertEqual(self.link(destination, target).returncode, 0)

        result = self.run_cli(
            "retire-owned-link",
            "--manifest",
            str(self.manifest),
            "--path",
            str(destination),
            "--target",
            str(other),
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(destination.is_symlink())
        self.assertIn(str(destination), self.read_manifest()["managed_paths"])

    def test_remove_preserves_foreign_replacement_swapped_at_quarantine(
        self,
    ) -> None:
        spec = importlib.util.spec_from_file_location(
            "install_state_remove_race",
            SCRIPT,
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        target = self.repo / "owned"
        destination = self.home / ".codex" / "skills" / "tGD"
        foreign_content = b"foreign replacement\n"
        target.mkdir()
        module.link_path(self.manifest, destination, target, [])
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
                destination.write_bytes(foreign_content)
            return original_replace(source, replacement)

        with mock.patch.object(
            module.os,
            "replace",
            side_effect=swap_before_quarantine,
        ):
            with self.assertRaises(module.InstallStateError):
                module.remove_path(self.manifest, destination)

        self.assertTrue(swapped)
        self.assertEqual(foreign_content, destination.read_bytes())
        self.assertIn(
            str(destination),
            self.read_manifest()["managed_paths"],
        )
        self.assertEqual(
            [],
            list(destination.parent.glob(".tGD.tgd-quarantine.*")),
        )

    def test_remove_restores_path_and_manifest_when_quarantine_discard_fails(
        self,
    ) -> None:
        spec = importlib.util.spec_from_file_location(
            "install_state_remove_cleanup_failure",
            SCRIPT,
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        target = self.repo / "owned"
        destination = self.home / ".codex" / "skills" / "tGD"
        target.mkdir()
        module.link_path(self.manifest, destination, target, [])
        original_unlink = Path.unlink
        failed_once = False

        def fail_quarantine_discard(path, *args, **kwargs):
            nonlocal failed_once
            if ".tgd-quarantine." in path.name and not failed_once:
                failed_once = True
                raise PermissionError("simulated quarantine discard failure")
            return original_unlink(path, *args, **kwargs)

        with mock.patch.object(Path, "unlink", fail_quarantine_discard):
            with self.assertRaises(module.InstallStateError) as raised:
                module.remove_path(self.manifest, destination)

        self.assertTrue(failed_once)
        self.assertIn("path and ownership were restored", str(raised.exception))
        self.assertTrue(destination.is_symlink())
        self.assertEqual(target.resolve(), destination.resolve())
        self.assertEqual(
            str(target),
            self.read_manifest()["managed_paths"][str(destination)]["target"],
        )
        self.assertEqual(
            [],
            list(destination.parent.glob(".tGD.tgd-quarantine.*")),
        )

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

    def test_remove_all_keeps_manifest_for_owned_links_that_cannot_be_removed(
        self,
    ) -> None:
        spec = importlib.util.spec_from_file_location("install_state_remove", SCRIPT)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        target = self.repo / "owned"
        target.mkdir()
        managed = self.home / ".codex" / "skills" / "owned"
        self.assertEqual(self.link(managed, target).returncode, 0)
        original_unlink = Path.unlink
        failed_once = False

        def fail_managed_unlink(path, *args, **kwargs):
            nonlocal failed_once
            if ".tgd-quarantine." in path.name and not failed_once:
                failed_once = True
                raise PermissionError("simulated permission failure")
            return original_unlink(path, *args, **kwargs)

        with mock.patch.object(Path, "unlink", fail_managed_unlink):
            with self.assertRaises(module.InstallStateError):
                module.remove_all(self.manifest)

        self.assertTrue(failed_once)
        self.assertTrue(managed.is_symlink())
        self.assertEqual(
            {str(managed)},
            set(self.read_manifest()["managed_paths"]),
            "failed owned links must remain recorded for a safe retry",
        )

    def test_remove_all_preserves_swapped_foreign_path_and_failed_ownership(
        self,
    ) -> None:
        spec = importlib.util.spec_from_file_location(
            "install_state_remove_all_race",
            SCRIPT,
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        target = self.repo / "owned"
        safe = self.home / "a-safe"
        swapped_path = self.home / "z-swapped"
        foreign_content = b"foreign replacement\n"
        target.mkdir()
        module.link_path(self.manifest, safe, target, [])
        module.link_path(self.manifest, swapped_path, target, [])
        original_replace = module.os.replace
        swapped = False

        def swap_before_quarantine(source, replacement):
            nonlocal swapped
            if (
                not swapped
                and Path(source) == swapped_path
                and ".tgd-quarantine." in Path(replacement).name
            ):
                swapped = True
                swapped_path.unlink()
                swapped_path.write_bytes(foreign_content)
            return original_replace(source, replacement)

        with mock.patch.object(
            module.os,
            "replace",
            side_effect=swap_before_quarantine,
        ):
            with self.assertRaises(module.InstallStateError):
                module.remove_all(self.manifest)

        self.assertTrue(swapped)
        self.assertFalse(os.path.lexists(safe))
        self.assertEqual(foreign_content, swapped_path.read_bytes())
        self.assertEqual(
            {str(swapped_path)},
            set(self.read_manifest()["managed_paths"]),
            "only the failed ownership entry must remain for retry",
        )
        self.assertEqual(
            [],
            list(self.home.glob(".z-swapped.tgd-quarantine.*")),
        )

    def test_version_marker_is_adopted_recorded_updated_and_removed(self) -> None:
        marker = self.home / ".tgd-installed-version"
        marker.write_text("v2026.07.11.3\n", encoding="utf-8")

        installed = self.run_cli(
            "write-marker",
            "--manifest",
            str(self.manifest),
            "--path",
            str(marker),
            "--version",
            "v2026.07.26.1",
            "--legacy-version",
            "v2026.07.11.3",
        )

        self.assertEqual(0, installed.returncode, installed.stderr)
        self.assertEqual("v2026.07.26.1\n", marker.read_text(encoding="utf-8"))
        self.assertEqual(
            {
                "kind": "version-marker",
                "version": "v2026.07.26.1",
            },
            self.read_manifest()["managed_files"][str(marker)],
        )

        updated = self.run_cli(
            "write-marker",
            "--manifest",
            str(self.manifest),
            "--path",
            str(marker),
            "--version",
            "v2026.07.26.2",
        )
        removed = self.run_cli(
            "remove-all",
            "--manifest",
            str(self.manifest),
        )

        self.assertEqual(0, updated.returncode, updated.stderr)
        self.assertEqual(0, removed.returncode, removed.stderr)
        self.assertFalse(marker.exists())
        self.assertFalse(self.manifest.exists())

    def test_version_marker_refuses_foreign_and_tampered_content(self) -> None:
        marker = self.home / ".tgd-installed-version"
        marker.write_text("foreign owner\n", encoding="utf-8")

        foreign = self.run_cli(
            "write-marker",
            "--manifest",
            str(self.manifest),
            "--path",
            str(marker),
            "--version",
            "v2026.07.26",
        )

        self.assertNotEqual(0, foreign.returncode)
        self.assertIn("foreign version marker", foreign.stderr)
        self.assertEqual("foreign owner\n", marker.read_text(encoding="utf-8"))

        marker.write_text("v2026.07.23\n", encoding="utf-8")
        adopted = self.run_cli(
            "write-marker",
            "--manifest",
            str(self.manifest),
            "--path",
            str(marker),
            "--version",
            "v2026.07.26",
            "--legacy-version",
            "v2026.07.23",
        )
        self.assertEqual(0, adopted.returncode, adopted.stderr)
        marker.write_text("user changed this\n", encoding="utf-8")

        tampered = self.run_cli(
            "check-marker",
            "--manifest",
            str(self.manifest),
            "--path",
            str(marker),
        )

        self.assertNotEqual(0, tampered.returncode)
        self.assertIn("changed since it was recorded", tampered.stderr)
        self.assertEqual("user changed this\n", marker.read_text(encoding="utf-8"))

    def test_version_marker_recovers_an_interrupted_managed_upgrade(self) -> None:
        marker = self.home / ".tgd-installed-version"
        marker.write_text("v2026.07.26.2\n", encoding="utf-8")
        self.manifest.parent.mkdir(parents=True)
        self.manifest.write_text(
            json.dumps(
                {
                    "version": 1,
                    "managed_paths": {},
                    "managed_files": {
                        str(marker): {
                            "kind": "version-marker",
                            "version": "v2026.07.26.1",
                        }
                    },
                }
            ),
            encoding="utf-8",
        )

        checked = self.run_cli(
            "check-marker",
            "--manifest",
            str(self.manifest),
            "--path",
            str(marker),
            "--recovery-version",
            "v2026.07.26.2",
        )
        recovered = self.run_cli(
            "write-marker",
            "--manifest",
            str(self.manifest),
            "--path",
            str(marker),
            "--version",
            "v2026.07.26.2",
        )

        self.assertEqual(0, checked.returncode, checked.stderr)
        self.assertEqual(0, recovered.returncode, recovered.stderr)
        self.assertEqual(
            "v2026.07.26.2",
            self.read_manifest()["managed_files"][str(marker)]["version"],
        )

    def test_new_marker_rollback_preserves_a_concurrent_foreign_file(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "install_state_new_marker",
            SCRIPT,
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        marker = self.home / ".tgd-installed-version"

        def replace_marker_then_fail(*args, **kwargs):
            marker.write_text("foreign replacement\n", encoding="utf-8")
            raise OSError("simulated manifest failure")

        with mock.patch.object(
            module,
            "write_json_atomic",
            side_effect=replace_marker_then_fail,
        ):
            with self.assertRaises(module.InstallStateError):
                module.write_marker(
                    self.manifest,
                    marker,
                    "v2026.07.26.1",
                    [],
                )

        self.assertEqual(
            "foreign replacement\n",
            marker.read_text(encoding="utf-8"),
        )

    def test_existing_marker_rollback_preserves_same_content_new_inode(
        self,
    ) -> None:
        spec = importlib.util.spec_from_file_location(
            "install_state_existing_marker",
            SCRIPT,
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        marker = self.home / ".tgd-installed-version"
        marker.write_text("v2026.07.23\n", encoding="utf-8")
        replacement_inode = None

        def replace_marker_then_fail(*args, **kwargs):
            nonlocal replacement_inode
            marker.unlink()
            marker.write_text("v2026.07.26\n", encoding="utf-8")
            replacement_inode = marker.stat().st_ino
            raise OSError("simulated manifest failure")

        with mock.patch.object(
            module,
            "write_json_atomic",
            side_effect=replace_marker_then_fail,
        ):
            with self.assertRaises(module.InstallStateError):
                module.write_marker(
                    self.manifest,
                    marker,
                    "v2026.07.26",
                    ["v2026.07.23"],
                )

        self.assertEqual("v2026.07.26\n", marker.read_text(encoding="utf-8"))
        self.assertEqual(replacement_inode, marker.stat().st_ino)
        self.assertFalse(self.manifest.exists())

    def test_marker_atomic_writer_rejects_an_observed_foreign_update(self) -> None:
        spec = importlib.util.spec_from_file_location("install_state_marker", SCRIPT)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        marker = self.home / ".tgd-installed-version"
        marker.write_bytes(b"before\n")
        expected = marker.read_bytes()
        marker.write_bytes(b"foreign-newer\n")

        with self.assertRaises(module.InstallStateError):
            module.write_bytes_atomic(
                marker,
                b"tgd-update\n",
                0o600,
                expected,
            )

        self.assertEqual(b"foreign-newer\n", marker.read_bytes())

    def test_marker_initial_write_rejects_same_content_new_inode(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "install_state_marker_initial_race",
            SCRIPT,
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        marker = self.home / ".tgd-installed-version"
        original_content = b"v2026.07.23\n"
        marker.write_bytes(original_content)
        original_inode = marker.stat().st_ino
        original_writer = module.write_bytes_atomic
        replacement_inode = None

        def replace_before_initial_write(*args, **kwargs):
            nonlocal replacement_inode
            replacement = marker.with_name(".tgd-installed-version.replacement")
            replacement.write_bytes(original_content)
            replacement_inode = replacement.stat().st_ino
            self.assertNotEqual(original_inode, replacement_inode)
            os.replace(replacement, marker)
            return original_writer(*args, **kwargs)

        with mock.patch.object(
            module,
            "write_bytes_atomic",
            side_effect=replace_before_initial_write,
        ):
            with self.assertRaises(module.InstallStateError):
                module.write_marker(
                    self.manifest,
                    marker,
                    "v2026.07.26",
                    ["v2026.07.23"],
                )

        self.assertEqual(original_content, marker.read_bytes())
        self.assertEqual(replacement_inode, marker.stat().st_ino)
        self.assertFalse(self.manifest.exists())

    def test_manifest_lock_serializes_complete_link_transactions(self) -> None:
        first_target = self.repo / "first"
        second_target = self.repo / "second"
        first_target.mkdir()
        second_target.mkdir()
        first_link = self.home / "first-link"
        second_link = self.home / "second-link"
        ready = self.root / "holder-ready"
        release = self.root / "release-holder"
        holder_code = """
import importlib.util
from pathlib import Path
import sys
import time

spec = importlib.util.spec_from_file_location("install_state_holder", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
original = module._link_path_unlocked

def delayed(*args, **kwargs):
    Path(sys.argv[6]).write_text("ready", encoding="utf-8")
    while not Path(sys.argv[7]).exists():
        time.sleep(0.01)
    return original(*args, **kwargs)

module._link_path_unlocked = delayed
module.link_path(
    Path(sys.argv[2]),
    Path(sys.argv[3]),
    Path(sys.argv[4]),
    [],
)
"""
        holder = subprocess.Popen(
            [
                sys.executable,
                "-c",
                holder_code,
                str(SCRIPT),
                str(self.manifest),
                str(first_link),
                str(first_target),
                "unused",
                str(ready),
                str(release),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        deadline = time.monotonic() + 5
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(ready.exists(), "first transaction never acquired its lock")

        contender = subprocess.Popen(
            [
                sys.executable,
                str(SCRIPT),
                "link",
                "--manifest",
                str(self.manifest),
                "--path",
                str(second_link),
                "--target",
                str(second_target),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        time.sleep(0.1)
        self.assertIsNone(
            contender.poll(),
            "second transaction should block while the first owns the lock",
        )
        release.write_text("go", encoding="utf-8")
        holder_stdout, holder_stderr = holder.communicate(timeout=5)
        contender_stdout, contender_stderr = contender.communicate(timeout=5)

        self.assertEqual(0, holder.returncode, holder_stdout + holder_stderr)
        self.assertEqual(
            0,
            contender.returncode,
            contender_stdout + contender_stderr,
        )
        self.assertTrue(first_link.is_symlink())
        self.assertTrue(second_link.is_symlink())
        self.assertEqual(
            {str(first_link), str(second_link)},
            set(self.read_manifest()["managed_paths"]),
        )

    def test_remove_legacy_suffix_deletes_a_whole_generated_file(self) -> None:
        suffix = b"\n# generated tGD legacy block\n"
        destination = self.home / ".config" / "legacy.md"
        destination.parent.mkdir(parents=True)
        destination.write_bytes(suffix)

        result = self.run_cli(
            "remove-legacy-suffix",
            "--manifest",
            str(self.manifest),
            "--path",
            str(destination),
            "--size",
            str(len(suffix)),
            "--sha256",
            hashlib.sha256(suffix).hexdigest(),
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("removed legacy suffix", result.stdout)
        self.assertFalse(destination.exists())

    def test_remove_legacy_suffix_preserves_the_user_prefix(self) -> None:
        prefix = b"# user configuration\n"
        suffix = b"\n# generated tGD legacy block\n"
        destination = self.home / ".config" / "legacy.md"
        destination.parent.mkdir(parents=True)
        destination.write_bytes(prefix + suffix)

        result = self.run_cli(
            "remove-legacy-suffix",
            "--manifest",
            str(self.manifest),
            "--path",
            str(destination),
            "--size",
            str(len(suffix)),
            "--sha256",
            hashlib.sha256(suffix).hexdigest(),
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("removed legacy suffix", result.stdout)
        self.assertEqual(prefix, destination.read_bytes())

    def test_remove_legacy_suffix_preserves_a_modified_generated_block(
        self,
    ) -> None:
        suffix = b"\n# generated tGD legacy block\n"
        modified = suffix + b"# user edit\n"
        destination = self.home / ".config" / "legacy.md"
        destination.parent.mkdir(parents=True)
        destination.write_bytes(modified)

        result = self.run_cli(
            "remove-legacy-suffix",
            "--manifest",
            str(self.manifest),
            "--path",
            str(destination),
            "--size",
            str(len(suffix)),
            "--sha256",
            hashlib.sha256(suffix).hexdigest(),
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("preserved legacy suffix", result.stdout)
        self.assertEqual(modified, destination.read_bytes())

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
