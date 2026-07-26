#!/usr/bin/env python3
"""Install or remove one canonical tGD hook without touching foreign hooks."""

import argparse
import json
import os
import shlex
import stat
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Optional, Sequence, Tuple


PLATFORM_SCRIPTS = {
    "claude": Path("hooks/session-start.sh"),
    "codex": Path("hooks/codex/session-start.sh"),
    "gemini": Path("hooks/gemini/session-start.sh"),
}
TGD_HOOK_NAME = "tgd-session-start"
LEGACY_ROOT_MARKERS = ("${CLAUDE_PLUGIN_ROOT}", "${TGD_DIR}")
TGD_SCRIPT_SUFFIXES = (
    "/hooks/session-start.sh",
    "/hooks/codex/session-start.sh",
    "/hooks/gemini/session-start.sh",
)


class HookConfigError(ValueError):
    """Raised when a hook config cannot be changed safely."""


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Atomically install or remove the canonical tGD agent hook."
    )
    parser.add_argument("action", choices=("install", "remove"))
    parser.add_argument(
        "--platform",
        required=True,
        choices=tuple(PLATFORM_SCRIPTS),
    )
    parser.add_argument(
        "--repo-root",
        required=True,
        type=Path,
        help="Path to the checked-out tGD repository.",
    )
    parser.add_argument(
        "--destination",
        required=True,
        type=Path,
        help="Agent settings/hooks JSON file to update.",
    )
    return parser.parse_args(argv)


def _canonical_repo_root(path: Path) -> Path:
    try:
        resolved = path.expanduser().resolve(strict=True)
    except OSError as error:
        raise HookConfigError(f"repository root is not accessible: {path}") from error
    if not resolved.is_dir():
        raise HookConfigError(f"repository root is not a directory: {resolved}")
    return resolved


def _canonical_script(repo_root: Path, platform: str, require_file: bool) -> Path:
    candidate = repo_root / PLATFORM_SCRIPTS[platform]
    try:
        resolved = candidate.resolve(strict=require_file)
    except OSError as error:
        raise HookConfigError(f"hook script is not accessible: {candidate}") from error
    if require_file and not resolved.is_file():
        raise HookConfigError(f"hook script is not a regular file: {resolved}")
    try:
        resolved.relative_to(repo_root)
    except ValueError as error:
        raise HookConfigError(
            f"hook script escapes repository root: {candidate}"
        ) from error
    return resolved


def _all_canonical_scripts(repo_root: Path) -> Tuple[str, ...]:
    return tuple(
        str(_canonical_script(repo_root, platform, require_file=False))
        for platform in PLATFORM_SCRIPTS
    )


def _script_from_command(command: str) -> Optional[str]:
    try:
        words = shlex.split(command)
    except ValueError:
        return None
    if len(words) < 2 or Path(words[0]).name not in ("bash", "sh"):
        return None
    return words[1]


def _has_tgd_path_component(script: str) -> bool:
    normalized = script.replace("\\", "/")
    return any(part.casefold() == "tgd" for part in PurePosixPath(normalized).parts)


def _is_tgd_command(command: Any, repo_root: Path) -> bool:
    if not isinstance(command, str):
        return False
    script = _script_from_command(command)
    if script is None:
        return False
    if script in _all_canonical_scripts(repo_root):
        return True
    if any(marker in script for marker in LEGACY_ROOT_MARKERS):
        return any(script.endswith(suffix) for suffix in TGD_SCRIPT_SUFFIXES)
    return _has_tgd_path_component(script) and any(
        script.replace("\\", "/").endswith(suffix) for suffix in TGD_SCRIPT_SUFFIXES
    )


def _is_tgd_hook(value: Any, repo_root: Path) -> bool:
    if not isinstance(value, dict):
        return False
    if value.get("name") == TGD_HOOK_NAME:
        return True
    return _is_tgd_command(value.get("command"), repo_root)


def _clean_entry(value: Any, repo_root: Path) -> Tuple[Optional[Any], bool]:
    if not isinstance(value, dict):
        return value, False
    if _is_tgd_hook(value, repo_root):
        return None, True

    nested = value.get("hooks")
    if not isinstance(nested, list):
        return value, False

    cleaned_hooks = []
    changed = False
    for hook in nested:
        cleaned, removed = _clean_entry(hook, repo_root)
        changed = changed or removed
        if cleaned is not None:
            cleaned_hooks.append(cleaned)

    if not changed:
        return value, False
    if not cleaned_hooks:
        return None, True

    cleaned_value = dict(value)
    cleaned_value["hooks"] = cleaned_hooks
    return cleaned_value, True


