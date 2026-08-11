<template>
    <div class="ui-test-scene-builder">
        <div class="page-header">
            <h3>{{ $t('appAutomation.sceneBuilder.header.title') }}</h3>
            <div class="header-actions">
                <el-button
                    type="primary"
                    size="small"
                    :icon="Check"
                    :loading="saving"
                    @click="saveScene"
                >
                    {{ $t('appAutomation.sceneBuilder.header.saveCase') }}
                </el-button>
                <el-button size="small" :icon="Refresh" @click="resetScene">
                    {{ $t('appAutomation.common.reset') }}
                </el-button>
            </div>
        </div>

        <el-card class="scene-config">
            <el-form :model="sceneForm" label-width="120px" size="small">
                <el-row :gutter="16">
                    <el-col :span="8">
                        <el-form-item :label="$t('appAutomation.sceneBuilder.form.sceneName')" required>
                            <el-input
                                v-model.trim="sceneForm.name"
                                :placeholder="$t('appAutomation.sceneBuilder.form.sceneNamePlaceholder')"
                                clearable
                            />
                        </el-form-item>
                    </el-col>
                    <el-col :span="8">
                        <el-form-item :label="$t('appAutomation.sceneBuilder.form.belongProject')">
                            <el-select v-model="sceneForm.project" :placeholder="$t('appAutomation.sceneBuilder.form.pleaseSelectProject')" clearable filterable style="width:100%">
                                <el-option v-for="p in projectList" :key="p.id" :label="p.name" :value="p.id" />
                            </el-select>
                        </el-form-item>
                    </el-col>
                    <el-col :span="8">
                        <el-form-item :label="$t('appAutomation.sceneBuilder.form.sceneDescription')">
                            <el-input
                                v-model.trim="sceneForm.description"
                                :placeholder="$t('appAutomation.sceneBuilder.form.optional')"
                                clearable
                            />
                        </el-form-item>
                    </el-col>
                </el-row>
                <el-row :gutter="16">
                    <el-col :span="24">
                        <el-form-item :label="$t('appAutomation.sceneBuilder.form.sceneVariables')">
                            <div class="scene-variables">
                                <div
                                    v-for="(item, index) in sceneVariables"
                                    :key="`var_${index}`"
                                    class="scene-variable-item"
                                >
                                    <el-input
                                        v-model.trim="item.name"
                                        :placeholder="$t('appAutomation.sceneBuilder.form.variableName')"
                                        size="small"
                                    />
                                    <el-select v-model="item.scope" :placeholder="$t('appAutomation.sceneBuilder.form.scopePlaceholder')" size="small">
                                        <el-option label="local" value="local" />
                                        <el-option label="global" value="global" />
                                    </el-select>
                                    <el-select v-model="item.type" :placeholder="$t('appAutomation.sceneBuilder.form.typePlaceholder')" size="small">
                                        <el-option label="string" value="string" />
                                        <el-option label="number" value="number" />
                                        <el-option label="boolean" value="boolean" />
                                        <el-option label="array" value="array" />
                                        <el-option label="object" value="object" />
                                    </el-select>
                                    <el-input
                                        v-model.trim="item.value"
                                        :placeholder="$t('appAutomation.sceneBuilder.form.defaultValue')"
                                        size="small"
                                    />
                                    <el-input
                                        v-model.trim="item.description"
                                        :placeholder="$t('appAutomation.sceneBuilder.form.descriptionPlaceholder')"
                                        size="small"
                                    />
                                    <el-button link size="small" @click="removeSceneVariable(index)">
                                        {{ $t('appAutomation.common.delete') }}
                                    </el-button>
                                </div>
                                <el-button link size="small" @click="addSceneVariable">
                                    + {{ $t('appAutomation.sceneBuilder.form.addVariable') }}
                                </el-button>
                            </div>
                        </el-form-item>
                    </el-col>
                </el-row>
                <el-row :gutter="16">
                    <el-col :span="10">
                        <el-form-item label="API_BASE_URL">
                            <el-input
                                v-model.trim="sceneRuntime.base_url"
                                placeholder="http://127.0.0.1:8000"
                                size="small"
                            />
                        </el-form-item>
                    </el-col>
                </el-row>
                <el-row :gutter="16">
                    <el-col :span="8">
                        <el-form-item :label="$t('appAutomation.sceneBuilder.form.retryTimes')">
                            <el-input
                                v-model.number="sceneRuntime.retry_times"
                                type="number"
                                placeholder="0"
                                size="small"
                            />
                        </el-form-item>
                    </el-col>
                    <el-col :span="8">
                        <el-form-item :label="$t('appAutomation.sceneBuilder.form.retryInterval')">
                            <el-input
                                v-model.number="sceneRuntime.retry_interval"
                                type="number"
                                placeholder="0.5"
                                size="small"
                            />
                        </el-form-item>
                    </el-col>
                </el-row>
            </el-form>
        </el-card>

        <el-row :gutter="16" class="scene-layout">
            <el-col :span="6">
                <el-card class="palette-card" shadow="never">
                    <template #header>
                        <div class="card-title">
                            <span>{{ $t('appAutomation.sceneBuilder.palette.title') }}</span>
                            <div class="palette-toolbar">
                                <el-button type="primary" size="small" :icon="Upload" @click="openPackageDialog">
                                    {{ $t('appAutomation.sceneBuilder.palette.importPackage') }}
                                </el-button>
                                <el-button type="success" size="small" :icon="Download" @click="openExportDialog">
                                    {{ $t('appAutomation.sceneBuilder.palette.exportPackage') }}
                                </el-button>
                            </div>
                        </div>
                    </template>
                    <el-tabs v-model="paletteTab" stretch>
                        <el-tab-pane :label="$t('appAutomation.sceneBuilder.palette.baseComponents')" name="base">
                            <draggable
                                class="palette-list"
                                :list="componentPalette"
                                :group="{ name: 'ui-components', pull: 'clone', put: false }"
                                :clone="cloneComponent"
                                :sort="false"
                                item-key="type"
                            >
                                <template #item="{ element }">
                                    <div
                                        class="palette-item"
                                    >
                                        <span class="palette-name">{{ element.name }}</span>
                                        <span class="palette-type">{{ element.type }}</span>
                                    </div>
                                </template>
                                <template #footer>
                                    <div v-if="componentPalette.length === 0" class="palette-empty">
                                        {{ $t('appAutomation.sceneBuilder.palette.noBaseComponents') }}
                                    </div>
                                </template>
                            </draggable>
                        </el-tab-pane>
                        <el-tab-pane :label="$t('appAutomation.sceneBuilder.palette.customComponents')" name="custom">
                            <draggable
                                class="palette-list"
                                :list="customComponentPalette"
                                :group="{ name: 'ui-components', pull: 'clone', put: false }"
                                :clone="cloneComponent"
                                :sort="false"
                                item-key="id"
                            >
                                <template #item="{ element }">
                                    <div
                                        class="palette-item"
                                    >
                                        <div class="palette-left">
                                            <span class="palette-name">{{ element.name }}</span>
                                            <span class="palette-type">{{ element.type }}</span>
                                        </div>
                                        <div class="palette-actions">
                                            <el-button link size="small" @click.stop="openEditCustomComponent(element)">
                                                {{ $t('appAutomation.common.edit') }}
                                            </el-button>
                                            <el-button
                                                link
                                                size="small"
                                                style="color: #f56c6c"
                                                @click.stop="deleteCustomComponent(element)"
                                            >
                                                {{ $t('appAutomation.common.delete') }}
                                            </el-button>
                                        </div>
                                    </div>
                                </template>
                                <template #footer>
                                    <div v-if="customComponentPalette.length === 0" class="palette-empty">
                                        {{ $t('appAutomation.sceneBuilder.palette.noCustomComponents') }}
                                    </div>
                                </template>
                            </draggable>
                        </el-tab-pane>
                    </el-tabs>
                </el-card>
            </el-col>

            <el-col :span="12">
                <el-card class="scene-card" shadow="never">
                    <template #header>
                        <div class="card-title">
                            <span>{{ $t('appAutomation.sceneBuilder.steps.title') }}</span>
                            <el-button
                                type="primary"
                                size="small"
                                :icon="FolderAdd"
                                :disabled="scenarioSteps.length === 0"
                                @click="openCustomComponentDialog"
                            >
                                {{ $t('appAutomation.sceneBuilder.steps.saveAsCustomComponent') }}
                            </el-button>
                        </div>
                    </template>
                    <div class="scene-hint" v-if="scenarioSteps.length === 0">
                        {{ $t('appAutomation.sceneBuilder.steps.dragHint') }}
                    </div>
                    <draggable
                        v-model="scenarioSteps"
                        class="scene-list"
                        :group="{ name: 'ui-components', pull: true, put: true }"
                        :animation="200"
                        item-key="id"
                    >
                        <template #item="{ element, index }">
                            <div class="scene-item-wrapper">
                                <div
                                    class="scene-item"
                                    :class="{
                                        active: selectedIndex === index && selectedSubIndex === null,
                                        'is-expanded': element._expanded
                                    }"
                                    @click="selectStep(index)"
                                >
                                    <div class="scene-item-main">
                                        <span class="scene-index">{{ index + 1 }}</span>
                                        <span class="scene-name">{{ element.name }}</span>
                                        <span class="scene-type">{{ element.type }}</span>
                                        <el-tag v-if="element.kind === 'custom'" size="small" type="info">{{ $t('appAutomation.sceneBuilder.custom') }}</el-tag>
                                    </div>
                                    <div class="scene-item-actions">
                                        <el-button
                                            v-if="element.kind === 'custom' && element.steps && element.steps.length"
                                            link
                                            size="small"
                                            @click.stop="toggleExpandCustomStep(index)"
                                        >
                                            {{ element._expanded ? $t('appAutomation.sceneBuilder.steps.collapse') : $t('appAutomation.sceneBuilder.steps.expand') }}
                                        </el-button>
                                        <el-button
                                            link
                                            size="small"
                                            @click.stop="duplicateStep(index)"
                                        >
                                            {{ $t('appAutomation.sceneBuilder.steps.copy') }}
                                        </el-button>
                                        <el-button
                                            link
                                            size="small"
                                            @click.stop="removeStep(index)"
                                        >
                                            {{ $t('appAutomation.common.delete') }}
                                        </el-button>
                                    </div>
                                </div>
                                <!-- 自定义组件展开的子步骤 -->
                                <div v-if="element._expanded && element.steps" class="custom-sub-steps">
                                    <div
                                        v-for="(subStep, subIdx) in element.steps"
                                        :key="subStep.id || subIdx"
                                        class="scene-item sub-step-item"
                                        :class="{ active: selectedIndex === index && selectedSubIndex === subIdx }"
                                        @click.stop="selectSubStep(index, subIdx)"
                                    >
                                        <div class="scene-item-main">
                                            <span class="scene-index sub-index">{{ Number(index) + 1 }}.{{ Number(subIdx) + 1 }}</span>
                                            <span class="scene-name">{{ subStep.name || subStep.type }}</span>
                                            <span class="scene-type">{{ subStep.type }}</span>
                                        </div>
                                        <div class="scene-item-actions">
                                            <el-button link size="small" @click.stop="duplicateSubStep(index, subIdx)">{{ $t('appAutomation.sceneBuilder.steps.copy') }}</el-button>
                                            <el-button link size="small" @click.stop="removeSubStep(index, subIdx)">{{ $t('appAutomation.common.delete') }}</el-button>
                                        </div>
                                    </div>
                                    <div class="sub-step-toolbar">
                                        <el-button size="small" type="primary" link @click.stop="addSubStep(index)">
                                            + {{ $t('appAutomation.sceneBuilder.steps.addSubStep') }}
                                        </el-button>
                                    </div>
                                </div>
                            </div>
                        </template>
                    </draggable>
                </el-card>
            </el-col>

            <el-col :span="6">
                <el-card class="config-card" shadow="never">
                    <template #header>
                        <div class="card-title">
                            {{ $t('appAutomation.sceneBuilder.config.title') }}
                            <el-button
                                type="success"
                                size="small"
                                :icon="Camera"
                                style="margin-left: auto;"
                                @click="openCaptureElementDialog"
                            >
                                {{ $t('appAutomation.sceneBuilder.config.createElementTool') }}
                            </el-button>
                        </div>
                    </template>
                    <div v-if="!activeStep" class="config-empty">
                        {{ $t('appAutomation.sceneBuilder.config.selectStepHint') }}
                    </div>
                    <!-- 选中自定义组件父级时提示展开编辑 -->
                    <div v-else-if="activeParentStep && activeParentStep.kind === 'custom' && selectedSubIndex === null" class="config-form">
                        <el-form label-width="110px" size="small">
                            <el-form-item :label="$t('appAutomation.sceneBuilder.config.stepName')">
                                <el-input v-model.trim="activeParentStep.name" />
                            </el-form-item>
                            <el-form-item :label="$t('appAutomation.sceneBuilder.config.componentType')">
                                <el-input :model-value="activeParentStep.type" disabled />
                            </el-form-item>
                            <el-form-item :label="$t('appAutomation.sceneBuilder.config.subStepCount')">
                                <span>{{ $t('appAutomation.sceneBuilder.config.subStepCountValue', { count: (activeParentStep.steps || []).length }) }}</span>
                            </el-form-item>
                            <el-alert
                                type="info"
                                :closable="false"
                                style="margin-top: 8px;"
                            >
                                {{ $t('appAutomation.sceneBuilder.config.customParentHint') }}
                            </el-alert>
                        </el-form>
                    </div>
                    <div v-else class="config-form">
                        <el-form :model="activeStep" label-width="110px" size="small">
                            <el-form-item :label="$t('appAutomation.sceneBuilder.config.stepName')">
                                <el-input v-model.trim="activeStep.name" />
                            </el-form-item>


                            <div class="variable-hint">
                                <span>{{ $t('appAutomation.sceneBuilder.config.variableHint') }}</span><span v-pre>{{local.xxx}} / {{global.xxx}} / {{outputs.last.xxx}} / {{steps.step_id.xxx}}</span>
                            </div>
                            <div v-if="activeStep && activeStep.type === 'image_exists_click'" class="variable-hint hint-danger">
                                {{ $t('appAutomation.sceneBuilder.config.logicImageExistsClick') }}
                            </div>
                            <div v-if="activeStep && activeStep.type === 'image_exists_click_chain'" class="variable-hint hint-danger">
                                {{ $t('appAutomation.sceneBuilder.config.logicImageExistsClickChain') }}
                            </div>
                            <div v-if="activeStep && activeStep.type === 'foreach_assert'" class="variable-hint hint-danger">
                                {{ $t('appAutomation.sceneBuilder.config.logicForeachAssert') }}
                            </div>
                            <div v-if="activeStep && activeStep.type === 'api_request'" class="api-template-block">
                                <div class="tool-hint">{{ $t('appAutomation.sceneBuilder.config.apiTemplateTitle') }}</div>
                                <div class="template-list">
                                    <div v-for="item in apiRequestTemplates" :key="item.name" class="template-item">
                                        <span class="template-name">{{ item.name }}</span>
                                        <div class="template-actions">
                                            <el-button link size="small" @click="applyApiRequestTemplate(item, activeStep)">
                                                {{ $t('appAutomation.sceneBuilder.config.use') }}
                                            </el-button>
                                        </div>
                                    </div>
                                    <div v-if="apiRequestTemplates.length === 0" class="tool-hint">{{ $t('appAutomation.sceneBuilder.config.noTemplate') }}</div>
                                </div>
                            </div>
                            <!-- 统一的字段分组显示 -->
                            <template v-if="schemaFields.length > 0">
                                <div
                                    v-for="group in getFieldGroups()"
                                    :key="group.key"
                                    class="field-group"
                                >
                                    <div class="group-header">
                                        <span class="group-title">{{ group.title }}</span>
                                        <!-- 定位类分组显示选择按钮 -->
                                        <el-button
                                            v-if="group.key !== 'other'"
                                            type="primary"
                                            size="small"
                                            @click="openElementSelector(group.key)"
                                        >
                                            <el-icon><Link /></el-icon>
                                            {{ linkedElements[group.key] ? $t('appAutomation.sceneBuilder.config.changeElement') : $t('appAutomation.sceneBuilder.config.selectElement') }}
                                        </el-button>
                                    </div>

                                    <!-- 关联状态提示 -->
                                    <el-alert
                                        v-if="linkedElements[group.key]"
                                        type="success"
                                        :closable="false"
                                        class="element-linked-alert"
                                    >
                                        {{ $t('appAutomation.sceneBuilder.config.linkedElement', { name: linkedElements[group.key].name, type: linkedElements[group.key].type }) }}
                                        <el-button
                                            link
                                            type="danger"
                                            @click="clearLinkedElement(group.key)"
                                            style="margin-left: 10px;"
                                        >
                                            {{ $t('appAutomation.sceneBuilder.config.clear') }}
                                        </el-button>
                                    </el-alert>

                                    <!-- 字段列表 -->
                                    <el-form-item
                                        v-for="field in group.fields"
                                        :key="field"
                                        :label="getFieldLabel(field)"
                                        :required="schemaRequired.includes(field)"
                                    >
                                        <el-input
                                            v-if="field === 'expected_list'"
                                            type="textarea"
                                            :rows="4"
                                            :model-value="getExpectedListValue(activeStep && activeStep.config)"
                                            :placeholder="getFieldPlaceholder(field)"
                                            @update:model-value="updateExpectedList(activeStep.config, $event)"
                                        />
                                        <el-input
                                            v-else-if="isJsonField(field)"
                                            type="textarea"
                                            :rows="getJsonFieldRows(field)"
                                            :value="getJsonFieldValue(activeStep && activeStep.config, field)"
                                            :placeholder="getFieldPlaceholder(field)"
                                            @input="updateJsonField(activeStep.config, field, $event)"
                                        />
                                        <el-select
                                            v-else-if="getFieldOptions(field).length"
                                            v-model="activeStep.config[field]"
                                            :placeholder="$t('appAutomation.sceneBuilder.config.pleaseSelect')"
                                            :filterable="isImageScopeField(field)"
                                        >
                                            <el-option
                                                v-for="option in getFieldOptions(field)"
                                                :key="option.value"
                                                :label="option.label"
                                                :value="option.value"
                                            />
                                        </el-select>
                                        <el-switch
                                            v-else-if="getFieldType(field) === 'boolean'"
                                            v-model="activeStep.config[field]"
                                        />
                                        <el-input-number
                                            v-else-if="getFieldType(field) === 'number'"
                                            v-model="activeStep.config[field]"
                                            :min="getFieldNumberRule(field).min"
                                            :max="getFieldNumberRule(field).max"
                                            :step="getFieldNumberRule(field).step"
                                            controls-position="right"
                                        />
                                        <el-input
                                            v-else
                                            v-model.trim="activeStep.config[field]"
                                            :placeholder="getFieldPlaceholder(field)"
                                        />
                                    </el-form-item>
                                </div>
                            </template>

                            <!-- 无配置字段 -->
                            <div v-else class="config-empty">{{ $t('appAutomation.sceneBuilder.config.noSchema') }}</div>
                        </el-form>
                    </div>
                </el-card>
            </el-col>
        </el-row>

        <!-- 从设备创建元素对话框 -->
        <CaptureElementDialog 
            v-model="captureElementDialogVisible"
            @success="handleElementCreated"
        />

        <el-dialog
            :title="$t('appAutomation.sceneBuilder.dialog.importPackage')"
            v-model="packageDialogVisible"
            width="520px"
            :close-on-click-modal="false"
            @close="resetPackageDialog"
        >
            <el-form label-width="110px" size="small">
                <el-form-item :label="$t('appAutomation.sceneBuilder.dialog.overwriteExisting')">
                    <el-switch v-model="packageOverwrite" />
                </el-form-item>
                <el-form-item :label="$t('appAutomation.sceneBuilder.dialog.selectFile')">
                    <el-upload
                        :show-file-list="false"
                        :http-request="handlePackageUpload"
                        accept=".json,.yaml,.yml"
                    >
                        <el-button size="small" type="primary" :loading="packageUploading">
                            {{ $t('appAutomation.sceneBuilder.dialog.selectPackage') }}
                        </el-button>
                        <template #tip>
                            <div class="el-upload__tip">{{ $t('appAutomation.sceneBuilder.dialog.supportedFormats') }}</div>
                        </template>
                    </el-upload>
                </el-form-item>
                <el-divider></el-divider>
                <div class="package-title">{{ $t('appAutomation.sceneBuilder.dialog.importedPackages') }}</div>
                <div class="package-list" v-loading="packageLoading">
                    <div v-for="item in packageList" :key="item.id" class="package-item">
                        <div class="package-name">{{ item.name }}</div>
                        <div class="package-meta">
                            <span>{{ item.version || "-" }}</span>
                            <span>{{ item.updated_at || item.created_at || "-" }}</span>
                        </div>
                    </div>
                    <div v-if="packageList.length === 0" class="package-empty">{{ $t('appAutomation.sceneBuilder.dialog.noPackage') }}</div>
                </div>
            </el-form>
            <template #footer>
                <div class="dialog-footer">
                    <el-button @click="packageDialogVisible = false">{{ $t('appAutomation.common.close') }}</el-button>
                </div>
            </template>
        </el-dialog>

        <el-dialog
            :title="$t('appAutomation.sceneBuilder.dialog.exportPackage')"
            v-model="exportDialogVisible"
            width="420px"
            :close-on-click-modal="false"
            @close="resetExportDialog"
        >
            <el-form label-width="110px" size="small">
                <el-form-item :label="$t('appAutomation.sceneBuilder.dialog.exportIncludeDisabled')">
                    <el-switch v-model="packageIncludeDisabled" />
                </el-form-item>
            </el-form>
            <template #footer>
                <div class="dialog-footer">
                    <el-button type="primary" plain @click="exportPackage('yaml')">{{ $t('appAutomation.sceneBuilder.dialog.exportYaml') }}</el-button>
                    <el-button type="primary" plain @click="exportPackage('json')">{{ $t('appAutomation.sceneBuilder.dialog.exportJson') }}</el-button>
                    <el-button @click="exportDialogVisible = false">{{ $t('appAutomation.common.close') }}</el-button>
                </div>
            </template>
        </el-dialog>

        <el-dialog
            :title="customDialogTitle"
            v-model="customDialogVisible"
            width="50vw"
            :close-on-click-modal="false"
            @close="resetCustomDialog"
        >
            <el-form ref="customFormRef" :model="customForm" :rules="customRules" label-width="110px">
                <el-form-item :label="$t('appAutomation.sceneBuilder.dialog.componentName')" prop="name">
                    <el-input v-model.trim="customForm.name" :placeholder="$t('appAutomation.sceneBuilder.dialog.componentNamePlaceholder')" />
                </el-form-item>
                <el-form-item :label="$t('appAutomation.sceneBuilder.dialog.componentType')" prop="type">
                    <el-input v-model.trim="customForm.type" :placeholder="$t('appAutomation.sceneBuilder.dialog.componentTypePlaceholder')" />
                </el-form-item>
                <el-form-item :label="$t('appAutomation.sceneBuilder.dialog.componentDescription')">
                    <el-input v-model.trim="customForm.description" :placeholder="$t('appAutomation.sceneBuilder.dialog.optional')" />
                </el-form-item>
            </el-form>
            <!-- 组件步骤编辑区域（独占整行，不受 form label-width 约束） -->
            <div v-if="customDialogMode === 'edit'" class="custom-steps-section">
                <div class="custom-steps-label">{{ $t('appAutomation.sceneBuilder.dialog.componentSteps') }}</div>
                <div class="custom-edit-steps">
                        <div class="custom-step-list">
                            <div class="custom-step-toolbar">
                                <el-select v-model="editStepType" :placeholder="$t('appAutomation.sceneBuilder.dialog.selectBaseComponent')" size="small">
                                    <el-option
                                        v-for="item in componentPalette"
                                        :key="item.type"
                                        :label="item.name"
                                        :value="item.type"
                                    />
                                </el-select>
                                <el-button size="small" @click="addEditStep">{{ $t('appAutomation.common.add') }}</el-button>
                            </div>
                            <draggable
                                v-model="editingCustomSteps"
                                class="custom-step-items"
                                :group="{ name: 'ui-custom-edit', pull: false, put: false }"
                                :animation="200"
                                item-key="id"
                            >
                                <template #item="{ element, index }">
                                    <div
                                        class="custom-step-item scene-item"
                                        :class="{ active: editingSelectedIndex === index }"
                                        @click="selectEditStep(index)"
                                    >
                                        <div class="scene-item-main">
                                            <span class="scene-index">{{ index + 1 }}</span>
                                            <span class="scene-name">{{ element.name }}</span>
                                            <span class="scene-type">{{ element.type }}</span>
                                        </div>
                                        <div class="scene-item-actions">
                                            <el-button
                                                link
                                                size="small"
                                                @click.stop="duplicateEditStep(index)"
                                            >
                                                {{ $t('appAutomation.sceneBuilder.steps.copy') }}
                                            </el-button>
                                            <el-button
                                                link
                                                size="small"
                                                @click.stop="removeEditStep(index)"
                                            >
                                                {{ $t('appAutomation.common.delete') }}
                                            </el-button>
                                        </div>
                                    </div>
                                </template>
                            </draggable>
                        </div>
                        <div class="custom-step-config">
                            <div v-if="!editingActiveStep" class="config-empty">
                                {{ $t('appAutomation.sceneBuilder.config.selectStepHintEdit') }}
                            </div>
                            <div v-else class="config-form">
                                <el-form :model="editingActiveStep" label-width="110px" size="small">
                                    <el-form-item :label="$t('appAutomation.sceneBuilder.config.stepName')">
                                        <el-input v-model.trim="editingActiveStep.name" />
                                    </el-form-item>
                                    <div class="variable-hint">
                                        <span>{{ $t('appAutomation.sceneBuilder.config.variableHintShort') }}</span><span v-pre>{{local.xxx}} / {{global.xxx}}</span>
                                    </div>
                                    <div v-if="editingActiveStep && editingActiveStep.type === 'api_request'" class="api-template-block">
                                        <div class="tool-hint">{{ $t('appAutomation.sceneBuilder.config.apiTemplateTitle') }}</div>
                                        <div class="template-list">
                                            <div v-for="item in apiRequestTemplates" :key="item.name" class="template-item">
                                                <span class="template-name">{{ item.name }}</span>
                                                <div class="template-actions">
                                                    <el-button link size="small" @click="applyApiRequestTemplate(item, editingActiveStep)">
                                                        {{ $t('appAutomation.sceneBuilder.config.use') }}
                                                    </el-button>
                                                </div>
                                            </div>
                                            <div v-if="apiRequestTemplates.length === 0" class="tool-hint">{{ $t('appAutomation.sceneBuilder.config.noTemplate') }}</div>
                                        </div>
                                    </div>
                                    <!-- 分组显示（与场景步骤配置面板一致） -->
                                    <template v-if="editingSchemaFields.length > 0">
                                        <div
                                            v-for="group in getEditingFieldGroups()"
                                            :key="group.key"
                                            class="field-group"
                                        >
                                            <div class="group-header">
                                                <span class="group-title">{{ group.title }}</span>
                                                <el-button
                                                    v-if="group.key !== 'other'"
                                                    type="primary"
                                                    size="small"
                                                    @click="openElementSelector(group.key)"
                                                >
                                                    <el-icon><Link /></el-icon>
                                                    {{ linkedElements[group.key] ? $t('appAutomation.sceneBuilder.config.changeElement') : $t('appAutomation.sceneBuilder.config.selectElement') }}
                                                </el-button>
                                            </div>
                                            <el-alert
                                                v-if="linkedElements[group.key]"
                                                type="success"
                                                :closable="false"
                                                class="element-linked-alert"
                                            >
                                                {{ $t('appAutomation.sceneBuilder.config.linkedElement', { name: linkedElements[group.key].name, type: linkedElements[group.key].type }) }}
                                                <el-button
                                                    link
                                                    type="danger"
                                                    @click="clearLinkedElement(group.key)"
                                                    style="margin-left: 10px;"
                                                >
                                                    {{ $t('appAutomation.sceneBuilder.config.clear') }}
                                                </el-button>
                                            </el-alert>
                                            <el-form-item
                                                v-for="field in group.fields"
                                                :key="field"
                                                :label="getFieldLabel(field)"
                                                :required="editingSchemaRequired.includes(field)"
                                            >
                                                <el-input
                                                    v-if="field === 'expected_list'"
                                                    type="textarea"
                                                    :rows="4"
                                                    :model-value="getExpectedListValue(editingActiveStep && editingActiveStep.config)"
                                                    :placeholder="getFieldPlaceholder(field)"
                                                    @update:model-value="updateExpectedList(editingActiveStep.config, $event)"
                                                />
                                                <el-input
                                                    v-else-if="isJsonField(field)"
                                                    type="textarea"
                                                    :rows="getJsonFieldRows(field)"
                                                    :value="getJsonFieldValue(editingActiveStep && editingActiveStep.config, field)"
                                                    :placeholder="getFieldPlaceholder(field)"
                                                    @input="updateJsonField(editingActiveStep.config, field, $event)"
                                                />
                                                <el-select
                                                    v-else-if="getFieldOptions(field).length"
                                                    v-model="editingActiveStep.config[field]"
                                                    :placeholder="$t('appAutomation.sceneBuilder.config.pleaseSelect')"
                                                    :filterable="isImageScopeField(field)"
                                                >
                                                    <el-option
                                                        v-for="option in getFieldOptions(field)"
                                                        :key="option.value"
                                                        :label="option.label"
                                                        :value="option.value"
                                                    />
                                                </el-select>
                                                <el-switch
                                                    v-else-if="getFieldTypeForDef(editingActiveDef, field) === 'boolean'"
                                                    v-model="editingActiveStep.config[field]"
                                                />
                                                <el-input-number
                                                    v-else-if="getFieldTypeForDef(editingActiveDef, field) === 'number'"
                                                    v-model="editingActiveStep.config[field]"
                                                    :min="getFieldNumberRuleForDef(editingActiveDef, field).min"
                                                    :max="getFieldNumberRuleForDef(editingActiveDef, field).max"
                                                    :step="getFieldNumberRuleForDef(editingActiveDef, field).step"
                                                    controls-position="right"
                                                />
                                                <el-input
                                                    v-else
                                                    v-model.trim="editingActiveStep.config[field]"
                                                    :placeholder="getFieldPlaceholder(field)"
                                                />
                                            </el-form-item>
                                        </div>
                                    </template>
                                    <div v-else class="config-empty">{{ $t('appAutomation.sceneBuilder.config.noSchema') }}</div>
                                </el-form>
                            </div>
                        </div>
                    </div>
                </div>
            <template #footer>
                <div class="dialog-footer">
                    <el-button @click="customDialogVisible = false">{{ $t('appAutomation.common.cancel') }}</el-button>
                    <el-button type="primary" :loading="customSaving" @click="saveCustomComponent">{{ $t('appAutomation.common.save') }}</el-button>
                </div>
            </template>
        </el-dialog>

        <!-- 元素选择对话框 -->
        <el-dialog
            v-model="elementSelectorVisible"
            :title="$t('appAutomation.sceneBuilder.elementSelector.title')"
            width="1200px"
            destroy-on-close
        >
            <div class="element-selector-container">
                <!-- 筛选条件 -->
                <div class="element-selector-filter">
                    <el-space wrap>
                        <el-radio-group v-model="elementFilterType" @change="loadElementsForSelector">
                            <el-radio-button value="">{{ $t('appAutomation.common.all') }}</el-radio-button>
                            <el-radio-button value="image">{{ $t('appAutomation.sceneBuilder.elementSelector.image') }}</el-radio-button>
                            <el-radio-button value="pos">{{ $t('appAutomation.sceneBuilder.elementSelector.coordinate') }}</el-radio-button>
                            <el-radio-button value="region">{{ $t('appAutomation.sceneBuilder.elementSelector.region') }}</el-radio-button>
                        </el-radio-group>

                        <el-input
                            v-model="elementSearchKeyword"
                            :placeholder="$t('appAutomation.sceneBuilder.elementSelector.searchPlaceholder')"
                            style="width: 250px"
                            clearable
                            @change="loadElementsForSelector"
                        >
                            <template #prefix>
                                <el-icon><Search /></el-icon>
                            </template>
                        </el-input>
                    </el-space>
                </div>

                <!-- 元素列表 -->
                <el-table
                    :data="selectorElements"
                    border
                    v-loading="elementSelectorLoading"
                    max-height="450px"
                    highlight-current-row
                    @row-click="handleElementRowClick"
                >
                    <el-table-column prop="name" :label="$t('appAutomation.sceneBuilder.elementSelector.elementName')" width="200">
                        <template #default="{ row }">
                            <el-link type="primary">{{ row.name }}</el-link>
                        </template>
                    </el-table-column>

                    <el-table-column prop="element_type" :label="$t('appAutomation.sceneBuilder.elementSelector.type')" width="100">
                        <template #default="{ row }">
                            <el-tag :type="getTypeTagColor(row.element_type)">
                                {{ row.element_type_display }}
                            </el-tag>
                        </template>
                    </el-table-column>

                    <el-table-column :label="$t('appAutomation.sceneBuilder.elementSelector.imageCategory')" width="120">
                        <template #default="{ row }">
                            <el-tag v-if="row.element_type === 'image' && row.config?.image_category" type="info" size="small">
                                {{ row.config.image_category }}
                            </el-tag>
                            <span v-else style="color: #909399;">-</span>
                        </template>
                    </el-table-column>

                    <el-table-column prop="tags" :label="$t('appAutomation.sceneBuilder.elementSelector.tags')" width="180">
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

                    <el-table-column :label="$t('appAutomation.sceneBuilder.elementSelector.preview')" width="200" align="center">
                        <template #default="{ row }">
                            <div v-if="row.element_type === 'image'" class="preview-image">
                                <el-image
                                    :src="row.preview_url"
                                    fit="contain"
                                    style="width: 150px; height: 60px"
                                />
                            </div>
                            <div v-else-if="row.element_type === 'pos'" class="preview-pos">
                                <el-space :size="4">
                                    <el-tag type="primary" size="small">X: {{ row.config?.x }}</el-tag>
                                    <el-tag type="primary" size="small">Y: {{ row.config?.y }}</el-tag>
                                </el-space>
                            </div>
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

                    <el-table-column :label="$t('appAutomation.common.operation')" width="100" fixed="right">
                        <template #default="{ row }">
                            <div class="table-actions">
                                <el-button link type="primary" size="small" @click.stop="applyElement(row)">
                                    {{ $t('appAutomation.sceneBuilder.elementSelector.apply') }}
                                </el-button>
                            </div>
                        </template>
                    </el-table-column>
                </el-table>

                <!-- 分页 -->
                <el-pagination
                    v-model:current-page="elementCurrentPage"
                    v-model:page-size="elementPageSize"
                    :total="elementTotal"
                    :page-sizes="[10, 20, 50]"
                    layout="total, sizes, prev, pager, next"
                    @current-change="loadElementsForSelector"
                    @size-change="loadElementsForSelector"
                    style="margin-top: 15px; justify-content: flex-end"
                />
            </div>

            <template #footer>
                <el-button @click="elementSelectorVisible = false">{{ $t('appAutomation.common.close') }}</el-button>
            </template>
        </el-dialog>
    </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { Upload, Download, FolderAdd, DocumentCopy, Check, Search, Link, Refresh, Camera } from '@element-plus/icons-vue'
