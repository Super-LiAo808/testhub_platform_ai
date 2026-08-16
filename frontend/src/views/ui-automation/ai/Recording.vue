<template>
  <div class="recording-page">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>录制回归脚本</span>
          <div class="header-tags">
            <el-tag v-if="session" :type="statusType">{{ statusText }}</el-tag>
            <el-tag v-if="browserReady" type="success">浏览器已就绪</el-tag>
            <el-tag v-if="generatedCaseId" type="success">用例 #{{ generatedCaseId }}</el-tag>
            <el-tag v-if="generatedScriptId" type="success">脚本 #{{ generatedScriptId }}</el-tag>
          </div>
        </div>
      </template>

      <el-form label-width="100px" class="form">
        <el-form-item label="UI 项目" required>
          <el-select v-model="projectId" placeholder="选择项目" filterable style="width: 360px" :disabled="recording">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="起始 URL">
          <el-input v-model="startUrl" placeholder="默认使用项目 base_url" :disabled="recording" style="width: 480px" />
        </el-form-item>
        <el-form-item label="用例名称">
          <el-input v-model="caseName" placeholder="编译后的回归用例名" style="width: 360px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="starting" :disabled="recording || !projectId" @click="startRecording">
            开始录制
          </el-button>
          <el-button type="warning" :loading="stopping" :disabled="!session || session.status !== 'recording'" @click="stopRecording">
            停止并生成用例
          </el-button>
          <el-button type="success" :disabled="!actionTraceId || recording" :loading="compiling" @click="compileTrace">
            重新编译
          </el-button>
        </el-form-item>
      </el-form>

      <el-alert
        type="info"
        :closable="false"
        title="使用说明"
        description="1) 选择项目并开始录制，等待本机弹出 Chromium；2) 在浏览器中完成操作；3) 点击「停止并生成用例」，系统会自动生成可回归 TestCase，并同步创建一一对应的配套脚本。"
        style="margin-bottom: 16px"
      />

      <el-alert
        v-if="lastMessage"
        :type="lastMessageType"
        :closable="true"
        :title="lastMessage"
        style="margin-bottom: 16px"
        @close="lastMessage = ''"
      />

      <div class="meta">事件数：{{ events.length }}　轨迹 ID：{{ actionTraceId || '-' }}</div>

      <el-table :data="events" height="420" border>
        <el-table-column type="index" width="60" label="#" />
        <el-table-column prop="type" label="类型" width="100" />
        <el-table-column prop="description" label="描述" min-width="160" />
        <el-table-column prop="url" label="URL" min-width="200" show-overflow-tooltip />
        <el-table-column label="定位器" min-width="220">
          <template #default="{ row }">
            <span v-if="row.selectors?.length">
              {{ row.selectors[0].strategy }}={{ row.selectors[0].value }}
            </span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  compileActionTrace,
  createRecordingSession,
  getRecordingSession,
  getRecordingSessionEvents,
  getUiProjects,
  stopRecordingSession
} from '@/api/ui_automation'

const projects = ref([])
const projectId = ref(null)
const startUrl = ref('')
const caseName = ref('')
const session = ref(null)
const events = ref([])
const actionTraceId = ref(null)
const starting = ref(false)
const stopping = ref(false)
const compiling = ref(false)
const browserReady = ref(false)
const generatedCaseId = ref(null)
const generatedScriptId = ref(null)
const lastMessage = ref('')
const lastMessageType = ref('info')
let pollTimer = null

const recording = computed(() => session.value?.status === 'recording')
const statusText = computed(() => session.value?.status || 'idle')
const statusType = computed(() => {
  const map = { recording: 'warning', stopped: 'success', failed: 'danger', idle: 'info' }
  return map[session.value?.status] || 'info'
})

watch(projectId, (id) => {
  const p = projects.value.find((x) => x.id === id)
  if (p?.base_url && !startUrl.value) startUrl.value = p.base_url
})

onMounted(async () => {
  const res = await getUiProjects({ page_size: 200 })
  projects.value = res.data?.results || res.data || []
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})

