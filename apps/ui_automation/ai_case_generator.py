import csv
import io
import json
import logging
import os
import re
import uuid
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime

import requests
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.requirement_analysis.models import AIModelConfig
from .models import Element

logger = logging.getLogger(__name__)

MAX_SOURCE_FILE_SIZE = 10 * 1024 * 1024
SUPPORTED_SOURCE_EXTENSIONS = {'.txt', '.md', '.json', '.csv', '.xlsx', '.xmind'}
SUPPORTED_ACTION_TYPES = {
    'click', 'fill', 'fillAndEnter', 'getText', 'waitFor', 'hover', 'scroll',
    'drag', 'screenshot', 'assert', 'wait', 'switchTab', 'refreshCurrentPage',
    'closeCurrentPage',
}
SUPPORTED_ASSERT_TYPES = {'textContains', 'textEquals', 'isVisible', 'exists', 'hasAttribute'}
ELEMENT_ACTION_TYPES = {
    'click', 'fill', 'fillAndEnter', 'getText', 'waitFor', 'hover', 'scroll', 'drag', 'assert'
}
VALID_ELEMENT_TYPES = {
    'INPUT', 'BUTTON', 'LINK', 'DROPDOWN', 'CHECKBOX', 'RADIO', 'TEXT',
    'IMAGE', 'CONTAINER', 'TABLE', 'FORM', 'MODAL',
}

DEFAULT_UI_GENERATION_SKILL = """
你是资深 UI 自动化测试工程师。你的任务是把自然语言、Excel、XMind、TXT、CSV 或 JSON 测试用例转换为 TestHub 可导入的 UI 自动化测试用例 manifest。
输出要求：
1. 只输出 JSON，不要输出 Markdown、解释文本或代码块。
2. JSON 根对象必须包含 format、version、source_project、exported_at、test_cases。
3. format 固定为 "ui_automation_test_cases"，version 固定为 1。
4. 每个 test case 包含 name、description、status、priority、folder_name、steps。
5. status 只能是 draft/ready，priority 只能是 high/medium/low。
6. action_type 只能使用 click、fill、fillAndEnter、getText、waitFor、hover、scroll、drag、screenshot、assert、wait、switchTab、refreshCurrentPage、closeCurrentPage。
7. click/fill/fillAndEnter/getText/waitFor/hover/scroll/drag/assert 原则上必须提供 element；wait、switchTab、screenshot、refreshCurrentPage、closeCurrentPage 不需要 element。
8. element 必须包含 name、description、element_type、page、component_name、group_path、locator_strategy、locator_value、backup_locators、wait_timeout、is_unique、is_visible、is_enabled、force_action。
9. 优先复用已有元素上下文中的定位策略和定位值；没有已有元素时，生成稳定 XPath、CSS 或 text 定位器，不要输出空定位器。
10. 断言使用 action_type="assert"，assert_type 使用 textContains/textEquals/isVisible/exists/hasAttribute。
11. 同一业务流程片段可以设置 transaction_id 和 transaction_name；transaction_id 可用 "tx-" 前缀。
12. wait_time 单位为毫秒，默认 1000；等待页面、弹窗或 toast 可使用 3000-15000。
13. 输入值可以使用项目变量或数据工厂表达式，例如 ${random_string(8, letters, 1)}；需要后续引用时填写 save_as。
14. 如果输入来自模板文件，按 case_name/folder_name/priority/step_description/action_type/element_name/locator_strategy/locator_value/input_value/assert_type/assert_value 等列理解。
""".strip()


class ParsedSource:
    def __init__(self, text='', name='', source_type='text', warnings=None):
        self.text = text
        self.name = name
        self.source_type = source_type
        self.warnings = warnings or []


def truthy(value):
    if isinstance(value, bool):
        return value
    return str(value or '').strip().lower() in {'1', 'true', 'yes', 'on'}


