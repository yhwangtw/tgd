from pathlib import Path
import subprocess
import tempfile
from typing import Optional
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "regression-gate.sh"


class RegressionCatalogAbsenceTests(unittest.TestCase):
    def run_gate(
        self, changelog: Optional[str] = None, catalog: Optional[str] = None
    ) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            artifacts = root / "artifacts"
            repo.mkdir()
            artifacts.mkdir()
            if changelog is not None:
                (artifacts / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
            if catalog is not None:
                (artifacts / "REGRESSION-CATALOG.md").write_text(
                    catalog, encoding="utf-8"
                )
            return subprocess.run(
                ["bash", str(SCRIPT), str(repo), str(artifacts)],
                text=True,
                capture_output=True,
                check=False,
            )

    def test_missing_catalog_is_exit_three_before_any_release(self) -> None:
        result = self.run_gate()
        self.assertEqual(3, result.returncode)
        self.assertIn("No release is recorded yet", result.stdout)

    def test_template_placeholder_does_not_count_as_a_release(self) -> None:
        result = self.run_gate("# Changelog\n\n## vYYYY.MM.DD\n")
        self.assertEqual(3, result.returncode)

    def test_missing_catalog_after_a_real_release_is_configuration_failure(self) -> None:
        result = self.run_gate("# Changelog\n\n## v2026.08.09\n")
        self.assertEqual(2, result.returncode)
        self.assertIn("missing after a recorded release", result.stdout)

    def test_seeded_empty_catalog_needs_no_test_runner(self) -> None:
        result = self.run_gate(
            "# Changelog\n\n## v2026.08.09.2\n",
            "# Regression Catalog\n\n> Last audited: 2026-08-09\n",
        )
        self.assertEqual(0, result.returncode)
        self.assertIn("0 entries", result.stdout)


if __name__ == "__main__":
    unittest.main()
