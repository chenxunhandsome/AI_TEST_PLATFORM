from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import AsyncMock, patch

from apps.ui_automation.local_execution_service import build_test_case_payload, execute_serialized_test_case
from apps.ui_automation.playwright_engine import PlaywrightTestEngine


class FakeStepQuerySet:
    def __init__(self, steps):
        self._steps = list(steps)

    def all(self):
        return self

    def order_by(self, field_name):
        if field_name != 'step_number':
            raise AssertionError(f'unexpected order_by field: {field_name}')
        return sorted(self._steps, key=lambda item: item.step_number)


def make_step(step_number, action_type, input_value='', assert_value='', save_as='', wait_time=1000, is_enabled=True):
    return SimpleNamespace(
        step_number=step_number,
        action_type=action_type,
        description=f'step-{step_number}',
        is_enabled=is_enabled,
        save_as=save_as,
        input_value=input_value,
        wait_time=wait_time,
        assert_type='textEquals' if action_type == 'assert' else '',
        assert_value=assert_value,
        element=None,
    )


class BuildTestCasePayloadTests(TestCase):
    def test_build_test_case_payload_includes_project_browser_resolution(self):
        project = SimpleNamespace(
            id=6,
            name='demo-project',
            base_url='http://example.com',
            global_variables=[],
            browser_width=1600,
            browser_height=900,
        )
        test_case = SimpleNamespace(
            id=16,
            name='resolution-case',
            project_id=project.id,
            project=project,
            steps=FakeStepQuerySet([]),
        )

        payload = build_test_case_payload(test_case)

        self.assertEqual(payload['browser_width'], 1600)
        self.assertEqual(payload['browser_height'], 900)

    def test_build_test_case_payload_pre_resolves_project_and_runtime_variables(self):
        project = SimpleNamespace(
            id=1,
            name='demo-project',
            base_url='http://example.com',
            global_variables=[{'name': 'base_url', 'value': 'http://service.local'}],
        )
        test_case = SimpleNamespace(
            id=11,
            name='demo-case',
            project_id=project.id,
            project=project,
            steps=FakeStepQuerySet([
                make_step(1, 'fill', input_value='${base_url}/login', save_as='login_url'),
                make_step(2, 'fill', input_value='${login_url}?next=${timestamp()}'),
            ]),
        )

        payload = build_test_case_payload(test_case)

        self.assertEqual(payload['steps'][0]['input_value'], 'http://service.local/login')
        self.assertTrue(payload['steps'][1]['input_value'].startswith('http://service.local/login?next='))
        self.assertNotIn('${timestamp()}', payload['steps'][1]['input_value'])

    def test_build_test_case_payload_keeps_assert_saved_variables_available(self):
        project = SimpleNamespace(
            id=3,
            name='demo-project',
            base_url='http://example.com',
            global_variables=[],
        )
        test_case = SimpleNamespace(
            id=13,
            name='assert-case',
            project_id=project.id,
            project=project,
            steps=FakeStepQuerySet([
                make_step(1, 'assert', assert_value='expected-token', save_as='token'),
                make_step(2, 'fill', input_value='Bearer ${token}'),
            ]),
        )

        payload = build_test_case_payload(test_case)

        self.assertEqual(payload['steps'][0]['assert_value'], 'expected-token')
        self.assertEqual(payload['steps'][1]['input_value'], 'Bearer expected-token')

    def test_build_test_case_payload_keeps_fill_and_enter_saved_variables_available(self):
        project = SimpleNamespace(
            id=4,
            name='demo-project',
            base_url='http://example.com',
            global_variables=[],
        )
        test_case = SimpleNamespace(
            id=14,
            name='fill-enter-case',
            project_id=project.id,
            project=project,
            steps=FakeStepQuerySet([
                make_step(1, 'fillAndEnter', input_value='hello world', save_as='keyword'),
                make_step(2, 'fill', input_value='search=${keyword}'),
            ]),
        )

        payload = build_test_case_payload(test_case)

        self.assertEqual(payload['steps'][0]['input_value'], 'hello world')
        self.assertEqual(payload['steps'][1]['input_value'], 'search=hello world')

    def test_build_test_case_payload_does_not_publish_runtime_variables_from_disabled_steps(self):
        project = SimpleNamespace(
            id=5,
            name='demo-project',
            base_url='http://example.com',
            global_variables=[],
        )
        test_case = SimpleNamespace(
            id=15,
            name='disabled-step-case',
            project_id=project.id,
            project=project,
            steps=FakeStepQuerySet([
                make_step(1, 'fill', input_value='disabled-value', save_as='from_disabled', is_enabled=False),
                make_step(2, 'fill', input_value='reuse=${from_disabled}'),
            ]),
        )

        payload = build_test_case_payload(test_case)

        self.assertFalse(payload['steps'][0]['is_enabled'])
        self.assertEqual(payload['steps'][1]['input_value'], 'reuse=${from_disabled}')

    def test_local_execution_keeps_runtime_variable_value_consistent_for_dynamic_functions(self):
        project = SimpleNamespace(
            id=2,
            name='demo-project',
            base_url='http://example.com',
            global_variables=[],
        )
        test_case = SimpleNamespace(
            id=12,
            name='assert-case',
            project_id=project.id,
            project=project,
            steps=FakeStepQuerySet([
                make_step(1, 'fill', input_value='${random_string(8, all, 1)}', save_as='data_abc'),
                make_step(2, 'fill', input_value='${data_abc}'),
            ]),
        )

        payload = build_test_case_payload(test_case)
        self.assertEqual(payload['steps'][0]['input_value'], payload['steps'][1]['input_value'])

        captured_inputs = []

        class DummyEngine:
            def __init__(self, *args, **kwargs):
                pass

            async def start(self):
                pass

            async def stop(self):
                pass

            async def navigate(self, url):
                return True, f'navigate:{url}'

            async def execute_step(self, step, element_data):
                captured_inputs.append(step.input_value)
                return True, 'ok', None

            async def capture_screenshot(self):
                return None

        with patch('apps.ui_automation.local_execution_service.PlaywrightTestEngine', DummyEngine):
            result = execute_serialized_test_case(payload, engine_type='playwright')

        self.assertEqual(result['status'], 'passed')
        self.assertEqual(len(captured_inputs), 2)
        self.assertEqual(captured_inputs[0], captured_inputs[1])

    def test_local_execution_fill_and_enter_keeps_runtime_variable_value_consistent(self):
        payload = {
            'test_case_id': 21,
            'test_case_name': 'fill-enter-runtime-case',
            'project_id': 2,
            'project_name': 'demo-project',
            'base_url': 'http://example.com',
            'project_global_variables': [],
            'steps': [
                {
                    'step_number': 1,
                    'action_type': 'fillAndEnter',
                    'description': 'fill and enter',
                    'save_as': 'query_value',
                    'input_value': '${random_string(8, all, 1)}',
                    'wait_time': 1000,
                    'assert_type': '',
                    'assert_value': '',
                    'element_data': None,
                },
                {
                    'step_number': 2,
                    'action_type': 'fill',
                    'description': 'reuse query',
                    'save_as': '',
                    'input_value': '${query_value}',
                    'wait_time': 1000,
                    'assert_type': '',
                    'assert_value': '',
                    'element_data': None,
                },
            ],
        }

        captured_inputs = []

        class DummyEngine:
            def __init__(self, *args, **kwargs):
                pass

            async def start(self):
                pass

            async def stop(self):
                pass

            async def navigate(self, url):
                return True, f'navigate:{url}'

            async def execute_step(self, step, element_data):
                captured_inputs.append((step.action_type, step.input_value))
                return True, 'ok', None

            async def capture_screenshot(self):
                return None

        with patch('apps.ui_automation.local_execution_service.PlaywrightTestEngine', DummyEngine):
            result = execute_serialized_test_case(payload, engine_type='playwright')

        self.assertEqual(result['status'], 'passed')
        self.assertEqual(len(captured_inputs), 2)
        self.assertEqual(captured_inputs[0][0], 'fillAndEnter')
        self.assertEqual(captured_inputs[0][1], captured_inputs[1][1])

    def test_local_execution_skips_disabled_steps(self):
        payload = {
            'test_case_id': 22,
            'test_case_name': 'disabled-step-runtime-case',
            'project_id': 2,
            'project_name': 'demo-project',
            'base_url': 'http://example.com',
            'project_global_variables': [],
            'steps': [
                {
                    'step_number': 1,
                    'action_type': 'click',
                    'description': 'disabled click',
                    'is_enabled': False,
                    'save_as': '',
                    'input_value': '',
                    'wait_time': 1000,
                    'assert_type': '',
                    'assert_value': '',
                    'element_data': None,
                },
                {
                    'step_number': 2,
                    'action_type': 'fill',
                    'description': 'enabled fill',
                    'is_enabled': True,
                    'save_as': '',
                    'input_value': 'active',
                    'wait_time': 1000,
                    'assert_type': '',
                    'assert_value': '',
                    'element_data': None,
                },
            ],
        }

        executed_steps = []

        class DummyEngine:
            def __init__(self, *args, **kwargs):
                pass

            async def start(self):
                pass

            async def stop(self):
                pass

            async def navigate(self, url):
                return True, f'navigate:{url}'

            async def execute_step(self, step, element_data):
                executed_steps.append(step.description)
                return True, 'ok', None

            async def capture_screenshot(self):
                return None

        with patch('apps.ui_automation.local_execution_service.PlaywrightTestEngine', DummyEngine):
            result = execute_serialized_test_case(payload, engine_type='playwright')

        self.assertEqual(result['status'], 'passed')
        self.assertEqual(executed_steps, ['enabled fill'])
        logs = result['logs']
        self.assertIn('"status": "skipped"', logs)
        self.assertIn('步骤已禁用，已跳过执行', logs)


