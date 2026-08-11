<template>
  <div class="element-management">
    <el-card>
      <!-- 顶部操作栏 -->
      <template #header>
        <div class="header-actions">
          <el-space wrap>
            <!-- 项目筛选 -->
            <el-select v-model="projectFilter" :placeholder="$t('appAutomation.element.allProjects')" clearable filterable style="width: 160px" @change="handleSearch">
              <el-option v-for="p in projectList" :key="p.id" :label="p.name" :value="p.id" />
            </el-select>

            <!-- 类型切换 -->
            <el-radio-group v-model="typeFilter" @change="loadElements">
              <el-radio-button value="">{{ $t('appAutomation.common.all') }}</el-radio-button>
              <el-radio-button value="image">{{ $t('appAutomation.element.types.image') }}</el-radio-button>
              <el-radio-button value="pos">{{ $t('appAutomation.element.types.pos') }}</el-radio-button>
              <el-radio-button value="region">{{ $t('appAutomation.element.types.region') }}</el-radio-button>
            </el-radio-group>

            <!-- 搜索 -->
            <el-input
              v-model="searchQuery"
              :placeholder="$t('appAutomation.element.searchPlaceholder')"
              style="width: 250px"
              clearable
              @clear="handleSearch"
              @keyup.enter="handleSearch"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
              <template #suffix>
                <el-button
                  v-if="searchQuery"
                  type="primary"
                  link
                  :icon="Search"
                  @click="handleSearch"
                  style="padding: 0"
                />
              </template>
            </el-input>
          </el-space>
          
          <!-- 操作按钮 -->
          <el-space>
            <el-button type="success" @click="showCaptureDialog">
              <el-icon><Camera /></el-icon>
              {{ $t('appAutomation.element.createFromDevice') }}
            </el-button>
            <el-button type="primary" @click="showCreateDialog">
              <el-icon><Plus /></el-icon>
              {{ $t('appAutomation.element.createManually') }}
            </el-button>
          </el-space>
        </div>
      </template>
    
      <!-- 元素列表 -->
      <el-table
        :data="elements"
        border
        v-loading="loading"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="55" />
        
        <el-table-column prop="name" :label="$t('appAutomation.element.elementName')" width="200" fixed="left">
          <template #default="{ row }">
            <el-link type="primary" @click="handleView(row)">
              {{ row.name }}
            </el-link>
          </template>
        </el-table-column>

        <el-table-column prop="element_type" :label="$t('appAutomation.element.type')" width="100">
          <template #default="{ row }">
            <el-tag :type="getTypeColor(row.element_type)">
              {{ getTypeName(row.element_type) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column :label="$t('appAutomation.element.imageCategory')" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.element_type === 'image' && row.config?.image_category" type="info" size="small">
              {{ row.config.image_category }}
            </el-tag>
            <span v-else style="color: #909399;">-</span>
          </template>
        </el-table-column>

        <el-table-column prop="tags" :label="$t('appAutomation.element.tags')" width="200">
          <template #default="{ row }">
            <el-tag
              v-for="tag in row.tags"
              :key="tag"
              size="small"
              style="margin-right: 5px"
            >
              {{ tag }}
            </el-tag>
          </template>
        </el-table-column>
        
        <!-- 预览 -->
        <el-table-column :label="$t('appAutomation.element.preview')" width="200" align="center">
          <template #default="{ row }">
            <!-- 图片类型 -->
            <div v-if="row.element_type === 'image'" class="preview-image">
              <el-image
                :src="getImageUrl(row)"
                fit="contain"
                style="width: 150px; height: 80px; cursor: pointer"
                :preview-src-list="[getImageUrl(row)]"
                preview-teleported
              />
            </div>
            
            <!-- 坐标类型 -->
            <div v-else-if="row.element_type === 'pos'" class="preview-pos">
              <el-space :size="4">
                <el-tag type="primary" size="small">X: {{ row.config?.x }}</el-tag>
                <el-tag type="primary" size="small">Y: {{ row.config?.y }}</el-tag>
              </el-space>
            </div>
            
            <!-- 区域类型 -->
            <div v-else-if="row.element_type === 'region'" class="preview-region">
              <el-space direction="vertical" :size="4">
                <el-space :size="4">
                  <el-tag type="success" size="small">X1: {{ row.config?.x1 }}</el-tag>
                  <el-tag type="success" size="small">Y1: {{ row.config?.y1 }}</el-tag>
                </el-space>
                <el-space :size="4">
                  <el-tag type="warning" size="small">X2: {{ row.config?.x2 }}</el-tag>
                  <el-tag type="warning" size="small">Y2: {{ row.config?.y2 }}</el-tag>
                </el-space>
              </el-space>
            </div>
          </template>
        </el-table-column>
        
        <el-table-column prop="usage_count" :label="$t('appAutomation.element.usageCount')" width="100" sortable />

        <el-table-column prop="created_at" :label="$t('appAutomation.common.createTime')" width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.created_at) }}
          </template>
        </el-table-column>

        <el-table-column :label="$t('appAutomation.common.operation')" width="200" fixed="right">
          <template #default="{ row }">
            <div class="table-actions">
              <el-button link type="primary" size="small" @click="handleEdit(row)">
                {{ $t('appAutomation.common.edit') }}
              </el-button>
              <el-button link size="small" @click="handleDuplicate(row)">
                {{ $t('appAutomation.element.copy') }}
              </el-button>
              <el-button link type="danger" size="small" @click="handleDelete(row)">
                {{ $t('appAutomation.common.delete') }}
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
      
      <!-- 批量操作栏 -->
      <div v-if="selectedElements.length > 0" class="batch-actions">
        <el-space>
          <span>{{ $t('appAutomation.element.selectedCount', { count: selectedElements.length }) }}</span>
          <el-button type="danger" size="small" @click="handleBatchDelete">
            {{ $t('appAutomation.common.batchDelete') }}
          </el-button>
        </el-space>
      </div>
      
      <!-- 分页 -->
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @current-change="loadElements"
        @size-change="loadElements"
        style="margin-top: 20px; justify-content: flex-end"
      />
    </el-card>

    <!-- 从设备截图创建对话框 -->
    <CaptureElementDialog
      v-model="captureDialogVisible"
      :project-list="projectList"
      @success="handleCreateSuccess"
    />

    <!-- 手动创建/编辑对话框 -->
    <ManualElementDialog
      v-model="dialogVisible"
      :edit-data="editElement"
      :project-list="projectList"
      @success="handleCreateSuccess"
    />

    <!-- 查看详情对话框 -->
    <el-dialog
      v-model="detailDialogVisible"
      :title="$t('appAutomation.element.elementDetail')"
      width="800px"
    >
      <el-descriptions :column="2" border v-if="viewingElement">
        <el-descriptions-item :label="$t('appAutomation.element.elementName')">{{ viewingElement.name }}</el-descriptions-item>
        <el-descriptions-item :label="$t('appAutomation.element.elementType')">
          <el-tag :type="getTypeColor(viewingElement.element_type)">
            {{ getTypeName(viewingElement.element_type) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item :label="$t('appAutomation.element.tags')" :span="2">
          <el-tag v-for="tag in viewingElement.tags" :key="tag" size="small" style="margin-right: 5px">
            {{ tag }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item :label="$t('appAutomation.element.configInfo')" :span="2">
          <pre style="margin: 0; padding: 10px; background: #f5f7fa; border-radius: 4px;">{{ JSON.stringify(viewingElement.config, null, 2) }}</pre>
        </el-descriptions-item>
        <el-descriptions-item :label="$t('appAutomation.element.usageCount')">{{ viewingElement.usage_count || 0 }}</el-descriptions-item>
        <el-descriptions-item :label="$t('appAutomation.common.createTime')">{{ formatDateTime(viewingElement.created_at) }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getAppElementList,
  createAppElement,
  deleteAppElement as apiDeleteAppElement,
  getAppProjects
} from '@/api/app-automation'
import { Search, Plus, Camera } from '@element-plus/icons-vue'
import { formatDateTime } from '@/utils/app-automation-helpers'
import { useI18n } from 'vue-i18n'
import CaptureElementDialog from './components/CaptureElementDialog.vue'
import ManualElementDialog from './components/ManualElementDialog.vue'

const { t } = useI18n()

// 状态
const loading = ref(false)
const elements = ref([])
const selectedElements = ref([])

// 筛选条件
const searchQuery = ref('')
const typeFilter = ref('')
const projectFilter = ref(null)
const projectList = ref([])
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)

// 对话框
const dialogVisible = ref(false)
const captureDialogVisible = ref(false)
const detailDialogVisible = ref(false)
const editElement = ref(null)
const viewingElement = ref(null)

const loadElements = async () => {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value,
      element_type: typeFilter.value
    }
    if (projectFilter.value) params.project = projectFilter.value
    
    // 只有搜索关键词不为空时才添加 search 参数
    if (searchQuery.value && searchQuery.value.trim()) {
      params.search = searchQuery.value.trim()
    }
    
    const res = await getAppElementList(params)
    elements.value = res.data.results || []
    total.value = res.data.count || 0
  } catch (error) {
    ElMessage.error(t('appAutomation.element.messages.loadFailed') + ': ' + (error.message || t('appAutomation.element.messages.unknownError')))
  } finally {
    loading.value = false
  }
}

