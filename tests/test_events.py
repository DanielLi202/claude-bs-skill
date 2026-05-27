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


if __name__ == '__main__':
    unittest.main()
