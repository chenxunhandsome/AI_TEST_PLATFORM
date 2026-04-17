from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from apps.ui_automation.test_executor import TestExecutor


class FakePlaywrightPage:
    def __init__(self):
        self.url = 'http://example.com'
        self.wait_calls = []

    def screenshot(self, timeout=None):
        return b'playwright-screenshot'

    def wait_for_timeout(self, timeout):
        self.wait_calls.append(timeout)

    def title(self):
        return 'Fake Page'


class FakeSeleniumDriver:
    def __init__(self):
        self.screenshot_calls = 0

    def get_screenshot_as_png(self):
        self.screenshot_calls += 1
        return b'selenium-screenshot'


class LegacyExecutorScreenshotTests(TestCase):
    def _make_executor(self):
        return TestExecutor(
            test_suite=SimpleNamespace(project=SimpleNamespace(base_url='')),
            engine='playwright',
            browser='chrome',
            headless=True,
            executed_by=None,
        )

    def test_playwright_case_continues_after_screenshot_step_without_element(self):
        executor = self._make_executor()
        executor.current_page = FakePlaywrightPage()

        case_data = {
            'id': 1,
            'name': 'case-with-screenshot',
            'project_global_variables': [],
            'steps': [
                {
                    'step_number': 1,
                    'action_type': 'screenshot',
                    'description': 'manual screenshot',
                    'wait_time': 1000,
                    'input_value': '',
                    'assert_value': '',
                    'assert_type': '',
                    'save_as': '',
                    'element': None,
                },
                {
                    'step_number': 2,
                    'action_type': 'wait',
                    'description': 'wait after screenshot',
                    'wait_time': 200,
                    'input_value': '',
                    'assert_value': '',
                    'assert_type': '',
                    'save_as': '',
                    'element': None,
                },
            ],
        }

        result = executor.execute_test_case_playwright_no_db(case_data)

        self.assertEqual(result['status'], 'passed')
        self.assertEqual(len(result['steps']), 2)
        self.assertTrue(result['steps'][0]['success'])
        self.assertTrue(result['steps'][1]['success'])
        self.assertEqual(len(result['screenshots']), 1)
        self.assertTrue(result['screenshots'][0]['url'].startswith('data:image/png;base64,'))

    def test_selenium_case_continues_after_screenshot_step_without_element(self):
        executor = self._make_executor()
        driver = FakeSeleniumDriver()

        case_data = {
            'id': 2,
            'name': 'selenium-case-with-screenshot',
            'project_global_variables': [],
            'steps': [
                {
                    'step_number': 1,
                    'action_type': 'screenshot',
                    'description': 'manual screenshot',
                    'wait_time': 1000,
                    'input_value': '',
                    'assert_value': '',
                    'assert_type': '',
                    'save_as': '',
                    'element': None,
                },
                {
                    'step_number': 2,
                    'action_type': 'wait',
                    'description': 'wait after screenshot',
                    'wait_time': 200,
                    'input_value': '',
                    'assert_value': '',
                    'assert_type': '',
                    'save_as': '',
                    'element': None,
                },
            ],
        }

        with patch('apps.ui_automation.test_executor.time.sleep', return_value=None):
            result = executor.execute_test_case_selenium_no_db(driver, case_data)

        self.assertEqual(result['status'], 'passed')
        self.assertEqual(len(result['steps']), 2)
        self.assertTrue(result['steps'][0]['success'])
        self.assertTrue(result['steps'][1]['success'])
        self.assertEqual(len(result['screenshots']), 1)
        self.assertTrue(result['screenshots'][0]['url'].startswith('data:image/png;base64,'))
        self.assertGreaterEqual(driver.screenshot_calls, 1)
