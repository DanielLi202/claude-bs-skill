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
SOURCE_PATH_RE = re.compile(
    r"(?<![\w./-])"
    r"(?P<path>"
    r"(?:"
    r"(?:crates|apps|packages|services|components|tools)/[A-Za-z0-9._+-]+/src/"
    r"|"
    r"src/"
    r")"
    r"[A-Za-z0-9._+@/-]+"
    r"\.(?:rs|py|js|jsx|ts|tsx|go|java|kt|kts|swift|c|cc|cpp|cxx|h|hpp|m|mm|rb|php|ex|exs|erl|hrl|scala|sh|bash|zsh|fish|sql|lua|r|dart|vue|svelte)"
    r")"
    r"(?::\d+)?"
)
PROJECT_SCOPED_RE = re.compile(r"^(?:crates|apps|packages|services|components|tools)/[^/]+/")
REPO_PATH_WITH_DIR_RE = re.compile(
    r"(?<![\w./-])"
    r"(?P<path>"
    r"(?:\./)?"
    r"(?:[A-Za-z0-9._+@-]+/)+"
    r"[A-Za-z0-9._+@-]+(?:\.[A-Za-z0-9][A-Za-z0-9._-]*)"
    r")"
    r"(?::\d+)?"
    r"(?![\w./-])"
)
ROOT_LOCKFILE_RE = re.compile(
    r"(?<![\w./-])(?P<path>pnpm-lock\.yaml|Cargo\.lock|package-lock\.json|yarn\.lock)(?![\w./-])"
)
PRODUCTION_LOCI_LINE_RE = re.compile(r"^\s*Production loci:\s*(?P<paths>.+)$", re.IGNORECASE | re.MULTILINE)
BLOCKING_CONTEXT_RE = re.compile(
    r"\b(?:P0|P1|block(?:ing|er)?|fail(?:ed|ing|s)?|unverified|regress(?:ed|ion)?|"
    r"defect|root cause|unresolved|remediation|fix:|recommended)\b",
    re.IGNORECASE,
)
STRONG_REPO_PATH_RE = re.compile(r"^(?:crates|apps|packages|services|components|tools)/[^/]+/src/")
PACKAGE_MANIFESTS = {"package.json", "Cargo.toml", "pyproject.toml"}
LOCKFILES = {"pnpm-lock.yaml", "Cargo.lock", "package-lock.json", "yarn.lock"}
ROOT_OVERRIDE_FILES = PACKAGE_MANIFESTS | LOCKFILES
ASSET_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif", "svg", "ico", "icns", "avif"}
CONFIG_SCRIPT_EXTENSIONS = {"ts", "js", "mts", "mjs", "cts", "cjs"}


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


