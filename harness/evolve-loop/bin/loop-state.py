#!/usr/bin/env python3
"""bs-evolve-loop state ledger — single JSON at <state_dir>/state.json.

Keeps the loop crash-safe and lets the orchestrator stay a thin re-entrant
process: every turn re-derives "where am I" from disk instead of context memory.

Subcommands:
  init   --target P --skill P [--mode dry-run|auto] [--max N] [--fail-threshold N]
  get    <dotted.key>                    # prints value (str raw, else JSON); empty if absent
  set    <dotted.key> <value>            # value JSON-parsed, else stored as string
  begin-iteration                        # ++iteration, mkdir iter-NNN/, prints N
  append-history '<json-object>'         # append to history[]
  should-stop                            # prints reason + exit 10 to STOP, else exit 0

State dir from --state-dir or $BS_LOOP_STATE_DIR.
Stop reasons: stop_file | backlog_exhausted | max_iterations | consecutive_failures
"""
import json, os, sys, pathlib


def _state_dir():
    argv = sys.argv
    sd = argv[argv.index("--state-dir") + 1] if "--state-dir" in argv else None
    sd = sd or os.environ.get("BS_LOOP_STATE_DIR")
    if not sd:
        print("state-dir required (--state-dir or $BS_LOOP_STATE_DIR)", file=sys.stderr)
        sys.exit(2)
    p = pathlib.Path(sd)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _load(p):
    f = p / "state.json"
    return json.loads(f.read_text()) if f.exists() else {}


def _save(p, s):
    (p / "state.json").write_text(json.dumps(s, indent=2, ensure_ascii=False))


def _dotget(s, k):
    cur = s
    for part in k.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _dotset(s, k, v):
    cur = s
    parts = k.split(".")
    for part in parts[:-1]:
        cur = cur.setdefault(part, {})
    cur[parts[-1]] = v


def main():
    args = list(sys.argv[1:])
    if "--state-dir" in args:
        i = args.index("--state-dir")
        del args[i:i + 2]
    if not args:
        print("subcommand required", file=sys.stderr)
        sys.exit(2)
    cmd, rest = args[0], args[1:]
    p = _state_dir()
    s = _load(p)

    def opt(name, default=None):
        return rest[rest.index(name) + 1] if name in rest else default

    if cmd == "init":
        if not s:
            s = {
                "loop": "bs-evolve-loop",
                "target_repo": opt("--target"),
                "skill_repo": opt("--skill"),
                "mode": opt("--mode", "dry-run"),
                "max_iterations": int(opt("--max", "5")),
                "fail_threshold": int(opt("--fail-threshold", "2")),
                "iteration": 0,
                "consecutive_failures": 0,
                "anchor": {},
                "stop_reason": None,
                "history": [],
            }
            _save(p, s)
            print("initialized")
        else:
            print("exists")
    elif cmd == "get":
        v = _dotget(s, rest[0])
        print("" if v is None else (v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)))
    elif cmd == "set":
        k, raw = rest[0], rest[1]
        try:
            v = json.loads(raw)
        except Exception:
            v = raw
        _dotset(s, k, v)
        _save(p, s)
        print("ok")
    elif cmd == "begin-iteration":
        s["iteration"] = int(s.get("iteration", 0)) + 1
        _save(p, s)
        (p / f"iter-{s['iteration']:03d}").mkdir(exist_ok=True)
        print(s["iteration"])
    elif cmd == "append-history":
        s.setdefault("history", []).append(json.loads(rest[0]))
        _save(p, s)
        print("ok")
    elif cmd == "should-stop":
        reason = None
        if (p / "STOP").exists():
            reason = "stop_file"
        elif s.get("stop_reason"):
            reason = s["stop_reason"]
        elif int(s.get("iteration", 0)) >= int(s.get("max_iterations", 5)):
            reason = "max_iterations"
        elif int(s.get("consecutive_failures", 0)) >= int(s.get("fail_threshold", 2)):
            reason = "consecutive_failures"
        if reason:
            print(reason)
            sys.exit(10)
        sys.exit(0)
    else:
        print(f"unknown subcommand {cmd}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
