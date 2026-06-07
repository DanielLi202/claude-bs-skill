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
        self.assertIn('spec_compliance_matrix', text)
        self.assertIn('negative_regression_tests', text)
        self.assertIn('secret_leakage_audit', text)
        self.assertIn('dependency_spec_review', text)

    def test_conduct_self_hang_hardening_guidance_is_present(self):
        text = COMMAND.read_text(encoding='utf-8')
        # #2 forbid broad filesystem dependency hunts in the capsule
        self.assertIn('non-goals MUST forbid broad filesystem dependency hunts', text)
        self.assertIn('outside the worktree', text)
        # #1 process-group reaping described
        self.assertIn('own POSIX process group', text)
        # #4 kill-resistant launch recommendation
        self.assertIn('detached', text)
        self.assertIn('tmux', text)
        # #3 terminal-candidate opt-in flags
        self.assertIn('--terminal-candidate-idle-sec', text)
        self.assertIn('--on-terminal-candidate', text)
        # #5 interrupted-with-delta verify-and-accept path
        self.assertIn('Interrupted-with-delta verify-and-accept', text)
        self.assertIn('interrupted_with_delta', text)
        self.assertIn('recovery_decision.yaml', text)
        self.assertIn('workflow_reflection.yaml', text)
if __name__ == '__main__': unittest.main()
