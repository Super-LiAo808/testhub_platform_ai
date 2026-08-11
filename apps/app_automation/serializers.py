# -*- coding: utf-8 -*-
from rest_framework import serializers
from django.utils import timezone
from .models import (
    AppProject,
    AppTestConfig,
    AppDevice,
    AppElement,
    AppComponent,
    AppCustomComponent,
    AppComponentPackage,
    AppPackage,
    AppTestCase,
    AppTestSuite,
    AppTestSuiteCase,
    AppTestExecution,
    AppScheduledTask,
    AppNotificationLog,
)


# ========== 项目管理序列化器 ==========

class AppProjectSerializer(serializers.ModelSerializer):
    """APP项目序列化器 - 列表/详情"""
    owner_name = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()
    test_case_count = serializers.SerializerMethodField()
    test_suite_count = serializers.SerializerMethodField()

    class Meta:
        model = AppProject
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')

    def get_owner_name(self, obj):
        return obj.owner.username if obj.owner else None

    def get_member_count(self, obj):
        return obj.members.count()

    def get_test_case_count(self, obj):
        return obj.test_cases.count()

    def get_test_suite_count(self, obj):
        return obj.test_suites.count()


class AppProjectCreateSerializer(serializers.ModelSerializer):
    """APP项目创建序列化器"""
    class Meta:
        model = AppProject
        fields = ('name', 'description', 'status', 'start_date', 'end_date', 'members')
        extra_kwargs = {
            'members': {'required': False},
        }


class AppProjectUpdateSerializer(serializers.ModelSerializer):
    """APP项目更新序列化器"""
    class Meta:
        model = AppProject
        fields = ('name', 'description', 'status', 'start_date', 'end_date', 'members')


# ========== 配置序列化器 ==========

