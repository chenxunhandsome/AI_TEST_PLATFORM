import json

from django.db import transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .local_execution_service import (
    LOCAL_RUNNER_REQUIRED_PROTOCOL_VERSION,
    attach_execution_plan,
    build_execution_plan_from_payload,
    build_test_case_payload,
)
from .execution_dispatcher import (
    refresh_scheduled_task_execution_progress,
    refresh_suite_execution_progress,
)
from .models import LocalRunner, TestCaseExecution
from .scroll_coordinate_picker import (
    claim_local_scroll_coordinate_picker_task,
    report_local_scroll_coordinate_picker_task,
)
from .serializers import LocalRunnerSerializer, TestCaseExecutionSerializer


def _normalize_protocol_version(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _get_runner_incompatibility_message(runner):
    metadata = runner.metadata if isinstance(runner.metadata, dict) else {}
    protocol_version = _normalize_protocol_version(metadata.get('local_runner_protocol_version'))
    if protocol_version >= LOCAL_RUNNER_REQUIRED_PROTOCOL_VERSION:
        return ''

    return (
        f'本地执行器版本过旧或未同步，当前协议版本 {protocol_version or "未知"}，'
        f'服务端要求协议版本 {LOCAL_RUNNER_REQUIRED_PROTOCOL_VERSION}。'
        f'请在本地执行器机器同步最新 SVN 代码并重启本地执行器后重新执行。'
    )


def _fail_pending_executions_for_incompatible_runner(user, runner, message):
    pending_executions = list(
        TestCaseExecution.objects
        .select_for_update()
        .filter(
            created_by=user,
            execution_mode='local',
            status='pending',
            assigned_runner=runner,
        )
    )
    if not pending_executions:
        return 0

    now = timezone.now()
    for execution in pending_executions:
        execution.status = 'failed'
        execution.error_message = message
        execution.finished_at = now
        execution.save(update_fields=['status', 'error_message', 'finished_at'])

        if execution.test_suite_id and execution.run_identifier:
            refresh_suite_execution_progress(execution.test_suite, execution.run_identifier)

        if execution.scheduled_task_id and execution.run_identifier:
            refresh_scheduled_task_execution_progress(execution.scheduled_task, execution.run_identifier)

    return len(pending_executions)


def _parse_reported_step_results(logs):
    try:
        parsed = json.loads(logs or '[]')
    except (TypeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


def _get_execution_plan(execution):
    execution_plan = getattr(execution, 'execution_plan', {})
    plan = execution_plan if isinstance(execution_plan, dict) else {}
    if plan.get('planned_step_count') is not None:
        return plan

    payload = build_test_case_payload(execution.test_case)
    return build_execution_plan_from_payload(payload)


def _validate_local_execution_integrity(execution, reported_status, logs, error_message):
    if reported_status != 'passed':
        return reported_status, error_message

    plan = _get_execution_plan(execution)
    planned_step_count = int(plan.get('planned_step_count') or 0)
    if planned_step_count <= 0:
        return reported_status, error_message

    reported_steps = _parse_reported_step_results(logs)
    reported_step_count = len(reported_steps)
    reported_step_numbers = [
        step.get('step_number')
        for step in reported_steps
        if isinstance(step, dict)
    ]
    if reported_step_count == planned_step_count and reported_step_numbers == list(range(1, planned_step_count + 1)):
        return reported_status, error_message

    integrity_error = (
        f'本地执行器执行步骤不完整: 当前执行计划 {planned_step_count} 步，'
        f'本地执行器只上报 {reported_step_count} 步，已阻止错误标记为成功。'
        f'请同步并重启本地执行器后重新执行。'
    )
    if error_message:
        integrity_error = f'{error_message}\n{integrity_error}'
    return 'failed', integrity_error


class LocalRunnerViewSet(viewsets.ReadOnlyModelViewSet):
    """UI 自动化本地执行器管理与任务协同接口。"""

    serializer_class = LocalRunnerSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return LocalRunner.objects.filter(user=self.request.user).order_by('-updated_at')

    def _get_runner(self, request):
        runner_uuid = request.data.get('runner_uuid') or request.query_params.get('runner_uuid')
        if not runner_uuid:
            return None, Response({'error': 'runner_uuid is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            runner = LocalRunner.objects.get(runner_uuid=runner_uuid, user=request.user)
        except LocalRunner.DoesNotExist:
            return None, Response({'error': 'local runner not found'}, status=status.HTTP_404_NOT_FOUND)

        runner.last_heartbeat = timezone.now()
        runner.status = 'online'
        runner.save(update_fields=['last_heartbeat', 'status', 'updated_at'])
        return runner, None

    @action(detail=False, methods=['post'])
    def register(self, request):
        runner_uuid = request.data.get('runner_uuid')
        if not runner_uuid:
            return Response({'error': 'runner_uuid is required'}, status=status.HTTP_400_BAD_REQUEST)

        defaults = {
            'user': request.user,
            'name': request.data.get('name') or request.data.get('hostname') or runner_uuid,
            'hostname': request.data.get('hostname', ''),
            'platform': request.data.get('platform', ''),
            'status': 'online',
            'last_heartbeat': timezone.now(),
            'metadata': request.data.get('metadata') or {},
        }

        runner, created = LocalRunner.objects.get_or_create(
            runner_uuid=runner_uuid,
            defaults=defaults,
        )

        if not created:
            if runner.user_id != request.user.id:
                return Response({'error': 'runner_uuid already belongs to another user'}, status=status.HTTP_403_FORBIDDEN)
            for field, value in defaults.items():
                setattr(runner, field, value)
            runner.save()

        return Response(LocalRunnerSerializer(runner).data)

    @action(detail=False, methods=['post'])
    def heartbeat(self, request):
        runner, error_response = self._get_runner(request)
        if error_response:
            return error_response

        metadata = request.data.get('metadata')
        if metadata:
            runner.metadata = metadata
            runner.save(update_fields=['metadata', 'updated_at'])

        return Response(LocalRunnerSerializer(runner).data)

    @action(detail=False, methods=['post'])
    def claim(self, request):
        runner, error_response = self._get_runner(request)
        if error_response:
            return error_response

        incompatibility_message = _get_runner_incompatibility_message(runner)
        if incompatibility_message:
            with transaction.atomic():
                failed_count = _fail_pending_executions_for_incompatible_runner(
                    request.user,
                    runner,
                    incompatibility_message,
                )
            return Response({
                'task': None,
                'runner_incompatible': True,
                'failed_pending_executions': failed_count,
                'message': incompatibility_message,
            })

        picker_task = claim_local_scroll_coordinate_picker_task(request.user.id, runner.id)
        if picker_task:
            return Response({'task': picker_task})

        with transaction.atomic():
            execution = (
                TestCaseExecution.objects
                .select_for_update()
                .select_related('test_case', 'project', 'assigned_runner', 'created_by')
                .filter(
                    created_by=request.user,
                    execution_mode='local',
                    status='pending',
                    assigned_runner=runner,
                )
                .order_by('created_at')
                .first()
            )

            if not execution:
                return Response({'task': None})

            execution.status = 'running'
            execution.started_at = timezone.now()
            execution.save(update_fields=['status', 'started_at'])

        plan = execution.execution_plan if isinstance(execution.execution_plan, dict) else {}
        payload = plan.get('payload') if isinstance(plan.get('payload'), dict) else None
        if not payload:
            payload = build_test_case_payload(execution.test_case)
            attach_execution_plan(execution, payload)
        return Response({
            'task': {
                'task_type': 'test_case',
                'execution_id': execution.id,
                'engine': execution.engine,
                'browser': execution.browser,
                'headless': execution.headless,
                'payload': payload,
            }
        })

    @action(detail=False, methods=['post'])
    def report(self, request):
        runner, error_response = self._get_runner(request)
        if error_response:
            return error_response

        task_type = request.data.get('task_type')
        if task_type == 'scroll_coordinate_picker':
            session_id = request.data.get('session_id')
            action = request.data.get('action')
            if not session_id or not action:
                return Response({'error': 'session_id and action are required'}, status=status.HTTP_400_BAD_REQUEST)

            try:
                report_local_scroll_coordinate_picker_task(
                    request.user.id,
                    runner.id,
                    str(session_id),
                    str(action),
                    bool(request.data.get('success')),
                    payload=request.data.get('payload') or {},
                    error=request.data.get('error_message', ''),
                    command_sequence=request.data.get('command_sequence'),
                )
            except ValueError as exc:
                return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

            return Response({'success': bool(request.data.get('success'))})

        execution_id = request.data.get('execution_id')
        if not execution_id:
            return Response({'error': 'execution_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            execution = TestCaseExecution.objects.select_related(
                'assigned_runner',
                'test_case',
                'test_suite',
                'scheduled_task',
            ).get(
                id=execution_id,
                created_by=request.user,
                execution_mode='local',
                assigned_runner=runner,
            )
        except TestCaseExecution.DoesNotExist:
            return Response({'error': 'execution not found'}, status=status.HTTP_404_NOT_FOUND)

        reported_status = request.data.get('status') or ('passed' if request.data.get('success') else 'failed')
        if reported_status not in {'passed', 'failed', 'error'}:
            reported_status = 'error'
        execution_logs = request.data.get('logs', '')
        error_message = request.data.get('error_message', '')
        reported_status, error_message = _validate_local_execution_integrity(
            execution,
            reported_status,
            execution_logs,
            error_message,
        )

        execution.status = reported_status
        execution.execution_logs = execution_logs
        execution.screenshots = request.data.get('screenshots') or []
        execution.execution_time = request.data.get('execution_time') or 0
        execution.error_message = error_message
        execution.finished_at = timezone.now()
        execution.save(
            update_fields=[
                'status', 'execution_logs', 'screenshots', 'execution_time',
                'error_message', 'finished_at'
            ]
        )

        if execution.test_suite_id and execution.run_identifier:
            refresh_suite_execution_progress(execution.test_suite, execution.run_identifier)

        if execution.scheduled_task_id and execution.run_identifier:
            refresh_scheduled_task_execution_progress(execution.scheduled_task, execution.run_identifier)

        return Response({
            'success': execution.status == 'passed',
            'execution': TestCaseExecutionSerializer(execution).data,
        })
