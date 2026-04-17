<template>
  <div class="test-case-manager">
    <div class="page-header">
      <h1 class="page-title">{{ t('uiAutomation.testCase.title') }}</h1>
      <div class="header-actions">
        <el-select v-model="projectId" :placeholder="t('uiAutomation.project.selectProject')" style="width: 200px; margin-right: 15px" @change="onProjectChange">
          <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
        </el-select>
        <el-button @click="openFolderDialog">
          <el-icon><FolderAdd /></el-icon>
          {{ text.newFolder }}
        </el-button>
        <el-button type="primary" @click="openCreateDialog">
          <el-icon><Plus /></el-icon>
          {{ t('uiAutomation.testCase.newTestCase') }}
        </el-button>
        <el-button :disabled="!projectId" @click="openImportDialog">导入用例</el-button>
        <el-button :disabled="!projectId || !selectedCaseIds.length" @click="handleExportSelectedCases">导出选中</el-button>
        <el-button :disabled="!projectId" @click="handleExportAllCases">导出全部</el-button>
      </div>
    </div>

    <div class="main-content">
      <!-- 左侧：测试用例列表 -->
      <div class="left-panel">
        <div class="panel-header">
          <div class="panel-header-top">
            <h3>{{ t('uiAutomation.testCase.testCaseList') }}</h3>
            <span class="case-total">{{ filteredTestCases.length }}</span>
          </div>
          <div class="panel-filters">
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
            <el-select v-model="folderFilter" size="small">
              <el-option :label="text.folderFilterAll" value="all" />
              <el-option :label="text.folderFilterUngrouped" value="ungrouped" />
              <el-option
                v-for="folder in testCaseFolders"
                :key="folder.id"
                :label="folder.name"
                :value="String(folder.id)"
              />
            </el-select>
          </div>
          <div class="panel-toolbar">
            <span class="selected-summary">
              {{ text.selectedPrefix }} {{ selectedCaseIds.length }} {{ text.selectedSuffix }}
            </span>
            <el-button size="small" :disabled="!selectedCaseIds.length" @click="openMoveDialog(selectedCaseIds)">
              <el-icon><FolderOpened /></el-icon>
              {{ text.moveCases }}
            </el-button>
          </div>
        </div>

        <div class="test-case-list">
          <div
            v-for="testCase in filteredTestCases"
            :key="testCase.id"
            class="test-case-item"
            :class="{ active: selectedTestCase?.id === testCase.id }"
            @click="selectTestCase(testCase)"
          >
            <div class="case-header">
              <div class="case-select" @click.stop>
                <el-checkbox :model-value="selectedCaseIds.includes(testCase.id)" @change="toggleCaseSelection(testCase.id, $event)" />
              </div>
              <div class="case-info">
                <h4 class="case-name">{{ testCase.name }}</h4>
                <p class="case-description">{{ testCase.description || t('uiAutomation.testCase.noDescription') }}</p>
                <div class="case-actions">
                  <el-button size="small" text @click.stop="runTestCase(testCase)">
                    <el-icon><CaretRight /></el-icon>
                  </el-button>
                  <el-button size="small" text @click.stop="editTestCase(testCase)">
                    <el-icon><Edit /></el-icon>
                  </el-button>
                  <el-button size="small" text @click.stop="copyTestCase(testCase)">
                    <el-icon><CopyDocument /></el-icon>
                  </el-button>
                  <el-button size="small" text @click.stop="openMoveDialog([testCase.id])">
                    <el-icon><FolderOpened /></el-icon>
                  </el-button>
                  <el-button size="small" text type="danger" @click.stop="deleteTestCase(testCase)">
                    <el-icon><Delete /></el-icon>
                  </el-button>
                </div>
              </div>
            </div>
            <div class="case-meta">
              <!-- 移除状态显示 -->
              <el-tag v-if="testCase.folder" size="small" type="success">{{ testCase.folder.name }}</el-tag>
              <el-tag v-else size="small" type="info">{{ text.ungrouped }}</el-tag>
              <span class="step-count">{{ testCase.steps?.length || 0 }} {{ t('uiAutomation.testCase.stepsCount') }}</span>
              <span class="update-time">{{ formatTime(testCase.updated_at) }}</span>
            </div>
          </div>
          <el-empty v-if="!filteredTestCases.length" :description="text.emptyList" />
        </div>
      </div>

      <!-- 右侧：测试用例详情和步骤编辑 -->
      <div class="right-panel">
        <div v-if="selectedTestCase" class="test-case-detail">
          <div class="detail-header">
            <h3>{{ selectedTestCase.name }}</h3>
            <div class="detail-actions">
              <el-button size="small" @click="addStep">
                <el-icon><Plus /></el-icon>
                {{ t('uiAutomation.testCase.addStep') }}
              </el-button>
              <el-button size="small" type="primary" @click="saveTestCase">
                <el-icon><Check /></el-icon>
                {{ t('uiAutomation.testCase.saveTestCase') }}
              </el-button>
              <el-select v-model="selectedEngine" :placeholder="t('uiAutomation.testCase.selectEngine')" size="small" style="width: 130px; margin-right: 10px">
                <el-option label="Playwright" value="playwright" />
                <el-option label="Selenium" value="selenium" />
              </el-select>
              <el-select v-model="selectedBrowser" :placeholder="t('uiAutomation.testCase.selectBrowser')" size="small" style="width: 120px; margin-right: 10px">
                <el-option label="Chrome" value="chrome" />
                <el-option label="Firefox" value="firefox" />
                <el-option label="Safari" value="safari" />
                <el-option label="Edge" value="edge" />
              </el-select>
              <el-select v-model="headlessMode" :placeholder="t('uiAutomation.testCase.runModeLabel')" size="small" style="width: 110px; margin-right: 10px">
                <el-option :label="t('uiAutomation.testCase.headedMode')" :value="false" />
                <el-option :label="t('uiAutomation.testCase.headlessMode')" :value="true" />
              </el-select>
              <el-select v-model="executionMode" size="small" style="width: 120px; margin-right: 10px">
                <el-option label="服务器执行" value="server" />
                <el-option label="本机执行" value="local" />
              </el-select>
              <el-select
                v-if="executionMode === 'local'"
                v-model="selectedRunnerId"
                size="small"
                style="width: 180px; margin-right: 10px"
                placeholder="选择本地执行器"
              >
                <el-option
                  v-for="runner in onlineLocalRunners"
                  :key="runner.id"
                  :label="`${runner.name}${runner.hostname ? ` (${runner.hostname})` : ''}`"
                  :value="runner.id"
                />
              </el-select>
              <el-button size="small" type="success" @click="runTestCase(selectedTestCase)" :loading="isRunning">
                <el-icon v-if="!isRunning"><CaretRight /></el-icon>
                {{ isRunning ? t('uiAutomation.testCase.running') : t('uiAutomation.testCase.runLabel') }}
              </el-button>
              <el-button size="small" v-if="executionResult" @click="toggleView">
                <el-icon><component :is="showSteps ? 'View' : 'Edit'" /></el-icon>
                {{ showSteps ? t('uiAutomation.testCase.viewResult') : '返回测试步骤' }}
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

          <!-- 测试步骤编辑 -->
          <div class="steps-container" v-show="showSteps">
            <div class="steps-header">
              <div class="steps-header-main">
                <h4>{{ t('uiAutomation.testCase.testSteps') }}</h4>
                <span class="steps-selection-summary">已勾选 {{ checkedStepCount }} 个步骤</span>
              </div>
              <div class="steps-header-actions">
                <el-button size="small" :disabled="!checkedStepCount" @click="createTransactionBlock">
                  <el-icon><FolderAdd /></el-icon>
                  创建事务块
                </el-button>
                <el-button size="small" :disabled="!checkedStepCount" @click="removeSelectedFromTransaction">
                  <el-icon><FolderOpened /></el-icon>
                  移出事务块
                </el-button>
                <el-button size="small" text @click="expandAllSteps">
                  {{ allStepsExpanded ? t('uiAutomation.testCase.foldAll') : t('uiAutomation.testCase.expandAll') }}
                </el-button>
              </div>
            </div>

            <div class="steps-scroll-container">
              <div class="steps-list">
                <draggable
                  v-model="currentSteps"
                  item-key="id"
                  handle=".drag-handle"
                  @change="handleStepsReorder"
                >
                  <template #item="{ element, index }">
                    <div class="step-entry">
                      <div
                        v-if="shouldRenderTransactionHeader(index)"
                        class="transaction-block"
                        :class="{ collapsed: isTransactionCollapsed(element.transaction_id) }"
                      >
                        <div class="transaction-block-main" @click="toggleTransactionCollapse(element.transaction_id)">
                          <el-icon class="transaction-block-toggle">
                            <component :is="isTransactionCollapsed(element.transaction_id) ? 'ArrowDown' : 'ArrowUp'" />
                          </el-icon>
                          <el-checkbox
                            class="transaction-block-checkbox"
                            :model-value="isTransactionFullyChecked(element.transaction_id)"
                            @click.stop
                            @change="toggleTransactionSelection(element.transaction_id, $event)"
                          />
                          <el-icon class="transaction-block-icon"><Folder /></el-icon>
                          <span class="transaction-block-name">{{ element.transaction_name }}</span>
                          <el-tag size="small" type="info">{{ getTransactionStepCount(element.transaction_id) }} 步</el-tag>
                          <span class="transaction-block-summary">{{ getTransactionSummary(element.transaction_id) }}</span>
                        </div>
                        <div class="transaction-block-actions" @click.stop>
                          <el-button size="small" text @click="renameTransactionBlock(element.transaction_id)">
                            重命名
                          </el-button>
                          <el-button size="small" text type="danger" @click="clearTransactionBlock(element.transaction_id)">
                            解散事务块
                          </el-button>
                        </div>
                      </div>

                      <div
                        v-if="!shouldHideStepItem(element)"
                        class="step-item"
                        :class="{
                          expanded: element.expanded,
                          selected: isSelectedStep(element.id),
                          'step-item--in-transaction': hasTransaction(element)
                        }"
                        @click="selectStep(element.id)"
                      >
                        <div class="step-header">
                          <div class="step-left">
                            <el-checkbox
                              class="step-select-checkbox"
                              :model-value="isStepChecked(element.id)"
                              @click.stop
                              @change="toggleStepChecked(element.id, $event)"
                            />
                            <el-icon class="drag-handle" @click.stop><Rank /></el-icon>
                            <span class="step-number">{{ index + 1 }}</span>
                            <div class="step-summary" @click="element.expanded = !element.expanded">
                              <div class="step-summary-title">
                                {{ getStepSummary(element, index) }}
                              </div>
                              <div class="step-summary-meta">
                                <span>{{ getActionTypeText(element.action_type) }}</span>
                                <span v-if="needsElement(element.action_type)">{{ getStepElementSummary(element) }}</span>
                                <span v-if="element.transaction_name">事务块：{{ element.transaction_name }}</span>
                                <span v-if="canStoreVariable(element.action_type) && element.save_as">
                                  {{ formatStoredVariable(element.save_as) }}
                                </span>
                              </div>
                            </div>
                          </div>
                          <div class="step-right" @click.stop>
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
                        <div class="step-param">
                          <label>{{ t('uiAutomation.testCase.stepDescription') }}</label>
                          <el-input
                            v-model="element.description"
                            :placeholder="t('uiAutomation.testCase.stepDescPlaceholder')"
                            size="small"
                          />
                        </div>

                        <div class="step-param">
                          <label>{{ t('uiAutomation.testCase.selectAction') }}</label>
                          <el-select
                            v-model="element.action_type"
                            :placeholder="t('uiAutomation.testCase.selectAction')"
                            size="small"
                            style="width: 220px"
                            @change="onActionTypeChange(element)"
                          >
                            <el-option :label="t('uiAutomation.testCase.actionClick')" value="click" />
                            <el-option :label="t('uiAutomation.testCase.actionFill')" value="fill" />
                            <el-option :label="t('uiAutomation.testCase.actionFillAndEnter')" value="fillAndEnter" />
                            <el-option :label="t('uiAutomation.testCase.actionGetText')" value="getText" />
                            <el-option :label="t('uiAutomation.testCase.actionWaitFor')" value="waitFor" />
                            <el-option :label="t('uiAutomation.testCase.actionHover')" value="hover" />
                            <el-option :label="t('uiAutomation.testCase.actionScroll')" value="scroll" />
                            <el-option label="拖拽" value="drag" />
                            <el-option :label="t('uiAutomation.testCase.actionScreenshot')" value="screenshot" />
                            <el-option :label="t('uiAutomation.testCase.actionAssert')" value="assert" />
                            <el-option :label="t('uiAutomation.testCase.actionWait')" value="wait" />
                            <el-option :label="t('uiAutomation.testCase.actionSwitchTab')" value="switchTab" />
                            <el-option :label="t('uiAutomation.testCase.actionCloseCurrentPage')" value="closeCurrentPage" />
                          </el-select>
                        </div>

                        <div v-if="needsElement(element.action_type)" class="step-param">
                          <label>{{ t('uiAutomation.testCase.selectElement') }}</label>
                          <el-button
                            size="small"
                            class="element-selector-trigger"
                            @click="openElementSelector(element)"
                          >
                            <el-icon><FolderOpened /></el-icon>
                            <span class="element-selector-text">{{ getSelectedElementLabel(element.element_id) }}</span>
                          </el-button>
                        </div>
                        <!-- 输入参数 -->
                        <div v-if="element.action_type === 'drag'" class="step-param">
                          <label>拖拽目标元素</label>
                          <el-button
                            size="small"
                            class="element-selector-trigger"
                            @click="openElementSelector(element, 'drag_target_element_id')"
                          >
                            <el-icon><FolderOpened /></el-icon>
                            <span class="element-selector-text">{{ getSelectedElementLabel(element.drag_target_element_id) }}</span>
                          </el-button>
                        </div>

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
                        <div v-if="canStoreVariable(element.action_type)" class="step-param step-param--stacked">
                          <label>{{ t('uiAutomation.testCase.storeAs') }}</label>
                          <div class="step-param-main">
                            <el-input
                              v-model="element.save_as"
                              :placeholder="t('uiAutomation.testCase.storeAsPlaceholder')"
                              size="small"
                              clearable
                            />
                            <div class="step-help">
                              {{ getStoreAsHelp(element.save_as) }}
                            </div>
                          </div>
                        </div>

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
              <div class="result-header-main">
                <h4>{{ t('uiAutomation.testCase.executionResult') }}</h4>
                <el-tag :type="executionResult.success ? 'success' : 'danger'">
                  {{ executionResult.success ? t('uiAutomation.testCase.executionSuccess') : t('uiAutomation.testCase.executionFailed') }}
                </el-tag>
              </div>
              <div class="result-header-actions">
                <el-button size="small" @click="returnToTestSteps">
                  <el-icon><ArrowLeft /></el-icon>
                  返回测试步骤
                </el-button>
              </div>
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
        <el-form-item :label="text.folderLabel">
          <el-select v-model="testCaseForm.folder_id" clearable style="width: 100%" :placeholder="text.folderPlaceholder">
            <el-option :label="text.ungrouped" :value="null" />
            <el-option v-for="folder in testCaseFolders" :key="folder.id" :label="folder.name" :value="folder.id" />
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
      v-model="showFolderDialog"
      :title="text.newFolder"
      :close-on-click-modal="false"
      width="420px"
    >
      <el-form :model="folderForm" label-width="100px">
        <el-form-item :label="text.folderName" required>
          <el-input v-model="folderForm.name" :placeholder="text.folderNamePlaceholder" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showFolderDialog = false">{{ t('uiAutomation.common.cancel') }}</el-button>
          <el-button type="primary" @click="saveFolder">{{ t('uiAutomation.common.confirm') }}</el-button>
        </span>
      </template>
    </el-dialog>

    <el-dialog
      v-model="showMoveDialog"
      :title="text.moveCases"
      :close-on-click-modal="false"
      width="420px"
    >
      <el-form :model="moveForm" label-width="100px">
        <el-form-item :label="text.moveCount">
          <span>{{ text.selectedPrefix }} {{ moveForm.test_case_ids.length }} {{ text.selectedSuffix }}</span>
        </el-form-item>
        <el-form-item :label="text.targetFolder">
          <el-select v-model="moveForm.folder_id" clearable style="width: 100%" :placeholder="text.folderPlaceholder">
            <el-option :label="text.ungrouped" :value="null" />
            <el-option v-for="folder in testCaseFolders" :key="folder.id" :label="folder.name" :value="folder.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showMoveDialog = false">{{ t('uiAutomation.common.cancel') }}</el-button>
          <el-button type="primary" @click="submitMoveCases">{{ t('uiAutomation.common.confirm') }}</el-button>
        </span>
      </template>
    </el-dialog>

    <el-dialog
      v-model="showImportDialog"
      title="导入测试用例"
      :close-on-click-modal="false"
      width="420px"
    >
      <el-form label-width="100px">
        <el-form-item label="导入项目">
          <span>{{ selectedProject?.name || '-' }}</span>
        </el-form-item>
        <el-form-item label="JSON文件">
          <el-upload
            :auto-upload="false"
            :limit="1"
            accept=".json,application/json"
            :show-file-list="true"
            :on-change="handleImportFileChange"
            :on-remove="handleImportFileRemove"
          >
            <el-button>选择文件</el-button>
          </el-upload>
        </el-form-item>
        <el-form-item label="覆盖同名用例">
          <el-switch v-model="importOverwrite" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showImportDialog = false">{{ t('uiAutomation.common.cancel') }}</el-button>
          <el-button type="primary" :loading="importing" @click="submitImportCases">开始导入</el-button>
        </span>
      </template>
    </el-dialog>

    <el-dialog
      v-model="showElementSelectorDialog"
      :title="text.selectElement"
      :close-on-click-modal="false"
      :width="`${elementSelectorDialogSize.width}px`"
      class="element-selector-dialog"
    >
      <div
        class="element-selector-dialog-body"
        :style="{ height: `${elementSelectorDialogSize.height}px` }"
      >
        <el-input
          v-model="elementSelectorKeyword"
          :placeholder="text.searchElementPlaceholder"
          clearable
          class="element-selector-search"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>

        <div class="element-selector-tree-wrapper">
          <el-tree
            :data="filteredElementTreeOptions"
            :props="{ children: 'children', label: 'name' }"
            node-key="treeKey"
            :default-expand-all="Boolean(elementSelectorKeyword)"
            :expand-on-click-node="false"
            highlight-current
            :current-node-key="currentSelectingStep?.element_id ? `element-${currentSelectingStep.element_id}` : undefined"
            @node-click="handleElementTreeNodeClick"
          >
            <template #default="{ data }">
              <div class="element-tree-node">
                <div class="element-tree-node-main">
                  <el-icon class="element-tree-node-icon">
                    <component :is="data.type === 'group' ? Folder : Document" />
                  </el-icon>
                  <el-tooltip
                    v-if="data.type === 'element'"
                    placement="right-start"
                    effect="dark"
                    :show-after="150"
                    popper-class="element-data-tooltip"
                  >
                    <template #content>
                      <div class="element-tooltip-content">
                        <div class="element-tooltip-title">{{ data.name }}</div>
                        <pre class="element-tooltip-json">{{ getElementTooltipContent(data) }}</pre>
                      </div>
                    </template>
                    <span class="element-tree-node-label is-hoverable">{{ data.name }}</span>
                  </el-tooltip>
                  <span v-else class="element-tree-node-label">{{ data.name }}</span>
                </div>
                <span v-if="data.type === 'element'" class="element-tree-node-extra">{{ data.locator_value }}</span>
              </div>
            </template>
          </el-tree>
          <el-empty v-if="!filteredElementTreeOptions.length" :description="text.noMatchedElements" />
        </div>

        <div
          class="element-selector-resizer"
          @mousedown="startElementSelectorResize"
        />
      </div>
    </el-dialog>

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
                  <el-button link type="primary" size="small">{{ t('uiAutomation.testCase.insert') }}</el-button>
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
import { ref, reactive, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Search, Plus, Edit, Delete, Check, CaretRight, ArrowUp, ArrowDown, Rank, Picture, Warning, View, ZoomIn, Refresh, WarningFilled, MagicStick, CopyDocument, FolderAdd, FolderOpened, Folder, Document, ArrowLeft
} from '@element-plus/icons-vue'
import draggable from 'vuedraggable'
import DataFactorySelector from '@/components/DataFactorySelector.vue'
import { useI18n } from 'vue-i18n'

