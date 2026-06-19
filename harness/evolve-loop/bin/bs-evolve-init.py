#!/usr/bin/env python3
"""Initialize a target repository for /bs-evolve."""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone

import yaml

SCRIPT = pathlib.Path(__file__).resolve()
SKILL_REPO = SCRIPT.parents[3]
CONFIG_HELPER = SCRIPT.with_name("bs-evolve-config.py")
GITIGNORE_HELPER = SCRIPT.with_name("bs-evolve-gitignore.py")
LOCK_HELPER = SCRIPT.with_name("evolve-lock.py")
FLEET_UPDATE = SCRIPT.with_name("fleet-update.py")
LOOP_STATE = SCRIPT.with_name("loop-state.py")
FIXTURE_ROOT = SKILL_REPO / "tests" / "grade_lint_fixtures"
GRADE_LINT = SKILL_REPO / "runtime" / "grade_lint.py"
FLEET = SKILL_REPO / ".bs-evolve" / "fleet.yaml"
PRODUCTISH = re.compile(
    r"/(?:Users|private|tmp|var|opt|home)/"
    r"|decision[-_ ]?\w+"
    r"|\bT-\d{8,}(?:-\d+)?-[A-Za-z0-9_.-]+\b"
    r"|\b[A-Z]{1,8}-\d+[A-Za-z0-9'_.-]*\b"
    "|" + "Open" + "Symphony" + "|" + "Project" + "Zephyr",
)


def run(cmd: list[str], *, cwd: pathlib.Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, check=check, text=True, capture_output=True)


def git_root(path: pathlib.Path) -> pathlib.Path:
    return pathlib.Path(run(["git", "-C", str(path), "rev-parse", "--show-toplevel"]).stdout.strip()).resolve()


def now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def find_corpus(target: pathlib.Path) -> list[pathlib.Path]:
    roots = [target / ".prompts" / "dogfood", target / ".bootstrap" / "cycles", target / "dogfood"]
    cycles: list[pathlib.Path] = []
    for root in roots:
        if root.exists():
            cycles.extend(sorted(p for p in root.glob("cycle-*") if p.is_dir()))
    return cycles


def anonymize(text: str, *, target: pathlib.Path, slug: str) -> str:
    dynamic = {target.name, slug, target.stem}
    generic_path_parts = {"/", "Users", "workspace", "utils", "private", "tmp", "var", "opt", "home"}
    dynamic.update(part for part in target.parts[-3:] if part and part not in generic_path_parts)
    replacements = [
        (r"/(?:Users|private|tmp|var|opt|home)/[^\s`'\"]+", "ABS_PATH_REDACTED"),
        (r"\bT-\d{8,}(?:-\d+)?-[A-Za-z0-9_.-]+\b", "TASK_REDACTED"),
        (r"\b[A-Z]{1,8}-\d+[A-Za-z0-9'_.-]*\b", "TASK_REDACTED"),
        (r"\b[A-Z]+-\d{3}\b", "TASK_REDACTED"),
        (r"decision[-_ ]?[A-Za-z0-9_.-]+", "JUDGMENT_REDACTED"),
    ]
    out = text
    for token in sorted(dynamic, key=len, reverse=True):
        if len(token) >= 3 and re.search(r"[A-Za-z]", token):
            replacements.append((re.escape(token), "ProjectRedacted"))
    for pat, repl in replacements:
        out = re.sub(pat, repl, out, flags=re.I)
    return out[:4000]


def source_text(cycle: pathlib.Path) -> str:
    for name in ("grade_round_1.md", "outcome.md", "r1.md", "README.md"):
        hits = list(cycle.rglob(name))
        if hits:
            return hits[0].read_text(encoding="utf-8", errors="replace")
    for p in cycle.rglob("*.md"):
        return p.read_text(encoding="utf-8", errors="replace")
    return ""


