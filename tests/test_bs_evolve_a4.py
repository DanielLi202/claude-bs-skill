from __future__ import annotations

import json
import subprocess
import uuid
import sys
import tempfile
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def run(cmd, cwd=None, check=True):
    return subprocess.run(cmd, cwd=cwd, check=check, text=True, capture_output=True)


def make_repo(base: Path, name: str = "target") -> Path:
    repo = base / name
    repo.mkdir()
    run(["git", "init"], cwd=repo)
    run(["git", "config", "user.email", "test@example.com"], cwd=repo)
    run(["git", "config", "user.name", "Test User"], cwd=repo)
    dog = repo / ".prompts" / "dogfood" / "cycle-001"
    dog.mkdir(parents=True)
    (dog / "grade_round_1.md").write_text(
        "spec_compliance_matrix:\n"
        "- id: T-20260526-180000-c001shp1\n"
        "  status: PASS\n"
        "  evidence_ref: ProjectZephyr package manager registry check passed under "
        "/Users/example/ProjectZephyr with TASK-123, DA-6, UX-36, and decision-abc redacted\n",
        encoding="utf-8",
    )
    run(["git", "add", ".prompts/dogfood/cycle-001/grade_round_1.md"], cwd=repo)
    run(["git", "commit", "-m", "seed corpus"], cwd=repo)
    return repo


def clone_skill(src: Path, dest: Path) -> None:
    run(["git", "clone", "--quiet", str(src), str(dest)])
    run(["git", "config", "user.email", "test@example.com"], cwd=dest)
    run(["git", "config", "user.name", "Test User"], cwd=dest)


class BsEvolveA4InitTests(unittest.TestCase):
    def test_init_commits_anonymous_fixture_and_clean_clone_can_lint_it(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            skill = base / "skill"
            clone_skill(ROOT, skill)
            init = skill / "harness" / "evolve-loop" / "bin" / "bs-evolve-init.py"
            repo = make_repo(base, "ProjectZephyr")
            slug = "demo-" + uuid.uuid4().hex[:8]

            proc = run([sys.executable, str(init), str(repo), "--slug", slug, "--mode", "auto"])
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["cycles"], 1)
            fixture = Path(payload["fixture"])
            fixture_rel = fixture.resolve().relative_to(skill.resolve()).as_posix()

            cfg = yaml.safe_load((repo / ".bs-evolve" / "config.yaml").read_text(encoding="utf-8"))
            self.assertEqual(cfg["state_dir"], ".")
            self.assertEqual(cfg["reviews_root"], "./reviews")
            self.assertEqual(cfg["corpus_dir"], "./corpus")
            self.assertEqual(cfg["mode"], "auto")
            self.assertTrue((repo / ".bs-evolve" / "state.json").exists())
            self.assertEqual(run(["git", "check-ignore", "-q", ".bs-evolve/config.yaml"], cwd=repo, check=False).returncode, 0)
            self.assertEqual(run(["git", "check-ignore", "-q", ".bs-evolve/state.json"], cwd=repo, check=False).returncode, 0)
            self.assertNotEqual(run(["git", "check-ignore", "-q", ".bs-evolve/reviews/cycle-001/closure.yaml"], cwd=repo, check=False).returncode, 0)
            self.assertEqual(run(["git", "check-ignore", "-q", ".bs-evolve/fleet.yaml"], cwd=skill, check=False).returncode, 0)

            tracked = run(["git", "ls-files", fixture_rel], cwd=skill).stdout.splitlines()
            self.assertEqual(
                tracked,
                [
                    f"{fixture_rel}/grade.md",
                    f"{fixture_rel}/metadata.yaml",
                    f"{fixture_rel}/outcome.md",
                    f"{fixture_rel}/source_excerpt.md",
                ],
            )
            self.assertIn(f"bs-evolve-init: add anonymous fixture {fixture.name}", run(["git", "log", "-1", "--pretty=%s"], cwd=skill).stdout)

            clean = base / "skill-clean"
            clone_skill(skill, clean)
            clean_fixture = clean / fixture_rel
            meta = yaml.safe_load((clean_fixture / "metadata.yaml").read_text(encoding="utf-8"))
            text = "\n".join(p.read_text(encoding="utf-8") for p in clean_fixture.iterdir() if p.is_file())
            self.assertEqual(meta["task_type"], "code")
            self.assertEqual(meta["risk_level"], "low")
            self.assertNotRegex(
                text,
                r"ProjectZephyr"
                r"|/(?:Users|private|tmp|var|opt|home)/"
                r"|decision[-_ ]"
                r"|\bT-\d{8,}(?:-\d+)?-[A-Za-z0-9_.-]+\b"
                r"|\b[A-Z]{1,8}-\d+[A-Za-z0-9'_.-]*\b",
            )
            lint = run([
                sys.executable,
                str(clean / "runtime" / "grade_lint.py"),
                "--task-type",
                meta["task_type"],
                "--risk-level",
                meta["risk_level"],
                "--grade-file",
                str(clean_fixture / "grade.md"),
                "--outcome-file",
                str(clean_fixture / "outcome.md"),
                "--evidence-file",
                str(base / "fixture_lint.json"),
            ], check=False)
            self.assertEqual(lint.returncode, 0, lint.stdout + lint.stderr)

    def test_init_fails_without_corpus(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "empty"
            repo.mkdir()
            run(["git", "init"], cwd=repo)
            proc = run([sys.executable, str(ROOT / "harness" / "evolve-loop" / "bin" / "bs-evolve-init.py"), str(repo), "--slug", "empty"], check=False)
            self.assertEqual(proc.returncode, 3)
            self.assertIn("corpus_dir glob found no code cycles", proc.stderr)


if __name__ == "__main__":
    unittest.main()