import {
  getUiProjects,
  getElementTree,
  getElementGroupTree,
  createTestCase,
  createTestCaseFolder,
  updateTestCase,
  deleteTestCase as deleteTestCaseApi,
  getTestCaseFolders,
  getTestCases,
  moveTestCases,
  runTestCase as runTestCaseApi,
  copyTestCase as copyTestCaseApi,
  exportTestCases,
  importTestCases,
  getLocatorStrategies,
  getLocalRunners,
  getTestCaseExecutionDetail
} from '@/api/ui_automation'
import { getVariableFunctions } from '@/api/data-factory'
import { useUiAutomationStore } from '@/stores/uiAutomation'

const { t } = useI18n()
const uiAutomationStore = useUiAutomationStore()

const text = {
  newFolder: '\u65b0\u5efa\u6587\u4ef6\u5939',
  folderFilterAll: '\u5168\u90e8\u6587\u4ef6\u5939',
  folderFilterUngrouped: '\u672a\u5206\u7ec4',
  selectedPrefix: '\u5df2\u9009',
  selectedSuffix: '\u9879',
  moveCases: '\u79fb\u52a8\u7528\u4f8b',
  emptyList: '\u6682\u65e0\u6d4b\u8bd5\u7528\u4f8b',
  ungrouped: '\u672a\u5206\u7ec4',
  folderLabel: '\u6240\u5c5e\u6587\u4ef6\u5939',
  folderPlaceholder: '\u8bf7\u9009\u62e9\u6587\u4ef6\u5939',
  folderName: '\u6587\u4ef6\u5939\u540d\u79f0',
  folderNamePlaceholder: '\u8bf7\u8f93\u5165\u6587\u4ef6\u5939\u540d\u79f0',
  moveCount: '\u79fb\u52a8\u6570\u91cf',
  targetFolder: '\u76ee\u6807\u6587\u4ef6\u5939',
  folderNameRequired: '\u8bf7\u8f93\u5165\u6587\u4ef6\u5939\u540d\u79f0',
  folderCreateSuccess: '\u6587\u4ef6\u5939\u521b\u5efa\u6210\u529f',
  folderCreateFailed: '\u6587\u4ef6\u5939\u521b\u5efa\u5931\u8d25',
  moveCasesEmpty: '\u8bf7\u5148\u9009\u62e9\u9700\u8981\u79fb\u52a8\u7684\u7528\u4f8b',
  moveSuccess: '\u7528\u4f8b\u79fb\u52a8\u6210\u529f',
  moveFailed: '\u7528\u4f8b\u79fb\u52a8\u5931\u8d25',
  selectElement: '\u9009\u62e9\u5143\u7d20',
  selectElementPlaceholder: '\u8bf7\u9009\u62e9\u5143\u7d20',
  searchElementPlaceholder: '\u641c\u7d22\u5143\u7d20\u540d\u79f0\u6216\u5b9a\u4f4d\u5185\u5bb9',
  noMatchedElements: '\u672a\u627e\u5230\u5339\u914d\u7684\u5143\u7d20',
  ungroupedElements: '\u672a\u5206\u7ec4\u5143\u7d20'
}

