from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import re
try:
    import yaml
except Exception as exc:  # pragma: no cover
    yaml = None

TYPE = {"code", "docs", "infra", "refactor", "spec"}
RISK = {"low", "medium", "high"}
STATUS = {"pending", "in_progress", "completed", "escalated", "parked"}
ID_RE = re.compile(r"^[A-Z]+-\d{3}$")

class BacklogError(ValueError): pass

@dataclass
class Task:
    raw: dict
    @property
    def id(self): return self.raw["id"]
    @property
    def status(self): return self.raw["status"]
    @property
    def blocked_by(self): return self.raw.get("blocked_by") or []

def load_yaml(path: Path) -> dict:
    if yaml is None:
        raise BacklogError("PyYAML is required for bs backlog parsing")
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise BacklogError("backlog root must be a mapping")
    return data

def validate(data: dict) -> list[Task]:
    if data.get("schema_version") != 1:
        raise BacklogError("schema_version must be 1")
    tasks = data.get("tasks")
    if not isinstance(tasks, list):
        raise BacklogError("tasks must be a list")
    seen, out = {}, []
    for i, t in enumerate(tasks):
        if not isinstance(t, dict):
            raise BacklogError(f"tasks[{i}] must be a mapping")
        for f in ["id", "title", "type", "risk_level", "status", "blocked_by", "spec_refs"]:
            if f not in t or t[f] in (None, ""):
                raise BacklogError(f"tasks[{i}].{f} is required")
        if not ID_RE.match(t["id"]):
            raise BacklogError(f"invalid id: {t['id']}")
        if t["id"] in seen:
            raise BacklogError(f"duplicate id: {t['id']}")
        seen[t["id"]] = t
        if t["type"] not in TYPE: raise BacklogError(f"{t['id']}.type invalid")
        if t["risk_level"] not in RISK: raise BacklogError(f"{t['id']}.risk_level invalid")
        if t["status"] not in STATUS: raise BacklogError(f"{t['id']}.status invalid")
        if not isinstance(t["blocked_by"], list): raise BacklogError(f"{t['id']}.blocked_by must be list")
        if not isinstance(t["spec_refs"], list) or not t["spec_refs"]: raise BacklogError(f"{t['id']}.spec_refs must be non-empty list")
        terminal = t["status"] in {"completed", "escalated", "parked"}
        if bool(t.get("closed_in")) != terminal: raise BacklogError(f"{t['id']}.closed_in terminal invariant failed")
        if t["status"] == "escalated" and not t.get("escalation_reason"): raise BacklogError(f"{t['id']}.escalation_reason required")
        if t["status"] != "escalated" and t.get("escalation_reason"): raise BacklogError(f"{t['id']}.escalation_reason must be null")
        if t["status"] == "parked" and not t.get("parked_reason"): raise BacklogError(f"{t['id']}.parked_reason required")
        if t["status"] != "parked" and t.get("parked_reason"): raise BacklogError(f"{t['id']}.parked_reason must be null")
        out.append(Task(t))
    for t in out:
        for dep in t.blocked_by:
            if dep not in seen:
                raise BacklogError(f"{t.id}.blocked_by: unknown id {dep}")
    visiting, visited = set(), set()
    def dfs(tid, stack):
        if tid in visiting: raise BacklogError("cycle detected: " + " -> ".join(stack + [tid]))
        if tid in visited: return
        visiting.add(tid)
        for dep in seen[tid].get("blocked_by") or []: dfs(dep, stack + [tid])
        visiting.remove(tid); visited.add(tid)
    for tid in seen: dfs(tid, [])
    return out

def next_task(tasks: list[Task]) -> Task:
    by_id = {t.id: t for t in tasks}
    pending = [t for t in tasks if t.status == "pending" and t.id != "B-000"]
    if not pending: raise BacklogError("no pending tasks")
    unblocked = [t for t in pending if all(by_id[d].status == "completed" for d in t.blocked_by)]
    if not unblocked: raise BacklogError("all pending tasks are blocked")
    return min(unblocked, key=lambda t: t.id)
