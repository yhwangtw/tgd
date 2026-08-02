# Using tGD with Windsurf

## Setup

### Project Rules

Windsurf uses `.windsurfrules` for project-specific agent instructions:

```bash
# Create a combined rules file from your most important skills
cat /path/to/tGD/skills/tgd-develop-tdd/SKILL.md > .windsurfrules
echo "\n---\n" >> .windsurfrules
cat /path/to/tGD/skills/tgd-develop-incremental/SKILL.md >> .windsurfrules
echo "\n---\n" >> .windsurfrules
cat /path/to/tGD/skills/tgd-review-quality/SKILL.md >> .windsurfrules
```

### Global Rules

For skills you want across all projects, add them to Windsurf's global rules:

1. Open Windsurf → Settings → AI → Global Rules
2. Paste the content of your most-used skills

## Recommended Configuration

Keep `.windsurfrules` focused on 2-3 essential skills to stay within context limits:

```
# .windsurfrules
# Essential tGD for this project

[Paste tgd-develop-tdd SKILL.md]

---

[Paste tgd-develop-incremental SKILL.md]

---

[Paste tgd-review-quality SKILL.md]
```

## Usage Tips

1. **Be selective** — Windsurf's context is limited. Choose skills that address your biggest quality gaps.
2. **Reference in conversation** — Paste additional skill content into the chat when working on specific phases (e.g., paste `tgd-review-security` when building auth).
3. **Use references as checklists** — Paste `references/security-checklist.md` and ask Windsurf to verify each item.