// 响应式数据
const projects = ref([])
const projectId = ref('')
const testCases = ref([])
const testCaseFolders = ref([])
const elementGroups = ref([])
const selectedTestCase = ref(null)
const selectedCaseIds = ref([])
const currentSteps = ref([])
const selectedStepId = ref(null)
const checkedStepIds = ref([])
const transactionCollapseState = ref({})
const availableElements = ref([])
const searchKeyword = ref('')
const folderFilter = ref('all')
const showCreateDialog = ref(false)
const showFolderDialog = ref(false)
const showMoveDialog = ref(false)
const showImportDialog = ref(false)
const showElementSelectorDialog = ref(false)
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
const executionMode = ref('server')
const localRunners = ref([])
const selectedRunnerId = ref(null)
const showVariableHelper = ref(false)
const currentEditingStep = ref(null)
const currentEditingField = ref('')
const showDataFactorySelector = ref(false)
const currentStepForDataFactory = ref(null)
const currentFieldForDataFactory = ref('')
const currentSelectingStep = ref(null)
const currentSelectingField = ref('element_id')
const elementSelectorKeyword = ref('')
const variableCategories = ref([])
const loading = ref(false)
const importing = ref(false)
let localExecutionPollTimer = null
const elementSelectorDialogSize = reactive({
  width: 640,
  height: 520
})
const ELEMENT_SELECTOR_MIN_WIDTH = 520
const ELEMENT_SELECTOR_MIN_HEIGHT = 360
const ELEMENT_SELECTOR_VIEWPORT_WIDTH_PADDING = 80
const ELEMENT_SELECTOR_VIEWPORT_HEIGHT_PADDING = 140
let elementSelectorResizeHandlers = null
const STEP_RUNTIME_VARIABLE_RE = /^[A-Za-z_][A-Za-z0-9_]*$/
const importFile = ref(null)
const importOverwrite = ref(false)



// 表单数据
const testCaseForm = reactive({
  name: '',
  description: '',
  priority: 'medium',
  folder_id: null
})

const folderForm = reactive({
  name: ''
})

const moveForm = reactive({
  test_case_ids: [],
  folder_id: null
})

