#!/usr/bin/env python3
"""Install/check target-side .bs-evolve git hygiene rules."""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

SNIPPET_BEGIN = "# >>> bs-evolve local state >>>"
SNIPPET_END = "# <<< bs-evolve local state <<<"
PATTERNS = [
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


def repo_root(path: pathlib.Path) -> pathlib.Path:
    return pathlib.Path(subprocess.check_output(["git", "-C", str(path), "rev-parse", "--show-toplevel"], text=True).strip())


def snippet() -> str:
    return "\n".join([SNIPPET_BEGIN, *PATTERNS, SNIPPET_END, ""])


def install(root: pathlib.Path) -> None:
    gi = root / ".gitignore"
    existing = gi.read_text(encoding="utf-8") if gi.exists() else ""
    if SNIPPET_BEGIN in existing:
        pre = existing.split(SNIPPET_BEGIN, 1)[0].rstrip()
        post = existing.split(SNIPPET_END, 1)[1].lstrip() if SNIPPET_END in existing else ""
        new = (pre + "\n\n" if pre else "") + snippet() + ("\n" + post if post else "")
    else:
        new = existing.rstrip() + ("\n\n" if existing.strip() else "") + snippet()
    gi.write_text(new, encoding="utf-8")


def check(root: pathlib.Path) -> int:
    failures: list[str] = []
    for rel in PATTERNS:
        probe = rel.replace("**", "probe").replace("*", "probe")
        rc = subprocess.run(["git", "-C", str(root), "check-ignore", "--no-index", "-q", probe]).returncode
        if rc != 0:
            failures.append(f"not ignored: {rel}")
    rc = subprocess.run(["git", "-C", str(root), "check-ignore", "--no-index", "-q", ".bs-evolve/reviews/cycle-001/closure.yaml"]).returncode
    if rc == 0:
        failures.append("reviews ledger is ignored but must be trackable")
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print("bs-evolve gitignore OK")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True, type=pathlib.Path)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    root = repo_root(args.target)
    if args.check:
        return check(root)
    install(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