def clean_grade_fixture() -> str:
    return """# Anonymous must-not-fire grade fixture
```yaml
grade_summary:
  p0_count: 0
  p1_count: 0
  p2_count: 0
```
```yaml
acceptance_status:
  - id: CFG
    status: pass
    severity: P1
  - id: INIT
    status: pass
    severity: P2
```
```yaml
spec_compliance_matrix:
  - acceptance_id: CFG
    status: pass
    severity_if_fail: P1
    spec_ref: docs/spec.md#config
    evidence_ref: tests/config.rs::locked_dependency_and_yaml_comments
  - acceptance_id: INIT
    status: pass
    severity_if_fail: P2
    spec_ref: docs/spec.md#init
    evidence_ref: tests/init.rs::init_smoke
```
```yaml
negative_regression_tests:
  - acceptance_id: CFG
    status: pass
    severity_if_fail: P1
    scenario: malformed secret-bearing YAML does not echo the secret and locked dependency is present
    evidence_ref: tests/config.rs::malformed_secret_yaml_is_redacted
```
```yaml
secret_leakage_audit:
  status: pass
  checked_surfaces: [debug, display, errors, logs]
  cleartext_secret_probe:
    status: pass
    shapes:
      - token=sk-secret-test
      - '{"api_key":"sk-secret-test"}'
      - "Authorization: Bearer sk-secret-test"
  evidence_ref: tests/config.rs::malformed_secret_yaml_is_redacted
```
```yaml
dependency_spec_review:
  - dependency: serde_yaml_bw
    status: pass
    severity_if_fail: P1
    spec_ref: docs/architecture/tech-stack.yaml
    evidence_ref: cargo tree -p generic-config
```
"""


def clean_outcome_fixture() -> str:
    return """# Anonymous must-not-fire outcome fixture
```yaml
acceptance:
  - id: CFG
    severity: P1
    statement: use locked crate dependency and reject malformed config safely
  - id: INIT
    severity: P2
    statement: init writes files
```
"""


def validate_fixture(out: pathlib.Path) -> None:
    meta = yaml.safe_load((out / "metadata.yaml").read_text(encoding="utf-8")) or {}
    proc = run([
        sys.executable,
        str(GRADE_LINT),
        "--task-type",
        str(meta.get("task_type", "code")),
        "--risk-level",
        str(meta.get("risk_level", "low")),
        "--grade-file",
        str(out / "grade.md"),
        "--outcome-file",
        str(out / "outcome.md"),
        "--evidence-file",
        str(out / "grade_lint.json"),
    ], check=False)
    if proc.returncode != 0:
        raise SystemExit("init failed: generated fixture does not pass grade_lint:\n" + proc.stdout + proc.stderr)
    (out / "grade_lint.json").unlink(missing_ok=True)


def assert_fixture_anonymous(out: pathlib.Path) -> None:
    for path in out.iterdir():
        if path.is_file() and PRODUCTISH.search(path.read_text(encoding="utf-8", errors="replace")):
            raise SystemExit(f"init failed: anonymized fixture still contains product/path/decision identifiers in {path.name}")


def commit_fixture(out: pathlib.Path) -> None:
    rel = out.relative_to(SKILL_REPO).as_posix()
    run(["git", "-C", str(SKILL_REPO), "add", rel])
    diff = run(["git", "-C", str(SKILL_REPO), "diff", "--cached", "--quiet", "--", rel], check=False)
    if diff.returncode == 0:
        return
    run([
        "git",
        "-C",
        str(SKILL_REPO),
        "-c",
        "user.email=bs-evolve-init@example.invalid",
        "-c",
        "user.name=bs-evolve-init",
        "commit",
        "-m",
        f"bs-evolve-init: add anonymous fixture {out.name}",
        "--",
        rel,
    ])


def seed_fixture(target: pathlib.Path, cycles: list[pathlib.Path], slug: str) -> pathlib.Path:
    if not cycles:
        raise SystemExit("init failed: corpus_dir glob found no code cycles")
    text = ""
    for cycle in cycles:
        text = source_text(cycle)
        if text.strip():
            break
    text = anonymize(text, target=target, slug=slug)
    if len(text.strip()) < 40:
        raise SystemExit("init failed: no minimal anonymizable negative fixture could be produced")
    if PRODUCTISH.search(text):
        raise SystemExit("init failed: anonymized fixture still contains product/path/decision identifiers")
    digest = hashlib.sha256((slug + text).encode()).hexdigest()[:12]
    out = FIXTURE_ROOT / f"anon-{digest}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "metadata.yaml").write_text(yaml.safe_dump({
        "fixture_id": f"anon_{digest}",
        "source": "bs-evolve-init anonymized target corpus",
        "created_at": now_z(),
        "task_type": "code",
        "risk_level": "low",
        "expect": "must_not_fire",
        "source_excerpt_sha256": hashlib.sha256(text.encode()).hexdigest(),
    }, sort_keys=False), encoding="utf-8")
    (out / "grade.md").write_text(clean_grade_fixture(), encoding="utf-8")
    (out / "outcome.md").write_text(clean_outcome_fixture(), encoding="utf-8")
    (out / "source_excerpt.md").write_text(text + "\n", encoding="utf-8")
    validate_fixture(out)
    assert_fixture_anonymous(out)
    commit_fixture(out)
    return out