import draggable from "vuedraggable"
import CaptureElementDialog from '../elements/components/CaptureElementDialog.vue'
import {
  getComponents,
  getCustomComponents,
  createCustomComponent as apiCreateCustomComponent,
  updateCustomComponent as apiUpdateCustomComponent,
  deleteCustomComponent as apiDeleteCustomComponent,
  importComponentPackage,
  exportComponentPackage,
  getTestCaseDetail,
  createTestCase,
  updateTestCase,
  getAppElementList,
  getAppImageCategories,
  getDeviceList,
  getAppProjects
} from '@/api/app-automation'

// Route
const route = useRoute()
const router = useRouter()
const { t } = useI18n()

// Reactive state
const saving = ref(false)
const paletteTab = ref("base")
const projectList = ref([])
const sceneForm = ref({
    name: "",
    description: "",
    project: null
})
const sceneVariables = ref([])
const sceneRuntime = ref({
    base_url: "http://127.0.0.1:8000",
    retry_times: 0,
    retry_interval: 0.5
})
// 组件库初始化为空数组，完全从后端 API 加载
const componentPalette = ref([])
const defaultPalette = ref([])
const customComponentPalette = ref([])
const defaultCustomPalette = ref([])
const scenarioSteps = ref([])
const selectedIndex = ref(null)
const selectedSubIndex = ref(null)    // 当前选中的子步骤索引（展开编辑用）
const componentDefinitions = ref({})
const customComponentDefinitions = ref({})
const editingCaseId = ref(null)
const apiRequestTemplates = computed(() => [
    {
        name: t('appAutomation.sceneBuilder.config.vipInitTemplate'),
        config: {
            method: "POST",
            url: "/api/ui_test/configs/vip-setup/",
            headers: {
                "Content-Type": "application/json"
            },
            json: {
                user_id: "",
                vip_level: 16,
                level: 0,
                coin: 68510000000
            },
            timeout: 10,
            expected_status: 200,
            response_type: "json"
        }
    }
])
const customDialogVisible = ref(false)
const customSaving = ref(false)
const customDialogMode = ref("create")
const editingCustomId = ref(null)
const editingCustomSteps = ref([])
const editingSelectedIndex = ref(null)
const editStepType = ref("")
const customForm = ref({
    name: "",
    type: "",
    description: ""
})
const packageDialogVisible = ref(false)
const packageUploading = ref(false)
const packageOverwrite = ref(true)
const packageIncludeDisabled = ref(false)
const packageList = ref([])
const packageLoading = ref(false)
const exportDialogVisible = ref(false)
const captureElementDialogVisible = ref(false)
const customRules = computed(() => ({
    name: [{ required: true, message: t('appAutomation.sceneBuilder.dialog.rules.nameRequired'), trigger: "blur" }],
    type: [{ required: true, message: t('appAutomation.sceneBuilder.dialog.rules.typeRequired'), trigger: "blur" }]
}))

