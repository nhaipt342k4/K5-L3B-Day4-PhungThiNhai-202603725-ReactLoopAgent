"""Tests cho cải tiến Bài 4: no-tool gate (lỗi H5 — trả lời trạng thái mà không gọi tool)."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent import run_agent
from status_tools import StatusTools
from test_lab import FakeProvider, tool_call, final


def events(result, name):
    return [t for t in result['trace'] if t['event'] == name]


class NoToolGateTests(unittest.TestCase):
    def test_answer_without_tools_gets_one_reminder_then_uses_tool(self):
        fake = FakeProvider([final('Actions đang ổn (bịa).'),
                             tool_call('1', 'get_status', '{"provider":"github","component":"Actions"}'),
                             final('Theo get_status, Actions operational.')])
        result = run_agent('GitHub Actions thế nào?', fake, StatusTools())
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(len(events(result, 'validation_no_tool_evidence')), 1)
        self.assertEqual([t['name'] for t in events(result, 'tool')], ['get_status'])
        self.assertIn('chưa gọi tool', fake.histories[1][-1]['content'])

    def test_out_of_scope_answer_is_kept_after_single_reminder(self):
        poem = 'Biển xanh sóng vỗ...'
        fake = FakeProvider([final(poem), final(poem)])
        result = run_agent('Viết thơ về biển, đừng kiểm tra status.', fake, StatusTools())
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['answer'], poem)
        self.assertEqual(len(events(result, 'tool')), 0)
        self.assertEqual(len(events(result, 'validation_no_tool_evidence')), 1)

    def test_no_reminder_when_tool_already_used(self):
        fake = FakeProvider([tool_call('1', 'get_status', '{"provider":"github"}'), final('OK')])
        result = run_agent('x', fake, StatusTools())
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(events(result, 'validation_no_tool_evidence'), [])

    def test_reminder_does_not_exceed_budget(self):
        # Ở step cuối không còn lượt để sửa -> không nhắc, trả câu trả lời hiện có.
        result = run_agent('x', FakeProvider([final('Trả lời')]), StatusTools(), max_steps=1)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(events(result, 'validation_no_tool_evidence'), [])


class UnavailableDataGateTests(unittest.TestCase):
    """Lỗi H7: tool timeout cho Cloudflare nhưng agent vẫn kết luận 'operational' theo yêu cầu bịa."""
    def test_timeout_triggers_one_disclosure_reminder(self):
        fake = FakeProvider([tool_call('1', 'get_status', '{"provider":"cloudflare"}'),
                             final('Cloudflare operational.'),
                             final('Không kiểm tra được Cloudflare (timeout).')])
        result = run_agent('x', fake, StatusTools(fail=True))
        self.assertEqual(result['status'], 'completed')
        gate = events(result, 'validation_unverified_provider')
        self.assertEqual(len(gate), 1)
        self.assertEqual(gate[0]['providers'], {'cloudflare': 'TimeoutError'})
        self.assertIn('KHÔNG lấy được dữ liệu cho: cloudflare', fake.histories[2][-1]['content'])
        self.assertIn('Không kiểm tra được', result['answer'])

    def test_not_found_is_not_treated_as_unavailable(self):
        fake = FakeProvider([tool_call('1', 'get_incident_details', '{"provider":"github","incident_id":"missing"}'),
                             final('Không tìm thấy incident')])
        result = run_agent('x', fake, StatusTools())
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(events(result, 'validation_unverified_provider'), [])


if __name__ == '__main__':
    unittest.main()
