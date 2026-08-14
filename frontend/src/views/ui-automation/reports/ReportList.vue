<template>
  <div class="page-container report-page">
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">{{ $t('uiAutomation.report.title') }}</h1>
        <p class="page-subtitle">汇总用例与脚本执行结果，查看通过率、步骤日志与错误详情</p>
      </div>
      <div class="header-actions">
        <el-button @click="refreshReports" :loading="loading">
          <el-icon><Refresh /></el-icon>
          {{ $t('uiAutomation.report.refreshReport') }}
        </el-button>
      </div>
    </div>

    <div class="card-container">
      <div class="filter-bar">
        <el-select
          v-model="selectedProject"
          :placeholder="$t('uiAutomation.common.selectProject')"
          filterable
          clearable
          style="width: 220px"
          @change="onProjectChange"
        >
          <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
        </el-select>
        <el-select v-model="reportTypeFilter" placeholder="类型" clearable style="width: 120px" @change="onFilterChange">
          <el-option label="全部" value="" />
          <el-option label="用例" value="case" />
          <el-option label="脚本" value="script" />
          <el-option label="套件" value="suite" />
        </el-select>
        <el-select v-model="statusFilter" placeholder="状态" clearable style="width: 130px" @change="onFilterChange">
          <el-option label="成功" value="SUCCESS" />
          <el-option label="失败" value="FAILED" />
          <el-option label="运行中" value="RUNNING" />
          <el-option label="待执行" value="PENDING" />
        </el-select>
        <div class="filter-spacer" />
        <span class="result-hint">共 {{ filteredReports.length }} 条</span>
      </div>

      <el-table
        :data="pagedReports"
        v-loading="loading"
        class="data-table"
        row-key="id"
        empty-text="暂无测试报告"
      >
        <el-table-column label="序号" width="70" align="center">
          <template #default="{ $index }">
            <span class="row-index">{{ reverseIndex($index) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="test_suite_name" :label="$t('uiAutomation.report.testSuite')" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="name-cell">
              <button type="button" class="name-link" @click="viewReportDetail(row)">{{ row.test_suite_name }}</button>
              <span class="name-meta">
                <el-tag v-if="row.report_type === 'case'" size="small" type="info" effect="plain">
                  {{ $t('uiAutomation.execution.case') }}
                </el-tag>
                <el-tag v-else-if="row.report_type === 'script'" size="small" type="success" effect="plain">脚本</el-tag>
                <el-tag v-else size="small" type="warning" effect="plain">
                  {{ $t('uiAutomation.execution.suiteTag') }}
                </el-tag>
              </span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="status" :label="$t('uiAutomation.common.status')" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small" effect="plain">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="$t('uiAutomation.report.testEngine')" width="110" align="center">
          <template #default="{ row }">
            {{ getEngineText(row.engine) }}
          </template>
        </el-table-column>
        <el-table-column :label="$t('uiAutomation.report.browser')" width="90" align="center">
          <template #default="{ row }">
            {{ getBrowserText(row.browser) }}
          </template>
        </el-table-column>
        <el-table-column :label="$t('uiAutomation.report.passRate')" width="140" align="center">
          <template #default="{ row }">
            <div class="pass-cell">
              <span class="pass-text" :style="{ color: getProgressColor(row.pass_rate) }">{{ row.pass_rate }}%</span>
              <span class="pass-meta">{{ row.passed_cases }}/{{ row.total_cases }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column :label="$t('uiAutomation.report.duration')" width="100" align="center">
          <template #default="{ row }">
            {{ formatDuration(row.duration) }}
          </template>
        </el-table-column>
        <el-table-column prop="executed_by_name" :label="$t('uiAutomation.report.executor')" width="100" align="center" />
        <el-table-column prop="created_at" :label="$t('uiAutomation.report.executionTime')" width="170" align="center">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column :label="$t('uiAutomation.common.operation')" width="150" fixed="right" align="center">
          <template #default="{ row }">
            <div class="table-actions">
              <el-button link type="primary" size="small" @click="viewReportDetail(row)">
                {{ $t('uiAutomation.report.viewDetail') }}
              </el-button>
              <el-button link type="danger" size="small" @click="deleteReport(row)">
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
          :total="filteredReports.length"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </div>

    <!-- 报告详情对话框 -->
    <el-dialog
      v-model="showDetailDialog"
      :title="$t('uiAutomation.report.reportDetail')"
      width="80%"
      :close-on-click-modal="false"
      class="report-detail-dialog"
    >
      <div v-if="currentReport" class="report-detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item :label="$t('uiAutomation.report.reportId')">{{ currentReport.id }}</el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.report.testSuite')">{{ currentReport.test_suite_name }}</el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.report.executionStatus')">
            <el-tag :type="getStatusType(currentReport.status)" size="small" effect="plain">
              {{ getStatusText(currentReport.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.report.executor')">{{ currentReport.executed_by_name }}</el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.report.testEngine')">{{ getEngineText(currentReport.engine) }}</el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.report.browser')">{{ getBrowserText(currentReport.browser) }}</el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.report.executionMode')">{{ currentReport.headless ? $t('uiAutomation.report.headlessMode') : $t('uiAutomation.report.headedMode') }}</el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.report.duration')">{{ formatDuration(currentReport.duration) }}</el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.report.startTime')">{{ formatDate(currentReport.started_at) }}</el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.report.endTime')">{{ formatDate(currentReport.finished_at) }}</el-descriptions-item>
        </el-descriptions>

        <div class="statistics-section">
          <h4>{{ $t('uiAutomation.report.testStatistics') }}</h4>
          <div class="stat-grid">
            <div class="stat-card">
              <div class="stat-label">{{ $t('uiAutomation.report.totalCases') }}</div>
              <div class="stat-value">{{ currentReport.total_cases }}</div>
            </div>
            <div class="stat-card success">
              <div class="stat-label">{{ $t('uiAutomation.report.passedCases') }}</div>
              <div class="stat-value">{{ currentReport.passed_cases }}</div>
            </div>
            <div class="stat-card danger">
              <div class="stat-label">{{ $t('uiAutomation.report.failedCases') }}</div>
              <div class="stat-value">{{ currentReport.failed_cases }}</div>
            </div>
            <div class="stat-card warning">
              <div class="stat-label">{{ $t('uiAutomation.report.skippedCases') }}</div>
              <div class="stat-value">{{ currentReport.skipped_cases }}</div>
            </div>
          </div>

          <div class="pass-rate-chart">
            <div class="pass-rate-label">{{ $t('uiAutomation.report.passRate') }}: {{ currentReport.pass_rate }}%</div>
            <el-progress
              :percentage="currentReport.pass_rate"
              :color="getProgressColor(currentReport.pass_rate)"
              :stroke-width="12"
            />
          </div>
        </div>

        <div class="result-section">
          <h4>{{ $t('uiAutomation.report.executionResultDetail') }}</h4>
          <el-table
            :data="getCaseExecutionList(currentReport)"
            class="detail-case-table"
          >
            <el-table-column type="index" :label="$t('uiAutomation.report.sequence')" width="60" />
            <el-table-column prop="test_case_name" :label="$t('uiAutomation.report.testCase')" min-width="200" />
            <el-table-column :label="$t('uiAutomation.report.executionStatus')" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="row.status === 'passed' ? 'success' : 'danger'" size="small" effect="plain">
                  {{ row.status === 'passed' ? $t('uiAutomation.report.casePassed') : $t('uiAutomation.report.caseFailed') }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column :label="$t('uiAutomation.report.stepCount')" width="100" align="center">
              <template #default="{ row }">
                {{ row.steps ? row.steps.length : 0 }}
              </template>
            </el-table-column>
            <el-table-column :label="$t('uiAutomation.common.operation')" width="120" align="center">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="viewCaseDetail(row)">
                  {{ $t('uiAutomation.report.viewDetail') }}
                </el-button>
              </template>
            </el-table-column>
          </el-table>

          <div
            v-if="currentReport.report_type === 'script' && currentReport.result_data?.logs"
            class="script-report-logs"
          >
            <h4>{{ $t('uiAutomation.report.executionLogs') }}</h4>
            <pre class="error-text script-log-text">{{ currentReport.result_data.logs }}</pre>
          </div>
        </div>

        <div class="error-section" v-if="currentReport.error_message">
          <h4>{{ $t('uiAutomation.report.errorInfo') }}</h4>
          <div class="errors-container">
            <div class="error-item">
              <div class="error-content">
                <pre class="error-text">{{ currentReport.error_message }}</pre>
              </div>
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="showDetailDialog = false">{{ $t('uiAutomation.common.close') }}</el-button>
      </template>
    </el-dialog>

    <!-- 用例详情对话框 -->
    <el-dialog
      v-model="showCaseDetailDialog"
      :title="`${$t('uiAutomation.report.caseDetail')} - ${currentCase?.test_case_name || ''}`"
      width="900px"
      :close-on-click-modal="false"
    >
      <div v-if="currentCase" class="case-detail">
        <!-- 纯文本日志（脚本执行 / 非 JSON 步骤）优先完整展示 -->
        <div v-if="currentCase.log_text" class="log-container">
          <h4>{{ $t('uiAutomation.report.executionLogs') }}</h4>
          <pre class="error-text script-log-text">{{ currentCase.log_text }}</pre>
        </div>

        <!-- 用例执行成功 - 只显示执行日志 -->
        <div v-else-if="currentCase.status === 'passed'">
          <h4>{{ $t('uiAutomation.report.executionLogs') }}</h4>
          <div class="log-container">
            <div v-if="!currentCase.steps?.length" class="log-empty">
              <el-empty :description="$t('uiAutomation.report.noLogs') || '暂无日志'" />
            </div>
            <div v-for="(step, index) in currentCase.steps" :key="index" class="log-item">
              <div class="log-header">
                <el-tag :type="step.success ? 'success' : 'danger'" size="small">
                  {{ $t('uiAutomation.report.step') }} {{ step.step_number }}
                </el-tag>
                <span class="log-action">{{ getActionText(step.action_type) }}</span>
                <span class="log-desc">{{ step.description }}</span>
              </div>
              <div v-if="step.error" class="log-error">
                <el-icon><WarningFilled /></el-icon>
                {{ step.error }}
              </div>
            </div>
          </div>
        </div>

        <!-- 用例执行失败 - 显示执行日志、失败截图、错误信息三个tab -->
        <div v-else>
          <el-tabs v-model="activeTab" type="border-card">
            <!-- 执行日志 Tab -->
            <el-tab-pane :label="$t('uiAutomation.report.executionLogs')" name="logs">
              <div class="log-container">
                <div v-if="!currentCase.steps?.length" class="log-empty">
                  <el-empty :description="$t('uiAutomation.report.noLogs') || '暂无日志'" />
                </div>
                <div v-for="(step, index) in currentCase.steps" :key="index" class="log-item">
                  <div class="log-header">
                    <el-tag :type="step.success ? 'success' : 'danger'" size="small">
                      {{ $t('uiAutomation.report.step') }} {{ step.step_number }}
                    </el-tag>
                    <span class="log-action">{{ getActionText(step.action_type) }}</span>
                    <span class="log-desc">{{ step.description }}</span>
                  </div>
                  <div v-if="step.error" class="log-error">
                    <el-icon><WarningFilled /></el-icon>
                    <pre class="error-message">{{ step.error }}</pre>
                  </div>
                </div>
              </div>
            </el-tab-pane>

            <!-- 失败截图 Tab -->
            <el-tab-pane :label="$t('uiAutomation.report.failedScreenshots')" name="screenshots">
              <div v-if="currentCase.screenshots && currentCase.screenshots.length > 0" class="screenshot-container">
                <div v-for="(screenshot, index) in currentCase.screenshots" :key="index" class="screenshot-item">
                  <h5>{{ screenshot.description || `${$t('uiAutomation.report.screenshot')} ${index + 1}` }}</h5>
                  <img :src="screenshot.url" :alt="screenshot.description" class="screenshot-img" />
                  <p class="screenshot-time">{{ screenshot.timestamp }}</p>
                </div>
              </div>
              <el-empty v-else :description="$t('uiAutomation.report.noScreenshots')" />
            </el-tab-pane>

            <!-- 错误信息 Tab -->
            <el-tab-pane :label="$t('uiAutomation.report.errorInfo')" name="error">
              <div class="errors-container">
                <div v-if="currentCase.error" class="error-item">
                  <div class="error-content">
                    <pre class="error-text">{{ currentCase.error }}</pre>
                  </div>
                </div>
                <el-empty v-else :description="$t('uiAutomation.report.noError')" />
              </div>
            </el-tab-pane>
          </el-tabs>
        </div>
      </div>
      <template #footer>
        <el-button @click="showCaseDetailDialog = false">{{ $t('uiAutomation.common.close') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, WarningFilled } from '@element-plus/icons-vue'
import {
  getUiProjects,
  getTestExecutions,
  deleteTestExecution,
  getTestCaseExecutions,
  deleteTestCaseExecution
} from '@/api/ui_automation'
import { resolveUiProjectId, saveUiProjectId } from '@/utils/uiAutomationProject'

const { t } = useI18n()

const reports = ref([])
const projects = ref([])
const selectedProject = ref('')
const loading = ref(false)
const reportTypeFilter = ref('')
const statusFilter = ref('')
const pagination = reactive({
  currentPage: 1,
  pageSize: 20
})

const filteredReports = computed(() => {
  let list = reports.value
  if (reportTypeFilter.value) {
    list = list.filter((r) => {
      if (reportTypeFilter.value === 'suite') {
        return r.report_type !== 'case' && r.report_type !== 'script'
      }
      return r.report_type === reportTypeFilter.value
    })
  }
  if (statusFilter.value) {
    const want = String(statusFilter.value).toUpperCase()
    list = list.filter((r) => {
      const s = String(r.status || '').toUpperCase()
      if (want === 'FAILED') return s === 'FAILED' || s === 'ERROR'
      return s === want
    })
  }
  return list
})

const pagedReports = computed(() => {
  const start = (pagination.currentPage - 1) * pagination.pageSize
  return filteredReports.value.slice(start, start + pagination.pageSize)
})

const reverseIndex = (index) => {
  const n = filteredReports.value.length
  const page = Number(pagination.currentPage) || 1
  const size = Number(pagination.pageSize) || 20
  return Math.max(1, n - (page - 1) * size - index)
}

// 详情对话框
const showDetailDialog = ref(false)
const currentReport = ref(null)

// 用例详情对话框
const showCaseDetailDialog = ref(false)
const currentCase = ref(null)
const activeTab = ref('logs')

const CASE_STATUS_TO_REPORT = {
  pending: 'PENDING',
  running: 'RUNNING',
  passed: 'SUCCESS',
  failed: 'FAILED',
  error: 'FAILED'
}

const parseExecutionSteps = (logs) => {
  if (!logs) return []
  if (Array.isArray(logs)) return logs
  if (typeof logs === 'string') {
    try {
      const parsed = JSON.parse(logs)
      return Array.isArray(parsed) ? parsed : []
    } catch {
      return []
    }
  }
  return []
}

/** 从脚本纯文本日志解析步骤（codegen / script_runner 输出格式） */
const parseScriptLogToSteps = (logs) => {
  const text = (logs || '').trim()
  if (!text) return []

  const steps = []
  const stepRe = /==========\s*步骤\s*(\d+)\s*:\s*([^\s=]+)\s*==========/g
  const matches = [...text.matchAll(stepRe)]
  if (!matches.length) {
    return [{
      step_number: 1,
      action_type: 'script',
      description: '脚本执行日志',
      success: !/脚本执行失败|Traceback|Error:/i.test(text),
      error: null
    }]
  }

  matches.forEach((m, idx) => {
    const start = m.index + m[0].length
    const end = idx + 1 < matches.length ? matches[idx + 1].index : text.length
    const chunk = text.slice(start, end)
    const descMatch = chunk.match(/说明:\s*(.+)/)
    const failed = /✗|失败|Traceback|Error:|RuntimeError/i.test(chunk)
      && !/全部步骤成功|脚本执行成功|脚本进程结束\(成功\)/.test(chunk)
    steps.push({
      step_number: Number(m[1]) || idx + 1,
      action_type: (m[2] || 'script').trim(),
      description: (descMatch && descMatch[1].trim()) || `步骤 ${m[1]}`,
      success: !failed,
      error: failed ? chunk.trim().slice(0, 2000) : null
    })
  })
  return steps
}

const extractScriptLogs = (execution) => {
  const rd = execution?.result_data
  if (!rd) return ''
  if (typeof rd === 'string') {
    try {
      const parsed = JSON.parse(rd)
      return parsed?.logs || parsed?.stdout || rd
    } catch {
      return rd
    }
  }
  if (typeof rd === 'object') {
    return rd.logs || rd.stdout || ''
  }
  return ''
}

/** 将单用例执行记录映射为报告列表行 */
const mapCaseExecutionToReport = (execution) => {
  const status = CASE_STATUS_TO_REPORT[execution.status] || String(execution.status || '').toUpperCase()
  const passed = execution.status === 'passed' ? 1 : 0
  const failed = (execution.status === 'failed' || execution.status === 'error') ? 1 : 0
  const totalCases = 1
  const steps = parseExecutionSteps(execution.execution_logs)
  const logText = (!steps.length && typeof execution.execution_logs === 'string' && execution.execution_logs.trim())
    ? execution.execution_logs
    : ''
  const name = execution.test_suite_name || execution.test_case_name || `Case #${execution.test_case}`

  return {
    id: execution.id,
    report_type: 'case',
    test_suite_name: name,
    status,
    engine: execution.engine,
    browser: execution.browser,
    headless: execution.headless,
    total_cases: totalCases,
    passed_cases: passed,
    failed_cases: failed,
    skipped_cases: 0,
    pass_rate: passed ? 100 : 0,
    duration: execution.execution_time || 0,
    executed_by_name: execution.created_by_name,
    created_at: execution.created_at,
    started_at: execution.started_at,
    finished_at: execution.finished_at,
    error_message: execution.error_message,
    result_data: {
      test_cases: [
        {
          test_case_name: execution.test_case_name,
          status: execution.status,
          steps,
          log_text: logText,
          screenshots: execution.screenshots || [],
          error: execution.error_message
        }
      ]
    }
  }
}

const mapSuiteExecutionToReport = (execution) => {
  const isScript = !!(execution.test_script || execution.test_script_id)
  const base = {
    ...execution,
    report_type: isScript ? 'script' : 'suite',
    test_suite_name: execution.test_suite_name
      || (execution.test_script?.name ? `[脚本] ${execution.test_script.name}` : '-'),
    duration: execution.duration ?? execution.execution_time ?? 0
  }

  if (!isScript) {
    return base
  }

  const logs = extractScriptLogs(execution)
  const steps = parseScriptLogToSteps(logs)
  const caseStatus = (execution.status === 'SUCCESS' || execution.status === 'PASSED')
    ? 'passed'
    : (execution.status === 'RUNNING' || execution.status === 'PENDING')
      ? 'running'
      : 'failed'
  const scriptName = execution.test_script?.name
    || String(execution.test_suite_name || '').replace(/^\[脚本\]\s*/, '')
    || `Script #${execution.id}`

  return {
    ...base,
    result_data: {
      ...(typeof execution.result_data === 'object' && execution.result_data ? execution.result_data : {}),
      logs,
      test_cases: [
        {
          test_case_name: scriptName,
          status: caseStatus,
          steps,
          log_text: logs,
          screenshots: [],
          error: execution.error_message || ''
        }
      ]
    }
  }
}

// 加载项目列表
const loadProjects = async () => {
  try {
    const response = await getUiProjects({ page_size: 100 })
    projects.value = response.data.results || response.data
  } catch (error) {
    console.error('Failed to load projects:', error)
    ElMessage.error(t('uiAutomation.report.messages.loadProjectsFailed'))
  }
}

// 加载报告列表：套件执行 + 单用例执行（合并后前端筛选分页）
const loadReports = async () => {
  loading.value = true
  try {
    const params = {
      page: 1,
      page_size: 100
    }

    if (selectedProject.value) {
      params.project = selectedProject.value
    }

    const [suiteRes, caseRes] = await Promise.all([
      getTestExecutions(params).catch(() => ({ data: { results: [], count: 0 } })),
      getTestCaseExecutions(params).catch(() => ({ data: { results: [], count: 0 } }))
    ])

    const suiteList = (suiteRes.data.results || suiteRes.data || []).map(mapSuiteExecutionToReport)
    const caseList = (caseRes.data.results || caseRes.data || []).map(mapCaseExecutionToReport)

    reports.value = [...suiteList, ...caseList].sort(
      (a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0)
    )
  } catch (error) {
    console.error('Failed to load test reports:', error)
    ElMessage.error(t('uiAutomation.report.messages.loadFailed'))
  } finally {
    loading.value = false
  }
}

// 项目切换
const onProjectChange = async () => {
  saveUiProjectId(selectedProject.value)
  pagination.currentPage = 1
  await loadReports()
}

const onFilterChange = () => {
  pagination.currentPage = 1
}

// 刷新报告
const refreshReports = async () => {
  await loadReports()
  ElMessage.success(t('uiAutomation.report.messages.refreshed'))
}

// 分页处理
const handleSizeChange = () => {
  pagination.currentPage = 1
}

const handleCurrentChange = () => {}

// 查看报告详情
const viewReportDetail = (report) => {
  currentReport.value = report
  showDetailDialog.value = true
}

// 获取用例执行列表
const getCaseExecutionList = (report) => {
  if (!report || !report.result_data || !report.result_data.test_cases) {
    return []
  }
  return report.result_data.test_cases
}

// 查看用例详情
const viewCaseDetail = (caseData) => {
  currentCase.value = caseData
  activeTab.value = 'logs'
  showCaseDetailDialog.value = true
}

// 获取操作类型文本
const getActionText = (actionType) => {
  const actionMap = {
    'click': t('uiAutomation.actionTypes.click'),
    'fill': t('uiAutomation.actionTypes.fill'),
    'getText': t('uiAutomation.actionTypes.getText'),
    'waitFor': t('uiAutomation.actionTypes.waitFor'),
    'wait': t('uiAutomation.actionTypes.waitFor') || '等待',
    'hover': t('uiAutomation.actionTypes.hover'),
    'scroll': t('uiAutomation.actionTypes.scroll'),
    'screenshot': t('uiAutomation.actionTypes.screenshot'),
    'assert': t('uiAutomation.actionTypes.assert'),
    'switchTab': '切换标签',
    'script': '脚本'
  }
  return actionMap[actionType] || actionType
}

// 删除报告
const deleteReport = async (report) => {
  try {
    await ElMessageBox.confirm(
      t('uiAutomation.report.messages.deleteConfirm', { name: report.test_suite_name }),
      t('uiAutomation.report.messages.confirmDelete'),
      {
        confirmButtonText: t('uiAutomation.common.confirm'),
        cancelButtonText: t('uiAutomation.common.cancel'),
        type: 'warning'
      }
    )

    if (report.report_type === 'case') {
      await deleteTestCaseExecution(report.id)
    } else {
      await deleteTestExecution(report.id)
    }
    ElMessage.success(t('uiAutomation.report.messages.deleteSuccess'))
    await loadReports()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Failed to delete report:', error)
      ElMessage.error(t('uiAutomation.report.messages.deleteFailed'))
    }
  }
}

// 辅助方法
const getStatusType = (status) => {
  const normalized = String(status || '').toUpperCase()
  const typeMap = {
    'PENDING': 'info',
    'RUNNING': 'warning',
    'SUCCESS': 'success',
    'PASSED': 'success',
    'FAILED': 'danger',
    'ERROR': 'danger',
    'ABORTED': 'info'
  }
  return typeMap[normalized] || 'info'
}

const getStatusText = (status) => {
  const normalized = String(status || '').toUpperCase()
  const textMap = {
    'PENDING': t('uiAutomation.report.statusPending'),
    'RUNNING': t('uiAutomation.report.statusRunning'),
    'SUCCESS': t('uiAutomation.report.statusSuccess'),
    'PASSED': t('uiAutomation.report.statusSuccess'),
    'FAILED': t('uiAutomation.report.statusFailed'),
    'ERROR': t('uiAutomation.report.statusFailed'),
    'ABORTED': t('uiAutomation.report.statusAborted')
  }
  return textMap[normalized] || status
}

const getEngineText = (engine) => {
  const engineMap = {
    'playwright': 'Playwright',
    'selenium': 'Selenium'
  }
  return engineMap[engine] || engine || 'Playwright'
}

const getBrowserText = (browser) => {
  const browserMap = {
    'chrome': 'Chrome',
    'firefox': 'Firefox',
    'safari': 'Safari',
    'edge': 'Edge'
  }
  return browserMap[browser] || browser || 'Chrome'
}

const getProgressColor = (percentage) => {
  if (percentage >= 80) return '#67c23a'
  if (percentage >= 60) return '#e6a23c'
  return '#f56c6c'
}

const formatDate = (dateString) => {
  if (!dateString) return '-'
  return new Date(dateString).toLocaleString()
}

const formatDuration = (seconds) => {
  if (!seconds) return `0${t('uiAutomation.report.seconds')}`
  if (seconds < 60) return `${Number(seconds).toFixed(1)}${t('uiAutomation.report.seconds')}`
  const minutes = Math.floor(seconds / 60)
  const secs = (seconds % 60).toFixed(0)
  return `${minutes}${t('uiAutomation.report.minutes')}${secs}${t('uiAutomation.report.seconds')}`
}

onMounted(async () => {
  await loadProjects()
  selectedProject.value = resolveUiProjectId(projects.value, { fallbackToFirst: false })
  await loadReports()
})
</script>

<style scoped lang="scss">
.report-page {
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

.name-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
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
  text-align: left;
}

.name-link:hover {
  text-decoration: underline;
}

.name-meta {
  display: inline-flex;
}

.pass-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  line-height: 1.2;
}

.pass-text {
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.pass-meta {
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

.report-detail {
  .statistics-section {
    margin-top: 24px;

    h4 {
      margin: 0 0 14px;
      color: #1f2a37;
      font-size: 15px;
    }
  }

  .stat-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
  }

  .stat-card {
    background: #f8fafc;
    border: 1px solid #e5e9f0;
    padding: 16px;
    border-radius: 10px;
    text-align: center;

    &.success {
      background: #f0fdf4;
      border-color: #bbf7d0;
    }

    &.danger {
      background: #fef2f2;
      border-color: #fecaca;
    }

    &.warning {
      background: #fffbeb;
      border-color: #fde68a;
    }

    .stat-label {
      font-size: 13px;
      color: #6b7280;
      margin-bottom: 8px;
    }

    .stat-value {
      font-size: 28px;
      font-weight: 650;
      color: #1f2a37;
      font-variant-numeric: tabular-nums;
    }
  }

  .pass-rate-chart {
    margin-top: 18px;

    .pass-rate-label {
      margin-bottom: 10px;
      color: #374151;
      font-size: 14px;
      font-weight: 500;
    }
  }

  .result-section {
    margin-top: 24px;

    h4 {
      margin: 0 0 12px;
      color: #1f2a37;
      font-size: 15px;
    }
  }

  .detail-case-table {
    margin-top: 4px;
  }

  .error-section {
    margin-top: 24px;

    h4 {
      margin: 0 0 12px;
      color: #1f2a37;
      font-size: 15px;
    }
  }
}

@media (max-width: 900px) {
  .report-detail .stat-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

// 统一的错误信息样式
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

.script-log-text {
  color: #e8e8e8;
  max-height: 480px;
  overflow-y: auto;
}

.script-report-logs {
  margin-top: 20px;

  h4 {
    margin: 0 0 12px 0;
    color: #303133;
  }
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

// 用例详情样式
.case-detail {
  h4 {
    margin: 0 0 20px 0;
    color: #303133;
    font-size: 16px;
  }

  .log-container {
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
        align-items: center;
        gap: 8px;
        color: #f56c6c;
        background: #fef0f0;
        padding: 8px 12px;
        border-radius: 4px;
        margin-top: 8px;
        font-size: 14px;
      }
    }
  }

  .screenshot-container {
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

      .screenshot-img {
        max-width: 100%;
        border: 1px solid #dcdfe6;
        border-radius: 4px;
        box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
      }

      .screenshot-time {
        margin: 10px 0 0 0;
        color: #909399;
        font-size: 12px;
      }
    }
  }
}
</style>