// 搜索处理
const handleSearch = () => {
  currentPage.value = 1  // 搜索时重置到第一页
  loadElements()
}

// 对话框操作
const showCreateDialog = () => {
  editElement.value = null
  dialogVisible.value = true
}

const showCaptureDialog = () => {
  captureDialogVisible.value = true
}

const handleView = (element) => {
  viewingElement.value = element
  detailDialogVisible.value = true
}

const handleEdit = (element) => {
  editElement.value = element
  dialogVisible.value = true
}

// 智能生成唯一的副本名称
const findAvailableName = (baseName) => {
  const copySuffix = t('appAutomation.element.copySuffix')
  // 先尝试 "原名_副本"
  const firstCandidate = `${baseName}${copySuffix}`
  if (!elements.value.some(el => el.name === firstCandidate)) {
    return firstCandidate
  }

  // 查找 "原名_副本(n)" 中的最大 n
  const escapedSuffix = copySuffix.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const pattern = new RegExp(`^${baseName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}${escapedSuffix}\\((\\d+)\\)$`)
  let maxNum = 1

  elements.value.forEach(el => {
    const match = el.name.match(pattern)
    if (match) {
      const num = parseInt(match[1])
      if (num > maxNum) {
        maxNum = num
      }
    }
  })

  return `${baseName}${copySuffix}(${maxNum + 1})`
}

