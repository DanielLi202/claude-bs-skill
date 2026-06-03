from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json

class EventError(ValueError):
    pass

TERMINAL = {"completed", "failed"}
VALID_EVENTS = {"started", "completed", "failed"}
VALID_REASON_CODES = {"semantic_blocked_final_answer", "semantic_refusal_final_answer", "semantic_required_effect_missing", "transport_eof_before_completion", "launch_transient", "launch_fatal", "verify_command_failed", "verify_evidence_missing", "wall_clock_policy_exceeded"}

@dataclass(frozen=True)
class EventKey:
    step: str
    attempt: int


def append_event(path: Path, **event):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + '\n')


def _attempt(event: dict) -> int:
    raw = event.get('attempt', event.get('retry', 0))
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
        raise EventError(f"invalid attempt for {event.get('step')}: {raw!r}")
    return raw


def iter_events(path: Path):
    if not path.exists():
        return
    for n, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise EventError(f"line {n}: invalid json: {exc}") from exc
        if not isinstance(event, dict):
            raise EventError(f"line {n}: event must be an object")
        name = event.get('event')
        if name not in VALID_EVENTS:
            raise EventError(f"line {n}: invalid event {name!r}")
        step = event.get('step')
        if not isinstance(step, str) or not step:
            raise EventError(f"line {n}: missing step")
        reason_code = event.get('reason_code')
        if reason_code is not None and reason_code not in VALID_REASON_CODES:
            raise EventError(f"line {n}: invalid reason_code {reason_code!r}")
        if name in TERMINAL:
            for field in ("workspace_delta_files", "evidence_delta_files"):
                if field in event and not isinstance(event[field], list):
                    raise EventError(f"line {n}: {field} must be list when present")
            if "write_actions" in event and (isinstance(event["write_actions"], bool) or not isinstance(event["write_actions"], int) or event["write_actions"] < 0):
                raise EventError(f"line {n}: write_actions must be non-negative int")
            if "driver_exit" in event and (isinstance(event["driver_exit"], bool) or not isinstance(event["driver_exit"], int)):
                raise EventError(f"line {n}: driver_exit must be int")
            if "conduct_result" in event and (not isinstance(event["conduct_result"], str) or not event["conduct_result"]):
                raise EventError(f"line {n}: conduct_result must be non-empty string")
        yield n, EventKey(step, _attempt(event)), name, event


def attempt_states(path: Path) -> dict[EventKey, str]:
    states: dict[EventKey, str] = {}
    open_lines: dict[EventKey, int] = {}
    if not path.exists():
        return states
    for n, key, name, _event in iter_events(path):
        if name == 'started':
            if key in open_lines:
                raise EventError(f"line {n}: nested started for {key.step} attempt {key.attempt}; previous start line {open_lines[key]}")
            if states.get(key) in TERMINAL:
                raise EventError(f"line {n}: started after terminal event for {key.step} attempt {key.attempt}")
            open_lines[key] = n
            states[key] = 'in_progress'
            continue
        if key not in open_lines:
            raise EventError(f"line {n}: {name} without matching started for {key.step} attempt {key.attempt}")
        del open_lines[key]
        states[key] = name
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