// 计算属性
const filteredTestCases = computed(() => {
  const keyword = searchKeyword.value.trim()

  return testCases.value.filter((tc) => {
    const matchedFolder =
      folderFilter.value === 'all' ||
      (folderFilter.value === 'ungrouped' && !tc.folder) ||
      String(tc.folder?.id || '') === folderFilter.value

    const matchedKeyword =
      !keyword ||
      tc.name.includes(keyword) ||
      tc.description?.includes(keyword)

    return matchedFolder && matchedKeyword
  })
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

const onlineLocalRunners = computed(() => {
  return localRunners.value.filter(item => item.is_online)
})

const selectedProject = computed(() => {
  return projects.value.find(item => String(item.id) === String(projectId.value)) || null
})

const projectVariableCategory = computed(() => {
  const variables = (selectedProject.value?.global_variables || []).map(item => ({
    name: item.name,
    desc: item.description || `当前值: ${item.value || ''}`,
    syntax: `\${${item.name}}`,
    example: `\${${item.name}}`
  }))

  if (!variables.length) {
    return null
  }

  return {
    label: '项目全局变量',
    variables
  }
})

const elementTreeOptions = computed(() => {
  const mapElementNode = (element) => ({
    ...element,
    treeKey: `element-${element.id}`,
    type: 'element',
    children: []
  })

  const buildGroupNodes = (groups) => {
    return groups.map((group) => {
      const childGroups = buildGroupNodes(group.children || [])
      const childElements = availableElements.value
        .filter(element => element.group_id === group.id)
        .map(mapElementNode)

      return {
        ...group,
        treeKey: `group-${group.id}`,
        type: 'group',
        children: [...childGroups, ...childElements]
      }
    })
  }

  const groupNodes = buildGroupNodes(elementGroups.value || [])
  const ungroupedElements = availableElements.value
    .filter(element => !element.group_id)
    .map(mapElementNode)

  if (ungroupedElements.length > 0) {
    groupNodes.push({
      id: 'ungrouped-root',
      treeKey: 'group-ungrouped-root',
      name: text.ungroupedElements,
      type: 'group',
      children: ungroupedElements
    })
  }

  return groupNodes
})

const filteredElementTreeOptions = computed(() => {
  const keyword = elementSelectorKeyword.value.trim().toLowerCase()
  if (!keyword) {
    return elementTreeOptions.value
  }

  const filterNodes = (nodes) => {
    return nodes.reduce((result, node) => {
      const children = node.children ? filterNodes(node.children) : []
      const matchedSelf = [
        node.name,
        node.locator_value,
        node.description,
        node.page,
        node.component_name,
        node.locator_strategy
      ].some((value) => String(value || '').toLowerCase().includes(keyword))

      if (matchedSelf || children.length > 0) {
        result.push({
          ...node,
          children
        })
      }

      return result
    }, [])
  }

  return filterNodes(elementTreeOptions.value)
})

// 方法定义
const canStoreVariable = (actionType) => {
  return ['fill', 'fillAndEnter', 'switchTab', 'assert'].includes(actionType)
}

const parseDragTargetPayload = (inputValue) => {
  const rawValue = String(inputValue || '').trim()
  if (!rawValue) {
    return {}
  }

  try {
    const payload = JSON.parse(rawValue)
    return typeof payload === 'object' && payload !== null ? payload : {}
  } catch (error) {
    return {}
  }
}

const buildDragTargetPayload = (targetElementId) => {
  const targetElement = availableElements.value.find(item => item.id === targetElementId)
  if (!targetElement) {
    return ''
  }

  return JSON.stringify({
    target_element_id: targetElement.id,
    target_element_name: targetElement.name,
    target_locator_strategy: targetElement.locator_strategy?.name || targetElement.locator_strategy || 'css',
    target_locator_value: targetElement.locator_value
  })
}

const createStepDraft = (step = {}, expanded = false) => ({
  ...(() => {
    const dragPayload = parseDragTargetPayload(step.input_value)
    return {
      drag_target_element_id: dragPayload.target_element_id || ''
    }
  })(),
  id: step.id ?? `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
  action_type: step.action_type || 'click',
  element_id: step.element_id ?? step.element ?? '',
  input_value: step.input_value || '',
  wait_time: Number(step.wait_time ?? 1000) || 1000,
  assert_type: step.assert_type || 'textContains',
  assert_value: step.assert_value || '',
  description: step.description || '',
  save_as: step.save_as || '',
  transaction_id: String(step.transaction_id || '').trim(),
  transaction_name: String(step.transaction_name || '').trim(),
  expanded
})

const createTransactionId = () => {
  return `tx-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

const getTransactionId = (step) => {
  return String(step?.transaction_id || '').trim()
}

const getTransactionName = (step) => {
  return String(step?.transaction_name || '').trim()
}

const hasTransaction = (step) => {
  return Boolean(getTransactionId(step))
}

const isStepChecked = (stepId) => {
  return checkedStepIds.value.some(id => isSameStepId(id, stepId))
}

const checkedStepCount = computed(() => checkedStepIds.value.length)

const syncCheckedStepIds = () => {
  checkedStepIds.value = checkedStepIds.value.filter(id =>
    currentSteps.value.some(step => isSameStepId(step.id, id))
  )
}

const syncTransactionCollapseMap = () => {
  const validTransactionIds = new Set(
    currentSteps.value
      .map(step => getTransactionId(step))
      .filter(Boolean)
  )

  transactionCollapseState.value = Object.fromEntries(
    Object.entries(transactionCollapseState.value).filter(([transactionId]) => validTransactionIds.has(transactionId))
  )
}

const clearTransactionFromSteps = (steps = []) => {
  steps.forEach((step) => {
    step.transaction_id = ''
    step.transaction_name = ''
  })
}

const applyTransactionToStep = (step, transactionSource) => {
  const transactionId = getTransactionId(transactionSource)
  const transactionName = getTransactionName(transactionSource)

  if (!transactionId || !transactionName) {
    step.transaction_id = ''
    step.transaction_name = ''
    return
  }

  step.transaction_id = transactionId
  step.transaction_name = transactionName
}

const getAdjacentTransactionSource = (index) => {
  const previousStep = currentSteps.value[index - 1]
  const nextStep = currentSteps.value[index + 1]
  const previousTransactionId = getTransactionId(previousStep)
  const nextTransactionId = getTransactionId(nextStep)

  if (previousTransactionId && previousTransactionId === nextTransactionId) {
    return previousStep
  }

  if (previousTransactionId) {
    return previousStep
  }

  if (nextTransactionId) {
    return nextStep
  }

  return null
}

const normalizeTransactionBlocks = () => {
  const seenTransactionIds = new Set()
  let segmentSteps = []
  let segmentTransactionId = ''
  let segmentTransactionName = ''

  const finalizeSegment = () => {
    if (!segmentSteps.length) {
      return
    }

    if (!segmentTransactionId || !segmentTransactionName || segmentSteps.length < 2 || seenTransactionIds.has(segmentTransactionId)) {
      clearTransactionFromSteps(segmentSteps)
      delete transactionCollapseState.value[segmentTransactionId]
    } else {
      segmentSteps.forEach((step) => {
        step.transaction_id = segmentTransactionId
        step.transaction_name = segmentTransactionName
      })
      seenTransactionIds.add(segmentTransactionId)
    }

    segmentSteps = []
    segmentTransactionId = ''
    segmentTransactionName = ''
  }

  currentSteps.value.forEach((step) => {
    const transactionId = getTransactionId(step)
    const transactionName = getTransactionName(step)

    if (!transactionId || !transactionName) {
      finalizeSegment()
      step.transaction_id = ''
      step.transaction_name = ''
      return
    }

    if (!segmentSteps.length || segmentTransactionId === transactionId) {
      segmentSteps.push(step)
      segmentTransactionId = transactionId
      segmentTransactionName = segmentTransactionName || transactionName || '未命名事务块'
      return
    }

    finalizeSegment()
    segmentSteps = [step]
    segmentTransactionId = transactionId
    segmentTransactionName = transactionName || '未命名事务块'
  })

  finalizeSegment()

  syncCheckedStepIds()
  syncTransactionCollapseMap()
  return

  const groups = new Map()

  currentSteps.value.forEach((step) => {
    const transactionId = getTransactionId(step)
    const transactionName = getTransactionName(step)

    if (!transactionId || !transactionName) {
      step.transaction_id = ''
      step.transaction_name = ''
      return
    }

    if (!groups.has(transactionId)) {
      groups.set(transactionId, [])
    }
    groups.get(transactionId).push(step)
  })

  groups.forEach((steps, transactionId) => {
    if (steps.length < 2) {
      steps.forEach((step) => {
        step.transaction_id = ''
        step.transaction_name = ''
      })
      delete transactionCollapseState.value[transactionId]
      return
    }

    const transactionName = steps.map(step => getTransactionName(step)).find(Boolean) || '未命名事务块'
    steps.forEach((step) => {
      step.transaction_id = transactionId
      step.transaction_name = transactionName
    })
  })

  syncCheckedStepIds()
  syncTransactionCollapseMap()
}

const toggleStepChecked = (stepId, checked) => {
  if (checked) {
    if (!isStepChecked(stepId)) {
      checkedStepIds.value.push(stepId)
    }
    return
  }

  checkedStepIds.value = checkedStepIds.value.filter(id => !isSameStepId(id, stepId))
}

const getTransactionSteps = (transactionId) => {
  return currentSteps.value.filter(step => getTransactionId(step) === String(transactionId || ''))
}

const getCheckedStepIndices = () => {
  return currentSteps.value.reduce((result, step, index) => {
    if (isStepChecked(step.id)) {
      result.push(index)
    }
    return result
  }, [])
}

const areCheckedStepsConsecutive = () => {
  const indices = getCheckedStepIndices()
  if (indices.length < 2) {
    return true
  }

  return indices.every((stepIndex, index) => index === 0 || stepIndex === indices[index - 1] + 1)
}

const shouldRenderTransactionHeader = (index) => {
  const currentStep = currentSteps.value[index]
  if (!hasTransaction(currentStep)) {
    return false
  }

  const previousStep = currentSteps.value[index - 1]
  return getTransactionId(previousStep) !== getTransactionId(currentStep)
}

const isTransactionCollapsed = (transactionId) => {
  return Boolean(transactionCollapseState.value[String(transactionId || '')])
}

const shouldHideStepItem = (step) => {
  return hasTransaction(step) && isTransactionCollapsed(getTransactionId(step))
}

const toggleTransactionCollapse = (transactionId) => {
  const normalizedId = String(transactionId || '')
  transactionCollapseState.value = {
    ...transactionCollapseState.value,
    [normalizedId]: !isTransactionCollapsed(normalizedId)
  }
}

const getTransactionStepCount = (transactionId) => {
  return getTransactionSteps(transactionId).length
}

const getTransactionSummary = (transactionId) => {
  const steps = getTransactionSteps(transactionId)
  const labels = steps
    .map((step, index) => String(step.description || '').trim() || `${getActionTypeText(step.action_type)} ${index + 1}`)
    .slice(0, 3)

  if (!labels.length) {
    return '点击展开查看事务块步骤'
  }

  return labels.length < steps.length
    ? `${labels.join(' / ')} 等`
    : labels.join(' / ')
}

const isTransactionFullyChecked = (transactionId) => {
  const steps = getTransactionSteps(transactionId)
  return steps.length > 0 && steps.every(step => isStepChecked(step.id))
}

const toggleTransactionSelection = (transactionId, checked) => {
  const transactionStepIds = getTransactionSteps(transactionId).map(step => step.id)
  if (checked) {
    transactionStepIds.forEach((stepId) => {
      if (!isStepChecked(stepId)) {
        checkedStepIds.value.push(stepId)
      }
    })
    return
  }

  checkedStepIds.value = checkedStepIds.value.filter(id =>
    !transactionStepIds.some(stepId => isSameStepId(stepId, id))
  )
}

const createTransactionBlock = async () => {
  if (!checkedStepCount.value) {
    ElMessage.warning('请先勾选要归入事务块的步骤')
    return
  }

  if (!areCheckedStepsConsecutive()) {
    ElMessage.warning('事务块内的步骤必须连续，请重新勾选连续的步骤')
    return
  }

  try {
    const { value } = await ElMessageBox.prompt('请输入事务块名称，例如“登录功能”', '创建事务块', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputPlaceholder: '请输入事务块名称',
      inputValidator: (inputValue) => String(inputValue || '').trim() ? true : '事务块名称不能为空'
    })

    const transactionId = createTransactionId()
    const transactionName = String(value || '').trim()

    currentSteps.value.forEach((step) => {
      if (isStepChecked(step.id)) {
        step.transaction_id = transactionId
        step.transaction_name = transactionName
      }
    })

    transactionCollapseState.value = {
      ...transactionCollapseState.value,
      [transactionId]: false
    }
    normalizeTransactionBlocks()
    ElMessage.success(`已创建事务块“${transactionName}”`)
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('创建事务块失败')
    }
  }
}

const removeSelectedFromTransaction = () => {
  if (!checkedStepCount.value) {
    ElMessage.warning('请先勾选要移出的步骤')
    return
  }

  currentSteps.value.forEach((step) => {
    if (isStepChecked(step.id)) {
      step.transaction_id = ''
      step.transaction_name = ''
    }
  })

  normalizeTransactionBlocks()
  ElMessage.success('已将选中步骤移出事务块')
}

const renameTransactionBlock = async (transactionId) => {
  const steps = getTransactionSteps(transactionId)
  if (!steps.length) {
    return
  }

  try {
    const { value } = await ElMessageBox.prompt('请输入新的事务块名称', '重命名事务块', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputValue: steps[0].transaction_name || '',
      inputPlaceholder: '请输入事务块名称',
      inputValidator: (inputValue) => String(inputValue || '').trim() ? true : '事务块名称不能为空'
    })

    const transactionName = String(value || '').trim()
    steps.forEach((step) => {
      step.transaction_name = transactionName
    })
    normalizeTransactionBlocks()
    ElMessage.success('事务块名称已更新')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('重命名事务块失败')
    }
  }
}

