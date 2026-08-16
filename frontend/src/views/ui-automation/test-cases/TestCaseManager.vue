<template>
  <div class="test-case-manager">
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">{{ t('uiAutomation.testCase.title') }}</h1>
        <p class="page-subtitle">录制回放、步骤编排与一键执行</p>
      </div>
      <div class="header-actions">
        <el-select
          v-model="projectId"
          :placeholder="t('uiAutomation.project.selectProject')"
          filterable
          style="width: 220px"
          @change="onProjectSelectChange"
        >
          <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
        </el-select>
        <el-button type="primary" @click="showCreateDialog = true">
          <el-icon><Plus /></el-icon>
          {{ t('uiAutomation.testCase.newTestCase') }}
        </el-button>
      </div>
    </div>

    <div class="main-content">
      <!-- 左侧：测试用例列表 -->
      <div class="left-panel">
        <div class="panel-header">
          <div class="panel-title-row">
            <h3>{{ t('uiAutomation.testCase.testCaseList') }}</h3>
            <span class="case-count">{{ filteredTestCases.length }}</span>
          </div>
          <div class="panel-header-actions">
            <el-button
              v-if="selectedCaseIds.length"
              size="small"
              type="danger"
              plain
              @click="batchDeleteTestCases"
            >
              {{ t('uiAutomation.common.delete') }} ({{ selectedCaseIds.length }})
            </el-button>
            <el-input
              v-model="searchKeyword"
              :placeholder="t('uiAutomation.testCase.searchPlaceholder')"
              clearable
              size="small"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
          </div>
        </div>

        <div class="test-case-list">
          <div v-if="!filteredTestCases.length" class="empty-cases">
            <el-empty description="暂无用例" :image-size="72" />
          </div>
          <div
            v-for="testCase in filteredTestCases"
            :key="testCase.id"
            class="test-case-item"
            :class="{ active: selectedTestCase?.id === testCase.id }"
            @click="selectTestCase(testCase)"
          >
            <div class="case-header">
              <div class="case-select" @click.stop>
                <el-checkbox
                  :model-value="selectedCaseIds.includes(testCase.id)"
                  @change="(val) => toggleCaseSelect(testCase.id, val)"
                />
              </div>
              <div class="case-info">
                <h4 class="case-name">{{ testCase.name }}</h4>
                <p class="case-description">{{ testCase.description || t('uiAutomation.testCase.noDescription') }}</p>
              </div>
              <el-dropdown trigger="click" @command="(cmd) => onCaseCommand(cmd, testCase)" @click.stop>
                <el-button size="small" text class="more-btn" @click.stop>
                  <el-icon><MoreFilled /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="run">运行</el-dropdown-item>
                    <el-dropdown-item command="edit">编辑信息</el-dropdown-item>
                    <el-dropdown-item command="copy">复制</el-dropdown-item>
                    <el-dropdown-item command="delete" divided>
                      <span style="color:#dc2626">删除</span>
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
            <div class="case-meta">
              <span class="meta-chip">{{ testCase.steps?.length || 0 }} 步</span>
              <span v-if="testCase.linked_script_id" class="meta-chip linked">
                脚本 #{{ testCase.linked_script_id }}
                <el-tag
                  v-if="testCase.script_inconsistent"
                  size="small"
                  type="warning"
                  effect="plain"
                  style="margin-left: 4px"
                >不一致</el-tag>
              </span>
              <span class="update-time">{{ formatTime(testCase.updated_at) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧：测试用例详情和步骤编辑 -->
      <div class="right-panel">
        <div v-if="selectedTestCase" class="test-case-detail">
          <div class="detail-header">
            <div class="detail-title-block">
              <h3>{{ selectedTestCase.name }}</h3>
              <p v-if="selectedTestCase.description" class="detail-desc">{{ selectedTestCase.description }}</p>
            </div>
            <div class="detail-actions">
              <div class="action-group">
                <el-button size="small" @click="addStep">
                  <el-icon><Plus /></el-icon>
                  {{ t('uiAutomation.testCase.addStep') }}
                </el-button>
                <el-button size="small" type="primary" @click="saveTestCase">
                  <el-icon><Check /></el-icon>
                  {{ t('uiAutomation.testCase.saveTestCase') }}
                </el-button>
                <el-button size="small" type="danger" plain @click="deleteTestCase(selectedTestCase)">
                  <el-icon><Delete /></el-icon>
                  {{ t('uiAutomation.common.delete') }}
                </el-button>
              </div>
              <div class="run-group">
                <el-select v-model="selectedEngine" size="small" style="width: 120px">
                  <el-option label="Playwright" value="playwright" />
                  <el-option label="Selenium" value="selenium" />
                </el-select>
                <el-select v-model="selectedBrowser" size="small" style="width: 110px">
                  <el-option label="Chrome" value="chrome" />
                  <el-option label="Firefox" value="firefox" />
                  <el-option label="Safari" value="safari" />
                  <el-option label="Edge" value="edge" />
                </el-select>
                <el-select v-model="headlessMode" size="small" style="width: 100px">
                  <el-option :label="t('uiAutomation.testCase.headedMode')" :value="false" />
                  <el-option :label="t('uiAutomation.testCase.headlessMode')" :value="true" />
                </el-select>
                <el-button size="small" type="success" @click="runTestCase(selectedTestCase)" :loading="isRunning">
                  <el-icon v-if="!isRunning"><CaretRight /></el-icon>
                  {{ isRunning ? t('uiAutomation.testCase.running') : t('uiAutomation.testCase.runLabel') }}
                </el-button>
                <el-button size="small" v-if="executionResult" @click="toggleView">
                  <el-icon><component :is="showSteps ? 'View' : 'Edit'" /></el-icon>
                  {{ showSteps ? t('uiAutomation.testCase.viewResult') : t('uiAutomation.testCase.editSteps') }}
                </el-button>
                <el-button
                  size="small"
                  v-if="executionResult && !showSteps"
                  type="success"
                  @click="runTestCase(selectedTestCase)"
                  :loading="isRunning"
                >
                  <el-icon v-if="!isRunning"><Refresh /></el-icon>
                  {{ t('uiAutomation.testCase.rerun') }}
                </el-button>
              </div>
            </div>
          </div>

          <!-- 测试步骤编辑 -->
          <div class="steps-container" v-show="showSteps">
            <div class="steps-header">
              <h4>{{ t('uiAutomation.testCase.testSteps') }}</h4>
              <el-button size="small" text @click="expandAllSteps">
                {{ allStepsExpanded ? t('uiAutomation.testCase.foldAll') : t('uiAutomation.testCase.expandAll') }}
              </el-button>
            </div>

            <div class="steps-scroll-container">
              <div class="steps-list">
                <draggable
                  v-model="currentSteps"
                  item-key="id"
                  handle=".drag-handle"
                  @change="onStepsReorder"
                >
                  <template #item="{ element, index }">
                    <div class="step-item" :class="{ expanded: element.expanded }">
                      <div class="step-header">
                        <div class="step-left">
                          <el-icon class="drag-handle"><Rank /></el-icon>
                          <span class="step-number">{{ index + 1 }}</span>
                          <el-select
                            v-model="element.action_type"
                            :placeholder="t('uiAutomation.testCase.selectAction')"
                            size="small"
                            style="width: 120px"
                            @change="onActionTypeChange(element)"
                          >
                            <el-option :label="t('uiAutomation.testCase.actionClick')" value="click" />
                            <el-option :label="t('uiAutomation.testCase.actionFill')" value="fill" />
                            <el-option :label="t('uiAutomation.testCase.actionGetText')" value="getText" />
                            <el-option :label="t('uiAutomation.testCase.actionWaitFor')" value="waitFor" />
                            <el-option :label="t('uiAutomation.testCase.actionHover')" value="hover" />
                            <el-option :label="t('uiAutomation.testCase.actionScroll')" value="scroll" />
                            <el-option :label="t('uiAutomation.testCase.actionScreenshot')" value="screenshot" />
                            <el-option :label="t('uiAutomation.testCase.actionAssert')" value="assert" />
                            <el-option :label="t('uiAutomation.testCase.actionWait')" value="wait" />
                            <el-option :label="t('uiAutomation.testCase.actionSwitchTab')" value="switchTab" />
                          </el-select>
                          <el-select
                            v-if="needsElement(element.action_type)"
                            v-model="element.element_id"
                            :placeholder="t('uiAutomation.testCase.selectElement')"
                            size="small"
                            style="width: 200px"
                            filterable
                            @change="onElementChange(element)"
                          >
                            <el-option
                              v-for="elem in availableElements"
                              :key="elem.id"
                              :label="`${elem.name} (${elem.locator_value})`"
                              :value="elem.id"
                            />
                          </el-select>
                        </div>
                        <div class="step-right">
                          <el-button
                            size="small"
                            text
                            @click="element.expanded = !element.expanded"
                          >
                            <el-icon>
                              <component :is="element.expanded ? 'ArrowUp' : 'ArrowDown'" />
                            </el-icon>
                          </el-button>
                          <el-button size="small" text type="danger" @click="removeStep(index)">
                            <el-icon><Delete /></el-icon>
                          </el-button>
                        </div>
                      </div>

                      <div v-if="element.expanded" class="step-content">
                        <!-- 输入参数 -->
                        <div v-if="needsInputValue(element.action_type)" class="step-param">
                          <label>{{ t('uiAutomation.testCase.inputValue') }}</label>
                          <div style="display: flex; gap: 5px; flex: 1">
                            <el-input
                              v-model="element.input_value"
                              :placeholder="element.action_type === 'switchTab' ? t('uiAutomation.testCase.switchTabPlaceholder') : t('uiAutomation.testCase.inputPlaceholder')"
                              size="small"
                            >
                              <template #append>
                                <el-button
                                  size="small"
                                  :icon="MagicStick"
                                  @click="openDataFactorySelector(element, 'input_value')"
                                  :title="t('uiAutomation.testCase.referenceDataFactory')"
                                  class="data-factory-btn"
                                />
                              </template>
                            </el-input>
                            <el-tooltip :content="t('uiAutomation.testCase.insertVariable')" placement="top" v-if="element.action_type !== 'switchTab'">
                              <el-button size="small" @click="openVariableHelper(element, 'input_value')" class="variable-helper-btn">
                                <el-icon><MagicStick /></el-icon>
                              </el-button>
                            </el-tooltip>
                          </div>
                        </div>

                        <!-- 等待时间 -->
                        <div v-if="needsWaitTime(element.action_type)" class="step-param">
                          <label>{{ t('uiAutomation.testCase.waitTime') }}</label>
                          <el-input-number
                            v-model="element.wait_time"
                            :min="100"
                            :max="30000"
                            :step="100"
                            size="small"
                          />
                        </div>

                        <!-- 断言参数 -->
                        <div v-if="element.action_type === 'assert'" class="step-param">
                          <label>{{ t('uiAutomation.testCase.assertType') }}</label>
                          <el-select v-model="element.assert_type" size="small" style="width: 150px">
                            <el-option :label="t('uiAutomation.testCase.assertTextContains')" value="textContains" />
                            <el-option :label="t('uiAutomation.testCase.assertTextEquals')" value="textEquals" />
                            <el-option :label="t('uiAutomation.testCase.assertIsVisible')" value="isVisible" />
                            <el-option :label="t('uiAutomation.testCase.assertExists')" value="exists" />
                            <el-option :label="t('uiAutomation.testCase.assertHasAttribute')" value="hasAttribute" />
                          </el-select>
                          <div style="display: flex; align-items: center; margin-left: 10px; width: 240px">
                            <el-input
                              v-model="element.assert_value"
                              :placeholder="t('uiAutomation.testCase.expectedValue')"
                              size="small"
                              style="flex: 1"
                            >
                              <template #append>
                                <el-button
                                  size="small"
                                  :icon="MagicStick"
                                  @click="openDataFactorySelector(element, 'assert_value')"
                                  :title="t('uiAutomation.testCase.referenceDataFactory')"
                                  class="data-factory-btn"
                                />
                              </template>
                            </el-input>
                            <el-tooltip :content="t('uiAutomation.testCase.insertVariable')" placement="top">
                              <el-button size="small" style="margin-left: 5px" @click="openVariableHelper(element, 'assert_value')" class="variable-helper-btn">
                                <el-icon><MagicStick /></el-icon>
                              </el-button>
                            </el-tooltip>
                          </div>
                        </div>

                        <!-- 步骤描述 -->
                        <div class="step-param">
                          <label>{{ t('uiAutomation.testCase.stepDescription') }}</label>
                          <el-input
                            v-model="element.description"
                            :placeholder="t('uiAutomation.testCase.stepDescPlaceholder')"
                            size="small"
                          />
                        </div>
                      </div>
                    </div>
                  </template>
                </draggable>
              </div>
            </div>
          </div>

          <!-- 执行结果 -->
          <div v-if="executionResult" class="execution-result" v-show="!showSteps">
            <div class="result-header">
              <h4>{{ t('uiAutomation.testCase.executionResult') }}</h4>
              <el-tag :type="executionResult.success ? 'success' : 'danger'">
                {{ executionResult.success ? t('uiAutomation.testCase.executionSuccess') : t('uiAutomation.testCase.executionFailed') }}
              </el-tag>
            </div>
            <div class="result-content">
              <el-tabs v-model="resultActiveTab">
                <el-tab-pane :label="t('uiAutomation.testCase.executionLogs')" name="logs">
                  <div class="logs-container">
                    <div v-if="parsedExecutionLogs.length > 0">
                      <div v-for="(step, index) in parsedExecutionLogs" :key="index" class="log-item">
                        <div class="log-header">
                          <el-tag :type="step.success ? 'success' : 'danger'" size="small">
                            {{ t('uiAutomation.testCase.step') }} {{ step.step_number }}
                          </el-tag>
                          <span class="log-action">{{ getActionText(step.action_type) }}</span>
                          <span class="log-desc">{{ step.description }}</span>
                        </div>
                        <div v-if="step.error" class="log-error">
                          <el-icon><WarningFilled /></el-icon>
                          <pre class="error-message">{{ step.error }}</pre>
                        </div>
                      </div>
                    </div>
                    <el-empty :description="t('uiAutomation.testCase.noLogs')" />
                  </div>
                </el-tab-pane>
                <el-tab-pane :label="t('uiAutomation.testCase.failedScreenshots')" name="screenshots" v-if="executionResult.screenshots && executionResult.screenshots.length > 0">
                  <div class="screenshots-container">
                    <div
                      v-for="(screenshot, index) in executionResult.screenshots"
                      :key="index"
                      class="screenshot-item"
                      @click="previewScreenshot(screenshot)"
                    >
                      <div class="screenshot-wrapper">
                        <img
                          :src="screenshot.url"
                          :alt="`${t('uiAutomation.testCase.screenshot')} ${index + 1}`"
                          :data-index="index"
                          @error="handleImageError"
                          @load="handleImageLoad"
                        />
                        <div class="screenshot-placeholder" v-if="!screenshot.loaded">
                          <el-icon><Picture /></el-icon>
                          <span>{{ t('uiAutomation.testCase.loadingImage') }}</span>
                        </div>
                        <div class="screenshot-error" v-if="screenshot.error">
                          <el-icon><Warning /></el-icon>
                          <span>{{ t('uiAutomation.testCase.imageLoadFailed') }}</span>
                        </div>
                        <div class="screenshot-overlay">
                          <el-icon class="zoom-icon"><ZoomIn /></el-icon>
                        </div>
                      </div>
                      <div class="screenshot-info">
                        <p class="screenshot-description">{{ screenshot.description || t('uiAutomation.testCase.screenshot') + ' ' + (index + 1) }}</p>
                        <p class="screenshot-meta" v-if="screenshot.step_number">{{ t('uiAutomation.testCase.step') }} {{ screenshot.step_number }}</p>
                        <p class="screenshot-time" v-if="screenshot.timestamp">{{ formatTime(screenshot.timestamp) }}</p>
                      </div>
                    </div>
                  </div>
                </el-tab-pane>
                <el-tab-pane :label="t('uiAutomation.testCase.errorInfo')" name="errors" v-if="executionResult.errors && executionResult.errors.length > 0">
                  <div class="errors-container">
                    <div
                      v-for="(error, index) in executionResult.errors"
                      :key="index"
                      class="error-item"
                    >
                      <div class="error-header">
                        <el-tag type="danger" size="large">
                          <el-icon><WarningFilled /></el-icon>
                          {{ error.message || error }}
                        </el-tag>
                        <span v-if="error.step_number" class="error-step">
                          {{ t('uiAutomation.testCase.step') }} {{ error.step_number }}
                        </span>
                      </div>

                      <div v-if="error.action_type || error.element || error.description" class="error-meta">
                        <div v-if="error.action_type" class="meta-item">
                          <span class="meta-label">{{ t('uiAutomation.testCase.operationType') }}</span>
                          <span class="meta-value">{{ error.action_type }}</span>
                        </div>
                        <div v-if="error.element" class="meta-item">
                          <span class="meta-label">{{ t('uiAutomation.testCase.targetElement') }}</span>
                          <span class="meta-value">{{ error.element }}</span>
                        </div>
                        <div v-if="error.description" class="meta-item">
                          <span class="meta-label">{{ t('uiAutomation.testCase.stepDesc') }}</span>
                          <span class="meta-value">{{ error.description }}</span>
                        </div>
                      </div>

                      <div v-if="error.details || error.stack" class="error-details">
                        <div class="details-header">{{ t('uiAutomation.testCase.detailErrorInfo') }}</div>
                        <pre class="details-content">{{ error.details || error.stack }}</pre>
                      </div>
                    </div>
                  </div>
                </el-tab-pane>
              </el-tabs>
            </div>
          </div>
        </div>

        <div v-else class="no-selection">
          <el-empty :description="t('uiAutomation.testCase.selectTestCase')" />
        </div>
      </div>
    </div>

    <!-- 新建/编辑测试用例对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      :title="editingTestCase ? t('uiAutomation.testCase.editTestCase') : t('uiAutomation.testCase.createTestCase')"
      :close-on-click-modal="false"
      width="500px"
    >
      <el-form :model="testCaseForm" label-width="100px">
        <el-form-item :label="t('uiAutomation.testCase.caseName')" required>
          <el-input v-model="testCaseForm.name" :placeholder="t('uiAutomation.testCase.caseNamePlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('uiAutomation.testCase.caseDescription')">
          <el-input
            v-model="testCaseForm.description"
            type="textarea"
            :rows="3"
            :placeholder="t('uiAutomation.testCase.caseDescPlaceholder')"
          />
        </el-form-item>
        <el-form-item :label="t('uiAutomation.testCase.priority')">
          <el-select v-model="testCaseForm.priority" style="width: 100%">
            <el-option :label="t('uiAutomation.testCase.priorityHigh')" value="high" />
            <el-option :label="t('uiAutomation.testCase.priorityMedium')" value="medium" />
            <el-option :label="t('uiAutomation.testCase.priorityLow')" value="low" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showCreateDialog = false">{{ t('uiAutomation.common.cancel') }}</el-button>
          <el-button type="primary" @click="saveTestCaseForm">{{ t('uiAutomation.common.confirm') }}</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 截图预览对话框 -->
    <el-dialog
      v-model="showScreenshotPreview"
      :title="t('uiAutomation.testCase.screenshotPreview')"
      width="80%"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      :modal="true"
      :destroy-on-close="false"
    >
      <div v-if="currentScreenshot" class="screenshot-preview">
        <div class="preview-info">
          <h4>{{ currentScreenshot.description }}</h4>
          <p v-if="currentScreenshot.step_number">{{ t('uiAutomation.testCase.failedStep') }}: {{ t('uiAutomation.testCase.step') }} {{ currentScreenshot.step_number }}</p>
          <p v-if="currentScreenshot.timestamp">{{ t('uiAutomation.testCase.screenshotTime') }}: {{ formatTime(currentScreenshot.timestamp) }}</p>
        </div>
        <div class="preview-image">
          <img :src="currentScreenshot.url" :alt="currentScreenshot.description" />
        </div>
      </div>
    </el-dialog>

    <!-- 变量助手对话框 -->
    <el-dialog
      :close-on-press-escape="false"
      :modal="true"
      :destroy-on-close="false"
      v-model="showVariableHelper"
      :title="t('uiAutomation.testCase.variableHelper')"
      :close-on-click-modal="false"
      width="900px"
    >
      <el-tabs tab-position="left" style="height: 450px">
        <el-tab-pane
          v-for="(category, index) in variableCategoriesComputed"
          :key="index"
          :label="category.label"
        >
          <div style="height: 450px; overflow-y: auto; padding: 10px;">
            <el-table :data="category.variables" style="width: 100%" @row-click="insertVariable" highlight-current-row>
              <el-table-column prop="name" :label="t('uiAutomation.testCase.functionName')" width="150" show-overflow-tooltip>
                <template #default="{ row }">
                  <el-tag size="small">{{ row.name }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="desc" :label="t('uiAutomation.testCase.description')" min-width="150" />
              <el-table-column prop="syntax" :label="t('uiAutomation.testCase.syntax')" min-width="200" show-overflow-tooltip />
              <el-table-column prop="example" :label="t('uiAutomation.testCase.example')" min-width="200" show-overflow-tooltip />
              <el-table-column :label="t('uiAutomation.testCase.operation')" width="80" fixed="right">
                <template #default="{ row }">
                  <div class="table-actions">
                    <el-button link type="primary" size="small">{{ t('uiAutomation.testCase.insert') }}</el-button>
                  </div>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-dialog>
    
    <DataFactorySelector
      v-model="showDataFactorySelector"
      @select="handleDataFactorySelect"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Search, Plus, Edit, Delete, Check, CaretRight, ArrowUp, ArrowDown, Rank, Picture, Warning, View, ZoomIn, Refresh, WarningFilled, MagicStick, CopyDocument, MoreFilled
} from '@element-plus/icons-vue'
import draggable from 'vuedraggable'
import DataFactorySelector from '@/components/DataFactorySelector.vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

import {
  getUiProjects,
  getElements,
  createTestCase,
  updateTestCase,
  deleteTestCase as deleteTestCaseApi,
  batchDeleteTestCases as batchDeleteTestCasesApi,
  getTestCases,
  runTestCase as runTestCaseApi,
  copyTestCase as copyTestCaseApi,
  getLocatorStrategies
} from '@/api/ui_automation'
import { getVariableFunctions } from '@/api/data-factory'
import { resolveUiProjectId, saveUiProjectId } from '@/utils/uiAutomationProject'

// 响应式数据
const projects = ref([])
const projectId = ref('')
const testCases = ref([])
const selectedTestCase = ref(null)
const currentSteps = ref([])
const availableElements = ref([])
const searchKeyword = ref('')
const selectedCaseIds = ref([])
const showCreateDialog = ref(false)
const editingTestCase = ref(null)
const executionResult = ref(null)
const resultActiveTab = ref('logs')
const allStepsExpanded = ref(false)
const showSteps = ref(true)
const showScreenshotPreview = ref(false)
const currentScreenshot = ref(null)
const isRunning = ref(false)
const selectedEngine = ref('playwright')  // 默认使用Playwright
const selectedBrowser = ref('chrome')  // 默认使用Chrome
const headlessMode = ref(false)  // 默认使用有头模式
const showVariableHelper = ref(false)
const currentEditingStep = ref(null)
const currentEditingField = ref('')
const showDataFactorySelector = ref(false)
const currentStepForDataFactory = ref(null)
const currentFieldForDataFactory = ref('')
const variableCategories = ref([])
const loading = ref(false)



// 表单数据
const testCaseForm = reactive({
  name: '',
  description: '',
  priority: 'medium'
})

// 计算属性
const filteredTestCases = computed(() => {
  if (!searchKeyword.value) return testCases.value
  return testCases.value.filter(tc =>
    tc.name.includes(searchKeyword.value) ||
    tc.description?.includes(searchKeyword.value)
  )
})

// 解析执行日志
const parsedExecutionLogs = computed(() => {
  if (!executionResult.value || !executionResult.value.logs) return []
  try {
    return typeof executionResult.value.logs === 'string'
      ? JSON.parse(executionResult.value.logs)
      : executionResult.value.logs
  } catch (e) {
    console.error('解析执行日志失败:', e)
    return []
  }
})

// 方法定义
const loadProjects = async () => {
  try {
    const response = await getUiProjects({ page_size: 100 })
    projects.value = response.data.results || response.data
  } catch (error) {
    ElMessage.error('获取项目列表失败')
    console.error('获取项目列表失败:', error)
  }
}

const loadTestCases = async () => {
  if (!projectId.value) {
    testCases.value = []
    return
  }

  try {
    const response = await getTestCases({ project: projectId.value })
    testCases.value = response.data.results || response.data
  } catch (error) {
    console.error('获取测试用例失败:', error)
  }
}

const loadElements = async () => {
  if (!projectId.value) {
    availableElements.value = []
    return
  }

  try {
    const response = await getElements({ project: projectId.value })
    availableElements.value = response.data.results || response.data
  } catch (error) {
    console.error('获取元素列表失败:', error)
  }
}

const onProjectSelectChange = async () => {
  saveUiProjectId(projectId.value)
  await onProjectChange()
}

const onProjectChange = async () => {
  selectedTestCase.value = null
  selectedCaseIds.value = []
  currentSteps.value = []
  executionResult.value = null

  await Promise.all([
    loadTestCases(),
    loadElements()
  ])
}

const selectTestCase = (testCase) => {
  // 如果点击的是同一个用例，不做任何处理
  if (selectedTestCase.value && selectedTestCase.value.id === testCase.id) {
    return
  }

  selectedTestCase.value = testCase
  // 确保步骤数据格式正确，添加前端需要的字段
  if (testCase.steps && testCase.steps.length > 0) {
    currentSteps.value = testCase.steps.map(step => ({
      ...step,
      element_id: step.element || '',
      expanded: false
    }))
  } else {
    currentSteps.value = []
  }
  // 只有在切换到不同用例时才清空执行结果
  executionResult.value = null
  showSteps.value = true
}

const addStep = () => {
  const newStep = {
    id: Date.now(),
    action_type: 'click',
    element_id: '',
    input_value: '',
    wait_time: 1000,
    assert_type: 'textContains',
    assert_value: '',
    description: '',
    expanded: true
  }
  currentSteps.value.push(newStep)
}

const removeStep = (index) => {
  currentSteps.value.splice(index, 1)
}

const onStepsReorder = () => {
  // 步骤重新排序后的处理
  console.log('步骤已重新排序')
}

const onActionTypeChange = (step) => {
  // 根据操作类型重置相关参数
  if (step.action_type !== 'fill') {
    step.input_value = ''
  }
  if (step.action_type !== 'wait') {
    step.wait_time = 1000
  }
  if (step.action_type !== 'assert') {
    step.assert_type = 'textContains'
    step.assert_value = ''
  }
}

const onElementChange = (step) => {
  // 元素变化时的处理
  const element = availableElements.value.find(e => e.id === step.element_id)
  if (element && !step.description) {
    step.description = `${getActionTypeText(step.action_type)}${element.name}`
  }
}

const needsInputValue = (actionType) => {
  return ['fill', 'switchTab'].includes(actionType)
}

const needsWaitTime = (actionType) => {
  return ['wait', 'waitFor'].includes(actionType)
}

const needsElement = (actionType) => {
  return !['wait', 'switchTab', 'screenshot'].includes(actionType)
}

const expandAllSteps = () => {
  allStepsExpanded.value = !allStepsExpanded.value
  currentSteps.value.forEach(step => {
    step.expanded = allStepsExpanded.value
  })
}

const saveTestCase = async () => {
  if (!selectedTestCase.value) return

  try {
    const updateData = {
      ...selectedTestCase.value,
      steps: currentSteps.value
    }

    await updateTestCase(selectedTestCase.value.id, updateData)
    ElMessage.success(t('uiAutomation.testCase.save.success'))

    // 更新本地数据
    const index = testCases.value.findIndex(tc => tc.id === selectedTestCase.value.id)
    if (index !== -1) {
      testCases.value[index] = { ...updateData }
      selectedTestCase.value = { ...updateData }
    }
  } catch (error) {
      console.error('保存测试用例失败:', error)
      ElMessage.error(t('uiAutomation.testCase.save.failed'))
    }
}

const runTestCase = async (testCase) => {
  isRunning.value = true
  try {
    const modeText = headlessMode.value ? t('uiAutomation.testCase.runMode.headless') : t('uiAutomation.testCase.runMode.headed')
    ElMessage.info(t('uiAutomation.testCase.run.start', { engine: selectedEngine.value.toUpperCase(), browser: selectedBrowser.value.toUpperCase(), mode: modeText }))

    const response = await runTestCaseApi(testCase.id, {
      project_id: projectId.value,
      engine: selectedEngine.value,
      browser: selectedBrowser.value,
      headless: headlessMode.value
    })

    executionResult.value = response.data
    resultActiveTab.value = 'logs'
    showSteps.value = false  // 自动切换到结果视图

    if (response.data.success) {
      ElMessage.success(t('uiAutomation.testCase.run.success'))
    } else {
      ElMessage.error(t('uiAutomation.testCase.run.failed'))
      // 如果有截图，自动切换到截图标签页
      if (response.data.screenshots && response.data.screenshots.length > 0) {
        resultActiveTab.value = 'screenshots'
      }
    }
  } catch (error) {
    console.error('执行测试用例失败:', error)

    // 即使出错也要设置执行结果,显示错误信息
    const errorMessage = error.response?.data?.message || error.message || '执行失败'
    const errorLogs = error.response?.data?.logs || `测试用例执行出错\n\n错误信息: ${errorMessage}`

    // 格式化错误信息为统一的对象格式
    const errors = error.response?.data?.errors || [{
      message: errorMessage,
      details: error.stack || '',
      step_number: null,
      action_type: '',
      element: '',
      description: ''
    }]

    executionResult.value = {
      success: false,
      logs: errorLogs,
      screenshots: error.response?.data?.screenshots || [],
      execution_time: 0,
      errors: errors
    }
    resultActiveTab.value = 'logs'
    showSteps.value = false  // 切换到结果视图显示错误

    ElMessage.error(t('uiAutomation.testCase.run.failedWithMessage', { message: errorMessage }))
  } finally {
    isRunning.value = false
  }
}

const toggleView = () => {
  showSteps.value = !showSteps.value
}

const editTestCase = (testCase) => {
  editingTestCase.value = testCase
  testCaseForm.name = testCase.name
  testCaseForm.description = testCase.description || ''
  testCaseForm.priority = testCase.priority || 'medium'
  showCreateDialog.value = true
}

const toggleCaseSelect = (id, checked) => {
  if (checked) {
    if (!selectedCaseIds.value.includes(id)) {
      selectedCaseIds.value.push(id)
    }
  } else {
    selectedCaseIds.value = selectedCaseIds.value.filter((x) => x !== id)
  }
}

const onCaseCommand = (cmd, testCase) => {
  if (cmd === 'run') runTestCase(testCase)
  else if (cmd === 'edit') editTestCase(testCase)
  else if (cmd === 'copy') copyTestCase(testCase)
  else if (cmd === 'delete') deleteTestCase(testCase)
}

const deleteTestCase = async (testCase) => {
  if (!testCase?.id) return
  try {
    await ElMessageBox.confirm(
      t('uiAutomation.testCase.delete.confirm', { name: testCase.name }),
      t('uiAutomation.testCase.delete.title'),
      {
        confirmButtonText: t('uiAutomation.common.confirm'),
        cancelButtonText: t('uiAutomation.common.cancel'),
        type: 'warning'
      }
    )

    await deleteTestCaseApi(testCase.id)
    ElMessage.success(t('uiAutomation.testCase.delete.success'))

    // 从列表中移除
    const index = testCases.value.findIndex(tc => tc.id === testCase.id)
    if (index !== -1) {
      testCases.value.splice(index, 1)
    }
    selectedCaseIds.value = selectedCaseIds.value.filter((x) => x !== testCase.id)

    // 如果删除的是当前选中的用例，清空选择
    if (selectedTestCase.value?.id === testCase.id) {
      selectedTestCase.value = null
      currentSteps.value = []
      executionResult.value = null
    }
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      console.error('删除测试用例失败:', error)
      const msg = error?.response?.data?.error
        || error?.response?.data?.detail
        || t('uiAutomation.testCase.messages.deleteFailed')
        || '删除失败'
      ElMessage.error(typeof msg === 'string' ? msg : '删除失败')
    }
  }
}

const batchDeleteTestCases = async () => {
  const ids = [...selectedCaseIds.value]
  if (!ids.length) return
  try {
    await ElMessageBox.confirm(
      t('uiAutomation.testCase.delete.batchConfirm', { count: ids.length })
        || `确定删除选中的 ${ids.length} 个测试用例吗？此操作不可恢复。`,
      t('uiAutomation.testCase.delete.title'),
      {
        confirmButtonText: t('uiAutomation.common.confirm'),
        cancelButtonText: t('uiAutomation.common.cancel'),
        type: 'warning'
      }
    )
    await batchDeleteTestCasesApi(ids)
    ElMessage.success(t('uiAutomation.testCase.delete.success'))
    testCases.value = testCases.value.filter((tc) => !ids.includes(tc.id))
    if (selectedTestCase.value && ids.includes(selectedTestCase.value.id)) {
      selectedTestCase.value = null
      currentSteps.value = []
      executionResult.value = null
    }
    selectedCaseIds.value = []
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      console.error('批量删除测试用例失败:', error)
      const msg = error?.response?.data?.error
        || error?.response?.data?.detail
        || t('uiAutomation.testCase.messages.deleteFailed')
        || '删除失败'
      ElMessage.error(typeof msg === 'string' ? msg : '删除失败')
    }
  }
}

