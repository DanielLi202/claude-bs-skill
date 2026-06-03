from pathlib import Path
import hashlib, re
try:
    import yaml
except Exception:
    yaml = None

class BindingError(ValueError): pass
HEX64 = re.compile(r"^[0-9a-f]{64}$")
MANIFEST_ROW = re.compile(r"^\|\s*([^|`][^|]*?)\s*\|\s*([0-9a-f]{64})\s*\|\s*$")

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load(path: Path) -> dict:
    if yaml is None:
        raise BindingError("PyYAML is required for bs binding parsing")
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict): raise BindingError(".bootstrap.yaml root must be mapping")
    return data

def parse_runtime_manifest(contract_text: str) -> dict[str, str]:
    manifest: dict[str, str] = {}
    in_section = False
    for line in contract_text.splitlines():
        if line.strip().startswith("## Runtime manifest"):
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if not in_section or not line.startswith("|"):
            continue
        m = MANIFEST_ROW.match(line.strip())
        if not m:
            continue
        file, digest = m.groups()
        file = file.strip().strip("`")
        if file.lower() == "file":
            continue
        manifest[file] = digest
    return manifest

def validate_runtime_manifest(skill_root: Path, contract_text: str) -> None:
    manifest = parse_runtime_manifest(contract_text)
    if not manifest:
        return
    for rel, locked in manifest.items():
        if rel.startswith("/") or ".." in Path(rel).parts:
            raise BindingError(f"runtime manifest path invalid: {rel}")
        path = skill_root / rel
        if not path.exists():
            raise BindingError(f"runtime manifest path missing: {rel}")
        actual = sha256(path)
        if actual != locked:
            raise BindingError(f"runtime manifest hash drift: {rel}")


def validate_verify_config(data: dict) -> None:
    verify = data.get("verify")
    if verify is None: return
    if not isinstance(verify, dict): raise BindingError("verify must be mapping")
    grade = verify.get("grade")
    if grade is not None:
        if not isinstance(grade, dict): raise BindingError("verify.grade must be mapping")
        for task_type, commands in grade.items():
            if task_type not in {"code", "docs", "infra", "refactor", "spec"}: raise BindingError(f"verify.grade has unknown task type: {task_type}")
            if not isinstance(commands, list) or not commands or not all(isinstance(c, str) and c.strip() for c in commands): raise BindingError(f"verify.grade.{task_type} must be non-empty list of strings")
    env = verify.get("env")
    if env is not None:
        if not isinstance(env, dict): raise BindingError("verify.env must be mapping")
        clear = env.get("clear")
        if clear is not None and (not isinstance(clear, list) or not all(isinstance(c, str) and c for c in clear)): raise BindingError("verify.env.clear must be list of strings")
    not_required = verify.get("not_required")
    if not_required is not None and (not isinstance(not_required, list) or not all(isinstance(c, str) for c in not_required)): raise BindingError("verify.not_required must be list of task type strings")


def validate_preflight_config(data: dict) -> None:
    preflight = data.get("preflight")
    if preflight is None: return
    if not isinstance(preflight, dict): raise BindingError("preflight must be mapping")
    require = preflight.get("require_council")
    if require is not None and not isinstance(require, bool): raise BindingError("preflight.require_council must be bool")
    quorum = preflight.get("council_quorum_min")
    if quorum is not None and (isinstance(quorum, bool) or not isinstance(quorum, int) or quorum < 0): raise BindingError("preflight.council_quorum_min must be non-negative int")
    required_when = preflight.get("council_required_when")
    if required_when is not None and not isinstance(required_when, dict): raise BindingError("preflight.council_required_when must be mapping")

def validate(repo: Path, data: dict, skill_contract: Path) -> None:
    if data.get("schema_version") != 1: raise BindingError("schema_version must be 1")
    for f in ["contract", "backlog", "ledger", "cycle_dir_root", "red_lines", "verify_command"]:
        if f not in data: raise BindingError(f"missing {f}")
    c = data["contract"]
    for f in ["source_url", "source_tag", "source_commit", "source_sha256", "sha256_path", "compatible_range"]:
        if not c.get(f): raise BindingError(f"missing contract.{f}")
    if not HEX64.match(c["source_sha256"]): raise BindingError("contract.source_sha256 must be 64 lowercase hex")
    hash_file = repo / c["sha256_path"]
    if not hash_file.exists(): raise BindingError(f"missing {c['sha256_path']}")
    locked = hash_file.read_text().strip()
    if locked != c["source_sha256"]: raise BindingError("contract hash drift: binding and sha256 file differ")
    if sha256(skill_contract) != locked: raise BindingError("contract hash drift: skill contract differs from locked hash")
    validate_runtime_manifest(skill_contract.parent, skill_contract.read_text(encoding="utf-8"))
    validate_verify_config(data)
    validate_preflight_config(data)
    for f in ["backlog", "ledger"]:
        if not (repo / data[f]).exists(): raise BindingError(f"path not found: {data[f]}")
    if data.get("workflow_dir") and not (repo / data["workflow_dir"]).exists():
        raise BindingError(f"workflow_dir not found: {data['workflow_dir']}")
