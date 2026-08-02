#!/usr/bin/env python3
"""Deterministic, confirmation-gated TASKS.md to Jira Data Center sync.

The ``plan`` command performs read-only Jira requests and writes a reviewable
plan artifact. The ``apply`` command accepts only that exact plan digest,
re-checks the source file, mutates Jira, verifies the remote result, and then
atomically records Jira keys in TASKS.md.

Authentication is intentionally environment-only: ``JIRA_TOKEN`` is never a
command-line option and is never serialized into a plan.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import re
import ssl
import stat
import sys
import tempfile
import time
from typing import Any, Dict, Iterable, List, Mapping, NamedTuple, Optional, Sequence, Tuple
import urllib.error
import urllib.parse
import urllib.request


PLAN_SCHEMA_VERSION = 3
PROPERTY_KEY = "tgd.sync"
DEFAULT_ISSUE_TYPE = "Story"
AUTOMATIC_CREATE_FIELDS = {
    "project",
    "summary",
    "issuetype",
    "description",
    "priority",
    "labels",
}
VALID_PRIORITIES = {"High", "Medium", "Low"}
PRIORITY_ALIASES = {
    "High": ("High", "Highest", "Critical"),
    "Medium": ("Medium", "Normal"),
    "Low": ("Low", "Lowest"),
}
VALID_STATUS_RE = re.compile(r"^(?:pending|in-progress|complete|blocked(?::\s*.+)?)$")
TASK_HEADING_RE = re.compile(r"^## Task\s+(\d+):\s*(.+?)\s*$")
LEVEL_TWO_HEADING_RE = re.compile(r"^##\s+")
LEVEL_THREE_HEADING_RE = re.compile(r"^###\s+")
ISSUE_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]*-\d+$")
SYNC_ID_RE = re.compile(r"^tgd-sync-[a-z0-9][a-z0-9-]{2,63}$")
SOURCE_ID_RE = re.compile(
    r"^tgd-source-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
AC_RE = re.compile(r"^\s*-\s+\*\*(AC-(\d+)\.\d+)\*\*\s+[—-]\s+(.+)$")
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
SECRET_RE = re.compile(r"(?i)(Bearer\s+)[A-Za-z0-9._~+/=-]+")
LEGACY_HEADING_KEY_RE = re.compile(r"(?<!\S)\[([A-Z][A-Z0-9_]*-\d+)\](?!\S)")
_NOT_FOUND = object()


class ContractError(RuntimeError):
    """Raised when a local document or confirmation violates the sync contract."""


class JiraError(RuntimeError):
    """Raised for a definite Jira transport or API failure."""


class JiraBatchAbort(JiraError):
    """Raised for a systemic Jira failure where the remaining batch must stop."""


class AmbiguousMutation(JiraError):
    """Raised when Jira might have accepted a create request before disconnecting."""


class RemoteUnknown(JiraError):
    """Raised when a remote mutation cannot be reconciled to one Jira issue."""


class RemoteUnknownBatchAbort(JiraBatchAbort):
    """Current mutation is unknown and a systemic lookup failure aborts the batch."""


class TaskRecord(NamedTuple):
    number: int
    title: str
    story_id: Optional[str]
    status: str
    priority: str
    ac_ids: Tuple[str, ...]
    acceptance_criteria: Tuple[str, ...]
    files: Tuple[str, ...]
    context: str
    jira_key: Optional[str]
    sync_id: Optional[str]
    legacy_jira_key: Optional[str]


class TasksDocument(NamedTuple):
    path: Path
    raw_text: str
    source_sha256: str
    feature_name: str
    source_id: str
    tasks: Tuple[TaskRecord, ...]


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256_json(value: Any) -> str:
    return _sha256_bytes(_canonical_json(value))


def _outside_fences(lines: Sequence[str]) -> List[bool]:
    outside: List[bool] = []
    fence_char: Optional[str] = None
    fence_len = 0
    for line in lines:
        match = FENCE_RE.match(line)
        if fence_char is None:
            outside.append(True)
            if match:
                marker = match.group(1)
                fence_char = marker[0]
                fence_len = len(marker)
        else:
            outside.append(False)
            if match:
                marker = match.group(1)
                if marker[0] == fence_char and len(marker) >= fence_len:
                    fence_char = None
                    fence_len = 0
    if fence_char is not None:
        raise ContractError("TASKS.md contains an unclosed Markdown fence")
    return outside


def _task_ranges(lines: Sequence[str]) -> List[Tuple[int, int, re.Match[str]]]:
    outside = _outside_fences(lines)
    starts: List[Tuple[int, re.Match[str]]] = []
    for index, line in enumerate(lines):
        if not outside[index]:
            continue
        match = TASK_HEADING_RE.match(line.rstrip("\r\n"))
        if match:
            starts.append((index, match))

    ranges: List[Tuple[int, int, re.Match[str]]] = []
    for position, (start, match) in enumerate(starts):
        next_task = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
        end = next_task
        for index in range(start + 1, next_task):
            if outside[index] and LEVEL_TWO_HEADING_RE.match(lines[index]):
                end = index
                break
        ranges.append((start, end, match))
    return ranges


def _single_field(
    block: Sequence[str], pattern: re.Pattern[str], field_name: str
) -> str:
    values = []
    outside = _outside_fences(block)
    for index, line in enumerate(block):
        if not outside[index]:
            continue
        match = pattern.match(line.rstrip("\r\n"))
        if match:
            values.append(match.group(1).strip())
    if len(values) != 1:
        raise ContractError(
            f"task must contain exactly one {field_name} field (found {len(values)})"
        )
    return values[0]


def _optional_marker(value: str) -> Optional[str]:
    stripped = value.strip()
    if stripped in {"", "-", "—", "pending", "none", "None"}:
        return None
    return stripped


def _section(
    block: Sequence[str], heading_pattern: re.Pattern[str]
) -> Tuple[List[str], List[bool]]:
    outside = _outside_fences(block)
    start: Optional[int] = None
    for index, line in enumerate(block):
        if outside[index] and heading_pattern.match(line.rstrip("\r\n")):
            if start is not None:
                raise ContractError(f"duplicate section: {line.strip()}")
            start = index + 1
    if start is None:
        raise ContractError(f"missing section matching {heading_pattern.pattern}")
    end = len(block)
    for index in range(start, len(block)):
        if outside[index] and LEVEL_THREE_HEADING_RE.match(block[index]):
            end = index
            break
    return list(block[start:end]), outside[start:end]


def _plain_markdown(value: str) -> str:
    value = value.replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", value).strip()


def _strip_legacy_heading_key(title: str) -> Tuple[str, Optional[str]]:
    """Extract one legacy standalone ``[KEY-123]`` token from a task heading."""

    matches = list(LEGACY_HEADING_KEY_RE.finditer(title))
    if len(matches) > 1:
        keys = ", ".join(match.group(1) for match in matches)
        raise ContractError(f"task heading contains multiple legacy Jira keys: {keys}")
    if not matches:
        return title, None
    match = matches[0]
    cleaned = (title[: match.start()] + title[match.end() :]).strip()
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    if not cleaned:
        raise ContractError("task title is empty after removing its legacy Jira key")
    return cleaned, match.group(1)


def parse_tasks_file(path: Path) -> TasksDocument:
    """Parse and validate the canonical TASKS.md task blocks."""

    source_path = Path(path).expanduser().resolve()
    try:
        raw_bytes = source_path.read_bytes()
        raw_text = raw_bytes.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ContractError(f"cannot read UTF-8 TASKS.md: {exc}") from exc

    feature_match = re.search(r"(?m)^# TASKS\.md:\s*(.+?)\s*$", raw_text)
    if not feature_match:
        raise ContractError("TASKS.md is missing '# TASKS.md: <feature>'")
    feature_name = feature_match.group(1).strip()
    if not feature_name:
        raise ContractError("TASKS.md feature name is empty")

    lines = raw_text.splitlines(keepends=True)
    outside = _outside_fences(lines)
    source_matches = []
    source_pattern = re.compile(r"^> \*\*Jira-Source-ID\*\*:\s*(\S+)\s*$")
    for index, line in enumerate(lines):
        if not outside[index]:
            continue
        match = source_pattern.match(line.rstrip("\r\n"))
        if match:
            source_matches.append(match.group(1))
    if len(source_matches) != 1 or not SOURCE_ID_RE.fullmatch(source_matches[0]):
        raise ContractError(
            "TASKS.md must contain one valid '> **Jira-Source-ID**: tgd-source-<lowercase UUID v4>' field"
        )
    source_id = source_matches[0]

    ranges = _task_ranges(lines)
    if not ranges:
        raise ContractError("TASKS.md has no canonical '## Task N:' blocks")

    tasks: List[TaskRecord] = []
    seen_numbers = set()
    seen_ac_ids = set()
    seen_sync_ids: Dict[str, int] = {}
    for start, end, heading in ranges:
        number = int(heading.group(1))
        if number in seen_numbers:
            raise ContractError(f"duplicate task number: {number}")
        seen_numbers.add(number)

        heading_title = heading.group(2).strip()
        story_id: Optional[str] = None
        story_match = re.search(
            r"\s+\(Story ID:\s*([^)]+?)\)\s*$", heading_title, re.IGNORECASE
        )
        if story_match:
            story_id = story_match.group(1).strip()
            heading_title = heading_title[: story_match.start()].rstrip()
        heading_title, legacy_jira_key = _strip_legacy_heading_key(heading_title)
        if not heading_title:
            raise ContractError(f"task {number} title is empty")

        block = lines[start:end]
        status = _single_field(
            block,
            re.compile(r"^\*\*Status:\*\*\s*([^<\r\n]+)"),
            "Status",
        )
        if not VALID_STATUS_RE.fullmatch(status):
            raise ContractError(f"task {number} has invalid Status: {status}")

        priority = _single_field(
            block,
            re.compile(r"^\s*-\s+\*\*Priority\*\*:\s*(\S+)\s*$"),
            "Priority",
        )
        if priority not in VALID_PRIORITIES:
            raise ContractError(f"task {number} has invalid Priority: {priority}")

        jira_value = _single_field(
            block,
            re.compile(r"^\*\*Jira:\*\*\s*(.*?)\s*$"),
            "Jira",
        )
        jira_key = _optional_marker(jira_value)
        if jira_key and not ISSUE_KEY_RE.fullmatch(jira_key):
            raise ContractError(f"task {number} has invalid Jira key: {jira_key}")
        if jira_key and legacy_jira_key and jira_key != legacy_jira_key:
            raise ContractError(
                f"task {number} Jira field {jira_key} conflicts with legacy heading key "
                f"{legacy_jira_key}"
            )

        sync_value = _single_field(
            block,
            re.compile(r"^\*\*Jira-Sync-ID:\*\*\s*(.*?)\s*$"),
            "Jira-Sync-ID",
        )
        sync_id = _optional_marker(sync_value)
        if sync_id and not SYNC_ID_RE.fullmatch(sync_id):
            raise ContractError(f"task {number} has invalid Jira-Sync-ID: {sync_id}")
        if sync_id:
            previous_task = seen_sync_ids.get(sync_id)
            if previous_task is not None:
                raise ContractError(
                    f"duplicate Jira-Sync-ID {sync_id}: tasks {previous_task} and {number}"
                )
            seen_sync_ids[sync_id] = number

        ac_lines, ac_outside = _section(
            block, re.compile(r"^### 3\. Acceptance Criteria \(BDD\)\s*$")
        )
        ac_ids: List[str] = []
        acceptance: List[str] = []
        for index, line in enumerate(ac_lines):
            if not ac_outside[index]:
                continue
            match = AC_RE.match(line.rstrip("\r\n"))
            if not match:
                continue
            ac_id = match.group(1)
            ac_task = int(match.group(2))
            if ac_task != number:
                raise ContractError(
                    f"{ac_id} belongs to task {ac_task}, not task {number}"
                )
            if ac_id in seen_ac_ids:
                raise ContractError(f"duplicate acceptance criterion: {ac_id}")
            criterion = match.group(3).strip()
            for marker in ("**Given**", "**When**", "**Then**"):
                if marker not in criterion:
                    raise ContractError(f"{ac_id} is missing {marker}")
            seen_ac_ids.add(ac_id)
            ac_ids.append(ac_id)
            acceptance.append(f"{ac_id}: {_plain_markdown(criterion)}")
        if not ac_ids:
            raise ContractError(f"task {number} has no canonical BDD acceptance criteria")

        file_lines, file_outside = _section(
            block, re.compile(r"^### 4\. Files Likely Touched\s*$")
        )
        files: List[str] = []
        for index, line in enumerate(file_lines):
            if not file_outside[index]:
                continue
            match = re.match(r"^\s*-\s+`([^`]+)`\s*$", line.rstrip("\r\n"))
            if match:
                files.append(match.group(1).strip())
        if not files:
            raise ContractError(f"task {number} has no Files Likely Touched")

        context_lines, context_outside = _section(
            block, re.compile(r"^### 1\. Context & Goal\s*$")
        )
        context_parts = []
        for index, line in enumerate(context_lines):
            if not context_outside[index]:
                continue
            stripped = line.strip()
            if stripped and not stripped.startswith("- **Priority") and not stripped.startswith(
                "- **Dependencies"
            ):
                context_parts.append(_plain_markdown(stripped))
        context = " ".join(context_parts).strip()

        tasks.append(
            TaskRecord(
                number=number,
                title=heading_title,
                story_id=story_id,
                status=status,
                priority=priority,
                ac_ids=tuple(ac_ids),
                acceptance_criteria=tuple(acceptance),
                files=tuple(files),
                context=context,
                jira_key=jira_key,
                sync_id=sync_id,
                legacy_jira_key=legacy_jira_key,
            )
        )

    return TasksDocument(
        path=source_path,
        raw_text=raw_text,
        source_sha256=_sha256_bytes(raw_bytes),
        feature_name=feature_name,
        source_id=source_id,
        tasks=tuple(tasks),
    )


def write_jira_links(
    raw_text: str, links: Mapping[int, Tuple[str, str]]
) -> str:
    """Replace canonical Jira fields without changing task headings or content."""

    if not links:
        return raw_text
    lines = raw_text.splitlines(keepends=True)
    ranges = _task_ranges(lines)
    found = set()
    for start, end, heading in ranges:
        number = int(heading.group(1))
        if number not in links:
            continue
        issue_key, sync_id = links[number]
        if not ISSUE_KEY_RE.fullmatch(issue_key):
            raise ContractError(f"cannot write invalid Jira key: {issue_key}")
        if not SYNC_ID_RE.fullmatch(sync_id):
            raise ContractError(f"cannot write invalid Jira-Sync-ID: {sync_id}")
        jira_indexes = []
        sync_indexes = []
        outside = _outside_fences(lines[start:end])
        for relative, line in enumerate(lines[start:end]):
            if not outside[relative]:
                continue
            if re.match(r"^\*\*Jira:\*\*", line):
                jira_indexes.append(start + relative)
            if re.match(r"^\*\*Jira-Sync-ID:\*\*", line):
                sync_indexes.append(start + relative)
        if len(jira_indexes) != 1 or len(sync_indexes) != 1:
            raise ContractError(
                f"task {number} must have one Jira and one Jira-Sync-ID field"
            )
        jira_eol = "\r\n" if lines[jira_indexes[0]].endswith("\r\n") else "\n"
        sync_eol = "\r\n" if lines[sync_indexes[0]].endswith("\r\n") else "\n"
        if not lines[jira_indexes[0]].endswith(("\n", "\r\n")):
            jira_eol = ""
        if not lines[sync_indexes[0]].endswith(("\n", "\r\n")):
            sync_eol = ""
        lines[jira_indexes[0]] = f"**Jira:** {issue_key}{jira_eol}"
        lines[sync_indexes[0]] = f"**Jira-Sync-ID:** {sync_id}{sync_eol}"
        heading_eol = "\r\n" if lines[start].endswith("\r\n") else "\n"
        if not lines[start].endswith(("\n", "\r\n")):
            heading_eol = ""
        heading_match = TASK_HEADING_RE.match(lines[start].rstrip("\r\n"))
        if heading_match:
            clean_title, legacy_key = _strip_legacy_heading_key(heading_match.group(2))
            if legacy_key:
                if legacy_key != issue_key:
                    raise ContractError(
                        f"task {number} legacy heading key {legacy_key} conflicts with "
                        f"verified Jira issue {issue_key}"
                    )
                lines[start] = f"## Task {number}: {clean_title}{heading_eol}"
        found.add(number)
    missing = set(links) - found
    if missing:
        raise ContractError(
            "cannot write Jira links for missing task(s): "
            + ", ".join(str(number) for number in sorted(missing))
        )
    return "".join(lines)


def _project_view(project: Mapping[str, Any], default_key: Optional[str]) -> Dict[str, Any]:
    key = str(project.get("key", "")).strip()
    name = str(project.get("name", "")).strip()
    project_id = str(project.get("id", "")).strip()
    if not key or not name:
        raise ContractError("Jira returned a project without key or name")
    if not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
        raise ContractError(f"Jira returned an unsafe project key: {key!r}")
    if any(ord(character) < 32 or ord(character) == 127 for character in name):
        raise ContractError(f"Jira returned an unsafe project name for {key}")
    return {
        "id": project_id,
        "key": key,
        "name": name,
        "is_default": bool(default_key and key == default_key),
    }


def project_choices(client: Any, default_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return accessible projects; the saved key is display-only metadata."""

    projects = [_project_view(project, default_key) for project in client.list_projects()]
    projects.sort(key=lambda item: item["key"])
    return projects


