<template>
  <div class="page-container execution-page">
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">{{ $t('uiAutomation.execution.title') }}</h1>
        <p class="page-subtitle">用例与脚本执行历史，支持详情、重跑与自愈诊断</p>
      </div>
      <div class="header-actions">
        <el-select
          v-model="projectId"
          :placeholder="$t('uiAutomation.common.selectProject')"
          filterable
          clearable
          style="width: 220px"
          @change="onProjectChange"
        >
          <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
        </el-select>
        <el-button @click="loadExecutions" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <div class="card-container">
      <div class="filter-bar">
        <el-input
          v-model="queryParams.search"
          :placeholder="$t('uiAutomation.execution.searchPlaceholder')"
          clearable
          style="width: 220px"
          @keyup.enter="handleSearch"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-select v-model="queryParams.recordType" placeholder="类型" clearable style="width: 120px" @change="handleSearch">
          <el-option label="全部" value="" />
          <el-option label="用例" value="case" />
          <el-option label="脚本" value="script" />
        </el-select>
        <el-select v-model="queryParams.status" :placeholder="$t('uiAutomation.execution.statusFilter')" clearable style="width: 120px">
          <el-option :label="$t('uiAutomation.status.pending')" value="pending" />
          <el-option :label="$t('uiAutomation.status.running')" value="running" />
          <el-option :label="$t('uiAutomation.status.passed')" value="passed" />
          <el-option :label="$t('uiAutomation.status.failed')" value="failed" />
          <el-option :label="$t('uiAutomation.status.error')" value="error" />
        </el-select>
        <el-select v-model="queryParams.browser" :placeholder="$t('uiAutomation.execution.browserFilter')" clearable style="width: 120px">
          <el-option label="Chrome" value="chrome" />
          <el-option label="Firefox" value="firefox" />
          <el-option label="Safari" value="safari" />
          <el-option label="Edge" value="edge" />
        </el-select>
        <el-button type="primary" @click="handleSearch">{{ $t('uiAutomation.common.query') }}</el-button>
        <el-button @click="resetQuery">{{ $t('uiAutomation.common.reset') }}</el-button>
        <div class="filter-spacer" />
        <span class="result-hint">共 {{ displayTotal }} 条</span>
        <el-button
          type="danger"
          plain
          :disabled="selectedIds.length === 0"
          @click="handleBatchDelete"
        >
          {{ $t('uiAutomation.common.batchDelete') }}
          <template v-if="selectedIds.length"> ({{ selectedIds.length }})</template>
        </el-button>
      </div>

      <el-table
        :data="filteredExecutions"
        v-loading="loading"
        class="data-table"
        row-key="id"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="48" align="center" />
        <el-table-column label="序号" width="70" align="center">
          <template #default="{ $index }">
            <span class="row-index">{{ reverseIndex($index) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="test_case_name" :label="$t('uiAutomation.execution.caseName')" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <button type="button" class="name-link" @click="viewExecutionDetail(row)">{{ row.test_case_name }}</button>
          </template>
        </el-table-column>
        <el-table-column :label="$t('uiAutomation.execution.relatedObject')" width="90" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.record_type === 'script'" type="success" size="small" effect="plain">脚本</el-tag>
            <el-tag v-else-if="row.test_suite" type="warning" size="small" effect="plain">{{ $t('uiAutomation.execution.suiteTag') }}</el-tag>
            <el-tag v-else type="info" size="small" effect="plain">{{ $t('uiAutomation.execution.case') }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" :label="$t('uiAutomation.execution.statusFilter')" width="96" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small" effect="plain">{{ getStatusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="engine" :label="$t('uiAutomation.execution.testEngine')" width="110" align="center">
          <template #default="{ row }">
            {{ getEngineText(row.engine) }}
          </template>
        </el-table-column>
        <el-table-column prop="browser" :label="$t('uiAutomation.execution.browserFilter')" width="100" align="center">
          <template #default="{ row }">
            {{ getBrowserText(row.browser) }}
            <span class="mode-hint">{{ row.headless ? '无头' : '有头' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_by_name" :label="$t('uiAutomation.execution.executor')" width="100" align="center" />
        <el-table-column prop="started_at" :label="$t('uiAutomation.execution.startTime')" width="170" align="center">
          <template #default="{ row }">
            {{ formatDateTime(row.started_at) }}
          </template>
        </el-table-column>
        <el-table-column :label="$t('uiAutomation.execution.duration')" width="100" align="center">
          <template #default="{ row }">
            {{ formatDuration(row.execution_time) }}
          </template>
        </el-table-column>
        <el-table-column :label="$t('uiAutomation.common.operation')" width="220" fixed="right" align="center">
          <template #default="{ row }">
            <div class="table-actions">
              <el-button size="small" type="primary" link @click="viewExecutionDetail(row)">
                {{ $t('uiAutomation.common.details') }}
              </el-button>
              <el-button
                v-if="row.record_type !== 'script' && (row.status === 'failed' || row.status === 'error')"
                size="small"
                type="warning"
                link
                @click="showRerunDialog(row)"
              >
                {{ $t('uiAutomation.common.rerun') }}
              </el-button>
              <el-button
                v-if="row.status === 'failed' || row.status === 'error'"
                size="small"
                type="success"
                link
                @click="openHealDiagnosis(row)"
              >
                自愈
              </el-button>
              <el-button link type="danger" size="small" @click="handleDelete(row)">
                {{ $t('uiAutomation.common.delete') }}
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-container">
        <el-pagination
          v-model:current-page="pagination.currentPage"
          v-model:page-size="pagination.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          :total="total"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </div>

    <!-- 执行详情对话框 -->
    <el-dialog v-model="showDetailDialog" :title="$t('uiAutomation.execution.executionDetail')" width="900px" class="detail-dialog">
      <div v-if="currentExecution" class="execution-detail">
        <!-- 基本信息 -->
        <el-descriptions :column="2" border>
          <el-descriptions-item :label="$t('uiAutomation.execution.caseName')">{{ currentExecution.test_case_name }}</el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.execution.statusFilter')">
            <el-tag :type="getStatusType(currentExecution.status)">{{ getStatusText(currentExecution.status) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.execution.browserFilter')">{{ getBrowserText(currentExecution.browser) }}</el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.execution.executor')">{{ currentExecution.created_by_name }}</el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.execution.startTime')">{{ formatDateTime(currentExecution.started_at) }}</el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.execution.endTime')">{{ formatDateTime(currentExecution.finished_at) }}</el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.execution.duration')" :span="2">{{ formatDuration(currentExecution.execution_time) }}</el-descriptions-item>
        </el-descriptions>

        <!-- 执行结果选项卡 -->
        <el-tabs v-model="activeTab" class="execution-tabs" style="margin-top: 20px;">
          <!-- 执行日志 - 所有状态都显示 -->
          <el-tab-pane :label="$t('uiAutomation.execution.executionLogs')" name="logs">
            <div class="logs-container">
              <div v-if="currentExecution.execution_logs">
                <template v-if="currentExecution.record_type === 'script'">
                  <pre class="error-text">{{ currentExecution.execution_logs }}</pre>
                </template>
                <template v-else>
                  <div v-for="(step, index) in parseExecutionLogs(currentExecution.execution_logs)" :key="index" class="log-item">
                    <div class="log-header">
                      <el-tag :type="step.success ? 'success' : 'danger'" size="small">
                        {{ $t('uiAutomation.execution.step') }} {{ step.step_number }}
                      </el-tag>
                      <span class="log-action">{{ getActionText(step.action_type) }}</span>
                      <span class="log-desc">{{ step.description }}</span>
                    </div>
                    <div v-if="step.error" class="log-error">
                      <el-icon><WarningFilled /></el-icon>
                      <pre class="error-message">{{ step.error }}</pre>
                    </div>
                  </div>
                </template>
              </div>
              <el-empty v-else :description="$t('uiAutomation.execution.noLogs')" />
            </div>
          </el-tab-pane>

          <!-- 失败截图 - 仅失败或错误状态显示 -->
          <el-tab-pane :label="$t('uiAutomation.execution.failedScreenshots')" name="screenshots" v-if="currentExecution.status === 'failed' || currentExecution.status === 'error'">
            <div class="screenshots-container">
              <div v-if="currentExecution.screenshots && currentExecution.screenshots.length > 0">
                <div v-for="(screenshot, index) in currentExecution.screenshots" :key="index" class="screenshot-item">
                  <h5>{{ screenshot.description || `${$t('uiAutomation.execution.screenshot')} ${index + 1}` }}</h5>
                  <!-- 检查截图URL是否有效 -->
                  <div v-if="screenshot.url" class="screenshot-wrapper">
                    <img
                      :src="screenshot.url"
                      :alt="screenshot.description"
                      class="screenshot-img"
                      @error="handleImageError($event, screenshot)"
                    />
                  </div>
                  <div v-else class="screenshot-error">
                    <el-icon><WarningFilled /></el-icon>
                    <span>{{ $t('uiAutomation.execution.screenshotFailed') }}{{ screenshot.error || $t('uiAutomation.execution.unknownReason') }}</span>
                  </div>
                  <p class="screenshot-time">{{ formatDateTime(screenshot.timestamp) }}</p>
                </div>
              </div>
              <el-empty v-else :description="$t('uiAutomation.execution.noScreenshots')" />
            </div>
          </el-tab-pane>

          <!-- 错误信息 - 仅失败或错误状态显示 -->
          <el-tab-pane :label="$t('uiAutomation.execution.errorInfo')" name="error" v-if="currentExecution.status === 'failed' || currentExecution.status === 'error'">
            <div class="errors-container">
              <div v-if="currentExecution.error_message" class="error-item">
                <div class="error-content">
                  <pre class="error-text">{{ currentExecution.error_message }}</pre>
                </div>
              </div>
              <el-empty v-else :description="$t('uiAutomation.execution.noError')" />
            </div>
          </el-tab-pane>

          <!-- 自愈诊断 -->
          <el-tab-pane
            label="自愈"
            name="heal"
            v-if="currentExecution.status === 'failed' || currentExecution.status === 'error'"
          >
            <div class="heal-tab" v-loading="detailHealLoading">
              <div class="heal-tab-actions">
                <el-button type="primary" size="small" :loading="detailHealLoading" @click="loadDetailHeal(true)">
                  {{ detailHealDiagnosis ? '重新诊断' : '开始诊断' }}
                </el-button>
                <el-button
                  v-if="detailHealDiagnosis"
                  size="small"
                  @click="openHealFromDetail"
                >
                  在侧栏打开
                </el-button>
              </div>
              <template v-if="detailHealDiagnosis">
                <el-descriptions :column="1" border size="small" class="heal-desc">
                  <el-descriptions-item label="分类">
                    {{ detailHealDiagnosis.category_display || detailHealDiagnosis.category }}
                  </el-descriptions-item>
                  <el-descriptions-item label="置信度">
                    {{ ((detailHealDiagnosis.confidence || 0) * 100).toFixed(0) }}%
                  </el-descriptions-item>
                  <el-descriptions-item label="摘要">
                    {{ detailHealDiagnosis.summary }}
                  </el-descriptions-item>
                </el-descriptions>
                <h4 class="heal-proposals-title">修复提案</h4>
                <el-card
                  v-for="p in detailHealProposals"
                  :key="p.id"
                  shadow="never"
                  class="heal-proposal-card"
                >
                  <div class="heal-proposal-head">
                    <el-tag size="small">{{ p.target_display || p.target }}</el-tag>
                    <el-tag size="small" type="info">{{ p.status_display || p.status }}</el-tag>
                    <span>{{ p.title }}</span>
                  </div>
                  <pre class="heal-diff">{{ p.diff || JSON.stringify(p.patch_payload, null, 2) }}</pre>
                  <el-button
                    v-if="p.target === 'test_asset' && p.status !== 'applied' && p.status !== 'rolled_back'"
                    type="primary"
                    size="small"
                    :loading="detailApplying === p.id"
                    @click="applyDetailHealProposal(p)"
                  >
                    应用测试修复
                  </el-button>
                </el-card>
                <el-empty v-if="!detailHealProposals.length" description="暂无修复提案" />
              </template>
              <el-empty v-else-if="!detailHealLoading" description="暂无诊断结果，可点击「开始诊断」" />
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>
      <template #footer>
        <el-button @click="showDetailDialog = false">{{ $t('uiAutomation.common.close') }}</el-button>
      </template>
    </el-dialog>

    <!-- 重跑测试用例对话框 -->
    <el-dialog v-model="showRerunDialogVisible" :title="$t('uiAutomation.execution.rerunTitle')" width="500px">
      <el-form :model="rerunFormData" label-width="100px">
        <el-form-item :label="$t('uiAutomation.execution.testEngine')">
          <el-radio-group v-model="rerunFormData.engine">
            <el-radio label="playwright">Playwright</el-radio>
            <el-radio label="selenium">Selenium</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item :label="$t('uiAutomation.execution.browserFilter')">
          <el-select v-model="rerunFormData.browser" style="width: 100%">
            <el-option label="Chrome" value="chrome" />
            <el-option label="Firefox" value="firefox" />
            <el-option label="Safari" value="safari" />
            <el-option label="Edge" value="edge" />
          </el-select>
        </el-form-item>
        <el-form-item :label="$t('uiAutomation.execution.executionMode')">
          <el-radio-group v-model="rerunFormData.headless">
            <el-radio :label="false">{{ $t('uiAutomation.execution.headedMode') }}</el-radio>
            <el-radio :label="true">{{ $t('uiAutomation.execution.headlessMode') }}</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRerunDialogVisible = false">{{ $t('uiAutomation.common.cancel') }}</el-button>
        <el-button type="primary" @click="handleRerun" :loading="rerunning">{{ $t('uiAutomation.execution.confirmRerun') }}</el-button>
      </template>
    </el-dialog>

    <FailureDiagnosisPanel
      v-model="showHealPanel"
      :diagnosis="healDiagnosis"
      :proposals="healProposals"
      :loading="healLoading"
      @refresh="loadHealForCurrent"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, View, WarningFilled, Refresh } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import {
  getTestCaseExecutions,
  getTestExecutions,
  getUiProjects,
  deleteTestCaseExecution,
  deleteTestExecution,
  batchDeleteTestCaseExecutions,
  runTestCase,
  listFailureDiagnoses,
  diagnoseTestCaseExecution,
  diagnoseTestExecution,
  applyScriptFix
} from '@/api/ui_automation'
import FailureDiagnosisPanel from '../ai/FailureDiagnosisPanel.vue'
import { resolveUiProjectId, saveUiProjectId } from '@/utils/uiAutomationProject'

const route = useRoute()
const { t } = useI18n()

const showHealPanel = ref(false)
const healDiagnosis = ref(null)
const healProposals = ref([])
const healLoading = ref(false)
const healExecutionId = ref(null)
const healExecutionType = ref('testcase')

const detailHealLoading = ref(false)
const detailHealDiagnosis = ref(null)
const detailHealProposals = ref([])
const detailApplying = ref(null)

function healQueryForRow(row) {
  const isScript = row?.record_type === 'script'
  return {
    execution_type: isScript ? 'script' : 'testcase',
    execution_id: row?.raw_id || row?.id
  }
}

async function openHealDiagnosis(row) {
  const q = healQueryForRow(row)
  healExecutionId.value = q.execution_id
  healExecutionType.value = q.execution_type
  showHealPanel.value = true
  healLoading.value = true
  try {
    const list = await listFailureDiagnoses(q)
    const rows = list.data?.results || list.data || []
    if (rows[0]) {
      healDiagnosis.value = rows[0]
      healProposals.value = rows[0].proposals || rows[0].fix_proposals || []
    } else if (q.execution_type === 'script') {
      const res = await diagnoseTestExecution(q.execution_id, { use_llm: true })
      healDiagnosis.value = res.data?.diagnosis
      healProposals.value = res.data?.proposals || []
    } else {
      const res = await diagnoseTestCaseExecution(q.execution_id, { use_llm: true })
      healDiagnosis.value = res.data?.diagnosis
      healProposals.value = res.data?.proposals || []
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.error || e.message || '诊断失败')
  } finally {
    healLoading.value = false
  }
}

async function loadHealForCurrent() {
  if (!healExecutionId.value) return
  const list = await listFailureDiagnoses({
    execution_type: healExecutionType.value,
    execution_id: healExecutionId.value
  })
  const rows = list.data?.results || list.data || []
  if (rows[0]) {
    healDiagnosis.value = rows[0]
    healProposals.value = rows[0].proposals || rows[0].fix_proposals || []
  }
}

async function loadDetailHeal(forceDiagnose = false) {
  const row = currentExecution.value
  if (!row || (row.status !== 'failed' && row.status !== 'error')) return
  const q = healQueryForRow(row)
  detailHealLoading.value = true
  try {
    if (!forceDiagnose) {
      const list = await listFailureDiagnoses(q)
      const rows = list.data?.results || list.data || []
      if (rows[0]) {
        detailHealDiagnosis.value = rows[0]
        detailHealProposals.value = rows[0].proposals || rows[0].fix_proposals || []
        return
      }
    }
    const res = q.execution_type === 'script'
      ? await diagnoseTestExecution(q.execution_id, { use_llm: true, force: forceDiagnose })
      : await diagnoseTestCaseExecution(q.execution_id, { use_llm: true })
    detailHealDiagnosis.value = res.data?.diagnosis
    detailHealProposals.value = res.data?.proposals || []
  } catch (e) {
    if (forceDiagnose) {
      ElMessage.error(e.response?.data?.error || e.message || '诊断失败')
    }
  } finally {
    detailHealLoading.value = false
  }
}

function openHealFromDetail() {
  if (!currentExecution.value) return
  healDiagnosis.value = detailHealDiagnosis.value
  healProposals.value = detailHealProposals.value
  const q = healQueryForRow(currentExecution.value)
  healExecutionId.value = q.execution_id
  healExecutionType.value = q.execution_type
  showHealPanel.value = true
}

async function applyDetailHealProposal(proposal) {
  if (!detailHealDiagnosis.value?.id) return
  detailApplying.value = proposal.id
  try {
    await applyScriptFix(detailHealDiagnosis.value.id, {
      proposal_id: proposal.id
    })
    ElMessage.success('已应用修复')
    await loadDetailHeal(false)
  } catch (e) {
    ElMessage.error(e.response?.data?.error || e.message || '应用失败')
  } finally {
    detailApplying.value = null
  }
}

// 项目和执行数据
const projects = ref([])
const projectId = ref('')
const executions = ref([])
const loading = ref(false)
const total = ref(0)
const pagination = reactive({
  currentPage: 1,
  pageSize: 20
})

// 搜索和筛选
const queryParams = reactive({
  project: undefined,
  search: '',
  status: '',
  browser: '',
  recordType: ''
})
const selectedIds = ref([])

const filteredExecutions = computed(() => executions.value)

const displayTotal = computed(() => Number(total.value) || executions.value.length || 0)

const reverseIndex = (index) => {
  const n = displayTotal.value
  const page = Number(pagination.currentPage) || 1
  const size = Number(pagination.pageSize) || 20
  return Math.max(1, n - (page - 1) * size - index)
}

// 详情对话框相关
const showDetailDialog = ref(false)
const activeTab = ref('logs')
const currentExecution = ref(null)

// 重跑对话框相关
const showRerunDialogVisible = ref(false)
const rerunning = ref(false)
const rerunFormData = reactive({
  testCaseId: null,
  engine: 'playwright',
  browser: 'chrome',
  headless: false
})

// 格式化日期时间
const formatDateTime = (dateString) => {
  if (!dateString) return '-'
  const date = new Date(dateString)
  if (isNaN(date.getTime())) return '-'
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

// 处理图片加载错误
const handleImageError = (event, screenshot) => {
  console.error('Screenshot load failed:', screenshot)
  const img = event.target
  img.style.display = 'none'
  // Show error message after image
  const errorDiv = img.parentElement.querySelector('.img-load-error')
  if (!errorDiv) {
    const div = document.createElement('div')
    div.className = 'img-load-error'
    div.innerHTML = `
      <i class="el-icon-warning"></i>
      <span>${t('uiAutomation.execution.imageLoadFailed')}</span>
    `
    img.parentElement.appendChild(div)
  }
}

// 格式化持续时间（execution_time单位是秒）
const formatDuration = (seconds) => {
  if (!seconds && seconds !== 0) return '-'

  const totalSeconds = Math.floor(seconds)
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const secs = totalSeconds % 60

  if (hours > 0) {
    return `${hours}h ${minutes}m ${secs}s`
  } else if (minutes > 0) {
    return `${minutes}m ${secs}s`
  } else {
    return `${secs}s`
  }
}

// 获取状态样式
const getStatusType = (status) => {
  const statusMap = {
    'pending': 'info',
    'running': 'warning',
    'passed': 'success',
    'failed': 'danger',
    'error': 'danger'
  }
  return statusMap[status] || 'info'
}

// 获取状态文本
const getStatusText = (status) => {
  const statusMap = {
    'pending': t('uiAutomation.status.pending'),
    'running': t('uiAutomation.status.running'),
    'passed': t('uiAutomation.status.passed'),
    'failed': t('uiAutomation.status.failed'),
    'error': t('uiAutomation.status.error')
  }
  return statusMap[status] || status
}

// 获取浏览器文本
const getBrowserText = (browser) => {
  const browserMap = {
    'chrome': 'Chrome',
    'firefox': 'Firefox',
    'safari': 'Safari',
    'edge': 'Edge'
  }
  return browserMap[browser] || browser || 'Chrome'
}

// 获取测试引擎文本
const getEngineText = (engine) => {
  const engineMap = {
    'playwright': 'Playwright',
    'selenium': 'Selenium'
  }
  return engineMap[engine] || engine || 'Playwright'
}

// 获取操作类型文本
const getActionText = (actionType) => {
  const actionMap = {
    'click': t('uiAutomation.actionTypes.click'),
    'fill': t('uiAutomation.actionTypes.fill'),
    'getText': t('uiAutomation.actionTypes.getText'),
    'waitFor': t('uiAutomation.actionTypes.waitFor'),
    'hover': t('uiAutomation.actionTypes.hover'),
    'scroll': t('uiAutomation.actionTypes.scroll'),
    'screenshot': t('uiAutomation.actionTypes.screenshot'),
    'assert': t('uiAutomation.actionTypes.assert'),
    'wait': t('uiAutomation.actionTypes.wait')
  }
  return actionMap[actionType] || actionType
}

// 解析执行日志
const parseExecutionLogs = (logs) => {
  if (!logs) return []
  try {
    return typeof logs === 'string' ? JSON.parse(logs) : logs
  } catch (e) {
    console.error('解析执行日志失败:', e)
    return []
  }
}

// 加载项目列表
const loadProjects = async () => {
  try {
    const response = await getUiProjects({ page_size: 100 })
    projects.value = response.data.results || response.data
  } catch (error) {
    ElMessage.error(t('uiAutomation.project.messages.loadFailed'))
    console.error('获取项目列表失败:', error)
  }
}

const SCRIPT_STATUS_MAP = {
  PENDING: 'pending',
  RUNNING: 'running',
  SUCCESS: 'passed',
  FAILED: 'failed',
  ABORTED: 'error'
}

const mapScriptExecutionRow = (execution) => {
  const status = SCRIPT_STATUS_MAP[execution.status]
    || String(execution.status || '').toLowerCase()
  const browserRaw = execution.browser || execution.environment || 'chrome'
  const browser = String(browserRaw).toLowerCase().replace(/^chrome$/, 'chrome')
  const name = execution.test_script?.name
    || (typeof execution.test_suite_name === 'string' ? execution.test_suite_name.replace(/^\[脚本\]\s*/, '') : '')
    || `脚本 #${execution.test_script?.id || execution.id}`

  return {
    id: `script-${execution.id}`,
    raw_id: execution.id,
    record_type: 'script',
    test_case_name: name,
    test_suite: null,
    status,
    engine: execution.engine || execution.test_script?.framework || 'playwright',
    browser,
    headless: execution.headless,
    execution_time: execution.duration,
    created_by_name: execution.executed_by_name,
    started_at: execution.started_at,
    finished_at: execution.finished_at,
    created_at: execution.created_at,
    error_message: execution.error_message,
    execution_logs: (execution.result_data && execution.result_data.logs) || execution.error_message || '',
    screenshots: []
  }
}

// 加载执行列表（用例执行 + 脚本执行）
const loadExecutions = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.currentPage,
      page_size: pagination.pageSize,
      search: queryParams.search || undefined,
      browser: queryParams.browser || undefined
    }

    if (projectId.value) {
      params.project = projectId.value
    }

    const caseStatus = queryParams.status || undefined
    const scriptStatusMap = {
      pending: 'PENDING',
      running: 'RUNNING',
      passed: 'SUCCESS',
      failed: 'FAILED',
      error: 'FAILED'
    }
    const scriptStatus = caseStatus ? scriptStatusMap[caseStatus] : undefined
    const recordType = queryParams.recordType
    const loadCase = recordType !== 'script'
    const loadScript = recordType !== 'case'

    const emptyRes = { data: { results: [], count: 0 } }
    const [caseRes, scriptRes] = await Promise.all([
      loadCase
        ? getTestCaseExecutions({ ...params, status: caseStatus })
        : Promise.resolve(emptyRes),
      loadScript
        ? getTestExecutions({
            ...params,
            status: scriptStatus,
            has_script: 1
          }).catch(() => emptyRes)
        : Promise.resolve(emptyRes)
    ])

    const caseRows = (caseRes.data.results || caseRes.data || []).map((row) => ({
      ...row,
      record_type: 'case',
      raw_id: row.id
    }))

    const scriptRows = (scriptRes.data.results || scriptRes.data || []).map(mapScriptExecutionRow)

    const merged = [...caseRows, ...scriptRows].sort(
      (a, b) => new Date(b.created_at || b.started_at || 0) - new Date(a.created_at || a.started_at || 0)
    )
    executions.value = merged
    const caseCount = caseRes.data.count ?? caseRows.length
    const scriptCount = scriptRes.data.count ?? scriptRows.length
    total.value = caseCount + scriptCount
  } catch (error) {
    ElMessage.error(t('uiAutomation.execution.messages.loadFailed'))
    console.error('获取执行列表失败:', error)
  } finally {
    loading.value = false
  }
}

// 项目变更处理（仅用户切换时写入记忆；初始化赋值不触发 el-select change）
const onProjectChange = () => {
  saveUiProjectId(projectId.value)
  queryParams.search = ''
  queryParams.status = ''
  queryParams.browser = ''
  queryParams.recordType = ''
  pagination.currentPage = 1
  loadExecutions()
}

// 搜索处理
const handleSearch = () => {
  pagination.currentPage = 1
  loadExecutions()
}

// 重置查询
const resetQuery = () => {
  queryParams.search = ''
  queryParams.status = ''
  queryParams.browser = ''
  queryParams.recordType = ''
  pagination.currentPage = 1
  loadExecutions()
}

// 分页处理
const handleSizeChange = (val) => {
  pagination.pageSize = val
  pagination.currentPage = 1
  loadExecutions()
}

const handleCurrentChange = (val) => {
  pagination.currentPage = val
  loadExecutions()
}

// 表格多选（脚本行用 raw_id；批量删除仅支持用例执行）
const handleSelectionChange = (selection) => {
  selectedIds.value = selection
    .filter((item) => item.record_type !== 'script')
    .map((item) => item.raw_id || item.id)
}

// 删除单个执行记录
const handleDelete = (row) => {
  ElMessageBox.confirm(t('uiAutomation.execution.messages.deleteConfirm'), t('uiAutomation.messages.confirm.tip'), {
    confirmButtonText: t('uiAutomation.common.confirm'),
    cancelButtonText: t('uiAutomation.common.cancel'),
    type: 'warning'
  }).then(async () => {
    try {
      if (row.record_type === 'script') {
        await deleteTestExecution(row.raw_id)
      } else {
        await deleteTestCaseExecution(row.raw_id || row.id)
      }
      ElMessage.success(t('uiAutomation.execution.messages.deleteSuccess'))
      loadExecutions()
    } catch (error) {
      console.error('删除失败:', error)
      ElMessage.error(t('uiAutomation.execution.messages.deleteFailed'))
    }
  })
}

// 批量删除执行记录
const handleBatchDelete = () => {
  if (selectedIds.value.length === 0) return

  ElMessageBox.confirm(t('uiAutomation.execution.messages.batchDeleteConfirm', { count: selectedIds.value.length }), t('uiAutomation.messages.confirm.tip'), {
    confirmButtonText: t('uiAutomation.common.confirm'),
    cancelButtonText: t('uiAutomation.common.cancel'),
    type: 'warning'
  }).then(async () => {
    try {
      await batchDeleteTestCaseExecutions(selectedIds.value)
      ElMessage.success(t('uiAutomation.execution.messages.batchDeleteSuccess'))
      selectedIds.value = []
      loadExecutions()
    } catch (error) {
      console.error('批量删除失败:', error)
      ElMessage.error(t('uiAutomation.execution.messages.batchDeleteFailed'))
    }
  })
}

// 查看执行详情
const viewExecutionDetail = (execution) => {
  currentExecution.value = execution
  activeTab.value = 'logs'
  detailHealDiagnosis.value = null
  detailHealProposals.value = []
  showDetailDialog.value = true
  if (execution.status === 'failed' || execution.status === 'error') {
    loadDetailHeal(false)
  }
}

watch(activeTab, (name) => {
  if (name === 'heal' && currentExecution.value && !detailHealDiagnosis.value) {
    loadDetailHeal(false)
  }
})

// 显示重跑对话框
const showRerunDialog = (execution) => {
  rerunFormData.testCaseId = execution.test_case
  rerunFormData.engine = execution.engine || 'playwright'
  rerunFormData.browser = execution.browser || 'chrome'
  rerunFormData.headless = execution.headless || false
  showRerunDialogVisible.value = true
}

// 执行重跑
const handleRerun = async () => {
  if (!rerunFormData.testCaseId) {
    ElMessage.error(t('uiAutomation.execution.messages.invalidCaseId'))
    return
  }

  rerunning.value = true
  try {
    const response = await runTestCase(rerunFormData.testCaseId, {
      engine: rerunFormData.engine,
      browser: rerunFormData.browser,
      headless: rerunFormData.headless
    })

    // 无论成功失败，都关闭弹框并刷新列表
    showRerunDialogVisible.value = false

    // 延迟一下再刷新，确保后端已经保存完成
    setTimeout(async () => {
      await loadExecutions()
    }, 500)

    // 根据返回结果显示消息
    if (response.data.success) {
      ElMessage.success(t('uiAutomation.execution.messages.rerunSuccess'))
    } else {
      ElMessage.warning(t('uiAutomation.execution.messages.rerunCompleteWithFailure') + ': ' + (response.data.errors?.[0]?.message || t('uiAutomation.execution.messages.viewDetails')))
    }
  } catch (error) {
    showRerunDialogVisible.value = false
    ElMessage.error(t('uiAutomation.execution.messages.rerunFailed') + ': ' + (error.response?.data?.message || error.message || t('uiAutomation.messages.error.unknown')))
    console.error('重跑失败:', error)
    // 即使失败也刷新列表，因为可能已经创建了执行记录
    setTimeout(async () => {
      await loadExecutions()
    }, 500)
  } finally {
    rerunning.value = false
  }
}

// 组件挂载时加载数据
onMounted(async () => {
  await loadProjects()
  const qProject = Number(route.query.project)
  if (qProject && projects.value.some((p) => Number(p.id) === qProject)) {
    projectId.value = qProject
  } else {
    projectId.value = resolveUiProjectId(projects.value, { fallbackToFirst: false })
  }
  await loadExecutions()
})
</script>

<style scoped lang="scss">
.execution-page {
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

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
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

.data-table {
  flex: 1;
}

.row-index {
  font-variant-numeric: tabular-nums;
  color: #6b7280;
  font-weight: 500;
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

.mode-hint {
  margin-left: 4px;
  font-size: 12px;
  color: #9ca3af;
}

.table-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-wrap: wrap;
  justify-content: center;
}

.pagination-container {
  margin-top: 14px;
  display: flex;
  justify-content: flex-end;
}

.execution-detail {
  .execution-tabs {
    margin-top: 20px;
  }

  .logs-container {
    max-height: 500px;
    overflow-y: auto;
    background: #f5f7fa;
    padding: 15px;
    border-radius: 4px;

    .log-item {
      margin-bottom: 15px;
      padding: 12px;
      background: white;
      border-radius: 4px;
      border-left: 3px solid #409eff;

      &:last-child {
        margin-bottom: 0;
      }

      .log-header {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 8px;

        .log-action {
          font-weight: 500;
          color: #606266;
        }

        .log-desc {
          color: #909399;
          font-size: 14px;
        }
      }

      .log-error {
        display: flex;
        align-items: flex-start;  /* 改为 flex-start，适配多行文本 */
        gap: 8px;
        color: #f56c6c;
        background: #fef0f0;
        padding: 8px 12px;
        border-radius: 4px;
        margin-top: 8px;
        font-size: 14px;

        .error-message {
          margin: 0;
          padding: 0;
          font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
          font-size: 13px;
          line-height: 1.6;
          white-space: pre-wrap;  /* 保留换行符和空格 */
          word-break: break-word;  /* 长单词换行 */
          flex: 1;
        }

        .el-icon {
          margin-top: 2px;  /* 图标与文本顶部对齐 */
          flex-shrink: 0;  /* 图标不缩小 */
        }
      }
    }
  }

  .screenshots-container {
    max-height: 600px;
    overflow-y: auto;
    padding: 10px;

    .screenshot-item {
      margin-bottom: 30px;
      text-align: center;

      h5 {
        margin: 0 0 15px 0;
        color: #303133;
        font-size: 14px;
      }

      .screenshot-wrapper {
        position: relative;
      }

      .screenshot-img {
        max-width: 100%;
        border: 1px solid #dcdfe6;
        border-radius: 4px;
        box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
      }

      .screenshot-error {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 12px 20px;
        background: #fef0f0;
        color: #f56c6c;
        border: 1px solid #fbc4c4;
        border-radius: 4px;
        font-size: 14px;

        .el-icon {
          font-size: 16px;
        }
      }

      .img-load-error {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 12px 20px;
        background: #fff7e6;
        color: #e6a23c;
        border: 1px solid #f5dab1;
        border-radius: 4px;
        font-size: 14px;
        margin-top: 10px;

        i {
          font-size: 16px;
        }
      }

      .screenshot-time {
        margin: 10px 0 0 0;
        color: #909399;
        font-size: 12px;
      }
    }
  }

  .errors-container {
    padding: 10px;
    height: 100%;
    overflow-y: auto;
  }

  .error-item {
    background: #fff;
    border: 2px solid #f56c6c;
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 15px;
  }

  .error-item:last-child {
    margin-bottom: 0;
  }

  .error-content {
    display: flex;
    flex-direction: column;
  }

  .error-text {
    margin: 0;
    padding: 15px;
    background: #2d2d2d;
    color: #ff6b6b;
    border-radius: 4px;
    font-family: 'Courier New', Courier, monospace;
    font-size: 13px;
    line-height: 1.6;
    white-space: pre-wrap;
    word-wrap: break-word;
    overflow-x: auto;
  }

  .error-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 15px;
    padding-bottom: 15px;
    border-bottom: 1px solid #f5f5f5;
  }

  .error-header .el-tag {
    font-size: 16px;
    padding: 10px 15px;
    font-weight: 600;
  }
}

.heal-tab {
  min-height: 160px;
}

.heal-tab-actions {
  margin-bottom: 12px;
  display: flex;
  gap: 8px;
}

.heal-desc {
  margin-bottom: 12px;
}

.heal-proposals-title {
  margin: 12px 0 8px;
  font-size: 14px;
}

.heal-proposal-card {
  margin-bottom: 10px;
}

.heal-proposal-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.heal-diff {
  margin: 0 0 10px;
  padding: 10px;
  background: #f5f7fa;
  border-radius: 4px;
  font-size: 12px;
  max-height: 180px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
