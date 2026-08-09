from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / "skills"


class SkillLanguageContractTests(unittest.TestCase):
    def test_canonical_skill_sources_use_english_letters_only(self) -> None:
        violations: list[str] = []
        for path in sorted(SKILLS_DIR.glob("*/SKILL.md")):
            for line_number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                non_english_letters = sorted(
                    {char for char in line if char.isalpha() and not char.isascii()}
                )
                if non_english_letters:
                    rendered = "".join(non_english_letters)
                    violations.append(
                        f"{path.relative_to(ROOT)}:{line_number}: {rendered}"
                    )

        self.assertEqual([], violations)

    def test_user_facing_labels_follow_the_users_language(self) -> None:
        core = (SKILLS_DIR / "tgd-core-rules" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        interview = (SKILLS_DIR / "tgd-define-interview" / "SKILL.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("Render choices and labels in the user's language.", core)
        self.assertIn("Labels and speech acts follow the user's language.", interview)
        self.assertIn("never literal\noutput to copy", interview)
        self.assertIn("do not default to English", interview)


if __name__ == "__main__":
    unittest.main()
