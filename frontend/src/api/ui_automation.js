import request from '@/utils/api'

// 仪表盘相关API
export function getDashboardStats() {
  return request({
    url: '/ui-automation/dashboard/stats/',
    method: 'get'
  })
}

// UI项目相关API

// 获取UI项目列表
export function getUiProjects(params) {
  return request({
    url: '/ui-automation/projects/',
    method: 'get',
    params
  })
}

// 创建UI项目
export function createUiProject(data) {
  return request({
    url: '/ui-automation/projects/',
    method: 'post',
    data
  })
}

// 获取UI项目详情
export function getUiProjectDetail(id) {
  return request({
    url: `/ui-automation/projects/${id}/`,
    method: 'get'
  })
}

// 更新UI项目
export function updateUiProject(id, data) {
  return request({
    url: `/ui-automation/projects/${id}/`,
    method: 'patch',
    data
  })
}

// 删除UI项目
export function deleteUiProject(id) {
  return request({
    url: `/ui-automation/projects/${id}/`,
    method: 'delete'
  })
}

// 定位策略相关API

// 获取定位策略列表
export function getLocatorStrategies(params) {
  return request({
    url: '/ui-automation/locator-strategies/',
    method: 'get',
    params
  })
}

// 创建定位策略
export function createLocatorStrategy(data) {
  return request({
    url: '/ui-automation/locator-strategies/',
    method: 'post',
    data
  })
}

// UI元素相关API

// 获取UI元素列表
export function getElements(params) {
  return request({
    url: '/ui-automation/elements/',
    method: 'get',
    params
  })
}

// 创建UI元素
export function createElement(data) {
  return request({
    url: '/ui-automation/elements/',
    method: 'post',
    data
  })
}

// 获取UI元素详情
export function getElementDetail(id) {
  return request({
    url: `/ui-automation/elements/${id}/`,
    method: 'get'
  })
}

// 更新UI元素
export function updateElement(id, data) {
  return request({
    url: `/ui-automation/elements/${id}/`,
    method: 'patch',
    data
  })
}

// 删除UI元素
export function deleteElement(id) {
  return request({
    url: `/ui-automation/elements/${id}/`,
    method: 'delete'
  })
}

// 测试脚本相关API

// 获取测试脚本列表
export function getTestScripts(params) {
  return request({
    url: '/ui-automation/test-scripts/',
    method: 'get',
    params
  })
}

// 创建测试脚本
export function createTestScript(data) {
  return request({
    url: '/ui-automation/test-scripts/',
    method: 'post',
    data
  })
}

// 获取测试脚本详情
export function getTestScriptDetail(id) {
  return request({
    url: `/ui-automation/test-scripts/${id}/`,
    method: 'get'
  })
}

// 更新测试脚本
export function updateTestScript(id, data) {
  return request({
    url: `/ui-automation/test-scripts/${id}/`,
    method: 'patch',
    data
  })
}

// 删除测试脚本
export function deleteTestScript(id) {
  return request({
    url: `/ui-automation/test-scripts/${id}/`,
    method: 'delete'
  })
}

// 测试套件相关API

// 获取测试套件列表
export function getTestSuites(params) {
  return request({
    url: '/ui-automation/test-suites/',
    method: 'get',
    params
  })
}

// 创建测试套件
export function createTestSuite(data) {
  return request({
    url: '/ui-automation/test-suites/',
    method: 'post',
    data
  })
}

// 获取测试套件详情
export function getTestSuiteDetail(id) {
  return request({
    url: `/ui-automation/test-suites/${id}/`,
    method: 'get'
  })
}

// 更新测试套件
export function updateTestSuite(id, data) {
  return request({
    url: `/ui-automation/test-suites/${id}/`,
    method: 'patch',
    data
  })
}

// 删除测试套件
export function deleteTestSuite(id) {
  return request({
    url: `/ui-automation/test-suites/${id}/`,
    method: 'delete'
  })
}

// 获取测试套件中的测试用例
export function getTestSuiteTestCases(id) {
  return request({
    url: `/ui-automation/test-suites/${id}/test_cases/`,
    method: 'get'
  })
}

