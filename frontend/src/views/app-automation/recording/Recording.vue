<template>
  <div class="app-recording-page">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>APP 操作录制（Android）</span>
          <div class="header-tags">
            <el-tag v-if="session" :type="statusType">{{ statusText }}</el-tag>
            <el-tag v-if="mirrorModeTag" :type="mirrorMode === 'scrcpy' ? 'success' : 'warning'">{{ mirrorModeTag }}</el-tag>
            <el-tag v-if="streamTag" :type="wsConnected ? 'success' : 'warning'">{{ streamTag }}</el-tag>
            <el-tag v-if="testCaseId" type="success">用例 #{{ testCaseId }}</el-tag>
          </div>
        </div>
      </template>

      <el-form label-width="90px" class="form" inline>
        <el-form-item label="项目" required>
          <el-select v-model="projectId" placeholder="选择项目" filterable style="width: 220px" :disabled="recording">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="设备" required>
          <el-select v-model="deviceId" placeholder="选择 Android 设备" filterable style="width: 260px" :disabled="recording">
            <el-option
              v-for="d in devices"
              :key="d.id"
              :label="`${d.name || d.device_id} (${d.device_id})`"
              :value="d.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="用例名">
          <el-input v-model="caseName" placeholder="停止后保存的用例名" style="width: 220px" />
        </el-form-item>
        <el-form-item label="清晰度">
          <el-select v-model="streamQuality" style="width: 120px" @change="onQualityChange">
            <el-option label="均衡" value="balanced" />
            <el-option label="清晰" value="clear" />
            <el-option label="流畅" value="fast" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="starting" :disabled="recording || !projectId || !deviceId" @click="startRecording">
            {{ starting ? startingLabel : '开始录制' }}
          </el-button>
          <el-button type="warning" :loading="stopping" :disabled="!recording" @click="stopRecording">
            停止并保存用例
          </el-button>
          <el-button v-if="testCaseId" type="success" @click="openSceneBuilder">在用例编排中查看</el-button>
        </el-form-item>
      </el-form>

      <el-alert
        type="info"
        :closable="false"
        title="说明"
        description="实时投屏必须用 Daphne（不要用 runserver）。推荐 USB。顶栏出现「投屏 WS·H264」才是实时；若只有「投屏 HTTP（非实时）」说明 WebSocket 未通。"
        style="margin-bottom: 12px"
      />
      <el-alert
        v-if="!wsConnected && recording && wsFailed"
        type="error"
        :closable="false"
        title="WebSocket 未连通：请确认只用 Daphne（不要 runserver），命令：python -m daphne -b 0.0.0.0 -p 8000 backend.asgi:application，然后刷新重试"
        style="margin-bottom: 12px"
      />
      <el-alert
        v-else-if="!wsConnected && recording"
        type="warning"
        :closable="false"
        title="正在连接 WebSocket…"
        style="margin-bottom: 12px"
      />
      <el-alert
        v-if="streamHint"
        type="warning"
        :closable="false"
        :title="streamHint"
        style="margin-bottom: 12px"
      />

      <el-row :gutter="16">
        <el-col :span="16">
          <div class="mirror-toolbar">
            <span class="toolbar-label">投屏</span>
            <el-button-group>
              <el-button size="small" @click="zoomOut" :disabled="mirrorScale <= 0.8">缩小</el-button>
              <el-button size="small" @click="zoomReset">100%</el-button>
              <el-button size="small" @click="zoomIn" :disabled="mirrorScale >= 2.5">放大</el-button>
              <el-button size="small" @click="zoomFit">适应宽度</el-button>
            </el-button-group>
            <span class="scale-text">{{ Math.round(mirrorScale * 100) }}%</span>
            <el-button size="small" type="primary" plain @click="toggleMaximize">
              {{ mirrorMaximized ? '退出最大化' : '最大化投屏' }}
            </el-button>
          </div>
          <div
            class="mirror-panel"
            :class="{ maximized: mirrorMaximized }"
          >
            <div v-if="mirrorMaximized" class="max-bar">
              <span>投屏最大化 · {{ Math.round(mirrorScale * 100) }}%</span>
              <div class="max-bar-actions">
                <el-button size="small" @click="zoomOut">缩小</el-button>
                <el-button size="small" @click="zoomIn">放大</el-button>
                <el-button size="small" type="primary" @click="toggleMaximize">退出</el-button>
              </div>
            </div>
            <div
              class="mirror-wrap"
              ref="mirrorWrap"
              @pointerdown="onPointerDown"
              @pointermove="onPointerMove"
              @pointerup="onPointerUp"
              @pointercancel="onPointerUp"
              @wheel.prevent="onMirrorWheel"
            >
              <div class="mirror-stage" :style="stageStyle">
                <canvas
                  ref="mirrorCanvas"
                  class="mirror-img mirror-canvas"
                  :class="{ 'is-active': mirrorMode === 'scrcpy' && videoReady }"
                />
                <img
                  v-show="frameUrl && !(mirrorMode === 'scrcpy' && videoReady)"
                  :src="frameUrl"
                  class="mirror-img"
                  draggable="false"
                  alt="device mirror"
                />
                <div
                  v-if="!frameUrl && !videoReady"
                  class="mirror-empty"
                  :style="placeholderStyle"
                >等待投屏画面…</div>
              </div>
              <div v-if="dragLine" class="drag-line" :style="dragLineStyle" />
            </div>
          </div>
          <div class="input-row">
            <el-input v-model="inputText" placeholder="先点投屏里的输入框聚焦，再输入中文/英文后点发送（中文不会抢前台）" style="flex: 1" />
            <el-button type="primary" :disabled="!canInteract || !inputText" @click="sendText">发送输入</el-button>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="steps-title">
            <span>已录制步骤（{{ steps.length }}）</span>
            <el-radio-group v-model="stepsView" size="small">
              <el-radio-button value="list">列表</el-radio-button>
              <el-radio-button value="script">脚本</el-radio-button>
            </el-radio-group>
          </div>
          <el-scrollbar :height="mirrorMaximized ? '200px' : '560px'">
            <template v-if="stepsView === 'list'">
              <div v-for="(s, idx) in steps" :key="idx" class="step-item">
                <span class="idx">{{ idx + 1 }}.</span>
                <span class="act">{{ stepType(s) }}</span>
                <span class="name">{{ s.name || '-' }}</span>
                <span v-if="stepElementId(s)" class="elid">#{{ stepElementId(s) }}</span>
                <span v-if="stepValue(s)" class="val">{{ stepValue(s) }}</span>
              </div>
              <div v-if="!steps.length" class="empty-steps">暂无步骤</div>
            </template>
            <pre v-else class="script-json">{{ scriptJson }}</pre>
          </el-scrollbar>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  getAppProjects,
  getDeviceList,
  createAppRecordingSession,
  stopAppRecordingSession,
  sendAppRecordingEvent,
  getAppRecordingFrame,
  updateAppRecordingSettings
} from '@/api/app-automation'

