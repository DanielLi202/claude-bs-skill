from pathlib import Path
import hashlib
import re
import tempfile
import unittest

from lib import binding

SKILL_ROOT = Path(__file__).resolve().parents[1]


class BindingManifestTests(unittest.TestCase):
    def test_parse_runtime_manifest(self):
        digest = 'a' * 64
        text = f'''# Contract\n\n## Runtime manifest (locked)\n\n| file | sha256 |\n|---|---|\n| runtime/preflight.sh | {digest} |\n\n## Next\n'''
        self.assertEqual(binding.parse_runtime_manifest(text), {'runtime/preflight.sh': digest})

    def test_validate_runtime_manifest_detects_drift(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'runtime').mkdir()
            f = root / 'runtime' / 'preflight.sh'
            f.write_text('ok', encoding='utf-8')
            good = hashlib.sha256(b'ok').hexdigest()
            contract = f'''## Runtime manifest (locked)\n\n| file | sha256 |\n|---|---|\n| runtime/preflight.sh | {good} |\n'''
            binding.validate_runtime_manifest(root, contract)
            bad = f'''## Runtime manifest (locked)\n\n| file | sha256 |\n|---|---|\n| runtime/preflight.sh | {'b' * 64} |\n'''
            with self.assertRaises(binding.BindingError):
                binding.validate_runtime_manifest(root, bad)

    def test_validate_verify_and_preflight_config_accepts_new_fields(self):
        data = {
            "verify": {"grade": {"code": ["cargo build"], "docs": ["bash scripts/verify-docs.sh"]}, "env": {"clear": ["RUSTC_WRAPPER"]}},
            "preflight": {"require_council": False, "council_quorum_min": 2, "council_required_when": {"risk_level": "high"}},
            "conduct": {"mcp_policy": "allowlist", "mcp_allowlist": ["github"]},
        }
        binding.validate_verify_config(data)
        binding.validate_preflight_config(data)
        binding.validate_conduct_config(data)

    def test_validate_verify_config_rejects_missing_command_list_shape(self):
        with self.assertRaises(binding.BindingError):
            binding.validate_verify_config({"verify": {"grade": {"code": []}}})
        with self.assertRaises(binding.BindingError):
            binding.validate_preflight_config({"preflight": {"require_council": "false"}})
        with self.assertRaises(binding.BindingError):
            binding.validate_conduct_config({"conduct": {"mcp_policy": "weird"}})
        with self.assertRaises(binding.BindingError):
            binding.validate_conduct_config({"conduct": {"mcp_allowlist": "github"}})

    def test_version_skew_warnings_compare_binding_title_driver_and_skill(self):
        data = {"contract": {"source_tag": "v1.4.4"}}
        contract = "# Bootstrap Development Workflow Contract v1.4.2\n"
        warnings = binding.version_skew_warnings(
            data,
            contract,
            driver_client_version="1.4.2",
            skill_version="1.4.2",
        )
        self.assertEqual(len(warnings), 3)
        self.assertIn("contract title v1.4.2", warnings[0])

    def test_version_skew_warnings_empty_when_aligned(self):
        data = {"contract": {"source_tag": "v1.4.4"}}
        contract = "# Bootstrap Development Workflow Contract v1.4.4\n"
        self.assertEqual(
            binding.version_skew_warnings(data, contract, driver_client_version="1.4.4", skill_version="1.4.4"),
            [],
        )

    def test_validate_status_marker_config_accepts_valid_and_absent(self):
        binding.validate_status_marker_config({})  # absent -> ok
        binding.validate_status_marker_config({
            "status_marker": {
                "file": "AGENTS.md",
                "next_task_marker": "§1-next-bs-task",
                "post_sync_command": "scripts/sync-claude-md.sh",
                "next_task_line": {"start": "<!-- a -->", "end": "<!-- b -->", "template": "{id} {title}"},
                "stale_id_guard": {"enabled": True, "start": "<!-- status:start -->", "end": "<!-- status:end -->"},
            }
        })

    def test_validate_status_marker_config_rejects_bad_shapes(self):
        for bad in (
            {"status_marker": "AGENTS.md"},                                  # not a mapping
            {"status_marker": {"next_task_marker": "x"}},                    # missing file
            {"status_marker": {"file": "AGENTS.md"}},                        # missing marker
            {"status_marker": {"file": "AGENTS.md", "next_task_marker": ""}},# empty marker
            {"status_marker": {"file": "AGENTS.md", "next_task_marker": "x", "post_sync_command": "  "}},
            {"status_marker": {"file": "AGENTS.md", "next_task_marker": "x", "next_task_line": {"start": "a"}}},  # missing end
            {"status_marker": {"file": "AGENTS.md", "next_task_marker": "x", "stale_id_guard": "yes"}},
            {"status_marker": {"file": "AGENTS.md", "next_task_marker": "x", "stale_id_guard": {"enabled": "true"}}},
            {"status_marker": {"file": "AGENTS.md", "next_task_marker": "x", "stale_id_guard": {"start": "a"}}},
        ):
            with self.assertRaises(binding.BindingError):
                binding.validate_status_marker_config(bad)


