#!/usr/bin/env python3
"""
generate-mirrors.py — Regenerate all platform command mirrors from the
single source of truth: .claude/commands/*.md

Outputs (committed to the repo — platforms read them at install time):

    .codex/prompts/<name>.md            # /<name> header + same body
    .opencode/commands/<name>.md        YAML frontmatter + same body
    .gemini/commands/<name>.toml        description + prompt=\"\"\"body\"\"\"
    .pi/prompts/<name>.md               # frontmatter description + same body
                                        # (native pi prompt template — /<name>)

Workflow:
    1. Edit .claude/commands/<name>.md ONLY. Never hand-edit a mirror.
    2. Run: python3 scripts/generate-mirrors.py
    3. Commit the source change together with the regenerated mirrors.

CI runs this script and fails the build if `git diff` is non-empty
afterwards (see .github/workflows/lint.yml, job "mirror-sync"), so a
hand-edited mirror or a forgotten regeneration cannot land on main.

Deterministic: same input always produces byte-identical output.
Python 3.8+ stdlib only. Exits non-zero with a precise message when a
command file cannot be encoded safely for a target format.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = REPO_ROOT / ".claude" / "commands"
CODEX_DIR = REPO_ROOT / ".codex" / "prompts"
OPENCODE_DIR = REPO_ROOT / ".opencode" / "commands"
GEMINI_DIR = REPO_ROOT / ".gemini" / "commands"
PI_PROMPTS_DIR = REPO_ROOT / ".pi" / "prompts"

# The 7 lifecycle commands, in pipeline order (drives pi registration order).
COMMANDS = [
    "tgd-map",
    "tgd-define",
    "tgd-plan",
    "tgd-develop",
    "tgd-verify",
    "tgd-review",
    "tgd-release",
]


def die(msg: str) -> None:
    sys.stderr.write(f"[generate-mirrors] ERROR: {msg}\n")
    raise SystemExit(1)


def parse_source(name: str) -> Tuple[str, str]:
    """Return (description, body) from .claude/commands/<name>.md.

    Expected layout:
        line 1: ---
        line 2: description: <text>
        line 3: ---
        line 4+: body (copied verbatim into every mirror)
    """
    path = SOURCE_DIR / f"{name}.md"
    if not path.is_file():
        die(f"source missing: {path}")
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    if len(lines) < 4 or lines[0].strip() != "---" or lines[2].strip() != "---":
        die(f"{path}: expected 3-line YAML frontmatter (---, description:, ---)")
    if not lines[1].startswith("description:"):
        die(f"{path}: line 2 must start with 'description:'")
    description = lines[1][len("description:"):].strip()
    if not description:
        die(f"{path}: empty description")
    body = "".join(lines[3:])
    return description, body


def check_toml_safe(name: str, description: str, body: str) -> None:
    if '"' in description or "\\" in description or "\n" in description:
        die(f"{name}: description contains characters unsafe for a TOML basic string")
    if '"""' in body:
        die(f'{name}: body contains \'"""\' which would terminate the TOML multi-line string')
    if "\\" in body:
        die(f"{name}: body contains a backslash, which TOML multi-line basic strings interpret as an escape")


def check_pi_safe(name: str, body: str) -> None:
    # pi prompt templates expand $1..$9, $@, $ARGUMENTS, and ${...} as
    # call-time arguments. The tGD commands take no arguments, so any such
    # token in a body would be silently mangled at invocation. Guard it.
    m = re.search(r"\$[1-9]|\$@|\$ARGUMENTS|\$\{", body)
    if m:
        die(f"{name}: body contains pi argument-expansion token '{m.group(0)}' — "
            f"pi would expand it at invocation. These commands take no args; rewrite to avoid it.")


def gen_codex(name: str, description: str, body: str) -> str:
    return f"# /{name}\n\n{description}\n{body}"


def gen_opencode(name: str, description: str, body: str) -> str:
    return f"---\ndescription: {description}\n---\n{body}"


def gen_gemini(name: str, description: str, body: str) -> str:
    return f'description = "{description}"\n\nprompt = """\n{body}"""\n'


def gen_pi_prompt(name: str, description: str, body: str) -> str:
    # pi prompt templates are CLIENT-SIDE TEXT EXPANSION: whatever the template
    # contains becomes the user message, rendered in full by the TUI
    # (agent-session.js expandPromptTemplate -> _queueFollowUp(expandedText);
    # UserMessageComponent renders the whole text). Shipping the full command
    # body therefore reproduces the wall-of-text-under-the-user's-name problem
    # the old sendUserMessage extension had — different mechanism, same screen.
    #
    # So the pi template is a 4-line STUB (a pointer): the agent loads the real
    # command file itself, keeping the user turn tiny. The full body ships only
    # in .claude/commands/ (present in every tGD clone; ~/.pi/agent/prompts/*
    # symlinks resolve into that clone).
    del body  # intentionally NOT embedded — see comment above
    return (
        "---\n"
        f"description: {description}\n"
        "---\n"
        f"Execute the tGD `/{name}` workflow. This template is a POINTER, not the workflow — load the full instructions first:\n"
        "\n"
        f"1. If `.claude/commands/{name}.md` exists in the current project (you are inside the tGD repo), read it.\n"
        f"2. Otherwise resolve the installed copy: run `python3 -c \"import os;print(os.path.realpath(os.path.expanduser('~/.pi/agent/prompts/{name}.md')))\"` and replace `/.pi/prompts/` with `/.claude/commands/` in the result — read that file.\n"
        "\n"
        "Then execute ALL of its instructions in order, from the first pre-flight to the final verification gate. Do not improvise from this stub — that file is the single source of truth.\n"
    )


def write_if_changed(path: Path, content: str, changed: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.read_text(encoding="utf-8") == content:
        return
    path.write_text(content, encoding="utf-8")
    changed.append(str(path.relative_to(REPO_ROOT)))


def main() -> int:
    entries: List[Tuple[str, str, str]] = []
    for name in COMMANDS:
        description, body = parse_source(name)
        check_toml_safe(name, description, body)
        check_pi_safe(name, body)
        entries.append((name, description, body))

    changed: List[str] = []
    for name, description, body in entries:
        write_if_changed(CODEX_DIR / f"{name}.md", gen_codex(name, description, body), changed)
        write_if_changed(OPENCODE_DIR / f"{name}.md", gen_opencode(name, description, body), changed)
        write_if_changed(GEMINI_DIR / f"{name}.toml", gen_gemini(name, description, body), changed)
        write_if_changed(PI_PROMPTS_DIR / f"{name}.md", gen_pi_prompt(name, description, body), changed)

    if changed:
        print(f"[generate-mirrors] Updated {len(changed)} file(s):")
        for c in changed:
            print(f"  {c}")
    else:
        print("[generate-mirrors] All mirrors already in sync.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
