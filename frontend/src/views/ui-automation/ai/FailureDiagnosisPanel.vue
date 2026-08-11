<template>
  <el-drawer v-model="visible" title="失败诊断 / 自愈" size="480px" @close="emit('update:modelValue', false)">
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
      </el-descriptions>

      <h4 style="margin-top: 16px">修复提案</h4>
      <el-card v-for="p in proposals" :key="p.id" shadow="never" class="proposal">
        <div class="proposal-title">
          <el-tag size="small">{{ p.target_display || p.target }}</el-tag>
          <el-tag size="small" type="info">{{ p.status_display || p.status }}</el-tag>
          <span>{{ p.title }}</span>
        </div>
        <pre class="diff">{{ p.diff || JSON.stringify(p.patch_payload, null, 2) }}</pre>
        <div class="actions">
          <el-button
            v-if="p.target === 'test_asset' && p.status !== 'applied'"
            type="primary"
            size="small"
            :loading="applying === p.id"
            @click="applyFix(p)"
          >
            应用测试修复
          </el-button>
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
  rejectFixProposal
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

async function applyFix(p) {
  applying.value = p.id
  try {
    await applyScriptFix(props.diagnosis.id, { proposal_id: p.id })
    ElMessage.success('测试侧修复已应用')
    emit('refresh')
  } catch (e) {
    ElMessage.error(e.response?.data?.error || e.message || '应用失败')
  } finally {
    applying.value = null
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

watch(() => props.modelValue, () => {})
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
</style>