const clearTransactionBlock = (transactionId) => {
  getTransactionSteps(transactionId).forEach((step) => {
    step.transaction_id = ''
    step.transaction_name = ''
  })

  normalizeTransactionBlocks()
  ElMessage.success('已解散事务块')
}

const isSameStepId = (left, right) => {
  if (left === null || left === undefined || right === null || right === undefined) {
    return false
  }

  return String(left) === String(right)
}

const isSelectedStep = (stepId) => {
  return isSameStepId(stepId, selectedStepId.value)
}

const selectStep = (stepId) => {
  selectedStepId.value = stepId
}

const getSelectedStepIndex = () => {
  return currentSteps.value.findIndex(step => isSameStepId(step.id, selectedStepId.value))
}

const buildStepPayload = (step, index) => ({
  id: step.id,
  step_number: index + 1,
  action_type: step.action_type || 'click',
  element_id: step.element_id || null,
  input_value: step.action_type === 'drag'
    ? buildDragTargetPayload(step.drag_target_element_id)
    : (needsInputValue(step.action_type) ? (step.input_value || '') : ''),
  wait_time: needsWaitTime(step.action_type) ? (Number(step.wait_time) || 1000) : 1000,
  assert_type: step.action_type === 'assert' ? (step.assert_type || 'textContains') : '',
  assert_value: step.action_type === 'assert' ? (step.assert_value || '') : '',
  description: String(step.description || '').trim(),
  save_as: canStoreVariable(step.action_type) ? String(step.save_as || '').trim() : '',
  transaction_id: getTransactionId(step),
  transaction_name: getTransactionName(step)
})

const formatStoredVariable = (name) => {
  const value = String(name || '').trim()
  return value ? `\${${value}}` : ''
}

const getStoreAsHelp = (name) => {
  const variableName = String(name || '').trim() || 'abcd'
  return t('uiAutomation.testCase.storeAsHelp', { name: variableName })
}

const getStepSummary = (step, index) => {
  const description = String(step.description || '').trim()
  if (description) {
    return description
  }
  return t('uiAutomation.testCase.stepSummaryPlaceholder', { step: index + 1 })
}

const getStepElementSummary = (step) => {
  if (!needsElement(step.action_type)) {
    return ''
  }
  const element = availableElements.value.find(item => item.id === step.element_id)
  if (step.action_type === 'drag') {
    const targetElement = availableElements.value.find(item => item.id === step.drag_target_element_id)
    if (element?.name && targetElement?.name) {
      return `${element.name} -> ${targetElement.name}`
    }
  }
  return element?.name || t('uiAutomation.testCase.elementPending')
}

const validateCurrentSteps = () => {
  for (const [index, step] of currentSteps.value.entries()) {
    step.description = String(step.description || '').trim()
    step.save_as = canStoreVariable(step.action_type) ? String(step.save_as || '').trim() : ''

    if (!step.description) {
      step.expanded = true
      ElMessage.warning(t('uiAutomation.testCase.stepDescriptionRequired', { step: index + 1 }))
      return false
    }

    if (step.save_as && !STEP_RUNTIME_VARIABLE_RE.test(step.save_as)) {
      step.expanded = true
      ElMessage.warning(t('uiAutomation.testCase.storeAsInvalid', { step: index + 1 }))
      return false
    }

    if (step.action_type === 'drag' && !step.drag_target_element_id) {
      step.expanded = true
      ElMessage.warning(`步骤 ${index + 1} 请选择拖拽目标元素`)
      return false
    }
  }

  return true
}

const getElementSelectorMaxWidth = () => {
  if (typeof window === 'undefined') {
    return elementSelectorDialogSize.width
  }

  return Math.max(ELEMENT_SELECTOR_MIN_WIDTH, window.innerWidth - ELEMENT_SELECTOR_VIEWPORT_WIDTH_PADDING)
}

const getElementSelectorMaxHeight = () => {
  if (typeof window === 'undefined') {
    return elementSelectorDialogSize.height
  }

  return Math.max(ELEMENT_SELECTOR_MIN_HEIGHT, window.innerHeight - ELEMENT_SELECTOR_VIEWPORT_HEIGHT_PADDING)
}

const normalizeElementSelectorDialogSize = () => {
  elementSelectorDialogSize.width = Math.min(
    Math.max(elementSelectorDialogSize.width, ELEMENT_SELECTOR_MIN_WIDTH),
    getElementSelectorMaxWidth()
  )
  elementSelectorDialogSize.height = Math.min(
    Math.max(elementSelectorDialogSize.height, ELEMENT_SELECTOR_MIN_HEIGHT),
    getElementSelectorMaxHeight()
  )
}

const getElementTooltipContent = (node) => {
  if (!node || node.type !== 'element') {
    return ''
  }

  const tooltipData = Object.entries(node).reduce((result, [key, value]) => {
    if (['children', 'treeKey'].includes(key) || value === undefined) {
      return result
    }

    result[key] = value
    return result
  }, {})

  return JSON.stringify(tooltipData, null, 2)
}

const stopElementSelectorResize = () => {
  if (!elementSelectorResizeHandlers) {
    return
  }

  document.removeEventListener('mousemove', elementSelectorResizeHandlers.handleMouseMove)
  document.removeEventListener('mouseup', elementSelectorResizeHandlers.handleMouseUp)
  document.body.style.userSelect = ''
  elementSelectorResizeHandlers = null
}

const startElementSelectorResize = (event) => {
  if (typeof window === 'undefined') {
    return
  }

  event.preventDefault()

  const startX = event.clientX
  const startY = event.clientY
  const initialWidth = elementSelectorDialogSize.width
  const initialHeight = elementSelectorDialogSize.height

  const handleMouseMove = (moveEvent) => {
    const nextWidth = initialWidth + (moveEvent.clientX - startX)
    const nextHeight = initialHeight + (moveEvent.clientY - startY)

    elementSelectorDialogSize.width = Math.min(
      Math.max(nextWidth, ELEMENT_SELECTOR_MIN_WIDTH),
      getElementSelectorMaxWidth()
    )
    elementSelectorDialogSize.height = Math.min(
      Math.max(nextHeight, ELEMENT_SELECTOR_MIN_HEIGHT),
      getElementSelectorMaxHeight()
    )
  }

  const handleMouseUp = () => {
    stopElementSelectorResize()
  }

  stopElementSelectorResize()
  document.body.style.userSelect = 'none'
  document.addEventListener('mousemove', handleMouseMove)
  document.addEventListener('mouseup', handleMouseUp)
  elementSelectorResizeHandlers = {
    handleMouseMove,
    handleMouseUp
  }
}

const loadProjects = async () => {
  try {
    const response = await getUiProjects({ page_size: 100 })
    projects.value = response.data.results || response.data
  } catch (error) {
    ElMessage.error('获取项目列表失败')
    console.error('获取项目列表失败:', error)
  }
}

const getDownloadFilename = (contentDisposition, fallbackName) => {
  if (!contentDisposition) {
    return fallbackName
  }

  const utf8Match = /filename\*=UTF-8''([^;]+)/i.exec(contentDisposition)
  if (utf8Match && utf8Match[1]) {
    return decodeURIComponent(utf8Match[1])
  }

  const plainMatch = /filename="?([^"]+)"?/i.exec(contentDisposition)
  if (plainMatch && plainMatch[1]) {
    return plainMatch[1]
  }

  return fallbackName
}