class ReleaseSelfConsistencyTests(unittest.TestCase):
    """Locks the v1.4.x release invariants: the real Runtime manifest must match
    the real bundled files, and every version string must agree so that an
    adopter pinned to the matching tag gets zero version_skew_warnings."""

    def _client_versions(self):
        out = {}
        for rel in ("runtime/codex_driver.py", "runtime/preflight.sh"):
            text = (SKILL_ROOT / rel).read_text(encoding="utf-8")
            m = re.search(r'clientInfo[^}]*?"version"\s*:\s*"([0-9]+\.[0-9]+\.[0-9]+)"', text)
            self.assertIsNotNone(m, f"clientInfo version not found in {rel}")
            out[rel] = m.group(1)
        return out

    def _skill_version(self):
        for line in (SKILL_ROOT / "skill.yaml").read_text(encoding="utf-8").splitlines():
            m = re.match(r'\s*version:\s*"([0-9]+\.[0-9]+\.[0-9]+)"', line)
            if m:
                return m.group(1)
        self.fail("version not found in skill.yaml")

    def test_real_runtime_manifest_matches_bundled_files(self):
        contract = (SKILL_ROOT / "contract.md").read_text(encoding="utf-8")
        # Raises BindingError on any drift between the locked table and real files.
        binding.validate_runtime_manifest(SKILL_ROOT, contract)

    def test_all_version_strings_are_aligned_and_skew_free(self):
        contract = (SKILL_ROOT / "contract.md").read_text(encoding="utf-8")
        title = binding.extract_contract_title_version(contract)
        skill = self._skill_version()
        clients = self._client_versions()
        self.assertEqual({title, skill, *clients.values()}, {title},
                         f"version mismatch: title={title} skill={skill} clients={clients}")
        # An adopter pinned to the matching tag must see no skew warnings.
        data = {"contract": {"source_tag": f"v{title}"}}
        self.assertEqual(
            binding.version_skew_warnings(data, contract, driver_client_version=clients["runtime/codex_driver.py"], skill_version=skill),
            [],
        )

    def test_release_facing_locators_track_the_release_version(self):
        # The bundled init template's locator and the README version line are
        # release-facing: an adopter initialized/refreshed from this release must
        # land on the matching tag, not a stale one (cycle-015 follow-up GOV/DOC).
        title = binding.extract_contract_title_version((SKILL_ROOT / "contract.md").read_text(encoding="utf-8"))
        tmpl = (SKILL_ROOT / "bundle" / "bootstrap.yaml.template").read_text(encoding="utf-8")
        self.assertRegex(tmpl, rf'source_tag:\s*"v{re.escape(title)}"')
        self.assertIn(f"/v{title}/contract.md", tmpl)
        readme = (SKILL_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(f"skill v{title}", readme)


if __name__ == '__main__':
    unittest.main()
