from pathlib import Path
import tempfile
import unittest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib'))

from events import EventError, step_states


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


if __name__ == '__main__':
    unittest.main()
