# -*- coding: utf-8 -*-
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

from .constants import DeviceStatus, ExecutionStatus, ExecutionResult, ElementType

User = get_user_model()


class AppProject(models.Model):
    """APP自动化测试项目"""
    STATUS_CHOICES = [
        ('NOT_STARTED', '未开始'),
        ('IN_PROGRESS', '进行中'),
        ('COMPLETED', '已结束'),
    ]

    name = models.CharField(max_length=200, verbose_name='项目名称')
    description = models.TextField(blank=True, default='', verbose_name='项目描述')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='IN_PROGRESS', verbose_name='项目状态')
    start_date = models.DateField(null=True, blank=True, verbose_name='开始日期')
    end_date = models.DateField(null=True, blank=True, verbose_name='结束日期')
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='owned_app_projects', verbose_name='负责人'
    )
    members = models.ManyToManyField(
        User, blank=True,
        related_name='app_projects', verbose_name='团队成员'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'app_projects'
        verbose_name = 'APP自动化项目'
        verbose_name_plural = 'APP自动化项目'
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class AppTestConfig(models.Model):
    """APP自动化测试配置"""
    adb_path = models.CharField(
        max_length=500, 
        default='adb', 
        verbose_name='ADB路径',
        help_text='Android Debug Bridge 工具路径，默认为 adb（系统PATH）'
    )
    appium_server_url = models.CharField(
        max_length=500,
        default='http://127.0.0.1:4723',
        verbose_name='Appium Server 地址',
        help_text='Appium Server URL，默认 http://127.0.0.1:4723',
    )
    appium_command = models.CharField(
        max_length=500,
        default='appium',
        verbose_name='Appium 启动命令',
        help_text='用于平台自动拉起的命令，如 appium 或 npx appium，也可填绝对路径',
    )
    appium_auto_start = models.BooleanField(
        default=True,
        verbose_name='自动拉起 Appium',
        help_text='录制开始时若 Server 未运行则由平台自动启动（需本机已安装 Appium）',
    )
    android_sdk_path = models.CharField(
        max_length=500,
        blank=True,
        default='',
        verbose_name='Android SDK 路径',
        help_text='ANDROID_HOME；可留空，将根据 ADB 路径自动推断（需包含 platform-tools）',
    )
    scrcpy_path = models.CharField(
        max_length=500,
        blank=True,
        default='',
        verbose_name='scrcpy 路径',
        help_text='scrcpy 可执行文件或所在目录；也可通过环境变量 SCRCPY_PATH 配置',
    )
    scrcpy_server_path = models.CharField(
        max_length=500,
        blank=True,
        default='',
        verbose_name='scrcpy-server 路径',
        help_text='scrcpy-server jar；也可通过 SCRCPY_SERVER_PATH 配置',
    )
    scrcpy_max_size = models.PositiveIntegerField(
        default=1280,
        verbose_name='scrcpy 最大边长',
        help_text='投屏缩放最大边（像素），对应 SCRCPY_MAX_SIZE',
    )
    scrcpy_bit_rate = models.CharField(
        max_length=32,
        blank=True,
        default='4000000',
        verbose_name='scrcpy 码率',
        help_text='如 4000000 或 4M；对应 SCRCPY_BIT_RATE',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'app_test_config'
        verbose_name = 'APP测试配置'
        verbose_name_plural = 'APP测试配置'
    
    def __str__(self):
        return f"APP测试配置 (ADB: {self.adb_path})"


class AppDevice(models.Model):
    """Android 设备模型 - 整合了设备管理功能"""
    STATUS_CHOICES = [
        (DeviceStatus.AVAILABLE, '可用'),
        (DeviceStatus.LOCKED, '已锁定'),
        (DeviceStatus.ONLINE, '在线'),
        (DeviceStatus.OFFLINE, '离线'),
    ]
    
    CONNECTION_TYPE_CHOICES = [
        ('emulator', '本地模拟器'),
        ('remote_emulator', '远程模拟器'),
        ('real_device', '真实设备'),
    ]
    
    device_id = models.CharField(max_length=255, unique=True, verbose_name='设备序列号')
    name = models.CharField(max_length=255, blank=True, default='', verbose_name='设备名称')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=DeviceStatus.OFFLINE, verbose_name='状态')
    android_version = models.CharField(max_length=50, blank=True, default='', verbose_name='Android版本')
    connection_type = models.CharField(max_length=20, choices=CONNECTION_TYPE_CHOICES, default='emulator', verbose_name='连接类型')
    ip_address = models.CharField(max_length=50, blank=True, default='', verbose_name='IP地址')
    port = models.IntegerField(default=5555, verbose_name='端口')
    
    # 设备锁定相关字段
    locked_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='locked_app_devices', 
        verbose_name='锁定用户'
    )
    locked_at = models.DateTimeField(null=True, blank=True, verbose_name='锁定时间')
    max_allocation_time = models.IntegerField(default=28800, verbose_name='最大分配时间(秒)', help_text='默认8小时')
    
    # 设备规格信息
    device_specs = models.JSONField(default=dict, verbose_name='设备规格', help_text='RAM, CPU, 分辨率等信息')
    description = models.TextField(blank=True, default='', verbose_name='设备描述')
    location = models.CharField(max_length=200, blank=True, default='', verbose_name='设备位置')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'app_devices'
        verbose_name = 'APP测试设备'
        verbose_name_plural = 'APP测试设备'
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['device_id']),
        ]
    
    def __str__(self):
        return f"{self.name or self.device_id} ({self.get_status_display()})"
    
    def lock(self, user):
        """锁定设备"""
        self.locked_by = user
        self.locked_at = timezone.now()
        self.status = DeviceStatus.LOCKED
        self.save()
    
    def unlock(self):
        """释放设备"""
        self.locked_by = None
        self.locked_at = None
        self.status = DeviceStatus.AVAILABLE
        self.save()
    
    def is_lock_expired(self):
        """检查锁定是否过期"""
        if not self.locked_at:
            return False
        elapsed = (timezone.now() - self.locked_at).total_seconds()
        return elapsed > self.max_allocation_time


