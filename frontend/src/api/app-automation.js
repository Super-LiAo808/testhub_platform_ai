/**
 * APP自动化测试 API
 */
import request from '../utils/api'

// ========== 项目管理 ==========

export function getAppProjects(params) {
  return request({ url: '/app-automation/projects/', method: 'get', params })
}

export function getAppProject(id) {
  return request({ url: `/app-automation/projects/${id}/`, method: 'get' })
}

export function createAppProject(data) {
  return request({ url: '/app-automation/projects/', method: 'post', data })
}

export function updateAppProject(id, data) {
  return request({ url: `/app-automation/projects/${id}/`, method: 'put', data })
}

export function deleteAppProject(id) {
  return request({ url: `/app-automation/projects/${id}/`, method: 'delete' })
}

// ========== 配置管理 ==========

/**
 * 获取 APP 测试配置
 */
export function getAppConfig() {
  return request({
    url: '/app-automation/config/current/',
    method: 'get'
  })
}

/**
 * 更新 APP 测试配置
 */
export function updateAppConfig(data) {
  return request({
    url: '/app-automation/config/save/',
    method: 'post',
    data
  })
}

// ========== Dashboard ==========

/**
 * 获取 Dashboard 统计数据
 */
export function getDashboardStatistics(params = {}) {
  return request({
    url: '/app-automation/dashboard/statistics/',
    method: 'get',
    params
  })
}

/**
 * 获取最近执行记录
 */
export function getDashboardRecentExecutions(params = {}) {
  return request({
    url: '/app-automation/dashboard/recent-executions/',
    method: 'get',
    params
  })
}

// ========== 设备管理 ==========

/**
 * 获取设备列表
 */
export function getDeviceList(params) {
  return request({
    url: '/app-automation/devices/',
    method: 'get',
    params
  })
}

/**
 * 获取设备截图
 */
export function captureDeviceScreenshot(id) {
  return request({
    url: `/app-automation/devices/${id}/screenshot/`,
    method: 'post',
    timeout: 15000 // 截图可能需要较长时间
  })
}

/**
 * 删除设备
 */
export function deleteDevice(id) {
  return request({
    url: `/app-automation/devices/${id}/`,
    method: 'delete'
  })
}

/**
 * 发现 ADB 设备
 */
export function discoverDevices(params) {
  return request({
    url: '/app-automation/devices/discover/',
    method: 'get',
    params
  })
}

/**
 * 锁定设备
 */
export function lockDevice(id) {
  return request({
    url: `/app-automation/devices/${id}/lock/`,
    method: 'post'
  })
}

/**
 * 释放设备
 */
export function unlockDevice(id) {
  return request({
    url: `/app-automation/devices/${id}/unlock/`,
    method: 'post'
  })
}

// 断开远程设备连接
export function disconnectDevice(id) {
  return request({
    url: `/app-automation/devices/${id}/disconnect/`,
    method: 'post'
  })
}

/**
 * 连接远程设备
 */
export function connectDevice(data) {
  return request({
    url: '/app-automation/devices/connect/',
    method: 'post',
    data
  })
}


// ========== 元素管理 ==========

/**
 * 获取元素列表
 */
export function getAppElementList(params) {
  return request({
    url: '/app-automation/elements/',
    method: 'get',
    params
  })
}

/**
 * 创建元素
 */
export function createAppElement(data) {
  return request({
    url: '/app-automation/elements/',
    method: 'post',
    data
  })
}

/**
 * 更新元素
 */
export function updateAppElement(id, data) {
  return request({
    url: `/app-automation/elements/${id}/`,
    method: 'put',
    data
  })
}

/**
 * 删除元素
 */
export function deleteAppElement(id) {
  return request({
    url: `/app-automation/elements/${id}/`,
    method: 'delete'
  })
}

/**
 * 上传元素图片
 * @param {File} file - 图片文件
 * @param {string} category - 分类名称，默认 'common'
 * @param {number} elementId - 元素ID（编辑模式时传递，用于排除自身）
 */
