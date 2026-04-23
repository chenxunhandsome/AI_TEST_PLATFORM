from django.db import transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .local_execution_service import build_test_case_payload
from .execution_dispatcher import (
    refresh_scheduled_task_execution_progress,
    refresh_suite_execution_progress,
)
from .models import LocalRunner, TestCaseExecution
from .serializers import LocalRunnerSerializer, TestCaseExecutionSerializer


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

        payload = build_test_case_payload(execution.test_case)
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

        execution_id = request.data.get('execution_id')
        if not execution_id:
            return Response({'error': 'execution_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            execution = TestCaseExecution.objects.select_related(
                'assigned_runner',
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

        execution.status = reported_status
        execution.execution_logs = request.data.get('logs', '')
        execution.screenshots = request.data.get('screenshots') or []
        execution.execution_time = request.data.get('execution_time') or 0
        execution.error_message = request.data.get('error_message', '')
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