const copyTestCase = async (testCase) => {
  try {
    await ElMessageBox.confirm(
      t('uiAutomation.testCase.copy.confirm', { name: testCase.name }),
      t('uiAutomation.testCase.copy.title'),
      {
        confirmButtonText: t('uiAutomation.common.confirm'),
        cancelButtonText: t('uiAutomation.common.cancel'),
        type: 'info'
      }
    )

    const response = await copyTestCaseApi(testCase.id)
    ElMessage.success(t('uiAutomation.testCase.copy.success'))

    // 找到原用例的位置
    const index = testCases.value.findIndex(tc => tc.id === testCase.id)
    if (index !== -1) {
      // 在原用例下方插入新用例
      testCases.value.splice(index + 1, 0, response.data)
    } else {
      // 如果找不到，就添加到末尾
      testCases.value.push(response.data)
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('复制测试用例失败:', error)
      ElMessage.error('复制失败')
    }
  }
}

// 加载变量函数
const loadVariableFunctions = async () => {
  try {
    loading.value = true
    console.log('开始加载变量函数...')
    const apiResponse = await getVariableFunctions()
    console.log('变量函数响应:', apiResponse)
    console.log('变量函数响应.data:', apiResponse.data)
    
    // 检查不同可能的数据结构
    let functionsData = []
    if (apiResponse && apiResponse.data) {
      if (Array.isArray(apiResponse.data)) {
        // 后端返回的是数组，直接使用
        functionsData = apiResponse.data
      } else if (apiResponse.data.functions) {
        // 如果data中有functions字段，使用它
        functionsData = apiResponse.data.functions
      } else if (typeof apiResponse.data === 'object') {
        // 如果data是对象但没有functions字段，假设整个对象就是按分类组织的函数
        functionsData = apiResponse.data
      }
    }
    
    console.log('处理后的函数数据:', functionsData)
    
    // 处理函数数据，按分类组织
    const grouped = {}
    
    if (Array.isArray(functionsData)) {
      // 如果是数组格式
      functionsData.forEach(func => {
        const category = func.category || '未分类'
        if (!grouped[category]) {
          grouped[category] = []
        }
        grouped[category].push({
          name: func.name,
          syntax: func.syntax,
          desc: func.description || func.desc || '',
          example: func.example
        })
      })
    } else if (typeof functionsData === 'object') {
      // 如果是按分类组织的对象格式
      for (const [category, funcs] of Object.entries(functionsData)) {
        if (Array.isArray(funcs)) {
          grouped[category] = funcs.map(func => ({
            name: func.name,
            syntax: func.syntax,
            desc: func.description || func.desc || '',
            example: func.example
          }))
        }
      }
    }
    
    console.log('按分类组织后的函数:', grouped)
    
    // 定义固定的分类顺序
    const categoryOrder = ['随机数', '测试数据', '字符串', '编码转换', '加密', '时间日期', 'Crontab', '未分类']
    
    // 按固定顺序构建分类列表
    const orderedCategories = []
    categoryOrder.forEach(category => {
      if (grouped[category]) {
        orderedCategories.push({
          label: category,
          variables: grouped[category]
        })
        delete grouped[category]
      }
    })
    
    // 添加剩余的分类
    for (const [category, funcs] of Object.entries(grouped)) {
      orderedCategories.push({
        label: category,
        variables: funcs
      })
    }
    
    console.log('最终的分类列表:', orderedCategories)
    variableCategories.value = orderedCategories
  } catch (error) {
    console.error('加载变量函数失败:', error)
    ElMessage.error('加载变量函数失败，使用本地数据')
    useLocalVariableCategories()
  } finally {
    loading.value = false
  }
}

