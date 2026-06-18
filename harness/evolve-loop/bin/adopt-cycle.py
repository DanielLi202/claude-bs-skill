#!/usr/bin/env python3
"""Find the latest target corpus cycle eligible for closure adoption.

The lower bound is explicit to avoid re-evaluating old closed history during A2
migration and later target moves.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

CYCLE = re.compile(r"^cycle-(\d+)$")


def cycle_num(path: pathlib.Path) -> int | None:
    m = CYCLE.match(path.name)
    return int(m.group(1)) if m else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus-root", required=True, type=pathlib.Path)
    ap.add_argument("--reviews-root", required=True, type=pathlib.Path)
    ap.add_argument("--min-cycle", required=True, type=int)
    args = ap.parse_args()
    if args.min_cycle < 0:
        print("--min-cycle must be non-negative", file=sys.stderr)
        return 2
    candidates: list[tuple[int, pathlib.Path]] = []
    for d in args.corpus_root.glob("cycle-*"):
        n = cycle_num(d)
        if n is None or n < args.min_cycle:
            continue
        if (args.reviews_root / d.name / "closure.yaml").exists():
            continue
        candidates.append((n, d))
    if not candidates:
        return 10
    n, d = sorted(candidates)[-1]
    print(d)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
