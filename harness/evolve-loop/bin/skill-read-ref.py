#!/usr/bin/env python3
"""Read a skill file from a pinned git commit/ref without touching the worktree."""
from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys

SAFE_PATH = re.compile(r"^[A-Za-z0-9_./-]+$")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill", required=True, type=pathlib.Path)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--path", required=True)
    args = ap.parse_args()
    rel = args.path.strip("/")
    if not rel or ".." in pathlib.PurePosixPath(rel).parts or not SAFE_PATH.match(rel):
        print("skill-read-ref: unsafe path", file=sys.stderr)
        return 2
    skill = args.skill.resolve()
    commit = subprocess.run(["git", "-C", str(skill), "rev-parse", "--verify", f"{args.ref}^{{commit}}"], text=True, capture_output=True)
    if commit.returncode != 0:
        print("skill-read-ref: ref is not a commit", file=sys.stderr)
        return 2
    show = subprocess.run(["git", "-C", str(skill), "show", f"{commit.stdout.strip()}:{rel}"], text=True, capture_output=True)
    if show.returncode != 0:
        print(show.stderr, file=sys.stderr, end="")
        return 1
    print(show.stdout, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
