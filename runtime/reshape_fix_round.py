#!/usr/bin/env python3
"""Prepare a bs fix round by re-shaping the live outcome capsule.

The helper is intentionally deterministic: it archives the previous capsule,
extracts structured grade findings from machine-readable YAML blocks, writes a
bounded fix-context section, and emits a marker consumed by conduct.sh.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None

MAX_FIX_ROUNDS = 3
CORRECTIONS_LIMIT = 1500
MARKER_RE = re.compile(
    r"<!--\s*bs-fix-round:\s*(?P<round>\d+);\s*archive=(?P<archive>[^;]+);\s*grade=(?P<grade>[^;]+);\s*failed=(?P<failed>\[[^\]]*\])\s*-->"
)


class ReshapeError(ValueError):
    pass


def _die(message: str, code: int = 2) -> int:
    print(f"reshape_fix_round: {message}", file=sys.stderr)
    return code


def _rel_or_abs(base: Path, raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def _yaml_blocks(text: str) -> list[dict]:
    if yaml is None:
        raise ReshapeError("PyYAML is required")
    blocks: list[dict] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if lines[i].strip() in {"```yaml", "```yml"}:
            start = i + 1
            i = start
            while i < len(lines) and lines[i].strip() != "```":
                i += 1
            if i >= len(lines):
                raise ReshapeError("unterminated yaml fence")
            raw = "\n".join(lines[start:i])
            try:
                data = yaml.safe_load(raw) if raw.strip() else None
            except Exception as exc:
                raise ReshapeError(f"malformed yaml block: {exc}") from exc
            if isinstance(data, dict):
                blocks.append(data)
        i += 1
    return blocks


def parse_grade(path: Path) -> tuple[dict, list[dict]]:
    if not path.exists():
        raise ReshapeError(f"grade file missing: {path}")
    blocks = _yaml_blocks(path.read_text(encoding="utf-8"))
    summary = None
    acceptance = None
    for block in blocks:
        if "grade_summary" in block:
            summary = block["grade_summary"]
        if "acceptance_status" in block:
            acceptance = block["acceptance_status"]
    if not isinstance(summary, dict):
        raise ReshapeError("missing or malformed grade_summary block")
    for key in ("p0_count", "p1_count", "p2_count"):
        value = summary.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ReshapeError(f"grade_summary.{key} must be a non-negative integer")
    if not isinstance(acceptance, list):
        raise ReshapeError("missing or malformed acceptance_status block")
    normalized: list[dict] = []
    for i, row in enumerate(acceptance):
        if not isinstance(row, dict):
            raise ReshapeError(f"acceptance_status[{i}] must be an object")
        item_id = row.get("id")
        status = row.get("status")
        severity = row.get("severity")
        if not isinstance(item_id, str) or not item_id:
            raise ReshapeError(f"acceptance_status[{i}].id is required")
        if status not in {"pass", "fail"}:
            raise ReshapeError(f"acceptance_status[{i}].status invalid")
        if severity not in {"P0", "P1", "P2", None}:
            raise ReshapeError(f"acceptance_status[{i}].severity invalid")
        if status == "fail" and severity is None:
            raise ReshapeError(f"acceptance_status[{i}].severity required for fail")
        normalized.append({"id": item_id, "status": status, "severity": severity})
    return summary, normalized


def blocking_count(summary: dict) -> int:
    return int(summary["p0_count"]) + int(summary["p1_count"])


def markers(text: str) -> list[re.Match[str]]:
    return list(MARKER_RE.finditer(text))


def marker_for_round(text: str, round_number: int) -> re.Match[str] | None:
    matches = [m for m in markers(text) if m.group("round") == str(round_number)]
    if len(matches) > 1:
        raise ReshapeError(f"inconsistent fix-round state: multiple markers for round {round_number}")
    return matches[0] if matches else None


def enforce_bounds(cycle_dir: Path, grade_file: Path, round_number: int, summary: dict) -> None:
    if round_number < 1:
        raise ReshapeError("--round must be >= 1")
    if round_number > MAX_FIX_ROUNDS:
        raise ReshapeError(f"round {round_number} exceeds max_fix_rounds={MAX_FIX_ROUNDS}")
    if round_number >= 2:
        previous = cycle_dir / f"grade_round_{round_number - 2}.md"
        prev_summary, _ = parse_grade(previous)
        if blocking_count(summary) >= blocking_count(prev_summary):
            raise ReshapeError(
                "P0+P1 did not strictly decrease: "
                f"previous={blocking_count(prev_summary)} current={blocking_count(summary)}"
            )


def read_corrections(path: Path | None) -> str:
    if path is None:
        return ""
    text = path.read_text(encoding="utf-8").strip()
    if len(text) > CORRECTIONS_LIMIT:
        raise ReshapeError(f"corrections exceed {CORRECTIONS_LIMIT} chars")
    return text


def reshape(cycle_dir: Path, outcome_file: Path, grade_file: Path, round_number: int, corrections_file: Path | None) -> str:
    if not cycle_dir.is_absolute():
        raise ReshapeError("--cycle-dir must be absolute")
    cycle_dir = cycle_dir.resolve()
    outcome_file = outcome_file.resolve()
    grade_file = grade_file.resolve()
    grade_name = grade_file.name
    g = round_number - 1
    expected_grade = f"grade_round_{g}.md"
    if grade_name != expected_grade:
        raise ReshapeError(f"--round {round_number} requires {expected_grade}, got {grade_name}")
    if not outcome_file.exists():
        raise ReshapeError(f"outcome file missing: {outcome_file}")
    if round_number < 1:
        raise ReshapeError("--round must be >= 1")
    if round_number > MAX_FIX_ROUNDS:
        raise ReshapeError(f"round {round_number} exceeds max_fix_rounds={MAX_FIX_ROUNDS}")

    summary, acceptance = parse_grade(grade_file)
    enforce_bounds(cycle_dir, grade_file, round_number, summary)

    archive_name = f"outcome.v{g}.md"
    archive = cycle_dir / archive_name
    text = outcome_file.read_text(encoding="utf-8")
    all_markers = markers(text)
    future_markers = [m.group("round") for m in all_markers if int(m.group("round")) > round_number]
    if future_markers:
        raise ReshapeError(f"inconsistent fix-round state: future marker(s) present before round {round_number}: {','.join(future_markers)}")
    existing_marker = marker_for_round(text, round_number)

    if archive.exists() and existing_marker:
        if existing_marker.group("archive") == archive_name and existing_marker.group("grade") == grade_name:
            return "no-op: fix round already reshaped"
        raise ReshapeError("inconsistent fix-round state: archive exists but marker references a different round/grade")
    if archive.exists() and not existing_marker:
        raise ReshapeError("inconsistent fix-round state: archive exists but current-round marker is missing")
    if existing_marker and not archive.exists():
        raise ReshapeError("inconsistent fix-round state: current-round marker exists without archive")

    failed_ids = [row["id"] for row in acceptance if row["status"] == "fail"]
    if not failed_ids:
        raise ReshapeError("acceptance_status contains no failed IDs to reshape")
    corrections = read_corrections(corrections_file)

    shutil.copy2(outcome_file, archive)
    failed_json = json.dumps(failed_ids, ensure_ascii=False, separators=(",", ":"))
    section_lines = [
        "",
        f"## Fix Round {round_number} (auto re-shape; bounded)",
        f"Unmet acceptance: {', '.join(failed_ids)}",
        f"Grade detail (reference, not inlined): {grade_name}",
    ]
    if corrections:
        section_lines.append("Corrections:")
        section_lines.append(corrections)
    else:
        section_lines.append("Corrections: none")
    section_lines.append(f"<!-- bs-fix-round: {round_number}; archive={archive_name}; grade={grade_name}; failed={failed_json} -->")
    section = "\n".join(section_lines) + "\n"
    outcome_file.write_text(text.rstrip() + section, encoding="utf-8")
    return f"reshaped round {round_number}: {archive_name} <- {grade_name} failed={failed_json}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycle-dir", required=True)
    ap.add_argument("--outcome-file", required=True)
    ap.add_argument("--grade-file", required=True)
    ap.add_argument("--round", required=True, type=int)
    ap.add_argument("--corrections-file", default=None)
    args = ap.parse_args(argv)
    try:
        cycle_dir = Path(args.cycle_dir)
        grade_file = _rel_or_abs(cycle_dir, args.grade_file)
        corrections_file = _rel_or_abs(cycle_dir, args.corrections_file) if args.corrections_file else None
        message = reshape(cycle_dir, _rel_or_abs(cycle_dir, args.outcome_file), grade_file, args.round, corrections_file)
        print(message)
        return 0
    except ReshapeError as exc:
        return _die(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
