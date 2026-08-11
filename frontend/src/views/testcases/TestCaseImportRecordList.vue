<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h1 class="page-title">{{ $t('testcase.importRecordTitle') }}</h1>
      </div>
      <div class="header-actions">
        <el-button @click="router.push('/ai-generation/testcases')">
          {{ $t('testcase.backToList') }}
        </el-button>
        <el-button type="primary" @click="fetchRecords">
          {{ $t('common.refresh') }}
        </el-button>
      </div>
    </div>

    <div class="card-container">
      <div class="table-container">
        <el-table :data="records" v-loading="loading" style="width: 100%">
          <el-table-column prop="import_no" :label="$t('testcase.importNo')" min-width="220" />
          <el-table-column prop="project_name" :label="$t('testcase.importProject')" min-width="160" />
          <el-table-column prop="status" :label="$t('testcase.importStatus')" width="120">
            <template #default="{ row }">
              <el-tag :type="getStatusType(row.status)">{{ getStatusText(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="progress" :label="$t('testcase.importProgress')" width="180">
            <template #default="{ row }">
              <el-progress :percentage="row.progress || 0" :status="row.status === 'failed' ? 'exception' : undefined" />
            </template>
          </el-table-column>
          <el-table-column :label="$t('testcase.importSummary')" min-width="180">
            <template #default="{ row }">
              {{ row.success_count }}/{{ row.total_rows }}
              <span v-if="row.failed_count > 0">, {{ $t('testcase.failed') }} {{ row.failed_count }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="created_by_name" :label="$t('testcase.importOperator')" width="140" />
          <el-table-column prop="created_at" :label="$t('testcase.createdAt')" width="180">
            <template #default="{ row }">
              {{ formatDate(row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column prop="completed_at" :label="$t('testcase.completedAt')" width="180">
            <template #default="{ row }">
              {{ row.completed_at ? formatDate(row.completed_at) : '-' }}
            </template>
          </el-table-column>
          <el-table-column :label="$t('project.actions')" width="180" fixed="right">
            <template #default="{ row }">
              <div class="table-actions">
                <el-button link type="primary" size="small" @click="showRecordDetail(row)">{{ $t('common.view') }}</el-button>
                <el-button
                  v-if="row.failed_count > 0"
                  link
                  type="danger"
                  size="small"
                  @click="downloadFailureReport(row)"
                >
                  {{ $t('testcase.downloadFailureReport') }}
                </el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div class="pagination-container">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="total"
          layout="total, sizes, prev, pager, next"
          @current-change="fetchRecords"
          @size-change="handleSizeChange"
        />
      </div>
    </div>

    <el-dialog
      v-model="detailDialogVisible"
      :title="currentRecord?.import_no || $t('testcase.importRecordTitle')"
      width="720px"
    >
      <el-descriptions :column="2" border v-if="currentRecord">
        <el-descriptions-item :label="$t('testcase.importProject')">{{ currentRecord.project_name }}</el-descriptions-item>
        <el-descriptions-item :label="$t('testcase.importStatus')">{{ getStatusText(currentRecord.status) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('testcase.importProgress')">{{ currentRecord.progress }}%</el-descriptions-item>
        <el-descriptions-item :label="$t('testcase.importSummary')">
          {{ currentRecord.success_count }}/{{ currentRecord.total_rows }},
          {{ $t('testcase.failed') }} {{ currentRecord.failed_count }}
        </el-descriptions-item>
        <el-descriptions-item :label="$t('testcase.errorMessage')" :span="2">
          {{ currentRecord.error_message || '-' }}
        </el-descriptions-item>
      </el-descriptions>

      <div class="failure-section">
        <div class="failure-header">
          <span>{{ $t('testcase.failureDetails') }}</span>
          <el-button
            v-if="currentRecord?.failed_count > 0"
            type="danger"
            size="small"
            @click="downloadFailureReport(currentRecord)"
          >
            {{ $t('testcase.downloadFailureReport') }}
          </el-button>
        </div>

        <el-empty v-if="!currentRecord?.failure_details?.length" :description="$t('testcase.noFailureDetails')" />

        <el-table
          v-else
          :data="currentRecord.failure_details"
          size="small"
          max-height="320"
          style="width: 100%"
        >
          <el-table-column prop="row_number" label="Row" width="90" />
          <el-table-column prop="title" :label="$t('testcase.caseTitle')" min-width="180" />
          <el-table-column :label="$t('testcase.failureReason')" min-width="280">
            <template #default="{ row }">
              {{ row.errors?.join('；') || '-' }}
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import dayjs from 'dayjs'
import api from '@/utils/api'

const router = useRouter()
const { t } = useI18n()

const loading = ref(false)
const records = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)
const detailDialogVisible = ref(false)
const currentRecord = ref(null)

let pollTimer = null

const formatDate = (dateString) => {
  return dayjs(dateString).format('YYYY-MM-DD HH:mm')
}

const getStatusText = (status) => {
  return t(`testcase.importStatusMap.${status}`) || status
}

const getStatusType = (status) => {
  const typeMap = {
    pending: 'info',
    importing: 'warning',
    completed: 'success',
    partial_success: 'warning',
    failed: 'danger'
  }
  return typeMap[status] || 'info'
}

const startPolling = () => {
  stopPolling()
  if (!records.value.some(item => ['pending', 'importing'].includes(item.status))) {
    return
  }

  pollTimer = window.setInterval(() => {
    fetchRecords(false)
  }, 5000)
}

const stopPolling = () => {
  if (pollTimer) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
}

const fetchRecords = async (showLoading = true) => {
  if (showLoading) {
    loading.value = true
  }
  try {
    const response = await api.get('/testcases/import-records/', {
      params: {
        page: currentPage.value,
        page_size: pageSize.value
      }
    })
    records.value = response.data.results || []
    total.value = response.data.count || 0
    startPolling()
  } catch (error) {
    ElMessage.error(t('testcase.fetchImportRecordsFailed'))
  } finally {
    loading.value = false
  }
}

const handleSizeChange = () => {
  currentPage.value = 1
  fetchRecords()
}

const showRecordDetail = async (record) => {
  try {
    const response = await api.get(`/testcases/import-records/${record.id}/`)
    currentRecord.value = response.data
    detailDialogVisible.value = true
  } catch (error) {
    ElMessage.error(t('testcase.fetchImportDetailFailed'))
  }
}

const downloadBlob = (blob, fileName) => {
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = fileName
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}

const downloadFailureReport = async (record) => {
  if (!record.failed_count) {
    ElMessage.warning(t('testcase.noImportFile'))
    return
  }

  try {
    const response = await api.get(`/testcases/import-records/${record.id}/failure-report/`, {
      responseType: 'blob'
    })
    downloadBlob(response.data, `${record.import_no}_failed_rows.xlsx`)
  } catch (error) {
    ElMessage.error(t('testcase.downloadFailureReportFailed'))
  }
}

onMounted(() => {
  fetchRecords()
})

onBeforeUnmount(() => {
  stopPolling()
})
</script>

<style lang="scss" scoped>
.page-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  padding: 20px;
  box-sizing: border-box;
  overflow: hidden;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  flex-shrink: 0;
}

.page-title {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: #303133;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.card-container {
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow: hidden;
  background: #fff;
  border-radius: 4px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.table-container {
  flex: 1;
  overflow: auto;
  padding: 20px;
}

.pagination-container {
  padding: 20px;
  border-top: 1px solid #ebeef5;
  display: flex;
  justify-content: center;
}

.failure-section {
  margin-top: 20px;
}

.failure-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
</style>
