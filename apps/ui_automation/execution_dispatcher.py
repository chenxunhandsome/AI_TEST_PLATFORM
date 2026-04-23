import uuid

from django.db import transaction

from .models import TestCaseExecution


def generate_run_identifier():
    return uuid.uuid4().hex


def queue_local_test_case_executions(
    test_cases,
    *,
    project,
    engine,
    browser,
    headless,
    created_by,
    assigned_runner,
    execution_source,
    test_suite=None,
    scheduled_task=None,
    run_identifier=None,
):
    run_identifier = run_identifier or generate_run_identifier()
    executions = []

    with transaction.atomic():
        for test_case in test_cases:
            executions.append(
                TestCaseExecution.objects.create(
                    test_case=test_case,
                    project=project,
                    test_suite=test_suite,
                    execution_source=execution_source,
                    execution_mode='local',
                    status='pending',
                    engine=engine,
                    browser=browser,
                    headless=headless,
                    created_by=created_by,
                    scheduled_task=scheduled_task,
                    assigned_runner=assigned_runner,
                    run_identifier=run_identifier,
                )
            )

    return executions, run_identifier


def queue_local_suite_execution(
    test_suite,
    *,
    engine,
    browser,
    headless,
    created_by,
    assigned_runner,
    execution_source='suite',
    scheduled_task=None,
    run_identifier=None,
):
    suite_test_cases = test_suite.suite_test_cases.select_related('test_case').order_by('order')
    test_cases = [suite_case.test_case for suite_case in suite_test_cases]

    if not test_cases:
        return [], run_identifier or generate_run_identifier()

    test_suite.execution_status = 'running'
    test_suite.passed_count = 0
    test_suite.failed_count = 0
    test_suite.save(update_fields=['execution_status', 'passed_count', 'failed_count'])

    return queue_local_test_case_executions(
        test_cases,
        project=test_suite.project,
        engine=engine,
        browser=browser,
        headless=headless,
        created_by=created_by,
        assigned_runner=assigned_runner,
        execution_source=execution_source,
        test_suite=test_suite,
        scheduled_task=scheduled_task,
        run_identifier=run_identifier,
    )


def refresh_suite_execution_progress(test_suite, run_identifier):
    if not test_suite or not run_identifier:
        return None

    queryset = TestCaseExecution.objects.filter(
        test_suite=test_suite,
        run_identifier=run_identifier,
    )
    total = queryset.count()
    passed = queryset.filter(status='passed').count()
    failed = queryset.filter(status__in=['failed', 'error']).count()
    active = queryset.filter(status__in=['pending', 'running']).count()

    if total == 0:
        return None

    if active > 0:
        suite_status = 'running'
    else:
        suite_status = 'passed' if failed == 0 and passed > 0 else 'failed'

    test_suite.passed_count = passed
    test_suite.failed_count = failed
    test_suite.execution_status = suite_status
    test_suite.save(update_fields=['passed_count', 'failed_count', 'execution_status'])

    return {
        'total': total,
        'passed': passed,
        'failed': failed,
        'active': active,
        'status': suite_status,
    }


def initialize_local_task_result(task, run_identifier, queued_count):
    if not task:
        return

    runner_name = task.assigned_runner.name if task.assigned_runner else ''
    message = f'任务已下发到本地执行器，等待领取执行'
    if runner_name:
        message = f'任务已下发到本地执行器：{runner_name}'

    task.last_result = {
        'status': 'queued',
        'message': message,
        'run_identifier': run_identifier,
        'queued_count': queued_count,
        'success_count': 0,
        'failed_count': 0,
        'active_count': queued_count,
        'finalized': False,
    }
    task.error_message = ''
    task.save(update_fields=['last_result', 'error_message', 'updated_at'])


def refresh_scheduled_task_execution_progress(task, run_identifier):
    if not task or not run_identifier:
        return None

    queryset = task.case_executions.filter(run_identifier=run_identifier)
    total = queryset.count()
    passed = queryset.filter(status='passed').count()
    failed = queryset.filter(status__in=['failed', 'error']).count()
    active = queryset.filter(status__in=['pending', 'running']).count()

    if total == 0:
        return None

    is_complete = active == 0
    was_finalized = (
        isinstance(task.last_result, dict)
        and task.last_result.get('run_identifier') == run_identifier
        and bool(task.last_result.get('finalized'))
    )

    if active > 0:
        result_status = 'running'
        result_message = f'任务执行中：成功 {passed} 个，失败 {failed} 个，剩余 {active} 个'
    elif failed == 0:
        result_status = 'success'
        result_message = f'执行完成：{passed} 个成功'
    elif passed > 0:
        result_status = 'partial'
        result_message = f'执行完成：{passed} 个成功，{failed} 个失败'
    else:
        result_status = 'failed'
        result_message = f'执行失败：{failed} 个失败'

    task.last_result = {
        'status': result_status,
        'message': result_message,
        'run_identifier': run_identifier,
        'queued_count': total,
        'success_count': passed,
        'failed_count': failed,
        'active_count': active,
        'finalized': is_complete,
    }
    task.error_message = '' if failed == 0 else f'{failed} 个测试用例执行失败'

    update_fields = ['last_result', 'error_message', 'updated_at']

    if is_complete and not was_finalized:
        if failed == 0:
            task.successful_runs += 1
            update_fields.append('successful_runs')
        else:
            task.failed_runs += 1
            update_fields.append('failed_runs')

    task.save(update_fields=update_fields)

    if is_complete and not was_finalized:
        from .views import UiScheduledTaskViewSet

        viewset = UiScheduledTaskViewSet()
        viewset._send_task_notification(task, success=(failed == 0))

    return {
        'total': total,
        'passed': passed,
        'failed': failed,
        'active': active,
        'status': result_status,
        'complete': is_complete,
    }
