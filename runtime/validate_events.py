#!/usr/bin/env python3
"""Validate bs step_events.jsonl append-only pairing semantics."""
from __future__ import annotations

import json
import sys


TERMINAL_EVENTS = {"completed", "failed"}


def fail(rule: str, step: object, attempt: object, message: str) -> int:
    print(f"ERROR: {rule} step={step!r} attempt={attempt!r}: {message}", file=sys.stderr)
    return 1


def event_key(obj: dict) -> tuple[object, object]:
    return obj.get("step"), obj.get("attempt", 0)


def validate(path: str) -> int:
    open_attempts: dict[tuple[object, object], int] = {}
    last_ts: object = None
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
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                print(f"ERROR: invalid_json step=None attempt=None: line {lineno}: {exc}", file=sys.stderr)
                return 1
            count += 1

            step, attempt = event_key(obj)
            ts = obj.get("ts")
            if last_ts is not None and ts < last_ts:
                return fail("ts_not_monotonic", step, attempt, f"line {lineno} ts={ts!r} before previous ts={last_ts!r}")
            last_ts = ts

            event = obj.get("event")
            key = (step, attempt)
            if event == "started":
                if key in open_attempts:
                    return fail("duplicate_started", step, attempt, f"line {lineno} nested start before terminal; prior start line {open_attempts[key]}")
                open_attempts[key] = lineno
            elif event in TERMINAL_EVENTS:
                if key not in open_attempts:
                    return fail("terminal_without_started", step, attempt, f"line {lineno} event={event!r} has no matching prior started")
                del open_attempts[key]
            else:
                return fail("unknown_event", step, attempt, f"line {lineno} event={event!r}")

    if open_attempts:
        (step, attempt), lineno = next(iter(open_attempts.items()))
        return fail("unclosed_started", step, attempt, f"started at line {lineno} has no terminal event")

    print(f"OK: {count} events validated")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python3 validate_events.py <path/to/step_events.jsonl>", file=sys.stderr)
        return 2
    return validate(argv[1])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
