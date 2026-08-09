# tGD — Session Preamble

<!--
CANONICAL SOURCE for the optional tGD session layer.
Edit THIS file only. Pi's supported append file is generated from it:
  .pi/APPEND_SYSTEM.md      (→ ~/.pi/agent/APPEND_SYSTEM.md)
Run: python3 scripts/generate-mirrors.py   (CI "Mirror sync" fails on drift)
With explicit setup opt-in, Claude, Codex, and Gemini inject this bounded
preamble at session start, Pi appends it to the system prompt, and Hermes
injects it once per session via pre_llm_call. It tells the agent what to load
on demand; it does not inject the full router. OpenCode has no tGD session
plugin and routes through installed skills and commands.

NOT generated from this file (deliberately): .claude/CLAUDE.md. That file is
instructions for agents developing tGD itself; setup.sh never installs it into
user homes.
-->

## Verification Iron Law

This preamble is a bounded loader, not the tGD rulebook.

- For any tGD action, load the `tgd-core-rules` skill before acting. It owns the
  lifecycle invariants, completion-evidence gate, selection protocol, phase
  tone, closing report, and human sign-off rules.
- When no lifecycle command already supplies the pipeline and intent needs
  routing, **Load the `tgd-core-router` skill** after the core rules.
