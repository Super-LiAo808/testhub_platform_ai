<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">{{ $t('uiAutomation.project.title') }}</h1>
      <el-button type="primary" @click="showCreateDialog = true">
        <el-icon><Plus /></el-icon>
        {{ $t('uiAutomation.project.newProject') }}
      </el-button>
    </div>
    
    <div class="card-container">
      <div class="filter-bar">
        <el-row :gutter="20">
          <el-col :span="6">
            <el-input
              v-model="searchText"
              :placeholder="$t('uiAutomation.project.searchPlaceholder')"
              clearable
              @input="handleSearch"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
          </el-col>
          <el-col :span="4">
            <el-select v-model="statusFilter" :placeholder="$t('uiAutomation.project.statusFilter')" clearable @change="handleFilter">
              <el-option :label="$t('uiAutomation.status.notStarted')" value="NOT_STARTED" />
              <el-option :label="$t('uiAutomation.status.inProgress')" value="IN_PROGRESS" />
              <el-option :label="$t('uiAutomation.status.completed')" value="COMPLETED" />
            </el-select>
          </el-col>
        </el-row>
      </div>
      
      <el-table :data="projects" v-loading="loading" style="width: 100%">
        <el-table-column prop="name" :label="$t('uiAutomation.project.projectName')" min-width="200">
          <template #default="{ row }">
            <el-link @click="goToProjectDetail(row.id)" type="primary">
              {{ row.name }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column prop="description" :label="$t('uiAutomation.common.description')" min-width="300" show-overflow-tooltip />
        <el-table-column prop="status" :label="$t('uiAutomation.common.status')" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ getStatusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="base_url" :label="$t('uiAutomation.project.baseUrl')" min-width="200" show-overflow-tooltip />
        <el-table-column prop="owner.username" :label="$t('uiAutomation.project.owner')" width="100" />
        <el-table-column prop="created_at" :label="$t('uiAutomation.common.createTime')" width="180" :formatter="formatDate" />
        <el-table-column prop="updated_at" :label="$t('uiAutomation.common.updateTime')" width="180" :formatter="formatDate" />
        <el-table-column :label="$t('uiAutomation.common.operation')" width="200" fixed="right">
          <template #default="{ row }">
            <div class="table-actions">
              <el-button link type="primary" size="small" @click="goToProjectDetail(row.id)">
                <el-icon><View /></el-icon>
                {{ $t('uiAutomation.common.view') }}
              </el-button>
              <el-button link type="primary" size="small" @click="editProject(row)">
                <el-icon><Edit /></el-icon>
                {{ $t('uiAutomation.common.edit') }}
              </el-button>
              <el-button link type="danger" size="small" @click="deleteProject(row.id)">
                <el-icon><Delete /></el-icon>
                {{ $t('uiAutomation.common.delete') }}
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
      
      <div class="pagination-container">
        <el-pagination
          v-model:current-page="pagination.currentPage"
          v-model:page-size="pagination.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          :total="total"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </div>
    
    <!-- 创建项目对话框 -->
    <el-dialog v-model="showCreateDialog" :title="$t('uiAutomation.project.createProject')" width="500px" :close-on-click-modal="false">
      <el-form ref="createFormRef" :model="createForm" :rules="formRules" label-width="80px">
        <el-form-item :label="$t('uiAutomation.project.projectName')" prop="name">
          <el-input v-model="createForm.name" :placeholder="$t('uiAutomation.project.rules.nameRequired')" />
        </el-form-item>
        <el-form-item :label="$t('uiAutomation.project.projectDesc')" prop="description">
          <el-input v-model="createForm.description" type="textarea" :placeholder="$t('uiAutomation.project.projectDesc')" />
        </el-form-item>
        <el-form-item :label="$t('uiAutomation.common.status')" prop="status">
          <el-select v-model="createForm.status" :placeholder="$t('uiAutomation.project.rules.selectStatus')">
            <el-option :label="$t('uiAutomation.status.notStarted')" value="NOT_STARTED" />
            <el-option :label="$t('uiAutomation.status.inProgress')" value="IN_PROGRESS" />
            <el-option :label="$t('uiAutomation.status.completed')" value="COMPLETED" />
          </el-select>
        </el-form-item>
        <el-form-item label="基础URL" prop="base_url">
          <el-input 
            v-model="createForm.base_url" 
            placeholder="请输入基础URL（如：https://www.example.com）"
          >
            <template #prepend>
              <el-select v-model="urlProtocol" placeholder="协议" style="width: 100px">
                <el-option label="https://" value="https://" />
                <el-option label="http://" value="http://" />
              </el-select>
            </template>
          </el-input>
          <div style="color: #909399; font-size: 12px; margin-top: 4px;">
            提示：请输入完整的URL地址，包含协议（http:// 或 https://）
          </div>
        </el-form-item>
        <el-form-item :label="$t('uiAutomation.project.startDate')" prop="start_date">
          <el-date-picker v-model="createForm.start_date" type="date" :placeholder="$t('uiAutomation.project.selectDate')" />
        </el-form-item>
        <el-form-item :label="$t('uiAutomation.project.endDate')" prop="end_date">
          <el-date-picker v-model="createForm.end_date" type="date" :placeholder="$t('uiAutomation.project.selectDate')" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showCreateDialog = false">{{ $t('uiAutomation.common.cancel') }}</el-button>
          <el-button type="primary" @click="handleCreate">{{ $t('uiAutomation.common.confirm') }}</el-button>
        </span>
      </template>
    </el-dialog>
    
    <!-- 编辑项目对话框 -->
    <el-dialog v-model="showEditDialog" :title="$t('uiAutomation.project.editProject')" width="500px" :close-on-click-modal="false">
      <el-form ref="editFormRef" :model="editForm" :rules="formRules" label-width="80px">
        <el-form-item :label="$t('uiAutomation.project.projectName')" prop="name">
          <el-input v-model="editForm.name" :placeholder="$t('uiAutomation.project.rules.nameRequired')" />
        </el-form-item>
        <el-form-item :label="$t('uiAutomation.project.projectDesc')" prop="description">
          <el-input v-model="editForm.description" type="textarea" :placeholder="$t('uiAutomation.project.projectDesc')" />
        </el-form-item>
        <el-form-item :label="$t('uiAutomation.common.status')" prop="status">
          <el-select v-model="editForm.status" :placeholder="$t('uiAutomation.project.rules.selectStatus')">
            <el-option :label="$t('uiAutomation.status.notStarted')" value="NOT_STARTED" />
            <el-option :label="$t('uiAutomation.status.inProgress')" value="IN_PROGRESS" />
            <el-option :label="$t('uiAutomation.status.completed')" value="COMPLETED" />
          </el-select>
        </el-form-item>
        <el-form-item label="基础URL" prop="base_url">
          <el-input 
            v-model="editForm.base_url" 
            placeholder="请输入基础URL（如：https://www.example.com）"
          >
            <template #prepend>
              <el-select v-model="editUrlProtocol" placeholder="协议" style="width: 100px">
                <el-option label="https://" value="https://" />
                <el-option label="http://" value="http://" />
              </el-select>
            </template>
          </el-input>
          <div style="color: #909399; font-size: 12px; margin-top: 4px;">
            提示：请输入完整的URL地址，包含协议（http:// 或 https://）
          </div>
        </el-form-item>
        <el-form-item :label="$t('uiAutomation.project.startDate')" prop="start_date">
          <el-date-picker v-model="editForm.start_date" type="date" :placeholder="$t('uiAutomation.project.selectDate')" />
        </el-form-item>
        <el-form-item :label="$t('uiAutomation.project.endDate')" prop="end_date">
          <el-date-picker v-model="editForm.end_date" type="date" :placeholder="$t('uiAutomation.project.selectDate')" />
        </el-form-item>
        <el-divider content-position="left">自愈策略</el-divider>
        <el-form-item label="自动诊断">
          <el-switch v-model="editForm.heal_settings.auto_diagnose" />
        </el-form-item>
        <el-form-item label="模式">
          <el-select v-model="editForm.heal_settings.mode" style="width: 100%">
            <el-option label="仅诊断" value="diagnose_only" />
            <el-option label="人工应用（默认）" value="manual_apply" />
            <el-option label="低风险自动应用" value="auto_low_risk" />
          </el-select>
        </el-form-item>
        <el-form-item label="应用后重跑验证">
          <el-switch v-model="editForm.heal_settings.verify_rerun" />
        </el-form-item>
        <el-form-item label="备用定位自动升格">
          <el-switch v-model="editForm.heal_settings.auto_promote_backup" />
        </el-form-item>
        <el-form-item label="结合元素库自动选点">
          <el-switch v-model="editForm.heal_settings.auto_pick_from_element" />
          <div class="form-tip">诊断时根据元素主/备定位自动判定修复方案；低风险模式下可自动升格备用定位</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showEditDialog = false">{{ $t('uiAutomation.common.cancel') }}</el-button>
          <el-button type="primary" @click="handleEdit">{{ $t('uiAutomation.common.confirm') }}</el-button>
        </span>
      </template>
    </el-dialog>
    
    <!-- 项目详情弹框 -->
    <el-dialog v-model="showDetailDialog" :title="$t('uiAutomation.project.projectDetail')" width="600px">
      <div v-if="currentProjectDetail" class="project-detail">
        <el-descriptions bordered column="1">
          <el-descriptions-item :label="$t('uiAutomation.project.projectName')">{{ currentProjectDetail.name }}</el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.project.projectDesc')" :span="2">{{ currentProjectDetail.description || $t('uiAutomation.project.noDescription') }}</el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.common.status')">
            <el-tag :type="getStatusType(currentProjectDetail.status)">
              {{ getStatusText(currentProjectDetail.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.project.baseUrl')">{{ currentProjectDetail.base_url }}</el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.project.owner')">{{ currentProjectDetail.owner?.username || $t('uiAutomation.project.none') }}</el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.project.startDate')">{{ currentProjectDetail.start_date ? formatDate(null, null, currentProjectDetail.start_date) : $t('uiAutomation.project.notSet') }}</el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.project.endDate')">{{ currentProjectDetail.end_date ? formatDate(null, null, currentProjectDetail.end_date) : $t('uiAutomation.project.notSet') }}</el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.common.createTime')">{{ formatDate(null, null, currentProjectDetail.created_at) }}</el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.common.updateTime')">{{ formatDate(null, null, currentProjectDetail.updated_at) }}</el-descriptions-item>
        </el-descriptions>
      </div>
      <div v-else class="text-center text-gray-500">
        {{ $t('uiAutomation.common.loading') }}
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showDetailDialog = false">{{ $t('uiAutomation.common.close') }}</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search, View, Edit, Delete } from '@element-plus/icons-vue'
import { getUiProjects, createUiProject, updateUiProject, deleteUiProject } from '@/api/ui_automation'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

// 项目数据
const projects = ref([])
const loading = ref(false)
const total = ref(0)
const pagination = reactive({
  currentPage: 1,
  pageSize: 10
})

// 搜索和筛选
const searchText = ref('')
const statusFilter = ref('')

// URL 协议选择
const urlProtocol = ref('https://')
const editUrlProtocol = ref('https://')

// 表单相关
const showCreateDialog = ref(false)
const showEditDialog = ref(false)
const createFormRef = ref(null)
const editFormRef = ref(null)
const currentEditId = ref(null)

// 表单数据
const createForm = reactive({
  name: '',
  description: '',
  status: 'IN_PROGRESS',
  base_url: '',
  start_date: null,
  end_date: null
})

const editForm = reactive({
  name: '',
  description: '',
  status: 'IN_PROGRESS',
  base_url: '',
  start_date: null,
  end_date: null,
  heal_settings: {
    auto_diagnose: true,
    mode: 'manual_apply',
    verify_rerun: true,
    auto_promote_backup: false,
    auto_pick_from_element: true,
    auto_apply_types: ['increase_wait', 'add_backup_locator', 'promote_backup'],
    use_llm_on_manual_diagnose: true
  }
})

// 表单验证规则
const formRules = computed(() => ({
  name: [
    { required: true, message: t('uiAutomation.project.rules.nameRequired'), trigger: 'blur' },
    { min: 2, max: 200, message: t('uiAutomation.project.rules.nameLength'), trigger: 'blur' }
  ],
  base_url: [
    { required: true, message: '请输入基础URL', trigger: 'blur' },
    { 
      validator: (rule, value, callback) => {
        if (!value) {
          callback(new Error('请输入基础URL'))
        } else if (!value.startsWith('http://') && !value.startsWith('https://')) {
          callback(new Error('URL必须以 http:// 或 https:// 开头'))
        } else {
          // 简单的URL格式验证
          try {
            new URL(value)
            callback()
          } catch (e) {
            callback(new Error('请输入有效的URL格式'))
          }
        }
      }, 
      trigger: 'blur' 
    }
  ]
}))

// 格式化日期
const formatDate = (row, column, cellValue) => {
  if (!cellValue) return ''
  return new Date(cellValue).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

// 获取状态样式
const getStatusType = (status) => {
  const statusMap = {
    'NOT_STARTED': 'warning',
    'IN_PROGRESS': 'primary',
    'COMPLETED': 'success'
  }
  return statusMap[status] || 'default'
}

// 获取状态文本
const getStatusText = (status) => {
  const statusKey = {
    'NOT_STARTED': 'notStarted',
    'IN_PROGRESS': 'inProgress',
    'COMPLETED': 'completed'
  }[status]
  return statusKey ? t(`uiAutomation.status.${statusKey}`) : status
}

// 加载项目列表
const loadProjects = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.currentPage,
      page_size: pagination.pageSize
    }
    
    // 添加搜索条件
    if (searchText.value) {
      params.search = searchText.value
    }
    
    // 添加筛选条件
    if (statusFilter.value) {
      params.status = statusFilter.value
    }
    
    const response = await getUiProjects(params)
    projects.value = response.data.results || response.data
    total.value = response.data.count || projects.value.length
  } catch (error) {
    ElMessage.error(t('uiAutomation.project.messages.loadFailed'))
    console.error('获取项目列表失败:', error)
  } finally {
    loading.value = false
  }
}

