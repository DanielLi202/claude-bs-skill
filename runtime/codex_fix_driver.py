#!/usr/bin/env python3
"""Minimal Codex app-server fix driver for bs v1.3.

Runs one prompt against `codex app-server --listen stdio://`, captures JSON-RPC
requests, raw server output, and stderr, and exits non-zero unless the turn
finishes with status=completed. This driver is intentionally small; orchestration
(step events, git worktree setup, and artifact checks) remains owned by the bs
runtime/command layer.
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


def write_jsonl(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cwd", required=True, help="absolute worktree cwd")
    ap.add_argument("--prompt-file", required=True)
    ap.add_argument("--evidence-dir", required=True)
    ap.add_argument("--model", default=None)
    ap.add_argument("--effort", default="low", choices=["none", "minimal", "low", "medium", "high", "xhigh"])
    ap.add_argument("--timeout-sec", type=int, default=180)
    args = ap.parse_args()

    cwd = Path(args.cwd).resolve()
    prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    evidence = Path(args.evidence_dir)
    evidence.mkdir(parents=True, exist_ok=True)

    raw = (evidence / "raw_vendor_output.jsonl").open("a", encoding="utf-8")
    rpc = (evidence / "rpc_requests.jsonl").open("a", encoding="utf-8")
    err = (evidence / "vendor_stderr.txt").open("a", encoding="utf-8")

    proc = subprocess.Popen(
        ["codex", "app-server", "--listen", "stdio://"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        cwd=str(cwd),
    )

    def send(i: int, method: str, params: dict) -> None:
        req = {"jsonrpc": "2.0", "id": i, "method": method, "params": params}
        line = json.dumps(req, ensure_ascii=False)
        rpc.write(line + "\n"); rpc.flush()
        assert proc.stdin is not None
        proc.stdin.write(line + "\n"); proc.stdin.flush()

    def read_response(target: int, timeout: int) -> dict:
        start = time.time()
        assert proc.stdout is not None and proc.stderr is not None
        while time.time() - start < timeout:
            ready, _, _ = select.select([proc.stdout, proc.stderr], [], [], 0.5)
            for stream in ready:
                line = stream.readline()
                if not line:
                    continue
                if stream is proc.stdout:
                    raw.write(line); raw.flush()
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if obj.get("id") == target:
                        return obj
                else:
                    err.write(line); err.flush()
        raise TimeoutError(f"timed out waiting for response id={target}")

    try:
        send(1, "initialize", {"clientInfo": {"name": "bs-codex-driver", "version": "0.1"}, "capabilities": {"experimentalApi": True}})
        init = read_response(1, 10)
        if "error" in init:
            raise RuntimeError(init["error"])

        thread_params = {"cwd": str(cwd), "approvalPolicy": "never", "sandbox": "workspace-write", "ephemeral": True}
        if args.model:
            thread_params["model"] = args.model
        send(2, "thread/start", thread_params)
        thread = read_response(2, 30)
        if "error" in thread:
            raise RuntimeError(thread["error"])
        thread_id = thread["result"]["thread"]["id"]

        send(3, "turn/start", {
            "threadId": thread_id,
            "input": [{"type": "text", "text": prompt}],
            "cwd": str(cwd),
            "approvalPolicy": "never",
            "sandboxPolicy": {"type": "workspaceWrite", "writableRoots": [str(cwd)], "networkAccess": False},
            "effort": args.effort,
        })
        turn = read_response(3, 20)
        if "error" in turn:
            raise RuntimeError(turn["error"])

        last = time.time()
        assert proc.stdout is not None and proc.stderr is not None
        while time.time() - last < args.timeout_sec:
            ready, _, _ = select.select([proc.stdout, proc.stderr], [], [], 1.0)
            if not ready:
                continue
            for stream in ready:
                line = stream.readline()
                if not line:
                    continue
                last = time.time()
                if stream is proc.stdout:
                    raw.write(line); raw.flush()
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if obj.get("method") == "turn/completed":
                        status = obj["params"]["turn"].get("status")
                        return 0 if status == "completed" else 2
                else:
                    err.write(line); err.flush()
        raise TimeoutError("turn completion timeout")
    finally:
        try:
            proc.kill()
        except Exception:
            pass
        raw.close(); rpc.close(); err.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"codex_driver failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