def _stable_sync_id(project_key: str, document: TasksDocument, task: TaskRecord) -> str:
    identity = {
        "project": project_key,
        "source_id": document.source_id,
        "task": task.number,
    }
    return "tgd-sync-" + _sha256_json(identity)[:24]


def _description(document: TasksDocument, task: TaskRecord, sync_id: str) -> str:
    lines = [task.context or task.title, "", "Acceptance Criteria:"]
    lines.extend(f"* {criterion}" for criterion in task.acceptance_criteria)
    lines.extend(["", "Files Likely Touched:"])
    lines.extend(f"* {path}" for path in task.files)
    lines.extend(
        [
            "",
            f"Source: TASKS.md / {document.feature_name} / Task {task.number}",
            f"tGD Sync ID: {sync_id}",
        ]
    )
    return "\n".join(lines)


def _priority_choice(priorities: Iterable[Mapping[str, Any]], name: str) -> Optional[Dict[str, str]]:
    choices = list(priorities)
    aliases = PRIORITY_ALIASES.get(name, (name,))
    for alias in aliases:
        for priority in choices:
            if str(priority.get("name", "")).casefold() == alias.casefold():
                return {
                    "id": str(priority.get("id", "")),
                    "name": str(priority.get("name", "")),
                }
    return None


def _create_contract_sha256(
    issue_type: Mapping[str, Any],
    fields: Mapping[str, Any],
    priorities: Iterable[Mapping[str, Any]],
) -> str:
    normalized_fields: Dict[str, Any] = {}
    for key in sorted(str(item) for item in fields):
        metadata = fields[key]
        if not isinstance(metadata, Mapping):
            normalized_fields[key] = None
            continue
        schema = metadata.get("schema", {})
        normalized_schema = {}
        if isinstance(schema, Mapping):
            normalized_schema = {
                name: schema.get(name)
                for name in ("type", "items", "system", "custom", "customId")
                if name in schema
            }
        normalized_fields[key] = {
            "name": metadata.get("name"),
            "required": bool(metadata.get("required")),
            "schema": normalized_schema,
            "allowedValues": metadata.get("allowedValues", []),
        }
    normalized_priorities = sorted(
        (
            {"id": str(item.get("id", "")), "name": str(item.get("name", ""))}
            for item in priorities
        ),
        key=lambda item: (item["id"], item["name"]),
    )
    return _sha256_json(
        {
            "issue_type": {
                "id": str(issue_type.get("id", "")),
                "name": str(issue_type.get("name", "")),
            },
            "fields": normalized_fields,
            "priorities": normalized_priorities,
        }
    )


def _validate_json_value(value: Any, context: str) -> None:
    nodes = 0

    def visit(item: Any, depth: int) -> None:
        nonlocal nodes
        nodes += 1
        if nodes > 10000 or depth > 12:
            raise ContractError(f"{context} is too large or deeply nested")
        if item is None or isinstance(item, (bool, int, str)):
            if isinstance(item, str) and len(item) > 100000:
                raise ContractError(f"{context} contains an oversized string")
            return
        if isinstance(item, float):
            if not math.isfinite(item):
                raise ContractError(f"{context} contains a non-finite number")
            return
        if isinstance(item, list):
            for child in item:
                visit(child, depth + 1)
            return
        if isinstance(item, Mapping):
            for key, child in item.items():
                if not isinstance(key, str) or len(key) > 256:
                    raise ContractError(f"{context} contains an invalid object key")
                visit(child, depth + 1)
            return
        raise ContractError(f"{context} contains a non-JSON value")

    visit(value, 0)


def _answer_is_empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _allowed_selectors(value: Any) -> List[str]:
    if isinstance(value, Mapping):
        selectors = []
        for key in ("id", "key", "value", "name"):
            if key in value and value[key] is not None:
                selectors.append(str(value[key]))
        return selectors
    if isinstance(value, (str, int, float)) and not isinstance(value, bool):
        return [str(value)]
    return []


def _allowed_api_value(value: Any) -> Any:
    if not isinstance(value, Mapping):
        return value
    for key in ("id", "key", "value", "name"):
        if key in value:
            return {key: value[key]}
    return dict(value)


def _normalize_allowed_value(value: Any, allowed_values: Sequence[Any], field_name: str) -> Any:
    exact_matches = [item for item in allowed_values if item == value]
    if len(exact_matches) == 1:
        return _allowed_api_value(exact_matches[0])
    selectors = set(_allowed_selectors(value))
    matches = [
        item
        for item in allowed_values
        if selectors and selectors.intersection(_allowed_selectors(item))
    ]
    if len(matches) != 1:
        raise ContractError(f"Jira field {field_name} answer is not one of the allowed values")
    return _allowed_api_value(matches[0])


def _normalize_field_value(descriptor: Mapping[str, Any], value: Any) -> Any:
    field_name = str(descriptor["name"])
    if _answer_is_empty(value):
        raise ContractError(f"Jira field {field_name} answer is empty")
    _validate_json_value(value, f"Jira field {field_name} answer")
    schema = descriptor.get("schema", {})
    schema_type = str(schema.get("type", "")) if isinstance(schema, Mapping) else ""
    allowed_values = descriptor.get("allowed_values", [])
    if not isinstance(allowed_values, list):
        raise ContractError(f"Jira field {field_name} has invalid allowed values")

    if schema_type == "array":
        if not isinstance(value, list) or not value:
            raise ContractError(f"Jira field {field_name} answer must be a non-empty list")
        if allowed_values:
            return [
                _normalize_allowed_value(item, allowed_values, field_name) for item in value
            ]
        return value
    if allowed_values:
        return _normalize_allowed_value(value, allowed_values, field_name)
    if schema_type in {"string", "date", "datetime"} and not isinstance(value, str):
        raise ContractError(f"Jira field {field_name} answer must be text")
    if schema_type == "number" and (
        isinstance(value, bool) or not isinstance(value, (int, float))
    ):
        raise ContractError(f"Jira field {field_name} answer must be numeric")
    if schema_type == "integer" and (isinstance(value, bool) or not isinstance(value, int)):
        raise ContractError(f"Jira field {field_name} answer must be an integer")
    if schema_type == "boolean" and not isinstance(value, bool):
        raise ContractError(f"Jira field {field_name} answer must be true or false")
    return value


