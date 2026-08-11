<template>
  <div class="scheduled-tasks">
    <div class="header">
      <h3>{{ $t('appAutomation.scheduledTask.title') }}</h3>
      <el-button type="primary" @click="handleCreate">
        <el-icon><Plus /></el-icon>
        {{ $t('appAutomation.scheduledTask.newTask') }}
      </el-button>
    </div>

    <!-- 筛选 -->
    <div class="filters">
      <el-row :gutter="20">
        <el-col :span="5">
          <el-select v-model="filters.project" :placeholder="$t('appAutomation.scheduledTask.allProjects')" clearable filterable>
            <el-option v-for="p in projectList" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-col>
        <el-col :span="5">
          <el-select v-model="filters.task_type" :placeholder="$t('appAutomation.scheduledTask.taskType')" clearable>
            <el-option :label="$t('appAutomation.scheduledTask.taskTypes.testSuite')" value="TEST_SUITE" />
            <el-option :label="$t('appAutomation.scheduledTask.taskTypes.testCase')" value="TEST_CASE" />
          </el-select>
        </el-col>
        <el-col :span="5">
          <el-select v-model="filters.trigger_type" :placeholder="$t('appAutomation.scheduledTask.triggerType')" clearable>
            <el-option :label="$t('appAutomation.scheduledTask.triggerTypes.cron')" value="CRON" />
            <el-option :label="$t('appAutomation.scheduledTask.triggerTypes.interval')" value="INTERVAL" />
            <el-option :label="$t('appAutomation.scheduledTask.triggerTypes.once')" value="ONCE" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-select v-model="filters.status" :placeholder="$t('appAutomation.common.status')" clearable>
            <el-option :label="$t('appAutomation.scheduledTask.statusTypes.active')" value="ACTIVE" />
            <el-option :label="$t('appAutomation.scheduledTask.statusTypes.paused')" value="PAUSED" />
            <el-option :label="$t('appAutomation.scheduledTask.statusTypes.completed')" value="COMPLETED" />
            <el-option :label="$t('appAutomation.status.failed')" value="FAILED" />
          </el-select>
        </el-col>
        <el-col :span="5">
          <el-button @click="resetFilters">{{ $t('appAutomation.common.reset') }}</el-button>
          <el-button type="primary" @click="loadTasks">{{ $t('appAutomation.common.query') }}</el-button>
        </el-col>
      </el-row>
    </div>

    <!-- 列表 -->
    <el-table :data="tasks" v-loading="loading" border>
      <el-table-column prop="name" :label="$t('appAutomation.scheduledTask.taskName')" min-width="180" />
      <el-table-column prop="task_type" :label="$t('appAutomation.scheduledTask.taskType')" width="120">
        <template #default="{ row }">
          <el-tag :type="row.task_type === 'TEST_SUITE' ? 'success' : 'primary'" size="small">
            {{ row.task_type_display }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="trigger_type" :label="$t('appAutomation.scheduledTask.trigger')" width="100">
        <template #default="{ row }">
          <el-tag size="small">{{ row.trigger_type_display }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column :label="$t('appAutomation.scheduledTask.notification')" width="100">
        <template #default="{ row }">
          <el-tag v-if="row.notification_type" :type="row.notification_type === 'webhook' ? 'primary' : row.notification_type === 'both' ? 'warning' : ''" size="small">
            {{ row.notification_type_display }}
          </el-tag>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column prop="status" :label="$t('appAutomation.common.status')" width="90">
        <template #default="{ row }">
          <el-tag :type="row.status === 'ACTIVE' ? 'success' : row.status === 'PAUSED' ? 'warning' : 'info'" size="small">
            {{ row.status_display }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column :label="$t('appAutomation.scheduledTask.device')" width="130">
        <template #default="{ row }">
          {{ row.device_name || '-' }}
        </template>
      </el-table-column>
      <el-table-column :label="$t('appAutomation.scheduledTask.nextRunTime')" width="170">
        <template #default="{ row }">
          {{ formatDateTime(row.next_run_time) }}
        </template>
      </el-table-column>
      <el-table-column :label="$t('appAutomation.scheduledTask.lastRunTime')" width="170">
        <template #default="{ row }">
          {{ formatDateTime(row.last_run_time) }}
        </template>
      </el-table-column>
      <el-table-column :label="$t('appAutomation.scheduledTask.executionStats')" width="140">
        <template #default="{ row }">
          <span>{{ $t('appAutomation.scheduledTask.total') }} {{ row.total_runs }}  </span>
          <span style="color:#67c23a">{{ $t('appAutomation.common.success') }} {{ row.successful_runs }}  </span>
          <span style="color:#f56c6c">{{ $t('appAutomation.common.failed') }} {{ row.failed_runs }}</span>
        </template>
      </el-table-column>
      <el-table-column :label="$t('appAutomation.common.operation')" width="140" fixed="right">
        <template #default="{ row }">
          <div class="table-actions">
            <el-button link type="primary" size="small" @click="runNow(row)" :loading="row._running">{{ $t('appAutomation.common.execute') }}</el-button>
            <el-dropdown @command="cmd => handleAction(cmd, row)">
              <el-button link size="small">{{ $t('appAutomation.scheduledTask.more') }}<el-icon><ArrowDown /></el-icon></el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="edit">{{ $t('appAutomation.common.edit') }}</el-dropdown-item>
                  <el-dropdown-item command="pause" v-if="row.status === 'ACTIVE'">{{ $t('appAutomation.scheduledTask.actions.pause') }}</el-dropdown-item>
                  <el-dropdown-item command="resume" v-if="row.status === 'PAUSED'">{{ $t('appAutomation.scheduledTask.actions.resume') }}</el-dropdown-item>
                  <el-dropdown-item command="delete" divided>{{ $t('appAutomation.common.delete') }}</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <div class="pagination">
      <el-pagination
        v-model:current-page="pagination.current"
        v-model:page-size="pagination.size"
        :total="pagination.total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        @size-change="loadTasks"
        @current-change="loadTasks"
      />
    </div>

    <!-- 创建/编辑对话框 -->
    <el-dialog v-model="showDialog" :title="editingTask ? $t('appAutomation.scheduledTask.editTask') : $t('appAutomation.scheduledTask.createTask')" width="720px" :close-on-click-modal="false" @close="resetForm">
      <el-form :model="form" label-width="110px">
        <el-form-item :label="$t('appAutomation.scheduledTask.taskName')" required>
          <el-input v-model="form.name" :placeholder="$t('appAutomation.scheduledTask.rules.nameRequired')" />
        </el-form-item>
        <el-form-item :label="$t('appAutomation.scheduledTask.relatedProject')">
          <el-select v-model="form.project" :placeholder="$t('appAutomation.common.selectProject')" clearable filterable style="width:100%">
            <el-option v-for="p in projectList" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="$t('appAutomation.scheduledTask.taskDesc')">
          <el-input v-model="form.description" type="textarea" :placeholder="$t('appAutomation.scheduledTask.taskDescPlaceholder')" />
        </el-form-item>

        <el-form-item :label="$t('appAutomation.scheduledTask.taskType')" required>
          <el-radio-group v-model="form.task_type">
            <el-radio value="TEST_SUITE">{{ $t('appAutomation.scheduledTask.taskTypes.testSuiteShort') }}</el-radio>
            <el-radio value="TEST_CASE">{{ $t('appAutomation.scheduledTask.taskTypes.testCaseShort') }}</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item v-if="form.task_type === 'TEST_SUITE'" :label="$t('appAutomation.scheduledTask.testSuite')" required>
          <el-select v-model="form.test_suite" :placeholder="$t('appAutomation.scheduledTask.selectSuite')" filterable>
            <el-option v-for="s in suites" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>

        <el-form-item v-if="form.task_type === 'TEST_CASE'" :label="$t('appAutomation.scheduledTask.testCase')" required>
          <el-select v-model="form.test_case" :placeholder="$t('appAutomation.scheduledTask.selectTestCase')" filterable>
            <el-option v-for="tc in testCases" :key="tc.id" :label="tc.name" :value="tc.id" />
          </el-select>
        </el-form-item>

        <el-form-item :label="$t('appAutomation.scheduledTask.executionDevice')" required>
          <el-select v-model="form.device" :placeholder="$t('appAutomation.scheduledTask.selectDevice')" filterable>
            <el-option v-for="d in devices" :key="d.id" :label="d.name || d.device_id" :value="d.id" />
          </el-select>
        </el-form-item>

        <el-form-item :label="$t('appAutomation.scheduledTask.appPackage')">
          <el-select v-model="form.app_package" :placeholder="$t('appAutomation.scheduledTask.selectAppPackage')" filterable clearable>
            <el-option v-for="p in packages" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>

        <el-form-item :label="$t('appAutomation.scheduledTask.triggerType')" required>
          <el-radio-group v-model="form.trigger_type">
            <el-radio value="CRON">{{ $t('appAutomation.scheduledTask.triggerTypes.cron') }}</el-radio>
            <el-radio value="INTERVAL">{{ $t('appAutomation.scheduledTask.triggerTypes.interval') }}</el-radio>
            <el-radio value="ONCE">{{ $t('appAutomation.scheduledTask.triggerTypes.once') }}</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item v-if="form.trigger_type === 'CRON'" :label="$t('appAutomation.scheduledTask.cronExpression')" required>
          <el-input v-model="form.cron_expression" :placeholder="$t('appAutomation.scheduledTask.cronPlaceholder')" />
          <div class="cron-help">
            <el-tooltip raw-content placement="top">
              <template #content>
                <div style="line-height: 1.6; text-align: left;">
                  <div>{{ $t('appAutomation.scheduledTask.cronHelp.format') }}</div>
                  <div>{{ $t('appAutomation.scheduledTask.cronHelp.minute') }}</div>
                  <div>{{ $t('appAutomation.scheduledTask.cronHelp.hour') }}</div>
                  <div>{{ $t('appAutomation.scheduledTask.cronHelp.day') }}</div>
                  <div>{{ $t('appAutomation.scheduledTask.cronHelp.month') }}</div>
                  <div>{{ $t('appAutomation.scheduledTask.cronHelp.week') }}</div>
                  <div style="margin-top: 8px;">{{ $t('appAutomation.scheduledTask.cronHelp.examples') }}</div>
                  <div>{{ $t('appAutomation.scheduledTask.cronHelp.everyDay') }}</div>
                  <div>{{ $t('appAutomation.scheduledTask.cronHelp.everyHour') }}</div>
                  <div>{{ $t('appAutomation.scheduledTask.cronHelp.everyMonday') }}</div>
                  <div>{{ $t('appAutomation.scheduledTask.cronHelp.everyMonth') }}</div>
                </div>
              </template>
              <span style="cursor: pointer; color: #409EFF;">{{ $t('appAutomation.scheduledTask.cronHelpLink') }}</span>
            </el-tooltip>
          </div>
        </el-form-item>

        <el-form-item v-if="form.trigger_type === 'INTERVAL'" :label="$t('appAutomation.scheduledTask.intervalTime')" required>
          <el-input-number v-model="form.interval_seconds" :min="60" :step="60" />
          <span class="unit">{{ $t('appAutomation.scheduledTask.intervalUnit') }}</span>
        </el-form-item>

        <el-form-item v-if="form.trigger_type === 'ONCE'" :label="$t('appAutomation.scheduledTask.executeTime')" required>
          <el-date-picker v-model="form.execute_at" type="datetime" :placeholder="$t('appAutomation.scheduledTask.selectExecuteTime')" />
        </el-form-item>

        <el-form-item :label="$t('appAutomation.scheduledTask.notificationSettings')">
          <el-checkbox v-model="form.notify_on_success">{{ $t('appAutomation.scheduledTask.notifyOnSuccess') }}</el-checkbox>
          <el-checkbox v-model="form.notify_on_failure">{{ $t('appAutomation.scheduledTask.notifyOnFailure') }}</el-checkbox>
        </el-form-item>

        <el-form-item v-if="form.notify_on_success || form.notify_on_failure" :label="$t('appAutomation.scheduledTask.notificationType')">
          <el-select v-model="form.notification_type" :placeholder="$t('appAutomation.scheduledTask.selectNotificationType')">
            <el-option :label="$t('appAutomation.scheduledTask.notificationTypes.email')" value="email" />
            <el-option :label="$t('appAutomation.scheduledTask.notificationTypes.webhook')" value="webhook" />
            <el-option :label="$t('appAutomation.scheduledTask.notificationTypes.both')" value="both" />
          </el-select>
        </el-form-item>

        <el-form-item
          v-if="(form.notify_on_success || form.notify_on_failure) && (form.notification_type === 'email' || form.notification_type === 'both')"
          :label="$t('appAutomation.scheduledTask.notifyEmails')"
        >
          <el-select v-model="form.notify_emails" multiple filterable allow-create :placeholder="$t('appAutomation.scheduledTask.notifyEmailsPlaceholder')">
          </el-select>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showDialog = false">{{ $t('appAutomation.common.cancel') }}</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitting">
          {{ editingTask ? $t('appAutomation.common.save') : $t('appAutomation.scheduledTask.create') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { Plus, ArrowDown } from '@element-plus/icons-vue'
import {
  getAppScheduledTasks,
  createAppScheduledTask,
  updateAppScheduledTask,
  deleteAppScheduledTask,
  pauseAppScheduledTask,
  resumeAppScheduledTask,
  runAppScheduledTask,
  getTestSuiteList,
  getTestCaseList,
  getDeviceList,
  getPackageList,
  getAppProjects,
} from '@/api/app-automation.js'

const { t } = useI18n()

const projectList = ref([])
const tasks = ref([])
const suites = ref([])
const testCases = ref([])
const devices = ref([])
const packages = ref([])
const loading = ref(false)
const submitting = ref(false)
const showDialog = ref(false)
const editingTask = ref(null)

const filters = reactive({ project: null, task_type: '', trigger_type: '', status: '' })
const pagination = reactive({ current: 1, size: 10, total: 0 })

const defaultForm = {
  name: '', description: '', project: null, task_type: 'TEST_SUITE', trigger_type: 'CRON',
  cron_expression: '0 0 * * *', interval_seconds: 3600, execute_at: '',
  device: '', app_package: '', test_suite: '', test_case: '',
  notify_on_success: false, notify_on_failure: false,
  notification_type: '', notify_emails: [],
}
const form = reactive({ ...defaultForm })

onMounted(() => {
  getAppProjects({ page_size: 100 }).then(res => { projectList.value = res.data.results || res.data || [] }).catch(() => {})
  loadTasks()
  loadOptions()
})

const loadTasks = async () => {
  loading.value = true
  try {
    const params = { page: pagination.current, page_size: pagination.size }
    if (filters.project) params.project = filters.project
    if (filters.task_type) params.task_type = filters.task_type
    if (filters.trigger_type) params.trigger_type = filters.trigger_type
    if (filters.status) params.status = filters.status
    const res = await getAppScheduledTasks(params)
    tasks.value = (res.data.results || []).map(t => ({ ...t, _running: false }))
    pagination.total = res.data.count || 0
  } catch { ElMessage.error(t('appAutomation.scheduledTask.messages.loadFailed')) }
  finally { loading.value = false }
}

const loadOptions = async () => {
  try {
    const [s, tc, d, p] = await Promise.all([
      getTestSuiteList({ page_size: 200 }),
      getTestCaseList({ page_size: 500 }),
      getDeviceList({ page_size: 100 }),
      getPackageList({ page_size: 100 }),
    ])
    suites.value = s.data.results || s.data || []
    testCases.value = tc.data.results || tc.data || []
    devices.value = d.data.results || d.data || []
    packages.value = p.data.results || p.data || []
  } catch (e) { console.error('加载选项失败', e) }
}

const handleCreate = () => {
  editingTask.value = null
  resetForm()
  showDialog.value = true
}

const resetForm = () => Object.assign(form, { ...defaultForm, notify_emails: [] })
const resetFilters = () => { Object.assign(filters, { project: null, task_type: '', trigger_type: '', status: '' }); loadTasks() }

const submitForm = async () => {
  if (!form.name) return ElMessage.warning(t('appAutomation.scheduledTask.rules.nameRequired'))
  if (!form.device) return ElMessage.warning(t('appAutomation.scheduledTask.rules.deviceRequired'))

  submitting.value = true
  try {
    const data = { ...form }
    // 清理多余字段
    if (data.task_type === 'TEST_SUITE') delete data.test_case
    else delete data.test_suite
    if (data.trigger_type !== 'CRON') delete data.cron_expression
    if (data.trigger_type !== 'INTERVAL') delete data.interval_seconds
    if (data.trigger_type !== 'ONCE') delete data.execute_at
    if (!data.notify_on_success && !data.notify_on_failure) {
      delete data.notification_type
      delete data.notify_emails
    }
    if (!data.app_package) delete data.app_package

    if (editingTask.value) {
      await updateAppScheduledTask(editingTask.value.id, data)
      ElMessage.success(t('appAutomation.common.updateSuccess'))
    } else {
      await createAppScheduledTask(data)
      ElMessage.success(t('appAutomation.common.createSuccess'))
    }
    showDialog.value = false
    loadTasks()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.response?.data?.message || t('appAutomation.scheduledTask.messages.operationFailed'))
  } finally { submitting.value = false }
}

const runNow = async (task) => {
  task._running = true
  try {
    await runAppScheduledTask(task.id)
    ElMessage.success(t('appAutomation.scheduledTask.messages.runSuccess'))
    setTimeout(loadTasks, 2000)
  } catch (e) {
    ElMessage.error(e.response?.data?.message || t('appAutomation.scheduledTask.messages.runFailed'))
  } finally { task._running = false }
}

const handleAction = (cmd, task) => {
  switch (cmd) {
    case 'edit': editTask(task); break
    case 'pause': pauseTask(task); break
    case 'resume': resumeTask(task); break
    case 'delete': deleteTask(task); break
  }
}

const editTask = (task) => {
  editingTask.value = task
  Object.assign(form, {
    name: task.name, description: task.description || '',
    task_type: task.task_type, trigger_type: task.trigger_type,
    cron_expression: task.cron_expression || '0 0 * * *',
    interval_seconds: task.interval_seconds || 3600,
    execute_at: task.execute_at || '',
    device: task.device || '', app_package: task.app_package || '',
    test_suite: task.test_suite || '', test_case: task.test_case || '',
    notify_on_success: task.notify_on_success || false,
    notify_on_failure: task.notify_on_failure || false,
    notification_type: task.notification_type || '',
    notify_emails: task.notify_emails || [],
  })
  showDialog.value = true
}

const pauseTask = async (task) => {
  try { await pauseAppScheduledTask(task.id); ElMessage.success(t('appAutomation.scheduledTask.messages.pauseSuccess')); loadTasks() }
  catch { ElMessage.error(t('appAutomation.scheduledTask.messages.pauseFailed')) }
}
const resumeTask = async (task) => {
  try { await resumeAppScheduledTask(task.id); ElMessage.success(t('appAutomation.scheduledTask.messages.resumeSuccess')); loadTasks() }
  catch { ElMessage.error(t('appAutomation.scheduledTask.messages.resumeFailed')) }
}
const deleteTask = async (task) => {
  try {
    await ElMessageBox.confirm(t('appAutomation.scheduledTask.messages.deleteConfirm', { name: task.name }), t('appAutomation.scheduledTask.messages.deleteConfirmTitle'), { type: 'warning' })
    await deleteAppScheduledTask(task.id)
    ElMessage.success(t('appAutomation.common.deleteSuccess'))
    loadTasks()
  } catch (e) { if (e !== 'cancel') ElMessage.error(t('appAutomation.common.deleteFailed')) }
}

const formatDateTime = (s) => {
  if (!s) return '-'
  return new Date(s).toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  }).replace(/\//g, '-')
}
</script>

<style scoped>
.scheduled-tasks { padding: 20px; display: flex; flex-direction: column; height: 100%; }
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.filters { margin-bottom: 20px; background: #f8f9fa; padding: 20px; border-radius: 8px; }
.pagination { margin-top: 20px; display: flex; justify-content: flex-end; }
.cron-help { margin-top: 8px; font-size: 12px; }
.unit { margin-left: 8px; color: #606266; }
</style>
