# tGD

This is the tGD project — a collection of production-grade engineering skills for AI coding agents.

## Project Structure

```
skills/       → Core skills (SKILL.md per directory)
agents/       → Reusable agent personas (code-reviewer, test-engineer, security-auditor)
hooks/        → Session lifecycle hooks
.claude/commands/ → Slash commands (/tgd-map, /tgd-define, /tgd-plan, /tgd-develop, /tgd-verify, /tgd-review, /tgd-release)
references/   → Supplementary checklists (testing, performance, security, accessibility)
docs/         → Setup guides for different tools
```

## Skills by Phase

**Define:** tgd-define-interview, tgd-define-ideate, tgd-define-spec, tgd-define-sketch
**Plan:** tgd-plan-breakdown, tgd-plan-jira
**Develop:** tgd-develop-incremental, tgd-develop-subagents, tgd-develop-tdd, tgd-core-context, tgd-develop-source, tgd-core-doubt, tgd-develop-ui, tgd-define-api, tgd-verify-completion
**Verify:** tgd-verify-browser, tgd-verify-debug
**Review:** tgd-review-quality, tgd-review-simplify, tgd-review-security, tgd-review-performance
**Release:** tgd-core-git, tgd-release-ci, tgd-release-migration, tgd-review-adr, tgd-release-ship
**Support:** tgd-support-wiki
**Meta (always-on):** tgd-core-router, tgd-core-rules

## Conventions

- Every skill lives in `skills/<name>/SKILL.md`
- YAML frontmatter with `name` and `description` fields
- Description starts with what the skill does (third person), followed by trigger conditions ("Use when...")
- Every skill has: Overview, When to Use, Process, Common Rationalizations, Red Flags, Verification
- References are in `references/`, not inside skill directories
- Supporting files only created when content exceeds 100 lines

## Commands

- `npm test` — Not applicable (this is a documentation project)
- Validate: Check that all SKILL.md files have valid YAML frontmatter with name and description

## Boundaries

- Always: Follow the skill-anatomy.md format for new skills
- Always: When adding or removing a skill, update `skills/tgd-core-router/SKILL.md` (decision tree + Quick Reference), the pipeline table in `skills/tgd-core-rules/SKILL.md`, and the Skills by Phase list above — the router must know every routable skill
- Always: Edit lifecycle commands in `.claude/commands/` only, then run `python3 scripts/generate-mirrors.py`
- Never: Hand-edit the platform mirrors (`.codex/skills/`, `.opencode/commands/`, `.gemini/commands/`, `.pi/prompts/`) — they are generated
- Never: Add skills that are vague advice instead of actionable processes
- Never: Duplicate content between skills — reference other skills instead
