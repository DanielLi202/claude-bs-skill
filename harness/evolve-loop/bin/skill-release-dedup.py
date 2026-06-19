#!/usr/bin/env python3
"""Stage-4 deterministic r2 item dedup/recovery helper.

The helper is intentionally data-only: while SKILL.lock is held, feed it the
current r2 item list plus ids already covered by current origin/main. It records
covered/needs-human/done state in closure.yaml and emits the remaining item ids
that still need implementation. If no release is needed it writes a non-empty
skill_release sentinel so closure.py can advance to remediation/close.
"""
from __future__ import annotations

import argparse
import json
import pathlib
from datetime import datetime, timezone
from typing import Any

import yaml


def now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_yaml(path: pathlib.Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else None


def save_yaml(path: pathlib.Path, data: Any) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def item_id(item: Any) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict) and item.get("id"):
        return str(item["id"])
    raise SystemExit(f"invalid item without id: {item!r}")


def deterministic(item: Any) -> bool:
    if isinstance(item, str):
        return True
    if item.get("needs_human") is True:
        return False
    if item.get("deterministic") is False:
        return False
    return True


def covered_ids(path: pathlib.Path | None) -> set[str]:
    if not path:
        return set()
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if not text.strip():
        return set()
    try:
        data = yaml.safe_load(text)
        if isinstance(data, list):
            return {str(x) for x in data}
    except Exception:
        pass
    return {line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")}


def load_closure(path: pathlib.Path) -> dict[str, Any]:
    data = load_yaml(path) or {}
    if not isinstance(data, dict):
        raise SystemExit("closure must be a mapping")
    return data


def classify(items: list[Any], closure: dict[str, Any], covered: set[str]) -> dict[str, Any]:
    done = closure.get("skill_release_items_done") or {}
    if not isinstance(done, dict):
        done = {}
    rows = []
    implement = []
    for raw in items:
        iid = item_id(raw)
        if iid in covered:
            status = "covered_upstream"
        elif iid in done:
            status = "already_done"
        elif not deterministic(raw):
            status = "needs_human"
        else:
            status = "implement"
            implement.append(iid)
        rows.append({"id": iid, "status": status})
    if implement:
        reason = None
    elif not items:
        reason = "no_deterministic_items"
    elif all(r["status"] == "covered_upstream" for r in rows):
        reason = "all_covered_upstream"
    elif all(r["status"] in {"needs_human", "already_done"} for r in rows):
        reason = "all_needs_human_or_done"
    else:
        reason = "no_uncovered_items"
    return {"items": rows, "implement": implement, "noop_reason": reason}


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("--closure", required=True, type=pathlib.Path)
    plan.add_argument("--items", required=True, type=pathlib.Path)
    plan.add_argument("--covered-upstream", type=pathlib.Path)
    plan.add_argument("--write", action="store_true")
    mark = sub.add_parser("mark-done")
    mark.add_argument("--closure", required=True, type=pathlib.Path)
    mark.add_argument("--item-id", required=True)
    mark.add_argument("--commit", required=True)
    args = ap.parse_args()

    closure_path = args.closure
    closure = load_closure(closure_path)
    if args.cmd == "mark-done":
        done = closure.setdefault("skill_release_items_done", {})
        done[args.item_id] = {"commit": args.commit, "updated_at": now_z()}
        closure["updated_at"] = now_z()
        save_yaml(closure_path, closure)
        print(json.dumps({"status": "marked", "item_id": args.item_id}, sort_keys=True))
        return 0

    raw_items = load_yaml(args.items) or []
    if not isinstance(raw_items, list):
        raise SystemExit("items must be a YAML list")
    result = classify(raw_items, closure, covered_ids(args.covered_upstream))
    if args.write:
        closure["skill_release_dedup"] = {"updated_at": now_z(), **result}
        covered = [r["id"] for r in result["items"] if r["status"] == "covered_upstream"]
        if covered:
            closure["covered_upstream"] = sorted(set((closure.get("covered_upstream") or []) + covered))
        needs = [r["id"] for r in result["items"] if r["status"] == "needs_human"]
        if needs:
            closure["escalated_to_human"] = sorted(set((closure.get("escalated_to_human") or []) + needs))
        if not result["implement"] and not closure.get("skill_release"):
            closure["skill_release"] = {
                "status": "no_release",
                "reason": result["noop_reason"],
                "updated_at": now_z(),
                "covered_upstream": covered,
                "needs_human": needs,
            }
        closure["updated_at"] = now_z()
        save_yaml(closure_path, closure)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
