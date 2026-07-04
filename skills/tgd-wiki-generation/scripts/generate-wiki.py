#!/usr/bin/env python3
"""
generate-wiki.py — Compile Understand-Anything + CodeGraph outputs into a
multi-repo Docusaurus MDX wiki under $TGD_DIR/wiki/.

Called by /tgd-map Step 6 (via the tgd-wiki-generation skill).

Every repo scanned in $TGD_DIR/.scans/<slug>/ gets its OWN full wiki
tree under $TGD_DIR/wiki/docs/repos/<slug>/, with overview, architecture,
onboarding, modules/, flows/, and diagrams/. The top-level docs/ hosts a
unified home page (repo selector grid) plus a shared sources page.

Usage:
    python generate-wiki.py <TGD_DIR> [--primary <slug>] [--dashboard-url URL] [--quiet]

Inputs:
    $TGD_DIR/.scans/<slug>/.understand-anything/knowledge-graph.json  (required per repo)
    $TGD_DIR/.scans/<slug>/.codegraph/                                (optional)

Outputs (all under $TGD_DIR/wiki/):
    docs/index.mdx                          ← home: repo selector grid
    docs/sources.mdx                        ← shared: source list
    docs/manifest.json                      ← top-level manifest (all repos)
    docs/repos/<slug>/index.mdx             ← per-repo home
    docs/repos/<slug>/overview.mdx
    docs/repos/<slug>/architecture.mdx
    docs/repos/<slug>/onboarding.mdx
    docs/repos/<slug>/modules/*.mdx
    docs/repos/<slug>/flows/*.mdx
    docs/repos/<slug>/source/*.mdx            ← offline source browser + line anchors
    docs/repos/<slug>/diagrams/index.mdx
    docs/repos/<slug>/diagrams/architecture.mmd
    docs/repos/<slug>/diagrams/dependencies.mmd
    docs/repos/<slug>/manifest.json         ← per-repo manifest
    src/components/*.tsx                    ← copied from skill assets
    src/css/custom.css                      ← copied from skill assets

Fails hard on unrecoverable errors (missing $TGD_DIR, no knowledge graph).
Degrades gracefully when optional per-repo data is missing.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from jinja2 import Environment, FileSystemLoader, Undefined
except ImportError:
    sys.stderr.write("Error: Jinja2 is required. Install with: pip install jinja2\n")
    sys.exit(2)


GENERATOR_VERSION = "0.3.0"
SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
TEMPLATE_DIR = SKILL_DIR / "templates" / "mdx"
ASSETS_DIR = SKILL_DIR / "assets"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class WikiModel:
    project: Dict[str, Any]
    layers: List[Dict[str, Any]]
    tour: List[Dict[str, Any]]
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    modules: List[Dict[str, Any]] = field(default_factory=list)
    flows: List[Dict[str, Any]] = field(default_factory=list)
    entry_points: List[Dict[str, Any]] = field(default_factory=list)
    repo_slug: str = ""
    repo_path: str = ""
    dashboard_url: Optional[str] = None
    architecture_mermaid: str = ""
    dependency_mermaid: str = ""
    patterns: List[Dict[str, Any]] = field(default_factory=list)
    node_paths: Dict[str, str] = field(default_factory=dict)
    source_files: List[Dict[str, Any]] = field(default_factory=list)
    generated_at: str = ""


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


_SLUG_RX = re.compile(r"[^a-z0-9]+")

_LAYER_ACCENT_HINTS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"ui|front", re.I), "ui"),
    (re.compile(r"api|route|http|controller", re.I), "api"),
    (re.compile(r"domain|service|business", re.I), "domain"),
    (re.compile(r"persist|db|database|model|repo", re.I), "persistence"),
    (re.compile(r"infra|deploy|docker|ops", re.I), "infra"),
]

_LAYER_ICON_HINTS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"ui|front", re.I), "🎨"),
    (re.compile(r"api|route|http", re.I), "🔌"),
    (re.compile(r"domain|service|business", re.I), "🧠"),
    (re.compile(r"persist|db|database|model|repo", re.I), "🗄️"),
    (re.compile(r"infra|deploy|docker|ops", re.I), "⚙️"),
]


def slugify(text: str) -> str:
    slug = _SLUG_RX.sub("-", (text or "").lower()).strip("-")
    return slug or "unnamed"


def infer_layer_accent(name: str) -> str:
    for rx, accent in _LAYER_ACCENT_HINTS:
        if rx.search(name or ""):
            return accent
    return "default"


def infer_layer_icon(name: str) -> str:
    for rx, icon in _LAYER_ICON_HINTS:
        if rx.search(name or ""):
            return icon
    return "🧩"


def log(msg: str, *, quiet: bool = False) -> None:
    if not quiet:
        sys.stderr.write(f"[tgd-wiki] {msg}\n")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# MDX escaping
# ---------------------------------------------------------------------------


def escape_mdx_inline(text: str) -> str:
    if not text:
        return ""
    return (
        text.replace("<", "&lt;").replace(">", "&gt;")
        .replace("{", r"\{").replace("}", r"\}")
    )


def escape_mdx_table_cell(text: str) -> str:
    if not text:
        return ""
    return escape_mdx_inline(text).replace("|", r"\|").replace("\n", " ")


# ---------------------------------------------------------------------------
# Scan discovery
# ---------------------------------------------------------------------------


def discover_repos(tgd_dir: Path) -> List[Tuple[str, Path]]:
    scans = tgd_dir / ".scans"
    if not scans.is_dir():
        return []
    repos: List[Tuple[str, Path]] = []
    for entry in sorted(scans.iterdir()):
        if entry.is_dir() and (entry / ".understand-anything" / "knowledge-graph.json").is_file():
            repos.append((entry.name, entry))
    return repos


def pick_primary_slug(
    repos: List[Tuple[str, Path]], requested: Optional[str]
) -> str:
    if not repos:
        raise SystemExit(
            "No repos with a knowledge-graph.json found under $TGD_DIR/.scans/. "
            "Run /tgd-map Step 4 first."
        )
    if requested:
        for slug, _ in repos:
            if slug == requested:
                return slug
        raise SystemExit(
            f"Requested primary repo '{requested}' not found. Available: "
            + ", ".join(s for s, _ in repos)
        )
    return repos[0][0]


# ---------------------------------------------------------------------------
# Model building
# ---------------------------------------------------------------------------


FILE_LEVEL_TYPES = {
    "file", "config", "document", "service", "pipeline",
    "table", "schema", "resource", "endpoint",
}


SYMBOL_TYPES = {"function", "class", "method", "interface", "type", "enum", "component"}


def source_slug(file_path: str) -> str:
    """Stable source-page slug for a repo-relative file path."""
    stem = _SLUG_RX.sub("-", (file_path or "source").lower()).strip("-")
    return stem or "source"


def source_href(repo_slug: str, file_path: str, line: Optional[int] = None) -> str:
    href = f"/repos/{repo_slug}/source/{source_slug(file_path)}"
    if line and line > 0:
        href += f"#L{line}"
    return href


def explicit_line(node: Dict[str, Any]) -> Optional[int]:
    """Read line number from common graph schemas, if present."""
    for key in ("startLine", "line", "lineNumber", "lineno"):
        value = node.get(key)
        if isinstance(value, int) and value > 0:
            return value
    for key in ("range", "location", "loc"):
        value = node.get(key) or {}
        if isinstance(value, dict):
            start = value.get("start") or value.get("begin") or {}
            if isinstance(start, dict):
                line = start.get("line") or start.get("lineNumber")
                if isinstance(line, int) and line > 0:
                    return line
    return None


def infer_symbol_line(repo_root: Path, file_path: str, symbol_name: str, node_type: str) -> Optional[int]:
    """Best-effort offline symbol locator.

    UA graphs do not consistently include line numbers. When the local source
    file exists, infer the line with conservative regexes. If no match is found,
    callers fall back to the file-level source page.
    """
    if not repo_root or not file_path or not symbol_name:
        return None
    path = (repo_root / file_path).resolve()
    try:
        if not path.is_file() or repo_root.resolve() not in path.parents:
            return None
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return None

    escaped = re.escape(symbol_name)
    patterns = [
        rf"^\s*(async\s+)?def\s+{escaped}\s*\(",
        rf"^\s*class\s+{escaped}\b",
        rf"^\s*(export\s+)?(async\s+)?function\s+{escaped}\s*\(",
        rf"^\s*(export\s+)?(const|let|var)\s+{escaped}\s*=",
        rf"^\s*(export\s+)?class\s+{escaped}\b",
        rf"^\s*(export\s+)?interface\s+{escaped}\b",
        rf"^\s*(export\s+)?type\s+{escaped}\b",
        rf"^\s*{escaped}\s*[:=]\s*",  # object method / property shorthand
    ]
    for i, line in enumerate(lines, start=1):
        if any(re.search(p, line) for p in patterns):
            return i
    return None


def collect_source_files(nodes: List[Dict[str, Any]], repo_root: Path) -> List[Dict[str, Any]]:
    seen: Dict[str, Dict[str, Any]] = {}
    for n in nodes:
        fp = n.get("filePath") or n.get("path") or ""
        if not fp:
            continue
        item = seen.setdefault(fp, {
            "path": fp,
            "slug": source_slug(fp),
            "href": "",  # filled by caller with repo slug
            "available": False,
            "line_count": 0,
            "language": language_for_path(fp),
            "lines": [],
        })
        full = (repo_root / fp).resolve() if repo_root else Path(fp)
        try:
            if repo_root and full.is_file() and repo_root.resolve() in full.parents:
                raw_lines = full.read_text(encoding="utf-8", errors="replace").splitlines()
                item["available"] = True
                item["line_count"] = len(raw_lines)
                item["lines"] = [
                    {"number": idx, "text": text}
                    for idx, text in enumerate(raw_lines, start=1)
                ]
        except Exception:
            pass
    return sorted(seen.values(), key=lambda x: x["path"])


def language_for_path(file_path: str) -> str:
    ext = Path(file_path).suffix.lower().lstrip(".")
    return {
        "py": "python",
        "ts": "typescript",
        "tsx": "tsx",
        "js": "javascript",
        "jsx": "jsx",
        "rs": "rust",
        "go": "go",
        "java": "java",
        "kt": "kotlin",
        "swift": "swift",
        "rb": "ruby",
        "php": "php",
        "cs": "csharp",
        "cpp": "cpp",
        "c": "c",
        "h": "c",
        "md": "markdown",
        "json": "json",
        "yaml": "yaml",
        "yml": "yaml",
        "toml": "toml",
        "sh": "bash",
    }.get(ext, "text")


def _node_map(nodes: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {n["id"]: n for n in nodes if "id" in n}


def _node_paths(nodes: List[Dict[str, Any]]) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for n in nodes:
        nid = n.get("id")
        if not nid:
            continue
        result[nid] = n.get("filePath") or n.get("path") or n.get("name") or nid
    return result


def build_modules(
    layers: List[Dict[str, Any]],
    node_map: Dict[str, Dict[str, Any]],
    edges: List[Dict[str, Any]],
    repo_slug: str,
    repo_root: Path,
) -> List[Dict[str, Any]]:
    modules: List[Dict[str, Any]] = []
    for layer in layers:
        title = layer.get("name") or layer.get("id") or "unnamed"
        slug = slugify(title)
        node_ids = layer.get("nodeIds") or layer.get("nodes") or []
        files: List[Dict[str, Any]] = []
        symbols: List[Dict[str, Any]] = []
        for nid in node_ids:
            node = node_map.get(nid)
            if not node:
                continue
            ntype = node.get("type")
            entry = {
                "path": node.get("filePath") or node.get("path") or node.get("name") or nid,
                "summary": node.get("summary") or "",
                "source_href": source_href(repo_slug, node.get("filePath") or node.get("path") or node.get("name") or nid),
            }
            if ntype in FILE_LEVEL_TYPES:
                files.append(entry)
            elif ntype in SYMBOL_TYPES:
                symbol_file = node.get("filePath") or node.get("path") or ""
                line = explicit_line(node) or infer_symbol_line(
                    repo_root, symbol_file, node.get("name") or nid, ntype or ""
                )
                symbols.append({
                    "name": node.get("name") or nid,
                    "file": symbol_file,
                    "line": line,
                    "source_href": source_href(repo_slug, symbol_file, line) if symbol_file else "",
                    "file_href": source_href(repo_slug, symbol_file) if symbol_file else "",
                    "summary": node.get("summary") or "",
                })
        symbols_capped = sorted(symbols, key=lambda s: s["name"])[:40]
        module_ids = set(node_ids)
        dep_mermaid = _module_dependency_mermaid(module_ids, edges, node_map, title)
        modules.append({
            "id": layer.get("id") or f"layer:{slug}",
            "title": title,
            "slug": slug,
            "summary": layer.get("description") or "",
            "files": files,
            "symbols": symbols_capped,
            "dependency_mermaid": dep_mermaid,
            "node_ids": sorted(module_ids),
            "file_count": len(files),
            "symbol_count": len(symbols_capped),
            "icon": infer_layer_icon(title),
            "accent": infer_layer_accent(title),
            "related_modules": [],
        })
    return modules


def _module_dependency_mermaid(
    module_ids: set,
    edges: List[Dict[str, Any]],
    node_map: Dict[str, Dict[str, Any]],
    label: str,
) -> str:
    subset = [
        e for e in edges
        if e.get("source") in module_ids and e.get("target") in module_ids
    ]
    if not subset:
        return f"graph TD\n  A[No internal edges in {label}]"
    lines = ["graph TD"]
    for e in subset[:60]:
        s = node_map.get(e["source"], {}).get("name") or e["source"]
        t = node_map.get(e["target"], {}).get("name") or e["target"]
        etype = e.get("type") or "->"
        lines.append(f'  {_mm_id(s)}[{s}] -->|{etype}| {_mm_id(t)}[{t}]')
    if len(subset) > 60:
        lines.append(f"  %% Truncated: {len(subset) - 60} more edges omitted")
    return "\n".join(lines)


def _mm_id(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", name)[:80] or "n"


def build_flows(
    tour: List[Dict[str, Any]], node_paths: Dict[str, str]
) -> List[Dict[str, Any]]:
    flows: List[Dict[str, Any]] = []
    for step in tour or []:
        title = step.get("title") or f"Step {step.get('order', '?')}"
        slug = slugify(title)
        files = [
            {"path": node_paths.get(nid, nid), "summary": ""}
            for nid in step.get("nodeIds") or []
        ]
        flows.append({
            "title": title,
            "slug": slug,
            "description": step.get("description") or "",
            "mermaid": _flow_sequence_mermaid(title, files),
            "files": files,
            "order": step.get("order", 0),
        })
    return flows


def _flow_sequence_mermaid(title: str, files: List[Dict[str, Any]]) -> str:
    if not files:
        return f"sequenceDiagram\n  Note over Flow: {title} (no files captured)"
    lines = ["sequenceDiagram"]
    actors: List[str] = []
    seen_actors = set()
    for f in files:
        actor = _mm_id(Path(f["path"]).stem or "step")
        if actor not in seen_actors:
            lines.append(f"  participant {actor}")
            seen_actors.add(actor)
        actors.append(actor)
    for i, actor in enumerate(actors):
        if i == 0:
            lines.append(f"  Note over {actor}: start")
        else:
            lines.append(f"  {actors[i-1]}->>+{actor}: next")
    return "\n".join(lines)


def build_architecture_mermaid(
    layers: List[Dict[str, Any]], edges: List[Dict[str, Any]], node_map: Dict[str, Dict[str, Any]]
) -> str:
    if not layers:
        return "graph TD\n  A[No layers detected]"
    node_to_layer: Dict[str, str] = {}
    for l in layers:
        for nid in l.get("nodeIds") or []:
            node_to_layer[nid] = l.get("id") or slugify(l.get("name") or "layer")
    layer_edges: Dict[Tuple[str, str], int] = {}
    for e in edges:
        src = e.get("source") or ""
        tgt = e.get("target") or ""
        s = node_to_layer.get(src)
        t = node_to_layer.get(tgt)
        if s and t and s != t:
            layer_edges[(s, t)] = layer_edges.get((s, t), 0) + 1
    lines = ["graph TD"]
    for l in layers:
        lid = l.get("id") or slugify(l.get("name") or "layer")
        lname = l.get("name") or lid
        lines.append(f'  {_mm_id(lid)}["{lname}"]')
    for (s, t), weight in sorted(layer_edges.items(), key=lambda kv: (-kv[1], kv[0]))[:30]:
        lines.append(f"  {_mm_id(s)} -->|{weight}| {_mm_id(t)}")
    return "\n".join(lines)


def build_dependency_mermaid(
    edges: List[Dict[str, Any]], node_map: Dict[str, Dict[str, Any]]
) -> str:
    counts: Dict[str, int] = {}
    for e in edges:
        counts[e.get("source", "")] = counts.get(e.get("source", ""), 0) + 1
        counts[e.get("target", "")] = counts.get(e.get("target", ""), 0) + 1
    top_list = [nid for nid, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:25]]
    top = set(top_list)
    if not top_list:
        return "graph TD\n  A[No edges]"
    lines = ["graph LR"]
    for nid in top_list:
        n = node_map.get(nid, {})
        lbl = n.get("name") or nid
        lines.append(f'  {_mm_id(nid)}["{lbl}"]')
    seen = 0
    for e in edges:
        if e.get("source") in top and e.get("target") in top:
            lines.append(f"  {_mm_id(e['source'])} --> {_mm_id(e['target'])}")
            seen += 1
            if seen >= 80:
                lines.append(f"  %% Truncated after 80 edges")
                break
    return "\n".join(lines)


def detect_entry_points(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    hits: List[Dict[str, Any]] = []
    entry_patterns = (
        "main.py", "__main__.py", "manage.py",
        "index.ts", "index.js", "main.ts", "main.tsx",
        "app.py", "server.ts", "server.js",
        "cmd/", "src/main.rs", "cli.py",
        "wsgi.py", "asgi.py",
    )
    seen = set()
    for n in nodes:
        fp = n.get("filePath") or n.get("path") or ""
        tags = n.get("tags") or []
        is_entry = any(fp.endswith(p) or f"/{p}" in f"/{fp}" for p in entry_patterns) or "entry" in tags
        if is_entry and fp and fp not in seen:
            seen.add(fp)
            hits.append({"path": fp, "kind": "entry"})
        if len(hits) >= 10:
            break
    return hits


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


class SilentUndefined(Undefined):
    def _fail_with_undefined_error(self, *args, **kwargs):  # type: ignore[override]
        return ""

    def __str__(self):
        return ""


def make_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        undefined=SilentUndefined,
        trim_blocks=False,
        lstrip_blocks=False,
        keep_trailing_newline=True,
    )
    env.filters["tojson"] = lambda v: json.dumps(v, ensure_ascii=False)
    return env


def render(env: Environment, template_name: str, ctx: Dict[str, Any]) -> str:
    return env.get_template(template_name).render(**ctx)


# ---------------------------------------------------------------------------
# Per-repo manifest
# ---------------------------------------------------------------------------


def build_repo_manifest(model: WikiModel, base_path: str) -> Dict[str, Any]:
    pages: List[Dict[str, Any]] = []

    def add(page_id: str, rel: str, page_type: str, summary: str, related=None):
        pages.append({
            "id": page_id,
            "path": rel,
            "type": page_type,
            "summary": summary,
            "relatedNodes": related or [],
        })

    slug = model.repo_slug
    add("index", f"wiki/docs/repos/{slug}/index.mdx", "index", f"{slug} wiki home")
    add("overview", f"wiki/docs/repos/{slug}/overview.mdx", "overview", model.project.get("description") or "")
    add("architecture", f"wiki/docs/repos/{slug}/architecture.mdx", "architecture", "Layers and dependencies")
    add("onboarding", f"wiki/docs/repos/{slug}/onboarding.mdx", "onboarding", "Suggested reading path")
    for m in model.modules:
        add(
            f"modules/{m['slug']}",
            f"wiki/docs/repos/{slug}/modules/{m['slug']}.mdx",
            "module",
            m["summary"],
            related=m.get("node_ids") or [],
        )
    for f in model.flows:
        add(
            f"flows/{f['slug']}",
            f"wiki/docs/repos/{slug}/flows/{f['slug']}.mdx",
            "flow",
            f["description"],
        )
    add("source", f"wiki/docs/repos/{slug}/source/index.mdx", "source-index", "Source browser")
    for sf in model.source_files:
        add(
            f"source/{sf['slug']}",
            f"wiki/docs/repos/{slug}/source/{sf['slug']}.mdx",
            "source-file",
            sf["path"],
        )
    add("diagrams", f"wiki/docs/repos/{slug}/diagrams/index.mdx", "diagrams",
        "Architecture and dependency diagrams")

    return {
        "generator": {
            "name": "tgd-wiki-generation",
            "version": GENERATOR_VERSION,
            "engine": "docusaurus",
            "generatedAt": model.generated_at,
        },
        "repo": {
            "slug": model.repo_slug,
            "name": model.project.get("name") or model.repo_slug,
            "description": model.project.get("description") or "",
            "path": model.repo_path,
            "languages": model.project.get("languages") or [],
            "frameworks": model.project.get("frameworks") or [],
            "basePath": base_path,
        },
        "entryPoints": model.entry_points,
        "importantFlows": [
            f"wiki/docs/repos/{slug}/flows/{f['slug']}.mdx" for f in model.flows
        ],
        "pages": pages,
    }


# ---------------------------------------------------------------------------
# Top-level manifest (all repos)
# ---------------------------------------------------------------------------


def build_top_manifest(
    repo_summaries: List[Dict[str, Any]],
    primary_slug: str,
    generated_at: str,
    dashboard_urls: Dict[str, Optional[str]],
) -> Dict[str, Any]:
    return {
        "generator": {
            "name": "tgd-wiki-generation",
            "version": GENERATOR_VERSION,
            "engine": "docusaurus",
            "generatedAt": generated_at,
        },
        "primaryRepoSlug": primary_slug,
        "repos": [
            {
                "slug": r["slug"],
                "name": r["name"],
                "description": r["description"],
                "path": r["path"],
                "basePath": f"/repos/{r['slug']}",
                "modules": r["modules"],
                "flows": r["flows"],
                "dashboardUrl": dashboard_urls.get(r["slug"]),
                "manifestPath": f"wiki/docs/repos/{r['slug']}/manifest.json",
            }
            for r in repo_summaries
        ],
        "topPages": [
            {"id": "index", "path": "wiki/docs/index.mdx", "type": "home"},
            {"id": "search", "path": "wiki/docs/search.mdx", "type": "search"},
            {"id": "sources", "path": "wiki/docs/sources.mdx", "type": "sources"},
        ],
    }


# ---------------------------------------------------------------------------
# Assets copy
# ---------------------------------------------------------------------------


def copy_assets(tgd_dir: Path, *, quiet: bool = False) -> None:
    wiki_dir = tgd_dir / "wiki"
    dest_components = wiki_dir / "src" / "components"
    dest_css = wiki_dir / "src" / "css"
    dest_components.mkdir(parents=True, exist_ok=True)
    dest_css.mkdir(parents=True, exist_ok=True)

    for f in sorted((ASSETS_DIR / "components").glob("*.tsx")):
        shutil.copy2(f, dest_components / f.name)
    for f in sorted((ASSETS_DIR / "css").glob("*.css")):
        shutil.copy2(f, dest_css / f.name)

    log(f"Copied React components → {dest_components}", quiet=quiet)
    log(f"Copied CSS → {dest_css}", quiet=quiet)


# ---------------------------------------------------------------------------
# Model compile (one per repo)
# ---------------------------------------------------------------------------


def compile_repo_model(
    graph: Dict[str, Any],
    repo_slug: str,
    repo_path: str,
    repo_root: Path,
    dashboard_url: Optional[str],
) -> WikiModel:
    project = graph.get("project") or {}
    layers = graph.get("layers") or []
    tour = graph.get("tour") or []
    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []

    escaped_project = dict(project)
    escaped_project["description"] = escape_mdx_inline(project.get("description") or "")

    escaped_layers: List[Dict[str, Any]] = []
    for l in layers:
        nl = dict(l)
        nl["description"] = escape_mdx_inline(l.get("description") or "")
        nl["accent"] = infer_layer_accent(l.get("name") or "")
        nl["node_count"] = len(l.get("nodeIds") or [])
        escaped_layers.append(nl)

    for n in nodes:
        n["summary"] = escape_mdx_inline(n.get("summary") or "")

    for t in tour:
        t["description"] = escape_mdx_inline(t.get("description") or "")

    node_map = _node_map(nodes)
    node_paths = _node_paths(nodes)
    modules = build_modules(escaped_layers, node_map, edges, repo_slug, repo_root)
    for m in modules:
        m["summary"] = escape_mdx_inline(m["summary"])
        for f in m["files"]:
            f["summary"] = escape_mdx_inline(f["summary"])
        for s in m["symbols"]:
            s["summary"] = escape_mdx_inline(s["summary"])

    flows = build_flows(tour, node_paths)
    entry_points = detect_entry_points(nodes)
    arch_mm = build_architecture_mermaid(escaped_layers, edges, node_map)
    dep_mm = build_dependency_mermaid(edges, node_map)
    source_files = collect_source_files(nodes, repo_root)
    for sf in source_files:
        sf["href"] = source_href(repo_slug, sf["path"])

    return WikiModel(
        project=escaped_project,
        layers=escaped_layers,
        tour=tour,
        nodes=nodes,
        edges=edges,
        modules=modules,
        flows=flows,
        entry_points=entry_points,
        repo_slug=repo_slug,
        repo_path=repo_path,
        dashboard_url=dashboard_url,
        architecture_mermaid=arch_mm,
        dependency_mermaid=dep_mm,
        patterns=[],
        node_paths=node_paths,
        source_files=source_files,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def infer_repo_path(scan_dir: Path, project: Any) -> str:
    # project can be a dict (real UA output), a string (simple graph),
    # or None — handle all three defensively.
    if isinstance(project, dict):
        root = project.get("rootPath") or project.get("primaryRepoPath")
        if root:
            return root
        name = project.get("name") or ""
    elif isinstance(project, str):
        name = project
    else:
        name = ""
    home = Path.home()
    guess = home / (name or scan_dir.name)
    return str(guess if guess.is_dir() else (scan_dir.name if not name else name))


# ---------------------------------------------------------------------------
# Rendering one repo's wiki tree
# ---------------------------------------------------------------------------


def render_repo(
    model: WikiModel,
    repo_docs_dir: Path,
    base_path: str,
    all_repos: List[Dict[str, Any]],
) -> None:
    env = make_env()

    kpi = {
        "files": sum(1 for n in model.nodes if n.get("type") in FILE_LEVEL_TYPES),
        "modules": len(model.modules),
        "flows": len(model.flows),
        "edges": len(model.edges),
    }

    ctx = {
        "generator_version": GENERATOR_VERSION,
        "generated_at": model.generated_at,
        "project": model.project,
        "repo_slug": model.repo_slug,
        "repo_path": model.repo_path,
        "base_path": base_path,  # e.g. "/repos/backend"
        "dashboard_url": model.dashboard_url,
        "modules": model.modules,
        "flows": model.flows,
        "source_files": model.source_files,
        "kpi": kpi,
        "all_repos": all_repos,
    }

    hero_title = f"{model.project.get('name') or model.repo_slug} — Project Wiki"
    hero_subtitle = model.project.get("description") or "Explore the architecture, modules, and flows of this codebase."

    write_text(
        repo_docs_dir / "index.mdx",
        render(env, "repo-index.mdx.jinja", {
            **ctx,
            "hero_title": hero_title,
            "hero_subtitle": hero_subtitle,
        }),
    )

    write_text(
        repo_docs_dir / "overview.mdx",
        render(env, "overview.mdx.jinja", {
            **ctx,
            "entry_points": model.entry_points,
            "layers": model.layers,
        }),
    )

    write_text(
        repo_docs_dir / "architecture.mdx",
        render(env, "architecture.mdx.jinja", {
            **ctx,
            "layers": model.layers,
            "architecture_mermaid": model.architecture_mermaid,
            "dependency_mermaid": model.dependency_mermaid,
            "patterns": model.patterns,
        }),
    )

    write_text(
        repo_docs_dir / "onboarding.mdx",
        render(env, "onboarding.mdx.jinja", {
            **ctx,
            "tour": model.tour,
            "node_paths": model.node_paths,
        }),
    )

    for m in model.modules:
        write_text(
            repo_docs_dir / "modules" / f"{m['slug']}.mdx",
            render(env, "module.mdx.jinja", {**ctx, "module": m}),
        )

    for f in model.flows:
        write_text(
            repo_docs_dir / "flows" / f"{f['slug']}.mdx",
            render(env, "flow.mdx.jinja", {**ctx, "flow": f}),
        )

    # source/*.mdx — offline source browser with line anchors for symbol jumps
    write_text(
        repo_docs_dir / "source" / "index.mdx",
        render(env, "source-index.mdx.jinja", {**ctx}),
    )
    for sf in model.source_files:
        write_text(
            repo_docs_dir / "source" / f"{sf['slug']}.mdx",
            render(env, "source-file.mdx.jinja", {
                **ctx,
                "source_file": sf,
                # JSON-encoded lines for the React component prop. Pass through
                # Jinja with `| safe` to avoid double-escaping the JSON.
                "source_file_lines_json": json.dumps(
                    sf.get("lines", []), ensure_ascii=False
                ),
            }),
        )

    write_text(
        repo_docs_dir / "diagrams" / "index.mdx",
        render(env, "diagrams-index.mdx.jinja", {
            **ctx,
            "architecture_mermaid": model.architecture_mermaid,
            "dependency_mermaid": model.dependency_mermaid,
        }),
    )
    write_text(repo_docs_dir / "diagrams" / "architecture.mmd", model.architecture_mermaid)
    write_text(repo_docs_dir / "diagrams" / "dependencies.mmd", model.dependency_mermaid)


# ---------------------------------------------------------------------------
# Top-level rendering (home + sources)
# ---------------------------------------------------------------------------


def render_top_level(
    docs_dir: Path,
    repo_summaries: List[Dict[str, Any]],
    primary_slug: str,
    generated_at: str,
) -> None:
    env = make_env()

    total_modules = sum(r["module_count"] for r in repo_summaries)
    total_flows = sum(r["flow_count"] for r in repo_summaries)

    ctx = {
        "generator_version": GENERATOR_VERSION,
        "generated_at": generated_at,
        "repos": repo_summaries,
        "primary_slug": primary_slug,
        "repo_count": len(repo_summaries),
        "total_modules": total_modules,
        "total_flows": total_flows,
    }

    write_text(
        docs_dir / "index.mdx",
        render(env, "home.mdx.jinja", ctx),
    )
    write_text(
        docs_dir / "sources.mdx",
        render(env, "sources.mdx.jinja", ctx),
    )
    write_text(
        docs_dir / "search.mdx",
        render(env, "search.mdx.jinja", ctx),
    )


def write_search_index(tgd_dir: Path, models: List[WikiModel]) -> None:
    """Emit a small offline search index consumed by LocalSearch.tsx."""
    items: List[Dict[str, Any]] = []

    def add(title: str, item_type: str, repo: str, path: str, summary: str = "", keywords=None):
        items.append({
            "title": title,
            "type": item_type,
            "repo": repo,
            "path": path,
            "summary": summary or "",
            "keywords": keywords or [],
        })

    for model in models:
        repo = model.repo_slug
        repo_name = model.project.get("name") or repo
        base = f"/repos/{repo}"
        add(repo_name, "repo", repo, base, model.project.get("description") or "",
            keywords=[repo, model.repo_path] + (model.project.get("languages") or []) + (model.project.get("frameworks") or []))
        add("Overview", "page", repo, f"{base}/overview", model.project.get("description") or "")
        add("Architecture", "page", repo, f"{base}/architecture", "Layers and dependencies")
        add("Onboarding", "page", repo, f"{base}/onboarding", "Suggested reading path")
        add("Source Browser", "page", repo, f"{base}/source", "Offline source browser")

        for m in model.modules:
            add(m["title"], "module", repo, f"{base}/modules/{m['slug']}", m.get("summary") or "",
                keywords=[f.get("path", "") for f in m.get("files") or []])
            for s in m.get("symbols") or []:
                add(
                    s.get("name") or "symbol",
                    "symbol",
                    repo,
                    s.get("source_href") or f"{base}/source",
                    s.get("summary") or "",
                    keywords=[s.get("file") or "", m["title"], str(s.get("line") or "")],
                )

        for f in model.flows:
            add(f["title"], "flow", repo, f"{base}/flows/{f['slug']}", f.get("description") or "")

        for sf in model.source_files:
            add(sf["path"], "source", repo, sf.get("href") or f"{base}/source/{sf['slug']}",
                f"{sf.get('line_count') or 0} lines" if sf.get("available") else "Source unavailable",
                keywords=[sf.get("language") or "", sf.get("slug") or ""])

    data_dir = tgd_dir / "wiki" / "src" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(items, ensure_ascii=False, indent=2)
    write_text(data_dir / "searchIndex.ts", f"// Auto-generated by tgd-wiki-generation. Do not edit.\nexport default {payload};\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate tGD multi-repo Wiki (Docusaurus MDX)")
    parser.add_argument("tgd_dir", help="$TGD_DIR path")
    parser.add_argument("--primary", help="Primary repo slug (defaults to first scan)")
    parser.add_argument("--dashboard-url", help="Dashboard URL to embed (applied to primary)")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    tgd_dir = Path(args.tgd_dir).expanduser().resolve()
    if not tgd_dir.is_dir():
        sys.stderr.write(f"Error: TGD_DIR does not exist: {tgd_dir}\n")
        return 2

    repos = discover_repos(tgd_dir)
    if not repos:
        sys.stderr.write(
            f"Error: no repos with knowledge-graph.json under {tgd_dir}/.scans/\n"
            f"Run /tgd-map Step 4 (Understand-Anything) first.\n"
        )
        return 2

    primary_slug = pick_primary_slug(repos, args.primary)
    log(f"Discovered {len(repos)} repo(s). Primary: {primary_slug}", quiet=args.quiet)

    docs_dir = tgd_dir / "wiki" / "docs"

    # Clear previous per-repo trees so removed repos don't leave stale pages
    repos_root = docs_dir / "repos"
    if repos_root.is_dir():
        shutil.rmtree(repos_root)

    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    repo_summaries: List[Dict[str, Any]] = []
    dashboard_urls: Dict[str, Optional[str]] = {}
    models: List[WikiModel] = []

    for slug, scan_dir in repos:
        graph_path = scan_dir / ".understand-anything" / "knowledge-graph.json"
        try:
            graph = load_json(graph_path)
        except Exception as e:
            log(f"⚠️  Skipping {slug}: cannot load graph ({e})", quiet=False)
            continue

        log(
            f"[{slug}] graph: {len(graph.get('nodes') or [])} nodes, "
            f"{len(graph.get('edges') or [])} edges, "
            f"{len(graph.get('layers') or [])} layers, "
            f"{len(graph.get('tour') or [])} tour steps",
            quiet=args.quiet,
        )

        repo_path = infer_repo_path(scan_dir, graph.get("project") or {})
        repo_root = Path(repo_path).expanduser().resolve() if repo_path else Path("")
        this_dashboard = args.dashboard_url if slug == primary_slug else None
        dashboard_urls[slug] = this_dashboard

        model = compile_repo_model(
            graph=graph,
            repo_slug=slug,
            repo_path=repo_path,
            repo_root=repo_root,
            dashboard_url=this_dashboard,
        )
        # override generated_at so all repos share one timestamp
        model.generated_at = generated_at
        models.append(model)

        proj = model.project
        icon = infer_layer_icon(proj.get("name") or slug)
        accent = infer_layer_accent(proj.get("name") or slug)
        repo_summaries.append({
            "slug": slug,
            "name": proj.get("name") or slug,
            "description": proj.get("description") or "",
            "path": repo_path,
            "modules": [{"slug": m["slug"], "title": m["title"], "icon": m["icon"]}
                        for m in model.modules],
            "flows": [{"slug": f["slug"], "title": f["title"]} for f in model.flows],
            "module_count": len(model.modules),
            "flow_count": len(model.flows),
            "source_count": len(model.source_files),
            "kpi": {
                "files": sum(1 for n in model.nodes if n.get("type") in FILE_LEVEL_TYPES),
                "edges": len(model.edges),
            },
            "icon": icon,
            "accent": accent,
            "is_primary": slug == primary_slug,
            "dashboard_url": this_dashboard,
        })

    if not models:
        sys.stderr.write("Error: no repos could be compiled.\n")
        return 2

    # Build all_repos view for cross-linking inside each repo tree
    all_repos = [
        {
            "slug": r["slug"],
            "name": r["name"],
            "base_path": f"/repos/{r['slug']}",
            "is_primary": r["is_primary"],
            "icon": r["icon"],
        }
        for r in repo_summaries
    ]

    # Render each repo
    for model in models:
        base_path = f"/repos/{model.repo_slug}"
        repo_docs_dir = docs_dir / "repos" / model.repo_slug
        log(f"Rendering repo → {repo_docs_dir}", quiet=args.quiet)
        render_repo(model, repo_docs_dir, base_path, all_repos)

        # Per-repo manifest
        manifest = build_repo_manifest(model, base_path)
        write_json(repo_docs_dir / "manifest.json", manifest)

    # Top-level home + sources + manifest
    log(f"Rendering top-level home → {docs_dir}/index.mdx", quiet=args.quiet)
    render_top_level(docs_dir, repo_summaries, primary_slug, generated_at)
    write_search_index(tgd_dir, models)

    top_manifest = build_top_manifest(repo_summaries, primary_slug, generated_at, dashboard_urls)
    write_json(docs_dir / "manifest.json", top_manifest)

    # Copy React assets + CSS
    copy_assets(tgd_dir, quiet=args.quiet)

    log("Done.", quiet=args.quiet)
    log(f"  Repos:    {len(models)}", quiet=args.quiet)
    log(f"  Primary:  {primary_slug}", quiet=args.quiet)
    log(f"  Home:     {docs_dir}/index.mdx", quiet=args.quiet)
    log(f"  Manifest: {docs_dir}/manifest.json", quiet=args.quiet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