const downloadBlob = (blob, filename) => {
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}

const loadTestCaseFolders = async () => {
  if (!projectId.value) {
    testCaseFolders.value = []
    return
  }

  try {
    const response = await getTestCaseFolders({ project: projectId.value, page_size: 200 })
    testCaseFolders.value = response.data.results || response.data || []
  } catch (error) {
    console.error('获取用例文件夹列表失败:', error)
    testCaseFolders.value = []
  }
}

const loadElementGroups = async () => {
  if (!projectId.value) {
    elementGroups.value = []
    return
  }

  try {
    const response = await getElementGroupTree({ project: projectId.value })
    elementGroups.value = response.data || []
  } catch (error) {
    console.error('获取元素分组树失败:', error)
    elementGroups.value = []
  }
}

const syncSelectedTestCase = () => {
  if (!selectedTestCase.value) {
    return
  }

  const latestCase = testCases.value.find(item => item.id === selectedTestCase.value.id)
  if (!latestCase) {
    selectedTestCase.value = null
    currentSteps.value = []
    selectedStepId.value = null
    checkedStepIds.value = []
    transactionCollapseState.value = {}
    executionResult.value = null
    return
  }

  selectedTestCase.value = latestCase
  const previousSelectedStepId = selectedStepId.value
  const previousCheckedStepIds = [...checkedStepIds.value]
  currentSteps.value = (latestCase.steps || []).map(step =>
    createStepDraft(step, currentSteps.value.find(item => item.id === step.id)?.expanded || false)
  )
  normalizeTransactionBlocks()
  selectedStepId.value = currentSteps.value.some(step => isSameStepId(step.id, previousSelectedStepId))
    ? previousSelectedStepId
    : null
  checkedStepIds.value = previousCheckedStepIds.filter(id =>
    currentSteps.value.some(step => isSameStepId(step.id, id))
  )
  syncTransactionCollapseMap()
}

const loadLocalRunnerList = async () => {
  try {
    const response = await getLocalRunners({ page_size: 100 })
    localRunners.value = response.data.results || response.data || []
    if (!selectedRunnerId.value && onlineLocalRunners.value.length > 0) {
      selectedRunnerId.value = onlineLocalRunners.value[0].id
    }
  } catch (error) {
    console.error('获取本地执行器列表失败:', error)
    localRunners.value = []
  }
}

const stopLocalExecutionPolling = () => {
  if (localExecutionPollTimer) {
    clearTimeout(localExecutionPollTimer)
    localExecutionPollTimer = null
  }
}

const pollLocalExecutionResult = async (executionId) => {
  stopLocalExecutionPolling()

  const poll = async () => {
    try {
      const response = await getTestCaseExecutionDetail(executionId)
      const execution = response.data

      if (execution.status === 'pending' || execution.status === 'running') {
        localExecutionPollTimer = setTimeout(poll, 2000)
        return
      }

      executionResult.value = {
        success: execution.status === 'passed',
        logs: execution.execution_logs,
        screenshots: execution.screenshots || [],
        execution_time: execution.execution_time || 0,
        errors: execution.error_message ? [{
          message: execution.error_message,
          details: execution.error_message,
          step_number: null,
          action_type: '',
          element: '',
          description: ''
        }] : []
      }
      resultActiveTab.value = executionResult.value.screenshots.length > 0 ? 'screenshots' : 'logs'
      showSteps.value = false

      if (execution.status === 'passed') {
        ElMessage.success('本地执行已完成')
      } else {
        ElMessage.error('本地执行失败，请查看结果详情')
      }
    } catch (error) {
      console.error('轮询本地执行结果失败:', error)
      localExecutionPollTimer = setTimeout(poll, 3000)
    }
  }

  await poll()
}

const loadTestCases = async () => {
  if (!projectId.value) {
    testCases.value = []
    selectedCaseIds.value = []
    selectedStepId.value = null
    checkedStepIds.value = []
    transactionCollapseState.value = {}
    return
  }

  try {
    const response = await getTestCases({ project: projectId.value })
    testCases.value = response.data.results || response.data
    selectedCaseIds.value = selectedCaseIds.value.filter(id => testCases.value.some(item => item.id === id))
    syncSelectedTestCase()
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
    const response = await getElements({ project: projectId.value, page_size: 1000 })
    const elements = response.data.results || response.data || []
    availableElements.value = elements.filter((element) => {
      const elementProjectId = element.project?.id ?? element.project_id ?? element.project
      return String(elementProjectId) === String(projectId.value)
    })
  } catch (error) {
    console.error('获取元素列表失败:', error)
  }
}

const loadElementsForCurrentProject = async () => {
  if (!projectId.value) {
    availableElements.value = []
    return
  }

  const currentProjectId = String(projectId.value)
  availableElements.value = []

  try {
    const response = await getElementTree({ project: currentProjectId })
    const elements = Array.isArray(response.data) ? response.data : []

    if (String(projectId.value) !== currentProjectId) {
      return
    }

    availableElements.value = elements.map((element) => ({
      ...element,
      project_id: currentProjectId
    }))
  } catch (error) {
    console.error('加载当前项目元素树失败:', error)
    availableElements.value = []
  }
}

const onProjectChange = async () => {
  uiAutomationStore.setSelectedProject(projectId.value)
  selectedTestCase.value = null
  selectedCaseIds.value = []
  currentSteps.value = []
  selectedStepId.value = null
  checkedStepIds.value = []
  transactionCollapseState.value = {}
  executionResult.value = null
  folderFilter.value = 'all'
  availableElements.value = []
  elementGroups.value = []

  await Promise.all([
    loadTestCaseFolders(),
    loadTestCases(),
    loadElementGroups(),
    loadElementsForCurrentProject()
  ])
}

const openCreateDialog = () => {
  editingTestCase.value = null
  resetForm()
  if (folderFilter.value !== 'all' && folderFilter.value !== 'ungrouped') {
    testCaseForm.folder_id = Number(folderFilter.value)
  }
  showCreateDialog.value = true
}

const openFolderDialog = () => {
  folderForm.name = ''
  showFolderDialog.value = true
}

const saveFolder = async () => {
  if (!projectId.value) {
    ElMessage.warning(t('uiAutomation.project.selectProject'))
    return
  }

  if (!folderForm.name.trim()) {
    ElMessage.warning(text.folderNameRequired)
    return
  }

  try {
    const response = await createTestCaseFolder({
      project: projectId.value,
      name: folderForm.name.trim()
    })
    testCaseFolders.value.push(response.data)
    testCaseFolders.value.sort((a, b) => a.name.localeCompare(b.name, 'zh-Hans-CN'))
    showFolderDialog.value = false
    folderForm.name = ''
    ElMessage.success(text.folderCreateSuccess)
  } catch (error) {
    console.error('创建用例文件夹失败:', error)
    ElMessage.error(text.folderCreateFailed)
  }
}

const openMoveDialog = (ids) => {
  moveForm.test_case_ids = [...new Set((ids || []).filter(Boolean))]
  if (!moveForm.test_case_ids.length) {
    ElMessage.warning(text.moveCasesEmpty)
    return
  }

  if (moveForm.test_case_ids.length === 1) {
    const targetCase = testCases.value.find(item => item.id === moveForm.test_case_ids[0])
    moveForm.folder_id = targetCase?.folder?.id ?? null
  } else {
    moveForm.folder_id = null
  }

  showMoveDialog.value = true
}

const submitMoveCases = async () => {
  if (!moveForm.test_case_ids.length) {
    ElMessage.warning(text.moveCasesEmpty)
    return
  }

  try {
    await moveTestCases({
      test_case_ids: moveForm.test_case_ids,
      folder_id: moveForm.folder_id
    })
    showMoveDialog.value = false
    ElMessage.success(text.moveSuccess)
    await loadTestCases()
    selectedCaseIds.value = selectedCaseIds.value.filter(id => testCases.value.some(item => item.id === id))
  } catch (error) {
    console.error('移动用例失败:', error)
    ElMessage.error(text.moveFailed)
  }
}

const handleExportCases = async (ids = []) => {
  if (!projectId.value) {
    ElMessage.warning(t('uiAutomation.project.selectProject'))
    return
  }

  try {
    const response = await exportTestCases({
      project: projectId.value,
      ids: ids.join(',')
    })
    const blob = new Blob([response.data], {
      type: response.headers['content-type'] || 'application/json'
    })
    const filename = getDownloadFilename(response.headers['content-disposition'], 'ui-test-cases.json')
    downloadBlob(blob, filename)
    ElMessage.success('测试用例导出成功')
  } catch (error) {
    console.error('导出测试用例失败:', error)
    ElMessage.error('测试用例导出失败')
  }
}

const handleExportSelectedCases = async () => {
  if (!selectedCaseIds.value.length) {
    ElMessage.warning('请先选择要导出的用例')
    return
  }
  await handleExportCases(selectedCaseIds.value)
}

const handleExportAllCases = async () => {
  await handleExportCases([])
}

const openImportDialog = () => {
  if (!projectId.value) {
    ElMessage.warning(t('uiAutomation.project.selectProject'))
    return
  }
  importFile.value = null
  importOverwrite.value = false
  showImportDialog.value = true
}

const handleImportFileChange = (file) => {
  importFile.value = file.raw
}

const handleImportFileRemove = () => {
  importFile.value = null
}

