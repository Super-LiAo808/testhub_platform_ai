<template>
  <div class="device-management">
    <!-- 页面标题和操作按钮 -->
    <div class="device-header">
      <h3>{{ $t('appAutomation.device.title') }}</h3>
      <div class="device-actions">
        <el-button
          type="primary"
          :icon="Refresh"
          :loading="refreshing"
          @click="refreshDevices"
        >
          {{ $t('appAutomation.device.refreshDevice') }}
        </el-button>
        <el-button
          type="success"
          :icon="Plus"
          @click="showAddRemoteDialog"
        >
          {{ $t('appAutomation.device.addRemoteDevice') }}
        </el-button>
      </div>
    </div>

    <!-- 设备列表 -->
    <el-table
      v-loading="loading"
      :data="devices"
      style="width: 100%; margin-top: 20px"
      :empty-text="emptyText"
    >
      <el-table-column prop="name" :label="$t('appAutomation.device.deviceName')" min-width="150">
        <template #default="{ row }">
          <span>{{ row.name || row.device_id }}</span>
        </template>
      </el-table-column>

      <el-table-column prop="device_id" :label="$t('appAutomation.device.serialNumber')" min-width="180" />

      <el-table-column prop="status" :label="$t('appAutomation.common.status')" width="100">
        <template #default="{ row }">
          <el-tag :type="getStatusType(row.status)" size="small">
            {{ getStatusText(row.status) }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column prop="locked_by" :label="$t('appAutomation.device.lockedUser')" width="120">
        <template #default="{ row }">
          <span v-if="row.locked_by_name">
            {{ row.locked_by_name }}
          </span>
          <span v-else>-</span>
        </template>
      </el-table-column>

      <el-table-column prop="locked_at" :label="$t('appAutomation.device.lockedTime')" width="180">
        <template #default="{ row }">
          <span v-if="row.locked_at">
            {{ formatDate(row.locked_at) }}
          </span>
          <span v-else>-</span>
        </template>
      </el-table-column>

      <el-table-column prop="android_version" :label="$t('appAutomation.device.androidVersion')" width="120" />

      <el-table-column prop="connection_type" :label="$t('appAutomation.device.connectionType')" width="120">
        <template #default="{ row }">
          <el-tag
            :type="getConnectionType(row.connection_type) === 'local' ? 'primary' : 'warning'"
            size="small"
          >
            {{ getConnectionTypeName(row.connection_type) }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column prop="ip_address" :label="$t('appAutomation.device.ipAddress')" width="150">
        <template #default="{ row }">
          <span v-if="row.ip_address">
            {{ row.ip_address }}
          </span>
          <span v-else>-</span>
        </template>
      </el-table-column>

      <el-table-column prop="usage_count" :label="$t('appAutomation.device.usageCount')" width="100" />

      <el-table-column prop="updated_at" :label="$t('appAutomation.common.updateTime')" width="180">
        <template #default="{ row }">
          {{ formatDate(row.updated_at) }}
        </template>
      </el-table-column>

      <el-table-column :label="$t('appAutomation.common.operation')" width="260" fixed="right">
        <template #default="{ row }">
          <div class="table-actions">
            <el-button
              v-if="row.status === 'available' || row.status === 'online'"
              link
              size="small"
              type="primary"
              @click="lockDevice(row)"
            >
              {{ $t('appAutomation.device.lock') }}
            </el-button>
            <el-button
              v-if="row.status === 'locked'"
              link
              size="small"
              type="success"
              @click="unlockDevice(row)"
            >
              {{ $t('appAutomation.device.unlock') }}
            </el-button>
            <el-button
              v-if="isRemoteDevice(row.connection_type) && row.status === 'offline'"
              link
              size="small"
              type="warning"
              :loading="reconnectingDevices[row.id]"
              @click="reconnectDevice(row)"
            >
              {{ $t('appAutomation.device.reconnect') }}
            </el-button>
            <el-button
              link
              type="primary"
              size="small"
              @click="viewDeviceInfo(row)"
            >
              {{ $t('appAutomation.common.details') }}
            </el-button>
            <el-button
              v-if="isRemoteDevice(row.connection_type) && (row.status === 'online' || row.status === 'available')"
              link
              size="small"
              type="warning"
              @click="disconnectDevice(row)"
            >
              {{ $t('appAutomation.common.disconnect') }}
            </el-button>
            <el-button
              link
              size="small"
              type="danger"
              @click="handleDeleteDevice(row)"
            >
              {{ $t('appAutomation.common.delete') }}
            </el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <!-- 添加远程设备对话框 -->
    <el-dialog
      v-model="addRemoteDialogVisible"
      :title="$t('appAutomation.device.addRemoteDevice')"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="remoteDeviceFormRef"
        :model="remoteDeviceForm"
        :rules="remoteDeviceRules"
        label-width="100px"
      >
        <el-form-item :label="$t('appAutomation.device.ipAddress')" prop="ip_address">
          <el-input
            v-model="remoteDeviceForm.ip_address"
            :placeholder="$t('appAutomation.device.ipAddressPlaceholder')"
          />
        </el-form-item>

        <el-form-item :label="$t('appAutomation.device.port')" prop="port">
          <el-input-number
            v-model="remoteDeviceForm.port"
            :min="1"
            :max="65535"
            :placeholder="$t('appAutomation.device.portPlaceholder')"
            style="width: 100%"
          />
        </el-form-item>

        <el-alert
          :title="$t('appAutomation.device.tip')"
          type="info"
          :closable="false"
          style="margin-top: 10px"
        >
          <div>{{ $t('appAutomation.device.remoteTipTitle') }}</div>
          <div>{{ $t('appAutomation.device.remoteTip1') }}</div>
          <div>{{ $t('appAutomation.device.remoteTip2') }}</div>
          <div>{{ $t('appAutomation.device.remoteTip3') }}</div>
        </el-alert>
      </el-form>

      <template #footer>
        <div class="dialog-footer">
          <el-button @click="addRemoteDialogVisible = false">{{ $t('appAutomation.common.cancel') }}</el-button>
          <el-button
            type="primary"
            :loading="connecting"
            @click="connectRemoteDevice"
          >
            {{ $t('appAutomation.common.connect') }}
          </el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 设备详情对话框 -->
    <el-dialog
      v-model="deviceInfoDialogVisible"
      :title="$t('appAutomation.device.deviceDetail')"
      width="600px"
    >
      <el-descriptions v-if="selectedDevice" :column="2" border>
        <el-descriptions-item :label="$t('appAutomation.device.deviceName')">
          {{ selectedDevice.name || selectedDevice.device_id }}
        </el-descriptions-item>
        <el-descriptions-item :label="$t('appAutomation.device.serialNumber')">
          {{ selectedDevice.device_id }}
        </el-descriptions-item>
        <el-descriptions-item :label="$t('appAutomation.common.status')">
          <el-tag :type="getStatusType(selectedDevice.status)" size="small">
            {{ getStatusText(selectedDevice.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item :label="$t('appAutomation.device.lockedUser')">
          {{ selectedDevice.locked_by_name || '-' }}
        </el-descriptions-item>
        <el-descriptions-item :label="$t('appAutomation.device.lockedTime')">
          {{ selectedDevice.locked_at ? formatDate(selectedDevice.locked_at) : '-' }}
        </el-descriptions-item>
        <el-descriptions-item :label="$t('appAutomation.device.androidVersion')">
          {{ selectedDevice.android_version || '-' }}
        </el-descriptions-item>
        <el-descriptions-item :label="$t('appAutomation.device.connectionType')">
          <el-tag
            :type="getConnectionType(selectedDevice.connection_type) === 'local' ? 'primary' : 'warning'"
            size="small"
          >
            {{ getConnectionTypeName(selectedDevice.connection_type) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item :label="$t('appAutomation.device.ipAddress')">
          {{ selectedDevice.ip_address || '-' }}
        </el-descriptions-item>
        <el-descriptions-item :label="$t('appAutomation.device.port')">
          {{ selectedDevice.port || '-' }}
        </el-descriptions-item>
        <el-descriptions-item :label="$t('appAutomation.device.usageCount')">
          {{ selectedDevice.usage_count || 0 }}
        </el-descriptions-item>
        <el-descriptions-item :label="$t('appAutomation.common.createTime')">
          {{ formatDate(selectedDevice.created_at) }}
        </el-descriptions-item>
        <el-descriptions-item :label="$t('appAutomation.common.updateTime')">
          {{ formatDate(selectedDevice.updated_at) }}
        </el-descriptions-item>
      </el-descriptions>

      <template #footer>
        <div class="dialog-footer">
          <el-button @click="deviceInfoDialogVisible = false">{{ $t('appAutomation.common.close') }}</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Plus } from '@element-plus/icons-vue'
import {
  getDeviceList,
  discoverDevices,
  lockDevice as apiLockDevice,
  unlockDevice as apiUnlockDevice,
  connectDevice,
  disconnectDevice as apiDisconnectDevice,
  deleteDevice
} from '@/api/app-automation'
import { getDeviceStatusType, getDeviceStatusText, formatDateTime } from '@/utils/app-automation-helpers'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

// Refs
const remoteDeviceFormRef = ref(null)

// 响应式数据
const devices = ref([])
const loading = ref(false)
const refreshing = ref(false)
const connecting = ref(false)
const reconnectingDevices = ref({})
const addRemoteDialogVisible = ref(false)
const deviceInfoDialogVisible = ref(false)
const selectedDevice = ref(null)
const emptyText = ref(t('appAutomation.device.emptyText'))
const refreshTimer = ref(null)

const remoteDeviceForm = ref({
  ip_address: '',
  port: 5555
})

const remoteDeviceRules = computed(() => ({
  ip_address: [
    { required: true, message: t('appAutomation.device.rules.ipRequired'), trigger: 'blur' },
    {
      pattern: /^(\d{1,3}\.){3}\d{1,3}$/,
      message: t('appAutomation.device.rules.ipInvalid'),
      trigger: 'blur'
    }
  ],
  port: [
    { required: true, message: t('appAutomation.device.rules.portRequired'), trigger: 'blur' }
  ]
}))

// 方法
const getDevices = async () => {
  loading.value = true
  try {
    const res = await getDeviceList({ page: 1, page_size: 1000 })
    devices.value = res.data.results || []
    if (devices.value.length === 0) {
      emptyText.value = t('appAutomation.device.emptyText')
    }
  } catch (error) {
    console.error('获取设备列表失败:', error)
    ElMessage.error(t('appAutomation.device.messages.loadFailed') + ': ' + (error.message || t('appAutomation.device.unknownError')))
  } finally {
    loading.value = false
  }
}

const refreshDevices = async () => {
  refreshing.value = true
  try {
    const res = await discoverDevices()
    if (res.data.success) {
      devices.value = res.data.devices || []
      ElMessage.success(res.data.message || t('appAutomation.device.messages.refreshedSuccess'))
    } else {
      ElMessage.error(res.data.message || t('appAutomation.device.messages.refreshFailed'))
    }
  } catch (error) {
    console.error('刷新设备列表失败:', error)
    ElMessage.error(t('appAutomation.device.messages.refreshFailed') + ': ' + (error.message || t('appAutomation.device.unknownError')))
  } finally {
    refreshing.value = false
  }
}

const showAddRemoteDialog = () => {
  addRemoteDialogVisible.value = true
  remoteDeviceForm.value = {
    ip_address: '',
    port: 5555
  }
  if (remoteDeviceFormRef.value) {
    remoteDeviceFormRef.value.clearValidate()
  }
}

const connectRemoteDevice = async () => {
  if (!remoteDeviceFormRef.value) return
  
  remoteDeviceFormRef.value.validate(async (valid) => {
    if (!valid) return
    
    connecting.value = true
    try {
      const res = await connectDevice({
        ip_address: remoteDeviceForm.value.ip_address,
        port: remoteDeviceForm.value.port
      })
      
      if (res.data.success) {
        ElMessage.success(res.data.message || t('appAutomation.device.messages.connectSuccess'))
        addRemoteDialogVisible.value = false
        await getDevices()
      } else {
        ElMessage.error(res.data.message || t('appAutomation.device.messages.connectFailed'))
      }
    } catch (error) {
      console.error('连接远程设备失败:', error)
      ElMessage.error(t('appAutomation.device.messages.connectFailed') + ': ' + (error.message || t('appAutomation.device.unknownError')))
    } finally {
      connecting.value = false
    }
  })
}

const reconnectDevice = async (device) => {
  if (!device.ip_address || !device.port) {
    ElMessage.error(t('appAutomation.device.messages.incompleteInfo'))
    return
  }

  reconnectingDevices.value[device.id] = true

  try {
    const res = await connectDevice({
      ip_address: device.ip_address,
      port: device.port
    })

    if (res.data.success) {
      ElMessage.success(t('appAutomation.device.messages.reconnectSuccess'))
      await getDevices()
    } else {
      ElMessage.error(res.data.message || t('appAutomation.device.messages.reconnectFailed'))
    }
  } catch (error) {
    console.error('设备重连失败:', error)
    ElMessage.error(t('appAutomation.device.messages.reconnectFailed'))
  } finally {
    reconnectingDevices.value[device.id] = false
  }
}

const disconnectDevice = async (device) => {
  try {
    await ElMessageBox.confirm(
      t('appAutomation.device.messages.disconnectConfirm', { name: device.name || device.device_id }),
      t('appAutomation.device.tip'),
      {
        confirmButtonText: t('appAutomation.common.confirm'),
        cancelButtonText: t('appAutomation.common.cancel'),
        type: 'warning'
      }
    )

    const res = await apiDisconnectDevice(device.id)

    if (res.data.success) {
      ElMessage.success(t('appAutomation.device.messages.disconnected'))
      await getDevices()
    } else {
      ElMessage.error(res.data.message || t('appAutomation.device.messages.disconnectFailed'))
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('断开设备失败:', error)
      ElMessage.error(t('appAutomation.device.messages.disconnectFailed') + ': ' + (error.message || t('appAutomation.device.unknownError')))
    }
  }
}

const viewDeviceInfo = (device) => {
  selectedDevice.value = device
  deviceInfoDialogVisible.value = true
}

const lockDevice = async (device) => {
  try {
    await ElMessageBox.confirm(
      t('appAutomation.device.messages.lockConfirm', { name: device.name || device.device_id }),
      t('appAutomation.device.tip'),
      {
        confirmButtonText: t('appAutomation.common.confirm'),
        cancelButtonText: t('appAutomation.common.cancel'),
        type: 'warning'
      }
    )

    const res = await apiLockDevice(device.id)

    if (res.data.success) {
      ElMessage.success(t('appAutomation.device.messages.locked'))
      await getDevices()
    } else {
      ElMessage.error(res.data.message || t('appAutomation.device.messages.lockFailed'))
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('锁定设备失败:', error)
      ElMessage.error(t('appAutomation.device.messages.lockFailed') + ': ' + (error.message || t('appAutomation.device.unknownError')))
    }
  }
}

const unlockDevice = async (device) => {
  try {
    await ElMessageBox.confirm(
      t('appAutomation.device.messages.unlockConfirm', { name: device.name || device.device_id }),
      t('appAutomation.device.tip'),
      {
        confirmButtonText: t('appAutomation.common.confirm'),
        cancelButtonText: t('appAutomation.common.cancel'),
        type: 'warning'
      }
    )

    const res = await apiUnlockDevice(device.id)

    if (res.data.success) {
      ElMessage.success(t('appAutomation.device.messages.unlocked'))
      await getDevices()
    } else {
      ElMessage.error(res.data.message || t('appAutomation.device.messages.unlockFailed'))
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('解锁设备失败:', error)
      ElMessage.error(t('appAutomation.device.messages.unlockFailed') + ': ' + (error.message || t('appAutomation.device.unknownError')))
    }
  }
}

const handleDeleteDevice = async (device) => {
  try {
    await ElMessageBox.confirm(
      t('appAutomation.device.messages.deleteConfirm', { name: device.name || device.device_id }),
      t('appAutomation.device.messages.deleteDeviceTitle'),
      {
        confirmButtonText: t('appAutomation.common.confirm'),
        cancelButtonText: t('appAutomation.common.cancel'),
        type: 'warning',
        dangerouslyUseHTMLString: false
      }
    )

    const res = await deleteDevice(device.id)

    if (res.status === 204 || res.status === 200) {
      ElMessage.success(t('appAutomation.device.messages.deleted'))
      await getDevices()
    } else {
      ElMessage.error(res.data?.message || t('appAutomation.device.messages.deleteFailed'))
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除设备失败:', error)
      ElMessage.error(t('appAutomation.device.messages.deleteFailed') + ': ' + (error.message || t('appAutomation.device.unknownError')))
    }
  }
}

const formatDate = formatDateTime
const getStatusType = getDeviceStatusType
const getStatusText = getDeviceStatusText

const getConnectionType = (type) => {
  // emulator, remote_emulator, remote, usb 等
  if (type === 'emulator' || type === 'usb') {
    return 'local'
  }
  return 'remote'
}

const getConnectionTypeName = (type) => {
  const typeKey = {
    'emulator': 'emulator',
    'remote_emulator': 'remoteEmulator',
    'remote': 'remote',
    'usb': 'usb'
  }[type]
  return typeKey ? t(`appAutomation.device.connectionTypes.${typeKey}`) : type
}

const isRemoteDevice = (type) => {
  return type === 'remote_emulator' || type === 'remote'
}

// 生命周期
onMounted(() => {
  getDevices()

  // 30秒自动刷新设备列表
  refreshTimer.value = setInterval(() => {
    getDevices()
  }, 30000)
})

onBeforeUnmount(() => {
  if (refreshTimer.value) {
    clearInterval(refreshTimer.value)
  }
})
</script>

<style scoped lang="scss">
.device-management {
  padding: 20px;
}

.device-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;

  h3 {
    margin: 0;
    font-size: 20px;
    color: #303133;
  }
}

.device-actions {
  display: flex;
  gap: 10px;
}

.dialog-footer {
  text-align: right;
}
</style>
