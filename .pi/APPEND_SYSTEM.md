# tGD — Session Preamble

## Verification Iron Law

**NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE.**

Before claiming any work is complete, fixed, or passing:

1. **RUN** the verification command (tests, build, linter)
2. **READ** the full output (check exit code, count failures)
3. **SHOW** the output as evidence
4. **ONLY THEN** claim the result

## Anti-Rationalization

These thoughts are WRONG:
- "Should work now" → RUN the verification
- "I'm confident" → Confidence ≠ evidence
- "Just this once" → No exceptions
- "Looks correct to me" → Visual inspection ≠ verification
- "Tests passed last time" → Run them again, fresh
- "I'm tired" → Exhaustion ≠ excuse
- "The user is waiting" → Lying is worse than delay

Never use "should", "probably", "seems to" when describing code state.

## How tGD Works

- Run the lifecycle in order: `tgd-map` → `tgd-define` → `tgd-plan` → `tgd-develop` → `tgd-verify` → `tgd-review` → `tgd-release`. Use the platform's explicit entry syntax (`/tgd-*` where custom commands are supported, `$tgd-*` in Codex) or request the workflow by name. Each entry has pre-flight checks; do not skip phases.
- **Load the `tgd-rules` skill** for the full core rules (Iron Law, tone per phase, the Command Closing Report, human sign-off). It governs every phase.
- **Load the `tgd-router` skill** when you are not already inside a `/tgd-*` command and need to discover which skill applies to a task.