def parse_uploaded_case_source(uploaded_file):
    if not uploaded_file:
        return ParsedSource()

    filename = uploaded_file.name or ''
    ext = os.path.splitext(filename.lower())[1]
    if ext == '.xls':
        raise ValidationError('暂不支持 .xls 二进制 Excel，请另存为 .xlsx 或 .csv 后上传')
    if ext not in SUPPORTED_SOURCE_EXTENSIONS:
        raise ValidationError('暂不支持该文件类型，请上传 txt/md/json/csv/xlsx/xmind 文件')
    if uploaded_file.size and uploaded_file.size > MAX_SOURCE_FILE_SIZE:
        raise ValidationError('上传文件不能超过 10MB')

    data = uploaded_file.read()
    warnings = []

    if ext in {'.txt', '.md'}:
        return ParsedSource(decode_text(data), filename, 'file', warnings)
    if ext == '.json':
        text = decode_text(data)
        try:
            parsed = json.loads(text)
            return ParsedSource(json.dumps(parsed, ensure_ascii=False, indent=2), filename, 'file', warnings)
        except json.JSONDecodeError:
            return ParsedSource(text, filename, 'file', warnings)
    if ext == '.csv':
        return ParsedSource(parse_csv_text(data), filename, 'file', warnings)
    if ext == '.xlsx':
        return ParsedSource(parse_xlsx_text(data), filename, 'file', warnings)
    if ext == '.xmind':
        return ParsedSource(parse_xmind_text(data), filename, 'file', warnings)

    return ParsedSource()


def decode_text(data):
    for encoding in ('utf-8-sig', 'utf-8', 'gb18030'):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode('utf-8', errors='ignore')


def parse_csv_text(data):
    text = decode_text(data)
    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample)
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(io.StringIO(text), dialect))
    return rows_to_text(rows)


def parse_xlsx_text(data):
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ValidationError(f'Excel 文件解析失败: {exc}')

    shared_strings = []
    if 'xl/sharedStrings.xml' in archive.namelist():
        shared_root = ET.fromstring(archive.read('xl/sharedStrings.xml'))
        for item in shared_root.iter():
            if item.tag.endswith('}si') or item.tag == 'si':
                texts = [node.text or '' for node in item.iter() if node.tag.endswith('}t') or node.tag == 't']
                shared_strings.append(''.join(texts))

    rows = []
    sheet_names = sorted(name for name in archive.namelist() if re.match(r'xl/worksheets/sheet\d+\.xml$', name))
    for sheet_name in sheet_names:
        rows.append([f'worksheet {os.path.basename(sheet_name)}'])
        root = ET.fromstring(archive.read(sheet_name))
        for row in root.iter():
            if not (row.tag.endswith('}row') or row.tag == 'row'):
                continue
            values = []
            for cell in list(row):
                if not (cell.tag.endswith('}c') or cell.tag == 'c'):
                    continue
                cell_type = cell.attrib.get('t')
                value = ''
                value_node = next((node for node in cell if node.tag.endswith('}v') or node.tag == 'v'), None)
                inline_node = next((node for node in cell if node.tag.endswith('}is') or node.tag == 'is'), None)
                if value_node is not None and value_node.text is not None:
                    value = value_node.text
                    if cell_type == 's':
                        try:
                            value = shared_strings[int(value)]
                        except (ValueError, IndexError):
                            pass
                elif inline_node is not None:
                    value = ''.join(node.text or '' for node in inline_node.iter() if node.tag.endswith('}t') or node.tag == 't')
                values.append(value)
            if any(str(value).strip() for value in values):
                rows.append(values)
    return rows_to_text(rows)


