#!/usr/bin/env python3
"""Compatibility shim for the retired Codex-only hook merger.

Older setup integrations invoke this file with ``TGD_ABS`` and ``HOOKS_DST``.
Delegate them to the ownership-safe cross-platform merger so those callers get
the same exact-path matching, atomic writes, and current Codex hook contract.
"""

import os
from pathlib import Path
import subprocess
import sys


def main() -> int:
    repo_root = os.environ.get("TGD_ABS", "")
    destination = os.environ.get("HOOKS_DST", "")
    if not repo_root or not destination:
        print(
            "error: TGD_ABS and HOOKS_DST environment variables are required",
            file=sys.stderr,
        )
        return 1

    helper = Path(__file__).resolve().with_name("merge-agent-hooks.py")
    return subprocess.call(
        [
            sys.executable,
            str(helper),
            "install",
            "--platform",
            "codex",
            "--repo-root",
            repo_root,
            "--destination",
            destination,
        ]
    )


if __name__ == "__main__":
    sys.exit(main())
