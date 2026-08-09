"""Behavior contracts for the seven-stage tGD workflow."""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "tests" / "fixtures" / "workflow-contract.json"
PHASES = [
    "tgd-map",
    "tgd-define",
    "tgd-plan",
    "tgd-develop",
    "tgd-verify",
    "tgd-review",
    "tgd-release",
]
SCENARIOS = {
    "tgd-map": {"tier-1", "tier-2-available", "tier-2-unavailable-degraded"},
    "tgd-define": {
        "non-ui", "ui-mode-1", "ui-mode-2", "ui-mode-3", "missing-design",
        "direction-not-approved", "direction-approved",
    },
    "tgd-plan": {"new", "replan", "jira-skip", "jira-required-fields", "jira-conflict", "jira-stale-digest"},
    "tgd-develop": {
        "delegation-available", "delegation-unavailable-inline", "dirty-worktree",
        "blocked-task", "resume", "two-stage-reviews",
    },
    "tgd-verify": {
        "test-failure", "documentation-only", "missing-ac", "missing-ui-evidence",
        "regression", "success",
    },
    "tgd-review": {
        "general", "documentation-only", "conditional-security",
        "conditional-performance", "conditional-adr", "blocking-finding",
    },
    "tgd-release": {
        "signoffs", "documentation-only", "regression", "metrics", "merge",
        "release", "migration", "successful-deploy", "framework-maintenance",
    },
}
ALLOWED_ARTIFACT_ROLES = {"consumed", "produced", "conditional", "mutated"}
ALLOWED_BEHAVIOR_TYPES = {"boundary", "gate", "handoff", "routing", "selection"}
TOP_LEVEL_FIELDS = {"version", "phase_order", "policy", "stages", "behaviors", "forbidden"}
POLICY_FIELDS = {
    "contract_kind", "formal_semantic_proof", "owners_are_normative",
    "duplicates_are_removable",
}
STAGE_FIELDS = {"source", "skills", "artifacts", "invariants", "scenarios", "next"}
BEHAVIOR_REQUIRED_FIELDS = {"type", "owner", "clause", "anchors"}
BEHAVIOR_OPTIONAL_FIELDS = {"opposite_clauses", "duplicates", "duplicate_clause"}


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def owner_evidence(rule: dict, reader=read) -> tuple[list[str], list[str]]:
    """Evaluate evidence from the normative owner, never from duplicates."""

    owner = normalize_whitespace(reader(rule["owner"]))
    required = [rule["clause"], *rule["anchors"]]
    missing = [item for item in required if normalize_whitespace(item) not in owner]
    forbidden = [
        item for item in rule.get("opposite_clauses", [])
        if normalize_whitespace(item) in owner
    ]
    return missing, forbidden


def artifacts() -> dict[str, dict[str, str]]:
    """Parse the intentionally simple artifact manifest without PyYAML."""

    result: dict[str, dict[str, str]] = {}
    current = None
    active = False
    for line in read("templates/manifest.yaml").splitlines():
        if line == "artifacts:":
            active = True
            continue
        if not active:
            continue
        match = re.fullmatch(r"  ([A-Z][A-Z-]*):", line)
        if match:
            current = match.group(1)
            result[current] = {}
            continue
        match = re.fullmatch(r"    ([a-z_]+): (.+)", line)
        if current and match:
            result[current][match.group(1)] = match.group(2)
    return result


