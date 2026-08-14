<template>
  <el-drawer v-model="visible" title="失败诊断 / 自愈" size="520px" @close="emit('update:modelValue', false)">
    <div v-if="loading" class="loading">诊断中...</div>
    <div v-else-if="diagnosis">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="分类">
          {{ diagnosis.category_display || diagnosis.category }}
        </el-descriptions-item>
        <el-descriptions-item label="置信度">
          {{ (diagnosis.confidence * 100).toFixed(0) }}%
        </el-descriptions-item>
        <el-descriptions-item label="摘要">
          {{ diagnosis.summary }}
        </el-descriptions-item>
        <el-descriptions-item v-if="contextMeta.element_id" label="失败元素">
          #{{ contextMeta.element_id }}
          <span v-if="contextMeta.element_name"> · {{ contextMeta.element_name }}</span>
        </el-descriptions-item>
        <el-descriptions-item v-if="contextMeta.step_id" label="失败步骤">
          #{{ contextMeta.step_id }}
          <span v-if="contextMeta.failed_step?.step_number">（步骤 {{ contextMeta.failed_step.step_number }}）</span>
        </el-descriptions-item>
      </el-descriptions>

      <div v-if="allCandidates.length" class="candidates">
        <h4>候选定位器</h4>
        <el-radio-group v-model="selectedLocatorKey" class="candidate-list">
          <el-radio
            v-for="c in allCandidates"
            :key="locatorKey(c)"
            :value="locatorKey(c)"
            class="candidate-item"
          >
            <el-tag size="small" type="info">{{ c.source || 'candidate' }}</el-tag>
            <code>{{ c.strategy }}={{ c.value }}</code>
            <span v-if="c.label" class="label">{{ c.label }}</span>
          </el-radio>
        </el-radio-group>
      </div>

      <h4 style="margin-top: 16px">修复提案</h4>
      <el-card v-for="p in proposals" :key="p.id" shadow="never" class="proposal">
        <div class="proposal-title">
          <el-tag size="small">{{ p.target_display || p.target }}</el-tag>
          <el-tag size="small" type="info">{{ p.status_display || p.status }}</el-tag>
          <el-tag
            v-if="p.verify_status"
            size="small"
            :type="p.verify_status === 'failed' ? 'danger' : (p.verify_status === 'passed' ? 'success' : 'info')"
          >
            验证: {{ p.verify_status_display || p.verify_status }}
          </el-tag>
          <span>{{ p.title }}</span>
        </div>
        <pre class="diff">{{ p.diff || JSON.stringify(p.patch_payload, null, 2) }}</pre>
        <div class="actions">
          <el-button
            v-if="p.target === 'test_asset' && p.status !== 'applied' && p.status !== 'rolled_back'"
            type="primary"
            size="small"
            :loading="applying === p.id"
            @click="applyFix(p)"
          >
            应用测试修复
          </el-button>
          <el-button
            v-if="p.target === 'test_asset' && p.status === 'applied'"
            type="danger"
            size="small"
            plain
            :loading="rolling === p.id"
            @click="rollbackFix(p)"
          >
            回滚
          </el-button>
          <el-tag v-if="p.verify_status === 'failed'" type="danger" size="small">建议回滚</el-tag>
          <el-button
            v-if="p.target === 'product_code' && p.status === 'proposed'"
            type="success"
            size="small"
            @click="approve(p)"
          >
            批准补丁（不自动改仓）
          </el-button>
          <el-button
            v-if="p.status === 'proposed'"
            size="small"
            @click="reject(p)"
          >
            拒绝
          </el-button>
          <el-button
            v-if="p.target === 'product_code'"
            type="warning"
            size="small"
            @click="createDefect"
          >
            创建缺陷
          </el-button>
        </div>
      </el-card>
    </div>
    <el-empty v-else description="暂无诊断结果" />
  </el-drawer>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  applyScriptFix,
  approveFixProposal,
  createDefectFromDiagnosis,
  rejectFixProposal,
  rollbackScriptFix
} from '@/api/ui_automation'

const props = defineProps({
  modelValue: Boolean,
  diagnosis: { type: Object, default: null },
  proposals: { type: Array, default: () => [] },
  loading: Boolean
})
const emit = defineEmits(['update:modelValue', 'refresh'])

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v)
})
const applying = ref(null)
const rolling = ref(null)
const selectedLocatorKey = ref('')

