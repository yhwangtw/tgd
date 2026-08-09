from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SupportWikiContractTests(unittest.TestCase):
    def test_wiki_generation_is_explicit_and_standalone(self) -> None:
        skill = (ROOT / "skills" / "tgd-support-wiki" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        generator = (
            ROOT / "skills" / "tgd-support-wiki" / "scripts" / "generate-wiki.py"
        ).read_text(encoding="utf-8")
        map_command = (ROOT / ".claude" / "commands" / "tgd-map.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("standalone", skill.lower())
        self.assertIn("not** part of the Map pipeline", skill)
        self.assertIn("Invoked manually", generator)
        self.assertIn("/tgd-map never calls this generator", generator)
        self.assertNotIn("Called by /tgd-map", generator)
        self.assertNotIn("tgd-support-wiki", map_command)


if __name__ == "__main__":
    unittest.main()
