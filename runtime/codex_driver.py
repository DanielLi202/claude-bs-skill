#!/usr/bin/env python3
"""Codex app-server driver for bs v1.3.

Runs one prompt against `codex app-server --listen stdio://`, captures JSON-RPC
requests, raw server output, stderr, and driver metadata. The driver preserves
v1.2 completion robustness: a 30s heartbeat while waiting and a 5s inferred
completion timer armed by final-answer/idle signals when an explicit
`turn/completed` event is missing or raced.
"""
from __future__ import annotations

import argparse
import json
import select
import subprocess
import sys
import time
from pathlib import Path
from typing import TextIO


def write_jsonl(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n")


def detect_inferred_completion_signal(obj: dict) -> str | None:
    """Return a reason when an app-server notification can arm inference.

    Codex app-server versions have emitted both final-answer item completion and
    thread status changes. The explicit `turn/completed` notification remains the
    authority; these signals only arm the short fallback timer.
    """
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
    proc.stdin.write(line + "\n")
    proc.stdin.flush()


def read_response(proc: subprocess.Popen, raw: TextIO, err: TextIO, target: int, timeout: int) -> dict:
    start = time.monotonic()
    assert proc.stdout is not None and proc.stderr is not None
    while time.monotonic() - start < timeout:
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
                    return obj
            else:
                err.write(line)
                err.flush()
    raise TimeoutError(f"timed out waiting for response id={target}")


def wait_for_turn_completion(
    proc: subprocess.Popen,
    raw: TextIO,
    err: TextIO,
    meta: TextIO,
    timeout_sec: int,
    heartbeat_sec: int,
    inferred_completion_sec: int,
) -> int:
    start = time.monotonic()
    last_activity = start
    last_heartbeat = start
    inferred_armed_at: float | None = None
    inferred_reason: str | None = None
    assert proc.stdout is not None and proc.stderr is not None

    while time.monotonic() - start < timeout_sec:
        now = time.monotonic()
        if heartbeat_sec > 0 and now - last_heartbeat >= heartbeat_sec:
            emit_meta(meta, event="heartbeat", idle_sec=round(now - last_activity, 3))
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
            last_activity = time.monotonic()
            if stream is proc.stdout:
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
    raise TimeoutError("turn completion timeout")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cwd", required=True, help="absolute worktree cwd")
    ap.add_argument("--prompt-file", required=True)
    ap.add_argument("--evidence-dir", required=True)
    ap.add_argument("--model", default=None)
    ap.add_argument("--effort", default="low", choices=["none", "minimal", "low", "medium", "high", "xhigh"])
    ap.add_argument("--timeout-sec", type=int, default=180)
    ap.add_argument("--heartbeat-sec", type=int, default=30)
    ap.add_argument("--inferred-completion-sec", type=int, default=5)
    args = ap.parse_args()

    cwd = Path(args.cwd).resolve()
    prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    evidence = Path(args.evidence_dir)
    evidence.mkdir(parents=True, exist_ok=True)

    with (evidence / "raw_vendor_output.jsonl").open("a", encoding="utf-8") as raw, \
        (evidence / "rpc_requests.jsonl").open("a", encoding="utf-8") as rpc, \
        (evidence / "vendor_stderr.txt").open("a", encoding="utf-8") as err, \
        (evidence / "driver_events.jsonl").open("a", encoding="utf-8") as meta:

        proc = subprocess.Popen(
            ["codex", "app-server", "--listen", "stdio://"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=str(cwd),
        )

        try:
            send(proc, rpc, 1, "initialize", {"clientInfo": {"name": "bs-codex-driver", "version": "0.2"}, "capabilities": {"experimentalApi": True}})
            init = read_response(proc, raw, err, 1, 10)
            if "error" in init:
                raise RuntimeError(init["error"])

            thread_params = {"cwd": str(cwd), "approvalPolicy": "never", "sandbox": "workspace-write", "ephemeral": True}
            if args.model:
                thread_params["model"] = args.model
            send(proc, rpc, 2, "thread/start", thread_params)
            thread = read_response(proc, raw, err, 2, 30)
            if "error" in thread:
                raise RuntimeError(thread["error"])
            thread_id = thread["result"]["thread"]["id"]

            send(proc, rpc, 3, "turn/start", {
                "threadId": thread_id,
                "input": [{"type": "text", "text": prompt}],
                "cwd": str(cwd),
                "approvalPolicy": "never",
                "sandboxPolicy": {"type": "workspaceWrite", "writableRoots": [str(cwd)], "networkAccess": False},
                "effort": args.effort,
            })
            turn = read_response(proc, raw, err, 3, 20)
            if "error" in turn:
                raise RuntimeError(turn["error"])

            return wait_for_turn_completion(
                proc,
                raw,
                err,
                meta,
                timeout_sec=args.timeout_sec,
                heartbeat_sec=args.heartbeat_sec,
                inferred_completion_sec=args.inferred_completion_sec,
            )
        finally:
            try:
                proc.kill()
            except Exception:
                pass


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"codex_driver failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