const contextMeta = computed(() => {
  const evidence = props.diagnosis?.evidence || {}
  return evidence.context || {}
})

const allCandidates = computed(() => {
  const fromCtx = contextMeta.value.candidate_locators || []
  const fromProposals = []
  for (const p of props.proposals || []) {
    const cands = p.patch_payload?.candidate_locators || []
    fromProposals.push(...cands)
    const loc = p.patch_payload?.locator
    if (loc?.value) {
      fromProposals.push({ ...loc, source: loc.source || 'proposal', label: '提案定位器' })
    }
  }
  const merged = [...fromCtx, ...fromProposals]
  const seen = new Set()
  return merged.filter((c) => {
    if (!c?.value) return false
    const k = locatorKey(c)
    if (seen.has(k)) return false
    seen.add(k)
    return true
  })
})

function locatorKey(c) {
  return `${(c.strategy || 'css').toLowerCase()}::${c.value}`
}

function parseSelectedLocator() {
  if (!selectedLocatorKey.value) return null
  const [strategy, ...rest] = selectedLocatorKey.value.split('::')
  const value = rest.join('::')
  if (!value) return null
  return { strategy: strategy || 'css', value }
}

watch(allCandidates, (list) => {
  if (!list.length) {
    selectedLocatorKey.value = ''
    return
  }
  const preferred =
    list.find((c) => c.source === 'llm') ||
    list.find((c) => c.source === 'action_trace') ||
    list.find((c) => c.source === 'backup') ||
    list[0]
  selectedLocatorKey.value = locatorKey(preferred)
}, { immediate: true })

async function applyFix(p) {
  applying.value = p.id
  try {
    const body = { proposal_id: p.id }
    const selected = parseSelectedLocator()
    const fixType = p.patch_payload?.type
    if (selected && (!fixType || fixType === 'update_locator' || fixType === 'add_backup_locator')) {
      body.locator = selected
    }
    if (contextMeta.value.element_id) body.element_id = contextMeta.value.element_id
    if (contextMeta.value.step_id) body.step_id = contextMeta.value.step_id
    await applyScriptFix(props.diagnosis.id, body)
    ElMessage.success('测试侧修复已应用（若开启验证将自动重跑）')
    emit('refresh')
  } catch (e) {
    ElMessage.error(e.response?.data?.error || e.message || '应用失败')
  } finally {
    applying.value = null
  }
}

async function rollbackFix(p) {
  rolling.value = p.id
  try {
    await rollbackScriptFix(props.diagnosis.id, { proposal_id: p.id })
    ElMessage.success('已回滚到应用前快照')
    emit('refresh')
  } catch (e) {
    ElMessage.error(e.response?.data?.error || e.message || '回滚失败')
  } finally {
    rolling.value = null
  }
}

async function approve(p) {
  await approveFixProposal(p.id)
  ElMessage.success('已批准（业务代码补丁不会自动写入仓库）')
  emit('refresh')
}

async function reject(p) {
  await rejectFixProposal(p.id)
  ElMessage.info('已拒绝')
  emit('refresh')
}

async function createDefect() {
  try {
    const { value } = await ElMessageBox.prompt(
      '请输入手工测试项目 projects.Project 的 ID（与 UI 项目不同）',
      '创建缺陷',
      { inputPattern: /^\d+$/, inputErrorMessage: '请输入数字 ID' }
    )
    const res = await createDefectFromDiagnosis(props.diagnosis.id, { project_id: Number(value) })
    ElMessage.success(`缺陷已创建 #${res.data.defect_id || res.data.code}`)
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error(e.response?.data?.error || e.message || '创建失败')
    }
  }
}
</script>

<style scoped>
.loading { padding: 24px; color: #909399; }
.proposal { margin-bottom: 12px; }
.proposal-title { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
.diff {
  background: #f5f7fa;
  padding: 8px;
  max-height: 180px;
  overflow: auto;
  font-size: 12px;
}
.actions { margin-top: 8px; display: flex; gap: 8px; flex-wrap: wrap; }
.candidates { margin-top: 16px; }
.candidate-list { display: flex; flex-direction: column; align-items: flex-start; gap: 8px; width: 100%; }
.candidate-item { height: auto; margin-right: 0; white-space: normal; align-items: flex-start; }
.candidate-item code { margin-left: 6px; font-size: 12px; word-break: break-all; }
.candidate-item .label { margin-left: 6px; color: #909399; font-size: 12px; }
</style>