const router = useRouter()
const projects = ref([])
const devices = ref([])
const projectId = ref(null)
const deviceId = ref(null)
const caseName = ref('')
const session = ref(null)
const starting = ref(false)
const startingLabel = ref('开始录制')
const stopping = ref(false)
const frameUrl = ref('')
const steps = ref([])
const stepsView = ref('list')
const wsConnected = ref(false)
const wsFailed = ref(false)
const pollActive = ref(false)
const streamReady = ref(false)
const streamHint = ref('')
const testCaseId = ref(null)
const inputText = ref('')
const deviceWidth = ref(0)
const deviceHeight = ref(0)
const mirrorWrap = ref(null)
const mirrorCanvas = ref(null)
const mirrorScale = ref(1)
const mirrorMaximized = ref(false)
const streamQuality = ref('balanced')
const mirrorMode = ref('') // scrcpy | screenshot | ''
const videoReady = ref(false)

let ws = null
let wsRetryTimer = null
let wsAttempt = 0
let wsSessionId = null
let pollTimer = null
let pointerStart = null
let dragging = false
const dragLine = ref(null)

let videoDecoder = null
let h264Buffer = new Uint8Array(0)
let decoderConfigured = false
let pendingSps = null
let pendingPps = null

const recording = computed(() => session.value?.status === 'recording')
const hasMirror = computed(() => !!frameUrl.value || videoReady.value)
// 录制就绪且已知分辨率即可点击；不强制等画面（避免 canvas 未解码时完全锁死）
const canInteract = computed(() =>
  recording.value && streamReady.value && deviceWidth.value > 0 && deviceHeight.value > 0
)
const statusType = computed(() => {
  const map = { recording: 'warning', stopped: 'success', failed: 'danger', idle: 'info' }
  return map[session.value?.status] || 'info'
})
const statusText = computed(() => {
  const map = { recording: '录制中', stopped: '已停止', failed: '失败', idle: '空闲' }
  return map[session.value?.status] || '-'
})
const mirrorModeTag = computed(() => {
  if (mirrorMode.value === 'scrcpy') return '投屏 scrcpy'
  if (mirrorMode.value === 'screenshot') return '投屏 截屏回退'
  return ''
})
const streamTag = computed(() => {
  if (wsConnected.value && mirrorMode.value === 'scrcpy' && videoReady.value) return '投屏 WS·H264'
  if (wsConnected.value && mirrorMode.value === 'scrcpy') return '投屏 WS·解码中'
  if (wsConnected.value) return '投屏 WS'
  if (pollActive.value && frameUrl.value) return '投屏 HTTP（非实时）'
  if (pollActive.value) return '拉取画面中'
  return ''
})
const scriptJson = computed(() => JSON.stringify(steps.value, null, 2))
const stageStyle = computed(() => ({
  transform: `scale(${mirrorScale.value})`,
  transformOrigin: 'top center'
}))
const placeholderStyle = computed(() => {
  const dw = deviceWidth.value || 1080
  const dh = deviceHeight.value || 1920
  const maxW = 420
  const h = Math.round(maxW * dh / dw)
  return { width: `${maxW}px`, height: `${Math.min(h, 640)}px`, margin: '0 auto' }
})
const dragLineStyle = computed(() => {
  if (!dragLine.value) return {}
  const { x1, y1, x2, y2 } = dragLine.value
  const len = Math.hypot(x2 - x1, y2 - y1)
  const angle = Math.atan2(y2 - y1, x2 - x1) * 180 / Math.PI
  return {
    left: `${x1}px`,
    top: `${y1}px`,
    width: `${len}px`,
    transform: `rotate(${angle}deg)`
  }
})

