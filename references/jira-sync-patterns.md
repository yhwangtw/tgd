# Jira Sync Patterns

Illustrative command and data shapes only. The authorization, digest, identity,
retention, and reconciliation rules live in
[`tgd-plan-jira`](../skills/tgd-plan-jira/SKILL.md).

## Environment and TASKS.md Shape

```text
TASKS_PATH = $TGD_DIR/<feature-name>/TASKS.md
JIRA_URL   = Jira Data Center base URL from the process environment
JIRA_TOKEN = Personal Access Token from the process environment
ANSWERS    = Private JSON used only for extra required fields
```

```markdown
> **Jira-Source-ID**: tgd-source-123e4567-e89b-42d3-a456-426614174000

**Jira:** —
**Jira-Sync-ID:** —
```

## Read-Only Discovery

```bash
python3 "$TGD_REPO_ROOT/scripts/jira-sync.py" projects

python3 "$TGD_REPO_ROOT/scripts/jira-sync.py" fields \
  --project "$PROJECT_KEY" \
  --issue-type "$ISSUE_TYPE"
```

`PROJECT_KEY` in this example represents an exact returned selection, not a
free-typed or saved default.

## Private Answers Shape

```json
{
  "defaults": {
    "customfield_10020": [{"id": "55"}],
    "customfield_20000": "2026-08-15"
  },
  "tasks": {
    "2": {"customfield_10020": [{"id": "56"}]}
  }
}
```

The main skill owns the private-file requirements; this illustrates only the
defaults and per-task override structure.

## Plan Command Shape

```bash
: "${PROJECT_KEY:?select an exact returned Project key}"
: "${ISSUE_TYPE:?select an issue type}"
: "${TASKS_PATH:?resolve canonical TASKS.md}"
: "${TGD_REPO_ROOT:?resolve the tGD repository root}"

umask 077
JIRA_PLAN_DIR="$(mktemp -d "${TMPDIR:-/tmp}/tgd-jira-plan.XXXXXX")" || {
  echo "Failed to create a private Jira plan directory" >&2
  exit 1
}
test -n "$JIRA_PLAN_DIR" && test -d "$JIRA_PLAN_DIR" || exit 1
JIRA_PLAN_PATH="$JIRA_PLAN_DIR/plan.json"

python3 "$TGD_REPO_ROOT/scripts/jira-sync.py" plan \
  --tasks "$TASKS_PATH" \
  --project "$PROJECT_KEY" \
  --issue-type "$ISSUE_TYPE" \
  --output "$JIRA_PLAN_PATH"
```

When required answers exist, a private `answers.json` inside the same directory
is supplied with `--answers "$JIRA_ANSWERS_PATH"`. The main skill determines
when files are retained for reconciliation or removed.

## Confirmation Shape

```text
Apply this exact Jira plan?
1. Apply to <PROJECT_KEY> (digest: <SHA-256>)
2. Cancel

Choose one (default 2):
```

## Apply Command Shape

```bash
: "${JIRA_PLAN_PATH:?review the generated plan}"
: "${PLAN_DIGEST:?use the displayed SHA-256 digest}"

python3 "$TGD_REPO_ROOT/scripts/jira-sync.py" apply \
  --plan "$JIRA_PLAN_PATH" \
  --confirm "$PLAN_DIGEST"
```

## End-to-End Sequence

```text
TASKS.md → preview → list Projects → exact selection → discover fields
→ private answers → dry-run → display digest/actions → explicit confirmation
→ apply → verify remote issues → atomic Jira-field writeback → report
```
