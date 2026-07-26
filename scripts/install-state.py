#!/usr/bin/env python3
"""Safely manage symlinks owned by the tGD installer."""

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
from typing import Any, Dict, Iterable, Optional


MANIFEST_VERSION = 1
VERSION_PATTERN = re.compile(
    r"^v[0-9]{4}\.[0-9]{2}\.[0-9]{2}(?:\.[1-9][0-9]*)?$"
)
_UNSET = object()


class InstallStateError(Exception):
    """A safe, user-facing install-state failure."""


def normalize_path(value: str) -> Path:
    """Expand HOME and return a normalized absolute path without resolving links."""
    return Path(os.path.abspath(os.path.expanduser(value)))


@contextmanager
def manifest_lock(manifest_path: Path):
    """Serialize ownership mutations across concurrent installer processes."""
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = manifest_path.with_name(manifest_path.name + ".lock")
    flags = os.O_CREAT | os.O_RDWR
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(str(lock_path), flags, 0o600)
    except OSError as error:
        raise InstallStateError(
            "cannot safely open ownership lock: {}".format(lock_path)
        ) from error
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise InstallStateError(
                "ownership lock is not a regular file: {}".format(lock_path)
            )
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)


def symlink_target(path: Path) -> Path:
    """Return a symlink's target as a normalized absolute path."""
    raw_target = os.readlink(str(path))
    if os.path.isabs(raw_target):
        return normalize_path(raw_target)
    return normalize_path(os.path.join(str(path.parent), raw_target))


def empty_manifest() -> Dict[str, Any]:
    return {"version": MANIFEST_VERSION, "managed_paths": {}}


def load_manifest(path: Path) -> Dict[str, Any]:
    if path.is_symlink():
        raise InstallStateError("invalid manifest: manifest path is a symlink")
    if not path.exists():
        return empty_manifest()
    try:
        with path.open(encoding="utf-8") as stream:
            data = json.load(stream)
    except (OSError, json.JSONDecodeError) as error:
        raise InstallStateError("invalid manifest: {}".format(error)) from error

    if not isinstance(data, dict) or data.get("version") != MANIFEST_VERSION:
        raise InstallStateError("invalid manifest: unsupported or missing version")
    managed_paths = data.get("managed_paths")
    if not isinstance(managed_paths, dict):
        raise InstallStateError("invalid manifest: managed_paths must be an object")
    for managed_path, entry in managed_paths.items():
        if (
            not isinstance(managed_path, str)
            or not isinstance(entry, dict)
            or entry.get("kind") != "symlink"
            or not isinstance(entry.get("target"), str)
        ):
            raise InstallStateError("invalid manifest: malformed managed path entry")
    managed_files = data.get("managed_files", {})
    if not isinstance(managed_files, dict):
        raise InstallStateError("invalid manifest: managed_files must be an object")
    for managed_path, entry in managed_files.items():
        if (
            not isinstance(managed_path, str)
            or not isinstance(entry, dict)
            or entry.get("kind") != "version-marker"
            or not isinstance(entry.get("version"), str)
            or VERSION_PATTERN.fullmatch(entry["version"]) is None
        ):
            raise InstallStateError("invalid manifest: malformed managed file entry")
    return data


def write_json_atomic(path: Path, data: Dict[str, Any]) -> None:
    """Write JSON through a same-directory temporary file and atomic replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=".{}.".format(path.name),
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(str(temporary_path), str(path))
        fsync_directory(path.parent)
    except BaseException:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass
        raise


def fsync_directory(path: Path) -> None:
    """Best-effort directory sync so an atomic rename survives power loss."""
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    try:
        descriptor = os.open(str(path), flags)
    except OSError:
        return
    try:
        try:
            os.fsync(descriptor)
        except OSError:
            pass
    finally:
        os.close(descriptor)


def write_bytes_atomic(
    path: Path,
    content: bytes,
    mode: int,
    expected_original: Any = _UNSET,
    expected_identity: Optional[os.stat_result] = None,
) -> None:
    """Safely replace one regular file after an optimistic content recheck."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise InstallStateError("collision: managed file path is a symlink: {}".format(path))
    descriptor, temporary_name = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=".{}.".format(path.name),
    )
    temporary_path = Path(temporary_name)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if expected_original is None:
            if os.path.lexists(str(path)):
                raise InstallStateError(
                    "managed file changed while it was being updated: {}".format(path)
                )
        elif expected_original is not _UNSET:
            current_identity = path.lstat()
            identity_changed = (
                expected_identity is not None
                and (
                    current_identity.st_dev != expected_identity.st_dev
                    or current_identity.st_ino != expected_identity.st_ino
                )
            )
            if (
                path.is_symlink()
                or not stat.S_ISREG(current_identity.st_mode)
                or identity_changed
                or path.read_bytes() != expected_original
            ):
                raise InstallStateError(
                    "managed file changed while it was being updated: {}".format(path)
                )
        elif path.is_symlink():
            raise InstallStateError(
                "collision: managed file path changed to a symlink: {}".format(path)
            )
        os.replace(str(temporary_path), str(path))
        fsync_directory(path.parent)
    except BaseException:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass
        raise


