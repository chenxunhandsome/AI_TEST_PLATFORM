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
from django.db import models
from django.utils import timezone

from apps.requirement_analysis.models import AIModelConfig
from .group_paths import normalize_group_path
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
TABULAR_CASE_COLUMN_ALIASES = {
    'case_name': {'用例名称', '用例名', '用例', '测试用例', 'case', 'case_name', 'casename', 'title', '标题'},
    'folder_name': {'文件夹', '目录', 'folder', 'folder_name', 'foldername'},
    'priority': {'优先级', 'priority'},
    'precondition': {'前置条件', '前提条件', 'precondition', 'preconditions'},
    'step_number': {'步骤序号', '步骤编号', '步骤号', 'step_number', 'stepno', 'step_no', 'step'},
    'step_description': {
        '操作描述', '步骤描述', '操作步骤', '测试步骤', '步骤内容', 'step_description',
        'stepdescription', 'action_description', 'description',
    },
    'test_data': {'测试数据', '输入数据', 'data', 'test_data', 'testdata', 'input_value'},
    'expected_result': {'预期结果', '预期', 'expected_result', 'expected', 'assert_value'},
    'remark': {'备注', 'remark', 'notes', 'note'},
}
MAX_FULL_SKILL_CHARS = 16000
MAX_RELEVANT_SKILL_CHARS = 22000
MIN_GENERATION_MAX_TOKENS = 8192
LONG_GENERATION_MAX_TOKENS = 12000
MAX_GENERATION_MAX_TOKENS = 32768

GENERATION_HARD_CONSTRAINTS = """
你是资深 UI 自动化测试用例生成器。无论业务 Skill 多长，都必须遵守以下硬约束：
1. 只输出 JSON，不输出 Markdown、解释、代码块或省略号。
2. JSON 根对象必须是 TestHub 可导入的 ui_automation_test_cases manifest。
3. 必须完整覆盖自然语言用例中的全部步骤，不允许因为输出较长而提前停止或只生成前半段。
4. click/fill/fillAndEnter/getText/waitFor/hover/scroll/drag/assert 原则上必须绑定 element；普通等待使用 wait。
5. 搜索、查询、切换模式、提交、保存、确定、确认等会触发页面变化的动作后，必须安排 wait 或 waitFor。
6. 断言必须使用 action_type="assert"，assert_type 使用 textContains/textEquals/isVisible/exists/hasAttribute。
7. 若业务 Skill 与硬约束冲突，以硬约束为准；若业务 Skill 有更具体的业务流程要求，必须展开为完整可执行步骤。
""".strip()

DEFAULT_UI_GENERATION_SKILL = """
你是 TestHub UI 自动化测试用例生成的主 Skill 入口。你的职责是控制全局生成策略，而不是承载所有业务细节。

架构规则：
1. 主 Skill 只负责输出格式、全局硬约束、模块调用协议和质量要求。
2. 具体业务流程、页面规则、特殊等待、特殊断言由后端按需加载的模块化 Skill 提供。
3. 当提示词中出现【按需加载的 Skill 模块】时，必须严格执行这些模块中的业务流程。
4. 如果多个模块同时出现，优先级为：业务流程模块 > 页面模块 > 修复规则模块 > 全局规范模块。
5. 如果模块内容和主 Skill 冲突，以主 Skill 的输出格式和安全硬约束为准；如果模块提供更具体的业务步骤，以模块业务流程为准。
6. 不要臆测未提供的业务流程；如果模块给出了完整流程，必须按完整流程展开，不允许只生成前半段。

输出硬约束：
1. 只输出 JSON，不要输出 Markdown、解释文本、代码块、注释或省略号。
2. JSON 根对象必须是 TestHub 可导入的 ui_automation_test_cases manifest。
3. 根对象必须包含 format、version、source_project、exported_at、test_cases。
4. format 固定为 "ui_automation_test_cases"，version 固定为 1。
5. 每个 test case 必须包含 name、description、status、priority、folder_name、steps。
6. status 只能是 draft/ready，priority 只能是 high/medium/low。
7. 必须完整覆盖自然语言用例中的全部步骤，不允许因为流程较长而提前结束。

步骤与元素规则：
1. action_type 只能使用 click、fill、fillAndEnter、getText、waitFor、hover、scroll、drag、screenshot、assert、wait、switchTab、refreshCurrentPage、closeCurrentPage。
2. click/fill/fillAndEnter/getText/waitFor/hover/scroll/drag/assert 原则上必须提供 element。
3. wait、switchTab、screenshot、refreshCurrentPage、closeCurrentPage 不需要 element。
4. element 必须包含 name、description、element_type、page、component_name、group_path、locator_strategy、locator_value、backup_locators、wait_timeout、is_unique、is_visible、is_enabled、force_action。
5. 优先复用已有元素上下文中的定位策略和定位值；没有已有元素时，生成稳定 XPath、CSS 或 text 定位器。
6. 不允许输出空 locator_value，不允许编造明显不可用的定位器。

等待与断言规则：
1. 搜索、查询、切换管理模式/用户模式、提交、保存、点击确定/确认后，必须生成 wait 或 waitFor。
2. 打开弹窗后必须等待弹窗或弹窗内第一个关键元素出现。
3. 提交成功后优先 waitFor 操作成功 toast；如果没有明确 toast 元素，再使用 wait。
4. 断言必须使用 action_type="assert"，assert_type 使用 textContains/textEquals/isVisible/exists/hasAttribute。
5. 验证成功类步骤不能省略，必须生成可执行断言或等待成功提示。

数据与变量规则：
1. 输入值可以使用项目变量或数据工厂表达式，例如 ${random_string(8, letters, 1)}。
2. 后续步骤需要引用前面生成或读取的值时，必须使用 save_as 保存。
3. 如果自然语言明确指定业务值，例如 SYS Decimal、用户名 test001，必须使用指定值。

模块执行要求：
1. 仔细阅读【后端识别结果】中的 intents 和 entities。
2. 对【按需加载的 Skill 模块】逐个执行，不要忽略业务流程模块。
3. 若业务流程模块列出了完整步骤，必须生成完整步骤链。
4. 若页面模块提供元素命名或页面上下文，必须优先使用。
5. 若修复规则模块要求补等待、补确认、补断言，必须体现在最终 JSON 中。
""".strip()


SKILL_MODULE_TYPE_LABELS = {
    'global': '全局规范',
    'page': '页面模块',
    'business_flow': '业务流程',
    'repair': '修复规则',
}

SKILL_TRIGGER_TYPE_LABELS = {
    'keyword': '关键词',
    'regex': '正则',
    'intent': '意图',
    'page': '页面',
    'entity': '实体',
}

SKILL_ROUTE_REASON_LABELS = {
    'module_metadata': '命中模块元数据',
    'always_on': '全局/修复模块默认常驻',
    'dependency': '由依赖关系自动带入',
    'intent_match': '命中模块意图',
    'keyword_match': '命中模块关键词',
    'page_match': '命中模块页面',
    'technical_term_match': '命中技术术语',
    'create_flow_bias': '创建类流程额外加权',
    'page_name_bias': '页面模块名称额外加权',
    'trigger_match': '命中显式触发器',
}


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
    structured_text = tabular_rows_to_case_text(rows)
    if structured_text:
        return structured_text
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

    sheet_texts = []
    fallback_rows = []
    sheet_names = sorted(name for name in archive.namelist() if re.match(r'xl/worksheets/sheet\d+\.xml$', name))
    for sheet_name in sheet_names:
        root = ET.fromstring(archive.read(sheet_name))
        sheet_rows = extract_xlsx_sheet_rows(root, shared_strings)
        structured_text = tabular_rows_to_case_text(sheet_rows, sheet_name=os.path.basename(sheet_name))
        if structured_text:
            sheet_texts.append(structured_text)
            continue
        fallback_rows.append([f'worksheet {os.path.basename(sheet_name)}'])
        fallback_rows.extend(sheet_rows)

    if sheet_texts:
        return '\n\n'.join(item for item in sheet_texts if item).strip()
    return rows_to_text(fallback_rows)


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


def excel_column_letters_to_index(column_letters):
    result = 0
    for char in str(column_letters or '').strip().upper():
        if 'A' <= char <= 'Z':
            result = result * 26 + (ord(char) - ord('A') + 1)
    return max(result - 1, 0)


def parse_excel_cell_reference(reference):
    match = re.match(r'^(?P<column>[A-Z]+)(?P<row>\d+)$', str(reference or '').strip().upper())
    if not match:
        return None, None
    return excel_column_letters_to_index(match.group('column')), int(match.group('row')) - 1


def read_xlsx_cell_value(cell, shared_strings):
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
    return value


def apply_xlsx_merged_cells(root, row_maps):
    for node in root.iter():
        if not (node.tag.endswith('}mergeCell') or node.tag == 'mergeCell'):
            continue
        ref = str(node.attrib.get('ref') or '').strip()
        if ':' not in ref:
            continue
        start_ref, end_ref = ref.split(':', 1)
        start_col, start_row = parse_excel_cell_reference(start_ref)
        end_col, end_row = parse_excel_cell_reference(end_ref)
        if start_col is None or start_row is None or end_col is None or end_row is None:
            continue
        top_left_value = row_maps.get(start_row, {}).get(start_col, '')
        if top_left_value == '':
            continue
        for row_index in range(start_row, end_row + 1):
            row_map = row_maps.setdefault(row_index, {})
            for column_index in range(start_col, end_col + 1):
                row_map.setdefault(column_index, top_left_value)


def extract_xlsx_sheet_rows(root, shared_strings):
    row_maps = {}
    max_column_index = -1
    for row in root.iter():
        if not (row.tag.endswith('}row') or row.tag == 'row'):
            continue
        declared_row_index = int(row.attrib.get('r', '1')) - 1
        row_map = row_maps.setdefault(declared_row_index, {})
        for cell in list(row):
            if not (cell.tag.endswith('}c') or cell.tag == 'c'):
                continue
            column_index, parsed_row_index = parse_excel_cell_reference(cell.attrib.get('r'))
            if column_index is None:
                continue
            row_index = parsed_row_index if parsed_row_index is not None else declared_row_index
            row_map = row_maps.setdefault(row_index, {})
            row_map[column_index] = read_xlsx_cell_value(cell, shared_strings)
            max_column_index = max(max_column_index, column_index)

    apply_xlsx_merged_cells(root, row_maps)
    for row_map in row_maps.values():
        if row_map:
            max_column_index = max(max_column_index, max(row_map.keys()))

    rows = []
    for row_index in sorted(row_maps.keys()):
        row_map = row_maps[row_index]
        values = [str(row_map.get(column_index, '') or '') for column_index in range(max_column_index + 1)]
        while values and not str(values[-1]).strip():
            values.pop()
        if any(str(value).strip() for value in values):
            rows.append(values)
    return rows


def normalize_table_header(value):
    return re.sub(r'[\s_\-（）()【】\[\]]+', '', str(value or '').strip().lower())


def detect_tabular_case_columns(row):
    detected = {}
    for index, value in enumerate(row):
        normalized = normalize_table_header(value)
        if not normalized:
            continue
        for field, aliases in TABULAR_CASE_COLUMN_ALIASES.items():
            if normalized in {normalize_table_header(alias) for alias in aliases} and field not in detected:
                detected[field] = index
                break
    if 'case_name' in detected and 'step_description' in detected:
        return detected
    return None