def parse_xmind_text(data):
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ValidationError(f'XMind 文件解析失败: {exc}')

    names = archive.namelist()
    if 'content.json' in names:
        payload = json.loads(archive.read('content.json').decode('utf-8'))
        lines = []
        for sheet in payload if isinstance(payload, list) else [payload]:
            walk_xmind_json_topic(sheet.get('rootTopic') or {}, lines, 0)
        return '\n'.join(lines)
    if 'content.xml' in names:
        root = ET.fromstring(archive.read('content.xml'))
        lines = []
        for topic in root.iter():
            if topic.tag.endswith('}topic') or topic.tag == 'topic':
                title = ''
                for node in topic:
                    if node.tag.endswith('}title') or node.tag == 'title':
                        title = node.text or ''
                        break
                if title.strip():
                    lines.append(title.strip())
        return '\n'.join(lines)

    raise ValidationError('XMind 文件中未找到 content.json 或 content.xml')


def walk_xmind_json_topic(topic, lines, depth):
    title = str(topic.get('title') or '').strip()
    if title:
        lines.append(f'{"  " * depth}- {title}')
    children = topic.get('children') or {}
    for child in children.get('attached') or []:
        walk_xmind_json_topic(child, lines, depth + 1)


def rows_to_text(rows):
    lines = []
    for row in rows:
        cleaned = [str(item or '').strip() for item in row]
        if any(cleaned):
            lines.append(' | '.join(cleaned))
    return '\n'.join(lines)


def get_generation_model_config(config_id=None):
    if config_id:
        return AIModelConfig.objects.filter(id=config_id, is_active=True).first()
    queryset = AIModelConfig.objects.filter(is_active=True)
    return (
        queryset.filter(role='browser_use_text').order_by('-updated_at').first()
        or queryset.filter(role='writer').order_by('-updated_at').first()
    )


def build_existing_element_context(project, limit=200):
    elements = Element.objects.filter(project=project).select_related('locator_strategy').order_by('page', 'name')[:limit]
    lines = []
    for element in elements:
        strategy = element.locator_strategy.name if element.locator_strategy else ''
        lines.append(
            f'- page:{element.page or "-"} element:{element.name} type:{element.element_type} '
            f'locator:{strategy}={element.locator_value}'
        )
    return '\n'.join(lines)


def generate_ui_test_case_manifest(project, source_text, skill_content='', model_config=None, use_ai=True):
    warnings = []
    source_text = str(source_text or '').strip()
    if not source_text:
        raise ValidationError('请提供自然语言用例或上传可解析的用例文件')

    prebuilt_manifest = try_parse_manifest(source_text)
    if prebuilt_manifest:
        manifest = normalize_manifest(project, prebuilt_manifest)
        warnings.extend(validate_manifest_quality(manifest))
        return manifest, warnings, 'manifest'

    if use_ai and model_config:
        try:
            raw = call_openai_compatible_model(project, source_text, skill_content, model_config)
            manifest = normalize_manifest(project, extract_json_payload(raw))
            warnings.extend(validate_manifest_quality(manifest))
            return manifest, warnings, 'ai'
        except Exception as exc:
            logger.warning('AI UI test case generation failed, fallback to heuristic parser: %s', exc, exc_info=True)
            warnings.append(f'AI生成失败，已使用规则解析兜底: {exc}')

    manifest = heuristic_manifest(project, source_text)
    warnings.extend(validate_manifest_quality(manifest))
    return manifest, warnings, 'heuristic'


def try_parse_manifest(source_text):
    try:
        parsed = json.loads(source_text)
    except (TypeError, json.JSONDecodeError):
        return None
    if isinstance(parsed, dict) and parsed.get('format') == 'ui_automation_test_cases':
        return parsed
    return None