// 使用本地变量分类数据作为 fallback
const useLocalVariableCategories = () => {
  variableCategories.value = [
    {
      label: t('uiAutomation.testCase.variableCategory.randomNumber'),
      variables: [
        { name: 'random_int', syntax: '${random_int(min, max, count)}', desc: t('uiAutomation.testCase.variable.randomInt.desc'), example: '${random_int(100, 999, 1)}' },
        { name: 'random_float', syntax: '${random_float(min, max, precision, count)}', desc: t('uiAutomation.testCase.variable.randomFloat.desc'), example: '${random_float(0, 1, 2, 1)}' }
      ]
    },
    {
      label: t('uiAutomation.testCase.variableCategory.randomString'),
      variables: [
        { name: 'random_string', syntax: '${random_string(length, char_type, count)}', desc: t('uiAutomation.testCase.variable.randomString.desc'), example: '${random_string(8, "all", 1)}' }
      ]
    }
  ]
}

// 计算属性提供变量分类数据
const variableCategoriesComputed = computed(() => {
  return variableCategories.value.length > 0 ? variableCategories.value : [
    {
      label: t('uiAutomation.testCase.variableCategory.randomNumber'),
      variables: []
    }
  ]
})

const openVariableHelper = (step, field) => {
  console.log('TestCaseManager openVariableHelper 被调用, step:', step, 'field:', field)
  console.log('variableCategories.value:', variableCategories.value)
  console.log('variableCategories.value.length:', variableCategories.value.length)
  currentEditingStep.value = step
  currentEditingField.value = field
  showVariableHelper.value = true
  console.log('showVariableHelper.value:', showVariableHelper.value)
}