def update_fleet_unlocked(target: pathlib.Path, slug: str, config: pathlib.Path) -> None:
    run([sys.executable, str(FLEET_UPDATE), "--fleet", str(FLEET), "--slug", slug, "--target", str(target), "--config", str(config)])


def acquire_skill_lock(slug: str) -> tuple[pathlib.Path, str]:
    lock = FLEET.parent / "SKILL.lock"
    proc = run([sys.executable, str(LOCK_HELPER), "acquire", "--lock-file", str(lock), "--owner", f"init:{slug}"], check=False)
    if proc.returncode != 0:
        raise SystemExit("init failed: SKILL.lock held; retry later\n" + proc.stdout + proc.stderr)
    return lock, json.loads(proc.stdout)["token"]


def ensure_skill_ignore() -> None:
    gi = SKILL_REPO / ".gitignore"
    text = gi.read_text(encoding="utf-8") if gi.exists() else ""
    if ".bs-evolve/" not in text:
        gi.write_text(text.rstrip() + "\n\n# bs-evolve local fleet/state\n.bs-evolve/\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("target", type=pathlib.Path)
    ap.add_argument("--mode", choices=["auto", "dry-run"], default="auto")
    ap.add_argument("--max-iterations", type=int, default=5)
    ap.add_argument("--slug")
    args = ap.parse_args()
    target = git_root(args.target)
    slug = args.slug or re.sub(r"[^A-Za-z0-9_.-]+", "-", target.name).strip("-._") or "target"
    config_dir = target / ".bs-evolve"
    config_dir.mkdir(parents=True, exist_ok=True)
    config = config_dir / "config.yaml"
    cycles = find_corpus(target)
    if not cycles:
        print("init failed: corpus_dir glob found no code cycles", file=sys.stderr)
        return 3
    config.write_text(yaml.safe_dump({
        "schema_version": 1,
        "project_slug": slug,
        "target_repo": "..",
        "skill_repo": str(SKILL_REPO),
        "state_dir": ".",
        "reviews_root": "./reviews",
        "corpus_dir": "./corpus",
        "adopt_min_cycle": min(int(re.search(r"(\d+)$", c.name).group(1)) for c in cycles if re.search(r"(\d+)$", c.name)),
        "mode": args.mode,
        "max_iterations": args.max_iterations,
        "wake_prompt": f"/bs-evolve --config {config}",
    }, sort_keys=False), encoding="utf-8")
    # Keep a local corpus pointer by copying lightweight cycle dirs names only when absent.
    corpus_dir = config_dir / "corpus"
    corpus_dir.mkdir(exist_ok=True)
    for c in cycles[:3]:
        marker = corpus_dir / c.name
        marker.mkdir(exist_ok=True)
        (marker / ".source").write_text(str(c), encoding="utf-8")
    run([sys.executable, str(GITIGNORE_HELPER), "--target", str(target)])
    run([sys.executable, str(GITIGNORE_HELPER), "--target", str(target), "--check"])
    run([sys.executable, str(LOOP_STATE), "--state-dir", str(config_dir), "init", "--target", str(target), "--skill", str(SKILL_REPO), "--mode", args.mode, "--max", str(args.max_iterations)])
    lock, token = acquire_skill_lock(slug)
    try:
        fixture = seed_fixture(target, cycles, slug)
        ensure_skill_ignore()
        update_fleet_unlocked(target, slug, config)
        # Ensure local skill state remains ignored while fixture is committed-capable.
        ignored = run(["git", "-C", str(SKILL_REPO), "check-ignore", "-q", ".bs-evolve/fleet.yaml"], check=False).returncode == 0
        if not ignored:
            print("init failed: skill .bs-evolve/fleet.yaml is not ignored", file=sys.stderr)
            return 4
    finally:
        run([sys.executable, str(LOCK_HELPER), "release", "--lock-file", str(lock), "--token", token], check=False)
    print(json.dumps({"target": str(target), "config": str(config), "fixture": str(fixture), "cycles": len(cycles)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
