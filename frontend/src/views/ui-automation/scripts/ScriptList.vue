<template>
  <div class="page-container script-page">
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">{{ $t('uiAutomation.script.title') }}</h1>
        <p class="page-subtitle">管理独立 Playwright / Selenium 脚本，支持运行与用例同步</p>
      </div>
      <div class="header-actions">
        <el-button type="primary" @click="goToScriptEditor">
          <el-icon><Plus /></el-icon>
          {{ $t('uiAutomation.script.newScript') }}
        </el-button>
      </div>
    </div>

    <div class="card-container">
      <div class="filter-bar">
        <el-select
          v-model="selectedProject"
          :placeholder="$t('uiAutomation.common.selectProject')"
          filterable
          style="width: 220px"
          @change="onProjectChange"
        >
          <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
        </el-select>
        <el-input
          v-model="searchText"
          clearable
          placeholder="搜索脚本名称"
          style="width: 240px"
          @input="onSearchInput"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-select v-model="frameworkFilter" clearable placeholder="框架" style="width: 140px" @change="loadScripts">
          <el-option label="Playwright" value="playwright" />
          <el-option label="Selenium" value="selenium" />
        </el-select>
        <div class="filter-spacer" />
        <span v-if="selectedProject" class="result-hint">共 {{ total }} 个脚本</span>
        <el-button
          type="danger"
          plain
          :disabled="selectedIds.length === 0"
          @click="batchDeleteScripts"
        >
          {{ $t('uiAutomation.common.batchDelete') || '批量删除' }}
          <template v-if="selectedIds.length"> ({{ selectedIds.length }})</template>
        </el-button>
      </div>

      <el-table
        :data="scripts"
        v-loading="loading"
        class="script-table"
        row-key="id"
        empty-text="暂无脚本，请先选择项目或新建脚本"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="48" align="center" />
        <el-table-column :label="$t('uiAutomation.script.index')" width="72" align="center">
          <template #default="{ $index }">
            <span class="row-index">{{ reverseIndex($index) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="name" :label="$t('uiAutomation.script.nameColumn')" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="name-cell">
              <button class="name-link" type="button" @click="viewScript(row)">{{ row.name }}</button>
              <span v-if="row.source_test_case_id" class="name-meta">用例 #{{ row.source_test_case_id }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="一致性" width="130">
          <template #default="{ row }">
            <el-tag size="small" effect="plain" :type="syncTagType(row)">
              {{ row.sync_label || syncFallbackLabel(row) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="$t('uiAutomation.script.languageColumn')" width="100">
          <template #default="{ row }">
            <el-tag size="small" effect="plain" :type="row.language === 'python' ? 'success' : ''">
              {{ getLanguageText(row.language) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="$t('uiAutomation.script.frameworkColumn')" width="120">
          <template #default="{ row }">
            <el-tag size="small" effect="plain" :type="row.framework === 'playwright' ? 'warning' : 'info'">
              {{ getFrameworkText(row.framework) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" :label="$t('uiAutomation.script.createTimeColumn')" width="170">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column :label="$t('uiAutomation.script.operationColumn')" width="280" fixed="right">
          <template #default="{ row }">
            <div class="table-actions">
              <el-button link type="success" size="small" :loading="runningId === row.id" @click="runScript(row)">
                运行
              </el-button>
              <el-button
                v-if="row.inconsistent && row.source_test_case_id"
                link
                type="warning"
                size="small"
                @click="syncFromCase(row)"
              >
                同步
              </el-button>
              <el-button link type="primary" size="small" @click="viewScript(row)">详情</el-button>
              <el-button link type="primary" size="small" @click="editScript(row)">编辑</el-button>
              <el-dropdown trigger="click" @command="(cmd) => onMoreCommand(cmd, row)">
                <el-button link size="small">更多</el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="rename">重命名</el-dropdown-item>
                    <el-dropdown-item command="delete" divided>
                      <span class="danger-text">删除</span>
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-container">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </div>

    <el-dialog v-model="showDetailDialog" :title="$t('uiAutomation.script.scriptDetail')" width="72%">
      <div v-if="currentScript" class="script-detail">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item :label="$t('uiAutomation.script.scriptName')" :span="2">{{ currentScript.name }}</el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.script.project')">{{ currentScript.project?.name || $t('uiAutomation.script.unknownProject') }}</el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.script.language')">{{ getLanguageText(currentScript.language) }}</el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.script.framework')">{{ getFrameworkText(currentScript.framework) }}</el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.script.scriptType')">{{ getScriptTypeText(currentScript.script_type) }}</el-descriptions-item>
          <el-descriptions-item label="一致性">{{ currentScript.sync_label || syncFallbackLabel(currentScript) }}</el-descriptions-item>
          <el-descriptions-item label="关联用例">{{ currentScript.source_test_case_id ? `#${currentScript.source_test_case_id} ${currentScript.source_test_case_name || ''}` : '无（独立脚本）' }}</el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.script.createTime')">{{ formatTime(currentScript.created_at) }}</el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.script.updateTime')">{{ formatTime(currentScript.updated_at) }}</el-descriptions-item>
        </el-descriptions>
        <div class="script-content">
          <h4>{{ $t('uiAutomation.script.scriptContent') }}</h4>
          <pre class="code-view">{{ currentScript.content || $t('uiAutomation.script.noContent') }}</pre>
        </div>
      </div>
      <template #footer>
        <el-button @click="showDetailDialog = false">{{ $t('uiAutomation.script.close') }}</el-button>
        <el-button type="primary" @click="editScript(currentScript)">{{ $t('uiAutomation.script.editScript') }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showRenameDialog" :title="$t('uiAutomation.script.renameScript')" width="420px">
      <el-form :model="renameForm" label-width="80px">
        <el-form-item :label="$t('uiAutomation.script.newName')">
          <el-input v-model="renameForm.newName" :placeholder="$t('uiAutomation.script.newNamePlaceholder')" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRenameDialog = false">{{ $t('uiAutomation.common.cancel') }}</el-button>
        <el-button type="primary" @click="confirmRename">{{ $t('uiAutomation.common.confirm') }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showEditDialog" :title="$t('uiAutomation.script.editScript')" width="80%" :close-on-click-modal="false">
      <div v-if="editingScript" class="script-editor">
        <div class="editor-header">
          <span class="script-name">{{ editingScript.name }}</span>
          <div class="editor-info">
            <el-tag size="small" effect="plain" :type="editingScript.language === 'python' ? 'success' : ''">
              {{ getLanguageText(editingScript.language) }}
            </el-tag>
            <el-tag size="small" effect="plain" :type="editingScript.framework === 'playwright' ? 'warning' : 'info'" style="margin-left: 8px">
              {{ getFrameworkText(editingScript.framework) }}
            </el-tag>
          </div>
        </div>
        <div class="editor-container">
          <textarea
            v-model="editingScript.content"
            class="code-editor"
            :placeholder="$t('uiAutomation.script.scriptEditorPlaceholder')"
          />
        </div>
      </div>
      <template #footer>
        <el-button @click="showEditDialog = false">{{ $t('uiAutomation.common.cancel') }}</el-button>
        <el-button type="primary" @click="saveEditedScript" :loading="saving">{{ $t('uiAutomation.script.save') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import {
  getUiProjects,
  getTestScripts,
  updateTestScript,
  deleteTestScript,
  batchDeleteTestScripts,
  runTestScript,
  syncTestScriptFromCase
} from '@/api/ui_automation'
import { resolveUiProjectId, saveUiProjectId } from '@/utils/uiAutomationProject'

const router = useRouter()
const { t } = useI18n()

const projects = ref([])
const selectedProject = ref('')
const scripts = ref([])
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const runningId = ref(null)
const loading = ref(false)
const searchText = ref('')
const frameworkFilter = ref('')
const selectedIds = ref([])
let searchTimer = null

const showDetailDialog = ref(false)
const showRenameDialog = ref(false)
const showEditDialog = ref(false)
const currentScript = ref(null)
const editingScript = ref(null)
const saving = ref(false)

const renameForm = reactive({
  scriptId: null,
  newName: ''
})

const reverseIndex = (index) => {
  const n = Number(total.value) || 0
  const page = Number(currentPage.value) || 1
  const size = Number(pageSize.value) || 20
  return Math.max(1, n - (page - 1) * size - index)
}

const loadProjects = async () => {
  try {
    const response = await getUiProjects({ page_size: 100 })
    projects.value = response.data.results || response.data
  } catch (error) {
    ElMessage.error(t('uiAutomation.script.messages.loadProjectsFailed'))
    console.error('获取项目列表失败:', error)
  }
}

const loadScripts = async () => {
  if (!selectedProject.value) {
    scripts.value = []
    total.value = 0
    return
  }

  loading.value = true
  try {
    const params = {
      project: selectedProject.value,
      page: currentPage.value,
      page_size: pageSize.value,
      ordering: '-created_at'
    }
    if (searchText.value.trim()) params.search = searchText.value.trim()
    if (frameworkFilter.value) params.framework = frameworkFilter.value

    const response = await getTestScripts(params)
    if (response.data.results) {
      scripts.value = response.data.results
      total.value = response.data.count || 0
    } else {
      scripts.value = response.data
      total.value = response.data.length
    }
  } catch (error) {
    ElMessage.error(t('uiAutomation.script.messages.loadScriptsFailed'))
    console.error('获取脚本列表失败:', error)
  } finally {
    loading.value = false
  }
}

const onProjectChange = async () => {
  saveUiProjectId(selectedProject.value)
  currentPage.value = 1
  await loadScripts()
}

const onSearchInput = () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    currentPage.value = 1
    loadScripts()
  }, 300)
}

const handleSizeChange = async () => {
  currentPage.value = 1
  await loadScripts()
}

const handleCurrentChange = async () => {
  await loadScripts()
}

const goToScriptEditor = () => {
  router.push('/ui-automation/scripts/editor')
}

const syncTagType = (row) => {
  const map = {
    independent: 'info',
    synced: 'success',
    case_ahead: 'warning',
    script_ahead: 'warning',
    diverged: 'danger'
  }
  return map[row.sync_status] || 'info'
}

const syncFallbackLabel = (row) => {
  if (!row.source_test_case_id) return '独立脚本'
  return row.inconsistent ? '与用例不一致' : '与用例一致'
}

const onMoreCommand = (cmd, row) => {
  if (cmd === 'rename') renameScript(row)
  if (cmd === 'delete') deleteScript(row)
}

const runScript = async (row) => {
  runningId.value = row.id
  try {
    const res = await runTestScript(row.id, { headless: true, browser: 'chrome' })
    const executionId = res.data?.execution_id
    ElMessage.success(`脚本已开始执行，执行记录 #${executionId || '-'}`)
    try {
      await ElMessageBox.confirm(
        '是否前往执行记录查看进度？',
        '脚本已启动',
        { type: 'success', confirmButtonText: '去查看', cancelButtonText: '稍后' }
      )
      router.push('/ui-automation/executions')
    } catch (_) { /* cancel */ }
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || '启动脚本失败')
  } finally {
    runningId.value = null
  }
}

const syncFromCase = async (row) => {
  try {
    await ElMessageBox.confirm(
      '将用关联用例重新生成脚本内容，覆盖当前脚本。是否继续？',
      '从用例同步',
      { type: 'warning' }
    )
    await syncTestScriptFromCase(row.id)
    ElMessage.success('已从用例同步')
    await loadScripts()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(error?.response?.data?.error || '同步失败')
    }
  }
}

const viewScript = (script) => {
  currentScript.value = script
  showDetailDialog.value = true
}

const editScript = (script) => {
  if (!script) return
  editingScript.value = { ...script }
  showDetailDialog.value = false
  showEditDialog.value = true
}

const renameScript = (script) => {
  renameForm.scriptId = script.id
  renameForm.newName = script.name
  showRenameDialog.value = true
}

const confirmRename = async () => {
  if (!renameForm.newName.trim()) {
    ElMessage.warning(t('uiAutomation.script.messages.enterNewName'))
    return
  }
  try {
    await updateTestScript(renameForm.scriptId, { name: renameForm.newName.trim() })
    ElMessage.success(t('uiAutomation.script.messages.renameSuccess'))
    showRenameDialog.value = false
    await loadScripts()
  } catch (error) {
    ElMessage.error(t('uiAutomation.script.messages.renameFailed'))
  }
}

const saveEditedScript = async () => {
  if (!editingScript.value) return
  saving.value = true
  try {
    await updateTestScript(editingScript.value.id, { content: editingScript.value.content })
    ElMessage.success(t('uiAutomation.script.messages.saveSuccess'))
    showEditDialog.value = false
    await loadScripts()
  } catch (error) {
    ElMessage.error(t('uiAutomation.script.messages.saveFailed'))
  } finally {
    saving.value = false
  }
}

const deleteScript = async (script) => {
  try {
    await ElMessageBox.confirm(
      t('uiAutomation.script.messages.deleteConfirm', { name: script.name }),
      t('uiAutomation.common.warning') || '警告',
      { type: 'warning' }
    )
    await deleteTestScript(script.id)
    ElMessage.success(t('uiAutomation.script.messages.deleteSuccess'))
    selectedIds.value = selectedIds.value.filter((id) => id !== script.id)
    await loadScripts()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(t('uiAutomation.script.messages.deleteFailed'))
    }
  }
}

const handleSelectionChange = (rows) => {
  selectedIds.value = rows.map((r) => r.id)
}

const batchDeleteScripts = async () => {
  const ids = [...selectedIds.value]
  if (!ids.length) return
  try {
    await ElMessageBox.confirm(
      t('uiAutomation.script.messages.batchDeleteConfirm', { count: ids.length }),
      t('uiAutomation.script.messages.confirmDelete') || '确认删除',
      { type: 'warning' }
    )
    let deleted = 0
    let failed = 0
    try {
      const res = await batchDeleteTestScripts(ids)
      deleted = res.data?.deleted ?? ids.length
      failed = res.data?.failed ?? 0
    } catch (err) {
      // 405/404：服务未热更新时回退为逐条删除
      const status = err?.response?.status
      if (status !== 405 && status !== 404) throw err
      for (const id of ids) {
        try {
          await deleteTestScript(id)
          deleted += 1
        } catch {
          failed += 1
        }
      }
    }
    if (failed) {
      ElMessage.warning(`已删除 ${deleted} 个，失败 ${failed} 个`)
    } else {
      ElMessage.success(t('uiAutomation.script.messages.deleteSuccess'))
    }
    selectedIds.value = []
    await loadScripts()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(t('uiAutomation.script.messages.deleteFailed'))
    }
  }
}

const getLanguageText = (language) => {
  const map = { python: 'Python', javascript: 'JavaScript', typescript: 'TypeScript' }
  return map[language] || language
}

const getFrameworkText = (framework) => {
  const map = { playwright: 'Playwright', selenium: 'Selenium' }
  return map[framework] || framework
}

const getScriptTypeText = (type) => {
  const map = { recorded: '录制', manual: '手工', generated: '生成' }
  return map[type] || type || '-'
}

const formatTime = (time) => {
  if (!time) return '-'
  return new Date(time).toLocaleString()
}

onMounted(async () => {
  await loadProjects()
  selectedProject.value = resolveUiProjectId(projects.value, { fallbackToFirst: true })
  if (selectedProject.value) {
    await loadScripts()
  }
})
</script>

<style scoped lang="scss">
.script-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f3f5f8;
  padding: 16px 20px 20px;
  box-sizing: border-box;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}

.page-title {
  margin: 0;
  font-size: 22px;
  font-weight: 650;
  color: #1f2a37;
  letter-spacing: -0.02em;
}

.page-subtitle {
  margin: 6px 0 0;
  font-size: 13px;
  color: #6b7280;
}

.card-container {
  flex: 1;
  min-height: 0;
  background: #fff;
  border: 1px solid #e5e9f0;
  border-radius: 12px;
  padding: 16px 18px 12px;
  display: flex;
  flex-direction: column;
  box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
}

.filter-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}

.filter-spacer {
  flex: 1;
}

.result-hint {
  font-size: 13px;
  color: #6b7280;
}

.script-table {
  flex: 1;
}

.row-index {
  font-variant-numeric: tabular-nums;
  color: #6b7280;
  font-weight: 500;
}

.name-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
  align-items: flex-start;
}

.name-link {
  border: none;
  background: none;
  padding: 0;
  color: #2563eb;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
}

.name-link:hover {
  text-decoration: underline;
}

.name-meta {
  font-size: 12px;
  color: #9ca3af;
}

.table-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-wrap: wrap;
}

.danger-text {
  color: #dc2626;
}

.pagination-container {
  margin-top: 14px;
  display: flex;
  justify-content: flex-end;
}

.script-content {
  margin-top: 16px;

  h4 {
    margin: 0 0 10px;
    font-size: 14px;
    color: #374151;
  }
}

.code-view,
.code-editor {
  background: #111827;
  color: #e5e7eb;
  padding: 14px;
  border-radius: 8px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
  line-height: 1.55;
}

.code-view {
  max-height: 420px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
}

.script-editor {
  display: flex;
  flex-direction: column;
  height: 600px;
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0 12px;
}

.script-name {
  font-weight: 600;
  font-size: 15px;
}

.editor-container {
  flex: 1;
}

.code-editor {
  width: 100%;
  height: 100%;
  border: 1px solid #1f2937;
  outline: none;
  resize: none;
  box-sizing: border-box;
}
</style>