// 向测试套件添加测试用例
export function addTestCaseToTestSuite(id, data) {
  return request({
    url: `/ui-automation/test-suites/${id}/add_test_case/`,
    method: 'post',
    data
  })
}

// 从测试套件移除测试用例
export function removeTestCaseFromTestSuite(suiteId, testCaseId) {
  return request({
    url: `/ui-automation/test-suites/${suiteId}/remove_test_case/`,
    method: 'delete',
    data: { test_case_id: testCaseId }
  })
}

// 更新测试套件中测试用例的顺序
export function updateTestCaseOrder(suiteId, testCaseOrders) {
  return request({
    url: `/ui-automation/test-suites/${suiteId}/update_test_case_order/`,
    method: 'post',
    data: { test_case_orders: testCaseOrders }
  })
}

// 运行测试套件
export function runTestSuite(suiteId, data) {
  return request({
    url: `/ui-automation/test-suites/${suiteId}/run_suite/`,
    method: 'post',
    data,
    timeout: 600000  // 10分钟超时，因为套件可能包含多个测试用例
  })
}

// 测试执行相关API

// 获取测试执行列表
export function getTestExecutions(params) {
  return request({
    url: '/ui-automation/test-executions/',
    method: 'get',
    params
  })
}

// 创建测试执行
export function createTestExecution(data) {
  return request({
    url: '/ui-automation/test-executions/',
    method: 'post',
    data
  })
}

// 获取测试执行详情
export function getTestExecutionDetail(id) {
  return request({
    url: `/ui-automation/test-executions/${id}/`,
    method: 'get'
  })
}

// 删除测试执行记录
export function deleteTestExecution(id) {
  return request({
    url: `/ui-automation/test-executions/${id}/`,
    method: 'delete'
  })
}

// 运行测试执行
export function runTestExecution(id) {
  return request({
    url: `/ui-automation/test-executions/${id}/run/`,
    method: 'post'
  })
}

// 中止测试执行
export function abortTestExecution(id) {
  return request({
    url: `/ui-automation/test-executions/${id}/abort/`,
    method: 'post'
  })
}

// 测试环境相关API

// 获取测试环境列表
export function getTestEnvironments(params) {
  return request({
    url: '/ui-automation/test-environments/',
    method: 'get',
    params
  })
}

// 创建测试环境
export function createTestEnvironment(data) {
  return request({
    url: '/ui-automation/test-environments/',
    method: 'post',
    data
  })
}

// 获取测试环境详情
export function getTestEnvironmentDetail(id) {
  return request({
    url: `/ui-automation/test-environments/${id}/`,
    method: 'get'
  })
}

// 更新测试环境
export function updateTestEnvironment(id, data) {
  return request({
    url: `/ui-automation/test-environments/${id}/`,
    method: 'patch',
    data
  })
}

// 删除测试环境
export function deleteTestEnvironment(id) {
  return request({
    url: `/ui-automation/test-environments/${id}/`,
    method: 'delete'
  })
}

// 截图相关API

// 获取截图列表
export function getScreenshots(params) {
  return request({
    url: '/ui-automation/screenshots/',
    method: 'get',
    params
  })
}

// 创建截图
export function createScreenshot(data) {
  return request({
    url: '/ui-automation/screenshots/',
    method: 'post',
    data
  })
}

// 获取截图详情
export function getScreenshotDetail(id) {
  return request({
    url: `/ui-automation/screenshots/${id}/`,
    method: 'get'
  })
}

// 删除截图
export function deleteScreenshot(id) {
  return request({
    url: `/ui-automation/screenshots/${id}/`,
    method: 'delete'
  })
}

// ============ 新增功能API ============

// 元素分组相关API
export function getElementGroups(params) {
  return request({
    url: '/ui-automation/element-groups/',
    method: 'get',
    params
  })
}

export function createElementGroup(data) {
  return request({
    url: '/ui-automation/element-groups/',
    method: 'post',
    data
  })
}

export function getElementGroupDetail(id) {
  return request({
    url: `/ui-automation/element-groups/${id}/`,
    method: 'get'
  })
}

export function updateElementGroup(id, data) {
  return request({
    url: `/ui-automation/element-groups/${id}/`,
    method: 'patch',
    data
  })
}