def call_openai_compatible_model(project, source_text, skill_content, model_config):
    base_url = (model_config.base_url or '').rstrip('/')
    if not base_url:
        raise ValidationError('AI模型配置缺少 base_url')
    if base_url.endswith('/chat/completions'):
        url = base_url
    elif re.search(r'/v\d+/?$', base_url):
        url = f'{base_url}/chat/completions'
    else:
        url = f'{base_url}/v1/chat/completions'

    system_prompt = skill_content.strip() if skill_content and skill_content.strip() else DEFAULT_UI_GENERATION_SKILL
    user_prompt = f"""
项目名称: {project.name}
项目基础URL: {project.base_url}

可复用的已有元素:
{build_existing_element_context(project) or '暂无已有元素，请根据用例文本生成稳定定位器。'}

自然语言/文件解析后的测试用例:
{source_text}
""".strip()

    payload = {
        'model': model_config.model_name,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt},
        ],
        'max_tokens': model_config.max_tokens,
        'stream': False,
    }
    apply_sampling_params(payload, model_config)
    response = requests.post(
        url,
        headers={'Authorization': f'Bearer {model_config.api_key}', 'Content-Type': 'application/json'},
        json=payload,
        timeout=(60, 900),
    )
    if response.status_code >= 400:
        raise ValidationError(f'AI模型调用失败: {response.status_code} {response.text[:1000]}')
    data = response.json()
    try:
        return data['choices'][0]['message']['content']
    except (KeyError, IndexError, TypeError) as exc:
        raise ValidationError(f'AI模型响应格式不正确: {exc}')


def extract_json_payload(raw_text):
    text = str(raw_text or '').strip()
    fenced = re.search(r'```(?:json)?\s*(.*?)```', text, flags=re.S | re.I)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find('{')
        end = text.rfind('}')
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
        raise


def normalize_manifest(project, manifest):
    if not isinstance(manifest, dict):
        raise ValidationError('AI生成结果不是JSON对象')
    test_cases = manifest.get('test_cases') or []
    if not isinstance(test_cases, list) or not test_cases:
        raise ValidationError('AI生成结果中没有 test_cases')

    return {
        'format': 'ui_automation_test_cases',
        'version': 1,
        'source_project': {'id': project.id, 'name': project.name},
        'exported_at': timezone.now().isoformat(),
        'test_cases': [normalize_case(case, index) for index, case in enumerate(test_cases, start=1)],
    }


def normalize_case(case, case_index):
    case = case if isinstance(case, dict) else {}
    status = case.get('status') if case.get('status') in {'draft', 'ready'} else 'draft'
    priority = case.get('priority') if case.get('priority') in {'high', 'medium', 'low'} else 'medium'
    steps = case.get('steps') if isinstance(case.get('steps'), list) else []
    return {
        'name': (str(case.get('name') or f'AI生成用例{case_index}').strip() or f'AI生成用例{case_index}')[:200],
        'description': str(case.get('description') or '').strip(),
        'status': status,
        'priority': priority,
        'folder_name': str(case.get('folder_name') or '').strip(),
        'steps': [normalize_step(step, index) for index, step in enumerate(steps, start=1)],
    }


def normalize_step(step, step_index):
    step = step if isinstance(step, dict) else {}
    description = str(step.get('description') or '').strip()
    raw_action_type = str(step.get('action_type') or '').strip()
    inferred_action_type = infer_action_type(description)
    action_type = raw_action_type if raw_action_type in SUPPORTED_ACTION_TYPES else inferred_action_type
    if action_type == 'click' and inferred_action_type in {'fill', 'fillAndEnter'}:
        action_type = inferred_action_type

    transaction_name = str(step.get('transaction_name') or '').strip()
    transaction_id = str(step.get('transaction_id') or '').strip()
    if transaction_name and not transaction_id:
        transaction_id = f'tx-{uuid.uuid4().hex[:12]}'
    if not transaction_name:
        transaction_id = ''

    assert_type = str(step.get('assert_type') or '').strip()
    if assert_type and assert_type not in SUPPORTED_ASSERT_TYPES:
        assert_type = 'textContains'

    input_value = str(step.get('input_value') or '').strip()
    if action_type in {'fill', 'fillAndEnter'} and not input_value:
        input_value = infer_input_value(description)

    assert_value = str(step.get('assert_value') or '').strip()
    if action_type == 'assert' and not assert_value:
        assert_value = infer_assert_value(description)

    return {
        'step_number': step_index,
        'action_type': action_type,
        'description': description or action_type,
        'is_enabled': truthy(step.get('is_enabled', True)),
        'input_value': input_value,
        'wait_time': normalize_int(step.get('wait_time'), 1000, 0, 120000),
        'assert_type': assert_type,
        'assert_value': assert_value,
        'save_as': str(step.get('save_as') or '').strip(),
        'transaction_id': transaction_id,
        'transaction_name': transaction_name,
        'element': normalize_element(step.get('element')) if action_type in ELEMENT_ACTION_TYPES else None,
        'drag_target_element': normalize_element(step.get('drag_target_element')) if action_type == 'drag' else None,
    }


