import json
from datetime import timedelta

from django.utils import timezone


INPUT_ACTIONS = {'fill', 'fillAndEnter', 'switchTab'}
CLICK_ACTIONS = {'click', 'doubleClick', 'double_click', 'canvasClick'}


def parse_execution_logs(logs):
    if not logs:
        return []
    if isinstance(logs, list):
        return logs
    if isinstance(logs, str):
        try:
            parsed = json.loads(logs)
        except (TypeError, ValueError):
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def _get_attr_or_key(item, key, default=None):
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _normalize_element(element_data):
    if not isinstance(element_data, dict) or not element_data:
        return None
    return {
        'id': element_data.get('id'),
        'name': element_data.get('name') or element_data.get('locator_value') or '',
        'locator_strategy': element_data.get('locator_strategy') or element_data.get('strategy') or '',
        'locator_value': element_data.get('locator_value') or element_data.get('value') or '',
        'element_type': element_data.get('element_type') or element_data.get('type') or '',
        'page': element_data.get('page') or '',
    }


def _normalize_source(source):
    if not source:
        return {}

    step = _get_attr_or_key(source, 'step')
    element_data = (
        _get_attr_or_key(source, 'element_data')
        or _get_attr_or_key(source, 'element')
    )

    return {
        'step_id': (
            _get_attr_or_key(source, 'step_id')
            or _get_attr_or_key(source, 'id')
            or _get_attr_or_key(step, 'id')
        ),
        'step_number': _get_attr_or_key(source, 'step_number') or _get_attr_or_key(step, 'step_number'),
        'action_type': _get_attr_or_key(source, 'action_type') or _get_attr_or_key(step, 'action_type') or '',
        'description': _get_attr_or_key(source, 'description') or _get_attr_or_key(step, 'description') or '',
        'input_value': _get_attr_or_key(source, 'input_value') or _get_attr_or_key(step, 'input_value') or '',
        'assert_value': _get_attr_or_key(source, 'assert_value') or _get_attr_or_key(step, 'assert_value') or '',
        'wait_time': _get_attr_or_key(source, 'wait_time') or _get_attr_or_key(step, 'wait_time'),
        'element': _normalize_element(element_data),
    }


def _sources_from_execution_plan(execution_plan):
    if not isinstance(execution_plan, dict):
        return []
    payload = execution_plan.get('payload') or {}
    if isinstance(payload, dict):
        steps = payload.get('steps') or []
        if isinstance(steps, list) and steps:
            return steps

    plan_items = execution_plan.get('plan_items') or []
    if not isinstance(plan_items, list):
        return []
    return [
        {
            'step_id': item.get('step_id'),
            'step_number': item.get('sequence') or item.get('source_step_number'),
            'action_type': item.get('action_type') or '',
            'description': item.get('description') or '',
        }
        for item in plan_items
        if isinstance(item, dict)
    ]


def _result_lookup(step_results):
    lookup = {}
    for index, result in enumerate(step_results or [], start=1):
        if not isinstance(result, dict):
            continue
        key = result.get('step_number') or index
        lookup[key] = result
    return lookup


def build_execution_step_details(step_results, step_sources=None, execution_plan=None):
    """Build stable, UI-friendly step details from execution logs and planned step data."""
    normalized_results = parse_execution_logs(step_results)
    sources = step_sources if step_sources is not None else _sources_from_execution_plan(execution_plan)
    sources = sources or []
    result_by_number = _result_lookup(normalized_results)

    total = max(len(sources), len(normalized_results))
    details = []
    for index in range(1, total + 1):
        source = _normalize_source(sources[index - 1] if index - 1 < len(sources) else {})
        result = result_by_number.get(index) or (
            normalized_results[index - 1]
            if index - 1 < len(normalized_results) and isinstance(normalized_results[index - 1], dict)
            else {}
        )

        action_type = result.get('action_type') or source.get('action_type') or ''
        description = result.get('description') or source.get('description') or ''
        element = result.get('element') if isinstance(result.get('element'), dict) else source.get('element')
        element = _normalize_element(element) if element else None
        input_value = result.get('input_value')
        if input_value in (None, ''):
            input_value = source.get('input_value') or ''
        assert_value = result.get('assert_value')
        if assert_value in (None, ''):
            assert_value = source.get('assert_value') or ''

        clicked_content = result.get('clicked_content') or result.get('clicked_text') or ''
        if action_type in CLICK_ACTIONS and not clicked_content:
            clicked_content = (element or {}).get('name') or description

        input_content = input_value if action_type in INPUT_ACTIONS else ''
        operation_content = clicked_content or input_content
        if not operation_content and action_type == 'assert':
            operation_content = assert_value

        details.append({
            'step_number': result.get('step_number') or source.get('step_number') or index,
            'step_id': result.get('step_id') or source.get('step_id'),
            'action_type': action_type,
            'description': description,
            'status': result.get('status') or ('passed' if result.get('success') else 'failed'),
            'success': result.get('success'),
            'message': result.get('message') or '',
            'error': result.get('error') or '',
            'log': result.get('log') or result.get('raw_log') or result.get('error') or '',
            'clicked_content': clicked_content,
            'input_content': input_content,
            'assert_content': assert_value if action_type == 'assert' else '',
            'operation_content': operation_content,
            'element': element,
            'locator_strategy': (element or {}).get('locator_strategy', ''),
            'locator_value': (element or {}).get('locator_value', ''),
            'wait_time': result.get('wait_time') or source.get('wait_time'),
        })

    return details


def set_execution_step_details(execution, step_results=None, step_sources=None):
    step_results = step_results if step_results is not None else execution.execution_logs
    execution.step_details = build_execution_step_details(
        step_results,
        step_sources=step_sources,
        execution_plan=getattr(execution, 'execution_plan', None),
    )
    return execution.step_details


def cleanup_execution_records_for_setting(setting, now=None):
    from .models import TestCaseExecution

    now = now or timezone.now()
    retention_days = max(int(setting.retention_days or 1), 1)
    cutoff = now - timedelta(days=retention_days)
    queryset = TestCaseExecution.objects.filter(
        project=setting.project,
        created_at__lt=cutoff,
    ).exclude(status__in=['pending', 'running'])
    deleted_count = queryset.delete()[0]
    setting.last_cleaned_at = now
    setting.save(update_fields=['last_cleaned_at', 'updated_at'])
    return {
        'deleted_count': deleted_count,
        'cutoff': cutoff,
        'retention_days': retention_days,
    }


def cleanup_due_execution_records(now=None, min_interval_hours=24):
    from .models import UiExecutionCleanupSetting

    now = now or timezone.now()
    due_before = now - timedelta(hours=min_interval_hours)
    settings = UiExecutionCleanupSetting.objects.filter(enabled=True).filter(
        last_cleaned_at__isnull=True
    ) | UiExecutionCleanupSetting.objects.filter(
        enabled=True,
        last_cleaned_at__lte=due_before,
    )

    results = []
    for setting in settings.select_related('project').distinct():
        results.append({
            'project_id': setting.project_id,
            'project_name': setting.project.name,
            **cleanup_execution_records_for_setting(setting, now=now),
        })
    return results