// 搜索处理
const handleSearch = () => {
  pagination.currentPage = 1
  loadProjects()
}

// 筛选处理
const handleFilter = () => {
  pagination.currentPage = 1
  loadProjects()
}

// 分页处理
const handleSizeChange = (size) => {
  pagination.pageSize = size
  loadProjects()
}

const handleCurrentChange = (current) => {
  pagination.currentPage = current
  loadProjects()
}

// 详情相关
const showDetailDialog = ref(false)
const currentProjectDetail = ref(null)

// 查看项目详情
const goToProjectDetail = (id) => {
  // 查找当前项目
  const project = projects.value.find(p => p.id === id)
  if (project) {
    currentProjectDetail.value = project
    showDetailDialog.value = true
  } else {
    ElMessage.error(t('uiAutomation.project.messages.notFound'))
  }
}

// 编辑项目
const editProject = (project) => {
  currentEditId.value = project.id
  // 复制项目数据到编辑表单
  Object.assign(editForm, {
    name: project.name,
    description: project.description,
    status: project.status,
    base_url: project.base_url,
    start_date: project.start_date ? new Date(project.start_date) : null,
    end_date: project.end_date ? new Date(project.end_date) : null,
    heal_settings: {
      auto_diagnose: true,
      mode: 'manual_apply',
      verify_rerun: true,
      auto_promote_backup: false,
      auto_pick_from_element: true,
      auto_apply_types: ['increase_wait', 'add_backup_locator', 'promote_backup'],
      use_llm_on_manual_diagnose: true,
      ...(project.heal_settings || {})
    }
  })
  showEditDialog.value = true
}

