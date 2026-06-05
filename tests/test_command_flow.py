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

    def test_mcp_policy_and_step10_event_contract_are_explicit(self):
        text = COMMAND.read_text(encoding='utf-8')
        self.assertIn('conduct.mcp_policy', text)
        self.assertIn('--mcp-policy <policy>', text)
        self.assertIn('--worktree <worktree>', text)
        self.assertIn('MUST pass the resolved `--mcp-policy` explicitly', text)
        self.assertIn('--allow-open-current step_10', text)
        self.assertIn('post-close full validation', text)
        self.assertIn('retry_kind', text)
        self.assertIn('recorded_at', text)
        self.assertIn('occurred_at', text)
        self.assertIn('lib.events.append_started/append_completed/append_failed', text)
        self.assertIn('generate `auto_merge_gate.yaml` from parsed Grade summary', text)
if __name__ == '__main__': unittest.main()
