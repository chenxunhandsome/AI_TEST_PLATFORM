import time
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import patch

from selenium.common.exceptions import NoAlertPresentException

from apps.ui_automation.playwright_engine import PlaywrightTestEngine
from apps.ui_automation.selenium_engine import SeleniumTestEngine
from apps.ui_automation.test_executor import TestExecutor


def make_step(action_type, wait_time=1000):
    return SimpleNamespace(
        action_type=action_type,
        description=action_type,
        save_as='',
        input_value='',
        wait_time=wait_time,
        assert_type='',
        assert_value='',
    )


class FakeAsyncPlaywrightPage:
    def __init__(self, context, url='http://example.com'):
        self.context = context
        self.url = url
        self.closed = False
        self.events = {}

    def on(self, event_name, handler):
        self.events[event_name] = handler

    def is_closed(self):
        return self.closed

    async def close(self):
        self.closed = True

    async def bring_to_front(self):
        return None

    async def goto(self, url, **kwargs):
        self.url = url


class FakeAsyncPlaywrightContext:
    def __init__(self):
        self.pages = []
        self.events = {}

    def on(self, event_name, handler):
        self.events[event_name] = handler

    async def new_page(self):
        page = FakeAsyncPlaywrightPage(self, 'about:blank')
        self.pages.append(page)
        return page


class FakeAlert:
    def __init__(self, text):
        self.text = text
        self.dismissed = False
        self.accepted = False

    def dismiss(self):
        self.dismissed = True

    def accept(self):
        self.accepted = True


class FakeSeleniumSwitchTo:
    def __init__(self, driver, alert=None):
        self.driver = driver
        self._alert = alert

    @property
    def alert(self):
        if self._alert is None:
            raise NoAlertPresentException()
        return self._alert

    def new_window(self, kind):
        self.driver.open_new_window()

    def window(self, handle):
        self.driver.current_window_handle = handle
        self.driver.current_url = self.driver.urls[handle]


class FakeSeleniumDriver:
    def __init__(self, alert=None):
        self.window_handles = ['main']
        self.current_window_handle = 'main'
        self.urls = {'main': 'http://example.com'}
        self.current_url = self.urls['main']
        self.switch_to = FakeSeleniumSwitchTo(self, alert=alert)

    def open_new_window(self):
        handle = f'window-{len(self.window_handles) + 1}'
        self.window_handles.append(handle)
        self.urls[handle] = 'about:blank'
        self.current_window_handle = handle
        self.current_url = self.urls[handle]

    def get(self, url):
        self.urls[self.current_window_handle] = url
        self.current_url = url

    def close(self):
        closed_handle = self.current_window_handle
        self.window_handles = [handle for handle in self.window_handles if handle != closed_handle]
        self.urls.pop(closed_handle, None)
        if self.window_handles:
            self.current_window_handle = self.window_handles[-1]
            self.current_url = self.urls[self.current_window_handle]
        else:
            self.current_window_handle = None
            self.current_url = ''


class FakeSyncPlaywrightPage:
    def __init__(self, context, url='http://example.com'):
        self.context = context
        self.url = url
        self.closed = False
        self.events = {}
        self.wait_calls = []

    def on(self, event_name, handler):
        self.events[event_name] = handler

    def is_closed(self):
        return self.closed

    def close(self):
        self.closed = True

    def bring_to_front(self):
        return None

    def goto(self, url, **kwargs):
        self.url = url

    def wait_for_timeout(self, timeout):
        self.wait_calls.append(timeout)

    def title(self):
        return 'Fake Page'


class FakeSyncPlaywrightContext:
    def __init__(self):
        self.pages = []
        self.events = {}

    def on(self, event_name, handler):
        self.events[event_name] = handler

    def new_page(self):
        page = FakeSyncPlaywrightPage(self, 'about:blank')
        self.pages.append(page)
        return page


class CloseCurrentPageEngineTests(IsolatedAsyncioTestCase):
    async def test_playwright_close_current_page_consumes_recent_dialog(self):
        engine = PlaywrightTestEngine()
        engine._recent_dialog = {
            'type': 'alert',
            'message': 'Need close',
            'timestamp': time.time(),
        }

        success, log, screenshot = await engine.execute_step(make_step('closeCurrentPage'), {})

        self.assertTrue(success)
        self.assertIsNone(screenshot)
        self.assertIn('已关闭浏览器弹窗', log)
        self.assertIn('Need close', log)

    async def test_playwright_close_current_page_keeps_session_alive_for_last_page(self):
        engine = PlaywrightTestEngine()
        context = FakeAsyncPlaywrightContext()
        current_page = FakeAsyncPlaywrightPage(context)
        context.pages.append(current_page)
        engine.context = context
        engine.page = current_page

        success, log, _ = await engine.execute_step(make_step('closeCurrentPage'), {})

        self.assertTrue(success)
        self.assertTrue(current_page.closed)
        self.assertIsNot(engine.page, current_page)
        self.assertEqual(engine.page.url, 'about:blank')
        self.assertEqual(len([page for page in context.pages if not page.is_closed()]), 1)
        self.assertIn('保留会话', log)


class CloseCurrentPageSeleniumEngineTests(TestCase):
    def test_selenium_close_current_page_closes_alert_first(self):
        engine = SeleniumTestEngine()
        alert = FakeAlert('Need close')
        engine.driver = FakeSeleniumDriver(alert=alert)

        success, log, screenshot = engine.execute_step(make_step('closeCurrentPage'), {})

        self.assertTrue(success)
        self.assertIsNone(screenshot)
        self.assertTrue(alert.dismissed or alert.accepted)
        self.assertIn('已关闭浏览器弹窗', log)
        self.assertIn('Need close', log)

    def test_selenium_close_current_page_keeps_session_alive_for_last_window(self):
        engine = SeleniumTestEngine()
        engine.driver = FakeSeleniumDriver()

        success, log, _ = engine.execute_step(make_step('closeCurrentPage'), {})

        self.assertTrue(success)
        self.assertEqual(engine.driver.window_handles, ['window-2'])
        self.assertEqual(engine.driver.current_url, 'about:blank')
        self.assertIn('保留会话', log)


class CloseCurrentPageLegacyExecutorTests(TestCase):
    def _make_executor(self):
        return TestExecutor(
            test_suite=SimpleNamespace(project=SimpleNamespace(base_url='')),
            engine='playwright',
            browser='chrome',
            headless=True,
            executed_by=None,
        )

    def test_legacy_playwright_case_continues_after_close_current_page(self):
        executor = self._make_executor()
        context = FakeSyncPlaywrightContext()
        current_page = FakeSyncPlaywrightPage(context)
        context.pages.append(current_page)
        executor.current_page = current_page

        case_data = {
            'id': 1,
            'name': 'close-page-case',
            'project_global_variables': [],
            'steps': [
                {
                    'step_number': 1,
                    'action_type': 'closeCurrentPage',
                    'description': 'close current page',
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
                    'description': 'wait after close',
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
        self.assertEqual(executor.current_page.url, 'about:blank')

    def test_legacy_selenium_case_continues_after_close_current_page(self):
        executor = self._make_executor()
        driver = FakeSeleniumDriver()

        case_data = {
            'id': 2,
            'name': 'close-window-case',
            'project_global_variables': [],
            'steps': [
                {
                    'step_number': 1,
                    'action_type': 'closeCurrentPage',
                    'description': 'close current window',
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
                    'description': 'wait after close',
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
        self.assertEqual(driver.current_url, 'about:blank')
