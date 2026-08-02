"""
tGD Plugin for Hermes Agent.

Registers 7 lifecycle slash commands (/tgd-map ... /tgd-release). An optional
pre_llm_call hook injects the bounded session preamble only when setup created
the explicit opt-in marker.

Command prompts are sourced from ~/tGD/.claude/commands/*.md — single source
of truth, shared with Claude Code / Codex / OpenCode.
"""

import os
import logging
from pathlib import Path
from typing import Optional, Set

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path resolution — find the tGD repo root
# ---------------------------------------------------------------------------

def _find_tgd_dir() -> Optional[Path]:
    """Resolve $TGD_DIR or fall back to common locations."""
    # 1. Environment variable
    env = os.environ.get("TGD_DIR")
    if env and Path(env).is_dir():
        return Path(env)

    # 2. Common clone locations
    candidates = [
        Path.home() / "tGD",
        Path.home() / "Projects" / "tGD",
        Path(__file__).resolve().parent.parent.parent.parent,  # .hermes/plugins/tgd/ → repo root (when installed from tGD repo itself)
    ]
    for c in candidates:
        if (
            (c / "skills" / "tgd-core-router" / "SKILL.md").exists()
            or (c / "skills" / "tgd-router" / "SKILL.md").exists()
        ):
            return c

    return None


TGD_DIR = _find_tgd_dir()


def _read_command_prompt(name: str) -> str:
    """Read a command prompt from .claude/commands/<name>.md.

    Falls back to a minimal message if the file is not found.
    """
    if TGD_DIR is None:
        return f"tGD: Cannot locate tGD installation. Set $TGD_DIR or clone to ~/tGD. Command /{name} unavailable."

    # Strip YAML frontmatter (--- ... ---) and return the body
    path = TGD_DIR / ".claude" / "commands" / f"{name}.md"
    if not path.exists():
        return f"tGD: Command file not found: {path}"

    text = path.read_text(encoding="utf-8")
    # Remove YAML frontmatter if present
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            text = text[end + 3:].lstrip("\n")

    return text


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def _make_handler(cmd_name: str):
    """Create a slash-command handler that returns the prompt text."""
    def handler(raw_args: str = "", **kwargs) -> str:
        del kwargs
        prompt = _read_command_prompt(cmd_name)
        # If user passed args (e.g. "/tgd-develop add login page"), append them
        if raw_args and raw_args.strip():
            prompt += f"\n\n## Additional Context\n\n{raw_args.strip()}"
        return prompt
    handler.__name__ = f"handle_{cmd_name.replace('-', '_')}"
    return handler


# ---------------------------------------------------------------------------
# Optional pre-LLM hook — inject the bounded preamble once per session
# ---------------------------------------------------------------------------

_INJECTED_SESSIONS: Set[str] = set()


def _session_preamble_enabled() -> bool:
    """Return true only after explicit setup opt-in."""
    if os.environ.get("TGD_SESSION_PREAMBLE") == "1":
        return True
    state_dir = Path(
        os.environ.get(
            "TGD_STATE_DIR",
            os.path.expanduser("~/.tgd"),
        )
    )
    return (state_dir / "session-preamble.enabled").is_file()


def _pre_llm_call(session_id: str = "", **kwargs):
    """Inject bounded tGD guidance once per session when explicitly enabled."""
    del kwargs

    if not _session_preamble_enabled() or TGD_DIR is None:
        return None

    session_key = session_id or "__unknown_session__"
    if session_key in _INJECTED_SESSIONS:
        return None

    preamble_path = TGD_DIR / "hooks" / "session-preamble.md"
    if not preamble_path.exists():
        logger.debug("tGD: session preamble not found at %s", preamble_path)
        return None

    _INJECTED_SESSIONS.add(session_key)
    return {"context": preamble_path.read_text(encoding="utf-8")}


def _on_session_end(session_id: str = "", **kwargs):
    """Release the once-per-session bookkeeping when Hermes closes a session."""
    del kwargs
    if session_id:
        _INJECTED_SESSIONS.discard(session_id)


# ---------------------------------------------------------------------------
# Plugin registration
# ---------------------------------------------------------------------------

_TGD_COMMANDS = [
    "tgd-map",
    "tgd-define",
    "tgd-plan",
    "tgd-develop",
    "tgd-verify",
    "tgd-review",
    "tgd-release",
]

_COMMAND_DESCRIPTIONS = {
    "tgd-map":     "Map — scan and understand the existing project context",
    "tgd-define":  "Define — create spec, PRD, and acceptance criteria",
    "tgd-plan":    "Plan — break the spec into ordered implementation tasks",
    "tgd-develop": "Develop — implement tasks incrementally with TDD",
    "tgd-verify":  "Verify — run tests and validate completion claims",
    "tgd-review":  "Review — multi-axis code review before merge",
    "tgd-release": "Release — create version tag and changelog",
}


def register(ctx):
    """Register all tGD commands and the dormant optional context hook."""
    # Register slash commands
    for cmd in _TGD_COMMANDS:
        ctx.register_command(
            name=cmd,
            handler=_make_handler(cmd),
            description=_COMMAND_DESCRIPTIONS.get(cmd, f"tGD {cmd} command"),
        )
        logger.debug("tGD: registered command /%s", cmd)

    ctx.register_hook("pre_llm_call", _pre_llm_call)
    ctx.register_hook("on_session_end", _on_session_end)
    logger.debug("tGD: registered optional pre_llm_call hook")

    logger.info("tGD plugin registered: %d commands", len(_TGD_COMMANDS))
