# tGD — Session Preamble

## Verification Iron Law

This preamble is a bounded loader, not the tGD rulebook.

- For any tGD action, load the `tgd-core-rules` skill before acting. It owns the
  lifecycle invariants, completion-evidence gate, selection protocol, phase
  tone, closing report, and human sign-off rules.
- When no lifecycle command already supplies the pipeline and intent needs
  routing, **Load the `tgd-core-router` skill** after the core rules.
