#!/usr/bin/env python3
"""Advance a repo's status marker (the next-/bs-task pointer) from the backlog.

Optional, opt-in feature: only acts when the binding declares a `status_marker`
block. Idempotent. Step 10 of the cycle runs this after writing ledger+backlog and
before the atomic close commit, so the freshly-written backlog (current task now
`completed`) yields the *next* selectable task, and the marker is staged in the same
atomic close commit. When the binding has no `status_marker`, this is a no-op and the
close stages only ledger + backlog exactly as before.

Binding shape (all under `status_marker`):

    status_marker:
      file: AGENTS.md                        # required: file holding the marker
      next_task_marker: "§1-next-bs-task"    # required: HTML-comment token
      next_task_line:                        # optional: a human-visible line to render
        start: "<!-- next-task:start -->"
        end: "<!-- next-task:end -->"
        template: "**{id}** — {title}"
      post_sync_command: "scripts/sync-claude-md.sh"  # optional: shell, run in repo root

The marker rewritten in `file` looks like:  <!-- §1-next-bs-task: B-NNN -->

Target task = the in_progress task if one exists (a cycle is open), else the next
pending-unblocked task (lib.backlog.next_task), else no change (nothing selectable).
"""
from __future__ import annotations
import argparse, json, re, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # skill root, for `lib`
from lib import backlog as bl  # noqa: E402

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None

ID_TOKEN = r"[A-Z]+-\d{3}"


def target_task(tasks):
    """The marker target: the open (in_progress) task wins; else the next
    pending-unblocked task; else None (nothing selectable -> leave marker as-is)."""
    in_progress = [t for t in tasks if t.status == "in_progress"]
    if in_progress:
        return min(in_progress, key=lambda t: t.id)
    try:
        return bl.next_task(tasks)
    except bl.BacklogError:
        return None


def rewrite_marker(text: str, token: str, task_id: str):
    pat = re.compile(r"(<!--\s*" + re.escape(token) + r":\s*)(" + ID_TOKEN + r"|TBD|none)?(\s*-->)")
    return pat.subn(lambda m: m.group(1) + task_id + m.group(3), text)


def rewrite_line(text: str, start: str, end: str, rendered: str):
    pat = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    return pat.subn(lambda _m: start + rendered + end, text)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Advance the next-/bs-task status marker from the backlog.")
    ap.add_argument("--binding-file", required=True)
    ap.add_argument("--repo-root", default=".")
    a = ap.parse_args(argv)

    def emit(obj, code):
        print(json.dumps({"status_marker": obj}, ensure_ascii=False))
        return code

    if yaml is None:
        return emit({"status": "error", "error": "PyYAML is required for sync_status_marker.py"}, 2)

    repo = Path(a.repo_root).resolve()
    binding = yaml.safe_load(Path(a.binding_file).read_text(encoding="utf-8")) or {}
    cfg = binding.get("status_marker")
    if cfg is None:
        return emit({"configured": False, "status": "noop"}, 0)
    if not isinstance(cfg, dict):
        return emit({"status": "error", "error": "status_marker must be a mapping"}, 2)

    fpath = cfg.get("file")
    token = cfg.get("next_task_marker")
    if not (isinstance(fpath, str) and fpath and isinstance(token, str) and token):
        return emit({"status": "error", "error": "status_marker.file and status_marker.next_task_marker are required strings"}, 2)

    backlog_rel = binding.get("backlog", ".bootstrap/backlog.yaml")
    try:
        tasks = bl.validate(bl.load_yaml(repo / backlog_rel))
    except bl.BacklogError as exc:
        return emit({"status": "error", "error": f"backlog invalid: {exc}"}, 2)

    target = target_task(tasks)
    if target is None:
        return emit({"status": "noop", "reason": "no selectable task", "file": fpath}, 0)

    target_path = repo / fpath
    if not target_path.exists():
        return emit({"status": "error", "error": f"status_marker.file not found: {fpath}", "next": target.id}, 2)

    original = target_path.read_text(encoding="utf-8")
    text, n_marker = rewrite_marker(original, token, target.id)
    if n_marker == 0:
        return emit({"status": "error", "error": f"marker token not found: <!-- {token}: ... -->", "file": fpath, "next": target.id}, 3)

    n_line = 0
    line_cfg = cfg.get("next_task_line")
    if isinstance(line_cfg, dict):
        start, end = line_cfg.get("start"), line_cfg.get("end")
        template = line_cfg.get("template", "{id}")
        if isinstance(start, str) and isinstance(end, str) and isinstance(template, str):
            rendered = template.format(id=target.id, title=str(target.raw.get("title", "")))
            text, n_line = rewrite_line(text, start, end, rendered)

    changed = text != original
    if changed:
        target_path.write_text(text, encoding="utf-8")

    post_exit = None
    cmd = cfg.get("post_sync_command")
    if changed and isinstance(cmd, str) and cmd.strip():
        post_exit = subprocess.run(cmd, cwd=str(repo), shell=True).returncode

    code = 0 if post_exit in (None, 0) else 4
    return emit({"status": "ok", "file": fpath, "marker": token, "next": target.id,
                 "marker_rewrites": n_marker, "line_rewrites": n_line, "changed": changed,
                 "post_sync_exit": post_exit}, code)


if __name__ == "__main__":
    raise SystemExit(main())
