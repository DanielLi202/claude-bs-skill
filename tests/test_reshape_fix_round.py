from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

HELPER = Path(__file__).resolve().parents[1] / 'runtime' / 'reshape_fix_round.py'


def grade(p0=0, p1=1, p2=0, ids=('a2',), body='RAW GRADE PROSE MUST NOT BE INLINED'):
    rows = '\n'.join(f'  - id: {i}\n    status: fail\n    severity: P1' for i in ids)
    return (
        f"# Grade\n"
        f"{body}\n\n"
        f"```yaml\n"
        f"grade_summary:\n"
        f"  p0_count: {p0}\n"
        f"  p1_count: {p1}\n"
        f"  p2_count: {p2}\n"
        f"```\n\n"
        f"```yaml\n"
        f"acceptance_status:\n"
        f"{rows}\n"
        f"```\n"
    )



class ReshapeFixRoundTests(unittest.TestCase):
    def run_helper(self, root: Path, round_number: int, grade_file: str, extra=None):
        cmd = [sys.executable, str(HELPER), '--cycle-dir', str(root), '--outcome-file', str(root / 'outcome.md'), '--grade-file', grade_file, '--round', str(round_number)]
        if extra:
            cmd.extend(extra)
        return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def test_happy_path_archives_injects_marker_and_excludes_raw_grade(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'outcome.md').write_text('# Outcome\n', encoding='utf-8')
            (root / 'grade_round_0.md').write_text(grade(p1=2, ids=('a2', 'a4')), encoding='utf-8')
            corrections = root / 'corrections.txt'
            corrections.write_text('- tighten a2\n- add a4 proof', encoding='utf-8')
            proc = self.run_helper(root, 1, 'grade_round_0.md', ['--corrections-file', str(corrections)])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue((root / 'outcome.v0.md').exists())
            text = (root / 'outcome.md').read_text(encoding='utf-8')
            self.assertIn('bs-fix-round: 1', text)
            self.assertIn('failed=["a2","a4"]', text)
            self.assertIn('Grade detail (reference, not inlined): grade_round_0.md', text)
            self.assertNotIn('RAW GRADE PROSE MUST NOT BE INLINED', text)

    def test_resume_safe_noop_when_archive_and_matching_marker_exist(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'outcome.md').write_text('# Outcome\n', encoding='utf-8')
            (root / 'grade_round_0.md').write_text(grade(), encoding='utf-8')
            first = self.run_helper(root, 1, 'grade_round_0.md')
            self.assertEqual(first.returncode, 0, first.stderr)
            before = (root / 'outcome.v0.md').read_text(encoding='utf-8')
            second = self.run_helper(root, 1, 'grade_round_0.md')
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertIn('no-op', second.stdout)
            self.assertEqual((root / 'outcome.v0.md').read_text(encoding='utf-8'), before)

    def test_partial_state_is_loud_failure(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'outcome.md').write_text('# Outcome\n', encoding='utf-8')
            (root / 'grade_round_0.md').write_text(grade(), encoding='utf-8')
            (root / 'outcome.v0.md').write_text('# Archived\n', encoding='utf-8')
            proc = self.run_helper(root, 1, 'grade_round_0.md')
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn('inconsistent fix-round state', proc.stderr)

    def test_missing_machine_readable_blocks_fail_fast(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'outcome.md').write_text('# Outcome\n', encoding='utf-8')
            (root / 'grade_round_0.md').write_text('# no blocks\n', encoding='utf-8')
            proc = self.run_helper(root, 1, 'grade_round_0.md')
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn('grade_summary', proc.stderr)

    def test_bounds_and_strict_decrease_are_enforced(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'outcome.md').write_text('# Outcome\n', encoding='utf-8')
            (root / 'grade_round_0.md').write_text(grade(p1=2, ids=('a1', 'a2')), encoding='utf-8')
            (root / 'grade_round_1.md').write_text(grade(p1=2, ids=('a2', 'a3')), encoding='utf-8')
            too_many = self.run_helper(root, 4, 'grade_round_3.md')
            self.assertNotEqual(too_many.returncode, 0)
            self.assertIn('exceeds max_fix_rounds', too_many.stderr)
            non_decrease = self.run_helper(root, 2, 'grade_round_1.md')
            self.assertNotEqual(non_decrease.returncode, 0)
            self.assertIn('strictly decrease', non_decrease.stderr)

    def test_corrections_cap_enforced(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'outcome.md').write_text('# Outcome\n', encoding='utf-8')
            (root / 'grade_round_0.md').write_text(grade(), encoding='utf-8')
            corrections = root / 'corrections.txt'
            corrections.write_text('x' * 1501, encoding='utf-8')
            proc = self.run_helper(root, 1, 'grade_round_0.md', ['--corrections-file', str(corrections)])
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn('corrections exceed', proc.stderr)


if __name__ == '__main__':
    unittest.main()