function stepType(s) {
  return s?.type || s?.action || '-'
}
function stepElementId(s) {
  return s?.config?.element_id || s?.element_id || null
}
function stepValue(s) {
  const v = s?.config?.value ?? s?.value ?? s?.text
  return v ? String(v) : ''
}

function zoomIn() {
  mirrorScale.value = Math.min(2.5, Math.round((mirrorScale.value + 0.15) * 100) / 100)
}
function zoomOut() {
  mirrorScale.value = Math.max(0.8, Math.round((mirrorScale.value - 0.15) * 100) / 100)
}
function zoomReset() {
  mirrorScale.value = 1
}
function zoomFit() {
  mirrorScale.value = 1
}
function toggleMaximize() {
  mirrorMaximized.value = !mirrorMaximized.value
  if (mirrorMaximized.value && mirrorScale.value < 1.2) {
    mirrorScale.value = 1.35
  }
}
function onMirrorWheel(e) {
  if (!e.ctrlKey && !e.metaKey) return
  if (e.deltaY < 0) zoomIn()
  else zoomOut()
}

watch(mirrorMaximized, (v) => {
  document.body.style.overflow = v ? 'hidden' : ''
})

onMounted(async () => {
  try {
    const [pRes, dRes] = await Promise.all([
      getAppProjects({ page_size: 100 }),
      getDeviceList({ page_size: 100 })
    ])
    projects.value = pRes.data?.results || pRes.data || []
    devices.value = dRes.data?.results || dRes.data || []
    if (projects.value.length) projectId.value = projects.value[0].id
    if (devices.value.length) deviceId.value = devices.value[0].id
  } catch (e) {
    ElMessage.error('加载项目/设备失败')
  }
})

onBeforeUnmount(() => {
  document.body.style.overflow = ''
  stopStreaming()
})

function stopStreaming() {
  closeWs()
  stopPoll()
  resetVideoDecoder()
}

function resetVideoDecoder() {
  try {
    if (videoDecoder && videoDecoder.state !== 'closed') videoDecoder.close()
  } catch (_) { /* ignore */ }
  videoDecoder = null
  decoderConfigured = false
  pendingSps = null
  pendingPps = null
  h264Buffer = new Uint8Array(0)
  videoReady.value = false
}

function supportsWebCodecs() {
  return typeof window !== 'undefined' && typeof window.VideoDecoder === 'function'
}

function concatUint8(a, b) {
  const out = new Uint8Array(a.length + b.length)
  out.set(a, 0)
  out.set(b, a.length)
  return out
}

function findStartCode(data, from = 0) {
  for (let i = from; i + 3 < data.length; i++) {
    if (data[i] === 0 && data[i + 1] === 0) {
      if (data[i + 2] === 1) return { index: i, len: 3 }
      if (data[i + 2] === 0 && data[i + 3] === 1) return { index: i, len: 4 }
    }
  }
  return null
}

function splitAnnexBNalus(data) {
  const nalus = []
  let sc = findStartCode(data, 0)
  while (sc) {
    const next = findStartCode(data, sc.index + sc.len)
    const end = next ? next.index : data.length
    const nalu = data.subarray(sc.index + sc.len, end)
    if (nalu.length) nalus.push(nalu)
    sc = next
  }
  return nalus
}

function codecFromSps(sps) {
  if (!sps || sps.length < 4) return 'avc1.42E01E'
  const profile = sps[1].toString(16).padStart(2, '0')
  const compat = sps[2].toString(16).padStart(2, '0')
  const level = sps[3].toString(16).padStart(2, '0')
  return `avc1.${profile}${compat}${level}`.toUpperCase().replace('AVC1.', 'avc1.')
}

