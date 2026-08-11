<template>
  <div class="app-settings">
    <el-card>
      <template #header>
        <div class="card-header">
          <span><el-icon><Setting /></el-icon> {{ $t('appAutomation.settings.title') }}</span>
        </div>
      </template>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="120px"
        style="max-width: 600px"
      >
        <el-form-item :label="$t('appAutomation.settings.adbPath')" prop="adb_path">
          <el-input
            v-model="form.adb_path"
            :placeholder="$t('appAutomation.settings.adbPathPlaceholder')"
            clearable
          >
            <template #prepend>
              <el-icon><FolderOpened /></el-icon>
            </template>
          </el-input>
          <div class="form-item-tip">
            <el-text size="small" type="info">
              {{ $t('appAutomation.settings.adbPathTip') }}
            </el-text>
          </div>
        </el-form-item>

        <el-form-item :label="$t('appAutomation.settings.appiumServerUrl')" prop="appium_server_url">
          <el-input
            v-model="form.appium_server_url"
            :placeholder="$t('appAutomation.settings.appiumServerUrlPlaceholder')"
            clearable
          />
          <div class="form-item-tip">
            <el-text size="small" type="info">
              {{ $t('appAutomation.settings.appiumServerUrlTip') }}
            </el-text>
          </div>
        </el-form-item>

        <el-form-item :label="$t('appAutomation.settings.appiumCommand')" prop="appium_command">
          <el-input
            v-model="form.appium_command"
            :placeholder="$t('appAutomation.settings.appiumCommandPlaceholder')"
            clearable
          />
          <div class="form-item-tip">
            <el-text size="small" type="info">
              {{ $t('appAutomation.settings.appiumCommandTip') }}
            </el-text>
          </div>
        </el-form-item>

        <el-form-item :label="$t('appAutomation.settings.appiumAutoStart')">
          <el-switch v-model="form.appium_auto_start" />
          <div class="form-item-tip">
            <el-text size="small" type="info">
              {{ $t('appAutomation.settings.appiumAutoStartTip') }}
            </el-text>
          </div>
        </el-form-item>

        <el-form-item :label="$t('appAutomation.settings.androidSdkPath')" prop="android_sdk_path">
          <el-input
            v-model="form.android_sdk_path"
            :placeholder="$t('appAutomation.settings.androidSdkPathPlaceholder')"
            clearable
          />
          <div class="form-item-tip">
            <el-text size="small" type="info">
              {{ $t('appAutomation.settings.androidSdkPathTip') }}
            </el-text>
          </div>
        </el-form-item>

        <el-form-item :label="$t('appAutomation.settings.scrcpyPath')" prop="scrcpy_path">
          <el-input
            v-model="form.scrcpy_path"
            :placeholder="$t('appAutomation.settings.scrcpyPathPlaceholder')"
            clearable
          />
          <div class="form-item-tip">
            <el-text size="small" type="info">
              {{ $t('appAutomation.settings.scrcpyPathTip') }}
            </el-text>
          </div>
        </el-form-item>

        <el-form-item :label="$t('appAutomation.settings.scrcpyServerPath')" prop="scrcpy_server_path">
          <el-input
            v-model="form.scrcpy_server_path"
            :placeholder="$t('appAutomation.settings.scrcpyServerPathPlaceholder')"
            clearable
          />
          <div class="form-item-tip">
            <el-text size="small" type="info">
              {{ $t('appAutomation.settings.scrcpyServerPathTip') }}
            </el-text>
          </div>
        </el-form-item>

        <el-form-item :label="$t('appAutomation.settings.scrcpyMaxSize')" prop="scrcpy_max_size">
          <el-input-number v-model="form.scrcpy_max_size" :min="480" :max="4096" :step="160" />
          <div class="form-item-tip">
            <el-text size="small" type="info">
              {{ $t('appAutomation.settings.scrcpyMaxSizeTip') }}
            </el-text>
          </div>
        </el-form-item>

        <el-form-item :label="$t('appAutomation.settings.scrcpyBitRate')" prop="scrcpy_bit_rate">
          <el-input
            v-model="form.scrcpy_bit_rate"
            :placeholder="$t('appAutomation.settings.scrcpyBitRatePlaceholder')"
            clearable
          />
          <div class="form-item-tip">
            <el-text size="small" type="info">
              {{ $t('appAutomation.settings.scrcpyBitRateTip') }}
            </el-text>
          </div>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="handleSave" :loading="saving">
            <el-icon><Check /></el-icon>
            {{ $t('appAutomation.settings.saveConfig') }}
          </el-button>
          <el-button @click="handleReset">
            <el-icon><RefreshLeft /></el-icon>
            {{ $t('appAutomation.common.reset') }}
          </el-button>
        </el-form-item>
      </el-form>

      <el-divider />

      <div class="config-info">
        <el-descriptions :title="$t('appAutomation.settings.currentConfig')" :column="1" border>
          <el-descriptions-item :label="$t('appAutomation.settings.adbPath')">
            <el-tag>{{ currentConfig.adb_path || 'adb' }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item :label="$t('appAutomation.settings.appiumServerUrl')">
            <el-tag type="info">{{ currentConfig.appium_server_url || 'http://127.0.0.1:4723' }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item :label="$t('appAutomation.settings.appiumCommand')">
            <el-tag type="info">{{ currentConfig.appium_command || 'appium' }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item :label="$t('appAutomation.settings.appiumAutoStart')">
            <el-tag :type="currentConfig.appium_auto_start ? 'success' : 'warning'">
              {{ currentConfig.appium_auto_start ? 'ON' : 'OFF' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item :label="$t('appAutomation.settings.androidSdkPath')">
            <el-tag type="info">{{ currentConfig.android_sdk_path || '-' }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item :label="$t('appAutomation.settings.scrcpyPath')">
            <el-tag type="info">{{ currentConfig.scrcpy_path || '-' }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item :label="$t('appAutomation.settings.scrcpyServerPath')">
            <el-tag type="info">{{ currentConfig.scrcpy_server_path || '-' }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item :label="$t('appAutomation.settings.scrcpyMaxSize')">
            <el-tag type="info">{{ currentConfig.scrcpy_max_size || 1280 }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item :label="$t('appAutomation.settings.scrcpyBitRate')">
            <el-tag type="info">{{ currentConfig.scrcpy_bit_rate || '4000000' }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item :label="$t('appAutomation.common.updateTime')">
            {{ formatTime(currentConfig.updated_at) }}
          </el-descriptions-item>
          <el-descriptions-item :label="$t('appAutomation.common.createTime')">
            {{ formatTime(currentConfig.created_at) }}
          </el-descriptions-item>
        </el-descriptions>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { Setting, FolderOpened, Check, RefreshLeft } from '@element-plus/icons-vue'
import { getAppConfig, updateAppConfig } from '@/api/app-automation'
import { formatDateTime } from '@/utils/app-automation-helpers'

const { t } = useI18n()

const formRef = ref(null)
const saving = ref(false)

const form = reactive({
  adb_path: 'adb',
  appium_server_url: 'http://127.0.0.1:4723',
  appium_command: 'appium',
  appium_auto_start: true,
  android_sdk_path: '',
  scrcpy_path: '',
  scrcpy_server_path: '',
  scrcpy_max_size: 1280,
  scrcpy_bit_rate: '4000000'
})

const currentConfig = reactive({
  adb_path: '',
  appium_server_url: '',
  appium_command: '',
  appium_auto_start: true,
  android_sdk_path: '',
  scrcpy_path: '',
  scrcpy_server_path: '',
  scrcpy_max_size: 1280,
  scrcpy_bit_rate: '4000000',
  created_at: '',
  updated_at: ''
})

const rules = computed(() => ({
  adb_path: [
    { required: true, message: t('appAutomation.settings.rules.adbPathRequired'), trigger: 'blur' }
  ],
  appium_server_url: [
    { required: true, message: t('appAutomation.settings.rules.appiumServerUrlRequired'), trigger: 'blur' }
  ],
  appium_command: [
    { required: true, message: t('appAutomation.settings.rules.appiumCommandRequired'), trigger: 'blur' }
  ]
}))

// 加载配置
const loadConfig = async () => {
  try {
    const res = await getAppConfig()
    if (res.data.success && res.data.data) {
      Object.assign(form, res.data.data)
      Object.assign(currentConfig, res.data.data)
    }
  } catch (error) {
    console.error('加载配置失败:', error)
    ElMessage.error(t('appAutomation.settings.messages.loadFailed'))
  }
}

// 保存配置
const handleSave = async () => {
  if (!formRef.value) return

  try {
    await formRef.value.validate()
    saving.value = true

    const res = await updateAppConfig(form)
    if (res.data.success) {
      ElMessage.success(t('appAutomation.settings.messages.saveSuccess'))
      await loadConfig()
    } else {
      ElMessage.error(res.data.message || t('appAutomation.settings.messages.saveFailed'))
    }
  } catch (error) {
    if (error !== false) { // 不是表单验证错误
      console.error('保存配置失败:', error)
      ElMessage.error(t('appAutomation.settings.messages.saveFailed'))
    }
  } finally {
    saving.value = false
  }
}

// 重置表单
const handleReset = () => {
  Object.assign(form, currentConfig)
}

const formatTime = formatDateTime

onMounted(() => {
  loadConfig()
})
</script>

<style scoped lang="scss">
.app-settings {
  padding: 20px;

  .card-header {
    display: flex;
    align-items: center;
    font-weight: bold;
    
    span {
      display: flex;
      align-items: center;
      gap: 8px;
    }
  }

  .form-item-tip {
    margin-top: 8px;
  }

  .config-info {
    margin-top: 20px;
  }
}
</style>
