/**
 * APP自动化测试模块 - 公共工具函数
 */
import i18n from '@/locales'

const t = (key, params) => i18n.global.t(key, params)

// ========== 执行状态映射（任务生命周期） ==========

// 状态值 → i18n key / Element Plus Tag 类型
const EXECUTION_STATUS_KEY = {
  'pending':   'appAutomation.status.pending',
  'running':   'appAutomation.status.running',
  'completed': 'appAutomation.status.completed',
  'error':     'appAutomation.status.error',
  'stopped':   'appAutomation.status.stopped',
  'success':   'appAutomation.status.success',
  'failed':    'appAutomation.status.failed',
}

const EXECUTION_STATUS_TYPE = {
  'pending':   'info',
  'running':   'warning',
  'completed': 'success',
  'error':     'danger',
  'stopped':   'info',
  'success':   'success',
  'failed':    'danger',
}

// ========== 测试结果映射（用例通过/失败） ==========

const EXECUTION_RESULT_KEY = {
  'passed':  'appAutomation.status.passed',
  'failed':  'appAutomation.status.failed',
  'skipped': 'appAutomation.status.skipped',
}

const EXECUTION_RESULT_TYPE = {
  'passed':  'success',
  'failed':  'danger',
  'skipped': 'warning',
}

const DEVICE_STATUS_KEY = {
  'available': 'appAutomation.status.available',
  'locked':    'appAutomation.status.locked',
  'online':    'appAutomation.status.online',
  'offline':   'appAutomation.status.offline',
}

const DEVICE_STATUS_TYPE = {
  'available': 'success',
  'locked':    'warning',
  'online':    'success',
  'offline':   'danger',
}

/**
 * 获取执行状态的 Element Plus Tag 类型
 * @param {string} status - 状态值
 * @returns {string}
 */
export function getExecutionStatusType(status) {
  return EXECUTION_STATUS_TYPE[status] || 'info'
}

/**
 * 获取执行状态的显示文本
 * @param {string} status - 状态值
 * @returns {string}
 */
export function getExecutionStatusText(status) {
  const key = EXECUTION_STATUS_KEY[status]
  return key ? t(key) : status
}

/**
 * 获取测试结果的 Element Plus Tag 类型
 * @param {string} result - 结果值 (passed/failed/skipped)
 * @returns {string}
 */
export function getResultType(result) {
  return EXECUTION_RESULT_TYPE[result] || 'info'
}

/**
 * 获取测试结果的显示文本
 * @param {string} result - 结果值
 * @returns {string}
 */
export function getResultText(result) {
  const key = EXECUTION_RESULT_KEY[result]
  return key ? t(key) : '-'
}

/**
 * 获取综合展示的类型和文本（优先显示测试结果，其次显示任务状态）
 * 适用于列表中单列展示场景
 * @param {string} status - 任务状态
 * @param {string|null} result - 测试结果
 * @returns {{ type: string, text: string }}
 */
export function getDisplayStatus(status, result) {
  // 任务还在进行中，显示任务状态
  if (status === 'pending' || status === 'running') {
    const key = EXECUTION_STATUS_KEY[status]
    return { type: EXECUTION_STATUS_TYPE[status], text: key ? t(key) : status }
  }
  // 任务异常，显示异常状态
  if (status === 'error') {
    return { type: 'danger', text: t('appAutomation.status.error') }
  }
  // 任务已停止
  if (status === 'stopped') {
    return { type: 'info', text: t('appAutomation.status.stopped') }
  }
  // 任务已完成，显示测试结果
  if (result) {
    const key = EXECUTION_RESULT_KEY[result]
    return key
      ? { type: EXECUTION_RESULT_TYPE[result], text: t(key) }
      : { type: 'info', text: result }
  }
  // 兜底
  const key = EXECUTION_STATUS_KEY[status]
  return key
    ? { type: EXECUTION_STATUS_TYPE[status], text: t(key) }
    : { type: 'info', text: status || '-' }
}

/**
 * 获取设备状态的 Element Plus Tag 类型
 * @param {string} status - 状态值
 * @returns {string}
 */
export function getDeviceStatusType(status) {
  return DEVICE_STATUS_TYPE[status] || 'info'
}

/**
 * 获取设备状态的显示文本
 * @param {string} status - 状态值
 * @returns {string}
 */
export function getDeviceStatusText(status) {
  const key = DEVICE_STATUS_KEY[status]
  return key ? t(key) : status
}

// ========== 日期格式化 ==========

/**
 * 格式化日期时间（完整格式）
 * @param {string} timeStr - ISO 时间字符串
 * @returns {string}
 */
export function formatDateTime(timeStr) {
  if (!timeStr) return '-'
  return new Date(timeStr).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

/**
 * 格式化为相对时间（如"3分钟前"）
 * @param {string} timeStr - ISO 时间字符串
 * @returns {string}
 */
export function formatRelativeTime(timeStr) {
  if (!timeStr) return '-'
  const date = new Date(timeStr)
  const now = new Date()
  const diff = now.getTime() - date.getTime()

  if (diff < 60000) return t('appAutomation.common.justNow')
  if (diff < 3600000) return t('appAutomation.common.minutesAgo', { n: Math.floor(diff / 60000) })
  if (diff < 86400000) return t('appAutomation.common.hoursAgo', { n: Math.floor(diff / 3600000) })
  return t('appAutomation.common.daysAgo', { n: Math.floor(diff / 86400000) })
}

/**
 * 格式化执行时长（秒）
 * @param {number} seconds
 * @returns {string}
 */
export function formatDuration(seconds) {
  const n = Number(seconds)
  if (!n || n <= 0) return '0s'
  if (n < 60) return `${n.toFixed(n < 10 ? 1 : 0)}s`
  const m = Math.floor(n / 60)
  const s = Math.round(n % 60)
  if (m < 60) return `${m}m${s}s`
  const h = Math.floor(m / 60)
  return `${h}h${m % 60}m`
}
