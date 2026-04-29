from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.ui_automation.local_execution_service import build_test_case_payload
from apps.ui_automation.models import Element, LocatorStrategy, TestCase as UiTestCase, TestCaseStep, UiProject
from apps.ui_automation.variable_resolver import (
    clear_runtime_variables,
    resolve_element_locator_payload,
    set_runtime_variable,
)


User = get_user_model()


class LocatorParameterizationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='locator_parameter_tester',
            email='locator_parameter_tester@example.com',
            password='password123',
        )
        self.project = UiProject.objects.create(
            name='locator-project',
            description='',
            status='IN_PROGRESS',
            base_url='https://example.com',
            owner=self.user,
            global_variables=[
                {'name': 'text', 'value': '提交', 'description': ''},
            ],
        )
        self.xpath_strategy = LocatorStrategy.objects.create(name='XPath', description='')

    def tearDown(self):
        clear_runtime_variables()

    def test_resolve_element_locator_payload_with_runtime_variable(self):
        set_runtime_variable('text', '确认')

        payload = resolve_element_locator_payload({
            'locator_strategy': 'XPath',
            'locator_value': "//span[text()='${text}']",
            'name': '确认按钮',
        })

        self.assertEqual(payload['locator_value'], "//span[text()='确认']")

    def test_resolve_element_locator_payload_with_builtin_date_function(self):
        payload = resolve_element_locator_payload({
            'locator_strategy': 'XPath',
            'locator_value': "//span[text()='${date}']",
            'name': '日期文本',
        })

        self.assertNotIn('${date}', payload['locator_value'])
        self.assertRegex(payload['locator_value'], r"//span\[text\(\)='\d{4}-\d{2}-\d{2}'\]")

    def test_build_local_execution_payload_resolves_project_global_variable_in_locator(self):
        element = Element.objects.create(
            project=self.project,
            name='提交按钮',
            element_type='BUTTON',
            locator_strategy=self.xpath_strategy,
            locator_value="//span[text()='${text}']",
            created_by=self.user,
        )
        test_case = UiTestCase.objects.create(
            name='locator-case',
            description='',
            project=self.project,
            status='draft',
            priority='medium',
            created_by=self.user,
        )
        TestCaseStep.objects.create(
            test_case=test_case,
            step_number=1,
            action_type='click',
            element=element,
            description='点击提交',
        )

        payload = build_test_case_payload(test_case)

        self.assertEqual(
            payload['steps'][0]['element_data']['locator_value'],
            "//span[text()='提交']",
        )

    def test_build_local_execution_payload_resolves_prior_step_saved_variable_in_locator(self):
        input_element = Element.objects.create(
            project=self.project,
            name='文本输入框',
            element_type='INPUT',
            locator_strategy=self.xpath_strategy,
            locator_value="//input[@name='keyword']",
            created_by=self.user,
        )
        target_element = Element.objects.create(
            project=self.project,
            name='动态文本',
            element_type='TEXT',
            locator_strategy=self.xpath_strategy,
            locator_value="//span[text()='${dynamic_text}']",
            created_by=self.user,
        )
        test_case = UiTestCase.objects.create(
            name='saved-variable-locator-case',
            description='',
            project=self.project,
            status='draft',
            priority='medium',
            created_by=self.user,
        )
        TestCaseStep.objects.create(
            test_case=test_case,
            step_number=1,
            action_type='fill',
            element=input_element,
            input_value='运行时文本',
            save_as='dynamic_text',
            description='输入并保存变量',
        )
        TestCaseStep.objects.create(
            test_case=test_case,
            step_number=2,
            action_type='click',
            element=target_element,
            description='点击动态文本',
        )

        payload = build_test_case_payload(test_case)

        self.assertEqual(
            payload['steps'][1]['element_data']['locator_value'],
            "//span[text()='运行时文本']",
        )
