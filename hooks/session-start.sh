#!/usr/bin/env bash
# Claude Code SessionStart hook — injects the bounded tGD session preamble.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PREAMBLE="$SCRIPT_DIR/session-preamble.md"

if ! command -v python3 >/dev/null 2>&1; then
  exit 0
fi

exec python3 - "$PREAMBLE" <<'PY'
import json
from pathlib import Path
import sys

preamble = Path(sys.argv[1])
if preamble.is_file():
    context = "tGD session guidance:\n\n" + preamble.read_text(encoding="utf-8")
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        }
    }))
else:
    print(json.dumps({
        "systemMessage": "tGD session preamble is missing; installed skills remain available."
    }))
PY