const openDataFactorySelector = (step, field) => {
  currentStepForDataFactory.value = step
  currentFieldForDataFactory.value = field
  showDataFactorySelector.value = true
}

const handleDataFactorySelect = (record) => {
  const step = currentStepForDataFactory.value
  const field = currentFieldForDataFactory.value
  
  if (record && record.output_data && step && field) {
    let valueToSet = ''
    
    if (typeof record.output_data === 'string') {
      valueToSet = record.output_data
    } else if (record.output_data.result) {
      valueToSet = record.output_data.result
    } else if (record.output_data.output_data) {
      valueToSet = record.output_data.output_data
    } else {
      valueToSet = JSON.stringify(record.output_data)
    }
    
    step[field] = valueToSet
    ElMessage.success(t('uiAutomation.testCase.messages.dataFactorySelected', { toolName: record.tool_name }))
  }
  
  showDataFactorySelector.value = false
}

const insertVariable = (variable) => {
  if (currentEditingStep.value && currentEditingField.value) {
    const example = variable.example
    const currentValue = currentEditingStep.value[currentEditingField.value] || ''
    
    // 简单起见，这里直接追加到末尾，或者如果为空则替换
    if (!currentValue) {
      currentEditingStep.value[currentEditingField.value] = example
    } else {
      currentEditingStep.value[currentEditingField.value] = currentValue + example
    }
    
    ElMessage.success(t('uiAutomation.testCase.messages.variableInserted', { name: variable.name }))
    showVariableHelper.value = false
  }
}

