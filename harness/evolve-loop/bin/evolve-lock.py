#!/usr/bin/env python3
"""Atomic lock helper for bs-evolve project and skill locks.

A lock is a JSON file created with O_CREAT|O_EXCL.  The owner token is written
inside the lock file and must be presented for heartbeat/release.  Stale project
locks fail closed when an inflight record exists; stale empty locks may be taken
over atomically.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import pathlib
import secrets
import socket
import sys
import time
from datetime import datetime, timezone
from contextlib import contextmanager
from typing import Any



@contextmanager
def lock_guard(path: pathlib.Path):
    guard = path.with_name(path.name + ".guard")
    guard.parent.mkdir(parents=True, exist_ok=True)
    with guard.open("a+", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

def now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def live_pgid(pgid: Any) -> bool:
    try:
        n = int(pgid)
    except Exception:
        return False
    if n <= 1:
        return False
    try:
        os.kill(-n, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def inflight_records(inflight_dir: pathlib.Path | None) -> list[pathlib.Path]:
    if not inflight_dir or not inflight_dir.exists():
        return []
    return sorted(p for p in inflight_dir.glob("*.json") if p.is_file())


def has_live_or_unresolved_inflight(inflight_dir: pathlib.Path | None) -> bool:
    records = inflight_records(inflight_dir)
    if not records:
        return False
    # Any durable inflight record keeps stale project locks fail-closed.  If a
    # pgid is present and alive this is definitely live; otherwise the record is
    # unresolved crash state that must be resumed, not overwritten by a new stage.
    for p in records:
        data = read_json(p)
        if live_pgid(data.get("pgid") or data.get("process_group_id")):
            return True
    return True


def write_lock_atomic(path: pathlib.Path, payload: dict[str, Any]) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        fd = os.open(str(path), flags, 0o600)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(payload, f, sort_keys=True)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    return True


def acquire(path: pathlib.Path, *, owner: str, stale_sec: int, inflight_dir: pathlib.Path | None) -> int:
    with lock_guard(path):
        token = secrets.token_urlsafe(24)
        payload = {
            "owner_token": token,
            "owner": owner,
            "pid": os.getpid(),
            "host": socket.gethostname(),
            "started_at": now_z(),
            "heartbeat_at": now_z(),
        }
        if write_lock_atomic(path, payload):
            print(json.dumps({"status": "acquired", "token": token, "lock": str(path)}, sort_keys=True))
            return 0

        if not path.exists():
            print(json.dumps({"status": "race_lost", "lock": str(path)}, sort_keys=True))
            return 11

        age = max(0, int(time.time() - path.stat().st_mtime))
        data = read_json(path)
        if age < stale_sec:
            print(json.dumps({"status": "locked", "age_sec": age, "owner": data.get("owner"), "lock": str(path)}, sort_keys=True))
            return 11

        if has_live_or_unresolved_inflight(inflight_dir):
            print(json.dumps({"status": "locked", "reason": "stale_with_inflight", "age_sec": age, "lock": str(path)}, sort_keys=True))
            return 11

        stale_name = path.with_name(path.name + f".stale-{int(time.time())}-{os.getpid()}")
        try:
            os.replace(path, stale_name)
        except FileNotFoundError:
            pass
        except OSError as exc:
            print(json.dumps({"status": "locked", "reason": f"stale_replace_failed:{exc}", "lock": str(path)}, sort_keys=True))
            return 11
        if write_lock_atomic(path, payload):
            print(json.dumps({"status": "acquired", "token": token, "lock": str(path), "replaced_stale": str(stale_name)}, sort_keys=True))
            return 0
        print(json.dumps({"status": "race_lost", "lock": str(path)}, sort_keys=True))
        return 11

def token_matches(path: pathlib.Path, token: str) -> tuple[bool, dict[str, Any]]:
    data = read_json(path)
    return bool(token) and data.get("owner_token") == token, data


def heartbeat(path: pathlib.Path, token: str) -> int:
    with lock_guard(path):
        ok, data = token_matches(path, token)
        if not ok:
            print(json.dumps({"status": "token_mismatch", "lock": str(path)}, sort_keys=True))
            return 12
        data["heartbeat_at"] = now_z()
        tmp = path.with_name(path.name + f".tmp-{os.getpid()}")
        tmp.write_text(json.dumps(data, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, path)
        print(json.dumps({"status": "heartbeat", "lock": str(path)}, sort_keys=True))
        return 0

def release(path: pathlib.Path, token: str) -> int:
    with lock_guard(path):
        if not path.exists():
            print(json.dumps({"status": "missing", "lock": str(path)}, sort_keys=True))
            return 0
        ok, _ = token_matches(path, token)
        if not ok:
            print(json.dumps({"status": "token_mismatch", "lock": str(path)}, sort_keys=True))
            return 12
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        print(json.dumps({"status": "released", "lock": str(path)}, sort_keys=True))
        return 0

def status(path: pathlib.Path) -> int:
    if not path.exists():
        print(json.dumps({"status": "unlocked", "lock": str(path)}, sort_keys=True))
        return 0
    data = read_json(path)
    print(json.dumps({"status": "locked", "lock": str(path), "owner": data.get("owner"), "heartbeat_at": data.get("heartbeat_at")}, sort_keys=True))
    return 11


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["acquire", "heartbeat", "release", "status"])
    ap.add_argument("--lock-file", required=True, type=pathlib.Path)
    ap.add_argument("--owner", default=f"pid:{os.getpid()}")
    ap.add_argument("--token", default=os.environ.get("BS_LOOP_LOCK_TOKEN", ""))
    ap.add_argument("--stale-sec", type=int, default=int(os.environ.get("BS_LOOP_LOCK_STALE_SEC", "7200")))
    ap.add_argument("--inflight-dir", type=pathlib.Path)
    args = ap.parse_args()

    lock = args.lock_file.resolve()
    if args.command == "acquire":
        return acquire(lock, owner=args.owner, stale_sec=args.stale_sec, inflight_dir=args.inflight_dir)
    if args.command == "heartbeat":
        return heartbeat(lock, args.token)
    if args.command == "release":
        return release(lock, args.token)
    return status(lock)


if __name__ == "__main__":
    raise SystemExit(main())
