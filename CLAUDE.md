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

**Define:** interview-me, idea-refine, spec-driven-development, sketch
**Plan:** planning-and-task-breakdown, jira-auto-sync
**Build:** incremental-implementation, subagent-driven-development, test-driven-development, context-engineering, source-driven-development, doubt-driven-development, frontend-ui-engineering, api-and-interface-design, verification-before-completion
**Verify:** agent-browser, debugging-and-error-recovery
**Review:** code-review-and-quality, code-simplification, security-and-hardening, performance-optimization
**Release:** git-workflow-and-versioning, ci-cd-and-automation, deprecation-and-migration, documentation-and-adrs, shipping-and-launch
**Meta (always-on):** router, rules

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
