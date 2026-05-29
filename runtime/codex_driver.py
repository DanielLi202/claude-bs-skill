#!/usr/bin/env python3
"""Codex app-server driver for bs v1.3.4.

Runs one frozen outcome capsule through `codex app-server --listen stdio://`
using `/goal @<outcome.md>`. Captures JSON-RPC requests, raw server output,
stderr, and driver metadata. Launch/handshake transient failures retry; fatal
protocol/auth/capability errors fail fast. No `codex exec` fallback exists.
"""
from __future__ import annotations

import argparse
import json
import os
import select
import subprocess
import sys
import time
from pathlib import Path
from typing import TextIO


class LaunchTransient(Exception):
    """Retryable app-server launch/handshake failure."""


class LaunchFatal(Exception):
    """Deterministic app-server launch/handshake failure."""


def write_jsonl(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n")


def detect_inferred_completion_signal(obj: dict) -> str | None:
    """Return a reason when an app-server notification can arm inference."""
    method = obj.get("method")
    params = obj.get("params") or {}
    if method == "item/completed":
        item = params.get("item") or {}
        phase = item.get("phase") or params.get("phase")
        item_type = item.get("type") or params.get("type")
        role = item.get("role") or params.get("role")
        if phase == "final_answer" or (item_type in {"message", "assistant_message"} and role in {"assistant", None}):
            return "item_completed_final_answer"
    if method == "thread/status/changed":
        status = params.get("status") or (params.get("thread") or {}).get("status")
        if isinstance(status, dict):
            status = status.get("type")
        if status in {"idle", "completed"}:
            return f"thread_status_{status}"
    return None


def emit_meta(meta: TextIO, **obj: object) -> None:
    obj.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    meta.write(json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n")
    meta.flush()


def send(proc: subprocess.Popen, rpc: TextIO, i: int, method: str, params: dict) -> None:
    req = {"jsonrpc": "2.0", "id": i, "method": method, "params": params}
    line = json.dumps(req, ensure_ascii=False)
    rpc.write(line + "\n")
    rpc.flush()
    assert proc.stdin is not None
    try:
        proc.stdin.write(line + "\n")
        proc.stdin.flush()
    except (BrokenPipeError, OSError) as exc:
        raise LaunchTransient(f"app-server stdin unavailable during {method}: {exc}") from exc


def classify_rpc_error(resp: dict) -> LaunchFatal:
    err = resp.get("error")
    if isinstance(err, dict):
        msg = err.get("message") or json.dumps(err, ensure_ascii=False, sort_keys=True)
    else:
        msg = str(err)
    return LaunchFatal(msg)


def read_response(proc: subprocess.Popen, raw: TextIO, err: TextIO, target: int, timeout: int) -> dict:
    start = time.monotonic()
    assert proc.stdout is not None and proc.stderr is not None
    while time.monotonic() - start < timeout:
        if proc.poll() is not None:
            raise LaunchTransient(f"app-server exited before response id={target} (exit={proc.returncode})")
        ready, _, _ = select.select([proc.stdout, proc.stderr], [], [], 0.5)
        for stream in ready:
            line = stream.readline()
            if not line:
                continue
            if stream is proc.stdout:
                raw.write(line)
                raw.flush()
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("id") == target:
                    if "error" in obj:
                        raise classify_rpc_error(obj)
                    return obj
            else:
                err.write(line)
                err.flush()
    raise LaunchTransient(f"timed out waiting for response id={target}")


def kill_proc(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    try:
        proc.kill()
    except Exception:
        return
    try:
        proc.wait(timeout=2)
    except Exception:
        pass


def wait_for_turn_completion(
    proc: subprocess.Popen,
    raw: TextIO,
    err: TextIO,
    meta: TextIO,
    timeout_sec: int,
    heartbeat_sec: int,
    inferred_completion_sec: int,
    idle_timeout_sec: int,
) -> int:
    start = time.monotonic()
    last_stdout_activity = start
    last_heartbeat = start
    inferred_armed_at: float | None = None
    inferred_reason: str | None = None
    assert proc.stdout is not None and proc.stderr is not None

    while True:
        now = time.monotonic()
        if now - start > timeout_sec:
            emit_meta(meta, event="turn_total_timeout", timeout_sec=timeout_sec)
            kill_proc(proc)
            return 2
        if idle_timeout_sec > 0 and now - last_stdout_activity > idle_timeout_sec:
            emit_meta(meta, event="turn_idle_timeout", idle_timeout_sec=idle_timeout_sec)
            kill_proc(proc)
            return 2
        if heartbeat_sec > 0 and now - last_heartbeat >= heartbeat_sec:
            emit_meta(meta, event="heartbeat", idle_sec=round(now - last_stdout_activity, 3))
            last_heartbeat = now
        if inferred_armed_at is not None and now - inferred_armed_at >= inferred_completion_sec:
            emit_meta(
                meta,
                event="turn_completed_inferred",
                inferred_completion=True,
                reason=inferred_reason,
                armed_for_sec=inferred_completion_sec,
            )
            return 0

        ready, _, _ = select.select([proc.stdout, proc.stderr], [], [], 0.25)
        if not ready:
            continue
        for stream in ready:
            line = stream.readline()
            if not line:
                continue
            if stream is proc.stdout:
                last_stdout_activity = time.monotonic()
                raw.write(line)
                raw.flush()
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("method") == "turn/completed":
                    status = (obj.get("params") or {}).get("turn", {}).get("status")
                    emit_meta(meta, event="turn_completed_explicit", status=status)
                    return 0 if status == "completed" else 2
                reason = detect_inferred_completion_signal(obj)
                if reason and inferred_armed_at is None:
                    inferred_armed_at = time.monotonic()
                    inferred_reason = reason
                    emit_meta(meta, event="inferred_completion_armed", reason=reason, delay_sec=inferred_completion_sec)
            else:
                err.write(line)
                err.flush()


def build_goal_input(outcome_file: Path) -> str:
    return f"/goal @{outcome_file}"


def resolve_codex_bin(args: argparse.Namespace) -> str:
    if args.codex_bin:
        return args.codex_bin
    if os.environ.get("BS_TEST_FAKE_CODEX") == "1":
        return os.environ.get("CODEX_BIN", "codex")
    return "codex"


def launch_and_handshake(args: argparse.Namespace, raw: TextIO, rpc: TextIO, err: TextIO, meta: TextIO) -> tuple[subprocess.Popen, str]:
    cwd = Path(args.cwd).resolve()
    outcome_file = Path(args.outcome_file).resolve()
    proc: subprocess.Popen | None = None
    codex_bin = resolve_codex_bin(args)
    try:
        proc = subprocess.Popen(
            [codex_bin, "app-server", "--listen", "stdio://"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=str(cwd),
        )
        send(proc, rpc, 1, "initialize", {"clientInfo": {"name": "bs-codex-driver", "version": "0.4"}, "capabilities": {"experimentalApi": True}})
        read_response(proc, raw, err, 1, args.handshake_timeout_sec)

        thread_params = {"cwd": str(cwd), "approvalPolicy": "never", "sandbox": "workspace-write", "ephemeral": True}
        if args.model:
            thread_params["model"] = args.model
        send(proc, rpc, 2, "thread/start", thread_params)
        thread = read_response(proc, raw, err, 2, args.handshake_timeout_sec)
        thread_id = thread["result"]["thread"]["id"]

        send(proc, rpc, 3, "turn/start", {
            "threadId": thread_id,
            "input": [{"type": "text", "text": build_goal_input(outcome_file)}],
            "cwd": str(cwd),
            "approvalPolicy": "never",
            "sandboxPolicy": {"type": "workspaceWrite", "writableRoots": [str(cwd)], "networkAccess": False},
            "effort": args.effort,
        })
        read_response(proc, raw, err, 3, args.handshake_timeout_sec)
        return proc, thread_id
    except LaunchFatal:
        kill_proc(proc)
        raise
    except LaunchTransient:
        kill_proc(proc)
        raise
    except OSError as exc:
        kill_proc(proc)
        raise LaunchTransient(f"spawn failed: {exc}") from exc
    except KeyError as exc:
        kill_proc(proc)
        raise LaunchFatal(f"missing expected app-server field: {exc}") from exc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cwd", required=True, help="absolute worktree cwd")
    ap.add_argument("--outcome-file", required=True, help="absolute path to frozen outcome.md; goal mode is mandatory")
    ap.add_argument("--evidence-dir", required=True)
    ap.add_argument("--model", default=None)
    ap.add_argument("--effort", default="low", choices=["none", "minimal", "low", "medium", "high", "xhigh"])
    ap.add_argument("--timeout-sec", type=int, default=3600)
    ap.add_argument("--idle-timeout-sec", type=int, default=120)
    ap.add_argument("--heartbeat-sec", type=int, default=30)
    ap.add_argument("--inferred-completion-sec", type=int, default=5)
    ap.add_argument("--handshake-timeout-sec", type=int, default=20)
    ap.add_argument("--launch-retries", type=int, default=2)
    ap.add_argument("--launch-backoff", default="1,2")
    ap.add_argument("--codex-bin", default=None, help="test-only binary override; production conduct.sh never passes this")
    args = ap.parse_args()

    cwd = Path(args.cwd).resolve()
    outcome_file = Path(args.outcome_file).resolve()
    if not outcome_file.exists():
        print(f"outcome file not found: {outcome_file}", file=sys.stderr)
        return 4
    evidence = Path(args.evidence_dir)
    evidence.mkdir(parents=True, exist_ok=True)
    backoffs = [int(x) for x in args.launch_backoff.split(",") if x.strip()]
    if not backoffs:
        backoffs = [1]

    with (evidence / "raw_vendor_output.jsonl").open("a", encoding="utf-8") as raw, \
        (evidence / "rpc_requests.jsonl").open("a", encoding="utf-8") as rpc, \
        (evidence / "vendor_stderr.txt").open("a", encoding="utf-8") as err, \
        (evidence / "driver_events.jsonl").open("a", encoding="utf-8") as meta:

        proc = None
        for attempt in range(args.launch_retries + 1):
            emit_meta(meta, event="launch_attempt", attempt=attempt)
            try:
                proc, _thread_id = launch_and_handshake(args, raw, rpc, err, meta)
                emit_meta(meta, event="launch_ok", attempt=attempt)
                break
            except LaunchFatal as exc:
                emit_meta(meta, event="launch_fatal", attempt=attempt, reason=str(exc))
                return 4
            except LaunchTransient as exc:
                emit_meta(meta, event="launch_failed", attempt=attempt, reason=str(exc))
                if attempt < args.launch_retries:
                    time.sleep(backoffs[min(attempt, len(backoffs) - 1)])
        else:
            emit_meta(meta, event="launch_exhausted", attempts=args.launch_retries + 1)
            return 3

        try:
            assert proc is not None
            return wait_for_turn_completion(
                proc,
                raw,
                err,
                meta,
                timeout_sec=args.timeout_sec,
                heartbeat_sec=args.heartbeat_sec,
                inferred_completion_sec=args.inferred_completion_sec,
                idle_timeout_sec=args.idle_timeout_sec,
            )
        finally:
            kill_proc(proc)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"codex_driver failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