def get_tabular_row_value(row, index):
    if index is None or index < 0 or index >= len(row):
        return ''
    return str(row[index] or '').strip()


def should_append_expected_result_to_step(operation):
    normalized = normalize_match_text(operation)
    if not normalized:
        return True
    keywords = (
        '验证', '校验', '断言', '检查', '确认', '比对',
        '预期', '结果', '成功', '失败', 'toast', '提示',
    )
    return any(keyword in normalized for keyword in keywords)


def build_tabular_step_description(operation, test_data='', expected_result='', remark=''):
    operation = str(operation or '').strip()
    extras = []
    if str(test_data or '').strip():
        extras.append(f'测试数据：{str(test_data).strip()}')
    if str(expected_result or '').strip() and should_append_expected_result_to_step(operation):
        extras.append(f'预期结果：{str(expected_result).strip()}')
    if str(remark or '').strip():
        extras.append(f'备注：{str(remark).strip()}')
    if not extras:
        return operation
    if not operation:
        return '；'.join(extras)
    return f'{operation}（{"；".join(extras)}）'


def format_tabular_cases_as_text(cases):
    blocks = []
    for case in cases:
        steps = case.get('steps') or []
        if not case.get('name') or not steps:
            continue
        lines = [f'用例：{case["name"]}']
        if case.get('folder_name'):
            lines.append(f'文件夹：{case["folder_name"]}')
        if case.get('priority'):
            lines.append(f'优先级：{case["priority"]}')
        if case.get('precondition'):
            lines.append(f'前置条件：{case["precondition"]}')
        lines.append('步骤：')
        for step_index, step in enumerate(steps, start=1):
            description = str(step.get('description') or '').strip()
            if description:
                lines.append(f'{step_index}. {description}')
        blocks.append('\n'.join(lines))
    return '\n\n'.join(blocks).strip()


def tabular_rows_to_case_text(rows, sheet_name=''):
    if not rows:
        return ''

    cases = []
    current_case = None
    current_columns = None

    for raw_row in rows:
        row = [str(item or '').strip() for item in (raw_row or [])]
        if not any(row):
            continue

        if len(row) == 1 and row[0].lower().startswith('worksheet '):
            current_columns = None
            current_case = None
            continue

        detected_columns = detect_tabular_case_columns(row)
        if detected_columns:
            current_columns = detected_columns
            current_case = None
            continue

        if not current_columns:
            continue

        case_name = get_tabular_row_value(row, current_columns.get('case_name'))
        folder_name = get_tabular_row_value(row, current_columns.get('folder_name'))
        priority = get_tabular_row_value(row, current_columns.get('priority'))
        precondition = get_tabular_row_value(row, current_columns.get('precondition'))
        operation = get_tabular_row_value(row, current_columns.get('step_description'))
        test_data = get_tabular_row_value(row, current_columns.get('test_data'))
        expected_result = get_tabular_row_value(row, current_columns.get('expected_result'))
        remark = get_tabular_row_value(row, current_columns.get('remark'))

        if case_name:
            if not current_case or current_case.get('name') != case_name:
                current_case = {
                    'name': case_name,
                    'folder_name': folder_name,
                    'priority': priority,
                    'precondition': precondition,
                    'sheet_name': sheet_name,
                    'steps': [],
                }
                cases.append(current_case)
            else:
                current_case['folder_name'] = current_case.get('folder_name') or folder_name
                current_case['priority'] = current_case.get('priority') or priority
                current_case['precondition'] = current_case.get('precondition') or precondition
        elif current_case is None:
            continue

        if not operation and not test_data and not expected_result and not remark:
            continue

        description = build_tabular_step_description(operation, test_data, expected_result, remark)
        if description:
            current_case['steps'].append({
                'description': description,
                'step_number': get_tabular_row_value(row, current_columns.get('step_number')),
            })

    return format_tabular_cases_as_text(cases)


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


def build_generation_system_prompt(skill_content, source_text):
    skill = str(skill_content or '').strip() or DEFAULT_UI_GENERATION_SKILL
    if len(skill) > MAX_FULL_SKILL_CHARS:
        skill = select_relevant_skill_content(skill, source_text)
        skill_header = '【业务 Skill 相关片段】'
        skill_note = (
            '当前 Skill 内容较长，系统已抽取与当前自然语言用例最相关的片段。'
            '如果片段中包含完整业务流程，必须按流程补全后续步骤。'
        )
    else:
        skill_header = '【业务 Skill】'
        skill_note = '必须严格执行以下业务 Skill 中的流程、元素命名和等待要求。'

    return f'{GENERATION_HARD_CONSTRAINTS}\n\n{skill_header}\n{skill}\n\n【执行要求】\n{skill_note}'


def select_relevant_skill_content(skill_content, source_text, max_chars=MAX_RELEVANT_SKILL_CHARS):
    skill = str(skill_content or '').strip()
    if len(skill) <= max_chars:
        return skill

    chunks = split_skill_into_chunks(skill)
    keywords = extract_relevance_keywords(source_text)
    scored = []
    for index, chunk in enumerate(chunks):
        normalized = normalize_match_text(chunk)
        score = 0
        for keyword in keywords:
            if keyword and keyword in normalized:
                score += 1 + min(normalized.count(keyword), 3)
        if any(marker in normalized for marker in ['json', 'manifest', 'action_type', 'element', 'waitfor']):
            score += 2
        if index == 0:
            score += 3
        scored.append((score, index, chunk))

    selected_indexes = {0}
    total = len(chunks[0]) if chunks else 0
    for score, index, chunk in sorted(scored, key=lambda item: (-item[0], item[1])):
        if score <= 0 and total > max_chars * 0.6:
            continue
        if index in selected_indexes:
            continue
        projected = total + len(chunk) + 2
        if projected > max_chars and total >= max_chars * 0.7:
            continue
        selected_indexes.add(index)
        total = projected
        if total >= max_chars:
            break

    selected = [chunks[index] for index in sorted(selected_indexes)]
    result = '\n\n'.join(selected).strip()
    if len(result) > max_chars:
        result = result[:max_chars].rsplit('\n', 1)[0].strip()
    return result


def split_skill_into_chunks(skill_content):
    skill = str(skill_content or '').strip()
    if not skill:
        return []

    chunks = re.split(r'(?m)\n\s*\n|(?=^\s*(?:\d+[\.\、\)]|[一二三四五六七八九十]+[、.])\s*)', skill)
    cleaned = [chunk.strip() for chunk in chunks if chunk and chunk.strip()]
    if len(cleaned) <= 1:
        cleaned = [skill[index:index + 1800].strip() for index in range(0, len(skill), 1800)]
    return cleaned


def extract_relevance_keywords(source_text):
    text = str(source_text or '')
    normalized = normalize_match_text(text)
    keywords = set()
    keywords.update(re.findall(r'[A-Za-z][A-Za-z0-9_\- ]{1,40}', text))
    keywords.update(re.findall(r'[\u4e00-\u9fff]{2,12}', text))
    for keyword in [
        '数据要素', '数据定义', '管理模式', '用户模式', '登录', '创建', '新建',
        '验证', '成功', '搜索', '查询', '提交', '保存', '确定', '确认',
    ]:
        if keyword in text:
            keywords.add(keyword)
    return {
        normalize_match_text(keyword)
        for keyword in keywords
        if len(normalize_match_text(keyword)) >= 2 and normalize_match_text(keyword) in normalized
    }


def estimate_generation_max_tokens(model_config, source_text, skill_content=''):
    configured = normalize_int(getattr(model_config, 'max_tokens', None), MIN_GENERATION_MAX_TOKENS, 1024, MAX_GENERATION_MAX_TOKENS)
    requested = MIN_GENERATION_MAX_TOKENS
    if len(str(source_text or '')) > 3000 or len(str(skill_content or '')) > MAX_FULL_SKILL_CHARS:
        requested = LONG_GENERATION_MAX_TOKENS
    return min(max(configured, requested), MAX_GENERATION_MAX_TOKENS)


def build_routed_generation_skill_content(project, source_text, root_skill=None, user=None):
    """Build a compact skill prompt from the root skill plus matched modules."""
    root_content = getattr(root_skill, 'content', None) or str(root_skill or '').strip() or DEFAULT_UI_GENERATION_SKILL
    route_info = route_generation_skill_modules(project, source_text, user=user)
    modules = route_info.get('selected_module_objects') or []
    if not modules:
        return root_content, route_info

    parts = [
        '【主 Skill 入口】',
        root_content,
        '',
        '【后端识别结果】',
        json.dumps({
            'intents': route_info.get('detected_intents') or [],
            'entities': route_info.get('detected_entities') or {},
        }, ensure_ascii=False, indent=2),
        '',
        '【按需加载的 Skill 模块】',
    ]
    for module in modules:
        content = str(module.content or '').strip()
        max_chars = normalize_int(getattr(module, 'max_prompt_chars', None), 4000, 500, 16000)
        if len(content) > max_chars:
            content = content[:max_chars].rsplit('\n', 1)[0].strip()
        parts.append(
            f'\n### {module.code} | {module.name} | {module.module_type} | priority={module.priority}\n'
            f'摘要: {module.summary or module.description or "-"}\n'
            f'{content}'
        )
    skill_content = '\n'.join(parts).strip()
    route_info['prompt_chars'] = len(skill_content)
    return skill_content, route_info


def split_skill_module_summary(summary):
    text = str(summary or '').strip()
    if not text:
        return []

    items = []
    for line in text.splitlines():
        normalized = re.sub(r'^\s*(?:[-*•]+|\d+[.)、：:]?)\s*', '', line).strip()
        if normalized:
            items.append(normalized)

    if len(items) <= 1:
        text = items[0] if items else text
        items = [
            item.strip()
            for item in re.split(r'[；;\n]+', text)
            if item.strip()
        ]

    return items or [text]


