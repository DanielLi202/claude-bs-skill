from pathlib import Path
import os, subprocess, sys, tempfile, unittest
HELPER = Path(__file__).resolve().parents[1] / 'runtime' / 'grade_verify.py'
class GradeVerifyTests(unittest.TestCase):
    def run_helper(self, binding_text: str, task_type='code', env=None):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); cycle=root/'cycle'; cycle.mkdir(); binding=cycle/'binding.yaml'; binding.write_text(binding_text, encoding='utf-8'); worktree=root/'worktree'; worktree.mkdir()
            proc=subprocess.run([sys.executable,str(HELPER),'--cycle-dir',str(cycle),'--binding-file',str(binding),'--task-id','B-001','--task-type',task_type,'--round','0','--worktree',str(worktree)], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env or os.environ.copy(), timeout=10)
            out=cycle/'evidence'/'grade_verify_round_0.yaml'
            return proc, out.read_text(encoding='utf-8') if out.exists() else ''
    def test_code_task_without_verify_mapping_fails(self):
        proc,out=self.run_helper('verify_command: "bash scripts/verify-docs.sh"\n'); self.assertEqual(proc.returncode,2); self.assertIn('requires verify.grade.code',out); self.assertIn('status: fail',out)
    def test_verify_command_failure_returns_nonzero(self):
        proc,out=self.run_helper('''\nverify:\n  grade:\n    code:\n      - "python3 -c 'import sys; sys.exit(7)'"\n'''); self.assertEqual(proc.returncode,1); self.assertIn('status: fail',out); self.assertIn('exit: 7',out)
    def test_env_clear_removes_rustc_wrapper(self):
        env=os.environ.copy(); env['RUSTC_WRAPPER']='bad-wrapper'
        proc,out=self.run_helper('''\nverify:\n  grade:\n    code:\n      - >\n        python3 -c 'import os, sys; sys.exit(0 if os.environ.get("RUSTC_WRAPPER") is None else 3)'\n  env:\n    clear:\n      - RUSTC_WRAPPER\n''', env=env); self.assertEqual(proc.returncode,0,out); self.assertIn('status: pass',out); self.assertIn('RUSTC_WRAPPER',out)
    def test_docs_task_can_use_legacy_verify_command(self):
        proc,out=self.run_helper('verify_command: "python3 -c pass"\n', task_type='docs'); self.assertEqual(proc.returncode,0,out); self.assertIn('status: pass',out)
if __name__ == '__main__': unittest.main()
