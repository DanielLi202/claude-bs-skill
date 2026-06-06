from pathlib import Path
import hashlib
import tempfile
import unittest

from lib import binding


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
        ):
            with self.assertRaises(binding.BindingError):
                binding.validate_status_marker_config(bad)


if __name__ == '__main__':
    unittest.main()