function ensureVideoDecoder(codec) {
  if (!supportsWebCodecs()) return false
  if (videoDecoder && videoDecoder.state !== 'closed') return true
  const canvas = mirrorCanvas.value
  if (!canvas) return false
  const ctx = canvas.getContext('2d')
  videoDecoder = new VideoDecoder({
    output: (frame) => {
      try {
        if (canvas.width !== frame.displayWidth || canvas.height !== frame.displayHeight) {
          canvas.width = frame.displayWidth
          canvas.height = frame.displayHeight
        }
        ctx.drawImage(frame, 0, 0)
        videoReady.value = true
        streamReady.value = true
      } finally {
        frame.close()
      }
    },
    error: (err) => {
      console.warn('VideoDecoder error', err)
      streamHint.value = 'H.264 解码失败，已回退显示低频截屏。建议使用较新的 Chrome/Edge'
      resetVideoDecoder()
      mirrorMode.value = 'screenshot'
    }
  })
  try {
    videoDecoder.configure({ codec: codec || 'avc1.42E01E', optimizeForLatency: true })
    decoderConfigured = true
    return true
  } catch (e) {
    console.warn('VideoDecoder configure failed', e)
    streamHint.value = '当前浏览器不支持 WebCodecs H.264，请升级 Chrome/Edge；将使用截屏画面'
    resetVideoDecoder()
    return false
  }
}

function feedH264Base64(b64) {
  if (!b64) return
  if (!supportsWebCodecs()) {
    if (mirrorMode.value === 'scrcpy') {
      streamHint.value = '浏览器不支持 WebCodecs，请使用 Chrome/Edge；暂用 HTTP 截屏画面'
    }
    return
  }
  let bytes
  try {
    const bin = atob(b64)
    bytes = new Uint8Array(bin.length)
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
  } catch (_) {
    return
  }
  h264Buffer = concatUint8(h264Buffer, bytes)
  // Keep a trailing incomplete NALU window
  const sc = findStartCode(h264Buffer, 0)
  if (!sc) {
    if (h264Buffer.length > 1024 * 1024) h264Buffer = new Uint8Array(0)
    return
  }
  let lastSc = sc
  let cursor = sc.index + sc.len
  while (true) {
    const next = findStartCode(h264Buffer, cursor)
    if (!next) break
    lastSc = next
    cursor = next.index + next.len
  }
  // Process complete NALUs before the last start code (last may be incomplete)
  const completeEnd = lastSc.index
  if (completeEnd <= 0) return
  const complete = h264Buffer.subarray(0, completeEnd)
  h264Buffer = h264Buffer.subarray(completeEnd)

  const nalus = splitAnnexBNalus(complete)
  let accessUnit = []
  let isKey = false
  const flushAu = () => {
    if (!accessUnit.length) return
    if (!decoderConfigured) {
      if (!pendingSps) return
      if (!ensureVideoDecoder(codecFromSps(pendingSps))) return
    }
    if (!videoDecoder || videoDecoder.state === 'closed') return
    // Build Annex-B AU
    let total = 0
    const parts = []
    for (const n of accessUnit) {
      const sc4 = new Uint8Array([0, 0, 0, 1])
      parts.push(sc4, n)
      total += 4 + n.length
    }
    const au = new Uint8Array(total)
    let off = 0
    for (const p of parts) {
      au.set(p, off)
      off += p.length
    }
    try {
      const chunk = new EncodedVideoChunk({
        type: isKey ? 'key' : 'delta',
        timestamp: performance.now() * 1000,
        data: au
      })
      videoDecoder.decode(chunk)
    } catch (e) {
      console.debug('decode failed', e)
    }
    accessUnit = []
    isKey = false
  }

  for (const nalu of nalus) {
    const nalType = nalu[0] & 0x1f
    if (nalType === 7) {
      pendingSps = nalu
      continue
    }
    if (nalType === 8) {
      pendingPps = nalu
      continue
    }
    if (nalType === 9) {
      // AUD — boundary
      flushAu()
      continue
    }
    if (nalType === 5) {
      isKey = true
      // prepend SPS/PPS for IDR
      if (pendingSps) accessUnit.push(pendingSps)
      if (pendingPps) accessUnit.push(pendingPps)
      accessUnit.push(nalu)
      flushAu()
      continue
    }
    if (nalType === 1) {
      accessUnit.push(nalu)
      flushAu()
    }
  }
}

