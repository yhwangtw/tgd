# Using tGD with Cursor

## Setup

### Option 1: Rules Directory (Recommended)

Cursor supports a `.cursor/rules/` directory for project-specific rules:

```bash
# Create the rules directory
mkdir -p .cursor/rules

# Copy skills you want as rules
cp /path/to/tGD/skills/tgd-develop-tdd/SKILL.md .cursor/rules/tgd-develop-tdd.md
cp /path/to/tGD/skills/tgd-review-quality/SKILL.md .cursor/rules/tgd-review-quality.md
cp /path/to/tGD/skills/tgd-develop-incremental/SKILL.md .cursor/rules/tgd-develop-incremental.md
```

Rules in this directory are automatically loaded into Cursor's context.

### Option 2: .cursorrules File

Create a `.cursorrules` file in your project root with the essential skills inlined:

```bash
# Generate a combined rules file
cat /path/to/tGD/skills/tgd-develop-tdd/SKILL.md > .cursorrules
echo "\n---\n" >> .cursorrules
cat /path/to/tGD/skills/tgd-review-quality/SKILL.md >> .cursorrules
```

## Recommended Configuration

### Essential Skills (Always Load)

Add these to `.cursor/rules/`:

1. `tgd-develop-tdd.md` — TDD workflow and Prove-It pattern
2. `tgd-review-quality.md` — Five-axis review
3. `tgd-develop-incremental.md` — Build in small verifiable slices

### Phase-Specific Skills (Load on Demand)

For phase-specific work, create additional rule files as needed:

- `spec-development.md` -> `tgd-define-spec/SKILL.md`
- `tgd-develop-ui.md` -> `tgd-develop-ui/SKILL.md`
- `security.md` -> `tgd-review-security/SKILL.md`
- `performance.md` -> `tgd-review-performance/SKILL.md`

Add these to `.cursor/rules/` when working on relevant tasks, then remove when done to manage context limits.

## Usage Tips

1. **Don't load all skills at once** - Cursor has context limits. Load 2-3 essential skills as rules and add phase-specific skills as needed.
2. **Reference skills explicitly** - Tell Cursor "Follow the tgd-develop-tdd rules for this change" to ensure it reads the loaded rules.
3. **Use agents for review** - Copy `agents/code-reviewer.md` content and tell Cursor to "review this diff using this code review framework."
4. **Load references on demand** - When working on performance, add `performance.md` to `.cursor/rules/` or paste the checklist content directly.
