from pathlib import Path
import unittest
COMMAND = Path(__file__).resolve().parents[1] / 'commands' / 'bs.md'
class CommandFlowTests(unittest.TestCase):
    def test_grade_verify_is_required_before_initial_and_fix_grade(self):
        text = COMMAND.read_text(encoding='utf-8')
        self.assertIn('Before each Grade round, always run `${runtime}/grade_verify.py', text)
        self.assertIn('must create `evidence/grade_verify_round_<N>.yaml` before `grade_round_<N>.md` is authored', text)
        self.assertIn('MUST cite `evidence/grade_verify_round_<N>.yaml`', text)
        self.assertIn('Run `${runtime}/grade_verify.py ... --round <g+1>` again before the fix Grade is authored', text)
        self.assertIn('citing `evidence/grade_verify_round_<g+1>.yaml`', text)
        self.assertIn('cannot substitute for per-round Grade verify helper invocation', text)
if __name__ == '__main__': unittest.main()
