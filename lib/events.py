from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import re

class EventError(ValueError):
    pass

TERMINAL = {"completed", "failed"}
VALID_EVENTS = {"started", "completed", "failed", "repair"}
VALID_REASON_CODES = {"semantic_blocked_final_answer", "semantic_refusal_final_answer", "semantic_required_effect_missing", "transport_eof_before_completion", "launch_transient", "launch_fatal", "verify_command_failed", "verify_evidence_missing", "wall_clock_policy_exceeded"}
VALID_RETRY_KINDS = {"transport_retry", "semantic_fix_round", "launch_retry"}
VALID_REPAIR_KINDS = {"missing_started"}
ISO_Z_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")

@dataclass(frozen=True)
class EventKey:
    step: str
    attempt: int


def utc_now_z() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def append_event(path: Path, **event):
    path = Path(path)
    if "recorded_at" not in event and "ts" not in event:
        event["recorded_at"] = utc_now_z()
    if "recorded_at" in event and "occurred_at" not in event:
        event["occurred_at"] = event["recorded_at"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + '\n')


def append_started(path: Path, step: str, attempt: int = 0, **fields):
    append_event(path, step=step, attempt=attempt, event="started", **fields)


def append_completed(path: Path, step: str, attempt: int = 0, **fields):
    append_event(path, step=step, attempt=attempt, event="completed", **fields)


def append_failed(path: Path, step: str, attempt: int = 0, **fields):
    append_event(path, step=step, attempt=attempt, event="failed", **fields)


def append_repair(path: Path, *, target_step: str, target_attempt: int, target_line: int, target_event_hash: str, reason: str, operator: str | None = None, **fields):
    payload = {
        "event": "repair",
        "repair_kind": "missing_started",
        "target_step": target_step,
        "target_attempt": target_attempt,
        "target_line": target_line,
        "target_event_hash": target_event_hash,
        "reason": reason,
    }
    if operator:
        payload["operator"] = operator
    payload.update(fields)
    append_event(path, **payload)


def _attempt(event: dict) -> int:
    raw = event.get('attempt', event.get('retry', 0))
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
        raise EventError(f"invalid attempt for {event.get('step')}: {raw!r}")
    return raw


