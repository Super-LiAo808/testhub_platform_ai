# -*- coding: utf-8 -*-
"""APP测试用例管理视图"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.filters import SearchFilter
from django_filters.rest_framework import DjangoFilterBackend
import logging

from ..models import AppPackage, AppTestCase, AppDevice, AppTestExecution
from ..serializers import AppPackageSerializer, AppTestCaseSerializer, AppTestExecutionSerializer

logger = logging.getLogger(__name__)


class AppPagination(PageNumberPagination):
    """APP自动化模块通用分页"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class AppPackageViewSet(viewsets.ModelViewSet):
    """APP应用包名管理 ViewSet"""
    queryset = AppPackage.objects.all()
    serializer_class = AppPackageSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = AppPagination
    search_fields = ['name', 'package_name']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class AppTestCaseViewSet(viewsets.ModelViewSet):
    """APP测试用例 ViewSet"""
    queryset = AppTestCase.objects.all()
    serializer_class = AppTestCaseSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = AppPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['project', 'app_package']
    search_fields = ['name']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def execute(self, request, pk=None):
        """执行测试用例"""
        test_case = self.get_object()
        device_id = request.data.get('device_id')
        package_name = request.data.get('package_name')
        
        if not device_id:
            return Response({
                'success': False,
                'message': '请选择执行设备'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # 检查设备是否可用
            device = AppDevice.objects.get(device_id=device_id)
            if device.status == 'locked' and device.locked_by != request.user:
                return Response({
                    'success': False,
                    'message': '设备已被其他用户锁定'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # 创建执行记录
            execution = AppTestExecution.objects.create(
                test_case=test_case,
                device=device,
                user=request.user,
                status='pending'
            )
            
            # 调用 Celery（无 worker 时自动兜底本地线程）
            from ..tasks import dispatch_app_test_execution
            task_id = dispatch_app_test_execution(execution.id, package_name=package_name)
            execution.task_id = task_id
            execution.save()
            
            logger.info(f"测试已提交执行: execution_id={execution.id}, task_id={task_id}")
            
            return Response({
                'success': True,
                'message': '测试已提交执行' if not str(task_id).startswith('thread-') else '测试已提交执行（本地线程模式，未检测到 Celery worker）',
                'execution': AppTestExecutionSerializer(execution).data
            })
            
        except AppDevice.DoesNotExist:
            return Response({
                'success': False,
                'message': '设备不存在'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"执行测试失败: {str(e)}")
            return Response({
                'success': False,
                'message': f'执行测试失败: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