export function uploadAppElementImage(file, category = 'common', elementId = null) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('category', category)
  if (elementId) {
    formData.append('element_id', String(elementId))
  }
  
  return request({
    url: '/app-automation/elements/upload/',
    method: 'post',
    data: formData,
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}

/**
 * 获取图片分类列表
 */
export function getAppImageCategories() {
  return request({
    url: '/app-automation/elements/image-categories/',
    method: 'get'
  })
}

/**
 * 创建图片分类
 * @param {string} name - 分类名称
 */
export function createAppImageCategory(name) {
  return request({
    url: '/app-automation/elements/image-categories/create/',
    method: 'post',
    data: { name }
  })
}

/**
 * 删除图片分类
 * @param {string} name - 分类名称
 */
export function deleteAppImageCategory(name) {
  return request({
    url: `/app-automation/elements/image-categories/${name}/`,
    method: 'delete'
  })
}

// ========== 应用包名管理 ==========

/**
 * 获取应用包名列表
 */
export function getPackageList(params) {
  return request({
    url: '/app-automation/packages/',
    method: 'get',
    params
  })
}

/**
 * 创建应用包名
 */
export function createPackage(data) {
  return request({
    url: '/app-automation/packages/',
    method: 'post',
    data
  })
}

/**
 * 更新应用包名
 */
export function updatePackage(id, data) {
  return request({
    url: `/app-automation/packages/${id}/`,
    method: 'put',
    data
  })
}

/**
 * 删除应用包名
 */
export function deletePackage(id) {
  return request({
    url: `/app-automation/packages/${id}/`,
    method: 'delete'
  })
}

// ========== 测试用例管理 ==========

/**
 * 获取测试用例列表
 */
export function getTestCaseList(params) {
  return request({
    url: '/app-automation/test-cases/',
    method: 'get',
    params
  })
}

/**
 * 获取测试用例详情
 */
export function getTestCaseDetail(id) {
  return request({
    url: `/app-automation/test-cases/${id}/`,
    method: 'get'
  })
}

/**
 * 创建测试用例
 */
export function createTestCase(data) {
  return request({
    url: '/app-automation/test-cases/',
    method: 'post',
    data
  })
}

/**
 * 更新测试用例
 */
export function updateTestCase(id, data) {
  return request({
    url: `/app-automation/test-cases/${id}/`,
    method: 'put',
    data
  })
}

/**
 * 删除测试用例
 */
export function deleteTestCase(id) {
  return request({
    url: `/app-automation/test-cases/${id}/`,
    method: 'delete'
  })
}

/**
 * 执行测试用例
 */
export function executeTestCase(id, data) {
  return request({
    url: `/app-automation/test-cases/${id}/execute/`,
    method: 'post',
    data
  })
}

// ========== 执行记录管理 ==========

/**
 * 获取执行记录列表
 */
export function getExecutionList(params) {
  return request({
    url: '/app-automation/executions/',
    method: 'get',
    params
  })
}

/**
 * 获取执行记录详情
 */
export function getExecutionDetail(id) {
  return request({
    url: `/app-automation/executions/${id}/`,
    method: 'get'
  })
}

/**
 * 检查 WebSocket 是否可用
 */
export function getWsStatus() {
  return request({
    url: '/app-automation/executions/ws_status/',
    method: 'get'
  })
}

/**
 * 删除执行记录
 */
export function deleteExecution(id) {
  return request({
    url: `/app-automation/executions/${id}/`,
    method: 'delete'
  })
}

/**
 * 停止执行
 */
export function stopExecution(id) {
  return request({
    url: `/app-automation/executions/${id}/stop/`,
    method: 'post'
  })
}

export function diagnoseAppExecution(id, data = {}) {
  return request({
    url: `/app-automation/executions/${id}/diagnose/`,
    method: 'post',
    data
  })
}

// ========== 测试套件管理 ==========

/**
 * 获取测试套件列表
 */
export function getTestSuiteList(params) {
  return request({
    url: '/app-automation/test-suites/',
    method: 'get',
    params
  })
}

/**
 * 获取测试套件详情
 */
export function getTestSuiteDetail(id) {
  return request({
    url: `/app-automation/test-suites/${id}/`,
    method: 'get'
  })
}

/**
 * 创建测试套件
 */
export function createTestSuite(data) {
  return request({
    url: '/app-automation/test-suites/',
    method: 'post',
    data
  })
}

/**
 * 更新测试套件
 */
export function updateTestSuite(id, data) {
  return request({
    url: `/app-automation/test-suites/${id}/`,
    method: 'patch',
    data
  })
}

/**
 * 删除测试套件
 */
export function deleteTestSuite(id) {
  return request({
    url: `/app-automation/test-suites/${id}/`,
    method: 'delete'
  })
}

/**
 * 获取套件中的测试用例
 */
export function getTestSuiteTestCases(id) {
  return request({
    url: `/app-automation/test-suites/${id}/test_cases/`,
    method: 'get'
  })
}

/**
 * 向套件添加测试用例
 */
export function addTestCaseToSuite(suiteId, data) {
  return request({
    url: `/app-automation/test-suites/${suiteId}/add_test_case/`,
    method: 'post',
    data
  })
}

/**
 * 批量添加测试用例到套件
 */
export function addTestCasesToSuite(suiteId, data) {
  return request({
    url: `/app-automation/test-suites/${suiteId}/add_test_cases/`,
    method: 'post',
    data
  })
}

/**
 * 从套件移除测试用例
 */
export function removeTestCaseFromSuite(suiteId, data) {
  return request({
    url: `/app-automation/test-suites/${suiteId}/remove_test_case/`,
    method: 'post',
    data
  })
}

/**
 * 更新套件中用例的执行顺序
 */
export function updateSuiteTestCaseOrder(suiteId, data) {
  return request({
    url: `/app-automation/test-suites/${suiteId}/update_test_case_order/`,
    method: 'post',
    data
  })
}

/**
 * 执行测试套件
 */
export function runTestSuite(suiteId, data) {
  return request({
    url: `/app-automation/test-suites/${suiteId}/run/`,
    method: 'post',
    data
  })
}

/**
 * 获取套件的执行历史
 */
export function getTestSuiteExecutions(suiteId) {
  return request({
    url: `/app-automation/test-suites/${suiteId}/executions/`,
    method: 'get'
  })
}

// ========== 组件库管理 ==========

/**
 * 获取基础组件列表
 */
export function getComponents(params) {
  return request({
    url: '/app-automation/components/',
    method: 'get',
    params
  })
}

/**
 * 获取自定义组件列表
 */
export function getCustomComponents(params) {
  return request({
    url: '/app-automation/custom-components/',
    method: 'get',
    params
  })
}

/**
 * 创建自定义组件
 */
export function createCustomComponent(data) {
  return request({
    url: '/app-automation/custom-components/',
    method: 'post',
    data
  })
}

/**
 * 更新自定义组件
 */
export function updateCustomComponent(id, data) {
  return request({
    url: `/app-automation/custom-components/${id}/`,
    method: 'put',
    data
  })
}

/**
 * 删除自定义组件
 */
export function deleteCustomComponent(id) {
  return request({
    url: `/app-automation/custom-components/${id}/`,
    method: 'delete'
  })
}

/**
 * 导入组件包
 */
export function importComponentPackage(data) {
  return request({
    url: '/app-automation/component-packages/',
    method: 'post',
    data,
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}

/**
 * 导出组件包
 * 注意: 参数名用 export_format 而非 format（format 是 DRF Router 保留字）
 */
export function exportComponentPackage(params) {
  return request({
    url: '/app-automation/component-packages/export/',
    method: 'get',
    params,
    responseType: 'blob'
  })
}

// ==================== 定时任务管理 ====================

/**
 * 获取定时任务列表
 */
export function getAppScheduledTasks(params) {
  return request({ url: '/app-automation/scheduled-tasks/', method: 'get', params })
}

/**
 * 获取定时任务详情
 */
export function getAppScheduledTaskDetail(id) {
  return request({ url: `/app-automation/scheduled-tasks/${id}/`, method: 'get' })
}

/**
 * 创建定时任务
 */
export function createAppScheduledTask(data) {
  return request({ url: '/app-automation/scheduled-tasks/', method: 'post', data })
}

/**
 * 更新定时任务
 */
export function updateAppScheduledTask(id, data) {
  return request({ url: `/app-automation/scheduled-tasks/${id}/`, method: 'patch', data })
}

/**
 * 删除定时任务
 */
export function deleteAppScheduledTask(id) {
  return request({ url: `/app-automation/scheduled-tasks/${id}/`, method: 'delete' })
}

/**
 * 暂停定时任务
 */
export function pauseAppScheduledTask(id) {
  return request({ url: `/app-automation/scheduled-tasks/${id}/pause/`, method: 'post' })
}

/**
 * 恢复定时任务
 */
export function resumeAppScheduledTask(id) {
  return request({ url: `/app-automation/scheduled-tasks/${id}/resume/`, method: 'post' })
}

/**
 * 立即运行定时任务
 */
export function runAppScheduledTask(id) {
  return request({ url: `/app-automation/scheduled-tasks/${id}/run_now/`, method: 'post' })
}

// ==================== 通知日志 ====================

/**
 * 获取通知日志列表
 */
export function getAppNotificationLogs(params) {
  return request({ url: '/app-automation/notification-logs/', method: 'get', params })
}

/**
 * 重试发送通知
 */
export function retryAppNotification(id) {
  return request({ url: `/app-automation/notification-logs/${id}/retry/`, method: 'post' })
}

// ==================== APP 操作录制 ====================

export function createAppRecordingSession(data) {
  // Create returns quickly; Appium/APK install runs in background worker
  return request({ url: '/app-automation/recording-sessions/', method: 'post', data, timeout: 30000 })
}

export function getAppRecordingSession(id) {
  return request({ url: `/app-automation/recording-sessions/${id}/`, method: 'get' })
}

export function stopAppRecordingSession(id, data = {}) {
  return request({ url: `/app-automation/recording-sessions/${id}/stop/`, method: 'post', data })
}

export function saveAppRecordingCase(id, data = {}) {
  return request({ url: `/app-automation/recording-sessions/${id}/save-case/`, method: 'post', data })
}

export function sendAppRecordingEvent(id, data) {
  return request({ url: `/app-automation/recording-sessions/${id}/event/`, method: 'post', data })
}

export function updateAppRecordingSettings(id, data) {
  return request({ url: `/app-automation/recording-sessions/${id}/stream-settings/`, method: 'post', data, timeout: 10000 })
}

export function getAppRecordingFrame(id) {
  return request({ url: `/app-automation/recording-sessions/${id}/frame/`, method: 'get', timeout: 15000 })
}
