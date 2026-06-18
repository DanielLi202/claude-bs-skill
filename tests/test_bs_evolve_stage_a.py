from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BsEvolveStageAGuards(unittest.TestCase):
    def test_runtime_surfaces_have_no_opensymphony_hardcoding_outside_docs_tests(self):
        forbidden = [
            "OpenSymphony",
            "opensymphony",
            "/Users/lidongyuan/workspace/utils/OpenSymphony-V3",
            "reviews/opensymphony",
            ".prompts/dogfood",
            ".prompts/loop",
        ]
        roots = [ROOT / "commands", ROOT / "harness" / "evolve-loop"]
        offenders: list[str] = []
        for root in roots:
            for path in root.rglob("*"):
                if path.name == "migrate-inplace.sh":
                    continue  # the in-place migrator intentionally names legacy .prompts paths
                if path.is_file() and "__pycache__" not in path.parts:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                    for token in forbidden:
                        if token in text:
                            offenders.append(f"{path.relative_to(ROOT)} contains {token}")
        self.assertEqual(offenders, [])

    def test_legacy_loop_prompt_is_tombstone_not_algorithm_body(self):
        text = (ROOT / "harness" / "evolve-loop" / "loop-prompt.md").read_text(encoding="utf-8")
        self.assertIn("legacy", text.lower())
        self.assertIn("/bs-evolve --config", text)
        self.assertIn("do not continue the legacy loop", text)
        self.assertNotIn("Stage 1", text)


if __name__ == "__main__":
    unittest.main()
