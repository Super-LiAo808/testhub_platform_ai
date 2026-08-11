<template>
  <div class="execution-detail">
    <!-- 页面头部：扁平、克制，Grafana 式仪表盘标题区 -->
    <header class="plan-header">
      <div class="plan-header__title-row">
        <h1 class="plan-header__title">{{ testPlan.name }}</h1>
        <span v-if="testPlan.version" class="version-chip">
          <el-icon class="version-chip__icon"><Stamp /></el-icon>
          {{ testPlan.version }}
        </span>
      </div>
      <div class="plan-header__meta">
        <span class="meta-item">
          <el-icon class="meta-item__icon"><FolderOpened /></el-icon>
          <template v-if="testPlan.projects && testPlan.projects.length > 0">
            {{ testPlan.projects.join(', ') }}
          </template>
          <template v-else>{{ $t('execution.noProject') }}</template>
        </span>
        <span v-if="testPlan.created_at" class="meta-item meta-dim">
          {{ $t('execution.createdAt') }} · {{ formatDate(testPlan.created_at) }}
        </span>
      </div>
    </header>

    <!-- 测试执行区 -->
    <template v-if="testPlan.test_runs && testPlan.test_runs.length > 0">
      <section v-for="run in testPlan.test_runs" :key="run.id" class="run-card">
        <!-- 运行头部：标题 + 状态 + 进度 + 批量保存 -->
        <div class="run-card__head">
          <div class="run-card__title-row">
            <div class="run-card__title-group">
              <h2 class="run-card__title">{{ run.name }}</h2>
              <span class="status-chip" :class="runStatusClass(run.progress)">
                <span class="status-chip__dot"></span>
                {{ getRunStatusText(run.progress) }}
              </span>
            </div>
            <el-button
              v-if="dirtyCount(run) > 0"
              size="small"
              type="primary"
              :loading="batchRunId === run.id"
              @click="saveAllInRun(run)">
              {{ $t('execution.batchSaveAll') }} ({{ dirtyCount(run) }})
            </el-button>
          </div>

          <div class="run-progress">
            <span class="run-progress__pct">{{ run.progress.progress }}%</span>
            <div class="run-progress__track">
              <div
                class="run-progress__fill"
                :class="progressFillClass(run.progress.progress)"
                :style="{ width: run.progress.progress + '%' }">
              </div>
            </div>
          </div>
        </div>

        <!-- 统计指标瓦片：中性底 + 语义色左侧细条（取代原彩虹渐变填充） -->
        <div class="stats-grid">
          <div class="stat-tile stat-tile--total">
            <span class="stat-tile__value">{{ run.progress.total }}</span>
            <span class="stat-tile__label">{{ $t('execution.total') }}</span>
          </div>
          <div class="stat-tile stat-tile--passed">
            <span class="stat-tile__value">{{ run.progress.passed }}</span>
            <span class="stat-tile__label">{{ $t('execution.passed') }}</span>
          </div>
          <div class="stat-tile stat-tile--failed">
            <span class="stat-tile__value">{{ run.progress.failed }}</span>
            <span class="stat-tile__label">{{ $t('execution.failed') }}</span>
          </div>
          <div class="stat-tile stat-tile--blocked">
            <span class="stat-tile__value">{{ run.progress.blocked }}</span>
            <span class="stat-tile__label">{{ $t('execution.blocked') }}</span>
          </div>
          <div class="stat-tile stat-tile--untested">
            <span class="stat-tile__value">{{ run.progress.untested }}</span>
            <span class="stat-tile__label">{{ $t('execution.untested') }}</span>
          </div>
        </div>

        <!-- 批量操作按钮 -->
        <div v-if="selectedCases.length > 0" class="batch-actions">
          <el-button
            type="danger"
            :icon="Delete"
            @click="batchDeleteCases"
            :disabled="isDeleting">
            {{ $t('execution.batchDelete') }} ({{ selectedCases.length }})
          </el-button>
        </div>

        <!-- 用例表格 -->
        <el-table
          ref="tableRef"
          :data="paginatedCases(run.run_cases)"
          style="width: 100%"
          class="execution-table"
          :row-class-name="rowClassName"
          @selection-change="handleSelectionChange"
          :row-key="(row) => row.id">
          <el-table-column type="selection" width="48" :reserve-selection="true" />
          <el-table-column
            type="index"
            :label="$t('execution.serialNumber')"
            width="72"
            :index="getSerialNumber" />
          <el-table-column prop="testcase" :label="$t('execution.testCase')" min-width="250" />
          <el-table-column :label="$t('execution.executionStatus')" width="160">
            <template #default="scope">
              <el-select
                v-model="scope.row.status"
                size="small"
                class="status-select">
                <el-option :label="$t('execution.untested')" value="untested" />
                <el-option :label="$t('execution.passed')" value="passed" />
                <el-option :label="$t('execution.failed')" value="failed" />
                <el-option :label="$t('execution.blocked')" value="blocked" />
                <el-option :label="$t('execution.retest')" value="retest" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column :label="$t('execution.comments')" min-width="250">
            <template #default="scope">
              <el-input
                v-model="scope.row.comments"
                :placeholder="$t('execution.commentsPlaceholder')"
                type="textarea"
                :rows="2"
                size="small">
              </el-input>
            </template>
          </el-table-column>
          <el-table-column :label="$t('execution.actions')" width="160" fixed="right" class-name="action-col">
            <template #default="scope">
              <div class="table-actions">
                <el-button
                  link
                  type="primary"
                  size="small"
                  :icon="Check"
                  :loading="savingId === scope.row.id"
                  :disabled="!isRowDirty(scope.row)"
                  @click="saveRunCase(scope.row, run)">
                  {{ $t('common.save') }}
                </el-button>
                <el-button
                  link
                  type="primary"
                  size="small"
                  :icon="Clock"
                  @click="viewCaseHistory(scope.row)">
                  {{ $t('execution.viewHistory') }}
                </el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>

        <!-- 分页组件 -->
        <div v-if="run.run_cases && run.run_cases.length > 0" class="pagination-container">
          <el-pagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :page-sizes="[10, 20, 50, 100]"
            :total="run.run_cases.length"
            layout="total, sizes, prev, pager, next, jumper"
            @current-change="handlePageChange"
            @size-change="handleSizeChange">
          </el-pagination>
        </div>
      </section>
    </template>

    <!-- 空态 -->
    <div v-else-if="loaded" class="empty-state">
      {{ $t('execution.noRuns') }}
    </div>

    <!-- 历史记录对话框 -->
    <el-dialog
      :title="$t('execution.executionHistory')"
      v-model="historyDialogVisible"
      width="80%">
      <el-table :data="currentCaseHistory" style="width: 100%">
        <el-table-column prop="status" :label="$t('execution.status')" width="100">
          <template #default="scope">
            <el-tag :type="getStatusType(scope.row.status)">
              {{ getStatusText(scope.row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="comments" :label="$t('execution.comments')" show-overflow-tooltip />
        <el-table-column prop="executed_by.username" :label="$t('execution.executedBy')" width="120" />
        <el-table-column prop="executed_at" :label="$t('execution.executedAt')" width="180">
          <template #default="scope">
            {{ formatDate(scope.row.executed_at) }}
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Clock, Check, Stamp, FolderOpened } from '@element-plus/icons-vue'
import api from '@/utils/api'

const { t } = useI18n()

const route = useRoute()
const testPlan = ref({})
const historyDialogVisible = ref(false)
const currentCaseHistory = ref([])
const selectedCases = ref([])
const currentPage = ref(1)
const pageSize = ref(10)
const isDeleting = ref(false)
const tableRef = ref(null)
const loaded = ref(false)

// 已保存快照：row.id -> { status, comments }，用于判断某行是否有未提交的改动
const savedState = ref({})
// 单行保存中的用例 id；批量保存中的 run.id
const savingId = ref(null)
const batchRunId = ref(null)

const fetchTestPlan = async () => {
  try {
    const planId = route.params.id
    const response = await api.get(`/executions/plans/${planId}/`)
    testPlan.value = response.data
    buildSavedState()
  } catch (error) {
    ElMessage.error(t('execution.fetchDetailFailed'))
  } finally {
    loaded.value = true
  }
}

// 依据当前已持久化的数据构建"已保存快照"
const buildSavedState = () => {
  const map = {}
  const runs = testPlan.value.test_runs
  if (runs) {
    for (const run of runs) {
      if (run.run_cases) {
        for (const rc of run.run_cases) {
          map[rc.id] = { status: rc.status, comments: rc.comments || '' }
        }
      }
    }
  }
  savedState.value = map
}

// 行是否有未提交改动（状态或备注与快照不一致）
const isRowDirty = (runCase) => {
  const saved = savedState.value[runCase.id]
  if (!saved) return false
  return runCase.status !== saved.status || (runCase.comments || '') !== saved.comments
}

// 某 run 内未提交的用例数
const dirtyCount = (run) => {
  if (!run.run_cases) return 0
  return run.run_cases.filter(rc => isRowDirty(rc)).length
}

// 表格行样式：未提交行加 row-dirty 类
const rowClassName = ({ row }) => (isRowDirty(row) ? 'row-dirty' : '')

// 本地重算 run 进度（与后端 progress_stats 公式一致），
// 避免整页 fetchTestPlan 刷新替换行对象、从而丢失其他行的未提交草稿
const recomputeProgress = (run) => {
  const cases = run.run_cases || []
  const p = run.progress || (run.progress = {})
  p.total = cases.length
  p.untested = 0
  p.passed = 0
  p.failed = 0
  p.blocked = 0
  p.retest = 0
  for (const c of cases) {
    if (c.status && p[c.status] !== undefined) p[c.status]++
  }
  p.tested = p.passed + p.failed + p.blocked + p.retest
  p.progress = p.total > 0 ? Math.round((p.tested / p.total) * 100 * 10) / 10 : 0
}

// 保存单个用例：状态 + 备注一次提交，只产生一条历史记录
const saveRunCase = async (runCase, run) => {
  if (!isRowDirty(runCase)) return
  savingId.value = runCase.id
  try {
    await api.patch(`/executions/run_cases/${runCase.id}/update_status/`, {
      status: runCase.status,
      comments: runCase.comments || ''
    })
    // 本地同步快照 -> 行变为"已保存"
    savedState.value[runCase.id] = { status: runCase.status, comments: runCase.comments || '' }
    if (run) recomputeProgress(run)
    ElMessage.success(t('execution.statusUpdateSuccess'))
  } catch (error) {
    ElMessage.error(t('execution.statusUpdateFailed'))
  } finally {
    savingId.value = null
  }
}

// 批量保存某 run 内所有未提交用例
const saveAllInRun = async (run) => {
  const dirty = (run.run_cases || []).filter(rc => isRowDirty(rc))
  if (!dirty.length) return
  batchRunId.value = run.id
  let ok = 0
  let fail = 0
  for (const rc of dirty) {
    try {
      await api.patch(`/executions/run_cases/${rc.id}/update_status/`, {
        status: rc.status,
        comments: rc.comments || ''
      })
      savedState.value[rc.id] = { status: rc.status, comments: rc.comments || '' }
      ok++
    } catch (error) {
      fail++
    }
  }
  recomputeProgress(run)
  batchRunId.value = null
  if (fail > 0) {
    ElMessage.success(t('execution.batchSavePartialSuccess', { successCount: ok, failCount: fail }))
  } else {
    ElMessage.success(t('execution.batchSaveSuccess', { count: ok }))
  }
}

const viewCaseHistory = async (runCase) => {
  try {
    const response = await api.get(`/executions/run_cases/${runCase.id}/history/`)
    currentCaseHistory.value = response.data
    historyDialogVisible.value = true
  } catch (error) {
    ElMessage.error(t('execution.fetchHistoryFailed'))
  }
}

// 处理选择变化
const handleSelectionChange = (selection) => {
  selectedCases.value = selection
}

// 清空所有表格选择（tableRef 在 v-for 下可能是数组）
const clearAllSelections = () => {
  if (!tableRef.value) return
  const tables = Array.isArray(tableRef.value) ? tableRef.value : [tableRef.value]
  tables.forEach(tbl => tbl && tbl.clearSelection && tbl.clearSelection())
}

// 批量删除：本地移除 + 重算进度（不整页刷新，保留其他行未提交草稿）
const batchDeleteCases = async () => {
  if (selectedCases.value.length === 0) {
    ElMessage.warning(t('execution.selectCasesFirst'))
    return
  }

  try {
    await ElMessageBox.confirm(
      t('execution.batchDeleteCasesConfirm', { count: selectedCases.value.length }),
      t('common.warning'),
      {
        confirmButtonText: t('common.confirm'),
        cancelButtonText: t('common.cancel'),
        type: 'warning'
      }
    )

    isDeleting.value = true
    let successCount = 0
    let failCount = 0
    const deletedIds = new Set()

    for (const runCase of selectedCases.value) {
      try {
        await api.delete(`/executions/run_cases/${runCase.id}/`)
        successCount++
        deletedIds.add(runCase.id)
      } catch (error) {
        console.error(`删除用例 ${runCase.id} 失败:`, error)
        failCount++
      }
    }

    // 本地移除已删除用例并重算进度
    if (deletedIds.size > 0 && testPlan.value.test_runs) {
      for (const run of testPlan.value.test_runs) {
        if (run.run_cases) {
          run.run_cases = run.run_cases.filter(rc => !deletedIds.has(rc.id))
          recomputeProgress(run)
        }
      }
      for (const id of deletedIds) delete savedState.value[id]
    }

    selectedCases.value = []
    clearAllSelections()

    if (successCount > 0) {
      if (failCount > 0) {
        ElMessage.success(t('execution.batchDeleteCasesPartialSuccess', { successCount, failCount }))
      } else {
        ElMessage.success(t('execution.batchDeleteCasesSuccess', { successCount }))
      }
    } else {
      ElMessage.error(t('execution.batchDeleteFailed'))
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('批量删除失败:', error)
      ElMessage.error(t('execution.batchDeleteFailed'))
    }
  } finally {
    isDeleting.value = false
  }
}

// 分页相关
const paginatedCases = (cases) => {
  if (!cases) return []
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return cases.slice(start, end)
}

const getSerialNumber = (index) => {
  return (currentPage.value - 1) * pageSize.value + index + 1
}

const handlePageChange = () => {
  selectedCases.value = []
  clearAllSelections()
}

const handleSizeChange = () => {
  currentPage.value = 1
  selectedCases.value = []
  clearAllSelections()
}

const formatDate = (dateString) => {
  if (!dateString) return '-'
  return new Date(dateString).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 运行状态 -> chip 样式修饰符（颜色由 CSS 变量驱动，语义化而非装饰）
const runStatusClass = (progress) => {
  if (progress.progress === 100) return 'is-completed'
  if (progress.untested === progress.total) return 'is-pending'
  if (progress.failed > 0) return 'is-failed'
  if (progress.blocked > 0) return 'is-blocked'
  return 'is-progress'
}

// 进度条填充色阶（健康度语义：<30 红 / <70 琥珀 / ≥70 绿）
const progressFillClass = (percentage) => {
  if (percentage < 30) return 'fill--low'
  if (percentage < 70) return 'fill--mid'
  return 'fill--high'
}

const getRunStatusText = (progress) => {
  if (progress.progress === 100) return t('execution.completed')
  if (progress.untested === progress.total) return t('execution.notStarted')
  return t('execution.inProgress')
}

const getStatusType = (status) => {
  const typeMap = {
    'untested': 'info',
    'passed': 'success',
    'failed': 'danger',
    'blocked': 'warning',
    'retest': 'primary'
  }
  return typeMap[status] || 'info'
}

const getStatusText = (status) => {
  const textMap = {
    'untested': t('execution.untested'),
    'passed': t('execution.passed'),
    'failed': t('execution.failed'),
    'blocked': t('execution.blocked'),
    'retest': t('execution.retest')
  }
  return textMap[status] || status
}

onMounted(() => {
  fetchTestPlan()
})
</script>

<style scoped>
.execution-detail {
  /* —— Grafana 设计令牌（取自 opendesign.cc/packs/grafana/spec.json）—— */
  --g-bg: #ffffff;
  --g-bg-soft: #f4f4f6;
  --g-bg-quiet: #f9f9fa;
  --g-ink: #000000;
  --g-ink-soft: #67677e;
  --g-muted: #454554;
  --g-accent: #1b55f5;
  --g-line: #aeaebc;
  --g-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
  /* 语义状态色：仅作细条/圆点等功能性强调，非装饰填充 */
  --st-total: #1b55f5;
  --st-passed: #3bc36c;
  --st-failed: #f2495c;
  --st-blocked: #f0a847;
  --st-untested: #8a8a99;
  /* 字体：Poppins(display) / Inter(body) —— Grafana 真实字族配对 */
  --font-display: 'Poppins', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', sans-serif;
  --font-body: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', sans-serif;

  padding: 24px;
  background: var(--g-bg-soft);
  min-height: 100vh;
  font-family: var(--font-body);
  color: var(--g-ink);
}

/* —— 页面头部：扁平卡片，克制 —— */
.plan-header {
  background: var(--g-bg);
  border: 1px solid var(--g-line);
  border-radius: 8px;
  box-shadow: var(--g-shadow);
  padding: 20px 24px;
  margin-bottom: 24px;
}

.plan-header__title-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.plan-header__title {
  margin: 0;
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 600;
  line-height: 1.2;
  letter-spacing: -0.3px;
  color: var(--g-ink);
}

.version-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 10px;
  font-size: 12px;
  font-weight: 500;
  color: var(--g-accent);
  background: rgba(27, 85, 245, 0.08);
  border: 1px solid rgba(27, 85, 245, 0.2);
  border-radius: 999px;
  line-height: 1.6;
}

.version-chip__icon {
  font-size: 13px;
}

.plan-header__meta {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  margin-top: 10px;
  font-size: 13px;
  color: var(--g-ink-soft);
}

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.meta-item__icon {
  font-size: 15px;
  color: var(--g-ink-soft);
}

.meta-dim {
  color: #9a9aa8;
}

/* —— 运行卡片 —— */
.run-card {
  background: var(--g-bg);
  border: 1px solid var(--g-line);
  border-radius: 8px;
  box-shadow: var(--g-shadow);
  padding: 20px 24px;
  margin-bottom: 24px;
}

.run-card__head {
  margin-bottom: 20px;
}

.run-card__title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}

.run-card__title-group {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.run-card__title {
  margin: 0;
  font-family: var(--font-display);
  font-size: 17px;
  font-weight: 600;
  letter-spacing: -0.2px;
  color: var(--g-ink);
}

/* 状态 chip：中性底 + 语义色圆点 */
.status-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 10px;
  font-size: 12px;
  font-weight: 500;
  border-radius: 999px;
  border: 1px solid var(--g-line);
  background: var(--g-bg-quiet);
  color: var(--g-ink);
  line-height: 1.7;
}

.status-chip__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--g-ink-soft);
}

