#!/usr/bin/env python3
"""
ac-trace.py — Requirement-coverage gate: verify every Acceptance Criterion
in TASKS.md is referenced by at least one test.

Coverage floors measure LINE coverage; this gate measures REQUIREMENT
coverage. 100% line coverage can still miss half the acceptance criteria —
and an agent writing its own tests tends to write the easy ones. This
script makes the gap visible and machine-enforced.

Convention (defined in skills/tgd-planning-and-task-breakdown/SKILL.md):
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
    0 = every AC referenced by a test; every [R] AC has an existing Test: file
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
TEST_FILE_RX = re.compile(
    r"(^test_.*\.py$|_test\.py$|\.test\.[jt]sx?$|\.spec\.[jt]sx?$|_test\.go$|_spec\.rb$|Test\.java$|_test\.rs$)"
)
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist",
             "build", "target", ".codegraph", ".understand-anything", "vendor"}


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
        regression = "[R]" in block
        # Tolerate both markdown stylings: "**Test**: `x`" and "**Test:** `x`"
        tm = re.search(r"Test\*{0,2}:\*{0,2}\s*`?([^`\n]+)`?", block)
        test = tm.group(1).strip() if tm else None
        # Doc carrier for documentation-only criteria:
        #   Doc: `README.md` contains "getMonthlySummary("
        doc = None
        dm = re.search(r"Doc\*{0,2}:\*{0,2}\s*`?([^`\s]+)`?\s+contains\s+\"([^\"]+)\"", block)
        if dm:
            doc = (dm.group(1).strip(), dm.group(2))
        acs[ac_id] = {"regression": regression, "test": test, "doc": doc}
    return acs


def collect_test_refs(client_repo: Path) -> Dict[str, Set[str]]:
    """Return {ac_id: {test files that mention it}} across the client repo."""
    refs: Dict[str, Set[str]] = {}
    for path in client_repo.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if not TEST_FILE_RX.search(path.name):
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        rel = str(path.relative_to(client_repo))
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
            "  skills/tgd-planning-and-task-breakdown/SKILL.md. A TASKS.md\n"
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
        if not traced and info.get("doc"):
            # Doc-carrier criterion: traced iff the named file exists and
            # contains the quoted string — no test reference expected.
            doc_file, needle = info["doc"]
            doc_path = client_repo / doc_file
            if doc_path.is_file() and needle in doc_path.read_text(
                    encoding="utf-8", errors="replace"):
                traced = True
                detail = f"doc: {doc_file} contains \"{needle}\""
            else:
                detail = f"doc: {doc_file} missing or lacks \"{needle}\""
        flag = "R" if info["regression"] else ""
        print(f"{ac_id:<10} {flag:<4} {'yes' if traced else 'NO':<7} {detail}")
        if not traced:
            untraced.append(ac_id)
        if info["regression"] and info.get("doc"):
            r_doc_conflict.append(ac_id)
        if info["regression"]:
            test = info["test"]
            if not test:
                r_missing_test.append(ac_id)
            else:
                test_file = test.split()[-1]
                if not (client_repo / test_file).is_file():
                    r_stale_test.append(f"{ac_id} ({test_file})")

    ok = True
    print()
    if untraced:
        ok = False
        print(f"❌ {len(untraced)} criteria have NO test referencing them: "
              + ", ".join(untraced))
        print("   Fix: add the AC id to the verifying test's name/docstring/comment,")
        print("   or write the missing test.")
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
        print("✅ AC TRACE PASSED: every criterion is referenced by a test; "
              "all [R] criteria name existing test files")
        return 0
    print("\n❌ AC TRACE FAILED — requirement coverage is incomplete (see above)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
