from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json

class EventError(ValueError):
    pass

TERMINAL = {"completed", "failed"}
VALID_EVENTS = {"started", "completed", "failed"}

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