def generate_skill_module_content_draft(
    *,
    name='',
    code='',
    module_type='business_flow',
    summary='',
    keywords=None,
    intents=None,
    pages=None,
):
    summary_rules = split_skill_module_summary(summary)
    module_label = SKILL_MODULE_TYPE_LABELS.get(module_type, module_type or '模块')
    normalized_keywords = normalize_json_list(keywords)
    normalized_intents = normalize_json_list(intents)
    normalized_pages = normalize_json_list(pages)

    type_specific_guidance = {
        'global': [
            '该模块用于补充全局输出约束，只描述全局适用规则，不要绑定单一业务页面。',
            '如果摘要中出现格式、断言、等待、元素复用等要求，必须提升为所有相关用例都遵守的规则。',
            '当其他业务模块给出更具体流程时，本模块只负责补充全局边界，不重复展开具体步骤。',
        ],
        'page': [
            '该模块只描述目标页面或页面簇的上下文、页面入口、页面关键区域、稳定等待点和优先复用元素命名。',
            '如果摘要中包含页面层级或弹窗名称，必须明确这些页面名称在生成结果中如何被引用。',
            '页面模块可以给出页面内通用操作顺序，但不要代替完整业务流模块描述端到端流程。',
        ],
        'business_flow': [
            '该模块必须把业务流程展开为完整、连续、不可跳步的执行链路，不能只写前半段或关键节点。',
            '若摘要中包含“创建/新增/提交/保存/确认/验证成功”等动作，必须覆盖从进入页面到最终成功验证的完整闭环。',
            '需要明确关键等待点、弹窗确认、提交动作和成功验证，避免 AI 只生成到中途步骤。',
        ],
        'repair': [
            '该模块用于修复模型常见漏步或错误生成问题，要明确指出哪些情况必须补齐、替换或禁止。',
            '修复规则应优先描述“当出现什么情况时，必须如何修复”，并给出可执行的补齐策略。',
            '如果摘要包含反例或历史问题，必须把这些问题转成明确的禁止事项或纠正规则。',
        ],
    }

    lines = [
        f'你是 TestHub UI 自动化测试用例生成的模块化 Skill：{name or code or "未命名模块"}。',
        f'模块编码：{code or "-"}',
        f'模块类型：{module_label}',
        '',
        '职责定位：',
        f'1. 该模块只在命中当前业务上下文时参与生成，用于补充“{module_label}”相关规则。',
        '2. 输出内容必须服务于 TestHub 可导入的 UI 自动化 JSON manifest 生成，不输出闲聊说明。',
        '3. 如果和主 Skill 冲突，遵循主 Skill 的输出格式和安全约束；如果本模块更具体，则以本模块的业务细节为准。',
        '',
        '命中上下文：',
        f'- intents: {", ".join(normalized_intents) if normalized_intents else "-"}',
        f'- keywords: {", ".join(normalized_keywords) if normalized_keywords else "-"}',
        f'- pages: {", ".join(normalized_pages) if normalized_pages else "-"}',
        '',
        '摘要规则：',
    ]

    if summary_rules:
        lines.extend([f'{index}. {rule}' for index, rule in enumerate(summary_rules, start=1)])
    else:
        lines.append('1. 未提供摘要规则，请补充具体业务约束。')

    lines.extend([
        '',
        '模块执行要求：',
        '1. 仔细识别自然语言中的业务目标、页面入口、操作对象、等待点、断言点和结果校验。',
        '2. 只输出可以落地执行的规则，不写空泛原则，不写“按实际情况处理”这类模糊措辞。',
        '3. 涉及页面切换、弹窗打开、搜索查询、提交保存、确认按钮、模式切换时，必须补充 wait 或 waitFor 规则。',
        '4. 涉及成功校验时，必须补充可执行的断言或成功提示等待，不允许省略验证成功步骤。',
        '5. 涉及元素描述时，优先约束元素命名、页面归属、定位稳定性和复用优先级。',
        '',
        f'{module_label}专项约束：',
    ])
    lines.extend([f'{index}. {rule}' for index, rule in enumerate(type_specific_guidance.get(module_type, []), start=1)])

    lines.extend([
        '',
        '输出风格要求：',
        '1. 使用规则化、约束化表达，优先使用“必须 / 禁止 / 优先 / 若…则…”这类明确措辞。',
        '2. 如果摘要本身包含步骤顺序，必须保留顺序语义并展开为完整链路。',
        '3. 如果摘要本身包含特定业务名词、页面名、数据定义名或弹窗名，必须原样保留，不要改写成泛称。',
        '',
        '禁止事项：',
        '1. 不要生成与当前模块无关的业务流程。',
        '2. 不要省略摘要中已明确要求的关键步骤、确认动作或成功校验。',
        '3. 不要输出 Markdown 代码块，不要加入解释性前后缀。',
    ])
    return '\n'.join(lines).strip()


def analyze_generation_skill_module_match(module, normalized_source, keywords, intents, entities):
    score = 0
    reasons = []
    module_intents = normalize_json_list(getattr(module, 'intents', None))
    module_keywords = normalize_json_list(getattr(module, 'keywords', None))
    module_pages = normalize_json_list(getattr(module, 'pages', None))

    matched_intents = [intent for intent in module_intents if intent in intents]
    matched_keywords = []
    matched_pages = []
    matched_terms = []

    for intent in matched_intents:
        score += 100
        if 'intent_match' not in reasons:
            reasons.append('intent_match')

    for keyword in module_keywords:
        normalized_keyword = normalize_match_text(keyword)
        if not normalized_keyword:
            continue
        if normalized_keyword in normalized_source:
            score += 50
            matched_keywords.append(keyword)
        elif normalized_keyword in keywords:
            score += 25
            matched_keywords.append(keyword)
    if matched_keywords:
        reasons.append('keyword_match')

    for page in module_pages:
        normalized_page = normalize_match_text(page)
        if normalized_page and normalized_page in normalized_source:
            score += 30
            matched_pages.append(page)
    if matched_pages:
        reasons.append('page_match')

    if module.module_type == 'business_flow' and any(intent.startswith('create_') for intent in intents):
        score += 10
        reasons.append('create_flow_bias')
    if module.module_type == 'page' and any(keyword in normalize_match_text(module.name) for keyword in keywords):
        score += 10
        reasons.append('page_name_bias')

    for term in entities.get('technical_terms') or []:
        normalized_term = normalize_match_text(term)
        if normalized_term and normalized_term in normalize_match_text(module.content):
            score += 10
            matched_terms.append(term)
    if matched_terms:
        reasons.append('technical_term_match')

    if score > 0:
        score += int(getattr(module, 'priority', 0) or 0)
        reasons.insert(0, 'module_metadata')

    return {
        'score': score,
        'matched_intents': matched_intents,
        'matched_keywords': matched_keywords,
        'matched_pages': matched_pages,
        'matched_terms': matched_terms,
        'reasons': reasons,
        'keywords': module_keywords,
        'intents': module_intents,
        'pages': module_pages,
    }


def build_generation_skill_module_debug_info(
    module,
    *,
    score=0,
    reasons=None,
    match_details=None,
    matched_triggers=None,
    selected=False,
    omitted_reason='',
):
    match_details = match_details or {}
    matched_triggers = matched_triggers or []
    prompt_char_limit = normalize_int(getattr(module, 'max_prompt_chars', None), 4000, 500, 16000)
    content_chars = len(str(module.content or ''))
    return {
        'id': module.id,
        'code': module.code,
        'name': module.name,
        'module_type': module.module_type,
        'module_type_label': SKILL_MODULE_TYPE_LABELS.get(module.module_type, module.module_type),
        'priority': module.priority,
        'summary': module.summary or module.description or '',
        'score': score,
        'reasons': reasons or [],
        'reason_labels': [SKILL_ROUTE_REASON_LABELS.get(item, item) for item in (reasons or [])],
        'keywords': match_details.get('keywords') or normalize_json_list(getattr(module, 'keywords', None)),
        'intents': match_details.get('intents') or normalize_json_list(getattr(module, 'intents', None)),
        'pages': match_details.get('pages') or normalize_json_list(getattr(module, 'pages', None)),
        'matched_intents': match_details.get('matched_intents') or [],
        'matched_keywords': match_details.get('matched_keywords') or [],
        'matched_pages': match_details.get('matched_pages') or [],
        'matched_terms': match_details.get('matched_terms') or [],
        'matched_triggers': matched_triggers,
        'selected': selected,
        'omitted_reason': omitted_reason,
        'content_chars': content_chars,
        'prompt_char_limit': prompt_char_limit,
        'effective_prompt_chars': min(content_chars, prompt_char_limit),
    }


def route_generation_skill_modules(project, source_text, user=None, max_modules=12, max_chars=24000):
    """Select the smallest useful set of modular skills for the current case."""
    ensure_builtin_generation_skill_modules()
    intents, entities = detect_generation_intents_and_entities(source_text)
    normalized_source = normalize_match_text(source_text)
    keywords = extract_relevance_keywords(source_text)

    try:
        from .models import (
            AITestCaseGenerationSkillDependency,
            AITestCaseGenerationSkillModule,
            AITestCaseGenerationSkillTrigger,
        )
        access_filter = models.Q(created_by__isnull=True)
        if user and getattr(user, 'is_authenticated', False):
            access_filter |= models.Q(created_by=user)
        modules = list(
            AITestCaseGenerationSkillModule.objects.filter(access_filter, is_active=True)
            .select_related('category', 'created_by')
            .order_by('-priority', 'module_type', 'name')
        )
        triggers = list(
            AITestCaseGenerationSkillTrigger.objects.filter(module__in=modules, is_active=True)
            .select_related('module')
        )
    except Exception as exc:
        logger.warning('AI generation skill routing skipped: %s', exc)
        return {
            'detected_intents': intents,
            'detected_entities': entities,
            'matched_modules': [],
            'omitted_modules': [],
            'selected_modules': [],
            'selected_module_objects': [],
            'prompt_chars': 0,
            'warnings': [f'Skill模块路由跳过: {exc}'],
        }

    module_scores = {}
    module_reasons = {}
    module_match_details = {}
    module_trigger_hits = {}
    module_by_id = {module.id: module for module in modules}
    for module in modules:
        match_details = analyze_generation_skill_module_match(module, normalized_source, keywords, intents, entities)
        module_match_details[module.id] = match_details
        score = match_details['score']
        if score > 0:
            module_scores[module.id] = score
            module_reasons[module.id] = list(match_details.get('reasons') or ['module_metadata'])
        if module.module_type in {'global', 'repair'}:
            module_scores[module.id] = max(module_scores.get(module.id, 0), 20 + module.priority)
            module_reasons.setdefault(module.id, []).append('always_on')

    for trigger in triggers:
        module = trigger.module
        if module.id not in module_by_id:
            continue
        matched = match_generation_skill_trigger(trigger, normalized_source, intents, entities)
        if matched:
            module_scores[module.id] = module_scores.get(module.id, 0) + trigger.weight
            module_reasons.setdefault(module.id, []).append('trigger_match')
            module_trigger_hits.setdefault(module.id, []).append({
                'trigger_type': trigger.trigger_type,
                'trigger_type_label': SKILL_TRIGGER_TYPE_LABELS.get(trigger.trigger_type, trigger.trigger_type),
                'value': trigger.value,
                'weight': trigger.weight,
            })

    ranked = sorted(
        [module_by_id[module_id] for module_id in module_scores.keys()],
        key=lambda item: (-module_scores[item.id], -item.priority, item.code),
    )
    ranked = resolve_generation_skill_dependencies(ranked, module_by_id)
    for module in ranked:
        module_scores.setdefault(module.id, int(getattr(module, 'priority', 0) or 0))
        module_reasons.setdefault(module.id, ['dependency'])

    matched_modules = [
        build_generation_skill_module_debug_info(
            module,
            score=module_scores.get(module.id, 0),
            reasons=list(dict.fromkeys(module_reasons.get(module.id, []))),
            match_details=module_match_details.get(module.id) or {},
            matched_triggers=module_trigger_hits.get(module.id) or [],
            selected=False,
        )
        for module in ranked
    ]

    selected = []
    selected_ids = set()
    total_chars = 0
    omitted_modules = []
    for module in ranked:
        module_chars = min(len(str(module.content or '')), normalize_int(module.max_prompt_chars, 4000, 500, 16000))
        if selected and len(selected) >= max_modules:
            omitted_modules.append(
                build_generation_skill_module_debug_info(
                    module,
                    score=module_scores.get(module.id, 0),
                    reasons=list(dict.fromkeys(module_reasons.get(module.id, []))),
                    match_details=module_match_details.get(module.id) or {},
                    matched_triggers=module_trigger_hits.get(module.id) or [],
                    selected=False,
                    omitted_reason='max_modules',
                )
            )
            continue
        if selected and total_chars + module_chars > max_chars:
            omitted_modules.append(
                build_generation_skill_module_debug_info(
                    module,
                    score=module_scores.get(module.id, 0),
                    reasons=list(dict.fromkeys(module_reasons.get(module.id, []))),
                    match_details=module_match_details.get(module.id) or {},
                    matched_triggers=module_trigger_hits.get(module.id) or [],
                    selected=False,
                    omitted_reason='max_prompt_chars',
                )
            )
            continue
        selected.append(module)
        selected_ids.add(module.id)
        total_chars += module_chars

    selected_info = []
    for item in matched_modules:
        if item['id'] in selected_ids:
            item['selected'] = True
            item['omitted_reason'] = ''
            selected_info.append(item)
    return {
        'detected_intents': intents,
        'detected_entities': entities,
        'matched_modules': matched_modules,
        'omitted_modules': omitted_modules,
        'selected_modules': selected_info,
        'selected_module_objects': selected,
        'prompt_chars': total_chars,
        'warnings': [],
    }