const saveTestCaseForm = async () => {
  if (!testCaseForm.name.trim()) {
    ElMessage.warning(t('uiAutomation.testCase.form.nameRequired'))
    return
  }

  try {
    const data = {
      name: testCaseForm.name,
      description: testCaseForm.description,
      priority: testCaseForm.priority,
      project: projectId.value,
      steps: []
    }

    if (editingTestCase.value) {
      // 编辑现有用例
      await updateTestCase(editingTestCase.value.id, data)
      ElMessage.success(t('uiAutomation.testCase.update.success'))

      // 更新本地数据
      const index = testCases.value.findIndex(tc => tc.id === editingTestCase.value.id)
      if (index !== -1) {
        testCases.value[index] = { ...testCases.value[index], ...data }
      }
    } else {
      // 创建新用例
      const response = await createTestCase(data)
      ElMessage.success(t('uiAutomation.testCase.create.success'))
      testCases.value.push(response.data)
    }

    showCreateDialog.value = false
    editingTestCase.value = null
    resetForm()
  } catch (error) {
    console.error('保存测试用例失败:', error)
    ElMessage.error(t('uiAutomation.testCase.save.failed'))
  }
}

const resetForm = () => {
  testCaseForm.name = ''
  testCaseForm.description = ''
  testCaseForm.priority = 'medium'
}