async function startRecording() {
  starting.value = true
  generatedCaseId.value = null
  generatedScriptId.value = null
  lastMessage.value = ''
  try {
    const res = await createRecordingSession({
      project_id: projectId.value,
      start_url: startUrl.value,
      name: caseName.value || undefined
    })
    session.value = res.data
    actionTraceId.value = res.data.action_trace_id || res.data.action_trace || null
    events.value = []
    browserReady.value = false
    ElMessage.success('录制已开始，请等待浏览器弹出后操作')
    if (pollTimer) clearInterval(pollTimer)
    pollTimer = setInterval(pollEvents, 1000)
  } catch (e) {
    ElMessage.error(e.response?.data?.error || e.message || '启动录制失败')
  } finally {
    starting.value = false
  }
}

async function pollEvents() {
  if (!session.value?.id) return
  try {
    const res = await getRecordingSessionEvents(session.value.id)
    events.value = res.data?.events || []
    if (res.data?.action_trace_id) actionTraceId.value = res.data.action_trace_id
    browserReady.value = !!res.data?.ready
    if (res.data?.error_message && res.data.status === 'failed') {
      lastMessage.value = res.data.error_message
      lastMessageType.value = 'error'
    }
    if (res.data?.status && res.data.status !== 'recording') {
      session.value = { ...session.value, status: res.data.status }
      if (pollTimer) {
        clearInterval(pollTimer)
        pollTimer = null
      }
      const detail = await getRecordingSession(session.value.id)
      session.value = detail.data
      actionTraceId.value = detail.data.action_trace_id || detail.data.action_trace
    }
  } catch (_) {
    /* ignore poll errors */
  }
}

async function stopRecording() {
  if (!session.value?.id) return
  stopping.value = true
  try {
    const res = await stopRecordingSession(session.value.id, {
      auto_compile: true,
      name: caseName.value || undefined
    })
    const payload = res.data || {}
    session.value = payload.session || payload
    actionTraceId.value = payload.action_trace_id || session.value.action_trace_id || session.value.action_trace
    if (payload.test_case?.id) {
      generatedCaseId.value = payload.test_case.id
      generatedScriptId.value = payload.script_id
        || payload.test_case.linked_script_id
        || payload.preview?.linked_script_id
        || null
      lastMessageType.value = 'success'
    } else if (payload.compile_error) {
      lastMessageType.value = 'warning'
    } else {
      lastMessageType.value = 'info'
    }
    lastMessage.value = payload.message || '录制已停止'
    await pollEvents()
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
    if (generatedCaseId.value) {
      const scriptHint = generatedScriptId.value ? `，配套脚本 #${generatedScriptId.value}` : ''
      ElMessage.success(`已生成回归用例 #${generatedCaseId.value}${scriptHint}`)
    } else {
      ElMessage.warning(payload.compile_error || payload.message || '已停止，但未生成用例')
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.error || e.message || '停止失败')
  } finally {
    stopping.value = false
  }
}

async function compileTrace() {
  if (!actionTraceId.value) {
    ElMessage.warning('没有可编译的轨迹')
    return
  }
  compiling.value = true
  try {
    const res = await compileActionTrace(actionTraceId.value, {
      name: caseName.value || `录制用例-${actionTraceId.value}`,
      commit: true
    })
    const id = res.data?.test_case?.id
    if (id) {
      generatedCaseId.value = id
      generatedScriptId.value = res.data?.script?.id
        || res.data?.test_case?.linked_script_id
        || res.data?.preview?.linked_script_id
        || null
      const scriptHint = generatedScriptId.value ? `，配套脚本 #${generatedScriptId.value}` : ''
      ElMessage.success(`已生成回归用例 #${id}${scriptHint}`)
    } else {
      ElMessage.success('编译完成')
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.error || e.message || '编译失败')
  } finally {
    compiling.value = false
  }
}
</script>

<style scoped>
.recording-page {
  padding: 16px;
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.header-tags {
  display: flex;
  gap: 8px;
  align-items: center;
}
.form {
  margin-bottom: 12px;
}
.meta {
  margin-bottom: 8px;
  color: #909399;
  font-size: 13px;
}
</style>