def detect_generation_intents_and_entities(source_text):
    text = str(source_text or '')
    normalized = normalize_match_text(text)
    intents = []
    entities = {}

    def add_intent(intent):
        if intent not in intents:
            intents.append(intent)

    if any(keyword in normalized for keyword in ['登录', '登陆']):
        add_intent('login')
    if any(keyword in normalized for keyword in ['管理模式', '进入管理']):
        add_intent('enter_admin_mode')
    if any(keyword in normalized for keyword in ['用户模式', '进入用户']):
        add_intent('enter_user_mode')
    if any(keyword in normalized for keyword in ['创建', '新建', '新增']):
        add_intent('create')
    if any(keyword in normalized for keyword in ['验证', '校验', '断言', '检查']):
        add_intent('verify')
    if '数据要素' in text:
        add_intent('data_element')
    if '数据定义' in text:
        add_intent('data_definition')

    data_element_intents = extract_data_element_creation_intents(text)
    if data_element_intents:
        add_intent('create_data_element')
        entities['data_elements'] = data_element_intents

    for name in re.findall(r'[A-Z][A-Za-z0-9_]*(?:\s+[A-Z][A-Za-z0-9_]*)*', text):
        if len(name.strip()) >= 2:
            entities.setdefault('technical_terms', []).append(name.strip())

    return intents, entities


def score_generation_skill_module(module, normalized_source, keywords, intents, entities):
    score = 0
    module_intents = normalize_json_list(getattr(module, 'intents', None))
    module_keywords = normalize_json_list(getattr(module, 'keywords', None))
    module_pages = normalize_json_list(getattr(module, 'pages', None))

    for intent in module_intents:
        if intent in intents:
            score += 100
    for keyword in module_keywords:
        normalized_keyword = normalize_match_text(keyword)
        if normalized_keyword and normalized_keyword in normalized_source:
            score += 50
        elif normalized_keyword in keywords:
            score += 25
    for page in module_pages:
        normalized_page = normalize_match_text(page)
        if normalized_page and normalized_page in normalized_source:
            score += 30

    if module.module_type == 'business_flow' and any(intent.startswith('create_') for intent in intents):
        score += 10
    if module.module_type == 'page' and any(keyword in normalize_match_text(module.name) for keyword in keywords):
        score += 10

    for term in entities.get('technical_terms') or []:
        normalized_term = normalize_match_text(term)
        if normalized_term and normalized_term in normalize_match_text(module.content):
            score += 10
    if score > 0:
        score += int(getattr(module, 'priority', 0) or 0)
    return score


def match_generation_skill_trigger(trigger, normalized_source, intents, entities):
    trigger_type = trigger.trigger_type
    value = str(trigger.value or '').strip()
    normalized_value = normalize_match_text(value)
    if not value:
        return False
    if trigger_type in {'keyword', 'page'}:
        return normalized_value in normalized_source
    if trigger_type == 'intent':
        return normalized_value in {normalize_match_text(item) for item in intents}
    if trigger_type == 'regex':
        try:
            return bool(re.search(value, normalized_source, flags=re.I))
        except re.error:
            return False
    if trigger_type == 'entity':
        entity_text = normalize_match_text(json.dumps(entities, ensure_ascii=False))
        return normalized_value in entity_text
    return False


def resolve_generation_skill_dependencies(ranked_modules, module_by_id):
    selected_by_id = {module.id: module for module in ranked_modules}
    try:
        from .models import AITestCaseGenerationSkillDependency
        dependencies = AITestCaseGenerationSkillDependency.objects.filter(
            module_id__in=selected_by_id.keys()
        ).select_related('depends_on')
    except Exception:
        return ranked_modules
    for dependency in dependencies:
        if dependency.depends_on_id in module_by_id:
            selected_by_id.setdefault(dependency.depends_on_id, module_by_id[dependency.depends_on_id])
    return sorted(selected_by_id.values(), key=lambda item: (-item.priority, item.module_type, item.code))


def normalize_json_list(value):
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in re.split(r'[,，;；\n]+', value) if item.strip()]
    return []


def ensure_builtin_generation_skill_modules():
    try:
        from .models import (
            AITestCaseGenerationSkillCategory,
            AITestCaseGenerationSkillModule,
            AITestCaseGenerationSkillTrigger,
        )
    except Exception:
        return

    try:
        category, _ = AITestCaseGenerationSkillCategory.objects.get_or_create(
            code='builtin',
            defaults={
                'name': '内置生成能力',
                'description': '系统内置的 UI 自动化用例生成 Skill 模块',
                'order': 0,
                'is_active': True,
            },
        )
        builtin_modules = [
            {
                'code': 'ui.global.output_manifest',
                'name': '全局输出规范',
                'module_type': 'global',
                'priority': 100,
                'keywords': ['JSON', 'manifest', 'action_type', 'element', 'waitFor'],
                'intents': [],
                'pages': [],
                'summary': '约束模型输出 TestHub 可导入 JSON manifest。',
                'config': {},
                'content': GENERATION_HARD_CONSTRAINTS,
            },
            {
                'code': 'ui.global.wait_rules',
                'name': '通用等待规则',
                'module_type': 'global',
                'priority': 90,
                'keywords': ['等待', '搜索', '查询', '提交', '保存', '确定', '确认', '管理模式'],
                'intents': ['enter_admin_mode', 'enter_user_mode', 'verify'],
                'pages': [],
                'summary': '页面变化动作后必须安排 wait 或 waitFor。',
                'config': {},
                'content': (
                    '搜索、查询、切换管理模式/用户模式、提交、保存、点击确定/确认后，'
                    '必须生成 wait 或 waitFor。若下一步操作具体元素，优先 waitFor 下一步元素；'
                    '若下一步验证成功提示，优先 waitFor 操作成功 toast。'
                ),
            },
            {
                'code': 'ui.flow.data_element.create',
                'name': '创建数据要素流程',
                'module_type': 'business_flow',
                'priority': 200,
                'keywords': ['创建数据要素', '新建数据要素', '数据要素', '数据定义', 'SYS Decimal'],
                'intents': ['create_data_element', 'data_element'],
                'pages': ['数据结构设置', '数据要素'],
                'summary': '创建数据要素时强制补齐数据定义确认、标签、提交和成功验证。',
                'config': {
                    'deterministic_rule': 'ensure_data_element_creation_flow',
                    'required_phases': [
                        'nav_structure',
                        'nav_element',
                        'open_create',
                        'fill_name',
                        'open_definition_dialog',
                        'search_definition',
                        'wait_search',
                        'select_definition',
                        'confirm_definition',
                        'wait_definition_confirm',
                        'fill_label',
                        'submit_create',
                        'wait_success',
                    ],
                },
                'content': (
                    '创建数据要素完整流程必须包含：进入数据结构设置，进入数据要素，点击新建，'
                    '填写数据要素名称，打开选择数据定义弹框，在搜索框输入目标数据定义并回车，'
                    '等待搜索结果，选中目标数据定义，点击选择数据定义弹框确定按钮，等待弹框关闭，'
                    '填写要素标签，点击新建数据要素弹窗确定按钮提交，等待操作成功提示出现。'
                    '如果自然语言指定 SYS Decimal 等数据定义，搜索和选择步骤必须使用该数据定义名称。'
                ),
            },
        ]
        for module_data in builtin_modules:
            module, created = AITestCaseGenerationSkillModule.objects.get_or_create(
                code=module_data['code'],
                defaults={
                    **module_data,
                    'category': category,
                    'description': module_data['summary'],
                    'is_active': True,
                    'max_prompt_chars': 4000,
                    'created_by': None,
                },
            )

            if not created:
                updated_fields = []
                if module.category_id != category.id:
                    module.category = category
                    updated_fields.append('category')
                if module.created_by_id is not None:
                    module.created_by = None
                    updated_fields.append('created_by')
                if not module.description and module_data.get('summary'):
                    module.description = module_data['summary']
                    updated_fields.append('description')
                if not module.summary and module_data.get('summary'):
                    module.summary = module_data['summary']
                    updated_fields.append('summary')
                if not module.max_prompt_chars:
                    module.max_prompt_chars = 4000
                    updated_fields.append('max_prompt_chars')
                if updated_fields:
                    updated_fields.append('updated_at')
                    module.save(update_fields=updated_fields)

            for keyword in (module.keywords or module_data.get('keywords') or []):
                AITestCaseGenerationSkillTrigger.objects.get_or_create(
                    module=module,
                    trigger_type='keyword',
                    value=keyword,
                    defaults={'weight': 50, 'is_active': True},
                )
            for intent in (module.intents or module_data.get('intents') or []):
                AITestCaseGenerationSkillTrigger.objects.get_or_create(
                    module=module,
                    trigger_type='intent',
                    value=intent,
                    defaults={'weight': 100, 'is_active': True},
                )
    except Exception as exc:
        logger.warning('Failed to ensure builtin AI generation skill modules: %s', exc)


