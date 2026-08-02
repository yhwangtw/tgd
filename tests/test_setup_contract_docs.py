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
        self.assertIn("Plain setup never runs `npm install -g`", readme)
        self.assertIn("repository-pinned pnpm through Corepack", readme)
        self.assertIn("under `vendor/understand-anything/`", readme)
        self.assertIn("Python 3.9", readme)
        self.assertIn("source or lockfile change triggers a rebuild", readme)
        self.assertIn("`~/.understand-anything-plugin`", readme)
        self.assertIn("`~/.agents/skills/<name>`", readme)
        self.assertIn("Use `--no-deps` to skip all", readme)
        self.assertIn("downloads and builds", readme)
        self.assertNotIn(
            "tgd-verify-browser dependencies installed automatically",
            readme,
        )
        self.assertNotIn("clean broken symlinks", readme)

    def test_readme_describes_prepare_only_release_script(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn(
            "bash scripts/release.sh --dry-run",
            readme,
        )
        self.assertIn(
            "bash scripts/release.sh --yes",
            readme,
        )
        self.assertNotIn("bash scripts/release.sh v2026.06.09", readme)
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
                self.assertIn("bash setup.sh --with-session-preamble", readme)
                self.assertIn("bash setup.sh --no-deps", readme)
                self.assertIn("on demand", readme)
                self.assertIn("npm install -g", readme)
                self.assertIn("Corepack", readme)
                self.assertIn("Node.js 22.12", readme)
                self.assertIn("Python 3.9", readme)
                self.assertIn("vendor/understand-anything/", readme)
                self.assertIn("`~/.understand-anything-plugin`", readme)
                self.assertIn("`~/.agents/skills/<name>`", readme)
                self.assertIn("clean worktree", readme)
                self.assertIn("`/hooks`", readme)
                self.assertIn(
                    "bash scripts/release.sh --dry-run",
                    readme,
                )
                self.assertIn(
                    "bash scripts/release.sh --yes",
                    readme,
                )
                self.assertNotIn(
                    "bash scripts/release.sh v2026.06.09",
                    readme,
                )
                self.assertNotIn("TGD_VERSION", readme)
                self.assertNotIn("gh release create", readme)

    def test_gemini_guide_matches_installed_assets(self) -> None:
        guide = (ROOT / "docs" / "gemini-cli-setup.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("one `SessionStart`", guide)
        self.assertIn("explicit opt-in", guide)
        self.assertIn("bash setup.sh --with-session-preamble", guide)
        self.assertIn("merges", guide)
        self.assertIn("7 slash commands", guide)
        self.assertIn("`~/.gemini/settings.json`", guide)
        self.assertIn("`gemini mcp`", guide)
        self.assertIn("bounded tGD session preamble", guide)
        self.assertIn("load `tgd-core-router` on demand", guide)
        self.assertNotIn("~/.gemini/config.json", guide)
        self.assertNotIn("Injects `tgd-core-router` meta-skill", guide)
        self.assertNotIn("five hooks", guide)
        self.assertNotIn("8 slash commands", guide)
        self.assertNotIn(
            'ln -sf "$(pwd)/.gemini/settings.json"',
            guide,
        )

    def test_gemini_skills_use_supported_one_level_discovery_paths(self) -> None:
        guide = (ROOT / "docs" / "gemini-cli-setup.md").read_text(
            encoding="utf-8"
        )
        workflow = (
            ROOT / ".github" / "workflows" / "test-plugin-install.yml"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "$HOME/.gemini/skills/$(basename \"$skill_dir\")",
            guide,
        )
        self.assertIn("one directory deep", guide)
        self.assertIn("`~/.agents/skills/<canonical-name>`", guide)
        self.assertIn("canonical path has a collision", guide)
        self.assertIn("`~/.understand-anything-plugin`", guide)
        self.assertNotIn("~/.gemini/skills/tGD", guide)
        self.assertNotIn("$HOME/.gemini/skills/tGD", guide)
        self.assertNotIn("$HOME/.gemini/skills/tGD|", workflow)
        self.assertIn(
            'for target in "$GITHUB_WORKSPACE"/skills/*; do',
            workflow,
        )
        self.assertIn(
            '$HOME/.gemini/skills/$(basename "$target")',
            workflow,
        )
        self.assertIn(
            'link="$HOME/.agents/skills/$(basename "$target")"',
            workflow,
        )
        self.assertIn(
            "$HOME/.understand-anything-plugin|$GITHUB_WORKSPACE/vendor/understand-anything/understand-anything-plugin",
            workflow,
        )

        for filename in (
            "README.md",
            "README.zh-TW.md",
            "README.ja.md",
            "README.de.md",
        ):
            with self.subTest(filename=filename):
                readme = (ROOT / filename).read_text(encoding="utf-8")
                self.assertIn(
                    "$HOME/.gemini/skills/$(basename \"$skill_dir\")",
                    readme,
                )
                self.assertNotIn("~/.gemini/skills/tGD", readme)

    def test_opencode_guide_matches_installed_assets(self) -> None:
        guide = (ROOT / "docs" / "opencode-setup.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("7 slash commands", guide)
        self.assertIn("native TypeScript plugins", guide)
        self.assertIn("does not install a session plugin", guide)
        self.assertIn("does not install a global `AGENTS.md`", guide)
        self.assertIn("model compliance", guide)
        self.assertIn("does not inject model context", guide)
        self.assertNotIn("session-availability log/notification", guide)
        self.assertNotIn("Workflows are enforced via `AGENTS.md`", guide)
        self.assertNotIn("These rules are enforced via `AGENTS.md`", guide)
        self.assertNotIn("does not have a native plugin system", guide)
        self.assertNotIn("Injects `tgd-core-router` meta-skill", guide)
        self.assertNotIn("No native slash commands", guide)
        self.assertNotIn("three plugins", guide)
        self.assertNotIn("**safe-edit**", guide)
        self.assertNotIn("**sdd-cache**", guide)
        self.assertNotIn("client.app.log", guide)

    def test_session_preamble_describes_bounded_hook_context(self) -> None:
        preamble = (ROOT / "hooks" / "session-preamble.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("explicit setup opt-in", preamble)
        self.assertIn("preamble at session start", preamble)
        self.assertIn("does not inject the full router", preamble)
        self.assertIn("OpenCode has no tGD", preamble)

    def test_platform_adapters_use_supported_activation_surfaces(self) -> None:
        generator = (ROOT / "scripts" / "generate-mirrors.py").read_text(
            encoding="utf-8"
        )
        hermes_plugin = (
            ROOT / ".hermes" / "plugins" / "tgd" / "__init__.py"
        ).read_text(encoding="utf-8")

        self.assertIn('.codex" / "skills"', generator)
        self.assertNotIn('.codex" / "prompts"', generator)
        self.assertIn("APPEND_SYSTEM.md", generator)
        self.assertNotIn("PI_INSTRUCTIONS", generator)
        self.assertIn('register_hook("pre_llm_call"', hermes_plugin)
        self.assertNotIn('register_hook("on_session_start"', hermes_plugin)

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

    def test_setup_completion_message_uses_platform_native_invocation(self) -> None:
        setup = (ROOT / "setup.sh").read_text(encoding="utf-8")

        self.assertIn("Codex: \\$tgd-map", setup)
        self.assertIn("Claude/Gemini/OpenCode/Pi/Hermes: /tgd-map", setup)
        self.assertNotIn("Then type '/tgd-map' to initialize.", setup)

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