// 辅助方法
const getStatusTag = (status) => {
  const tagMap = {
    'draft': 'info',
    'ready': 'success',
    'running': 'warning',
    'passed': 'success',
    'failed': 'danger'
  }
  return tagMap[status] || 'info'
}

const getStatusText = (status) => {
  const textMap = {
    'draft': t('uiAutomation.testCase.status.draft'),
    'ready': t('uiAutomation.testCase.status.ready'),
    'running': t('uiAutomation.testCase.status.running'),
    'passed': t('uiAutomation.testCase.status.passed'),
    'failed': t('uiAutomation.testCase.status.failed')
  }
  return textMap[status] || t('uiAutomation.testCase.status.unknown')
}

const getActionTypeText = (actionType) => {
  const textMap = {
    'click': t('uiAutomation.testCase.actionType.click'),
    'fill': t('uiAutomation.testCase.actionType.fill'),
    'getText': t('uiAutomation.testCase.actionType.getText'),
    'waitFor': t('uiAutomation.testCase.actionType.waitFor'),
    'hover': t('uiAutomation.testCase.actionType.hover'),
    'scroll': t('uiAutomation.testCase.actionType.scroll'),
    'screenshot': t('uiAutomation.testCase.actionType.screenshot'),
    'assert': t('uiAutomation.testCase.actionType.assert'),
    'wait': t('uiAutomation.testCase.actionType.wait')
  }
  return textMap[actionType] || actionType
}