def _iter_yaml_rows(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _iter_yaml_rows(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_yaml_rows(child)


def _row_text(value) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _failed_blocking_ids(blocks: list[dict]) -> set[str]:
    failed: set[str] = set()
    for block in blocks:
        rows = block.get("acceptance_status")
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            if row.get("status") in {"fail", "unverified"} and row.get("severity") in {"P0", "P1"}:
                item_id = row.get("id")
                if isinstance(item_id, str) and item_id:
                    failed.add(item_id)
    return failed


def _is_blocking_yaml_row(row: dict, failed_ids: set[str]) -> bool:
    row_id = row.get("id") or row.get("acceptance_id") or row.get("acceptance_ref")
    status = row.get("status")
    severity = row.get("severity") or row.get("severity_if_fail")
    if status in {"fail", "unverified"} and severity in {"P0", "P1"}:
        return True
    if isinstance(row_id, str) and row_id in failed_ids:
        return True
    return False


def _blocking_text_snippets(grade_text: str) -> list[str]:
    snippets: list[str] = []
    try:
        blocks = _yaml_blocks(grade_text)
    except ReshapeError:
        blocks = []
    failed_ids = _failed_blocking_ids(blocks)
    for block in blocks:
        for row in _iter_yaml_rows(block):
            if _is_blocking_yaml_row(row, failed_ids):
                snippets.append(_row_text(row))

    prose = re.sub(r"```(?:yaml|yml)\s*\n.*?```", "", grade_text, flags=re.DOTALL)
    for paragraph in re.split(r"\n\s*\n", prose):
        if _has_production_locus_candidate(paragraph) and BLOCKING_CONTEXT_RE.search(paragraph):
            snippets.append(paragraph)
    return snippets


def _clean_repo_path(raw: str) -> str:
    path = str(raw).strip().strip("`'\"()[]{}<>")
    while path.startswith("./"):
        path = path[2:]
    return path.replace("\\", "/").strip()


def _is_repo_relative_path(path: str) -> bool:
    if not path or path.startswith(("/", "~", "-")) or "://" in path:
        return False
    parts = path.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return False
    return True


def _is_test_path(path: str) -> bool:
    normalized = _clean_repo_path(path)
    parts = normalized.split("/")
    if any(part in {"tests", "__tests__"} for part in parts):
        return True
    basename = normalized.rsplit("/", 1)[-1]
    if basename.startswith("test_"):
        return True
    stem = basename.rsplit(".", 1)[0]
    return stem.endswith(("_test", ".test", ".spec", "-test", "-spec"))


def _is_source_locus(path: str) -> bool:
    return bool(SOURCE_PATH_RE.fullmatch(path))


def _is_config_locus(path: str) -> bool:
    basename = path.rsplit("/", 1)[-1]
    lower = basename.lower()
    if lower == "tauri.conf.json":
        return True
    if re.fullmatch(r"vite\.config\.[A-Za-z0-9]+", basename):
        return True
    if "." in basename:
        prefix, ext = basename.rsplit(".", 1)
        if prefix.endswith(".config") and ext in CONFIG_SCRIPT_EXTENSIONS:
            return True
    if lower.endswith((".yaml", ".yml", ".toml")) and PROJECT_SCOPED_RE.match(path):
        return True
    return False


def _is_asset_locus(path: str) -> bool:
    basename = path.rsplit("/", 1)[-1]
    if "." not in basename:
        return False
    ext = basename.rsplit(".", 1)[-1].lower()
    return ext in ASSET_EXTENSIONS


def _is_production_locus_path(path: str) -> bool:
    normalized = _clean_repo_path(path)
    if not _is_repo_relative_path(normalized) or _is_test_path(normalized):
        return False
    if "/" not in normalized:
        return normalized in LOCKFILES
    basename = normalized.rsplit("/", 1)[-1]
    if _is_source_locus(normalized):
        return True
    if basename in PACKAGE_MANIFESTS or basename in LOCKFILES:
        return True
    return _is_config_locus(normalized) or _is_asset_locus(normalized)


def _repo_path_tokens(text: str):
    for match in REPO_PATH_WITH_DIR_RE.finditer(text):
        yield _clean_repo_path(match.group("path"))


def _extract_override_loci(text: str) -> set[str]:
    paths: set[str] = set()
    for match in PRODUCTION_LOCI_LINE_RE.finditer(text):
        for raw in match.group("paths").split(","):
            path = _clean_repo_path(raw)
            if not _is_repo_relative_path(path) or _is_test_path(path):
                continue
            if "/" in path or path in ROOT_OVERRIDE_FILES:
                paths.add(path)
    return paths


def _extract_production_paths(text: str) -> set[str]:
    paths: set[str] = set()
    for path in _repo_path_tokens(text):
        if _is_production_locus_path(path):
            paths.add(path)
    for match in ROOT_LOCKFILE_RE.finditer(text):
        path = _clean_repo_path(match.group("path"))
        if _is_production_locus_path(path):
            paths.add(path)
    return paths


def _has_production_locus_candidate(text: str) -> bool:
    return bool(_extract_production_paths(text))


def _extract_source_paths(text: str) -> set[str]:
    paths: set[str] = set()
    for match in SOURCE_PATH_RE.finditer(text):
        path = _clean_repo_path(match.group("path"))
        if not _is_test_path(path):
            paths.add(path)
    return paths


def extract_production_loci(grade_text: str) -> list[str]:
    """Extract repo-relative production loci from blocking grade findings."""
    candidates: set[str] = set()
    candidates.update(_extract_override_loci(grade_text))
    for snippet in _blocking_text_snippets(grade_text):
        candidates.update(_extract_source_paths(snippet))
        candidates.update(_extract_production_paths(snippet))
    strong = {path for path in candidates if STRONG_REPO_PATH_RE.match(path)}
    if strong:
        candidates = {path for path in candidates if not path.startswith("src/")}
    return sorted(candidates)


def _normalize_repo_path(path: str) -> str:
    return str(path).replace("\\", "/").lstrip("./")


def _path_matches_locus(changed_file: str, locus: str) -> bool:
    changed = _normalize_repo_path(changed_file)
    required = _normalize_repo_path(locus)
    return changed == required or changed.endswith(f"/{required}")


def fix_round_alignment(
    changed_files: list[str],
    production_loci: list[str],
    *,
    alt_justification: bool = False,
) -> tuple[bool, str]:
    """Return whether a fix-round diff touched the Grade-localized production loci."""
    loci = sorted({_normalize_repo_path(path) for path in production_loci if str(path).strip()})
    changed = sorted({_normalize_repo_path(path) for path in changed_files if str(path).strip()})
    if not loci:
        return True, "no production loci extracted (fail-open)"
    if alt_justification:
        return True, "explicit alternate-fix justification"
    for changed_file in changed:
        if any(_path_matches_locus(changed_file, locus) for locus in loci):
            return True, f"changed file touches required production locus: {changed_file}"
    if not changed:
        return False, "fix round produced no file changes"
    return (
        False,
        "required production loci not touched: "
        + ", ".join(loci)
        + "; changed files: "
        + ", ".join(changed)
        + " (helper/test-only or alternate locus requires justification)",
    )


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


def write_alignment_sidecar(
    cycle_dir: Path,
    round_number: int,
    failed_ids: list[str],
    prior_blocking_count: int,
    required_production_loci: list[str],
) -> Path:
    if yaml is None:
        raise ReshapeError("PyYAML is required")
    path = cycle_dir / f"fix_round_{round_number}_alignment.yaml"
    prior = {}
    if path.exists():
        try:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                prior = loaded
        except Exception:
            prior = {}
    data = {
        "round": round_number,
        "failed_ids": failed_ids,
        "prior_blocking_count": prior_blocking_count,
        "required_production_loci": required_production_loci,
        "alt_justification": bool(prior.get("alt_justification", False)),
    }
    if prior.get("alt_locus_reason") not in (None, ""):
        data["alt_locus_reason"] = prior.get("alt_locus_reason")
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def load_alignment_sidecar(path: Path) -> tuple[list[str], bool]:
    if yaml is None:
        raise ReshapeError("PyYAML is required")
    if not path.exists():
        raise ReshapeError(f"alignment sidecar missing: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ReshapeError("alignment sidecar must be a mapping")
    raw_loci = data.get("required_production_loci", [])
    if raw_loci is None:
        raw_loci = []
    if not isinstance(raw_loci, list) or not all(isinstance(item, str) for item in raw_loci):
        raise ReshapeError("alignment sidecar required_production_loci must be a string list")
    alt_reason = data.get("alt_locus_reason")
    alt = bool(data.get("alt_justification", False)) or (isinstance(alt_reason, str) and bool(alt_reason.strip()))
    return raw_loci, alt


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

    grade_text = grade_file.read_text(encoding="utf-8")
    summary, acceptance = parse_grade(grade_file)
    enforce_bounds(cycle_dir, grade_file, round_number, summary)
    failed_ids = [row["id"] for row in acceptance if row["status"] == "fail"]
    if not failed_ids:
        raise ReshapeError("acceptance_status contains no failed IDs to reshape")
    production_loci = extract_production_loci(grade_text)
    prior_blocking_count = blocking_count(summary)

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
            write_alignment_sidecar(cycle_dir, round_number, failed_ids, prior_blocking_count, production_loci)
            return "no-op: fix round already reshaped"
        raise ReshapeError("inconsistent fix-round state: archive exists but marker references a different round/grade")
    if archive.exists() and not existing_marker:
        raise ReshapeError("inconsistent fix-round state: archive exists but current-round marker is missing")
    if existing_marker and not archive.exists():
        raise ReshapeError("inconsistent fix-round state: current-round marker exists without archive")

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
    write_alignment_sidecar(cycle_dir, round_number, failed_ids, prior_blocking_count, production_loci)
    return f"reshaped round {round_number}: {archive_name} <- {grade_name} failed={failed_json}"


def _read_changed_files(path: Path | None, inline: list[str]) -> list[str]:
    files = list(inline)
    if path is not None:
        files.extend(path.read_text(encoding="utf-8").splitlines())
    return [item.strip() for item in files if item.strip()]


def _alignment_command(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="reshape_fix_round.py alignment")
    ap.add_argument("--sidecar", required=True)
    ap.add_argument("--changed-files-file", default=None)
    ap.add_argument("--changed-file", action="append", default=[])
    args = ap.parse_args(argv)
    sidecar = Path(args.sidecar)
    try:
        loci, alt = load_alignment_sidecar(sidecar)
        changed_files = _read_changed_files(Path(args.changed_files_file) if args.changed_files_file else None, args.changed_file)
        aligned, reason = fix_round_alignment(changed_files, loci, alt_justification=alt)
        print(
            json.dumps(
                {
                    "aligned": aligned,
                    "reason": reason,
                    "required_production_loci": loci,
                    "changed_files": changed_files,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0 if aligned else 10
    except (OSError, ReshapeError) as exc:
        print(
            json.dumps(
                {
                    "aligned": True,
                    "reason": f"alignment unavailable (fail-open): {exc}",
                    "required_production_loci": [],
                    "changed_files": [],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if argv and argv[0] == "alignment":
        return _alignment_command(argv[1:])
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