function closeWs() {
  wsSessionId = null
  wsAttempt = 0
  wsFailed.value = false
  if (wsRetryTimer) {
    clearTimeout(wsRetryTimer)
    wsRetryTimer = null
  }
  if (ws) {
    try {
      ws.onopen = null
      ws.onclose = null
      ws.onerror = null
      ws.onmessage = null
      ws.close()
    } catch (_) { /* ignore */ }
    ws = null
  }
  wsConnected.value = false
}

function stopPoll() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  pollActive.value = false
}

function startPoll(sessionId) {
  stopPoll()
  pollActive.value = true
  let polling = false
  const tick = async () => {
    if (!session.value || session.value.status !== 'recording') return
    if (polling) return
    polling = true
    try {
      const res = await getAppRecordingFrame(sessionId)
      const data = res.data || {}
      if (data.session_status && data.session_status !== 'recording') {
        session.value = { ...(session.value || {}), status: data.session_status }
        if (Array.isArray(data.steps)) steps.value = data.steps
        if (data.session_status === 'failed') {
          streamHint.value = data.screencap_error || '录制会话已失败，请重新开始'
          stopPoll()
        }
        return
      }
      if (data.image) frameUrl.value = data.image
      if (data.ready) streamReady.value = true
      if (data.mirror_mode) mirrorMode.value = data.mirror_mode
      if (data.device_width) deviceWidth.value = data.device_width
      if (data.device_height) deviceHeight.value = data.device_height
      if (Array.isArray(data.steps)) {
        const confirmed = steps.value.filter(s => !s._pending).length
        if (data.steps.length >= confirmed) steps.value = data.steps
      }
      if (data.screencap_error) {
        streamHint.value = data.screencap_error
      } else if ((data.image || videoReady.value) && data.ready) {
        if (mirrorMode.value === 'scrcpy' && wsConnected.value) {
          streamHint.value = '投屏中（scrcpy / WebSocket）— 可开始点击录制'
        } else if (wsConnected.value) {
          streamHint.value = '投屏中（WebSocket）— 可开始点击录制'
        } else {
          streamHint.value = '投屏中（HTTP 轮询）— 建议用 Daphne 启用 WebSocket 以获得 scrcpy 流畅度'
        }
      } else if (!data.ready) {
        streamHint.value = '正在连接设备 / 启动投屏，请稍候…'
      }
    } catch (_) { /* ignore transient */ }
    finally { polling = false }
  }
  tick()
  pollTimer = setInterval(tick, mirrorMode.value === 'scrcpy' && wsConnected.value ? 2000 : 200)
}

function buildWsCandidates(sessionId) {
  const path = `/ws/app-automation/recording/${sessionId}/`
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const list = [`${proto}://${window.location.host}${path}`]
  if (window.location.port === '3000' || window.location.port === '5173') {
    list.push(`ws://127.0.0.1:8000${path}`)
    list.push(`ws://localhost:8000${path}`)
  }
  return list
}

function connectWs(sessionId) {
  // 保留 session，清旧连接
  if (wsRetryTimer) {
    clearTimeout(wsRetryTimer)
    wsRetryTimer = null
  }
  if (ws) {
    try {
      ws.onopen = null
      ws.onclose = null
      ws.onerror = null
      ws.onmessage = null
      ws.close()
    } catch (_) { /* ignore */ }
    ws = null
  }
  wsConnected.value = false
  wsFailed.value = false
  wsAttempt = 0
  wsSessionId = sessionId
  openWs(sessionId)
}

