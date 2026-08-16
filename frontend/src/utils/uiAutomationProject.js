/** UI 自动化模块跨页面共享的当前项目选择 */

const STORAGE_KEY = 'ui_automation_selected_project_id'

export function getSavedUiProjectId() {
  const raw = localStorage.getItem(STORAGE_KEY)
  if (raw == null || raw === '') return null
  const id = Number(raw)
  return Number.isFinite(id) ? id : null
}

export function saveUiProjectId(id) {
  if (id == null || id === '') {
    localStorage.removeItem(STORAGE_KEY)
    return
  }
  localStorage.setItem(STORAGE_KEY, String(id))
}

/**
 * 在项目列表中解析应选中的项目。
 * @param {Array<{id: number|string}>} projects
 * @param {{ fallbackToFirst?: boolean }} options
 *   - fallbackToFirst=true：无记忆时选第一个（用例/元素页需要明确项目）
 *   - fallbackToFirst=false：无记忆时返回 null，表示「全部项目」（执行记录/报告）
 * @returns {number|string|null}
 */
export function resolveUiProjectId(projects, options = {}) {
  const { fallbackToFirst = true } = options
  if (!projects || !projects.length) return null
  const saved = getSavedUiProjectId()
  if (saved != null) {
    const matched = projects.find((p) => Number(p.id) === saved)
    if (matched) return matched.id
  }
  return fallbackToFirst ? projects[0].id : null
}
