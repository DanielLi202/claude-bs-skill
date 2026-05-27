from pathlib import Path
import importlib.util
import unittest

DRIVER = Path(__file__).resolve().parents[1] / 'runtime' / 'codex_driver.py'
spec = importlib.util.spec_from_file_location('codex_driver', DRIVER)
codex_driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(codex_driver)


class CodexDriverTests(unittest.TestCase):
    def test_final_answer_signal_arms_inferred_completion(self):
        obj = {'method': 'item/completed', 'params': {'item': {'phase': 'final_answer', 'type': 'message', 'role': 'assistant'}}}
        self.assertEqual(codex_driver.detect_inferred_completion_signal(obj), 'item_completed_final_answer')

    def test_idle_signal_arms_inferred_completion(self):
        obj = {'method': 'thread/status/changed', 'params': {'status': 'idle'}}
        self.assertEqual(codex_driver.detect_inferred_completion_signal(obj), 'thread_status_idle')

    def test_driver_defaults_include_heartbeat_and_inferred_timer(self):
        source = DRIVER.read_text(encoding='utf-8')
        self.assertIn('default=30', source)
        self.assertIn('default=5', source)
        self.assertIn('turn_completed_inferred', source)
        self.assertIn('heartbeat', source)


if __name__ == '__main__':
    unittest.main()
