---
name: tgd-plan-jira
description: "Preview, confirm, apply, and verify Jira Data Center issue sync from canonical TASKS.md. Use as an opt-in skill after /tgd-plan writes TASKS.md."
trigger: "After /tgd-plan generates TASKS.md, when the user chooses to preview Jira sync"
---

# Jira Auto-Sync (TASKS.md → Jira Issues)

## Overview

Use `scripts/jira-sync.py` for the entire Jira sync. The CLI parses canonical
`TASKS.md`, lists accessible Jira Projects, builds a read-only plan, applies
only the exact plan the user confirmed, verifies every remote issue, and then
writes the verified Jira key and stable sync identity back to `TASKS.md`.

No Jira field is special-cased. Required fields are discovered from create
metadata, shown to the user, and bound into the reviewed plan. Sprint is handled
like any other field. The workflow does not call Jira Agile APIs and must not be
reimplemented with ad-hoc `curl`, inline Python, or manual TASKS.md edits.

## Safety Contract

- **No automatic writes.** Listing Projects and dry-run are read-only. Jira
  mutation requires an explicit apply action plus the displayed plan digest.
- **Exact Project choice every time.** Always list all accessible Projects and
  require the user to select one returned key. `JIRA_PROJECT`, if present, is a
  hint only and never authorizes selection or apply.
- **PAT is environment-only.** Read `JIRA_TOKEN` only from the process
  environment. Never accept a token argument, ask the user to paste it into
  chat, write it to `.env` or another file, or print it in logs/errors.
- **Generic required fields.** Ask for every non-automatic field marked
  required by the selected Project and issue type. Use returned choices when
  available; never guess. Sprint follows this same rule and receives no special
  rejection or automatic assignment. Do not call `/rest/agile/*`.
- **Private, digest-bound answers.** Put answers in a new mode-`0600` JSON file,
  never command arguments. Support defaults plus per-task overrides. Normalize
  allowed choices to stable Jira references and bind every value into the plan
  digest before asking for apply confirmation.
- **Verify before writeback.** After each create or update, GET the issue and
  verify its Project, stable sync identity, and CLI-owned fields. Only then may
  the CLI update `**Jira:**` and `**Jira-Sync-ID:**` in `TASKS.md`.
- **Legacy links require explicit adoption.** A standalone `[ENG-1234]` in an
  old task heading is a migration candidate, never proof of ownership. The
  dry-run must show `adopt`; apply must re-check the exact Project/key and that
  no tGD marker/property owns the issue. Missing, duplicate, or differently
  owned candidates are conflicts and must never fall through to `create`.
- **Do not promise exactly-once.** Stable sync IDs make normal retries
  reconcilable and successful reruns idempotent, but Jira provides no
  exactly-once guarantee across concurrent clients. Two simultaneous applies
  can still race before either client observes the other's issue.

## Prerequisites

Resolve `$TGD_REPO_ROOT` per `tgd-core-rules` and identify:

```text
TASKS_PATH = $TGD_DIR/<feature-name>/TASKS.md
JIRA_URL   = Jira Data Center base URL (process environment)
JIRA_TOKEN = Personal Access Token (process environment; secret)
ANSWERS    = Private JSON file created only when Jira reports extra required fields
```

`TASKS.md` must use the canonical `tgd-plan-breakdown` schema.
The document has one immutable source namespace and every task includes:

```markdown
> **Jira-Source-ID**: tgd-source-123e4567-e89b-42d3-a456-426614174000

**Jira:** —
**Jira-Sync-ID:** —
```

Existing values are durable sync state. Never clear or regenerate them during
a re-plan. If `JIRA_URL` or `JIRA_TOKEN` is absent, stop and ask the user to
export it outside the conversation, then resume. Never disable TLS certificate
verification.

For a migrated legacy task, keep one standalone heading key such as
`[ENG-1234]` plus `—` placeholders until the CLI proposes an explicit `adopt`.
Do not copy the old key into `**Jira:**` or remove it by hand. Successful apply
removes the heading token and fills both fields in one locked atomic writeback.

## Workflow

### 1. List Projects and require an exact choice

Run the CLI's read-only Project listing:

```bash
python3 "$TGD_REPO_ROOT/scripts/jira-sync.py" projects
```

Present every returned Project as exact key + name using the Selection
Protocol. Even if `JIRA_PROJECT` is configured, show the full list and require
a reply. Reject free-typed keys that were not returned by the CLI.

### 2. Discover required fields and collect answers

For the selected Project and issue type, run:

