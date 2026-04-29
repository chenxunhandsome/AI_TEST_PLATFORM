import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import logging
import time
import traceback
from types import SimpleNamespace

from django.utils import timezone

from .models import TestCaseStep
from .playwright_engine import PlaywrightTestEngine
from .selenium_engine import SeleniumTestEngine
from .variable_resolver import (
    clear_runtime_variables,
    get_runtime_variables,
    resolve_element_locator_payload,
    resolve_variables,
    set_runtime_variable,
    set_runtime_variables,
)
from .project_runtime import initialize_project_runtime_variables

logger = logging.getLogger(__name__)


def _normalize_runtime_variable_name(value):
    return str(value or '').strip()


def _resolve_serialized_step_payload(step):
    resolved_input_value = step.input_value or ''
    if step.input_value:
        resolved_input_value = resolve_variables(step.input_value)

    resolved_assert_value = step.assert_value or ''
    if step.assert_value:
        resolved_assert_value = resolve_variables(step.assert_value)

    is_enabled = getattr(step, 'is_enabled', True) is not False
    save_as = _normalize_runtime_variable_name(step.save_as)
    if is_enabled and save_as:
        if step.action_type in {'fill', 'fillAndEnter', 'switchTab'}:
            set_runtime_variable(save_as, resolved_input_value)
        elif step.action_type == 'assert':
            set_runtime_variable(save_as, resolved_assert_value)

    return {
        'step_number': step.step_number,
        'action_type': step.action_type,
        'description': step.description or '',
        'is_enabled': is_enabled,
        'save_as': save_as,
        'input_value': resolved_input_value,
        'wait_time': step.wait_time,
        'assert_type': step.assert_type or '',
        'assert_value': resolved_assert_value,
    }


def build_test_case_payload(test_case):
    """将数据库中的测试用例转换为可在本地 runner 上执行的 payload。"""
    steps = []
    previous_runtime_variables = get_runtime_variables()

    try:
        initialize_project_runtime_variables(project=test_case.project)

        for step in test_case.steps.all().order_by('step_number'):
            element_data = None
            if step.element:
                element_data = resolve_element_locator_payload({
                    'locator_strategy': step.element.locator_strategy.name if step.element.locator_strategy else 'css',
                    'locator_value': step.element.locator_value,
                    'name': step.element.name,
                    'wait_timeout': step.element.wait_timeout,
                    'force_action': step.element.force_action,
                })

            step_payload = _resolve_serialized_step_payload(step)
            step_payload['element_data'] = element_data
            steps.append(step_payload)
    finally:
        clear_runtime_variables()
        if previous_runtime_variables:
            set_runtime_variables(previous_runtime_variables)

    return {
        'test_case_id': test_case.id,
        'test_case_name': test_case.name,
        'project_id': test_case.project_id,
        'project_name': test_case.project.name,
        'base_url': test_case.project.base_url,
        'project_global_variables': test_case.project.global_variables or [],
        'steps': steps,
    }


def execute_serialized_test_case(payload, engine_type='playwright', browser='chrome', headless=False):
    """在当前机器执行序列化后的测试用例 payload。"""
    start_time = time.time()
    detailed_errors = []
    step_results = []
    screenshots = []

    try:
        if engine_type == 'selenium':
            return _run_selenium(payload, browser, headless, start_time, step_results, screenshots, detailed_errors)
        return _run_playwright(payload, browser, headless, start_time, step_results, screenshots, detailed_errors)
    except Exception as exc:
        logger.exception("本地执行序列化测试用例失败")
        return {
            'success': False,
            'status': 'error',
            'logs': json.dumps(step_results, ensure_ascii=False),
            'screenshots': screenshots,
            'execution_time': round(time.time() - start_time, 2),
            'errors': detailed_errors or [{
                'message': str(exc),
                'details': traceback.format_exc(),
                'step_number': None,
                'action_type': '',
                'element': '',
                'description': '',
            }],
            'error_message': str(exc),
        }


def _make_step(step_data):
    return SimpleNamespace(
        action_type=step_data.get('action_type', ''),
        description=step_data.get('description', ''),
        is_enabled=step_data.get('is_enabled', True),
        save_as=step_data.get('save_as', ''),
        input_value=step_data.get('input_value', ''),
        wait_time=step_data.get('wait_time') or 1000,
        assert_type=step_data.get('assert_type', ''),
        assert_value=step_data.get('assert_value', ''),
        element_data=step_data.get('element_data') or {},
    )


