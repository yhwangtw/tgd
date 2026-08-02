from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


class DesignFlowContractTests(unittest.TestCase):
    def test_map_records_frontend_design_context(self) -> None:
        map_command = read(".claude/commands/tgd-map.md")
        context_template = read("templates/CONTEXT.md.tmpl")
        self.assertIn("templates/CONTEXT.md.tmpl", map_command)
        self.assertIn("## UI Landscape", context_template)
        self.assertIn("Design-system source", context_template)
        self.assertIn("Token source", context_template)

    def test_define_places_design_between_prd_and_spec(self) -> None:
        define_command = read(".claude/commands/tgd-define.md")
        prd = define_command.index("write PRD.md")
        design = define_command.index("UI Design Routing")
        spec = define_command.index("write/finalize SPEC.md")
        self.assertLess(prd, design)
        self.assertLess(design, spec)
        for mode in ("Existing approved design", "Extend existing product UI", "Explore a new experience", "No user-facing UI"):
            self.assertIn(mode, define_command)
        self.assertIn("Status to `direction-approved`", define_command)
        self.assertIn("`not-applicable` for mode 4", define_command)

    def test_sketch_uses_context_as_navigation_and_source_files_as_truth(self) -> None:
        sketch_skill = read("skills/tgd-define-sketch/SKILL.md")
        self.assertIn("CONTEXT.md is navigation, not the visual source of truth", sketch_skill)
        self.assertIn("0 variants", sketch_skill)
        self.assertIn("2 variants", sketch_skill)
        self.assertIn("3 variants", sketch_skill)

    def test_design_system_precedence_is_consistent(self) -> None:
        spec_skill = read("skills/tgd-define-spec/SKILL.md")
        frontend_skill = read("skills/tgd-develop-ui/SKILL.md")
        precedence = "Existing design system > approved DESIGN.md additions > tGD fallback defaults"
        self.assertIn(precedence, spec_skill)
        self.assertIn(precedence, frontend_skill)

    def test_downstream_phases_enforce_design_handoff(self) -> None:
        plan = read(".claude/commands/tgd-plan.md")
        verify = read(".claude/commands/tgd-verify.md")
        review = read(".claude/commands/tgd-review.md")
        release = read(".claude/commands/tgd-release.md")
        self.assertIn("DESIGN**: Direction Approved", plan)
        self.assertIn("Design Conformance Gate", verify)
        self.assertIn("## Design Conformance (if UI)", review)
        self.assertIn("DESIGN**: Implementation Approved", release)
        for phase in (verify, review, release):
            self.assertIn("PRD UI mode is 1–3", phase)

    def test_design_handoff_does_not_add_a_lifecycle_stage(self) -> None:
        rules = read("skills/tgd-core-rules/SKILL.md")
        self.assertIn("role handoffs resume the same Define phase", rules)
        self.assertIn("tGD has four human roles", rules)
        self.assertFalse((ROOT / ".claude/commands/tgd-design.md").exists())

    def test_public_docs_describe_the_context_grounded_design_flow(self) -> None:
        readme = read("README.md")
        self.assertIn("UI Landscape", readme)
        self.assertIn("PRD → design → SPEC", readme)
        self.assertIn("0 / 2 / 3", readme)
        self.assertIn("**DESIGN**", readme)
        for name in ("README.md", "README.zh-TW.md", "README.ja.md", "README.de.md"):
            translated = read(name)
            self.assertIn("prototype/conservative/index.html", translated)
            self.assertIn("prototype/strong-fit/index.html", translated)
            self.assertNotIn("prototype/variant-a.html", translated)

    def test_ci_runs_design_flow_contract_tests(self) -> None:
        workflow = read(".github/workflows/test-plugin-install.yml")
        self.assertIn("python3 -m unittest discover -s tests -p 'test_*.py'", workflow)

    def test_public_html_and_desktop_guide_match_the_same_flow(self) -> None:
        intro = read("docs/tGD-intro.html")
        site = read("docs/index.html")
        desktop = read("docs/claude-desktop-setup.md")
        self.assertIn("PRD → 0/2/3 design → SPEC", intro)
        self.assertIn("DESIGN — Experience", intro)
        self.assertIn("routes 0/2/3 UI design", site)
        self.assertIn("PRD → 0/2/3 UI design routing → final SPEC", desktop)
        for surface in (intro, site, desktop):
            self.assertNotIn("PRD + SPEC + DESIGN", surface)


if __name__ == "__main__":
    unittest.main()