```bash
python3 "$TGD_REPO_ROOT/scripts/jira-sync.py" \
  fields \
  --project "<PROJECT_KEY>" \
  --issue-type "<ISSUE_TYPE>"
```

The JSON output lists every required field not filled automatically, including
its exact field id, display name, schema, and `allowed_values`. Ask the user for
each value. When choices are present, show them and accept only one of those
choices. When the same answer applies to every new issue, store it under
`defaults`; use `tasks.<task-number>` only for overrides.

Sprint is ordinary metadata here. Ask for it only when Jira marks it required,
using the same choice/value behavior as every other field. Do not call Agile
endpoints to invent separate Sprint behavior.

Create a new private mode-`0600` JSON answers file only when needed:

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

Never place these values directly in CLI arguments. The CLI rejects symlinked,
non-regular, non-user-owned, group-readable, or world-readable answer files.

### 3. Build the dry-run plan

For the selected exact Project key:

```bash
JIRA_PLAN_DIR="$(mktemp -d "${TMPDIR:-/tmp}/tgd-jira-plan.XXXXXX")"
JIRA_PLAN_PATH="$JIRA_PLAN_DIR/plan.json"
JIRA_ANSWERS_PATH="$JIRA_PLAN_DIR/answers.json" # only when answers are required
python3 "$TGD_REPO_ROOT/scripts/jira-sync.py" \
  plan \
  --tasks "$TASKS_PATH" \
  --project "<PROJECT_KEY>" \
  --issue-type "<ISSUE_TYPE>" \
  --answers "$JIRA_ANSWERS_PATH" \
  --output "$JIRA_PLAN_PATH"
```

Omit `--answers` when `fields` returned an empty required-field list.

The `plan` subcommand is the dry-run: Jira access is GET-only, it must not
create or update Jira issues, and it must not modify `TASKS.md`. Its only local
write is the reviewable mode-`0600` JSON plan inside the new private temporary
directory. The CLI refuses symlink targets and existing output files.
Show the user:

- Jira origin and selected Project key + name
- plan SHA-256 digest
- each task's proposed operation: `create`, `adopt`, `update`, `skip`, or `conflict`
- every required-field answer attached to each proposed `create`
- totals for every operation and any validation failure

The digest binds the current TASKS.md content, Jira origin, exact Project,
required-field metadata and answers, resolved issue metadata, and proposed
operations. Do not hide conflicts or collapse the plan to counts only.

The plan artifact is still written when validation finds a `conflict`, and the
command exits non-zero so it can be inspected. Show all candidate issue keys,
but do not continue to apply. Reconcile the conflict and generate a new plan.

`adopt` is a visually distinct, digest-bound migration operation. It is allowed
only when a task has one unambiguous legacy heading key, that issue exists in
the chosen Project, and it has no conflicting tGD ownership. The CLI must
re-check those conditions immediately before mutation.

### 4. Obtain explicit apply confirmation

After showing a conflict-free complete dry-run, ask:

```text
Apply this exact Jira plan?
1. Apply to <PROJECT_KEY> (digest: <SHA-256>)
2. Cancel

Choose one (default 2):
```

Only choice 1 authorizes mutation. A vague acknowledgement, prior consent,
configured credentials, or a saved Project is not confirmation.

### 5. Apply the confirmed digest

Run apply only after explicit confirmation:

```bash
python3 "$TGD_REPO_ROOT/scripts/jira-sync.py" \
  apply \
  --plan "$JIRA_PLAN_PATH" \
  --confirm "<SHA-256>"
```

The CLI must reject a missing or stale digest, a changed TASKS.md, a different
Project, or changed plan inputs before performing writes. It owns issue
creation/update, remote verification, atomic TASKS.md writeback, and its exit
status. Do not reproduce those operations manually.

### 6. Report and reconcile

Report each task as one of:

| Result | Meaning |
|---|---|
| `created` | Issue was created and verified remotely; inspect its per-task `writeback` state |
| `updated` | Existing CLI-owned fields were updated, or a legacy link was explicitly adopted, and verified remotely; inspect `writeback` |
| `skipped` | Remote owned fields already matched; the local Jira link may still be filled in |
| `conflicts` | Plan-time ownership or duplicate conflict; apply is refused |
| `remote_unknown` | Jira may have accepted a write, but safe reconciliation is inconclusive |
| `failed` | A task or verification failed definitively |
| `writeback_pending` | Remote issue verified, local locked atomic writeback failed |
| `aborted` | Tasks not attempted after a systemic Jira failure |