def normalize_element(element):
    if not isinstance(element, dict):
        return None
    name = str(element.get('name') or element.get('locator_value') or '未命名元素').strip()
    element_type = str(element.get('element_type') or 'BUTTON').strip().upper()
    if element_type not in VALID_ELEMENT_TYPES:
        element_type = 'BUTTON'
    group_path = element.get('group_path') or []
    if isinstance(group_path, str):
        group_path = [group_path]
    if not isinstance(group_path, list):
        group_path = []
    group_path = [str(item).strip() for item in group_path if str(item).strip()]

    locator_strategy = str(element.get('locator_strategy') or 'XPath').strip()
    locator_value = str(element.get('locator_value') or '').strip()
    if not locator_value:
        locator_strategy = 'text'
        locator_value = name

    return {
        'name': name[:200],
        'description': str(element.get('description') or '').strip(),
        'element_type': element_type,
        'page': str(element.get('page') or '').strip(),
        'component_name': str(element.get('component_name') or '').strip(),
        'group_path': group_path,
        'locator_strategy': locator_strategy,
        'locator_value': locator_value,
        'backup_locators': element.get('backup_locators') if isinstance(element.get('backup_locators'), list) else [],
        'wait_timeout': normalize_int(element.get('wait_timeout'), 5, 1, 120),
        'is_unique': truthy(element.get('is_unique', False)),
        'is_visible': truthy(element.get('is_visible', True)),
        'is_enabled': truthy(element.get('is_enabled', True)),
        'force_action': truthy(element.get('force_action', False)),
    }


def normalize_int(value, default, minimum, maximum):
    try:
        result = int(value)
    except (TypeError, ValueError):
        result = default
    return max(minimum, min(maximum, result))


def heuristic_manifest(project, source_text):
    cases = split_source_into_cases(source_text)
    return normalize_manifest(project, {
        'test_cases': [heuristic_case(case_name, body, index) for index, (case_name, body) in enumerate(cases, start=1)]
    })


def split_source_into_cases(source_text):
    lines = [line.strip() for line in source_text.splitlines() if line.strip()]
    if not lines:
        return [('AI生成用例', source_text)]
    cases = []
    current_name = None
    current_lines = []
    case_heading_re = re.compile(r'^(?:用例|测试用例|case|场景|标题|功能)[:：\s]+(.+)$', re.I)
    for line in lines:
        match = case_heading_re.match(line)
        if match:
            if current_name or current_lines:
                cases.append((current_name or f'AI生成用例{len(cases) + 1}', '\n'.join(current_lines)))
            current_name = match.group(1).strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_name or current_lines:
        cases.append((current_name or guess_case_name(lines), '\n'.join(current_lines)))
    return cases[:50]


def guess_case_name(lines):
    first = lines[0] if lines else 'AI生成用例'
    first = re.sub(r'^[-*\d.、\s]+', '', first)
    return first[:80] or 'AI生成用例'


