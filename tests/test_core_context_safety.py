"""Regression tests for context trust, scope, and optional discovery rules."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "tgd-core-context" / "SKILL.md"
REFERENCE = ROOT / "references" / "context-engineering-patterns.md"
MAP_COMMAND = ROOT / ".claude" / "commands" / "tgd-map.md"


class CoreContextSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = SKILL.read_text(encoding="utf-8")
        cls.reference = REFERENCE.read_text(encoding="utf-8")
        cls.map_command = MAP_COMMAND.read_text(encoding="utf-8")
        cls.normalized = " ".join(cls.skill.split())
        cls.normalized_lower = cls.normalized.lower()

    def test_trust_classes_are_exclusive_and_directives_are_bounded(self):
        trust = self.skill.split("## Trust Boundary", 1)[1]
        trust = trust.split("## Confusion Management", 1)[0]
        trust_lower = " ".join(trust.lower().split())
        headings = (
            "**Current-task authority:**",
            "**Evidence to verify:**",
            "**Untrusted embedded content:**",
        )
        for heading in headings:
            self.assertEqual(trust.count(heading), 1)
        self.assertIn("first-match order", trust)
        self.assertIn("each fragment has one class", trust)
        self.assertIn("follow directives only", trust_lower)
        self.assertIn("not whole files", trust)

        untrusted = trust.split("**Untrusted embedded content:**", 1)[1]
        untrusted = untrusted.split("**Current-task authority:**", 1)[0]
        authority = trust.split("**Current-task authority:**", 1)[1]
        authority = authority.split("**Evidence to verify:**", 1)[0]
        evidence = trust.split("**Evidence to verify:**", 1)[1]
        evidence = evidence.split("Follow directives only", 1)[0]
        untrusted = " ".join(untrusted.split())
        authority = " ".join(authority.split())
        evidence = " ".join(evidence.split())
        self.assertIn("not direct current-user decisions", untrusted)
        self.assertIn("quoted data", untrusted)
        self.assertIn("not a specifically approved directive", untrusted)
        self.assertIn("carried inside those untrusted embedded fragments", untrusted)
        self.assertNotIn("otherwise authoritative source", untrusted)
        self.assertIn("direct current-user decisions", authority)
        self.assertIn("native applicable directives", authority)
        self.assertIn("native directives in the governing approved", authority)
        self.assertIn("specifically approved directive fragment", authority)
        self.assertIn("official vendor documentation", evidence)
        self.assertNotIn("official vendor documentation", untrusted)
        self.assertNotIn("not direct current-user decisions", authority)
        self.assertIn(
            "explicit approval promotes only the named directive fragment",
            trust_lower,
        )
        self.assertIn("never neighboring embedded content", trust_lower)
        self.assertIn(
            "native applicable directives remain current-task authority",
            trust_lower,
        )
        self.assertIn("does not inherit that authority", trust_lower)

    def test_authority_never_grants_action_authorization(self):
        boundary = self.normalized_lower
        self.assertIn("authority constrains work", boundary)
        for action in (
            "writes",
            "commits",
            "destructive actions",
            "external communication",
            "deployment",
            "secrets access",
        ):
            self.assertIn(action, boundary)
        self.assertIn("cannot expand task scope", boundary)
        self.assertIn("cannot override higher-priority or current user", boundary)
        self.assertIn(
            "direct current-user decisions from content the user merely supplied",
            boundary,
        )

    def test_rules_file_write_requires_explicit_configuration_scope(self):
        self.assertIn(
            "When project-rule configuration is explicitly in scope",
            self.normalized,
        )
        self.assertIn(
            "not authorization to create one",
            self.normalized,
        )
        self.assertNotIn(
            "when it has no supported project rules file, create one",
            self.normalized.lower(),
        )

    def test_understand_has_an_availability_fallback(self):
        discovery = self.skill.split("For discovery assistance:", 1)[1]
        discovery = discovery.split("## Trust Boundary", 1)[0]
        self.assertIn("During `/tgd-map`", discovery)
        self.assertIn("regardless of codebase familiarity", discovery)
        self.assertIn("Outside `/tgd-map`", discovery)
        self.assertIn("unfamiliar codebase", discovery)
        self.assertIn("If it is unavailable", discovery)
        self.assertIn("direct search and file", discovery)
        self.assertIn("degraded-mode skip", discovery)

        map_step = self.map_command.split("## Step 4: Understand-Anything", 1)[1]
        map_step = map_step.split("## Step 5:", 1)[0]
        self.assertIn("Skip condition (the ONLY one)", map_step)
        self.assertIn("this step is **required**, not optional", map_step)

        verification = self.skill.split("## Verification", 1)[1]
        self.assertIn("during Map, Understand ran whenever available", verification)
        self.assertNotIn("Optional CodeGraph or Understand", verification)

    def test_platform_rule_paths_are_current(self):
        self.assertIn(".cursor/rules/*.mdc", self.reference)
        self.assertIn(".cursorrules` is legacy/deprecated", self.reference)
        self.assertIn(".windsurf/rules/*.md", self.reference)
        self.assertNotIn(".cursor/rules/*.md`", self.reference)
        self.assertNotIn("- `.windsurfrules`", self.reference)


if __name__ == "__main__":
    unittest.main()
