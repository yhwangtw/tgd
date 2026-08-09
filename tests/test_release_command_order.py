from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / ".claude" / "commands" / "tgd-release.md"


class ReleaseCommandOrderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.command = RELEASE.read_text(encoding="utf-8")

    def test_release_orders_gates_before_irreversible_progress(self) -> None:
        anchors = (
            "Chat or session approval does not replace an artifact sign-off",
            "complete its Pre-Launch Gates",
            "Run the pre-merge Regression Catalog Audit below.",
            "Deploy staging from the verified feature branch",
            "Land the feature on `main`",
            "continue `tgd-release-ship` from that exact SHA",
            "Clean up worktrees and landed branches only after",
        )
        positions = [self.command.index(anchor) for anchor in anchors]
        self.assertEqual(sorted(positions), positions)

    def test_open_pr_cannot_pass_or_trigger_cleanup(self) -> None:
        self.assertIn("Opening a PR is a pending state", self.command)
        self.assertIn("A merely opened PR does not pass", self.command)
        self.assertNotIn("merged to `main` (or PR opened)", self.command)
        self.assertIn(
            "Only after the merge landed and the initial production checks passed",
            self.command,
        )

    def test_chat_approval_cannot_replace_artifact_signoff(self) -> None:
        self.assertIn(
            "Chat or session approval does not replace an artifact sign-off",
            self.command,
        )
        self.assertNotIn("PM go-ahead in this session may replace", self.command)

    def test_production_uses_the_landed_sha(self) -> None:
        self.assertIn("deploy production from that SHA", self.command)
        self.assertIn(
            "never from the feature worktree or an unverified local HEAD",
            self.command,
        )


if __name__ == "__main__":
    unittest.main()
