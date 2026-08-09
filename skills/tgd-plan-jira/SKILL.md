---
name: tgd-plan-jira
description: "Preview, confirm, apply, and verify Jira Data Center issue sync from canonical TASKS.md. Use as an opt-in skill after /tgd-plan writes TASKS.md."
trigger: "After /tgd-plan generates TASKS.md, when the user chooses to preview Jira sync"
---

# Jira Auto-Sync (TASKS.md → Jira Issues)

## Overview

Use `scripts/jira-sync.py` for the complete sync. It parses canonical TASKS.md,
lists accessible Projects, builds a read-only plan, applies only the exact plan
the user confirmed, verifies remote issues, then writes verified Jira keys and
stable identities back to TASKS.md. Do not recreate it with ad-hoc `curl`,
inline Python, manual field edits, or Jira Agile APIs.

Sprint and every other required field follow the same create-metadata process;
no Jira field receives a separate workflow.

## Safety Contract

- Listing Projects and planning are read-only. Mutation requires the explicit
  apply choice and the displayed plan digest.
- Always list every accessible Project and require selection of one returned
  key. `JIRA_PROJECT` is a hint, never authorization.
- Read `JIRA_TOKEN` only from the process environment. Never accept it as an
  argument, request it in chat, persist it, print it, or disable TLS checks.
- Ask for every non-automatic field marked required by the selected Project and issue type. Use returned choices when available; never guess. Sprint follows this same rule and receives no special rejection or automatic assignment.
- Store required-field answers only in a new user-owned mode-`0600` regular JSON
  file, with defaults and optional per-task overrides. Never pass answers as
  command arguments. Bind normalized values into the plan digest.
- After create/update, GET and verify Project, stable identity, and CLI-owned
  fields before the CLI writes `**Jira:**` or `**Jira-Sync-ID:**`.
- A legacy heading key is only an adoption candidate. Apply must re-check its
  exact Project/key and absence of conflicting tGD ownership. Missing,
  duplicate, or differently owned candidates are conflicts and must never fall
  through to `create`.
- Stable IDs make retries reconcilable, not exactly-once. Concurrent clients
  can race; ambiguous or duplicate state requires human reconciliation.

## Prerequisites and Durable State

Resolve `$TGD_REPO_ROOT`, `$TGD_DIR/<feature-name>/TASKS.md`, `JIRA_URL`, and
environment-only `JIRA_TOKEN`. TASKS.md must follow `tgd-plan-breakdown` and
contain one immutable `tgd-source-<lowercase UUID v4>` `Jira-Source-ID`; every task carries
`**Jira:**` and `**Jira-Sync-ID:**`. Existing values are durable state and must
survive re-plans and repository moves.

If URL or token is absent, stop and ask the user to export it outside the
conversation, then resume. A migrated task keeps its single standalone heading
key and blank new fields until the CLI proposes digest-bound `adopt`; successful
apply removes the old token and fills both fields atomically.

Environment, schema, JSON, and command examples are optional. Load
[Jira Sync Patterns](../../references/jira-sync-patterns.md) only when a worked
shape helps; this skill remains the sole normative owner.

## Workflow

### 1. List Projects and require an exact choice

Run the CLI's read-only `projects` command and present every returned Project as
an exact key plus name with the Selection Protocol. Even if `JIRA_PROJECT` is configured, show the full list and require a reply. Reject free-typed keys that were not returned by the CLI.

### 2. Discover required fields and collect answers

Run `fields` for the chosen Project and issue type. Ask for every returned
non-automatic required field; show and restrict allowed choices when present.
Inspect its exact field id, display name, schema, and `allowed_values`, and
normalize allowed choices to stable Jira references before digest binding.
Use `defaults` for shared values and `tasks.<task-number>` only for overrides.
Sprint is ordinary metadata: ask only when required and never call
`/rest/agile/*`. Create the private answers file only when fields are required;
the CLI must reject unsafe file ownership, permissions, type, or symlinks.

### 3. Build and display the dry-run

Run `plan` with the canonical TASKS.md, exact Project, issue type, optional
answers, and a new private plan output. The `plan` subcommand is the dry-run: Jira access is GET-only, it must not create or update Jira issues, and it must not modify `TASKS.md`. Its only local write is a new mode-`0600` JSON plan; it
must refuse symlinks and existing outputs.

Display Jira origin, exact Project key/name, SHA-256 digest, every task's
`create`/`adopt`/`update`/`skip`/`conflict` operation, required-field answers,
operation totals, and validation failures. The digest binds TASKS.md, Jira
origin, Project, field metadata/answers, resolved issues, and operations.