// 元素选择器相关状态
const elementSelectorVisible = ref(false)
const elementSelectorLoading = ref(false)
const selectorElements = ref([])
const elementFilterType = ref('')
const elementSearchKeyword = ref('')
const elementCurrentPage = ref(1)
const elementPageSize = ref(10)
const elementTotal = ref(0)
const imageCategoryOptions = ref([])  // 图片分类选项

// 关联元素信息追踪
const elementSelectorTarget = ref('') // 当前选择器的目标：'selector' | 'fallback' | 'click' | 'ocr' | 'start' | 'end' | 'target'
const linkedElements = ref({
    selector: null,  // 通用定位关联的元素: { id, name, type }
    fallback: null,  // 备用定位关联的元素
    click: null,     // 点击定位关联的元素
    ocr: null,       // OCR定位关联的元素
    start: null,     // 起始定位关联的元素
    end: null,       // 结束定位关联的元素
    target: null,    // 目标定位关联的元素
    expected: null   // 期望值关联的元素
})

// Refs
const customFormRef = ref(null)

// Computed properties
const activeStep = computed(() => {
    if (selectedIndex.value === null) {
        return null
    }
    const parentStep = scenarioSteps.value[selectedIndex.value]
    if (!parentStep) return null
    
    // 如果选中了子步骤，返回子步骤
    if (selectedSubIndex.value !== null && parentStep.steps) {
        return parentStep.steps[selectedSubIndex.value] || null
    }
    return parentStep
})

const activeParentStep = computed(() => {
    if (selectedIndex.value === null) return null
    return scenarioSteps.value[selectedIndex.value] || null
})

const activeComponentDef = computed(() => {
    if (!activeStep.value) {
        return null
    }
    // 子步骤一定是基础组件
    if (selectedSubIndex.value !== null) {
        return componentDefinitions.value[activeStep.value.type] || null
    }
    if (activeStep.value.kind === "custom") {
        return customComponentDefinitions.value[activeStep.value.type] || null
    }
    return componentDefinitions.value[activeStep.value.type] || null
})

const editingActiveStep = computed(() => {
    if (editingSelectedIndex.value === null) {
        return null
    }
    return editingCustomSteps.value[editingSelectedIndex.value] || null
})

const editingActiveDef = computed(() => {
    if (!editingActiveStep.value) {
        return null
    }
    return componentDefinitions.value[editingActiveStep.value.type] || null
})

const editingSchemaFields = computed(() => {
    if (!editingActiveDef.value || !editingActiveDef.value.schema) {
        return []
    }
    const properties = editingActiveDef.value.schema.properties || {}
    const required = editingSchemaRequired.value
    const fields = Object.keys(properties)
    const ordered = [
        ...fields.filter(field => required.includes(field)),
        ...fields.filter(field => !required.includes(field))
    ]
    let visible = ordered.filter(field => shouldShowField(field, editingActiveStep.value))
    return getFieldOrder(visible)
})

const editingSchemaRequired = computed(() => {
    if (!editingActiveDef.value || !editingActiveDef.value.schema) {
        return []
    }
    return editingActiveDef.value.schema.required || []
})

const customDialogTitle = computed(() => {
    return customDialogMode.value === "edit" ? t('appAutomation.sceneBuilder.dialog.editCustomComponent') : t('appAutomation.sceneBuilder.dialog.saveAsCustomComponent')
})