class AppElement(models.Model):
    """APP UI元素管理 - 统一管理图片、坐标、区域元素"""
    
    ELEMENT_TYPE_CHOICES = [
        (ElementType.IMAGE, '图片元素'),
        (ElementType.POS, '坐标元素'),
        (ElementType.REGION, '区域元素'),
    ]

    project = models.ForeignKey(
        AppProject, on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='elements', verbose_name='所属项目'
    )
    
    # 基础信息
    name = models.CharField(
        max_length=200,
        unique=True,
        verbose_name='元素名称',
        help_text='元素的唯一标识名称'
    )
    
    element_type = models.CharField(
        max_length=10,
        choices=ELEMENT_TYPE_CHOICES,
        verbose_name='元素类型'
    )
    
    # 标签
    tags = models.JSONField(
        default=list,
        verbose_name='标签',
        help_text='标签列表，如：["登录", "大厅", "支付"]'
    )
    
    # 元素配置（根据类型不同，内容不同）
    config = models.JSONField(
        default=dict,
        verbose_name='元素配置',
        help_text="""
        image类型: {
            "image_category": "common",
            "image_path": "common/login.png", 
            "file_hash": "abc123...",
            "image_threshold": 0.7, 
            "rgb": false
        }
        pos类型: {"x": 100, "y": 200}
        region类型: {"x1": 100, "y1": 200, "x2": 300, "y2": 400}
        """
    )
    
    # 多分辨率配置（可选）
    resolution_configs = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='分辨率配置',
        help_text='不同分辨率下的配置，如：{"1920x1080": {...}, "1280x720": {...}}'
    )
    
    # 使用统计
    usage_count = models.IntegerField(
        default=0,
        verbose_name='使用次数',
        help_text='该元素被用例引用的次数'
    )
    
    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='最后使用时间'
    )
    
    # 元数据
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_app_elements',
        verbose_name='创建人'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='更新时间'
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name='是否启用',
        help_text='软删除标记'
    )
    
    class Meta:
        db_table = 'app_elements'
        verbose_name = 'APP UI元素'
        verbose_name_plural = 'APP UI元素'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['element_type']),
            models.Index(fields=['name']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"[{self.get_element_type_display()}] {self.name}"
    
    def increment_usage(self):
        """增加使用次数"""
        self.usage_count = models.F('usage_count') + 1
        self.last_used_at = timezone.now()
        self.save(update_fields=['usage_count', 'last_used_at'])


class AppComponent(models.Model):
    """APP UI组件定义, 用于UI场景编排与校验"""
    name = models.CharField(max_length=100, verbose_name='组件名称')
    type = models.CharField(max_length=50, unique=True, verbose_name='组件类型')
    category = models.CharField(max_length=50, blank=True, default='', verbose_name='类别')
    description = models.TextField(blank=True, default='', verbose_name='描述')
    schema = models.JSONField(default=dict, verbose_name='配置Schema')
    default_config = models.JSONField(default=dict, verbose_name='默认配置')
    enabled = models.BooleanField(default=True, verbose_name='是否启用')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'app_components'
        verbose_name = 'APP组件定义'
        verbose_name_plural = 'APP组件定义'
        ordering = ['sort_order', '-updated_at']

    def __str__(self):
        return f"{self.name} ({self.type})"


class AppCustomComponent(models.Model):
    """APP UI自定义组件定义, 由基础组件组合而成"""
    name = models.CharField(max_length=100, verbose_name='组件名称')
    type = models.CharField(max_length=50, unique=True, verbose_name='组件类型')
    description = models.TextField(blank=True, default='', verbose_name='描述')
    schema = models.JSONField(default=dict, verbose_name='参数Schema')
    default_config = models.JSONField(default=dict, verbose_name='默认参数')
    steps = models.JSONField(default=list, verbose_name='组合步骤')
    enabled = models.BooleanField(default=True, verbose_name='是否启用')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'app_custom_components'
        verbose_name = 'APP自定义组件'
        verbose_name_plural = 'APP自定义组件'
        ordering = ['sort_order', '-updated_at']

    def __str__(self):
        return f"{self.name} ({self.type})"


class AppComponentPackage(models.Model):
    """APP UI组件包(用于导入/安装组件定义)"""
    SOURCE_CHOICES = [
        ('upload', '上传'),
        ('market', '市场'),
        ('local', '本地'),
    ]

    name = models.CharField(max_length=100, verbose_name='包名称')
    version = models.CharField(max_length=50, blank=True, default='', verbose_name='版本')
    description = models.TextField(blank=True, default='', verbose_name='描述')
    author = models.CharField(max_length=100, blank=True, default='', verbose_name='作者')
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='upload', verbose_name='来源')
    manifest = models.JSONField(default=dict, verbose_name='包清单')
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='created_app_packages',
        verbose_name='创建人'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'app_component_packages'
        verbose_name = 'APP组件包'
        verbose_name_plural = 'APP组件包'
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.name} ({self.version})"


