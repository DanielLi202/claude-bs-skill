from pathlib import Path
import json

class EventError(ValueError): pass
TERMINAL = {"completed", "failed"}

def append_event(path: Path, **event):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + '\n')

def step_states(path: Path) -> dict:
    states = {}
    if not path.exists(): return states
    for n, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip(): continue
        e = json.loads(line)
        if e.get('event') not in {'started','completed','failed'}:
            raise EventError(f"line {n}: invalid event")
        states[e['step']] = 'in_progress' if e['event'] == 'started' else e['event']
    return states

def incomplete_steps(path: Path) -> list[str]:
    return [s for s, state in step_states(path).items() if state == 'in_progress']