def load_generator():
    path = ROOT / "scripts" / "generate-mirrors.py"
    spec = importlib.util.spec_from_file_location("tgd_mirror_generator", path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WorkflowSemanticContractTests(unittest.TestCase):
    def test_ac_1_0_schema_and_policy_are_explicit(self) -> None:
        """AC-1.0: every fixture field has a validated contract meaning."""

        data = contract()
        self.assertEqual(set(data), TOP_LEVEL_FIELDS)
        self.assertEqual(data["version"], 1)
        self.assertEqual(set(data["policy"]), POLICY_FIELDS)
        self.assertEqual(
            data["policy"]["contract_kind"],
            "prose contract with independent review",
        )
        self.assertIs(data["policy"]["formal_semantic_proof"], False)
        self.assertIs(data["policy"]["owners_are_normative"], True)
        self.assertIs(data["policy"]["duplicates_are_removable"], True)

        for name, stage in data["stages"].items():
            with self.subTest(stage=name):
                self.assertEqual(set(stage), STAGE_FIELDS)
                self.assertIsInstance(stage["source"], str)
                self.assertIsInstance(stage["skills"], list)
                self.assertIsInstance(stage["artifacts"], list)
                self.assertIsInstance(stage["invariants"], list)
                self.assertIsInstance(stage["scenarios"], dict)
                self.assertTrue(stage["next"] is None or isinstance(stage["next"], str))

        allowed_fields = BEHAVIOR_REQUIRED_FIELDS | BEHAVIOR_OPTIONAL_FIELDS
        for rule_id, rule in data["behaviors"].items():
            with self.subTest(rule=rule_id):
                self.assertTrue(BEHAVIOR_REQUIRED_FIELDS.issubset(rule))
                self.assertTrue(set(rule).issubset(allowed_fields))
                self.assertIn(rule["type"], ALLOWED_BEHAVIOR_TYPES)
                self.assertTrue(rule["owner"])
                self.assertTrue(rule["clause"])
                self.assertIsInstance(rule["anchors"], list)
                self.assertIsInstance(rule.get("opposite_clauses", []), list)
                self.assertIsInstance(rule.get("duplicates", []), list)
                self.assertEqual("duplicate_clause" in rule, "duplicates" in rule)

        forbidden_ids = set()
        for rule in data["forbidden"]:
            self.assertEqual(set(rule), {"id", "absent"})
            self.assertNotIn(rule["id"], forbidden_ids)
            forbidden_ids.add(rule["id"])
            self.assertFalse((ROOT / rule["absent"]).exists())

    def test_ac_1_1_contract_covers_all_stages_and_scenarios(self) -> None:
        """AC-1.1: all seven phases and required scenarios are represented."""

        data = contract()
        self.assertEqual(data["phase_order"], PHASES)
        self.assertEqual(list(data["stages"]), PHASES)
        commands = sorted(path.stem for path in (ROOT / ".claude" / "commands").glob("tgd-*.md"))
        self.assertEqual(commands, sorted(PHASES))
        expected_next = PHASES[1:] + [None]
        manifest = artifacts()

        for artifact, metadata in manifest.items():
            with self.subTest(artifact=artifact):
                self.assertIn(metadata["producer"], PHASES)
                self.assertTrue((ROOT / "templates" / metadata["file"]).is_file())

        for index, (name, stage) in enumerate(data["stages"].items()):
            with self.subTest(stage=name):
                self.assertEqual(stage["source"], f".claude/commands/{name}.md")
                self.assertEqual(stage["next"], expected_next[index])
                self.assertEqual(set(stage["scenarios"]), SCENARIOS[name])
                self.assertTrue((ROOT / stage["source"]).is_file())
                self.assertTrue(stage["invariants"])
                for behavior in stage["invariants"]:
                    self.assertIn(behavior, data["behaviors"])
                for scenario in stage["scenarios"].values():
                    self.assertTrue(set(scenario).issubset(stage["invariants"]))
                for item in stage["artifacts"]:
                    artifact, role = item.split(":", 1)
                    self.assertIn(role, ALLOWED_ARTIFACT_ROLES)
                    self.assertIn(artifact, manifest)
                    self.assertTrue((ROOT / "templates" / manifest[artifact]["file"]).is_file())
                    if role == "produced":
                        self.assertEqual(manifest[artifact]["producer"], name)
                    elif role == "conditional":
                        self.assertIn("conditional", manifest[artifact])
                    else:
                        self.assertNotEqual(manifest[artifact]["producer"], name)
                for item in stage["skills"]:
                    if item.endswith("@external"):
                        continue
                    skill, path = item.split("=", 1)
                    self.assertIn(f"name: {skill}", read(path))

    def test_ac_1_2_full_clauses_exist_at_declared_owners(self) -> None:
        """AC-1.2: full clauses and anchors exist, while opposites do not."""

        data = contract()
        referenced = set()
        for stage_name, stage in data["stages"].items():
            local_owners = {stage["source"]}
            local_owners.update(
                declaration.split("=", 1)[1]
                for declaration in stage["skills"]
                if not declaration.endswith("@external")
            )
            for rule_id in stage["invariants"]:
                referenced.add(rule_id)
                rule = data["behaviors"][rule_id]
                evidence_reads = []

                def evidence_reader(path: str) -> str:
                    evidence_reads.append(path)
                    return read(path)

                with self.subTest(stage=stage_name, rule=rule_id):
                    self.assertIn(
                        rule["owner"],
                        local_owners,
                        f"{rule_id}: owner is not declared by {stage_name}",
                    )
                    missing, forbidden = owner_evidence(rule, evidence_reader)
                    self.assertEqual([], missing, f"{rule_id}: owner lost clause/anchors")
                    self.assertEqual([], forbidden, f"{rule_id}: owner contains opposite")
                    self.assertEqual([rule["owner"]], evidence_reads)

        self.assertEqual(set(data["behaviors"]), referenced)

    def test_ac_1_3_duplicate_sources_are_not_semantic_owners(self) -> None:
        """AC-1.3: duplicate prose/path removal cannot affect owner evidence."""

        data = contract()
        self.assertTrue(data["policy"]["owners_are_normative"])
        self.assertTrue(data["policy"]["duplicates_are_removable"])
        duplicated_rules = [
            rule for rule in data["behaviors"].values() if rule.get("duplicates")
        ]
        self.assertTrue(duplicated_rules)

        for rule in duplicated_rules:
            evidence_reads = []

            def evidence_reader(path: str) -> str:
                evidence_reads.append(path)
                return read(path)

            with self.subTest(owner=rule["owner"]):
                self.assertEqual(([], []), owner_evidence(rule, evidence_reader))
                self.assertEqual([rule["owner"]], evidence_reads)
            duplicate_clause = normalize_whitespace(rule["duplicate_clause"])
            self.assertIn(duplicate_clause, normalize_whitespace(read(rule["owner"])))
            for duplicate in rule["duplicates"]:
                self.assertNotEqual(rule["owner"], duplicate)
                self.assertNotIn(duplicate, evidence_reads)
                self.assertIn(duplicate_clause, normalize_whitespace(read(duplicate)))

        # A duplicate path may already be deleted; owner evidence is unchanged.
        synthetic = dict(duplicated_rules[0])
        synthetic["duplicates"] = ["tests/fixtures/deleted-duplicate.md"]
        evidence_reads = []
        self.assertEqual(([], []), owner_evidence(
            synthetic,
            lambda path: evidence_reads.append(path) or read(path),
        ))
        self.assertEqual([synthetic["owner"]], evidence_reads)

    def test_ac_1_4_mirrors_derive_from_canonical_commands(self) -> None:
        """AC-1.4: all platform mirrors equal generator output from canonical sources."""

        generator = load_generator()
        self.assertEqual(generator.COMMANDS, PHASES)
        for name in PHASES:
            with self.subTest(command=name):
                description, body = generator.parse_source(name)
                expected = {
                    f".codex/skills/{name}/SKILL.md": generator.gen_codex(name, description, body),
                    f".opencode/commands/{name}.md": generator.gen_opencode(name, description, body),
                    f".gemini/commands/{name}.toml": generator.gen_gemini(name, description, body),
                    f".pi/prompts/{name}.md": generator.gen_pi_prompt(name, description, body),
                }
                for path, output in expected.items():
                    self.assertEqual(read(path), output)


if __name__ == "__main__":
    unittest.main()
