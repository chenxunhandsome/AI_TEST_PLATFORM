from types import SimpleNamespace
from unittest import TestCase

from apps.ui_automation.playwright_engine import append_runtime_variable_log as append_playwright_runtime_variable_log
from apps.ui_automation.selenium_engine import append_runtime_variable_log as append_selenium_runtime_variable_log
from apps.ui_automation.test_executor import _store_runtime_variable_for_step
from apps.ui_automation.variable_resolver import clear_runtime_variables, get_runtime_variable


class RuntimeVariableStorageTests(TestCase):
    def setUp(self):
        clear_runtime_variables()

    def tearDown(self):
        clear_runtime_variables()

    def test_selenium_get_text_log_stores_runtime_variable(self):
        step = SimpleNamespace(save_as='captured_text')

        log = append_selenium_runtime_variable_log(step, 'ok', 'welcome')

        self.assertIn('${captured_text}', log)
        self.assertEqual(get_runtime_variable('captured_text'), 'welcome')

    def test_playwright_get_text_log_stores_runtime_variable(self):
        step = SimpleNamespace(save_as='captured_text')

        log = append_playwright_runtime_variable_log(step, 'ok', 'page-title')

        self.assertIn('${captured_text}', log)
        self.assertEqual(get_runtime_variable('captured_text'), 'page-title')

    def test_legacy_executor_get_text_stores_runtime_variable(self):
        _store_runtime_variable_for_step(
            {
                'action_type': 'getText',
                'save_as': 'captured_text',
            },
            resolved_result_value='runtime-value',
        )

        self.assertEqual(get_runtime_variable('captured_text'), 'runtime-value')