function openWs(sessionId) {
  if (wsSessionId !== sessionId) return
  const candidates = buildWsCandidates(sessionId)
  const idx = Math.min(wsAttempt, candidates.length - 1)
  const wsUrl = candidates[idx]
  try {
    ws = new WebSocket(wsUrl)
  } catch (_) {
    scheduleWsRetry(sessionId)
    return
  }
  ws.onopen = () => {
    wsConnected.value = true
    wsFailed.value = false
    wsAttempt = 0
  }
  ws.onclose = () => {
    wsConnected.value = false
    if (wsSessionId === sessionId && session.value?.status === 'recording') {
      scheduleWsRetry(sessionId)
    }
  }
  ws.onerror = () => {
    wsConnected.value = false
  }
  ws.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data)
      if (msg.event === 'h264' && msg.data) {
        mirrorMode.value = 'scrcpy'
        streamReady.value = true
        if (msg.device_width) deviceWidth.value = msg.device_width
        if (msg.device_height) deviceHeight.value = msg.device_height
        feedH264Base64(msg.data)
        streamHint.value = '投屏中（scrcpy 实时）— 可开始点击录制'
        if (pollTimer && pollActive.value) {
          clearInterval(pollTimer)
          pollTimer = setInterval(() => {
            if (!session.value || session.value.status !== 'recording') return
            getAppRecordingFrame(sessionId).then((res) => {
              const data = res.data || {}
              if (Array.isArray(data.steps)) {
                const confirmed = steps.value.filter(s => !s._pending).length
                if (data.steps.length >= confirmed) steps.value = data.steps
              }
              if (data.session_status && data.session_status !== 'recording') {
                session.value = { ...(session.value || {}), status: data.session_status }
              }
            }).catch(() => {})
          }, 3000)
        }
      } else if (msg.event === 'frame' && msg.image) {
        frameUrl.value = msg.image
        streamReady.value = true
        if (msg.mirror_mode) mirrorMode.value = msg.mirror_mode
        if (msg.device_width) deviceWidth.value = msg.device_width
        if (msg.device_height) deviceHeight.value = msg.device_height
      } else if (msg.event === 'mirror_mode') {
        if (msg.mirror_mode) mirrorMode.value = msg.mirror_mode
        if (msg.screen_width) deviceWidth.value = msg.screen_width
        if (msg.screen_height) deviceHeight.value = msg.screen_height
        if (msg.message) streamHint.value = msg.message
        if (msg.mirror_mode === 'scrcpy' && !supportsWebCodecs()) {
          streamHint.value = '已启用 scrcpy，但浏览器不支持 WebCodecs，请用 Chrome/Edge；同时保留截屏兜底'
        }
      } else if (msg.event === 'step_added') {
        steps.value = msg.steps || [...steps.value, msg.step]
      } else if (msg.event === 'status') {
        if (msg.status) session.value = { ...(session.value || {}), status: msg.status }
        if (msg.steps) steps.value = msg.steps
        if (msg.screen_width) deviceWidth.value = msg.screen_width
        if (msg.screen_height) deviceHeight.value = msg.screen_height
        if (msg.mirror_mode) mirrorMode.value = msg.mirror_mode
        if (msg.message) streamHint.value = msg.message
        if (msg.status === 'recording' && (msg.screen_width || msg.message || msg.mirror_mode)) {
          streamReady.value = true
        }
      } else if (msg.event === 'error') {
        streamHint.value = msg.message || '录制错误'
        ElMessage.warning(streamHint.value)
      }
    } catch (_) { /* ignore */ }
  }
}

function scheduleWsRetry(sessionId) {
  if (wsSessionId !== sessionId || session.value?.status !== 'recording') return
  if (wsRetryTimer) clearTimeout(wsRetryTimer)
  wsAttempt += 1
  if (wsAttempt >= 6) wsFailed.value = true
  const delay = Math.min(800 * wsAttempt, 4000)
  wsRetryTimer = setTimeout(() => {
    if (wsSessionId !== sessionId || session.value?.status !== 'recording') return
    if (ws) {
      try { ws.close() } catch (_) { /* ignore */ }
      ws = null
    }
    openWs(sessionId)
  }, delay)
}

async function onQualityChange(val) {
  if (!session.value?.id || !recording.value) return
  try {
    await updateAppRecordingSettings(session.value.id, { stream_quality: val })
    ElMessage.success(`已切换为「${{ balanced: '均衡', clear: '清晰', fast: '流畅' }[val] || val}」`)
  } catch (e) {
    ElMessage.warning(e.response?.data?.error || '清晰度切换失败')
  }
}

async function startRecording() {
  starting.value = true
  startingLabel.value = '正在启动…'
  testCaseId.value = null
  steps.value = []
  frameUrl.value = ''
  streamReady.value = false
  videoReady.value = false
  mirrorMode.value = ''
  resetVideoDecoder()
  streamHint.value = '正在创建录制会话…'
  try {
    const res = await createAppRecordingSession({
      project_id: projectId.value,
      device_id: deviceId.value,
      name: caseName.value || undefined,
      stream_quality: streamQuality.value
    })
    session.value = res.data
    deviceWidth.value = res.data.screen_width || 0
    deviceHeight.value = res.data.screen_height || 0
    streamHint.value = '会话已创建，正在后台启动 scrcpy / 投屏…'
    startPoll(res.data.id)
    connectWs(res.data.id)
    ElMessage.success('录制已开始，后台准备中…')
  } catch (e) {
    const err = e.response?.data?.error || e.message || '启动失败'
    streamHint.value = err
    ElMessage.error(err)
  } finally {
    starting.value = false
    startingLabel.value = '开始录制'
  }
}

async function stopRecording() {
  if (!session.value?.id) return
  stopping.value = true
  try {
    const res = await stopAppRecordingSession(session.value.id, {
      auto_save: true,
      name: caseName.value || undefined
    })
    session.value = res.data?.session || session.value
    const flow = session.value?.ui_flow
    if (Array.isArray(flow)) {
      steps.value = flow
    } else if (flow?.steps) {
      steps.value = flow.steps
    }
    if (res.data?.test_case?.id) {
      testCaseId.value = res.data.test_case.id
      ElMessage.success(`已生成用例 #${testCaseId.value}，可在用例编排中查看并执行`)
    } else {
      ElMessage.warning(res.data?.message || res.data?.save_error || '已停止')
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.error || e.message || '停止失败')
  } finally {
    stopStreaming()
    stopping.value = false
    mirrorMaximized.value = false
  }
}