On conflict, retain the inspectable plan and non-zero result. Show all candidate issue keys, but do not continue to apply. Reconcile the conflict and generate a new plan. `adopt` is a visually distinct, digest-bound operation allowed only for one
unambiguous legacy key in the selected Project with no conflicting tGD
ownership, re-checked immediately before write.

### 4. Obtain explicit apply confirmation

Show the exact Project and digest and offer only Apply or Cancel, defaulting to
Cancel. Only choice 1 authorizes mutation. Vague acknowledgement, old consent,
credentials, or a saved Project do not authorize writes.

### 5. Apply the confirmed digest

Run `apply` only with the reviewed plan and exact confirmed digest. The CLI must reject a missing or stale digest, a changed TASKS.md, a different Project, or changed plan inputs before performing writes. The CLI alone owns issue mutation,
remote verification, atomic TASKS.md writeback, and exit status.

### 6. Report, reconcile, and clean up

| Result | Meaning |
|---|---|
| `created` | Remote issue created and verified; inspect `writeback` |
| `updated` | Owned fields updated or legacy link adopted, then verified |
| `skipped` | Remote owned fields matched; local link may be filled |
| `conflicts` | Ownership/duplicate conflict; apply refused |
| `remote_unknown` | Jira may have written, but reconciliation is inconclusive |
| `failed` | Mutation or verification failed definitively |
| `writeback_pending` | Remote verified; locked local writeback failed |
| `aborted` | Remaining tasks not attempted after systemic failure |

Operations use singular `create`, `adopt`, `update`, `skip`, and `conflict`;
result keys above are canonical. Any conflict, unknown, failure, pending
writeback, or abort makes sync incomplete and non-zero. Re-list and re-plan;
never blindly retry create or hand-edit Jira fields.

After success or cancellation, remove private plan/answers. For incomplete
reconciliation, retain mode-`0600` files only until reported issue keys are
reconciled, then remove them.

## Stable Identity and Concurrency

`Jira-Source-ID` is the immutable document namespace. `Jira-Sync-ID` is the
durable task identity stored locally and remotely; summary matching is
forbidden. Generated identity uses exact Project key, source UUID, and immutable
task number—not title, feature, Story ID, or changing task content.

Verified writeback makes normal reruns idempotent but supplies neither
distributed locking nor exactly-once creation. Stop on a race, duplicate, or
ambiguous state and require human reconciliation before another apply.

## Interaction with `/tgd-plan`

`/tgd-plan` owns prompts and invokes this skill only after canonical TASKS.md is
written and the user chooses preview. Skipping means no Jira or TASKS.md
mutation: Jira fields stay unchanged and only new unsynced tasks remain `—`.
Skipping Jira leaves all Jira fields unchanged; only new unsynced tasks remain `—`. Skipping does not fail the Plan phase.

## When to Use

- After `/tgd-plan` produced canonical TASKS.md and the user chose preview
- For a safe update or reconciliation of a prior verified sync

Do not use for manual one-off creation, Jira Cloud-only APIs, Agile planning,
or background synchronization.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "The Project is saved" | Every run lists Projects and requires an exact choice. |
| "Credentials authorize apply" | Only the displayed digest confirmation does. |
| "A matching summary is the task" | Only stable sync identity may reconcile it. |
| "Retry a timed-out create" | Jira may have written; reconcile first. |
| "Sprint needs another flow" | It is an ordinary required field. |
| "The legacy key proves ownership" | It is only a digest-bound adoption hint. |

## Red Flags

- Mutation before exact Project, full plan, and digest confirmation
- Project auto-selection, guessed/omitted fields, or Agile field special cases
- PAT or field answers in chat, arguments, logs, `.env`, or unsafe files
- TASKS.md writeback before remote verification
- Summary matching, manual Jira-field edits, or silent legacy-key creation
- Whole-label-array replacement instead of adding only the owned sync label
- Exactly-once claims or silent retry/success for ambiguous results

## Verification

- [ ] All accessible Projects were listed and one returned exact key was selected.
- [ ] Dry-run made no Jira or TASKS.md mutation; full actions/digest were shown.
- [ ] Required fields were asked, normalized, displayed, and digest-bound.
- [ ] Apply used the exact confirmed Project and digest.
- [ ] Every local Jira key/identity followed remote verification and CLI writeback.
- [ ] Legacy keys were conflicts or explicit verified adoptions.
- [ ] Sprint was generic, no Agile API ran, and no PAT was exposed.
- [ ] Ambiguous, conflict, writeback, and aborted results remained incomplete.
