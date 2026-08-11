<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">缺陷列表</h1>
      <div class="header-actions">
        <el-button @click="exportList">
          <el-icon><Download /></el-icon>
          导出
        </el-button>
        <el-button type="primary" @click="router.push('/defects/create')">
          <el-icon><Plus /></el-icon>
          新建缺陷
        </el-button>
      </div>
    </div>

    <div class="card-container">
      <div class="filter-bar">
        <el-row :gutter="12">
          <el-col :xs="24" :sm="12" :md="6">
            <el-input v-model="filters.search" placeholder="搜索标题、编号、描述" clearable @keyup.enter="handleSearch">
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
          </el-col>
          <el-col :xs="12" :sm="6" :md="4">
            <el-select v-model="filters.status" placeholder="状态" clearable>
              <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-col>
          <el-col :xs="12" :sm="6" :md="4">
            <el-select v-model="filters.severity" placeholder="严重级别" clearable>
              <el-option v-for="item in severityOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-col>
          <el-col :xs="12" :sm="6" :md="4">
            <el-select v-model="filters.priority" placeholder="优先级" clearable>
              <el-option v-for="item in priorityOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-col>
          <el-col :xs="12" :sm="6" :md="4">
            <el-input v-model="filters.module" placeholder="所属模块" clearable />
          </el-col>
          <el-col :xs="12" :sm="6" :md="4">
            <el-select v-model="filters.project" placeholder="项目" filterable clearable @change="handleProjectFilterChange">
              <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
            </el-select>
          </el-col>
          <el-col :xs="12" :sm="6" :md="4">
            <el-select
              v-model="filters.version"
              placeholder="版本"
              filterable
              clearable
              :disabled="!filters.project"
            >
              <el-option v-for="version in versions" :key="version.id" :label="version.name" :value="version.id" />
            </el-select>
          </el-col>
          <el-col :xs="12" :sm="6" :md="4">
            <el-select v-model="filters.assignee" placeholder="处理人" filterable clearable>
              <el-option v-for="user in users" :key="user.id" :label="user.username || user.name" :value="user.id" />
            </el-select>
          </el-col>
          <el-col :xs="12" :sm="6" :md="4">
            <el-button type="primary" class="full-width" @click="handleSearch">查询</el-button>
          </el-col>
        </el-row>
      </div>

      <div v-if="selectedRows.length" class="batch-bar">
        <span>已选择 {{ selectedRows.length }} 条</span>
        <el-select v-model="batchAction" placeholder="批量动作" size="small" class="batch-select">
          <el-option label="批量指派" value="assign" />
          <el-option label="设置优先级" value="set_priority" />
          <el-option label="设置版本" value="set_version" />
          <el-option label="批量关闭" value="close" />
          <el-option label="重新打开" value="reopen" />
        </el-select>
        <el-select
          v-if="batchAction === 'assign'"
          v-model="batchPayload.assignee_id"
          size="small"
          filterable
          clearable
          placeholder="处理人"
          class="batch-input"
        >
          <el-option v-for="user in users" :key="user.id" :label="user.username || user.name" :value="user.id" />
        </el-select>
        <el-select
          v-if="batchAction === 'set_priority'"
          v-model="batchPayload.priority"
          size="small"
          placeholder="优先级"
          class="batch-input"
        >
          <el-option v-for="item in priorityOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-select
          v-if="batchAction === 'set_version'"
          v-model="batchPayload.version_id"
          size="small"
          filterable
          clearable
          placeholder="版本"
          class="batch-input"
          :disabled="!filters.project"
        >
          <el-option v-for="version in versions" :key="version.id" :label="version.name" :value="version.id" />
        </el-select>
        <el-button size="small" type="primary" @click="submitBatchAction">执行</el-button>
      </div>

      <el-table
        :data="defects"
        v-loading="loading"
        style="width: 100%"
        @selection-change="selectedRows = $event"
      >
        <el-table-column type="selection" width="48" />
        <el-table-column prop="code" label="编号" width="150">
          <template #default="{ row }">
            <el-link type="primary" @click="router.push(`/defects/${row.id}`)">{{ row.code || `#${row.id}` }}</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="260" show-overflow-tooltip />
        <el-table-column prop="severity" label="严重级别" width="110">
          <template #default="{ row }">
            <el-tag :type="getOptionType(severityOptions, row.severity)">{{ getOptionLabel(severityOptions, row.severity) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="90">
          <template #default="{ row }">
            <el-tag :type="getOptionType(priorityOptions, row.priority)">{{ getOptionLabel(priorityOptions, row.priority) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="getOptionType(statusOptions, row.status)">{{ getOptionLabel(statusOptions, row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="module" label="模块" width="130" show-overflow-tooltip />
        <el-table-column label="处理人" width="120">
          <template #default="{ row }">{{ getUserName(row.assignee) }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <div class="table-actions">
              <el-button link type="primary" size="small" @click="router.push(`/defects/${row.id}`)">详情</el-button>
              <el-button link type="primary" size="small" @click="router.push(`/defects/${row.id}/edit`)">编辑</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-container">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="fetchDefects"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Download, Plus, Search } from '@element-plus/icons-vue'
import dayjs from 'dayjs'
import api from '@/utils/api'
import { bulkActionDefects, exportDefects, getDefects } from '@/api/defects'
import {
  getOptionLabel,
  getOptionType,
  priorityOptions,
  severityOptions,
  statusOptions
} from './options'

const router = useRouter()
const loading = ref(false)
const defects = ref([])
const projects = ref([])
const versions = ref([])
const users = ref([])
const selectedRows = ref([])
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const batchAction = ref('')
const batchPayload = reactive({
  assignee_id: '',
  priority: '',
  version_id: ''
})

const filters = reactive({
  search: '',
  status: '',
  severity: '',
  priority: '',
  module: '',
  project: '',
  version: '',
  assignee: ''
})

const buildParams = () => ({
  page: currentPage.value,
  page_size: pageSize.value,
  search: filters.search || undefined,
  status: filters.status || undefined,
  severity: filters.severity || undefined,
  priority: filters.priority || undefined,
  module: filters.module || undefined,
  project: filters.project || undefined,
  version: filters.version || undefined,
  assignee: filters.assignee || undefined,
  ordering: '-created_at'
})

const normalizeList = (data) => data?.results || data || []

const fetchProjects = async () => {
  try {
    const response = await api.get('/projects/')
    projects.value = normalizeList(response.data)
  } catch (error) {
    projects.value = []
  }
}

const fetchVersions = async (projectId = filters.project) => {
  if (!projectId) {
    versions.value = []
    return
  }

  try {
    const response = await api.get(`/versions/projects/${projectId}/versions/`)
    versions.value = normalizeList(response.data)
  } catch (error) {
    versions.value = []
  }
}

const fetchUsers = async () => {
  try {
    const response = await api.get('/users/')
    users.value = normalizeList(response.data)
  } catch (error) {
    users.value = []
  }
}

const fetchDefects = async () => {
  loading.value = true
  try {
    const response = await getDefects(buildParams())
    const data = response.data || {}
    defects.value = data.results || data || []
    total.value = data.count || defects.value.length
  } catch (error) {
    defects.value = []
    total.value = 0
    ElMessage.warning('缺陷列表接口暂不可用，已显示空列表')
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  currentPage.value = 1
  fetchDefects()
}

const handleProjectFilterChange = async () => {
  filters.version = ''
  batchPayload.version_id = ''
  await fetchVersions()
}

const getUserName = (user) => {
  if (!user) return '-'
  if (typeof user === 'string') return user
  return user.username || user.name || user.id || '-'
}

const formatDate = (value) => {
  return value ? dayjs(value).format('YYYY-MM-DD HH:mm') : '-'
}

const submitBatchAction = async () => {
  if (!batchAction.value) {
    ElMessage.warning('请选择批量动作')
    return
  }

  const data = {
    action: batchAction.value,
    defect_ids: selectedRows.value.map((row) => row.id)
  }

  if (batchAction.value === 'assign') {
    if (!batchPayload.assignee_id) {
      ElMessage.warning('请选择处理人')
      return
    }
    data.assignee_id = batchPayload.assignee_id
  }

  if (batchAction.value === 'set_priority') {
    if (!batchPayload.priority) {
      ElMessage.warning('请选择优先级')
      return
    }
    data.priority = batchPayload.priority
  }

  if (batchAction.value === 'set_version') {
    if (!filters.project) {
      ElMessage.warning('请先选择项目，再设置版本')
      return
    }
    if (!batchPayload.version_id) {
      ElMessage.warning('请选择版本')
      return
    }
    data.version_id = batchPayload.version_id
  }

  try {
    await bulkActionDefects(data)
    ElMessage.success('批量操作已提交')
    selectedRows.value = []
    fetchDefects()
  } catch (error) {
    ElMessage.error('批量操作失败')
  }
}

const exportList = async () => {
  try {
    const response = await exportDefects(buildParams())
    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.download = `defects-${dayjs().format('YYYYMMDDHHmmss')}.xlsx`
    link.click()
    window.URL.revokeObjectURL(url)
  } catch (error) {
    ElMessage.error('导出失败')
  }
}

onMounted(() => {
  fetchProjects()
  fetchUsers()
  fetchDefects()
})
</script>

<style lang="scss" scoped>
.header-actions,
.batch-bar {
  display: flex;
  align-items: center;
  gap: 10px;
}

.filter-bar {
  margin-bottom: 16px;

  // 筛选项在窄屏下会折成多行，el-row 的 gutter 只产生水平间距，
  // 折行后行与行之间没有纵向间距会“挤到一起”，这里补一个 row-gap
  :deep(.el-row) {
    row-gap: 12px;
  }
}

.full-width {
  width: 100%;
}

.batch-bar {
  margin-bottom: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  background: #f5f7fa;
}

.batch-select {
  width: 140px;
}

.batch-input {
  width: 160px;
}

.pagination-container {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}
</style>
