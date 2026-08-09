"""Regression tests for coverage metric and AC carrier behavior."""

from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
COVERAGE_SCRIPT = ROOT / "scripts" / "coverage-check.sh"
AC_TRACE_SCRIPT = ROOT / "scripts" / "ac-trace.py"


class CoverageAndAcContractTests(unittest.TestCase):
    def run_coverage(
        self,
        runner="python",
        output="TOTAL 10 0 100%",
        allow_missing="",
        floors=None,
        critical=False,
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            if runner == "python":
                (project / "pyproject.toml").write_text("[project]\nname='fixture'\n")
            else:
                (project / "package.json").write_text('{"name":"fixture"}\n')
            fake = project / "fake-coverage.sh"
            fake.write_text(f"#!/bin/sh\nprintf '%s\\n' '{output}'\n")
            fake.chmod(0o700)
            env = os.environ.copy()
            for key in (
                "COVERAGE_ALLOW_MISSING_METRICS",
                "COVERAGE_LINE_FLOOR",
                "COVERAGE_BRANCH_FLOOR",
                "COVERAGE_FUNC_FLOOR",
            ):
                env.pop(key, None)
            if allow_missing:
                env["COVERAGE_ALLOW_MISSING_METRICS"] = allow_missing
            if floors:
                env.update(floors)
            if critical:
                env["COVERAGE_CRITICAL_PATH"] = "1"
            return subprocess.run(
                ["bash", str(COVERAGE_SCRIPT), str(fake)],
                cwd=project,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

    def test_missing_metrics_fail_closed_by_default(self):
        result = self.run_coverage()
        self.assertEqual(result.returncode, 2)
        self.assertIn("required metric(s): branches,functions", result.stdout)

    def test_explicit_noncritical_missing_metric_allowance_is_visible(self):
        for value in ("branches,functions", " branches , functions "):
            with self.subTest(value=value):
                result = self.run_coverage(allow_missing=value)
                self.assertEqual(result.returncode, 0)
                self.assertIn("Allowed missing metrics: branches,functions", result.stdout)
                self.assertIn("Coverage Exceptions", result.stdout)

    def test_partial_allowance_still_fails_closed(self):
        result = self.run_coverage(allow_missing="branches")
        self.assertEqual(result.returncode, 2)
        self.assertIn("required metric(s): functions", result.stdout)

    def test_reported_metrics_below_floors_exit_one(self):
        result = self.run_coverage(
            runner="npm", output="All files | 50 | 50 | 50 | 50 |"
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("Coverage gate FAILED", result.stdout)
        self.assertIn("lines: 50% < 80%", result.stdout)
        self.assertIn("branches: 50% < 60%", result.stdout)
        self.assertIn("functions: 50% < 90%", result.stdout)

    def test_malformed_reported_percentage_exits_two(self):
        result = self.run_coverage(
            runner="npm", output="All files | 100.0.0 | 100.0.0 | 100.0.0 | 100.0.0 |"
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("invalid percentage", result.stdout)

    def test_known_unavailable_markers_use_missing_metric_policy(self):
        for marker in ("Unknown", "N/A", "-"):
            output = f"All files | 100 | {marker} | {marker} | 100 |"
            with self.subTest(marker=marker, policy="default"):
                result = self.run_coverage(runner="npm", output=output)
                self.assertEqual(result.returncode, 2)
                self.assertIn("required metric(s): branches,functions", result.stdout)
            with self.subTest(marker=marker, policy="explicit-allowance"):
                result = self.run_coverage(
                    runner="npm",
                    output=output,
                    allow_missing="branches,functions",
                )
                self.assertEqual(result.returncode, 0)
                self.assertIn("Allowed missing metrics: branches,functions", result.stdout)

    def test_unavailable_line_marker_never_falls_back_to_statements(self):
        for marker in ("Unknown", "N/A", "-"):
            with self.subTest(marker=marker):
                result = self.run_coverage(
                    runner="npm",
                    output=f"All files | 100 | 100 | 100 | {marker} |",
                    allow_missing="branches,functions",
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn("Could not parse a line-coverage number", result.stdout)

    def test_allowance_never_waives_a_reported_low_metric(self):
        result = self.run_coverage(
            runner="npm",
            output="All files | 100 | 50 | 100 | 100 |",
            allow_missing="branches",
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("branches: 50% < 60%", result.stdout)

    def test_missing_line_metric_always_exits_two(self):
        result = self.run_coverage(
            output="coverage output has no TOTAL row",
            allow_missing="branches,functions",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("Could not parse a line-coverage number", result.stdout)

    def test_invalid_allowance_values_exit_two(self):
        for value in (
            "lines",
            "unknown",
            "branches,unknown",
            "branch es,fun ctions",
            "branches,",
            "branches,,functions",
            "branches\ninvalid",
            "branches\rinvalid",
        ):
            with self.subTest(value=value):
                result = self.run_coverage(allow_missing=value)
                self.assertEqual(result.returncode, 2)
                self.assertIn("Invalid COVERAGE_ALLOW_MISSING_METRICS", result.stdout)

    def test_floor_values_must_be_finite_percentages(self):
        for key in (
            "COVERAGE_LINE_FLOOR",
            "COVERAGE_BRANCH_FLOOR",
            "COVERAGE_FUNC_FLOOR",
        ):
            for value in ("not-a-number", "-1", "101"):
                with self.subTest(key=key, value=value):
                    result = self.run_coverage(floors={key: value})
                    self.assertEqual(result.returncode, 2)
                    self.assertIn(f"Invalid {key}", result.stdout)

    def test_critical_path_rejects_missing_metric_allowances(self):
        result = self.run_coverage(
            allow_missing="branches,functions", critical=True
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("Critical-path coverage cannot allow missing metrics", result.stdout)

    def test_critical_path_forces_line_and_branch_to_one_hundred(self):
        result = self.run_coverage(
            runner="npm",
            output="All files | 100 | 99 | 100 | 100 |",
            floors={"COVERAGE_LINE_FLOOR": "10", "COVERAGE_BRANCH_FLOOR": "10"},
            critical=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("branches: 99% < 100%", result.stdout)

    def test_doc_only_ac_contract_is_consistent(self):
        skill = (ROOT / "skills/tgd-develop-tdd/SKILL.md").read_text()
        command = (ROOT / ".claude/commands/tgd-verify.md").read_text()
        template = (ROOT / "templates/TASKS.md.tmpl").read_text()
        for text in (skill, command, template):
            self.assertIn("documentation-only", text)
            self.assertIn("Doc:", text)
        self.assertIn("cannot be `[R]`", skill)
        self.assertIn("cannot be `[R]`", command)

    def run_doc_trace(self, criterion, readme="Install the CLI"):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            feature = root / "feature"
            repo = root / "repo"
            feature.mkdir()
            repo.mkdir()
            (feature / "TASKS.md").write_text(criterion)
            (repo / "README.md").write_text(readme)
            return subprocess.run(
                [sys.executable, str(AC_TRACE_SCRIPT), str(feature), str(repo)],
                text=True,
                capture_output=True,
                check=False,
            )

    def run_trace_fixture(self, criterion, files):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            feature = root / "feature"
            repo = root / "repo"
            feature.mkdir()
            repo.mkdir()
            (feature / "TASKS.md").write_text(criterion)
            for relative, content in files.items():
                path = repo / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            return subprocess.run(
                [sys.executable, str(AC_TRACE_SCRIPT), str(feature), str(repo)],
                text=True,
                capture_output=True,
                check=False,
            )

    def test_executable_ac_requires_an_ac_tagged_test(self):
        criterion = '- **AC-1.1** Executable behavior works\n'
        passed = self.run_trace_fixture(
            criterion, {"test_feature.py": "# AC-1.1\ndef test_feature(): pass\n"}
        )
        self.assertEqual(passed.returncode, 0)
        failed = self.run_trace_fixture(criterion, {"test_feature.py": "def test_feature(): pass\n"})
        self.assertEqual(failed.returncode, 1)
        self.assertIn("NO valid test or Doc: carrier", failed.stdout)

    def test_valid_doc_carrier_passes_without_a_fabricated_test(self):
        result = self.run_doc_trace(
            '- **AC-1.1** Documentation is current\n'
            '  - **Doc:** `README.md` contains "Install the CLI"\n'
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("valid test or Doc: carrier", result.stdout)

    def test_valid_backticked_doc_path_may_contain_spaces(self):
        result = self.run_trace_fixture(
            '- **AC-1.1** Documentation is current\n'
            '  - **Doc:** `docs/User Guide.md` contains "Install the CLI"\n',
            {"docs/User Guide.md": "Install the CLI\n"},
        )
        self.assertEqual(result.returncode, 0)

    def test_malformed_doc_declaration_fails_even_with_test_tag(self):
        result = self.run_trace_fixture(
            '- **AC-1.1** Documentation is current\n'
            '  - **Doc:** `docs/User Guide.md` has text without contains syntax\n',
            {
                "docs/User Guide.md": "Install the CLI\n",
                "test_docs.py": "# AC-1.1\ndef test_docs(): pass\n",
            },
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("malformed Doc: carrier", result.stdout)

    def test_doc_text_inside_executable_criterion_is_not_a_carrier(self):
        result = self.run_trace_fixture(
            '- **AC-1.1** Then the visible label is "Doc:"\n',
            {"test_label.py": "# AC-1.1\ndef test_label(): pass\n"},
        )
        self.assertEqual(result.returncode, 0)

    def test_doc_example_inside_code_fence_is_not_a_carrier(self):
        result = self.run_trace_fixture(
            '- **AC-1.1** Executable behavior works\n'
            '```text\n'
            'Doc: `README.md` contains "Install the CLI"\n'
            '```\n',
            {"README.md": "Install the CLI\n"},
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("NO valid test or Doc: carrier", result.stdout)

    def test_missing_doc_evidence_fails(self):
        result = self.run_doc_trace(
            '- **AC-1.1** Documentation is current\n'
            '  - **Doc:** `README.md` contains "Missing phrase"\n'
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("NO valid test or Doc: carrier", result.stdout)

    def test_invalid_doc_cannot_be_bypassed_by_a_test_reference(self):
        result = self.run_trace_fixture(
            '- **AC-1.1** Documentation is current\n'
            '  - **Doc:** `README.md` contains "Missing phrase"\n',
            {
                "README.md": "Install the CLI\n",
                "test_docs.py": "# AC-1.1\ndef test_docs(): pass\n",
            },
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("NO valid test or Doc: carrier", result.stdout)

    def test_doc_carrier_cannot_be_regression_catalog_input(self):
        result = self.run_doc_trace(
            '- **AC-1.1** [R] Documentation is current\n'
            '  - **Doc:** `README.md` contains "Install the CLI"\n'
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("both [R] and Doc:-carried", result.stdout)

    def test_doc_path_cannot_escape_client_repo(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            feature = root / "feature"
            repo = root / "repo"
            feature.mkdir()
            repo.mkdir()
            outside = root / "outside.md"
            outside.write_text("external evidence\n")
            (repo / "escape.md").symlink_to(outside)

            carriers = (
                f'`{outside}` contains "external evidence"',
                '`../outside.md` contains "external evidence"',
                '`escape.md` contains "external evidence"',
            )
            for index, carrier in enumerate(carriers, start=1):
                with self.subTest(carrier=carrier):
                    (feature / "TASKS.md").write_text(
                        f'- **AC-1.{index}** Documentation is current\n'
                        f'  - **Doc:** {carrier}\n'
                    )
                    result = subprocess.run(
                        [sys.executable, str(AC_TRACE_SCRIPT), str(feature), str(repo)],
                        text=True,
                        capture_output=True,
                        check=False,
                    )
                    self.assertEqual(result.returncode, 1)
                    self.assertIn("unsafe, unreadable, missing, or lacks", result.stdout)

    def test_doc_carrier_rejects_invalid_utf8(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            feature = root / "feature"
            repo = root / "repo"
            feature.mkdir()
            repo.mkdir()
            (feature / "TASKS.md").write_text(
                '- **AC-1.1** Documentation is current\n'
                '  - **Doc:** `README.md` contains "a�b"\n'
            )
            (repo / "README.md").write_bytes(b"a\xffb")
            result = subprocess.run(
                [sys.executable, str(AC_TRACE_SCRIPT), str(feature), str(repo)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("unsafe, unreadable, missing, or lacks", result.stdout)

    def test_regression_test_carrier_is_contained_and_bound_to_ac(self):
        valid = self.run_trace_fixture(
            '- **AC-1.1** [R] Executable behavior works\n'
            '  - **Test:** `test_feature.py`\n',
            {"test_feature.py": "# AC-1.1\ndef test_feature(): pass\n"},
        )
        self.assertEqual(valid.returncode, 0)

        not_bound = self.run_trace_fixture(
            '- **AC-1.1** [R] Executable behavior works\n'
            '  - **Test:** `test_feature.py`\n',
            {
                "test_feature.py": "def test_feature(): pass\n",
                "test_other.py": "# AC-1.1\ndef test_other(): pass\n",
            },
        )
        self.assertEqual(not_bound.returncode, 1)
        self.assertIn("does not reference AC-1.1", not_bound.stdout)

    def test_regression_test_carrier_must_be_a_standalone_field(self):
        carriers = (
            '```text\nTest: `test_feature.py`\n```\n',
            'Inline example: Test: `test_feature.py`\n',
        )
        for carrier in carriers:
            with self.subTest(carrier=carrier):
                result = self.run_trace_fixture(
                    '- **AC-1.1** [R] Executable behavior works\n' + carrier,
                    {"test_feature.py": "# AC-1.1\ndef test_feature(): pass\n"},
                )
                self.assertEqual(result.returncode, 1)
                self.assertIn("have no 'Test:' file reference", result.stdout)

    def test_regression_test_path_cannot_escape_or_name_non_test(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            feature = root / "feature"
            repo = root / "repo"
            feature.mkdir()
            repo.mkdir()
            outside = root / "test_external.py"
            outside.write_text("# AC-1.1\ndef test_external(): pass\n")
            (repo / "test_escape.py").symlink_to(outside)
            (repo / "evidence.txt").write_text("AC-1.1\n")
            (repo / "test_internal.py").write_text(
                "# AC-1.1\ndef test_internal(): pass\n"
            )

            carriers = (str(outside), "../test_external.py", "test_escape.py", "evidence.txt")
            for carrier in carriers:
                with self.subTest(carrier=carrier):
                    (feature / "TASKS.md").write_text(
                        '- **AC-1.1** [R] Executable behavior works\n'
                        f'  - **Test:** `{carrier}`\n'
                    )
                    result = subprocess.run(
                        [sys.executable, str(AC_TRACE_SCRIPT), str(feature), str(repo)],
                        text=True,
                        capture_output=True,
                        check=False,
                    )
                    self.assertEqual(result.returncode, 1)

    def test_non_regression_test_discovery_ignores_external_symlink(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            feature = root / "feature"
            repo = root / "repo"
            feature.mkdir()
            repo.mkdir()
            (feature / "TASKS.md").write_text(
                '- **AC-1.1** Executable behavior works\n'
            )
            outside = root / "test_external.py"
            outside.write_text("# AC-1.1\ndef test_external(): pass\n")
            (repo / "test_link.py").symlink_to(outside)
            result = subprocess.run(
                [sys.executable, str(AC_TRACE_SCRIPT), str(feature), str(repo)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("NO valid test or Doc: carrier", result.stdout)


if __name__ == "__main__":
    unittest.main()
