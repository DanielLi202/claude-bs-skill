#!/usr/bin/env python3
"""Load bs-evolve target config and emit the per-turn environment.

This helper is intentionally small: the slash-command body owns orchestration, while
this helper makes the target-specific binding explicit and testable.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shlex
import subprocess
import sys
from typing import Any

import yaml

SCRIPT = pathlib.Path(__file__).resolve()
DEFAULT_SKILL_REPO = SCRIPT.parents[3]
LOOP_STATE = SCRIPT.with_name("loop-state.py")
REQUIRED = ("target_repo", "project_slug", "state_dir", "reviews_root", "corpus_dir")
EXPORT_KEYS = (
    "BS_LOOP_SKILL_REPO",
    "BS_LOOP_TARGET_REPO",
    "BS_LOOP_PROJECT_SLUG",
    "BS_LOOP_STATE_DIR",
    "BS_LOOP_REVIEWS_ROOT",
    "BS_LOOP_CORPUS_DIR",
    "BS_LOOP_HARNESS",
    "BS_LOOP_WAKE_PROMPT",
    "BS_LOOP_MODE",
    "BS_LOOP_MAX_ITERATIONS",
    "BS_LOOP_ADOPT_MIN_CYCLE",
)


class ConfigError(RuntimeError):
    pass


def _resolve(base: pathlib.Path, value: str) -> str:
    p = pathlib.Path(os.path.expandvars(os.path.expanduser(value)))
    if not p.is_absolute():
        p = base / p
    return str(p.resolve())


def discover_config_from_cwd(cwd: pathlib.Path) -> pathlib.Path:
    proc = subprocess.run(
        ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise ConfigError(
            "current directory is not inside a git repository; run /bs-evolve "
            "from an initialized target repo or pass --config <path>"
        )
    target = pathlib.Path(proc.stdout.strip()).resolve()
    config = target / ".bs-evolve" / "config.yaml"
    if not config.exists():
        raise ConfigError(f"{target} 未初始化（无 .bs-evolve/config.yaml）；先运行一次 /bs-evolve-init")
    return config


def load_config(path: pathlib.Path) -> dict[str, Any]:
    path = path.expanduser().resolve()
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError as exc:
        raise ConfigError(f"config not found: {path}") from exc
    if not isinstance(raw, dict):
        raise ConfigError("config must be a YAML mapping")
    missing = [k for k in REQUIRED if not raw.get(k)]
    if missing:
        raise ConfigError(f"missing required config field(s): {', '.join(missing)}")

    base = path.resolve().parent
    slug = str(raw["project_slug"])
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", slug):
        raise ConfigError("project_slug must be 1-64 chars of letters/digits/_.- and start alnum")

    mode = str(raw.get("mode", "dry-run"))
    if mode not in {"auto", "dry-run"}:
        raise ConfigError("mode must be auto or dry-run")

    skill_repo = _resolve(base, str(raw.get("skill_repo") or DEFAULT_SKILL_REPO))
    target_repo = _resolve(base, str(raw["target_repo"]))
    state_dir = _resolve(base, str(raw["state_dir"]))
    reviews_root = _resolve(base, str(raw["reviews_root"]))
    corpus_dir = _resolve(base, str(raw["corpus_dir"]))
    target_path = pathlib.Path(target_repo).resolve()
    for label, resolved in {"state_dir": state_dir, "reviews_root": reviews_root, "corpus_dir": corpus_dir}.items():
        try:
            pathlib.Path(resolved).resolve().relative_to(target_path)
        except ValueError as exc:
            raise ConfigError(f"{label} must resolve inside target_repo") from exc
    harness = str((pathlib.Path(skill_repo) / "harness" / "evolve-loop").resolve())
    wake_prompt = str(raw.get("wake_prompt") or f"读取 {path.resolve()} 并执行 /bs-evolve --config {path.resolve()}")

    if "adopt_min_cycle" in raw:
        adopt_min_cycle = int(raw["adopt_min_cycle"])
    elif "migrated_through_cycle" in raw:
        adopt_min_cycle = int(raw["migrated_through_cycle"]) + 1
    else:
        adopt_min_cycle = 0

    return {
        "BS_LOOP_SKILL_REPO": skill_repo,
        "BS_LOOP_TARGET_REPO": target_repo,
        "BS_LOOP_PROJECT_SLUG": slug,
        "BS_LOOP_STATE_DIR": state_dir,
        "BS_LOOP_REVIEWS_ROOT": reviews_root,
        "BS_LOOP_CORPUS_DIR": corpus_dir,
        "BS_LOOP_HARNESS": harness,
        "BS_LOOP_WAKE_PROMPT": wake_prompt,
        "BS_LOOP_MODE": mode,
        "BS_LOOP_MAX_ITERATIONS": str(int(raw.get("max_iterations", 5))),
        "BS_LOOP_ADOPT_MIN_CYCLE": str(adopt_min_cycle),
    }


def emit_env(cfg: dict[str, Any]) -> None:
    for key in EXPORT_KEYS:
        print(f"export {key}={shlex.quote(str(cfg[key]))}")


def init_state_if_needed(cfg: dict[str, Any]) -> None:
    state_file = pathlib.Path(cfg["BS_LOOP_STATE_DIR"]) / "state.json"
    if state_file.exists():
        return
    subprocess.run(
        [
            sys.executable,
            str(LOOP_STATE),
            "--state-dir",
            cfg["BS_LOOP_STATE_DIR"],
            "init",
            "--target",
            cfg["BS_LOOP_TARGET_REPO"],
            "--skill",
            cfg["BS_LOOP_SKILL_REPO"],
            "--mode",
            cfg["BS_LOOP_MODE"],
            "--max",
            cfg["BS_LOOP_MAX_ITERATIONS"],
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )


def state_get(cfg: dict[str, Any], key: str) -> str:
    return subprocess.check_output(
        [sys.executable, str(LOOP_STATE), "--state-dir", cfg["BS_LOOP_STATE_DIR"], "get", key],
        text=True,
    ).strip()


def state_call(cfg: dict[str, Any], *args: str) -> str:
    return subprocess.check_output(
        [sys.executable, str(LOOP_STATE), "--state-dir", cfg["BS_LOOP_STATE_DIR"], *args],
        text=True,
    ).strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=pathlib.Path)
    ap.add_argument("--emit-env", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    try:
        config_path = args.config.expanduser().resolve() if args.config else discover_config_from_cwd(pathlib.Path.cwd())
        cfg = load_config(config_path)
        if args.emit_env:
            emit_env(cfg)
        elif args.json:
            print(json.dumps(cfg, indent=2, sort_keys=True))
        else:
            ap.error("choose --emit-env or --json")
    except ConfigError as exc:
        print(f"bs-evolve config error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