The wire-format result keys above are canonical; plan operations remain the
singular verbs `create`, `adopt`, `update`, `skip`, and `conflict`. Any non-zero
`conflicts`, `remote_unknown`, `failed`, `writeback_pending`, or `aborted`
makes the sync incomplete and must return non-zero.
Re-run Project listing and dry-run to reconcile; never blindly retry a create
or hand-edit the two Jira fields.

After a successful apply or a user cancellation, remove the private answers and
plan directory. If reconciliation is incomplete, retain the mode-`0600` files
only until the reported issue keys are reconciled, then remove them.

## Stable Identity and Concurrency

`> **Jira-Source-ID**:` is a lowercase UUID v4 namespace generated once for
the TASKS document. It prevents same-named features in different repositories
from sharing task identities and must survive repository moves and re-plans.

`**Jira-Sync-ID:**` is the durable task identity. The CLI stores the same
identity on the Jira issue and uses it to distinguish create, update, and
no-op operations. Summary matching alone is forbidden.

For a generated identity, the stable inputs are the exact Project key, immutable
document source UUID, and immutable task number. Feature, title, Story ID, and
task content may change during a safe re-plan and therefore must not create a
new identity while local writeback is pending.

This provides retry safety after a successful verified writeback. It does not
provide distributed locking or exactly-once creation. If concurrent clients
race, stop on duplicates or ambiguous state, report the issue keys, and require
human reconciliation before another apply.

## Interaction with `/tgd-plan`

`/tgd-plan` owns the user prompts and invokes this skill only after writing a
canonical TASKS.md. The sequence is fixed:

```text
TASKS.md → choose preview → list Projects → exact Project choice
→ discover required fields → ask and normalize answers → dry-run
→ display answers, digest, and actions → explicit apply confirmation → apply
→ verify remote issues → write back Jira fields → report
```

Skipping Jira leaves all Jira fields unchanged; only new unsynced tasks remain
`—`. Skipping does not fail the Plan phase.

## When to Use

- After `/tgd-plan` has produced a canonical `TASKS.md`
- When the user explicitly chooses to preview a Jira Data Center sync
- When an earlier verified sync needs a safe update or reconciliation pass

Do not use this skill for one-off manual issue creation, Jira Cloud-only APIs,
Agile board planning, or automatic background synchronization.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "The Project is saved, so selection is unnecessary" | A saved key is only a hint; every run lists Projects and requires an exact choice. |
| "Credentials are configured, so apply is already authorized" | Credentials grant capability, not user intent. Only the displayed digest confirmation authorizes apply. |
| "A matching summary is probably the same task" | Summaries change and are not unique. Only the stable sync ID may drive reconciliation. |
| "A timed-out create is safe to retry" | Jira may already have created it. Reconcile the stable marker first and report an unknown result if it is not unique. |
| "Sprint needs a separate workflow" | It is just another Jira field. Follow createmeta, ask only when required, and bind the answer into the same plan digest. |
| "The old `[ENG-1234]` proves ownership" | It is only a migration hint. Show `adopt`, confirm its digest, and re-check Project plus absence of other tGD ownership before writing. |

## Red Flags

- Jira create/update occurs before the dry-run digest is confirmed
- A configured or saved Project is selected without listing all Projects
- A PAT appears in chat, command arguments, `.env`, output, logs, or temp files
- A required field, including Sprint, is rejected, guessed, or silently omitted instead of being asked generically
- Required-field values appear directly in command arguments or a non-private answers file
- Jira Agile endpoints are called to special-case a field
- `TASKS.md` is updated before remote verification succeeds
- Summary text is treated as the unique sync identity
- A legacy bracket key silently becomes `create` or is copied into the new fields by hand
- An entire Jira labels array is rewritten instead of atomically adding only the owned sync label
- The agent claims exactly-once behavior across concurrent clients
- A conflict or ambiguous result is silently retried or reported as success

## Verification

- [ ] All accessible Projects were listed and the user selected an exact returned key
- [ ] Dry-run made no Jira or TASKS.md writes
- [ ] The full action list and SHA-256 digest were shown
- [ ] Every non-automatic required field was asked, normalized, displayed, and included in the digest for create actions
- [ ] Apply used the exact confirmed Project and digest
- [ ] Every written-back Jira key was verified remotely first
- [ ] `**Jira:**` and `**Jira-Sync-ID:**` were changed only by the CLI
- [ ] Every legacy heading key was either reported as a conflict or explicitly adopted and removed by verified atomic writeback
- [ ] Sprint was treated like any other field, no Agile API was used, and no PAT was persisted or exposed
- [ ] Conflicts, ambiguous results, and writeback failures were reported as incomplete