def remove_tgd_hooks(
    config: Dict[str, Any], repo_root: Path
) -> Tuple[Dict[str, Any], bool]:
    hooks = config.get("hooks")
    if hooks is None:
        return config, False
    if not isinstance(hooks, dict):
        raise HookConfigError("top-level 'hooks' must be an object")

    cleaned_events: Dict[str, Any] = {}
    changed = False
    for event, entries in hooks.items():
        if not isinstance(entries, list):
            raise HookConfigError(f"hooks.{event} must be an array")
        cleaned_entries = []
        for entry in entries:
            cleaned, removed = _clean_entry(entry, repo_root)
            changed = changed or removed
            if cleaned is not None:
                cleaned_entries.append(cleaned)
        if cleaned_entries or not entries:
            cleaned_events[event] = cleaned_entries
        elif entries:
            changed = True

    if not changed:
        return config, False
    cleaned_config = dict(config)
    cleaned_config["hooks"] = cleaned_events
    return cleaned_config, True


def _canonical_entry(platform: str, script: Path) -> Dict[str, Any]:
    hook: Dict[str, Any] = {
        "type": "command",
        "command": "bash " + shlex.quote(str(script)),
    }
    entry: Dict[str, Any] = {"hooks": [hook]}
    if platform == "codex":
        entry["matcher"] = "startup|resume"
        hook["statusMessage"] = "Loading tGD meta-skill"
    elif platform == "gemini":
        entry["matcher"] = "*"
        hook["name"] = TGD_HOOK_NAME
    return entry


def install_tgd_hook(
    config: Dict[str, Any], repo_root: Path, platform: str
) -> Dict[str, Any]:
    cleaned, _ = remove_tgd_hooks(config, repo_root)
    hooks = cleaned.get("hooks")
    if hooks is None:
        hooks = {}
    if not isinstance(hooks, dict):
        raise HookConfigError("top-level 'hooks' must be an object")

    session_start = hooks.get("SessionStart")
    if session_start is None:
        session_start = []
    if not isinstance(session_start, list):
        raise HookConfigError("hooks.SessionStart must be an array")

    installed = dict(cleaned)
    installed_hooks = dict(hooks)
    installed_hooks["SessionStart"] = session_start + [
        _canonical_entry(
            platform,
            _canonical_script(repo_root, platform, require_file=True),
        )
    ]
    installed["hooks"] = installed_hooks
    return installed


def _load_destination(path: Path) -> Tuple[Dict[str, Any], int]:
    if path.is_symlink():
        raise HookConfigError(f"destination must not be a symlink: {path}")
    if not path.exists():
        return {}, 0o600

    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(str(path), flags)
    except OSError as error:
        raise HookConfigError(f"cannot safely open destination: {path}") from error

    try:
        file_stat = os.fstat(descriptor)
        if not stat.S_ISREG(file_stat.st_mode):
            raise HookConfigError(f"destination must be a regular file: {path}")
        with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
            descriptor = -1
            config = json.load(stream)
    finally:
        if descriptor >= 0:
            os.close(descriptor)

    if not isinstance(config, dict):
        raise HookConfigError("hook config root must be a JSON object")
    return config, stat.S_IMODE(file_stat.st_mode)


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    try:
        descriptor = os.open(str(path), flags)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_atomic(path: Path, config: Dict[str, Any], mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.parent.is_dir():
        raise HookConfigError(f"destination parent is not a directory: {path.parent}")
    if path.is_symlink():
        raise HookConfigError(f"destination must not be a symlink: {path}")

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    temporary_path = Path(temporary_name)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            descriptor = -1
            json.dump(config, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(str(temporary_path), str(path))
        _fsync_directory(path.parent)
    except Exception:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass
        raise


def run(args: argparse.Namespace) -> int:
    repo_root = _canonical_repo_root(args.repo_root)
    destination = args.destination.expanduser()

    if (
        args.action == "remove"
        and not destination.exists()
        and not destination.is_symlink()
    ):
        print(f"No {args.platform} hook config found; nothing to remove.")
        return 0

    config, mode = _load_destination(destination)
    if args.action == "install":
        updated = install_tgd_hook(config, repo_root, args.platform)
        action_text = "installed"
    else:
        updated, changed = remove_tgd_hooks(config, repo_root)
        if not changed:
            print(f"No tGD hooks found in {destination}; nothing to remove.")
            return 0
        action_text = "removed"

    if updated != config:
        _write_atomic(destination, updated, mode)
    print(f"tGD {args.platform} hook {action_text}: {destination}")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        return run(parse_args(argv))
    except (HookConfigError, json.JSONDecodeError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
