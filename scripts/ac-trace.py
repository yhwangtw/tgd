#!/usr/bin/env python3
"""
ac-trace.py — Requirement-coverage gate: verify every Acceptance Criterion
in TASKS.md has a valid executable-test or documentation carrier.

Coverage floors measure LINE coverage; this gate measures REQUIREMENT
coverage. 100% line coverage can still miss half the acceptance criteria —
and an agent writing its own tests tends to write the easy ones. This
script makes the gap visible and machine-enforced.

Convention (defined in skills/tgd-plan-breakdown/SKILL.md):
  - Every criterion in TASKS.md carries a stable ID:  **AC-<task>.<n>**
    (e.g. AC-1.1, AC-2.3)
  - Every test that verifies a criterion mentions the ID in its name,
    docstring, or a comment:  test("AC-1.1: rejects empty password", ...)
  - Criteria marked [R] (regression) MUST additionally carry a
    "Test: <path>" line naming the concrete test file.
  - Documentation-only criteria carry a Doc: carrier instead of a test:
        Doc: `README.md` contains "getMonthlySummary("
    Traced iff the named file exists in the client repo and contains the
    quoted string. Doc: criteria cannot be [R].

Usage:
    python3 scripts/ac-trace.py <feature-dir> [client-repo]

    feature-dir: $TGD_DIR/<feature-name>/ (contains TASKS.md)
    client-repo: defaults to current working directory

Exit codes:
    0 = every AC has a valid test or Doc: carrier; every [R] AC has an existing Test: file
    1 = at least one AC untraced or an [R] AC without a valid Test: file
    2 = usage error (no TASKS.md, no ACs found, client repo missing)

Python 3.8+ stdlib only.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set

AC_ID_RX = re.compile(r"\bAC-\d+\.\d+\b")
DOC_FIELD_PREFIX = r"^ {0,3}(?:-\s*)?(?:\*\*)?Doc\*{0,2}:\*{0,2}"
TEST_FIELD_PREFIX = r"^ {0,3}(?:-\s*)?(?:\*\*)?Test\*{0,2}:\*{0,2}"
TEST_FILE_RX = re.compile(
    r"(^test_.*\.py$|_test\.py$|\.test\.[jt]sx?$|\.spec\.[jt]sx?$|_test\.go$|_spec\.rb$|Test\.java$|_test\.rs$)"
)
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist",
             "build", "target", ".codegraph", ".understand-anything", "vendor"}


def without_fenced_code(text: str) -> str:
    """Return Markdown text with fenced code blocks removed."""
    kept: List[str] = []
    fence_char: Optional[str] = None
    fence_len = 0
    for line in text.splitlines(keepends=True):
        candidate = line.lstrip(" ")
        indent = len(line) - len(candidate)
        if fence_char is None:
            opening = re.match(r"(`{3,}|~{3,})", candidate) if indent <= 3 else None
            if opening:
                marker = opening.group(1)
                fence_char = marker[0]
                fence_len = len(marker)
                continue
            kept.append(line)
            continue
        if indent <= 3 and re.fullmatch(
            re.escape(fence_char) + "{" + str(fence_len) + r",}[ \t]*(?:\r?\n)?",
            candidate,
        ):
            fence_char = None
            fence_len = 0
    return "".join(kept)


def die(msg: str, code: int = 2) -> None:
    sys.stderr.write(f"[ac-trace] ERROR: {msg}\n")
    raise SystemExit(code)


def parse_tasks(tasks_path: Path) -> Dict[str, Dict]:
    """Return {ac_id: {"regression": bool, "test": Optional[str]}}.

    An AC block starts at the line containing the AC id and extends to the
    next AC id or section break; [R] and Test: are read from that block.
    """
    text = tasks_path.read_text(encoding="utf-8")
    acs: Dict[str, Dict] = {}
    # Split into chunks anchored at each AC id occurrence (first occurrence wins)
    matches = list(AC_ID_RX.finditer(text))
    for i, m in enumerate(matches):
        ac_id = m.group(0)
        if ac_id in acs:
            continue
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end]
        field_block = without_fenced_code(block)
        regression = "[R]" in block
        # A Test: carrier, like Doc:, must be a standalone Markdown field
        # outside code fences. Tolerate both bold-colon stylings.
        tm = re.search(
            TEST_FIELD_PREFIX + r"\s*(?:`([^`]+)`|([^\s`]+))",
            field_block,
            re.MULTILINE,
        )
        test = ((tm.group(1) or tm.group(2)).strip()) if tm else None
        # Doc carrier for documentation-only criteria. Detect declaration
        # separately so a malformed carrier fails closed instead of silently
        # falling back to a test reference.
        #   Doc: `README.md` contains "getMonthlySummary("
        doc_declared = bool(re.search(DOC_FIELD_PREFIX, field_block, re.MULTILINE))
        doc = None
        dm = re.search(
            DOC_FIELD_PREFIX + r'\s*(?:`([^`]+)`|([^\s]+))'
            r'\s+contains\s+"([^"]+)"',
            field_block,
            re.MULTILINE,
        )
        if dm:
            doc = ((dm.group(1) or dm.group(2)).strip(), dm.group(3))
        acs[ac_id] = {
            "regression": regression,
            "test": test,
            "doc": doc,
            "doc_declared": doc_declared,
        }
    return acs


def resolve_repo_file(client_repo: Path, raw_path: str) -> Optional[Path]:
    """Resolve a declared carrier path only when it stays inside client_repo."""
    relative = Path(raw_path)
    if relative.is_absolute() or ".." in relative.parts:
        return None
    resolved = (client_repo / relative).resolve()
    try:
        resolved.relative_to(client_repo)
    except ValueError:
        return None
    return resolved


def collect_test_refs(client_repo: Path) -> Dict[str, Set[str]]:
    """Return {ac_id: {contained test files that mention it}}."""
    refs: Dict[str, Set[str]] = {}
    for path in client_repo.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if not TEST_FILE_RX.search(path.name):
            continue
        rel = str(path.relative_to(client_repo))
        safe_path = resolve_repo_file(client_repo, rel)
        if safe_path is None or not safe_path.is_file():
            continue
        try:
            content = safe_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for ac_id in set(AC_ID_RX.findall(content)):
            refs.setdefault(ac_id, set()).add(rel)
    return refs


def main() -> int:
    if len(sys.argv) < 2:
        die("Usage: python3 ac-trace.py <feature-dir> [client-repo]")
    feature_dir = Path(sys.argv[1]).expanduser().resolve()
    client_repo = Path(sys.argv[2] if len(sys.argv) > 2 else ".").expanduser().resolve()

    tasks_path = feature_dir / "TASKS.md"
    if not tasks_path.is_file():
        die(f"TASKS.md not found: {tasks_path}")
    if not client_repo.is_dir():
        die(f"client repo not found: {client_repo}")

    acs = parse_tasks(tasks_path)
    if not acs:
        die(
            f"No AC-<task>.<n> IDs found in {tasks_path}.\n"
            "  Criteria must carry stable IDs (AC-1.1, AC-1.2, ...) — see\n"
            "  skills/tgd-plan-breakdown/SKILL.md. A TASKS.md\n"
            "  without IDs cannot be traced and fails closed."
        )

    refs = collect_test_refs(client_repo)

    untraced: List[str] = []
    r_missing_test: List[str] = []
    r_stale_test: List[str] = []
    r_doc_conflict: List[str] = []

    print(f"[ac-trace] {len(acs)} acceptance criteria in {tasks_path.name}, "
          f"{len(refs)} AC ids referenced across tests\n")
    print(f"{'AC':<10} {'[R]':<4} {'Traced':<7} Details")
    print("-" * 72)
    for ac_id in sorted(acs, key=lambda a: [int(x) for x in a[3:].split(".")]):
        info = acs[ac_id]
        traced = ac_id in refs
        detail = ", ".join(sorted(refs.get(ac_id, []))) or "—"
        if info.get("doc_declared"):
            # A declared Doc: carrier is authoritative for this criterion and
            # must validate even if a test file also mentions the AC id.
            if not info.get("doc"):
                traced = False
                detail = "doc: malformed Doc: carrier"
            else:
                doc_file, needle = info["doc"]
                doc_path = resolve_repo_file(client_repo, doc_file)
                content = None
                if doc_path is not None and doc_path.is_file():
                    try:
                        content = doc_path.read_text(encoding="utf-8")
                    except (OSError, UnicodeError):
                        content = None
                if content is not None and needle in content:
                    traced = True
                    detail = f"doc: {doc_file} contains \"{needle}\""
                else:
                    traced = False
                    detail = (
                        f"doc: {doc_file} unsafe, unreadable, missing, or lacks "
                        f"\"{needle}\""
                    )
        flag = "R" if info["regression"] else ""
        print(f"{ac_id:<10} {flag:<4} {'yes' if traced else 'NO':<7} {detail}")
        if not traced:
            untraced.append(ac_id)
        if info["regression"] and info.get("doc_declared"):
            r_doc_conflict.append(ac_id)
        if info["regression"]:
            test = info["test"]
            if not test:
                r_missing_test.append(ac_id)
            else:
                test_file = test
                test_path = resolve_repo_file(client_repo, test_file)
                if test_path is None or not test_path.is_file():
                    r_stale_test.append(f"{ac_id} ({test_file})")
                elif not TEST_FILE_RX.search(test_path.name):
                    r_stale_test.append(f"{ac_id} ({test_file}: not a test file)")
                else:
                    test_rel = str(test_path.relative_to(client_repo))
                    if test_rel not in refs.get(ac_id, set()):
                        r_stale_test.append(
                            f"{ac_id} ({test_file}: does not reference {ac_id})"
                        )

    ok = True
    print()
    if untraced:
        ok = False
        print(f"❌ {len(untraced)} criteria have NO valid test or Doc: carrier: "
              + ", ".join(untraced))
        print("   Fix: add the AC id to an executable test, or add/fix the")
        print("   documentation-only Doc: carrier. Do not fabricate a doc test.")
    if r_missing_test:
        ok = False
        print(f"❌ {len(r_missing_test)} [R] criteria have no 'Test:' file reference: "
              + ", ".join(r_missing_test))
        print("   [R] criteria feed REGRESSION-CATALOG.md at release — each MUST name")
        print("   its concrete test file in TASKS.md.")
    if r_stale_test:
        ok = False
        print(f"❌ {len(r_stale_test)} [R] 'Test:' references point to missing files: "
              + ", ".join(r_stale_test))
    if r_doc_conflict:
        ok = False
        print(f"❌ {len(r_doc_conflict)} criteria are both [R] and Doc:-carried: "
              + ", ".join(r_doc_conflict))
        print("   The regression catalog replays executable tests only — a doc-only")
        print("   criterion cannot be [R]. Change the carrier or drop the [R].")

    if ok:
        print("✅ AC TRACE PASSED: every criterion has a valid test or Doc: carrier; "
              "all [R] criteria name existing test files")
        return 0
    print("\n❌ AC TRACE FAILED — requirement coverage is incomplete (see above)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
