# -*- coding: utf-8 -*-
"""
APP自动化测试 Views 包
"""
from .project_views import AppProjectViewSet
from .config_views import AppConfigViewSet
from .device_views import AppDeviceViewSet
from .element_views import AppElementViewSet
from .component_views import (
    AppComponentViewSet,
    AppCustomComponentViewSet,
    AppComponentPackageViewSet,
)
from .test_case_views import (
    AppPackageViewSet,
    AppTestCaseViewSet,
)
from .execution_views import AppTestExecutionViewSet
from .suite_views import AppTestSuiteViewSet
from .scheduled_task_views import AppScheduledTaskViewSet, AppNotificationLogViewSet
from .dashboard_views import AppDashboardViewSet
from .recording_views import AppRecordingSessionViewSet

__all__ = [
    'AppProjectViewSet',
    'AppConfigViewSet',
    'AppDeviceViewSet',
    'AppElementViewSet',
    'AppComponentViewSet',
    'AppCustomComponentViewSet',
    'AppComponentPackageViewSet',
    'AppPackageViewSet',
    'AppTestCaseViewSet',
    'AppTestSuiteViewSet',
    'AppScheduledTaskViewSet',
    'AppNotificationLogViewSet',
    'AppTestExecutionViewSet',
    'AppDashboardViewSet',
    'AppRecordingSessionViewSet',
]
