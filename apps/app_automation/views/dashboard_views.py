# -*- coding: utf-8 -*-
"""APP自动化仪表盘视图"""
from datetime import timedelta
import logging

from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..constants import DeviceStatus, ExecutionResult, ExecutionStatus
from ..models import AppDevice, AppTestCase, AppTestExecution, AppTestSuite
from ..serializers import AppTestExecutionSerializer

logger = logging.getLogger(__name__)


class AppDashboardViewSet(viewsets.ViewSet):
    """APP自动化测试 Dashboard"""
    permission_classes = [IsAuthenticated]

    def _base_execution_qs(self, request):
        qs = AppTestExecution.objects.select_related(
            'test_case', 'test_case__project', 'device', 'user', 'test_suite'
        )
        project_id = request.query_params.get('project')
        if project_id:
            qs = qs.filter(
                Q(test_case__project_id=project_id) | Q(test_suite__project_id=project_id)
            )
        return qs

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """获取统计数据与最近执行记录"""
        try:
            days = int(request.query_params.get('days') or 30)
            days = max(1, min(days, 90))
            recent_limit = int(request.query_params.get('recent_limit') or 10)
            recent_limit = max(1, min(recent_limit, 50))

            project_id = request.query_params.get('project')

            # 设备统计
            device_qs = AppDevice.objects.all()
            total_devices = device_qs.count()
            available_devices = device_qs.filter(
                status__in=[DeviceStatus.AVAILABLE, DeviceStatus.ONLINE]
            ).count()
            locked_devices = device_qs.filter(status=DeviceStatus.LOCKED).count()
            offline_devices = device_qs.filter(status=DeviceStatus.OFFLINE).count()

            # 用例 / 套件
            case_qs = AppTestCase.objects.all()
            suite_qs = AppTestSuite.objects.all()
            if project_id:
                case_qs = case_qs.filter(project_id=project_id)
                suite_qs = suite_qs.filter(project_id=project_id)

            since = timezone.now() - timedelta(days=days)
            executions = self._base_execution_qs(request).filter(created_at__gte=since)

            total_executions = executions.count()
            running_executions = executions.filter(status=ExecutionStatus.RUNNING).count()
            # 真实通过/失败看 result；兼容旧 status=success/failed
            success_executions = executions.filter(
                Q(result=ExecutionResult.PASSED) | Q(status=ExecutionStatus.SUCCESS)
            ).count()
            failed_executions = executions.filter(
                Q(result=ExecutionResult.FAILED)
                | Q(status__in=[ExecutionStatus.ERROR, ExecutionStatus.FAILED])
            ).count()
            finished = success_executions + failed_executions
            pass_rate = round((success_executions / finished * 100) if finished > 0 else 0, 2)

            # 近 N 天趋势（按日）
            trend_rows = (
                executions.annotate(day=TruncDate('created_at'))
                .values('day')
                .annotate(
                    total=Count('id'),
                    passed=Count('id', filter=Q(result=ExecutionResult.PASSED) | Q(status=ExecutionStatus.SUCCESS)),
                    failed=Count(
                        'id',
                        filter=Q(result=ExecutionResult.FAILED)
                        | Q(status__in=[ExecutionStatus.ERROR, ExecutionStatus.FAILED]),
                    ),
                )
                .order_by('day')
            )
            trend = [
                {
                    'date': row['day'].isoformat() if row['day'] else None,
                    'total': row['total'],
                    'passed': row['passed'],
                    'failed': row['failed'],
                }
                for row in trend_rows
            ]

            # 最近执行记录
            recent_qs = self._base_execution_qs(request).order_by('-created_at')[:recent_limit]
            recent_executions_data = AppTestExecutionSerializer(recent_qs, many=True).data

            return Response({
                'success': True,
                'data': {
                    'devices': {
                        'total': total_devices,
                        'online': available_devices,
                        'available': available_devices,
                        'locked': locked_devices,
                        'offline': offline_devices,
                    },
                    'test_cases': {
                        'total': case_qs.count(),
                    },
                    'test_suites': {
                        'total': suite_qs.count(),
                    },
                    'executions': {
                        'total': total_executions,
                        'running': running_executions,
                        'success': success_executions,
                        'failed': failed_executions,
                        'pass_rate': pass_rate,
                        'days': days,
                    },
                    'trend': trend,
                    'recent_executions': recent_executions_data,
                }
            })
        except Exception as e:
            logger.exception('获取 APP 看板统计失败')
            return Response({
                'success': False,
                'message': f'获取统计数据失败: {e}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='recent-executions')
    def recent_executions(self, request):
        """单独拉取最近执行记录（供看板刷新）"""
        try:
            limit = int(request.query_params.get('limit') or 10)
            limit = max(1, min(limit, 50))
            qs = self._base_execution_qs(request).order_by('-created_at')[:limit]
            return Response({
                'success': True,
                'data': AppTestExecutionSerializer(qs, many=True).data,
            })
        except Exception as e:
            logger.exception('获取最近执行记录失败')
            return Response({
                'success': False,
                'message': str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
