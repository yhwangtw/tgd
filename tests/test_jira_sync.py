"""Behavioral tests for deterministic, confirmation-gated Jira sync."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "jira-sync.py"


def load_module():
    spec = importlib.util.spec_from_file_location("tgd_jira_sync", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CANONICAL_TASKS = """\
# TASKS.md: login-hardening

> **Corresponding PRD**: [PRD.md](PRD.md)
> **Tech Stack**: Python
> **Jira-Source-ID**: tgd-source-11111111-1111-4111-8111-111111111111

## Overview
Harden login behavior.

## Architecture Decisions
- Keep authentication server-side.

---

## Task 1: [backend] Create login endpoint (Story ID: US-01)
**Status:** pending
**Spec-Review:** pending
**Quality-Review:** pending
**Jira:** —
**Jira-Sync-ID:** —

### 1. Context & Goal
Users need a secure login endpoint.
- **Priority**: High
- **Dependencies**: None

### 2. Technical Design

```markdown
## Task 99: this fenced example is not a real task
- **AC-99.1** — **Given** fake **When** fake **Then** fake
```

### 3. Acceptance Criteria (BDD)
- **AC-1.1** — **Given** valid credentials **When** login is requested **Then** return a token
  - **Regression**: Yes `[R]`
  - **Test**: `tests/test_login.py`
- **AC-1.2** — **Given** invalid credentials **When** login is requested **Then** return 401
  - **Regression**: Yes `[R]`
  - **Test**: `tests/test_login.py`

### 4. Files Likely Touched
- `src/login.py`
- `tests/test_login.py`

---

## Task 2: Add audit event (Story ID: US-02)
**Status:** pending
**Spec-Review:** pending
**Quality-Review:** pending
**Jira:** ENG-42
**Jira-Sync-ID:** tgd-sync-existing

### 1. Context & Goal
Security needs an audit trail.
- **Priority**: Medium
- **Dependencies**: Task 1

### 2. Technical Design
Emit one structured event.

### 3. Acceptance Criteria (BDD)
- **AC-2.1** — **Given** a login attempt **When** authentication finishes **Then** emit an audit event
  - **Regression**: No
  - **Test**: `tests/test_audit.py`

### 4. Files Likely Touched
- `src/audit.py`

## Checkpoint: Verification
All tests pass.

## Risks & Mitigations
| Risk | Impact | Mitigation |
|---|---|---|
| Token leakage | High | Redact secrets |

## Open Questions
- None

