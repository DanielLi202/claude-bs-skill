#!/usr/bin/env python3
"""Validate bs step_events.jsonl append-only pairing semantics."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib.events import EventError, _validate_event_shape  # noqa: E402

TERMINAL_EVENTS = {"completed", "failed"}
ISO_Z_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")


def fail(rule: str, step: object, attempt: object, message: str) -> int:
    print(f"ERROR: {rule} step={step!r} attempt={attempt!r}: {message}", file=sys.stderr)
    return 1


def event_key(obj: dict) -> tuple[object, object]:
    return obj.get("step"), obj.get("attempt", 0)


def canonical_time(obj: dict) -> object:
    return obj.get("recorded_at", obj.get("ts"))


def time_key(ts: str) -> tuple[str, str]:
    body = ts[:-1]
    if "." in body:
        base, frac = body.split(".", 1)
    else:
        base, frac = body, ""
    return base, frac.ljust(12, "0")


def validate_time_fields(obj: dict, lineno: int, last_ts: str | None) -> tuple[int | None, str | None]:
    step, attempt = event_key(obj)
    ts = canonical_time(obj)
    if not isinstance(ts, str) or not ISO_Z_RE.match(ts):
        return fail("ts_missing_or_invalid", step, attempt, f"line {lineno} recorded_at/ts={ts!r} is missing or non-canonical"), last_ts
    occurred = obj.get("occurred_at")
    if occurred is not None and (not isinstance(occurred, str) or not ISO_Z_RE.match(occurred)):
        return fail("ts_missing_or_invalid", step, attempt, f"line {lineno} occurred_at={occurred!r} is non-canonical"), last_ts
    recorded = obj.get("recorded_at")
    if isinstance(recorded, str) and isinstance(occurred, str) and time_key(occurred) > time_key(recorded):
        return fail("occurred_after_recorded", step, attempt, f"line {lineno} occurred_at={occurred!r} after recorded_at={recorded!r}"), last_ts
    if last_ts is not None and time_key(ts) < time_key(last_ts):
        return fail("ts_not_monotonic", step, attempt, f"line {lineno} recorded_at/ts={ts!r} before previous recorded_at/ts={last_ts!r}"), last_ts
    return None, ts


def validate(path: str, allow_open_current: str | None = None) -> int:
    open_attempts: dict[tuple[object, object], int] = {}
    states: dict[tuple[object, object], str] = {}
    orphan_terminals: dict[int, tuple[tuple[object, object], str, str]] = {}
    last_ts: str | None = None
    count = 0

    try:
        handle = open(path, "r", encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: open_failed step=None attempt=None: {exc}", file=sys.stderr)
        return 1

    with handle:
        for lineno, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            raw_line = line.rstrip("\n")
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                print(f"ERROR: invalid_json step=None attempt=None: line {lineno}: {exc}", file=sys.stderr)
                return 1
            if not isinstance(obj, dict):
                print(f"ERROR: invalid_json step=None attempt=None: line {lineno}: event must be an object", file=sys.stderr)
                return 1
            count += 1

            failed, last_ts = validate_time_fields(obj, lineno, last_ts)
            if failed is not None:
                return failed
            try:
                _validate_event_shape(obj, lineno)
            except EventError as exc:
                return fail("schema_invalid", obj.get("step", obj.get("target_step")), obj.get("attempt", obj.get("target_attempt", 0)), str(exc))

            step, attempt = event_key(obj)
            event = obj.get("event")
            key = (step, attempt)
            if event == "started":
                if key in open_attempts:
                    return fail("duplicate_started", step, attempt, f"line {lineno} nested start before terminal; prior start line {open_attempts[key]}")
                if states.get(key) in TERMINAL_EVENTS:
                    return fail("started_after_terminal", step, attempt, f"line {lineno} started after terminal event")
                open_attempts[key] = lineno
            elif event in TERMINAL_EVENTS:
                if key not in open_attempts:
                    if states.get(key) in TERMINAL_EVENTS:
                        return fail("duplicate_terminal", step, attempt, f"line {lineno} event={event!r} follows prior terminal for same attempt")
                    orphan_terminals[lineno] = (key, event, hashlib.sha256(raw_line.encode("utf-8")).hexdigest())
                    continue
                del open_attempts[key]
                states[key] = event
            elif event == "repair":
                if obj.get("repair_kind") != "missing_started":
                    return fail("unsupported_repair", obj.get("target_step"), obj.get("target_attempt", 0), f"line {lineno} repair_kind={obj.get('repair_kind')!r}")
                target_line = obj.get("target_line")
                target_step = obj.get("target_step")
                target_attempt = obj.get("target_attempt", 0)
                orphan = orphan_terminals.pop(target_line, None)
                if orphan is None:
                    return fail("repair_target_missing", target_step, target_attempt, f"line {lineno} target_line={target_line!r} is not an unrepaired terminal_without_started")
                orphan_key, terminal_event, target_hash = orphan
                if orphan_key != (target_step, target_attempt):
                    return fail("repair_target_mismatch", target_step, target_attempt, f"line {lineno} target does not match line {target_line}")
                if obj.get("target_event_hash") != target_hash:
                    return fail("repair_hash_mismatch", target_step, target_attempt, f"line {lineno} target_event_hash does not match line {target_line}")
                if states.get(orphan_key) in TERMINAL_EVENTS:
                    return fail("repair_duplicate_terminal", target_step, target_attempt, f"line {lineno} target attempt already has a terminal event")
                states[orphan_key] = terminal_event
            else:
                return fail("unknown_event", step, attempt, f"line {lineno} event={event!r}")

    if orphan_terminals:
        lineno, (key, event, _target_hash) = next(iter(orphan_terminals.items()))
        step, attempt = key
        return fail("terminal_without_started", step, attempt, f"line {lineno} event={event!r} has no matching prior started or repair")

    if open_attempts:
        if allow_open_current is not None:
            allowed = [(key, line) for key, line in open_attempts.items() if key[0] == allow_open_current]
            if len(open_attempts) == 1 and len(allowed) == 1:
                print(f"OK: {count} events validated (allowed open {allow_open_current})")
                return 0
        (step, attempt), lineno = next(iter(open_attempts.items()))
        return fail("unclosed_started", step, attempt, f"started at line {lineno} has no terminal event")

    print(f"OK: {count} events validated")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path")
    parser.add_argument("--allow-open-current", default=None, help="allow exactly one open started pair for this step")
    args = parser.parse_args(argv[1:])
    return validate(args.path, allow_open_current=args.allow_open_current)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