const schemaFields = computed(() => {
    if (!activeComponentDef.value || !activeComponentDef.value.schema) {
        return []
    }
    const properties = activeComponentDef.value.schema.properties || {}
    const required = schemaRequired.value
    const fields = Object.keys(properties)
    const ordered = [
        ...fields.filter(field => required.includes(field)),
        ...fields.filter(field => !required.includes(field))
    ]
    let visible = ordered.filter(field => shouldShowField(field, activeStep.value))
    return getFieldOrder(visible)
})

const schemaRequired = computed(() => {
    if (!activeComponentDef.value || !activeComponentDef.value.schema) {
        return []
    }
    return activeComponentDef.value.schema.required || []
})

watch(() => activeStep.value?.config?.assert_type, (value) => {
    if (!activeStep.value || !activeStep.value.config) {
        return
    }
    if (value === "number" && activeStep.value.config.match_mode !== "exact") {
        activeStep.value.config.match_mode = "exact"
    }
})

// Lifecycle hooks
onMounted(async () => {
    // console.log('UiTestSceneBuilder mounted, $api:', $api)
    try {
        await Promise.all([
            loadComponentPalette(), 
            loadCustomComponentPalette(),
            loadImageCategoryOptions(),  // 加载图片分类选项
            getAppProjects({ page_size: 100 }).then(res => { projectList.value = res.data.results || res.data || [] })
        ])

        const caseId = route.query.case_id
        if (caseId) {
            editingCaseId.value = caseId
            loadCaseDetail(caseId)
        }
    } catch (error) {
        console.error('初始化组件数据失败:', error)
    }
})


// Methods
const shouldShowField = (field, step) => {
    if (!step || !step.config) {
        return field !== "image_scope"
    }

    const assertType = step.config.assert_type
    if (field === "image_scope") {
        const typeFields = [
            "selector_type",
            "start_selector_type",
            "end_selector_type",
            "target_selector_type",
            "click_selector_type"
        ]
        if (assertType === "image") {
            return true
        }
        return typeFields.some(key => step.config[key] === "image")
    }

    if (field === "image_threshold") {
        const typeFields = [
            "selector_type",
            "start_selector_type",
            "end_selector_type",
            "target_selector_type",
            "click_selector_type"
        ]
        if (assertType === "image") {
            return true
        }
        return typeFields.some(key => step.config[key] === "image")
    }


    if (field === "expected_image_scope") {
        return assertType === "image"
    }


    if (assertType === "image") {
        if (field === "ocr_selector_type" || field === "ocr_selector" || field === "match_mode" || field === "selector_type" || field === "selector") {
            return false
        }
        if (field === "min" || field === "max" || field === "expected_exists") {
            return false
        }
    }

    if (assertType === "exists") {
        if (field === "expected" || field === "match_mode" || field === "min" || field === "max" || field === "ocr_selector_type" || field === "ocr_selector") {
            return false
        }
    }

    if (assertType === "range") {
        if (field === "expected" || field === "match_mode" || field === "expected_exists") {
            return false
        }
    }

    if (assertType === "regex") {
        if (field === "match_mode" || field === "expected_exists" || field === "min" || field === "max") {
            return false
        }
    }

    if (step.type === "loop") {
        const mode = step.config.mode
        if (field === "times" && mode !== "count") {
            return false
        }
        if (field === "max_loops" && mode !== "condition") {
            return false
        }
        if ((field === "left" || field === "operator" || field === "right") && mode !== "condition") {
            return false
        }
        if ((field === "items" || field === "item_var" || field === "item_scope") && mode !== "foreach") {
            return false
        }
    }

    return true
}

const formatExpectedList = (value) => {
    if (Array.isArray(value)) {
        return value.join(",")
    }
    if (typeof value === "string") {
        return value
    }
    return ""
}

const getExpectedListValue = (config) => {
    if (!config) {
        return ""
    }
    if (typeof config.expected_list_input === "string") {
        return config.expected_list_input
    }
    return formatExpectedList(config.expected_list)
}

const getActiveConfigForField = () => {
    if (activeStep.value && activeStep.value.config) {
        return activeStep.value.config
    }
    if (editingActiveStep.value && editingActiveStep.value.config) {
        return editingActiveStep.value.config
    }
    return null
}

const updateExpectedList = (config, rawValue) => {
    if (!config) {
        return
    }
    if (Array.isArray(rawValue)) {
        config.expected_list = rawValue
        return
    }
    const inputValue = String(rawValue || "")
    config.expected_list_input = inputValue
    const parts = inputValue
        .split(/\n|,|，/)
        .map(item => item.trim())
        .filter(Boolean)
    config.expected_list = parts
}

const isJsonField = (field) => {
    const def = editingActiveDef.value || activeComponentDef.value
    const type = def ? getFieldTypeForDef(def, field) : getFieldType(field)
    return type === "array" || type === "object"
}

const getJsonFieldRows = (field) => {
    const largeFields = ["steps", "then_steps", "else_steps", "try_steps", "catch_steps", "finally_steps", "branches"]
    return largeFields.includes(field) ? 16 : 8
}

const getJsonFieldValue = (config, field) => {
    if (!config) {
        return ""
    }
    const inputKey = `${field}_input`
    if (typeof config[inputKey] === "string") {
        return config[inputKey]
    }
    const value = config[field]
    if (value === undefined || value === null || value === "") {
        return ""
    }
    try {
        return JSON.stringify(value, null, 2)
    } catch (error) {
        return String(value)
    }
}

const updateJsonField = (config, field, rawValue) => {
    if (!config) {
        return
    }
    const inputValue = String(rawValue || "")
    config[`${field}_input`] = inputValue
    if (!inputValue.trim()) {
        const def = editingActiveDef.value || activeComponentDef.value
        const fieldType = def ? getFieldTypeForDef(def, field) : getFieldType(field)
        if (fieldType === "array") {
            config[field] = []
        } else {
            config[field] = {}
        }
        return
    }
    try {
        config[field] = JSON.parse(inputValue)
    } catch (error) {
        // 保留原始输入
    }
}

const addSceneVariable = () => {
    sceneVariables.value.push({
        name: "",
        value: "",
        type: "string",
        scope: "local",
        description: ""
    })
}

const removeSceneVariable = (index) => {
    sceneVariables.value.splice(index, 1)
}

const formatSceneVariables = () => {
    return sceneVariables.value
        .filter(item => item && item.name)
        .map(item => ({
            name: item.name,
            scope: item.scope || "local",
            type: item.type || "string",
            value: parseSceneVariableValue(item.value, item.type),
            description: item.description || ""
        }))
}

const parseSceneVariableValue = (value, type) => {
    if (type === "number") {
        const num = Number(value)
        return Number.isNaN(num) ? 0 : num
    }
    if (type === "boolean") {
        if (typeof value === "boolean") {
            return value
        }
        return String(value).trim().toLowerCase() === "true"
    }
    if (type === "array" || type === "object") {
        if (typeof value === "string") {
            try {
                return JSON.parse(value)
            } catch (error) {
                return type === "array" ? [] : {}
            }
        }
        return value
    }
    return value
}

const loadSceneVariables = (rawVariables) => {
    if (!Array.isArray(rawVariables)) {
        sceneVariables.value = []
        return
    }
    sceneVariables.value = rawVariables.map(item => ({
        name: item.name || "",
        scope: item.scope || "local",
        type: item.type || "string",
        value: (item.type === "array" || item.type === "object")
            ? JSON.stringify(item.value || (item.type === "array" ? [] : {}))
            : (item.value !== undefined && item.value !== null ? String(item.value) : ""),
        description: item.description || ""
    }))
}

const generateStepId = () => {
    return `step_${Date.now()}_${Math.floor(Math.random() * 10000)}`
}

const cloneComponent = (item) => {
    const cloned = {
        id: generateStepId(),
        type: item.type,
        name: item.name,
        kind: item.kind || "atomic",
        config: {
            ...item.defaultConfig
        }
    }
    // 自定义组件：深拷贝子步骤到实例中（后续编辑不影响原始定义）
    if (item.kind === "custom" && item.steps && item.steps.length > 0) {
        cloned.steps = JSON.parse(JSON.stringify(item.steps)).map(s => ({
            ...s,
            id: s.id || generateStepId(),
            config: s.config || {}
        }))
        cloned._expanded = false  // 展开/收起状态
    }
    return cloned
}

const selectStep = (index) => {
    selectedIndex.value = index
    selectedSubIndex.value = null  // 切换主步骤时清除子步骤选中
    const step = scenarioSteps.value[index]
    if (step) {
        applyDefaultConfig(step)
    }
    // 清除所有关联元素信息（切换步骤时重置）
    linkedElements.value = {
        selector: null,
        fallback: null,
        click: null,
        ocr: null,
        start: null,
        end: null,
        target: null,
        expected: null
    }
}

const selectSubStep = (parentIndex, subIndex) => {
    selectedIndex.value = parentIndex
    selectedSubIndex.value = subIndex
    const parentStep = scenarioSteps.value[parentIndex]
    if (parentStep && parentStep.steps && parentStep.steps[subIndex]) {
        applyDefaultConfig(parentStep.steps[subIndex])
    }
    linkedElements.value = {
        selector: null, fallback: null, click: null, ocr: null,
        start: null, end: null, target: null, expected: null
    }
}

const toggleExpandCustomStep = (index) => {
    const step = scenarioSteps.value[index]
    if (step) {
        step._expanded = !step._expanded
        if (!step._expanded) {
            // 收起时清除子步骤选中
            if (selectedIndex.value === index && selectedSubIndex.value !== null) {
                selectedSubIndex.value = null
            }
        }
    }
}

const addSubStep = (parentIndex) => {
    const parentStep = scenarioSteps.value[parentIndex]
    if (!parentStep || !parentStep.steps) return
    // 弹出选择基础组件的提示，这里简化为添加一个 click 步骤
    const newStep = {
        id: generateStepId(),
        type: 'click',
        name: t('appAutomation.sceneBuilder.action.click'),
        config: { ...(componentDefinitions.value['click']?.default_config || { selector_type: 'image', timeout: 5 }) }
    }
    parentStep.steps.push(newStep)
    selectSubStep(parentIndex, parentStep.steps.length - 1)
}

const duplicateSubStep = (parentIndex, subIndex) => {
    const parentStep = scenarioSteps.value[parentIndex]
    if (!parentStep || !parentStep.steps) return
    const source = parentStep.steps[subIndex]
    if (!source) return
    const copy = JSON.parse(JSON.stringify(source))
    copy.id = generateStepId()
    copy.name = t('appAutomation.sceneBuilder.steps.duplicateName', { name: source.name || source.type })
    parentStep.steps.splice(subIndex + 1, 0, copy)
}

const removeSubStep = (parentIndex, subIndex) => {
    const parentStep = scenarioSteps.value[parentIndex]
    if (!parentStep || !parentStep.steps) return
    parentStep.steps.splice(subIndex, 1)
    // 调整选中状态
    if (selectedIndex.value === parentIndex && selectedSubIndex.value === subIndex) {
        selectedSubIndex.value = null
    } else if (selectedIndex.value === parentIndex && selectedSubIndex.value > subIndex) {
        selectedSubIndex.value--
    }
}

const removeStep = (index) => {
    scenarioSteps.value.splice(index, 1)
    if (selectedIndex.value === index) {
        selectedIndex.value = null
    } else if (selectedIndex.value > index) {
        selectedIndex.value -= 1
    }
}

const duplicateStep = (index) => {
    const source = scenarioSteps.value[index]
    if (!source) {
        return
    }
    const copy = JSON.parse(JSON.stringify(source))
    copy.id = generateStepId()
    const baseName = source.name || source.type || t('appAutomation.sceneBuilder.steps.step')
    copy.name = t('appAutomation.sceneBuilder.steps.duplicateName', { name: baseName })
    scenarioSteps.value.splice(index + 1, 0, copy)
    selectStep(index + 1)
}

const resetScene = () => {
    sceneForm.value = {
        name: "",
        description: "",
        project: null
    }
    sceneVariables.value = []
    sceneRuntime.value = {
        base_url: "http://127.0.0.1:8000",
        retry_times: 0,
        retry_interval: 0.5
    }
    scenarioSteps.value = []
    selectedIndex.value = null
}

const openCustomComponentDialog = () => {
    if (scenarioSteps.value.length === 0) {
        ElMessage.warning(t('appAutomation.sceneBuilder.messages.selectStepsToSave'))
        return
    }
    const hasCustomStep = scenarioSteps.value.some(step => step.kind === "custom")
    if (hasCustomStep) {
        ElMessage.warning(t('appAutomation.sceneBuilder.messages.noNestedCustom'))
        return
    }
    customDialogVisible.value = true
}

const resetCustomDialog = () => {
    customForm.value = {
        name: "",
        type: "",
        description: ""
    }
    customDialogMode.value = "create"
    editingCustomId.value = null
    editingCustomSteps.value = []
    editingSelectedIndex.value = null
    editStepType.value = ""
    if (customFormRef.value) {
        customFormRef.value.resetFields()
    }
}

const openEditCustomComponent = (item) => {
    customDialogMode.value = "edit"
    customDialogVisible.value = true
    editingCustomId.value = item.id
    customForm.value = {
        name: item.name || "",
        type: item.type || "",
        description: item.description || ""
    }
    const rawSteps = (item.steps && Array.isArray(item.steps))
        ? item.steps
        : (customComponentDefinitions.value[item.type] && customComponentDefinitions.value[item.type].steps) || []
    editingCustomSteps.value = JSON.parse(JSON.stringify(rawSteps)).map(step => ({
        id: step.id || generateStepId(),
        type: step.type,
        name: step.name,
        config: step.config || {}
    }))
    editingCustomSteps.value.forEach(step => applyDefaultConfig(step))
    editingSelectedIndex.value = null
}

const selectEditStep = (index) => {
    editingSelectedIndex.value = index
    const step = editingCustomSteps.value[index]
    if (step) {
        applyDefaultConfig(step)
    }
}

