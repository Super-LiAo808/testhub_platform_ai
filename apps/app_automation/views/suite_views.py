# -*- coding: utf-8 -*-
"""APP测试套件管理视图"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import SearchFilter
from django_filters.rest_framework import DjangoFilterBackend
import logging

from ..models import AppTestSuite, AppTestSuiteCase, AppTestCase, AppDevice, AppTestExecution
from .test_case_views import AppPagination
from ..serializers import (
    AppTestSuiteSerializer,
    AppTestSuiteCreateSerializer,
    AppTestSuiteUpdateSerializer,
    AppTestSuiteCaseSerializer,
    AppTestExecutionSerializer,
)

logger = logging.getLogger(__name__)


class AppTestSuiteViewSet(viewsets.ModelViewSet):
    """APP测试套件 ViewSet"""
    queryset = AppTestSuite.objects.all()
    permission_classes = [IsAuthenticated]
    pagination_class = AppPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['project']
    search_fields = ['name', 'description']

    def get_serializer_class(self):
        if self.action == 'create':
            return AppTestSuiteCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return AppTestSuiteUpdateSerializer
        return AppTestSuiteSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    # ---------- 用例管理 ----------

    @action(detail=True, methods=['get'])
    def test_cases(self, request, pk=None):
        """获取套件中的所有用例（按顺序）"""
        suite = self.get_object()
        cases = suite.suite_cases.select_related('test_case', 'test_case__app_package').all()
        serializer = AppTestSuiteCaseSerializer(cases, many=True)
        return Response({'success': True, 'data': serializer.data})

    @action(detail=True, methods=['post'])
    def add_test_case(self, request, pk=None):
        """向套件添加用例"""
        suite = self.get_object()
        test_case_id = request.data.get('test_case_id')
        order = request.data.get('order')

        if not test_case_id:
            return Response({'success': False, 'message': '请提供 test_case_id'},
                            status=status.HTTP_400_BAD_REQUEST)

        # 默认排在最后
        if order is None:
            max_order = suite.suite_cases.order_by('-order').values_list('order', flat=True).first()
            order = (max_order or 0) + 1

        try:
            sc = AppTestSuiteCase.objects.create(
                test_suite=suite,
                test_case_id=test_case_id,
                order=order
            )
            serializer = AppTestSuiteCaseSerializer(sc)
            return Response({'success': True, 'data': serializer.data},
                            status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'success': False, 'message': str(e)},
                            status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def add_test_cases(self, request, pk=None):
        """批量添加用例到套件"""
        suite = self.get_object()
        test_case_ids = request.data.get('test_case_ids', [])

        if not test_case_ids:
            return Response({'success': False, 'message': '请提供 test_case_ids'},
                            status=status.HTTP_400_BAD_REQUEST)

        max_order = suite.suite_cases.order_by('-order').values_list('order', flat=True).first()
        current_order = (max_order or 0) + 1

        # 排除已存在的
        existing_ids = set(suite.suite_cases.values_list('test_case_id', flat=True))
        added = 0
        for tc_id in test_case_ids:
            if tc_id not in existing_ids:
                AppTestSuiteCase.objects.create(
                    test_suite=suite,
                    test_case_id=tc_id,
                    order=current_order
                )
                current_order += 1
                added += 1

        return Response({
            'success': True,
            'message': f'成功添加 {added} 个用例',
            'added': added
        })

    @action(detail=True, methods=['post'])
    def remove_test_case(self, request, pk=None):
        """从套件移除用例"""
        suite = self.get_object()
        test_case_id = request.data.get('test_case_id')

        try:
            sc = AppTestSuiteCase.objects.get(
                test_suite=suite, test_case_id=test_case_id
            )
            sc.delete()
            return Response({'success': True, 'message': '已移除'})
        except AppTestSuiteCase.DoesNotExist:
            return Response({'success': False, 'message': '用例不在该套件中'},
                            status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'])
    def update_test_case_order(self, request, pk=None):
        """更新套件中用例的顺序"""
        suite = self.get_object()
        test_case_orders = request.data.get('test_case_orders', [])

        try:
            for item in test_case_orders:
                AppTestSuiteCase.objects.filter(
                    test_suite=suite,
                    test_case_id=item['test_case_id']
                ).update(order=item['order'])
            return Response({'success': True, 'message': '顺序更新成功'})
        except Exception as e:
            return Response({'success': False, 'message': str(e)},
                            status=status.HTTP_400_BAD_REQUEST)

    # ---------- 套件执行 ----------

    @action(detail=True, methods=['post'])
    def run(self, request, pk=None):
        """执行测试套件（顺序执行所有用例）"""
        suite = self.get_object()
        device_id = request.data.get('device_id')
        package_name = request.data.get('package_name')

        if not device_id:
            return Response({'success': False, 'message': '请选择执行设备'},
                            status=status.HTTP_400_BAD_REQUEST)

        # 检查套件是否包含用例
        suite_cases = suite.suite_cases.select_related('test_case').all()
        if not suite_cases.exists():
            return Response({'success': False, 'message': '该套件未包含任何测试用例'},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            device = AppDevice.objects.get(device_id=device_id)
            if device.status == 'locked' and device.locked_by != request.user:
                return Response({'success': False, 'message': '设备已被其他用户锁定'},
                                status=status.HTTP_400_BAD_REQUEST)

            # 为每个用例创建执行记录
            executions = []
            for sc in suite_cases:
                execution = AppTestExecution.objects.create(
                    test_case=sc.test_case,
                    test_suite=suite,
                    device=device,
                    user=request.user,
                    status='pending'
                )
                executions.append(execution)

            # 更新套件状态
            suite.execution_status = 'running'
            suite.save(update_fields=['execution_status'])

            # 触发执行任务，顺序执行（无 Celery worker 时走本地线程）
            from ..tasks import dispatch_app_suite_execution
            execution_ids = [e.id for e in executions]
            task_id = dispatch_app_suite_execution(
                suite_id=suite.id,
                execution_ids=execution_ids,
                package_name=package_name
            )

            # 记录 task_id 到第一个执行
            if executions:
                executions[0].task_id = task_id
                executions[0].save(update_fields=['task_id'])

            logger.info(f"测试套件已提交执行: suite={suite.name}, "
                        f"cases={len(executions)}, task_id={task_id}")

            return Response({
                'success': True,
                'message': f'测试套件已提交执行，共 {len(executions)} 个用例',
                'data': {
                    'suite_id': suite.id,
                    'task_id': task_id,
                    'execution_ids': execution_ids,
                    'test_case_count': len(executions),
                }
            })

        except AppDevice.DoesNotExist:
            return Response({'success': False, 'message': '设备不存在'},
                            status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"执行套件失败: {str(e)}", exc_info=True)
            suite.execution_status = 'failed'
            suite.save(update_fields=['execution_status'])
            return Response({'success': False, 'message': f'执行失败: {str(e)}'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def executions(self, request, pk=None):
        """获取套件的执行历史"""
        suite = self.get_object()
        execs = AppTestExecution.objects.filter(test_suite=suite).order_by('-created_at')[:50]
        serializer = AppTestExecutionSerializer(execs, many=True)
        return Response({'success': True, 'data': serializer.data})