class AppPackage(models.Model):
    """应用包名管理"""
    
    name = models.CharField(
        max_length=100,
        verbose_name='应用名称',
        help_text='友好的应用名称，如：Android设置'
    )
    
    package_name = models.CharField(
        max_length=255,
        unique=True,
        verbose_name='应用包名',
        help_text='Android包名，如：com.android.settings'
    )
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_app_package_names',
        verbose_name='创建人'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='更新时间'
    )
    
    class Meta:
        db_table = 'app_packages'
        verbose_name = 'APP应用包名'
        verbose_name_plural = 'APP应用包名管理'
        ordering = ['name']
        indexes = [
            models.Index(fields=['package_name']),
            models.Index(fields=['name']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.package_name})"


class AppTestSuite(models.Model):
    """APP测试套件"""
    EXECUTION_STATUS_CHOICES = [
        ('not_run', '未执行'),
        ('running', '执行中'),
        ('completed', '已完成'),
        ('error', '执行异常'),
    ]
    EXECUTION_RESULT_CHOICES = [
        ('passed', '通过'),
        ('failed', '失败'),
        ('skipped', '跳过'),
    ]

    project = models.ForeignKey(
        AppProject, on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='test_suites', verbose_name='所属项目'
    )
    name = models.CharField(max_length=200, verbose_name='套件名称')
    description = models.TextField(blank=True, default='', verbose_name='套件描述')
    test_cases = models.ManyToManyField(
        'AppTestCase',
        through='AppTestSuiteCase',
        verbose_name='测试用例',
        blank=True
    )

    # 执行统计
    execution_status = models.CharField(
        max_length=20,
        choices=EXECUTION_STATUS_CHOICES,
        default='not_run',
        verbose_name='执行状态'
    )
    execution_result = models.CharField(
        max_length=20,
        choices=EXECUTION_RESULT_CHOICES,
        null=True,
        blank=True,
        default=None,
        verbose_name='测试结果'
    )
    passed_count = models.IntegerField(default=0, verbose_name='通过用例数')
    failed_count = models.IntegerField(default=0, verbose_name='失败用例数')
    last_run_at = models.DateTimeField(null=True, blank=True, verbose_name='最后执行时间')

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_app_test_suites',
        verbose_name='创建人'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'app_test_suites'
        verbose_name = 'APP测试套件'
        verbose_name_plural = 'APP测试套件'
        ordering = ['-updated_at']

    def __str__(self):
        return self.name

    @property
    def test_case_count(self):
        return self.suite_cases.count()