const submitImportCases = async () => {
  if (!projectId.value) {
    ElMessage.warning(t('uiAutomation.project.selectProject'))
    return
  }
  if (!importFile.value) {
    ElMessage.warning('请先选择导入文件')
    return
  }

  importing.value = true
  try {
    const formData = new FormData()
    formData.append('project', projectId.value)
    formData.append('overwrite', importOverwrite.value ? '1' : '0')
    formData.append('file', importFile.value)
    const response = await importTestCases(formData)
    const summary = response.data?.summary || {}
    ElMessage.success(`测试用例导入成功，新增 ${summary.created || 0} 个，更新 ${summary.updated || 0} 个`)
    showImportDialog.value = false
    await Promise.all([
      loadTestCaseFolders(),
      loadTestCases(),
      loadElementsForCurrentProject()
    ])
  } catch (error) {
    console.error('导入测试用例失败:', error)
    ElMessage.error(error.response?.data?.detail || error.response?.data?.message || '测试用例导入失败')
  } finally {
    importing.value = false
  }
}

const toggleCaseSelection = (caseId, checked) => {
  if (checked) {
    if (!selectedCaseIds.value.includes(caseId)) {
      selectedCaseIds.value.push(caseId)
    }
    return
  }

  selectedCaseIds.value = selectedCaseIds.value.filter(id => id !== caseId)
}

const selectTestCase = (testCase) => {
  // 如果点击的是同一个用例，不做任何处理
  if (selectedTestCase.value && selectedTestCase.value.id === testCase.id) {
    return
  }

  selectedTestCase.value = testCase
  // 确保步骤数据格式正确，添加前端需要的字段
  if (testCase.steps && testCase.steps.length > 0) {
    currentSteps.value = testCase.steps.map(step => createStepDraft(step, false))
  } else {
    currentSteps.value = []
  }
  normalizeTransactionBlocks()
  selectedStepId.value = null
  checkedStepIds.value = []
  transactionCollapseState.value = {}
  allStepsExpanded.value = false
  // 只有在切换到不同用例时才清空执行结果
  executionResult.value = null
  showSteps.value = true
}

const addStep = () => {
  const newStep = createStepDraft({}, true)
  const selectedIndex = getSelectedStepIndex()

  if (selectedIndex >= 0) {
    const selectedStep = currentSteps.value[selectedIndex]
    const nextStep = currentSteps.value[selectedIndex + 1]
    if (
      hasTransaction(selectedStep) &&
      (!nextStep || getTransactionId(nextStep) === getTransactionId(selectedStep))
    ) {
      newStep.transaction_id = selectedStep.transaction_id
      newStep.transaction_name = selectedStep.transaction_name
    }
  }

  if (selectedIndex >= 0) {
    currentSteps.value.splice(selectedIndex + 1, 0, newStep)
  } else {
    currentSteps.value.push(newStep)
  }

  selectedStepId.value = newStep.id
  checkedStepIds.value = [newStep.id]
  normalizeTransactionBlocks()
  allStepsExpanded.value = false
}

const removeStep = (index) => {
  const [removedStep] = currentSteps.value.splice(index, 1)

  if (removedStep && isSameStepId(removedStep.id, selectedStepId.value)) {
    selectedStepId.value = currentSteps.value[index]?.id ?? currentSteps.value[index - 1]?.id ?? null
  }

  checkedStepIds.value = checkedStepIds.value.filter(id => !isSameStepId(id, removedStep?.id))
  normalizeTransactionBlocks()
}

const onStepsReorder = () => {
  // 步骤重新排序后的处理
  console.log('步骤已重新排序')
}

const handleStepsReorder = (event) => {
  const movedIndex = event?.moved?.newIndex

  if (Number.isInteger(movedIndex) && movedIndex >= 0) {
    const movedStep = currentSteps.value[movedIndex]
    const adjacentTransactionSource = getAdjacentTransactionSource(movedIndex)

    if (movedStep) {
      if (adjacentTransactionSource) {
        applyTransactionToStep(movedStep, adjacentTransactionSource)
      } else if (hasTransaction(movedStep)) {
        movedStep.transaction_id = ''
        movedStep.transaction_name = ''
      }
    }
  }

  normalizeTransactionBlocks()
  console.log('步骤已重新排序')
}

const onActionTypeChange = (step) => {
  // 根据操作类型重置相关参数
  if (!needsInputValue(step.action_type)) {
    step.input_value = ''
  }
  if (step.action_type !== 'drag') {
    step.drag_target_element_id = ''
  }
  if (!needsWaitTime(step.action_type)) {
    step.wait_time = 1000
  }
  if (step.action_type !== 'assert') {
    step.assert_type = 'textContains'
    step.assert_value = ''
  }
  if (!canStoreVariable(step.action_type)) {
    step.save_as = ''
  }
}

const onElementChange = (step) => {
  // 元素变化时的处理
  const element = availableElements.value.find(e => e.id === step.element_id)
  if (element && !step.description) {
    step.description = `${getActionTypeText(step.action_type)}${element.name}`
  }
}

const getSelectedElementLabel = (elementId) => {
  const element = availableElements.value.find(item => item.id === elementId)
  if (!element) {
    return t('uiAutomation.testCase.elementPending')
  }

  return `${element.name} (${element.locator_value})`
}

const openElementSelector = (step, field = 'element_id') => {
  currentSelectingStep.value = step
  currentSelectingField.value = field
  elementSelectorKeyword.value = ''
  showElementSelectorDialog.value = true
}

const handleElementTreeNodeClick = (node) => {
  if (node.type !== 'element' || !currentSelectingStep.value) {
    return
  }

  currentSelectingStep.value[currentSelectingField.value] = node.id
  if (currentSelectingField.value === 'element_id') {
    onElementChange(currentSelectingStep.value)
  }
  showElementSelectorDialog.value = false
}

const needsInputValue = (actionType) => {
  return ['fill', 'fillAndEnter', 'switchTab'].includes(actionType)
}

const needsWaitTime = (actionType) => {
  return ['wait', 'waitFor'].includes(actionType)
}

const needsElement = (actionType) => {
  return !['wait', 'switchTab', 'screenshot', 'closeCurrentPage'].includes(actionType)
}

const expandAllSteps = () => {
  allStepsExpanded.value = !allStepsExpanded.value
  currentSteps.value.forEach(step => {
    step.expanded = allStepsExpanded.value
  })
}