def heuristic_case(name, body, index):
    steps = []
    for line in [item.strip() for item in re.split(r'[\n；;]', body) if item.strip()]:
        action_type = infer_action_type(line)
        element = None
        if action_type in ELEMENT_ACTION_TYPES:
            element_name = infer_element_name(line)
            element = {
                'name': element_name,
                'element_type': infer_element_type(action_type, element_name),
                'locator_strategy': 'text' if action_type == 'click' else 'XPath',
                'locator_value': element_name if action_type == 'click' else f"//*[contains(normalize-space(.),'{escape_xpath_text(element_name)}') or @placeholder='{escape_xpath_text(element_name)}']",
            }
        steps.append({
            'action_type': action_type,
            'description': line,
            'input_value': infer_input_value(line) if action_type in {'fill', 'fillAndEnter', 'switchTab'} else '',
            'wait_time': 3000 if action_type == 'wait' else 1000,
            'assert_type': 'textContains' if action_type == 'assert' else '',
            'assert_value': infer_assert_value(line) if action_type == 'assert' else '',
            'element': element,
        })
    if not steps:
        steps.append({'action_type': 'wait', 'description': body[:200] or name, 'wait_time': 1000})
    return {
        'name': name or f'AI生成用例{index}',
        'description': body,
        'status': 'draft',
        'priority': 'medium',
        'folder_name': '',
        'steps': steps,
    }


def infer_action_type(text):
    lowered = text.lower()
    if any(word in text for word in ['输入并回车', '回车']) or 'enter' in lowered:
        return 'fillAndEnter'
    if any(word in text for word in ['输入', '填写', '填入', '录入', '设置为']):
        return 'fill'
    if any(word in text for word in ['断言', '校验', '验证', '应该', '显示', '看到']):
        return 'assert'
    if any(word in text for word in ['等待', '暂停']):
        return 'wait'
    if any(word in text for word in ['悬停', 'hover']):
        return 'hover'
    if any(word in text for word in ['滚动', 'scroll']):
        return 'scroll'
    if any(word in text for word in ['截图', 'screenshot']):
        return 'screenshot'
    if any(word in text for word in ['切换标签', '切换页签', 'switch tab']):
        return 'switchTab'
    if any(word in text for word in ['刷新']):
        return 'refreshCurrentPage'
    if any(word in text for word in ['关闭当前']):
        return 'closeCurrentPage'
    return 'click'


def infer_element_name(text):
    cleaned = re.sub(r'^(?:[-*\d.、\s]|步骤\d+[:：]?)+', '', text).strip()
    target, _ = split_input_instruction(cleaned)
    if target:
        cleaned = target
    cleaned = re.sub(r'^(点击|单击|输入并回车|输入|填写|填入|录入|等待|验证|校验|断言|悬停|滚动)\s*', '', cleaned)
    cleaned = re.split(r'[:：,，。]', cleaned)[0].strip()
    return cleaned[:80] or '目标元素'


def infer_element_type(action_type, name):
    if action_type in {'fill', 'fillAndEnter'}:
        return 'INPUT'
    if action_type == 'assert':
        return 'TEXT'
    if any(word in name for word in ['弹窗', 'toast', '提示']):
        return 'MODAL'
    return 'BUTTON'


def infer_input_value(text):
    _, value = split_input_instruction(text)
    return value


