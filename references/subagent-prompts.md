# Subagent Prompts

Illustrative prompt scaffolding only. Dispatch order, review gates, retry
limits, evidence, and fallback behavior live in
[`tgd-develop-subagents`](../skills/tgd-develop-subagents/SKILL.md).

## Implementer

```text
You are implementing one task from an approved implementation plan.

WORKING DIRECTORY:
{worktree_path}

TASK:
{task_description_including_AC_ids}

RELEVANT FILES:
{file_list}

CONTEXT:
{relevant_context}

REQUIREMENTS:
1. Implement exactly the task scope.
2. Use Red-Green-Refactor; tests precede production code.
3. Every criterion test mentions its AC-<task>.<n> id.
4. Modify no unrelated files and fix no out-of-scope bugs.
5. Run the task's exact verification and commit the completed task.
6. Stop and report ambiguity that prevents safe implementation.

RETURN:
- commit SHA and changed-file summary
- observed test commands/results
- each AC id and its verifying test path
- out-of-scope bugs: file, symptom, suspected cause
```

For a `[repo-name]` task, `{worktree_path}` is that repository's isolated
worktree, never the main checkout or another repository's worktree.

## Spec Reviewer

```text
Review this task for specification compliance only.

TASK SPEC:
{task_description}

CODE CHANGES:
{diff_or_file_list}

CHECK:
1. Every required behavior is implemented.
2. No requirement or specified edge case is missing.
3. No behavior outside the task scope was added.

RETURN:
- PASS: one-line evidence that the task matches the spec
- FAIL: concrete missing, incorrect, or extra behavior
```

## Code-Quality Reviewer

```text
Review this already spec-compliant task for code quality.

CODE CHANGES:
{diff_or_file_list}

CHECK:
1. Readability and structure
2. Existing project patterns and architecture
3. Meaningful tests, not coverage-only assertions
4. Error and edge handling
5. Obvious performance risks
6. Obvious security risks

RETURN:
- PASS: one-line evidence and checks performed
- FAIL: concrete findings labeled critical, important, or nit
```

## Review-Fix Handoff

```text
Implement the same task in a fresh context.

ORIGINAL TASK:
{task_description}

REVIEW FINDINGS TO FIX:
{exact_fail_list}

Preserve task scope. Run the required verification and return the same evidence
as the implementer prompt.
```
