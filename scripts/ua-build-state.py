#!/usr/bin/env python3
"""Track whether bundled Understand-Anything build artifacts are current.

The stamp lives outside the vendored checkout.  It binds the canonical UA root
to a deterministic fingerprint of package-manager metadata and build inputs.
Generated directories such as node_modules and dist are deliberately excluded.

Python 3.9+ stdlib only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from typing import Iterable, Iterator, List, Sequence


SCHEMA_VERSION = 1
MODULE_MANIFEST = Path("node_modules/.modules.yaml")
CORE_OUTPUT = Path(
    "understand-anything-plugin/packages/core/dist/index.js"
)

FIXED_INPUTS = (
    Path(".npmrc"),
    Path("package.json"),
    Path("pnpm-lock.yaml"),
    Path("pnpm-workspace.yaml"),
    Path("tsconfig.json"),
    Path("vitest.config.ts"),
    Path("eslint.config.mjs"),
    Path("understand-anything-plugin/package.json"),
    Path("understand-anything-plugin/pnpm-lock.yaml"),
    Path("understand-anything-plugin/pnpm-workspace.yaml"),
    Path("understand-anything-plugin/tsconfig.json"),
    Path("understand-anything-plugin/vitest.config.ts"),
    Path("homepage/package.json"),
    Path("homepage/astro.config.mjs"),
    Path("homepage/tsconfig.json"),
)

SOURCE_TREES = (
    Path("understand-anything-plugin/src"),
    Path("understand-anything-plugin/packages"),
    Path("homepage/src"),
    Path("homepage/public"),
)

IGNORED_DIRECTORY_NAMES = frozenset(
    {
        ".astro",
        ".git",
        ".turbo",
        "__pycache__",
        "coverage",
        "dist",
        "node_modules",
    }
)
IGNORED_RELATIVE_PREFIXES = (Path("homepage/public/demo"),)
IGNORED_FILE_NAMES = frozenset({".DS_Store"})
IGNORED_FILE_SUFFIXES = (".pyc", ".pyo", ".tsbuildinfo")


class BuildStateError(RuntimeError):
    """A malformed root, input, or stamp that cannot be handled safely."""


def canonical_root(path: Path) -> Path:
    root = path.expanduser().resolve()
    if not root.is_dir():
        raise BuildStateError("UA root is not a directory: {}".format(root))
    return root


def absolute_stamp_path(path: Path) -> Path:
    """Normalize a stamp path without following its final path component."""
    return Path(os.path.abspath(os.path.expanduser(str(path))))


def is_ignored_relative(path: Path) -> bool:
    if path.name in IGNORED_FILE_NAMES:
        return True
    if path.name.endswith(IGNORED_FILE_SUFFIXES):
        return True
    return any(
        path == prefix or prefix in path.parents
        for prefix in IGNORED_RELATIVE_PREFIXES
    )


def walk_tree(root: Path, relative_tree: Path) -> Iterator[Path]:
    absolute_tree = root / relative_tree
    if not absolute_tree.exists() and not absolute_tree.is_symlink():
        return

    if absolute_tree.is_symlink():
        yield relative_tree
        return

    for directory, dirnames, filenames in os.walk(
        str(absolute_tree),
        followlinks=False,
    ):
        directory_path = Path(directory)
        relative_directory = directory_path.relative_to(root)
        kept_directories: List[str] = []
        for dirname in sorted(dirnames):
            relative = relative_directory / dirname
            absolute = directory_path / dirname
            if dirname in IGNORED_DIRECTORY_NAMES or is_ignored_relative(relative):
                continue
            if absolute.is_symlink():
                yield relative
                continue
            kept_directories.append(dirname)
        dirnames[:] = kept_directories

        for filename in sorted(filenames):
            relative = relative_directory / filename
            if not is_ignored_relative(relative):
                yield relative


def input_paths(root: Path) -> Iterable[Path]:
    candidates = {
        path
        for path in FIXED_INPUTS
        if (root / path).exists() or (root / path).is_symlink()
    }
    for source_tree in SOURCE_TREES:
        candidates.update(walk_tree(root, source_tree))
    return sorted(candidates, key=lambda path: path.as_posix())


def update_with_file(digest: "hashlib._Hash", root: Path, relative: Path) -> None:
    absolute = root / relative
    digest.update(relative.as_posix().encode("utf-8"))
    digest.update(b"\0")

    if absolute.is_symlink():
        digest.update(b"symlink\0")
        digest.update(os.readlink(str(absolute)).encode("utf-8"))
        digest.update(b"\0")
        return

    try:
        mode = absolute.lstat().st_mode
    except FileNotFoundError as error:
        raise BuildStateError(
            "UA input disappeared while fingerprinting: {}".format(relative)
        ) from error
    if not stat.S_ISREG(mode):
        raise BuildStateError(
            "UA build input is not a regular file: {}".format(relative)
        )

    digest.update(b"file\0")
    with absolute.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    digest.update(b"\0")


def fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    digest.update(b"tgd-ua-build-inputs-v1\0")
    for relative in input_paths(root):
        update_with_file(digest, root, relative)
    return digest.hexdigest()


def artifacts_present(root: Path) -> bool:
    return (root / MODULE_MANIFEST).is_file() and (root / CORE_OUTPUT).is_file()


def expected_state(root: Path) -> dict:
    return {
        "fingerprint": fingerprint(root),
        "schema": SCHEMA_VERSION,
        "ua_root": str(root),
    }


def read_state(stamp: Path) -> dict:
    try:
        mode = stamp.lstat().st_mode
    except FileNotFoundError:
        return {}
    if not stat.S_ISREG(mode):
        return {}
    try:
        value = json.loads(stamp.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def is_current(root: Path, stamp: Path) -> bool:
    if not artifacts_present(root):
        return False
    return read_state(stamp) == expected_state(root)


def fsync_directory(directory: Path) -> None:
    descriptor = os.open(str(directory), os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_state(root: Path, stamp: Path) -> None:
    if not artifacts_present(root):
        raise BuildStateError(
            "cannot stamp UA build state before required artifacts exist"
        )
    if stamp.is_symlink():
        raise BuildStateError(
            "refusing to replace symlinked state file: {}".format(stamp)
        )

    stamp.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(expected_state(root), indent=2, sort_keys=True) + "\n"
    file_descriptor = -1
    temporary_path = ""
    try:
        file_descriptor, temporary_path = tempfile.mkstemp(
            dir=str(stamp.parent),
            prefix=".{}.".format(stamp.name),
            text=True,
        )
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
            file_descriptor = -1
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, str(stamp))
        temporary_path = ""
        fsync_directory(stamp.parent)
    finally:
        if file_descriptor >= 0:
            os.close(file_descriptor)
        if temporary_path:
            try:
                os.unlink(temporary_path)
            except FileNotFoundError:
                pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("fingerprint", "is-current", "write"),
    )
    parser.add_argument("--ua-root", required=True, type=Path)
    parser.add_argument("--stamp", required=True, type=Path)
    return parser


def main(argv: Sequence[str] = ()) -> int:
    args = build_parser().parse_args(list(argv) if argv else None)
    try:
        root = canonical_root(args.ua_root)
        stamp = absolute_stamp_path(args.stamp)
        if args.command == "fingerprint":
            print(fingerprint(root))
            return 0
        if args.command == "is-current":
            return 0 if is_current(root, stamp) else 1
        write_state(root, stamp)
        print(fingerprint(root))
        return 0
    except BuildStateError as error:
        print("ua-build-state: {}".format(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
