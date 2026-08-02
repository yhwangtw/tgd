"""Contracts for the shared tGD artifact templates."""

from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"


class TemplateContractTests(unittest.TestCase):
    def test_manifest_lists_every_canonical_artifact(self) -> None:
        manifest = (TEMPLATES / "manifest.yaml").read_text(encoding="utf-8")
        for name in (
            "CONTEXT",
            "PRD",
            "SPEC",
            "DESIGN",
            "TASKS",
            "TRACKING-PLAN",
            "TEST-REPORT",
            "REVIEW",
            "ADR",
            "CHANGELOG",
            "METRICS",
            "REGRESSION-CATALOG",
        ):
            with self.subTest(name=name):
                self.assertIn(f"  {name}:\n", manifest)

    def test_all_templates_are_non_empty_raw_markdown(self) -> None:
        for template in TEMPLATES.glob("*.md.tmpl"):
            with self.subTest(template=template.name):
                content = template.read_text(encoding="utf-8")
                self.assertTrue(content.strip())
                self.assertTrue(content.startswith("# "))
                self.assertFalse(content.startswith("```"))

    def test_section_checker_reads_raw_templates(self) -> None:
        checker = ROOT / "scripts" / "check-doc-sections.py"
        for artifact in ("PRD", "SPEC", "DESIGN", "TASKS", "REVIEW"):
            with self.subTest(artifact=artifact):
                result = subprocess.run(
                    [
                        "python3",
                        str(checker),
                        artifact,
                        str(TEMPLATES / f"{artifact}.md.tmpl"),
                    ],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_capture_script_starts_from_shared_test_report_template(self) -> None:
        script = ROOT / "scripts" / "capture-test-output.sh"
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "TEST-REPORT.md"
            result = subprocess.run(
                ["bash", str(script), str(report), "printf '1 passed\\n'"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            content = report.read_text(encoding="utf-8")
            self.assertIn("# TEST-REPORT: [Feature Name]", content)
            self.assertIn("## Raw Test Output", content)
            self.assertIn("test-output-meta:", content)

    def test_workflow_sources_resolve_templates_from_repo_root(self) -> None:
        for relative_path in (
            ".claude/commands/tgd-map.md",
            ".claude/commands/tgd-review.md",
            ".claude/commands/tgd-release.md",
            ".claude/commands/tgd-verify.md",
        ):
            with self.subTest(relative_path=relative_path):
                command = (ROOT / relative_path).read_text(encoding="utf-8")
                self.assertIn("$TGD_REPO_ROOT/templates/", command)


if __name__ == "__main__":
    unittest.main()
