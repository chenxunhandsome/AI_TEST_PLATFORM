from unittest import TestCase

from apps.ui_automation.test_executor import _normalize_step_result
from apps.ui_automation.views import _record_step_failure


class StepExecutionStatusTests(TestCase):
    def test_normalize_step_result_forces_error_state_to_failed(self):
        step_result = {
            'step_number': 2,
            'success': True,
            'error': 'assert failed',
        }

        normalized = _normalize_step_result(step_result)

        self.assertFalse(normalized['success'])
        self.assertEqual(normalized['error'], 'assert failed')

    def test_record_step_failure_without_screenshot_still_marks_failed_and_stops(self):
        execution_result = {'status': 'passed', 'error_message': None}
        detailed_errors = []
        screenshots = []
        execution_logs = []

        should_continue = _record_step_failure(
            execution_result,
            detailed_errors,
            screenshots,
            execution_logs,
            step_number=3,
            step_count=5,
            action_type_text='输入',
            element_data={'name': '搜索框'},
            description='输入关键字后回车',
            step_log='导航到测试页面失败',
            screenshot_base64=None,
        )

        self.assertFalse(should_continue)
        self.assertEqual(execution_result['status'], 'failed')
        self.assertEqual(execution_result['error_message'], '导航到测试页面失败')
        self.assertEqual(screenshots, [])
        self.assertEqual(len(detailed_errors), 1)
        self.assertEqual(detailed_errors[0]['step_number'], 3)
        self.assertIn('步骤失败,准备退出执行', execution_logs[-1])