const handleDuplicate = async (element) => {
  try {
    // 智能生成唯一名称
    const newName = findAvailableName(element.name)
    
    // 复制配置，移除 file_hash（避免重复检测）
    const newConfig = { ...element.config }
    delete newConfig.file_hash  // 允许多个元素共享同一图片
    
    // 复制元素数据
    const duplicateData = {
      ...element,
      name: newName,
      id: undefined,
      created_at: undefined,
      updated_at: undefined,
      created_by: undefined,
      created_by_id: undefined,
      last_used_at: undefined,
      usage_count: 0,
      config: newConfig  // 使用清理后的配置
    }
    
    await createAppElement(duplicateData)
    ElMessage.success(t('appAutomation.element.messages.copiedAs', { name: newName }))
    loadElements()
  } catch (error) {
    console.error('复制失败:', error)
    const errorMsg = error.response?.data?.config?.[0] ||
                     error.response?.data?.name?.[0] ||
                     error.response?.data?.message ||
                     t('appAutomation.element.messages.copyFailed')
    ElMessage.error(errorMsg)
  }
}

const handleCreateSuccess = () => {
  loadElements()
}

const handleSelectionChange = (selection) => {
  selectedElements.value = selection
}

const handleBatchDelete = async () => {
  try {
    await ElMessageBox.confirm(
      t('appAutomation.element.messages.batchDeleteConfirm', { count: selectedElements.value.length }),
      t('appAutomation.element.messages.batchDeleteTitle'),
      {
        confirmButtonText: t('appAutomation.common.confirm'),
        cancelButtonText: t('appAutomation.common.cancel'),
        type: 'warning'
      }
    )

    for (const element of selectedElements.value) {
      await apiDeleteAppElement(element.id)
    }

    ElMessage.success(t('appAutomation.element.messages.batchDeleteSuccess'))
    selectedElements.value = []
    loadElements()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('批量删除失败:', error)
      ElMessage.error(t('appAutomation.element.messages.batchDeleteFailed'))
    }
  }
}

