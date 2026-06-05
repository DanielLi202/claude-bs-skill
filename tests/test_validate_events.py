from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

VALIDATOR = Path(__file__).resolve().parents[1] / 'runtime' / 'validate_events.py'


def ev(step, event, ts, attempt=0, **extra):
    obj = {'step': step, 'event': event, 'recorded_at': ts, 'occurred_at': extra.pop('occurred_at', ts)}
    if attempt:
        obj['attempt'] = attempt
    obj.update(extra)
    import json
    return json.dumps(obj, sort_keys=True)


class ValidateEventsTests(unittest.TestCase):
    def run_log(self, lines, *args):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'step_events.jsonl'
            path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
            return subprocess.run([sys.executable, str(VALIDATOR), str(path), *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def test_valid_multi_attempt_retry(self):
        proc = self.run_log([
            ev('step_3', 'started', '2026-06-05T00:00:00Z'),
            ev('step_3', 'failed', '2026-06-05T00:00:01Z'),
            ev('step_3', 'started', '2026-06-05T00:00:02Z', attempt=1),
            ev('step_3', 'completed', '2026-06-05T00:00:03Z', attempt=1),
        ])
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_first_event_missing_ts_is_rejected(self):
        proc = self.run_log(['{"step":"step_1","event":"started"}'])
        self.assertEqual(proc.returncode, 1)
        self.assertIn('ts_missing_or_invalid', proc.stderr)

    def test_later_missing_ts_is_clean_error_not_traceback(self):
        proc = self.run_log([
            ev('step_1', 'started', '2026-06-05T00:00:00Z'),
            '{"step":"step_1","event":"completed"}',
        ])
        self.assertEqual(proc.returncode, 1)
        self.assertIn('ts_missing_or_invalid', proc.stderr)
        self.assertNotIn('Traceback', proc.stderr)

    def test_non_canonical_offset_is_rejected(self):
        proc = self.run_log(['{"step":"step_1","event":"started","ts":"2026-06-05T00:00:00+00:00"}'])
        self.assertEqual(proc.returncode, 1)
        self.assertIn('ts_missing_or_invalid', proc.stderr)

    def test_duplicate_started_fixture_is_rejected(self):
        proc = self.run_log([
            ev('step_3', 'started', '2026-06-05T00:00:00Z'),
            ev('step_3', 'started', '2026-06-05T00:00:01Z'),
        ])
        self.assertEqual(proc.returncode, 1)
        self.assertIn('duplicate_started', proc.stderr)

    def test_terminal_without_started_fixture_is_rejected(self):
        proc = self.run_log([
            ev('step_3', 'completed', '2026-06-05T00:00:00Z'),
        ])
        self.assertEqual(proc.returncode, 1)
        self.assertIn('terminal_without_started', proc.stderr)

    def test_allow_open_current_tolerates_only_step_10(self):
        lines = [
            ev('step_9', 'started', '2026-06-05T00:00:00Z'),
            ev('step_9', 'completed', '2026-06-05T00:00:01Z'),
            ev('step_10', 'started', '2026-06-05T00:00:02Z'),
        ]
        self.assertEqual(self.run_log(lines, '--allow-open-current', 'step_10').returncode, 0)
        proc = self.run_log(lines)
        self.assertEqual(proc.returncode, 1)
        self.assertIn('unclosed_started', proc.stderr)

    def test_post_close_full_log_passes(self):
        proc = self.run_log([
            ev('step_10', 'started', '2026-06-05T00:00:00Z'),
            ev('step_10', 'completed', '2026-06-05T00:00:01Z'),
        ])
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_backfilled_occurred_recorded_passes(self):
        proc = self.run_log([
            ev('step_0', 'started', '2026-06-05T00:00:10Z', occurred_at='2026-06-05T00:00:00Z'),
            ev('step_0', 'completed', '2026-06-05T00:00:11Z', occurred_at='2026-06-05T00:00:01Z'),
        ])
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_non_monotonic_recorded_at_fails(self):
        proc = self.run_log([
            ev('step_0', 'started', '2026-06-05T00:00:10Z'),
            ev('step_0', 'completed', '2026-06-05T00:00:09Z'),
        ])
        self.assertEqual(proc.returncode, 1)
        self.assertIn('ts_not_monotonic', proc.stderr)

    def test_fractional_after_whole_second_is_monotonic(self):
        proc = self.run_log([
            ev('step_1', 'started', '2026-06-05T00:00:00Z'),
            ev('step_1', 'completed', '2026-06-05T00:00:00.001Z'),
        ])
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_legacy_ts_only_log_still_validates(self):
        proc = self.run_log([
            '{"step":"step_1","event":"started","ts":"2026-06-05T00:00:00Z"}',
            '{"step":"step_1","event":"completed","ts":"2026-06-05T00:00:01Z"}',
        ])
        self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == '__main__':
    unittest.main()