def split_input_instruction(text):
    text = str(text or '').strip()
    patterns = [
        r'(.+?)(?:输入|填写|填入|录入|设置为|=|：|:)\s*[“"\'`]?(.+?)[”"\'`]?$',
        r'(?:输入|填写|填入|录入)\s*[“"\'`]?(.+?)[”"\'`]?\s*(?:到|至|在)\s*(.+)$',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        if pattern.startswith('(?:'):
            value, target = match.group(1), match.group(2)
        else:
            target, value = match.group(1), match.group(2)
        return clean_input_target(target), clean_input_value(value)
    return '', ''


def clean_input_target(value):
    value = str(value or '').strip()
    value = re.sub(r'^(?:在|向|给|往)\s*', '', value)
    return value.strip(' ：:，,')


def clean_input_value(value):
    value = str(value or '').strip()
    value = re.sub(r'^(?:内容|值|文本)\s*', '', value)
    return value.strip(' “”"\'`：:,，')


def infer_assert_value(text):
    match = re.search(r'(?:包含|显示|看到|等于|为)[:：]?\s*(.+)$', text)
    return match.group(1).strip() if match else text


def escape_xpath_text(text):
    return str(text or '').replace("'", "\\'")


def validate_manifest_quality(manifest):
    warnings = []
    for case_index, case in enumerate(manifest.get('test_cases') or [], start=1):
        if not case.get('steps'):
            warnings.append(f'用例 {case_index} 未生成步骤')
            continue
        for step_index, step in enumerate(case.get('steps') or [], start=1):
            action_type = step.get('action_type')
            element = step.get('element')
            if action_type in ELEMENT_ACTION_TYPES and not element:
                warnings.append(f'用例 {case_index} 步骤 {step_index} 缺少元素，导入后可能无法执行')
            if element and not element.get('locator_value'):
                warnings.append(f'用例 {case_index} 步骤 {step_index} 的元素缺少定位值')
    return warnings


def optimize_skill_with_ai(current_skill, instruction, model_config=None):
    current_skill = str(current_skill or DEFAULT_UI_GENERATION_SKILL).strip()
    instruction = str(instruction or '').strip()
    if not instruction:
        raise ValidationError('请输入优化要求')
    if not model_config:
        return heuristic_optimize_skill(current_skill, instruction), ['未配置AI模型，已将优化要求追加到Skill']
    try:
        base_url = (model_config.base_url or '').rstrip('/')
        if not base_url:
            raise ValidationError('AI模型未配置base_url')
        if base_url.endswith('/chat/completions'):
            url = base_url
        elif re.search(r'/v\d+/?$', base_url):
            url = f'{base_url}/chat/completions'
        else:
            url = f'{base_url}/v1/chat/completions'

        prompt = f"""
请根据用户的优化要求改写 UI 自动化测试用例生成 Skill。
要求：
1. 只输出优化后的 Skill 正文。
2. 保留“输出 JSON manifest 且可导入 TestHub UI自动化用例管理”的硬约束。
3. 不要输出解释。

当前 Skill:
{current_skill}

用户优化要求:
{instruction}
""".strip()
        payload = {
            'model': model_config.model_name,
            'messages': [{'role': 'user', 'content': prompt}],
            'max_tokens': min(model_config.max_tokens, 4096),
            'stream': False,
        }
        apply_sampling_params(payload, model_config, temperature_override=min(model_config.temperature, 0.5))
        response = requests.post(
            url,
            headers={'Authorization': f'Bearer {model_config.api_key}', 'Content-Type': 'application/json'},
            json=payload,
            timeout=(60, 900),
        )
        if response.status_code >= 400:
            raise ValidationError(f'AI模型调用失败: {response.status_code} {response.text[:1000]}')
        data = response.json()
        return data['choices'][0]['message']['content'].strip(), []
    except Exception as exc:
        logger.warning('AI skill optimization failed, fallback to heuristic mode: %s', exc, exc_info=True)
        return heuristic_optimize_skill(current_skill, instruction), [f'AI优化失败，已使用规则兜底: {exc}']


def heuristic_optimize_skill(current_skill, instruction):
    stamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return f'{current_skill}\n\n补充优化要求（{stamp}）：\n{instruction}'


def apply_sampling_params(payload, model_config, temperature_override=None):
    model_type = str(getattr(model_config, 'model_type', '') or '').lower()
    model_name = str(getattr(model_config, 'model_name', '') or '').lower()
    is_claude_like = model_type == 'anthropic' or 'claude' in model_name

    temperature = temperature_override
    if temperature is None:
        temperature = getattr(model_config, 'temperature', None)
    if temperature is not None:
        payload['temperature'] = temperature

    # Some OpenAI-compatible Claude gateways reject requests when both
    # temperature and top_p are present. Keep temperature only for them.
    if not is_claude_like:
        top_p = getattr(model_config, 'top_p', None)
        if top_p is not None:
            payload['top_p'] = top_p
    return payload
