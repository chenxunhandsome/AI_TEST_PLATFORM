"""Helpers for resolving user-requested UI element attributes."""

import json
import re


ATTRIBUTE_ALIASES = {
    'visible': 'visible',
    'isvisible': 'visible',
    'is_visible': 'visible',
    'displayed': 'visible',
    '可见': 'visible',
    '是否可见': 'visible',
    'clickable': 'clickable',
    'isclickable': 'clickable',
    'is_clickable': 'clickable',
    '可点击': 'clickable',
    '是否可点击': 'clickable',
    'enabled': 'enabled',
    'isenabled': 'enabled',
    'is_enabled': 'enabled',
    '可用': 'enabled',
    '是否可用': 'enabled',
    'disabled': 'disabled',
    'isdisabled': 'disabled',
    'is_disabled': 'disabled',
    '禁用': 'disabled',
    '是否禁用': 'disabled',
    'exists': 'exists',
    'exist': 'exists',
    'present': 'exists',
    '存在': 'exists',
    '是否存在': 'exists',
    'checked': 'checked',
    'ischecked': 'checked',
    'is_checked': 'checked',
    '选中': 'checked',
    '是否选中': 'checked',
    'selected': 'selected',
    'isselected': 'selected',
    'is_selected': 'selected',
    'readonly': 'readonly',
    'read_only': 'readonly',
    '只读': 'readonly',
    '是否只读': 'readonly',
    'text': 'text',
    'innertext': 'text',
    'inner_text': 'text',
    '文本': 'text',
    'value': 'value',
    '值': 'value',
    '输入值': 'value',
    'count': 'count',
    '数量': 'count',
    'tag': 'tagName',
    'tagname': 'tagName',
    'tag_name': 'tagName',
    '标签': 'tagName',
    'html': 'innerHTML',
    'innerhtml': 'innerHTML',
    'inner_html': 'innerHTML',
    'outerhtml': 'outerHTML',
    'outer_html': 'outerHTML',
    'textcontent': 'textContent',
    'text_content': 'textContent',
}


def parse_attribute_requests(raw_value):
    """Split the user's input into one or more requested attributes."""
    raw = str(raw_value or '').strip()
    if not raw:
        return []

    parts = [
        part.strip()
        for part in re.split(r'[,，\n\r;；]+', raw)
        if part and part.strip()
    ]
    return parts or [raw]


def normalize_attribute_name(name):
    """Map common human-friendly names to canonical attribute keys."""
    value = str(name or '').strip()
    key = re.sub(r'[\s\-]+', '_', value).lower()
    compact_key = key.replace('_', '')

    if key in ATTRIBUTE_ALIASES:
        return ATTRIBUTE_ALIASES[key]
    if compact_key in ATTRIBUTE_ALIASES:
        return ATTRIBUTE_ALIASES[compact_key]
    return value


def format_attribute_value(value):
    """Convert resolved values into stable strings for logs and variables."""
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if value is None:
        return ''
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def format_attribute_results(results):
    """Return a scalar for one attribute and a JSON object for multiple."""
    if not results:
        return ''

    if len(results) == 1:
        return format_attribute_value(next(iter(results.values())))

    return json.dumps(
        {name: format_attribute_value(value) for name, value in results.items()},
        ensure_ascii=False,
    )


def build_attribute_log_lines(results):
    return [
        f"  - {name}: {format_attribute_value(value)}"
        for name, value in results.items()
    ]