class AppTestSuiteCase(models.Model):
    """APP测试套件与用例的关联模型"""
    test_suite = models.ForeignKey(
        AppTestSuite,
        on_delete=models.CASCADE,
        related_name='suite_cases',
        verbose_name='测试套件'
    )
    test_case = models.ForeignKey(
        'AppTestCase',
        on_delete=models.CASCADE,
        related_name='suite_memberships',
        verbose_name='测试用例'
    )
    order = models.IntegerField(default=0, verbose_name='执行顺序')

    class Meta:
        db_table = 'app_test_suite_cases'
        verbose_name = 'APP套件用例关联'
        verbose_name_plural = 'APP套件用例关联'
        ordering = ['order']
        unique_together = ['test_suite', 'test_case']

    def __str__(self):
        return f'{self.test_suite.name} - {self.test_case.name}'


class AppTestCase(models.Model):
    """APP测试用例"""
    project = models.ForeignKey(
        AppProject, on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='test_cases', verbose_name='所属项目'
    )
    name = models.CharField(max_length=200, verbose_name='用例名称')
    description = models.TextField(blank=True, default='', verbose_name='用例描述')
    app_package = models.ForeignKey(
        AppPackage, 
        on_delete=models.CASCADE, 
        related_name='test_cases',
        null=True,
        blank=True,
        verbose_name='应用包名'
    )
    ui_flow = models.JSONField(default=dict, verbose_name='UI流程定义', help_text='UI Flow JSON配置')
    variables = models.JSONField(default=list, verbose_name='变量定义', help_text='测试变量列表')
    
    # 用例配置
    timeout = models.IntegerField(default=300, verbose_name='超时时间(秒)', help_text='默认5分钟')
    retry_count = models.IntegerField(default=0, verbose_name='失败重试次数')
    
    # 元数据
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_app_test_cases',
        verbose_name='创建人'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'app_test_cases'
        verbose_name = 'APP测试用例'
        verbose_name_plural = 'APP测试用例'
        ordering = ['-updated_at']
    
    def __str__(self):
        return self.name


class AppTestExecution(models.Model):
    """APP测试执行记录"""
    STATUS_CHOICES = [
        (ExecutionStatus.PENDING, '等待中'),
        (ExecutionStatus.RUNNING, '执行中'),
        (ExecutionStatus.COMPLETED, '已完成'),
        (ExecutionStatus.ERROR, '执行异常'),
        (ExecutionStatus.STOPPED, '已停止'),
    ]

    RESULT_CHOICES = [
        (ExecutionResult.PASSED, '通过'),
        (ExecutionResult.FAILED, '失败'),
        (ExecutionResult.SKIPPED, '跳过'),
    ]
    
    test_case = models.ForeignKey(
        AppTestCase, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='executions', 
        verbose_name='测试用例'
    )
    test_suite = models.ForeignKey(
        AppTestSuite,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='executions',
        verbose_name='所属套件'
    )
    device = models.ForeignKey(
        AppDevice, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='executions', 
        verbose_name='执行设备'
    )
    user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='app_test_executions', 
        verbose_name='执行用户'
    )
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default=ExecutionStatus.PENDING, 
        verbose_name='执行状态'
    )
    result = models.CharField(
        max_length=20,
        choices=RESULT_CHOICES,
        null=True,
        blank=True,
        default=None,
        verbose_name='测试结果'
    )
    task_id = models.CharField(
        max_length=255, 
        blank=True, 
        default='', 
        verbose_name='Celery任务ID', 
        help_text='用于停止任务'
    )
    progress = models.IntegerField(default=0, verbose_name='执行进度(0-100)')
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='开始时间')
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name='结束时间')
    duration = models.FloatField(default=0, verbose_name='执行时长(秒)')
    report_path = models.CharField(max_length=500, blank=True, default='', verbose_name='Allure报告路径')
    error_message = models.TextField(blank=True, default='', verbose_name='错误信息')
    
    # 执行结果统计
    total_steps = models.IntegerField(default=0, verbose_name='总步骤数')
    passed_steps = models.IntegerField(default=0, verbose_name='通过步骤数')
    failed_steps = models.IntegerField(default=0, verbose_name='失败步骤数')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'app_test_executions'
        verbose_name = 'APP测试执行记录'
        verbose_name_plural = 'APP测试执行记录'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"{self.test_case.name} - {self.get_status_display()}"
    
    @property
    def case_name(self):
        """用例名称"""
        if self.test_case_id and self.test_case:
            return self.test_case.name
        if self.test_suite_id and self.test_suite:
            return f'[套件] {self.test_suite.name}'
        return ''
    
    @property
    def device_name(self):
        """设备名称"""
        if not self.device_id or not self.device:
            return ''
        return self.device.name or self.device.device_id or ''
    
    @property
    def user_name(self):
        """用户名"""
        return self.user.username if self.user else ''
    
    @property
    def pass_rate(self):
        """通过率"""
        if self.total_steps == 0:
            return 0
        return round((self.passed_steps / self.total_steps) * 100, 2)