def _browser_map(browser):
    return {
        'chrome': 'chromium',
        'firefox': 'firefox',
        'safari': 'webkit',
        'edge': 'chromium',
    }.get(browser, 'chromium')


def _format_final_result(start_time, step_results, screenshots, detailed_errors, error_message, status_value):
    return {
        'success': status_value == 'passed',
        'status': status_value,
        'logs': json.dumps(step_results, ensure_ascii=False),
        'screenshots': screenshots,
        'execution_time': round(time.time() - start_time, 2),
        'errors': detailed_errors,
        'error_message': error_message or '',
    }


def _append_step_result(step_results, step_number, action_type, description, success, error=None, status=None, message=''):
    step_results.append({
        'step_number': step_number,
        'action_type': action_type,
        'description': description or '',
        'success': success,
        'error': error,
        'status': status or ('passed' if success else 'failed'),
        'message': message or '',
    })


def _append_error(detailed_errors, step_number, action_type, element_name, message, details, description):
    detailed_errors.append({
        'step_number': step_number,
        'action_type': action_type,
        'element': element_name or '',
        'message': message,
        'details': details,
        'description': description or '',
    })


def _append_screenshot(screenshots, screenshot_base64, description, step_number):
    if not screenshot_base64:
        return
    screenshots.append({
        'url': screenshot_base64,
        'description': description,
        'step_number': step_number,
        'timestamp': timezone.now().isoformat(),
    })


def _resolve_step_runtime_values(step):
    resolved_input_value = step.input_value
    if step.input_value:
        resolved_input_value = resolve_variables(step.input_value)

    resolved_assert_value = step.assert_value
    if step.assert_value:
        resolved_assert_value = resolve_variables(step.assert_value)

    step.input_value = resolved_input_value
    step.assert_value = resolved_assert_value
    if isinstance(getattr(step, 'element_data', None), dict):
        step.element_data = resolve_element_locator_payload(step.element_data)
    return resolved_input_value, resolved_assert_value


def _store_step_runtime_variable(step, resolved_input_value, resolved_assert_value):
    save_as = str(getattr(step, 'save_as', '') or '').strip()
    if not save_as:
        return

    if step.action_type in {'fill', 'fillAndEnter', 'switchTab'}:
        set_runtime_variable(save_as, resolved_input_value)
    elif step.action_type == 'assert':
        set_runtime_variable(save_as, resolved_assert_value)


def _run_selenium(payload, browser, headless, start_time, step_results, screenshots, detailed_errors):
    initialize_project_runtime_variables(global_variables=payload.get('project_global_variables'))
    is_available, error_msg = SeleniumTestEngine.check_browser_available(browser)
    if not is_available:
        return _format_final_result(
            start_time,
            step_results,
            screenshots,
            [{
                'message': f'{browser.capitalize()} 浏览器不可用',
                'details': error_msg,
                'step_number': None,
                'action_type': '浏览器检查',
                'element': '',
                'description': '',
            }],
            error_msg,
            'failed',
        )

    engine = SeleniumTestEngine(browser_type=browser, headless=headless)
    error_message = ''
    status_value = 'passed'

    try:
        engine.start()
        if payload.get('base_url'):
            success, nav_log = engine.navigate(payload['base_url'])
            if not success:
                return _format_final_result(
                    start_time,
                    step_results,
                    screenshots,
                    [{
                        'message': '导航失败',
                        'details': nav_log,
                        'step_number': None,
                        'action_type': 'navigate',
                        'element': '',
                        'description': '',
                    }],
                    nav_log,
                    'failed',
                )

        for index, step_data in enumerate(payload.get('steps', []), start=1):
            step = _make_step(step_data)
            action_text = dict(TestCaseStep.ACTION_TYPE_CHOICES).get(step.action_type, step.action_type)

            if getattr(step, 'is_enabled', True) is False:
                _append_step_result(
                    step_results,
                    index,
                    step.action_type,
                    step.description,
                    True,
                    None,
                    status='skipped',
                    message='步骤已禁用，已跳过执行',
                )
                continue

            resolved_input_value, resolved_assert_value = _resolve_step_runtime_values(step)
            element_data = getattr(step, 'element_data', None) or {}

            try:
                success, step_log, screenshot_base64 = engine.execute_step(step, element_data)
            except Exception as exc:
                success = False
                step_log = str(exc)
                screenshot_base64 = None

            if success:
                _store_step_runtime_variable(step, resolved_input_value, resolved_assert_value)

            _append_step_result(step_results, index, step.action_type, step.description, success, None if success else step_log)

            if step.action_type == 'screenshot' and screenshot_base64:
                _append_screenshot(screenshots, screenshot_base64, f'步骤 {index}: {step.description or "手动截图"}', index)

            if not success:
                status_value = 'failed'
                error_message = step_log
                element_name = element_data.get('name', '')
                _append_error(
                    detailed_errors,
                    index,
                    action_text,
                    element_name,
                    f'步骤 {index} 执行失败',
                    step_log,
                    step.description,
                )
                if not screenshot_base64:
                    try:
                        screenshot_base64 = engine.capture_screenshot()
                    except Exception:
                        screenshot_base64 = None
                _append_screenshot(screenshots, screenshot_base64, f'步骤 {index} 失败截图: {step.description or action_text}', index)
                break
    finally:
        try:
            engine.stop()
        except Exception:
            logger.exception("关闭本地 Selenium 浏览器失败")

    return _format_final_result(start_time, step_results, screenshots, detailed_errors, error_message, status_value)