const saveTestCase = async () => {
  if (!selectedTestCase.value) return
  normalizeTransactionBlocks()
  if (!validateCurrentSteps()) return

  try {
    const updateData = {
      ...selectedTestCase.value,
      steps: currentSteps.value.map(buildStepPayload)
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
    if (executionMode.value === 'local' && !selectedRunnerId.value) {
      ElMessage.warning('请先选择本地执行器')
      return
    }

    const modeText = headlessMode.value ? t('uiAutomation.testCase.runMode.headless') : t('uiAutomation.testCase.runMode.headed')
    ElMessage.info(t('uiAutomation.testCase.run.start', { engine: selectedEngine.value.toUpperCase(), browser: selectedBrowser.value.toUpperCase(), mode: modeText }))

    const response = await runTestCaseApi(testCase.id, {
      project_id: projectId.value,
      engine: selectedEngine.value,
      browser: selectedBrowser.value,
      headless: headlessMode.value,
      execution_mode: executionMode.value,
      runner_id: executionMode.value === 'local' ? selectedRunnerId.value : undefined
    })

    if (response.data.queued) {
      executionResult.value = null
      ElMessage.success(response.data.message || '任务已下发到本地执行器')
      await pollLocalExecutionResult(response.data.execution_id)
      return
    }

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

const returnToTestSteps = () => {
  showSteps.value = true
}

const editTestCase = (testCase) => {
  editingTestCase.value = testCase
  testCaseForm.name = testCase.name
  testCaseForm.description = testCase.description || ''
  testCaseForm.priority = testCase.priority || 'medium'
  testCaseForm.folder_id = testCase.folder?.id ?? null
  showCreateDialog.value = true
}

const deleteTestCase = async (testCase) => {
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

    // 如果删除的是当前选中的用例，清空选择
    if (selectedTestCase.value?.id === testCase.id) {
      selectedTestCase.value = null
      currentSteps.value = []
      selectedStepId.value = null
      checkedStepIds.value = []
      transactionCollapseState.value = {}
      executionResult.value = null
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除测试用例失败:', error)
      ElMessage.error('删除失败')
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
  const dynamicCategories = variableCategories.value.length > 0 ? variableCategories.value : [
    {
      label: t('uiAutomation.testCase.variableCategory.randomNumber'),
      variables: []
    }
  ]

  return projectVariableCategory.value
    ? [projectVariableCategory.value, ...dynamicCategories]
    : dynamicCategories
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
      folder_id: testCaseForm.folder_id,
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

    await loadTestCases()
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
  testCaseForm.folder_id = null
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
    'fillAndEnter': t('uiAutomation.testCase.actionType.fillAndEnter'),
    'getText': t('uiAutomation.testCase.actionType.getText'),
    'waitFor': t('uiAutomation.testCase.actionType.waitFor'),
    'hover': t('uiAutomation.testCase.actionType.hover'),
    'scroll': t('uiAutomation.testCase.actionType.scroll'),
    'drag': '拖拽',
    'screenshot': t('uiAutomation.testCase.actionType.screenshot'),
    'assert': t('uiAutomation.testCase.actionType.assert'),
    'wait': t('uiAutomation.testCase.actionType.wait'),
    'switchTab': t('uiAutomation.testCase.actionSwitchTab'),
    'closeCurrentPage': t('uiAutomation.testCase.actionCloseCurrentPage')
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
    'fillAndEnter': t('uiAutomation.testCase.actionText.fillAndEnter'),
    'getText': t('uiAutomation.testCase.actionText.getText'),
    'waitFor': t('uiAutomation.testCase.actionText.waitFor'),
    'hover': t('uiAutomation.testCase.actionText.hover'),
    'scroll': t('uiAutomation.testCase.actionText.scroll'),
    'drag': '拖拽',
    'screenshot': t('uiAutomation.testCase.actionText.screenshot'),
    'assert': t('uiAutomation.testCase.actionText.assert'),
    'wait': t('uiAutomation.testCase.actionText.wait'),
    'switchTab': t('uiAutomation.testCase.actionSwitchTab'),
    'closeCurrentPage': t('uiAutomation.testCase.actionCloseCurrentPage')
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
watch(showCreateDialog, (visible) => {
  if (!visible) {
    editingTestCase.value = null
    resetForm()
  }
})

watch(showFolderDialog, (visible) => {
  if (!visible) {
    folderForm.name = ''
  }
})

watch(showMoveDialog, (visible) => {
  if (!visible) {
    moveForm.test_case_ids = []
    moveForm.folder_id = null
  }
})

watch(showElementSelectorDialog, (visible) => {
  if (visible) {
    normalizeElementSelectorDialogSize()
    return
  }

  stopElementSelectorResize()
  if (!visible) {
    currentSelectingStep.value = null
    currentSelectingField.value = 'element_id'
    elementSelectorKeyword.value = ''
  }
})

onMounted(() => {
  window.addEventListener('resize', normalizeElementSelectorDialogSize)
})

onMounted(async () => {
  console.log('TestCaseManager onMounted 开始执行...')
  await loadProjects()
  console.log('loadProjects 完成，准备加载变量函数...')
  await loadVariableFunctions()
  await loadLocalRunnerList()
  console.log('loadVariableFunctions 完成')

  if (projects.value.length > 0) {
    projectId.value = uiAutomationStore.resolveSelectedProjectId(projects.value)
    await onProjectChange()
  }
})

onBeforeUnmount(() => {
  stopLocalExecutionPolling()
  stopElementSelectorResize()
  window.removeEventListener('resize', normalizeElementSelectorDialogSize)
})
</script>

<style scoped>
.test-case-manager {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid #e6e6e6;
  background: white;
}

.page-title {
  margin: 0;
  font-size: 24px;
}

.header-actions {
  display: flex;
  align-items: center;
}

.main-content {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.left-panel {
  width: 350px;
  border-right: 1px solid #e6e6e6;
  background: white;
  display: flex;
  flex-direction: column;
}

.panel-header {
  padding: 15px;
  border-bottom: 1px solid #e6e6e6;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.panel-header h3 {
  margin: 0;
}

.panel-header-top,
.panel-filters,
.panel-toolbar {
  width: 100%;
  display: flex;
  align-items: center;
}

.panel-header-top {
  justify-content: space-between;
}

.panel-filters {
  gap: 10px;
}

.panel-toolbar {
  justify-content: space-between;
}

.case-total,
.selected-summary {
  font-size: 12px;
  color: #909399;
}

.test-case-list {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
}

.test-case-item {
  border: 1px solid #e6e6e6;
  border-radius: 6px;
  margin-bottom: 10px;
  padding: 12px;
  cursor: pointer;
  transition: all 0.3s;
}

.test-case-item:hover {
  border-color: #409eff;
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.1);
}

.test-case-item.active {
  border-color: #409eff;
  background-color: #f0f8ff;
}

.case-header {
  display: flex;
  align-items: flex-start;
  margin-bottom: 8px;
  gap: 10px;
}

.case-select {
  padding-top: 2px;
}

.case-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.case-name {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.5;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.case-description {
  margin: 0;
  color: #666;
  font-size: 12px;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.case-actions {
  display: flex;
  gap: 5px;
  flex-wrap: wrap;
  align-items: center;
}

.case-actions :deep(.el-button) {
  margin-left: 0;
  min-height: 24px;
  padding: 2px 6px;
}

.case-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 12px;
  color: #888;
}

.step-count {
  color: #409eff;
  font-weight: 500;
}

.right-panel {
  flex: 1;
  background: white;
  display: flex;
  flex-direction: column;
}

.test-case-detail {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 20px;
  overflow: hidden;
  height: 100%;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 1px solid #e6e6e6;
}

.detail-header h3 {
  margin: 0;
}

.detail-actions {
  display: flex;
  gap: 10px;
}

.steps-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  margin-bottom: 20px;
  border: 1px solid #e6e6e6;
  border-radius: 6px;
  background: #fafafa;
  overflow: hidden;
}

.steps-container.has-steps {
  max-height: 50%;
}

.steps-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  margin-bottom: 15px;
  border-bottom: 1px solid #e6e6e6;
  background: #fff;
}

.steps-header-main {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.steps-header h4 {
  margin: 0;
}

.steps-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.steps-selection-summary {
  color: #606266;
  font-size: 13px;
}

.steps-list {
  padding: 0;
  padding-bottom: 20px;
}

.steps-scroll-container {
  overflow-y: auto;
  flex: 1;
  min-height: 0;
  padding: 12px;
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

.step-entry {
  margin-bottom: 10px;
}

.transaction-block {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid #d9ecff;
  border-radius: 8px;
  background: linear-gradient(90deg, #f5f9ff 0%, #eef6ff 100%);
  margin-bottom: 8px;
}

.transaction-block.collapsed {
  margin-bottom: 10px;
}

.transaction-block-main {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  flex: 1;
  cursor: pointer;
}

.transaction-block-toggle,
.transaction-block-icon {
  color: #409eff;
}

.transaction-block-checkbox {
  flex-shrink: 0;
}

.transaction-block-name {
  color: #303133;
  font-size: 14px;
  font-weight: 600;
}

.transaction-block-summary {
  min-width: 0;
  color: #606266;
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.transaction-block-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.step-item {
  border: 1px solid #e6e6e6;
  border-radius: 6px;
  background: white;
  transition: all 0.3s;
}

.step-item:hover {
  border-color: #409eff;
}

.step-item--in-transaction {
  margin-left: 20px;
  border-color: #d9ecff;
}

.step-item.selected {
  border-color: #409eff;
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.12);
}

.step-item.selected .step-header {
  background: #ecf5ff;
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
  min-width: 0;
  flex: 1;
}

.step-select-checkbox {
  flex-shrink: 0;
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

.step-summary {
  min-width: 0;
  flex: 1;
  cursor: pointer;
}

.step-summary-title {
  color: #303133;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.5;
  word-break: break-word;
}

.step-summary-meta {
  margin-top: 4px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  color: #909399;
  font-size: 12px;
}

.step-right {
  display: flex;
  gap: 5px;
}

.step-content {
  padding: 15px;
  border-top: 1px solid #e6e6e6;
}

.element-selector-trigger {
  width: 240px;
  justify-content: flex-start;
  overflow: hidden;
}

.element-selector-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.element-selector-search {
  margin-bottom: 12px;
}

.element-selector-dialog-body {
  position: relative;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.element-selector-tree-wrapper {
  flex: 1;
  min-height: 0;
  overflow: auto;
  border: 1px solid #e6e6e6;
  border-radius: 6px;
  padding: 10px;
  padding-right: 14px;
}

.element-tree-node {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  min-width: 0;
}

.element-tree-node-main {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.element-tree-node-icon {
  color: #409eff;
}

.element-tree-node-label {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.element-tree-node-label.is-hoverable {
  cursor: help;
  border-bottom: 1px dashed transparent;
}

.element-tree-node-label.is-hoverable:hover {
  color: #409eff;
  border-bottom-color: rgba(64, 158, 255, 0.45);
}

.element-tree-node-extra {
  color: #909399;
  font-size: 12px;
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.element-selector-resizer {
  position: absolute;
  right: 6px;
  bottom: 6px;
  width: 16px;
  height: 16px;
  cursor: nwse-resize;
  background:
    linear-gradient(135deg, transparent 0 34%, #c0c4cc 34% 44%, transparent 44% 58%, #c0c4cc 58% 68%, transparent 68% 82%, #c0c4cc 82% 100%);
}

.element-tooltip-content {
  max-width: min(640px, calc(100vw - 64px));
}

.element-tooltip-title {
  margin-bottom: 8px;
  font-weight: 600;
}

.element-tooltip-json {
  margin: 0;
  max-height: min(360px, calc(100vh - 180px));
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 12px;
  line-height: 1.5;
  font-family: Consolas, 'Courier New', monospace;
}

:deep(.element-selector-dialog) {
  max-width: calc(100vw - 32px);
}

:deep(.element-selector-dialog .el-dialog__body) {
  padding-top: 10px;
}

:deep(.element-data-tooltip) {
  max-width: min(680px, calc(100vw - 40px));
}

.step-param {
  display: flex;
  align-items: center;
  margin-bottom: 10px;
  gap: 10px;
}

.step-param--stacked {
  align-items: flex-start;
}

.step-param label {
  width: 120px;
  font-weight: 500;
  color: #333;
}

.step-param-main {
  flex: 1;
  min-width: 0;
}

.step-help {
  margin-top: 6px;
  color: #909399;
  font-size: 12px;
  line-height: 1.5;
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
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 15px;
  border-bottom: 1px solid #e6e6e6;
  background: #fafafa;
  border-radius: 6px 6px 0 0;
}

.result-header-main {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.result-header-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex-shrink: 0;
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