const handleDelete = async (element) => {
  try {
    await ElMessageBox.confirm(
      t('appAutomation.element.messages.deleteConfirm', { name: element.name }),
      t('appAutomation.common.confirmDelete'),
      {
        confirmButtonText: t('appAutomation.common.confirm'),
        cancelButtonText: t('appAutomation.common.cancel'),
        type: 'warning'
      }
    )

    await apiDeleteAppElement(element.id)
    ElMessage.success(t('appAutomation.common.deleteSuccess'))
    loadElements()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除失败:', error)
      ElMessage.error(t('appAutomation.common.deleteFailed'))
    }
  }
}

// 获取图片URL
const getImageUrl = (element) => {
  if (!element?.id) return ''
  // 使用 updated_at 作为版本号，确保图片更新后能刷新
  const timestamp = element.updated_at ? new Date(element.updated_at).getTime() : Date.now()
  return `/api/app-automation/elements/${element.id}/preview/?t=${timestamp}`
}

const getTypeColor = (type) => {
  const colorMap = {
    'image': 'primary',
    'pos': 'success',
    'region': 'warning'
  }
  return colorMap[type] || 'info'
}

const getTypeName = (type) => {
  const nameKey = {
    'image': 'image',
    'pos': 'pos',
    'region': 'region'
  }[type]
  return nameKey ? t(`appAutomation.element.types.${nameKey}`) : type
}

// formatDateTime 已从 app-automation-helpers 导入

onMounted(() => {
  getAppProjects({ page_size: 100 }).then(res => { projectList.value = res.data.results || res.data || [] }).catch(() => {})
  loadElements()
})
</script>

<style scoped lang="scss">
.element-management {
  padding: 20px;
  
  .header-actions {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
  }
  
  .preview-image {
    padding: 5px;
    
    :deep(.el-image) {
      border: 1px solid #e4e7ed;
      border-radius: 4px;
      overflow: hidden;
      
      &:hover {
        border-color: #409eff;
      }
    }
  }
  
  .preview-pos,
  .preview-region {
    display: flex;
    justify-content: center;
  }
  
  .batch-actions {
    margin-top: 15px;
    padding: 10px;
    background: #ecf5ff;
    border: 1px solid #b3d8ff;
    border-radius: 4px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    
    span {
      color: #409eff;
      font-weight: 500;
    }
  }
  
  :deep(.el-table) {
    .el-link {
      font-weight: 500;
    }
  }
  
  :deep(.el-pagination) {
    display: flex;
  }
  
  :deep(pre) {
    font-family: 'Courier New', Courier, monospace;
    font-size: 13px;
    line-height: 1.5;
  }
}
</style>
