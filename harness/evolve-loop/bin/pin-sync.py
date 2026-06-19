#!/usr/bin/env python3
"""Generic committed target-side bs contract pin sync for bs-evolve Step 0."""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import subprocess
import sys

import yaml

SCRIPT = pathlib.Path(__file__).resolve()
SKILL_REPO = SCRIPT.parents[3]
sys.path.insert(0, str(SKILL_REPO))
from lib import binding  # noqa: E402


def run(cmd: list[str], *, cwd: pathlib.Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, check=check, text=True, capture_output=True)


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dirty(target: pathlib.Path) -> bool:
    return bool(run(["git", "status", "--porcelain"], cwd=target).stdout.strip())


def update_bootstrap_yaml(path: pathlib.Path, digest: str) -> None:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    if not isinstance(data, dict):
        raise SystemExit("pin-sync failed: .bootstrap.yaml must be a mapping")
    contract = data.setdefault("contract", {})
    if not isinstance(contract, dict):
        raise SystemExit("pin-sync failed: .bootstrap.yaml contract must be a mapping")
    contract["source_sha256"] = digest
    contract.setdefault("sha256_path", ".bootstrap/contract.sha256")
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True, type=pathlib.Path)
    ap.add_argument("--skill", required=True, type=pathlib.Path)
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--push", action="store_true")
    args = ap.parse_args()
    target = args.target.resolve()
    skill = args.skill.resolve()
    contract = skill / "contract.md"
    if not contract.exists():
        print("pin-sync failed: skill contract.md missing", file=sys.stderr)
        return 2
    boot_yaml = target / ".bootstrap.yaml"
    if not boot_yaml.exists():
        print("pin-sync failed: .bootstrap.yaml missing", file=sys.stderr)
        return 2
    data = yaml.safe_load(boot_yaml.read_text(encoding="utf-8")) or {}
    sha_path = ((data.get("contract") or {}).get("sha256_path") or ".bootstrap/contract.sha256")
    pin = target / sha_path
    new = sha(contract)
    old = pin.read_text(encoding="utf-8").strip() if pin.exists() else ""
    old_yaml = str((data.get("contract") or {}).get("source_sha256") or "")
    if old == new and old_yaml == new:
        print("pin-sync: already current")
        return 0
    if dirty(target):
        print("pin-sync failed: target tree dirty before pin refresh", file=sys.stderr)
        return 3
    pin.parent.mkdir(parents=True, exist_ok=True)
    pin.write_text(new + "\n", encoding="utf-8")
    update_bootstrap_yaml(boot_yaml, new)
    try:
        binding.validate(target, yaml.safe_load(boot_yaml.read_text(encoding="utf-8")) or {}, contract)
    except Exception as exc:
        print(f"pin-sync failed: binding validation failed: {exc}", file=sys.stderr)
        return 4
    if args.commit:
        run(["git", "add", ".bootstrap.yaml", sha_path], cwd=target)
        diff = run(["git", "diff", "--cached", "--quiet"], cwd=target, check=False)
        if diff.returncode != 0:
            run(["git", "commit", "-m", "bs-evolve: refresh bs contract pin"], cwd=target)
        if dirty(target):
            print("pin-sync failed: target dirty after commit", file=sys.stderr)
            return 5
        if args.push:
            run(["git", "push", "origin", "HEAD"], cwd=target)
    print(f"pin-sync: updated {old or '<missing>'} -> {new}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
