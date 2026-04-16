import re

from .variable_resolver import clear_runtime_variables, set_runtime_variables


GLOBAL_VARIABLE_NAME_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


def normalize_project_global_variables(global_variables, strict=False):
    if not global_variables:
        return []

    if not isinstance(global_variables, list):
        if strict:
            raise ValueError('全局变量必须是列表格式')
        return []

    normalized = []
    seen_names = set()

    for index, raw_item in enumerate(global_variables, start=1):
        if not isinstance(raw_item, dict):
            if strict:
                raise ValueError(f'第 {index} 个全局变量格式不正确')
            continue

        name = str(raw_item.get('name', '') or '').strip()
        if not name:
            if strict:
                raise ValueError(f'第 {index} 个全局变量名称不能为空')
            continue

        if not GLOBAL_VARIABLE_NAME_RE.match(name):
            if strict:
                raise ValueError(f'全局变量名称不合法: {name}')
            continue

        if name in seen_names:
            if strict:
                raise ValueError(f'全局变量名称重复: {name}')
            continue

        seen_names.add(name)
        normalized.append({
            'name': name,
            'value': '' if raw_item.get('value') is None else str(raw_item.get('value')),
            'description': str(raw_item.get('description', '') or '').strip()
        })

    return normalized


def build_project_runtime_variables(project=None, global_variables=None):
    if project is not None:
        global_variables = getattr(project, 'global_variables', [])

    normalized = normalize_project_global_variables(global_variables, strict=False)
    return {item['name']: item.get('value', '') for item in normalized}


def initialize_project_runtime_variables(project=None, global_variables=None):
    clear_runtime_variables()
    runtime_variables = build_project_runtime_variables(project=project, global_variables=global_variables)
    if runtime_variables:
        set_runtime_variables(runtime_variables)
    return runtime_variables
