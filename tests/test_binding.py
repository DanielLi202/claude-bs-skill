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


if __name__ == '__main__':
    unittest.main()
