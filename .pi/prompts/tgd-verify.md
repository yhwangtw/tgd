---
description: Verify — prove it works with debugging and test pyramid
---
Execute the tGD `/tgd-verify` workflow. This template is a POINTER, not the workflow — load the full instructions first:

1. If `.claude/commands/tgd-verify.md` exists in the current project (you are inside the tGD repo), read it.
2. Otherwise resolve the installed copy: run `python3 -c "import os;print(os.path.realpath(os.path.expanduser('~/.pi/agent/prompts/tgd-verify.md')))"` and replace `/.pi/prompts/` with `/.claude/commands/` in the result — read that file.

Then execute ALL of its instructions in order, from the first pre-flight to the final verification gate. Do not improvise from this stub — that file is the single source of truth.