class AppTestConfigSerializer(serializers.ModelSerializer):
    """APP测试配置序列化器"""
    
    class Meta:
        model = AppTestConfig
        fields = [
            'id', 'adb_path',
            'appium_server_url', 'appium_command', 'appium_auto_start',
            'android_sdk_path',
            'scrcpy_path', 'scrcpy_server_path', 'scrcpy_max_size', 'scrcpy_bit_rate',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class AppDeviceSerializer(serializers.ModelSerializer):
    """APP设备序列化器"""
    locked_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = AppDevice
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')
    
    def get_locked_by_name(self, obj):
        return obj.locked_by.username if obj.locked_by else None


class AppElementSerializer(serializers.ModelSerializer):
    """APP元素序列化器"""
    created_by_name = serializers.SerializerMethodField()
    element_type_display = serializers.CharField(source='get_element_type_display', read_only=True)
    preview_url = serializers.SerializerMethodField()
    
    class Meta:
        model = AppElement
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at', 'usage_count', 'last_used_at')
    
    def get_created_by_name(self, obj):
        return obj.created_by.username if obj.created_by else None
    
    def get_preview_url(self, obj):
        """获取图片预览 URL"""
        if obj.element_type == 'image' and obj.config:
            image_path = obj.config.get('image_path')
            if image_path:
                from .utils.image_helpers import get_element_image_url
                return get_element_image_url(image_path)
        return None
    
    def validate_config(self, value):
        """验证配置项"""
        element_type = self.initial_data.get('element_type')
        
        if element_type == 'image':
            if not value.get('image_path'):
                raise serializers.ValidationError('图片元素必须包含 image_path 字段')
            
            # 如果有 file_hash，可以进行重复检测（在视图层处理更合适）
            file_hash = value.get('file_hash')
            if file_hash:
                # 检查是否有其他元素使用相同哈希（排除自身）
                instance_id = self.instance.id if self.instance else None
                existing = AppElement.objects.filter(
                    config__file_hash=file_hash
                ).exclude(id=instance_id).first()
                
                if existing:
                    raise serializers.ValidationError(
                        f'相同的图片已被元素 "{existing.name}" (ID: {existing.id}) 使用。'
                        f'建议复制该元素或上传不同的图片。'
                    )
        
        elif element_type == 'pos':
            # 坐标类型需要 x, y
            if 'x' not in value or 'y' not in value:
                raise serializers.ValidationError('坐标元素必须包含 x 和 y 字段')
        
        elif element_type == 'region':
            # 区域类型需要 x1, y1, x2, y2
            required_fields = ['x1', 'y1', 'x2', 'y2']
            missing_fields = [f for f in required_fields if f not in value]
            if missing_fields:
                raise serializers.ValidationError(
                    f'区域元素缺少必需字段: {", ".join(missing_fields)}'
                )
        
        return value
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        return data


class AppPackageSerializer(serializers.ModelSerializer):
    """APP应用包名序列化器"""
    created_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = AppPackage
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')
    
    def get_created_by_name(self, obj):
        return obj.created_by.username if obj.created_by else None


class AppTestCaseSerializer(serializers.ModelSerializer):
    """APP测试用例序列化器"""
    created_by_name = serializers.SerializerMethodField()
    app_package_name = serializers.CharField(source='app_package.name', read_only=True)
    
    class Meta:
        model = AppTestCase
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')
    
    def get_created_by_name(self, obj):
        return obj.created_by.username if obj.created_by else None


class AppTestExecutionSerializer(serializers.ModelSerializer):
    """APP测试执行记录序列化器"""
    case_name = serializers.CharField(read_only=True)
    device_name = serializers.CharField(read_only=True)
    user_name = serializers.CharField(read_only=True)
    pass_rate = serializers.FloatField(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    result_display = serializers.CharField(source='get_result_display', read_only=True, default=None)
    
    class Meta:
        model = AppTestExecution
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at', 'started_at', 'finished_at', 'duration')


class AppComponentSerializer(serializers.ModelSerializer):
    """UI组件定义序列化器"""
    
    class Meta:
        model = AppComponent
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')


class AppCustomComponentSerializer(serializers.ModelSerializer):
    """自定义组件定义序列化器"""
    
    class Meta:
        model = AppCustomComponent
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')


class AppComponentPackageSerializer(serializers.ModelSerializer):
    """组件包序列化器"""
    created_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = AppComponentPackage
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')
    
    def get_created_by_name(self, obj):
        return obj.created_by.username if obj.created_by else None


# ========== 测试套件序列化器 ==========

class AppTestSuiteCaseSerializer(serializers.ModelSerializer):
    """套件-用例关联序列化器"""
    test_case = serializers.SerializerMethodField()
    test_case_id = serializers.IntegerField(write_only=True, required=False)

    class Meta:
        model = AppTestSuiteCase
        fields = ('id', 'test_case', 'test_case_id', 'order')

    def get_test_case(self, obj):
        tc = obj.test_case
        return {
            'id': tc.id,
            'name': tc.name,
            'description': tc.description,
            'app_package_name': tc.app_package.name if tc.app_package else '',
            'updated_at': tc.updated_at,
        }


class AppTestSuiteSerializer(serializers.ModelSerializer):
    """测试套件列表序列化器"""
    created_by_name = serializers.SerializerMethodField()
    test_case_count = serializers.SerializerMethodField()
    suite_cases = AppTestSuiteCaseSerializer(many=True, read_only=True)
    execution_status_display = serializers.CharField(
        source='get_execution_status_display', read_only=True
    )
    execution_result_display = serializers.CharField(
        source='get_execution_result_display', read_only=True, default=None
    )

    class Meta:
        model = AppTestSuite
        fields = (
            'id', 'name', 'description', 'project',
            'execution_status', 'execution_status_display',
            'execution_result', 'execution_result_display',
            'passed_count', 'failed_count', 'last_run_at',
            'test_case_count', 'suite_cases',
            'created_by', 'created_by_name',
            'created_at', 'updated_at',
        )
        read_only_fields = (
            'created_at', 'updated_at',
            'execution_status', 'execution_result',
            'passed_count', 'failed_count', 'last_run_at',
        )

    def get_created_by_name(self, obj):
        return obj.created_by.username if obj.created_by else None

    def get_test_case_count(self, obj):
        return obj.suite_cases.count()


class AppTestSuiteCreateSerializer(serializers.ModelSerializer):
    """测试套件创建序列化器"""
    test_case_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        write_only=True,
        default=[]
    )

    class Meta:
        model = AppTestSuite
        fields = ('id', 'name', 'description', 'project', 'test_case_ids')
        read_only_fields = ('id',)

    def create(self, validated_data):
        test_case_ids = validated_data.pop('test_case_ids', [])
        suite = AppTestSuite.objects.create(**validated_data)
        for idx, tc_id in enumerate(test_case_ids):
            AppTestSuiteCase.objects.create(
                test_suite=suite,
                test_case_id=tc_id,
                order=idx
            )
        return suite


class AppTestSuiteUpdateSerializer(serializers.ModelSerializer):
    """测试套件更新序列化器"""
    class Meta:
        model = AppTestSuite
        fields = ('name', 'description', 'project')


# ========== 定时任务序列化器 ==========

class AppScheduledTaskSerializer(serializers.ModelSerializer):
    """APP定时任务序列化器"""
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    device_name = serializers.SerializerMethodField()
    app_package_name = serializers.CharField(source='app_package.name', read_only=True, default='')
    test_suite_name = serializers.CharField(source='test_suite.name', read_only=True, default='')
    test_case_name = serializers.CharField(source='test_case.name', read_only=True, default='')
    task_type_display = serializers.CharField(source='get_task_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    trigger_type_display = serializers.CharField(source='get_trigger_type_display', read_only=True)
    notification_type_display = serializers.SerializerMethodField()

    class Meta:
        model = AppScheduledTask
        fields = [
            'id', 'name', 'description', 'project',
            'task_type', 'task_type_display',
            'trigger_type', 'trigger_type_display',
            'cron_expression', 'interval_seconds', 'execute_at',
            'device', 'device_name',
            'app_package', 'app_package_name',
            'test_suite', 'test_suite_name',
            'test_case', 'test_case_name',
            'notify_on_success', 'notify_on_failure',
            'notification_type', 'notification_type_display', 'notify_emails',
            'status', 'status_display',
            'last_run_time', 'next_run_time',
            'total_runs', 'successful_runs', 'failed_runs',
            'last_result', 'error_message',
            'created_by', 'created_by_name',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'created_by', 'last_run_time', 'next_run_time',
            'total_runs', 'successful_runs', 'failed_runs',
            'last_result', 'error_message',
            'created_at', 'updated_at',
        ]

    def get_device_name(self, obj):
        if obj.device:
            return obj.device.name or obj.device.device_id
        return ''

    def get_notification_type_display(self, obj):
        return obj.get_notification_type_display() if obj.notification_type else '-'

    def validate(self, attrs):
        trigger_type = attrs.get('trigger_type')
        if trigger_type == 'CRON' and not attrs.get('cron_expression'):
            raise serializers.ValidationError('Cron表达式不能为空')
        if trigger_type == 'INTERVAL':
            if not attrs.get('interval_seconds'):
                raise serializers.ValidationError('间隔秒数不能为空')
            if attrs['interval_seconds'] < 60:
                raise serializers.ValidationError('间隔秒数不能小于60秒')
        if trigger_type == 'ONCE':
            if not attrs.get('execute_at'):
                raise serializers.ValidationError('执行时间不能为空')
            if attrs['execute_at'] <= timezone.now():
                raise serializers.ValidationError('执行时间必须大于当前时间')

        task_type = attrs.get('task_type')
        if task_type == 'TEST_SUITE' and not attrs.get('test_suite'):
            raise serializers.ValidationError('请选择测试套件')
        if task_type == 'TEST_CASE' and not attrs.get('test_case'):
            raise serializers.ValidationError('请选择测试用例')

        return attrs

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        instance = super().create(validated_data)
        instance.next_run_time = instance.calculate_next_run()
        instance.save(update_fields=['next_run_time'])
        return instance

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        instance.next_run_time = instance.calculate_next_run()
        instance.save(update_fields=['next_run_time'])
        return instance


class AppNotificationLogSerializer(serializers.ModelSerializer):
    """APP通知日志序列化器"""
    recipient_names = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    notification_type_display = serializers.CharField(source='get_notification_type_display', read_only=True)
    retry_status = serializers.SerializerMethodField()
    task_type_display = serializers.SerializerMethodField()
    actual_notification_type_display = serializers.SerializerMethodField()

    class Meta:
        model = AppNotificationLog
        fields = [
            'id', 'task', 'task_name',
            'notification_type', 'notification_type_display',
            'actual_notification_type_display', 'task_type_display',
            'sender_name', 'sender_email',
            'recipient_names', 'webhook_bot_info', 'notification_content',
            'status', 'status_display', 'error_message', 'response_info',
            'created_at', 'sent_at', 'retry_count', 'retry_status',
        ]
        read_only_fields = ['created_at', 'sent_at']

    def get_recipient_names(self, obj):
        return obj.get_recipient_names()

    def get_retry_status(self, obj):
        return obj.get_retry_status()

    def get_task_type_display(self, obj):
        if obj.task_type:
            choices = dict(AppScheduledTask.TASK_TYPE_CHOICES)
            return choices.get(obj.task_type, obj.task_type)
        return '未记录'

    def get_actual_notification_type_display(self, obj):
        if obj.webhook_bot_info:
            bot_type = obj.webhook_bot_info.get('type', '') or obj.webhook_bot_info.get('bot_type', '')
            type_map = {'wechat': '企微机器人', 'feishu': '飞书机器人', 'dingtalk': '钉钉机器人'}
            return type_map.get(bot_type, 'Webhook机器人')
        if obj.recipient_info and isinstance(obj.recipient_info, list) and len(obj.recipient_info) > 0:
            return '邮箱通知'
        return '-'
