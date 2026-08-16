<template>
  <div class="self-healing-page">
    <div class="toolbar">
      <el-select v-model="projectId" clearable placeholder="选择项目" style="width: 220px" @change="reload">
        <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
      </el-select>
      <el-select v-model="days" style="width: 120px; margin-left: 8px" @change="reload">
        <el-option :value="7" label="近 7 天" />
        <el-option :value="30" label="近 30 天" />
        <el-option :value="90" label="近 90 天" />
      </el-select>
      <el-button type="primary" :loading="loading" style="margin-left: 8px" @click="reload">刷新</el-button>
    </div>

    <el-row :gutter="16" class="stats-row">
      <el-col :span="6"><el-card shadow="hover"><div class="stat-label">诊断总数</div><div class="stat-value">{{ stats.diagnosis_total || 0 }}</div></el-card></el-col>
      <el-col :span="6"><el-card shadow="hover"><div class="stat-label">自愈成功率</div><div class="stat-value">{{ stats.success_rate || 0 }}%</div></el-card></el-col>
      <el-col :span="6"><el-card shadow="hover"><div class="stat-label">已应用 / 回滚</div><div class="stat-value">{{ stats.proposals?.applied || 0 }} / {{ stats.rollback_count || 0 }}</div></el-card></el-col>
      <el-col :span="6"><el-card shadow="hover"><div class="stat-label">备用命中 / 升格</div><div class="stat-value">{{ stats.backup_hit_count || 0 }} / {{ stats.promote_count || 0 }}</div></el-card></el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :span="10">
        <el-card header="失败分类分布">
          <div ref="chartRef" style="height: 280px" />
        </el-card>
      </el-col>
      <el-col :span="14">
        <el-card header="验证状态">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="通过">{{ stats.verification?.passed || 0 }}</el-descriptions-item>
            <el-descriptions-item label="失败">{{ stats.verification?.failed || 0 }}</el-descriptions-item>
            <el-descriptions-item label="跳过">{{ stats.verification?.skipped || 0 }}</el-descriptions-item>
            <el-descriptions-item label="待验证">{{ stats.verification?.pending || 0 }}</el-descriptions-item>
            <el-descriptions-item label="验证失败率">{{ stats.verify_fail_rate || 0 }}%</el-descriptions-item>
            <el-descriptions-item label="元素累计自愈">{{ stats.element_heals?.total_heal_count || 0 }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>

    <el-card header="诊断列表" style="margin-top: 16px">
      <el-table :data="rows" v-loading="listLoading" stripe>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="execution_type" label="类型" width="90" />
        <el-table-column prop="execution_id" label="执行ID" width="90" />
        <el-table-column prop="category_display" label="分类" width="110">
          <template #default="{ row }">{{ row.category_display || row.category }}</template>
        </el-table-column>
        <el-table-column prop="summary" label="摘要" min-width="200" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="90" />
        <el-table-column label="验证" width="100">
          <template #default="{ row }">
            <el-tag
              v-if="primaryProposal(row)?.verify_status === 'failed'"
              type="danger"
              size="small"
            >建议回滚</el-tag>
            <span v-else>{{ primaryProposal(row)?.verify_status || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间" width="170" />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDiagnosis(row)">查看</el-button>
            <el-button
              v-if="row.execution_type !== 'app'"
              link
              type="warning"
              @click="deepDiagnose(row)"
            >深度AI</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <FailureDiagnosisPanel
      v-model="showPanel"
      :diagnosis="activeDiagnosis"
      :proposals="activeProposals"
      :loading="panelLoading"
      @refresh="reload"
    />
  </div>
</template>

<script setup>
import { nextTick, onMounted, onBeforeUnmount, ref } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import {
  getSelfHealingStats,
  listFailureDiagnoses,
  getUiProjects,
  diagnoseAIExecution,
  diagnoseTestCaseExecution
} from '@/api/ui_automation'
import FailureDiagnosisPanel from '../ai/FailureDiagnosisPanel.vue'

const projects = ref([])
const projectId = ref(null)
const days = ref(30)
const stats = ref({})
const rows = ref([])
const loading = ref(false)
const listLoading = ref(false)
const chartRef = ref(null)
let chart = null

const showPanel = ref(false)
const activeDiagnosis = ref(null)
const activeProposals = ref([])
const panelLoading = ref(false)

function primaryProposal(row) {
  const list = row.proposals || []
  return list.find((p) => p.target === 'test_asset') || list[0]
}

async function loadProjects() {
  const res = await getUiProjects({ page_size: 200 })
  projects.value = res.data?.results || res.data || []
}

async function reload() {
  loading.value = true
  listLoading.value = true
  try {
    const params = { days: days.value }
    if (projectId.value) params.project_id = projectId.value
    const [s, list] = await Promise.all([
      getSelfHealingStats(params),
      listFailureDiagnoses({
        project: projectId.value || undefined,
        page_size: 50
      })
    ])
    stats.value = s.data || {}
    rows.value = list.data?.results || list.data || []
    await nextTick()
    renderChart()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || e.message || '加载失败')
  } finally {
    loading.value = false
    listLoading.value = false
  }
}

function renderChart() {
  if (!chartRef.value) return
  if (!chart) chart = echarts.init(chartRef.value)
  const cats = stats.value.by_category || []
  chart.setOption({
    tooltip: { trigger: 'item' },
    series: [{
      type: 'pie',
      radius: ['35%', '65%'],
      data: cats.map((c) => ({ name: c.category, value: c.count }))
    }]
  })
}

function openDiagnosis(row) {
  activeDiagnosis.value = row
  activeProposals.value = row.proposals || []
  showPanel.value = true
}

async function deepDiagnose(row) {
  panelLoading.value = true
  showPanel.value = true
  try {
    let res
    if (row.execution_type === 'ai') {
      res = await diagnoseAIExecution(row.execution_id, { use_llm: true })
    } else {
      res = await diagnoseTestCaseExecution(row.execution_id, { use_llm: true })
    }
    activeDiagnosis.value = res.data?.diagnosis
    activeProposals.value = res.data?.proposals || []
    await reload()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || e.message || '诊断失败')
  } finally {
    panelLoading.value = false
  }
}

onMounted(async () => {
  await loadProjects()
  await reload()
  window.addEventListener('resize', () => chart?.resize())
})

onBeforeUnmount(() => {
  chart?.dispose()
  chart = null
})
</script>

<style scoped>
.self-healing-page { padding: 16px; }
.toolbar { margin-bottom: 16px; display: flex; align-items: center; }
.stats-row { margin-bottom: 16px; }
.stat-label { color: #909399; font-size: 13px; }
.stat-value { font-size: 24px; font-weight: 600; margin-top: 6px; }
</style>