## Sign-off
- [ ] **DEV**: (pending)
"""


class FakeJira:
    def __init__(self) -> None:
        self.base_url = "https://jira.example.test"
        self.projects = [
            {"id": "100", "key": "ENG", "name": "Engineering"},
            {"id": "200", "key": "OPS", "name": "Operations"},
        ]
        self.issue_types = [
            {"id": "10", "name": "Story"},
            {"id": "20", "name": "Bug"},
        ]
        self.create_fields = {
            "project": {"required": True, "name": "Project"},
            "summary": {"required": True, "name": "Summary"},
            "issuetype": {"required": True, "name": "Issue Type"},
            "description": {"required": False, "name": "Description"},
            "priority": {"required": False, "name": "Priority"},
            "labels": {"required": False, "name": "Labels"},
        }
        self.priorities = [
            {"id": "1", "name": "High"},
            {"id": "2", "name": "Medium"},
            {"id": "3", "name": "Low"},
        ]
        self.issues = {
            "ENG-42": {
                "key": "ENG-42",
                "fields": {
                    "project": {"key": "ENG"},
                    "summary": "[login-hardening] Add audit event",
                    "description": (
                        "Security needs an audit trail.\n\n"
                        "Acceptance Criteria:\n"
                        "* AC-2.1: Given a login attempt When authentication finishes "
                        "Then emit an audit event\n\n"
                        "Files Likely Touched:\n"
                        "* src/audit.py\n\n"
                        "Source: TASKS.md / login-hardening / Task 2\n"
                        "tGD Sync ID: tgd-sync-existing"
                    ),
                    "priority": {"name": "Medium"},
                    "labels": ["tgd-sync-existing"],
                },
            }
        }
        self.properties = {}
        self.writes = []
        self.update_payloads = []
        self._next = 100

    def list_projects(self):
        return list(self.projects)

    def list_issue_types(self, project_key):
        if project_key not in {p["key"] for p in self.projects}:
            return []
        return list(self.issue_types)

    def get_create_fields(self, project_key, issue_type_id):
        return dict(self.create_fields)

    def list_priorities(self):
        return list(self.priorities)

    def search_issues_by_label(self, project_key, label):
        return [
            issue
            for issue in self.issues.values()
            if issue["fields"]["project"]["key"] == project_key
            and label in issue["fields"].get("labels", [])
        ]

    def get_issue(self, key, extra_fields=()):
        del extra_fields
        return self.issues.get(key)

    def get_issue_property(self, key, property_key):
        return self.properties.get((key, property_key))

    def create_issue(self, fields):
        self._next += 1
        key = f"ENG-{self._next}"
        self.issues[key] = {"key": key, "fields": json.loads(json.dumps(fields))}
        self.writes.append(("create", key))
        return key

    def update_issue(self, key, fields, label_to_add=None):
        self.issues[key]["fields"].update(json.loads(json.dumps(fields)))
        if label_to_add:
            labels = self.issues[key]["fields"].setdefault("labels", [])
            if label_to_add not in labels:
                labels.append(label_to_add)
        self.update_payloads.append(
            {
                "key": key,
                "fields": json.loads(json.dumps(fields)),
                "label_to_add": label_to_add,
            }
        )
        self.writes.append(("update", key))

    def set_issue_property(self, key, property_key, value):
        self.properties[(key, property_key)] = json.loads(json.dumps(value))
        self.writes.append(("property", key))


class JiraSyncContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sync = load_module()

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(prefix="tgd-jira-sync-")
        self.addCleanup(self.temp_dir.cleanup)
        self.tasks_path = Path(self.temp_dir.name) / "TASKS.md"
        self.tasks_path.write_text(CANONICAL_TASKS, encoding="utf-8")

    def test_ac_1_1_parser_reads_only_canonical_task_blocks(self) -> None:
        document = self.sync.parse_tasks_file(self.tasks_path)

        self.assertEqual("login-hardening", document.feature_name)
        self.assertEqual([1, 2], [task.number for task in document.tasks])
        self.assertEqual("[backend] Create login endpoint", document.tasks[0].title)
        self.assertEqual("High", document.tasks[0].priority)
        self.assertEqual(("AC-1.1", "AC-1.2"), document.tasks[0].ac_ids)
        self.assertEqual(("src/login.py", "tests/test_login.py"), document.tasks[0].files)
        self.assertEqual("ENG-42", document.tasks[1].jira_key)
        self.assertEqual("tgd-sync-existing", document.tasks[1].sync_id)

    def test_ac_1_2_parser_fails_closed_on_duplicate_task_numbers(self) -> None:
        broken = CANONICAL_TASKS.replace("## Task 2:", "## Task 1:")
        self.tasks_path.write_text(broken, encoding="utf-8")

        with self.assertRaisesRegex(self.sync.ContractError, "duplicate task number"):
            self.sync.parse_tasks_file(self.tasks_path)

    def test_ac_1_3_writeback_is_idempotent_and_preserves_other_content(self) -> None:
        first = self.sync.write_jira_links(
            CANONICAL_TASKS,
            {1: ("ENG-101", "tgd-sync-one")},
        )
        second = self.sync.write_jira_links(
            first,
            {1: ("ENG-101", "tgd-sync-one")},
        )

        self.assertEqual(first, second)
        self.assertIn("**Jira:** ENG-101", first)
        self.assertIn("**Jira-Sync-ID:** tgd-sync-one", first)
        self.assertIn("**Jira:** ENG-42", first)
        self.assertIn("AC-1.2", first)

    def test_ac_2_1_projects_are_listed_and_saved_project_is_only_a_default(self) -> None:
        projects = self.sync.project_choices(FakeJira(), default_key="OPS")

        self.assertEqual(["ENG", "OPS"], [p["key"] for p in projects])
        self.assertFalse(projects[0]["is_default"])
        self.assertTrue(projects[1]["is_default"])

    def test_ac_2_2_dry_run_requires_an_exact_project_and_performs_no_writes(self) -> None:
        client = FakeJira()
        document = self.sync.parse_tasks_file(self.tasks_path)

        with self.assertRaisesRegex(self.sync.ContractError, "unknown Jira project"):
            self.sync.build_sync_plan(client, document, project_key="UNKNOWN")

        plan = self.sync.build_sync_plan(client, document, project_key="ENG")

        self.assertEqual([], client.writes)
        self.assertEqual("ENG", plan["project"]["key"])
        self.assertEqual(["create", "update"], [a["operation"] for a in plan["actions"]])
        self.assertNotIn("sprint", json.dumps(plan).lower())
        # Product requirements may legitimately mention a login token; the plan
        # contract forbids credential fields and Authorization headers instead.
        serialized = json.dumps(plan).lower()
        self.assertNotIn("jira_token", serialized)
        self.assertNotIn("authorization", serialized)
        self.assertNotIn("bearer ", serialized)

    def test_ac_2_3_apply_rejects_a_missing_or_stale_confirmation(self) -> None:
        client = FakeJira()
        document = self.sync.parse_tasks_file(self.tasks_path)
        plan = self.sync.build_sync_plan(client, document, project_key="ENG")

        for confirmation in (None, "wrong-digest"):
            with self.subTest(confirmation=confirmation):
                with self.assertRaisesRegex(self.sync.ContractError, "confirmation"):
                    self.sync.apply_sync_plan(client, plan, confirmation=confirmation)
        self.assertEqual([], client.writes)

    def test_ac_3_1_apply_creates_updates_verifies_and_writes_back(self) -> None:
        client = FakeJira()
        document = self.sync.parse_tasks_file(self.tasks_path)
        plan = self.sync.build_sync_plan(client, document, project_key="ENG")

        report = self.sync.apply_sync_plan(
            client,
            plan,
            confirmation=plan["plan_sha256"],
        )

        self.assertEqual(0, report["failed"])
        self.assertEqual(1, report["created"])
        self.assertEqual(1, report["updated"])
        updated_tasks = self.tasks_path.read_text(encoding="utf-8")
        self.assertRegex(updated_tasks, r"\*\*Jira:\*\* ENG-\d+")
        self.assertIn("**Jira:** ENG-42", updated_tasks)
        self.assertTrue(any(kind == "property" for kind, _key in client.writes))

    def test_ac_3_2_second_plan_is_a_noop_after_successful_apply(self) -> None:
        client = FakeJira()
        document = self.sync.parse_tasks_file(self.tasks_path)
        first = self.sync.build_sync_plan(client, document, project_key="ENG")
        self.sync.apply_sync_plan(client, first, confirmation=first["plan_sha256"])

        second_document = self.sync.parse_tasks_file(self.tasks_path)
        second = self.sync.build_sync_plan(client, second_document, project_key="ENG")

        self.assertEqual(["skip", "skip"], [a["operation"] for a in second["actions"]])

    def test_ac_3_3_apply_rejects_tasks_changed_after_dry_run(self) -> None:
        client = FakeJira()
        document = self.sync.parse_tasks_file(self.tasks_path)
        plan = self.sync.build_sync_plan(client, document, project_key="ENG")
        self.tasks_path.write_text(CANONICAL_TASKS + "\nchanged after preview\n", encoding="utf-8")

        with self.assertRaisesRegex(self.sync.ContractError, "changed after dry-run"):
            self.sync.apply_sync_plan(
                client,
                plan,
                confirmation=plan["plan_sha256"],
            )
        self.assertEqual([], client.writes)

    def test_required_sprint_is_collected_like_any_other_required_field(self) -> None:
        client = FakeJira()
        client.create_fields["customfield_10020"] = {
            "required": True,
            "name": "Sprint",
            "schema": {"type": "array", "items": "option"},
            "allowedValues": [
                {"id": "55", "name": "Iteration 55"},
                {"id": "56", "name": "Iteration 56"},
            ],
        }
        client.create_fields["customfield_20000"] = {
            "required": True,
            "name": "Release Note",
            "schema": {"type": "string"},
        }
        document = self.sync.parse_tasks_file(self.tasks_path)

        questions = self.sync.required_field_questions(client, "ENG", "Story")
        self.assertEqual(
            ["Sprint", "Release Note"],
            [field["name"] for field in questions["required_fields"]],
        )
        self.assertEqual(
            "Iteration 55",
            questions["required_fields"][0]["allowed_values"][0]["name"],
        )

        with self.assertRaisesRegex(self.sync.ContractError, "missing required Jira field answers"):
            self.sync.build_sync_plan(client, document, project_key="ENG")

        plan = self.sync.build_sync_plan(
            client,
            document,
            project_key="ENG",
            field_answers={
                "defaults": {
                    "customfield_10020": [{"id": "55"}],
                    "customfield_20000": "Ship with audit notes",
                },
                "tasks": {},
            },
        )
        create_action = plan["actions"][0]
        self.assertEqual(
            {
                "customfield_10020": [{"id": "55"}],
                "customfield_20000": "Ship with audit notes",
            },
            create_action["create_only_fields"],
        )
        self.assertEqual({}, plan["actions"][1]["create_only_fields"])
        self.assertNotIn("agile", json.dumps(plan).lower())

        report = self.sync.apply_sync_plan(client, plan, plan["plan_sha256"])

        self.assertEqual(1, report["created"])
        created_key = next(
            link["issue_key"] for link in report["links"] if link["task_number"] == 1
        )
        self.assertEqual(
            [{"id": "55"}],
            client.issues[created_key]["fields"]["customfield_10020"],
        )
        self.assertEqual(
            "Ship with audit notes",
            client.issues[created_key]["fields"]["customfield_20000"],
        )

    def test_required_field_answers_reject_unknown_or_disallowed_values(self) -> None:
        client = FakeJira()
        client.create_fields["customfield_10020"] = {
            "required": True,
            "name": "Iteration",
            "schema": {"type": "array", "items": "option"},
            "allowedValues": [{"id": "55", "name": "Iteration 55"}],
        }
        document = self.sync.parse_tasks_file(self.tasks_path)

        cases = (
            (
                {"defaults": {"customfield_10020": [{"id": "999"}]}, "tasks": {}},
                "not one of the allowed values",
            ),
            (
                {
                    "defaults": {
                        "customfield_10020": [{"id": "55"}],
                        "customfield_unknown": "unsafe",
                    },
                    "tasks": {},
                },
                "unsupported Jira field answer",
            ),
        )
        for answers, error in cases:
            with self.subTest(error=error):
                with self.assertRaisesRegex(self.sync.ContractError, error):
                    self.sync.build_sync_plan(
                        client,
                        document,
                        project_key="ENG",
                        field_answers=answers,
                    )
        self.assertEqual([], client.writes)

    def test_required_field_questions_have_stable_field_id_order(self) -> None:
        client = FakeJira()
        client.create_fields["customfield_90000"] = {
            "required": True,
            "name": "Later field",
            "schema": {"type": "string"},
        }
        client.create_fields["customfield_10000"] = {
            "required": True,
            "name": "Earlier field",
            "schema": {"type": "string"},
        }

        questions = self.sync.required_field_questions(client, "ENG", "Story")

        self.assertEqual(
            ["customfield_10000", "customfield_90000"],
            [field["id"] for field in questions["required_fields"]],
        )

    def test_required_field_answers_support_per_task_overrides(self) -> None:
        client = FakeJira()
        client.issues.pop("ENG-42")
        unsynced = CANONICAL_TASKS.replace("**Jira:** ENG-42", "**Jira:** —").replace(
            "**Jira-Sync-ID:** tgd-sync-existing", "**Jira-Sync-ID:** —"
        )
        self.tasks_path.write_text(unsynced, encoding="utf-8")
        client.create_fields["customfield_30000"] = {
            "required": True,
            "name": "Component",
            "schema": {"type": "option"},
            "allowedValues": [
                {"id": "1", "name": "Backend"},
                {"id": "2", "name": "Frontend"},
            ],
        }
        document = self.sync.parse_tasks_file(self.tasks_path)

        plan = self.sync.build_sync_plan(
            client,
            document,
            project_key="ENG",
            field_answers={
                "defaults": {"customfield_30000": "Backend"},
                "tasks": {"2": {"customfield_30000": "Frontend"}},
            },
        )

        self.assertEqual(
            {"customfield_30000": {"id": "1"}},
            plan["actions"][0]["create_only_fields"],
        )
        self.assertEqual(
            {"customfield_30000": {"id": "2"}},
            plan["actions"][1]["create_only_fields"],
        )

    def test_field_answers_file_must_be_private_regular_json(self) -> None:
        answers_path = Path(self.temp_dir.name) / "answers.json"
        answers_path.write_text('{"defaults": {}, "tasks": {}}\n', encoding="utf-8")
        answers_path.chmod(0o644)

        with self.assertRaisesRegex(self.sync.ContractError, "must not be readable"):
            self.sync._read_field_answers(answers_path)

        answers_path.chmod(0o600)
        self.assertEqual(
            {"defaults": {}, "tasks": {}},
            self.sync._read_field_answers(answers_path),
        )

        symlink_path = Path(self.temp_dir.name) / "answers-link.json"
        symlink_path.symlink_to(answers_path)
        with self.assertRaisesRegex(self.sync.ContractError, "cannot open private"):
            self.sync._read_field_answers(symlink_path)

    def test_missing_labels_metadata_fails_closed(self) -> None:
        client = FakeJira()
        del client.create_fields["labels"]
        document = self.sync.parse_tasks_file(self.tasks_path)

        with self.assertRaisesRegex(self.sync.ContractError, "Labels field is unavailable"):
            self.sync.build_sync_plan(client, document, project_key="ENG")

        self.assertEqual([], client.writes)

    def test_multiple_stable_label_matches_conflict_and_apply_performs_no_writes(self) -> None:
        client = FakeJira()
        self.tasks_path.write_text(
            CANONICAL_TASKS.split("\n## Task 2:", 1)[0].rstrip() + "\n",
            encoding="utf-8",
        )
        document = self.sync.parse_tasks_file(self.tasks_path)
        initial_plan = self.sync.build_sync_plan(client, document, project_key="ENG")
        sync_id = initial_plan["actions"][0]["sync_id"]
        for key in ("ENG-501", "ENG-502"):
            client.issues[key] = {
                "key": key,
                "fields": {
                    "project": {"key": "ENG"},
                    "summary": "Conflicting stable-label match",
                    "description": "Conflict fixture",
                    "priority": {"name": "High"},
                    "labels": [sync_id],
                },
            }

        plan = self.sync.build_sync_plan(client, document, project_key="ENG")

        self.assertEqual("conflict", plan["actions"][0]["operation"])
        self.assertIn("multiple Jira issues", plan["actions"][0]["reason"])
        with self.assertRaisesRegex(self.sync.ContractError, "contains conflict"):
            self.sync.apply_sync_plan(
                client,
                plan,
                confirmation=plan["plan_sha256"],
            )
        self.assertEqual([], client.writes)

    def test_tampered_plan_content_is_rejected_even_with_original_digest(self) -> None:
        client = FakeJira()
        document = self.sync.parse_tasks_file(self.tasks_path)
        plan = self.sync.build_sync_plan(client, document, project_key="ENG")
        tampered = json.loads(json.dumps(plan))
        tampered["actions"][0]["owned_fields"]["summary"] = "tampered after review"

        with self.assertRaisesRegex(self.sync.ContractError, "plan content"):
            self.sync.apply_sync_plan(
                client,
                tampered,
                confirmation=tampered["plan_sha256"],
            )

        self.assertEqual([], client.writes)

    def test_recomputed_plan_cannot_add_unowned_jira_fields(self) -> None:
        client = FakeJira()
        document = self.sync.parse_tasks_file(self.tasks_path)
        plan = self.sync.build_sync_plan(client, document, project_key="ENG")
        plan["actions"][0]["owned_fields"]["assignee"] = {"name": "someone"}
        plan["plan_sha256"] = self.sync._plan_digest(plan)

        with self.assertRaisesRegex(self.sync.ContractError, "unowned Jira fields"):
            self.sync.apply_sync_plan(client, plan, plan["plan_sha256"])

        self.assertEqual([], client.writes)

    def test_recomputed_plan_cannot_change_managed_content_from_tasks(self) -> None:
        client = FakeJira()
        document = self.sync.parse_tasks_file(self.tasks_path)
        plan = self.sync.build_sync_plan(client, document, project_key="ENG")
        action = plan["actions"][0]
        action["owned_fields"]["summary"] = "approved digest but wrong source content"
        action["content_sha256"] = self.sync._sha256_json(
            {
                "summary": action["owned_fields"]["summary"],
                "description": action["owned_fields"]["description"],
                "priority": action["priority"],
                "sync_id": action["sync_id"],
            }
        )
        action["property"]["content_sha256"] = action["content_sha256"]
        plan["plan_sha256"] = self.sync._plan_digest(plan)

        with self.assertRaisesRegex(self.sync.ContractError, "managed content does not match"):
            self.sync.apply_sync_plan(client, plan, plan["plan_sha256"])

        self.assertEqual([], client.writes)

    def test_recorded_jira_key_in_another_project_is_a_conflict(self) -> None:
        client = FakeJira()
        client.issues["ENG-42"]["fields"]["project"] = {"key": "OPS"}
        document = self.sync.parse_tasks_file(self.tasks_path)
        document = document._replace(tasks=(document.tasks[1],))

        plan = self.sync.build_sync_plan(client, document, project_key="ENG")

        self.assertEqual("conflict", plan["actions"][0]["operation"])
        self.assertIn("belongs to another project", plan["actions"][0]["reason"])
        self.assertEqual([], client.writes)

    def test_recorded_key_still_detects_duplicate_marker_issues(self) -> None:
        client = FakeJira()
        client.issues["ENG-43"] = {
            "key": "ENG-43",
            "fields": {
                "project": {"key": "ENG"},
                "summary": "Duplicate marker",
                "description": "Duplicate marker",
                "priority": {"name": "Medium"},
                "labels": ["tgd-sync-existing"],
            },
        }
        document = self.sync.parse_tasks_file(self.tasks_path)
        plan = self.sync.build_sync_plan(client, document, project_key="ENG")

        action = plan["actions"][1]
        self.assertEqual("conflict", action["operation"])
        self.assertIn("ENG-42", action["reason"])
        self.assertIn("ENG-43", action["reason"])
        with self.assertRaisesRegex(self.sync.ContractError, "contains conflict"):
            self.sync.apply_sync_plan(client, plan, plan["plan_sha256"])
        self.assertEqual([], client.writes)

    def test_remote_property_from_another_source_is_a_conflict(self) -> None:
        client = FakeJira()
        client.properties[("ENG-42", self.sync.PROPERTY_KEY)] = {
            "sync_id": "tgd-sync-existing",
            "source": {
                "source_id": "tgd-source-22222222-2222-4222-8222-222222222222"
            },
        }
        document = self.sync.parse_tasks_file(self.tasks_path)
        plan = self.sync.build_sync_plan(client, document, project_key="ENG")

        self.assertEqual("conflict", plan["actions"][1]["operation"])
        self.assertIn("different TASKS source", plan["actions"][1]["reason"])

    def test_legacy_heading_key_requires_explicit_adoption_and_never_creates(self) -> None:
        legacy_tasks = CANONICAL_TASKS.split("\n## Task 2:", 1)[0].replace(
            "## Task 1: [backend] Create login endpoint (Story ID: US-01)",
            "## Task 1: [backend] Create login endpoint [ENG-77] (Story ID: US-01)",
        ).rstrip() + "\n"
        self.tasks_path.write_text(legacy_tasks, encoding="utf-8")
        client = FakeJira()
        client.issues["ENG-77"] = {
            "key": "ENG-77",
            "fields": {
                "project": {"key": "ENG"},
                "summary": "Legacy title",
                "description": "Legacy description",
                "priority": {"name": "High"},
                "labels": ["tgd", "login-hardening"],
            },
        }

        document = self.sync.parse_tasks_file(self.tasks_path)
        self.assertEqual("ENG-77", document.tasks[0].legacy_jira_key)
        self.assertEqual("[backend] Create login endpoint", document.tasks[0].title)

        plan = self.sync.build_sync_plan(client, document, project_key="ENG")
        action = plan["actions"][0]
        self.assertEqual("adopt", action["operation"])
        self.assertEqual("ENG-77", action["issue_key"])
        self.assertIn("legacy", action["reason"].lower())
        self.assertEqual([], client.writes)

        report = self.sync.apply_sync_plan(client, plan, plan["plan_sha256"])

        self.assertEqual(1, report["updated"])
        self.assertFalse(any(kind == "create" for kind, _key in client.writes))
        updated_tasks = self.tasks_path.read_text(encoding="utf-8")
        self.assertIn("**Jira:** ENG-77", updated_tasks)
        self.assertRegex(updated_tasks, r"\*\*Jira-Sync-ID:\*\* tgd-sync-")
        self.assertNotIn("[ENG-77]", updated_tasks)

    def test_missing_legacy_heading_key_is_a_conflict_not_a_create(self) -> None:
        legacy_tasks = CANONICAL_TASKS.split("\n## Task 2:", 1)[0].replace(
            "## Task 1: [backend] Create login endpoint (Story ID: US-01)",
            "## Task 1: [ENG-404] [backend] Create login endpoint (Story ID: US-01)",
        ).rstrip() + "\n"
        self.tasks_path.write_text(legacy_tasks, encoding="utf-8")
        client = FakeJira()
        document = self.sync.parse_tasks_file(self.tasks_path)

        plan = self.sync.build_sync_plan(client, document, project_key="ENG")

        self.assertEqual("conflict", plan["actions"][0]["operation"])
        self.assertEqual("ENG-404", plan["actions"][0]["issue_key"])
        self.assertEqual([], client.writes)

    def test_label_only_identity_with_mismatched_fields_is_a_conflict(self) -> None:
        first_task = CANONICAL_TASKS.split("\n## Task 2:", 1)[0].rstrip() + "\n"
        self.tasks_path.write_text(first_task, encoding="utf-8")
        client = FakeJira()
        document = self.sync.parse_tasks_file(self.tasks_path)
        initial = self.sync.build_sync_plan(client, document, project_key="ENG")
        sync_id = initial["actions"][0]["sync_id"]
        client.issues["ENG-88"] = {
            "key": "ENG-88",
            "fields": {
                "project": {"key": "ENG"},
                "summary": "Unrelated issue",
                "description": "Must not be overwritten",
                "priority": {"name": "High"},
                "labels": [sync_id],
            },
        }

        plan = self.sync.build_sync_plan(client, document, project_key="ENG")

        self.assertEqual("conflict", plan["actions"][0]["operation"])
        self.assertIn("label-only", plan["actions"][0]["reason"])
        with self.assertRaisesRegex(self.sync.ContractError, "contains conflict"):
            self.sync.apply_sync_plan(client, plan, plan["plan_sha256"])
        self.assertEqual([], client.writes)

    def test_rehashed_plan_cannot_inject_adoption_without_a_legacy_key(self) -> None:
        first_task = CANONICAL_TASKS.split("\n## Task 2:", 1)[0].rstrip() + "\n"
        self.tasks_path.write_text(first_task, encoding="utf-8")
        client = FakeJira()
        client.issues["ENG-77"] = {
            "key": "ENG-77",
            "fields": {
                "project": {"key": "ENG"},
                "summary": "Unowned issue",
                "description": "Unowned issue",
                "priority": {"name": "High"},
                "labels": [],
            },
        }
        document = self.sync.parse_tasks_file(self.tasks_path)
        plan = self.sync.build_sync_plan(client, document, project_key="ENG")
        plan["actions"][0]["operation"] = "adopt"
        plan["actions"][0]["issue_key"] = "ENG-77"
        plan["actions"][0]["reason"] = "tampered adoption"
        plan["plan_sha256"] = self.sync._plan_digest(plan)

        with self.assertRaisesRegex(self.sync.ContractError, "not backed by a legacy"):
            self.sync.apply_sync_plan(client, plan, plan["plan_sha256"])
        self.assertEqual([], client.writes)

    def test_duplicate_effective_legacy_issue_keys_fail_before_writes(self) -> None:
        duplicate = CANONICAL_TASKS.replace(
            "## Task 1: [backend] Create login endpoint (Story ID: US-01)",
            "## Task 1: [backend] Create login endpoint [ENG-77] (Story ID: US-01)",
        ).replace(
            "## Task 2: Add audit event (Story ID: US-02)",
            "## Task 2: Add audit event [ENG-77] (Story ID: US-02)",
        ).replace("**Jira:** ENG-42", "**Jira:** —").replace(
            "**Jira-Sync-ID:** tgd-sync-existing", "**Jira-Sync-ID:** —"
        )
        self.tasks_path.write_text(duplicate, encoding="utf-8")
        client = FakeJira()
        document = self.sync.parse_tasks_file(self.tasks_path)

        with self.assertRaisesRegex(self.sync.ContractError, "duplicate Jira issue key ENG-77"):
            self.sync.build_sync_plan(client, document, project_key="ENG")
        self.assertEqual([], client.writes)

    def test_parser_rejects_invalid_priority_and_ac_task_mismatch(self) -> None:
        cases = (
            (
                "invalid priority",
                CANONICAL_TASKS.replace(
                    "- **Priority**: High",
                    "- **Priority**: Critical",
                    1,
                ),
                "invalid Priority",
            ),
            (
                "acceptance criterion task mismatch",
                CANONICAL_TASKS.replace("**AC-1.1**", "**AC-2.9**", 1),
                "belongs to task 2, not task 1",
            ),
        )
        for label, contents, error_pattern in cases:
            with self.subTest(label=label):
                self.tasks_path.write_text(contents, encoding="utf-8")
                with self.assertRaisesRegex(self.sync.ContractError, error_pattern):
                    self.sync.parse_tasks_file(self.tasks_path)

    def test_cli_parser_rejects_token_argument(self) -> None:
        parser = self.sync._parser()
        stderr = io.StringIO()

        with contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as raised:
                parser.parse_args(
                    [
                        "plan",
                        "--tasks",
                        str(self.tasks_path),
                        "--project",
                        "ENG",
                        "--output",
                        str(Path(self.temp_dir.name) / "plan.json"),
                        "--token",
                        "must-not-be-accepted",
                    ]
                )

        self.assertEqual(2, raised.exception.code)
        self.assertIn("credentials must be supplied through the environment", stderr.getvalue())
        self.assertNotIn("must-not-be-accepted", stderr.getvalue())

    def test_jira_client_rejects_insecure_origin_and_malformed_token(self) -> None:
        with self.assertRaisesRegex(self.sync.ContractError, "must use HTTPS"):
            self.sync.JiraClient("http://localhost:8080", "dummy-token")
        with self.assertRaisesRegex(self.sync.ContractError, "invalid characters"):
            self.sync.JiraClient("https://jira.example.test", "secret-with-newline\n")

    def test_plan_json_keys_and_header_have_no_credential_semantics(self) -> None:
        client = FakeJira()
        document = self.sync.parse_tasks_file(self.tasks_path)
        plan = self.sync.build_sync_plan(client, document, project_key="ENG")

        self.assertTrue(
            {
                "schema_version",
                "jira_origin",
                "source",
                "project",
                "issue_type",
                "actions",
                "plan_sha256",
            }.issubset(plan),
            set(plan),
        )

        key_paths = []

        def collect_key_paths(value, prefix=""):
            if isinstance(value, dict):
                for key, child in value.items():
                    path = f"{prefix}.{key}" if prefix else str(key)
                    key_paths.append(path.casefold())
                    collect_key_paths(child, path)
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    collect_key_paths(child, f"{prefix}[{index}]")

        collect_key_paths(plan)
        forbidden = (
            "authorization",
            "bearer",
            "credential",
            "header",
            "password",
            "secret",
            "token",
            "cookie",
        )
        unsafe = [
            path
            for path in key_paths
            if any(fragment in path.rsplit(".", 1)[-1] for fragment in forbidden)
        ]
        self.assertEqual([], unsafe)

    def test_duplicate_sync_ids_are_rejected_before_any_jira_write(self) -> None:
        broken = CANONICAL_TASKS.replace(
            "**Jira-Sync-ID:** —",
            "**Jira-Sync-ID:** tgd-sync-existing",
            1,
        )
        self.tasks_path.write_text(broken, encoding="utf-8")

        with self.assertRaisesRegex(self.sync.ContractError, "duplicate Jira-Sync-ID"):
            self.sync.parse_tasks_file(self.tasks_path)

    def test_document_source_id_namespaces_generated_sync_ids(self) -> None:
        first_document = self.sync.parse_tasks_file(self.tasks_path)
        first_plan = self.sync.build_sync_plan(FakeJira(), first_document, project_key="ENG")
        second_text = CANONICAL_TASKS.replace(
            "tgd-source-11111111-1111-4111-8111-111111111111",
            "tgd-source-22222222-2222-4222-8222-222222222222",
        )
        self.tasks_path.write_text(second_text, encoding="utf-8")
        second_document = self.sync.parse_tasks_file(self.tasks_path)
        second_plan = self.sync.build_sync_plan(FakeJira(), second_document, project_key="ENG")

        self.assertNotEqual(
            first_plan["actions"][0]["sync_id"],
            second_plan["actions"][0]["sync_id"],
        )

    def test_generated_sync_id_survives_feature_story_and_content_edits(self) -> None:
        document = self.sync.parse_tasks_file(self.tasks_path)
        task = document.tasks[0]
        original = self.sync._stable_sync_id("ENG", document, task)
        edited_task = task._replace(
            title="Rewritten unstarted task",
            story_id="US-99",
            context="Rewritten context after remote verification",
        )
        edited_document = document._replace(
            feature_name="renamed-feature",
            tasks=(edited_task,) + document.tasks[1:],
        )

        self.assertEqual(
            original,
            self.sync._stable_sync_id("ENG", edited_document, edited_task),
        )

    def test_recorded_issue_without_matching_identity_is_not_taken_over(self) -> None:
        client = FakeJira()
        client.issues["ENG-42"]["fields"]["labels"] = []
        header, second_task = CANONICAL_TASKS.split("\n## Task 2:", 1)
        header = header.split("\n## Task 1:", 1)[0]
        self.tasks_path.write_text(
            header.rstrip() + "\n\n## Task 2:" + second_task,
            encoding="utf-8",
        )
        document = self.sync.parse_tasks_file(self.tasks_path)

        plan = self.sync.build_sync_plan(client, document, project_key="ENG")

        self.assertEqual("conflict", plan["actions"][0]["operation"])
        self.assertIn("no matching tGD sync identity", plan["actions"][0]["reason"])
        with self.assertRaisesRegex(self.sync.ContractError, "contains conflict"):
            self.sync.apply_sync_plan(client, plan, plan["plan_sha256"])
        self.assertEqual([], client.writes)

    def test_plan_output_cannot_alias_tasks_file(self) -> None:
        original_factory = self.sync._client_from_env
        self.sync._client_from_env = FakeJira
        self.addCleanup(setattr, self.sync, "_client_from_env", original_factory)
        args = self.sync.argparse.Namespace(
            tasks=self.tasks_path,
            output=self.tasks_path,
            project="ENG",
            issue_type="Story",
        )

        with self.assertRaisesRegex(self.sync.ContractError, "must not overwrite TASKS.md"):
            self.sync._cmd_plan(args)

        self.assertEqual(CANONICAL_TASKS, self.tasks_path.read_text(encoding="utf-8"))

    def test_plan_writer_refuses_existing_symlink_without_touching_target(self) -> None:
        victim = Path(self.temp_dir.name) / "victim.txt"
        victim.write_text("keep me", encoding="utf-8")
        output = Path(self.temp_dir.name) / "plan.json"
        output.symlink_to(victim)

        with self.assertRaisesRegex(self.sync.ContractError, "already exists"):
            self.sync._write_plan(output, {"plan_sha256": "0" * 64})

        self.assertEqual("keep me", victim.read_text(encoding="utf-8"))
        self.assertTrue(output.is_symlink())

    def test_atomic_writeback_does_not_overwrite_a_racing_editor(self) -> None:
        expected_sha = self.sync._sha256_bytes(CANONICAL_TASKS.encode("utf-8"))
        original_write_links = self.sync.write_jira_links

        def racing_write_links(raw_text, links):
            self.tasks_path.write_text(raw_text + "\nexternal editor change\n", encoding="utf-8")
            return original_write_links(raw_text, links)

        self.sync.write_jira_links = racing_write_links
        self.addCleanup(setattr, self.sync, "write_jira_links", original_write_links)

        with self.assertRaisesRegex(self.sync.ContractError, "immediately before"):
            self.sync._locked_writeback(
                self.tasks_path,
                expected_sha,
                {1: ("ENG-101", "tgd-sync-safe-writeback")},
            )

        self.assertIn("external editor change", self.tasks_path.read_text(encoding="utf-8"))
        self.assertNotIn("**Jira:** ENG-101", self.tasks_path.read_text(encoding="utf-8"))

    def test_apply_rejects_create_metadata_changed_after_dry_run(self) -> None:
        client = FakeJira()
        document = self.sync.parse_tasks_file(self.tasks_path)
        plan = self.sync.build_sync_plan(client, document, project_key="ENG")
        client.create_fields["description"]["required"] = True

        with self.assertRaisesRegex(self.sync.ContractError, "metadata changed"):
            self.sync.apply_sync_plan(client, plan, plan["plan_sha256"])

        self.assertEqual([], client.writes)

    def test_ambiguous_create_without_unique_reconciliation_is_reported_unknown(self) -> None:
        client = FakeJira()
        self.tasks_path.write_text(
            CANONICAL_TASKS.split("\n## Task 2:", 1)[0].rstrip() + "\n",
            encoding="utf-8",
        )
        document = self.sync.parse_tasks_file(self.tasks_path)
        plan = self.sync.build_sync_plan(client, document, project_key="ENG")

        def ambiguous_create(_fields):
            raise self.sync.AmbiguousMutation("connection ended after POST")

        client.create_issue = ambiguous_create
        report = self.sync.apply_sync_plan(client, plan, plan["plan_sha256"])

        self.assertEqual(1, report["remote_unknown"])
        self.assertEqual(1, report["failed"])
        self.assertIn("**Jira:** —", self.tasks_path.read_text(encoding="utf-8"))

    def test_ambiguous_create_with_invalid_lookup_is_remote_unknown(self) -> None:
        client = FakeJira()
        self.tasks_path.write_text(
            CANONICAL_TASKS.split("\n## Task 2:", 1)[0].rstrip() + "\n",
            encoding="utf-8",
        )
        document = self.sync.parse_tasks_file(self.tasks_path)
        plan = self.sync.build_sync_plan(client, document, project_key="ENG")
        calls = 0

        def lookup(_project_key, _label):
            nonlocal calls
            calls += 1
            if calls == 1:
                return []
            raise self.sync.JiraError("malformed identity response")

        def ambiguous_create(_fields):
            raise self.sync.AmbiguousMutation("connection ended after POST")

        client.search_issues_by_label = lookup
        client.create_issue = ambiguous_create
        report = self.sync.apply_sync_plan(client, plan, plan["plan_sha256"])

        self.assertEqual(1, report["remote_unknown"])
        self.assertEqual(1, report["failed"])
        self.assertEqual(0, report["aborted"])
        self.assertIn("**Jira:** —", self.tasks_path.read_text(encoding="utf-8"))

    def test_ambiguous_create_with_systemic_lookup_aborts_remaining_as_unknown(self) -> None:
        client = FakeJira()
        document = self.sync.parse_tasks_file(self.tasks_path)
        plan = self.sync.build_sync_plan(client, document, project_key="ENG")
        calls = 0

        def lookup(_project_key, _label):
            nonlocal calls
            calls += 1
            if calls == 1:
                return []
            raise self.sync.JiraBatchAbort("search unavailable")

        def ambiguous_create(_fields):
            raise self.sync.AmbiguousMutation("connection ended after POST")

        client.search_issues_by_label = lookup
        client.create_issue = ambiguous_create
        report = self.sync.apply_sync_plan(client, plan, plan["plan_sha256"])

        self.assertEqual(1, report["remote_unknown"])
        self.assertEqual(1, report["failed"])
        self.assertEqual(1, report["aborted"])
        self.assertEqual(2, report["unattempted"][0]["task_number"])
        self.assertIn("**Jira:** —", self.tasks_path.read_text(encoding="utf-8"))

    def test_verified_mutation_with_systemic_uniqueness_failure_is_unknown(self) -> None:
        client = FakeJira()
        self.tasks_path.write_text(
            CANONICAL_TASKS.split("\n## Task 2:", 1)[0].rstrip() + "\n",
            encoding="utf-8",
        )
        document = self.sync.parse_tasks_file(self.tasks_path)
        plan = self.sync.build_sync_plan(client, document, project_key="ENG")
        original_search = client.search_issues_by_label
        calls = 0

        def lookup(project_key, label):
            nonlocal calls
            calls += 1
            if calls == 1:
                return []
            if calls == 2:
                raise self.sync.JiraBatchAbort("search unavailable after verify")
            return original_search(project_key, label)

        client.search_issues_by_label = lookup
        report = self.sync.apply_sync_plan(client, plan, plan["plan_sha256"])

        self.assertEqual(1, report["remote_unknown"])
        self.assertEqual(1, report["failed"])
        self.assertEqual(0, report["aborted"])
        self.assertIn("**Jira:** —", self.tasks_path.read_text(encoding="utf-8"))

    def test_successful_create_with_malformed_verification_is_remote_unknown(self) -> None:
        client = FakeJira()
        self.tasks_path.write_text(
            CANONICAL_TASKS.split("\n## Task 2:", 1)[0].rstrip() + "\n",
            encoding="utf-8",
        )
        document = self.sync.parse_tasks_file(self.tasks_path)
        plan = self.sync.build_sync_plan(client, document, project_key="ENG")
        original_get_issue = client.get_issue
        reads = 0

        def malformed_after_create(key, extra_fields=()):
            nonlocal reads
            del extra_fields
            reads += 1
            if reads == 1:
                raise self.sync.JiraError("malformed issue response after create")
            return original_get_issue(key)

        client.get_issue = malformed_after_create
        report = self.sync.apply_sync_plan(client, plan, plan["plan_sha256"])

        self.assertEqual(1, report["remote_unknown"])
        self.assertEqual(1, report["failed"])
        self.assertEqual([], report["links"])
        self.assertIn("**Jira:** —", self.tasks_path.read_text(encoding="utf-8"))

    def test_post_create_duplicate_marker_is_not_reported_as_success(self) -> None:
        client = FakeJira()
        self.tasks_path.write_text(
            CANONICAL_TASKS.split("\n## Task 2:", 1)[0].rstrip() + "\n",
            encoding="utf-8",
        )
        document = self.sync.parse_tasks_file(self.tasks_path)
        plan = self.sync.build_sync_plan(client, document, project_key="ENG")
        original_create = client.create_issue

        def racing_create(fields):
            created_key = original_create(fields)
            client.issues["ENG-999"] = {
                "key": "ENG-999",
                "fields": json.loads(json.dumps(fields)),
            }
            return created_key

        client.create_issue = racing_create
        report = self.sync.apply_sync_plan(client, plan, plan["plan_sha256"])

        self.assertEqual(1, report["remote_unknown"])
        self.assertEqual(1, report["failed"])
        self.assertIn("ENG-999", report["errors"][0])
        self.assertIn("**Jira:** —", self.tasks_path.read_text(encoding="utf-8"))

    def test_systemic_failure_reports_every_unattempted_task(self) -> None:
        client = FakeJira()
        document = self.sync.parse_tasks_file(self.tasks_path)
        plan = self.sync.build_sync_plan(client, document, project_key="ENG")

        def abort_search(_project_key, _label):
            raise self.sync.JiraBatchAbort("authorization failed")

        client.search_issues_by_label = abort_search
        report = self.sync.apply_sync_plan(client, plan, plan["plan_sha256"])

        self.assertEqual(1, report["failed"])
        self.assertEqual(1, report["aborted"])
        self.assertEqual(2, report["unattempted"][0]["task_number"])
        self.assertEqual([], client.writes)

    def test_skip_rejects_a_second_tgd_marker_before_writeback(self) -> None:
        client = FakeJira()
        document = self.sync.parse_tasks_file(self.tasks_path)
        first = self.sync.build_sync_plan(client, document, project_key="ENG")
        self.sync.apply_sync_plan(client, first, first["plan_sha256"])
        current = self.tasks_path.read_text(encoding="utf-8")
        second_document = self.sync.parse_tasks_file(self.tasks_path)
        second = self.sync.build_sync_plan(client, second_document, project_key="ENG")
        first_issue_key = second["actions"][0]["issue_key"]
        client.issues[first_issue_key]["fields"]["labels"].append("tgd-sync-other-marker")

        report = self.sync.apply_sync_plan(client, second, second["plan_sha256"])

        self.assertEqual(1, report["failed"])
        self.assertIn("another tGD sync marker", report["errors"][0])
        self.assertEqual(current, self.tasks_path.read_text(encoding="utf-8"))

    def test_modern_createmeta_endpoints_are_paged_and_field_ids_are_keyed(self) -> None:
        client = object.__new__(self.sync.JiraClient)
        requested = []

        def fake_request(method, path, payload=None, allow_not_found=False):
            del payload, allow_not_found
            requested.append((method, path))
            if path.startswith("/rest/api/2/issue/createmeta/ENG/issuetypes/10?"):
                return {
                    "isLast": True,
                    "startAt": 0,
                    "total": 2,
                    "values": [
                        {"fieldId": "summary", "name": "Summary", "required": True},
                        {"fieldId": "labels", "name": "Labels", "required": False},
                    ],
                }
            if "startAt=0" in path:
                return {
                    "isLast": False,
                    "startAt": 0,
                    "total": 2,
                    "values": [{"id": "10", "name": "Story"}],
                }
            return {
                "isLast": True,
                "startAt": 1,
                "total": 2,
                "values": [{"id": "20", "name": "Bug"}],
            }

        client._request = fake_request

        self.assertEqual(
            ["Story", "Bug"],
            [item["name"] for item in client.list_issue_types("ENG")],
        )
        fields = client.get_create_fields("ENG", "10")
        self.assertEqual({"summary", "labels"}, set(fields))
        self.assertTrue(all(method == "GET" for method, _path in requested))
        self.assertTrue(any("startAt=1" in path for _method, path in requested))

    def test_identity_search_rejects_malformed_success_responses(self) -> None:
        malformed = (
            None,
            [],
            {},
            {"issues": None},
            {"issues": []},
            {"issues": ["not-an-object"]},
            {"issues": [{"key": "not-a-jira-key"}]},
            {"total": 1, "issues": [{"key": "ENG-42", "fields": {}}]},
            {
                "total": 1,
                "issues": [
                    {
                        "key": "ENG-42",
                        "fields": {
                            "project": {"key": "OPS"},
                            "summary": "Wrong project",
                            "labels": ["tgd-sync-valid-id"],
                        },
                    }
                ],
            },
            {
                "total": 1,
                "issues": [
                    {
                        "key": "ENG-42",
                        "fields": {
                            "project": {"key": "ENG"},
                            "summary": "Missing searched label",
                            "labels": [],
                        },
                    }
                ],
            },
            {"total": 1, "issues": []},
        )
        for response in malformed:
            with self.subTest(response=response):
                client = object.__new__(self.sync.JiraClient)
                client._request = lambda *_args, **_kwargs: response
                with self.assertRaises(self.sync.JiraError):
                    client.search_issues_by_label("ENG", "tgd-sync-valid-id")

    def test_issue_and_property_reads_distinguish_404_from_malformed_200(self) -> None:
        client = object.__new__(self.sync.JiraClient)
        for response in (
            None,
            [],
            {},
            {"key": "ENG-999", "fields": {}},
            {"key": "ENG-42", "fields": {}},
            {
                "key": "ENG-42",
                "fields": {
                    "project": {"key": "ENG"},
                    "summary": "Missing labels",
                },
            },
        ):
            with self.subTest(issue_response=response):
                client._request = lambda *_args, **_kwargs: response
                with self.assertRaises(self.sync.JiraError):
                    client.get_issue("ENG-42")

        for response in (None, [], {}, {"value": None}, {"value": "bad"}):
            with self.subTest(property_response=response):
                client._request = lambda *_args, **_kwargs: response
                with self.assertRaises(self.sync.JiraError):
                    client.get_issue_property("ENG-42", self.sync.PROPERTY_KEY)

        client._request = lambda *_args, **_kwargs: self.sync._NOT_FOUND
        self.assertIsNone(client.get_issue("ENG-42"))
        self.assertIsNone(client.get_issue_property("ENG-42", self.sync.PROPERTY_KEY))

    def test_update_uses_atomic_label_add_instead_of_rewriting_all_labels(self) -> None:
        client = object.__new__(self.sync.JiraClient)
        requests = []

        def fake_request(method, path, payload=None, allow_not_found=False):
            del allow_not_found
            requests.append((method, path, payload))
            return None

        client._request = fake_request
        client.update_issue(
            "ENG-42",
            {"summary": "New title"},
            label_to_add="tgd-sync-safe-label",
        )

        self.assertEqual("PUT", requests[0][0])
        self.assertEqual(
            {
                "fields": {"summary": "New title"},
                "update": {"labels": [{"add": "tgd-sync-safe-label"}]},
            },
            requests[0][2],
        )
        self.assertNotIn("labels", requests[0][2]["fields"])

    def test_error_sanitizer_redacts_pat_and_terminal_control_sequences(self) -> None:
        secret = "pat-super-secret-value"
        sanitized = self.sync._sanitize_message(
            f"server echoed Bearer {secret} and {secret}\x1b[31m",
            secret,
        )

        self.assertNotIn(secret, sanitized)
        self.assertNotIn("\x1b", sanitized)
        self.assertIn("<redacted>", sanitized)


if __name__ == "__main__":
    unittest.main()