def generate_ui_test_case_manifest(project, source_text, skill_content='', model_config=None, use_ai=True):
    warnings = []
    source_text = str(source_text or '').strip()
    if not source_text:
        raise ValidationError('请提供自然语言用例或上传可解析的用例文件')

    prebuilt_manifest = try_parse_manifest(source_text)
    if prebuilt_manifest:
        manifest = normalize_manifest(project, prebuilt_manifest)
        warnings.extend(enforce_generation_business_rules(project, manifest, source_text))
        warnings.extend(validate_manifest_quality(manifest))
        return manifest, warnings, 'manifest'

    if use_ai and model_config:
        try:
            raw = call_openai_compatible_model(project, source_text, skill_content, model_config)
            manifest = normalize_manifest(project, extract_json_payload(raw))
            warnings.extend(enforce_generation_business_rules(project, manifest, source_text))
            warnings.extend(validate_manifest_quality(manifest))
            return manifest, warnings, 'ai'
        except Exception as exc:
            logger.warning('AI UI test case generation failed, fallback to heuristic parser: %s', exc, exc_info=True)
            warnings.append(f'AI生成失败，已使用规则解析兜底: {exc}')

    manifest = heuristic_manifest(project, source_text)
    warnings.extend(enforce_generation_business_rules(project, manifest, source_text))
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

    system_prompt = build_generation_system_prompt(skill_content, source_text)
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
        'max_tokens': estimate_generation_max_tokens(model_config, source_text, skill_content),
        'stream': False,
    }
    temperature = getattr(model_config, 'temperature', None)
    if temperature is None:
        temperature = 0.2
    else:
        temperature = min(temperature, 0.3)
    apply_sampling_params(payload, model_config, temperature_override=temperature)
    response = requests.post(
        url,
        headers={'Authorization': f'Bearer {model_config.api_key}', 'Content-Type': 'application/json'},
        json=payload,
        timeout=(60, 900),
    )
    if response.status_code >= 400:
        raise ValidationError(f'AI模型调用失败: {response.status_code} {response.text[:1000]}')
    data = response.json()
    content, finish_reason = extract_model_choice_content(data)
    content_parts = [content]
    messages = payload['messages']

    for _ in range(2):
        if not is_length_limited_finish(finish_reason):
            break
        continuation_messages = messages + [
            {'role': 'assistant', 'content': ''.join(content_parts)},
            {
                'role': 'user',
                'content': '上一条 JSON 因长度限制被截断。请从截断位置继续输出剩余 JSON，不要重复已输出内容，不要解释，不要使用 Markdown。',
            },
        ]
        continuation_payload = dict(payload)
        continuation_payload['messages'] = continuation_messages
        try:
            continuation_response = requests.post(
                url,
                headers={'Authorization': f'Bearer {model_config.api_key}', 'Content-Type': 'application/json'},
                json=continuation_payload,
                timeout=(60, 900),
            )
            if continuation_response.status_code >= 400:
                logger.warning(
                    'AI UI test case generation continuation failed: %s %s',
                    continuation_response.status_code,
                    continuation_response.text[:1000],
                )
                break
            next_content, finish_reason = extract_model_choice_content(continuation_response.json())
        except Exception as exc:
            logger.warning('AI UI test case generation continuation failed: %s', exc, exc_info=True)
            break
        content_parts.append(next_content)
        messages = continuation_messages

    return ''.join(content_parts)


def extract_model_choice_content(data):
    try:
        choice = data['choices'][0]
        return choice['message']['content'], choice.get('finish_reason')
    except (KeyError, IndexError, TypeError) as exc:
        raise ValidationError(f'AI模型响应格式不正确: {exc}')


def is_length_limited_finish(finish_reason):
    return str(finish_reason or '').lower() in {'length', 'max_tokens', 'token_limit'}


def extract_json_payload(raw_text):
    text = str(raw_text or '').strip()
    fenced = re.search(r'```(?:json)?\s*(.*?)```', text, flags=re.S | re.I)
    if fenced:
        text = fenced.group(1).strip()
    candidates = [text]
    balanced_payload = extract_balanced_json_payload(text)
    if balanced_payload and balanced_payload not in candidates:
        candidates.append(balanced_payload)

    last_error = None
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = exc

        repaired = repair_json_like_text(candidate)
        if repaired != candidate:
            try:
                return json.loads(repaired)
            except json.JSONDecodeError as exc:
                last_error = exc

        truncated_repaired = repair_truncated_json_text(repaired)
        if truncated_repaired != repaired:
            for repaired_candidate in (truncated_repaired, repair_json_like_text(truncated_repaired)):
                try:
                    return json.loads(repaired_candidate)
                except json.JSONDecodeError as exc:
                    last_error = exc

    if last_error:
        raise last_error
    raise json.JSONDecodeError('No JSON object found', text, 0)


def extract_balanced_json_payload(text):
    start = text.find('{')
    if start < 0:
        return ''

    stack = []
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char in '{[':
            stack.append(char)
        elif char in '}]':
            if not stack:
                return ''
            opener = stack.pop()
            if (opener == '{' and char != '}') or (opener == '[' and char != ']'):
                return ''
            if not stack:
                return text[start:index + 1].strip()

    return ''


def repair_json_like_text(text):
    repaired = strip_json_comments(str(text or '').strip())
    repaired = re.sub(r'\bTrue\b', 'true', repaired)
    repaired = re.sub(r'\bFalse\b', 'false', repaired)
    repaired = re.sub(r'\bNone\b', 'null', repaired)
    repaired = quote_unquoted_json_keys(repaired)
    repaired = re.sub(r',(\s*[}\]])', r'\1', repaired)

    previous = None
    while previous != repaired:
        previous = repaired
        repaired = re.sub(r'(?<=[}\]])(\s*\n\s*)(?=[{\[])', r',\1', repaired)
        repaired = re.sub(r'(?<=[}\]"0-9])(\s*\n\s*)(?="[^"\n]+"\s*:)', r',\1', repaired)
        repaired = re.sub(r'(?<=\btrue)(\s*\n\s*)(?="[^"\n]+"\s*:)', r',\1', repaired)
        repaired = re.sub(r'(?<=\bfalse)(\s*\n\s*)(?="[^"\n]+"\s*:)', r',\1', repaired)
        repaired = re.sub(r'(?<=\bnull)(\s*\n\s*)(?="[^"\n]+"\s*:)', r',\1', repaired)
        repaired = re.sub(r',(\s*[}\]])', r'\1', repaired)

    return repaired


def repair_truncated_json_text(text):
    text = str(text or '').strip()
    if not text:
        return text

    result = []
    stack = []
    in_string = False
    escaped = False
    index = 0
    while index < len(text):
        char = text[index]

        if in_string:
            if escaped:
                result.append(char)
                escaped = False
                index += 1
                continue

            if char == '\\':
                result.append(char)
                escaped = True
                index += 1
                continue

            if char == '"':
                result.append(char)
                in_string = False
                index += 1
                continue

            if char in '\r\n':
                newline = '\r\n' if char == '\r' and index + 1 < len(text) and text[index + 1] == '\n' else char
                lookahead_index = index + len(newline)
                lookahead = text[lookahead_index:]
                if re.match(r'\s*"[^"\r\n]+"\s*:', lookahead):
                    result.append('"')
                    result.append(newline)
                    in_string = False
                else:
                    result.append('\\n')
                index += len(newline)
                continue

            result.append(char)
            index += 1
            continue

        if char == '"':
            result.append(char)
            in_string = True
            index += 1
            continue

        if char in '{[':
            stack.append(char)
            result.append(char)
            index += 1
            continue

        if char in '}]':
            if stack:
                opener = stack[-1]
                if (opener == '{' and char == '}') or (opener == '[' and char == ']'):
                    stack.pop()
            result.append(char)
            index += 1
            continue

        result.append(char)
        index += 1

    if escaped:
        result.append('\\')
    if in_string:
        result.append('"')

    repaired = ''.join(result).rstrip()
    repaired = remove_trailing_incomplete_json_fragment(repaired)
    while stack:
        opener = stack.pop()
        repaired += '}' if opener == '{' else ']'
    repaired = re.sub(r',(\s*[}\]])', r'\1', repaired)
    return repaired


def remove_trailing_incomplete_json_fragment(text):
    previous = None
    repaired = text.rstrip()
    while previous != repaired:
        previous = repaired
        repaired = re.sub(r',\s*$', '', repaired)
        repaired = re.sub(r'("[^"\r\n]*"\s*:\s*)$', '', repaired)
        repaired = re.sub(r'([{\[,]\s*)"[^"\r\n]*"\s*:\s*$', r'\1', repaired)
        repaired = re.sub(r'([{\[,]\s*)"[^"\r\n]*"\s*$', r'\1', repaired)
    return repaired.rstrip()


def quote_unquoted_json_keys(text):
    result = []
    in_string = False
    escaped = False
    index = 0
    while index < len(text):
        char = text[index]
        if in_string:
            result.append(char)
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue

        if char == '"':
            in_string = True
            result.append(char)
            index += 1
            continue

        if char in '{,':
            result.append(char)
            index += 1
            whitespace_start = index
            while index < len(text) and text[index].isspace():
                index += 1
            result.append(text[whitespace_start:index])

            key_start = index
            if index < len(text) and (text[index].isalpha() or text[index] == '_'):
                index += 1
                while index < len(text) and (text[index].isalnum() or text[index] in {'_', '-'}):
                    index += 1
                key = text[key_start:index]
                suffix_start = index
                while index < len(text) and text[index].isspace():
                    index += 1
                if index < len(text) and text[index] == ':':
                    result.append(f'"{key}"')
                    result.append(text[suffix_start:index])
                    continue
                result.append(text[key_start:index])
                continue
            continue

        result.append(char)
        index += 1

    return ''.join(result)


def strip_json_comments(text):
    result = []
    in_string = False
    escaped = False
    index = 0
    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ''

        if in_string:
            result.append(char)
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue

        if char == '"':
            in_string = True
            result.append(char)
            index += 1
            continue

        if char == '/' and next_char == '/':
            index += 2
            while index < len(text) and text[index] not in '\r\n':
                index += 1
            continue

        if char == '/' and next_char == '*':
            index += 2
            while index + 1 < len(text) and not (text[index] == '*' and text[index + 1] == '/'):
                index += 1
            index += 2
            continue

        result.append(char)
        index += 1

    return ''.join(result)


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
    group_path = normalize_group_path(element.get('group_path') or [])

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
    for line in lines:
        case_name, inline_body = parse_case_heading_line(line)
        if case_name:
            if current_name or current_lines:
                cases.append((current_name or f'AI生成用例{len(cases) + 1}', '\n'.join(current_lines)))
            current_name = case_name
            current_lines = [inline_body] if inline_body else []
        else:
            current_lines.append(line)
    if current_name or current_lines:
        cases.append((current_name or guess_case_name(lines), '\n'.join(current_lines)))
    return cases[:50]


def parse_case_heading_line(line):
    text = str(line or '').strip()
    if not text:
        return '', ''
    match = re.match(
        r'^(?:用例|测试用例|case|场景|标题|功能)[:：\s]+(?P<name>.+?)(?:\s*(?:步骤|步骤描述)[:：]\s*(?P<body>.+))?$',
        text,
        re.I | re.S,
    )
    if not match:
        return '', ''
    return match.group('name').strip(), str(match.group('body') or '').strip()


def extract_step_body_text(text):
    source = str(text or '').strip()
    if not source:
        return ''
    match = re.search(r'(?:步骤|步骤描述)[:：]\s*(.+)$', source, re.I | re.S)
    if match:
        return match.group(1).strip()
    return source


def extract_natural_language_steps(text):
    body = extract_step_body_text(text)
    if not body:
        return []

    numbered_matches = list(re.finditer(r'(?:(?<=^)|(?<=[\s,，;；]))(?P<index>\d+)\s*[.、]\s*', body))
    if numbered_matches:
        steps = []
        for index, match in enumerate(numbered_matches):
            start = match.end()
            end = numbered_matches[index + 1].start() if index + 1 < len(numbered_matches) else len(body)
            step_text = body[start:end].strip(' \t\r\n,，;；')
            if step_text:
                steps.append(step_text)
        if steps:
            return steps

    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if len(lines) > 1:
        return [re.sub(r'^(?:[-*]|\d+\s*[.、])\s*', '', line).strip() for line in lines if line.strip()]

    return [body] if body else []


def guess_case_name(lines):
    first = lines[0] if lines else 'AI生成用例'
    first = re.sub(r'^[-*\d.、\s]+', '', first)
    return first[:80] or 'AI生成用例'


