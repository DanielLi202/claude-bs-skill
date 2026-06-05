#!/usr/bin/env python3
"""Codex app-server driver for bs v1.4.1.

Delegates a frozen outcome capsule through a persistent, non-ephemeral Codex
app-server thread using `thread/goal/set`, not text `/goal`. The driver computes
outcome sha256 out-of-band, sets a `BS_GOAL_V1` objective, starts one
content-free launcher that asks the model to emit `BS_OUTCOME_READ`, and exits 0
only when final `thread/goal/get` normalizes to `complete` and read evidence
matches the driver hash. Cleanup best-effort clears the goal and archives the
thread on every thread-owned exit path.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import select
import signal
import subprocess
import sys
import tempfile
import time
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO


class LaunchTransient(Exception):
    pass


class LaunchFatal(Exception):
    pass


HARD_REFUSAL_MARKERS = ["Blocked: true", "required tools are unavailable", "goal-backed execution cannot start"]
SOFT_REFUSAL_MARKERS = ["I can't proceed", "I cannot proceed", "unable to proceed"]
WRITE_ACTIONS = {"write", "edit"}
DRIVER_EVIDENCE_FILES = {"raw_vendor_output.jsonl", "rpc_requests.jsonl", "vendor_stderr.txt", "driver_events.jsonl", "codex_env.json"}
GOAL_HEADER_PREFIX = "BS_GOAL_V1 "
OUTCOME_READ_PREFIX = "BS_OUTCOME_READ "
ACTIVE_CLEANUP: dict[str, object] = {}


@dataclass
class Snapshot:
    files: dict[str, str]


@dataclass
class TurnObservation:
    cwd: Path
    evidence_dir: Path
    final_answer_text: str | None = None
    final_answer_seen: bool = False
    command_actions: dict[str, int] = field(default_factory=lambda: {"read": 0, "search": 0, "write": 0, "edit": 0})
    final_answer_deltas: dict[str, str] = field(default_factory=dict)
    turn_start_snapshot: Snapshot | None = None
    turn_end_snapshot: Snapshot | None = None
    evidence_start_snapshot: Snapshot | None = None
    evidence_end_snapshot: Snapshot | None = None
    workspace_delta_files: list[str] = field(default_factory=list)
    evidence_delta_files: list[str] = field(default_factory=list)
    outcome_read_markers: list[dict] = field(default_factory=list)
    file_change_events: int = 0
    first_work_item_at: float | None = None
    first_model_output_at: float | None = None
    mcp_events_seen: int = 0
    skill_events_seen: int = 0
    observed_mcp_servers: set[str] = field(default_factory=set)
    observed_skills: set[str] = field(default_factory=set)

    @property
    def write_action_count(self) -> int:
        return sum(self.command_actions.get(k, 0) for k in WRITE_ACTIONS)

    def start(self) -> None:
        self.turn_start_snapshot = snapshot_tree(self.cwd, self.evidence_dir)
        self.evidence_start_snapshot = snapshot_evidence_tree(self.evidence_dir)

    def finish(self) -> None:
        self.turn_end_snapshot = snapshot_tree(self.cwd, self.evidence_dir)
        self.evidence_end_snapshot = snapshot_evidence_tree(self.evidence_dir)
        start = self.turn_start_snapshot.files if self.turn_start_snapshot else {}
        end = self.turn_end_snapshot.files if self.turn_end_snapshot else {}
        self.workspace_delta_files = sorted(p for p, d in end.items() if start.get(p) != d) + [f"{p} (removed)" for p in sorted(p for p in start if p not in end)]
        evs = self.evidence_start_snapshot.files if self.evidence_start_snapshot else {}
        eve = self.evidence_end_snapshot.files if self.evidence_end_snapshot else {}
        self.evidence_delta_files = sorted(p for p, d in eve.items() if evs.get(p) != d) + [f"{p} (removed)" for p in sorted(p for p in evs if p not in eve)]

    def record_text(self, text: str) -> None:
        marker = parse_outcome_read_marker(text)
        if marker is not None:
            self.outcome_read_markers.append(marker)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_goal_header(run_id: str, outcome_sha: str, outcome_file: Path) -> str:
    payload = {"run_id": run_id, "outcome_sha256": outcome_sha, "outcome_path": str(outcome_file)}
    return GOAL_HEADER_PREFIX + json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def parse_goal_header(objective: str | None) -> dict | None:
    if not objective:
        return None
    first = objective.splitlines()[0] if objective.splitlines() else objective
    if not first.startswith(GOAL_HEADER_PREFIX):
        return None
    try:
        obj = json.loads(first[len(GOAL_HEADER_PREFIX):])
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def build_goal_objective(outcome_file: Path, outcome_sha: str, run_id: str) -> str:
    objective = (
        build_goal_header(run_id, outcome_sha, outcome_file)
        + "\nImplement the frozen bs outcome capsule exactly. The absolute outcome file is the single source of truth; read it before changing files and continue until the goal status is complete."
    )
    if len(objective) > 4000:
        raise LaunchFatal("goal objective exceeds Codex 4000 character limit")
    return objective


def build_launcher_text(outcome_file: Path, outcome_sha: str) -> str:
    payload = json.dumps({"path": str(outcome_file), "sha256": outcome_sha}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return (
        f"Read the current goal objective. Before making changes, read {outcome_file} and emit exactly: "
        f"{OUTCOME_READ_PREFIX}{payload}. Then implement the frozen outcome to the letter and continue until the goal status is complete."
    )


def parse_outcome_read_marker(text: str) -> dict | None:
    idx = text.find(OUTCOME_READ_PREFIX)
    if idx < 0:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(text[idx + len(OUTCOME_READ_PREFIX):].lstrip())
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def normalize_goal_status(raw: object) -> str:
    if not isinstance(raw, str):
        return "unknown"
    mapped = {"usageLimited": "usage_limited", "budgetLimited": "budget_limited"}.get(raw, raw)
    return mapped if mapped in {"active", "paused", "blocked", "complete", "usage_limited", "budget_limited"} else "unknown"


def _goal_obj(result: dict) -> dict:
    obj = result.get("goal") or result.get("threadGoal") or result.get("data") or result
    return obj if isinstance(obj, dict) else {}


def extract_goal_status(result: dict) -> tuple[str, object]:
    raw = _goal_obj(result).get("status")
    return normalize_goal_status(raw), raw


def extract_goal_objective(result: dict) -> str | None:
    val = _goal_obj(result).get("objective")
    return val if isinstance(val, str) else None


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _fingerprint(path: Path) -> str:
    st = path.stat()
    h = hashlib.sha256()
    h.update(str(st.st_size).encode())
    h.update(str(st.st_mtime_ns).encode())
    return h.hexdigest()


def snapshot_tree(cwd: Path, evidence_dir: Path) -> Snapshot:
    files: dict[str, str] = {}
    er = evidence_dir.resolve()
    for path in cwd.rglob("*"):
        if not path.is_file():
            continue
        parts = path.relative_to(cwd).parts
        if ".git" in parts or "__pycache__" in parts or _is_relative_to(path, er):
            continue
        try:
            files[path.relative_to(cwd).as_posix()] = _fingerprint(path)
        except OSError:
            pass
    return Snapshot(files)


def snapshot_evidence_tree(evidence_dir: Path) -> Snapshot:
    files: dict[str, str] = {}
    if not evidence_dir.exists():
        return Snapshot(files)
    for path in evidence_dir.rglob("*"):
        if not path.is_file():
            continue
        try:
            rel = path.relative_to(evidence_dir).as_posix()
        except ValueError:
            rel = str(path)
        if rel in DRIVER_EVIDENCE_FILES:
            continue
        try:
            files[rel] = _fingerprint(path)
        except OSError:
            pass
    return Snapshot(files)


def detect_inferred_completion_signal(obj: dict) -> str | None:
    method = obj.get("method")
    params = obj.get("params") or {}
    if method == "item/completed":
        item = params.get("item") or {}
        phase = item.get("phase") or params.get("phase")
        typ = item.get("type") or params.get("type")
        role = item.get("role") or params.get("role")
        if phase == "final_answer" or (typ in {"message", "assistant_message", "agentMessage"} and role in {"assistant", None} and phase == "final_answer"):
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


def _codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser().resolve()


def _toml_mcp_servers(config: Path) -> list[str]:
    try:
        data = tomllib.loads(config.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return []
    servers = data.get("mcp_servers")
    return sorted(servers.keys()) if isinstance(servers, dict) else []


def _skill_names(home: Path) -> list[str]:
    skills = home / "skills"
    try:
        return sorted(p.name for p in skills.iterdir() if not p.name.startswith("."))
    except OSError:
        return []


def _instruction_sources(cwd: Path, home: Path) -> dict[str, object]:
    out: dict[str, object] = {
        "repo_agents_md": (cwd / "AGENTS.md").exists(),
        "codex_config": (home / "config.toml").exists(),
        "config_instruction_keys": [],
    }
    try:
        data = tomllib.loads((home / "config.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return out
    out["config_instruction_keys"] = sorted(k for k in data.keys() if "instruction" in str(k).lower())
    return out


def write_codex_env_snapshot(args: argparse.Namespace, obs: TurnObservation | None = None) -> None:
    evidence = Path(args.evidence_dir).resolve()
    home = _codex_home()
    payload: dict[str, object] = {
        "codex_home": str(home),
        "config_mcp_servers": _toml_mcp_servers(home / "config.toml"),
        "skills": _skill_names(home),
        "clean_codex_home": bool(getattr(args, "clean_codex_home", False)),
        "mcp_policy": getattr(args, "mcp_policy", None),
        "mcp_allowlist": getattr(args, "mcp_allowlist", []),
        "binding_mcp_policy": getattr(args, "binding_mcp_policy", None),
        "suppressed_mcp_servers": getattr(args, "suppressed_mcp_servers", []),
        "instruction_sources": _instruction_sources(Path(args.cwd).resolve(), home),
    }
    if obs is not None:
        payload.update({
            "observed_mcp_servers": sorted(obs.observed_mcp_servers),
            "observed_skills": sorted(obs.observed_skills),
            "mcp_events_seen": obs.mcp_events_seen,
            "skill_events_seen": obs.skill_events_seen,
        })
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "codex_env.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _content_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str):
                    out.append(text)
        return "".join(out)
    return ""


def _name_from_params(params: dict, item: dict) -> str | None:
    for source in (params, item):
        for key in ("name", "server", "serverName", "skill", "skillName", "id"):
            val = source.get(key)
            if isinstance(val, str) and val:
                return val
    return None


def _mark_work_item(obs: TurnObservation) -> None:
    if obs.first_work_item_at is None:
        obs.first_work_item_at = time.monotonic()


def observe_event(obj: dict, obs: TurnObservation) -> None:
    method = obj.get("method")
    params = obj.get("params") or {}
    params = params if isinstance(params, dict) else {}
    item = params.get("item") or {}
    item = item if isinstance(item, dict) else {}
    if isinstance(method, str) and method.startswith("mcpServer/"):
        obs.mcp_events_seen += 1
        name = _name_from_params(params, item)
        if name:
            obs.observed_mcp_servers.add(name)
    if method == "skills/changed":
        obs.skill_events_seen += 1
        name = _name_from_params(params, item)
        if name:
            obs.observed_skills.add(name)
    if method == "item/agentMessage/delta":
        obs.first_model_output_at = obs.first_model_output_at or time.monotonic()
        iid = str(params.get("itemId") or "")
        delta = params.get("delta")
        if iid and isinstance(delta, str):
            obs.final_answer_deltas[iid] = obs.final_answer_deltas.get(iid, "") + delta
            obs.record_text(obs.final_answer_deltas[iid])
        return
    actions = item.get("commandActions")
    if isinstance(actions, list):
        for action in actions:
            if isinstance(action, dict) and action.get("type") in obs.command_actions:
                obs.command_actions[action["type"]] += 1
    phase = item.get("phase") or params.get("phase")
    typ = item.get("type") or params.get("type")
    if method in {"item/started", "item/completed"}:
        _mark_work_item(obs)
    if method in {"item/started", "item/completed"} and typ == "fileChange":
        obs.file_change_events += 1
    text = item.get("text") or _content_text(item.get("content"))
    if isinstance(text, str) and text:
        obs.first_model_output_at = obs.first_model_output_at or time.monotonic()
        obs.record_text(text)
    if method in {"item/completed", "item/started"} and phase == "final_answer" and typ in {"agentMessage", "message", "assistant_message"}:
        iid = str(item.get("id") or "")
        text = text or obs.final_answer_deltas.get(iid, "")
        if isinstance(text, str):
            obs.final_answer_text = text
            obs.final_answer_seen = True


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
    msg = (err.get("message") if isinstance(err, dict) else str(err)) or json.dumps(err, ensure_ascii=False, sort_keys=True)
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
        proc.wait(timeout=2)
    except Exception:
        pass


def _matches_marker(text: str, markers: list[str]) -> str | None:
    low = text.lower()
    for marker in markers:
        if marker.lower() in low:
            return marker
    return None


def post_turn_validate(args: argparse.Namespace, obs: TurnObservation, meta: TextIO, completion_event: str, **fields: object) -> int:
    obs.finish()
    final = obs.final_answer_text or ""
    hard = _matches_marker(final, HARD_REFUSAL_MARKERS)
    soft = _matches_marker(final, SOFT_REFUSAL_MARKERS)
    workspace = bool(obs.workspace_delta_files)
    evidence = bool(obs.evidence_delta_files)
    any_delta = workspace or evidence
    present = True
    if args.expected_effect_required and args.expected_effect_kind != "none":
        present = {"workspace_delta": workspace, "evidence_delta": evidence, "any_delta": any_delta}[args.expected_effect_kind]
    reason = None
    if hard:
        reason = "semantic_blocked_final_answer" if "blocked" in hard.lower() else "semantic_refusal_final_answer"
    elif soft and not present:
        reason = "semantic_refusal_final_answer"
    elif not present:
        reason = "semantic_required_effect_missing"
    payload = dict(expected_effect_kind=args.expected_effect_kind, expected_effect_required=args.expected_effect_required, workspace_delta_files=obs.workspace_delta_files, evidence_delta_files=obs.evidence_delta_files, write_actions=obs.write_action_count, file_change_events=obs.file_change_events, completion_event=completion_event, **fields)
    if reason:
        emit_meta(meta, event="turn_semantic_observation", reason_code=reason, marker=hard or soft, final_answer_seen=obs.final_answer_seen, **payload)
    emit_meta(meta, event=completion_event, semantic_validated=True, **payload)
    return 0


def wait_for_turn_completion(proc: subprocess.Popen, raw: TextIO, err: TextIO, meta: TextIO, obs: TurnObservation, args: argparse.Namespace) -> int:
    start = time.monotonic()
    last_stdout = start
    last_heartbeat = start
    last_report = start
    inferred_at = None
    inferred_reason = None
    soft = False
    stale = False
    wall = False
    obs.start()
    assert proc.stdout is not None and proc.stderr is not None
    wall_limit = args.wall_clock_limit_sec or (args.timeout_sec if args.timeout_sec > 0 and args.on_wall_clock_limit in {"fail", "terminate"} else 0)
    no_work_stale = False
    while True:
        now = time.monotonic()
        silent = now - last_stdout
        elapsed = now - start
        if proc.poll() is not None:
            emit_meta(meta, event="transport_failed", reason_code="transport_eof_before_completion", exit=proc.returncode)
            write_codex_env_snapshot(args, obs)
            return 2
        if wall_limit > 0 and elapsed > wall_limit:
            if not wall:
                emit_meta(meta, event="turn_wall_clock_limit", reason_code="wall_clock_policy_exceeded", limit_sec=wall_limit, policy=args.on_wall_clock_limit)
                wall = True
            if args.on_wall_clock_limit in {"fail", "terminate"}:
                write_codex_env_snapshot(args, obs)
                kill_proc(proc)
                return 2
        if obs.first_work_item_at is None and args.first_work_item_stale_sec > 0 and not no_work_stale and elapsed > args.first_work_item_stale_sec:
            emit_meta(meta, event="turn_no_work_items_stale", elapsed_sec=round(elapsed, 3), stale_sec=args.first_work_item_stale_sec, mcp_events_seen=obs.mcp_events_seen, skill_events_seen=obs.skill_events_seen)
            no_work_stale = True
        if obs.first_work_item_at is None and args.on_no_work_items == "terminate" and args.first_work_item_terminate_sec > 0 and elapsed > args.first_work_item_terminate_sec:
            emit_meta(meta, event="turn_no_work_items_terminated", elapsed_sec=round(elapsed, 3), terminate_sec=args.first_work_item_terminate_sec, mcp_events_seen=obs.mcp_events_seen, skill_events_seen=obs.skill_events_seen)
            write_codex_env_snapshot(args, obs)
            kill_proc(proc)
            return 7
        if args.idle_timeout_sec > 0 and silent > args.idle_timeout_sec:
            emit_meta(meta, event="turn_idle_timeout", idle_timeout_sec=args.idle_timeout_sec)
            write_codex_env_snapshot(args, obs)
            kill_proc(proc)
            return 2
        if args.silent_soft_limit_sec > 0 and not soft and silent > args.silent_soft_limit_sec:
            emit_meta(meta, event="turn_silent_soft_limit", silent_for_sec=round(silent, 3), soft_limit_sec=args.silent_soft_limit_sec)
            soft = True
        if args.stale_notice_sec > 0 and not stale and silent > args.stale_notice_sec:
            emit_meta(meta, event="turn_progress_stale", stale_for_sec=round(silent, 3), stale_notice_sec=args.stale_notice_sec)
            stale = True
        if args.progress_report_sec > 0 and now - last_report >= args.progress_report_sec:
            emit_meta(meta, event="turn_monitor_snapshot", status="stale" if stale else "running", elapsed_sec=round(elapsed, 3), stale_for_sec=round(silent, 3), process_alive=proc.poll() is None, last_progress_kind="stdout" if last_stdout > start else "none")
            emit_meta(meta, event="turn_long_running", elapsed_sec=round(elapsed, 3))
            last_report = now
        if args.heartbeat_sec > 0 and now - last_heartbeat >= args.heartbeat_sec:
            emit_meta(meta, event="heartbeat", idle_sec=round(silent, 3))
            last_heartbeat = now
        if inferred_at is not None and now - inferred_at >= args.inferred_completion_sec:
            rc = post_turn_validate(args, obs, meta, "turn_completed_inferred", inferred_completion=True, reason=inferred_reason, armed_for_sec=args.inferred_completion_sec)
            write_codex_env_snapshot(args, obs)
            return rc
        ready, _, _ = select.select([proc.stdout, proc.stderr], [], [], 0.25)
        if not ready:
            continue
        for stream in ready:
            line = stream.readline()
            if not line:
                continue
            if stream is proc.stdout:
                last_stdout = time.monotonic()
                soft = False
                stale = False
                raw.write(line)
                raw.flush()
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("method") == "thread/goal/updated":
                    canonical, raw_status = extract_goal_status(obj.get("params") or {})
                    emit_meta(meta, event="goal_status_update", goal_status=canonical, raw_goal_status=raw_status)
                observe_event(obj, obs)
                if obj.get("method") == "turn/completed":
                    status = (obj.get("params") or {}).get("turn", {}).get("status")
                    if status == "completed":
                        rc = post_turn_validate(args, obs, meta, "turn_completed_explicit", status=status)
                        write_codex_env_snapshot(args, obs)
                        return rc
                    emit_meta(meta, event="turn_completed_explicit", status=status)
                    write_codex_env_snapshot(args, obs)
                    return 2
                reason = detect_inferred_completion_signal(obj)
                if reason and inferred_at is None:
                    inferred_at = time.monotonic()
                    inferred_reason = reason
                    emit_meta(meta, event="inferred_completion_armed", reason=reason, delay_sec=args.inferred_completion_sec)
            else:
                err.write(line)
                err.flush()


def rpc_call(proc: subprocess.Popen, raw: TextIO, rpc: TextIO, err: TextIO, i: int, method: str, params: dict, timeout: int) -> dict:
    send(proc, rpc, i, method, params)
    return read_response(proc, raw, err, i, timeout)


def cleanup_thread(proc: subprocess.Popen | None, raw: TextIO | None, rpc: TextIO | None, err: TextIO | None, meta: TextIO | None, thread_id: str | None, timeout: int = 5) -> None:
    if proc is None or thread_id is None or raw is None or rpc is None or err is None or meta is None:
        return
    if proc.poll() is not None:
        emit_meta(meta, event="cleanup_skipped", reason="process_exited", thread_id=thread_id)
        return
    for i, method, event in ((900001, "thread/goal/clear", "cleanup_goal_clear"), (900002, "thread/archive", "cleanup_thread_archive")):
        try:
            rpc_call(proc, raw, rpc, err, i, method, {"threadId": thread_id}, timeout)
            emit_meta(meta, event=event, success=True, thread_id=thread_id)
        except Exception as exc:
            emit_meta(meta, event=event, success=False, thread_id=thread_id, error=str(exc))


def _signal_handler(signum: int, _frame: object) -> None:
    meta = ACTIVE_CLEANUP.get("meta")
    if meta is not None:
        try:
            emit_meta(meta, event="signal_received", signal=signum)
        except Exception:
            pass
    cleanup_thread(ACTIVE_CLEANUP.get("proc"), ACTIVE_CLEANUP.get("raw"), ACTIVE_CLEANUP.get("rpc"), ACTIVE_CLEANUP.get("err"), ACTIVE_CLEANUP.get("meta"), ACTIVE_CLEANUP.get("thread_id"))  # type: ignore[arg-type]
    kill_proc(ACTIVE_CLEANUP.get("proc"))  # type: ignore[arg-type]
    raise SystemExit(2)


def install_signal_handlers() -> None:
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)


def build_goal_input(outcome_file: Path) -> str:
    raise LaunchFatal(f"inline /goal fallback is disabled for {outcome_file}")


def resolve_codex_bin(args: argparse.Namespace) -> str:
    if args.codex_bin:
        return args.codex_bin
    if os.environ.get("BS_TEST_FAKE_CODEX") == "1":
        return os.environ.get("CODEX_BIN", "codex")
    return "codex"


def launch_and_handshake(args: argparse.Namespace, raw: TextIO, rpc: TextIO, err: TextIO, meta: TextIO) -> tuple[subprocess.Popen, str, str, str]:
    cwd = Path(args.cwd).resolve()
    outcome_file = Path(args.outcome_file).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    proc = None
    thread_id = None
    codex_bin = resolve_codex_bin(args)
    outcome_sha = sha256_file(outcome_file)
    run_id = args.run_id or outcome_file.parent.name or hashlib.sha256(str(evidence_dir).encode()).hexdigest()[:16]
    objective = build_goal_objective(outcome_file, outcome_sha, run_id)
    expected = parse_goal_header(objective) or {}
    launcher = build_launcher_text(outcome_file, outcome_sha)
    try:
        proc = subprocess.Popen([codex_bin, "app-server", "--listen", "stdio://"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, cwd=str(cwd))
        rpc_call(proc, raw, rpc, err, 1, "initialize", {"clientInfo": {"name": "bs-codex-driver", "version": "1.4.2"}, "capabilities": {"experimentalApi": True}}, args.handshake_timeout_sec)
        params = {"cwd": str(cwd), "approvalPolicy": "never", "sandbox": "workspace-write", "ephemeral": False}
        if args.model:
            params["model"] = args.model
        thread = rpc_call(proc, raw, rpc, err, 2, "thread/start", params, args.handshake_timeout_sec)
        thread_id = thread["result"]["thread"]["id"]
        ACTIVE_CLEANUP.update({"proc": proc, "raw": raw, "rpc": rpc, "err": err, "meta": meta, "thread_id": thread_id})
        install_signal_handlers()
        emit_meta(meta, event="thread_started", thread_id=thread_id, ephemeral=False, outcome_sha256=outcome_sha, run_id=run_id)
        write_codex_env_snapshot(args)
        current = rpc_call(proc, raw, rpc, err, 3, "thread/goal/get", {"threadId": thread_id}, args.handshake_timeout_sec).get("result") or {}
        existing = parse_goal_header(extract_goal_objective(current))
        if existing and any(existing.get(k) != expected.get(k) for k in ("run_id", "outcome_sha256", "outcome_path")):
            raise LaunchFatal("existing goal header mismatch")
        rpc_call(proc, raw, rpc, err, 4, "thread/goal/set", {"threadId": thread_id, "objective": objective, "status": "active", "tokenBudget": None}, args.handshake_timeout_sec)
        emit_meta(meta, event="goal_set", thread_id=thread_id, goal_status="active", raw_goal_status="active", outcome_sha256=outcome_sha)
        rpc_call(proc, raw, rpc, err, 5, "turn/start", {"threadId": thread_id, "input": [{"type": "text", "text": launcher}], "cwd": str(cwd), "approvalPolicy": "never", "sandboxPolicy": {"type": "workspaceWrite", "writableRoots": [str(cwd)], "networkAccess": False}, "effort": args.effort}, args.handshake_timeout_sec)
        return proc, thread_id, outcome_sha, str(outcome_file)
    except LaunchFatal:
        cleanup_thread(proc, raw, rpc, err, meta, thread_id)
        kill_proc(proc)
        raise
    except LaunchTransient:
        cleanup_thread(proc, raw, rpc, err, meta, thread_id)
        kill_proc(proc)
        raise
    except OSError as exc:
        cleanup_thread(proc, raw, rpc, err, meta, thread_id)
        kill_proc(proc)
        raise LaunchTransient(f"spawn failed: {exc}") from exc
    except KeyError as exc:
        cleanup_thread(proc, raw, rpc, err, meta, thread_id)
        kill_proc(proc)
        raise LaunchFatal(f"missing expected app-server field: {exc}") from exc


def final_goal_check(proc: subprocess.Popen, raw: TextIO, rpc: TextIO, err: TextIO, meta: TextIO, thread_id: str, timeout: int) -> str:
    resp = rpc_call(proc, raw, rpc, err, 800001, "thread/goal/get", {"threadId": thread_id}, timeout)
    canonical, raw_status = extract_goal_status(resp.get("result") or {})
    emit_meta(meta, event="goal_status_final", goal_status=canonical, raw_goal_status=raw_status, thread_id=thread_id)
    return canonical


def validate_outcome_read_marker(obs: TurnObservation, path: str, sha: str, meta: TextIO) -> bool:
    for marker in obs.outcome_read_markers:
        ok = marker.get("path") == path and marker.get("sha256") == sha
        emit_meta(meta, event="outcome_read_marker", path=marker.get("path"), sha256=marker.get("sha256"), match=ok)
        if ok:
            return True
    emit_meta(meta, event="outcome_read_marker_missing_or_mismatch", expected_path=path, expected_sha256=sha, marker_count=len(obs.outcome_read_markers))
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cwd", required=True)
    ap.add_argument("--outcome-file", required=True)
    ap.add_argument("--evidence-dir", required=True)
    ap.add_argument("--model", default=None)
    ap.add_argument("--effort", default="low", choices=["none", "minimal", "low", "medium", "high", "xhigh"])
    ap.add_argument("--timeout-sec", type=int, default=0, help="legacy wall-clock limit; ignored unless on-wall-clock-limit is fail/terminate")
    ap.add_argument("--wall-clock-limit-sec", type=int, default=0)
    ap.add_argument("--on-wall-clock-limit", default="mark_stale", choices=["mark_stale", "fail", "terminate"])
    ap.add_argument("--first-work-item-stale-sec", type=int, default=300, help="emit telemetry when no item/started, item/completed, or fileChange appears after this many seconds; 0 disables")
    ap.add_argument("--first-work-item-terminate-sec", type=int, default=0, help="terminate with exit 7 when no work item appears after this many seconds and --on-no-work-items=terminate")
    ap.add_argument("--on-no-work-items", default="mark_stale", choices=["mark_stale", "terminate"])
    ap.add_argument("--idle-timeout-sec", type=int, default=0, help="deprecated hard idle kill; default disabled")
    ap.add_argument("--silent-soft-limit-sec", type=int, default=120)
    ap.add_argument("--stale-notice-sec", type=int, default=1800)
    ap.add_argument("--progress-report-sec", type=int, default=900)
    ap.add_argument("--heartbeat-sec", type=int, default=30)
    ap.add_argument("--inferred-completion-sec", type=int, default=5)
    ap.add_argument("--handshake-timeout-sec", type=int, default=20)
    ap.add_argument("--launch-retries", type=int, default=2)
    ap.add_argument("--launch-backoff", default="1,2")
    ap.add_argument("--expected-effect-kind", default="workspace_delta", choices=["workspace_delta", "evidence_delta", "any_delta", "none"])
    ap.add_argument("--expected-effect-required", default="true", choices=["true", "false"])
    ap.add_argument("--codex-bin", default=None)
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--clean-codex-home", action="store_true")
    ap.add_argument("--mcp-policy", default=None)
    ap.add_argument("--mcp-allowlist", default="")
    ap.add_argument("--binding-mcp-policy", default=None)
    ap.add_argument("--suppressed-mcp-servers", default="")
    args = ap.parse_args()
    args.expected_effect_required = args.expected_effect_required == "true"
    args.mcp_allowlist = [x for x in str(args.mcp_allowlist).split(",") if x]
    args.suppressed_mcp_servers = [x for x in str(args.suppressed_mcp_servers).split(",") if x]
    cwd = Path(args.cwd).resolve()
    outcome = Path(args.outcome_file).resolve()
    if not outcome.exists():
        print(f"outcome file not found: {outcome}", file=sys.stderr)
        return 4
    evidence = Path(args.evidence_dir).resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    backoffs = [int(x) for x in args.launch_backoff.split(",") if x.strip()] or [1]
    with (evidence / "raw_vendor_output.jsonl").open("a", encoding="utf-8") as raw, (evidence / "rpc_requests.jsonl").open("a", encoding="utf-8") as rpc, (evidence / "vendor_stderr.txt").open("a", encoding="utf-8") as err, (evidence / "driver_events.jsonl").open("a", encoding="utf-8") as meta:
        proc = None
        thread_id = None
        outcome_sha = None
        outcome_path = str(outcome)
        for attempt in range(args.launch_retries + 1):
            emit_meta(meta, event="launch_attempt", attempt=attempt)
            try:
                proc, thread_id, outcome_sha, outcome_path = launch_and_handshake(args, raw, rpc, err, meta)
                emit_meta(meta, event="launch_ok", attempt=attempt)
                break
            except LaunchFatal as exc:
                emit_meta(meta, event="launch_fatal", attempt=attempt, reason=str(exc), reason_code="launch_fatal")
                return 4
            except LaunchTransient as exc:
                emit_meta(meta, event="launch_failed", attempt=attempt, reason=str(exc), reason_code="launch_transient")
                if attempt < args.launch_retries:
                    time.sleep(backoffs[min(attempt, len(backoffs) - 1)])
        else:
            emit_meta(meta, event="launch_exhausted", attempts=args.launch_retries + 1)
            return 3
        try:
            assert proc is not None and thread_id is not None and outcome_sha is not None
            obs = TurnObservation(cwd, evidence)
            turn_rc = wait_for_turn_completion(proc, raw, err, meta, obs, args)
            if turn_rc != 0:
                return turn_rc
            final = final_goal_check(proc, raw, rpc, err, meta, thread_id, args.handshake_timeout_sec)
            if final != "complete":
                emit_meta(meta, event="goal_non_success", goal_status=final, reason_code=f"goal_{final}_after_turn")
                return 6
            if not validate_outcome_read_marker(obs, outcome_path, outcome_sha, meta):
                emit_meta(meta, event="turn_semantic_failed", reason_code="outcome_read_evidence_missing")
                return 6
            emit_meta(meta, event="driver_success", goal_status=final)
            return 0
        finally:
            cleanup_thread(proc, raw, rpc, err, meta, thread_id)
            kill_proc(proc)
            ACTIVE_CLEANUP.clear()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print(f"codex_driver failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
