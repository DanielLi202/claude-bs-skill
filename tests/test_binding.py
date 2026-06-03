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
        }
        binding.validate_verify_config(data)
        binding.validate_preflight_config(data)

    def test_validate_verify_config_rejects_missing_command_list_shape(self):
        with self.assertRaises(binding.BindingError):
            binding.validate_verify_config({"verify": {"grade": {"code": []}}})
        with self.assertRaises(binding.BindingError):
            binding.validate_preflight_config({"preflight": {"require_council": "false"}})


if __name__ == '__main__':
    unittest.main()
