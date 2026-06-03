#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, subprocess, sys, time
from pathlib import Path
try:
    import yaml
except Exception:
    yaml = None

CODE_TYPES_REQUIRING_VERIFY = {"code"}

def load_yaml(path: Path) -> dict:
    if yaml is None: raise RuntimeError("PyYAML is required for grade_verify.py")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict): raise RuntimeError(f"{path} root must be a mapping")
    return data

def commands_for(binding: dict, task_type: str) -> tuple[list[str], bool]:
    verify = binding.get("verify")
    if isinstance(verify, dict):
        grade = verify.get("grade")
        if isinstance(grade, dict):
            commands = grade.get(task_type)
            if isinstance(commands, list) and all(isinstance(c, str) and c.strip() for c in commands): return commands, True
            if commands is not None: raise RuntimeError(f"verify.grade.{task_type} must be a non-empty list of strings")
        if isinstance(verify.get("not_required"), list) and task_type in verify["not_required"]: return [], False
    legacy = binding.get("verify_command")
    if task_type == "docs" and isinstance(legacy, str) and legacy.strip(): return [legacy], True
    if task_type in CODE_TYPES_REQUIRING_VERIFY: raise RuntimeError(f"task type {task_type!r} requires verify.grade.{task_type}")
    return [], False

def env_clear(binding: dict) -> list[str]:
    verify = binding.get("verify")
    if not isinstance(verify, dict): return []
    env = verify.get("env")
    if not isinstance(env, dict): return []
    clear = env.get("clear")
    if clear is None: return []
    if not isinstance(clear, list) or not all(isinstance(x, str) and x for x in clear): raise RuntimeError("verify.env.clear must be a list of strings")
    return clear

def write_result(path: Path, result: dict) -> None:
    if yaml is not None:
        path.write_text(yaml.safe_dump(result, sort_keys=False), encoding="utf-8")
    else:
        path.write_text(json.dumps(result, indent=2), encoding="utf-8")

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycle-dir", required=True); ap.add_argument("--binding-file", required=True)
    ap.add_argument("--task-id", required=True); ap.add_argument("--task-type", required=True)
    ap.add_argument("--round", required=True, type=int); ap.add_argument("--worktree", default=".")
    args = ap.parse_args()
    cycle_dir = Path(args.cycle_dir).resolve(); binding_file = Path(args.binding_file).resolve(); worktree = Path(args.worktree).resolve()
    evidence_dir = cycle_dir / "evidence" / f"grade_verify_round_{args.round}"; evidence_dir.mkdir(parents=True, exist_ok=True)
    out_file = cycle_dir / "evidence" / f"grade_verify_round_{args.round}.yaml"
    try:
        binding = load_yaml(binding_file); commands, required = commands_for(binding, args.task_type); cleared = env_clear(binding)
    except Exception as exc:
        write_result(out_file, {"grade_verify": {"round": args.round, "task_id": args.task_id, "task_type": args.task_type, "status": "fail", "error": str(exc), "commands": []}})
        print(out_file); return 2
    if not required:
        write_result(out_file, {"grade_verify": {"round": args.round, "task_id": args.task_id, "task_type": args.task_type, "status": "not_required", "env_cleared": cleared, "commands": []}})
        print(out_file); return 0
    run_env = os.environ.copy()
    for key in cleared: run_env.pop(key, None)
    results=[]; overall="pass"
    for idx, command in enumerate(commands, 1):
        stdout_log=evidence_dir/f"cmd_{idx}.stdout.log"; stderr_log=evidence_dir/f"cmd_{idx}.stderr.log"; start=time.monotonic()
        proc=subprocess.run(command, cwd=str(worktree), env=run_env, shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout_log.write_text(proc.stdout, encoding="utf-8"); stderr_log.write_text(proc.stderr, encoding="utf-8")
        if proc.returncode != 0: overall="fail"
        results.append({"name": command, "exit": proc.returncode, "duration_sec": round(time.monotonic()-start,3), "stdout_log": stdout_log.relative_to(cycle_dir).as_posix(), "stderr_log": stderr_log.relative_to(cycle_dir).as_posix()})
    write_result(out_file, {"grade_verify": {"round": args.round, "task_id": args.task_id, "task_type": args.task_type, "status": overall, "env_cleared": cleared, "commands": results}})
    print(out_file); return 0 if overall == "pass" else 1
if __name__ == "__main__": raise SystemExit(main())