const formatTime = (timestamp) => {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  return date.toLocaleString()
}

// 获取操作类型文本
const getActionText = (actionType) => {
  const actionMap = {
    'click': t('uiAutomation.testCase.actionText.click'),
    'fill': t('uiAutomation.testCase.actionText.fill'),
    'getText': t('uiAutomation.testCase.actionText.getText'),
    'waitFor': t('uiAutomation.testCase.actionText.waitFor'),
    'hover': t('uiAutomation.testCase.actionText.hover'),
    'scroll': t('uiAutomation.testCase.actionText.scroll'),
    'screenshot': t('uiAutomation.testCase.actionText.screenshot'),
    'assert': t('uiAutomation.testCase.actionText.assert'),
    'wait': t('uiAutomation.testCase.actionText.wait')
  }
  return actionMap[actionType] || actionType
}

// 图片处理方法
const handleImageError = (event) => {
  const img = event.target
  const screenshotIndex = parseInt(img.dataset.index)
  if (executionResult.value && executionResult.value.screenshots) {
    executionResult.value.screenshots[screenshotIndex].error = true
    executionResult.value.screenshots[screenshotIndex].loaded = true
  }
}

const handleImageLoad = (event) => {
  const img = event.target
  const screenshotIndex = parseInt(img.dataset.index)
  if (executionResult.value && executionResult.value.screenshots) {
    executionResult.value.screenshots[screenshotIndex].loaded = true
    executionResult.value.screenshots[screenshotIndex].error = false
  }
}

const previewScreenshot = (screenshot) => {
  currentScreenshot.value = screenshot
  showScreenshotPreview.value = true
}

// 组件挂载
onMounted(async () => {
  console.log('TestCaseManager onMounted 开始执行...')
  await loadProjects()
  console.log('loadProjects 完成，准备加载变量函数...')
  await loadVariableFunctions()
  console.log('loadVariableFunctions 完成')

  if (projects.value.length > 0) {
    projectId.value = resolveUiProjectId(projects.value)
    await onProjectChange()
  }
})
</script>

<style scoped>
.test-case-manager {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f3f5f8;
  padding: 16px 20px 20px;
  box-sizing: border-box;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}

.page-title {
  margin: 0;
  font-size: 22px;
  font-weight: 650;
  color: #1f2a37;
  letter-spacing: -0.02em;
}

.page-subtitle {
  margin: 6px 0 0;
  font-size: 13px;
  color: #6b7280;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.main-content {
  flex: 1;
  min-height: 0;
  display: flex;
  gap: 14px;
  overflow: hidden;
}

.left-panel {
  width: 360px;
  flex-shrink: 0;
  background: #fff;
  border: 1px solid #e5e9f0;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
  overflow: hidden;
}

.panel-header {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px 14px 12px;
  border-bottom: 1px solid #eef1f5;
}

.panel-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.panel-title-row h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #1f2a37;
}

.case-count {
  min-width: 22px;
  height: 22px;
  padding: 0 7px;
  border-radius: 999px;
  background: #eef2ff;
  color: #4338ca;
  font-size: 12px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.panel-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.panel-header-actions .el-input {
  flex: 1;
}

.case-select {
  padding-top: 2px;
}

.test-case-list {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
}

.empty-cases {
  padding: 24px 8px;
}

.test-case-item {
  border: 1px solid #e8edf3;
  border-radius: 10px;
  margin-bottom: 8px;
  padding: 12px;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease, box-shadow 0.15s ease;
  background: #fff;
}

.test-case-item:hover {
  border-color: #bfdbfe;
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.06);
}

.test-case-item.active {
  border-color: #60a5fa;
  background: #f8fbff;
}

.case-header {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 8px;
}

.case-info {
  flex: 1;
  min-width: 0;
}

.case-name {
  margin: 0 0 4px;
  font-size: 14px;
  font-weight: 600;
  color: #111827;
  line-height: 1.35;
}

.case-description {
  margin: 0;
  color: #6b7280;
  font-size: 12px;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.more-btn {
  margin-top: -2px;
}

.case-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  font-size: 12px;
  color: #9ca3af;
  padding-left: 26px;
}

.meta-chip {
  display: inline-flex;
  align-items: center;
  padding: 1px 8px;
  border-radius: 999px;
  background: #f3f4f6;
  color: #4b5563;
}

.meta-chip.linked {
  background: #ecfdf5;
  color: #047857;
}

.update-time {
  margin-left: auto;
}

.right-panel {
  flex: 1;
  min-width: 0;
  background: #fff;
  border: 1px solid #e5e9f0;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
}

.test-case-detail {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  height: 100%;
}

.detail-header {
  padding: 14px 16px;
  border-bottom: 1px solid #eef1f5;
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: #fff;
}

.detail-title-block h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 650;
  color: #111827;
}

.detail-desc {
  margin: 4px 0 0;
  font-size: 13px;
  color: #6b7280;
}

.detail-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 14px;
  align-items: center;
  justify-content: space-between;
}

.action-group,
.run-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.no-selection {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.steps-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  margin: 12px 16px 16px;
  border: 1px solid #e8edf3;
  border-radius: 10px;
  background: #fafbfd;
  overflow: hidden;
}

.steps-container.has-steps {
  max-height: 50%;
}

.steps-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.steps-header h4 {
  margin: 0;
}

.steps-list {
  padding: 10px;
  padding-bottom: 20px;
}

.steps-scroll-container {
  overflow-y: auto;
  flex: 1;
  min-height: 0;
  padding: 10px;
  padding-right: 5px;
}

.steps-scroll-container::-webkit-scrollbar {
  width: 6px;
}

.steps-scroll-container::-webkit-scrollbar-track {
  background: #f5f5f5;
  border-radius: 3px;
}

.steps-scroll-container::-webkit-scrollbar-thumb {
  background: #ccc;
  border-radius: 3px;
}

.steps-scroll-container::-webkit-scrollbar-thumb:hover {
  background: #999;
}

.step-item {
  border: 1px solid #e6e6e6;
  border-radius: 6px;
  margin-bottom: 10px;
  background: white;
  transition: all 0.3s;
}

.step-item:hover {
  border-color: #409eff;
}

.step-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 15px;
  background: #fafafa;
  border-radius: 6px 6px 0 0;
}

.step-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.drag-handle {
  cursor: move;
  color: #999;
}

.step-number {
  background: #409eff;
  color: white;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: bold;
}

.step-right {
  display: flex;
  gap: 5px;
}

.step-content {
  padding: 15px;
  border-top: 1px solid #e6e6e6;
}

