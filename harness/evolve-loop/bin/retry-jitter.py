#!/usr/bin/env python3
"""Deterministic per-project retry jitter for lock-held wakeups."""
from __future__ import annotations

import argparse
import hashlib


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True)
    ap.add_argument("--base", type=int, default=1800)
    ap.add_argument("--spread", type=int, default=420)
    args = ap.parse_args()
    h = int(hashlib.sha256(args.slug.encode()).hexdigest()[:8], 16)
    print(args.base + (h % max(args.spread, 1)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