function openSceneBuilder() {
  if (!testCaseId.value) return
  router.push({ name: 'AppSceneBuilder', query: { case_id: testCaseId.value } })
}

function mapToDevice(clientX, clientY) {
  const el = mirrorWrap.value
  if (!el) return null
  let dw = deviceWidth.value
  let dh = deviceHeight.value
  if (!dw || !dh) return null

  // 优先用正在显示的画面（视频 canvas 或截屏 img），避免隐藏/空白 canvas 干扰
  let target = null
  if (mirrorMode.value === 'scrcpy' && videoReady.value) {
    target = el.querySelector('.mirror-canvas')
  }
  if (!target) {
    target = el.querySelector('img.mirror-img')
  }
  if (!target) {
    target = el.querySelector('.mirror-empty') || el
  }
  const rect = target.getBoundingClientRect()
  const wrapRect = el.getBoundingClientRect()
  if (!rect.width || !rect.height) return null

  // 画面横竖与上报分辨率不一致时（常见于只读了 Physical size），按画面朝向交换宽高
  const bufW = target.width || 0
  const bufH = target.height || 0
  if (bufW > 0 && bufH > 0) {
    const videoLandscape = bufW > bufH
    const deviceLandscape = dw > dh
    if (videoLandscape !== deviceLandscape) {
      const t = dw
      dw = dh
      dh = t
    }
  }

  const x = Math.round(((clientX - rect.left) / rect.width) * dw)
  const y = Math.round(((clientY - rect.top) / rect.height) * dh)
  return {
    x: Math.max(0, Math.min(dw - 1, x)),
    y: Math.max(0, Math.min(dh - 1, y)),
    cx: clientX - wrapRect.left + el.scrollLeft,
    cy: clientY - wrapRect.top + el.scrollTop
  }
}

function sendEvent(payload) {
  if (!session.value?.id) return
  if (payload.type === 'tap' || payload.type === 'click') {
    steps.value = [
      ...steps.value,
      {
        type: 'click',
        name: `录制点击_${steps.value.length + 1}`,
        config: { selector_type: 'pos', selector: [payload.x, payload.y], timeout: 5 },
        _pending: true
      }
    ]
    showTapFlash(payload)
  } else if (payload.type === 'swipe') {
    steps.value = [
      ...steps.value,
      {
        type: 'swipe',
        name: `滑动_${steps.value.length + 1}`,
        config: {
          selector_type: 'pos',
          start: [payload.x1, payload.y1],
          end: [payload.x2, payload.y2],
          duration: 0.18
        },
        _pending: true
      }
    ]
  } else if (payload.type === 'text' || payload.type === 'input') {
    steps.value = [
      ...steps.value,
      {
        type: 'input',
        name: `输入_${steps.value.length + 1}`,
        config: { selector_type: 'pos', selector: '', value: payload.text || '', send_enter: false },
        _pending: true
      }
    ]
  }

  // 手势一律走 HTTP（与录制 worker 同进程更可靠）；投屏视频仍用 WS
  sendAppRecordingEvent(session.value.id, payload).catch((e) => {
    const err = e.response?.data?.error || e.message || '发送手势失败'
    ElMessage.warning(err)
  })
}

function showTapFlash(payload) {
  const el = mirrorWrap.value
  if (!el || payload.x == null || payload.y == null) return
  const img = el.querySelector('.mirror-canvas') || el.querySelector('.mirror-img')
  const rect = (img || el).getBoundingClientRect()
  const wrapRect = el.getBoundingClientRect()
  if (!deviceWidth.value || !deviceHeight.value || !rect.width) return
  const lx = ((payload.x / deviceWidth.value) * rect.width) + (rect.left - wrapRect.left) + el.scrollLeft
  const ly = ((payload.y / deviceHeight.value) * rect.height) + (rect.top - wrapRect.top) + el.scrollTop
  const dot = document.createElement('div')
  dot.className = 'tap-flash'
  dot.style.left = `${lx}px`
  dot.style.top = `${ly}px`
  el.appendChild(dot)
  setTimeout(() => dot.remove(), 350)
}