class AppScheduledTask(models.Model):
    """APP自动化定时任务"""
    TASK_TYPE_CHOICES = [
        ('TEST_SUITE', '测试套件执行'),
        ('TEST_CASE', '测试用例执行'),
    ]
    STATUS_CHOICES = [
        ('ACTIVE', '激活'),
        ('PAUSED', '暂停'),
        ('COMPLETED', '已完成'),
        ('FAILED', '失败'),
    ]
    TRIGGER_TYPE_CHOICES = [
        ('CRON', 'Cron表达式'),
        ('INTERVAL', '固定间隔'),
        ('ONCE', '单次执行'),
    ]
    NOTIFICATION_TYPE_CHOICES = [
        ('email', '邮箱通知'),
        ('webhook', 'Webhook机器人'),
        ('both', '两者都发送'),
    ]

    project = models.ForeignKey(
        'AppProject', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='scheduled_tasks', verbose_name='所属项目'
    )
    name = models.CharField(max_length=200, verbose_name='任务名称')
    description = models.TextField(blank=True, default='', verbose_name='任务描述')
    task_type = models.CharField(max_length=20, choices=TASK_TYPE_CHOICES, verbose_name='任务类型')
    trigger_type = models.CharField(max_length=20, choices=TRIGGER_TYPE_CHOICES, verbose_name='触发器类型')

    # 调度配置
    cron_expression = models.CharField(max_length=100, blank=True, default='', verbose_name='Cron表达式')
    interval_seconds = models.IntegerField(null=True, blank=True, verbose_name='间隔秒数')
    execute_at = models.DateTimeField(null=True, blank=True, verbose_name='执行时间')

    # APP 特有配置
    device = models.ForeignKey(
        AppDevice, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='scheduled_tasks', verbose_name='执行设备'
    )
    app_package = models.ForeignKey(
        AppPackage, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='scheduled_tasks', verbose_name='应用包名'
    )
    test_suite = models.ForeignKey(
        AppTestSuite, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='scheduled_tasks', verbose_name='测试套件'
    )
    test_case = models.ForeignKey(
        AppTestCase, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='scheduled_tasks', verbose_name='测试用例'
    )

    # 通知配置
    notify_on_success = models.BooleanField(default=False, verbose_name='成功时通知')
    notify_on_failure = models.BooleanField(default=False, verbose_name='失败时通知')
    notification_type = models.CharField(
        max_length=20, blank=True, default='',
        choices=NOTIFICATION_TYPE_CHOICES, verbose_name='通知类型'
    )
    notify_emails = models.JSONField(default=list, blank=True, verbose_name='通知邮箱列表')

    # 状态与统计
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE', verbose_name='任务状态')
    last_run_time = models.DateTimeField(null=True, blank=True, verbose_name='最后运行时间')
    next_run_time = models.DateTimeField(null=True, blank=True, verbose_name='下次运行时间')
    total_runs = models.IntegerField(default=0, verbose_name='总运行次数')
    successful_runs = models.IntegerField(default=0, verbose_name='成功次数')
    failed_runs = models.IntegerField(default=0, verbose_name='失败次数')
    last_result = models.JSONField(default=dict, verbose_name='最后执行结果')
    error_message = models.TextField(blank=True, default='', verbose_name='错误信息')

    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='创建者')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'app_scheduled_tasks'
        verbose_name = 'APP定时任务'
        verbose_name_plural = 'APP定时任务'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.get_task_type_display()})"

    def calculate_next_run(self):
        from datetime import timedelta
        from croniter import croniter
        now = timezone.now()
        if self.trigger_type == 'CRON' and self.cron_expression:
            try:
                cron = croniter(self.cron_expression, now)
                return cron.get_next(type(now))
            except Exception:
                return None
        elif self.trigger_type == 'INTERVAL' and self.interval_seconds:
            return now + timedelta(seconds=self.interval_seconds)
        elif self.trigger_type == 'ONCE' and self.execute_at:
            return self.execute_at if self.execute_at > now else None
        return None

    def should_run_now(self):
        if self.status != 'ACTIVE':
            return False
        if not self.next_run_time:
            return False
        return timezone.now() >= self.next_run_time