def _normalized_field_answers(
    field_answers: Optional[Mapping[str, Any]],
    descriptors: Sequence[Mapping[str, Any]],
    task_numbers: Iterable[int],
) -> Tuple[Dict[str, Any], Dict[int, Dict[str, Any]]]:
    raw: Mapping[str, Any] = field_answers or {"defaults": {}, "tasks": {}}
    if not isinstance(raw, Mapping) or set(raw) != {"defaults", "tasks"}:
        raise ContractError("field answers must contain exactly 'defaults' and 'tasks' objects")
    raw_defaults = raw.get("defaults")
    raw_tasks = raw.get("tasks")
    if not isinstance(raw_defaults, Mapping) or not isinstance(raw_tasks, Mapping):
        raise ContractError("field answer defaults and tasks must be JSON objects")
    descriptor_by_id = {str(item["id"]): item for item in descriptors}
    valid_tasks = set(task_numbers)

    def normalize_values(values: Mapping[str, Any], scope: str) -> Dict[str, Any]:
        normalized: Dict[str, Any] = {}
        for raw_field_id, value in values.items():
            field_id = str(raw_field_id)
            descriptor = descriptor_by_id.get(field_id)
            if descriptor is None:
                raise ContractError(f"unsupported Jira field answer in {scope}: {field_id}")
            normalized[field_id] = _normalize_field_value(descriptor, value)
        return normalized

    defaults = normalize_values(raw_defaults, "defaults")
    tasks: Dict[int, Dict[str, Any]] = {}
    for raw_task_number, values in raw_tasks.items():
        try:
            task_number = int(str(raw_task_number))
        except ValueError as exc:
            raise ContractError(f"invalid task number in Jira field answers: {raw_task_number}") from exc
        if task_number not in valid_tasks:
            raise ContractError(f"Jira field answers name unknown task {task_number}")
        if not isinstance(values, Mapping):
            raise ContractError(f"Jira field answers for task {task_number} must be an object")
        tasks[task_number] = normalize_values(values, f"task {task_number}")
    return defaults, tasks


def _create_only_fields_for_task(
    descriptors: Sequence[Mapping[str, Any]],
    defaults: Mapping[str, Any],
    task_overrides: Mapping[int, Mapping[str, Any]],
    task_number: int,
) -> Dict[str, Any]:
    values = dict(defaults)
    values.update(task_overrides.get(task_number, {}))
    missing = [
        f"{descriptor['id']} ({descriptor['name']})"
        for descriptor in descriptors
        if descriptor["id"] not in values
    ]
    if missing:
        raise ContractError(
            f"missing required Jira field answers for task {task_number}: " + ", ".join(missing)
        )
    return {str(descriptor["id"]): values[str(descriptor["id"])] for descriptor in descriptors}


def _field_descriptor(field_id: str, metadata: Mapping[str, Any]) -> Dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", field_id):
        raise ContractError(f"Jira returned an unsafe field id: {field_id!r}")
    name = str(metadata.get("name", "")).strip()
    if not name:
        raise ContractError(f"Jira required field {field_id} has no display name")
    schema = metadata.get("schema", {})
    if schema is None:
        schema = {}
    if not isinstance(schema, Mapping):
        raise ContractError(f"Jira required field {field_id} has invalid schema metadata")
    normalized_schema = {
        key: schema.get(key)
        for key in ("type", "items", "system", "custom", "customId")
        if key in schema
    }
    allowed_values = metadata.get("allowedValues", [])
    if allowed_values is None:
        allowed_values = []
    if not isinstance(allowed_values, list):
        raise ContractError(f"Jira required field {field_id} has invalid allowed values")
    _validate_json_value(allowed_values, f"Jira allowed values for {field_id}")
    return {
        "id": field_id,
        "name": name,
        "schema": normalized_schema,
        "allowed_values": allowed_values,
    }


def _required_field_descriptors(create_fields: Mapping[str, Any]) -> List[Dict[str, Any]]:
    descriptors: List[Dict[str, Any]] = []
    for raw_field_id in sorted(create_fields, key=lambda item: str(item)):
        metadata = create_fields[raw_field_id]
        field_id = str(raw_field_id)
        if not isinstance(metadata, Mapping):
            raise ContractError(f"Jira field {field_id} has invalid create metadata")
        if bool(metadata.get("required")) and field_id.casefold() not in AUTOMATIC_CREATE_FIELDS:
            descriptors.append(_field_descriptor(field_id, metadata))
    return descriptors


def _resolve_create_context(
    client: Any,
    project_key: str,
    issue_type_name: str,
) -> Tuple[Dict[str, Any], Dict[str, Any], Mapping[str, Any], List[Mapping[str, Any]]]:
    projects = project_choices(client)
    project = next((item for item in projects if item["key"] == project_key), None)
    if project is None:
        raise ContractError(f"unknown Jira project: {project_key}")

    issue_types = list(client.list_issue_types(project_key))
    issue_type = next(
        (
            item
            for item in issue_types
            if str(item.get("name", "")).casefold() == issue_type_name.casefold()
        ),
        None,
    )
    if issue_type is None:
        available = ", ".join(str(item.get("name", "")) for item in issue_types) or "none"
        raise ContractError(
            f"issue type {issue_type_name!r} is not creatable in {project_key}; available: {available}"
        )
    issue_type_id = str(issue_type.get("id", ""))
    if not issue_type_id:
        raise ContractError("Jira issue type is missing an id")

    create_fields = client.get_create_fields(project_key, issue_type_id)
    if not isinstance(create_fields, Mapping):
        raise ContractError("Jira create metadata did not return a field map")
    for required_base_field in ("project", "summary", "issuetype", "description"):
        if required_base_field not in create_fields:
            raise ContractError(
                f"Jira {required_base_field} field is unavailable for the selected issue type"
            )
    if "labels" not in create_fields:
        raise ContractError("Jira Labels field is unavailable; stable upsert cannot be guaranteed")
    priorities = list(client.list_priorities()) if "priority" in create_fields else []
    return (
        dict(project),
        {"id": issue_type_id, "name": str(issue_type.get("name", ""))},
        create_fields,
        priorities,
    )


def required_field_questions(
    client: Any,
    project_key: str,
    issue_type_name: str = DEFAULT_ISSUE_TYPE,
) -> Dict[str, Any]:
    """Return the generic required-field questions for one Project/issue type."""

    project, issue_type, create_fields, _priorities = _resolve_create_context(
        client, project_key, issue_type_name
    )
    return {
        "project": {"id": project["id"], "key": project["key"], "name": project["name"]},
        "issue_type": issue_type,
        "required_fields": _required_field_descriptors(create_fields),
    }


def _property_value(
    document: TasksDocument,
    task: TaskRecord,
    sync_id: str,
    content_sha256: str,
) -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "sync_id": sync_id,
        "content_sha256": content_sha256,
        "source": {
            "source_id": document.source_id,
            "feature": document.feature_name,
            "task": task.number,
            "story_id": task.story_id,
        },
        "managed_fields": ["summary", "description", "priority", "labels:sync_id"],
    }


def _managed_action_content(
    document: TasksDocument,
    task: TaskRecord,
    sync_id: str,
    priorities: Iterable[Mapping[str, Any]],
    priority_enabled: bool,
) -> Tuple[Dict[str, Any], Optional[Dict[str, str]], str, Dict[str, Any]]:
    summary = f"[{document.feature_name}] {task.title}"
    if len(summary) > 255:
        summary = summary[:252].rstrip() + "..."
    priority = _priority_choice(priorities, task.priority) if priority_enabled else None
    owned_fields: Dict[str, Any] = {
        "summary": summary,
        "description": _description(document, task, sync_id),
    }
    if priority:
        owned_fields["priority"] = {"id": priority["id"]}
    content_hash = _sha256_json(
        {
            "summary": owned_fields["summary"],
            "description": owned_fields["description"],
            "priority": priority,
            "sync_id": sync_id,
        }
    )
    expected_property = _property_value(document, task, sync_id, content_hash)
    return owned_fields, priority, content_hash, expected_property


def _issue_project_key(issue: Mapping[str, Any]) -> str:
    fields = issue.get("fields", {})
    project = fields.get("project", {}) if isinstance(fields, Mapping) else {}
    return str(project.get("key", "")) if isinstance(project, Mapping) else ""


def _issue_labels(issue: Mapping[str, Any]) -> List[str]:
    fields = issue.get("fields", {})
    labels = fields.get("labels", []) if isinstance(fields, Mapping) else []
    return [str(label) for label in labels] if isinstance(labels, list) else []


def _property_proves_identity(
    current: Mapping[str, Any], expected: Mapping[str, Any]
) -> bool:
    """Require the complete tGD property identity, not only a forgeable label."""

    required_keys = {
        "schema_version",
        "sync_id",
        "content_sha256",
        "source",
        "managed_fields",
    }
    if set(current) != required_keys or current.get("schema_version") != 1:
        return False
    if current.get("sync_id") != expected.get("sync_id"):
        return False
    if not re.fullmatch(r"[0-9a-f]{64}", str(current.get("content_sha256", ""))):
        return False
    if current.get("managed_fields") != expected.get("managed_fields"):
        return False
    current_source = current.get("source")
    expected_source = expected.get("source")
    if not isinstance(current_source, Mapping) or not isinstance(expected_source, Mapping):
        return False
    if set(current_source) != {"source_id", "feature", "task", "story_id"}:
        return False
    return all(
        current_source.get(field) == expected_source.get(field)
        for field in ("source_id", "feature", "task")
    )


def _validated_issue_keys(issues: Iterable[Mapping[str, Any]]) -> List[str]:
    keys = []
    for issue in issues:
        key = str(issue.get("key", ""))
        if not ISSUE_KEY_RE.fullmatch(key):
            raise ContractError("Jira search returned an invalid issue key")
        keys.append(key)
    return sorted(keys)


def _strict_issue_view(
    value: Any,
    *,
    context: str,
    expected_key: Optional[str] = None,
    expected_project_key: Optional[str] = None,
    expected_label: Optional[str] = None,
) -> Mapping[str, Any]:
    """Validate the identity-bearing fields requested from Jira."""

    if not isinstance(value, Mapping):
        raise JiraError(f"{context} returned a non-object issue")
    key = str(value.get("key", ""))
    if not ISSUE_KEY_RE.fullmatch(key):
        raise JiraError(f"{context} returned an invalid issue key")
    if expected_key is not None and key != expected_key:
        raise JiraError(f"{context} key does not match the requested issue")
    fields = value.get("fields")
    if not isinstance(fields, Mapping):
        raise JiraError(f"{context} returned an invalid fields object")
    project = fields.get("project")
    project_key = str(project.get("key", "")) if isinstance(project, Mapping) else ""
    if not re.fullmatch(r"[A-Z][A-Z0-9_]*", project_key):
        raise JiraError(f"{context} returned an invalid Project field")
    if expected_project_key is not None and project_key != expected_project_key:
        raise JiraError(f"{context} returned an issue from another Project")
    labels = fields.get("labels")
    if not isinstance(labels, list) or any(not isinstance(label, str) for label in labels):
        raise JiraError(f"{context} returned an invalid Labels field")
    if expected_label is not None and expected_label not in labels:
        raise JiraError(f"{context} result does not contain the searched identity label")
    if not isinstance(fields.get("summary"), str):
        raise JiraError(f"{context} returned an invalid Summary field")
    return value


def _jira_value_matches(actual: Any, expected: Any) -> bool:
    if isinstance(expected, Mapping):
        if not isinstance(actual, Mapping):
            return False
        return all(key in actual and _jira_value_matches(actual[key], value) for key, value in expected.items())
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            return False
        unmatched = list(actual)
        for expected_item in expected:
            match_index = next(
                (
                    index
                    for index, actual_item in enumerate(unmatched)
                    if _jira_value_matches(actual_item, expected_item)
                ),
                None,
            )
            if match_index is None:
                return False
            unmatched.pop(match_index)
        return True
    return actual == expected


