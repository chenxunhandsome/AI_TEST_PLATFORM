import io
import json
import zipfile
from types import SimpleNamespace
from unittest.mock import patch
from xml.sax.saxutils import escape

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.ui_automation.ai_case_generator import (
    apply_sampling_params,
    build_generation_system_prompt,
    build_routed_generation_skill_content,
    call_openai_compatible_model,
    ensure_builtin_generation_skill_modules,
    estimate_generation_max_tokens,
    extract_data_element_creation_intents,
    extract_json_payload,
    generate_skill_module_content_draft,
    generate_ui_test_case_manifest,
    parse_uploaded_case_source,
    split_source_into_cases,
)
from apps.ui_automation.models import AITestCaseGenerationSkillModule, Element, LocatorStrategy, UiProject


User = get_user_model()


def build_excel_column_name(column_index):
    result = ''
    current = int(column_index)
    while current > 0:
        current, remainder = divmod(current - 1, 26)
        result = chr(ord('A') + remainder) + result
    return result or 'A'


def build_minimal_xlsx(rows, merges=None):
    shared_strings = []
    shared_string_index = {}

    def get_shared_string_index(value):
        text = str(value or '')
        if text not in shared_string_index:
            shared_string_index[text] = len(shared_strings)
            shared_strings.append(text)
        return shared_string_index[text]

    sheet_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for column_index, value in enumerate(row, start=1):
            if value is None:
                continue
            shared_index = get_shared_string_index(value)
            cell_ref = f'{build_excel_column_name(column_index)}{row_index}'
            cells.append(f'<c r="{cell_ref}" t="s"><v>{shared_index}</v></c>')
        sheet_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')

    shared_strings_xml = ''.join(
        f'<si><t>{escape(item)}</t></si>'
        for item in shared_strings
    )
    merge_ranges = merges or []
    merge_xml = ''
    if merge_ranges:
        merge_xml = (
            f'<mergeCells count="{len(merge_ranges)}">'
            + ''.join(f'<mergeCell ref="{escape(item)}"/>' for item in merge_ranges)
            + '</mergeCells>'
        )
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetData>'
        f'{"".join(sheet_rows)}'
        '</sheetData>'
        f'{merge_xml}'
        '</worksheet>'
    )
    shared_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        f'count="{len(shared_strings)}" uniqueCount="{len(shared_strings)}">'
        f'{shared_strings_xml}'
        '</sst>'
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('xl/worksheets/sheet1.xml', sheet_xml)
        archive.writestr('xl/sharedStrings.xml', shared_xml)
    return buffer.getvalue()


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
        self.locator_strategy = LocatorStrategy.objects.create(name='XPath', description='')

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

    def test_parse_uploaded_xlsx_source_preserves_multiple_cases(self):
        xlsx_bytes = build_minimal_xlsx([
            ['用例名称', '文件夹', '优先级', '前置条件', '步骤序号', '操作描述', '测试数据', '预期结果', '备注'],
            ['新建SYS Integer要素', '', 'high', '用户已存在且账号可用', '1', '登录', '', '', ''],
            ['', '', '', '', '2', '进入管理模式', '', '', ''],
            ['', '', '', '', '3', '新建数据要素，数据定义是SYS Integer', '', '', ''],
            ['', '', '', '', '4', '验证新建成功', '', '弹出成功toast', ''],
            ['新建SYS Currency要素', '', 'high', '用户已存在且账号可用', '1', '登录', '', '', ''],
            ['', '', '', '', '2', '进入管理模式', '', '', ''],
            ['', '', '', '', '3', '新建数据要素，数据定义是SYS Currency', '', '', ''],
            ['', '', '', '', '4', '验证新建成功', '', '弹出成功toast', ''],
        ])
        uploaded = SimpleUploadedFile(
            'cases_template.xlsx',
            xlsx_bytes,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

        parsed = parse_uploaded_case_source(uploaded)
        cases = split_source_into_cases(parsed.text)

        self.assertIn('用例：新建SYS Integer要素', parsed.text)
        self.assertIn('用例：新建SYS Currency要素', parsed.text)
        self.assertEqual(len(cases), 2)
        self.assertEqual(cases[0][0], '新建SYS Integer要素')
        self.assertEqual(cases[1][0], '新建SYS Currency要素')

    def test_generate_manifest_from_uploaded_xlsx_contains_multiple_cases(self):
        xlsx_bytes = build_minimal_xlsx([
            ['用例名称', '文件夹', '优先级', '前置条件', '步骤序号', '操作描述', '测试数据', '预期结果', '备注'],
            ['新建SYS Integer要素', '', 'high', '用户已存在且账号可用', '1', '登录', '', '', ''],
            ['', '', '', '', '2', '进入管理模式', '', '', ''],
            ['', '', '', '', '3', '新建数据要素，数据定义是SYS Integer', '', '', ''],
            ['', '', '', '', '4', '验证新建成功', '', '弹出成功toast', ''],
            ['新建SYS Currency要素', '', 'high', '用户已存在且账号可用', '1', '登录', '', '', ''],
            ['', '', '', '', '2', '进入管理模式', '', '', ''],
            ['', '', '', '', '3', '新建数据要素，数据定义是SYS Currency', '', '', ''],
            ['', '', '', '', '4', '验证新建成功', '', '弹出成功toast', ''],
        ])
        uploaded = SimpleUploadedFile(
            'cases_template.xlsx',
            xlsx_bytes,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

        parsed = parse_uploaded_case_source(uploaded)
        manifest, warnings, mode = generate_ui_test_case_manifest(
            self.project,
            parsed.text,
            use_ai=False,
        )

        self.assertEqual(mode, 'heuristic')
        self.assertEqual(len(manifest['test_cases']), 2)
        self.assertEqual(manifest['test_cases'][0]['name'], '新建SYS Integer要素')
        self.assertEqual(manifest['test_cases'][1]['name'], '新建SYS Currency要素')
        self.assertGreater(len(manifest['test_cases'][0]['steps']), 0)
        self.assertGreater(len(manifest['test_cases'][1]['steps']), 0)
        self.assertTrue(any('用例 1 已按自然语言步骤重建关键流程' in warning for warning in warnings))
        self.assertTrue(any('用例 2 已按自然语言步骤重建关键流程' in warning for warning in warnings))

    def test_parse_uploaded_xlsx_respects_merged_case_rows_and_sparse_columns(self):
        xlsx_bytes = build_minimal_xlsx(
            [
                ['用例名称', '文件夹', '优先级', '前置条件', '步骤序号', '操作描述', '测试数据', '预期结果', '备注'],
                ['新建SYS Integer要素', '', 'high', '用户已存在且账号可用', '1', '登录', '', '', ''],
                [None, None, None, None, '2', '进入管理模式', None, None, None],
                [None, None, None, None, '3', '新建数据要素，数据定义是SYS Integer', None, None, None],
                [None, None, None, None, '4', '验证新建成功', None, '新建成功，弹出成功toast', None],
                ['新建SYS Currency要素', '', 'high', '用户已存在且账号可用', '1', '登录', '', '', ''],
                [None, None, None, None, '2', '进入管理模式', None, None, None],
                [None, None, None, None, '3', '新建数据要素，数据定义是SYS Currency', None, None, None],
                [None, None, None, None, '4', '验证新建成功', None, '新建成功，弹出成功toast', None],
            ],
            merges=['A2:A5', 'A6:A9', 'B2:B5', 'B6:B9', 'C2:C5', 'C6:C9', 'D2:D5', 'D6:D9'],
        )
        uploaded = SimpleUploadedFile(
            'merged_cases_template.xlsx',
            xlsx_bytes,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

        parsed = parse_uploaded_case_source(uploaded)
        manifest, warnings, mode = generate_ui_test_case_manifest(
            self.project,
            parsed.text,
            use_ai=False,
        )

        self.assertIn('1. 登录', parsed.text)
        self.assertIn('2. 进入管理模式', parsed.text)
        self.assertIn('预期结果：新建成功，弹出成功toast', parsed.text)
        self.assertEqual(mode, 'heuristic')
        self.assertEqual(len(manifest['test_cases']), 2)
        self.assertEqual(manifest['test_cases'][0]['steps'][0]['description'], '填写账号输入框')
        self.assertEqual(manifest['test_cases'][1]['steps'][0]['description'], '填写账号输入框')
        self.assertTrue(any('用例 1 已按自然语言步骤重建关键流程' in warning for warning in warnings))
        self.assertTrue(any('用例 2 已按自然语言步骤重建关键流程' in warning for warning in warnings))

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

    def test_extract_json_payload_repairs_common_ai_json_errors(self):
        raw = """
```json
{
  "format": "ui_automation_test_cases",
  "version": 1,
  "test_cases": [
    {
      "name": "login",
      "status": "draft",
      "priority": "medium",
      "steps": [
        {
          "description": "fill username",
          "action_type": "fill",
          "input_value": "admin",
          "element": {"name": "username", "locator_strategy": "XPath", "locator_value": "//input[@name='username']"},
        }
        {
          "description": "click login",
          "action_type": "click",
          "element": {"name": "login", "locator_strategy": "text", "locator_value": "Login"}
        }
      ],
    }
  ],
}
```
"""

        parsed = extract_json_payload(raw)

        self.assertEqual(parsed['format'], 'ui_automation_test_cases')
        self.assertEqual(len(parsed['test_cases'][0]['steps']), 2)

    def test_extract_json_payload_repairs_unterminated_string_before_next_key(self):
        raw = """
{
  "format": "ui_automation_test_cases",
  "version": 1,
  "test_cases": [
    {
      "name": "login",
      "status": "draft",
      "priority": "medium",
      "steps": [
        {
          "description": "fill username
          "action_type": "fill",
          "input_value": "admin",
          "element": {"name": "username", "locator_strategy": "XPath", "locator_value": "//input[@name='username']"}
        }
      ]
    }
  ]
}
"""

        parsed = extract_json_payload(raw)

        self.assertEqual(parsed['test_cases'][0]['steps'][0]['description'], 'fill username')
        self.assertEqual(parsed['test_cases'][0]['steps'][0]['action_type'], 'fill')

    def test_extract_json_payload_repairs_truncated_manifest_tail(self):
        raw = """
{
  "format": "ui_automation_test_cases",
  "version": 1,
  "test_cases": [
    {
      "name": "login",
      "status": "draft",
      "priority": "medium",
      "steps": [
        {
          "description": "fill username
"""

        parsed = extract_json_payload(raw)

        self.assertEqual(parsed['format'], 'ui_automation_test_cases')
        self.assertEqual(parsed['test_cases'][0]['name'], 'login')
        self.assertEqual(parsed['test_cases'][0]['steps'][0]['description'], 'fill username')

    def test_ai_generation_uses_repaired_json_instead_of_heuristic_fallback(self):
        raw = """
{
  "format": "ui_automation_test_cases",
  "version": 1,
  "test_cases": [
    {
      "name": "login",
      "status": "draft",
      "priority": "medium",
      "steps": [
        {
          "description": "fill username",
          "action_type": "fill",
          "input_value": "admin",
          "element": {"name": "username", "locator_strategy": "XPath", "locator_value": "//input[@name='username']"},
        }
        {
          "description": "click login",
          "action_type": "click",
          "element": {"name": "login", "locator_strategy": "text", "locator_value": "Login"},
        }
      ],
    }
  ],
}
"""
        model_config = SimpleNamespace()

        with patch('apps.ui_automation.ai_case_generator.call_openai_compatible_model', return_value=raw):
            manifest, warnings, mode = generate_ui_test_case_manifest(
                self.project,
                'login flow',
                model_config=model_config,
                use_ai=True,
            )

        self.assertEqual(mode, 'ai')
        self.assertEqual(manifest['test_cases'][0]['name'], 'login')
        self.assertEqual(len(manifest['test_cases'][0]['steps']), 2)
        self.assertFalse(any('AI' in warning and 'fallback' in warning.lower() for warning in warnings))

    def test_long_skill_prompt_keeps_relevant_business_rule(self):
        long_skill = '\n\n'.join(
            [f'{index}. irrelevant rule {index}' for index in range(500)]
            + ['17. \u521b\u5efa\u6570\u636e\u8981\u7d20\u65f6\uff0c\u9009\u4e2d\u6570\u636e\u5b9a\u4e49\u540e\u5fc5\u987b\u70b9\u51fb\u786e\u5b9a\uff0c\u586b\u5199\u8981\u7d20\u6807\u7b7e\uff0c\u518d\u63d0\u4ea4\u5e76\u9a8c\u8bc1\u64cd\u4f5c\u6210\u529f\u3002']
            + [f'{index}. more irrelevant rule {index}' for index in range(500, 900)]
        )

        prompt = build_generation_system_prompt(
            long_skill,
            '\u7528\u4f8b\uff1a\u521b\u5efaSYS Decimal\u7c7b\u578b\u6570\u636e\u8981\u7d20',
        )

        self.assertIn('\u521b\u5efa\u6570\u636e\u8981\u7d20', prompt)
        self.assertIn('\u8981\u7d20\u6807\u7b7e', prompt)
        self.assertIn('ui_automation_test_cases', prompt)
        self.assertLessEqual(len(prompt), 26000)

    def test_generation_max_tokens_uses_safe_minimum_for_complex_output(self):
        low_config = SimpleNamespace(max_tokens=4096)
        high_config = SimpleNamespace(max_tokens=32000)

        self.assertEqual(estimate_generation_max_tokens(low_config, 'short case'), 8192)
        self.assertEqual(estimate_generation_max_tokens(low_config, 'x' * 4000, 'y' * 20000), 12000)
        self.assertEqual(estimate_generation_max_tokens(high_config, 'short case'), 32000)

    def test_routed_skill_content_loads_only_relevant_builtin_modules(self):
        ensure_builtin_generation_skill_modules()

        _, login_info = build_routed_generation_skill_content(
            self.project,
            'login only',
            root_skill=None,
            user=self.user,
        )
        data_content, data_info = build_routed_generation_skill_content(
            self.project,
            '\u7528\u4f8b\uff1a\u521b\u5efaSYS Decimal\u7c7b\u578b\u6570\u636e\u8981\u7d20',
            root_skill=None,
            user=self.user,
        )

        login_codes = [module['code'] for module in login_info['selected_modules']]
        data_codes = [module['code'] for module in data_info['selected_modules']]

        self.assertIn('ui.global.output_manifest', login_codes)
        self.assertNotIn('ui.flow.data_element.create', login_codes)
        self.assertIn('ui.flow.data_element.create', data_codes)
        self.assertIn('create_data_element', data_info['detected_intents'])
        self.assertIn('\u521b\u5efa\u6570\u636e\u8981\u7d20\u5b8c\u6574\u6d41\u7a0b\u5fc5\u987b\u5305\u542b', data_content)

    def test_custom_skill_module_is_selected_by_keyword(self):
        module = AITestCaseGenerationSkillModule.objects.create(
            name='Custom Report Export',
            code='custom.report.export',
            module_type='business_flow',
            content='报表导出必须先点击导出按钮，再等待下载完成。',
            keywords=['报表导出'],
            intents=[],
            pages=[],
            priority=150,
            created_by=self.user,
        )

        content, info = build_routed_generation_skill_content(
            self.project,
            '\u7528\u4f8b\uff1a\u62a5\u8868\u5bfc\u51fa',
            root_skill=None,
            user=self.user,
        )

        self.assertIn(module.code, [item['code'] for item in info['selected_modules']])
        self.assertIn('报表导出必须先点击导出按钮', content)

    def test_generated_skill_module_content_is_structured_from_summary(self):
        content = generate_skill_module_content_draft(
            name='创建数据要素流程',
            code='ui.flow.data_element.create',
            module_type='business_flow',
            summary='创建数据要素必须包含进入管理模式、选择数据定义、填写标签、点击确定并验证成功',
            keywords=['创建数据要素', 'SYS Decimal'],
            intents=['create_data_element'],
            pages=['数据结构设置', '数据要素'],
        )

        self.assertIn('ui.flow.data_element.create', content)
        self.assertIn('创建数据要素必须包含进入管理模式', content)
        self.assertIn('创建类流程', content)
        self.assertIn('keywords: 创建数据要素, SYS Decimal', content)

    def test_routed_skill_content_contains_match_debug_fields(self):
        _, info = build_routed_generation_skill_content(
            self.project,
            '用例：创建SYS Decimal类型数据要素',
            root_skill=None,
            user=self.user,
        )

        self.assertIn('matched_modules', info)
        self.assertIn('omitted_modules', info)
        self.assertTrue(info['selected_modules'])
        first_module = info['selected_modules'][0]
        self.assertIn('reason_labels', first_module)
        self.assertIn('effective_prompt_chars', first_module)

    def test_ensure_builtin_modules_does_not_override_user_edited_builtin_content(self):
        ensure_builtin_generation_skill_modules()
        module = AITestCaseGenerationSkillModule.objects.get(code='ui.flow.data_element.create')
        module.content = 'custom-user-edited-content'
        module.summary = 'custom-user-edited-summary'
        module.save(update_fields=['content', 'summary', 'updated_at'])

        ensure_builtin_generation_skill_modules()
        module.refresh_from_db()

        self.assertEqual(module.content, 'custom-user-edited-content')
        self.assertEqual(module.summary, 'custom-user-edited-summary')

    def test_model_output_continues_when_finish_reason_is_length(self):
        class FakeResponse:
            status_code = 200
            text = ''

            def __init__(self, content, finish_reason):
                self._content = content
                self._finish_reason = finish_reason

            def json(self):
                return {
                    'choices': [
                        {
                            'message': {'content': self._content},
                            'finish_reason': self._finish_reason,
                        }
                    ]
                }

        model_config = SimpleNamespace(
            base_url='https://example.com/v1',
            api_key='key',
            model_name='model',
            max_tokens=4096,
            temperature=0.8,
            top_p=0.9,
            model_type='other',
        )
        responses = [
            FakeResponse('{"format":"ui_automation_test_cases","test_cases":[', 'length'),
            FakeResponse('{"name":"case","steps":[]}]}', 'stop'),
        ]

        with patch('apps.ui_automation.ai_case_generator.requests.post', side_effect=responses) as mock_post:
            raw = call_openai_compatible_model(self.project, 'case text', '', model_config)

        self.assertEqual(raw, '{"format":"ui_automation_test_cases","test_cases":[{"name":"case","steps":[]}]}')
        self.assertEqual(mock_post.call_count, 2)

    def test_wait_for_without_element_is_repaired_to_wait(self):
        source_manifest = {
            'format': 'ui_automation_test_cases',
            'version': 1,
            'test_cases': [
                {
                    'name': 'wait repair',
                    'status': 'draft',
                    'priority': 'medium',
                    'steps': [
                        {
                            'description': 'wait for missing element',
                            'action_type': 'waitFor',
                            'wait_time': 2000,
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

        step = manifest['test_cases'][0]['steps'][0]

        self.assertEqual(mode, 'manifest')
        self.assertEqual(step['action_type'], 'wait')
        self.assertIsNone(step['element'])
        self.assertEqual(step['wait_time'], 2000)
        self.assertTrue(any('waitFor' in warning and 'wait' in warning for warning in warnings))

    def test_sensitive_action_inserts_wait_for_next_element(self):
        source_manifest = {
            'format': 'ui_automation_test_cases',
            'version': 1,
            'test_cases': [
                {
                    'name': 'mode switch',
                    'status': 'draft',
                    'priority': 'medium',
                    'steps': [
                        {
                            'description': '\u70b9\u51fb\u8fdb\u5165\u7ba1\u7406\u6a21\u5f0f',
                            'action_type': 'click',
                            'element': {
                                'name': '\u7ba1\u7406\u6a21\u5f0f\u6309\u94ae',
                                'locator_strategy': 'XPath',
                                'locator_value': "//*[text()='\u7ba1\u7406\u6a21\u5f0f']",
                            },
                        },
                        {
                            'description': '\u70b9\u51fb\u6570\u636e\u8981\u7d20\u83dc\u5355',
                            'action_type': 'click',
                            'element': {
                                'name': '\u6570\u636e\u8981\u7d20\u83dc\u5355',
                                'locator_strategy': 'XPath',
                                'locator_value': "//*[text()='\u6570\u636e\u8981\u7d20']",
                            },
                        },
                    ],
                }
            ],
        }

        manifest, warnings, mode = generate_ui_test_case_manifest(
            self.project,
            json.dumps(source_manifest, ensure_ascii=False),
            use_ai=False,
        )
        steps = manifest['test_cases'][0]['steps']

        self.assertEqual(mode, 'manifest')
        self.assertEqual(len(steps), 3)
        self.assertEqual(steps[1]['action_type'], 'waitFor')
        self.assertEqual(steps[1]['element']['name'], '\u6570\u636e\u8981\u7d20\u83dc\u5355')
        self.assertTrue(any('\u7b49\u5f85\u89c4\u5219' in warning for warning in warnings))

    def test_existing_wait_after_sensitive_action_is_not_duplicated(self):
        source_manifest = {
            'format': 'ui_automation_test_cases',
            'version': 1,
            'test_cases': [
                {
                    'name': 'submit with wait',
                    'status': 'draft',
                    'priority': 'medium',
                    'steps': [
                        {
                            'description': '\u70b9\u51fb\u786e\u5b9a\u6309\u94ae\u63d0\u4ea4',
                            'action_type': 'click',
                            'element': {
                                'name': '\u786e\u5b9a\u6309\u94ae',
                                'locator_strategy': 'XPath',
                                'locator_value': "//*[text()='\u786e\u5b9a']",
                            },
                        },
                        {
                            'description': '\u7b49\u5f85\u64cd\u4f5c\u5b8c\u6210',
                            'action_type': 'wait',
                            'wait_time': 1000,
                        },
                        {
                            'description': '\u9a8c\u8bc1\u521b\u5efa\u6210\u529f',
                            'action_type': 'assert',
                            'assert_type': 'isVisible',
                            'element': {
                                'name': '\u64cd\u4f5c\u6210\u529ftoast',
                                'locator_strategy': 'XPath',
                                'locator_value': "//*[contains(text(),'\u64cd\u4f5c\u6210\u529f')]",
                            },
                        },
                    ],
                }
            ],
        }

        manifest, warnings, mode = generate_ui_test_case_manifest(
            self.project,
            json.dumps(source_manifest, ensure_ascii=False),
            use_ai=False,
        )
        steps = manifest['test_cases'][0]['steps']

        self.assertEqual(mode, 'manifest')
        self.assertEqual(len(steps), 3)
        self.assertEqual([step['action_type'] for step in steps], ['click', 'wait', 'assert'])
        self.assertFalse(any('\u7b49\u5f85\u89c4\u5219' in warning for warning in warnings))

    def test_data_element_creation_flow_is_completed_after_partial_ai_output(self):
        for name in [
            '新建数据要素-选择数据定义弹窗-确定按钮',
            '新建数据要素-要素标签输入框',
            '新建数据要素-确定按钮',
            '操作成功toast',
        ]:
            Element.objects.create(
                project=self.project,
                name=name,
                element_type='INPUT' if '输入框' in name else 'BUTTON',
                locator_strategy=self.locator_strategy,
                locator_value=f"//*[contains(normalize-space(.),'{name}')]",
            )

        raw = """
{
  "format": "ui_automation_test_cases",
  "version": 1,
  "test_cases": [
    {
      "name": "创建数据要素",
      "status": "draft",
      "priority": "medium",
      "steps": [
        {"description": "点击进入数据结构设置菜单", "action_type": "click", "element": {"name": "进入数据结构设置", "locator_strategy": "XPath", "locator_value": "//*[text()='数据结构设置']"}},
        {"description": "点击进入数据要素子菜单", "action_type": "click", "element": {"name": "进入数据要素", "locator_strategy": "XPath", "locator_value": "//*[text()='数据要素']"}},
        {"description": "点击新建按钮，打开新建数据要素弹窗", "action_type": "click", "element": {"name": "数据要素新建按钮", "locator_strategy": "XPath", "locator_value": "//*[text()='新建']"}},
        {"description": "在数据要素名称输入框中填写要素名称", "action_type": "fill", "input_value": "${random_string(8, letters, 1)}", "element": {"name": "数据要素名称输入框", "locator_strategy": "XPath", "locator_value": "//input"}},
        {"description": "点击选择数据定义控件，打开选择数据定义弹框", "action_type": "click", "element": {"name": "新建数据要素-选择数据定义icon", "locator_strategy": "XPath", "locator_value": "//i"}},
        {"description": "在选择数据定义弹框的搜索框中输入SYS Decimal，触发搜索", "action_type": "fillAndEnter", "input_value": "SYS Decimal", "element": {"name": "新建要素-选择数据定义搜索框", "locator_strategy": "XPath", "locator_value": "//input"}},
        {"description": "等待选择数据定义搜索结果加载完成", "action_type": "wait", "wait_time": 1000},
        {"description": "点击选中SYS Decimal数据定义选项", "action_type": "click", "element": {"name": "新建数据要素-选择数据定义-选择数据", "locator_strategy": "XPath", "locator_value": "//tbody/tr"}}
      ]
    }
  ]
}
"""

        with patch('apps.ui_automation.ai_case_generator.call_openai_compatible_model', return_value=raw):
            manifest, warnings, mode = generate_ui_test_case_manifest(
                self.project,
                '用例：创建数据要素 步骤：1.登录 2.进入管理模式 3.创建SYS Decimal类型数据要素 4.验证创建成功',
                model_config=SimpleNamespace(),
                use_ai=True,
            )

        descriptions = [step['description'] for step in manifest['test_cases'][0]['steps']]

        self.assertEqual(mode, 'ai')
        self.assertIn('点击选择数据定义弹框中的确定按钮', descriptions)
        self.assertIn('在要素标签输入框中填写标签名称', descriptions)
        self.assertIn('点击新建数据要素弹窗确定按钮提交新建', descriptions)
        self.assertIn('等待操作成功提示出现', descriptions)
        self.assertTrue(any('数据要素创建流程' in warning for warning in warnings))

    def test_split_source_into_cases_supports_inline_steps(self):
        cases = split_source_into_cases(
            '用例：登录 步骤：1.登录 2.进入管理模式 3.新建数据要素，数据定义是SYS Decimal 4.验证新建要素成功'
        )

        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0][0], '登录')
        self.assertIn('1.登录', cases[0][1])

    def test_extract_data_element_intent_prefers_explicit_definition_value(self):
        intents = extract_data_element_creation_intents(
            '用例：登录 步骤：1.登录 2.进入管理模式 3.新建数据要素，数据定义是SYS Decimal 4.验证新建要素成功'
        )

        self.assertEqual(intents[0]['data_definition'], 'SYS Decimal')

    def test_extract_data_element_intent_strips_expected_result_suffix(self):
        intents = extract_data_element_creation_intents(
            '用例：创建图片要素 步骤：1.登录 2.进入管理模式 3.新建数据要素，数据定义是SYS Image（预期结果：新建正常） 4.验证新建正常'
        )

        self.assertEqual(intents[0]['data_definition'], 'SYS Image')

    def test_uploaded_xlsx_generation_does_not_mix_expected_result_into_definition_search(self):
        xlsx_bytes = build_minimal_xlsx([
            ['用例名称', '文件夹', '优先级', '前置条件', '步骤序号', '操作描述', '测试数据', '预期结果', '备注'],
            ['新建SYS Image要素', '', 'high', '用户已存在且账号可用', '1', '登录', '', '', ''],
            ['', '', '', '', '2', '进入管理模式', '', '', ''],
            ['', '', '', '', '3', '新建数据要素，数据定义是SYS Image', '', '新建正常', ''],
            ['', '', '', '', '4', '验证新建成功', '', '新建正常', ''],
        ])
        uploaded = SimpleUploadedFile(
            'cases_template.xlsx',
            xlsx_bytes,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

        parsed = parse_uploaded_case_source(uploaded)
        manifest, warnings, mode = generate_ui_test_case_manifest(
            self.project,
            parsed.text,
            use_ai=False,
        )

        search_steps = [
            step for step in manifest['test_cases'][0]['steps']
            if step.get('action_type') == 'fillAndEnter' and '数据定义' in str(step.get('description') or '')
        ]

        self.assertEqual(mode, 'heuristic')
        self.assertTrue(search_steps)
        self.assertEqual(search_steps[0]['input_value'], 'SYS Image')
        self.assertNotIn('预期结果', search_steps[0]['input_value'])
        self.assertFalse(any('SYS Image（预期结果：新建正常）' in line for line in parsed.text.splitlines()))
        self.assertTrue(any('用例 1 已按自然语言步骤重建关键流程' in warning for warning in warnings))

    def test_uploaded_xlsx_generation_keeps_success_verification_minimal_and_normalized_label(self):
        xlsx_bytes = build_minimal_xlsx([
            ['用例名称', '文件夹', '优先级', '前置条件', '步骤序号', '操作描述', '测试数据', '预期结果', '备注'],
            ['新建SYS Currency要素', '', 'high', '用户已存在且账号可用', '1', '登录', '', '', ''],
            ['', '', '', '', '2', '进入管理模式', '', '', ''],
            ['', '', '', '', '3', '新建数据要素，数据定义是SYS Currency', '', '', ''],
            ['', '', '', '', '4', '验证新建成功', '', '新建成功，弹出成功toast', ''],
        ])
        uploaded = SimpleUploadedFile(
            'cases_template.xlsx',
            xlsx_bytes,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

        parsed = parse_uploaded_case_source(uploaded)
        manifest, warnings, mode = generate_ui_test_case_manifest(
            self.project,
            parsed.text,
            use_ai=False,
        )
        steps = manifest['test_cases'][0]['steps']

        self.assertEqual(mode, 'heuristic')
        self.assertTrue(any(step.get('save_as') == 'data_el_name' for step in steps))
        self.assertTrue(any(step.get('input_value') == 'currency_${random_string(6, letters, 1)}' for step in steps))
        self.assertTrue(any(step.get('description') == '等待操作成功提示出现' for step in steps))
        self.assertFalse(any(step.get('input_value') == '${data_el_name}' for step in steps))
        self.assertFalse(any(step.get('assert_type') == 'isVisible' and step.get('assert_value') == '${data_el_name}' for step in steps))
        self.assertTrue(any('用例 1 已按自然语言步骤重建关键流程' in warning for warning in warnings))

    def test_multi_case_ai_generation_rebuilds_each_case_from_original_uploaded_source(self):
        xlsx_bytes = build_minimal_xlsx([
            ['用例名称', '文件夹', '优先级', '前置条件', '步骤序号', '操作描述', '测试数据', '预期结果', '备注'],
            ['新建SYS Integer要素', '', 'high', '用户已存在且账号可用', '1', '登录', '', '', ''],
            ['', '', '', '', '2', '进入管理模式', '', '', ''],
            ['', '', '', '', '3', '新建数据要素，数据定义是SYS Integer', '', '', ''],
            ['', '', '', '', '4', '验证新建成功', '', '新建成功，弹出成功toast', ''],
            ['新建SYS Currency要素', '', 'high', '用户已存在且账号可用', '1', '登录', '', '', ''],
            ['', '', '', '', '2', '进入管理模式', '', '', ''],
            ['', '', '', '', '3', '新建数据要素，数据定义是SYS Currency', '', '', ''],
            ['', '', '', '', '4', '验证新建成功', '', '新建成功，弹出成功toast', ''],
            ['新建SYS Image要素', '', 'high', '用户已存在且账号可用', '1', '登录', '', '', ''],
            ['', '', '', '', '2', '进入管理模式', '', '', ''],
            ['', '', '', '', '3', '新建数据要素，数据定义是SYS Image', '', '', ''],
            ['', '', '', '', '4', '验证新建成功', '', '新建成功，弹出成功toast', ''],
        ])
        uploaded = SimpleUploadedFile(
            'cases_template.xlsx',
            xlsx_bytes,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        parsed = parse_uploaded_case_source(uploaded)
        raw = """
{
  "format": "ui_automation_test_cases",
  "version": 1,
  "test_cases": [
    {"name": "创建要素", "description": "创建SYS Integer的", "status": "draft", "priority": "medium", "steps": [{"description": "click", "action_type": "click"}]},
    {"name": "创建要素", "description": "创建SYS Currency的", "status": "draft", "priority": "medium", "steps": [{"description": "click", "action_type": "click"}]},
    {"name": "创建要素", "description": "创建SYS Image的", "status": "draft", "priority": "medium", "steps": [{"description": "click", "action_type": "click"}]}
  ]
}
"""

        with patch('apps.ui_automation.ai_case_generator.call_openai_compatible_model', return_value=raw):
            manifest, warnings, mode = generate_ui_test_case_manifest(
                self.project,
                parsed.text,
                model_config=SimpleNamespace(),
                use_ai=True,
            )

        self.assertEqual(mode, 'ai')
        self.assertEqual(len(manifest['test_cases']), 3)
        self.assertEqual(manifest['test_cases'][0]['name'], '新建SYS Integer要素')
        self.assertEqual(manifest['test_cases'][1]['name'], '新建SYS Currency要素')
        self.assertEqual(manifest['test_cases'][2]['name'], '新建SYS Image要素')
        self.assertTrue(any(step.get('input_value') == 'SYS Integer' for step in manifest['test_cases'][0]['steps']))
        self.assertTrue(any(step.get('input_value') == 'SYS Currency' for step in manifest['test_cases'][1]['steps']))
        self.assertTrue(any(step.get('input_value') == 'SYS Image' for step in manifest['test_cases'][2]['steps']))
        self.assertFalse(any(step.get('input_value') == 'SYS Image的' for step in manifest['test_cases'][2]['steps']))
        self.assertTrue(all(len(case.get('steps') or []) >= 20 for case in manifest['test_cases']))
        self.assertTrue(sum('已按自然语言步骤重建关键流程' in warning for warning in warnings) >= 3)

    def test_multi_case_ai_generation_restores_missing_cases_from_uploaded_source(self):
        xlsx_bytes = build_minimal_xlsx([
            ['用例名称', '文件夹', '优先级', '前置条件', '步骤序号', '操作描述', '测试数据', '预期结果', '备注'],
            ['新建SYS Integer要素', '', 'high', '用户已存在且账号可用', '1', '登录', '', '', ''],
            ['', '', '', '', '2', '进入管理模式', '', '', ''],
            ['', '', '', '', '3', '新建数据要素，数据定义是SYS Integer', '', '', ''],
            ['', '', '', '', '4', '验证新建成功', '', '新建成功，弹出成功toast', ''],
            ['新建SYS Currency要素', '', 'high', '用户已存在且账号可用', '1', '登录', '', '', ''],
            ['', '', '', '', '2', '进入管理模式', '', '', ''],
            ['', '', '', '', '3', '新建数据要素，数据定义是SYS Currency', '', '', ''],
            ['', '', '', '', '4', '验证新建成功', '', '新建成功，弹出成功toast', ''],
        ])
        uploaded = SimpleUploadedFile(
            'cases_template.xlsx',
            xlsx_bytes,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        parsed = parse_uploaded_case_source(uploaded)
        raw = """
{
  "format": "ui_automation_test_cases",
  "version": 1,
  "test_cases": [
    {"name": "创建要素", "description": "只返回第一条", "status": "draft", "priority": "medium", "steps": [{"description": "click", "action_type": "click"}]}
  ]
}
"""

        with patch('apps.ui_automation.ai_case_generator.call_openai_compatible_model', return_value=raw):
            manifest, warnings, mode = generate_ui_test_case_manifest(
                self.project,
                parsed.text,
                model_config=SimpleNamespace(),
                use_ai=True,
            )

        self.assertEqual(mode, 'ai')
        self.assertEqual(len(manifest['test_cases']), 2)
        self.assertEqual(manifest['test_cases'][1]['name'], '新建SYS Currency要素')
        self.assertTrue(any('已按原始用例补齐剩余 1 条' in warning for warning in warnings))
        self.assertTrue(any(step.get('input_value') == 'SYS Currency' for step in manifest['test_cases'][1]['steps']))

    def test_explicit_search_verification_keeps_ai_skill_generated_steps(self):
        raw = """
{
  "format": "ui_automation_test_cases",
  "version": 1,
  "test_cases": [
    {
      "name": "创建数据要素",
      "status": "draft",
      "priority": "medium",
      "steps": [
        {"description": "点击搜索按钮", "action_type": "click", "element": {"name": "搜索按钮", "locator_strategy": "XPath", "locator_value": "//button[normalize-space()='搜索']"}},
        {"description": "等待500ms", "action_type": "wait", "wait_time": 500},
        {"description": "输入${data_el_name}", "action_type": "fill", "input_value": "${data_el_name}", "element": {"name": "搜索输入框", "locator_strategy": "XPath", "locator_value": "//input[@placeholder='请输入搜索内容']"}},
        {"description": "点击确定搜索", "action_type": "click", "element": {"name": "确定搜索按钮", "locator_strategy": "XPath", "locator_value": "//button[normalize-space()='确定']"}}
      ]
    }
  ]
}
"""

        with patch('apps.ui_automation.ai_case_generator.call_openai_compatible_model', return_value=raw):
            manifest, warnings, mode = generate_ui_test_case_manifest(
                self.project,
                '用例：创建数据要素 步骤：1.登录 2.进入管理模式 3.创建SYS Decimal类型数据要素 4.通过搜索方式验证创建成功，需要点击搜索按钮，等待500ms，再输入要素名称并点击确定搜索',
                model_config=SimpleNamespace(),
                use_ai=True,
            )

        descriptions = [step['description'] for step in manifest['test_cases'][0]['steps']]
        transaction_names = [step['transaction_name'] for step in manifest['test_cases'][0]['steps']]

        self.assertEqual(mode, 'ai')
        self.assertIn('login', transaction_names)
        self.assertIn('进入管理模式', transaction_names)
        self.assertIn('创建要素', transaction_names)
        self.assertIn('验证新建要素成功', transaction_names)
        self.assertIn('点击搜索按钮', descriptions)
        self.assertIn('等待500ms', descriptions)
        self.assertIn('输入${data_el_name}', descriptions)
        self.assertIn('点击确定搜索', descriptions)
        self.assertTrue(any('已按自然语言步骤重建关键流程' in warning for warning in warnings))
        self.assertTrue(any('显式搜索验证要求' in warning for warning in warnings))

    def test_bad_ai_placeholder_clicks_are_rebuilt_into_transaction_blocks(self):
        for name, page, locator_value, element_type in [
            ('账号输入框', '登录', "//input[@placeholder='请输入账号']", 'INPUT'),
            ('密码输入框', '登录', "//input[@placeholder='请输入密码']", 'INPUT'),
            ('登录按钮', '登录', "//button[normalize-space()='登录']", 'BUTTON'),
            ('工作台logo', '个人工作台', "//img[@class='logo-img']", 'BUTTON'),
            ('进入管理模式', '管理模式首页', "//div[text()='用户模式']", 'BUTTON'),
            ('进入数据结构设置', '数据结构设置', "//span[text()='数据结构设置']", 'BUTTON'),
            ('进入数据要素', '数据要素', "//span[text()='数据要素']", 'BUTTON'),
            ('数据要素新建按钮', '数据要素', "//span[contains(.,'新建')]", 'BUTTON'),
            ('数据要素名称输入框', '数据要素', "//input[@name='dataElementName']", 'INPUT'),
            ('新建数据要素-选择数据定义icon', '数据要素', "//i[contains(@class,'definition-selector')]", 'BUTTON'),
            ('新建要素-选择数据定义搜索框', '选择数据定义弹窗', "//input[@placeholder='请输入']", 'INPUT'),
            ('新建数据要素-选择数据定义-选择数据', '选择数据定义弹窗', "//tbody/tr", 'BUTTON'),
            ('新建数据要素-选择数据定义弹窗-确定按钮', '选择数据定义弹窗', "//button[normalize-space()='确定']", 'BUTTON'),
            ('新建数据要素-要素标签输入框', '数据要素', "//input[@name='elementLabel']", 'INPUT'),
            ('新建数据要素-确定按钮', '数据要素', "//button[@type='submit']", 'BUTTON'),
            ('操作成功toast', '通用元素', "//p[text()='操作成功！']", 'MODAL'),
        ]:
            Element.objects.create(
                project=self.project,
                name=name,
                page=page,
                element_type=element_type,
                locator_strategy=self.locator_strategy,
                locator_value=locator_value,
            )

        raw = """
{
  "format": "ui_automation_test_cases",
  "version": 1,
  "test_cases": [
    {
      "name": "创建要素",
      "status": "draft",
      "priority": "medium",
      "steps": [
        {"description": "click", "action_type": "click"},
        {"description": "click", "action_type": "click"},
        {"description": "click", "action_type": "click"},
        {"description": "click", "action_type": "click"}
      ]
    }
  ]
}
"""

        with patch('apps.ui_automation.ai_case_generator.call_openai_compatible_model', return_value=raw):
            manifest, warnings, mode = generate_ui_test_case_manifest(
                self.project,
                '用例：登录 步骤：1.登录 2.进入管理模式 3.新建数据要素，数据定义是SYS Decimal 4.验证新建要素成功',
                model_config=SimpleNamespace(),
                use_ai=True,
            )

        case = manifest['test_cases'][0]
        steps = case['steps']
        descriptions = [step['description'] for step in steps]
        transaction_names = [step['transaction_name'] for step in steps]

        self.assertEqual(mode, 'ai')
        self.assertEqual(case['name'], '登录')
        self.assertEqual(steps[0]['action_type'], 'fill')
        self.assertEqual(steps[0]['input_value'], '${username}')
        self.assertEqual(steps[1]['input_value'], '${password}')
        self.assertIn('login', transaction_names)
        self.assertIn('进入管理模式', transaction_names)
        self.assertIn('创建要素', transaction_names)
        self.assertIn('验证新建要素成功', transaction_names)
        self.assertIn('切换到最新标签页', descriptions)
        self.assertIn('等待操作成功提示出现', descriptions)
        self.assertTrue(any(step['save_as'] == 'data_el_name' for step in steps))
        self.assertTrue(any(step['input_value'] == 'SYS Decimal' for step in steps))
        self.assertFalse(any(step['action_type'] == 'click' and not step.get('element') for step in steps))
        self.assertTrue(any('重建关键流程' in warning for warning in warnings))
