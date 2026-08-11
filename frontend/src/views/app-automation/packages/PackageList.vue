<template>
  <div class="app-package-list">
    <div class="page-header">
      <h3>{{ $t('appAutomation.packages.title') }}</h3>
      <div class="header-actions">
        <el-button :icon="Refresh" :loading="loading" @click="loadPackages">
          {{ $t('appAutomation.common.refresh') }}
        </el-button>
        <el-button type="primary" :icon="Plus" @click="openCreateDialog">
          {{ $t('appAutomation.packages.newPackage') }}
        </el-button>
      </div>
    </div>

    <el-table
      v-loading="loading"
      :data="packages"
      style="width: 100%; margin-top: 16px"
      :empty-text="$t('appAutomation.packages.noPackages')"
    >
      <el-table-column prop="name" :label="$t('appAutomation.packages.appName')" min-width="180" />
      <el-table-column prop="package_name" :label="$t('appAutomation.packages.packageName')" min-width="220" />
      <el-table-column prop="created_by_name" :label="$t('appAutomation.packages.creator')" width="120">
        <template #default="{ row }">
          {{ row.created_by_name || '-' }}
        </template>
      </el-table-column>
      <el-table-column :label="$t('appAutomation.common.createTime')" width="180">
        <template #default="{ row }">
          {{ formatDateTime(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column :label="$t('appAutomation.common.updateTime')" width="180">
        <template #default="{ row }">
          {{ formatDateTime(row.updated_at) }}
        </template>
      </el-table-column>
      <el-table-column :label="$t('appAutomation.common.operation')" width="130" fixed="right">
        <template #default="{ row }">
          <div class="table-actions">
            <el-button link type="primary" size="small" @click="openEditDialog(row)">
              {{ $t('appAutomation.common.edit') }}
            </el-button>
            <el-button link type="danger" size="small" @click="handleDelete(row)">
              {{ $t('appAutomation.common.delete') }}
            </el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-show="total > 0"
      v-model:current-page="currentPage"
      v-model:page-size="pageSize"
      :total="total"
      :page-sizes="[10, 20, 50, 100]"
      layout="total, sizes, prev, pager, next, jumper"
      style="margin-top: 16px; text-align: right"
      @size-change="loadPackages"
      @current-change="loadPackages"
    />

    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="100px"
      >
        <el-form-item :label="$t('appAutomation.packages.appName')" prop="name">
          <el-input v-model="form.name" :placeholder="$t('appAutomation.packages.appNamePlaceholder')" />
        </el-form-item>
        <el-form-item :label="$t('appAutomation.packages.packageName')" prop="package_name">
          <el-input v-model="form.package_name" :placeholder="$t('appAutomation.packages.packageNamePlaceholder')" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">{{ $t('appAutomation.common.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="submitForm">
          {{ $t('appAutomation.common.save') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { Plus, Refresh } from '@element-plus/icons-vue'
import {
  getPackageList,
  createPackage,
  updatePackage,
  deletePackage
} from '@/api/app-automation'
import { formatDateTime } from '@/utils/app-automation-helpers'

const { t } = useI18n()

const loading = ref(false)
const saving = ref(false)
const packages = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)

const dialogVisible = ref(false)
const isEditing = ref(false)
const dialogTitle = computed(() =>
  isEditing.value ? t('appAutomation.packages.editPackage') : t('appAutomation.packages.newPackage')
)
const formRef = ref(null)
const form = reactive({
  id: null,
  name: '',
  package_name: ''
})

const rules = computed(() => ({
  name: [{ required: true, message: t('appAutomation.packages.rules.appNameRequired'), trigger: 'blur' }],
  package_name: [{ required: true, message: t('appAutomation.packages.rules.packageNameRequired'), trigger: 'blur' }]
}))

const loadPackages = async () => {
  loading.value = true
  try {
    const res = await getPackageList({
      page: currentPage.value,
      page_size: pageSize.value
    })
    const data = res.data
    const payload = data.success !== undefined ? data.data : data
    packages.value = payload?.results || payload || []
    total.value = payload?.count || packages.value.length || 0
  } catch (error) {
    console.error('加载应用包名失败:', error)
    packages.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

const resetForm = () => {
  form.id = null
  form.name = ''
  form.package_name = ''
  formRef.value?.clearValidate()
}

const openCreateDialog = () => {
  isEditing.value = false
  resetForm()
  dialogVisible.value = true
}

const openEditDialog = (row) => {
  isEditing.value = true
  form.id = row.id
  form.name = row.name
  form.package_name = row.package_name
  dialogVisible.value = true
}

const submitForm = () => {
  formRef.value?.validate(async (valid) => {
    if (!valid) return
    saving.value = true
    try {
      if (isEditing.value && form.id) {
        await updatePackage(form.id, {
          name: form.name,
          package_name: form.package_name
        })
        ElMessage.success(t('appAutomation.common.updateSuccess'))
      } else {
        await createPackage({
          name: form.name,
          package_name: form.package_name
        })
        ElMessage.success(t('appAutomation.common.createSuccess'))
      }
      dialogVisible.value = false
      loadPackages()
    } catch (error) {
      console.error('保存应用包名失败:', error)
      ElMessage.error(error?.response?.data?.detail || t('appAutomation.common.saveFailed'))
    } finally {
      saving.value = false
    }
  })
}

const handleDelete = (row) => {
  ElMessageBox.confirm(
    t('appAutomation.packages.messages.deleteConfirm', { name: row.name }),
    t('appAutomation.packages.messages.deleteConfirmTitle'),
    { type: 'warning' }
  ).then(async () => {
    try {
      await deletePackage(row.id)
      ElMessage.success(t('appAutomation.common.deleteSuccess'))
      loadPackages()
    } catch (error) {
      console.error('删除应用包名失败:', error)
      ElMessage.error(error?.response?.data?.detail || t('appAutomation.common.deleteFailed'))
    }
  }).catch(() => {})
}

// formatDateTime 已从 app-automation-helpers 导入

onMounted(() => {
  loadPackages()
})
</script>

<style scoped lang="scss">
.app-package-list {
  padding: 20px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-actions {
  display: flex;
  gap: 10px;
}
</style>
