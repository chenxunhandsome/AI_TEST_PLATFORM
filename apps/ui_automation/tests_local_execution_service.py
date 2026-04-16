from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from apps.ui_automation.local_execution_service import build_test_case_payload, execute_serialized_test_case


class FakeStepQuerySet:
    def __init__(self, steps):
        self._steps = list(steps)

    def all(self):
        return self

    def order_by(self, field_name):
        if field_name != 'step_number':
            raise AssertionError(f'unexpected order_by field: {field_name}')
        return sorted(self._steps, key=lambda item: item.step_number)


def make_step(step_number, action_type, input_value='', assert_value='', save_as='', wait_time=1000):
    return SimpleNamespace(
        step_number=step_number,
        action_type=action_type,
        description=f'step-{step_number}',
        save_as=save_as,
        input_value=input_value,
        wait_time=wait_time,
        assert_type='textEquals' if action_type == 'assert' else '',
        assert_value=assert_value,
        element=None,
    )


class BuildTestCasePayloadTests(TestCase):
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