const addEditStep = () => {
    if (!editStepType.value) {
        ElMessage.warning(t('appAutomation.sceneBuilder.messages.selectBaseComponent'))
        return
    }
    const item = componentPalette.value.find(component => component.type === editStepType.value)
    if (!item) {
        ElMessage.warning(t('appAutomation.sceneBuilder.messages.baseComponentNotFound'))
        return
    }
    const step = {
        id: generateStepId(),
        type: item.type,
        name: item.name,
        config: {
            ...item.defaultConfig
        }
    }
    editingCustomSteps.value.push(step)
    editingSelectedIndex.value = editingCustomSteps.value.length - 1
}

const removeEditStep = (index) => {
    editingCustomSteps.value.splice(index, 1)
    if (editingSelectedIndex.value === index) {
        editingSelectedIndex.value = null
    } else if (editingSelectedIndex.value > index) {
        editingSelectedIndex.value -= 1
    }
}

const duplicateEditStep = (index) => {
    const source = editingCustomSteps.value[index]
    if (!source) {
        return
    }
    const copy = JSON.parse(JSON.stringify(source))
    copy.id = generateStepId()
    const baseName = source.name || source.type || t('appAutomation.sceneBuilder.steps.step')
    copy.name = t('appAutomation.sceneBuilder.steps.duplicateName', { name: baseName })
    editingCustomSteps.value.splice(index + 1, 0, copy)
    editingSelectedIndex.value = index + 1
}

const deleteCustomComponent = async (item) => {
    try {
        await ElMessageBox.confirm(t('appAutomation.sceneBuilder.messages.deleteCustomComponentConfirm', { name: item.name }), t('appAutomation.sceneBuilder.messages.tip'), {
            confirmButtonText: t('appAutomation.common.confirm'),
            cancelButtonText: t('appAutomation.common.cancel'),
            type: "warning"
        })
    } catch (error) {
        return
    }
    try {
        await apiDeleteCustomComponent(item.id)
        ElMessage.success(t('appAutomation.common.deleteSuccess'))
        customComponentPalette.value = customComponentPalette.value.filter(
            component => component.id !== item.id
        )
        await loadCustomComponentPalette()
        paletteTab.value = "custom"
    } catch (error) {
        console.error("删除自定义组件失败:", error)
        ElMessage.error(t('appAutomation.common.deleteFailed'))
    }
}

const saveCustomComponent = () => {
    customFormRef.value.validate(async valid => {
        if (!valid) {
            return
        }
        if (customDialogMode.value === "create" && scenarioSteps.value.length === 0) {
            ElMessage.warning(t('appAutomation.sceneBuilder.messages.addSceneStepsFirst'))
            return
        }
        if (customDialogMode.value === "edit" && editingCustomSteps.value.length === 0) {
            ElMessage.warning(t('appAutomation.sceneBuilder.messages.addComponentStepsFirst'))
            return
        }
        customSaving.value = true
        try {
            const steps = (customDialogMode.value === "edit"
                ? editingCustomSteps.value
                : scenarioSteps.value
            ).map(step => ({
                type: step.type,
                name: step.name,
                config: step.config || {}
            }))
            const payload = {
                name: customForm.value.name,
                type: customForm.value.type,
                description: customForm.value.description || ""
            }
            if (customDialogMode.value === "create") {
                payload.schema = {}
                payload.default_config = {}
                payload.steps = steps
                payload.enabled = true
                payload.sort_order = 0
            } else {
                payload.steps = steps
            }

            const response = customDialogMode.value === "edit"
                ? await apiUpdateCustomComponent(editingCustomId.value, payload)
                : await apiCreateCustomComponent(payload)
            const data = response?.data || response
            if (data && (data.success || data.id)) {
                ElMessage.success(customDialogMode.value === "edit" ? t('appAutomation.sceneBuilder.messages.customComponentUpdated') : t('appAutomation.sceneBuilder.messages.customComponentSaved'))
                customDialogVisible.value = false
                await loadCustomComponentPalette()
                paletteTab.value = "custom"
            } else {
                ElMessage.error(response.data?.message || t('appAutomation.common.saveFailed'))
            }
        } catch (error) {
            console.error("保存自定义组件失败:", error)
            const errorMsg = (error.response && error.response.data && error.response.data.msg) || error.message
            ElMessage.error(t('appAutomation.sceneBuilder.messages.saveFailedWithError', { error: errorMsg }))
        } finally {
            customSaving.value = false
        }
    })
}

const loadComponentPalette = async () => {
    try {
        const response = await getComponents({ enabled: 1 })
        
        const list = response.data?.data || response.data || []
        
        if (list.length > 0) {
            const mergedList = list.map(item => ({
                type: item.type,
                name: item.name,
                schema: item.schema || {},
                defaultConfig: item.default_config || {},
                raw: item
            }))
            componentPalette.value = mergedList.map(item => ({
                type: item.type || '',
                name: item.name || '',
                schema: item.schema || {},
                defaultConfig: item.defaultConfig || {}
            })).filter(item => item.type)
            componentDefinitions.value = mergedList.reduce((acc, item) => {
                acc[item.type] = {
                    ...item.raw,
                    schema: item.schema,
                    default_config: item.defaultConfig
                }
                return acc
            }, {})
        } else {
            componentPalette.value = []
            componentDefinitions.value = {}
            ElMessage.warning(t('appAutomation.sceneBuilder.messages.noComponentDef'))
        }
    } catch (error) {
        console.error("加载组件库失败:", error)
        ElMessage.error(t('appAutomation.sceneBuilder.messages.loadPaletteFailed', { error: error.message || t('appAutomation.sceneBuilder.messages.unknownError') }))
        componentPalette.value = []
        componentDefinitions.value = {}
    }
}

const loadCustomComponentPalette = async () => {
    defaultCustomPalette.value = JSON.parse(JSON.stringify(customComponentPalette.value))
    try {
        const response = await getCustomComponents({ enabled: 1 })
        
        const list = response.data?.data || response.data || []
        
        if (list.length > 0) {
            customComponentPalette.value = list.map(item => ({
                id: item.id || `custom_${item.type}_${Date.now()}_${Math.random()}`,
                type: item.type || '',
                name: item.name || '',
                kind: "custom",
                schema: item.schema || {},
                defaultConfig: item.default_config || {},
                steps: item.steps || []
            })).filter(item => item.id && item.type)
            customComponentDefinitions.value = list.reduce((acc, item) => {
                acc[item.type] = item
                return acc
            }, {})
        } else {
            customComponentPalette.value = defaultCustomPalette.value.map(item => ({
                ...item,
                id: item.id || `custom_${item.type}_${Date.now()}_${Math.random()}`
            })).filter(item => item.id && item.type)
            customComponentDefinitions.value = customComponentPalette.value.reduce((acc, item) => {
                if (item && item.type) {
                    acc[item.type] = item
                }
                return acc
            }, {})
        }
    } catch (error) {
        console.error("加载自定义组件库失败:", error)
        customComponentPalette.value = defaultCustomPalette.value.map(item => ({
            ...item,
            id: item.id || `custom_${item.type}_${Date.now()}_${Math.random()}`
        })).filter(item => item.id && item.type)
        customComponentDefinitions.value = customComponentPalette.value.reduce((acc, item) => {
            if (item && item.type) {
                acc[item.type] = item
            }
            return acc
        }, {})
    }
}

const loadCaseDetail = async (caseId) => {
    try {
        const response = await getTestCaseDetail(caseId)
        const data = response.data || response
        if (data && data.id) {
            // 直接从 data 对象读取字段，匹配后端模型
            sceneForm.value.name = data.name || ""
            sceneForm.value.description = data.description || ""
            sceneForm.value.project = data.project || null
            loadSceneVariables(data.variables || [])
            sceneRuntime.value = {
                base_url: data.runtime?.base_url || "http://127.0.0.1:8000",
                retry_times: data.runtime?.retry_times || 0,
                retry_interval: data.runtime?.retry_interval || 0.5
            }
            const rawFlow = data.ui_flow
            const flowList = Array.isArray(rawFlow)
                ? rawFlow
                : (rawFlow && Array.isArray(rawFlow.steps) ? rawFlow.steps : [])
            scenarioSteps.value = flowList.map(step => {
                // 确保每个步骤有 id
                if (!step.id) step.id = generateStepId()
                // 兼容旧录制字段 action -> type
                if (!step.type && step.action) step.type = step.action === 'tap' ? 'click' : step.action
                if (!step.config) step.config = {}
                if (step.element_id && step.config.element_id === undefined) {
                    step.config.element_id = step.element_id
                }
                if (step.type === 'input') {
                    if (step.config.value === undefined && step.text != null) step.config.value = step.text
                    if (step.config.value === undefined && step.value != null) step.config.value = step.value
                }
                if (step.type === 'swipe') {
                    if (step.config.start === undefined && step.start) step.config.start = step.start
                    if (step.config.end === undefined && step.end) step.config.end = step.end
                    if (step.config.duration === undefined && step.duration != null) step.config.duration = step.duration
                }
                if ((step.type === 'click' || step.type === 'touch') && !step.config.selector && step.selector) {
                    step.config.selector = step.selector
                    step.config.selector_type = step.selector_type || step.config.selector_type || 'pos'
                }
                // 自定义组件初始化展开状态
                if (step.kind === 'custom' && step.steps) {
                    step._expanded = false
                    step.steps.forEach(sub => {
                        if (!sub.id) sub.id = generateStepId()
                    })
                }
                return step
            })
            scenarioSteps.value.forEach(step => applyDefaultConfig(step))
            selectedIndex.value = null
            selectedSubIndex.value = null
        }
    } catch (error) {
        console.error("加载用例失败:", error)
        ElMessage.error(t('appAutomation.sceneBuilder.messages.loadCaseFailed'))
    }
}

const applyDefaultConfig = (step) => {
    if (!step || !step.config) {
        return
    }
    const def = step.kind === "custom"
        ? customComponentDefinitions.value[step.type]
        : componentDefinitions.value[step.type]
    if (!def || !def.default_config) {
        return
    }
    const defaults = def.default_config
    Object.keys(defaults).forEach(key => {
        if (step.config[key] === undefined) {
            step.config[key] = defaults[key]
        }
    })
}

// 字段分组辅助函数（通用：支持场景步骤和自定义组件编辑）
const getFieldGroups = (fieldsOverride = null) => {
    const groups = []
    const allFields = fieldsOverride || schemaFields.value
    if (!allFields || allFields.length === 0) return []
    const usedFields = new Set()
    
    // 定义字段组规则
    const groupRules = [
        {
            key: 'selector',
            title: t('appAutomation.sceneBuilder.fieldGroup.selector'),
            fields: ['selector_type', 'selector', 'image_scope', 'image_threshold'],
            hasFields: () => allFields.includes('selector_type')
        },
        {
            key: 'fallback',
            title: t('appAutomation.sceneBuilder.fieldGroup.fallback'),
            fields: ['fallback_selector_type', 'fallback_selector', 'fallback_image_scope', 'fallback_image_threshold'],
            hasFields: () => allFields.includes('fallback_selector_type')
        },
        {
            key: 'click',
            title: t('appAutomation.sceneBuilder.fieldGroup.click'),
            fields: ['click_selector_type', 'click_selector', 'image_scope', 'image_threshold'],
            hasFields: () => allFields.includes('click_selector_type')
        },
        {
            key: 'ocr',
            title: t('appAutomation.sceneBuilder.fieldGroup.ocr'),
            fields: ['ocr_selector_type', 'ocr_selector'],
            hasFields: () => allFields.includes('ocr_selector_type')
        },
        {
            key: 'start',
            title: t('appAutomation.sceneBuilder.fieldGroup.start'),
            fields: ['start_selector_type', 'start_selector', 'image_scope', 'image_threshold'],
            hasFields: () => allFields.includes('start_selector_type')
        },
        {
            key: 'end',
            title: t('appAutomation.sceneBuilder.fieldGroup.end'),
            fields: ['end_selector_type', 'end_selector', 'image_scope', 'image_threshold'],
            hasFields: () => allFields.includes('end_selector_type')
        },
        {
            key: 'target',
            title: t('appAutomation.sceneBuilder.fieldGroup.target'),
            fields: ['target_selector_type', 'target_selector', 'image_scope', 'image_threshold'],
            hasFields: () => allFields.includes('target_selector_type')
        },
        {
            key: 'expected',
            title: t('appAutomation.sceneBuilder.fieldGroup.expected'),
            fields: ['assert_type', 'expected', 'expected_list', 'expected_image_scope', 'match_mode'],
            hasFields: () => allFields.includes('assert_type') || allFields.includes('expected')
        }
    ]

    // 检测每个组是否存在
    groupRules.forEach(rule => {
        if (rule.hasFields()) {
            const groupFields = rule.fields.filter(f => allFields.includes(f))
            if (groupFields.length > 0) {
                groups.push({
                    key: rule.key,
                    title: rule.title,
                    fields: groupFields
                })
                groupFields.forEach(f => usedFields.add(f))
            }
        }
    })

    // 其他字段
    const otherFields = allFields.filter(f => !usedFields.has(f))
    if (otherFields.length > 0) {
        // 计算定位类分组的数量（排除 'other'）
        const selectorGroupCount = groups.length

        // 如果没有定位类分组，标题为"配置"；否则为"其他配置"
        const otherTitle = selectorGroupCount === 0 ? t('appAutomation.sceneBuilder.fieldGroup.config') : t('appAutomation.sceneBuilder.fieldGroup.otherConfig')

        groups.push({
            key: 'other',
            title: otherTitle,
            fields: otherFields
        })
    }
    
    return groups
}

const getEditingFieldGroups = () => {
    return getFieldGroups(editingSchemaFields.value)
}

