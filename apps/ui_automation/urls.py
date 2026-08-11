from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from .views import (
    UiProjectViewSet,
    LocatorStrategyViewSet,
    ElementGroupViewSet,
    ElementViewSet,
    TestScriptViewSet,
    PageObjectViewSet,
    ScriptStepViewSet,
    TestSuiteViewSet,
    TestExecutionViewSet,
    ScreenshotViewSet,
    TestCaseViewSet,
    TestCaseStepViewSet,
    TestCaseExecutionViewSet,
    UiScheduledTaskViewSet,
    AIExecutionRecordViewSet,
    AICaseViewSet,
    UiNotificationLogViewSet,
    OperationRecordViewSet,
    UiDashboardViewSet
)
from .views_config import EnvironmentConfigViewSet, AIIntelligentModeConfigViewSet
from .views_pipeline import (
    UIActionTraceViewSet,
    RecordingSessionViewSet,
    FailureDiagnosisViewSet,
    AutoFixProposalViewSet,
)

router = DefaultRouter()
router.register(r'dashboard', UiDashboardViewSet, basename='dashboard')
router.register(r'projects', UiProjectViewSet)
router.register(r'locator-strategies', LocatorStrategyViewSet)
router.register(r'element-groups', ElementGroupViewSet)
router.register(r'elements', ElementViewSet)
router.register(r'test-scripts', TestScriptViewSet)
router.register(r'page-objects', PageObjectViewSet)
router.register(r'steps', ScriptStepViewSet)
router.register(r'test-suites', TestSuiteViewSet)
router.register(r'test-executions', TestExecutionViewSet)
router.register(r'screenshots', ScreenshotViewSet)
router.register(r'test-cases', TestCaseViewSet)
router.register(r'test-case-steps', TestCaseStepViewSet)
router.register(r'test-case-executions', TestCaseExecutionViewSet)
router.register(r'scheduled-tasks', UiScheduledTaskViewSet)
router.register(r'ai-execution-records', AIExecutionRecordViewSet)
router.register(r'ai-cases', AICaseViewSet, basename='ai-cases')
router.register(r'ai-case-generation', AICaseViewSet, basename='ai-case-generation')
router.register(r'notification-logs', UiNotificationLogViewSet)
router.register(r'operation-records', OperationRecordViewSet)
router.register(r'action-traces', UIActionTraceViewSet, basename='action-traces')
router.register(r'recording-sessions', RecordingSessionViewSet, basename='recording-sessions')
router.register(r'failure-diagnoses', FailureDiagnosisViewSet, basename='failure-diagnoses')
router.register(r'auto-fix-proposals', AutoFixProposalViewSet, basename='auto-fix-proposals')


# Configuration Center APIs
router.register(r'config/environment', EnvironmentConfigViewSet, basename='config-environment')
router.register(r'config/ai-mode', AIIntelligentModeConfigViewSet, basename='config-ai-mode')
router.register(r'ai-models', AIIntelligentModeConfigViewSet, basename='ai-models')

urlpatterns = [
    # 兼容无尾斜杠 POST，避免 APPEND_SLASH 导致 405/500
    path(
        'elements/scan-page',
        ElementViewSet.as_view({'post': 'scan_page'}),
        name='element-scan-page-noslash',
    ),
    path(
        'elements/scan-page/',
        ElementViewSet.as_view({'post': 'scan_page'}),
        name='element-scan-page-slash',
    ),
    path(
        'elements/scan-jobs',
        ElementViewSet.as_view({'get': 'scan_job_list'}),
        name='element-scan-jobs-list-noslash',
    ),
    path(
        'elements/scan-jobs/',
        ElementViewSet.as_view({'get': 'scan_job_list'}),
        name='element-scan-jobs-list-slash',
    ),
    path(
        'elements/scan-jobs/<int:job_id>',
        ElementViewSet.as_view({'get': 'scan_job_detail'}),
        name='element-scan-job-noslash',
    ),
    path(
        'elements/scan-jobs/<int:job_id>/',
        ElementViewSet.as_view({'get': 'scan_job_detail'}),
        name='element-scan-job-slash',
    ),
    path('', include(router.urls)),
]

# 添加媒体文件路由（仅 DEBUG；生产应由 Nginx/反向代理托管 media）
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