def _owned_fields_match(issue: Mapping[str, Any], action: Mapping[str, Any]) -> bool:
    fields = issue.get("fields", {})
    if not isinstance(fields, Mapping):
        return False
    owned = action["owned_fields"]
    if fields.get("summary") != owned.get("summary"):
        return False
    if fields.get("description") != owned.get("description"):
        return False
    if action["sync_id"] not in _issue_labels(issue):
        return False
    expected_priority = action.get("priority")
    if expected_priority:
        actual = fields.get("priority")
        if not isinstance(actual, Mapping):
            return False
        actual_id = str(actual.get("id", ""))
        actual_name = str(actual.get("name", ""))
        if actual_id != expected_priority["id"] and actual_name.casefold() != expected_priority[
            "name"
        ].casefold():
            return False
    for field_id, expected_value in action.get("create_only_fields", {}).items():
        if field_id not in fields or not _jira_value_matches(fields[field_id], expected_value):
            return False
    return True


def _plan_digest(plan: Mapping[str, Any]) -> str:
    unsigned = dict(plan)
    unsigned.pop("plan_sha256", None)
    return _sha256_json(unsigned)


def _validate_plan_structure(plan: Mapping[str, Any]) -> None:
    expected_top_level = {
        "schema_version",
        "jira_origin",
        "source",
        "project",
        "issue_type",
        "create_contract_sha256",
        "required_fields",
        "actions",
        "plan_sha256",
    }
    if set(plan) != expected_top_level:
        raise ContractError("Jira sync plan has unsupported top-level fields")
    for digest_field in ("plan_sha256", "create_contract_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", str(plan.get(digest_field, ""))):
            raise ContractError(f"Jira sync plan has invalid {digest_field}")
    if not isinstance(plan.get("jira_origin"), str) or not plan["jira_origin"]:
        raise ContractError("Jira sync plan has no Jira origin")

    source = plan.get("source")
    if not isinstance(source, Mapping) or set(source) != {
        "path",
        "sha256",
        "feature",
        "source_id",
    }:
        raise ContractError("Jira sync plan has an invalid source contract")
    if not isinstance(source.get("path"), str) or not source["path"]:
        raise ContractError("Jira sync plan source path is empty")
    if not re.fullmatch(r"[0-9a-f]{64}", str(source.get("sha256", ""))):
        raise ContractError("Jira sync plan source digest is invalid")
    if not isinstance(source.get("feature"), str) or not source["feature"]:
        raise ContractError("Jira sync plan feature is empty")
    if not SOURCE_ID_RE.fullmatch(str(source.get("source_id", ""))):
        raise ContractError("Jira sync plan source id is invalid")

    project = plan.get("project")
    if not isinstance(project, Mapping) or set(project) != {"id", "key", "name"}:
        raise ContractError("Jira sync plan has an invalid Project contract")
    if not re.fullmatch(r"[A-Z][A-Z0-9_]*", str(project.get("key", ""))):
        raise ContractError("Jira sync plan Project key is invalid")
    if not str(project.get("id", "")) or not str(project.get("name", "")):
        raise ContractError("Jira sync plan Project id or name is empty")

    issue_type = plan.get("issue_type")
    if not isinstance(issue_type, Mapping) or set(issue_type) != {"id", "name"}:
        raise ContractError("Jira sync plan has an invalid issue-type contract")
    if not str(issue_type.get("id", "")) or not str(issue_type.get("name", "")):
        raise ContractError("Jira sync plan issue type is empty")

    required_fields = plan.get("required_fields")
    if not isinstance(required_fields, list):
        raise ContractError("Jira sync plan required fields are invalid")
    required_field_ids = set()
    for descriptor in required_fields:
        if not isinstance(descriptor, Mapping) or set(descriptor) != {
            "id",
            "name",
            "schema",
            "allowed_values",
        }:
            raise ContractError("Jira sync plan has an invalid required-field descriptor")
        field_id = str(descriptor.get("id", ""))
        if (
            not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", field_id)
            or field_id.casefold() in AUTOMATIC_CREATE_FIELDS
            or field_id in required_field_ids
        ):
            raise ContractError(f"Jira sync plan required field id is invalid: {field_id}")
        if not isinstance(descriptor.get("name"), str) or not descriptor["name"]:
            raise ContractError(f"Jira sync plan required field {field_id} has no name")
        if not isinstance(descriptor.get("schema"), Mapping) or not isinstance(
            descriptor.get("allowed_values"), list
        ):
            raise ContractError(f"Jira sync plan required field {field_id} metadata is invalid")
        _validate_json_value(descriptor["allowed_values"], f"plan field {field_id} allowed values")
        required_field_ids.add(field_id)

    actions = plan.get("actions")
    if not isinstance(actions, list) or not actions:
        raise ContractError("Jira sync plan must contain at least one action")
    expected_action_fields = {
        "task_number",
        "title",
        "operation",
        "reason",
        "issue_key",
        "sync_id",
        "content_sha256",
        "owned_fields",
        "create_only_fields",
        "priority",
        "property",
    }
    seen_tasks = set()
    for action in actions:
        if not isinstance(action, Mapping) or set(action) != expected_action_fields:
            raise ContractError("Jira sync plan action has unsupported fields")
        task_number = action.get("task_number")
        if isinstance(task_number, bool) or not isinstance(task_number, int) or task_number <= 0:
            raise ContractError("Jira sync plan action has an invalid task number")
        if task_number in seen_tasks:
            raise ContractError(f"Jira sync plan repeats task {task_number}")
        seen_tasks.add(task_number)
        operation = action.get("operation")
        if operation not in {"create", "adopt", "update", "skip", "conflict"}:
            raise ContractError(f"Jira sync plan has unsupported operation: {operation}")
        if not isinstance(action.get("title"), str) or not isinstance(action.get("reason"), str):
            raise ContractError(f"Jira sync plan task {task_number} text is invalid")
        issue_key = action.get("issue_key")
        if issue_key is not None and not ISSUE_KEY_RE.fullmatch(str(issue_key)):
            raise ContractError(f"Jira sync plan task {task_number} issue key is invalid")
        if operation in {"adopt", "update", "skip"} and issue_key is None:
            raise ContractError(f"Jira sync plan task {task_number} needs an issue key")
        if operation == "create" and issue_key is not None:
            raise ContractError(f"Jira sync plan task {task_number} create must not name an issue key")
        sync_id = str(action.get("sync_id", ""))
        if not SYNC_ID_RE.fullmatch(sync_id):
            raise ContractError(f"Jira sync plan task {task_number} sync id is invalid")
        content_sha256 = str(action.get("content_sha256", ""))
        if not re.fullmatch(r"[0-9a-f]{64}", content_sha256):
            raise ContractError(f"Jira sync plan task {task_number} content digest is invalid")

        owned_fields = action.get("owned_fields")
        if not isinstance(owned_fields, Mapping):
            raise ContractError(f"Jira sync plan task {task_number} owned fields are invalid")
        if set(owned_fields) not in (
            {"summary", "description"},
            {"summary", "description", "priority"},
        ):
            raise ContractError(f"Jira sync plan task {task_number} contains unowned Jira fields")
        summary = owned_fields.get("summary")
        description = owned_fields.get("description")
        if not isinstance(summary, str) or not summary or len(summary) > 255:
            raise ContractError(f"Jira sync plan task {task_number} summary is invalid")
        if not isinstance(description, str) or not description:
            raise ContractError(f"Jira sync plan task {task_number} description is invalid")

        create_only_fields = action.get("create_only_fields")
        if not isinstance(create_only_fields, Mapping):
            raise ContractError(f"Jira sync plan task {task_number} create-only fields are invalid")
        if operation == "create" and set(create_only_fields) != required_field_ids:
            raise ContractError(
                f"Jira sync plan task {task_number} does not answer every required Jira field"
            )
        if operation != "create" and create_only_fields:
            raise ContractError(
                f"Jira sync plan task {task_number} must not update create-only Jira fields"
            )
        _validate_json_value(create_only_fields, f"plan task {task_number} create-only fields")

        priority = action.get("priority")
        if priority is None:
            if "priority" in owned_fields:
                raise ContractError(f"Jira sync plan task {task_number} priority is inconsistent")
        else:
            if not isinstance(priority, Mapping) or set(priority) != {"id", "name"}:
                raise ContractError(f"Jira sync plan task {task_number} priority is invalid")
            if not str(priority.get("id", "")) or not str(priority.get("name", "")):
                raise ContractError(f"Jira sync plan task {task_number} priority is empty")
            if owned_fields.get("priority") != {"id": str(priority["id"])}:
                raise ContractError(f"Jira sync plan task {task_number} priority is inconsistent")

        calculated_content = _sha256_json(
            {
                "summary": summary,
                "description": description,
                "priority": priority,
                "sync_id": sync_id,
            }
        )
        if calculated_content != content_sha256:
            raise ContractError(f"Jira sync plan task {task_number} content digest does not match")

        property_value = action.get("property")
        if not isinstance(property_value, Mapping):
            raise ContractError(f"Jira sync plan task {task_number} property is invalid")
        if set(property_value) != {
            "schema_version",
            "sync_id",
            "content_sha256",
            "source",
            "managed_fields",
        } or property_value.get("schema_version") != 1:
            raise ContractError(f"Jira sync plan task {task_number} property schema is invalid")
        if property_value.get("sync_id") != sync_id or property_value.get(
            "content_sha256"
        ) != content_sha256:
            raise ContractError(f"Jira sync plan task {task_number} property identity is invalid")
        if property_value.get("managed_fields") != [
            "summary",
            "description",
            "priority",
            "labels:sync_id",
        ]:
            raise ContractError(f"Jira sync plan task {task_number} ownership contract is invalid")
        property_source = property_value.get("source")
        if not isinstance(property_source, Mapping) or set(property_source) != {
            "source_id",
            "feature",
            "task",
            "story_id",
        }:
            raise ContractError(f"Jira sync plan task {task_number} property source is invalid")
        if (
            property_source.get("source_id") != source["source_id"]
            or property_source.get("feature") != source["feature"]
            or property_source.get("task") != task_number
        ):
            raise ContractError(f"Jira sync plan task {task_number} property source does not match")


