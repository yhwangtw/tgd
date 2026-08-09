# Sketch Patterns

Illustrative templates only. Variant counts, naming, grounding, interaction,
verification, output, and selection rules live in
[`tgd-define-sketch`](../skills/tgd-define-sketch/SKILL.md).

## Lifecycle Folder Shape

```text
$TGD_DIR/<feature-name>/prototype/
├── conservative/{index.html,README.md}
├── strong-fit/{index.html,README.md}
└── divergent/{index.html,README.md}
```

## Fast HTML Reset

```html
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                 "Helvetica Neue", Arial, sans-serif;
    -webkit-font-smoothing: antialiased;
    color: #1a1a1a;
    background: #fafafa;
    line-height: 1.5;
  }
</style>
```

## Variant README Shape

```markdown
## Variant: {stance name}

### Design stance
One sentence describing the governing principle.

### Key choices
- Layout: ...
- Typography: ...
- Color: ...
- Interaction: ...

### Trade-offs
- Strong at: ...
- Weak at: ...

### Best for
- Audience or use case this stance serves
```

## Head-to-Head Shape

```markdown
| Dimension | Calm editorial | Utilitarian dense | Playful split |
|---|---|---|---|
| Density | Low | High | Medium |
| Primary action visibility | Low | High | Medium |
| Scan-ability | High | Medium | Low |
| Feel | Calm | Tool-like | Energetic |

**Assessment:** Name the strongest fit, explain why, and identify the weakest
tradeoff rather than declaring every option equally good.
```

## Minimal Shared Tokens

```css
:root {
  --color-bg: #fafafa;
  --color-fg: #1a1a1a;
  --color-accent: #0066ff;
  --color-muted: #666;
  --radius: 8px;
  --font-display: "Inter", sans-serif;
  --font-body: -apple-system, BlinkMacSystemFont, sans-serif;
}
```
