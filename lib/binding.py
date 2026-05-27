from pathlib import Path
import hashlib, re
try:
    import yaml
except Exception:
    yaml = None

class BindingError(ValueError): pass
HEX64 = re.compile(r"^[0-9a-f]{64}$")

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load(path: Path) -> dict:
    if yaml is None:
        raise BindingError("PyYAML is required for bs binding parsing")
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict): raise BindingError(".bootstrap.yaml root must be mapping")
    return data

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
    for f in ["backlog", "ledger"]:
        if not (repo / data[f]).exists(): raise BindingError(f"path not found: {data[f]}")
    if data.get("workflow_dir") and not (repo / data["workflow_dir"]).exists():
        raise BindingError(f"workflow_dir not found: {data['workflow_dir']}")
