# -*- coding: utf-8 -*-
"""APP测试执行管理视图"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import SearchFilter
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.http import FileResponse, Http404
from django.views.decorators.csrf import csrf_exempt
import logging
import os

from ..models import AppTestExecution
from ..serializers import AppTestExecutionSerializer
from ..tasks import send_execution_update
from .test_case_views import AppPagination

logger = logging.getLogger(__name__)


class AppTestExecutionViewSet(viewsets.ModelViewSet):
    """APP测试执行记录 ViewSet"""
    queryset = AppTestExecution.objects.all()
    serializer_class = AppTestExecutionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['status', 'test_case', 'device']
    search_fields = ['test_case__name', 'device__name', 'device__device_id', 'user__username']
    pagination_class = AppPagination
    
    def get_queryset(self):
        queryset = super().get_queryset()

        # 支持 test_suite__isnull 过滤，用于区分单独执行和套件执行
        suite_isnull = self.request.query_params.get('test_suite__isnull')
        if suite_isnull is not None:
            queryset = queryset.filter(test_suite__isnull=(suite_isnull.lower() in ('true', '1')))

        # 支持按项目间接过滤（通过 test_case.project）
        project_id = self.request.query_params.get('project')
        if project_id:
            queryset = queryset.filter(test_case__project_id=project_id)

        search_value = (self.request.query_params.get('search') or '').strip()
        if not search_value:
            return queryset
        return queryset.filter(
            Q(test_case__name__icontains=search_value) |
            Q(device__name__icontains=search_value) |
            Q(device__device_id__icontains=search_value) |
            Q(user__username__icontains=search_value)
        )
    
    @action(detail=False, methods=['get'])
    def ws_status(self, request):
        """检查 WebSocket 是否可用"""
        try:
            import daphne
            from channels.layers import get_channel_layer
            channel_layer = get_channel_layer()
            ws_available = channel_layer is not None and not isinstance(
                channel_layer, type(None)
            )
            # 检查是否通过 ASGI 服务器运行（非 runserver）
            server_type = request.META.get('SERVER_SOFTWARE', '')
            is_asgi = 'daphne' in server_type.lower() or request.META.get('asgi', False)
            return Response({'websocket': ws_available and is_asgi})
        except (ImportError, Exception):
            return Response({'websocket': False})

    @action(detail=True, methods=['post'])
    def stop(self, request, pk=None):
        """停止执行"""
        execution = self.get_object()
        
        if execution.status not in ['pending', 'running']:
            return Response({
                'success': False,
                'message': '只能停止待执行或执行中的任务'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # 停止 Celery 任务
            if execution.task_id:
                from celery import current_app
                current_app.control.revoke(execution.task_id, terminate=True, signal='SIGTERM')
                logger.info(f"Celery任务已终止: task_id={execution.task_id}")
            
            execution.status = 'stopped'
            execution.finished_at = timezone.now()
            if execution.started_at:
                execution.duration = (execution.finished_at - execution.started_at).total_seconds()
            execution.save()
            send_execution_update(
                execution.id,
                status='stopped',
                progress=execution.progress,
                message='任务已停止',
                report_path=execution.report_path,
                finished_at=execution.finished_at
            )
            
            return Response({
                'success': True,
                'message': '任务已停止'
            })
        except Exception as e:
            logger.error(f"停止任务失败: {str(e)}")
            return Response({
                'success': False,
                'message': f'停止任务失败: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'], url_path='diagnose')
    def diagnose(self, request, pk=None):
        """APP 执行失败诊断（分类级，不自动改图定位）。"""
        execution = self.get_object()
        from apps.ui_automation.services.diagnosis import diagnose_failure, has_diagnosis
        from apps.ui_automation.serializers import FailureDiagnosisSerializer, AutoFixProposalSerializer

        use_llm = request.data.get('use_llm', True)
        if has_diagnosis('app', execution.id) and not request.data.get('force'):
            from apps.ui_automation.models import FailureDiagnosis
            diagnosis = FailureDiagnosis.objects.filter(
                execution_type='app', execution_id=execution.id
            ).order_by('-created_at').first()
            return Response({
                'diagnosis': FailureDiagnosisSerializer(diagnosis).data,
                'proposals': AutoFixProposalSerializer(diagnosis.fix_proposals.all(), many=True).data,
                'cached': True,
            })

        logs = ''
        try:
            # step results may live on related fields / JSON
            logs = str(getattr(execution, 'error_message', '') or '')
            if hasattr(execution, 'step_results') and execution.step_results:
                import json
                logs = json.dumps(execution.step_results, ensure_ascii=False)[:8000]
        except Exception:
            pass

        ui_project = None
        # APP project is not UiProject — leave project null or try name match later
        diagnosis, proposals = diagnose_failure(
            execution_type='app',
            execution_id=execution.id,
            project=ui_project,
            logs=logs,
            error_message=execution.error_message or '',
            context={
                'test_case_id': execution.test_case_id,
                'device_id': execution.device_id,
                'status': execution.status,
                'result': execution.result,
            },
            created_by=request.user,
            use_llm=bool(use_llm),
            auto_apply=False,
        )
        return Response({
            'diagnosis': FailureDiagnosisSerializer(diagnosis).data,
            'proposals': AutoFixProposalSerializer(proposals, many=True).data,
        })


@csrf_exempt
def serve_report_file(request, execution_id, file_path=''):
    """提供 Allure 报告文件访问"""
    try:
        execution = AppTestExecution.objects.get(id=execution_id)
        if not execution.report_path:
            raise Http404("报告路径不存在")

        if not file_path:
            file_path = 'index.html'

        report_dir = execution.report_path
        full_path = os.path.join(report_dir, file_path)

        report_dir_abs = os.path.abspath(report_dir)
        full_path_abs = os.path.abspath(full_path)
        if not full_path_abs.startswith(report_dir_abs):
            raise Http404("无效的文件路径")

        if not os.path.exists(full_path_abs) or not os.path.isfile(full_path_abs):
            raise Http404("文件不存在")

        return FileResponse(open(full_path_abs, 'rb'), content_type=_get_content_type(file_path))
    except AppTestExecution.DoesNotExist:
        raise Http404("执行记录不存在")


def _get_content_type(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    content_types = {
        '.html': 'text/html',
        '.js': 'application/javascript',
        '.css': 'text/css',
        '.json': 'application/json',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.svg': 'image/svg+xml',
        '.ico': 'image/x-icon',
        '.woff': 'font/woff',
        '.woff2': 'font/woff2',
        '.ttf': 'font/ttf',
        '.eot': 'application/vnd.ms-fontobject',
        '.txt': 'text/plain',
    }
    return content_types.get(ext, 'application/octet-stream')
