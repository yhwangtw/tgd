#!/usr/bin/env python3
"""Safely manage symlinks owned by the tGD installer."""

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Dict, Iterable, Optional


MANIFEST_VERSION = 1


class InstallStateError(Exception):
    """A safe, user-facing install-state failure."""


def normalize_path(value: str) -> Path:
    """Expand HOME and return a normalized absolute path without resolving links."""
    return Path(os.path.abspath(os.path.expanduser(value)))


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
    except BaseException:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass
        raise


def entry_for(manifest: Dict[str, Any], path: Path) -> Optional[Dict[str, str]]:
    entry = manifest["managed_paths"].get(str(path))
    if entry is None:
        return None
    return entry


def restore_symlink(path: Path, raw_target: Optional[str]) -> None:
    if path.is_symlink():
        path.unlink()
    if raw_target is not None and not os.path.lexists(str(path)):
        os.symlink(raw_target, str(path))


def link_path(
    manifest_path: Path,
    path: Path,
    target: Path,
    legacy_targets: Iterable[Path],
) -> None:
    if not target.exists():
        raise InstallStateError("target does not exist: {}".format(target))

    manifest = load_manifest(manifest_path)
    entry = entry_for(manifest, path)
    legacy_target_set = set(legacy_targets)
    previous_raw_target = None

    if os.path.lexists(str(path)):
        if not path.is_symlink():
            raise InstallStateError("collision: path exists and is not a symlink: {}".format(path))
        previous_raw_target = os.readlink(str(path))
        current_target = symlink_target(path)
        if entry is not None:
            recorded_target = normalize_path(entry["target"])
            if current_target != recorded_target and current_target not in legacy_target_set:
                raise InstallStateError(
                    "managed symlink changed since it was recorded: {}".format(path)
                )
        elif current_target not in legacy_target_set:
            raise InstallStateError("collision: foreign symlink exists: {}".format(path))

    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if path.is_symlink():
            path.unlink()
        os.symlink(str(target), str(path))
        manifest["managed_paths"][str(path)] = {
            "kind": "symlink",
            "target": str(target),
        }
        write_json_atomic(manifest_path, manifest)
    except BaseException:
        restore_symlink(path, previous_raw_target)
        raise


def remove_path(manifest_path: Path, path: Path) -> None:
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

    previous_raw_target = os.readlink(str(path))
    path.unlink()
    del manifest["managed_paths"][str(path)]
    try:
        write_json_atomic(manifest_path, manifest)
    except BaseException:
        restore_symlink(path, previous_raw_target)
        raise


def remove_all(manifest_path: Path) -> Dict[str, int]:
    manifest = load_manifest(manifest_path)
    removed = 0
    kept = 0
    for raw_path, entry in sorted(manifest["managed_paths"].items()):
        path = normalize_path(raw_path)
        recorded_target = normalize_path(entry["target"])
        if path.is_symlink() and symlink_target(path) == recorded_target:
            try:
                path.unlink()
                removed += 1
            except OSError:
                kept += 1
        else:
            kept += 1

    try:
        manifest_path.unlink()
    except FileNotFoundError:
        pass
    return {"removed": removed, "kept": kept}


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
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    manifest_path = normalize_path(args.manifest)
    try:
        if args.command == "link":
            path = normalize_path(args.path)
            target = normalize_path(args.target)
            legacy_targets = [normalize_path(value) for value in args.legacy_target]
            link_path(manifest_path, path, target, legacy_targets)
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
        else:
            raise InstallStateError("unknown command: {}".format(args.command))
    except (InstallStateError, OSError) as error:
        print("install-state: {}".format(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
