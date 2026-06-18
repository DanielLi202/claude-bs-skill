from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "harness" / "evolve-loop" / "bin" / "bs-evolve-config.py"
GITIGNORE = ROOT / "harness" / "evolve-loop" / "bin" / "bs-evolve-gitignore.py"
ADOPT = ROOT / "harness" / "evolve-loop" / "bin" / "adopt-cycle.py"
CLOSURE = ROOT / "harness" / "evolve-loop" / "bin" / "closure.py"
REVIEWS_ROOT = ROOT / "harness" / "evolve-loop" / "reviews"
COMMAND = ROOT / "commands" / "bs-evolve.md"


def run(cmd, cwd=None, check=True):
    return subprocess.run(cmd, cwd=cwd, check=check, text=True, capture_output=True)


class BsEvolveA2StateMigrationTests(unittest.TestCase):
    def test_skill_reviews_root_contains_no_project_or_cycle_ledgers(self):
        tracked = run(["git", "-C", str(ROOT), "ls-files", "harness/evolve-loop/reviews"]).stdout.splitlines()
        self.assertEqual(tracked, ["harness/evolve-loop/reviews/.gitkeep"])
        all_paths = [p.relative_to(REVIEWS_ROOT).as_posix() for p in REVIEWS_ROOT.rglob("*")]
        self.assertEqual(all_paths, [".gitkeep"])

    def test_config_paths_must_resolve_inside_target_repo(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            cfg_dir = base / "target" / ".bs-evolve"
            cfg_dir.mkdir(parents=True)
            cfg = cfg_dir / "config.yaml"
            cfg.write_text("\n".join([
                "schema_version: 1",
                "project_slug: demo",
                "target_repo: ..",
                "state_dir: ../../outside-state",
                "reviews_root: ./reviews",
                "corpus_dir: ./corpus",
            ]), encoding="utf-8")
            proc = run([sys.executable, str(CONFIG), "--config", str(cfg), "--emit-env"], check=False)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("state_dir must resolve inside target_repo", proc.stderr)


    def test_documented_config_layout_exports_canonical_target_bsevolve_paths(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "target"
            config_dir = target / ".bs-evolve"
            config_dir.mkdir(parents=True)
            cfg = config_dir / "config.yaml"
            cfg.write_text("\n".join([
                "schema_version: 1",
                "project_slug: demo",
                "target_repo: ..",
                "state_dir: .",
                "reviews_root: ./reviews",
                "corpus_dir: ./corpus",
            ]), encoding="utf-8")
            out = run([sys.executable, str(CONFIG), "--config", str(cfg), "--json"]).stdout
            self.assertIn(f'"BS_LOOP_STATE_DIR": "{(target / ".bs-evolve").resolve()}', out)
            self.assertIn(f'"BS_LOOP_REVIEWS_ROOT": "{(target / ".bs-evolve" / "reviews").resolve()}', out)
            self.assertIn(f'"BS_LOOP_CORPUS_DIR": "{(target / ".bs-evolve" / "corpus").resolve()}', out)

    def test_target_gitignore_keeps_ledgers_committed_but_ignores_local_state(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "target"
            target.mkdir()
            run(["git", "init"], cwd=target)
            run(["git", "config", "user.email", "test@example.com"], cwd=target)
            run(["git", "config", "user.name", "Test User"], cwd=target)
            run([sys.executable, str(GITIGNORE), "--target", str(target)])
            run([sys.executable, str(GITIGNORE), "--target", str(target), "--check"])
            self.assertFalse((target / ".bs-evolve" / "reviews" / "cycle-001" / "closure.yaml").exists())
            empty_newest = run([sys.executable, str(CLOSURE), "--reviews-root", str(target / ".bs-evolve" / "reviews"), "newest-open"], check=False)
            self.assertEqual(empty_newest.returncode, 10)
            ledger = target / ".bs-evolve" / "reviews" / "cycle-001" / "closure.yaml"
            ledger.parent.mkdir(parents=True, exist_ok=True)
            ledger.write_text("cycle: cycle-001\nr1: null\nr2: null\nskill_release: null\nremediation: null\nclosed: false\n", encoding="utf-8")
            (target / ".bs-evolve" / "state.json").write_text("{}", encoding="utf-8")
            (target / ".bs-evolve" / "config.yaml").write_text("mode: auto\n", encoding="utf-8")
            run(["git", "add", ".gitignore", ".bs-evolve/reviews/cycle-001/closure.yaml"], cwd=target)
            status = run(["git", "status", "--short"], cwd=target).stdout
            self.assertIn("A  .bs-evolve/reviews/cycle-001/closure.yaml", status)
            self.assertNotIn("state.json", status)
            self.assertNotIn("config.yaml", status)
            run(["git", "commit", "-m", "add bs-evolve ledger"], cwd=target)
            listed = run(["git", "ls-files", ".bs-evolve/reviews/cycle-001/closure.yaml"], cwd=target).stdout.strip()
            self.assertEqual(listed, ".bs-evolve/reviews/cycle-001/closure.yaml")
            self.assertNotEqual(run(["git", "check-ignore", "-q", ".bs-evolve/reviews/cycle-001/closure.yaml"], cwd=target, check=False).returncode, 0)
            self.assertEqual(run(["git", "check-ignore", "-q", ".bs-evolve/state.json"], cwd=target, check=False).returncode, 0)
            clone = Path(td) / "clone"
            run(["git", "clone", str(target), str(clone)])
            newest = run([sys.executable, str(CLOSURE), "--reviews-root", str(clone / ".bs-evolve" / "reviews"), "newest-open"], check=False)
            self.assertEqual(newest.returncode, 0)
            self.assertTrue(newest.stdout.strip().endswith(".bs-evolve/reviews/cycle-001"))
            nxt = run([sys.executable, str(CLOSURE), "--dir", str(clone / ".bs-evolve" / "reviews" / "cycle-001"), "next"]).stdout.strip()
            self.assertEqual(nxt, "r1")

    def test_adopt_scan_requires_explicit_lower_bound_and_skips_closed_reviews(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            corpus = base / "corpus"
            reviews = base / "reviews"
            for n in [1, 18, 19, 20]:
                (corpus / f"cycle-{n:03d}").mkdir(parents=True)
            closed = reviews / "cycle-020"
            closed.mkdir(parents=True)
            (closed / "closure.yaml").write_text("closed: true\n", encoding="utf-8")
            proc = run([sys.executable, str(ADOPT), "--corpus-root", str(corpus), "--reviews-root", str(reviews), "--min-cycle", "18"])
            self.assertTrue(proc.stdout.strip().endswith("cycle-019"))
            proc2 = run([sys.executable, str(ADOPT), "--corpus-root", str(corpus), "--reviews-root", str(reviews), "--min-cycle", "21"], check=False)
            self.assertEqual(proc2.returncode, 10)

    def test_command_documents_target_state_and_gitignore_policy(self):
        text = COMMAND.read_text(encoding="utf-8")
        self.assertIn('adopt-cycle.py --corpus-root "$CORPUS" --reviews-root "$REVIEWS" --min-cycle "$BS_LOOP_ADOPT_MIN_CYCLE"', text)
        self.assertIn('bs-evolve-gitignore.py', text)
        self.assertIn('Do not ignore `.bs-evolve/reviews/**`', text)
        self.assertIn('closure ledgers must survive a clean checkout', text)


if __name__ == "__main__":
    unittest.main()
