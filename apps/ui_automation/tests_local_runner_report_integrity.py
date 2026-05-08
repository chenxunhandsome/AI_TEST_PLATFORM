from types import SimpleNamespace
from unittest import TestCase

from apps.ui_automation.local_runner_views import _validate_local_execution_integrity


class LocalRunnerReportIntegrityTests(TestCase):
    def test_passed_report_is_failed_when_reported_steps_are_incomplete(self):
        execution = SimpleNamespace(
            test_case=SimpleNamespace(
                steps=SimpleNamespace(count=lambda: 3)
            )
        )
        logs = '[{"step_number": 1, "success": true}, {"step_number": 2, "success": true}]'

        status, error_message = _validate_local_execution_integrity(
            execution,
            'passed',
            logs,
            '',
        )

        self.assertEqual(status, 'failed')
        self.assertIn('计划 3 步', error_message)
        self.assertIn('只上报 2 步', error_message)

    def test_passed_report_remains_passed_when_all_steps_are_reported(self):
        execution = SimpleNamespace(
            test_case=SimpleNamespace(
                steps=SimpleNamespace(count=lambda: 2)
            )
        )
        logs = '[{"step_number": 1, "success": true}, {"step_number": 2, "success": true}]'

        status, error_message = _validate_local_execution_integrity(
            execution,
            'passed',
            logs,
            '',
        )

        self.assertEqual(status, 'passed')
        self.assertEqual(error_message, '')
