from pathlib import Path
import tempfile
import unittest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib'))

from events import EventError, append_completed, append_started, step_states


class EventStateTests(unittest.TestCase):
    def write(self, text: str) -> Path:
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        path = Path(d.name) / 'step_events.jsonl'
        path.write_text(text, encoding='utf-8')
        return path

    def test_retry_attempt_pairs_are_valid(self):
        path = self.write('\n'.join([
            '{"step":"step_3","attempt":0,"event":"started"}',
            '{"step":"step_3","attempt":0,"event":"failed"}',
            '{"step":"step_3","attempt":1,"event":"started"}',
            '{"step":"step_3","attempt":1,"event":"completed"}',
        ]))
        self.assertEqual(step_states(path), {'step_3': 'completed'})

    def test_nested_started_is_rejected(self):
        path = self.write('\n'.join([
            '{"step":"step_3","event":"started"}',
            '{"step":"step_3","event":"started"}',
            '{"step":"step_3","event":"completed"}',
        ]))
        with self.assertRaisesRegex(EventError, 'nested started'):
            step_states(path)

    def test_unclosed_retry_started_is_rejected(self):
        path = self.write('\n'.join([
            '{"step":"step_3","event":"started"}',
            '{"step":"step_3","event":"failed"}',
            '{"step":"step_3","retry":1,"event":"started"}',
            '{"step":"step_3","event":"started"}',
            '{"step":"step_3","event":"completed"}',
        ]))
        with self.assertRaisesRegex(EventError, 'unclosed started|started after terminal'):
            step_states(path)

    def test_valid_reason_code_and_terminal_fields_are_allowed(self):
        path = self.write('\n'.join([
            '{"step":"step_3","event":"started"}',
            '{"step":"step_3","event":"failed","reason_code":"semantic_required_effect_missing","driver_exit":6,"conduct_result":"semantic_failed","workspace_delta_files":[],"evidence_delta_files":[],"write_actions":0}',
        ]))
        self.assertEqual(step_states(path), {'step_3': 'failed'})

    def test_invalid_reason_code_is_rejected(self):
        path = self.write('\n'.join([
            '{"step":"step_3","event":"started"}',
            '{"step":"step_3","event":"failed","reason_code":"environment_blocked"}',
        ]))
        with self.assertRaisesRegex(EventError, 'invalid reason_code'):
            step_states(path)

    def test_invalid_terminal_field_shape_is_rejected(self):
        path = self.write('\n'.join([
            '{"step":"step_3","event":"started"}',
            '{"step":"step_3","event":"failed","workspace_delta_files":"nope"}',
        ]))
        with self.assertRaisesRegex(EventError, 'workspace_delta_files must be list'):
            step_states(path)

    def test_occurred_recorded_are_accepted_and_legacy_ts_is_accepted(self):
        path = self.write('\n'.join([
            '{"step":"step_1","event":"started","occurred_at":"2026-06-05T00:00:00Z","recorded_at":"2026-06-05T00:00:10Z"}',
            '{"step":"step_1","event":"completed","occurred_at":"2026-06-05T00:00:01Z","recorded_at":"2026-06-05T00:00:11Z"}',
            '{"step":"step_2","event":"started","ts":"2026-06-05T00:00:12Z"}',
            '{"step":"step_2","event":"completed","ts":"2026-06-05T00:00:13Z"}',
        ]))
        self.assertEqual(step_states(path), {'step_1': 'completed', 'step_2': 'completed'})

    def test_append_helpers_machine_stamp_new_events(self):
        path = self.write('')
        append_started(str(path), 'step_1')
        append_completed(path, 'step_1')
        text = path.read_text(encoding='utf-8')
        self.assertIn('"event": "started"', text)
        self.assertIn('"recorded_at":', text)
        self.assertIn('"occurred_at":', text)
        self.assertEqual(step_states(path), {'step_1': 'completed'})

    def test_repair_event_can_append_only_ack_missing_started(self):
        import hashlib
        terminal = '{"step":"step_9","event":"completed"}'
        digest = hashlib.sha256(terminal.encode("utf-8")).hexdigest()
        path = self.write('\n'.join([
            terminal,
            '{"event":"repair","repair_kind":"missing_started","target_step":"step_9","target_attempt":0,"target_line":1,"target_event_hash":"' + digest + '","reason":"helper failed before started append"}',
        ]))
        self.assertEqual(step_states(path), {'step_9': 'completed'})

    def test_repair_event_hash_must_match_target_line(self):
        terminal = '{"step":"step_9","event":"completed"}'
        path = self.write('\n'.join([
            terminal,
            '{"event":"repair","repair_kind":"missing_started","target_step":"step_9","target_attempt":0,"target_line":1,"target_event_hash":"' + ('0' * 64) + '","reason":"helper failed before started append"}',
        ]))
        with self.assertRaisesRegex(EventError, 'target_event_hash does not match'):
            step_states(path)

    def test_unrepaired_orphan_terminal_is_clean_event_error(self):
        path = self.write('{"step":"step_9","event":"completed"}')
        with self.assertRaisesRegex(EventError, 'without matching started'):
            step_states(path)

    def test_repair_cannot_mask_duplicate_terminal_after_completed_attempt(self):
        import hashlib
        duplicate = '{"step":"step_1","event":"failed"}'
        digest = hashlib.sha256(duplicate.encode("utf-8")).hexdigest()
        path = self.write('\n'.join([
            '{"step":"step_1","event":"started"}',
            '{"step":"step_1","event":"completed"}',
            duplicate,
            '{"event":"repair","repair_kind":"missing_started","target_step":"step_1","target_attempt":0,"target_line":3,"target_event_hash":"' + digest + '","reason":"bad duplicate repair"}',
        ]))
        with self.assertRaisesRegex(EventError, 'duplicate terminal|already has terminal'):
            step_states(path)

    def test_terminal_counts_reject_null_and_count_list_ambiguity(self):
        path = self.write('\n'.join([
            '{"step":"step_3","event":"started"}',
            '{"step":"step_3","event":"completed","workspace_delta_files":14,"file_change_events":null}',
        ]))
        with self.assertRaisesRegex(EventError, 'workspace_delta_files must be list|file_change_events must be non-negative'):
            step_states(path)

    def test_invalid_recorded_at_is_rejected(self):
        path = self.write('\n'.join([
            '{"step":"step_1","event":"started","recorded_at":"2026-06-05T00:00:00+00:00","occurred_at":"2026-06-05T00:00:00Z"}',
        ]))
        with self.assertRaisesRegex(EventError, 'invalid recorded_at'):
            step_states(path)

    def test_retry_kind_enum_and_changed_note(self):
        for retry_kind, changed in [
            ('launch_retry', 'CODEX_HOME'),
            ('semantic_fix_round', 'outcome sha'),
            ('transport_retry', 'model'),
        ]:
            with self.subTest(retry_kind=retry_kind):
                path = self.write('\n'.join([
                    '{"step":"step_3","event":"started"}',
                    '{"step":"step_3","event":"failed"}',
                    f'{{"step":"step_3","attempt":1,"event":"started","retry_kind":"{retry_kind}","changed":"{changed}"}}',
                    f'{{"step":"step_3","attempt":1,"event":"completed","retry_kind":"{retry_kind}","changed":"{changed}"}}',
                ]))
                self.assertEqual(step_states(path), {'step_3': 'completed'})

    def test_retry_kind_on_attempt_zero_is_rejected(self):
        path = self.write('\n'.join([
            '{"step":"step_3","event":"started","retry_kind":"launch_retry","changed":"CODEX_HOME"}',
        ]))
        with self.assertRaisesRegex(EventError, 'only valid on non-zero attempts'):
            step_states(path)

    def test_retry_kind_requires_changed_note(self):
        path = self.write('\n'.join([
            '{"step":"step_3","attempt":1,"event":"started","retry_kind":"launch_retry"}',
        ]))
        with self.assertRaisesRegex(EventError, 'changed must be non-empty'):
            step_states(path)

    def test_invalid_retry_kind_is_rejected(self):
        path = self.write('\n'.join([
            '{"step":"step_3","attempt":1,"event":"started","retry_kind":"bad","changed":"x"}',
        ]))
        with self.assertRaisesRegex(EventError, 'invalid retry_kind'):
            step_states(path)


if __name__ == '__main__':
    unittest.main()