def build_sync_plan(
    client: Any,
    document: TasksDocument,
    project_key: str,
    issue_type_name: str = DEFAULT_ISSUE_TYPE,
    field_answers: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a GET-only, serializable plan for an exact Jira project key."""

    project, issue_type, create_fields, priorities = _resolve_create_context(
        client, project_key, issue_type_name
    )
    issue_type_id = str(issue_type["id"])
    priority_key = "priority" if "priority" in create_fields else None
    create_contract_sha256 = _create_contract_sha256(issue_type, create_fields, priorities)
    required_fields = _required_field_descriptors(create_fields)
    answer_defaults, task_answer_overrides = _normalized_field_answers(
        field_answers,
        required_fields,
        (task.number for task in document.tasks),
    )

    resolved_sync_ids: Dict[int, str] = {}
    sync_id_owners: Dict[str, int] = {}
    issue_key_owners: Dict[str, int] = {}
    for task in document.tasks:
        sync_id = task.sync_id or _stable_sync_id(project_key, document, task)
        previous_task = sync_id_owners.get(sync_id)
        if previous_task is not None:
            raise ContractError(
                f"duplicate Jira-Sync-ID {sync_id}: tasks {previous_task} and {task.number}"
            )
        sync_id_owners[sync_id] = task.number
        resolved_sync_ids[task.number] = sync_id
        effective_issue_key = task.jira_key or task.legacy_jira_key
        if effective_issue_key:
            previous_task = issue_key_owners.get(effective_issue_key)
            if previous_task is not None:
                raise ContractError(
                    f"duplicate Jira issue key {effective_issue_key}: tasks "
                    f"{previous_task} and {task.number}"
                )
            issue_key_owners[effective_issue_key] = task.number

    actions: List[Dict[str, Any]] = []
    for task in document.tasks:
        sync_id = resolved_sync_ids[task.number]
        owned_fields, priority, content_hash, expected_property = _managed_action_content(
            document,
            task,
            sync_id,
            priorities,
            priority_enabled=bool(priority_key),
        )
        if priority_key and priority is None:
            required = bool(create_fields.get(priority_key, {}).get("required"))
            if required:
                raise ContractError(f"required Jira priority is unavailable: {task.priority}")

        existing: Optional[Mapping[str, Any]] = None
        operation: str
        reason: str
        legacy_adoption = task.jira_key is None and task.legacy_jira_key is not None
        issue_key = task.jira_key or task.legacy_jira_key
        matches = list(client.search_issues_by_label(project_key, sync_id))
        match_keys = _validated_issue_keys(matches)
        if issue_key:
            existing = client.get_issue(issue_key)
            if len(matches) > 1:
                operation = "conflict"
                reason = (
                    f"stable marker {sync_id} matches multiple Jira issues: "
                    + ", ".join(match_keys)
                )
            elif len(matches) == 1 and match_keys[0] != issue_key:
                operation = "conflict"
                reason = (
                    f"recorded Jira issue {issue_key} conflicts with marker match {match_keys[0]}"
                )
            elif existing is None:
                operation = "conflict"
                prefix = "legacy" if legacy_adoption else "recorded"
                reason = f"{prefix} Jira issue {issue_key} does not exist or is not visible"
            elif _issue_project_key(existing) != project_key:
                operation = "conflict"
                prefix = "legacy" if legacy_adoption else "recorded"
                reason = f"{prefix} Jira issue {issue_key} belongs to another project"
            else:
                operation = "update"
                reason = (
                    "legacy Jira issue needs explicit ownership adoption"
                    if legacy_adoption
                    else "recorded Jira issue needs reconciliation"
                )
        else:
            if len(matches) > 1:
                operation = "conflict"
                reason = (
                    f"stable marker {sync_id} matches multiple Jira issues: "
                    + ", ".join(match_keys)
                )
            elif len(matches) == 1:
                existing = matches[0]
                issue_key = str(existing.get("key", ""))
                if not ISSUE_KEY_RE.fullmatch(issue_key):
                    operation = "conflict"
                    reason = "stable marker matched an issue without a valid Jira key"
                else:
                    operation = "update"
                    reason = "stable marker matched an existing Jira issue"
            else:
                operation = "create"
                reason = "no Jira issue has this stable marker"

        current_property = None
        if existing is not None and operation != "conflict":
            current_labels = [
                label for label in _issue_labels(existing) if label.startswith("tgd-sync-")
            ]
            other_markers = [label for label in current_labels if label != sync_id]
            if other_markers:
                operation = "conflict"
                reason = "Jira issue already belongs to a different tGD sync identity"
            else:
                current_property = client.get_issue_property(str(existing.get("key", "")), PROPERTY_KEY)
                property_proven = False
                if isinstance(current_property, Mapping):
                    property_sync_id = current_property.get("sync_id")
                    if property_sync_id and property_sync_id != sync_id:
                        operation = "conflict"
                        reason = "Jira issue property has a different tGD sync identity"
                    property_source = current_property.get("source")
                    property_source_id = (
                        property_source.get("source_id")
                        if isinstance(property_source, Mapping)
                        else None
                    )
                    if property_source_id and property_source_id != document.source_id:
                        operation = "conflict"
                        reason = "Jira issue property belongs to a different TASKS source"
                    elif operation != "conflict" and not _property_proves_identity(
                        current_property, expected_property
                    ):
                        operation = "conflict"
                        reason = "Jira issue has an incomplete or untrusted tGD sync property"
                    else:
                        property_proven = operation != "conflict"
                elif current_property is not None:
                    operation = "conflict"
                    reason = "Jira issue returned an invalid tGD sync property"
                label_proven = sync_id in current_labels
                fields_match = _owned_fields_match(
                    existing,
                    {
                        "owned_fields": owned_fields,
                        "priority": priority,
                        "sync_id": sync_id,
                    },
                )
                if (
                    operation != "conflict"
                    and label_proven
                    and not property_proven
                    and not fields_match
                ):
                    operation = "conflict"
                    reason = (
                        "label-only tGD identity does not match the managed TASKS.md fields"
                    )
                identity_proven = property_proven or (label_proven and fields_match)
                if operation != "conflict" and task.jira_key and not identity_proven:
                    operation = "conflict"
                    reason = (
                        f"recorded Jira issue {task.jira_key} has no matching tGD sync identity "
                        "that satisfies the trusted ownership contract"
                    )
                if operation != "conflict" and legacy_adoption and not identity_proven:
                    if current_property is None and not current_labels:
                        operation = "adopt"
                        reason = (
                            f"legacy heading key {issue_key} requires explicit digest-confirmed adoption"
                        )
                    else:
                        operation = "conflict"
                        reason = "legacy Jira issue ownership cannot be proven or safely adopted"
                if (
                    operation != "conflict"
                    and (task.jira_key or legacy_adoption)
                    and label_proven
                    and match_keys != [issue_key]
                ):
                    operation = "conflict"
                    reason = (
                        f"Jira issue {issue_key} is not the unique searchable marker match"
                    )
                if (
                    operation != "conflict"
                    and current_property == expected_property
                    and _owned_fields_match(
                        existing,
                        {
                            "owned_fields": owned_fields,
                            "priority": priority,
                            "sync_id": sync_id,
                        },
                    )
                ):
                    operation = "skip"
                    reason = "Jira issue already matches the TASKS.md content"

        create_only_fields = (
            _create_only_fields_for_task(
                required_fields,
                answer_defaults,
                task_answer_overrides,
                task.number,
            )
            if operation == "create"
            else {}
        )
        actions.append(
            {
                "task_number": task.number,
                "title": task.title,
                "operation": operation,
                "reason": reason,
                "issue_key": issue_key,
                "sync_id": sync_id,
                "content_sha256": content_hash,
                "owned_fields": owned_fields,
                "create_only_fields": create_only_fields,
                "priority": priority,
                "property": expected_property,
            }
        )

    plan: Dict[str, Any] = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "jira_origin": str(client.base_url).rstrip("/"),
        "source": {
            "path": str(document.path),
            "sha256": document.source_sha256,
            "feature": document.feature_name,
            "source_id": document.source_id,
        },
        "project": {"id": project["id"], "key": project["key"], "name": project["name"]},
        "issue_type": issue_type,
        "create_contract_sha256": create_contract_sha256,
        "required_fields": required_fields,
        "actions": actions,
    }
    plan["plan_sha256"] = _plan_digest(plan)
    return plan


def _apply_managed_update(
    client: Any,
    issue_key: str,
    issue: Mapping[str, Any],
    action: Mapping[str, Any],
) -> None:
    """Update owned fields and atomically add only the owned sync label."""

    sync_id = str(action["sync_id"])
    label_to_add = None if sync_id in _issue_labels(issue) else sync_id
    client.update_issue(
        issue_key,
        dict(action["owned_fields"]),
        label_to_add=label_to_add,
    )


def _create_fields(plan: Mapping[str, Any], action: Mapping[str, Any]) -> Dict[str, Any]:
    fields = dict(action["owned_fields"])
    fields.update(dict(action.get("create_only_fields", {})))
    fields["project"] = {"key": plan["project"]["key"]}
    fields["issuetype"] = {"id": plan["issue_type"]["id"]}
    fields["labels"] = [action["sync_id"]]
    return fields


def _verify_issue(
    client: Any,
    plan: Mapping[str, Any],
    action: Mapping[str, Any],
    issue_key: str,
) -> None:
    issue = client.get_issue(
        issue_key,
        extra_fields=tuple(action.get("create_only_fields", {})),
    )
    if issue is None:
        raise JiraError(f"verification failed: Jira issue {issue_key} is not readable")
    if _issue_project_key(issue) != plan["project"]["key"]:
        raise JiraError(f"verification failed: Jira issue {issue_key} is in the wrong project")
    sync_markers = [
        label for label in _issue_labels(issue) if label.startswith("tgd-sync-")
    ]
    if len(sync_markers) != 1 or sync_markers[0] != action["sync_id"]:
        raise JiraError(
            f"verification failed: Jira issue {issue_key} does not have exactly one tGD identity"
        )
    if not _owned_fields_match(issue, action):
        raise JiraError(f"verification failed: Jira issue {issue_key} fields do not match")
    remote_property = client.get_issue_property(issue_key, PROPERTY_KEY)
    if remote_property != action["property"]:
        raise JiraError(f"verification failed: Jira issue {issue_key} sync property does not match")


def _owned_issue_for_mutation(
    client: Any,
    project_key: str,
    action: Mapping[str, Any],
    issue_key: str,
    require_fields_match: bool = False,
) -> Mapping[str, Any]:
    """Re-check identity immediately before mutating an existing Jira issue."""

    issue = client.get_issue(
        issue_key,
        extra_fields=tuple(action.get("create_only_fields", {})),
    )
    if issue is None:
        raise JiraError(f"Jira issue {issue_key} is no longer readable")
    if _issue_project_key(issue) != project_key:
        raise JiraError(f"Jira issue {issue_key} belongs to another project")
    labels = _issue_labels(issue)
    expected_sync_id = str(action["sync_id"])
    other_markers = [
        label
        for label in labels
        if label.startswith("tgd-sync-") and label != expected_sync_id
    ]
    if other_markers:
        raise JiraError(f"Jira issue {issue_key} has another tGD sync marker")
    current_property = client.get_issue_property(issue_key, PROPERTY_KEY)
    if current_property is not None and not isinstance(current_property, Mapping):
        raise JiraError(f"Jira issue {issue_key} returned an invalid tGD sync property")
    property_proven = isinstance(current_property, Mapping) and _property_proves_identity(
        current_property, action["property"]
    )
    fields_match = _owned_fields_match(issue, action)
    label_proven = expected_sync_id in labels
    if isinstance(current_property, Mapping) and not property_proven:
        raise JiraError(f"Jira issue {issue_key} has an incomplete or untrusted tGD property")
    if not property_proven and not (label_proven and fields_match):
        raise JiraError(f"Jira issue {issue_key} no longer proves the planned tGD identity")
    if require_fields_match and not fields_match:
        raise JiraError(f"Jira issue {issue_key} does not match the planned create fields")
    return issue


def _unowned_issue_for_adoption(
    client: Any,
    project_key: str,
    issue_key: str,
) -> Mapping[str, Any]:
    """Re-check that a legacy issue is still unowned immediately before adoption."""

    issue = client.get_issue(issue_key)
    if issue is None:
        raise JiraError(f"legacy Jira issue {issue_key} is no longer readable")
    if _issue_project_key(issue) != project_key:
        raise JiraError(f"legacy Jira issue {issue_key} belongs to another project")
    markers = [label for label in _issue_labels(issue) if label.startswith("tgd-sync-")]
    if markers:
        raise JiraError(f"legacy Jira issue {issue_key} acquired a tGD sync marker; re-plan")
    if client.get_issue_property(issue_key, PROPERTY_KEY) is not None:
        raise JiraError(f"legacy Jira issue {issue_key} acquired a tGD sync property; re-plan")
    return issue


def _atomic_write(path: Path, text: str, expected_sha256: Optional[str] = None) -> None:
    stat_result = path.stat()
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_name, stat_result.st_mode & 0o777)
        if expected_sha256 is not None:
            if _sha256_bytes(path.read_bytes()) != expected_sha256:
                raise ContractError("TASKS.md changed immediately before atomic writeback")
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def _locked_writeback(
    path: Path,
    expected_sha256: str,
    links: Mapping[int, Tuple[str, str]],
) -> bool:
    """Serialize cooperating writers and re-check content immediately before replace."""

    lock_directory = Path(tempfile.gettempdir()) / f"tgd-jira-sync-locks-v1-{os.getuid()}"
    try:
        os.mkdir(lock_directory, 0o700)
    except FileExistsError:
        pass
    directory_stat = os.lstat(lock_directory)
    if (
        not stat.S_ISDIR(directory_stat.st_mode)
        or stat.S_ISLNK(directory_stat.st_mode)
        or directory_stat.st_uid != os.getuid()
        or stat.S_IMODE(directory_stat.st_mode) != 0o700
    ):
        raise ContractError("Jira writeback lock directory is not private and user-owned")
    lock_name = _sha256_bytes(str(path.resolve()).encode("utf-8")) + ".lock"
    lock_path = lock_directory / lock_name
    lock_flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0) | getattr(
        os, "O_NOFOLLOW", 0
    )
    lock_descriptor = os.open(str(lock_path), lock_flags, 0o600)
    lock_stat = os.fstat(lock_descriptor)
    if not stat.S_ISREG(lock_stat.st_mode) or lock_stat.st_uid != os.getuid():
        os.close(lock_descriptor)
        raise ContractError("Jira writeback lock file is not safe")
    with os.fdopen(lock_descriptor, "a+") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        current_bytes = path.read_bytes()
        if _sha256_bytes(current_bytes) != expected_sha256:
            raise ContractError("TASKS.md changed during apply; Jira links need local writeback")
        current_text = current_bytes.decode("utf-8")
        updated_text = write_jira_links(current_text, links)
        changed = updated_text != current_text
        if changed:
            _atomic_write(path, updated_text, expected_sha256=expected_sha256)
        return changed


def apply_sync_plan(
    client: Any,
    plan: Mapping[str, Any],
    confirmation: Optional[str],
) -> Dict[str, Any]:
    """Apply an exact reviewed plan, verify Jira, then atomically write TASKS.md."""

    expected_digest = str(plan.get("plan_sha256", ""))
    if not confirmation or not hmac.compare_digest(confirmation, expected_digest):
        raise ContractError("apply confirmation must exactly match plan_sha256")
    if not hmac.compare_digest(_plan_digest(plan), expected_digest):
        raise ContractError("plan content does not match its confirmation digest")
    if plan.get("schema_version") != PLAN_SCHEMA_VERSION:
        raise ContractError("unsupported Jira sync plan schema")
    _validate_plan_structure(plan)
    if any(action["operation"] == "conflict" for action in plan["actions"]):
        raise ContractError("plan contains conflict actions; resolve them and create a new dry-run")
    if str(client.base_url).rstrip("/") != str(plan.get("jira_origin", "")).rstrip("/"):
        raise ContractError("Jira origin changed after dry-run")

    source = plan.get("source", {})
    source_path = Path(str(source.get("path", ""))).expanduser().resolve()
    try:
        before_bytes = source_path.read_bytes()
    except OSError as exc:
        raise ContractError(f"cannot read TASKS.md before apply: {exc}") from exc
    if _sha256_bytes(before_bytes) != source.get("sha256"):
        raise ContractError("TASKS.md changed after dry-run; create a new plan")

    live_document = parse_tasks_file(source_path)
    if live_document.source_sha256 != source.get("sha256"):
        raise ContractError("TASKS.md changed while apply was validating it")
    if live_document.feature_name != source.get("feature"):
        raise ContractError("TASKS.md feature changed after dry-run")
    if live_document.source_id != source.get("source_id"):
        raise ContractError("TASKS.md Jira source id changed after dry-run")
    actions_by_task = {int(action["task_number"]): action for action in plan["actions"]}
    if list(actions_by_task) != [task.number for task in live_document.tasks]:
        raise ContractError("Jira sync plan tasks do not match TASKS.md")
    project_key = str(plan["project"]["key"])
    for task in live_document.tasks:
        action = actions_by_task[task.number]
        if action["title"] != task.title:
            raise ContractError(f"Jira sync plan task {task.number} title does not match TASKS.md")
        expected_sync_id = task.sync_id or _stable_sync_id(project_key, live_document, task)
        if action["sync_id"] != expected_sync_id:
            raise ContractError(f"Jira sync plan task {task.number} identity does not match TASKS.md")
        expected_issue_key = task.jira_key or task.legacy_jira_key
        if expected_issue_key and action.get("issue_key") != expected_issue_key:
            raise ContractError(f"Jira sync plan task {task.number} issue key does not match TASKS.md")
        if action["operation"] == "adopt" and (
            task.jira_key is not None
            or task.legacy_jira_key is None
            or action.get("issue_key") != task.legacy_jira_key
        ):
            raise ContractError(
                f"Jira sync plan task {task.number} adoption is not backed by a legacy heading key"
            )
        if task.legacy_jira_key and task.jira_key is None and action["operation"] == "create":
            raise ContractError(
                f"Jira sync plan task {task.number} must not create over a legacy heading key"
            )
        if action["property"]["source"].get("story_id") != task.story_id:
            raise ContractError(f"Jira sync plan task {task.number} Story ID does not match TASKS.md")

    live_project = next(
        (choice for choice in project_choices(client) if choice["key"] == project_key),
        None,
    )
    if live_project is None or live_project["id"] != str(plan["project"].get("id", "")):
        raise ContractError("selected Jira project changed after dry-run")

    live_issue_type = next(
        (
            item
            for item in client.list_issue_types(project_key)
            if str(item.get("id", "")) == str(plan["issue_type"].get("id", ""))
            and str(item.get("name", "")) == str(plan["issue_type"].get("name", ""))
        ),
        None,
    )
    if live_issue_type is None:
        raise ContractError("selected Jira issue type changed after dry-run")
    live_fields = client.get_create_fields(project_key, str(live_issue_type.get("id", "")))
    live_priorities = client.list_priorities() if "priority" in live_fields else []
    if _create_contract_sha256(live_issue_type, live_fields, live_priorities) != plan.get(
        "create_contract_sha256"
    ):
        raise ContractError("Jira create-field metadata changed after dry-run")
    live_required_fields = _required_field_descriptors(live_fields)
    if live_required_fields != plan.get("required_fields"):
        raise ContractError("Jira required-field metadata changed after dry-run")
    for task in live_document.tasks:
        action = actions_by_task[task.number]
        owned_fields, priority, content_sha256, property_value = _managed_action_content(
            live_document,
            task,
            str(action["sync_id"]),
            live_priorities,
            priority_enabled="priority" in live_fields,
        )
        if (
            action["owned_fields"] != owned_fields
            or action["priority"] != priority
            or action["content_sha256"] != content_sha256
            or action["property"] != property_value
        ):
            raise ContractError(
                f"Jira sync plan task {task.number} managed content does not match TASKS.md"
            )
        if action["operation"] == "create":
            normalized_defaults, _task_values = _normalized_field_answers(
                {"defaults": action["create_only_fields"], "tasks": {}},
                live_required_fields,
                [task.number],
            )
            normalized_create_fields = _create_only_fields_for_task(
                live_required_fields,
                normalized_defaults,
                {},
                task.number,
            )
            if normalized_create_fields != action["create_only_fields"]:
                raise ContractError(
                    f"Jira sync plan task {task.number} required field answers are not canonical"
                )

    report: Dict[str, Any] = {
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "conflicts": 0,
        "remote_unknown": 0,
        "failed": 0,
        "writeback_pending": 0,
        "aborted": 0,
        "errors": [],
        "links": [],
        "unattempted": [],
    }
    verified_links: Dict[int, Tuple[str, str]] = {}

    plan_actions = list(plan.get("actions", []))
    for action_index, raw_action in enumerate(plan_actions):
        action = dict(raw_action)
        operation = action.get("operation")
        task_number = int(action.get("task_number"))
        if operation == "conflict":
            report["conflicts"] += 1
            report["failed"] += 1
            report["errors"].append(f"Task {task_number}: {action.get('reason', 'conflict')}")
            continue
        issue_key = str(action.get("issue_key") or "")
        final_operation = operation
        try:
            if operation == "create":
                matches = list(client.search_issues_by_label(project_key, action["sync_id"]))
                if len(matches) > 1:
                    keys = ", ".join(_validated_issue_keys(matches))
                    raise JiraError(
                        f"multiple Jira issues appeared for the stable sync marker: {keys}"
                    )
                if len(matches) == 1:
                    issue_key = str(matches[0].get("key", ""))
                    _owned_issue_for_mutation(
                        client,
                        project_key,
                        action,
                        issue_key,
                        require_fields_match=True,
                    )
                    final_operation = "update"
                else:
                    try:
                        issue_key = str(client.create_issue(_create_fields(plan, action)))
                    except AmbiguousMutation:
                        try:
                            reconciled = list(
                                client.search_issues_by_label(project_key, action["sync_id"])
                            )
                            reconciled_keys = _validated_issue_keys(reconciled)
                        except JiraBatchAbort as exc:
                            raise RemoteUnknownBatchAbort(
                                "Jira create result is unknown and systemic reconciliation failed"
                            ) from exc
                        except (ContractError, JiraError, KeyError, TypeError, ValueError) as exc:
                            raise RemoteUnknown(
                                "Jira create result is unknown and reconciliation was invalid"
                            ) from exc
                        if len(reconciled) != 1:
                            keys = ", ".join(reconciled_keys) or "none"
                            raise RemoteUnknown(
                                "Jira create result is unknown; marker matches: "
                                f"{keys}; no safe automatic retry was attempted"
                            )
                        issue_key = str(reconciled[0].get("key", ""))
                        try:
                            _owned_issue_for_mutation(
                                client,
                                project_key,
                                action,
                                issue_key,
                                require_fields_match=True,
                            )
                        except JiraBatchAbort as exc:
                            raise RemoteUnknownBatchAbort(
                                "Jira create result is unknown and ownership reconciliation failed"
                            ) from exc
                        except (ContractError, JiraError, KeyError, TypeError, ValueError) as exc:
                            raise RemoteUnknown(
                                "Jira create result matched an unsafe reconciliation candidate"
                            ) from exc
                        final_operation = "update"
            elif operation == "adopt":
                matches = list(client.search_issues_by_label(project_key, action["sync_id"]))
                if matches:
                    keys = ", ".join(_validated_issue_keys(matches))
                    raise JiraError(
                        "legacy adoption is no longer unowned; stable marker matches: "
                        f"{keys}; create a new dry-run"
                    )
                live_issue = _unowned_issue_for_adoption(client, project_key, issue_key)
                _apply_managed_update(client, issue_key, live_issue, action)
            elif operation == "update":
                live_issue = _owned_issue_for_mutation(
                    client, project_key, action, issue_key
                )
                _apply_managed_update(client, issue_key, live_issue, action)
            elif operation == "skip":
                _owned_issue_for_mutation(client, project_key, action, issue_key)
            else:
                raise ContractError(f"unsupported plan operation: {operation}")

            if operation != "skip":
                client.set_issue_property(issue_key, PROPERTY_KEY, action["property"])
            try:
                _verify_issue(client, plan, action, issue_key)
            except JiraBatchAbort as exc:
                if operation != "skip":
                    raise RemoteUnknownBatchAbort(
                        f"Jira issue {issue_key} was mutated, but systemic verification failed"
                    ) from exc
                raise
            except JiraError as exc:
                if operation != "skip":
                    raise RemoteUnknown(
                        f"Jira issue {issue_key} was mutated, but verification is inconclusive"
                    ) from exc
                raise
            try:
                reconciled_keys = set(
                    _validated_issue_keys(
                        client.search_issues_by_label(project_key, action["sync_id"])
                    )
                )
            except JiraBatchAbort as exc:
                raise RemoteUnknownBatchAbort(
                    f"Jira issue {issue_key} was verified, but systemic uniqueness lookup failed"
                ) from exc
            except (ContractError, JiraError, KeyError, TypeError, ValueError) as exc:
                raise RemoteUnknown(
                    f"Jira issue {issue_key} was verified, but marker uniqueness is unknown"
                ) from exc
            if reconciled_keys != {issue_key}:
                rendered = ", ".join(sorted(key for key in reconciled_keys if key)) or "none"
                raise RemoteUnknown(
                    f"Jira issue {issue_key} was verified, but stable marker matches: {rendered}"
                )
            verified_links[task_number] = (issue_key, str(action["sync_id"]))
            report["links"].append(
                {
                    "task_number": task_number,
                    "operation": final_operation,
                    "issue_key": issue_key,
                    "sync_id": action["sync_id"],
                    "writeback": "pending",
                }
            )
            if final_operation == "create":
                report["created"] += 1
            elif final_operation in {"adopt", "update"}:
                report["updated"] += 1
            else:
                report["skipped"] += 1
        except RemoteUnknownBatchAbort as exc:
            report["remote_unknown"] += 1
            report["failed"] += 1
            report["errors"].append(f"Task {task_number}: remote unknown; batch aborted: {exc}")
            remaining = plan_actions[action_index + 1 :]
            report["aborted"] = len(remaining)
            report["unattempted"] = [
                {
                    "task_number": int(item["task_number"]),
                    "operation": item["operation"],
                    "reason": "not attempted after systemic Jira reconciliation failure",
                }
                for item in remaining
            ]
            break
        except JiraBatchAbort as exc:
            report["failed"] += 1
            report["errors"].append(f"Task {task_number}: batch aborted: {exc}")
            remaining = plan_actions[action_index + 1 :]
            report["aborted"] = len(remaining)
            report["unattempted"] = [
                {
                    "task_number": int(item["task_number"]),
                    "operation": item["operation"],
                    "reason": "not attempted after systemic Jira failure",
                }
                for item in remaining
            ]
            break
        except (RemoteUnknown, AmbiguousMutation) as exc:
            report["remote_unknown"] += 1
            report["failed"] += 1
            report["errors"].append(f"Task {task_number}: {exc}")
        except (ContractError, JiraError, KeyError, TypeError, ValueError) as exc:
            report["failed"] += 1
            report["errors"].append(f"Task {task_number}: {exc}")

    if verified_links:
        try:
            changed = _locked_writeback(
                source_path,
                str(source.get("sha256")),
                verified_links,
            )
            for link in report["links"]:
                link["writeback"] = "written" if changed else "already-current"
        except (OSError, UnicodeDecodeError, ContractError) as exc:
            pending = len(verified_links)
            report["writeback_pending"] = pending
            report["failed"] += pending
            report["errors"].append(f"remote verified, local writeback pending: {exc}")
    return report


class _SameOriginRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        old = urllib.parse.urlsplit(req.full_url)
        new = urllib.parse.urlsplit(newurl)
        if (old.scheme, old.hostname, old.port) != (new.scheme, new.hostname, new.port):
            raise JiraError("Jira refused a cross-origin redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _sanitize_message(message: str, token: str) -> str:
    sanitized = message.replace(token, "<redacted>") if token else message
    sanitized = SECRET_RE.sub(r"\1<redacted>", sanitized)
    return "".join(
        character
        for character in sanitized
        if character in {"\n", "\t"} or (ord(character) >= 32 and ord(character) != 127)
    )


class JiraClient:
    """Minimal Jira Data Center Platform REST API v2 client."""

    def __init__(
        self,
        base_url: str,
        token: str,
        ca_bundle: Optional[str] = None,
        timeout: float = 20.0,
        allow_insecure_localhost_for_tests: bool = False,
    ) -> None:
        parsed = urllib.parse.urlsplit(base_url.rstrip("/"))
        local_hosts = {"localhost", "127.0.0.1", "::1"}
        insecure_test_origin = (
            allow_insecure_localhost_for_tests
            and parsed.scheme == "http"
            and parsed.hostname in local_hosts
        )
        if parsed.scheme != "https" and not insecure_test_origin:
            raise ContractError("JIRA_URL must use HTTPS")
        if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ContractError("JIRA_URL must be a clean Jira origin without credentials or query data")
        if not token:
            raise ContractError("JIRA_TOKEN is required")
        if len(token) > 4096 or any(ord(character) < 33 or ord(character) > 126 for character in token):
            raise ContractError("JIRA_TOKEN contains invalid characters")
        self.base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout
        context = ssl.create_default_context(cafile=ca_bundle) if ca_bundle else ssl.create_default_context()
        self._opener = urllib.request.build_opener(
            urllib.request.ProxyHandler(),
            urllib.request.HTTPSHandler(context=context),
            _SameOriginRedirectHandler(),
        )

    def _request(
        self,
        method: str,
        path: str,
        payload: Optional[Mapping[str, Any]] = None,
        allow_not_found: bool = False,
    ) -> Any:
        url = self.base_url + path
        body = _canonical_json(payload) if payload is not None else None
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._token}",
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        attempts = 2 if method == "GET" else 1
        for attempt in range(attempts):
            try:
                with self._opener.open(request, timeout=self._timeout) as response:
                    content = response.read()
                    if not content:
                        return None
                    return json.loads(content.decode("utf-8"))
            except urllib.error.HTTPError as exc:
                if allow_not_found and exc.code == 404:
                    return _NOT_FOUND
                retryable = exc.code in {429, 502, 503, 504}
                if method == "GET" and retryable and attempt + 1 < attempts:
                    retry_after = exc.headers.get("Retry-After", "0")
                    try:
                        delay = min(max(float(retry_after), 0.0), 2.0)
                    except ValueError:
                        delay = 0.0
                    if delay:
                        time.sleep(delay)
                    continue
                try:
                    response_text = exc.read(4096).decode("utf-8", errors="replace")
                except Exception:
                    response_text = ""
                detail = _sanitize_message(response_text, self._token).strip()
                message = f"Jira API {method} {path} failed with HTTP {exc.code}"
                if detail:
                    message += f": {detail}"
                if exc.code in {401, 403, 429}:
                    raise JiraBatchAbort(message) from exc
                if method in {"POST", "PUT"} and exc.code >= 500:
                    raise AmbiguousMutation(message) from exc
                if method == "GET" and exc.code >= 500:
                    raise JiraBatchAbort(message) from exc
                raise JiraError(message) from exc
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                message = _sanitize_message(str(exc), self._token)
                if method == "GET" and attempt + 1 < attempts:
                    continue
                if method in {"POST", "PUT"}:
                    raise AmbiguousMutation(f"Jira mutation connection ended: {message}") from exc
                if method == "GET":
                    raise JiraBatchAbort(f"Jira connection failed: {message}") from exc
                raise JiraError(f"Jira connection failed: {message}") from exc
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                if method in {"POST", "PUT"}:
                    raise AmbiguousMutation(
                        f"Jira mutation returned invalid JSON for {method} {path}"
                    ) from exc
                raise JiraError(f"Jira returned invalid JSON for {method} {path}") from exc
        raise JiraError(f"Jira request failed: {method} {path}")

    def list_projects(self) -> List[Mapping[str, Any]]:
        data = self._request("GET", "/rest/api/2/project")
        if isinstance(data, list):
            return data
        if isinstance(data, Mapping) and isinstance(data.get("values"), list):
            return data["values"]
        raise JiraError("Jira project list response has an unsupported shape")

    def _create_meta(
        self, project_key: str, issue_type_id: Optional[str] = None
    ) -> Mapping[str, Any]:
        query: Dict[str, str] = {
            "projectKeys": project_key,
            "expand": "projects.issuetypes.fields" if issue_type_id else "projects.issuetypes",
        }
        if issue_type_id:
            query["issuetypeIds"] = issue_type_id
        path = "/rest/api/2/issue/createmeta?" + urllib.parse.urlencode(query)
        data = self._request("GET", path)
        if not isinstance(data, Mapping):
            raise JiraError("Jira create metadata response is not an object")
        return data

    def _paged_values(self, base_path: str) -> Optional[List[Mapping[str, Any]]]:
        """Read Jira's paged createmeta resources, or None when unsupported."""

        values: List[Mapping[str, Any]] = []
        start_at = 0
        for _page in range(200):
            separator = "&" if "?" in base_path else "?"
            path = (
                f"{base_path}{separator}"
                + urllib.parse.urlencode({"startAt": start_at, "maxResults": 50})
            )
            data = self._request("GET", path, allow_not_found=True)
            if data is _NOT_FOUND:
                return None
            if not isinstance(data, Mapping) or not isinstance(data.get("values"), list):
                raise JiraError("Jira paged create metadata response has an unsupported shape")
            page_values = data["values"]
            for item in page_values:
                if not isinstance(item, Mapping):
                    raise JiraError("Jira create metadata contains a non-object value")
                values.append(item)
            total = data.get("total")
            is_last = bool(data.get("isLast"))
            next_start = start_at + len(page_values)
            if is_last or (isinstance(total, int) and next_start >= total):
                return values
            if not page_values:
                raise JiraError("Jira create metadata pagination did not advance")
            start_at = next_start
        raise JiraError("Jira create metadata exceeded the pagination safety limit")

    def list_issue_types(self, project_key: str) -> List[Mapping[str, Any]]:
        encoded_project = urllib.parse.quote(project_key, safe="")
        modern = self._paged_values(
            f"/rest/api/2/issue/createmeta/{encoded_project}/issuetypes"
        )
        if modern is not None:
            return modern

        # Compatibility fallback for Jira versions earlier than 8.4. Jira 9+
        # removes this legacy query-form endpoint, so the paged path is always
        # attempted first.
        data = self._create_meta(project_key)
        projects = data.get("projects", [])
        if not isinstance(projects, list) or not projects:
            return []
        issue_types = projects[0].get("issuetypes", [])
        return issue_types if isinstance(issue_types, list) else []

    def get_create_fields(self, project_key: str, issue_type_id: str) -> Mapping[str, Any]:
        encoded_project = urllib.parse.quote(project_key, safe="")
        encoded_issue_type = urllib.parse.quote(issue_type_id, safe="")
        modern = self._paged_values(
            f"/rest/api/2/issue/createmeta/{encoded_project}/issuetypes/{encoded_issue_type}"
        )
        if modern is not None:
            fields: Dict[str, Any] = {}
            for metadata in modern:
                field_id = str(metadata.get("fieldId", "")).strip()
                if not field_id:
                    raise JiraError("Jira create field metadata is missing fieldId")
                if field_id in fields:
                    raise JiraError(f"Jira create field metadata repeats {field_id}")
                fields[field_id] = dict(metadata)
            return fields

        # Jira versions earlier than 8.4 expose fields through expanded legacy
        # createmeta. Keep the fallback read-only and fail closed on odd shapes.
        data = self._create_meta(project_key, issue_type_id)
        projects = data.get("projects", [])
        if not isinstance(projects, list) or not projects:
            return {}
        issue_types = projects[0].get("issuetypes", [])
        if not isinstance(issue_types, list):
            return {}
        for issue_type in issue_types:
            if str(issue_type.get("id", "")) == issue_type_id:
                fields = issue_type.get("fields", {})
                return fields if isinstance(fields, Mapping) else {}
        return {}

    def list_priorities(self) -> List[Mapping[str, Any]]:
        data = self._request("GET", "/rest/api/2/priority")
        return data if isinstance(data, list) else []

    def search_issues_by_label(self, project_key: str, label: str) -> List[Mapping[str, Any]]:
        if not SYNC_ID_RE.fullmatch(label):
            raise ContractError(f"unsafe Jira label: {label}")
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", project_key):
            raise ContractError(f"unsafe Jira project key: {project_key}")
        jql = f'project = "{project_key}" AND labels = "{label}"'
        query = urllib.parse.urlencode(
            {"jql": jql, "fields": "summary,description,priority,labels,project", "maxResults": "3"}
        )
        data = self._request("GET", "/rest/api/2/search?" + query)
        if not isinstance(data, Mapping) or not isinstance(data.get("issues"), list):
            raise JiraError("Jira issue search response has an unsupported shape")
        issues = data["issues"]
        validated: List[Mapping[str, Any]] = []
        for issue in issues:
            validated.append(
                _strict_issue_view(
                    issue,
                    context="Jira issue search",
                    expected_project_key=project_key,
                    expected_label=label,
                )
            )
        total = data.get("total")
        if isinstance(total, bool) or not isinstance(total, int) or total < 0:
            raise JiraError("Jira issue search returned an invalid total")
        if total != len(validated):
            raise JiraError("Jira issue search result count is incomplete or inconsistent")
        return validated

    def get_issue(
        self,
        key: str,
        extra_fields: Sequence[str] = (),
    ) -> Optional[Mapping[str, Any]]:
        if not ISSUE_KEY_RE.fullmatch(key):
            raise ContractError(f"unsafe Jira issue key: {key}")
        requested_fields = ["summary", "description", "priority", "labels", "project"]
        for field_id in extra_fields:
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", str(field_id)):
                raise ContractError(f"unsafe Jira field id: {field_id}")
            if field_id not in requested_fields:
                requested_fields.append(str(field_id))
        query = urllib.parse.urlencode(
            {"fields": ",".join(requested_fields)}
        )
        data = self._request(
            "GET", f"/rest/api/2/issue/{urllib.parse.quote(key)}?{query}", allow_not_found=True
        )
        if data is _NOT_FOUND:
            return None
        return _strict_issue_view(data, context="Jira issue response", expected_key=key)

    def get_issue_property(self, key: str, property_key: str) -> Optional[Mapping[str, Any]]:
        if property_key != PROPERTY_KEY:
            raise ContractError("unsupported Jira issue property")
        data = self._request(
            "GET",
            f"/rest/api/2/issue/{urllib.parse.quote(key)}/properties/{urllib.parse.quote(property_key)}",
            allow_not_found=True,
        )
        if data is _NOT_FOUND:
            return None
        if not isinstance(data, Mapping):
            raise JiraError("Jira issue property response has an unsupported shape")
        value = data.get("value")
        if not isinstance(value, Mapping):
            raise JiraError("Jira issue property response has no object value")
        return value

    def create_issue(self, fields: Mapping[str, Any]) -> str:
        data = self._request("POST", "/rest/api/2/issue", {"fields": fields})
        key = str(data.get("key", "")) if isinstance(data, Mapping) else ""
        if not ISSUE_KEY_RE.fullmatch(key):
            raise AmbiguousMutation("Jira create response did not include a valid issue key")
        return key

    def update_issue(
        self,
        key: str,
        fields: Mapping[str, Any],
        label_to_add: Optional[str] = None,
    ) -> None:
        payload: Dict[str, Any] = {"fields": dict(fields)}
        if label_to_add is not None:
            if not SYNC_ID_RE.fullmatch(label_to_add):
                raise ContractError(f"unsafe Jira label update: {label_to_add}")
            payload["update"] = {"labels": [{"add": label_to_add}]}
        self._request("PUT", f"/rest/api/2/issue/{urllib.parse.quote(key)}", payload)

    def set_issue_property(self, key: str, property_key: str, value: Mapping[str, Any]) -> None:
        self._request(
            "PUT",
            f"/rest/api/2/issue/{urllib.parse.quote(key)}/properties/{urllib.parse.quote(property_key)}",
            value,
        )


def _client_from_env() -> JiraClient:
    base_url = os.environ.get("JIRA_URL", "").strip()
    token = os.environ.get("JIRA_TOKEN", "")
    if not base_url:
        raise ContractError("JIRA_URL is required")
    if not token:
        raise ContractError("JIRA_TOKEN is required")
    ca_bundle = os.environ.get("JIRA_CA_BUNDLE") or os.environ.get("CURL_CA_BUNDLE")
    return JiraClient(base_url, token, ca_bundle=ca_bundle)


def _write_plan(path: Path, plan: Mapping[str, Any]) -> None:
    requested = path.expanduser()
    if not requested.is_absolute():
        requested = Path.cwd() / requested
    requested.parent.mkdir(parents=True, exist_ok=True)
    destination = requested.parent.resolve() / requested.name
    if os.path.lexists(str(destination)):
        raise ContractError(
            "plan output already exists; choose a new private path (existing files are never overwritten)"
        )
    text = json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=str(destination.parent))
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temp_name, destination)
        except FileExistsError as exc:
            raise ContractError(
                "plan output appeared during write; no existing file was overwritten"
            ) from exc
        os.unlink(temp_name)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def _paths_alias(left: Path, right: Path) -> bool:
    left_path = left.expanduser().resolve()
    right_path = right.expanduser().resolve()
    if left_path == right_path:
        return True
    try:
        return os.path.samefile(str(left_path), str(right_path))
    except OSError:
        return False