def heuristic_case(name, body, index):
    steps = []
    natural_steps = extract_natural_language_steps(body)
    candidate_lines = natural_steps or [item.strip() for item in re.split(r'[\n；;]', body) if item.strip()]
    for line in candidate_lines:
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


def enforce_generation_business_rules(project, manifest, source_text):
    warnings = []
    cases = manifest.get('test_cases') or []
    if not cases:
        return warnings

    element_lookup = build_project_element_lookup(project)
    source_cases = split_source_into_cases(source_text)
    original_case_count = len(cases)

    if len(source_cases) > len(cases):
        for source_index in range(len(cases), len(source_cases)):
            source_case_name, source_case_body = source_cases[source_index]
            cases.append(normalize_case(
                heuristic_case(source_case_name, source_case_body, source_index + 1),
                source_index + 1,
            ))
        warnings.append(
            f'源文本共解析出 {len(source_cases)} 条用例，生成结果仅返回 {original_case_count} 条，'
            f'已按原始用例补齐剩余 {len(source_cases) - original_case_count} 条'
        )

    for case_index, case in enumerate(cases, start=1):
        case_source_text = build_case_source_text(
            case,
            source_text,
            len(cases),
            source_cases=source_cases,
            case_index=case_index,
        )
        intents = extract_data_element_creation_intents(case_source_text)
        structured_request = parse_structured_generation_request(case_source_text)
        explicit_search_verify = has_explicit_search_verification_requirement(structured_request)
        rebuilt_case = False

        if explicit_search_verify:
            warnings.append(
                f'用例 {case_index} 检测到显式搜索验证要求，保留 AI/Skill 生成的验证步骤，不使用硬编码验证模板'
            )

        if should_rebuild_case_from_request(structured_request):
            rebuilt_steps = build_structured_case_steps(
                structured_request,
                element_lookup,
                case.get('steps') or [],
            )
            if rebuilt_steps:
                case['steps'] = rebuilt_steps
                case_name = structured_request.get('case_name')
                if case_name:
                    case['name'] = case_name
                summary = structured_request.get('summary')
                if summary:
                    case['description'] = summary
                rebuilt_case = True
                warnings.append(
                    f'用例 {case_index} 已按自然语言步骤重建关键流程，共生成 {len(rebuilt_steps)} 步，覆盖登录/管理模式/数据要素创建等关键事务块'
                )

        if intents and not rebuilt_case:
            for intent_index, intent in enumerate(intents):
                added_steps = ensure_data_element_creation_flow(
                    case,
                    intent,
                    element_lookup,
                    include_navigation=intent_index == 0,
                    force_new_flow=intent_index > 0,
                )
                if added_steps:
                    warnings.append(
                        f'用例 {case_index} 已按业务模板补齐数据要素创建流程缺失步骤: {intent["data_definition"]}，新增 {added_steps} 步'
                    )

        removed_placeholder_steps = prune_placeholder_steps(case)
        if removed_placeholder_steps:
            warnings.append(f'用例 {case_index} 已移除 {removed_placeholder_steps} 个无元素占位步骤')

        repaired_wait_for = repair_wait_for_without_element(case)
        if repaired_wait_for:
            warnings.append(f'用例 {case_index} 已将 {repaired_wait_for} 个缺少元素的 waitFor 自动调整为 wait')

        inserted_waits = enforce_wait_after_sensitive_actions(case, element_lookup)
        if inserted_waits:
            warnings.append(f'用例 {case_index} 已按等待规则自动插入 {inserted_waits} 个等待步骤')

    renumber_manifest_steps(manifest)
    return warnings


def extract_data_element_creation_intents(source_text):
    text = str(source_text or '')
    if '数据要素' not in text or not re.search(r'(新建|创建)', text):
        return []

    patterns = [
        r'数据定义\s*(?:为|是|=|:|：)\s*(?P<name>[^，,。；;\n\r]+)',
        r'(?:新建|创建)[^。\n\r]{0,80}?数据定义\s*(?:为|是|=|:|：)\s*(?P<name>[^，,。；;\n\r]+)',
        r'(?:新建|创建)\s*数据定义\s*(?:为|是|=|:|：)?\s*(?P<name>[^，,。；;\n\r]+?)\s*(?:的)?数据要素',
        r'(?:新建|创建)\s*(?P<name>[^，,。；;\n\r]*?)\s*(?:类型)?数据要素',
    ]
    intents = []
    seen = set()
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.I):
            raw_name = match.group('name') or ''
            names = split_data_definition_names(clean_data_definition_name(raw_name))
            for name in names:
                if is_generic_data_definition_name(name):
                    continue
                key = normalize_match_text(name)
                if key and key not in seen:
                    seen.add(key)
                    intents.append({
                        'data_definition': name,
                        'element_type': infer_data_element_type(name),
                    })
    if not intents and re.search(r'(?:新建|创建)\s*数据要素', text):
        intents.append({
            'data_definition': '数据定义',
            'element_type': 'data',
        })
    return intents


def clean_data_definition_name(value):
    value = str(value or '').strip()
    previous = None
    while previous != value:
        previous = value
        value = re.sub(r'^(?:数据定义|定义|名称)\s*', '', value, flags=re.I)
        value = re.sub(r'^(?:为|是|等于|使用)\s*', '', value, flags=re.I)
        value = re.sub(r'^(?:类型为|类型是)\s*', '', value, flags=re.I)
        value = re.sub(r'\s+\d+\s*[.、].*$', '', value)
        value = re.sub(r'[（(]\s*(?:预期结果|测试数据|备注)\s*[：:][^）)]*[）)]\s*$', '', value, flags=re.I)
        value = re.sub(r'(?:预期结果|测试数据|备注)\s*[：:]\s*.*$', '', value, flags=re.I)
    value = re.sub(r'(?:类型|的|的数据要素|的数据定义|数据定义)$', '', value, flags=re.I).strip()
    return value.strip(' （）()：:=，,。；;')


def split_data_definition_names(value):
    cleaned = clean_data_definition_name(value)
    if not cleaned:
        return []
    parts = re.split(r'\s*(?:、|,|，|/|;|；|\band\b|和|及)\s*', cleaned, flags=re.I)
    return [part.strip() for part in parts if part.strip()]


def infer_data_element_type(data_definition):
    lowered = str(data_definition or '').lower()
    known_types = [
        'decimal', 'integer', 'image', 'currency', 'text', 'string', 'date', 'datetime',
        'boolean', 'bool', 'number', 'file', 'double', 'float',
    ]
    for item in known_types:
        if item in lowered:
            return item
    return str(data_definition or '').strip() or 'data'


def build_data_element_label_value(data_definition, element_type=''):
    candidates = [element_type, clean_data_definition_name(data_definition)]
    for candidate in candidates:
        normalized = re.sub(r'^(?:sys[\s_-]*)', '', str(candidate or '').strip(), flags=re.I)
        normalized = re.sub(r'[^a-zA-Z0-9]+', '_', normalized).strip('_').lower()
        if normalized:
            if normalized[0].isdigit():
                normalized = f'data_{normalized}'
            return f'{normalized}_${{random_string(6, letters, 1)}}'
    return 'data_${random_string(6, letters, 1)}'


def is_generic_data_definition_name(value):
    normalized = normalize_match_text(value)
    return normalized in {'', '数据定义', '定义', '类型', '数据', '数据要素'}


def build_project_element_lookup(project):
    try:
        elements = Element.objects.filter(project=project).select_related('locator_strategy')
    except Exception:
        return {}

    lookup = {}
    for element in elements:
        keys = {
            normalize_match_text(element.name),
            normalize_match_text(element.description),
        }
        for key in keys:
            if key:
                lookup.setdefault(key, element)
    return lookup


def ensure_data_element_creation_flow(case, intent, element_lookup, include_navigation=True, force_new_flow=False):
    existing_steps = case.get('steps') if isinstance(case.get('steps'), list) else []
    case['steps'] = existing_steps

    template = build_data_element_creation_template(intent, element_lookup, include_navigation)
    missing_steps = []

    if force_new_flow:
        missing_steps = template
    else:
        for phase_key, step in template:
            if not has_data_element_phase(existing_steps, phase_key, intent):
                missing_steps.append((phase_key, step))

    if not missing_steps:
        return 0

    insert_at = find_data_element_insert_index(existing_steps)
    for offset, (_, step) in enumerate(missing_steps, start=1):
        existing_steps.insert(insert_at + offset, step)
    return len(missing_steps)


def build_data_element_creation_template(intent, element_lookup, include_navigation=True, include_wait_success=True):
    data_definition = intent.get('data_definition') or '数据定义'
    element_type = intent.get('element_type') or data_definition
    element_name_value = '${random_string(8, letters, 1)}'
    element_label_value = build_data_element_label_value(data_definition, element_type)

    steps = []
    if include_navigation:
        steps.extend([
            ('nav_structure', make_template_step(
                'click',
                '点击进入数据结构设置菜单',
                element_lookup,
                ['进入数据结构设置', '数据结构设置'],
            )),
            ('nav_element', make_template_step(
                'click',
                '点击进入数据要素子菜单',
                element_lookup,
                ['进入数据要素', '数据要素'],
            )),
        ])

    steps.extend([
        ('open_create', make_template_step(
            'click',
            '点击新建按钮，打开新建数据要素弹窗',
            element_lookup,
            ['数据要素新建按钮'],
        )),
        ('wait_create_dialog', make_template_step(
            'waitFor',
            '等待新建数据要素弹窗中的名称输入框出现',
            element_lookup,
            ['数据要素名称输入框', '数据要素名称'],
        )),
        ('fill_name', make_template_step(
            'fill',
            '在数据要素名称输入框中填写要素名称，使用8位随机字符串',
            element_lookup,
            ['数据要素名称输入框', '数据要素名称'],
            input_value=element_name_value,
            save_as='data_el_name',
        )),
        ('open_definition_dialog', make_template_step(
            'click',
            '点击选择数据定义控件，打开选择数据定义弹框',
            element_lookup,
            ['新建数据要素-选择数据定义icon', '选择数据定义控件', '选择数据定义'],
        )),
        ('wait_definition_dialog', make_template_step(
            'waitFor',
            '等待选择数据定义弹框中的搜索框出现',
            element_lookup,
            ['新建要素-选择数据定义搜索框', '选择数据定义搜索框'],
        )),
        ('search_definition', make_template_step(
            'fillAndEnter',
            f'在选择数据定义弹框的搜索框中输入{data_definition}，触发搜索',
            element_lookup,
            ['新建要素-选择数据定义搜索框', '选择数据定义搜索框'],
            input_value=data_definition,
        )),
        ('wait_search', make_template_step(
            'wait',
            '等待选择数据定义搜索结果加载完成',
            element_lookup,
            wait_time=1000,
        )),
        ('select_definition', make_template_step(
            'click',
            f'点击选中{data_definition}数据定义选项',
            element_lookup,
            ['新建数据要素-选择数据定义-选择数据', '选择数据定义-选择数据', data_definition],
        )),
        ('confirm_definition', make_template_step(
            'click',
            '点击选择数据定义弹框中的确定按钮',
            element_lookup,
            ['新建数据要素-选择数据定义弹窗-确定按钮', '选择数据定义弹窗-确定按钮', '选择数据定义确定按钮'],
        )),
        ('wait_definition_confirm', make_template_step(
            'wait',
            '等待选择数据定义弹框关闭',
            element_lookup,
            wait_time=1000,
        )),
        ('fill_label', make_template_step(
            'fill',
            '在要素标签输入框中填写标签名称',
            element_lookup,
            ['新建数据要素-要素标签输入框', '要素标签输入框', '要素标签'],
            input_value=element_label_value,
        )),
        ('submit_create', make_template_step(
            'click',
            '点击新建数据要素弹窗确定按钮提交新建',
            element_lookup,
            ['新建数据要素-确定按钮', '新建数据要素弹窗-确定按钮', '数据要素确定按钮'],
        )),
    ])
    if include_wait_success:
        steps.append((
            'wait_success',
            make_template_step(
                'waitFor',
                '等待操作成功提示出现',
                element_lookup,
                ['操作成功toast', '操作成功提示', '操作成功'],
            )
        ))
    return steps