class AppNotificationLog(models.Model):
    """APP自动化通知日志"""
    NOTIFICATION_TYPES = [
        ('task_execution', '定时任务执行'),
        ('test_suite_execution', '测试套件执行'),
        ('system_alert', '系统警告'),
        ('manual', '手动通知'),
    ]
    STATUS_CHOICES = [
        ('pending', '待发送'),
        ('sending', '发送中'),
        ('success', '发送成功'),
        ('failed', '发送失败'),
        ('cancelled', '已取消'),
    ]

    task = models.ForeignKey(
        AppScheduledTask, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='notification_logs', verbose_name='关联任务'
    )
    task_name = models.CharField(max_length=200, verbose_name='任务名称')
    task_type = models.CharField(max_length=20, blank=True, default='', verbose_name='任务类型快照')
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES, verbose_name='通知类型')
    sender_name = models.CharField(max_length=100, verbose_name='发件人姓名')
    sender_email = models.EmailField(verbose_name='发件人邮箱')
    recipient_info = models.JSONField(default=list, verbose_name='收件人信息')
    webhook_bot_info = models.JSONField(default=dict, blank=True, verbose_name='Webhook机器人信息')
    notification_content = models.TextField(verbose_name='通知内容')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='发送状态')
    error_message = models.TextField(blank=True, default='', verbose_name='错误信息')
    response_info = models.JSONField(default=dict, blank=True, verbose_name='响应信息')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name='发送时间')
    retry_count = models.IntegerField(default=0, verbose_name='重试次数')
    is_retried = models.BooleanField(default=False, verbose_name='是否已重试')

    class Meta:
        db_table = 'app_notification_logs'
        verbose_name = 'APP通知日志'
        verbose_name_plural = 'APP通知日志'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['notification_type']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.task_name} - {self.get_notification_type_display()} - {self.status}"

    def get_recipient_names(self):
        if not self.recipient_info:
            return '未知收件人'
        if isinstance(self.recipient_info, list):
            names = []
            for rec in self.recipient_info:
                email = rec.get('email', '')
                name = rec.get('name', '')
                names.append(f"{name}({email})" if name and email else (email or name or '未知'))
            return ', '.join(names)
        return '未知收件人'

    def get_retry_status(self):
        return f"已重试 {self.retry_count} 次" if self.is_retried else "未重试"


class AppRecordingSession(models.Model):
    """APP 操作录制会话（实时投屏 + 手势同步）"""
    STATUS_CHOICES = [
        ('idle', '空闲'),
        ('recording', '录制中'),
        ('stopped', '已停止'),
        ('failed', '失败'),
    ]

    project = models.ForeignKey(
        AppProject, on_delete=models.CASCADE,
        related_name='recording_sessions', verbose_name='所属项目'
    )
    device = models.ForeignKey(
        AppDevice, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='recording_sessions', verbose_name='录制设备'
    )
    name = models.CharField(max_length=200, blank=True, default='', verbose_name='会话名称')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='idle', verbose_name='状态')
    ui_flow = models.JSONField(default=list, blank=True, verbose_name='录制步骤')
    screen_width = models.IntegerField(default=0, verbose_name='设备宽度')
    screen_height = models.IntegerField(default=0, verbose_name='设备高度')
    error_message = models.TextField(blank=True, default='', verbose_name='错误信息')
    test_case = models.ForeignKey(
        'AppTestCase', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='from_recordings', verbose_name='生成用例'
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='创建人'
    )
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='开始时间')
    stopped_at = models.DateTimeField(null=True, blank=True, verbose_name='结束时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'app_recording_sessions'
        verbose_name = 'APP录制会话'
        verbose_name_plural = 'APP录制会话'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name or self.id} ({self.status})'