class PlaywrightNavigateTests(TestCase):
    def test_navigate_treats_networkidle_timeout_as_non_fatal_after_domcontentloaded(self):
        class FakeResponse:
            status = 200

        class FakePage:
            def __init__(self):
                self.goto_calls = []
                self.wait_calls = []

            async def goto(self, url, wait_until, timeout):
                self.goto_calls.append((url, wait_until, timeout))
                return FakeResponse()

            async def wait_for_load_state(self, state, timeout):
                self.wait_calls.append((state, timeout))
                if state == 'networkidle':
                    raise RuntimeError('page keeps polling')

        engine = PlaywrightTestEngine()
        engine.page = FakePage()

        with patch('apps.ui_automation.playwright_engine.asyncio.sleep', new=AsyncMock()) as sleep_mock:
            with patch('platform.system', return_value='Linux'):
                import asyncio
                success, log = asyncio.run(engine.navigate('http://example.com'))

        self.assertTrue(success)
        self.assertEqual(
            engine.page.goto_calls,
            [('http://example.com', 'domcontentloaded', 30000)]
        )
        self.assertIn(('load', 10000), engine.page.wait_calls)
        self.assertIn(('networkidle', 5000), engine.page.wait_calls)
        self.assertIn('domcontentloaded', log)
        self.assertIn('networkidle未稳定', log)
        sleep_mock.assert_awaited()