def make_template_step(action_type, description, element_lookup, aliases=None, input_value='', wait_time=1000,
                       assert_type='', assert_value='', save_as=''):
    aliases = aliases or []
    element = None
    if action_type in ELEMENT_ACTION_TYPES:
        element = find_manifest_element(element_lookup, aliases, action_type)

    return normalize_step({
        'action_type': action_type,
        'description': description,
        'input_value': input_value,
        'wait_time': wait_time,
        'assert_type': assert_type,
        'assert_value': assert_value,
        'save_as': save_as,
        'element': element,
    }, 1)


def find_manifest_element(element_lookup, aliases, action_type):
    for alias in aliases:
        key = normalize_match_text(alias)
        if key and key in element_lookup:
            return element_model_to_manifest(element_lookup[key])

    best_match = None
    best_score = None
    for key, element in element_lookup.items():
        for alias in aliases:
            normalized_alias = normalize_match_text(alias)
            if not normalized_alias or normalized_alias not in key:
                continue
            is_close_boundary_match = (
                key == normalized_alias
                or key.startswith(normalized_alias)
                or key.endswith(normalized_alias)
                or normalized_alias.startswith(key)
                or normalized_alias.endswith(key)
            )
            if not is_close_boundary_match:
                continue
            score = (
                int(key == normalized_alias) * 1000,
                int(key.startswith(normalized_alias) or key.endswith(normalized_alias)) * 200,
                -abs(len(key) - len(normalized_alias)),
            )
            if best_score is None or score > best_score:
                best_score = score
                best_match = element
    if best_match:
        return element_model_to_manifest(best_match)

    fallback_name = str(aliases[0] if aliases else '目标元素')
    return fallback_manifest_element(fallback_name, action_type)


def element_model_to_manifest(element):
    return {
        'name': element.name,
        'description': element.description or '',
        'element_type': element.element_type or 'BUTTON',
        'page': element.page or '',
        'component_name': element.component_name or '',
        'group_path': [],
        'locator_strategy': element.locator_strategy.name if element.locator_strategy else 'XPath',
        'locator_value': element.locator_value or element.name,
        'backup_locators': element.backup_locators if isinstance(element.backup_locators, list) else [],
        'wait_timeout': element.wait_timeout or 5,
        'is_unique': element.is_unique,
        'is_visible': element.is_visible,
        'is_enabled': element.is_enabled,
        'force_action': element.force_action,
    }


def fallback_manifest_element(name, action_type):
    element_type = infer_element_type(action_type, name)
    if '操作成功' in name:
        element_type = 'MODAL'
        locator_value = "//*[contains(normalize-space(.),'操作成功')]"
    elif action_type in {'fill', 'fillAndEnter'}:
        locator_value = f"//*[@placeholder='{escape_xpath_text(name)}' or contains(normalize-space(.),'{escape_xpath_text(name)}')]"
    else:
        locator_value = f"//*[contains(normalize-space(.),'{escape_xpath_text(name)}')]"
    return {
        'name': name[:200],
        'description': '',
        'element_type': element_type,
        'page': '',
        'component_name': '',
        'group_path': [],
        'locator_strategy': 'XPath',
        'locator_value': locator_value,
        'backup_locators': [],
        'wait_timeout': 5,
        'is_unique': False,
        'is_visible': True,
        'is_enabled': True,
        'force_action': False,
    }


def has_data_element_phase(steps, phase_key, intent):
    phase_keywords = {
        'nav_structure': ['数据结构设置'],
        'nav_element': ['数据要素子菜单', '进入数据要素'],
        'open_create': ['新建按钮', '新建数据要素弹窗'],
        'wait_create_dialog': ['新建数据要素弹窗', '名称输入框'],
        'fill_name': ['数据要素名称', '要素名称'],
        'open_definition_dialog': ['选择数据定义控件', '打开选择数据定义'],
        'wait_definition_dialog': ['选择数据定义弹框', '搜索框'],
        'search_definition': ['选择数据定义弹框', '搜索框', intent.get('data_definition', '')],
        'wait_search': ['搜索结果', '加载完成'],
        'select_definition': ['选中', '数据定义选项'],
        'confirm_definition': ['选择数据定义', '确定按钮'],
        'wait_definition_confirm': ['选择数据定义弹框关闭'],
        'fill_label': ['要素标签'],
        'submit_create': ['新建数据要素', '提交新建'],
        'wait_success': ['操作成功'],
        'search_created_element': ['搜索数据要素', '${data_el_name}'],
        'wait_created_element_result': ['数据要素搜索结果', '加载完成'],
        'assert_created_element': ['创建成功的数据要素', '${data_el_name}'],
    }
    required_keywords = [item for item in phase_keywords.get(phase_key, []) if item]
    for step in steps:
        text = step_search_text(step)
        if phase_key == 'wait_search':
            if step.get('action_type') == 'wait' and any(keyword in text for keyword in ['搜索', '加载', '等待']):
                return True
        elif phase_key == 'wait_definition_confirm':
            if step.get('action_type') == 'wait' and any(keyword in text for keyword in ['弹框关闭', '关闭选择数据定义', '确定后等待']):
                return True
        elif required_keywords and all(keyword in text for keyword in required_keywords):
            return True
    return False


def step_search_text(step):
    element = step.get('element') if isinstance(step, dict) else None
    parts = [
        str(step.get('description') or ''),
        str(step.get('action_type') or ''),
        str(step.get('input_value') or ''),
        str(step.get('assert_value') or ''),
    ]
    if isinstance(element, dict):
        parts.extend([
            str(element.get('name') or ''),
            str(element.get('page') or ''),
            str(element.get('locator_value') or ''),
        ])
    return '\n'.join(parts)


def find_data_element_insert_index(steps):
    keywords = ['数据要素', '数据定义', '要素标签', '操作成功', '新建按钮', '搜索结果']
    for index in range(len(steps) - 1, -1, -1):
        text = step_search_text(steps[index])
        if any(keyword in text for keyword in keywords):
            return index
    return len(steps) - 1


def renumber_manifest_steps(manifest):
    for case in manifest.get('test_cases') or []:
        for index, step in enumerate(case.get('steps') or [], start=1):
            step['step_number'] = index


def normalize_match_text(value):
    return re.sub(r'\s+', '', str(value or '').strip().lower())


def build_case_source_text(case, source_text, case_count, source_cases=None, case_index=None):
    if source_cases and case_index and 1 <= case_index <= len(source_cases):
        source_case_name, source_case_body = source_cases[case_index - 1]
        parts = []
        if str(source_case_name or '').strip():
            parts.append(f'用例：{str(source_case_name).strip()}')
        if str(source_case_body or '').strip():
            parts.append(str(source_case_body).strip())
        resolved = '\n'.join(parts).strip()
        if resolved:
            return resolved

    if case_count <= 1:
        return str(source_text or '')
    parts = []
    case_name = str(case.get('name') or '').strip()
    description = str(case.get('description') or '').strip()
    if case_name:
        parts.append(f'用例：{case_name}')
    if description:
        parts.append(description)
    return '\n'.join(parts).strip() or str(source_text or '')


def parse_structured_generation_request(source_text):
    text = str(source_text or '').strip()
    if not text:
        return {'case_name': '', 'summary': '', 'steps': [], 'data_intents': [], 'credentials': {}}

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    first_line = lines[0] if lines else text
    case_name, inline_body = parse_case_heading_line(first_line)
    step_text = '\n'.join(lines[1:]).strip()
    if inline_body:
        step_text = '\n'.join([inline_body, step_text]).strip()
    if not step_text:
        step_text = text if not case_name else inline_body

    natural_steps = extract_natural_language_steps(step_text or text)
    data_intents = extract_data_element_creation_intents(text)
    credentials = extract_login_credentials(text)
    structured_steps = []
    default_data_intent = data_intents[0] if data_intents else {
        'data_definition': '数据定义',
        'element_type': 'data',
    }
    for step_text_item in natural_steps:
        structured_steps.append(classify_structured_generation_step(step_text_item, default_data_intent))

    summary = '，'.join(step.get('raw') for step in structured_steps if step.get('raw'))
    return {
        'case_name': case_name,
        'summary': summary,
        'steps': structured_steps,
        'data_intents': data_intents,
        'credentials': credentials,
    }


def extract_login_credentials(source_text):
    text = str(source_text or '')
    credentials = {}
    patterns = {
        'username': [
            r'(?:账号|帐号|用户名)\s*(?:为|是|=|:|：)\s*[\'"`“”]?([^\s，,。；;]+)',
            r'登录(?:账号|帐号|用户名)\s*[\'"`“”]?([^\s，,。；;]+)',
        ],
        'password': [
            r'密码\s*(?:为|是|=|:|：)\s*[\'"`“”]?([^\s，,。；;]+)',
            r'登录密码\s*[\'"`“”]?([^\s，,。；;]+)',
        ],
    }
    for field, regex_list in patterns.items():
        for pattern in regex_list:
            match = re.search(pattern, text, flags=re.I)
            if not match:
                continue
            value = str(match.group(1) or '').strip().strip('\'"`“”')
            if value:
                credentials[field] = value
                break
    return credentials


def classify_structured_generation_step(step_text, default_data_intent):
    raw = str(step_text or '').strip()
    normalized = normalize_match_text(raw)
    step_kind = 'generic'
    transaction_name = raw[:30] or '事务块'

    if any(keyword in normalized for keyword in ['登录', '登陆']):
        step_kind = 'login'
        transaction_name = 'login'
    elif any(keyword in normalized for keyword in ['进入管理模式', '管理模式', '切换到管理模式', '进入管理']):
        step_kind = 'enter_admin_mode'
        transaction_name = '进入管理模式'
    elif '数据要素' in raw and any(keyword in normalized for keyword in ['新建', '创建', '新增']):
        step_kind = 'create_data_element'
        transaction_name = '创建要素'
    elif any(keyword in normalized for keyword in ['验证', '校验', '断言']) and any(
        keyword in normalized for keyword in ['成功', '要素', '数据要素', '新建']
    ):
        step_kind = 'verify_create_success'
        transaction_name = '验证新建要素成功'

    step_data_intent = default_data_intent
    extracted_intents = extract_data_element_creation_intents(raw)
    if extracted_intents:
        step_data_intent = extracted_intents[0]

    return {
        'raw': raw,
        'kind': step_kind,
        'transaction_name': transaction_name,
        'data_intent': step_data_intent,
    }