export function deleteElementGroup(id) {
  return request({
    url: `/ui-automation/element-groups/${id}/`,
    method: 'delete'
  })
}

export function getElementGroupTree(params) {
  return request({
    url: '/ui-automation/element-groups/tree/',
    method: 'get',
    params
  })
}

// 元素增强功能API
export function validateElementLocator(id) {
  return request({
    url: `/ui-automation/elements/${id}/validate_locator/`,
    method: 'post'
  })
}

export function getElementUsages(id) {
  return request({
    url: `/ui-automation/elements/${id}/usages/`,
    method: 'get'
  })
}

export function getElementTree(params) {
  return request({
    url: '/ui-automation/elements/tree/',
    method: 'get',
    params
  })
}

export function addBackupLocator(id, data) {
  return request({
    url: `/ui-automation/elements/${id}/add_backup_locator/`,
    method: 'post',
    data
  })
}

export function generateElementSuggestions(id) {
  return request({
    url: `/ui-automation/elements/${id}/generate_suggestions/`,
    method: 'post'
  })
}

/** 提交页面元素扫描异步任务（兼容旧版同步接口，超时放宽） */
export function scanPageElements(data) {
  return request({
    url: '/ui-automation/elements/scan-page/',
    method: 'post',
    data,
    timeout: 60000
  })
}

/** 查询页面扫描任务状态 */
export function getPageScanJob(jobId) {
  return request({
    url: `/ui-automation/elements/scan-jobs/${jobId}/`,
    method: 'get',
    timeout: 30000
  })
}

/** 页面扫描任务列表 */
export function listPageScanJobs(params) {
  return request({
    url: '/ui-automation/elements/scan-jobs/',
    method: 'get',
    params,
    timeout: 30000
  })
}

// 页面对象相关API
export function getPageObjects(params) {
  return request({
    url: '/ui-automation/page-objects/',
    method: 'get',
    params
  })
}

export function createPageObject(data) {
  return request({
    url: '/ui-automation/page-objects/',
    method: 'post',
    data
  })
}

export function getPageObjectDetail(id) {
  return request({
    url: `/ui-automation/page-objects/${id}/`,
    method: 'get'
  })
}

export function updatePageObject(id, data) {
  return request({
    url: `/ui-automation/page-objects/${id}/`,
    method: 'patch',
    data
  })
}

export function deletePageObject(id) {
  return request({
    url: `/ui-automation/page-objects/${id}/`,
    method: 'delete'
  })
}

export function generatePageObjectCode(id, data) {
  return request({
    url: `/ui-automation/page-objects/${id}/generate_code/`,
    method: 'post',
    data
  })
}

export function addElementToPageObject(id, data) {
  return request({
    url: `/ui-automation/page-objects/${id}/add_element/`,
    method: 'post',
    data
  })
}

export function getPageObjectElements(id) {
  return request({
    url: `/ui-automation/page-objects/${id}/elements/`,
    method: 'get'
  })
}

// 页面对象元素关联API
export function getPageObjectElementDetails(params) {
  return request({
    url: '/ui-automation/page-object-elements/',
    method: 'get',
    params
  })
}

export function createPageObjectElement(data) {
  return request({
    url: '/ui-automation/page-object-elements/',
    method: 'post',
    data
  })
}

export function updatePageObjectElement(id, data) {
  return request({
    url: `/ui-automation/page-object-elements/${id}/`,
    method: 'patch',
    data
  })
}

export function deletePageObjectElement(id) {
  return request({
    url: `/ui-automation/page-object-elements/${id}/`,
    method: 'delete'
  })
}

// 脚本步骤相关API
export function getScriptSteps(params) {
  return request({
    url: '/ui-automation/script-steps/',
    method: 'get',
    params
  })
}

export function createScriptStep(data) {
  return request({
    url: '/ui-automation/script-steps/',
    method: 'post',
    data
  })
}

export function batchCreateScriptSteps(data) {
  return request({
    url: '/ui-automation/script-steps/batch_create/',
    method: 'post',
    data
  })
}

export function updateScriptStep(id, data) {
  return request({
    url: `/ui-automation/script-steps/${id}/`,
    method: 'patch',
    data
  })
}