const getFieldLabel = (field) => {
    const labels = {
        selector_type: t('appAutomation.sceneBuilder.fieldLabel.selectorType'),
        selector: t('appAutomation.sceneBuilder.fieldLabel.selector'),
        fallback_selector_type: t('appAutomation.sceneBuilder.fieldLabel.fallbackSelectorType'),
        fallback_selector: t('appAutomation.sceneBuilder.fieldLabel.fallbackSelector'),
        fallback_image_scope: t('appAutomation.sceneBuilder.fieldLabel.fallbackImageScope'),
        fallback_image_threshold: t('appAutomation.sceneBuilder.fieldLabel.fallbackImageThreshold'),
        value: t('appAutomation.sceneBuilder.fieldLabel.value'),
        send_enter: t('appAutomation.sceneBuilder.fieldLabel.sendEnter'),
        direction: t('appAutomation.sceneBuilder.fieldLabel.direction'),
        timeout: t('appAutomation.sceneBuilder.fieldLabel.timeout'),
        expected: t('appAutomation.sceneBuilder.fieldLabel.expected'),
        assert_type: t('appAutomation.sceneBuilder.fieldLabel.assertType'),
        expected_exists: t('appAutomation.sceneBuilder.fieldLabel.expectedExists'),
        duration: t('appAutomation.sceneBuilder.fieldLabel.duration'),
        image_scope: t('appAutomation.sceneBuilder.fieldLabel.imageScope'),
        expected_image_scope: t('appAutomation.sceneBuilder.fieldLabel.expectedImageScope'),
        image_threshold: t('appAutomation.sceneBuilder.fieldLabel.imageThreshold'),
        expected_list: t('appAutomation.sceneBuilder.fieldLabel.expectedList'),
        click_selector_type: t('appAutomation.sceneBuilder.fieldLabel.clickSelectorType'),
        click_selector: t('appAutomation.sceneBuilder.fieldLabel.clickSelector'),
        ocr_selector_type: t('appAutomation.sceneBuilder.fieldLabel.ocrSelectorType'),
        ocr_selector: t('appAutomation.sceneBuilder.fieldLabel.ocrSelector'),
        start_selector_type: t('appAutomation.sceneBuilder.fieldLabel.startSelectorType'),
        start_selector: t('appAutomation.sceneBuilder.fieldLabel.startSelector'),
        end_selector_type: t('appAutomation.sceneBuilder.fieldLabel.endSelectorType'),
        end_selector: t('appAutomation.sceneBuilder.fieldLabel.endSelector'),
        target_selector_type: t('appAutomation.sceneBuilder.fieldLabel.targetSelectorType'),
        target_selector: t('appAutomation.sceneBuilder.fieldLabel.targetSelector'),
        max_swipes: t('appAutomation.sceneBuilder.fieldLabel.maxSwipes'),
        interval: t('appAutomation.sceneBuilder.fieldLabel.interval'),
        max_loops: t('appAutomation.sceneBuilder.fieldLabel.maxLoops'),
        note: t('appAutomation.sceneBuilder.fieldLabel.note'),
        match_mode: t('appAutomation.sceneBuilder.fieldLabel.matchMode'),
        name: t('appAutomation.sceneBuilder.fieldLabel.name'),
        value_type: t('appAutomation.sceneBuilder.fieldLabel.valueType'),
        scope: t('appAutomation.sceneBuilder.fieldLabel.scope'),
        source: t('appAutomation.sceneBuilder.fieldLabel.source'),
        path: t('appAutomation.sceneBuilder.fieldLabel.path'),
        method: t('appAutomation.sceneBuilder.fieldLabel.method'),
        url: t('appAutomation.sceneBuilder.fieldLabel.url'),
        headers: t('appAutomation.sceneBuilder.fieldLabel.headers'),
        params: t('appAutomation.sceneBuilder.fieldLabel.params'),
        data: t('appAutomation.sceneBuilder.fieldLabel.data'),
        json: t('appAutomation.sceneBuilder.fieldLabel.json'),
        expected_status: t('appAutomation.sceneBuilder.fieldLabel.expectedStatus'),
        response_type: t('appAutomation.sceneBuilder.fieldLabel.responseType'),
        save_as: t('appAutomation.sceneBuilder.fieldLabel.saveAs'),
        extracts: t('appAutomation.sceneBuilder.fieldLabel.extracts'),
        left: t('appAutomation.sceneBuilder.fieldLabel.left'),
        operator: t('appAutomation.sceneBuilder.fieldLabel.operator'),
        right: t('appAutomation.sceneBuilder.fieldLabel.right'),
        then_steps: t('appAutomation.sceneBuilder.fieldLabel.thenSteps'),
        else_steps: t('appAutomation.sceneBuilder.fieldLabel.elseSteps'),
        mode: t('appAutomation.sceneBuilder.fieldLabel.mode'),
        times: t('appAutomation.sceneBuilder.fieldLabel.times'),
        items: t('appAutomation.sceneBuilder.fieldLabel.items'),
        item_var: t('appAutomation.sceneBuilder.fieldLabel.itemVar'),
        item_scope: t('appAutomation.sceneBuilder.fieldLabel.itemScope'),
        steps: t('appAutomation.sceneBuilder.fieldLabel.steps'),
        branches: t('appAutomation.sceneBuilder.fieldLabel.branches'),
        merge_strategy: t('appAutomation.sceneBuilder.fieldLabel.mergeStrategy'),
        try_steps: t('appAutomation.sceneBuilder.fieldLabel.trySteps'),
        catch_steps: t('appAutomation.sceneBuilder.fieldLabel.catchSteps'),
        finally_steps: t('appAutomation.sceneBuilder.fieldLabel.finallySteps'),
        error_var: t('appAutomation.sceneBuilder.fieldLabel.errorVar'),
        error_scope: t('appAutomation.sceneBuilder.fieldLabel.errorScope'),
        min: t('appAutomation.sceneBuilder.fieldLabel.min'),
        max: t('appAutomation.sceneBuilder.fieldLabel.max'),
        retry_times: t('appAutomation.sceneBuilder.fieldLabel.retryTimes'),
        retry_interval: t('appAutomation.sceneBuilder.fieldLabel.retryInterval')
    }
    const config = getActiveConfigForField()
    const currentStep = activeStep.value || editingActiveStep.value
    if (field === "value" && currentStep && currentStep.type === "set_variable") {
        return t('appAutomation.sceneBuilder.fieldLabel.variableValue')
    }
    if (config && config.assert_type === "image") {
        if (field === "expected") {
            return t('appAutomation.sceneBuilder.fieldLabel.expectedImage')
        }
        if (field === "expected_list") {
            return t('appAutomation.sceneBuilder.fieldLabel.expectedImageList')
        }
    }
    return labels[field] || field
}

const getFieldPlaceholder = (field) => {
            const config = getActiveConfigForField()

            // 动态占位符：根据定位方式返回不同提示
            const getDynamicPlaceholder = (selectorField, typeField) => {
                if (!config) return null
                const type = config[typeField] || 'image'
                if (type === 'image') return t('appAutomation.sceneBuilder.fieldPlaceholder.imageFile')
                if (type === 'pos') return 'pos: x,y'
                if (type === 'region') return 'region: x1,y1,x2,y2'
                return null
            }

            if (field === 'selector') {
                return getDynamicPlaceholder('selector', 'selector_type') || t('appAutomation.sceneBuilder.fieldPlaceholder.selectorFull')
            }
            if (field === 'fallback_selector') {
                return getDynamicPlaceholder('fallback_selector', 'fallback_selector_type') || t('appAutomation.sceneBuilder.fieldPlaceholder.selectorFull')
            }
            if (field === 'click_selector') {
                return getDynamicPlaceholder('click_selector', 'click_selector_type') || t('appAutomation.sceneBuilder.fieldPlaceholder.selectorImagePos')
            }
            if (field === 'start_selector') {
                return getDynamicPlaceholder('start_selector', 'start_selector_type') || t('appAutomation.sceneBuilder.fieldPlaceholder.selectorImagePos')
            }
            if (field === 'end_selector') {
                return getDynamicPlaceholder('end_selector', 'end_selector_type') || t('appAutomation.sceneBuilder.fieldPlaceholder.selectorImagePos')
            }
            if (field === 'target_selector') {
                return getDynamicPlaceholder('target_selector', 'target_selector_type') || t('appAutomation.sceneBuilder.fieldPlaceholder.selectorImage')
            }
            if (field === 'ocr_selector') {
                return getDynamicPlaceholder('ocr_selector', 'ocr_selector_type') || "region: x1,y1,x2,y2 | pos: x,y"
            }

            const placeholders = {
                selector: t('appAutomation.sceneBuilder.fieldPlaceholder.selectorFull'),
                fallback_selector: t('appAutomation.sceneBuilder.fieldPlaceholder.selectorFull'),
                start_selector: t('appAutomation.sceneBuilder.fieldPlaceholder.selectorImagePos'),
                end_selector: t('appAutomation.sceneBuilder.fieldPlaceholder.selectorImagePos'),
                target_selector: t('appAutomation.sceneBuilder.fieldPlaceholder.selectorImage'),
                click_selector: t('appAutomation.sceneBuilder.fieldPlaceholder.selectorImagePos'),
                ocr_selector: "region: x1,y1,x2,y2 | pos: x,y",
                value: t('appAutomation.sceneBuilder.fieldPlaceholder.value'),
                send_enter: t('appAutomation.sceneBuilder.fieldPlaceholder.sendEnter'),
                expected: t('appAutomation.sceneBuilder.fieldPlaceholder.expected'),
                note: t('appAutomation.sceneBuilder.fieldPlaceholder.note'),
                image_scope: t('appAutomation.sceneBuilder.fieldPlaceholder.imageScope'),
                expected_image_scope: t('appAutomation.sceneBuilder.fieldPlaceholder.imageScope'),
                fallback_image_scope: t('appAutomation.sceneBuilder.fieldPlaceholder.imageScope'),
                image_threshold: "0.7 ~ 1.0",
                fallback_image_threshold: "0.7 ~ 1.0",
                expected_list: t('appAutomation.sceneBuilder.fieldPlaceholder.expectedList'),
                name: t('appAutomation.sceneBuilder.fieldPlaceholder.name'),
                value_type: "string/number/boolean/array/object",
                scope: t('appAutomation.sceneBuilder.fieldPlaceholder.scope'),
                source: t('appAutomation.sceneBuilder.fieldPlaceholder.source'),
                path: t('appAutomation.sceneBuilder.fieldPlaceholder.path'),
                method: "GET/POST/PUT/PATCH/DELETE",
                url: t('appAutomation.sceneBuilder.fieldPlaceholder.url'),
                headers: t('appAutomation.sceneBuilder.fieldPlaceholder.headers'),
                params: t('appAutomation.sceneBuilder.fieldPlaceholder.params'),
                data: t('appAutomation.sceneBuilder.fieldPlaceholder.data'),
                json: t('appAutomation.sceneBuilder.fieldPlaceholder.json'),
                expected_status: t('appAutomation.sceneBuilder.fieldPlaceholder.expectedStatus'),
                response_type: "auto/json/text",
                save_as: t('appAutomation.sceneBuilder.fieldPlaceholder.saveAs'),
                extracts: "[{\"name\":\"token\",\"path\":\"data.token\"}]",
                left: t('appAutomation.sceneBuilder.fieldPlaceholder.variableExpression'),
                operator: "== != > >= < <= contains regex truthy",
                right: t('appAutomation.sceneBuilder.fieldPlaceholder.variableExpression'),
                items: t('appAutomation.sceneBuilder.fieldPlaceholder.items'),
                item_var: t('appAutomation.sceneBuilder.fieldPlaceholder.itemVar'),
                item_scope: t('appAutomation.sceneBuilder.fieldPlaceholder.scope'),
                steps: t('appAutomation.sceneBuilder.fieldPlaceholder.jsonArraySteps'),
                then_steps: t('appAutomation.sceneBuilder.fieldPlaceholder.jsonArraySteps'),
                else_steps: t('appAutomation.sceneBuilder.fieldPlaceholder.jsonArraySteps'),
                branches: t('appAutomation.sceneBuilder.fieldPlaceholder.branches'),
                try_steps: t('appAutomation.sceneBuilder.fieldPlaceholder.jsonArraySteps'),
                catch_steps: t('appAutomation.sceneBuilder.fieldPlaceholder.jsonArraySteps'),
                finally_steps: t('appAutomation.sceneBuilder.fieldPlaceholder.jsonArraySteps')
    }
    const currentStep = activeStep.value || editingActiveStep.value
    if (field === "value" && currentStep && currentStep.type === "set_variable") {
        return t('appAutomation.sceneBuilder.fieldPlaceholder.valueExpression')
    }
    if (config && config.assert_type === "image") {
        if (field === "expected") {
            return t('appAutomation.sceneBuilder.fieldPlaceholder.expectedImage')
        }
        if (field === "expected_list") {
            return t('appAutomation.sceneBuilder.fieldPlaceholder.expectedImageList')
        }
    }
    return placeholders[field] || ""
}

const applyApiRequestTemplate = (template, targetStep) => {
    const step = targetStep || activeStep.value || editingActiveStep.value
    if (!step || !step.config) {
        ElMessage.warning(t('appAutomation.sceneBuilder.messages.selectStepFirst'))
        return
    }
    const config = template && template.config
        ? JSON.parse(JSON.stringify(template.config))
        : {}
    Object.keys(config).forEach(key => {
        step.config[key] = config[key]
    })
    ElMessage.success(t('appAutomation.sceneBuilder.messages.templateApplied', { name: template.name }))
}

// 判断是否是图片分类相关字段
const isImageScopeField = (field) => {
    return ['image_scope', 'expected_image_scope', 'fallback_image_scope'].includes(field)
}

const getFieldType = (field) => {
    if (!activeComponentDef.value || !activeComponentDef.value.schema) {
        return "string"
    }
    const properties = activeComponentDef.value.schema.properties || {}
    return properties[field] && properties[field].type ? properties[field].type : "string"
}

const getFieldTypeForDef = (def, field) => {
    if (!def || !def.schema) {
        return "string"
    }
    const properties = def.schema.properties || {}
    return properties[field] && properties[field].type ? properties[field].type : "string"
}