def _read_plan(path: Path) -> Mapping[str, Any]:
    try:
        data = json.loads(path.expanduser().read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot read Jira sync plan: {exc}") from exc
    if not isinstance(data, Mapping):
        raise ContractError("Jira sync plan must be a JSON object")
    return data


def _read_field_answers(path: Path) -> Mapping[str, Any]:
    answer_path = path.expanduser()
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(str(answer_path), flags)
    except OSError as exc:
        raise ContractError(f"cannot open private Jira field answers: {exc}") from exc
    try:
        file_stat = os.fstat(descriptor)
        if not stat.S_ISREG(file_stat.st_mode) or file_stat.st_uid != os.getuid():
            raise ContractError("Jira field answers must be a regular user-owned file")
        if stat.S_IMODE(file_stat.st_mode) & 0o077:
            raise ContractError("Jira field answers must not be readable by group or others")
        if file_stat.st_size > 1024 * 1024:
            raise ContractError("Jira field answers file is too large")
        with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
            descriptor = -1
            data = json.load(handle)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot read Jira field answers JSON: {exc}") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if not isinstance(data, Mapping):
        raise ContractError("Jira field answers must be a JSON object")
    return data


class _SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        self.print_usage(sys.stderr)
        self.exit(
            2,
            f"{self.prog}: error: invalid command-line arguments; "
            "credentials must be supplied through the environment\n",
        )


def _parser() -> argparse.ArgumentParser:
    parser = _SafeArgumentParser(
        description="Plan and apply deterministic TASKS.md sync to Jira Data Center",
        epilog=(
            "Environment: JIRA_URL and JIRA_TOKEN are required; JIRA_PROJECT is a "
            "display-only default hint; JIRA_CA_BUNDLE or CURL_CA_BUNDLE may name a "
            "trusted company CA bundle. A plan containing conflicts is still written "
            "for review and exits 1, but apply will refuse it."
        ),
    )
    subparsers = parser.add_subparsers(
        dest="command", required=True, parser_class=_SafeArgumentParser
    )

    projects = subparsers.add_parser(
        "projects",
        help="list accessible Jira projects",
        description=(
            "Requires JIRA_URL and JIRA_TOKEN. List every Jira Project visible to the PAT. "
            "JIRA_PROJECT only marks a "
            "saved default; the user must still choose one exact returned key."
        ),
    )
    projects.set_defaults(handler=_cmd_projects)

    fields = subparsers.add_parser(
        "fields",
        help="list generic required Jira field questions",
        description=(
            "Requires JIRA_URL and JIRA_TOKEN. Read create metadata for one exact Project "
            "and issue type, then print every non-automatic required field and its choices."
        ),
    )
    fields.add_argument("--project", required=True, help="exact Jira project key chosen by the user")
    fields.add_argument(
        "--issue-type",
        default=DEFAULT_ISSUE_TYPE,
        help=f"Jira issue type name (default: {DEFAULT_ISSUE_TYPE})",
    )
    fields.set_defaults(handler=_cmd_fields)

    plan = subparsers.add_parser(
        "plan",
        help="build a GET-only Jira sync plan",
        description=(
            "Requires JIRA_URL and JIRA_TOKEN. Use GET requests to build a reviewable "
            "plan. Jira and TASKS.md are not "
            "mutated; --output creates one new private JSON artifact."
        ),
    )
    plan.add_argument("--tasks", required=True, type=Path, help="canonical TASKS.md path")
    plan.add_argument("--project", required=True, help="exact Jira project key chosen by the user")
    plan.add_argument(
        "--issue-type",
        default=DEFAULT_ISSUE_TYPE,
        help=f"Jira issue type name (default: {DEFAULT_ISSUE_TYPE})",
    )
    plan.add_argument(
        "--answers",
        type=Path,
        help=(
            "private mode-0600 JSON answers file with defaults and per-task overrides for "
            "generic required Jira fields"
        ),
    )
    plan.add_argument(
        "--output",
        required=True,
        type=Path,
        help="new reviewable plan JSON path; existing paths and symlinks are refused",
    )
    plan.set_defaults(handler=_cmd_plan)

    apply_parser = subparsers.add_parser(
        "apply",
        help="apply one exact reviewed plan",
        description=(
            "Requires JIRA_URL and JIRA_TOKEN. Apply only the exact conflict-free plan "
            "whose SHA-256 digest the user "
            "confirmed, verify Jira, then perform locked atomic TASKS.md writeback."
        ),
    )
    apply_parser.add_argument("--plan", required=True, type=Path, help="plan JSON path")
    apply_parser.add_argument("--confirm", required=True, help="exact plan_sha256 shown by plan")
    apply_parser.set_defaults(handler=_cmd_apply)
    return parser


def _cmd_projects(args: argparse.Namespace) -> int:
    del args
    choices = project_choices(_client_from_env(), os.environ.get("JIRA_PROJECT"))
    if not choices:
        print("No accessible Jira projects.")
        return 1
    for index, project in enumerate(choices, start=1):
        marker = " [saved default]" if project["is_default"] else ""
        print(f"{index}. {project['key']} — {project['name']}{marker}")
    print("Choose one exact project key before creating a plan.")
    return 0


def _cmd_fields(args: argparse.Namespace) -> int:
    questions = required_field_questions(
        _client_from_env(),
        args.project,
        args.issue_type,
    )
    print(json.dumps(questions, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _cmd_plan(args: argparse.Namespace) -> int:
    client = _client_from_env()
    document = parse_tasks_file(args.tasks)
    if _paths_alias(document.path, args.output):
        raise ContractError("plan output must not overwrite TASKS.md")
    field_answers = _read_field_answers(args.answers) if args.answers else None
    plan = build_sync_plan(
        client,
        document,
        args.project,
        args.issue_type,
        field_answers=field_answers,
    )
    _write_plan(args.output, plan)
    counts: Dict[str, int] = {
        "adopt": 0,
        "create": 0,
        "update": 0,
        "skip": 0,
        "conflict": 0,
    }
    for action in plan["actions"]:
        counts[action["operation"]] = counts.get(action["operation"], 0) + 1
    print(f"Jira: {plan['jira_origin']}")
    print(f"Project: {plan['project']['key']} — {plan['project']['name']}")
    print("Actions: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items())))
    for action in plan["actions"]:
        issue = f" -> {action['issue_key']}" if action.get("issue_key") else ""
        print(
            f"  Task {action['task_number']}: {action['operation']}{issue} — {action['reason']}"
        )
        for field_id, value in action.get("create_only_fields", {}).items():
            field_name = next(
                (
                    item["name"]
                    for item in plan["required_fields"]
                    if item["id"] == field_id
                ),
                field_id,
            )
            print(f"    {field_name} ({field_id}) = {json.dumps(value, ensure_ascii=False)}")
    print(f"Plan: {args.output.expanduser().resolve()}")
    print(f"plan_sha256: {plan['plan_sha256']}")
    print("No Jira issues or TASKS.md fields were changed.")
    return 1 if counts.get("conflict", 0) else 0


def _cmd_apply(args: argparse.Namespace) -> int:
    plan = _read_plan(args.plan)
    report = apply_sync_plan(_client_from_env(), plan, args.confirm)
    print(
        "Result: "
        + ", ".join(
            f"{key}={report[key]}"
            for key in (
                "created",
                "updated",
                "skipped",
                "conflicts",
                "remote_unknown",
                "failed",
                "writeback_pending",
                "aborted",
            )
        )
    )
    for link in report["links"]:
        print(
            f"Task {link['task_number']}: {link['operation']} {link['issue_key']} "
            f"(sync_id={link['sync_id']}, writeback={link['writeback']})"
        )
    for item in report["unattempted"]:
        print(
            f"Task {item['task_number']}: aborted before {item['operation']} — {item['reason']}"
        )
    for error in report["errors"]:
        print(f"ERROR: {error}", file=sys.stderr)
    return 1 if report["failed"] else 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except ContractError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except JiraError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"ERROR: local I/O failed: {exc}", file=sys.stderr)
        return 1
    except ValueError:
        print("ERROR: invalid Jira request value", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
