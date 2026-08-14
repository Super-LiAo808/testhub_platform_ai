<template>
  <div class="app-automation-dashboard">
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">{{ $t('appAutomation.dashboard.title') || '数据看板' }}</h1>
        <p class="page-subtitle">设备与执行概览，查看最近执行记录</p>
      </div>
      <div class="header-actions">
        <el-select
          v-model="selectedProject"
          :placeholder="$t('appAutomation.common.selectProject') || '选择项目'"
          clearable
          filterable
          style="width: 220px"
          @change="onProjectChange"
        >
          <el-option
            v-for="p in projects"
            :key="p.id"
            :label="p.name"
            :value="p.id"
          />
        </el-select>
        <el-select v-model="days" style="width: 120px" @change="loadStatistics">
          <el-option :label="'近 7 天'" :value="7" />
          <el-option :label="'近 14 天'" :value="14" />
          <el-option :label="'近 30 天'" :value="30" />
        </el-select>
        <el-button :loading="loading" @click="loadStatistics">
          <el-icon><Refresh /></el-icon>
          {{ $t('appAutomation.common.refresh') || '刷新' }}
        </el-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-section">
      <el-row :gutter="16">
        <el-col :xs="12" :sm="6">
          <el-card shadow="hover" class="stat-card" @click="$router.push('/app-automation/devices')">
            <div class="stat-content">
              <div class="stat-icon bg-blue"><el-icon><Cellphone /></el-icon></div>
              <div class="stat-info">
                <div class="stat-value">{{ statistics.devices.total }}</div>
                <div class="stat-label">{{ $t('appAutomation.dashboard.totalDevices') }}</div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :xs="12" :sm="6">
          <el-card shadow="hover" class="stat-card">
            <div class="stat-content">
              <div class="stat-icon bg-green"><el-icon><CircleCheck /></el-icon></div>
              <div class="stat-info">
                <div class="stat-value">{{ statistics.devices.online }}</div>
                <div class="stat-label">{{ $t('appAutomation.dashboard.onlineDevices') }}</div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :xs="12" :sm="6">
          <el-card shadow="hover" class="stat-card">
            <div class="stat-content">
              <div class="stat-icon bg-orange"><el-icon><Lock /></el-icon></div>
              <div class="stat-info">
                <div class="stat-value">{{ statistics.devices.locked }}</div>
                <div class="stat-label">{{ $t('appAutomation.dashboard.lockedDevices') }}</div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :xs="12" :sm="6">
          <el-card shadow="hover" class="stat-card" @click="$router.push('/app-automation/test-cases')">
            <div class="stat-content">
              <div class="stat-icon bg-purple"><el-icon><Document /></el-icon></div>
              <div class="stat-info">
                <div class="stat-value">{{ statistics.test_cases.total }}</div>
                <div class="stat-label">{{ $t('appAutomation.dashboard.testCases') }}</div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <el-row :gutter="16" class="content-section">
      <!-- 执行统计 -->
      <el-col :xs="24" :lg="10">
        <el-card class="panel-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span>{{ $t('appAutomation.dashboard.executionStatistics') }}
                <span class="header-hint">（近 {{ statistics.executions.days || days }} 天）</span>
              </span>
            </div>
          </template>
          <div class="chart-container">
            <div class="stat-item">
              <div class="stat-label">{{ $t('appAutomation.dashboard.totalExecutions') }}</div>
              <div class="stat-value large">{{ statistics.executions.total }}</div>
            </div>
            <div class="stat-item">
              <div class="stat-label">{{ $t('appAutomation.dashboard.runningCount') || '执行中' }}</div>
              <div class="stat-value warning">{{ statistics.executions.running || 0 }}</div>
            </div>
            <div class="stat-item">
              <div class="stat-label">{{ $t('appAutomation.dashboard.successCount') }}</div>
              <div class="stat-value success">{{ statistics.executions.success }}</div>
            </div>
            <div class="stat-item">
              <div class="stat-label">{{ $t('appAutomation.dashboard.failedCount') }}</div>
              <div class="stat-value danger">{{ statistics.executions.failed }}</div>
            </div>
          </div>
          <div class="pass-rate-block">
            <div class="pass-rate-label">
              {{ $t('appAutomation.dashboard.passRate') }}：{{ statistics.executions.pass_rate }}%
            </div>
            <el-progress
              :percentage="Number(statistics.executions.pass_rate) || 0"
              :color="passRateColor"
              :stroke-width="12"
            />
          </div>
        </el-card>
      </el-col>

      <!-- 最近执行记录 -->
      <el-col :xs="24" :lg="14">
        <el-card class="panel-card recent-panel" shadow="never" v-loading="loading">
          <template #header>
            <div class="card-header">
              <span>{{ $t('appAutomation.dashboard.recentExecutions') }}</span>
              <el-button type="primary" link @click="$router.push('/app-automation/executions')">
                {{ $t('appAutomation.dashboard.viewAll') }}
              </el-button>
            </div>
          </template>

          <el-empty
            v-if="!loading && !recentExecutions.length"
            :description="$t('appAutomation.dashboard.noExecutionRecords')"
          />
          <el-table
            v-else
            :data="recentExecutions"
            size="small"
            class="recent-table"
            empty-text="暂无执行记录"
            @row-click="viewExecution"
          >
            <el-table-column prop="case_name" :label="$t('appAutomation.execution.testCase')" min-width="160" show-overflow-tooltip>
              <template #default="{ row }">
                <button type="button" class="name-link" @click.stop="viewExecution(row)">
                  {{ row.case_name || '-' }}
                </button>
              </template>
            </el-table-column>
            <el-table-column :label="$t('appAutomation.common.status')" width="96" align="center">
              <template #default="{ row }">
                <el-tag :type="getDisplayStatus(row.status, row.result).type" size="small" effect="plain">
                  {{ getDisplayStatus(row.status, row.result).text }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="device_name" :label="$t('appAutomation.execution.device')" width="120" show-overflow-tooltip />
            <el-table-column :label="$t('appAutomation.execution.duration')" width="90" align="center">
              <template #default="{ row }">
                {{ formatDuration(row.duration) }}
              </template>
            </el-table-column>
            <el-table-column :label="$t('appAutomation.execution.startTime')" width="150" align="center">
              <template #default="{ row }">
                {{ formatDateTime(row.started_at || row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column label="" width="72" align="center" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click.stop="viewExecution(row)">
                  {{ $t('appAutomation.common.view') }}
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <!-- 快速操作 -->
    <el-card class="panel-card quick-card" shadow="never">
      <template #header>
        <div class="card-header">
          <span>{{ $t('appAutomation.dashboard.quickActions') }}</span>
        </div>
      </template>
      <div class="actions-grid">
        <div class="action-item" @click="$router.push('/app-automation/devices')">
          <div class="action-icon bg-blue"><el-icon><Cellphone /></el-icon></div>
          <div class="action-label">{{ $t('appAutomation.dashboard.deviceManagement') }}</div>
        </div>
        <div class="action-item" @click="$router.push('/app-automation/elements')">
          <div class="action-icon bg-green"><el-icon><Picture /></el-icon></div>
          <div class="action-label">{{ $t('appAutomation.dashboard.elementManagement') }}</div>
        </div>
        <div class="action-item" @click="$router.push('/app-automation/test-cases')">
          <div class="action-icon bg-purple"><el-icon><Document /></el-icon></div>
          <div class="action-label">{{ $t('appAutomation.dashboard.testCases') }}</div>
        </div>
        <div class="action-item" @click="$router.push('/app-automation/executions')">
          <div class="action-icon bg-orange"><el-icon><Aim /></el-icon></div>
          <div class="action-label">{{ $t('appAutomation.dashboard.executionRecords') }}</div>
        </div>
      </div>
    </el-card>

    <!-- 执行详情抽屉 -->
    <el-drawer
      v-model="detailVisible"
      :title="$t('appAutomation.dashboard.executionDetail') || '执行详情'"
      size="480px"
      destroy-on-close
    >
      <div v-loading="detailLoading" class="detail-body">
        <template v-if="currentExecution">
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item :label="$t('appAutomation.execution.testCase')">
              {{ currentExecution.case_name || '-' }}
            </el-descriptions-item>
            <el-descriptions-item :label="$t('appAutomation.common.status')">
              <el-tag :type="getDisplayStatus(currentExecution.status, currentExecution.result).type" size="small" effect="plain">
                {{ getDisplayStatus(currentExecution.status, currentExecution.result).text }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item :label="$t('appAutomation.execution.device')">
              {{ currentExecution.device_name || '-' }}
            </el-descriptions-item>
            <el-descriptions-item :label="$t('appAutomation.execution.executor')">
              {{ currentExecution.user_name || '-' }}
            </el-descriptions-item>
            <el-descriptions-item :label="$t('appAutomation.execution.progress')">
              <el-progress
                :percentage="currentExecution.progress || 0"
                :status="progressStatus(currentExecution)"
                style="width: 180px"
              />
            </el-descriptions-item>
            <el-descriptions-item :label="$t('appAutomation.execution.stepStats')">
              {{ $t('appAutomation.status.passed') }} {{ currentExecution.passed_steps || 0 }}
              / {{ $t('appAutomation.status.failed') }} {{ currentExecution.failed_steps || 0 }}
              / {{ $t('appAutomation.execution.total') }} {{ currentExecution.total_steps || 0 }}
            </el-descriptions-item>
            <el-descriptions-item :label="$t('appAutomation.execution.duration')">
              {{ formatDuration(currentExecution.duration) }}
            </el-descriptions-item>
            <el-descriptions-item :label="$t('appAutomation.execution.startTime')">
              {{ formatDateTime(currentExecution.started_at || currentExecution.created_at) }}
            </el-descriptions-item>
            <el-descriptions-item :label="$t('appAutomation.execution.endTime')">
              {{ currentExecution.finished_at ? formatDateTime(currentExecution.finished_at) : '-' }}
            </el-descriptions-item>
          </el-descriptions>

          <div v-if="currentExecution.error_message" class="error-block">
            <h4>{{ $t('appAutomation.execution.errorInfo') || '错误信息' }}</h4>
            <pre>{{ currentExecution.error_message }}</pre>
          </div>

          <div class="detail-actions">
            <el-button
              v-if="currentExecution.report_path"
              type="primary"
              @click="openReport(currentExecution)"
            >
              {{ $t('appAutomation.execution.viewReport') }}
            </el-button>
            <el-button @click="$router.push('/app-automation/executions')">
              {{ $t('appAutomation.dashboard.viewAll') }}
            </el-button>
          </div>
        </template>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import {
  getDashboardStatistics,
  getExecutionDetail,
  getAppProjects
} from '@/api/app-automation'
import {
  getDisplayStatus,
  formatDateTime,
  formatDuration
} from '@/utils/app-automation-helpers'
import {
  Cellphone,
  CircleCheck,
  Lock,
  Document,
  Picture,
  Aim,
  Refresh
} from '@element-plus/icons-vue'

const { t } = useI18n()

const loading = ref(false)
const projects = ref([])
const selectedProject = ref('')
const days = ref(30)

const statistics = ref({
  devices: { total: 0, online: 0, locked: 0, available: 0, offline: 0 },
  test_cases: { total: 0 },
  test_suites: { total: 0 },
  executions: { total: 0, running: 0, success: 0, failed: 0, pass_rate: 0, days: 30 },
  recent_executions: [],
  trend: []
})

const recentExecutions = computed(() => statistics.value.recent_executions || [])

const passRateColor = computed(() => {
  const rate = Number(statistics.value.executions.pass_rate) || 0
  if (rate >= 90) return '#67c23a'
  if (rate >= 70) return '#e6a23c'
  return '#f56c6c'
})

const detailVisible = ref(false)
const detailLoading = ref(false)
const currentExecution = ref(null)

const loadProjects = async () => {
  try {
    const res = await getAppProjects({ page_size: 100 })
    projects.value = res.data?.results || res.data || []
  } catch (e) {
    console.error(e)
  }
}

const loadStatistics = async () => {
  loading.value = true
  try {
    const params = { days: days.value, recent_limit: 12 }
    if (selectedProject.value) params.project = selectedProject.value
    const res = await getDashboardStatistics(params)
    const payload = res.data?.data || res.data
    if (res.data?.success === false) {
      throw new Error(res.data?.message || 'load failed')
    }
    statistics.value = {
      devices: payload.devices || statistics.value.devices,
      test_cases: payload.test_cases || { total: 0 },
      test_suites: payload.test_suites || { total: 0 },
      executions: payload.executions || statistics.value.executions,
      recent_executions: payload.recent_executions || [],
      trend: payload.trend || []
    }
  } catch (error) {
    ElMessage.error(
      t('appAutomation.dashboard.messages.loadFailed') + ': ' +
      (error.message || t('appAutomation.dashboard.messages.unknownError'))
    )
  } finally {
    loading.value = false
  }
}

const onProjectChange = () => {
  loadStatistics()
}

const progressStatus = (row) => {
  if (row.status === 'error' || row.result === 'failed') return 'exception'
  if (row.result === 'passed') return 'success'
  return undefined
}

const viewExecution = async (row) => {
  if (!row?.id) return
  detailVisible.value = true
  detailLoading.value = true
  currentExecution.value = row
  try {
    const res = await getExecutionDetail(row.id)
    currentExecution.value = res.data?.data || res.data || row
  } catch (e) {
    // 列表数据已足够展示
    console.warn(e)
  } finally {
    detailLoading.value = false
  }
}

const openReport = (row) => {
  if (!row?.report_path) return
  const path = row.report_path.startsWith('http')
    ? row.report_path
    : `/api/app-automation/executions/${row.id}/report/`
  window.open(path, '_blank')
}

let refreshTimer = null

onMounted(async () => {
  await loadProjects()
  await loadStatistics()
  refreshTimer = setInterval(loadStatistics, 30000)
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
})
</script>

<style scoped lang="scss">
.app-automation-dashboard {
  padding: 16px 20px 24px;
  background: #f3f5f8;
  min-height: 100%;
  box-sizing: border-box;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
  gap: 12px;
  flex-wrap: wrap;
}

.page-title {
  margin: 0;
  font-size: 22px;
  font-weight: 650;
  color: #1f2a37;
}

.page-subtitle {
  margin: 6px 0 0;
  font-size: 13px;
  color: #6b7280;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.stats-section {
  margin-bottom: 16px;
}

.stat-card {
  margin-bottom: 12px;
  cursor: pointer;
  border: 1px solid #e5e9f0;
  border-radius: 12px;

  .stat-content {
    display: flex;
    align-items: center;
    gap: 14px;

    .stat-icon {
      width: 52px;
      height: 52px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 22px;
      color: white;

      &.bg-blue { background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); }
      &.bg-green { background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%); }
      &.bg-orange { background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); }
      &.bg-purple { background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%); }
    }

    .stat-info {
      .stat-value {
        font-size: 26px;
        font-weight: 650;
        color: #1f2a37;
        line-height: 1.1;
        font-variant-numeric: tabular-nums;
      }
      .stat-label {
        margin-top: 6px;
        font-size: 13px;
        color: #6b7280;
      }
    }
  }
}

.panel-card {
  border: 1px solid #e5e9f0;
  border-radius: 12px;
  margin-bottom: 16px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
  color: #1f2a37;
}

.header-hint {
  font-weight: 400;
  font-size: 12px;
  color: #9ca3af;
}

.chart-container {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;

  .stat-item {
    text-align: center;
    padding: 14px 10px;
    border-radius: 10px;
    background: #f8fafc;
    border: 1px solid #eef2f7;

    .stat-label {
      font-size: 13px;
      color: #6b7280;
      margin-bottom: 8px;
    }

    .stat-value {
      font-size: 24px;
      font-weight: 650;
      font-variant-numeric: tabular-nums;

      &.large { font-size: 28px; color: #2563eb; }
      &.success { color: #16a34a; }
      &.warning { color: #d97706; }
      &.danger { color: #dc2626; }
    }
  }
}

.pass-rate-block {
  margin-top: 16px;

  .pass-rate-label {
    margin-bottom: 8px;
    font-size: 13px;
    color: #374151;
  }
}

.recent-table {
  width: 100%;
}

.name-link {
  border: none;
  background: none;
  padding: 0;
  color: #2563eb;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  text-align: left;

  &:hover { text-decoration: underline; }
}

.actions-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;

  .action-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    padding: 18px 12px;
    border-radius: 10px;
    cursor: pointer;
    background: #f8fafc;
    border: 1px solid #eef2f7;
    transition: all 0.2s;

    &:hover {
      background: #eff6ff;
      border-color: #bfdbfe;
    }

    .action-icon {
      width: 44px;
      height: 44px;
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 20px;
      color: white;

      &.bg-blue { background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); }
      &.bg-green { background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%); }
      &.bg-orange { background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); }
      &.bg-purple { background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%); }
    }

    .action-label {
      font-size: 13px;
      font-weight: 500;
      color: #1f2a37;
    }
  }
}

.detail-body {
  min-height: 200px;
}

.error-block {
  margin-top: 16px;

  h4 {
    margin: 0 0 8px;
    font-size: 14px;
    color: #dc2626;
  }

  pre {
    margin: 0;
    padding: 12px;
    background: #fef2f2;
    border: 1px solid #fecaca;
    border-radius: 8px;
    white-space: pre-wrap;
    word-break: break-word;
    font-size: 12px;
    max-height: 240px;
    overflow: auto;
  }
}

.detail-actions {
  margin-top: 20px;
  display: flex;
  gap: 10px;
}

@media (max-width: 900px) {
  .actions-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