const getFieldOptions = (field) => {
            const optionsMap = {
                image_scope: imageCategoryOptions.value,  // 动态加载的图片分类选项
                expected_image_scope: imageCategoryOptions.value,  // 动态加载的图片分类选项
                fallback_image_scope: imageCategoryOptions.value,  // 动态加载的图片分类选项
                selector_type: [
                    { label: "image", value: "image" },
                    { label: "pos", value: "pos" },
                    { label: "region", value: "region" },
                    { label: "text", value: "text" }
                ],
                fallback_selector_type: [
                    { label: "image", value: "image" },
                    { label: "pos", value: "pos" },
                    { label: "region", value: "region" }
                ],
                assert_type: [
                    { label: "number", value: "number" },
                    { label: "text", value: "text" },
                    { label: "regex", value: "regex" },
                    { label: "range", value: "range" },
                    { label: "exists", value: "exists" },
                    { label: "image", value: "image" }
                ],
                start_selector_type: [
                    { label: "image", value: "image" },
                    { label: "pos", value: "pos" }
                ],
                end_selector_type: [
                    { label: "image", value: "image" },
                    { label: "pos", value: "pos" }
                ],
                target_selector_type: [
                    { label: "image", value: "image" }
                ],
                click_selector_type: [
                    { label: "image", value: "image" },
                    { label: "pos", value: "pos" }
                ],
                ocr_selector_type: [
                    { label: "region", value: "region" },
                    { label: "pos", value: "pos" }
                ],
                direction: [
                    { label: "up", value: "up" },
                    { label: "down", value: "down" },
                    { label: "left", value: "left" },
                    { label: "right", value: "right" }
                ],
                match_mode: [
                    { label: "contains", value: "contains" },
                    { label: "exact", value: "exact" }
                ],
                operator: [
                    { label: "==", value: "==" },
                    { label: "!=", value: "!=" },
                    { label: ">", value: ">" },
                    { label: ">=", value: ">=" },
                    { label: "<", value: "<" },
                    { label: "<=", value: "<=" },
                    { label: "contains", value: "contains" },
                    { label: "regex", value: "regex" },
                    { label: "truthy", value: "truthy" },
                    { label: "falsy", value: "falsy" }
                ],
                scope: [
                    { label: "local", value: "local" },
                    { label: "global", value: "global" }
                ],
                item_scope: [
                    { label: "local", value: "local" },
                    { label: "global", value: "global" }
                ],
                error_scope: [
                    { label: "local", value: "local" },
                    { label: "global", value: "global" }
                ],
                value_type: [
                    { label: "string", value: "string" },
                    { label: "number", value: "number" },
                    { label: "boolean", value: "boolean" },
                    { label: "array", value: "array" },
                    { label: "object", value: "object" }
                ],
                mode: [
                    { label: "count", value: "count" },
                    { label: "condition", value: "condition" },
                    { label: "foreach", value: "foreach" }
                ],
                method: [
                    { label: "GET", value: "GET" },
                    { label: "POST", value: "POST" },
                    { label: "PUT", value: "PUT" },
                    { label: "PATCH", value: "PATCH" },
                    { label: "DELETE", value: "DELETE" }
                ],
                response_type: [
                    { label: "auto", value: "auto" },
                    { label: "json", value: "json" },
                    { label: "text", value: "text" }
                ],
                merge_strategy: [
                    { label: "last", value: "last" },
                    { label: "first", value: "first" }
                ]
    }
    if (field === "assert_type") {
        const currentStep = activeStep.value || editingActiveStep.value
        if (currentStep && currentStep.type === "foreach_assert") {
            return [
                { label: "number", value: "number" },
                { label: "text", value: "text" },
                { label: "image", value: "image" }
            ]
        }
    }
    const currentStep = activeStep.value || editingActiveStep.value
    if (field === "match_mode" && currentStep && currentStep.config) {
        if (currentStep.config.assert_type === "number") {
            return [{ label: "exact", value: "exact" }]
        }
    }
    return optionsMap[field] || []
}

const getFieldOrder = (fields) => {
            const baseOrder = [
                "expected_list",
                "expected",
                "assert_type",
                "match_mode",
                "min",
                "max",
                "click_selector_type",
                "image_scope",
                "image_threshold",
                "click_selector",
                "ocr_selector_type",
                "ocr_selector",
                "max_loops",
                "interval",
                "selector_type",
                "selector",
                "value",
                "send_enter",
                "direction",
                "duration",
                "expected_exists",
                "start_selector_type",
                "start_selector",
                "end_selector_type",
                "end_selector",
                "target_selector_type",
                "target_selector",
                "max_swipes",
                "note",
                "name",
                "value_type",
                "scope",
                "source",
                "path",
                "method",
                "url",
                "headers",
                "params",
                "data",
                "json",
                "expected_status",
                "response_type",
                "save_as",
                "extracts",
                "left",
                "operator",
                "right",
                "then_steps",
                "else_steps",
                "mode",
                "times",
                "items",
                "item_var",
                "item_scope",
                "steps",
                "branches",
                "merge_strategy",
                "try_steps",
                "catch_steps",
                "finally_steps",
                "error_var",
                "error_scope",
                "retry_times",
                "retry_interval",
                "timeout"
    ]
    const orderIndex = baseOrder.reduce((acc, item, index) => {
        acc[item] = index
        return acc
    }, {})
    const currentStep = activeStep.value || editingActiveStep.value
    let ordered = [...fields].sort((a, b) => {
        const aIndex = orderIndex[a] !== undefined ? orderIndex[a] : 999
        const bIndex = orderIndex[b] !== undefined ? orderIndex[b] : 999
        return aIndex - bIndex
    })
    if (currentStep && currentStep.type === "foreach_assert") {
        const assertType = currentStep.config && currentStep.config.assert_type
        if (assertType === "image") {
            if (ordered.includes("expected_image_scope")) {
                ordered = ordered.filter(item => item !== "expected_image_scope")
                const expectedIndex = ordered.indexOf("expected_list")
                if (expectedIndex >= 0) {
                    ordered.splice(expectedIndex + 1, 0, "expected_image_scope")
                } else {
                    ordered.unshift("expected_image_scope")
                }
            }
        } else {
            ordered = ordered.filter(item => item !== "expected_image_scope")
        }
    }
    if (currentStep && (currentStep.type === "image_exists_click" || currentStep.type === "image_exists_click_chain")) {
        const timeoutIndex = ordered.indexOf("timeout")
        const imageFields = [
            "image_threshold"
        ]
        ordered = ordered.filter(item => !imageFields.includes(item))
        ordered = [
            ...imageFields.filter(item => fields.includes(item)),
            ...ordered
        ]
        if (timeoutIndex >= 0) {
            ordered = ordered.filter(item => item !== "timeout")
            ordered.push("timeout")
        }
    }
    return ordered
}

const getFieldNumberRule = (field) => {
    const rules = {
        timeout: { min: 1, max: 60, step: 1 },
        duration: { min: 0.1, max: 5, step: 0.1 },
        interval: { min: 0.1, max: 5, step: 0.1 },
        max_swipes: { min: 1, max: 20, step: 1 },
        max_loops: { min: 1, max: 50, step: 1 },
        times: { min: 1, max: 100, step: 1 },
        min: { min: -999999, max: 999999, step: 1 },
        max: { min: -999999, max: 999999, step: 1 },
        retry_times: { min: 0, max: 10, step: 1 },
        retry_interval: { min: 0.1, max: 10, step: 0.1 },
        expected_status: { min: 100, max: 600, step: 1 },
        image_threshold: { min: 0.1, max: 1, step: 0.01 }
    }
    return rules[field] || { min: 0, max: 999, step: 1 }
}

const getFieldNumberRuleForDef = (def, field) => {
    if (!def || !def.schema) {
        return getFieldNumberRule(field)
    }
    return getFieldNumberRule(field)
}

const openPackageDialog = async () => {
    packageDialogVisible.value = true
    await loadPackageList()
}

const resetPackageDialog = () => {
    packageUploading.value = false
    packageLoading.value = false
    packageList.value = []
}

const openExportDialog = () => {
    exportDialogVisible.value = true
}

const resetExportDialog = () => {
    exportDialogVisible.value = false
}

const openCaptureElementDialog = () => {
    captureElementDialogVisible.value = true
}

const handleElementCreated = () => {
    ElMessage.success(t('appAutomation.sceneBuilder.messages.elementCreated'))
    // 如果元素选择器对话框打开，可以刷新元素列表
    if (elementSelectorVisible.value) {
        loadElementsForSelector()
    }
}

const loadPackageList = async () => {
    packageLoading.value = true
    try {
        // 组件包列表暂不显示历史记录，仅保留导入功能
        packageList.value = []
    } catch (error) {
        console.error("加载组件包失败:", error)
        packageList.value = []
    } finally {
        packageLoading.value = false
    }
}

const handlePackageUpload = async (option) => {
    if (!option || !option.file) {
        return
    }
    packageUploading.value = true
    try {
        const formData = new FormData()
        formData.append("file", option.file)
        formData.append("overwrite", packageOverwrite.value ? "1" : "0")
        const response = await importComponentPackage(formData)
        const data = response.data || response
        if (data.success || data.data) {
            ElMessage.success(t('appAutomation.sceneBuilder.messages.packageImported'))
            await loadComponentPalette()
            await loadPackageList()
        } else {
            ElMessage.error(data.message || t('appAutomation.sceneBuilder.messages.importFailed'))
        }
    } catch (error) {
        console.error("导入组件包失败:", error)
        const errorMsg = (error.response && error.response.data && error.response.data.msg) || error.message
        ElMessage.error(errorMsg || t('appAutomation.sceneBuilder.messages.importFailed'))
    } finally {
        packageUploading.value = false
    }
}

const exportPackage = async (format) => {
    try {
        const response = await exportComponentPackage({
            export_format: format || "yaml",
            include_disabled: packageIncludeDisabled.value ? 1 : 0
        })
        const blob = new Blob([response.data], { type: response.headers["content-type"] || "application/octet-stream" })
        const filename = getDownloadFilename(response.headers["content-disposition"])
            || `ui-component-pack.${format === "json" ? "json" : "yaml"}`
        downloadBlob(blob, filename)
        ElMessage.success(t('appAutomation.sceneBuilder.messages.packageExported'))
        exportDialogVisible.value = false
    } catch (error) {
        console.error("导出组件包失败:", error)
        const errorMsg = (error.response && error.response.data && error.response.data.msg) || error.message
        ElMessage.error(errorMsg || t('appAutomation.sceneBuilder.messages.exportFailed'))
    }
}

const getDownloadFilename = (contentDisposition) => {
    if (!contentDisposition) {
        return ""
    }
    const match = /filename="?([^"]+)"?/i.exec(contentDisposition)
    if (match && match[1]) {
        return decodeURIComponent(match[1])
    }
    return ""
}

const downloadBlob = (blob, filename) => {
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement("a")
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
}

const saveScene = async () => {
    if (!sceneForm.value.name) {
        ElMessage.warning(t('appAutomation.sceneBuilder.messages.inputSceneName'))
        return
    }
    if (scenarioSteps.value.length === 0) {
        ElMessage.warning(t('appAutomation.sceneBuilder.messages.addAtLeastOneStep'))
        return
    }

    saving.value = true
    try {
        // 直接发送平铺的字段结构，匹配后端模型
        // 深拷贝并清理前端内部状态字段（_expanded 等）
        const cleanedSteps = JSON.parse(JSON.stringify(scenarioSteps.value)).map(step => {
            delete step._expanded
            return step
        })
        const caseData = {
            name: sceneForm.value.name,
            description: sceneForm.value.description,
            project: sceneForm.value.project || null,
            ui_flow: cleanedSteps,
            variables: formatSceneVariables()
        }

        let caseResponse = null
        if (editingCaseId.value) {
            caseResponse = await updateTestCase(editingCaseId.value, caseData)
        } else {
            caseResponse = await createTestCase(caseData)
        }

        const responseData = caseResponse.data || caseResponse
        if (responseData && (responseData.id || responseData.success)) {
            ElMessage.success(editingCaseId.value ? t('appAutomation.sceneBuilder.messages.sceneUpdateSuccess') : t('appAutomation.sceneBuilder.messages.sceneSaveSuccess'))
            if (responseData.id && !editingCaseId.value) {
                editingCaseId.value = responseData.id
            }
        } else {
            ElMessage.success(t('appAutomation.sceneBuilder.messages.sceneSubmitted'))
        }
    } catch (error) {
        console.error("保存场景失败:", error)
        const errorMsg = (error.response && error.response.data && error.response.data.msg) || error.message
        ElMessage.error(t('appAutomation.sceneBuilder.messages.saveSceneFailed', { error: errorMsg }))
    } finally {
        saving.value = false
    }
}

// 元素选择器相关方法
const openElementSelector = (target = '') => {
    elementSelectorTarget.value = target
    elementSelectorVisible.value = true
    loadElementsForSelector()
}

const loadElementsForSelector = async () => {
    elementSelectorLoading.value = true
    try {
        const params = {
            page: elementCurrentPage.value,
            size: elementPageSize.value,
            element_type: elementFilterType.value,
            keyword: elementSearchKeyword.value
        }
        
        const response = await getAppElementList(params)
        const data = response.data?.data || response.data
        selectorElements.value = data?.results || data || []
        elementTotal.value = data?.count || selectorElements.value.length
    } catch (error) {
        console.error('加载元素列表失败:', error)
        ElMessage.error(t('appAutomation.sceneBuilder.messages.loadElementsFailed'))
    } finally {
        elementSelectorLoading.value = false
    }
}

