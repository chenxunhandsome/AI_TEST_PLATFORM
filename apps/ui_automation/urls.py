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
    PageGraphViewSet,
    PageObjectViewSet,
    ScriptStepViewSet,
    TestSuiteViewSet,
    TestExecutionViewSet,
    ScreenshotViewSet,
    TestCaseFolderViewSet,
    TestCaseViewSet,
    TestCaseStepViewSet,
    TestCaseExecutionViewSet,
    UiScheduledTaskViewSet,
    AIExecutionRecordViewSet,
    AICaseViewSet,
    AITestCaseGenerationSkillCategoryViewSet,
    AITestCaseGenerationSkillDependencyViewSet,
    AITestCaseGenerationSkillExecutionLogViewSet,
    AITestCaseGenerationSkillModuleViewSet,
    AITestCaseGenerationSkillTriggerViewSet,
    AITestCaseGenerationSkillViewSet,
    AITestCaseGenerationViewSet,
    UiNotificationLogViewSet,
    OperationRecordViewSet,
    UiDashboardViewSet,
    UIPageEdgeViewSet,
    UIPageElementViewSet,
    UIPageGraphViewSet,
    UIPageNodeViewSet,
    start_scroll_coordinate_picker,
    get_scroll_coordinate_picker_position,
    get_scroll_coordinate_picker_pages,
    set_scroll_coordinate_picker_active_page,
    close_scroll_coordinate_picker,
)
from .views_config import EnvironmentConfigViewSet, AIIntelligentModeConfigViewSet
from .local_runner_views import LocalRunnerViewSet

router = DefaultRouter()
router.register(r'dashboard', UiDashboardViewSet, basename='dashboard')
router.register(r'projects', UiProjectViewSet)
router.register(r'locator-strategies', LocatorStrategyViewSet)
router.register(r'page-graphs', UIPageGraphViewSet, basename='page-graphs')
router.register(r'page-graph-nodes', UIPageNodeViewSet, basename='page-graph-nodes')
router.register(r'page-graph-elements', UIPageElementViewSet, basename='page-graph-elements')
router.register(r'page-graph-edges', UIPageEdgeViewSet, basename='page-graph-edges')
router.register(r'element-groups', ElementGroupViewSet)
router.register(r'elements', ElementViewSet)
router.register(r'test-scripts', TestScriptViewSet)
router.register(r'page-graphs', PageGraphViewSet, basename='page-graphs')
router.register(r'page-objects', PageObjectViewSet)
router.register(r'steps', ScriptStepViewSet)
router.register(r'test-suites', TestSuiteViewSet)
router.register(r'test-executions', TestExecutionViewSet)
router.register(r'screenshots', ScreenshotViewSet)
router.register(r'test-case-folders', TestCaseFolderViewSet, basename='test-case-folders')
router.register(r'test-cases', TestCaseViewSet)
router.register(r'test-case-steps', TestCaseStepViewSet)
router.register(r'test-case-executions', TestCaseExecutionViewSet)
router.register(r'scheduled-tasks', UiScheduledTaskViewSet)
router.register(r'ai-execution-records', AIExecutionRecordViewSet)
router.register(r'ai-cases', AICaseViewSet, basename='ai-cases')
router.register(r'ai-case-generation', AICaseViewSet, basename='ai-case-generation')
router.register(r'ai-test-case-generation-skills', AITestCaseGenerationSkillViewSet, basename='ai-test-case-generation-skills')
router.register(r'ai-test-case-generation-skill-categories', AITestCaseGenerationSkillCategoryViewSet, basename='ai-test-case-generation-skill-categories')
router.register(r'ai-test-case-generation-skill-modules', AITestCaseGenerationSkillModuleViewSet, basename='ai-test-case-generation-skill-modules')
router.register(r'ai-test-case-generation-skill-triggers', AITestCaseGenerationSkillTriggerViewSet, basename='ai-test-case-generation-skill-triggers')
router.register(r'ai-test-case-generation-skill-dependencies', AITestCaseGenerationSkillDependencyViewSet, basename='ai-test-case-generation-skill-dependencies')
router.register(r'ai-test-case-generation-skill-logs', AITestCaseGenerationSkillExecutionLogViewSet, basename='ai-test-case-generation-skill-logs')
router.register(r'ai-test-case-generation', AITestCaseGenerationViewSet, basename='ai-test-case-generation')
router.register(r'notification-logs', UiNotificationLogViewSet)
router.register(r'operation-records', OperationRecordViewSet)
router.register(r'local-runners', LocalRunnerViewSet, basename='local-runners')


# Configuration Center APIs
router.register(r'config/environment', EnvironmentConfigViewSet, basename='config-environment')
router.register(r'config/ai-mode', AIIntelligentModeConfigViewSet, basename='config-ai-mode')
router.register(r'ai-models', AIIntelligentModeConfigViewSet, basename='ai-models')

urlpatterns = [
    path('scroll-coordinate-picker/start/', start_scroll_coordinate_picker),
    path('scroll-coordinate-picker/position/', get_scroll_coordinate_picker_position),
    path('scroll-coordinate-picker/pages/', get_scroll_coordinate_picker_pages),
    path('scroll-coordinate-picker/active-page/', set_scroll_coordinate_picker_active_page),
    path('scroll-coordinate-picker/close/', close_scroll_coordinate_picker),
    path('', include(router.urls)),
]

# 添加媒体文件路由
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