export function deleteScriptStep(id) {
  return request({
    url: `/ui-automation/script-steps/${id}/`,
    method: 'delete'
  })
}

// 脚本元素使用情况API
export function getScriptElementUsages(params) {
  return request({
    url: '/ui-automation/script-element-usages/',
    method: 'get',
    params
  })
}

export function analyzeScriptElements(data) {
  return request({
    url: '/ui-automation/script-element-usages/analyze_script/',
    method: 'post',
    data
  })
}

export function createScriptElementUsage(data) {
  return request({
    url: '/ui-automation/script-element-usages/',
    method: 'post',
    data
  })
}

export function updateScriptElementUsage(id, data) {
  return request({
    url: `/ui-automation/script-element-usages/${id}/`,
    method: 'patch',
    data
  })
}

export function deleteScriptElementUsage(id) {
  return request({
    url: `/ui-automation/script-element-usages/${id}/`,
    method: 'delete'
  })
}

// 测试用例相关API

// 获取测试用例列表
export function getTestCases(params) {
  return request({
    url: '/ui-automation/test-cases/',
    method: 'get',
    params
  })
}

// 创建测试用例
export function createTestCase(data) {
  return request({
    url: '/ui-automation/test-cases/',
    method: 'post',
    data
  })
}

// 获取测试用例详情
export function getTestCaseDetail(id) {
  return request({
    url: `/ui-automation/test-cases/${id}/`,
    method: 'get'
  })
}

// 更新测试用例
export function updateTestCase(id, data) {
  return request({
    url: `/ui-automation/test-cases/${id}/`,
    method: 'patch',
    data
  })
}

// 删除测试用例
export function deleteTestCase(id) {
  return request({
    url: `/ui-automation/test-cases/${id}/`,
    method: 'delete'
  })
}

// 运行测试用例
export function runTestCase(testCaseId, data) {
  return request({
    url: `/ui-automation/test-cases/${testCaseId}/run/`,
    method: 'post',
    data,
    timeout: 300000  // 5分钟超时，因为测试执行需要启动浏览器和执行多个步骤
  })
}

// 复制测试用例
export function copyTestCase(id) {
  return request({
    url: `/ui-automation/test-cases/${id}/copy_case/`,
    method: 'post'
  })
}

// 获取测试用例执行历史
export function getTestCaseExecutions(params) {
  return request({
    url: '/ui-automation/test-case-executions/',
    method: 'get',
    params
  })
}

// 删除测试用例执行记录
export function deleteTestCaseExecution(id) {
  return request({
    url: `/ui-automation/test-case-executions/${id}/`,
    method: 'delete'
  })
}

// 批量删除测试用例执行记录
export function batchDeleteTestCaseExecutions(ids) {
  return request({
    url: '/ui-automation/test-case-executions/batch-delete/',
    method: 'post',
    data: { ids }
  })
}

// 批量运行测试用例
export function batchRunTestCases(data) {
  return request({
    url: '/ui-automation/test-cases/batch-run/',
    method: 'post',
    data
  })
}

// 操作记录相关API

// 获取操作记录列表
export function getOperationRecords(params) {
  return request({
    url: '/ui-automation/operation-records/',
    method: 'get',
    params
  })
}

// 创建操作记录
export function createOperationRecord(data) {
  return request({
    url: '/ui-automation/operation-records/',
    method: 'post',
    data
  })
}

// ==================== 定时任务相关API ====================

// 获取定时任务列表
export function getScheduledTasks(params) {
  return request({
    url: '/ui-automation/scheduled-tasks/',
    method: 'get',
    params
  })
}

// 创建定时任务
export function createScheduledTask(data) {
  return request({
    url: '/ui-automation/scheduled-tasks/',
    method: 'post',
    data
  })
}

// 获取定时任务详情
export function getScheduledTaskDetail(id) {
  return request({
    url: `/ui-automation/scheduled-tasks/${id}/`,
    method: 'get'
  })
}

// 更新定时任务
export function updateScheduledTask(id, data) {
  return request({
    url: `/ui-automation/scheduled-tasks/${id}/`,
    method: 'patch',
    data
  })
}