// 删除项目
const deleteProject = async (id) => {
  try {
    await ElMessageBox.confirm(t('uiAutomation.project.messages.deleteConfirm'), t('uiAutomation.messages.confirm.delete'), {
      confirmButtonText: t('uiAutomation.common.confirm'),
      cancelButtonText: t('uiAutomation.common.cancel'),
      type: 'warning'
    })

    await deleteUiProject(id)
    ElMessage.success(t('uiAutomation.project.messages.deleteSuccess'))
    loadProjects()
  } catch (error) {
    if (error === 'cancel') return
    ElMessage.error(t('uiAutomation.project.messages.deleteFailed'))
    console.error('删除项目失败:', error)
  }
}

// 导入用户store
import { useUserStore } from '@/stores/user'

// 日期格式化辅助函数
const formatDateToISO = (date) => {
  if (!date) return null
  // 确保是Date对象
  const d = new Date(date)
  // 格式化为YYYY-MM-DD格式
  return d.toISOString().split('T')[0]
}

// 处理创建项目
const handleCreate = async () => {
  const validate = await createFormRef.value.validate()
  if (!validate) return
  
  try {
    const userStore = useUserStore()
    // 确保用户信息已加载
    if (!userStore.user?.id) {
      await userStore.fetchProfile()
    }
    
    // 确保 base_url 包含协议
    let baseUrl = createForm.base_url.trim()
    if (baseUrl && !baseUrl.startsWith('http://') && !baseUrl.startsWith('https://')) {
      baseUrl = urlProtocol.value + baseUrl
    }
    
    // 创建包含owner字段的项目数据，并格式化日期字段
    const projectData = {
      ...createForm,
      base_url: baseUrl,
      owner: userStore.user.id,  // 添加owner字段，值为当前登录用户ID
      // 格式化日期为YYYY-MM-DD格式
      start_date: formatDateToISO(createForm.start_date),
      end_date: formatDateToISO(createForm.end_date)
    }
    
    await createUiProject(projectData)
    ElMessage.success(t('uiAutomation.project.messages.createSuccess'))
    showCreateDialog.value = false
    
    // 重置表单
    Object.keys(createForm).forEach(key => {
      createForm[key] = ''
    })
    createForm.status = 'IN_PROGRESS'
    urlProtocol.value = 'https://'
    
    loadProjects()
  } catch (error) {
    ElMessage.error(error.response?.data?.base_url?.[0] || error.response?.data?.detail || '项目创建失败')
    console.error('创建项目失败:', error)
  }
}