def _non_negative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _validate_event_shape(event: dict, line: int | None = None) -> tuple[EventKey | None, str]:
    prefix = f"line {line}: " if line is not None else ""
    name = event.get('event')
    if name not in VALID_EVENTS:
        raise EventError(f"{prefix}invalid event {name!r}")
    for field in ("recorded_at", "occurred_at", "ts"):
        value = event.get(field)
        if value is not None and (not isinstance(value, str) or not ISO_Z_RE.match(value)):
            raise EventError(f"{prefix}invalid {field} {value!r}")
    if "recorded_at" in event and "occurred_at" not in event:
        raise EventError(f"{prefix}occurred_at required when recorded_at is present")
    if "occurred_at" in event and "recorded_at" not in event:
        raise EventError(f"{prefix}recorded_at required when occurred_at is present")
    if name == "repair":
        repair_kind = event.get("repair_kind")
        if repair_kind not in VALID_REPAIR_KINDS:
            raise EventError(f"{prefix}invalid repair_kind {repair_kind!r}")
        target_step = event.get("target_step")
        if not isinstance(target_step, str) or not target_step:
            raise EventError(f"{prefix}target_step is required for repair")
        target_attempt = event.get("target_attempt", 0)
        if not _non_negative_int(target_attempt):
            raise EventError(f"{prefix}target_attempt must be non-negative int")
        if not _non_negative_int(event.get("target_line")) or int(event["target_line"]) < 1:
            raise EventError(f"{prefix}target_line must be positive int")
        target_hash = event.get("target_event_hash")
        if not isinstance(target_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", target_hash):
            raise EventError(f"{prefix}target_event_hash must be sha256 hex")
        reason = event.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise EventError(f"{prefix}repair reason must be non-empty string")
        operator = event.get("operator")
        if operator is not None and (not isinstance(operator, str) or not operator.strip()):
            raise EventError(f"{prefix}operator must be non-empty string when present")
        return None, name
    step = event.get('step')
    if not isinstance(step, str) or not step:
        raise EventError(f"{prefix}missing step")
    reason_code = event.get('reason_code')
    if reason_code is not None and reason_code not in VALID_REASON_CODES:
        raise EventError(f"{prefix}invalid reason_code {reason_code!r}")
    retry_kind = event.get('retry_kind')
    attempt = _attempt(event)
    if retry_kind is not None and retry_kind not in VALID_RETRY_KINDS:
        raise EventError(f"{prefix}invalid retry_kind {retry_kind!r}")
    if retry_kind is not None and attempt == 0:
        raise EventError(f"{prefix}retry_kind is only valid on non-zero attempts")
    if attempt > 0 and retry_kind is not None:
        changed = event.get('changed')
        if not isinstance(changed, str) or not changed.strip():
            raise EventError(f"{prefix}changed must be non-empty string when retry_kind is present")
    if name in TERMINAL:
        for field in ("workspace_delta_files", "evidence_delta_files", "repo_delta_files", "filesystem_delta_files"):
            if field in event and not isinstance(event[field], list):
                raise EventError(f"{prefix}{field} must be list when present")
        for field in ("write_actions", "file_change_events", "workspace_delta_count"):
            if field in event and not _non_negative_int(event[field]):
                raise EventError(f"{prefix}{field} must be non-negative int")
        if "driver_exit" in event and (isinstance(event["driver_exit"], bool) or not isinstance(event["driver_exit"], int)):
            raise EventError(f"{prefix}driver_exit must be int")
        if "conduct_result" in event and (not isinstance(event["conduct_result"], str) or not event["conduct_result"]):
            raise EventError(f"{prefix}conduct_result must be non-empty string")
    return EventKey(step, attempt), name


def iter_events(path: Path):
    path = Path(path)
    if not path.exists():
        return
    for n, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if not line.strip():
            continue
        raw_line = line
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise EventError(f"line {n}: invalid json: {exc}") from exc
        if not isinstance(event, dict):
            raise EventError(f"line {n}: event must be an object")
        key, name = _validate_event_shape(event, n)
        event["_line_hash"] = hashlib.sha256(raw_line.encode("utf-8")).hexdigest()
        yield n, key, name, event


def attempt_states(path: Path) -> dict[EventKey, str]:
    states: dict[EventKey, str] = {}
    open_lines: dict[EventKey, int] = {}
    orphan_terminals: dict[int, tuple[EventKey, str, str]] = {}
    if not path.exists():
        return states
    for n, key, name, _event in iter_events(path):
        if name == "repair":
            if _event.get("repair_kind") != "missing_started":
                raise EventError(f"line {n}: unsupported repair_kind {_event.get('repair_kind')!r}")
            target_line = _event["target_line"]
            orphan = orphan_terminals.pop(target_line, None)
            target = EventKey(_event["target_step"], _event.get("target_attempt", 0))
            if orphan is None or orphan[0] != target:
                raise EventError(f"line {n}: repair target does not match an unrepaired orphan terminal")
            if _event.get("target_event_hash") != orphan[2]:
                raise EventError(f"line {n}: repair target_event_hash does not match line {_event['target_line']}")
            if states.get(target) in TERMINAL:
                raise EventError(f"line {n}: repair target already has terminal event for {target.step} attempt {target.attempt}")
            states[target] = orphan[1]
            continue
        if name == 'started':
            if key in open_lines:
                raise EventError(f"line {n}: nested started for {key.step} attempt {key.attempt}; previous start line {open_lines[key]}")
            if states.get(key) in TERMINAL:
                raise EventError(f"line {n}: started after terminal event for {key.step} attempt {key.attempt}")
            open_lines[key] = n
            states[key] = 'in_progress'
            continue
        if key not in open_lines:
            if states.get(key) in TERMINAL:
                raise EventError(f"line {n}: duplicate terminal event for {key.step} attempt {key.attempt}")
            orphan_terminals[n] = (key, name, _event.get("_line_hash", ""))
            continue
        del open_lines[key]
        states[key] = name
    if orphan_terminals:
        n, (key, name, _line_hash) = next(iter(orphan_terminals.items()))
        raise EventError(f"line {n}: {name} without matching started for {key.step} attempt {key.attempt}")
    if open_lines:
        details = ', '.join(f"{key.step}[attempt={key.attempt}] line {line}" for key, line in sorted(open_lines.items(), key=lambda item: (item[0].step, item[0].attempt)))
        raise EventError(f"unclosed started events: {details}")
    return states


def step_states(path: Path) -> dict[str, str]:
    latest: dict[str, tuple[int, str]] = {}
    for key, state in attempt_states(path).items():
        current = latest.get(key.step)
        if current is None or key.attempt >= current[0]:
            latest[key.step] = (key.attempt, state)
    return {step: state for step, (_attempt_id, state) in latest.items()}


def incomplete_steps(path: Path) -> list[str]:
    return [s for s, state in step_states(path).items() if state == 'in_progress']
