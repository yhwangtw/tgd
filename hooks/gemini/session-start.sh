#!/bin/bash
# Gemini CLI SessionStart hook — injects tgd-router meta-skill
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# Script lives at hooks/gemini/session-start.sh, so skills/ is two levels up.
SKILLS_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)/skills"
META_SKILL="$SKILLS_DIR/tgd-router/SKILL.md"

if ! command -v jq >/dev/null 2>&1; then
  exit 0
fi

if [ -f "$META_SKILL" ]; then
  CONTENT=$(cat "$META_SKILL")
  jq -cn \
    --arg message "tGD loaded. Use the skill discovery flowchart to find the right skill for your task.

$CONTENT" \
    '{priority: "IMPORTANT", message: $message}'
else
  exit 0
fi