// 处理编辑项目
const handleEdit = async () => {
  const validate = await editFormRef.value.validate()
  if (!validate) return
  
  try {
    // 确保 base_url 包含协议
    let baseUrl = editForm.base_url.trim()
    if (baseUrl && !baseUrl.startsWith('http://') && !baseUrl.startsWith('https://')) {
      baseUrl = editUrlProtocol.value + baseUrl
    }
    
    // 创建包含格式化日期字段的项目数据
    const projectData = {
      ...editForm,
      base_url: baseUrl,
      // 格式化日期为YYYY-MM-DD格式
      start_date: formatDateToISO(editForm.start_date),
      end_date: formatDateToISO(editForm.end_date)
    }
    
    await updateUiProject(currentEditId.value, projectData)
    ElMessage.success(t('uiAutomation.project.messages.updateSuccess'))
    showEditDialog.value = false
    loadProjects()
  } catch (error) {
    ElMessage.error(error.response?.data?.base_url?.[0] || error.response?.data?.detail || '项目更新失败')
    console.error('更新项目失败:', error)
  }
}

// 组件挂载时加载数据
onMounted(() => {
  loadProjects()
})
</script>

<style scoped>
.page-container {
  padding: 20px;
  height: 100%;
  overflow-y: auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-title {
  margin: 0;
  font-size: 24px;
}

.card-container {
  background-color: #fff;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.filter-bar {
  margin-bottom: 20px;
}

.pagination-container {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.form-tip {
  margin-top: 4px;
  font-size: 12px;
  color: #909399;
  line-height: 1.4;
}
</style>