def path_matches_snapshot(
    path: Path,
    identity: os.stat_result,
    raw_target: Optional[str] = None,
    content: Optional[bytes] = None,
) -> bool:
    """Return whether a directory entry is still the exact observed object."""
    if not os.path.lexists(str(path)):
        return False
    current_identity = path.lstat()
    if (
        current_identity.st_dev != identity.st_dev
        or current_identity.st_ino != identity.st_ino
    ):
        return False
    if raw_target is not None:
        return path.is_symlink() and os.readlink(str(path)) == raw_target
    if content is not None:
        return (
            stat.S_ISREG(current_identity.st_mode)
            and path.read_bytes() == content
        )
    return False


def reserve_quarantine(path: Path) -> Path:
    """Reserve an unpredictable same-directory path for an atomic rename."""
    descriptor, quarantine_name = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=".{}.tgd-quarantine.".format(path.name),
    )
    os.close(descriptor)
    return Path(quarantine_name)


def restore_quarantined_path(quarantine: Path, path: Path) -> None:
    """Restore a quarantined link/file without overwriting a concurrent path."""
    if not os.path.lexists(str(quarantine)):
        return
    metadata = quarantine.lstat()
    if not (
        stat.S_ISREG(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
    ):
        raise InstallStateError(
            "unexpected path was preserved at quarantine: {}".format(
                quarantine
            )
        )
    try:
        os.link(
            str(quarantine),
            str(path),
            follow_symlinks=False,
        )
    except FileExistsError as error:
        raise InstallStateError(
            "path changed concurrently; prior data was preserved at {}".format(
                quarantine
            )
        ) from error
    except OSError as error:
        raise InstallStateError(
            "could not restore quarantined path; data was preserved at {}".format(
                quarantine
            )
        ) from error
    restored_identity = path.lstat()
    if (
        restored_identity.st_dev != metadata.st_dev
        or restored_identity.st_ino != metadata.st_ino
    ):
        raise InstallStateError(
            "path changed concurrently; prior data was preserved at {}".format(
                quarantine
            )
        )
    quarantine.unlink()
    fsync_directory(path.parent)


def quarantine_observed_path(
    path: Path,
    identity: os.stat_result,
    raw_target: Optional[str] = None,
    content: Optional[bytes] = None,
) -> Path:
    """Atomically move an observed entry aside and prove what was moved."""
    quarantine = reserve_quarantine(path)
    try:
        os.replace(str(path), str(quarantine))
    except BaseException:
        try:
            quarantine.unlink()
        except FileNotFoundError:
            pass
        raise

    if not path_matches_snapshot(
        quarantine,
        identity,
        raw_target=raw_target,
        content=content,
    ):
        restore_quarantined_path(quarantine, path)
        raise InstallStateError(
            "managed path changed while it was being updated: {}".format(path)
        )
    return quarantine


def discard_quarantined_path(
    quarantine: Path,
    identity: os.stat_result,
    raw_target: Optional[str] = None,
    content: Optional[bytes] = None,
) -> None:
    """Delete only the unchanged object held at an unpredictable path."""
    if not path_matches_snapshot(
        quarantine,
        identity,
        raw_target=raw_target,
        content=content,
    ):
        raise InstallStateError(
            "quarantined data changed and was preserved at {}".format(quarantine)
        )
    quarantine.unlink()
    fsync_directory(quarantine.parent)


def quarantine_and_remove_symlink(
    path: Path,
    expected_target: Path,
    expected_identity: Optional[os.stat_result] = None,
) -> bool:
    """Remove an exact symlink without deleting a swapped-in directory entry."""
    if not os.path.lexists(str(path)):
        return False
    if not path.is_symlink() or symlink_target(path) != expected_target:
        raise InstallStateError(
            "symlink does not match the expected target: {}".format(path)
        )
    identity = path.lstat()
    if expected_identity is not None and (
        identity.st_dev != expected_identity.st_dev
        or identity.st_ino != expected_identity.st_ino
    ):
        raise InstallStateError(
            "managed symlink changed while it was being updated: {}".format(path)
        )
    raw_target = os.readlink(str(path))
    quarantine = quarantine_observed_path(
        path,
        identity,
        raw_target=raw_target,
    )
    try:
        discard_quarantined_path(
            quarantine,
            identity,
            raw_target=raw_target,
        )
    except BaseException as error:
        try:
            restore_quarantined_path(quarantine, path)
        except InstallStateError as rollback_error:
            raise rollback_error from error
        raise
    return True


def quarantine_and_remove_file(
    path: Path,
    expected_content: bytes,
    expected_identity: Optional[os.stat_result] = None,
) -> bool:
    """Remove an exact regular file without deleting a swapped-in entry."""
    if not os.path.lexists(str(path)):
        return False
    identity = path.lstat()
    if (
        not stat.S_ISREG(identity.st_mode)
        or path.read_bytes() != expected_content
        or (
            expected_identity is not None
            and (
                identity.st_dev != expected_identity.st_dev
                or identity.st_ino != expected_identity.st_ino
            )
        )
    ):
        raise InstallStateError(
            "managed file changed while it was being updated: {}".format(path)
        )
    quarantine = quarantine_observed_path(
        path,
        identity,
        content=expected_content,
    )
    try:
        discard_quarantined_path(
            quarantine,
            identity,
            content=expected_content,
        )
    except BaseException as error:
        try:
            restore_quarantined_path(quarantine, path)
        except InstallStateError as rollback_error:
            raise rollback_error from error
        raise
    return True


def entry_for(manifest: Dict[str, Any], path: Path) -> Optional[Dict[str, str]]:
    entry = manifest["managed_paths"].get(str(path))
    if entry is None:
        return None
    return entry


def _link_path_unlocked(
    manifest_path: Path,
    path: Path,
    target: Path,
    legacy_targets: Iterable[Path],
    legacy_file_sha256s: Iterable[str] = (),
) -> None:
    if not target.exists():
        raise InstallStateError("target does not exist: {}".format(target))

    manifest = load_manifest(manifest_path)
    entry = entry_for(manifest, path)
    legacy_target_set = set(legacy_targets)
    legacy_file_hashes = set()
    for value in legacy_file_sha256s:
        normalized_hash = value.lower()
        if re.fullmatch(r"[0-9a-f]{64}", normalized_hash) is None:
            raise InstallStateError(
                "invalid legacy file SHA-256 fingerprint: {}".format(value)
            )
        legacy_file_hashes.add(normalized_hash)
    previous_raw_target = None
    previous_content = None
    previous_identity = None
    previous_quarantine = None
    written_identity = None
    manifest_committed = False

    if os.path.lexists(str(path)):
        if not path.is_symlink():
            metadata = path.stat()
            if not stat.S_ISREG(metadata.st_mode):
                raise InstallStateError(
                    "collision: path exists and is not a symlink: {}".format(path)
                )
            previous_content = path.read_bytes()
            previous_identity = path.lstat()
            content_hash = hashlib.sha256(previous_content).hexdigest()
            if entry is not None or content_hash not in legacy_file_hashes:
                raise InstallStateError(
                    "collision: path exists and is not a symlink: {}".format(path)
                )
        else:
            previous_raw_target = os.readlink(str(path))
            previous_identity = path.lstat()
            current_target = symlink_target(path)
            if entry is not None:
                recorded_target = normalize_path(entry["target"])
                if (
                    current_target != recorded_target
                    and current_target not in legacy_target_set
                ):
                    raise InstallStateError(
                        "managed symlink changed since it was recorded: {}".format(
                            path
                        )
                    )
            elif current_target not in legacy_target_set:
                raise InstallStateError(
                    "collision: foreign symlink exists: {}".format(path)
                )

    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if previous_identity is not None:
            previous_quarantine = quarantine_observed_path(
                path,
                previous_identity,
                raw_target=previous_raw_target,
                content=previous_content,
            )
        os.symlink(str(target), str(path))
        written_identity = path.lstat()
        manifest["managed_paths"][str(path)] = {
            "kind": "symlink",
            "target": str(target),
        }
        write_json_atomic(manifest_path, manifest)
        manifest_committed = True
        if previous_quarantine is not None:
            try:
                discard_quarantined_path(
                    previous_quarantine,
                    previous_identity,
                    raw_target=previous_raw_target,
                    content=previous_content,
                )
            except BaseException as cleanup_error:
                raise InstallStateError(
                    "managed path update committed; prior data was preserved at "
                    "{}".format(previous_quarantine)
                ) from cleanup_error
    except BaseException as error:
        if manifest_committed:
            raise
        try:
            if written_identity is not None:
                quarantine_and_remove_symlink(
                    path,
                    target,
                    written_identity,
                )
            if previous_quarantine is not None:
                restore_quarantined_path(previous_quarantine, path)
        except InstallStateError as rollback_error:
            raise rollback_error from error
        except OSError as rollback_error:
            raise InstallStateError(
                "could not roll back managed path update: {}".format(path)
            ) from rollback_error
        raise


def link_path(
    manifest_path: Path,
    path: Path,
    target: Path,
    legacy_targets: Iterable[Path],
    legacy_file_sha256s: Iterable[str] = (),
) -> None:
    with manifest_lock(manifest_path):
        _link_path_unlocked(
            manifest_path,
            path,
            target,
            legacy_targets,
            legacy_file_sha256s,
        )


def _remove_path_unlocked(manifest_path: Path, path: Path) -> None:
    manifest = load_manifest(manifest_path)
    entry = entry_for(manifest, path)
    if entry is None:
        raise InstallStateError("path is not managed: {}".format(path))

    if not os.path.lexists(str(path)):
        del manifest["managed_paths"][str(path)]
        write_json_atomic(manifest_path, manifest)
        return
    if not path.is_symlink():
        raise InstallStateError("managed path changed since it was recorded: {}".format(path))

    recorded_target = normalize_path(entry["target"])
    if symlink_target(path) != recorded_target:
        raise InstallStateError("managed symlink changed since it was recorded: {}".format(path))

    identity = path.lstat()
    previous_raw_target = os.readlink(str(path))
    quarantine = quarantine_observed_path(
        path,
        identity,
        raw_target=previous_raw_target,
    )
    del manifest["managed_paths"][str(path)]
    try:
        write_json_atomic(manifest_path, manifest)
    except BaseException as error:
        try:
            restore_quarantined_path(quarantine, path)
        except InstallStateError as rollback_error:
            raise rollback_error from error
        raise
    try:
        discard_quarantined_path(
            quarantine,
            identity,
            raw_target=previous_raw_target,
        )
    except BaseException as cleanup_error:
        try:
            if not path_matches_snapshot(
                quarantine,
                identity,
                raw_target=previous_raw_target,
            ):
                raise InstallStateError(
                    "managed symlink changed in quarantine and was preserved at "
                    "{}".format(quarantine)
                )
            restore_quarantined_path(quarantine, path)
            if not path_matches_snapshot(
                path,
                identity,
                raw_target=previous_raw_target,
            ):
                raise InstallStateError(
                    "managed symlink could not be restored safely: {}".format(
                        path
                    )
                )
            restored_manifest = dict(manifest)
            restored_paths = dict(manifest["managed_paths"])
            restored_paths[str(path)] = entry
            restored_manifest["managed_paths"] = restored_paths
            write_json_atomic(manifest_path, restored_manifest)
        except BaseException as rollback_error:
            raise InstallStateError(
                "managed path removal cleanup failed and recovery was incomplete; "
                "inspect {} and {}".format(path, quarantine)
            ) from rollback_error
        raise InstallStateError(
            "managed path removal failed; path and ownership were restored: "
            "{}".format(path)
        ) from cleanup_error


def remove_path(manifest_path: Path, path: Path) -> None:
    with manifest_lock(manifest_path):
        _remove_path_unlocked(manifest_path, path)


def _remove_all_unlocked(manifest_path: Path) -> Dict[str, int]:
    manifest = load_manifest(manifest_path)
    removed = 0
    kept = 0
    failed_paths: Dict[str, Any] = {}
    failed_files: Dict[str, Any] = {}
    for raw_path, entry in sorted(manifest["managed_paths"].items()):
        path = normalize_path(raw_path)
        recorded_target = normalize_path(entry["target"])
        if path.is_symlink() and symlink_target(path) == recorded_target:
            try:
                quarantine_and_remove_symlink(path, recorded_target)
                removed += 1
            except (InstallStateError, OSError):
                kept += 1
                failed_paths[raw_path] = entry
        else:
            kept += 1

    for raw_path, entry in sorted(manifest.get("managed_files", {}).items()):
        path = normalize_path(raw_path)
        recorded_content = marker_content(entry["version"])
        if (
            path.is_file()
            and not path.is_symlink()
            and path.read_bytes() == recorded_content
        ):
            try:
                quarantine_and_remove_file(path, recorded_content)
                removed += 1
            except (InstallStateError, OSError):
                kept += 1
                failed_files[raw_path] = entry
        else:
            kept += 1

    if failed_paths or failed_files:
        manifest["managed_paths"] = failed_paths
        if failed_files:
            manifest["managed_files"] = failed_files
        else:
            manifest.pop("managed_files", None)
        write_json_atomic(manifest_path, manifest)
        raise InstallStateError(
            "could not remove {} managed item(s); ownership was preserved "
            "for retry".format(len(failed_paths) + len(failed_files))
        )

    try:
        manifest_path.unlink()
    except FileNotFoundError:
        pass
    else:
        fsync_directory(manifest_path.parent)
    return {"removed": removed, "kept": kept}


def remove_all(manifest_path: Path) -> Dict[str, int]:
    with manifest_lock(manifest_path):
        return _remove_all_unlocked(manifest_path)


def verify_path(manifest_path: Path, path: Path, expected_target: Path) -> None:
    manifest = load_manifest(manifest_path)
    entry = entry_for(manifest, path)
    if entry is None:
        raise InstallStateError("path is not managed: {}".format(path))
    recorded_target = normalize_path(entry["target"])
    if recorded_target != expected_target:
        raise InstallStateError(
            "target mismatch: manifest records {}, expected {}".format(
                recorded_target,
                expected_target,
            )
        )
    if not path.is_symlink():
        raise InstallStateError("managed path is not a symlink: {}".format(path))
    if symlink_target(path) != expected_target:
        raise InstallStateError("target mismatch: symlink does not match manifest")
    if not expected_target.exists():
        raise InstallStateError("target does not exist: {}".format(expected_target))


def marker_content(version: str) -> bytes:
    if VERSION_PATTERN.fullmatch(version) is None:
        raise InstallStateError("invalid version marker value: {}".format(version))
    return (version + "\n").encode("utf-8")


def check_marker(
    manifest: Dict[str, Any],
    path: Path,
    legacy_versions: Iterable[str],
    recovery_versions: Iterable[str] = (),
) -> None:
    managed_files = manifest.get("managed_files", {})
    entry = managed_files.get(str(path))
    legacy_contents = {marker_content(version) for version in legacy_versions}
    recovery_contents = {
        marker_content(version) for version in recovery_versions
    }

    if not os.path.lexists(str(path)):
        return
    if path.is_symlink():
        raise InstallStateError("collision: version marker path is a symlink: {}".format(path))
    metadata = path.stat()
    if not stat.S_ISREG(metadata.st_mode):
        raise InstallStateError(
            "collision: version marker path is not a regular file: {}".format(path)
        )
    current = path.read_bytes()

    if entry is not None:
        recorded = marker_content(entry["version"])
        if current != recorded and current not in recovery_contents:
            raise InstallStateError(
                "managed version marker changed since it was recorded: {}".format(path)
            )
    elif current not in legacy_contents:
        raise InstallStateError("collision: foreign version marker exists: {}".format(path))


def _write_marker_unlocked(
    manifest_path: Path,
    path: Path,
    version: str,
    legacy_versions: Iterable[str],
) -> None:
    content = marker_content(version)
    manifest = load_manifest(manifest_path)
    check_marker(manifest, path, legacy_versions, (version,))

    previous_content: Optional[bytes] = None
    previous_identity: Optional[os.stat_result] = None
    previous_mode = 0o600
    if os.path.lexists(str(path)):
        previous_identity = path.lstat()
        if not stat.S_ISREG(previous_identity.st_mode):
            raise InstallStateError(
                "managed version marker changed while it was being updated: {}".format(
                    path
                )
            )
        previous_content = path.read_bytes()
        previous_mode = stat.S_IMODE(previous_identity.st_mode)

    write_bytes_atomic(
        path,
        content,
        previous_mode,
        previous_content,
        previous_identity,
    )
    written_identity = path.lstat()
    managed_files = dict(manifest.get("managed_files", {}))
    managed_files[str(path)] = {
        "kind": "version-marker",
        "version": version,
    }
    manifest["managed_files"] = managed_files
    try:
        write_json_atomic(manifest_path, manifest)
    except BaseException as error:
        written_quarantine = None
        try:
            if os.path.lexists(str(path)):
                written_quarantine = quarantine_observed_path(
                    path,
                    written_identity,
                    content=content,
                )
            if previous_content is not None:
                write_bytes_atomic(
                    path,
                    previous_content,
                    previous_mode,
                    None,
                )
            if written_quarantine is not None:
                discard_quarantined_path(
                    written_quarantine,
                    written_identity,
                    content=content,
                )
        except BaseException as rollback_error:
            if (
                written_quarantine is not None
                and os.path.lexists(str(written_quarantine))
                and not os.path.lexists(str(path))
            ):
                try:
                    restore_quarantined_path(written_quarantine, path)
                except BaseException:
                    pass
            if isinstance(rollback_error, InstallStateError):
                raise rollback_error from error
            raise InstallStateError(
                "could not roll back version marker update: {}".format(path)
            ) from rollback_error
        raise


def write_marker(
    manifest_path: Path,
    path: Path,
    version: str,
    legacy_versions: Iterable[str],
) -> None:
    with manifest_lock(manifest_path):
        _write_marker_unlocked(manifest_path, path, version, legacy_versions)


def verify_marker_collision(
    manifest_path: Path,
    path: Path,
    legacy_versions: Iterable[str],
    recovery_versions: Iterable[str],
) -> None:
    check_marker(
        load_manifest(manifest_path),
        path,
        legacy_versions,
        recovery_versions,
    )


def remove_exact_symlink(
    manifest_path: Path,
    path: Path,
    expected_target: Path,
) -> bool:
    """Remove one exact retired symlink under the installer lock."""
    with manifest_lock(manifest_path):
        return quarantine_and_remove_symlink(path, expected_target)


def remove_legacy_suffix(
    manifest_path: Path,
    path: Path,
    suffix_size: int,
    suffix_sha256: str,
) -> bool:
    """Remove one exact historical generated suffix from a regular file."""
    normalized_hash = suffix_sha256.lower()
    if suffix_size <= 0 or re.fullmatch(r"[0-9a-f]{64}", normalized_hash) is None:
        raise InstallStateError("invalid legacy suffix fingerprint")

    with manifest_lock(manifest_path):
        if not os.path.lexists(str(path)) or path.is_symlink():
            return False
        identity = path.lstat()
        if not stat.S_ISREG(identity.st_mode):
            return False
        original = path.read_bytes()
        if len(original) < suffix_size:
            return False
        suffix = original[-suffix_size:]
        if hashlib.sha256(suffix).hexdigest() != normalized_hash:
            return False

        prefix = original[:-suffix_size]
        if prefix:
            write_bytes_atomic(
                path,
                prefix,
                stat.S_IMODE(identity.st_mode),
                original,
                identity,
            )
        else:
            quarantine_and_remove_file(
                path,
                original,
                identity,
            )
        return True


def add_manifest_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--manifest", required=True, help="Ownership manifest path")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    link_parser = commands.add_parser("link", help="Create or replace a managed symlink")
    add_manifest_argument(link_parser)
    link_parser.add_argument("--path", required=True, help="Managed symlink path")
    link_parser.add_argument("--target", required=True, help="Expected symlink target")
    link_parser.add_argument(
        "--legacy-target",
        action="append",
        default=[],
        help="Exact legacy target that may be replaced; repeatable",
    )
    link_parser.add_argument(
        "--legacy-file-sha256",
        action="append",
        default=[],
        help="Exact generated legacy-file fingerprint that may be replaced",
    )

    remove_parser = commands.add_parser("remove", help="Remove one managed symlink")
    add_manifest_argument(remove_parser)
    remove_parser.add_argument("--path", required=True, help="Managed symlink path")

    remove_all_parser = commands.add_parser(
        "remove-all",
        help="Remove all matching managed symlinks and clear the manifest",
    )
    add_manifest_argument(remove_all_parser)

    verify_parser = commands.add_parser("verify", help="Verify a managed symlink")
    add_manifest_argument(verify_parser)
    verify_parser.add_argument("--path", required=True, help="Managed symlink path")
    verify_parser.add_argument("--target", required=True, help="Expected symlink target")

    exact_symlink_parser = commands.add_parser(
        "remove-exact-symlink",
        help="Safely remove an exact retired symlink",
    )
    add_manifest_argument(exact_symlink_parser)
    exact_symlink_parser.add_argument("--path", required=True)
    exact_symlink_parser.add_argument("--target", required=True)

    suffix_parser = commands.add_parser(
        "remove-legacy-suffix",
        help="Remove an exact historical generated file suffix",
    )
    add_manifest_argument(suffix_parser)
    suffix_parser.add_argument("--path", required=True)
    suffix_parser.add_argument("--size", required=True, type=int)
    suffix_parser.add_argument("--sha256", required=True)

    check_marker_parser = commands.add_parser(
        "check-marker",
        help="Preflight a managed version marker without changing it",
    )
    add_manifest_argument(check_marker_parser)
    check_marker_parser.add_argument("--path", required=True)
    check_marker_parser.add_argument(
        "--legacy-version",
        action="append",
        default=[],
        help="Exact unrecorded legacy version that may be adopted; repeatable",
    )
    check_marker_parser.add_argument(
        "--recovery-version",
        action="append",
        default=[],
        help="Exact requested version accepted after an interrupted managed update",
    )

    write_marker_parser = commands.add_parser(
        "write-marker",
        help="Atomically write and record the managed version marker",
    )
    add_manifest_argument(write_marker_parser)
    write_marker_parser.add_argument("--path", required=True)
    write_marker_parser.add_argument("--version", required=True)
    write_marker_parser.add_argument(
        "--legacy-version",
        action="append",
        default=[],
        help="Exact unrecorded legacy version that may be adopted; repeatable",
    )
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    manifest_path = normalize_path(args.manifest)
    try:
        if args.command == "link":
            path = normalize_path(args.path)
            target = normalize_path(args.target)
            legacy_targets = [normalize_path(value) for value in args.legacy_target]
            link_path(
                manifest_path,
                path,
                target,
                legacy_targets,
                args.legacy_file_sha256,
            )
            print("linked path={} target={}".format(path, target))
        elif args.command == "remove":
            path = normalize_path(args.path)
            remove_path(manifest_path, path)
            print("removed path={}".format(path))
        elif args.command == "remove-all":
            result = remove_all(manifest_path)
            print("removed={removed} kept={kept}".format(**result))
        elif args.command == "verify":
            path = normalize_path(args.path)
            target = normalize_path(args.target)
            verify_path(manifest_path, path, target)
            print("verified path={} target={}".format(path, target))
        elif args.command == "remove-exact-symlink":
            path = normalize_path(args.path)
            target = normalize_path(args.target)
            removed = remove_exact_symlink(manifest_path, path, target)
            print(
                "{} path={}".format(
                    "removed" if removed else "absent",
                    path,
                )
            )
        elif args.command == "remove-legacy-suffix":
            path = normalize_path(args.path)
            removed = remove_legacy_suffix(
                manifest_path,
                path,
                args.size,
                args.sha256,
            )
            print(
                "{} legacy suffix path={}".format(
                    "removed" if removed else "preserved",
                    path,
                )
            )
        elif args.command == "check-marker":
            path = normalize_path(args.path)
            verify_marker_collision(
                manifest_path,
                path,
                args.legacy_version,
                args.recovery_version,
            )
            print("verified marker path={}".format(path))
        elif args.command == "write-marker":
            path = normalize_path(args.path)
            write_marker(
                manifest_path,
                path,
                args.version,
                args.legacy_version,
            )
            print("wrote marker path={} version={}".format(path, args.version))
        else:
            raise InstallStateError("unknown command: {}".format(args.command))
    except (InstallStateError, OSError) as error:
        print("install-state: {}".format(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