// 删除定时任务
export function deleteScheduledTask(id) {
  return request({
    url: `/ui-automation/scheduled-tasks/${id}/`,
    method: 'delete'
  })
}

// 暂停定时任务
export function pauseScheduledTask(id) {
  return request({
    url: `/ui-automation/scheduled-tasks/${id}/pause/`,
    method: 'post'
  })
}

// 恢复定时任务
export function resumeScheduledTask(id) {
  return request({
    url: `/ui-automation/scheduled-tasks/${id}/resume/`,
    method: 'post'
  })
}

// 立即运行任务
export function runScheduledTask(id) {
  return request({
    url: `/ui-automation/scheduled-tasks/${id}/run_now/`,
    method: 'post'
  })
}

// ==================== 通知配置相关API ====================

// 获取通知配置列表
export function getNotificationConfigs(params) {
  return request({
    url: '/ui-automation/notification-configs/',
    method: 'get',
    params
  })
}

// 创建通知配置
export function createNotificationConfig(data) {
  return request({
    url: '/ui-automation/notification-configs/',
    method: 'post',
    data
  })
}

// 获取通知配置详情
export function getNotificationConfigDetail(id) {
  return request({
    url: `/ui-automation/notification-configs/${id}/`,
    method: 'get'
  })
}

// 更新通知配置
export function updateNotificationConfig(id, data) {
  return request({
    url: `/ui-automation/notification-configs/${id}/`,
    method: 'patch',
    data
  })
}

// 删除通知配置
export function deleteNotificationConfig(id) {
  return request({
    url: `/ui-automation/notification-configs/${id}/`,
    method: 'delete'
  })
}

// 设置为默认配置
export function setDefaultNotificationConfig(id) {
  return request({
    url: `/ui-automation/notification-configs/${id}/set_default/`,
    method: 'post'
  })
}

// ==================== 通知日志相关API ====================

// 获取通知日志列表
export function getNotificationLogs(params) {
  return request({
    url: '/ui-automation/notification-logs/',
    method: 'get',
    params
  })
}

// 重试发送通知
export function retryNotification(id) {
  return request({
    url: `/ui-automation/notification-logs/${id}/retry/`,
    method: 'post'
  })
}

// ==================== 任务通知设置相关API ====================

// 获取任务通知设置
export function getTaskNotificationSettings(params) {
  return request({
    url: '/ui-automation/task-notification-settings/',
    method: 'get',
    params
  })
}

// 创建任务通知设置
export function createTaskNotificationSetting(data) {
  return request({
    url: '/ui-automation/task-notification-settings/',
    method: 'post',
    data
  })
}

// 更新任务通知设置
export function updateTaskNotificationSetting(id, data) {
  return request({
    url: `/ui-automation/task-notification-settings/${id}/`,
    method: 'patch',
    data
  })
}

// 获取用户列表（复用接口测试的用户接口）
export function getUiUsers(params) {
  return request({
    url: '/api-testing/users/',
    method: 'get',
    params
  })
}

// ==================== AI 智能模式相关API ====================

// 获取 AI 用例列表
export function getAICases(params) {
  return request({
    url: '/ui-automation/ai-cases/',
    method: 'get',
    params
  })
}

// 创建 AI 用例
export function createAICase(data) {
  return request({
    url: '/ui-automation/ai-cases/',
    method: 'post',
    data
  })
}

// 获取 AI 用例详情
export function getAICaseDetail(id) {
  return request({
    url: `/ui-automation/ai-cases/${id}/`,
    method: 'get'
  })
}

// 更新 AI 用例
export function updateAICase(id, data) {
  return request({
    url: `/ui-automation/ai-cases/${id}/`,
    method: 'patch',
    data
  })
}

// 删除 AI 用例
export function deleteAICase(id) {
  return request({
    url: `/ui-automation/ai-cases/${id}/`,
    method: 'delete'
  })
}

// 运行 AI 用例
export function runAICase(id, data = {}) {
  return request({
    url: `/ui-automation/ai-cases/${id}/run/`,
    method: 'post',
    data
  })
}

// 获取 AI 执行记录列表
export function getAIExecutionRecords(params) {
  return request({
    url: '/ui-automation/ai-execution-records/',
    method: 'get',
    params
  })
}

