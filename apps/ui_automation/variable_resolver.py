"""
UI鑷姩鍖栨祴璇曞彉閲忚В鏋愬櫒锛堝凡搴熷純锛岃浣跨敤 apps.core.variable_resolver锛夈€傛鏂囦欢淇濈暀鐢ㄤ簬鍚戝悗鍏煎銆?
"""
import json

from apps.core.variable_resolver import (
    VariableResolver,
    resolve_variables,
    set_runtime_variable,
    set_runtime_variables,
    get_runtime_variable,
    get_runtime_variables,
    clear_runtime_variables,
)


def resolve_locator_value(locator_value):
    """Resolve runtime variables inside a UI element locator value."""
    if not isinstance(locator_value, str):
        return locator_value
    if '${' not in locator_value:
        return locator_value
    return resolve_variables(locator_value)


def resolve_element_locator_payload(element_data):
    """Return a shallow-copied element payload with parameterized locator resolved."""
    if not isinstance(element_data, dict):
        return element_data

    resolved_data = dict(element_data)
    resolved_data['locator_value'] = resolve_locator_value(resolved_data.get('locator_value', ''))
    return resolved_data


def parse_scroll_action_payload(input_value):
    """Parse coordinate-based scroll settings from a step input value."""
    if not isinstance(input_value, str):
        return None

    raw_value = input_value.strip()
    if not raw_value or not raw_value.startswith('{'):
        return None

    try:
        payload = json.loads(raw_value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None

    if not isinstance(payload, dict) or payload.get('scroll_mode') != 'coordinates':
        return None

    direction = str(payload.get('scroll_direction') or 'vertical').strip().lower()
    if direction not in {'vertical', 'horizontal', 'up', 'down'}:
        direction = 'vertical'

    scroll_scope = str(payload.get('scroll_scope') or 'window').strip().lower()
    if scroll_scope not in {'window', 'element'}:
        scroll_scope = 'window'

    def normalize_int(value):
        if value in (None, ''):
            return None
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None

    normalized = {
        'scroll_mode': 'coordinates',
        'scroll_direction': direction,
        'scroll_scope': scroll_scope,
        'start_x': normalize_int(payload.get('start_x')),
        'start_y': normalize_int(payload.get('start_y')),
        'target_x': normalize_int(payload.get('target_x')),
        'target_y': normalize_int(payload.get('target_y')),
    }

    if direction == 'horizontal':
        if normalized['start_x'] is None or normalized['target_x'] is None:
            return None
        normalized['start_y'] = normalized['start_y'] or 0
        normalized['target_y'] = normalized['target_y'] if normalized['target_y'] is not None else normalized['start_y']
    else:
        if normalized['start_y'] is None or normalized['target_y'] is None:
            return None
        normalized['start_x'] = normalized['start_x'] or 0
        normalized['target_x'] = normalized['target_x'] if normalized['target_x'] is not None else normalized['start_x']

    return normalized


def parse_canvas_action_payload(input_value):
    """Parse coordinate-based canvas click/drag settings from a step input value."""
    if not isinstance(input_value, str):
        return None

    raw_value = input_value.strip()
    if not raw_value or not raw_value.startswith('{'):
        return None

    try:
        payload = json.loads(raw_value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None

    if not isinstance(payload, dict) or payload.get('mode') != 'canvas':
        return None

    action = str(payload.get('action') or '').strip()
    if action not in {'click', 'drag'}:
        return None

    def normalize_int(value, default=None):
        if value in (None, ''):
            return default
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default

    def normalize_bool(value, default=False):
        if isinstance(value, bool):
            return value
        if value in (None, ''):
            return default
        return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}

    frame_selector = str(payload.get('frame_selector') or '').strip() or '#plt-workflow-iframe'
    normalized = {
        'mode': 'canvas',
        'action': action,
        'page_index': normalize_int(payload.get('page_index'), payload.get('active_page_index')),
        'active_page_index': normalize_int(payload.get('active_page_index'), payload.get('page_index')),
        'lock_page_index': normalize_bool(payload.get('lock_page_index'), False),
        'frame_selector': frame_selector,
        'frame_url': str(payload.get('frame_url') or '').strip(),
        'frame_url_keyword': str(payload.get('frame_url_keyword') or '').strip(),
        'hold_ms': max(normalize_int(payload.get('hold_ms'), 300) or 300, 0),
        'steps': max(normalize_int(payload.get('steps'), 30) or 30, 1),
    }

    if action == 'click':
        x = normalize_int(payload.get('x'))
        y = normalize_int(payload.get('y'))
        if x is None or y is None:
            return None
        normalized.update({'x': x, 'y': y})
        return normalized

    start = payload.get('start') if isinstance(payload.get('start'), dict) else {}
    target = payload.get('target') if isinstance(payload.get('target'), dict) else {}
    start_x = normalize_int(start.get('x'))
    start_y = normalize_int(start.get('y'))
    target_x = normalize_int(target.get('x'))
    target_y = normalize_int(target.get('y'))
    if None in {start_x, start_y, target_x, target_y}:
        return None

    normalized.update({
        'start': {'x': start_x, 'y': start_y},
        'target': {'x': target_x, 'y': target_y},
    })
    return normalized

__all__ = [
    'VariableResolver',
    'resolve_variables',
    'resolve_locator_value',
    'resolve_element_locator_payload',
    'parse_scroll_action_payload',
    'parse_canvas_action_payload',
    'set_runtime_variable',
    'set_runtime_variables',
    'get_runtime_variable',
    'get_runtime_variables',
    'clear_runtime_variables',
]
