#!/usr/bin/env python3
"""bs-evolve-loop closure ledger — one closure.yaml per cycle, committed to git.

The closure ledger makes per-iteration self-closure STRUCTURAL: an iteration is
"advance the newest incomplete closure to done"; a new /bs cycle may only start
when no incomplete closure exists. Leftover work is impossible by construction —
it is an unclosed ledger, and the next iteration must resume it (stage derived
from disk, not from context memory).

File: <reviews>/<cycle-NNN>/closure.yaml
Stages (in order):  r1 -> r2 -> skill_release -> remediation -> closed

Usage:
  closure.py --dir <cycle-review-dir> init --cycle cycle-018
  closure.py --dir D get [key]
  closure.py --dir D set <key> <value>        # value JSON-parsed, else string
  closure.py --dir D next                     # prints next incomplete stage | done
  closure.py --dir D check                    # exit 0 closed | 10 incomplete (prints next)
  closure.py --reviews-root R newest-open     # prints dir of newest incomplete closure | nothing
Exit: 0 ok | 10 incomplete/open-found-none(check/newest-open semantics below) | 2 usage
"""
import json
import pathlib
import sys
from datetime import datetime, timezone

import yaml

STAGES = ["r1", "r2", "skill_release", "remediation"]


def now_z():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load(d):
    f = d / "closure.yaml"
    if not f.exists():
        return None
    return yaml.safe_load(f.read_text()) or {}


def save(d, c):
    c["updated_at"] = now_z()
    (d / "closure.yaml").write_text(yaml.safe_dump(c, sort_keys=False, allow_unicode=True))


def next_stage(c):
    for s in STAGES:
        if not c.get(s):
            return s
    if not c.get("closed"):
        return "close"
    return "done"


def main():
    args = sys.argv[1:]

    def opt(name):
        if name in args:
            i = args.index(name)
            v = args[i + 1]
            del args[i:i + 2]
            return v
        return None

    dir_ = opt("--dir")
    reviews_root = opt("--reviews-root")
    if not args:
        print("subcommand required", file=sys.stderr)
        sys.exit(2)
    cmd, rest = args[0], args[1:]

    if cmd == "newest-open":
        root = pathlib.Path(reviews_root or ".")
        open_dirs = []
        for f in sorted(root.glob("cycle-*/closure.yaml")):
            c = yaml.safe_load(f.read_text()) or {}
            if not c.get("closed"):
                open_dirs.append(f.parent)
        if open_dirs:
            print(open_dirs[-1])
            sys.exit(0)
        sys.exit(10)

    if not dir_:
        print("--dir required", file=sys.stderr)
        sys.exit(2)
    d = pathlib.Path(dir_)
    d.mkdir(parents=True, exist_ok=True)

    if cmd == "init":
        cyc = rest[rest.index("--cycle") + 1] if "--cycle" in rest else d.name
        if load(d) is not None:
            print("exists")
            return
        save(d, {
            "cycle": cyc,
            "r1": None,                # "done" when r1.md written+committed
            "r2": None,                # "done" when r2.md written+committed
            "skill_release": None,     # release tag or no-release sentinel once deterministic r2 items are handled
            "skill_release_items_done": {},  # id -> commit for Stage 4 crash-safe self-recovery
            "covered_upstream": [],     # deterministic r2 items already covered by a concurrent release
            "remediation": None,       # merge/amendment commit on the target repo
            "escalated_to_human": [],  # non-deterministic items, surfaced in the report
            "closed": False,
        })
        print("initialized")
    elif cmd == "get":
        c = load(d) or {}
        if rest:
            v = c.get(rest[0])
            print("" if v is None else (v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)))
        else:
            print(yaml.safe_dump(c, sort_keys=False, allow_unicode=True))
    elif cmd == "set":
        c = load(d)
        if c is None:
            print("closure.yaml missing; run init first", file=sys.stderr)
            sys.exit(2)
        key, raw = rest[0], rest[1]
        try:
            val = json.loads(raw)
        except Exception:
            val = raw
        c[key] = val
        save(d, c)
        print("ok")
    elif cmd == "next":
        c = load(d)
        print("uninitialized" if c is None else next_stage(c))
    elif cmd == "check":
        c = load(d)
        if c is None:
            print("uninitialized")
            sys.exit(10)
        s = next_stage(c)
        print(s)
        sys.exit(0 if s == "done" else 10)
    else:
        print(f"unknown subcommand {cmd}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