def _run_playwright(payload, browser, headless, start_time, step_results, screenshots, detailed_errors):
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix='ui-local-playwright') as executor:
        future = executor.submit(
            lambda: asyncio.run(
                _run_playwright_async(payload, browser, headless, start_time, step_results, screenshots, detailed_errors)
            )
        )
        return future.result()


async def _run_playwright_async(payload, browser, headless, start_time, step_results, screenshots, detailed_errors):
    initialize_project_runtime_variables(global_variables=payload.get('project_global_variables'))
    engine = PlaywrightTestEngine(browser_type=_browser_map(browser), headless=headless)
    error_message = ''
    status_value = 'passed'

    try:
        await engine.start()
        if payload.get('base_url'):
            success, nav_log = await engine.navigate(payload['base_url'])
            if not success:
                return _format_final_result(
                    start_time,
                    step_results,
                    screenshots,
                    [{
                        'message': '导航失败',
                        'details': nav_log,
                        'step_number': None,
                        'action_type': 'navigate',
                        'element': '',
                        'description': '',
                    }],
                    nav_log,
                    'failed',
                )

        for index, step_data in enumerate(payload.get('steps', []), start=1):
            step = _make_step(step_data)
            action_text = dict(TestCaseStep.ACTION_TYPE_CHOICES).get(step.action_type, step.action_type)

            if getattr(step, 'is_enabled', True) is False:
                _append_step_result(
                    step_results,
                    index,
                    step.action_type,
                    step.description,
                    True,
                    None,
                    status='skipped',
                    message='步骤已禁用，已跳过执行',
                )
                continue

            resolved_input_value, resolved_assert_value = _resolve_step_runtime_values(step)
            element_data = getattr(step, 'element_data', None) or {}

            try:
                success, step_log, screenshot_base64 = await engine.execute_step(step, element_data)
            except Exception as exc:
                success = False
                step_log = str(exc)
                screenshot_base64 = None

            if success:
                _store_step_runtime_variable(step, resolved_input_value, resolved_assert_value)

            _append_step_result(step_results, index, step.action_type, step.description, success, None if success else step_log)

            if step.action_type == 'screenshot' and screenshot_base64:
                _append_screenshot(screenshots, screenshot_base64, f'步骤 {index}: {step.description or "手动截图"}', index)

            if not success:
                status_value = 'failed'
                error_message = step_log
                element_name = element_data.get('name', '')
                _append_error(
                    detailed_errors,
                    index,
                    action_text,
                    element_name,
                    f'步骤 {index} 执行失败',
                    step_log,
                    step.description,
                )
                if not screenshot_base64:
                    try:
                        screenshot_base64 = await engine.capture_screenshot()
                    except Exception:
                        screenshot_base64 = None
                _append_screenshot(screenshots, screenshot_base64, f'步骤 {index} 失败截图: {step.description or action_text}', index)
                break
    finally:
        try:
            await engine.stop()
        except Exception:
            logger.exception("关闭本地 Playwright 浏览器失败")

    return _format_final_result(start_time, step_results, screenshots, detailed_errors, error_message, status_value)
