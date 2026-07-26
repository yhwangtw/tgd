#!/usr/bin/env python3
"""Install or remove one canonical tGD hook without touching foreign hooks."""

import argparse
from contextlib import contextmanager
import fcntl
import json
import os
import re
import shlex
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, Optional, Sequence, Tuple


PLATFORM_SCRIPTS = {
    "claude": Path("hooks/session-start.sh"),
    "codex": Path("hooks/codex/session-start.sh"),
    "gemini": Path("hooks/gemini/session-start.sh"),
}
TGD_HOOK_NAME = "tgd-session-start"
TGD_ROOT_PLACEHOLDERS = ("${TGD_DIR}",)
TGD_SCRIPT_SUFFIXES = (
    "/hooks/session-start.sh",
    "/hooks/codex/session-start.sh",
    "/hooks/gemini/session-start.sh",
)
HOOK_STATE_VERSION = 1


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
    parser.add_argument(
        "--state",
        type=Path,
        help=(
            "Optional ownership state file. Exact commands recorded here can be "
            "migrated after an older checkout has moved or been deleted."
        ),
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


def _normalized_absolute_path(path: Path) -> Path:
    return Path(os.path.abspath(str(path.expanduser())))


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
    if len(words) != 2 or Path(words[0]).name not in ("bash", "sh"):
        return None
    return words[1]


def _unquoted_absolute_script_from_command(command: str) -> Optional[str]:
    """Recover a historical unquoted script path only when spaces split it."""
    match = re.fullmatch(r"\s*(\S+)[ \t]+(.+?)\s*", command)
    if match is None or Path(match.group(1)).name not in ("bash", "sh"):
        return None

    script = match.group(2)
    if (
        script.startswith(("'", '"'))
        or not Path(script).is_absolute()
        or not any(character.isspace() for character in script)
    ):
        return None
    return script


def _is_historical_gemini_relative_command(command: Any) -> bool:
    if not isinstance(command, str):
        return False
    try:
        words = shlex.split(command)
    except ValueError:
        return False
    return (
        len(words) == 2
        and Path(words[0]).name == "bash"
        and words[1].replace("\\", "/") == "hooks/gemini/session-start.sh"
    )


def _is_recognized_tgd_checkout(path: Path) -> bool:
    return (
        (path / "setup.sh").is_file()
        and (path / "VERSION").is_file()
        and (
            (path / "skills" / "tgd-rules" / "SKILL.md").is_file()
            or (path / "skills" / "rules" / "SKILL.md").is_file()
        )
    )


def _is_recognized_legacy_script(script: str) -> bool:
    normalized = script.replace("\\", "/")
    for suffix in TGD_SCRIPT_SUFFIXES:
        if not normalized.endswith(suffix):
            continue
        root = normalized[: -len(suffix)]
        if any(root == marker for marker in TGD_ROOT_PLACEHOLDERS):
            return True
        if root and _is_recognized_tgd_checkout(Path(root).expanduser()):
            return True
    return False


def _is_tgd_command(
    command: Any,
    repo_root: Path,
    owned_commands: Iterable[str] = (),
) -> bool:
    if not isinstance(command, str):
        return False
    if command in owned_commands:
        return True
    script = _script_from_command(command)
    if script is not None:
        if script in _all_canonical_scripts(repo_root):
            return True
        if _is_recognized_legacy_script(script):
            return True

    historical_script = _unquoted_absolute_script_from_command(command)
    return (
        historical_script is not None
        and _is_recognized_legacy_script(historical_script)
    )


def _is_tgd_hook(
    value: Any,
    repo_root: Path,
    owned_commands: Iterable[str] = (),
) -> bool:
    if not isinstance(value, dict):
        return False
    command = value.get("command")
    if _is_tgd_command(command, repo_root, owned_commands):
        return True
    return (
        value.get("name") == TGD_HOOK_NAME
        and _is_historical_gemini_relative_command(command)
    )


def _clean_entry(
    value: Any,
    repo_root: Path,
    owned_commands: Iterable[str] = (),
) -> Tuple[Optional[Any], bool]:
    if not isinstance(value, dict):
        return value, False
    if _is_tgd_hook(value, repo_root, owned_commands):
        return None, True

    nested = value.get("hooks")
    if not isinstance(nested, list):
        return value, False

    cleaned_hooks = []
    changed = False
    for hook in nested:
        cleaned, removed = _clean_entry(hook, repo_root, owned_commands)
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
    config: Dict[str, Any],
    repo_root: Path,
    owned_commands: Iterable[str] = (),
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
            cleaned, removed = _clean_entry(entry, repo_root, owned_commands)
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
    command = _canonical_command(script)
    hook: Dict[str, Any] = {
        "type": "command",
        "command": command,
    }
    entry: Dict[str, Any] = {"hooks": [hook]}
    if platform == "codex":
        entry["matcher"] = "startup|resume|clear|compact"
        hook["statusMessage"] = "Loading tGD session guidance"
    elif platform == "gemini":
        hook["name"] = TGD_HOOK_NAME
    return entry


def _canonical_command(script: Path) -> str:
    return "bash " + shlex.quote(str(script))


def _is_canonical_state_command(command: str, platform: str) -> bool:
    """Validate a persisted command's shape without requiring its checkout."""
    try:
        words = shlex.split(command)
    except ValueError:
        return False
    if len(words) != 2 or words[0] != "bash" or not Path(words[1]).is_absolute():
        return False
    normalized_script = words[1].replace("\\", "/")
    expected_suffix = "/" + str(PLATFORM_SCRIPTS[platform]).replace("\\", "/")
    return normalized_script.endswith(expected_suffix)


def _empty_hook_state() -> Dict[str, Any]:
    return {"version": HOOK_STATE_VERSION, "managed_hooks": {}}


FileIdentity = Tuple[int, int]


def _load_hook_state(
    path: Path,
) -> Tuple[Dict[str, Any], Optional[bytes], Optional[FileIdentity]]:
    state, _mode, original, identity = _load_destination(path)
    if original is None:
        return _empty_hook_state(), None, None
    if state.get("version") != HOOK_STATE_VERSION:
        raise HookConfigError("invalid hook state: unsupported or missing version")
    managed_hooks = state.get("managed_hooks")
    if not isinstance(managed_hooks, dict):
        raise HookConfigError("invalid hook state: managed_hooks must be an object")

    for platform, destinations in managed_hooks.items():
        if platform not in PLATFORM_SCRIPTS or not isinstance(destinations, dict):
            raise HookConfigError("invalid hook state: malformed platform entry")
        for destination, entry in destinations.items():
            if (
                not isinstance(destination, str)
                or not Path(destination).is_absolute()
                or str(_normalized_absolute_path(Path(destination))) != destination
                or not isinstance(entry, dict)
            ):
                raise HookConfigError("invalid hook state: malformed destination entry")
            commands = entry.get("commands")
            if (
                not isinstance(commands, list)
                or not commands
                or any(
                    not isinstance(command, str)
                    for command in commands
                )
                or len(set(commands)) != len(commands)
                or any(
                    not _is_canonical_state_command(command, platform)
                    for command in commands
                )
            ):
                raise HookConfigError("invalid hook state: malformed command entry")
    return state, original, identity


def _owned_state_commands(
    state: Dict[str, Any],
    platform: str,
    destination: Path,
) -> Tuple[str, ...]:
    entry = (
        state["managed_hooks"]
        .get(platform, {})
        .get(str(destination))
    )
    if entry is None:
        return ()
    return tuple(entry["commands"])


def _with_owned_state_commands(
    state: Dict[str, Any],
    platform: str,
    destination: Path,
    commands: Iterable[str],
) -> Dict[str, Any]:
    updated = dict(state)
    managed_hooks = dict(state["managed_hooks"])
    destinations = dict(managed_hooks.get(platform, {}))
    existing = destinations.get(str(destination), {}).get("commands", [])
    combined = list(existing)
    for command in commands:
        if command not in combined:
            combined.append(command)
    destinations[str(destination)] = {"commands": combined}
    managed_hooks[platform] = destinations
    updated["managed_hooks"] = managed_hooks
    return updated


def _without_owned_state_commands(
    state: Dict[str, Any],
    platform: str,
    destination: Path,
) -> Dict[str, Any]:
    destinations = state["managed_hooks"].get(platform)
    if not isinstance(destinations, dict) or str(destination) not in destinations:
        return state

    updated = dict(state)
    managed_hooks = dict(state["managed_hooks"])
    updated_destinations = dict(destinations)
    del updated_destinations[str(destination)]
    if updated_destinations:
        managed_hooks[platform] = updated_destinations
    else:
        managed_hooks.pop(platform, None)
    updated["managed_hooks"] = managed_hooks
    return updated


def _recognized_canonical_commands(
    value: Any,
    repo_root: Path,
    platform: str,
) -> Tuple[str, ...]:
    """Collect exact same-platform commands proven by the accessible checkout."""
    commands = []

    def visit(candidate: Any) -> None:
        if isinstance(candidate, dict):
            command = candidate.get("command")
            if (
                isinstance(command, str)
                and _is_canonical_state_command(command, platform)
                and _is_tgd_command(command, repo_root)
                and command not in commands
            ):
                commands.append(command)
            for child in candidate.values():
                visit(child)
        elif isinstance(candidate, list):
            for child in candidate:
                visit(child)

    visit(value)
    return tuple(commands)


def install_tgd_hook(
    config: Dict[str, Any],
    repo_root: Path,
    platform: str,
    owned_commands: Iterable[str] = (),
) -> Dict[str, Any]:
    cleaned, _ = remove_tgd_hooks(config, repo_root, owned_commands)
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


def _load_destination(
    path: Path,
) -> Tuple[Dict[str, Any], int, Optional[bytes], Optional[FileIdentity]]:
    if path.is_symlink():
        raise HookConfigError(f"destination must not be a symlink: {path}")
    if not path.exists():
        return {}, 0o600, None, None

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
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = -1
            original = stream.read()
            config = json.loads(original.decode("utf-8"))
    finally:
        if descriptor >= 0:
            os.close(descriptor)

    if not isinstance(config, dict):
        raise HookConfigError("hook config root must be a JSON object")
    return (
        config,
        stat.S_IMODE(file_stat.st_mode),
        original,
        (file_stat.st_dev, file_stat.st_ino),
    )


def _fsync_directory(path: Path) -> None:
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


def _path_matches_snapshot(
    path: Path,
    identity: FileIdentity,
    content: bytes,
) -> bool:
    if not os.path.lexists(str(path)) or path.is_symlink():
        return False
    try:
        current = path.lstat()
        return (
            stat.S_ISREG(current.st_mode)
            and (current.st_dev, current.st_ino) == identity
            and path.read_bytes() == content
        )
    except OSError:
        return False


def _reserve_quarantine(path: Path) -> Path:
    descriptor, quarantine_name = tempfile.mkstemp(
        prefix=f".{path.name}.tgd-quarantine.",
        dir=str(path.parent),
    )
    os.close(descriptor)
    return Path(quarantine_name)


def _restore_quarantine(quarantine: Path, path: Path) -> None:
    """Restore the exact quarantined inode without replacing a concurrent path."""
    if not os.path.lexists(str(quarantine)):
        return
    metadata = quarantine.lstat()
    if not stat.S_ISREG(metadata.st_mode):
        raise HookConfigError(
            f"unexpected data was preserved at quarantine: {quarantine}"
        )
    try:
        os.link(str(quarantine), str(path), follow_symlinks=False)
    except FileExistsError as error:
        raise HookConfigError(
            f"hook path changed concurrently; prior data was preserved at {quarantine}"
        ) from error
    except OSError as error:
        raise HookConfigError(
            f"could not restore hook data; prior data was preserved at {quarantine}"
        ) from error
    restored = path.lstat()
    if (restored.st_dev, restored.st_ino) != (metadata.st_dev, metadata.st_ino):
        raise HookConfigError(
            f"hook path changed concurrently; prior data was preserved at {quarantine}"
        )
    quarantine.unlink()
    _fsync_directory(path.parent)


def _quarantine_snapshot(
    path: Path,
    identity: FileIdentity,
    content: bytes,
) -> Path:
    quarantine = _reserve_quarantine(path)
    try:
        os.replace(str(path), str(quarantine))
    except BaseException:
        try:
            quarantine.unlink()
        except FileNotFoundError:
            pass
        raise

    if not _path_matches_snapshot(quarantine, identity, content):
        _restore_quarantine(quarantine, path)
        raise HookConfigError(
            f"destination changed while hooks were being updated: {path}"
        )
    _fsync_directory(path.parent)
    return quarantine


def _discard_quarantine(
    quarantine: Path,
    identity: FileIdentity,
    content: bytes,
) -> None:
    if not _path_matches_snapshot(quarantine, identity, content):
        raise HookConfigError(
            f"quarantined hook data changed and was preserved at {quarantine}"
        )
    quarantine.unlink()
    _fsync_directory(quarantine.parent)


@contextmanager
def _destination_lock(path: Path) -> Iterator[None]:
    """Serialize cooperating tGD writers across the full read-modify-write."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.parent.is_dir():
        raise HookConfigError(f"destination parent is not a directory: {path.parent}")

    lock_path = path.with_name(f".{path.name}.tgd.lock")
    flags = os.O_CREAT | os.O_RDWR
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(str(lock_path), flags, 0o600)
    except OSError as error:
        raise HookConfigError(
            f"cannot safely open destination lock: {lock_path}"
        ) from error

    try:
        descriptor_stat = os.fstat(descriptor)
        try:
            path_stat = os.lstat(lock_path)
        except OSError as error:
            raise HookConfigError(
                f"cannot safely inspect destination lock: {lock_path}"
            ) from error
        if (
            not stat.S_ISREG(descriptor_stat.st_mode)
            or not stat.S_ISREG(path_stat.st_mode)
            or descriptor_stat.st_dev != path_stat.st_dev
            or descriptor_stat.st_ino != path_stat.st_ino
        ):
            raise HookConfigError(
                f"destination lock is not a stable regular file: {lock_path}"
            )
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)


def _write_atomic(
    path: Path,
    config: Dict[str, Any],
    mode: int,
    expected_original: Optional[bytes],
    expected_identity: Optional[FileIdentity],
) -> None:
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
    quarantine: Optional[Path] = None
    installed = False
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            descriptor = -1
            json.dump(config, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        if expected_original is None:
            if os.path.lexists(str(path)):
                raise HookConfigError(
                    f"destination changed while hooks were being updated: {path}"
                )
        else:
            if expected_identity is None:
                raise HookConfigError(
                    f"destination identity is missing for safe update: {path}"
                )
            quarantine = _quarantine_snapshot(
                path,
                expected_identity,
                expected_original,
            )

        try:
            os.link(
                str(temporary_path),
                str(path),
                follow_symlinks=False,
            )
        except FileExistsError as error:
            raise HookConfigError(
                f"destination changed while hooks were being updated: {path}"
            ) from error
        except OSError as error:
            raise HookConfigError(
                f"cannot install updated hook destination: {path}"
            ) from error
        installed = True
        temporary_path.unlink()
        _fsync_directory(path.parent)
        if quarantine is not None:
            _discard_quarantine(
                quarantine,
                expected_identity,
                expected_original,
            )
    except Exception as error:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass
        if (
            quarantine is not None
            and os.path.lexists(str(quarantine))
            and not os.path.lexists(str(path))
        ):
            _restore_quarantine(quarantine, path)
        elif quarantine is not None and os.path.lexists(str(quarantine)):
            if installed:
                message = (
                    "updated hook config is installed, but prior data was "
                    f"preserved at {quarantine}"
                )
            else:
                message = (
                    "hook path changed concurrently; prior data was "
                    f"preserved at {quarantine}"
                )
            raise HookConfigError(message) from error
        raise


def _remove_atomic(
    path: Path,
    expected_original: Optional[bytes],
    expected_identity: Optional[FileIdentity],
) -> None:
    """Remove one state file only when it still has the bytes we loaded."""
    if expected_original is None:
        return
    if expected_identity is None:
        raise HookConfigError(f"state identity is missing for safe removal: {path}")
    quarantine = _quarantine_snapshot(
        path,
        expected_identity,
        expected_original,
    )
    try:
        _discard_quarantine(
            quarantine,
            expected_identity,
            expected_original,
        )
    except BaseException as error:
        try:
            _restore_quarantine(quarantine, path)
        except HookConfigError as rollback_error:
            raise rollback_error from error
        raise


def _persist_cleared_state(
    state_path: Path,
    cleared_state: Dict[str, Any],
    state_original: Optional[bytes],
    state_identity: Optional[FileIdentity],
) -> None:
    if cleared_state["managed_hooks"]:
        _write_atomic(
            state_path,
            cleared_state,
            0o600,
            state_original,
            state_identity,
        )
    else:
        _remove_atomic(state_path, state_original, state_identity)


def _run_with_locks(
    args: argparse.Namespace,
    repo_root: Path,
    destination: Path,
    state_path: Optional[Path],
) -> int:
    state = _empty_hook_state()
    state_original = None
    state_identity = None
    if state_path is not None:
        state, state_original, state_identity = _load_hook_state(state_path)
    owned_commands = _owned_state_commands(
        state,
        args.platform,
        destination,
    )

    destination_missing = (
        not destination.exists() and not destination.is_symlink()
    )
    if args.action == "remove" and destination_missing:
        if state_path is not None and owned_commands:
            cleared_state = _without_owned_state_commands(
                state,
                args.platform,
                destination,
            )
            _persist_cleared_state(
                state_path,
                cleared_state,
                state_original,
                state_identity,
            )
        print(f"No {args.platform} hook config found; nothing to remove.")
        return 0

    config, mode, original, identity = _load_destination(destination)
    if args.action == "install":
        script = _canonical_script(
            repo_root,
            args.platform,
            require_file=True,
        )
        current_command = _canonical_command(script)
        updated = install_tgd_hook(
            config,
            repo_root,
            args.platform,
            owned_commands,
        )

        if state_path is not None:
            recognized_commands = _recognized_canonical_commands(
                config,
                repo_root,
                args.platform,
            )
            updated_state = _with_owned_state_commands(
                state,
                args.platform,
                destination,
                tuple(recognized_commands) + (current_command,),
            )
            if updated_state != state:
                # Install ownership is monotonic: record exact commands before
                # mutating the config so an interrupted migration never loses
                # the previous checkout's command.
                _write_atomic(
                    state_path,
                    updated_state,
                    0o600,
                    state_original,
                    state_identity,
                )

        if updated != config:
            _write_atomic(destination, updated, mode, original, identity)
        action_text = "installed"
    else:
        updated, changed = remove_tgd_hooks(
            config,
            repo_root,
            owned_commands,
        )
        if changed:
            _write_atomic(destination, updated, mode, original, identity)

        state_cleared = False
        if state_path is not None and owned_commands:
            cleared_state = _without_owned_state_commands(
                state,
                args.platform,
                destination,
            )
            _persist_cleared_state(
                state_path,
                cleared_state,
                state_original,
                state_identity,
            )
            state_cleared = True

        if not changed:
            suffix = " Ownership state was cleared." if state_cleared else ""
            print(
                f"No tGD hooks found in {destination}; nothing to remove.{suffix}"
            )
            return 0
        action_text = "removed"

    print(f"tGD {args.platform} hook {action_text}: {destination}")
    return 0


def run(args: argparse.Namespace) -> int:
    repo_root = _canonical_repo_root(args.repo_root)
    destination = _normalized_absolute_path(args.destination)
    state_path = (
        _normalized_absolute_path(args.state)
        if args.state is not None
        else None
    )
    if state_path == destination:
        raise HookConfigError("hook state and destination must be different files")

    with _destination_lock(destination):
        if state_path is None:
            return _run_with_locks(
                args,
                repo_root,
                destination,
                None,
            )
        with _destination_lock(state_path):
            return _run_with_locks(
                args,
                repo_root,
                destination,
                state_path,
            )


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        return run(parse_args(argv))
    except (HookConfigError, json.JSONDecodeError, OSError, UnicodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
