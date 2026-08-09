from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ReleasePolicyOwnershipTests(unittest.TestCase):
    def test_ship_owns_rollout_thresholds_and_ci_owns_deployment_mechanics(self) -> None:
        ci = (ROOT / "skills" / "tgd-release-ci" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        ship = (ROOT / "skills" / "tgd-release-ship" / "SKILL.md").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("1% → 10% → 100%", ci)
        self.assertIn("`tgd-release-ship` owns rollout thresholds", ci)
        self.assertIn("5% → 25% → 50% → 100%", ship)
        self.assertIn("24–48 hours", ship)

        stages = ci.split("### Deployment Stages and Rollback", 1)[1].split(
            "## Environment and Secret Management", 1
        )[0]
        positions = [
            stages.index("release candidate to staging"),
            stages.index("Merge the PR to `main`"),
            stages.index("Deploy production from the landed `main` SHA"),
        ]
        self.assertEqual(sorted(positions), positions)
        self.assertIn("does not shorten that skill's longer rollout windows", stages)

    def test_regression_catalog_is_an_unconditional_release_artifact(self) -> None:
        manifest = (ROOT / "templates" / "manifest.yaml").read_text(
            encoding="utf-8"
        )
        block = manifest.split("  REGRESSION-CATALOG:", 1)[1]
        self.assertIn("producer: tgd-release", block)
        self.assertNotIn("conditional:", block)

    def test_all_readmes_describe_documentation_only_evidence(self) -> None:
        contracts = {
            "README.md": (
                "opened PR remains pending",
                "~15 minutes (from `/tgd-define` to `/tgd-release`)",
            ),
            "README.zh-TW.md": (
                "只 opened 的 PR 仍是 pending",
                "~15 分鐘（從 `/tgd-define` 到 `/tgd-release`）",
            ),
            "README.de.md": (
                "nur geöffneter PR bleibt pending",
                "~15 Minuten (von `/tgd-define` bis `/tgd-release`)",
            ),
            "README.ja.md": (
                "PR は pending のまま",
                "約15分（`/tgd-define` から `/tgd-release` まで）",
            ),
        }
        for name, (pending_phrase, stale_timing) in contracts.items():
            with self.subTest(readme=name):
                text = (ROOT / name).read_text(encoding="utf-8")
                self.assertIn("`N/A — documentation-only`", text)
                self.assertIn(pending_phrase, text)
                self.assertNotIn(stale_timing, text)

    def test_desktop_guide_matches_release_order(self) -> None:
        guide = (ROOT / "docs" / "claude-desktop-setup.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "Pre-launch/staging → merge + CI → landed-SHA production rollout",
            guide,
        )
        self.assertIn("documentation-only evidence", guide)


if __name__ == "__main__":
    unittest.main()