.status-chip.is-completed { color: #1f7a3a; }
.status-chip.is-completed .status-chip__dot { background: var(--st-passed); }
.status-chip.is-failed { color: #b32334; }
.status-chip.is-failed .status-chip__dot { background: var(--st-failed); }
.status-chip.is-blocked { color: #9a6a16; }
.status-chip.is-blocked .status-chip__dot { background: var(--st-blocked); }
.status-chip.is-pending .status-chip__dot { background: var(--st-untested); }
.status-chip.is-progress { color: var(--g-accent); }
.status-chip.is-progress .status-chip__dot { background: var(--g-accent); }

/* 运行进度条 */
.run-progress {
  display: flex;
  align-items: center;
  gap: 12px;
}

.run-progress__pct {
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 600;
  color: var(--g-ink);
  min-width: 42px;
}

.run-progress__track {
  flex: 1;
  height: 8px;
  background: var(--g-bg-soft);
  border-radius: 4px;
  overflow: hidden;
}

.run-progress__fill {
  height: 100%;
  border-radius: 4px;
  transition: width 300ms cubic-bezier(0.4, 0, 0.2, 1);
}

.run-progress__fill.fill--low { background: var(--st-failed); }
.run-progress__fill.fill--mid { background: var(--st-blocked); }
.run-progress__fill.fill--high { background: var(--st-passed); }

/* —— 统计瓦片：中性底 + 左侧语义色细条 —— */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}

.stat-tile {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 14px 16px 14px 18px;
  background: var(--g-bg-quiet);
  border: 1px solid var(--g-line);
  border-radius: 8px;
  overflow: hidden;
  transition: background-color 150ms cubic-bezier(0.4, 0, 0.2, 1);
}

.stat-tile:hover {
  background: var(--g-bg-soft);
}

/* 左侧 3px 语义色细条（::before，不干扰盒模型） */
.stat-tile::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: var(--g-line);
}

.stat-tile--total::before { background: var(--st-total); }
.stat-tile--passed::before { background: var(--st-passed); }
.stat-tile--failed::before { background: var(--st-failed); }
.stat-tile--blocked::before { background: var(--st-blocked); }
.stat-tile--untested::before { background: var(--st-untested); }

.stat-tile__value {
  font-family: var(--font-display);
  font-size: 26px;
  font-weight: 600;
  line-height: 1.05;
  letter-spacing: -0.5px;
  color: var(--g-ink);
}

.stat-tile__label {
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.6px;
  text-transform: uppercase;
  color: var(--g-ink-soft);
}

/* —— 批量操作 —— */
.batch-actions {
  margin-bottom: 16px;
  display: flex;
  justify-content: flex-end;
}

/* —— 表格：Grafana 化 —— */
.execution-table {
  --el-table-border-color: var(--g-line);
  --el-table-header-bg-color: var(--g-bg-soft);
  --el-table-row-hover-bg-color: var(--g-bg-quiet);
  border: 1px solid var(--g-line);
  border-radius: 8px;
  overflow: hidden;
}

:deep(.execution-table .el-table__header th) {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.6px;
  text-transform: uppercase;
  color: var(--g-ink-soft);
  background: var(--g-bg-soft) !important;
}

:deep(.execution-table .el-table__body td) {
  font-size: 13px;
  color: var(--g-ink);
}

/* 未提交行：极淡暖底，提示有待保存的改动 */
:deep(.execution-table .row-dirty td) {
  background: #fffaf2 !important;
}

:deep(.execution-table .row-dirty:hover td) {
  background: #fff3e0 !important;
}

:deep(.execution-table .status-select .el-select__wrapper) {
  border-radius: 6px;
}

/* 操作列：两按钮单行 */
:deep(.action-col .cell) {
  white-space: nowrap;
}

/* —— 分页 —— */
.pagination-container {
  margin-top: 16px;
  display: flex;
  justify-content: center;
}

/* —— 空态 —— */
.empty-state {
  background: var(--g-bg);
  border: 1px solid var(--g-line);
  border-radius: 8px;
  box-shadow: var(--g-shadow);
  padding: 48px 24px;
  text-align: center;
  color: var(--g-ink-soft);
  font-size: 14px;
}

/* —— 响应式 —— */
@media (max-width: 768px) {
  .execution-detail {
    padding: 16px;
  }
  .plan-header,
  .run-card {
    padding: 16px;
  }
  .plan-header__title {
    font-size: 19px;
  }
}
</style>