function onPointerDown(e) {
  if (!canInteract.value) {
    if (recording.value) {
      ElMessage.info(
        !streamReady.value
          ? '请等待投屏就绪后再操作'
          : (!deviceWidth.value || !deviceHeight.value)
            ? '尚未获取设备分辨率，请稍候'
            : '当前不可操作'
      )
    }
    return
  }
  e.preventDefault()
  const pt = mapToDevice(e.clientX, e.clientY)
  if (!pt) {
    ElMessage.warning('无法映射点击坐标，请确认投屏画面已显示')
    return
  }
  pointerStart = pt
  dragging = false
  dragLine.value = null
  e.currentTarget.setPointerCapture?.(e.pointerId)
}

function onPointerMove(e) {
  if (!pointerStart || !canInteract.value) return
  const pt = mapToDevice(e.clientX, e.clientY)
  if (!pt) return
  const dist = Math.hypot(pt.cx - pointerStart.cx, pt.cy - pointerStart.cy)
  if (dist > 12) {
    dragging = true
    dragLine.value = { x1: pointerStart.cx, y1: pointerStart.cy, x2: pt.cx, y2: pt.cy }
  }
}

function onPointerUp(e) {
  if (!pointerStart || !canInteract.value) {
    pointerStart = null
    dragging = false
    dragLine.value = null
    return
  }
  const pt = mapToDevice(e.clientX, e.clientY) || pointerStart
  if (dragging) {
    sendEvent({
      type: 'swipe',
      x1: pointerStart.x,
      y1: pointerStart.y,
      x2: pt.x,
      y2: pt.y,
      duration_ms: 180
    })
  } else {
    sendEvent({ type: 'tap', x: pointerStart.x, y: pointerStart.y })
  }
  pointerStart = null
  dragging = false
  dragLine.value = null
}

function sendText() {
  if (!inputText.value || !canInteract.value) return
  sendEvent({ type: 'text', text: inputText.value })
  inputText.value = ''
}
</script>

<style scoped>
.app-recording-page { padding: 0; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.header-tags { display: flex; gap: 8px; }
.form { margin-bottom: 8px; }
.mirror-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}
.toolbar-label { font-weight: 600; margin-right: 4px; }
.scale-text { color: #909399; font-size: 13px; min-width: 42px; }
.mirror-panel.maximized {
  position: fixed;
  inset: 0;
  z-index: 3000;
  background: #0b0b0b;
  display: flex;
  flex-direction: column;
  padding: 12px;
}
.max-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #ddd;
  margin-bottom: 8px;
}
.max-bar-actions { display: flex; gap: 8px; }
.mirror-wrap {
  position: relative;
  background: #111;
  border-radius: 8px;
  min-height: 520px;
  max-height: 75vh;
  display: block;
  overflow: auto;
  touch-action: none;
  user-select: none;
}
.mirror-panel.maximized .mirror-wrap {
  flex: 1;
  min-height: 0;
  max-height: none;
  border-radius: 0;
}
.mirror-stage {
  display: inline-block;
  min-width: 100%;
  text-align: center;
  padding: 8px 0 24px;
}
.mirror-img {
  max-width: min(100%, 920px);
  max-height: 70vh;
  width: auto;
  height: auto;
  display: inline-block;
  vertical-align: top;
  image-rendering: auto;
  user-select: none;
  pointer-events: none;
}
.mirror-canvas {
  background: #000;
  display: none;
}
.mirror-canvas.is-active {
  display: inline-block;
}
.mirror-panel.maximized .mirror-img {
  max-width: min(100%, 1200px);
  max-height: 85vh;
}
.mirror-empty { color: #888; padding: 80px 40px; }
.drag-line {
  position: absolute;
  height: 2px;
  background: #67c23a;
  transform-origin: 0 50%;
  pointer-events: none;
  z-index: 2;
}
.tap-flash {
  position: absolute;
  width: 18px;
  height: 18px;
  margin-left: -9px;
  margin-top: -9px;
  border-radius: 50%;
  border: 2px solid #67c23a;
  background: rgba(103, 194, 58, 0.35);
  pointer-events: none;
  z-index: 3;
  animation: tap-flash-pop 0.35s ease-out forwards;
}
@keyframes tap-flash-pop {
  from { transform: scale(0.4); opacity: 1; }
  to { transform: scale(1.8); opacity: 0; }
}
.input-row { display: flex; gap: 8px; margin-top: 10px; }
.steps-title {
  font-weight: 600;
  margin-bottom: 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.step-item {
  padding: 8px 10px;
  border-bottom: 1px solid #eee;
  font-size: 13px;
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}
.step-item .act { color: #409eff; font-family: monospace; }
.step-item .elid { color: #67c23a; }
.step-item .val { color: #909399; max-width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.empty-steps { color: #999; padding: 24px; text-align: center; }
.script-json {
  margin: 0;
  padding: 12px;
  background: #1e1e1e;
  color: #d4d4d4;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
