from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contract.md"
SKILL = ROOT / "skill.yaml"
VERIFY = ROOT / "harness" / "evolve-loop" / "bin" / "verify-manifest.sh"


def parse_manifest() -> dict[str, str]:
    rows = {}
    in_section = False
    for line in CONTRACT.read_text(encoding="utf-8").splitlines():
        if line.startswith("## Runtime manifest"):
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        m = re.match(r"^\|\s*([^|]+?)\s*\|\s*([0-9a-f]{64})\s*\|$", line)
        if m and m.group(1).strip() not in {"file", "---"}:
            rows[m.group(1).strip()] = m.group(2)
    return rows


class BsEvolveA3ManifestTests(unittest.TestCase):
    def test_new_commands_are_registered(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("name: bs-evolve", text)
        self.assertIn("name: bs-evolve-init", text)
        self.assertTrue((ROOT / "commands" / "bs-evolve.md").exists())
        self.assertTrue((ROOT / "commands" / "bs-evolve-init.md").exists())

    def test_manifest_locks_new_commands_and_bin_helpers(self):
        rows = parse_manifest()
        required = {
            "commands/bs-evolve.md",
            "commands/bs-evolve-init.md",
            "harness/evolve-loop/bin/adopt-cycle.py",
            "harness/evolve-loop/bin/bs-evolve-config.py",
            "harness/evolve-loop/bin/bs-evolve-gitignore.py",
            "harness/evolve-loop/bin/bs-evolve-init.py",
            "harness/evolve-loop/bin/closure.py",
            "harness/evolve-loop/bin/loop-state.py",
            "harness/evolve-loop/bin/verify-manifest.sh",
        }
        self.assertTrue(required.issubset(rows.keys()))
        for rel in required:
            self.assertEqual(hashlib.sha256((ROOT / rel).read_bytes()).hexdigest(), rows[rel])

    def test_verify_manifest_accepts_helpers_and_fails_on_drift(self):
        subprocess.run(["bash", str(VERIFY), str(ROOT)], check=True, text=True, capture_output=True)
        rows = parse_manifest()
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td) / "skill"
            for rel in rows:
                dest = tmp / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / rel, dest)
            shutil.copy2(CONTRACT, tmp / "contract.md")
            target = tmp / "harness" / "evolve-loop" / "bin" / "bs-evolve-config.py"
            target.write_text(target.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8")
            proc = subprocess.run(["bash", str(VERIFY), str(tmp)], text=True, capture_output=True)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("MISMATCH harness/evolve-loop/bin/bs-evolve-config.py", proc.stdout)


if __name__ == "__main__":
    unittest.main()