.step-param {
  display: flex;
  align-items: center;
  margin-bottom: 10px;
  gap: 10px;
}

.step-param label {
  width: 120px;
  font-weight: 500;
  color: #333;
}

.execution-result {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  border: 1px solid #e6e6e6;
  border-radius: 6px;
  background: white;
  overflow: hidden;
}

.execution-result.with-steps {
  margin-top: 0;
}

.execution-result .result-header {
  padding: 15px;
  border-bottom: 1px solid #e6e6e6;
  background: #fafafa;
  border-radius: 6px 6px 0 0;
}

.execution-result .result-content {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 15px;
}

.result-content {
  flex: 1;
  overflow: hidden;
}

/* 为el-tabs和el-tab-pane添加flex布局支持 */
.result-content :deep(.el-tabs) {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.result-content :deep(.el-tabs__content) {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.result-content :deep(.el-tab-pane) {
  height: 100%;
  overflow: auto;
}

/* .result-header 已在 .execution-result 中定义 */

.result-header h4 {
  margin: 0;
}

.logs-container {
  max-height: 500px;
  overflow-y: auto;
  background: #f5f7fa;
  padding: 15px;
  border-radius: 4px;
}

.log-item {
  margin-bottom: 15px;
  padding: 12px;
  background: white;
  border-radius: 4px;
  border-left: 3px solid #409eff;
}

.log-item:last-child {
  margin-bottom: 0;
}

.log-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.log-action {
  font-weight: 500;
  color: #606266;
}

.log-desc {
  color: #909399;
  font-size: 14px;
}

.log-error {
  display: flex;
  align-items: flex-start;  /* 改为 flex-start，适配多行文本 */
  gap: 8px;
  color: #f56c6c;
  background: #fef0f0;
  padding: 8px 12px;
  border-radius: 4px;
  margin-top: 8px;
  font-size: 14px;

  .error-message {
    margin: 0;
    padding: 0;
    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
    font-size: 13px;
    line-height: 1.6;
    white-space: pre-wrap;  /* 保留换行符和空格 */
    word-break: break-word;  /* 长单词换行 */
    flex: 1;
  }

  .el-icon {
    margin-top: 2px;  /* 图标与文本顶部对齐 */
    flex-shrink: 0;  /* 图标不缩小 */
  }
}

.screenshots-container {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
  padding: 10px;
}

.screenshot-item {
  display: flex;
  flex-direction: column;
  cursor: pointer;
  transition: transform 0.2s ease;
}

.screenshot-item:hover {
  transform: translateY(-4px);
}

.screenshot-wrapper {
  position: relative;
  width: 100%;
  min-height: 200px;
  background: #f5f5f5;
  border-radius: 8px;
  border: 2px solid #e6e6e6;
  overflow: hidden;
  transition: border-color 0.3s ease;
}

.screenshot-item:hover .screenshot-wrapper {
  border-color: #409eff;
}

.screenshot-wrapper img {
  width: 100%;
  height: auto;
  display: block;
  transition: opacity 0.3s ease;
}

.screenshot-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.3s ease;
}

.screenshot-item:hover .screenshot-overlay {
  opacity: 1;
}

.zoom-icon {
  font-size: 48px;
  color: white;
}

.screenshot-placeholder,
.screenshot-error {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  color: #999;
  font-size: 14px;
}

.screenshot-placeholder .el-icon,
.screenshot-error .el-icon {
  font-size: 32px;
  margin-bottom: 8px;
}

.screenshot-error {
  color: #f56c6c;
}

.screenshot-info {
  margin-top: 10px;
}

.screenshot-description {
  margin: 0 0 5px 0;
  font-size: 14px;
  font-weight: 500;
  color: #333;
  text-align: left;
}

.screenshot-meta {
  margin: 0 0 3px 0;
  font-size: 12px;
  color: #666;
  text-align: left;
}

.screenshot-time {
  margin: 0;
  font-size: 11px;
  color: #999;
  text-align: left;
}

/* 截图预览对话框样式 */
.screenshot-preview {
  display: flex;
  flex-direction: column;
}

.preview-info {
  margin-bottom: 20px;
  padding: 15px;
  background: #f5f7fa;
  border-radius: 6px;
}

.preview-info h4 {
  margin: 0 0 10px 0;
  font-size: 16px;
  color: #333;
}

.preview-info p {
  margin: 5px 0;
  font-size: 14px;
  color: #666;
}

.preview-image {
  display: flex;
  justify-content: center;
  align-items: center;
  background: #f5f5f5;
  border-radius: 8px;
  padding: 20px;
  max-height: 70vh;
  overflow: auto;
}

.preview-image img {
  max-width: 100%;
  height: auto;
  border-radius: 4px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.errors-container {
  padding: 10px;
  height: 100%;
  overflow-y: auto;
}

.error-item {
  background: #fff;
  border: 2px solid #f56c6c;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 15px;
}

.error-item:last-child {
  margin-bottom: 0;
}

.error-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 15px;
  padding-bottom: 15px;
  border-bottom: 1px solid #f5f5f5;
}

.error-header .el-tag {
  font-size: 16px;
  padding: 10px 15px;
  font-weight: 600;
}

.error-header .el-icon {
  margin-right: 5px;
}

.error-step {
  background: #fef0f0;
  color: #f56c6c;
  padding: 5px 12px;
  border-radius: 4px;
  font-weight: 600;
  font-size: 14px;
}

.error-meta {
  background: #f9f9f9;
  padding: 15px;
  border-radius: 6px;
  margin-bottom: 15px;
}

.meta-item {
  display: flex;
  align-items: flex-start;
  margin-bottom: 8px;
}

.meta-item:last-child {
  margin-bottom: 0;
}

.meta-label {
  font-weight: 600;
  color: #606266;
  min-width: 80px;
  margin-right: 10px;
}

.meta-value {
  color: #303133;
  flex: 1;
}

.error-details {
  background: #2d2d2d;
  border-radius: 6px;
  overflow: hidden;
}

.details-header {
  background: #1e1e1e;
  color: #fff;
  padding: 10px 15px;
  font-weight: 600;
  font-size: 14px;
  border-bottom: 1px solid #3d3d3d;
}

.details-content {
  color: #ff6b6b;
  padding: 15px;
  margin: 0;
  font-family: 'Courier New', Courier, monospace;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-wrap: break-word;
  max-height: 400px;
  overflow-y: auto;
}

.details-content::-webkit-scrollbar {
  width: 6px;
}

.details-content::-webkit-scrollbar-track {
  background: #1e1e1e;
}

.details-content::-webkit-scrollbar-thumb {
  background: #555;
  border-radius: 3px;
}

.details-content::-webkit-scrollbar-thumb:hover {
  background: #777;
}

.no-selection {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.data-factory-btn {
  background-color: #409eff !important;
  border-color: #409eff !important;
  color: white !important;
}

.data-factory-btn:hover {
  background-color: #66b1ff !important;
  border-color: #66b1ff !important;
}

.variable-helper-btn {
  background-color: #67c23a;
  border-color: #67c23a;
  color: white;
}

.variable-helper-btn:hover {
  background-color: #5daf34;
  border-color: #5daf34;
}
</style>