class EngineResolutionForwardingTests(TestCase):
    def test_playwright_execution_forwards_project_resolution_to_engine(self):
        captured_kwargs = {}

        class DummyEngine:
            def __init__(self, *args, **kwargs):
                captured_kwargs.update(kwargs)

            async def start(self):
                pass

            async def stop(self):
                pass

            async def navigate(self, url):
                return True, f'navigate:{url}'

            async def execute_step(self, step, element_data):
                return True, 'ok', None

            async def capture_screenshot(self):
                return None

        payload = {
            'test_case_id': 31,
            'test_case_name': 'playwright-resolution-case',
            'project_id': 7,
            'project_name': 'demo-project',
            'base_url': '',
            'project_global_variables': [],
            'browser_width': 1440,
            'browser_height': 810,
            'steps': [],
        }

        with patch('apps.ui_automation.local_execution_service.PlaywrightTestEngine', DummyEngine):
            result = execute_serialized_test_case(payload, engine_type='playwright')

        self.assertEqual(result['status'], 'passed')
        self.assertEqual(captured_kwargs['browser_width'], 1440)
        self.assertEqual(captured_kwargs['browser_height'], 810)

    def test_selenium_execution_forwards_project_resolution_to_engine(self):
        captured_kwargs = {}

        class DummyEngine:
            def __init__(self, *args, **kwargs):
                captured_kwargs.update(kwargs)

            @staticmethod
            def check_browser_available(browser):
                return True, ''

            def start(self):
                pass

            def stop(self):
                pass

            def navigate(self, url):
                return True, f'navigate:{url}'

            def execute_step(self, step, element_data):
                return True, 'ok', None

            def capture_screenshot(self):
                return None

        payload = {
            'test_case_id': 32,
            'test_case_name': 'selenium-resolution-case',
            'project_id': 8,
            'project_name': 'demo-project',
            'base_url': '',
            'project_global_variables': [],
            'browser_width': 1536,
            'browser_height': 864,
            'steps': [],
        }

        with patch('apps.ui_automation.local_execution_service.SeleniumTestEngine', DummyEngine):
            result = execute_serialized_test_case(payload, engine_type='selenium')

        self.assertEqual(result['status'], 'passed')
        self.assertEqual(captured_kwargs['browser_width'], 1536)
        self.assertEqual(captured_kwargs['browser_height'], 864)
