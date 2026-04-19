import json
from unittest import TestCase
from unittest.mock import patch

from apps.ui_automation.local_execution_service import execute_serialized_test_case
from apps.ui_automation.playwright_engine import PlaywrightTestEngine


class FakeAsyncPlaywrightPage:
    def __init__(self, context, url='http://example.com'):
        self.context = context
        self.url = url
        self.closed = False
        self.events = {}
        self.load_state_calls = []
        self.wait_timeout_calls = []

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

    async def title(self):
        return 'Fake Async Page'

    async def wait_for_load_state(self, state, timeout):
        self.load_state_calls.append((state, timeout))

    async def wait_for_timeout(self, timeout):
        self.wait_timeout_calls.append(timeout)


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


class DummyEngine(PlaywrightTestEngine):
    last_instance = None

    async def start(self):
        DummyEngine.last_instance = self
        self.context = FakeAsyncPlaywrightContext()
        self.page = FakeAsyncPlaywrightPage(self.context, 'http://example.com/current')
        self.context.pages.append(self.page)
        self._register_context_handlers()
        self._register_page_handlers(self.page)

    async def stop(self):
        return None

    async def navigate(self, url):
        return True, f'navigate:{url}'

    async def capture_screenshot(self):
        return None


class LocalExecutionCloseCurrentPageRegressionTests(TestCase):
    def test_local_execution_switch_tab_then_close_current_page_uses_new_page(self):
        payload = {
            'test_case_id': 31,
            'test_case_name': 'switch-tab-close-page-local',
            'project_id': 5,
            'project_name': 'demo-project',
            'base_url': '',
            'project_global_variables': [],
            'steps': [
                {
                    'step_number': 1,
                    'action_type': 'switchTab',
                    'description': 'switch to new tab',
                    'save_as': '',
                    'input_value': '',
                    'wait_time': 1000,
                    'assert_type': '',
                    'assert_value': '',
                    'element_data': None,
                },
                {
                    'step_number': 2,
                    'action_type': 'closeCurrentPage',
                    'description': 'close current page',
                    'save_as': '',
                    'input_value': '',
                    'wait_time': 1000,
                    'assert_type': '',
                    'assert_value': '',
                    'element_data': None,
                },
            ],
        }

        clock = {'now': 0.0, 'sleep_calls': 0}

        async def fake_sleep(_seconds):
            clock['sleep_calls'] += 1
            clock['now'] += 0.6
            engine = DummyEngine.last_instance
            if engine and clock['sleep_calls'] == 3:
                next_page = FakeAsyncPlaywrightPage(engine.context, 'http://example.com/next')
                engine.context.pages.append(next_page)

        with patch('apps.ui_automation.local_execution_service.PlaywrightTestEngine', DummyEngine):
            with patch('apps.ui_automation.playwright_engine.time.time', new=lambda: clock['now']):
                with patch('apps.ui_automation.playwright_engine.asyncio.sleep', new=fake_sleep):
                    result = execute_serialized_test_case(payload, engine_type='playwright')

        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['error_message'], '')
        self.assertEqual(result['errors'], [])

        step_results = json.loads(result['logs'])
        self.assertEqual(len(step_results), 2)
        self.assertTrue(all(step['success'] for step in step_results))

        engine = DummyEngine.last_instance
        self.assertIsNotNone(engine)
        current_page = engine.context.pages[0]
        next_page = engine.context.pages[1]

        self.assertGreaterEqual(clock['sleep_calls'], 3)
        self.assertTrue(next_page.closed)
        self.assertIs(engine.page, current_page)
        self.assertIn(1500, next_page.wait_timeout_calls)