// 获取 AI 执行记录详情
export function getAIExecutionRecordDetail(id) {
  return request({
    url: `/ui-automation/ai-execution-records/${id}/`,
    method: 'get'
  })
}

// 执行临时 AI 任务
export function runAdhocAITask(data) {
  return request({
    url: '/ui-automation/ai-execution-records/run_adhoc/',
    method: 'post',
    data
  })
}

// 停止 AI 任务
export function stopAITask(id) {
  return request({
    url: `/ui-automation/ai-execution-records/${id}/stop/`,
    method: 'post'
  })
}

// 批量删除 AI 执行记录
export function batchDeleteAIExecutionRecords(ids) {
  return request({
    url: '/ui-automation/ai-execution-records/batch_delete/',
    method: 'post',
    data: { ids }
  })
}

// 获取 AI 执行报告
export function getAIExecutionReport(id, params = {}) {
  return request({
    url: `/ui-automation/ai-execution-records/${id}/report/`,
    method: 'get',
    params
  })
}

// 导出 AI 执行报告为 PDF
export function exportAIExecutionReportPDF(id, params = {}) {
  return request({
    url: `/ui-automation/ai-execution-records/${id}/export-pdf/`,
    method: 'get',
    params,
    responseType: 'blob'
  })
}

// ===== AI Script Pipeline =====
export function compileAIExecutionToTestCase(id, data = {}) {
  return request({
    url: `/ui-automation/ai-execution-records/${id}/compile-to-testcase/`,
    method: 'post',
    data
  })
}

export function syncAIExecutionElements(id, data = {}) {
  return request({
    url: `/ui-automation/ai-execution-records/${id}/sync-elements/`,
    method: 'post',
    data
  })
}

export function diagnoseAIExecution(id, data = {}) {
  return request({
    url: `/ui-automation/ai-execution-records/${id}/diagnose/`,
    method: 'post',
    data
  })
}

export function exportTestCaseScript(id, data = {}) {
  return request({
    url: `/ui-automation/test-cases/${id}/export-script/`,
    method: 'post',
    data
  })
}

export function diagnoseTestCaseExecution(id, data = {}) {
  return request({
    url: `/ui-automation/test-case-executions/${id}/diagnose/`,
    method: 'post',
    data
  })
}

export function diagnoseTestCase(id, data = {}) {
  return request({
    url: `/ui-automation/test-cases/${id}/diagnose/`,
    method: 'post',
    data
  })
}

export function createRecordingSession(data) {
  return request({
    url: '/ui-automation/recording-sessions/',
    method: 'post',
    data
  })
}

export function stopRecordingSession(id, data = {}) {
  return request({
    url: `/ui-automation/recording-sessions/${id}/stop/`,
    method: 'post',
    data
  })
}

export function getRecordingSessionEvents(id) {
  return request({
    url: `/ui-automation/recording-sessions/${id}/events/`,
    method: 'get'
  })
}

export function getRecordingSession(id) {
  return request({
    url: `/ui-automation/recording-sessions/${id}/`,
    method: 'get'
  })
}

export function compileActionTrace(id, data = {}) {
  return request({
    url: `/ui-automation/action-traces/${id}/compile/`,
    method: 'post',
    data
  })
}

export function applyScriptFix(diagnosisId, data = {}) {
  return request({
    url: `/ui-automation/failure-diagnoses/${diagnosisId}/apply-script-fix/`,
    method: 'post',
    data
  })
}

export function createDefectFromDiagnosis(diagnosisId, data = {}) {
  return request({
    url: `/ui-automation/failure-diagnoses/${diagnosisId}/create-defect/`,
    method: 'post',
    data
  })
}

export function approveFixProposal(id) {
  return request({
    url: `/ui-automation/auto-fix-proposals/${id}/approve/`,
    method: 'post'
  })
}

export function rejectFixProposal(id) {
  return request({
    url: `/ui-automation/auto-fix-proposals/${id}/reject/`,
    method: 'post'
  })
}

export function getFailureDiagnosis(id) {
  return request({
    url: `/ui-automation/failure-diagnoses/${id}/`,
    method: 'get'
  })
}