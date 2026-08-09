# Wiki Generation Patterns

Illustrative shapes only. Fixed structure, input/output, prose, offline safety,
regeneration, and verification rules live in
[`tgd-support-wiki`](../skills/tgd-support-wiki/SKILL.md).

## Output Tree

```text
$TGD_DIR/wiki/
├── wiki.html
├── wiki-prose.json               # optional input, not generated
└── docs/
    ├── index.md
    ├── sources.md
    ├── manifest.json
    └── repos/<slug>/
        ├── index.md, overview.md, architecture.md, onboarding.md, files.md
        ├── files/*.md
        ├── modules/*.md
        ├── flows/*.md
        ├── diagrams/{index.md,architecture.mmd,dependencies.mmd}
        └── manifest.json
```

## Prose Sidecar Shape

```json
{
  "version": 1,
  "repos": {
    "<repo-slug>": {
      "overview": "How the repository and layers fit",
      "architecture": "Layering and dependency direction",
      "onboarding": "Narrated reading path",
      "layers": { "<layer-name>": "Responsibility" },
      "modules": { "<module-slug>": "Responsibility" },
      "flows": { "<flow-slug>": "Sequence narrative" },
      "files": {
        "<file-path>": {
          "summary": "File purpose",
          "hash": "<content-hash>",
          "symbols": { "<symbol-name>": "Purpose and gotchas" }
        }
      }
    }
  }
}
```

## Entry Points

| Audience | Entry point |
|---|---|
| Human | `$TGD_DIR/wiki/wiki.html` |
| Agent | `$TGD_DIR/wiki/docs/manifest.json` |
| Per-repo agent | `$TGD_DIR/wiki/docs/repos/<slug>/manifest.json` |
| Lifecycle stages | `$TGD_DIR/CONTEXT.md` |
