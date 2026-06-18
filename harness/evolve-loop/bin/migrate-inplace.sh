#!/usr/bin/env python3
"""In-place migration for a stopped legacy bs-evolve target.

Migrates a target from .prompts/loop runtime state to target-local .bs-evolve
config/state/reviews. The script is intentionally fail-closed: precondition
failures occur before target writes, dry-run performs zero writes, and rollback
uses a pre-migration snapshot plus the recorded target HEAD.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from typing import Any

try:
    import yaml
except Exception as exc:  # pragma: no cover - repository tests require PyYAML
    print(f"migrate-inplace: PyYAML required: {exc}", file=sys.stderr)
    sys.exit(2)

CYCLE_RE = re.compile(r"^cycle-(\d+)$")
SNIPPET_BEGIN = "# >>> bs-evolve local state >>>"
SNIPPET_END = "# <<< bs-evolve local state <<<"
GITIGNORE_PATTERNS = [
    ".prompts/loop/STOP",
    ".bs-evolve/config.yaml",
    ".bs-evolve/state.json",
    ".bs-evolve/RUNNING.lock*",
    ".bs-evolve/STOP",
    ".bs-evolve/PAUSE",
    ".bs-evolve/inflight/**",
    ".bs-evolve/corpus",
    ".bs-evolve/corpus/**",
    ".bs-evolve/fleet.yaml",
    ".bs-evolve/fleet/**",
]
SNAPSHOT_PATHS = [".prompts/loop", ".bootstrap", ".bs-evolve", ".gitignore", "reviews"]


def run(cmd: list[str], *, cwd: pathlib.Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, check=check, text=True, capture_output=True)


def repo_root(path: pathlib.Path) -> pathlib.Path:
    return pathlib.Path(run(["git", "-C", str(path), "rev-parse", "--show-toplevel"]).stdout.strip()).resolve()


def now_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def rel_from_cycle_path(path: str) -> pathlib.Path | None:
    parts = pathlib.PurePosixPath(path).parts
    try:
        idx = parts.index("reviews")
    except ValueError:
        return None
    tail = parts[idx + 1:]
    for i, part in enumerate(tail):
        if CYCLE_RE.match(part):
            rest = tail[i:]
            if len(rest) >= 2:
                return pathlib.Path(*rest)
    return None


def cycle_num(path: pathlib.Path) -> int | None:
    m = CYCLE_RE.match(path.name)
    return int(m.group(1)) if m else None


def detect_max_cycle(corpus: pathlib.Path) -> int:
    nums = [n for p in corpus.glob("cycle-*") if p.is_dir() for n in [cycle_num(p)] if n is not None]
    if not nums:
        raise RuntimeError(f"no dogfood cycles found under {corpus}")
    return max(nums)


def count_code_cycles(corpus: pathlib.Path) -> int:
    count = 0
    for cdir in corpus.glob("cycle-*"):
        cy = cdir / "cycle.yaml"
        if not cy.exists():
            continue
        text = cy.read_text(encoding="utf-8", errors="replace")
        if re.search(r"^\s*(?:task_)?type:\s*\"?code\"?\s*$", text, re.M):
            count += 1
    return count


def tree_manifest(root: pathlib.Path) -> dict[str, str]:
    """Small content manifest for rollback self-checks; excludes .git."""
    out: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if ".git" in path.parts:
            continue
        rel = path.relative_to(root).as_posix()
        if path.is_dir():
            out[rel + "/"] = "dir"
        elif path.is_symlink():
            out[rel] = "symlink:" + os.readlink(path)
        elif path.is_file():
            import hashlib
            out[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def process_cwd(pid: str) -> str | None:
    # macOS: lsof exposes cwd for same-user processes. If a candidate codex process
    # cannot be inspected, fail closed at the call site instead of assuming quiet.
    proc = run(["lsof", "-a", "-p", pid, "-d", "cwd", "-Fn"], check=False)
    if proc.returncode != 0:
        return None
    for line in proc.stdout.splitlines():
        if line.startswith("n"):
            return line[1:]
    return None


def is_codex_worker_command(command: str) -> bool:
    # Match Codex CLI/background worker invocations, not the desktop app process
    # named /Applications/Codex.app. The CLI form used by the harness is
    # `codex exec ...`; process argv may omit the target path, so cwd is checked.
    base = pathlib.Path(command.split()[0]).name if command.split() else ""
    return base == "codex" or "codex exec" in command


def target_index_is_clean(target: pathlib.Path) -> bool:
    return run(["git", "-C", str(target), "diff", "--cached", "--quiet"], check=False).returncode == 0


def quiet_preconditions(target: pathlib.Path) -> tuple[bool, list[str]]:
    target = target.resolve()
    loop = target / ".prompts" / "loop"
    reasons: list[str] = []
    if not loop.is_dir():
        reasons.append(f"missing legacy loop dir: {loop}")
    if (loop / "RUNNING.lock").exists():
        reasons.append("legacy .prompts/loop/RUNNING.lock exists")
    inflight = loop / "inflight"
    if inflight.exists() and any(inflight.iterdir()):
        reasons.append("legacy .prompts/loop/inflight is non-empty")
    if not target_index_is_clean(target):
        reasons.append("target git index has pre-staged changes; refusing to mix them into migration commit")
    state_file = loop / "state.json"
    if not state_file.exists():
        reasons.append("legacy .prompts/loop/state.json missing")
    else:
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
            stopped = bool(state.get("stop_reason")) or state.get("mode") in {"stopped", "stop"}
            if not stopped:
                reasons.append("legacy state.json has no stop_reason/equivalent stopped signal")
        except Exception as exc:
            reasons.append(f"legacy state.json is not valid JSON: {exc}")
    ps = run(["ps", "-axo", "pid=,pgid=,command="], check=False)
    if ps.returncode == 0:
        target_s = str(target)
        for line in ps.stdout.splitlines():
            stripped = line.strip()
            parts = stripped.split(None, 2)
            if len(parts) < 3:
                continue
            pid, _pgid, command = parts
            if not is_codex_worker_command(command):
                continue
            cwd = process_cwd(pid)
            cwd_path = pathlib.Path(cwd).resolve() if cwd else None
            cwd_inside_target = False
            if cwd_path is not None:
                try:
                    cwd_path.relative_to(target)
                    cwd_inside_target = True
                except ValueError:
                    cwd_inside_target = False
            if target_s in command or cwd_inside_target:
                reasons.append("live codex process group appears to reference target: " + stripped[:240])
            elif cwd is None:
                reasons.append("unable to inspect cwd for candidate codex process; fail-closed: " + stripped[:240])
    return (not reasons, reasons)


def add_gitignore(root: pathlib.Path) -> None:
    gi = root / ".gitignore"
    existing = gi.read_text(encoding="utf-8") if gi.exists() else ""
    snippet = "\n".join([SNIPPET_BEGIN, *GITIGNORE_PATTERNS, SNIPPET_END, ""])
    if SNIPPET_BEGIN in existing:
        pre = existing.split(SNIPPET_BEGIN, 1)[0].rstrip()
        post = existing.split(SNIPPET_END, 1)[1].lstrip() if SNIPPET_END in existing else ""
        new = (pre + "\n\n" if pre else "") + snippet + ("\n" + post if post else "")
    else:
        new = existing.rstrip() + ("\n\n" if existing.strip() else "") + snippet
    gi.write_text(new, encoding="utf-8")


def rewrite_paths(value: Any, old_loop: pathlib.Path, new_state: pathlib.Path) -> Any:
    if isinstance(value, str):
        return value.replace(str(old_loop), str(new_state)).replace(".prompts/loop", ".bs-evolve")
    if isinstance(value, list):
        return [rewrite_paths(v, old_loop, new_state) for v in value]
    if isinstance(value, dict):
        return {k: rewrite_paths(v, old_loop, new_state) for k, v in value.items()}
    return value


def safe_extract_tar(tar_path: pathlib.Path, dest: pathlib.Path) -> None:
    with tarfile.open(tar_path, "r:gz") as tf:
        for member in tf.getmembers():
            target = (dest / member.name).resolve()
            if not str(target).startswith(str(dest.resolve())):
                raise RuntimeError(f"unsafe tar member: {member.name}")
        tf.extractall(dest)


def create_backup(target: pathlib.Path, backup_dir: pathlib.Path) -> pathlib.Path:
    backup = backup_dir / f"bs-evolve-inplace-{target.name}-{now_slug()}"
    backup.mkdir(parents=True, exist_ok=False)
    manifest = {
        "target": str(target),
        "head": run(["git", "-C", str(target), "rev-parse", "HEAD"], check=False).stdout.strip(),
        "snapshot_paths": SNAPSHOT_PATHS,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "pre_tree_manifest": tree_manifest(target),
    }
    (backup / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    with tarfile.open(backup / "target-snapshot.tar.gz", "w:gz") as tf:
        for rel in SNAPSHOT_PATHS:
            path = target / rel
            if path.exists() or path.is_symlink():
                tf.add(path, arcname=rel)
    return backup


def restore_backup(backup: pathlib.Path) -> None:
    manifest_path = backup / "manifest.json"
    if not manifest_path.exists():
        raise RuntimeError(f"rollback manifest missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    target = pathlib.Path(manifest["target"]).resolve()
    if not target.exists():
        raise RuntimeError(f"rollback target missing: {target}")
    head = manifest.get("head") or ""
    if head:
        run(["git", "-C", str(target), "reset", "--hard", head])
    for rel in SNAPSHOT_PATHS:
        path = target / rel
        if path.exists() or path.is_symlink():
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink()
    tar_path = backup / "target-snapshot.tar.gz"
    if tar_path.exists():
        safe_extract_tar(tar_path, target)
    before = manifest.get("pre_tree_manifest")
    after = tree_manifest(target)
    if before is not None and before != after:
        diff_path = backup / "rollback-manifest-mismatch.json"
        diff_path.write_text(json.dumps({"before": before, "after": after}, indent=2, sort_keys=True), encoding="utf-8")
        raise RuntimeError(f"rollback restored files but tree manifest differs; see {diff_path}")
    print(f"ROLLBACK_OK target={target} backup={backup}")


def copy_legacy_reviews(target: pathlib.Path, reviews_dest: pathlib.Path) -> int:
    count = 0
    for src_root in [target / ".prompts" / "loop" / "reviews", target / "reviews"]:
        if not src_root.exists():
            continue
        for src in src_root.rglob("*"):
            if not src.is_file():
                continue
            rel = rel_from_cycle_path("reviews/" + src.relative_to(src_root).as_posix())
            if rel is None:
                continue
            dst = reviews_dest / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            if not dst.exists():
                shutil.copy2(src, dst)
                count += 1
    return count


def extract_skill_history_reviews(skill: pathlib.Path, reviews_dest: pathlib.Path) -> int:
    log = run(["git", "-C", str(skill), "log", "--format=%H", "--", "harness/evolve-loop/reviews"], check=False)
    if log.returncode != 0:
        raise RuntimeError(log.stderr.strip() or "git log failed while reading skill history")
    count = 0
    for sha in [line.strip() for line in log.stdout.splitlines() if line.strip()]:
        files = run(["git", "-C", str(skill), "ls-tree", "-r", "--name-only", sha, "--", "harness/evolve-loop/reviews"], check=False)
        if files.returncode != 0:
            continue
        for file_rel in files.stdout.splitlines():
            rel = rel_from_cycle_path(file_rel)
            if rel is None:
                continue
            dst = reviews_dest / rel
            if dst.exists():
                continue
            blob = run(["git", "-C", str(skill), "show", f"{sha}:{file_rel}"], check=False)
            if blob.returncode != 0:
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(blob.stdout, encoding="utf-8")
            count += 1
    return count


def write_config(target: pathlib.Path, skill: pathlib.Path, slug: str, max_cycle: int) -> None:
    cfg = {
        "schema_version": 1,
        "project_slug": slug,
        "skill_repo": str(skill),
        "target_repo": "..",
        "state_dir": ".",
        "reviews_root": "./reviews",
        "corpus_dir": "../.prompts/dogfood",
        "mode": "auto",
        "migrated_through_cycle": max_cycle,
    }
    path = target / ".bs-evolve" / "config.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8")


def write_fleet(target: pathlib.Path, slug: str) -> None:
    fleet = target / ".bs-evolve" / "fleet.yaml"
    fleet.parent.mkdir(parents=True, exist_ok=True)
    data = {"projects": {slug: {"target_repo": str(target), "config": str(target / ".bs-evolve" / "config.yaml")}}}
    fleet.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def migrate(args: argparse.Namespace) -> int:
    target = repo_root(pathlib.Path(args.target).resolve())
    skill = repo_root(pathlib.Path(args.skill).resolve())
    backup_dir = pathlib.Path(args.backup_dir).resolve()
    slug = args.slug
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", slug):
        print("migrate-inplace: --slug must be 1-64 chars of letters/digits/_.- and start alnum", file=sys.stderr)
        return 2

    ok, reasons = quiet_preconditions(target)
    corpus = target / ".prompts" / "dogfood"
    try:
        max_cycle = detect_max_cycle(corpus)
    except Exception as exc:
        ok = False
        reasons.append(str(exc))
        max_cycle = -1
    code_cycles = count_code_cycles(corpus) if corpus.exists() else 0
    if code_cycles < 1:
        ok = False
        reasons.append(f"corpus_dir glob found no code cycles under {corpus}")

    if not ok:
        print("migrate-inplace: refusing to migrate; target is not at a quiet boundary", file=sys.stderr)
        for r in reasons:
            print(f"- {r}", file=sys.stderr)
        return 3

    plan = [
        f"target={target}",
        f"skill={skill}",
        f"slug={slug}",
        f"detected_migrated_through_cycle={max_cycle:03d}",
        f"corpus_dir={corpus}",
        f"backup_dir={backup_dir}",
        "will snapshot target touched paths",
        "will create target .bs-evolve/config.yaml,state.json,reviews,STOP,fleet.yaml",
        "will extract historical reviews from skill git history without writing skill repo",
        "will commit target .gitignore and .bs-evolve/reviews only",
    ]
    print("MIGRATE_INPLACE_PLAN")
    for item in plan:
        print(f"- {item}")
    if args.dry_run:
        print("DRY_RUN_OK zero target writes performed")
        return 0

    backup = create_backup(target, backup_dir)
    print(f"BACKUP={backup}")

    bse = target / ".bs-evolve"
    reviews = bse / "reviews"
    reviews.mkdir(parents=True, exist_ok=True)
    add_gitignore(target)
    write_config(target, skill, slug, max_cycle)
    write_fleet(target, slug)

    old_loop = target / ".prompts" / "loop"
    old_state = json.loads((old_loop / "state.json").read_text(encoding="utf-8"))
    new_state = rewrite_paths(old_state, old_loop, bse)
    (bse / "state.json").write_text(json.dumps(new_state, indent=2, ensure_ascii=False), encoding="utf-8")
    (old_loop / "STOP").write_text("migrated to .bs-evolve; legacy wakes must stop here\n", encoding="utf-8")

    copied_legacy = copy_legacy_reviews(target, reviews)
    copied_history = extract_skill_history_reviews(skill, reviews)
    if not any(reviews.glob("cycle-*/closure.yaml")):
        raise RuntimeError("no review closure ledgers were migrated from target or skill history")

    run(["git", "-C", str(target), "add", ".gitignore", ".bs-evolve/reviews"])
    staged = run(["git", "-C", str(target), "diff", "--cached", "--quiet", "--", ".gitignore", ".bs-evolve/reviews"], check=False).returncode != 0
    if staged:
        run(["git", "-C", str(target), "commit", "-m", f"bs-evolve: migrate reviews for {slug}", "--", ".gitignore", ".bs-evolve/reviews"])
        committed = run(["git", "-C", str(target), "rev-parse", "HEAD"]).stdout.strip()
    else:
        committed = "none"

    print(f"MIGRATE_OK target={target}")
    print(f"migrated_through_cycle={max_cycle:03d}")
    print(f"code_cycles={code_cycles}")
    print(f"reviews_copied_from_target={copied_legacy}")
    print(f"reviews_copied_from_skill_history={copied_history}")
    print(f"target_commit={committed}")
    print(f"rollback_with={pathlib.Path(__file__).resolve()} --rollback {backup}")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target")
    ap.add_argument("--skill")
    ap.add_argument("--slug")
    ap.add_argument("--backup-dir")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rollback")
    args = ap.parse_args(argv)
    try:
        if args.rollback:
            restore_backup(pathlib.Path(args.rollback).resolve())
            return 0
        missing = [name for name in ["target", "skill", "slug", "backup_dir"] if not getattr(args, name)]
        if missing:
            ap.error("missing required argument(s): " + ", ".join("--" + m.replace("_", "-") for m in missing))
        return migrate(args)
    except subprocess.CalledProcessError as exc:
        print(f"migrate-inplace: command failed: {' '.join(exc.cmd)}", file=sys.stderr)
        if exc.stdout:
            print(exc.stdout, file=sys.stderr)
        if exc.stderr:
            print(exc.stderr, file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"migrate-inplace: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