def has_explicit_search_verification_requirement(structured_request):
    for step in structured_request.get('steps') or []:
        if step.get('kind') != 'verify_create_success':
            continue
        normalized = normalize_match_text(step.get('raw'))
        if any(keyword in normalized for keyword in ['搜索', '查询', '查找']):
            return True
    return False


def should_rebuild_case_from_request(structured_request):
    steps = structured_request.get('steps') or []
    if not steps:
        return False
    recognized = [step for step in steps if step.get('kind') != 'generic']
    if not recognized:
        return False
    if any(step.get('kind') == 'create_data_element' for step in recognized):
        return True
    return len(recognized) >= 2


def build_structured_case_steps(structured_request, element_lookup, original_steps=None):
    steps = []
    structured_steps = structured_request.get('steps') or []
    credentials = structured_request.get('credentials') or {}
    has_verify_success = any(step.get('kind') == 'verify_create_success' for step in structured_steps)
    explicit_search_verify = has_explicit_search_verification_requirement(structured_request)

    for step in structured_steps:
        kind = step.get('kind')
        if kind == 'login':
            steps.extend(assign_transaction_to_steps(
                build_login_flow_steps(element_lookup, credentials),
                step.get('transaction_name') or 'login',
            ))
            continue
        if kind == 'enter_admin_mode':
            steps.extend(assign_transaction_to_steps(
                build_enter_admin_mode_steps(element_lookup),
                step.get('transaction_name') or '进入管理模式',
            ))
            continue
        if kind == 'create_data_element':
            template_steps = [
                template_step
                for _, template_step in build_data_element_creation_template(
                    step.get('data_intent') or {'data_definition': '数据定义', 'element_type': 'data'},
                    element_lookup,
                    include_navigation=True,
                    include_wait_success=not has_verify_success,
                )
            ]
            steps.extend(assign_transaction_to_steps(
                template_steps,
                step.get('transaction_name') or '创建要素',
            ))
            continue
        if kind == 'verify_create_success':
            steps.extend(assign_transaction_to_steps(
                resolve_verify_success_steps(
                    element_lookup,
                    original_steps=original_steps,
                    preserve_ai_verify_steps=explicit_search_verify,
                ),
                step.get('transaction_name') or '验证新建要素成功',
            ))
            continue

        steps.extend(assign_transaction_to_steps(
            build_generic_transaction_steps(step.get('raw', '')),
            step.get('transaction_name') or '事务块',
        ))

    return steps


def assign_transaction_to_steps(steps, transaction_name):
    resolved_steps = [normalize_step(dict(step), 1) for step in (steps or []) if isinstance(step, dict)]
    if not resolved_steps:
        return []
    transaction_id = f'tx-{uuid.uuid4().hex[:12]}'
    for step in resolved_steps:
        step['transaction_id'] = transaction_id
        step['transaction_name'] = transaction_name
    return resolved_steps


def build_login_flow_steps(element_lookup, credentials):
    username = credentials.get('username') or '${username}'
    password = credentials.get('password') or '${password}'
    return [
        make_template_step(
            'fill',
            '填写账号输入框',
            element_lookup,
            ['账号输入框', '用户名输入框', '账号'],
            input_value=username,
        ),
        make_template_step(
            'fill',
            '填写密码输入框',
            element_lookup,
            ['密码输入框', '登录密码输入框', '密码'],
            input_value=password,
        ),
        make_template_step(
            'click',
            '点击登录按钮',
            element_lookup,
            ['登录按钮', '登录'],
        ),
    ]


def build_enter_admin_mode_steps(element_lookup):
    return [
        make_template_step(
            'waitFor',
            '等待工作台logo出现',
            element_lookup,
            ['工作台logo', '工作台Logo', 'logo'],
            wait_time=20000,
        ),
        normalize_step({
            'action_type': 'wait',
            'description': '等待3秒',
            'wait_time': 3000,
        }, 1),
        make_template_step(
            'click',
            '点击工作台logo',
            element_lookup,
            ['工作台logo', '工作台Logo', 'logo'],
        ),
        normalize_step({
            'action_type': 'switchTab',
            'description': '切换到最新标签页',
            'input_value': '',
            'wait_time': 1000,
        }, 1),
        make_template_step(
            'waitFor',
            '等待进入管理模式按钮出现',
            element_lookup,
            ['进入管理模式', '管理模式按钮', '切换到管理模式'],
        ),
        make_template_step(
            'click',
            '点击进入管理模式',
            element_lookup,
            ['进入管理模式', '管理模式按钮', '切换到管理模式'],
        ),
    ]


def resolve_verify_success_steps(element_lookup, original_steps=None, preserve_ai_verify_steps=False):
    if preserve_ai_verify_steps:
        preserved_steps = extract_search_verify_steps_from_ai_output(original_steps)
        if preserved_steps:
            return preserved_steps
    return build_verify_success_steps_minimal(element_lookup)


def extract_search_verify_steps_from_ai_output(original_steps):
    normalized_steps = [
        normalize_step(dict(step), index)
        for index, step in enumerate(original_steps or [], start=1)
        if isinstance(step, dict)
    ]
    if not normalized_steps:
        return []

    included_indexes = set()
    for index, step in enumerate(normalized_steps):
        if not is_search_verify_anchor_step(step):
            continue
        included_indexes.add(index)
        for neighbor in (index - 1, index + 1):
            if 0 <= neighbor < len(normalized_steps) and is_search_verify_context_step(normalized_steps[neighbor]):
                included_indexes.add(neighbor)

    if not included_indexes:
        return []

    preserved_steps = []
    for index, step in enumerate(normalized_steps):
        if index not in included_indexes:
            continue
        preserved_step = dict(step)
        preserved_step['transaction_id'] = ''
        preserved_step['transaction_name'] = ''
        preserved_steps.append(preserved_step)
    return preserved_steps


def is_search_verify_anchor_step(step):
    haystack = collect_search_verify_step_text(step)
    if any(keyword in haystack for keyword in ['搜索', '查询', '查找', 'search', 'query', 'find']):
        return True
    return False


def is_search_verify_context_step(step):
    action_type = str(step.get('action_type') or '').strip()
    if action_type in {'wait', 'waitFor', 'assert'}:
        return True
    haystack = collect_search_verify_step_text(step)
    if '${data_el_name}' in haystack:
        return True
    if any(keyword in haystack for keyword in ['结果', '列表', '成功', 'toast', '提示', 'visible']):
        return True
    return False


def collect_search_verify_step_text(step):
    parts = [
        step.get('description'),
        step.get('input_value'),
        step.get('assert_value'),
        (step.get('element') or {}).get('name'),
        (step.get('element') or {}).get('locator_value'),
    ]
    return normalize_match_text(' '.join(str(part or '') for part in parts))


def build_verify_success_steps_minimal(element_lookup):
    return [
        make_template_step(
            'waitFor',
            '等待操作成功提示出现',
            element_lookup,
            ['操作成功toast', '操作成功提示', '操作成功'],
        ),
    ]


def build_generic_transaction_steps(step_text):
    text = str(step_text or '').strip()
    if not text:
        return []
    action_type = infer_action_type(text)
    element = None
    if action_type in ELEMENT_ACTION_TYPES:
        element_name = infer_element_name(text)
        element = normalize_element({
            'name': element_name,
            'element_type': infer_element_type(action_type, element_name),
            'locator_strategy': 'text' if action_type == 'click' else 'XPath',
            'locator_value': element_name if action_type == 'click' else (
                f"//*[contains(normalize-space(.),'{escape_xpath_text(element_name)}') or "
                f"@placeholder='{escape_xpath_text(element_name)}']"
            ),
        })
    return [normalize_step({
        'action_type': action_type,
        'description': text,
        'input_value': infer_input_value(text) if action_type in {'fill', 'fillAndEnter', 'switchTab'} else '',
        'wait_time': 3000 if action_type == 'wait' else 1000,
        'assert_type': 'textContains' if action_type == 'assert' else '',
        'assert_value': infer_assert_value(text) if action_type == 'assert' else '',
        'element': element,
    }, 1)]


def prune_placeholder_steps(case):
    steps = case.get('steps') if isinstance(case.get('steps'), list) else []
    kept_steps = []
    removed = 0
    for step in steps:
        action_type = str(step.get('action_type') or '').strip()
        description = str(step.get('description') or '').strip().lower()
        element = step.get('element')
        if action_type in ELEMENT_ACTION_TYPES and not element and description in {'', action_type.lower(), 'click'}:
            removed += 1
            continue
        kept_steps.append(step)
    case['steps'] = kept_steps
    return removed


def repair_wait_for_without_element(case):
    repaired = 0
    for step in case.get('steps') or []:
        if step.get('action_type') == 'waitFor' and not step.get('element'):
            step['action_type'] = 'wait'
            step['wait_time'] = normalize_int(step.get('wait_time'), 1000, 1000, 120000)
            step['element'] = None
            repaired += 1
    return repaired


def enforce_wait_after_sensitive_actions(case, element_lookup):
    steps = case.get('steps') if isinstance(case.get('steps'), list) else []
    inserted = 0
    index = 0
    while index < len(steps):
        step = steps[index]
        if not requires_followup_wait(step):
            index += 1
            continue

        next_step = steps[index + 1] if index + 1 < len(steps) else None
        if is_wait_step(next_step):
            index += 1
            continue

        wait_step = build_followup_wait_step(next_step, element_lookup)
        wait_step['transaction_id'] = str(step.get('transaction_id') or '').strip()
        wait_step['transaction_name'] = str(step.get('transaction_name') or '').strip()
        steps.insert(index + 1, wait_step)
        inserted += 1
        index += 2

    return inserted


def requires_followup_wait(step):
    if not isinstance(step, dict):
        return False
    if is_wait_step(step):
        return False

    text = normalize_match_text(step_search_text(step))
    action_type = step.get('action_type')
    if any(keyword in text for keyword in ['管理模式', '用户模式', '切换模式', '进入管理']):
        return True
    if any(keyword in text for keyword in ['搜索', '查询']):
        return True
    if any(keyword in text for keyword in ['提交', '保存', '确认提交']):
        return True
    if action_type == 'click' and any(keyword in text for keyword in ['确定', '确认']):
        return True
    if action_type == 'fillAndEnter' and any(keyword in text for keyword in ['搜索', '查询', '关键词']):
        return True
    return False


def is_wait_step(step):
    return isinstance(step, dict) and step.get('action_type') in {'wait', 'waitFor'}


def build_followup_wait_step(next_step, element_lookup):
    next_element = next_step.get('element') if isinstance(next_step, dict) else None
    if isinstance(next_element, dict) and next_element.get('locator_value'):
        return normalize_step({
            'action_type': 'waitFor',
            'description': f'等待{next_element.get("name") or "目标元素"}出现',
            'wait_time': 1000,
            'element': next_element,
        }, 1)

    success_element = find_manifest_element(
        element_lookup,
        ['操作成功toast', '操作成功提示', '操作成功'],
        'waitFor',
    )
    if isinstance(next_step, dict) and any(keyword in normalize_match_text(step_search_text(next_step)) for keyword in ['操作成功', '成功提示']):
        return normalize_step({
            'action_type': 'waitFor',
            'description': '等待操作成功提示出现',
            'wait_time': 1000,
            'element': success_element,
        }, 1)

    return normalize_step({
        'action_type': 'wait',
        'description': '等待操作完成',
        'wait_time': 1000,
    }, 1)


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
