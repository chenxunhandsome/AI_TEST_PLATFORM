import json
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.ui_automation.ai_case_generator import (
    apply_sampling_params,
    generate_ui_test_case_manifest,
    parse_uploaded_case_source,
)
from apps.ui_automation.models import UiProject


User = get_user_model()


class AITestCaseGenerationServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='ai_case_generator_tester',
            email='ai_case_generator_tester@example.com',
            password='password123',
        )
        self.project = UiProject.objects.create(
            name='AI UI Project',
            description='',
            status='IN_PROGRESS',
            base_url='https://example.com',
            owner=self.user,
        )

    def test_heuristic_generation_returns_importable_manifest(self):
        manifest, warnings, mode = generate_ui_test_case_manifest(
            self.project,
            '用例：登录成功\n输入账号 admin\n输入密码 123456\n点击登录按钮\n验证显示首页',
            use_ai=False,
        )

        self.assertEqual(mode, 'heuristic')
        self.assertEqual(manifest['format'], 'ui_automation_test_cases')
        self.assertEqual(manifest['version'], 1)
        self.assertEqual(len(manifest['test_cases']), 1)
        self.assertEqual(manifest['test_cases'][0]['name'], '登录成功')
        self.assertGreaterEqual(len(manifest['test_cases'][0]['steps']), 4)
        self.assertEqual(manifest['test_cases'][0]['steps'][0]['action_type'], 'fill')
        self.assertIsInstance(warnings, list)

    def test_existing_manifest_is_normalized_without_ai_call(self):
        source_manifest = {
            'format': 'ui_automation_test_cases',
            'version': 1,
            'test_cases': [
                {
                    'name': '模板用例',
                    'priority': 'invalid-priority',
                    'status': 'invalid-status',
                    'steps': [
                        {
                            'description': '点击登录',
                            'action_type': 'click',
                            'element': {
                                'name': '登录',
                                'locator_strategy': 'text',
                                'locator_value': '登录',
                            },
                        }
                    ],
                }
            ],
        }

        manifest, warnings, mode = generate_ui_test_case_manifest(
            self.project,
            json.dumps(source_manifest, ensure_ascii=False),
            use_ai=False,
        )

        self.assertEqual(mode, 'manifest')
        self.assertEqual(manifest['test_cases'][0]['priority'], 'medium')
        self.assertEqual(manifest['test_cases'][0]['status'], 'draft')
        self.assertEqual(manifest['test_cases'][0]['steps'][0]['element']['element_type'], 'BUTTON')
        self.assertEqual(warnings, [])

    def test_parse_uploaded_csv_source(self):
        uploaded = SimpleUploadedFile(
            'cases.csv',
            'case_name,step_description\n登录成功,点击登录按钮\n'.encode('utf-8-sig'),
            content_type='text/csv',
        )

        parsed = parse_uploaded_case_source(uploaded)

        self.assertEqual(parsed.name, 'cases.csv')
        self.assertEqual(parsed.source_type, 'file')
        self.assertIn('登录成功', parsed.text)
        self.assertIn('点击登录按钮', parsed.text)

    def test_rejects_unsupported_uploaded_file_type(self):
        uploaded = SimpleUploadedFile('cases.docx', b'content')

        with self.assertRaises(ValidationError):
            parse_uploaded_case_source(uploaded)

    def test_claude_like_model_does_not_send_top_p(self):
        payload = {}
        model_config = SimpleNamespace(
            model_type='anthropic',
            model_name='claude-3-5-sonnet',
            temperature=0.2,
            top_p=0.9,
        )

        apply_sampling_params(payload, model_config)

        self.assertEqual(payload['temperature'], 0.2)
        self.assertNotIn('top_p', payload)

    def test_non_claude_model_sends_top_p(self):
        payload = {}
        model_config = SimpleNamespace(
            model_type='deepseek',
            model_name='deepseek-chat',
            temperature=0.2,
            top_p=0.9,
        )

        apply_sampling_params(payload, model_config)

        self.assertEqual(payload['temperature'], 0.2)
        self.assertEqual(payload['top_p'], 0.9)
