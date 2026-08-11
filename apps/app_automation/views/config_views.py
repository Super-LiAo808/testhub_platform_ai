# -*- coding: utf-8 -*-
"""APP自动化配置管理视图"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
import logging

from ..models import AppTestConfig
from ..serializers import AppTestConfigSerializer

logger = logging.getLogger(__name__)


class AppConfigViewSet(viewsets.ViewSet):
    """APP测试配置视图集"""
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def current(self, request):
        """获取当前配置"""
        try:
            # 获取或创建配置（单例模式）
            config, created = AppTestConfig.objects.get_or_create(
                id=1,
                defaults={
                    'adb_path': 'adb',
                    'appium_server_url': 'http://127.0.0.1:4723',
                    'appium_command': 'appium',
                    'appium_auto_start': True,
                }
            )
            
            serializer = AppTestConfigSerializer(config)
            return Response({
                'success': True,
                'data': serializer.data
            })
        except Exception as e:
            logger.error(f"获取配置失败: {str(e)}")
            return Response({
                'success': False,
                'message': f'获取配置失败: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def save(self, request):
        """保存配置"""
        try:
            # 获取或创建配置（单例模式）
            config, created = AppTestConfig.objects.get_or_create(
                id=1,
                defaults={
                    'adb_path': 'adb',
                    'appium_server_url': 'http://127.0.0.1:4723',
                    'appium_command': 'appium',
                    'appium_auto_start': True,
                }
            )
            
            serializer = AppTestConfigSerializer(config, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                logger.info(f"配置更新成功: {serializer.data}")
                return Response({
                    'success': True,
                    'message': '配置更新成功',
                    'data': serializer.data
                })
            else:
                return Response({
                    'success': False,
                    'message': '配置验证失败',
                    'errors': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"更新配置失败: {str(e)}")
            return Response({
                'success': False,
                'message': f'更新配置失败: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
