"""Regression tests for the high-risk guidance in tgd-core-git."""

from pathlib import Path
import re
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "tgd-core-git" / "SKILL.md"
REFERENCE = ROOT / "references" / "git-workflow-patterns.md"


class CoreGitSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = SKILL.read_text(encoding="utf-8")
        cls.reference = REFERENCE.read_text(encoding="utf-8")
        cls.guidance = cls.skill + "\n" + cls.reference
        cls.normalized_skill = " ".join(cls.skill.split())

    def test_commit_requires_separate_authorization(self):
        self.assertIn(
            "does not itself authorize creating a commit", self.normalized_skill
        )
        self.assertIn(
            "active lifecycle step or the user explicitly authorizes it",
            self.normalized_skill,
        )

        message_section = self.reference.split("## Atomic History and Messages", 1)[1]
        message_section = message_section.split("## Change Summary Example", 1)[0]
        guard = message_section.index(
            "After the active lifecycle step or user authorizes the commits"
        )
        commit = message_section.index('git commit -m "refactor:')
        self.assertLess(guard, commit)

    def test_broad_destructive_reset_is_not_recommended(self):
        broad_discard_patterns = (
            r"git\s+reset\s+--hard",
            r"git\s+restore(?:\s+--\S+)*\s+\.(?:\s|$)",
            r"git\s+checkout\s+--\s+\.(?:\s|$)",
            r"git\s+clean\s+-[^\n]*f",
            r"rm\s+-rf\b",
        )
        for pattern in broad_discard_patterns:
            self.assertIsNone(re.search(pattern, self.guidance, re.MULTILINE))

        self.assertIn(
            "exact agent-owned and explicitly authorized slice",
            self.normalized_skill,
        )
        self.assertIn(
            "unrelated staged, unstaged, or untracked work",
            self.normalized_skill,
        )
        self.assertIn("path-scoped restore", self.reference)

        recovery = self.reference.split("Before discarding any failed work", 1)[1]
        recovery = recovery.split("```bash", 1)[1].split("```", 1)[0]
        self.assertIn('git diff --name-status -- "$agent_owned_path"', recovery)
        self.assertIn(
            'git diff --staged --name-status -- "$agent_owned_path"', recovery
        )
        self.assertNotRegex(recovery, r"git diff(?: --staged)? -- \"")
        subprocess.run(
            ["sh", "-n"],
            input=recovery,
            text=True,
            check=True,
            capture_output=True,
        )

    def test_secret_gate_avoids_raw_output_and_orders_review(self):
        raw_match_patterns = (
            r"git\s+diff[^\n]*(?:--staged|--cached)[^\n]*\|\s*grep\b",
            r"git\s+diff[^\n]*(?:--staged|--cached)[^\n]*\|\s*rg\b",
        )
        for pattern in raw_match_patterns:
            self.assertIsNone(re.search(pattern, self.guidance, re.IGNORECASE))

        self.assertIn(
            "without printing matched secret values", self.normalized_skill
        )
        self.assertIn(
            "explicitly identified user or local repository owner",
            self.normalized_skill,
        )
        self.assertIn("non-logged local context", self.normalized_skill)
        self.assertIn("confirm that it contains no secrets", self.normalized_skill)
        self.assertIn("stop and do not commit", self.normalized_skill)

        scope = self.normalized_skill.index("git diff --staged --name-status")
        scanner = self.normalized_skill.index("repository-configured secret scanner")
        patch_review = self.normalized_skill.index("inspect the full staged patch")
        self.assertLess(scope, scanner)
        self.assertLess(scanner, patch_review)

    def test_all_copyable_shell_blocks_parse(self):
        shell_blocks = re.findall(r"```bash\n(.*?)```", self.reference, re.DOTALL)
        self.assertGreaterEqual(len(shell_blocks), 4)
        for block in shell_blocks:
            subprocess.run(
                ["sh", "-n"],
                input=block,
                text=True,
                check=True,
                capture_output=True,
            )

        reference_lines = self.reference.splitlines()
        scope = reference_lines.index("git diff --staged --name-status")
        scanner = next(
            index
            for index, line in enumerate(reference_lines)
            if "Run the repository-configured secret scanner" in line
        )
        patch_review = reference_lines.index("git diff --staged")
        self.assertLess(scope, scanner)
        self.assertLess(scanner, patch_review)
        self.assertIn(
            "After the scanner passes, or as the owner-confirmed fallback review",
            self.reference,
        )


if __name__ == "__main__":
    unittest.main()
