#!/usr/bin/env python3
"""
check-doc-sections.py — verify a produced tGD artifact contains the required
`##` sections its template prescribes.

Usage:
    python3 scripts/check-doc-sections.py <PRD|SPEC|DESIGN|REVIEW> <path-to-file>

Why this exists:
    PRD/SPEC/DESIGN/REVIEW templates prescribe sections, but the phase gates only
    checked the file existed and was non-empty — an agent that wrote a
    truncated or free-form document still passed. This is the floor that
    catches "half the sections are missing". It does NOT check content (an
    empty `## Risks` heading passes); template guidance and human review own
    quality. Presence is the machine-checkable part.

Single source of truth:
    The required section list is DERIVED AT RUNTIME from the canonical template
    (not hardcoded here), so the check can never drift from the template:
      - PRD, SPEC, DESIGN → skills/tgd-spec-driven-development/SKILL.md
      - REVIEW    → .claude/commands/tgd-review.md
    A section whose heading is marked "(if applicable)" / "(if <cond>)" in the
    template is OPTIONAL and not enforced. To relax a section, mark it in the
    template — nothing here changes.

Matching is tolerant: headings are compared by normalized text (leading `##`,
a leading "N." number, and any "(if ...)" suffix stripped, case-insensitive),
so `## 1. Executive Summary` and `## Executive Summary` are treated the same.

Exit codes:
    0 = every required section is present
    1 = one or more required sections are missing (listed on stderr)
    2 = usage/config error (unknown artifact, template or target not found,
        template block not parseable)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_SKILL = REPO_ROOT / "skills" / "tgd-spec-driven-development" / "SKILL.md"
PLAN_SKILL = REPO_ROOT / "skills" / "tgd-planning-and-task-breakdown" / "SKILL.md"
REVIEW_CMD = REPO_ROOT / ".claude" / "commands" / "tgd-review.md"

# artifact -> (template file, regex marking the START of that template block)
TEMPLATES = {
    "PRD": (SPEC_SKILL, r"^# PRD: "),
    "SPEC": (SPEC_SKILL, r"^# SPEC: "),
    "DESIGN": (SPEC_SKILL, r"^# DESIGN: "),
    "TASKS": (PLAN_SKILL, r"^# TASKS\.md: "),
    "REVIEW": (REVIEW_CMD, r"^# REVIEW: "),
}

# Repeating/parameterized template headings can't be required literally — the
# template writes "## Task 1: [User Story Title]" but a real file has
# "## Task 3: Add rate limiting". Each rule: template headings matching
# drop_rx are removed from the static required list, and instead the TARGET
# must contain at least one heading matching need_rx.
# artifact -> [(drop_rx, need_rx, human label)]
DYNAMIC_RULES = {
    "TASKS": [
        (r"^Task\s+\d+", r"^##\s+Task\s+\d+:", "## Task N: <title> — at least one task"),
        (r"^Checkpoint", r"^##\s+Checkpoint", "## Checkpoint: … — at least one checkpoint"),
    ],
}

_OPTIONAL_RX = re.compile(r"\(if\b", re.IGNORECASE)


def normalize(heading: str) -> str:
    h = re.sub(r"^#{2,3}\s*", "", heading.strip())        # strip ## / ###
    h = re.sub(r"^\d+[.)]\s*", "", h)                     # strip "1. " / "1) "
    h = re.sub(r"\s*\(if\b.*?\)\s*$", "", h, flags=re.I)  # strip "(if ...)"
    return h.strip().lower()


def extract_required(template_file: Path, start_rx: str) -> Optional[List[str]]:
    """Collect the level-2 (`## `) headings of the template block that begins
    at start_rx, up to the closing code fence. Headings marked "(if ...)" are
    dropped (optional). Returns None if the start marker is not found.

    Nested-fence rule: a template may contain INNER code blocks (e.g. the
    TASKS template's schema example). An inner fence must open with an info
    string (```lang); a BARE ``` at outer level closes the template. Without
    this, the first inner fence would silently truncate extraction and the
    gate would quietly require fewer sections."""
    try:
        lines = template_file.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    start = next((i for i, l in enumerate(lines) if re.search(start_rx, l)), None)
    if start is None:
        return None
    required: List[str] = []
    in_inner = False
    for line in lines[start + 1:]:
        stripped = line.lstrip()
        if stripped.startswith("```"):
            info = stripped[3:].strip()
            if in_inner:
                in_inner = False          # closes the inner block
            elif info:
                in_inner = True           # opens an inner block (```lang)
            else:
                break                     # bare ``` at outer level = template end
            continue
        if in_inner:
            continue
        m = re.match(r"^##\s+(.*)", line)     # level-2 sections only
        if m and not _OPTIONAL_RX.search(m.group(1)):
            required.append(m.group(1).strip())
    return required


def resolve(artifact: str) -> Tuple[Path, str]:
    return TEMPLATES[artifact]


def main() -> int:
    if len(sys.argv) != 3:
        sys.stderr.write("usage: check-doc-sections.py <PRD|SPEC|DESIGN|TASKS|REVIEW> <file>\n")
        return 2
    artifact = sys.argv[1].strip().upper()
    target = Path(sys.argv[2]).expanduser()

    if artifact not in TEMPLATES:
        sys.stderr.write(f"unknown artifact '{artifact}' — expected PRD, SPEC, DESIGN, TASKS, or REVIEW\n")
        return 2

    template_file, start_rx = resolve(artifact)
    if not template_file.is_file():
        sys.stderr.write(f"template source missing: {template_file}\n")
        return 2

    required = extract_required(template_file, start_rx)
    if not required:
        sys.stderr.write(
            f"could not extract the {artifact} template sections from "
            f"{template_file} (start marker not found or block empty)\n"
        )
        return 2

    if not target.is_file():
        sys.stderr.write(f"{artifact} file not found: {target}\n")
        return 2

    # Split off dynamic (repeating) headings: drop them from the static list,
    # then require the target to match each pattern at least once.
    dynamic = DYNAMIC_RULES.get(artifact, [])
    for drop_rx, _need_rx, _label in dynamic:
        required = [h for h in required if not re.match(drop_rx, h)]

    target_lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
    have = set()
    for line in target_lines:
        m = re.match(r"^##\s+(.*)", line)
        if m:
            have.add(normalize(m.group(1)))

    missing = [f"## {h}" for h in required if normalize(h) not in have]
    for _drop_rx, need_rx, label in dynamic:
        if not any(re.match(need_rx, line) for line in target_lines):
            missing.append(label)

    if missing:
        sys.stderr.write(f"❌ {artifact} {target} is missing required sections:\n")
        for h in missing:
            sys.stderr.write(f"   - {h}\n")
        sys.stderr.write(
            f"   (required list derived from the canonical template in "
            f"{template_file.name}; add the headings and re-run)\n"
        )
        return 1

    n = len(required) + len(dynamic)
    sys.stdout.write(
        f"✅ {artifact} {target.name}: all {n} required section checks passed\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
