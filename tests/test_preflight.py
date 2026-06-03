from pathlib import Path
import os
import subprocess
import tempfile
import unittest

PREFLIGHT = Path(__file__).resolve().parents[1] / 'runtime' / 'preflight.sh'


class PreflightCouncilTests(unittest.TestCase):
    def make_bin(self, root: Path, name: str, body: str):
        path = root / name
        path.write_text(body, encoding='utf-8')
        path.chmod(0o755)
        return path

    def run_preflight(self, extra_args=None, with_codex=True):
        with tempfile.TemporaryDirectory() as td:
            bindir = Path(td)
            if with_codex:
                self.make_bin(bindir, 'codex', '''#!/usr/bin/env bash
if [[ "$1" == "--version" ]]; then echo "codex 0.133.0"; exit 0; fi
if [[ "$1" == "login" && "$2" == "status" ]]; then exit 0; fi
exit 0
''')
            self.make_bin(bindir, 'gh', '''#!/usr/bin/env bash
if [[ "$1" == "auth" && "$2" == "status" ]]; then exit 0; fi
exit 0
''')
            env = os.environ.copy()
            env['PATH'] = f'{bindir}{os.pathsep}/bin{os.pathsep}/usr/bin'
            cmd = ['bash', str(PREFLIGHT), '--skip-verify-preflight']
            if extra_args:
                cmd.extend(extra_args)
            return subprocess.run(cmd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)

    def test_default_council_unavailable_is_warning_not_failure(self):
        proc = self.run_preflight()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn('overall: pass', proc.stdout)
        self.assertIn('name: council_quorum', proc.stdout)
        self.assertIn('status: warn', proc.stdout)
        self.assertIn('required: false', proc.stdout)
        self.assertIn('required_by=none', proc.stdout)

    def test_require_council_unmet_fails(self):
        proc = self.run_preflight(['--require-council'])
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('name: council_quorum', proc.stdout)
        self.assertIn('status: fail', proc.stdout)
        self.assertIn('required_by=explicit_policy', proc.stdout)

    def test_codex_auth_remains_hard_required_when_council_optional(self):
        proc = self.run_preflight(with_codex=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('codex_binary', proc.stdout)
        self.assertIn('required: true', proc.stdout)

    def test_skip_council_is_warning_only(self):
        proc = self.run_preflight(['--skip-council'])
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn('council checks skipped', proc.stdout)
        self.assertIn('required: false', proc.stdout)


if __name__ == '__main__':
    unittest.main()
