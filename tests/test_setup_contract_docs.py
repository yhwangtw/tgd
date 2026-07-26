"""Static contracts that keep setup documentation aligned with behavior."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SetupContractDocumentationTest(unittest.TestCase):
    def test_readme_describes_opt_in_dependencies_and_safe_upgrade(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("bash setup.sh --with-tools", readme)
        self.assertIn("bash setup.sh --with-browser", readme)
        self.assertIn("bash setup.sh --no-deps", readme)
        self.assertIn("ownership manifest", readme)
        self.assertNotIn(
            "tgd-agent-browser dependencies installed automatically",
            readme,
        )
        self.assertNotIn("clean broken symlinks", readme)

    def test_readme_describes_prepare_only_release_script(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn(
            "bash scripts/release.sh v2026.06.09 --yes",
            readme,
        )
        self.assertIn("CI tags and publishes", readme)
        self.assertNotIn("Update `TGD_VERSION` in `setup.sh`", readme)
        self.assertNotIn(
            "`tgd --release` | Create a GitHub release",
            readme,
        )

    def test_all_readme_translations_share_setup_and_release_contracts(self) -> None:
        for filename in (
            "README.md",
            "README.zh-TW.md",
            "README.ja.md",
            "README.de.md",
        ):
            with self.subTest(filename=filename):
                readme = (ROOT / filename).read_text(encoding="utf-8")
                self.assertIn("bash setup.sh --with-tools", readme)
                self.assertIn("bash setup.sh --with-browser", readme)
                self.assertIn("bash setup.sh --no-deps", readme)
                self.assertIn(
                    "bash scripts/release.sh v2026.06.09 --yes",
                    readme,
                )
                self.assertNotIn("TGD_VERSION", readme)
                self.assertNotIn("gh release create", readme)

    def test_gemini_guide_matches_installed_assets(self) -> None:
        guide = (ROOT / "docs" / "gemini-cli-setup.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("one `SessionStart` hook", guide)
        self.assertIn("merges", guide)
        self.assertIn("7 slash commands", guide)
        self.assertNotIn("five hooks", guide)
        self.assertNotIn("8 slash commands", guide)
        self.assertNotIn(
            'ln -sf "$(pwd)/.gemini/settings.json"',
            guide,
        )

    def test_opencode_guide_matches_installed_assets(self) -> None:
        guide = (ROOT / "docs" / "opencode-setup.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("7 slash commands", guide)
        self.assertIn("one plugin", guide)
        self.assertNotIn("No native slash commands", guide)
        self.assertNotIn("three plugins", guide)
        self.assertNotIn("**safe-edit**", guide)
        self.assertNotIn("**sdd-cache**", guide)

    def test_plugin_manifest_matches_repository_license(self) -> None:
        manifest = (ROOT / ".claude-plugin" / "plugin.json").read_text(
            encoding="utf-8"
        )

        self.assertIn('"license": "Apache-2.0"', manifest)
        self.assertNotIn('"license": "MIT"', manifest)

    def test_cli_help_matches_managed_install_location_and_uninstall(self) -> None:
        cli = (ROOT / "bin" / "tgd").read_text(encoding="utf-8")

        self.assertIn("Installed to ~/.local/bin/tgd", cli)
        self.assertIn("Remove only tGD-managed links and hooks", cli)
        self.assertNotIn("Remove all tGD deployments", cli)
        self.assertNotIn("Installed to /usr/local/bin/tgd", cli)

    def test_setup_ci_covers_supported_platforms_and_round_trip(self) -> None:
        workflow = (
            ROOT / ".github" / "workflows" / "test-plugin-install.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("ubuntu-latest", workflow)
        self.assertIn("macos-latest", workflow)
        self.assertIn("bash setup.sh --no-deps", workflow)
        self.assertIn("bash setup.sh --uninstall", workflow)
        self.assertIn("${{ runner.temp }}/tgd-test-home", workflow)


if __name__ == "__main__":
    unittest.main()
