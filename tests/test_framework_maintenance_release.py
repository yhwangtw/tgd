"""Contracts for tGD's self-maintenance release path."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / ".claude" / "commands" / "tgd-release.md"
MARKERS = (
    "skills/tgd-core-rules/SKILL.md",
    ".claude/commands/tgd-release.md",
    "scripts/generate-mirrors.py",
    "scripts/release.sh",
    ".github/workflows/release.yml",
    "VERSION",
)


class FrameworkMaintenanceReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.command = RELEASE.read_text(encoding="utf-8")
        self.routing = self.command.split(
            "## Release path selection (HARD ROUTING GATE)", 1
        )[1].split("## Downstream feature pre-flight", 1)[0]
        self.maintenance = self.command.split(
            "## Framework maintenance release path", 1
        )[1].split("## Release pipeline", 1)[0]
        self.routing_flat = re.sub(r"\s+", " ", self.routing)
        self.maintenance_flat = re.sub(r"\s+", " ", self.maintenance)

    def test_route_is_selected_before_downstream_artifact_resolution(self) -> None:
        self.assertLess(
            self.command.index("Classify the release before resolving `$TGD_DIR`"),
            self.command.index("Resolve `$TGD_DIR` from its environment variable"),
        )
        self.assertIn("the downstream path wins", self.routing_flat)
        self.assertIn(
            "Missing lifecycle artifacts alone never qualify a release for this path",
            self.routing_flat,
        )
        self.assertIn("Do not run both paths", self.routing_flat)

    def test_framework_identity_requires_every_canonical_marker(self) -> None:
        self.assertIn("all six canonical tGD markers", self.routing_flat)
        self.assertIn("git rev-parse --show-toplevel", self.routing_flat)
        self.assertIn(
            "every marker must be a tracked regular file at that exact root",
            self.routing_flat,
        )
        for marker in MARKERS:
            with self.subTest(marker=marker):
                self.assertIn(f"`{marker}`", self.routing_flat)
                self.assertTrue((ROOT / marker).is_file())
        self.assertIn("not for a downstream product that uses tGD", self.routing_flat)

    def test_maintenance_pr_gate_uses_exact_current_evidence(self) -> None:
        anchors = (
            "exact remote branch head equal to local `HEAD`",
            "Record the reviewed PR head SHA",
            "green on every required check for that exact head SHA",
            "Merge only after step 2 passes",
            "provider reports the PR merged",
            "Record the landed `main` SHA",
        )
        positions = [self.maintenance_flat.index(anchor) for anchor in anchors]
        self.assertEqual(sorted(positions), positions)
        self.assertIn("ready for review (not draft)", self.maintenance_flat)
        self.assertIn("An opened PR remains pending", self.maintenance_flat)

    def test_native_prepare_publish_and_cleanup_order_is_fail_closed(self) -> None:
        anchors = (
            "bash scripts/release.sh --dry-run",
            "bash scripts/release.sh --yes",
            "VERSION-changing release commit reaches",
            "Wait for `.github/workflows/release.yml`",
            "immutable tag resolves to that release commit",
            "Delete the maintenance/release branches or worktrees",
        )
        positions = [self.maintenance_flat.index(anchor) for anchor in anchors]
        self.assertEqual(sorted(positions), positions)
        self.assertIn("dry run must leave the worktree unchanged", self.maintenance_flat)
        self.assertIn("does not publish a tag or GitHub Release", self.maintenance_flat)
        self.assertIn("failed check, merge, tag, or publication blocks cleanup", self.maintenance_flat)

    def test_exception_does_not_weaken_downstream_signoffs(self) -> None:
        self.assertIn("Chat approval cannot turn a downstream feature", self.routing_flat)
        self.assertIn("## Sign-off Gate (HARD GATE)", self.command)
        self.assertIn(
            "Chat or session approval does not replace an artifact sign-off",
            self.command,
        )
        self.assertIn("do not run the downstream release pipeline", self.maintenance_flat)

    def test_all_readmes_document_the_narrow_self_maintenance_path(self) -> None:
        locale_evidence = {
            "README.md": "narrowly scoped",
            "README.zh-TW.md": "嚴格限縮",
            "README.ja.md": "厳密に限定",
            "README.de.md": "eng begrenzten",
        }
        for filename, phrase in locale_evidence.items():
            with self.subTest(filename=filename):
                readme = (ROOT / filename).read_text(encoding="utf-8")
                flattened = re.sub(r"\s+", " ", readme)
                self.assertIn("`Framework maintenance`", flattened)
                self.assertIn("`$TGD_DIR`", flattened)
                self.assertIn("`main`", flattened)
                self.assertIn(phrase, flattened)


if __name__ == "__main__":
    unittest.main()