// 加载图片分类选项（从 Template 目录扫描）
const loadImageCategoryOptions = async () => {
    try {
        console.log('=== 开始加载图片分类选项（从Template目录） ===')
        const response = await getAppImageCategories()
        console.log('API响应:', response)
        
        const categories = response.data?.data || response.data || []
        console.log('获取到的分类:', categories)
        
        // 转换为选项格式
        // 如果 categories 是对象数组（包含 name 字段），则使用 name；否则直接使用值
        imageCategoryOptions.value = categories.map(cat => {
            const categoryName = typeof cat === 'object' && cat.name ? cat.name : cat
            return {
                label: categoryName,
                value: categoryName
            }
        })
        
        console.log('最终选项:', imageCategoryOptions.value)
    } catch (error) {
        console.error('加载图片分类失败:', error)
        // 失败时使用默认值
        imageCategoryOptions.value = [{ label: 'common', value: 'common' }]
    }
}

const handleElementRowClick = (row) => {
    // 行点击事件（可选）
}

// 统一的字段填充函数
const fillFieldsByTarget = (element, config, target) => {
    console.log(`填充 ${target} 字段组`)
    
    // 映射：target -> 字段前缀
    const prefixMap = {
        selector: '',       // 通用定位没有前缀
        fallback: 'fallback_',  // 备用定位
        click: 'click_',
        ocr: 'ocr_',
        start: 'start_',
        end: 'end_',
        target: 'target_',
        expected: ''        // 断言字段特殊处理
    }
    
    const prefix = prefixMap[target] || ''
    const typeField = prefix ? `${prefix}selector_type` : 'selector_type'
    const valueField = prefix ? `${prefix}selector` : 'selector'
    const scopeField = prefix ? `${prefix}image_scope` : 'image_scope'
    
    // 保存 element_id 到步骤配置（runner 优先通过 element_id 从数据库解析）
    const elementIdField = prefix ? `${prefix}element_id` : 'element_id'
    config[elementIdField] = element.id

    // 根据元素类型填充（作为 fallback，即使 element_id 失效也能通过 selector 定位）
    if (element.element_type === 'image') {
        if (element.config && element.config.image_path) {
            const fileName = element.config.image_path.split('/').pop()

            // 设置定位类型和值
            if (target === 'expected') {
                // 断言字段特殊处理
                if (config.assert_type !== undefined) {
                    config.assert_type = 'image'
                    config.expected = fileName
                }
                if (element.config.image_category && config.expected_image_scope !== undefined) {
                    config.expected_image_scope = element.config.image_category
                }
            } else {
                config[typeField] = 'image'
                config[valueField] = fileName
                // 填充图片路径
                if (element.config.image_category) {
                    config[scopeField] = element.config.image_category
                }
            }

            ElMessage.success(t('appAutomation.sceneBuilder.messages.linkedElement', { target: getTargetTitle(target), name: element.name, type: t('appAutomation.sceneBuilder.elementSelector.image') }))
        } else {
            ElMessage.warning(t('appAutomation.sceneBuilder.messages.imageMissingPath'))
        }
    } else if (element.element_type === 'pos') {
        if (element.config && element.config.x !== undefined && element.config.y !== undefined) {
            const posValue = `${element.config.x}, ${element.config.y}`

            config[typeField] = 'pos'
            config[valueField] = posValue

            ElMessage.success(t('appAutomation.sceneBuilder.messages.linkedElement', { target: getTargetTitle(target), name: element.name, type: t('appAutomation.sceneBuilder.elementSelector.coordinate') }))
        }
    } else if (element.element_type === 'region') {
        if (element.config &&
            element.config.x1 !== undefined &&
            element.config.y1 !== undefined &&
            element.config.x2 !== undefined &&
            element.config.y2 !== undefined) {
            const regionValue = `${element.config.x1}, ${element.config.y1}, ${element.config.x2}, ${element.config.y2}`

            config[typeField] = 'region'
            config[valueField] = regionValue

            ElMessage.success(t('appAutomation.sceneBuilder.messages.linkedElement', { target: getTargetTitle(target), name: element.name, type: t('appAutomation.sceneBuilder.elementSelector.region') }))
        }
    } else {
        ElMessage.warning(t('appAutomation.sceneBuilder.messages.elementTypeNotApplicable', { type: element.element_type, target: getTargetTitle(target) }))
    }
}

// 获取目标组的显示标题
const getTargetTitle = (target) => {
    const titleMap = {
        selector: t('appAutomation.sceneBuilder.fieldGroup.selector'),
        fallback: t('appAutomation.sceneBuilder.fieldGroup.fallback'),
        click: t('appAutomation.sceneBuilder.fieldGroup.click'),
        ocr: t('appAutomation.sceneBuilder.fieldGroup.ocr'),
        start: t('appAutomation.sceneBuilder.fieldGroup.start'),
        end: t('appAutomation.sceneBuilder.fieldGroup.end'),
        target: t('appAutomation.sceneBuilder.fieldGroup.target'),
        expected: t('appAutomation.sceneBuilder.fieldGroup.expected')
    }
    return titleMap[target] || target
}

const applyElement = (element) => {
    // 优先使用编辑对话框的步骤，否则使用场景步骤
    const targetStep = (customDialogVisible.value && editingActiveStep.value)
        ? editingActiveStep.value
        : activeStep.value
    
    if (!targetStep) {
        ElMessage.warning(t('appAutomation.sceneBuilder.messages.selectStepFirst'))
        return
    }
    
    // 根据元素类型自动填充配置
    if (!targetStep.config) {
        targetStep.config = {}
    }
    
    const config = targetStep.config
    const target = elementSelectorTarget.value
    console.log('config before:', JSON.stringify(config))
    
    // 保存关联信息
    const elementInfo = {
        id: element.id,
        name: element.name,
        type: element.element_type
    }
    
    if (target && linkedElements.value[target] !== undefined) {
        linkedElements.value[target] = elementInfo
        // 填充对应的字段
        fillFieldsByTarget(element, config, target)
    } else {
        ElMessage.warning(t('appAutomation.sceneBuilder.messages.noValidFieldGroup'))
    }
    
    console.log('config after:', JSON.stringify(config))
    console.log('=== applyElement 完成 ===')
    
    // 关闭选择器
    elementSelectorVisible.value = false
}

// 统一的清除关联函数
const clearLinkedElement = (target) => {
    linkedElements.value[target] = null
    
    const targetStep = (customDialogVisible.value && editingActiveStep.value)
        ? editingActiveStep.value
        : activeStep.value
    
    if (targetStep && targetStep.config) {
        const config = targetStep.config
        
        // 映射：target -> 字段前缀
        const prefixMap = {
            selector: '',
            fallback: 'fallback_',
            click: 'click_',
            ocr: 'ocr_',
            start: 'start_',
            end: 'end_',
            target: 'target_',
            expected: ''
        }
        
        const prefix = prefixMap[target] || ''
        const typeField = prefix ? `${prefix}selector_type` : 'selector_type'
        const valueField = prefix ? `${prefix}selector` : 'selector'
        const scopeField = prefix ? `${prefix}image_scope` : 'image_scope'
        
        // 清空 element_id
        const elementIdField = prefix ? `${prefix}element_id` : 'element_id'
        delete config[elementIdField]

        // 清空字段值
        if (target === 'expected') {
            if (config.expected !== undefined) {
                config.expected = ''
            }
            if (config.expected_image_scope !== undefined) {
                config.expected_image_scope = 'common'
            }
        } else {
            if (config[valueField] !== undefined) {
                config[valueField] = ''
            }
            if (config[scopeField] !== undefined) {
                config[scopeField] = 'common'
            }
        }
    }
    
    ElMessage.info(t('appAutomation.sceneBuilder.messages.clearedLink', { target: getTargetTitle(target) }))
}

const getTypeTagColor = (type) => {
    const colorMap = {
        'image': 'primary',
        'pos': 'success',
        'region': 'warning'
    }
    return colorMap[type] || ''
}

// Template refs assignment
defineExpose({
    customForm: customFormRef
})
</script>

<style scoped>
.ui-test-scene-builder {
    padding: 16px;
}

.page-header {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 16px;
}

.page-header h3 {
    margin: 0;
}

.header-actions {
    display: flex;
    gap: 8px;
}

.scene-config {
    margin-top: 12px;
}

.scene-layout {
    margin-top: 16px;
}

.card-title {
    font-weight: 600;
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.scene-variables {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.scene-variable-item {
    display: grid;
    grid-template-columns: 140px 120px 120px 1fr 1fr auto;
    gap: 8px;
    align-items: center;
}

.variable-hint {
    font-size: 12px;
    color: #909399;
    margin: 0 0 8px 0;
}

.hint-danger {
    color: #f56c6c;
}

.palette-list {
    min-height: 360px;
}

.palette-item {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    padding: 8px 10px;
    border: 1px dashed #dcdfe6;
    border-radius: 4px;
    margin-bottom: 8px;
    cursor: grab;
    background: #fafafa;
}

.palette-left {
    display: flex;
    align-items: center;
    gap: 8px;
}

.palette-actions {
    display: flex;
    align-items: center;
    gap: 6px;
    opacity: 0;
    transition: opacity 0.15s ease;
}

.palette-item:hover .palette-actions {
    opacity: 1;
}

.palette-empty {
    color: #909399;
    font-size: 12px;
    padding: 8px 10px;
}

.palette-name {
    font-weight: 500;
    line-height: 20px;
}

.palette-type {
    color: #909399;
    font-size: 12px;
    line-height: 20px;
}

.custom-steps-section {
    margin-top: 12px;
}

.custom-steps-label {
    font-size: 14px;
    font-weight: 500;
    color: #606266;
    margin-bottom: 8px;
}

.custom-edit-steps {
    display: flex;
    gap: 12px;
}

.custom-step-list {
    flex: 1;
    border: 1px solid #ebeef5;
    border-radius: 6px;
    padding: 8px;
    min-height: 220px;
    max-height: 500px;
    overflow-y: auto;
}

.custom-step-toolbar {
    display: flex;
    gap: 8px;
    margin-bottom: 8px;
    align-items: center;
}

.custom-step-toolbar .el-select .el-input__inner {
    height: 32px;
    line-height: 32px;
}

.custom-step-toolbar .el-button {
    height: 32px;
    padding: 0 12px;
}

.custom-step-items {
    min-height: 160px;
}

.custom-step-item {
    width: 100%;
}

.custom-step-item .scene-index {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    height: 20px;
    min-width: 10px;
    line-height: 1;
    padding: 0 6px;
}

.custom-step-config {
    flex: 1;
    border: 1px solid #ebeef5;
    border-radius: 6px;
    padding: 12px;
    min-height: 220px;
    max-height: 500px;
    overflow-y: auto;
}


.scene-card {
    min-height: 480px;
}

.scene-hint {
    color: #909399;
    font-size: 13px;
    padding: 12px;
}

.scene-list {
    min-height: 420px;
}

.scene-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 12px;
    border: 1px solid #ebeef5;
    border-radius: 6px;
    cursor: pointer;
    background: #fff;
}

.scene-item.active {
    border-color: #409eff;
    background: #ecf5ff;
}

.scene-item-main {
    display: flex;
    align-items: center;
    gap: 8px;
}

.scene-index {
    background: #409eff;
    color: #fff;
    font-size: 12px;
    padding: 2px 6px;
    border-radius: 10px;
}

.scene-name {
    font-weight: 500;
}

.scene-type {
    color: #909399;
    font-size: 12px;
}

.scene-item-wrapper {
    margin-bottom: 8px;
}

.scene-item-wrapper > .scene-item {
    margin-bottom: 0;
}

.scene-item.is-expanded {
    border-color: #e6a23c;
    border-bottom-left-radius: 0;
    border-bottom-right-radius: 0;
    margin-bottom: 0;
}

.custom-sub-steps {
    border: 1px solid #e6a23c;
    border-top: none;
    border-radius: 0 0 6px 6px;
    background: #fdf6ec;
    padding: 6px 6px 4px 6px;
}

.sub-step-item {
    margin-bottom: 4px !important;
    padding: 7px 10px !important;
    margin-left: 16px !important;
    border-color: #dcdfe6 !important;
    background: #fff !important;
    font-size: 13px;
}

.sub-step-item.active {
    border-color: #e6a23c !important;
    background: #fef0e0 !important;
}

.sub-index {
    background: #e6a23c !important;
    font-size: 11px !important;
    padding: 1px 5px !important;
}

.sub-step-toolbar {
    text-align: center;
    padding: 2px 0 4px 0;
}

.config-card {
    min-height: 480px;
}

.config-empty {
    color: #909399;
    font-size: 13px;
    padding: 16px;
}

.package-title {
    font-size: 12px;
    color: #909399;
    margin-bottom: 6px;
}

.package-list {
    max-height: 240px;
    overflow-y: auto;
    border: 1px solid #ebeef5;
    border-radius: 4px;
    padding: 6px;
}

.package-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 4px 0;
    border-bottom: 1px dashed #ebeef5;
}

.package-item:last-child {
    border-bottom: none;
}

.package-name {
    font-size: 12px;
    color: #303133;
    max-width: 220px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.package-meta {
    display: flex;
    gap: 8px;
    color: #909399;
    font-size: 12px;
}

.package-empty {
    color: #909399;
    font-size: 12px;
    padding: 6px 0;
}

/* 元素选择器样式 */
.element-selector-container {
    display: flex;
    flex-direction: column;
    gap: 15px;
}

.element-selector-filter {
    padding: 10px;
    background-color: #f5f7fa;
    border-radius: 4px;
}

.preview-image {
    display: flex;
    justify-content: center;
    align-items: center;
}

.preview-pos,
.preview-region {
    font-size: 12px;
}

/* 字段分组样式 */
.field-group {
    margin-bottom: 20px;
    padding: 16px;
    background: #f5f7fa;
    border-radius: 4px;
    border: 1px solid #e4e7ed;
}

.group-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid #dcdfe6;
}

.group-title {
    font-size: 14px;
    font-weight: 600;
    color: #303133;
}

.element-linked-alert {
    margin-bottom: 12px;
}

.field-group :deep(.el-form-item) {
    margin-bottom: 12px;
}

.field-group:last-child {
    margin-bottom: 0;
}
</style>

