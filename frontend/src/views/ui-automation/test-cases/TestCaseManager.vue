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
        <el-button type="success" :disabled="!projectId" @click="openAiGenerateDialog">
          <el-icon><MagicStick /></el-icon>
          {{ aiText.openButton }}
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
            <el-button size="small" type="danger" :disabled="!selectedCaseIds.length" @click="handleBatchDelete">
              <el-icon><Delete /></el-icon>
              {{ text.batchDeleteCases }}
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
              <el-button
                size="small"
                :disabled="!importableSourceTestCases.length"
                @click="openImportCaseStepsDialog"
              >
                导入用例步骤
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
                        :class="{
                          collapsed: isTransactionCollapsed(element.transaction_id),
                          'transaction-block--disabled': isTransactionDisabled(element.transaction_id),
                          'transaction-block--dragging': draggingTransactionId === getTransactionId(element)
                        }"
                        draggable="true"
                        @dragstart="handleTransactionDragStart(element.transaction_id, $event)"
                        @dragover.prevent
                        @drop.prevent="handleTransactionDrop(element.transaction_id, $event)"
                        @dragend="handleTransactionDragEnd"
                      >
                        <div class="transaction-block-main" @click="toggleTransactionCollapse(element.transaction_id)">
                          <el-icon class="transaction-block-drag" @click.stop><Rank /></el-icon>
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
                          <el-tag v-if="isTransactionDisabled(element.transaction_id)" size="small" type="warning" effect="plain">已禁用</el-tag>
                          <span class="transaction-block-summary">{{ getTransactionSummary(element.transaction_id) }}</span>
                        </div>
                        <div class="transaction-block-actions" @click.stop>
                          <el-switch
                            size="small"
                            :model-value="!isTransactionDisabled(element.transaction_id)"
                            active-text="启用"
                            inactive-text="禁用"
                            @change="toggleTransactionDisabled(element.transaction_id, $event)"
                          />
                          <el-button size="small" text @click="copyTransactionBlock(element.transaction_id)">
                            复制
                          </el-button>
                          <el-button size="small" text @click="renameTransactionBlock(element.transaction_id)">
                            重命名
                          </el-button>
                          <el-button size="small" text type="danger" @click="deleteTransactionBlock(element.transaction_id)">
                            删除
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
                          'step-item--in-transaction': hasTransaction(element),
                          'step-item--disabled': element.is_enabled === false
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
                                <span>{{ getStepSummary(element, index) }}</span>
                                <el-tag v-if="element.is_enabled === false" size="small" type="info" effect="plain">
                                  {{ text.stepDisabled }}
                                </el-tag>
                              </div>
                              <div class="step-summary-meta">
                                <span>{{ getActionTypeText(element.action_type) }}</span>
                                <span v-if="needsElement(element.action_type)">{{ getStepElementSummary(element) }}</span>
                                <span v-else-if="isCanvasAction(element.action_type)">{{ getStepElementSummary(element) }}</span>
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
                        <div class="step-param step-param--toggle">
                          <label>{{ text.stepEnabledLabel }}</label>
                          <div class="step-toggle">
                            <el-switch v-model="element.is_enabled" />
                            <span
                              class="step-toggle-status"
                              :class="element.is_enabled === false ? 'is-disabled' : 'is-enabled'"
                            >
                              {{ element.is_enabled === false ? text.stepDisabled : text.stepEnabled }}
                            </span>
                          </div>
                        </div>

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
                            <el-option label="刷新当前页" value="refreshCurrentPage" />
                            <el-option :label="t('uiAutomation.testCase.actionCloseCurrentPage')" value="closeCurrentPage" />
                            <el-option label="画布点击" value="canvasClick" />
                            <el-option label="画布拖拽" value="canvasDrag" />
                          </el-select>
                        </div>

                        <div v-if="needsElement(element.action_type)" class="step-param">
                          <label>{{ element.action_type === 'scroll' ? '滚动元素/容器' : t('uiAutomation.testCase.selectElement') }}</label>
                          <el-button
                            size="small"
                            class="element-selector-trigger"
                            @click="openElementSelector(element)"
                          >
                            <el-icon><FolderOpened /></el-icon>
                            <span class="element-selector-text">{{ getSelectedElementLabel(element.element_id) }}</span>
                          </el-button>
                          <div v-if="element.action_type === 'scroll'" class="step-help">
                            如果要滚动左侧菜单栏，请在这里选择左侧菜单栏容器；未选择时，采集和执行的都是整个页面滚动。
                          </div>
                        </div>
                        <!-- 输入参数 -->
                        <div v-if="needsElement(element.action_type)" class="step-param step-param--stacked step-locator-override">
                          <label>定位表达式</label>
                          <div class="step-param-main">
                            <div class="locator-override-row">
                              <el-select
                                v-model="element.element_locator_strategy"
                                size="small"
                                style="width: 120px"
                                placeholder="策略"
                              >
                                <el-option label="CSS" value="css" />
                                <el-option label="XPath" value="xpath" />
                                <el-option label="ID" value="id" />
                                <el-option label="Text" value="text" />
                                <el-option label="Name" value="name" />
                                <el-option label="Placeholder" value="placeholder" />
                                <el-option label="Role" value="role" />
                                <el-option label="Label" value="label" />
                                <el-option label="Title" value="title" />
                                <el-option label="Test ID" value="test-id" />
                              </el-select>
                              <el-input
                                v-model="element.element_locator_value"
                                size="small"
                                clearable
                                :placeholder="getSelectedElementLocatorPlaceholder(element)"
                              />
                            </div>
                          </div>
                        </div>

                        <div v-if="element.action_type === 'scroll'" class="step-param step-param--stacked">
                          <label>滚动配置</label>
                          <div class="step-param-main">
                            <div class="scroll-config-grid">
                              <el-select
                                v-model="element.scroll_direction"
                                size="small"
                                clearable
                                placeholder="选择滚动方向"
                              >
                                <el-option label="纵向滚动" value="vertical" />
                                <el-option label="横向滚动" value="horizontal" />
                                <el-option label="往上滚动" value="up" />
                                <el-option label="往下滚动" value="down" />
                              </el-select>
                              <el-input-number
                                v-model="element.scroll_start_x"
                                :controls="false"
                                size="small"
                                placeholder="起始X"
                              />
                              <el-input-number
                                v-model="element.scroll_start_y"
                                :controls="false"
                                size="small"
                                placeholder="起始Y"
                              />
                              <el-input-number
                                v-model="element.scroll_target_x"
                                :controls="false"
                                size="small"
                                placeholder="目标X"
                              />
                              <el-input-number
                                v-model="element.scroll_target_y"
                                :controls="false"
                                size="small"
                                placeholder="目标Y"
                              />
                            </div>
                            <div class="scroll-picker-actions">
                              <el-button
                                size="small"
                                :loading="scrollCoordinatePickerStarting"
                                :disabled="!selectedProject?.base_url || (executionMode === 'local' && !selectedRunnerId) || scrollCoordinatePickerReadingStart || scrollCoordinatePickerReadingTarget"
                                @click="openScrollCoordinatePickerPage(element)"
                              >
                                打开网页
                              </el-button>
                              <el-button
                                size="small"
                                :loading="scrollCoordinatePickerStarting || scrollCoordinatePickerReadingStart"
                                :disabled="!selectedProject?.base_url || (executionMode === 'local' && !selectedRunnerId) || scrollCoordinatePickerReadingTarget"
                                @click="captureScrollCoordinate(element, 'start')"
                              >
                                开始滚动位置
                              </el-button>
                              <el-button
                                size="small"
                                :loading="scrollCoordinatePickerStarting || scrollCoordinatePickerReadingTarget"
                                :disabled="!selectedProject?.base_url || (executionMode === 'local' && !selectedRunnerId) || scrollCoordinatePickerReadingStart"
                                @click="captureScrollCoordinate(element, 'target')"
                              >
                                滚动到位置
                              </el-button>
                            </div>
                            <div class="scroll-picker-actions">
                              <el-select
                                :model-value="scrollCoordinatePickerActivePageIndex"
                                size="small"
                                placeholder="选择采集页面"
                                style="width: 320px"
                                :disabled="!scrollCoordinatePickerSessionId || scrollCoordinatePickerPagesLoading || scrollCoordinatePickerSwitchingPage"
                                @change="switchScrollCoordinatePickerPage"
                              >
                                <el-option
                                  v-for="page in scrollCoordinatePickerPages"
                                  :key="page.index"
                                  :label="`[${page.index}] ${page.title || page.url || '未命名页面'}${page.is_active ? '（当前）' : ''}`"
                                  :value="page.index"
                                />
                              </el-select>
                              <el-button
                                size="small"
                                :loading="scrollCoordinatePickerPagesLoading"
                                :disabled="!scrollCoordinatePickerSessionId || scrollCoordinatePickerSwitchingPage"
                                @click="refreshScrollCoordinatePickerPages(true)"
                              >
                                刷新页面列表
                              </el-button>
                            </div>
                            <div class="scroll-picker-guide">
                              <div
                                v-for="guide in getScrollCoordinateGuideLines(element)"
                                :key="guide"
                                class="scroll-picker-guide__line"
                              >
                                {{ guide }}
                              </div>
                            </div>
                            <div class="step-help">
                              已配置坐标时，会按坐标滚动；未配置坐标时，仍沿用原来的“滚动到元素”行为。纵向/往上/往下使用 Y 坐标，横向使用 X 坐标。
                            </div>
                          </div>
                        </div>

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

                        <div v-if="isCanvasAction(element.action_type)" class="step-param step-param--stacked">
                          <label>{{ element.action_type === 'canvasDrag' ? '画布拖拽' : '画布点击' }}</label>
                          <div class="step-param-main">
                            <div class="canvas-config-grid">
                              <el-input
                                v-model="element.canvas_frame_selector"
                                size="small"
                                placeholder="iframe选择器，默认 #plt-workflow-iframe"
                              />
                              <el-input-number
                                v-model="element.canvas_hold_ms"
                                :min="0"
                                :max="5000"
                                :step="100"
                                size="small"
                                placeholder="按住ms"
                              />
                              <el-input-number
                                v-model="element.canvas_steps"
                                :min="1"
                                :max="100"
                                :step="1"
                                size="small"
                                placeholder="拖拽步数"
                              />
                            </div>
                            <div class="canvas-coordinate-summary">
                              <span v-if="element.action_type === 'canvasClick'">
                                点击位置：{{ formatCanvasPoint(element.canvas_click_x, element.canvas_click_y) }}
                              </span>
                              <span v-else>
                                起点：{{ formatCanvasPoint(element.canvas_start_x, element.canvas_start_y) }}
                                <span class="canvas-coordinate-arrow">-></span>
                                终点：{{ formatCanvasPoint(element.canvas_target_x, element.canvas_target_y) }}
                              </span>
                            </div>
                            <div class="scroll-picker-actions">
                              <el-button
                                size="small"
                                :loading="scrollCoordinatePickerStarting"
                                :disabled="!selectedProject?.base_url || (executionMode === 'local' && !selectedRunnerId) || scrollCoordinatePickerReadingStart || scrollCoordinatePickerReadingTarget"
                                @click="openCanvasCoordinatePickerPage(element)"
                              >
                                打开采集页面
                              </el-button>
                              <el-button
                                v-if="element.action_type === 'canvasClick'"
                                size="small"
                                :loading="scrollCoordinatePickerStarting || scrollCoordinatePickerReadingStart"
                                :disabled="!selectedProject?.base_url || (executionMode === 'local' && !selectedRunnerId) || scrollCoordinatePickerReadingTarget"
                                @click="captureCanvasCoordinate(element, 'click')"
                              >
                                采集点击位置
                              </el-button>
                              <template v-else>
                                <el-button
                                  size="small"
                                  :loading="scrollCoordinatePickerStarting || scrollCoordinatePickerReadingStart"
                                  :disabled="!selectedProject?.base_url || (executionMode === 'local' && !selectedRunnerId) || scrollCoordinatePickerReadingTarget"
                                  @click="captureCanvasCoordinate(element, 'start')"
                                >
                                  采集起点
                                </el-button>
                                <el-button
                                  size="small"
                                  :loading="scrollCoordinatePickerStarting || scrollCoordinatePickerReadingTarget"
                                  :disabled="!selectedProject?.base_url || (executionMode === 'local' && !selectedRunnerId) || scrollCoordinatePickerReadingStart"
                                  @click="captureCanvasCoordinate(element, 'target')"
                                >
                                  采集终点
                                </el-button>
                              </template>
                            </div>
                            <div class="scroll-picker-actions">
                              <el-select
                                :model-value="scrollCoordinatePickerActivePageIndex"
                                size="small"
                                placeholder="选择采集页面"
                                style="width: 320px"
                                :disabled="!scrollCoordinatePickerSessionId || scrollCoordinatePickerPagesLoading || scrollCoordinatePickerSwitchingPage"
                                @change="switchScrollCoordinatePickerPage"
                              >
                                <el-option
                                  v-for="page in scrollCoordinatePickerPages"
                                  :key="page.index"
                                  :label="`[${page.index}] ${page.title || page.url || '未命名页面'}${page.is_active ? '（当前）' : ''}`"
                                  :value="page.index"
                                />
                              </el-select>
                              <el-button
                                size="small"
                                :loading="scrollCoordinatePickerPagesLoading"
                                :disabled="!scrollCoordinatePickerSessionId || scrollCoordinatePickerSwitchingPage"
                                @click="refreshScrollCoordinatePickerPages(true)"
                              >
                                刷新页面列表
                              </el-button>
                            </div>
                            <div class="step-help">
                              打开采集页面后，在工作流设计 iframe 内对准图形按钮或连接点右键一次即可采集坐标；执行时会自动换算 iframe 偏移并回放鼠标操作。
                            </div>
                          </div>
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
                          <el-tag :type="getExecutionLogTagType(step)" size="small">
                            {{ getExecutionLogStatusText(step) }}
                          </el-tag>
                          <span class="log-step-number">{{ t('uiAutomation.testCase.step') }} {{ step.step_number }}</span>
                          <span class="log-action">{{ getActionText(step.action_type) }}</span>
                          <span class="log-desc">{{ step.description }}</span>
                        </div>
                        <div v-if="step.message && !step.error" class="log-message">
                          {{ step.message }}
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
      :title="text.manageFolders"
      :close-on-click-modal="false"
      width="420px"
    >
      <el-form :model="folderForm" label-width="100px">
        <el-form-item :label="text.folderName" required>
          <el-input v-model="folderForm.name" :placeholder="text.folderNamePlaceholder" />
        </el-form-item>
      </el-form>
      <div class="folder-manage-list">
        <div v-if="testCaseFolders.length" class="folder-manage-items">
          <div v-for="folder in testCaseFolders" :key="folder.id" class="folder-manage-item">
            <div class="folder-manage-info">
              <span class="folder-manage-name">{{ folder.name }}</span>
              <span class="folder-manage-count">{{ text.folderCaseCount.replace('{count}', folder.test_case_count || 0) }}</span>
            </div>
            <el-button
              size="small"
              text
              type="danger"
              :loading="folderDeletingId === folder.id"
              @click="deleteFolder(folder)"
            >
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
        </div>
        <el-empty v-else :description="text.folderEmpty" :image-size="72" />
      </div>
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
      v-model="showAiGenerateDialog"
      :title="aiText.dialogTitle"
      :close-on-click-modal="false"
      width="1080px"
      class="ai-generate-dialog"
    >
      <div class="ai-generate-layout">
        <div class="ai-generate-config">
          <el-form label-width="112px">
            <el-form-item :label="aiText.targetProject">
              <span>{{ selectedProject?.name || '-' }}</span>
            </el-form-item>
            <el-form-item :label="aiText.aiModel">
              <el-select v-model="aiGenerateForm.model_config_id" clearable filterable style="width: 100%" :placeholder="aiText.defaultModel">
                <el-option
                  v-for="model in aiModelConfigs"
                  :key="model.id"
                  :label="`${model.name} / ${model.model_name}${model.is_active ? aiText.activeSuffix : ''}`"
                  :value="model.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item :label="aiText.skill">
              <el-select v-model="aiGenerateForm.skill_id" clearable filterable style="width: 100%" :placeholder="aiText.defaultSkill">
                <el-option
                  v-for="skill in aiSkills"
                  :key="skill.id"
                  :label="`${skill.name}${skill.is_default ? aiText.defaultSuffix : ''}`"
                  :value="skill.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item :label="aiText.targetFolder">
              <el-select v-model="aiGenerateForm.folder_id" clearable style="width: 100%" :placeholder="aiText.generatedFolder">
                <el-option :label="text.ungrouped" :value="null" />
                <el-option v-for="folder in testCaseFolders" :key="folder.id" :label="folder.name" :value="folder.id" />
              </el-select>
            </el-form-item>
            <el-form-item :label="aiText.overwrite">
              <el-switch v-model="aiGenerateForm.overwrite" />
            </el-form-item>
            <el-form-item :label="aiText.useAi">
              <el-switch v-model="aiGenerateForm.use_ai" />
            </el-form-item>
            <el-form-item :label="aiText.uploadFile">
              <div class="ai-upload-field">
                <div class="ai-upload-actions">
                  <el-upload
                    ref="aiSourceUploadRef"
                    :auto-upload="false"
                    :limit="1"
                    accept=".txt,.md,.json,.csv,.xlsx,.xmind"
                    :show-file-list="true"
                    :on-change="handleAiSourceFileChange"
                    :on-remove="handleAiSourceFileRemove"
                  >
                    <el-button>{{ aiText.chooseFile }}</el-button>
                  </el-upload>
                  <el-button type="primary" plain :loading="aiTemplateDownloading" @click="downloadAiCaseTemplate">
                    {{ aiText.downloadTemplate }}
                  </el-button>
                </div>
                <div class="ai-upload-tip">
                  {{ aiText.uploadTip }}
                </div>
                <div v-if="aiSourceFileInfo" class="ai-file-info">
                  <el-tag size="small" type="success">{{ aiSourceFileInfo.extension }}</el-tag>
                  <span class="ai-file-name">{{ aiSourceFileInfo.name }}</span>
                  <span class="ai-file-size">{{ aiSourceFileInfo.sizeText }}</span>
                </div>
              </div>
            </el-form-item>
          </el-form>

          <el-tabs v-model="aiGenerateTab">
            <el-tab-pane :label="aiText.sourceTab" name="source">
              <el-input
                v-model="aiGenerateForm.text"
                type="textarea"
                :rows="10"
                resize="vertical"
                :placeholder="aiText.sourcePlaceholder"
              />
            </el-tab-pane>
            <el-tab-pane :label="aiText.skillTab" name="skill">
              <el-alert
                type="info"
                :closable="false"
                show-icon
                class="ai-skill-router-tip"
                title="主 Skill 入口仍是上方选择的“生成Skill”。后端会根据自然语言意图自动加载下面的模块化 Skill，不再把所有 Skill 全部揉进主入口。"
              />
              <el-input
                v-model="aiSkillOptimizeInstruction"
                type="textarea"
                :rows="5"
                resize="vertical"
                :placeholder="aiText.skillPlaceholder"
              />
              <div class="ai-skill-actions">
                <el-button :loading="aiSkillOptimizing" @click="optimizeAiSkill('preview')">{{ aiText.previewSkill }}</el-button>
                <el-button type="primary" :loading="aiSkillOptimizing" @click="optimizeAiSkill('update')">{{ aiText.updateSkill }}</el-button>
                <el-button type="success" :loading="aiSkillSaving" @click="saveAiSkillPreview">{{ aiText.saveSkill }}</el-button>
              </div>
              <el-input
                v-model="aiSkillPreview"
                type="textarea"
                :rows="9"
                resize="vertical"
                :placeholder="aiText.skillPreviewPlaceholder"
              />
              <el-divider content-position="left">模块化 Skill 管理</el-divider>
              <div class="ai-skill-module-toolbar">
                <el-button size="small" :loading="aiSkillModulesLoading" @click="loadAiSkillModules">刷新模块</el-button>
                <el-button size="small" type="primary" plain :loading="aiSkillModulesLoading" @click="ensureBuiltinAiSkillModules">初始化内置模块</el-button>
                <el-button size="small" type="success" @click="openAiSkillModuleDialog()">新增模块</el-button>
              </div>
              <el-table
                v-loading="aiSkillModulesLoading"
                :data="aiSkillModules"
                size="small"
                border
                height="220"
                class="ai-skill-module-table"
              >
                <el-table-column prop="name" label="模块名称" min-width="150" show-overflow-tooltip />
                <el-table-column prop="code" label="编码" min-width="190" show-overflow-tooltip />
                <el-table-column label="类型" width="110">
                  <template #default="{ row }">
                    <el-tag size="small" :type="aiSkillModuleTypeTag(row.module_type)">
                      {{ aiSkillModuleTypeLabel(row.module_type) }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="priority" label="优先级" width="80" />
                <el-table-column label="触发" min-width="180" show-overflow-tooltip>
                  <template #default="{ row }">
                    {{ [...(row.intents || []), ...(row.keywords || [])].slice(0, 4).join(' / ') || '-' }}
                  </template>
                </el-table-column>
                <el-table-column label="状态" width="80">
                  <template #default="{ row }">
                    <el-tag size="small" :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '停用' }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="140" fixed="right">
                  <template #default="{ row }">
                    <el-button link type="primary" size="small" @click="openAiSkillModuleDialog(row)">编辑</el-button>
                    <el-button link type="danger" size="small" @click="deleteAiSkillModule(row)">删除</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </el-tab-pane>
          </el-tabs>

          <div class="ai-generate-actions">
            <el-button type="primary" :loading="aiGenerating" @click="submitAiGenerateCases">
              <el-icon><MagicStick /></el-icon>
              {{ aiText.generatePreview }}
            </el-button>
            <el-button :disabled="!aiGeneratedRecordId" type="success" :loading="aiImporting" @click="submitImportGeneratedCases">
              <el-icon><Check /></el-icon>
              {{ aiText.importNow }}
            </el-button>
          </div>
        </div>

        <div class="ai-generate-preview">
          <div class="ai-preview-header">
            <span>{{ aiText.previewTitle }}</span>
            <el-tag v-if="aiGenerationMode" size="small">{{ aiGenerationModeLabel }}</el-tag>
          </div>
          <div v-if="aiSkillRoute?.selected_modules?.length" class="ai-route-summary">
            <span>已命中 Skill 模块：</span>
            <el-tag
              v-for="module in aiSkillRoute.selected_modules.slice(0, 5)"
              :key="module.code"
              size="small"
              type="info"
            >
              {{ module.name || module.code }}
            </el-tag>
          </div>
          <div v-if="aiSkillRoute" class="ai-route-debug">
            <div class="ai-route-meta">
              <el-tag size="small" type="success">已加载 {{ aiSkillRoute.selected_modules?.length || 0 }}</el-tag>
              <el-tag size="small" type="info">命中 {{ aiSkillRoute.matched_modules?.length || aiSkillRoute.selected_modules?.length || 0 }}</el-tag>
              <el-tag v-if="aiSkillRoute.omitted_modules?.length" size="small" type="warning">未加载 {{ aiSkillRoute.omitted_modules.length }}</el-tag>
              <el-tag size="small">Prompt {{ aiSkillRoute.prompt_chars || 0 }} chars</el-tag>
            </div>
            <div v-if="aiSkillRoute.detected_intents?.length" class="ai-route-block">
              <div class="ai-route-block-title">识别意图</div>
              <div class="ai-route-tag-list">
                <el-tag v-for="intent in aiSkillRoute.detected_intents" :key="intent" size="small" type="success">{{ intent }}</el-tag>
              </div>
            </div>
            <div v-if="aiSkillRouteEntityEntries.length" class="ai-route-block">
              <div class="ai-route-block-title">识别实体</div>
              <div class="ai-route-entity-list">
                <div v-for="entry in aiSkillRouteEntityEntries" :key="entry.key" class="ai-route-entity-item">
                  <span class="ai-route-entity-key">{{ entry.key }}</span>
                  <span class="ai-route-entity-value">{{ formatAiSkillRouteEntityValue(entry.value) }}</span>
                </div>
              </div>
            </div>
            <div v-if="aiSkillRoute.selected_modules?.length" class="ai-route-block">
              <div class="ai-route-block-title">命中并加载的 Skill</div>
              <div class="ai-route-module-list">
                <div v-for="module in aiSkillRoute.selected_modules" :key="module.id || module.code" class="ai-route-module-card">
                  <div class="ai-route-module-header">
                    <div class="ai-route-module-title">
                      <span>{{ module.name || module.code }}</span>
                      <span class="ai-route-module-code">{{ module.code }}</span>
                    </div>
                    <div class="ai-route-tag-list">
                      <el-tag size="small" :type="aiSkillModuleTypeTag(module.module_type)">{{ aiSkillModuleTypeLabel(module.module_type) }}</el-tag>
                      <el-tag size="small" type="info">score {{ module.score || 0 }}</el-tag>
                    </div>
                  </div>
                  <div v-if="module.summary" class="ai-route-module-summary">{{ module.summary }}</div>
                  <div v-if="module.reason_labels?.length" class="ai-route-module-line">
                    <span class="ai-route-line-label">命中原因</span>
                    <div class="ai-route-tag-list">
                      <el-tag v-for="reason in module.reason_labels" :key="reason" size="small">{{ reason }}</el-tag>
                    </div>
                  </div>
                  <div v-if="module.matched_triggers?.length" class="ai-route-module-line">
                    <span class="ai-route-line-label">触发规则</span>
                    <div class="ai-route-tag-list">
                      <el-tag v-for="trigger in module.matched_triggers" :key="`${module.code}-${trigger.trigger_type}-${trigger.value}`" size="small" type="warning">
                        {{ trigger.trigger_type_label || trigger.trigger_type }}: {{ trigger.value }} (+{{ trigger.weight }})
                      </el-tag>
                    </div>
                  </div>
                  <div v-if="module.matched_intents?.length" class="ai-route-module-line">
                    <span class="ai-route-line-label">命中意图</span>
                    <div class="ai-route-tag-list">
                      <el-tag v-for="intent in module.matched_intents" :key="`${module.code}-intent-${intent}`" size="small" type="success">{{ intent }}</el-tag>
                    </div>
                  </div>
                  <div v-if="module.matched_keywords?.length" class="ai-route-module-line">
                    <span class="ai-route-line-label">命中关键词</span>
                    <div class="ai-route-tag-list">
                      <el-tag v-for="keyword in module.matched_keywords" :key="`${module.code}-keyword-${keyword}`" size="small" type="info">{{ keyword }}</el-tag>
                    </div>
                  </div>
                  <div v-if="module.matched_pages?.length" class="ai-route-module-line">
                    <span class="ai-route-line-label">命中页面</span>
                    <div class="ai-route-tag-list">
                      <el-tag v-for="page in module.matched_pages" :key="`${module.code}-page-${page}`" size="small">{{ page }}</el-tag>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div v-if="aiSkillRoute.omitted_modules?.length" class="ai-route-block">
              <div class="ai-route-block-title">命中但未加载</div>
              <div class="ai-route-module-list">
                <div v-for="module in aiSkillRoute.omitted_modules" :key="`omitted-${module.id || module.code}`" class="ai-route-module-card ai-route-module-card-omitted">
                  <div class="ai-route-module-header">
                    <div class="ai-route-module-title">
                      <span>{{ module.name || module.code }}</span>
                      <span class="ai-route-module-code">{{ module.code }}</span>
                    </div>
                    <div class="ai-route-tag-list">
                      <el-tag size="small" :type="aiSkillModuleTypeTag(module.module_type)">{{ aiSkillModuleTypeLabel(module.module_type) }}</el-tag>
                      <el-tag size="small" type="warning">{{ formatAiSkillRouteOmittedReason(module.omitted_reason) }}</el-tag>
                    </div>
                  </div>
                  <div v-if="module.summary" class="ai-route-module-summary">{{ module.summary }}</div>
                </div>
              </div>
            </div>
          </div>
          <el-alert
            v-if="aiGenerateWarnings.length"
            type="warning"
            :closable="false"
            show-icon
            class="ai-warning"
          >
            <template #title>
              {{ aiGenerateWarnings.slice(0, 3).join('；') }}{{ aiGenerateWarnings.length > 3 ? ` 等 ${aiGenerateWarnings.length} 条` : '' }}
            </template>
          </el-alert>
          <el-table v-if="aiGeneratedCases.length" :data="aiGeneratedCases" height="460" border>
            <el-table-column prop="name" :label="aiText.caseName" min-width="170" show-overflow-tooltip />
            <el-table-column prop="folder_name" :label="aiText.folderName" width="120" show-overflow-tooltip />
            <el-table-column prop="priority" :label="aiText.priority" width="80" />
            <el-table-column :label="aiText.stepCount" width="80">
              <template #default="{ row }">{{ row.steps?.length || 0 }}</template>
            </el-table-column>
            <el-table-column :label="aiText.firstSteps" min-width="260">
              <template #default="{ row }">
                <div class="ai-step-preview">
                  <div v-for="step in (row.steps || []).slice(0, 4)" :key="step.step_number">
                    {{ step.step_number }}. {{ step.description }}
                  </div>
                </div>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-else :description="aiText.emptyPreview" />
        </div>
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showAiGenerateDialog = false">{{ t('uiAutomation.common.cancel') }}</el-button>
          <el-button :disabled="!aiGeneratedRecordId" type="success" :loading="aiImporting" @click="submitImportGeneratedCases">
            {{ aiText.importToManager }}
          </el-button>
        </span>
      </template>
    </el-dialog>

    <el-dialog
      v-model="showAiSkillModuleDialog"
      :title="aiSkillModuleForm.id ? '编辑 Skill 模块' : '新增 Skill 模块'"
      :close-on-click-modal="false"
      width="760px"
    >
      <el-form :model="aiSkillModuleForm" label-width="104px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="模块名称" required>
              <el-input v-model="aiSkillModuleForm.name" placeholder="例如：创建数据要素流程" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="模块编码" required>
              <el-input v-model="aiSkillModuleForm.code" placeholder="例如：ui.flow.data_element.create" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="类型">
              <el-select v-model="aiSkillModuleForm.module_type" style="width: 100%">
                <el-option label="全局规范" value="global" />
                <el-option label="页面模块" value="page" />
                <el-option label="业务流程" value="business_flow" />
                <el-option label="修复规则" value="repair" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="优先级">
              <el-input-number v-model="aiSkillModuleForm.priority" :min="0" :max="999" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="启用">
              <el-switch v-model="aiSkillModuleForm.is_active" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="关键词">
          <el-input v-model="aiSkillModuleForm.keywordsText" placeholder="逗号分隔，例如：创建数据要素,SYS Decimal,数据定义" />
        </el-form-item>
        <el-form-item label="意图">
          <el-input v-model="aiSkillModuleForm.intentsText" placeholder="逗号分隔，例如：create_data_element,data_element" />
        </el-form-item>
        <el-form-item label="页面">
          <el-input v-model="aiSkillModuleForm.pagesText" placeholder="逗号分隔，例如：数据结构设置,数据要素" />
        </el-form-item>
        <el-form-item label="摘要">
          <el-input v-model="aiSkillModuleForm.summary" type="textarea" :rows="2" resize="vertical" />
        </el-form-item>
        <el-form-item label="模块内容" required>
          <div class="ai-skill-module-actions">
            <el-button size="small" :loading="aiSkillModuleGenerating" @click="generateAiSkillModuleContentPreview">系统生成提示词</el-button>
            <span class="ai-skill-module-tip">根据摘要、关键词、意图和页面自动生成规范模块提示词，可继续手工调整。</span>
          </div>
          <el-input
            v-model="aiSkillModuleForm.content"
            type="textarea"
            :rows="9"
            resize="vertical"
            placeholder="填写这个模块的具体业务规则。后端只会在命中关键词/意图时加载它。"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showAiSkillModuleDialog = false">取消</el-button>
          <el-button type="primary" :loading="aiSkillModuleSaving" @click="submitAiSkillModule">保存模块</el-button>
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
      v-model="showImportCaseStepsDialog"
      title="导入用例步骤"
      :close-on-click-modal="false"
      width="480px"
    >
      <el-form :model="importCaseStepsForm" label-width="100px">
        <el-form-item label="源用例" required>
          <el-select
            v-model="importCaseStepsForm.source_case_id"
            placeholder="请选择要导入的用例"
            style="width: 100%"
          >
            <el-option
              v-for="item in importableSourceTestCases"
              :key="item.id"
              :label="`${item.name} (${item.steps?.length || 0} 步)`"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="插入位置" required>
          <el-select
            v-model="importCaseStepsForm.insert_mode"
            placeholder="请选择插入位置"
            style="width: 100%"
          >
            <el-option
              v-for="item in importInsertModeOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
              :disabled="item.disabled"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="needsImportTargetStep" label="目标步骤" required>
          <el-select
            v-model="importCaseStepsForm.target_step_id"
            placeholder="请选择目标步骤"
            style="width: 100%"
          >
            <el-option
              v-for="item in importTargetStepOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showImportCaseStepsDialog = false">{{ t('uiAutomation.common.cancel') }}</el-button>
          <el-button type="primary" @click="submitImportCaseSteps">导入</el-button>
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

        <div class="element-selector-tree-wrapper" v-loading="elementSelectorLoading">
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
  deleteTestCaseFolder,
  updateTestCase,
  getTestCaseDetail,
  batchDeleteTestCases,
  deleteTestCase as deleteTestCaseApi,
  getTestCaseFolders,
  getTestCases,
  moveTestCases,
  runTestCase as runTestCaseApi,
  copyTestCase as copyTestCaseApi,
  exportTestCases,
  importTestCases,
  getAITestCaseGenerationSkills,
  ensureDefaultAITestCaseGenerationSkill,
  updateAITestCaseGenerationSkill,
  generateAITestCases,
  importGeneratedAITestCases,
  optimizeAITestCaseGenerationSkill,
  downloadAITestCaseTemplate,
  getAITestCaseGenerationSkillModules,
  createAITestCaseGenerationSkillModule,
  updateAITestCaseGenerationSkillModule,
  deleteAITestCaseGenerationSkillModule,
  generateAITestCaseGenerationSkillModuleContent,
  ensureBuiltinAITestCaseGenerationSkillModules,
  getUiAutomationAIModelConfigs,
  getLocatorStrategies,
  getLocalRunners,
  getTestCaseExecutionDetail,
  startScrollCoordinatePicker,
  getScrollCoordinatePickerPosition,
  getScrollCoordinatePickerPages,
  setScrollCoordinatePickerActivePage,
  closeScrollCoordinatePicker
} from '@/api/ui_automation'
import { getAIModelConfigs } from '@/api/requirement-analysis'
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
  batchDeleteCases: '\u6279\u91cf\u5220\u9664',
  emptyList: '\u6682\u65e0\u6d4b\u8bd5\u7528\u4f8b',
  ungrouped: '\u672a\u5206\u7ec4',
  folderLabel: '\u6240\u5c5e\u6587\u4ef6\u5939',
  folderPlaceholder: '\u8bf7\u9009\u62e9\u6587\u4ef6\u5939',
  folderName: '\u6587\u4ef6\u5939\u540d\u79f0',
  folderNamePlaceholder: '\u8bf7\u8f93\u5165\u6587\u4ef6\u5939\u540d\u79f0',
  manageFolders: '\u7ba1\u7406\u6587\u4ef6\u5939',
  moveCount: '\u79fb\u52a8\u6570\u91cf',
  targetFolder: '\u76ee\u6807\u6587\u4ef6\u5939',
  folderNameRequired: '\u8bf7\u8f93\u5165\u6587\u4ef6\u5939\u540d\u79f0',
  folderCreateSuccess: '\u6587\u4ef6\u5939\u521b\u5efa\u6210\u529f',
  folderCreateFailed: '\u6587\u4ef6\u5939\u521b\u5efa\u5931\u8d25',
  folderDeleteTitle: '\u5220\u9664\u6587\u4ef6\u5939',
  folderDeleteSuccess: '\u6587\u4ef6\u5939\u5220\u9664\u6210\u529f',
  folderDeleteFailed: '\u6587\u4ef6\u5939\u5220\u9664\u5931\u8d25',
  folderDeleteConfirm: '\u786e\u8ba4\u5220\u9664\u6587\u4ef6\u5939\u300c{name}\u300d\u5417\uff1f\u5176\u4e2d\u7684\u7528\u4f8b\u5c06\u81ea\u52a8\u79fb\u5230\u672a\u5206\u7ec4\u3002',
  folderEmpty: '\u6682\u65e0\u6587\u4ef6\u5939',
  folderCaseCount: '\u5171 {count} \u6761\u7528\u4f8b',
  moveCasesEmpty: '\u8bf7\u5148\u9009\u62e9\u9700\u8981\u79fb\u52a8\u7684\u7528\u4f8b',
  moveSuccess: '\u7528\u4f8b\u79fb\u52a8\u6210\u529f',
  moveFailed: '\u7528\u4f8b\u79fb\u52a8\u5931\u8d25',
  batchDeleteTitle: '\u6279\u91cf\u5220\u9664\u7528\u4f8b',
  batchDeleteConfirm: '\u786e\u8ba4\u5220\u9664\u5df2\u9009\u4e2d\u7684 {count} \u6761\u7528\u4f8b\u5417\uff1f',
  batchDeleteSuccess: '\u6279\u91cf\u5220\u9664\u6210\u529f',
  batchDeleteFailed: '\u6279\u91cf\u5220\u9664\u5931\u8d25',
  selectElement: '\u9009\u62e9\u5143\u7d20',
  selectElementPlaceholder: '\u8bf7\u9009\u62e9\u5143\u7d20',
  searchElementPlaceholder: '\u641c\u7d22\u5143\u7d20\u540d\u79f0\u6216\u5b9a\u4f4d\u5185\u5bb9',
  noMatchedElements: '\u672a\u627e\u5230\u5339\u914d\u7684\u5143\u7d20',
  ungroupedElements: '\u672a\u5206\u7ec4\u5143\u7d20',
  stepEnabledLabel: '\u6b65\u9aa4\u72b6\u6001',
  stepEnabled: '\u5df2\u542f\u7528',
  stepDisabled: '\u5df2\u7981\u7528',
  logPassed: '\u5df2\u901a\u8fc7',
  logFailed: '\u5df2\u5931\u8d25',
  logSkipped: '\u5df2\u8df3\u8fc7'
}

// 响应式数据
const aiText = {
  openButton: 'AI生成用例',
  dialogTitle: 'AI生成UI自动化测试用例',
  targetProject: '导入项目',
  aiModel: 'AI模型',
  defaultModel: '使用当前启用模型',
  skill: '生成Skill',
  defaultSkill: '默认Skill',
  targetFolder: '目标文件夹',
  generatedFolder: '使用生成结果中的文件夹',
  overwrite: '覆盖同名用例',
  useAi: '使用AI模型',
  uploadFile: '上传文件',
  chooseFile: '选择文件',
  downloadTemplate: '下载用例模板',
  uploadTip: '支持 txt、md、json、csv、xlsx、xmind，单个文件不超过 10MB；推荐下载 CSV 模板填写后上传。',
  sourceTab: '自然语言用例',
  skillTab: 'Skill优化',
  sourcePlaceholder: '例如：用例：登录成功。步骤：打开登录页，输入账号 admin，输入密码 123456，点击登录，验证进入首页。也可以粘贴多条功能测试用例。',
  skillPlaceholder: '用对话描述你希望Skill如何优化，例如：优先复用已有元素；弹窗确认按钮必须带弹窗标题限定；缺少定位器时不要编造。',
  previewSkill: '预览优化',
  updateSkill: '更新当前Skill',
  saveSkill: '保存Skill',
  skillPreviewPlaceholder: '优化后的Skill会显示在这里',
  generatePreview: '生成预览',
  importNow: '一键导入',
  previewTitle: '生成预览',
  caseName: '用例名称',
  folderName: '文件夹',
  priority: '优先级',
  stepCount: '步骤数',
  firstSteps: '首批步骤',
  emptyPreview: '暂无生成结果',
  importToManager: '一键导入到用例管理',
  activeSuffix: '（启用）',
  defaultSuffix: '（默认）',
  generationAi: 'AI生成',
  generationManifest: '模板/JSON',
  generationHeuristic: '规则兜底',
  fileTooLarge: '上传文件不能超过 10MB',
  unsupportedFile: '支持 txt/md/json/csv/xlsx/xmind 文件',
  needInput: '请输入自然语言用例或上传用例文件',
  generateSuccess: 'AI用例生成完成',
  importSuccess: 'AI生成用例导入成功',
  templateDownloadFailed: '模板下载失败'
}

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
const draggingTransactionId = ref('')
const availableElements = ref([])
const searchKeyword = ref('')
const folderFilter = ref('all')
const showCreateDialog = ref(false)
const showFolderDialog = ref(false)
const showMoveDialog = ref(false)
const showImportDialog = ref(false)
const showImportCaseStepsDialog = ref(false)
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
const scrollCoordinatePickerSessionId = ref('')
const scrollCoordinatePickerProjectId = ref('')
const scrollCoordinatePickerMode = ref('server')
const scrollCoordinatePickerRunnerId = ref('')
const scrollCoordinatePickerElementId = ref('')
const scrollCoordinatePickerStarting = ref(false)
const scrollCoordinatePickerReadingStart = ref(false)
const scrollCoordinatePickerReadingTarget = ref(false)
const scrollCoordinatePickerPages = ref([])
const scrollCoordinatePickerActivePageIndex = ref(0)
const scrollCoordinatePickerPagesLoading = ref(false)
const scrollCoordinatePickerSwitchingPage = ref(false)
const showVariableHelper = ref(false)
const currentEditingStep = ref(null)
const currentEditingField = ref('')
const showDataFactorySelector = ref(false)
const currentStepForDataFactory = ref(null)
const currentFieldForDataFactory = ref('')
const currentSelectingStep = ref(null)
const folderDeletingId = ref(null)
const currentSelectingField = ref('element_id')
const elementSelectorKeyword = ref('')
const elementSelectorLoading = ref(false)
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
const showAiGenerateDialog = ref(false)
const aiGenerateTab = ref('source')
const aiSourceUploadRef = ref(null)
const aiSkills = ref([])
const aiModelConfigs = ref([])
const aiSourceFile = ref(null)
const aiSourceFileInfo = ref(null)
const aiGenerating = ref(false)
const aiImporting = ref(false)
const aiSkillOptimizing = ref(false)
const aiSkillSaving = ref(false)
const aiTemplateDownloading = ref(false)
const aiGeneratedRecordId = ref(null)
const aiGeneratedManifest = ref(null)
const aiGeneratedCases = ref([])
const aiGenerateWarnings = ref([])
const aiGenerationMode = ref('')
const aiSkillRoute = ref(null)
const aiSkillPreview = ref('')
const aiSkillOptimizeInstruction = ref('')
const aiSkillModules = ref([])
const aiSkillModulesLoading = ref(false)
const showAiSkillModuleDialog = ref(false)
const aiSkillModuleSaving = ref(false)
const aiSkillModuleGenerating = ref(false)
const aiGenerateForm = reactive({
  text: '',
  model_config_id: null,
  skill_id: null,
  folder_id: null,
  overwrite: false,
  use_ai: true
})
const aiSkillModuleForm = reactive({
  id: null,
  name: '',
  code: '',
  module_type: 'business_flow',
  summary: '',
  content: '',
  keywordsText: '',
  intentsText: '',
  pagesText: '',
  priority: 100,
  is_active: true
})
const importCaseStepsForm = reactive({
  source_case_id: null,
  insert_mode: 'end',
  target_step_id: null
})



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
const importableSourceTestCases = computed(() => {
  const currentCaseId = selectedTestCase.value?.id
  return testCases.value.filter(item => item.id !== currentCaseId)
})

const importInsertModeOptions = computed(() => {
  const hasTargetSteps = currentSteps.value.length > 0
  return [
    { value: 'start', label: '\u63d2\u5165\u5230\u5f00\u5934', disabled: false },
    { value: 'end', label: '\u63d2\u5165\u5230\u672b\u5c3e', disabled: false },
    { value: 'before', label: '\u63d2\u5165\u5230\u6307\u5b9a\u6b65\u9aa4\u524d', disabled: !hasTargetSteps },
    { value: 'after', label: '\u63d2\u5165\u5230\u6307\u5b9a\u6b65\u9aa4\u540e', disabled: !hasTargetSteps }
  ]
})

const needsImportTargetStep = computed(() => {
  return ['before', 'after'].includes(importCaseStepsForm.insert_mode)
})

const importTargetStepOptions = computed(() => {
  return currentSteps.value.map((step, index) => ({
    value: step.id,
    label: `${index + 1}. ${getStepSummary(step, index)}`
  }))
})

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

const selectedScrollCoordinatePickerRunner = computed(() => {
  return onlineLocalRunners.value.find(item => String(item.id) === String(selectedRunnerId.value)) || null
})

const useLocalScrollCoordinatePicker = computed(() => {
  return executionMode.value === 'local' && Boolean(selectedRunnerId.value)
})

const scrollCoordinatePickerExecutionTargetLabel = computed(() => {
  if (useLocalScrollCoordinatePicker.value) {
    return selectedScrollCoordinatePickerRunner.value
      ? `访客机本地执行器“${selectedScrollCoordinatePickerRunner.value.name}”`
      : '访客机本地执行器'
  }
  return '服务器采集浏览器'
})

const scrollCoordinatePickerGuideText = computed(() => {
  if (useLocalScrollCoordinatePicker.value) {
    return [
      `当前会在${scrollCoordinatePickerExecutionTargetLabel.value}上打开坐标采集浏览器，不会在服务器上采集。`,
      '第1步：点击“开始滚动位置”或“滚动到位置”，系统会自动连接本地执行器并打开浏览器。',
      '第2步：在访客机打开的浏览器里滚动到目标位置。',
      '第3步：回到当前页面点击弹窗中的“确定”，系统会读取当前滚动坐标并自动回填。'
    ]
  }

  return [
    '当前未选择本地执行器，坐标将由服务器采集浏览器读取。',
    '第1步：点击“开始滚动位置”或“滚动到位置”打开采集浏览器。',
    '第2步：在采集浏览器里滚动到目标位置。',
    '第3步：回到当前页面点击弹窗中的“确定”，系统会读取当前滚动坐标并自动回填。'
  ]
})

const getScrollCoordinateTargetTypeLabel = (step) => {
  return step?.element_id ? '所选滚动容器' : '整个页面'
}

const getScrollCoordinateGuideLines = (step) => {
  const targetTypeLabel = getScrollCoordinateTargetTypeLabel(step)
  return [
    `点击“打开网页”后，会在${scrollCoordinatePickerExecutionTargetLabel.value}打开采集网页，取点目标为${targetTypeLabel}。`,
    '如果登录后跳到了新页面或新标签页，继续在当前看到的页面上操作即可，系统会捕捉该页面。',
    step?.element_id
      ? '请在需要滚动的容器内部右键取点，例如左侧菜单栏内部。'
      : '请在需要滚动的页面区域内右键取点。',
    '先点“开始滚动位置”，在网页里右键一次；再点“滚动到位置”，在网页里右键第二次。',
    '执行时会在开始坐标处使用鼠标滚轮滚动到目标方向，不再读取整个页面的 scrollTop。'
  ]

  if (useLocalScrollCoordinatePicker.value) {
    return [
      `当前会在${scrollCoordinatePickerExecutionTargetLabel.value}上打开坐标采集浏览器，采集目标为${targetTypeLabel}。`,
      step?.element_id
        ? '第1步：先给当前步骤选择左侧菜单栏这样的滚动容器，再点击“开始滚动位置”或“滚动到位置”。'
        : '第1步：点击“开始滚动位置”或“滚动到位置”，系统会自动连接本地执行器并打开浏览器。',
      step?.element_id
        ? '第2步：只在这个容器内部滚动，不要滚动整个页面；如果采到 Y=0，表示该容器当前在顶部。'
        : '第2步：在访客机浏览器里滚动整个页面到目标位置。',
      '第3步：回到当前页面点击弹窗中的“确定”，系统会读取当前滚动坐标并自动回填。'
    ]
  }

  return [
    `当前未选择本地执行器，坐标将由服务器采集浏览器读取，采集目标为${targetTypeLabel}。`,
    step?.element_id
      ? '第1步：先给当前步骤选择左侧菜单栏这样的滚动容器，再点击“开始滚动位置”或“滚动到位置”。'
      : '第1步：点击“开始滚动位置”或“滚动到位置”打开采集浏览器。',
    step?.element_id
      ? '第2步：只在这个容器内部滚动，不要滚动整个页面；如果采到 Y=0，表示该容器当前在顶部。'
      : '第2步：在采集浏览器里滚动整个页面到目标位置。',
    '第3步：回到当前页面点击弹窗中的“确定”，系统会读取当前滚动坐标并自动回填。'
  ]
}

const buildScrollCaptureSuccessMessage = (position, step, isStart) => {
  const x = Number(position?.x ?? 0)
  const y = Number(position?.y ?? 0)
  const prefix = isStart ? '已获取开始滚动位置' : '已获取目标滚动位置'
  const baseMessage = `${prefix} (${x}, ${y})`
  if (String(position?.scope || '').toLowerCase() === 'click') {
    const pageTitle = String(position?.title || '').trim()
    const pageUrl = String(position?.url || '').trim()
    const extra = [pageTitle, pageUrl].filter(Boolean).join(' | ')
    return extra ? `${baseMessage} - ${extra}` : baseMessage
  }

  if (String(position?.scope || '').toLowerCase() !== 'element') {
    return baseMessage
  }

  const selectedTarget = String(position?.target_name || '').trim() || getSelectedElementLabel(step?.element_id)
  const resolvedTarget = String(position?.resolvedTarget || '').trim()
  const rangeY = Number(position?.scrollRangeY ?? 0)
  const rangeX = Number(position?.scrollRangeX ?? 0)
  const details = [
    selectedTarget ? `目标元素：${selectedTarget}` : '',
    resolvedTarget ? `实际滚动容器：${resolvedTarget}` : '',
    `纵向范围：${rangeY}`,
    `横向范围：${rangeX}`,
    rangeY > 0 && y === 0 ? '当前位于容器顶部' : ''
  ].filter(Boolean)

  return details.length ? `${baseMessage}，${details.join('，')}` : baseMessage
}

const aiGenerationModeLabel = computed(() => {
  if (aiGenerationMode.value === 'ai') return aiText.generationAi
  if (aiGenerationMode.value === 'manifest') return aiText.generationManifest
  if (aiGenerationMode.value === 'heuristic') return aiText.generationHeuristic
  return aiGenerationMode.value
})

const aiSkillRouteEntityEntries = computed(() => {
  const entities = aiSkillRoute.value?.detected_entities || {}
  return Object.entries(entities).filter(([, value]) => {
    if (Array.isArray(value)) {
      return value.length > 0
    }
    if (value && typeof value === 'object') {
      return Object.keys(value).length > 0
    }
    return Boolean(value)
  }).map(([key, value]) => ({ key, value }))
})

const aiSkillModuleTypeLabel = (type) => {
  const labels = {
    global: '全局规范',
    page: '页面模块',
    business_flow: '业务流程',
    repair: '修复规则'
  }
  return labels[type] || type || '-'
}

const aiSkillModuleTypeTag = (type) => {
  const tags = {
    global: 'info',
    page: 'warning',
    business_flow: 'success',
    repair: 'danger'
  }
  return tags[type] || 'info'
}

const formatAiSkillRouteEntityValue = (value) => {
  if (Array.isArray(value)) {
    return value.map(item => (typeof item === 'object' ? JSON.stringify(item) : String(item))).join(' | ')
  }
  if (value && typeof value === 'object') {
    return JSON.stringify(value)
  }
  return String(value ?? '')
}

const formatAiSkillRouteOmittedReason = (reason) => {
  const labels = {
    max_modules: '超过模块数量上限',
    max_prompt_chars: '超过 Prompt 长度上限'
  }
  return labels[reason] || reason || '未加载'
}

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

const isSameEntityId = (left, right) => {
  if (left === null || left === undefined || right === null || right === undefined) {
    return false
  }

  return String(left) === String(right)
}

const collectElementGroupIds = (groups = [], target = new Set()) => {
  groups.forEach((group) => {
    if (group?.id !== null && group?.id !== undefined) {
      target.add(String(group.id))
    }
    if (group?.children?.length) {
      collectElementGroupIds(group.children, target)
    }
  })
  return target
}

const elementTreeOptions = computed(() => {
  const groupIds = collectElementGroupIds(elementGroups.value || [])

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
        .filter(element => isSameEntityId(element.group_id, group.id))
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
    .filter(element => !element.group_id || !groupIds.has(String(element.group_id)))
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
  return ['fill', 'fillAndEnter', 'getText', 'switchTab', 'assert'].includes(actionType)
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

const parseScrollPayload = (inputValue) => {
  const rawValue = String(inputValue || '').trim()
  if (!rawValue) {
    return {}
  }

  try {
    const payload = JSON.parse(rawValue)
    if (payload?.scroll_mode !== 'coordinates') {
      return {}
    }

    return {
      scroll_scope: payload.scroll_scope || '',
      scroll_direction: payload.scroll_direction || '',
      start_x: payload.start_x ?? null,
      start_y: payload.start_y ?? null,
      target_x: payload.target_x ?? null,
      target_y: payload.target_y ?? null
    }
  } catch (error) {
    return {}
  }
}

const hasScrollCoordinateConfig = (step) => {
  return Boolean(
    step?.scroll_direction ||
    step?.scroll_start_x !== null && step?.scroll_start_x !== '' && step?.scroll_start_x !== undefined ||
    step?.scroll_start_y !== null && step?.scroll_start_y !== '' && step?.scroll_start_y !== undefined ||
    step?.scroll_target_x !== null && step?.scroll_target_x !== '' && step?.scroll_target_x !== undefined ||
    step?.scroll_target_y !== null && step?.scroll_target_y !== '' && step?.scroll_target_y !== undefined
  )
}

const buildScrollPayload = (step) => {
  if (!hasScrollCoordinateConfig(step)) {
    return ''
  }

  return JSON.stringify({
    scroll_mode: 'coordinates',
    scroll_scope: step.element_id ? 'element' : 'window',
    scroll_direction: step.scroll_direction || 'vertical',
    start_x: step.scroll_start_x,
    start_y: step.scroll_start_y,
    target_x: step.scroll_target_x,
    target_y: step.scroll_target_y
  })
}

const parseCanvasPayload = (inputValue) => {
  const rawValue = String(inputValue || '').trim()
  if (!rawValue) {
    return {}
  }

  try {
    const payload = JSON.parse(rawValue)
    if (payload?.mode !== 'canvas') {
      return {}
    }

    return {
      canvas_action: payload.action || '',
      canvas_frame_selector: payload.frame_selector || '#plt-workflow-iframe',
      canvas_frame_url: payload.frame_url || '',
      canvas_page_index: payload.page_index ?? payload.active_page_index ?? null,
      canvas_click_x: payload.x ?? null,
      canvas_click_y: payload.y ?? null,
      canvas_start_x: payload.start?.x ?? null,
      canvas_start_y: payload.start?.y ?? null,
      canvas_target_x: payload.target?.x ?? null,
      canvas_target_y: payload.target?.y ?? null,
      canvas_hold_ms: payload.hold_ms ?? 300,
      canvas_steps: payload.steps ?? 30
    }
  } catch (error) {
    return {}
  }
}

const hasCoordinateValue = (value) => value !== null && value !== '' && value !== undefined

const buildCanvasPayload = (step) => {
  const frameSelector = String(step.canvas_frame_selector || '').trim() || '#plt-workflow-iframe'
  const basePayload = {
    mode: 'canvas',
    action: step.action_type === 'canvasDrag' ? 'drag' : 'click',
    frame_selector: frameSelector,
    frame_url: String(step.canvas_frame_url || '').trim(),
    frame_url_keyword: 'workflow-modeler',
    hold_ms: Number(step.canvas_hold_ms ?? 300) || 300,
    steps: Number(step.canvas_steps ?? 30) || 30
  }

  if (step.action_type === 'canvasClick') {
    if (!hasCoordinateValue(step.canvas_click_x) || !hasCoordinateValue(step.canvas_click_y)) {
      return ''
    }
    return JSON.stringify({
      ...basePayload,
      x: Number(step.canvas_click_x),
      y: Number(step.canvas_click_y)
    })
  }

  if (
    !hasCoordinateValue(step.canvas_start_x) ||
    !hasCoordinateValue(step.canvas_start_y) ||
    !hasCoordinateValue(step.canvas_target_x) ||
    !hasCoordinateValue(step.canvas_target_y)
  ) {
    return ''
  }

  return JSON.stringify({
    ...basePayload,
    start: {
      x: Number(step.canvas_start_x),
      y: Number(step.canvas_start_y)
    },
    target: {
      x: Number(step.canvas_target_x),
      y: Number(step.canvas_target_y)
    }
  })
}

const formatCanvasPoint = (x, y) => {
  if (!hasCoordinateValue(x) || !hasCoordinateValue(y)) {
    return '未采集'
  }
  return `(${x}, ${y})`
}

const createStepDraft = (step = {}, expanded = false) => ({
  ...(() => {
    const dragPayload = parseDragTargetPayload(step.input_value)
    const scrollPayload = parseScrollPayload(step.input_value)
    const canvasPayload = parseCanvasPayload(step.input_value)
    return {
      drag_target_element_id: dragPayload.target_element_id || '',
      scroll_direction: scrollPayload.scroll_direction || '',
      scroll_start_x: scrollPayload.start_x ?? null,
      scroll_start_y: scrollPayload.start_y ?? null,
      scroll_target_x: scrollPayload.target_x ?? null,
      scroll_target_y: scrollPayload.target_y ?? null,
      canvas_frame_selector: canvasPayload.canvas_frame_selector || '#plt-workflow-iframe',
      canvas_frame_url: canvasPayload.canvas_frame_url || '',
      canvas_page_index: canvasPayload.canvas_page_index ?? null,
      canvas_click_x: canvasPayload.canvas_click_x ?? null,
      canvas_click_y: canvasPayload.canvas_click_y ?? null,
      canvas_start_x: canvasPayload.canvas_start_x ?? null,
      canvas_start_y: canvasPayload.canvas_start_y ?? null,
      canvas_target_x: canvasPayload.canvas_target_x ?? null,
      canvas_target_y: canvasPayload.canvas_target_y ?? null,
      canvas_hold_ms: Number(canvasPayload.canvas_hold_ms ?? 300) || 300,
      canvas_steps: Number(canvasPayload.canvas_steps ?? 30) || 30
    }
  })(),
  id: step.id ?? `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
  action_type: step.action_type || 'click',
  element_id: step.element_id ?? step.element ?? '',
  element_locator_strategy: step.element_locator_strategy || '',
  element_locator_value: step.element_locator_value || '',
  input_value: step.input_value || '',
  wait_time: Number(step.wait_time ?? 1000) || 1000,
  assert_type: step.assert_type || 'textContains',
  assert_value: step.assert_value || '',
  description: step.description || '',
  is_enabled: step.is_enabled !== false,
  save_as: step.save_as || '',
  transaction_id: String(step.transaction_id || '').trim(),
  transaction_name: String(step.transaction_name || '').trim(),
  transaction_disabled: step.transaction_disabled === true,
  expanded
})

const createTransactionId = () => {
  return `tx-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

const resetImportCaseStepsForm = () => {
  importCaseStepsForm.source_case_id = importableSourceTestCases.value[0]?.id ?? null
  importCaseStepsForm.insert_mode = currentSteps.value.length ? 'after' : 'end'
  importCaseStepsForm.target_step_id = currentSteps.value.some(step => isSameStepId(step.id, selectedStepId.value))
    ? selectedStepId.value
    : (currentSteps.value[0]?.id ?? null)
}

const openImportCaseStepsDialog = () => {
  if (!selectedTestCase.value) {
    ElMessage.warning('\u8bf7\u5148\u9009\u62e9\u76ee\u6807\u7528\u4f8b')
    return
  }

  if (!importableSourceTestCases.value.length) {
    ElMessage.warning('\u5f53\u524d\u9879\u76ee\u6ca1\u6709\u5176\u4ed6\u53ef\u5bfc\u5165\u7528\u4f8b')
    return
  }

  resetImportCaseStepsForm()
  showImportCaseStepsDialog.value = true
}

const cloneImportedSteps = (sourceSteps = []) => {
  const transactionIdMap = new Map()

  return (sourceSteps || []).map((step) => {
    const clonedStep = createStepDraft({ ...step, id: null }, false)
    const originalTransactionId = String(step?.transaction_id || '').trim()

    if (!originalTransactionId) {
      clonedStep.transaction_id = ''
      clonedStep.transaction_name = ''
      clonedStep.transaction_disabled = false
      return clonedStep
    }

    if (!transactionIdMap.has(originalTransactionId)) {
      transactionIdMap.set(originalTransactionId, createTransactionId())
    }

    clonedStep.transaction_id = transactionIdMap.get(originalTransactionId)
    clonedStep.transaction_name = String(step?.transaction_name || '').trim()
    return clonedStep
  })
}

const getImportInsertIndex = () => {
  if (importCaseStepsForm.insert_mode === 'start') {
    return 0
  }

  if (importCaseStepsForm.insert_mode === 'end') {
    return currentSteps.value.length
  }

  const targetIndex = currentSteps.value.findIndex(step => isSameStepId(step.id, importCaseStepsForm.target_step_id))
  if (targetIndex < 0) {
    return -1
  }

  return importCaseStepsForm.insert_mode === 'before' ? targetIndex : targetIndex + 1
}

const getTransactionId = (step) => {
  return String(step?.transaction_id || '').trim()
}

const getTransactionName = (step) => {
  return String(step?.transaction_name || '').trim()
}

const getTransactionDisabled = (step) => {
  return step?.transaction_disabled === true
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

const collapseAllTransactionBlocks = () => {
  const transactionIds = [
    ...new Set(currentSteps.value.map(step => getTransactionId(step)).filter(Boolean))
  ]

  transactionCollapseState.value = Object.fromEntries(
    transactionIds.map(transactionId => [transactionId, true])
  )
}

const clearTransactionFromSteps = (steps = []) => {
  steps.forEach((step) => {
    step.transaction_id = ''
    step.transaction_name = ''
    step.transaction_disabled = false
  })
}

const applyTransactionToStep = (step, transactionSource) => {
  const transactionId = getTransactionId(transactionSource)
  const transactionName = getTransactionName(transactionSource)
  const transactionDisabled = getTransactionDisabled(transactionSource)

  if (!transactionId || !transactionName) {
    step.transaction_id = ''
    step.transaction_name = ''
    step.transaction_disabled = false
    return
  }

  step.transaction_id = transactionId
  step.transaction_name = transactionName
  step.transaction_disabled = transactionDisabled
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
  let segmentTransactionDisabled = false

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
        step.transaction_disabled = segmentTransactionDisabled
      })
      seenTransactionIds.add(segmentTransactionId)
    }

    segmentSteps = []
    segmentTransactionId = ''
    segmentTransactionName = ''
    segmentTransactionDisabled = false
  }

  currentSteps.value.forEach((step) => {
    const transactionId = getTransactionId(step)
    const transactionName = getTransactionName(step)

    if (!transactionId || !transactionName) {
      finalizeSegment()
      step.transaction_id = ''
      step.transaction_name = ''
      step.transaction_disabled = false
      return
    }

    if (!segmentSteps.length || segmentTransactionId === transactionId) {
      segmentSteps.push(step)
      segmentTransactionId = transactionId
      segmentTransactionDisabled = segmentTransactionDisabled || getTransactionDisabled(step)
      segmentTransactionName = segmentTransactionName || transactionName || '未命名事务块'
      return
    }

    finalizeSegment()
    segmentSteps = [step]
    segmentTransactionId = transactionId
    segmentTransactionDisabled = getTransactionDisabled(step)
    segmentTransactionName = transactionName || '未命名事务块'
  })

  finalizeSegment()

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

const isTransactionDisabled = (transactionId) => {
  const steps = getTransactionSteps(transactionId)
  return steps.length > 0 && steps.every(step => step.transaction_disabled === true)
}

const toggleTransactionDisabled = (transactionId, enabled) => {
  const disabled = !Boolean(enabled)
  getTransactionSteps(transactionId).forEach((step) => {
    step.transaction_disabled = disabled
  })
  ElMessage.success(disabled ? '事务块已禁用，执行时将跳过块内所有步骤' : '事务块已启用')
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
        step.transaction_disabled = false
      }
    })

    transactionCollapseState.value = {
      ...transactionCollapseState.value,
      [transactionId]: false
    }
    normalizeTransactionBlocks()
    ElMessage.success(`已创建事务块“${transactionName}”`)
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
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
      step.transaction_disabled = false
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

const copyTransactionBlock = (transactionId) => {
  const steps = getTransactionSteps(transactionId)
  if (!steps.length) {
    return
  }

  const range = getTransactionRange(transactionId)
  const newTransactionId = createTransactionId()
  const newTransactionName = `${getTransactionName(steps[0]) || '事务块'} 副本`
  const transactionDisabled = isTransactionDisabled(transactionId)
  const copiedSteps = steps.map((step) => {
    const copiedStep = createStepDraft({
      ...step,
      id: null,
      transaction_id: newTransactionId,
      transaction_name: newTransactionName,
      transaction_disabled: transactionDisabled
    }, false)
    copiedStep.expanded = false
    return copiedStep
  })

  currentSteps.value.splice((range?.end ?? currentSteps.value.length - 1) + 1, 0, ...copiedSteps)
  selectedStepId.value = copiedSteps[0]?.id ?? null
  checkedStepIds.value = copiedSteps.map(step => step.id)
  transactionCollapseState.value = {
    ...transactionCollapseState.value,
    [newTransactionId]: false
  }
  normalizeTransactionBlocks()
  ElMessage.success(`已复制事务块“${newTransactionName}”，请保存用例`)
}

const deleteTransactionBlock = async (transactionId) => {
  const steps = getTransactionSteps(transactionId)
  if (!steps.length) {
    return
  }

  const transactionName = getTransactionName(steps[0]) || '事务块'
  try {
    await ElMessageBox.confirm(
      `确认删除事务块“${transactionName}”及块内 ${steps.length} 个步骤？此操作保存后生效。`,
      '删除事务块',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
  } catch (error) {
    return
  }

  const stepIds = new Set(steps.map(step => String(step.id)))
  currentSteps.value = currentSteps.value.filter(step => !stepIds.has(String(step.id)))
  checkedStepIds.value = checkedStepIds.value.filter(id => !stepIds.has(String(id)))
  if (selectedStepId.value && stepIds.has(String(selectedStepId.value))) {
    selectedStepId.value = currentSteps.value[0]?.id ?? null
  }
  delete transactionCollapseState.value[String(transactionId || '')]
  normalizeTransactionBlocks()
  ElMessage.success(`已删除事务块“${transactionName}”，请保存用例`)
}

const clearTransactionBlock = (transactionId) => {
  getTransactionSteps(transactionId).forEach((step) => {
    step.transaction_id = ''
    step.transaction_name = ''
    step.transaction_disabled = false
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
  element_id: needsElement(step.action_type) ? (step.element_id || null) : null,
  element_locator_strategy: needsElement(step.action_type) ? (step.element_locator_strategy || '') : '',
  element_locator_value: needsElement(step.action_type) ? String(step.element_locator_value || '').trim() : '',
  input_value: isCanvasAction(step.action_type)
    ? buildCanvasPayload(step)
    : step.action_type === 'drag'
      ? buildDragTargetPayload(step.drag_target_element_id)
      : step.action_type === 'scroll'
        ? buildScrollPayload(step)
        : (needsInputValue(step.action_type) ? (step.input_value || '') : ''),
  wait_time: needsWaitTime(step.action_type) ? (Number(step.wait_time) || 1000) : 1000,
  assert_type: step.action_type === 'assert' ? (step.assert_type || 'textContains') : '',
  assert_value: step.action_type === 'assert' ? (step.assert_value || '') : '',
  description: String(step.description || '').trim(),
  is_enabled: step.is_enabled !== false,
  save_as: canStoreVariable(step.action_type) ? String(step.save_as || '').trim() : '',
  transaction_id: getTransactionId(step),
  transaction_name: getTransactionName(step),
  transaction_disabled: hasTransaction(step) && step.transaction_disabled === true
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
  if (isCanvasAction(step.action_type)) {
    if (step.action_type === 'canvasClick') {
      return `点击 ${formatCanvasPoint(step.canvas_click_x, step.canvas_click_y)}`
    }
    return `拖拽 ${formatCanvasPoint(step.canvas_start_x, step.canvas_start_y)} -> ${formatCanvasPoint(step.canvas_target_x, step.canvas_target_y)}`
  }

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

    if (step.action_type === 'canvasClick') {
      if (!hasCoordinateValue(step.canvas_click_x) || !hasCoordinateValue(step.canvas_click_y)) {
        step.expanded = true
        ElMessage.warning(`步骤 ${index + 1} 请先采集画布点击位置`)
        return false
      }
    }

    if (step.action_type === 'canvasDrag') {
      if (
        !hasCoordinateValue(step.canvas_start_x) ||
        !hasCoordinateValue(step.canvas_start_y) ||
        !hasCoordinateValue(step.canvas_target_x) ||
        !hasCoordinateValue(step.canvas_target_y)
      ) {
        step.expanded = true
        ElMessage.warning(`步骤 ${index + 1} 请先采集画布拖拽起点和终点`)
        return false
      }
    }

    if (step.action_type === 'scroll' && hasScrollCoordinateConfig(step)) {
      const direction = step.scroll_direction || 'vertical'
      const hasStartX = step.scroll_start_x !== null && step.scroll_start_x !== '' && step.scroll_start_x !== undefined
      const hasTargetX = step.scroll_target_x !== null && step.scroll_target_x !== '' && step.scroll_target_x !== undefined
      const hasStartY = step.scroll_start_y !== null && step.scroll_start_y !== '' && step.scroll_start_y !== undefined
      const hasTargetY = step.scroll_target_y !== null && step.scroll_target_y !== '' && step.scroll_target_y !== undefined

      if (direction === 'horizontal') {
        if (!hasStartX || !hasTargetX) {
          step.expanded = true
          ElMessage.warning(`步骤 ${index + 1} 横向滚动需要填写起始X和目标X坐标`)
          return false
        }
      } else if (!hasStartY || !hasTargetY) {
        step.expanded = true
        ElMessage.warning(`步骤 ${index + 1} 纵向滚动需要填写起始Y和目标Y坐标`)
        return false
      }

      if (direction === 'up' && Number(step.scroll_target_y) >= Number(step.scroll_start_y)) {
        step.expanded = true
        ElMessage.warning(`步骤 ${index + 1} 往上滚动要求目标Y小于起始Y`)
        return false
      }

      if (direction === 'down' && Number(step.scroll_target_y) <= Number(step.scroll_start_y)) {
        step.expanded = true
        ElMessage.warning(`步骤 ${index + 1} 往下滚动要求目标Y大于起始Y`)
        return false
      }
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

const getTransactionRange = (transactionId) => {
  const normalizedId = String(transactionId || '')
  const indices = currentSteps.value.reduce((result, step, index) => {
    if (getTransactionId(step) === normalizedId) {
      result.push(index)
    }
    return result
  }, [])

  if (!indices.length) {
    return null
  }

  return {
    start: Math.min(...indices),
    end: Math.max(...indices),
    length: indices.length
  }
}

const handleTransactionDragStart = (transactionId, event) => {
  const normalizedId = String(transactionId || '')
  if (!normalizedId) {
    return
  }

  draggingTransactionId.value = normalizedId
  if (event?.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', normalizedId)
  }
}

const handleTransactionDragEnd = () => {
  draggingTransactionId.value = ''
}

const handleTransactionDrop = (targetTransactionId, event) => {
  const sourceTransactionId = draggingTransactionId.value
  const targetId = String(targetTransactionId || '')
  draggingTransactionId.value = ''

  if (!sourceTransactionId || !targetId || sourceTransactionId === targetId) {
    return
  }

  const sourceRange = getTransactionRange(sourceTransactionId)
  const targetRange = getTransactionRange(targetId)
  if (!sourceRange || !targetRange) {
    return
  }

  const movedSteps = currentSteps.value.splice(sourceRange.start, sourceRange.length)
  const targetRect = event?.currentTarget?.getBoundingClientRect?.()
  const dropAfterTarget = targetRect
    ? event.clientY > targetRect.top + targetRect.height / 2
    : false
  let insertIndex = dropAfterTarget ? targetRange.end + 1 : targetRange.start
  if (sourceRange.start < insertIndex) {
    insertIndex = Math.max(0, insertIndex - sourceRange.length)
  }

  currentSteps.value.splice(insertIndex, 0, ...movedSteps)
  normalizeTransactionBlocks()
  ElMessage.success('事务块顺序已调整，请保存用例')
}

const extractRequestErrorMessage = (error, fallback) => {
  const responseData = error?.response?.data

  const normalizeMessage = (value) => {
    if (!value) {
      return ''
    }

    if (Array.isArray(value)) {
      return normalizeMessage(value[0])
    }

    if (typeof value === 'string') {
      return value
    }

    if (typeof value === 'object') {
      const nestedValue = Object.values(value).find(item => item)
      return normalizeMessage(nestedValue)
    }

    return ''
  }

  const prioritizedMessage = normalizeMessage(
    responseData?.name
      || responseData?.detail
      || responseData?.message
      || responseData?.error
      || responseData?.non_field_errors
  )

  if (prioritizedMessage) {
    return prioritizedMessage
  }

  if (responseData && typeof responseData === 'object') {
    const fieldMessage = Object.values(responseData)
      .map(item => normalizeMessage(item))
      .find(Boolean)
    if (fieldMessage) {
      return fieldMessage
    }
  }

  if (typeof error?.message === 'string' && error.message.trim()) {
    return error.message.trim()
  }

  return fallback
}

const resetScrollCoordinatePickerSession = () => {
  scrollCoordinatePickerSessionId.value = ''
  scrollCoordinatePickerProjectId.value = ''
  scrollCoordinatePickerMode.value = 'server'
  scrollCoordinatePickerRunnerId.value = ''
  scrollCoordinatePickerElementId.value = ''
  scrollCoordinatePickerPages.value = []
  scrollCoordinatePickerActivePageIndex.value = 0
}

const closeScrollCoordinatePickerSession = async (silent = false) => {
  const sessionId = scrollCoordinatePickerSessionId.value
  resetScrollCoordinatePickerSession()

  if (!sessionId) {
    return
  }

  try {
    await closeScrollCoordinatePicker({ session_id: sessionId })
  } catch (error) {
    if (!silent) {
      ElMessage.error(extractRequestErrorMessage(error, '关闭滚动坐标采集浏览器失败'))
    }
  }
}

const applyScrollCoordinatePickerPagesPayload = (payload) => {
  const pages = Array.isArray(payload?.pages) ? payload.pages : []
  scrollCoordinatePickerPages.value = pages

  const payloadIndex = Number(payload?.active_page_index ?? 0)
  const activeEntry = pages.find(item => item && item.is_active)
  const activeIndex = activeEntry ? Number(activeEntry.index ?? 0) : payloadIndex
  scrollCoordinatePickerActivePageIndex.value = Number.isFinite(activeIndex) ? activeIndex : 0
}

const refreshScrollCoordinatePickerPages = async (showError = false) => {
  const sessionId = scrollCoordinatePickerSessionId.value
  if (!sessionId) {
    scrollCoordinatePickerPages.value = []
    scrollCoordinatePickerActivePageIndex.value = 0
    return null
  }

  scrollCoordinatePickerPagesLoading.value = true
  try {
    const response = await getScrollCoordinatePickerPages({ session_id: sessionId })
    applyScrollCoordinatePickerPagesPayload(response.data || {})
    return response.data || {}
  } catch (error) {
    if (showError) {
      ElMessage.error(extractRequestErrorMessage(error, '读取采集页面列表失败'))
    }
    throw error
  } finally {
    scrollCoordinatePickerPagesLoading.value = false
  }
}

const switchScrollCoordinatePickerPage = async (pageIndex, showError = true) => {
  const sessionId = scrollCoordinatePickerSessionId.value
  if (!sessionId) {
    throw new Error('请先点击“打开网页”')
  }

  scrollCoordinatePickerSwitchingPage.value = true
  try {
    const response = await setScrollCoordinatePickerActivePage({
      session_id: sessionId,
      page_index: Number(pageIndex)
    })
    applyScrollCoordinatePickerPagesPayload(response.data || {})
    return response.data || {}
  } catch (error) {
    if (showError) {
      ElMessage.error(extractRequestErrorMessage(error, '切换采集页面失败'))
    }
    throw error
  } finally {
    scrollCoordinatePickerSwitchingPage.value = false
  }
}

const ensureScrollCoordinatePickerSession = async (step, options = {}) => {
  if (!selectedProject.value?.base_url) {
    throw new Error('当前项目未配置基础URL，无法获取滚动坐标')
  }

  const forceReopen = Boolean(options?.forceReopen)
  const currentProjectId = String(selectedProject.value.id || '')
  const expectedMode = useLocalScrollCoordinatePicker.value ? 'local' : 'server'
  const expectedRunnerId = useLocalScrollCoordinatePicker.value ? String(selectedRunnerId.value || '') : ''
  const expectedElementId = String(step?.element_id || '')
  if (
    !forceReopen &&
    scrollCoordinatePickerSessionId.value &&
    scrollCoordinatePickerProjectId.value === currentProjectId &&
    scrollCoordinatePickerMode.value === expectedMode &&
    scrollCoordinatePickerRunnerId.value === expectedRunnerId &&
    scrollCoordinatePickerElementId.value === expectedElementId
  ) {
    return {
      sessionId: scrollCoordinatePickerSessionId.value,
      mode: scrollCoordinatePickerMode.value,
      created: false
    }
  }

  if (scrollCoordinatePickerSessionId.value) {
    await closeScrollCoordinatePickerSession(true)
  }

  scrollCoordinatePickerStarting.value = true
  try {
    const response = await startScrollCoordinatePicker({
      project_id: selectedProject.value.id,
      browser: selectedBrowser.value,
      runner_id: useLocalScrollCoordinatePicker.value ? selectedRunnerId.value : undefined,
      element_id: step?.element_id || undefined
    })
    if (response.data?.mode === 'local' && response.data?.navigation_error) {
      ElMessage.warning(`本地执行器打开页面存在异常：${response.data.navigation_error}`)
    }
    scrollCoordinatePickerSessionId.value = response.data?.session_id || ''
    scrollCoordinatePickerProjectId.value = currentProjectId
    scrollCoordinatePickerMode.value = response.data?.mode || expectedMode
    scrollCoordinatePickerRunnerId.value = response.data?.runner_id ? String(response.data.runner_id) : expectedRunnerId
    scrollCoordinatePickerElementId.value = expectedElementId
    return {
      sessionId: scrollCoordinatePickerSessionId.value,
      mode: scrollCoordinatePickerMode.value,
      created: true
    }
  } finally {
    scrollCoordinatePickerStarting.value = false
  }
}

const openScrollCoordinatePickerPage = async (step) => {
  try {
    const session = await ensureScrollCoordinatePickerSession(step, { forceReopen: true })
    await refreshScrollCoordinatePickerPages(false)
    const isLocalMode = session?.mode === 'local'
    const runnerName = selectedScrollCoordinatePickerRunner.value?.name
    const executionTarget = isLocalMode
      ? (runnerName ? `访客机本地执行器“${runnerName}”上的浏览器` : '访客机本地执行器上的浏览器')
      : '服务器采集浏览器'
    ElMessage.success(`已在${executionTarget}打开网页。请先登录并切换到目标页面，在目标页面中把需要滚动的区域滚到目标位置后，再点击“开始滚动位置”或“滚动到位置”读取当前滚动值。`)
  } catch (error) {
    ElMessage.error(extractRequestErrorMessage(error, '打开坐标采集网页失败'))
  }
}

const captureScrollCoordinate = async (step, field) => {
  const isStart = field === 'start'
  const loadingRef = isStart ? scrollCoordinatePickerReadingStart : scrollCoordinatePickerReadingTarget

  try {
    const session = await ensureScrollCoordinatePickerSession(step)
    const sessionId = session?.sessionId
    if (!sessionId) {
      throw new Error('滚动坐标采集浏览器启动失败')
    }

    const selectedPageIndex = Number(scrollCoordinatePickerActivePageIndex.value ?? 0)
    await refreshScrollCoordinatePickerPages(false)
    await switchScrollCoordinatePickerPage(selectedPageIndex, false)
    const isLocalMode = session.mode === 'local'
    const targetTypeLabel = step?.element_id ? '所选滚动容器' : '整个页面'
    const executionTarget = isLocalMode
      ? (selectedScrollCoordinatePickerRunner.value
          ? `访客机本地执行器“${selectedScrollCoordinatePickerRunner.value.name}”上的浏览器`
          : '访客机本地执行器上的浏览器')
      : '服务器采集浏览器'

    if (session.created) {
      ElMessage.info(
        isLocalMode
          ? `已在${executionTarget}打开坐标采集页面，请先把${targetTypeLabel}滚动到目标位置，再回到当前页面读取当前滚动值。`
          : `已打开服务器采集浏览器，请先把${targetTypeLabel}滚动到目标位置，再回到当前页面读取当前滚动值。`
      )
    }

    loadingRef.value = true
    ElMessage.info(isStart
      ? `请先在${executionTarget}中把${targetTypeLabel}滚动到开始位置，当前将读取真实滚动值。`
      : `请先在${executionTarget}中把${targetTypeLabel}滚动到目标位置，当前将读取真实滚动值。`
    )
    const captureResponse = await getScrollCoordinatePickerPosition({ session_id: sessionId, field })
    const captureX = Number(captureResponse.data?.x ?? 0)
    const captureY = Number(captureResponse.data?.y ?? 0)

    if (!step.scroll_direction) {
      step.scroll_direction = 'vertical'
    }

    if (isStart) {
      step.scroll_start_x = captureX
      step.scroll_start_y = captureY
    } else {
      step.scroll_target_x = captureX
      step.scroll_target_y = captureY
    }

    ElMessage.success(buildScrollCaptureSuccessMessage(captureResponse.data, step, isStart))
    return
  } catch (error) {
    if (error === 'cancel') {
      return
    }

    const message = extractRequestErrorMessage(
      error,
      isStart ? '获取开始滚动位置失败' : '获取目标滚动位置失败'
    )
    if (message.includes('会话不存在') || message.includes('已过期')) {
      resetScrollCoordinatePickerSession()
    }
    ElMessage.error(message)
  } finally {
    loadingRef.value = false
  }
}

const getCanvasCaptureFieldLabel = (field) => {
  const labelMap = {
    click: '点击位置',
    start: '拖拽起点',
    target: '拖拽终点'
  }
  return labelMap[field] || '画布位置'
}

const openCanvasCoordinatePickerPage = async (step) => {
  try {
    step.element_id = ''
    const session = await ensureScrollCoordinatePickerSession(step, { forceReopen: true })
    await refreshScrollCoordinatePickerPages(false)
    const isLocalMode = session?.mode === 'local'
    const runnerName = selectedScrollCoordinatePickerRunner.value?.name
    const executionTarget = isLocalMode
      ? (runnerName ? `访客机本地执行器“${runnerName}”上的浏览器` : '访客机本地执行器上的浏览器')
      : '服务器采集浏览器'
    ElMessage.success(`已在${executionTarget}打开采集页面。请先登录并打开工作流设计页，如功能会弹出新页面，请切换到新页面后在 iframe 内右键采集图形坐标。`)
  } catch (error) {
    ElMessage.error(extractRequestErrorMessage(error, '打开画布坐标采集网页失败'))
  }
}

const captureCanvasCoordinate = async (step, field) => {
  const loadingRef = field === 'target'
    ? scrollCoordinatePickerReadingTarget
    : scrollCoordinatePickerReadingStart
  const fieldLabel = getCanvasCaptureFieldLabel(field)

  try {
    step.element_id = ''
    const session = await ensureScrollCoordinatePickerSession(step)
    const sessionId = session?.sessionId
    if (!sessionId) {
      throw new Error('画布坐标采集浏览器启动失败')
    }

    const selectedPageIndex = Number(scrollCoordinatePickerActivePageIndex.value ?? 0)
    await refreshScrollCoordinatePickerPages(false)
    await switchScrollCoordinatePickerPage(selectedPageIndex, false)

    const isLocalMode = session.mode === 'local'
    const executionTarget = isLocalMode
      ? (selectedScrollCoordinatePickerRunner.value
          ? `访客机本地执行器“${selectedScrollCoordinatePickerRunner.value.name}”上的浏览器`
          : '访客机本地执行器上的浏览器')
      : '服务器采集浏览器'

    if (session.created) {
      ElMessage.info(`已在${executionTarget}打开采集页面，请进入工作流设计 iframe 所在页面后右键采集${fieldLabel}。`)
    }

    loadingRef.value = true
    ElMessage.info(`请在${executionTarget}中对准${fieldLabel}右键一次，系统会回填 iframe 内坐标。`)
    const captureResponse = await getScrollCoordinatePickerPosition({
      session_id: sessionId,
      field: `canvas_${field}`
    })
    const data = captureResponse.data || {}
    const captureX = Number(data.x ?? 0)
    const captureY = Number(data.y ?? 0)

    step.canvas_page_index = data.active_page_index ?? scrollCoordinatePickerActivePageIndex.value ?? 0
    step.canvas_frame_selector = data.frame_selector || step.canvas_frame_selector || '#plt-workflow-iframe'
    step.canvas_frame_url = data.frame_url || data.url || step.canvas_frame_url || ''

    if (field === 'click') {
      step.canvas_click_x = captureX
      step.canvas_click_y = captureY
    } else if (field === 'start') {
      step.canvas_start_x = captureX
      step.canvas_start_y = captureY
    } else {
      step.canvas_target_x = captureX
      step.canvas_target_y = captureY
    }

    await refreshScrollCoordinatePickerPages(false).catch(() => null)
    ElMessage.success(`已采集${fieldLabel}: (${captureX}, ${captureY})`)
  } catch (error) {
    if (error === 'cancel') {
      return
    }

    const message = extractRequestErrorMessage(error, `采集${fieldLabel}失败`)
    if (message.includes('会话不存在') || message.includes('已过期')) {
      resetScrollCoordinatePickerSession()
    }
    ElMessage.error(message)
  } finally {
    loadingRef.value = false
  }
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

  const currentProjectId = String(projectId.value)
  try {
    const response = await getElementGroupTree({ project: currentProjectId })
    if (String(projectId.value) !== currentProjectId) {
      return
    }
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

const applySavedTestCaseToState = (savedCase) => {
  if (!savedCase?.id) {
    return
  }

  const caseIndex = testCases.value.findIndex(item => item.id === savedCase.id)
  if (caseIndex !== -1) {
    testCases.value.splice(caseIndex, 1, savedCase)
  } else {
    testCases.value.unshift(savedCase)
  }

  if (selectedTestCase.value?.id === savedCase.id) {
    selectedTestCase.value = savedCase
    const previousSelectedStepId = selectedStepId.value
    const previousCheckedStepIds = [...checkedStepIds.value]
    currentSteps.value = (savedCase.steps || []).map(step =>
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

const loadElementsForCurrentProject = async ({ clearBeforeLoad = true } = {}) => {
  if (!projectId.value) {
    availableElements.value = []
    return
  }

  const currentProjectId = String(projectId.value)
  if (clearBeforeLoad) {
    availableElements.value = []
  }

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
    if (clearBeforeLoad) {
      availableElements.value = []
    }
  }
}

const refreshElementCatalogForCurrentProject = async ({ clearBeforeLoad = true } = {}) => {
  if (!projectId.value) {
    elementGroups.value = []
    availableElements.value = []
    return
  }

  const currentProjectId = String(projectId.value)
  if (clearBeforeLoad) {
    elementGroups.value = []
    availableElements.value = []
  }

  await Promise.all([
    loadElementGroups(),
    loadElementsForCurrentProject({ clearBeforeLoad: false })
  ])

  if (String(projectId.value) !== currentProjectId) {
    return
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
    refreshElementCatalogForCurrentProject()
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

const openFolderDialog = async () => {
  folderForm.name = ''
  await loadTestCaseFolders()
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
    await createTestCaseFolder({
      project: projectId.value,
      name: folderForm.name.trim()
    })
    await loadTestCaseFolders()
    showFolderDialog.value = false
    folderForm.name = ''
    ElMessage.success(text.folderCreateSuccess)
  } catch (error) {
    console.error('创建用例文件夹失败:', error)
    ElMessage.error(extractRequestErrorMessage(error, text.folderCreateFailed))
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
    await Promise.all([
      loadTestCases(),
      loadTestCaseFolders()
    ])
    selectedCaseIds.value = selectedCaseIds.value.filter(id => testCases.value.some(item => item.id === id))
  } catch (error) {
    console.error('移动用例失败:', error)
    ElMessage.error(extractRequestErrorMessage(error, text.moveFailed))
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
      refreshElementCatalogForCurrentProject()
    ])
  } catch (error) {
    console.error('导入测试用例失败:', error)
    ElMessage.error(extractRequestErrorMessage(error, '测试用例导入失败'))
  } finally {
    importing.value = false
  }
}

const resetAiGenerateState = () => {
  aiGenerateForm.text = ''
  aiGenerateForm.model_config_id = null
  aiGenerateForm.skill_id = null
  aiGenerateForm.folder_id = null
  aiGenerateForm.overwrite = false
  aiGenerateForm.use_ai = true
  aiGenerateTab.value = 'source'
  aiSourceFile.value = null
  aiSourceFileInfo.value = null
  aiGeneratedRecordId.value = null
  aiGeneratedManifest.value = null
  aiGeneratedCases.value = []
  aiGenerateWarnings.value = []
  aiGenerationMode.value = ''
  aiSkillRoute.value = null
  aiSkillOptimizeInstruction.value = ''
  aiSkillPreview.value = ''
  aiSourceUploadRef.value?.clearFiles?.()
}

const normalizeApiList = (data) => {
  return data?.results || data || []
}

const normalizeAiModelConfigs = (responses) => {
  const modelMap = new Map()
  responses.forEach((response) => {
    normalizeApiList(response?.data).forEach((model) => {
      if (model?.id) {
        modelMap.set(model.id, model)
      }
    })
  })
  return Array.from(modelMap.values()).sort((a, b) => {
    if (a.is_active !== b.is_active) return a.is_active ? -1 : 1
    return new Date(b.updated_at || b.created_at || 0) - new Date(a.updated_at || a.created_at || 0)
  })
}

const normalizeAiSkills = (skills) => {
  const skillMap = new Map()
  ;(skills || []).forEach((skill) => {
    if (skill?.id) {
      skillMap.set(skill.id, skill)
    }
  })
  return Array.from(skillMap.values()).sort((a, b) => {
    if (a.is_default !== b.is_default) return a.is_default ? -1 : 1
    return new Date(b.updated_at || b.created_at || 0) - new Date(a.updated_at || a.created_at || 0)
  })
}

const normalizeSkillTextList = (value) => {
  if (Array.isArray(value)) return value.filter(Boolean).join(',')
  return String(value || '')
}

const parseSkillTextList = (value) => {
  return String(value || '')
    .split(/[,，;；\n]/)
    .map(item => item.trim())
    .filter(Boolean)
}

const loadAiSkillModules = async () => {
  aiSkillModulesLoading.value = true
  try {
    const response = await getAITestCaseGenerationSkillModules()
    aiSkillModules.value = normalizeApiList(response.data)
  } catch (error) {
    console.warn('加载模块化 Skill 失败:', error)
    ElMessage.error(extractRequestErrorMessage(error, '加载模块化 Skill 失败'))
  } finally {
    aiSkillModulesLoading.value = false
  }
}

const ensureBuiltinAiSkillModules = async () => {
  aiSkillModulesLoading.value = true
  try {
    await ensureBuiltinAITestCaseGenerationSkillModules()
    const response = await getAITestCaseGenerationSkillModules()
    aiSkillModules.value = normalizeApiList(response.data)
    ElMessage.success('内置 Skill 模块已初始化')
  } catch (error) {
    console.error('初始化内置 Skill 模块失败:', error)
    ElMessage.error(extractRequestErrorMessage(error, '初始化内置 Skill 模块失败'))
  } finally {
    aiSkillModulesLoading.value = false
  }
}

const resetAiSkillModuleForm = () => {
  Object.assign(aiSkillModuleForm, {
    id: null,
    name: '',
    code: '',
    module_type: 'business_flow',
    summary: '',
    content: '',
    keywordsText: '',
    intentsText: '',
    pagesText: '',
    priority: 100,
    is_active: true
  })
}

const openAiSkillModuleDialog = (module = null) => {
  resetAiSkillModuleForm()
  if (module) {
    Object.assign(aiSkillModuleForm, {
      id: module.id,
      name: module.name || '',
      code: module.code || '',
      module_type: module.module_type || 'business_flow',
      summary: module.summary || '',
      content: module.content || '',
      keywordsText: normalizeSkillTextList(module.keywords),
      intentsText: normalizeSkillTextList(module.intents),
      pagesText: normalizeSkillTextList(module.pages),
      priority: module.priority ?? 100,
      is_active: module.is_active !== false
    })
  }
  showAiSkillModuleDialog.value = true
}

const buildAiSkillModulePayload = (contentOverride = aiSkillModuleForm.content) => ({
  name: aiSkillModuleForm.name.trim(),
  code: aiSkillModuleForm.code.trim(),
  module_type: aiSkillModuleForm.module_type,
  summary: aiSkillModuleForm.summary,
  description: aiSkillModuleForm.summary,
  content: contentOverride,
  keywords: parseSkillTextList(aiSkillModuleForm.keywordsText),
  intents: parseSkillTextList(aiSkillModuleForm.intentsText),
  pages: parseSkillTextList(aiSkillModuleForm.pagesText),
  priority: aiSkillModuleForm.priority,
  is_active: aiSkillModuleForm.is_active
})

const generateAiSkillModuleContentPreview = async ({ silent = false } = {}) => {
  if (!aiSkillModuleForm.summary.trim()) {
    ElMessage.warning('请先在摘要中输入模块规则')
    return ''
  }

  aiSkillModuleGenerating.value = true
  try {
    const response = await generateAITestCaseGenerationSkillModuleContent(buildAiSkillModulePayload(''))
    const generatedContent = response.data?.content || ''
    aiSkillModuleForm.content = generatedContent
    if (!silent) {
      ElMessage.success('系统提示词已生成')
    }
    return generatedContent
  } catch (error) {
    console.error('生成 Skill 模块提示词失败:', error)
    ElMessage.error(extractRequestErrorMessage(error, '生成 Skill 模块提示词失败'))
    return ''
  } finally {
    aiSkillModuleGenerating.value = false
  }
}

const saveAiSkillModule = async () => {
  if (!aiSkillModuleForm.name.trim() || !aiSkillModuleForm.code.trim() || !aiSkillModuleForm.content.trim()) {
    ElMessage.warning('请填写模块名称、编码和内容')
    return
  }
  aiSkillModuleSaving.value = true
  const payload = {
    name: aiSkillModuleForm.name.trim(),
    code: aiSkillModuleForm.code.trim(),
    module_type: aiSkillModuleForm.module_type,
    summary: aiSkillModuleForm.summary,
    description: aiSkillModuleForm.summary,
    content: aiSkillModuleForm.content,
    keywords: parseSkillTextList(aiSkillModuleForm.keywordsText),
    intents: parseSkillTextList(aiSkillModuleForm.intentsText),
    pages: parseSkillTextList(aiSkillModuleForm.pagesText),
    priority: aiSkillModuleForm.priority,
    is_active: aiSkillModuleForm.is_active
  }
  try {
    if (aiSkillModuleForm.id) {
      await updateAITestCaseGenerationSkillModule(aiSkillModuleForm.id, payload)
    } else {
      await createAITestCaseGenerationSkillModule(payload)
    }
    showAiSkillModuleDialog.value = false
    await loadAiSkillModules()
    ElMessage.success('Skill 模块已保存')
  } catch (error) {
    console.error('保存 Skill 模块失败:', error)
    ElMessage.error(extractRequestErrorMessage(error, '保存 Skill 模块失败'))
  } finally {
    aiSkillModuleSaving.value = false
  }
}

const submitAiSkillModule = async () => {
  if (!aiSkillModuleForm.name.trim() || !aiSkillModuleForm.code.trim()) {
    ElMessage.warning('请填写模块名称和编码')
    return
  }

  let content = aiSkillModuleForm.content.trim()
  if (!content) {
    if (!aiSkillModuleForm.summary.trim()) {
      ElMessage.warning('请填写摘要，或先生成模块提示词')
      return
    }
    content = await generateAiSkillModuleContentPreview({ silent: true })
    if (!content.trim()) {
      return
    }
  }

  aiSkillModuleSaving.value = true
  const payload = buildAiSkillModulePayload(content)
  try {
    if (aiSkillModuleForm.id) {
      await updateAITestCaseGenerationSkillModule(aiSkillModuleForm.id, payload)
    } else {
      await createAITestCaseGenerationSkillModule(payload)
    }
    showAiSkillModuleDialog.value = false
    await loadAiSkillModules()
    ElMessage.success('Skill 模块已保存')
  } catch (error) {
    console.error('保存 Skill 模块失败:', error)
    ElMessage.error(extractRequestErrorMessage(error, '保存 Skill 模块失败'))
  } finally {
    aiSkillModuleSaving.value = false
  }
}

const deleteAiSkillModule = async (module) => {
  if (!module?.id) return

  const moduleName = module.name || module.code || '该 Skill 模块'
  try {
    await ElMessageBox.confirm(
      `确认删除 Skill 模块“${moduleName}”吗？删除后不会再参与 AI 生成命中。`,
      '删除 Skill 模块',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--danger'
      }
    )
  } catch {
    return
  }

  aiSkillModulesLoading.value = true
  try {
    await deleteAITestCaseGenerationSkillModule(module.id)
    await loadAiSkillModules()
    ElMessage.success('Skill 模块已删除')
  } catch (error) {
    console.error('删除 Skill 模块失败:', error)
    ElMessage.error(extractRequestErrorMessage(error, '删除 Skill 模块失败'))
  } finally {
    aiSkillModulesLoading.value = false
  }
}

const loadAiGenerateOptions = async () => {
  const defaultSkillResponse = await ensureDefaultAITestCaseGenerationSkill()
  const ensuredDefaultSkill = defaultSkillResponse.data

  aiSkills.value = normalizeAiSkills([ensuredDefaultSkill])
  aiGenerateForm.skill_id = ensuredDefaultSkill.id
  aiSkillPreview.value = ensuredDefaultSkill.content || ''

  const [skillsResult, generalModelsResult, uiAutomationModelsResult, skillModulesResult] = await Promise.allSettled([
    getAITestCaseGenerationSkills(),
    getAIModelConfigs({ is_active: true }),
    getUiAutomationAIModelConfigs(),
    getAITestCaseGenerationSkillModules()
  ])

  if (skillsResult.status === 'fulfilled') {
    aiSkills.value = normalizeAiSkills([
      ensuredDefaultSkill,
      ...normalizeApiList(skillsResult.value.data)
    ])
  } else {
    console.warn('加载AI生成Skill列表失败:', skillsResult.reason)
  }

  const modelResponses = [generalModelsResult, uiAutomationModelsResult]
    .filter(result => result.status === 'fulfilled')
    .map(result => result.value)

  aiModelConfigs.value = normalizeAiModelConfigs(modelResponses)
    .filter(model => model?.is_active !== false)

  if (generalModelsResult.status === 'rejected') {
    console.warn('加载通用AI模型配置失败:', generalModelsResult.reason)
  }
  if (uiAutomationModelsResult.status === 'rejected') {
    console.warn('加载UI自动化AI模型配置失败:', uiAutomationModelsResult.reason)
  }
  if (skillModulesResult.status === 'fulfilled') {
    aiSkillModules.value = normalizeApiList(skillModulesResult.value.data)
  } else {
    console.warn('加载模块化 Skill 失败:', skillModulesResult.reason)
  }

  const defaultSkill = aiSkills.value.find(item => item.id === ensuredDefaultSkill.id)
    || aiSkills.value.find(item => item.is_default)
    || aiSkills.value[0]
  if (defaultSkill) {
    aiGenerateForm.skill_id = defaultSkill.id
    aiSkillPreview.value = defaultSkill.content || ''
  }

  const activeModel = aiModelConfigs.value.find(item => item.is_active) || aiModelConfigs.value[0]
  if (activeModel) {
    aiGenerateForm.model_config_id = activeModel.id
  }
}

const openAiGenerateDialog = async () => {
  if (!projectId.value) {
    ElMessage.warning(t('uiAutomation.project.selectProject'))
    return
  }
  resetAiGenerateState()
  showAiGenerateDialog.value = true
  try {
    await loadAiGenerateOptions()
  } catch (error) {
    console.error('加载AI生成配置失败:', error)
    ElMessage.error(extractRequestErrorMessage(error, '加载AI生成配置失败'))
  }
}

const formatFileSize = (size) => {
  if (!size) return '0 KB'
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(2)} MB`
}

const handleAiSourceFileChange = (file) => {
  const raw = file.raw
  const extension = `.${(raw?.name || '').split('.').pop()?.toLowerCase() || ''}`
  const allowed = ['.txt', '.md', '.json', '.csv', '.xlsx', '.xmind']

  if (!allowed.includes(extension)) {
    ElMessage.warning(aiText.unsupportedFile)
    aiSourceUploadRef.value?.clearFiles?.()
    aiSourceFile.value = null
    aiSourceFileInfo.value = null
    return false
  }

  if (raw?.size > 10 * 1024 * 1024) {
    ElMessage.warning(aiText.fileTooLarge)
    aiSourceUploadRef.value?.clearFiles?.()
    aiSourceFile.value = null
    aiSourceFileInfo.value = null
    return false
  }

  aiSourceFile.value = raw
  aiSourceFileInfo.value = {
    name: raw.name,
    extension,
    sizeText: formatFileSize(raw.size)
  }
  return true
}

const handleAiSourceFileRemove = () => {
  aiSourceFile.value = null
  aiSourceFileInfo.value = null
}

const downloadAiCaseTemplate = async () => {
  aiTemplateDownloading.value = true
  try {
    const response = await downloadAITestCaseTemplate()
    const blob = new Blob([response.data], {
      type: response.headers['content-type'] || 'text/csv;charset=utf-8'
    })
    const filename = getDownloadFilename(response.headers['content-disposition'], 'ai-ui-test-case-template.csv')
    downloadBlob(blob, filename)
  } catch (error) {
    console.error('下载AI用例模板失败:', error)
    ElMessage.error(aiText.templateDownloadFailed)
  } finally {
    aiTemplateDownloading.value = false
  }
}

const submitAiGenerateCases = async () => {
  if (!projectId.value) {
    ElMessage.warning(t('uiAutomation.project.selectProject'))
    return
  }
  if (!aiGenerateForm.text.trim() && !aiSourceFile.value) {
    ElMessage.warning(aiText.needInput)
    return
  }

  aiGenerating.value = true
  try {
    const formData = new FormData()
    formData.append('project', projectId.value)
    formData.append('text', aiGenerateForm.text)
    formData.append('use_ai', aiGenerateForm.use_ai ? '1' : '0')
    if (aiGenerateForm.model_config_id) formData.append('model_config_id', aiGenerateForm.model_config_id)
    if (aiGenerateForm.skill_id) formData.append('skill_id', aiGenerateForm.skill_id)
    if (aiSourceFile.value) formData.append('file', aiSourceFile.value)

    const response = await generateAITestCases(formData)
    const data = response.data || {}
    const record = data.record || {}
    const manifest = data.manifest || record.manifest || {}
    aiGeneratedRecordId.value = record.id
    aiGeneratedManifest.value = manifest
    aiGeneratedCases.value = manifest.test_cases || []
    aiGenerateWarnings.value = data.warnings || record.warnings || []
    aiGenerationMode.value = data.generation_mode || ''
    aiSkillRoute.value = data.skill_route || null
    ElMessage.success(aiText.generateSuccess)
  } catch (error) {
    console.error('AI生成用例失败:', error)
    ElMessage.error(extractRequestErrorMessage(error, 'AI生成用例失败'))
  } finally {
    aiGenerating.value = false
  }
}

const submitImportGeneratedCases = async () => {
  if (!aiGeneratedRecordId.value) return
  aiImporting.value = true
  try {
    const response = await importGeneratedAITestCases(aiGeneratedRecordId.value, {
      overwrite: aiGenerateForm.overwrite ? '1' : '0',
      folder_id: aiGenerateForm.folder_id
    })
    const summary = response.data?.summary || {}
    ElMessage.success(`${aiText.importSuccess}，新增 ${summary.created || 0} 个，更新 ${summary.updated || 0} 个`)
    showAiGenerateDialog.value = false
    await Promise.all([
      loadTestCaseFolders(),
      loadTestCases(),
      refreshElementCatalogForCurrentProject()
    ])
  } catch (error) {
    console.error('导入AI生成用例失败:', error)
    ElMessage.error(extractRequestErrorMessage(error, '导入AI生成用例失败'))
  } finally {
    aiImporting.value = false
  }
}

const optimizeAiSkill = async (saveMode = 'preview') => {
  if (!aiSkillOptimizeInstruction.value.trim()) {
    ElMessage.warning('请输入Skill优化要求')
    return
  }
  aiSkillOptimizing.value = true
  try {
    const currentSkill = aiSkills.value.find(item => item.id === aiGenerateForm.skill_id)
    const response = await optimizeAITestCaseGenerationSkill({
      skill_id: aiGenerateForm.skill_id,
      model_config_id: aiGenerateForm.model_config_id,
      current_skill: currentSkill?.content || aiSkillPreview.value,
      instruction: aiSkillOptimizeInstruction.value,
      save_mode: saveMode
    })
    aiSkillPreview.value = response.data?.content || ''
    if (response.data?.skill) {
      const index = aiSkills.value.findIndex(item => item.id === response.data.skill.id)
      if (index >= 0) {
        aiSkills.value[index] = response.data.skill
      } else {
        aiSkills.value.push(response.data.skill)
      }
      aiGenerateForm.skill_id = response.data.skill.id
    }
    ElMessage.success(saveMode === 'update' ? 'Skill已更新' : 'Skill优化预览已生成')
  } catch (error) {
    console.error('优化Skill失败:', error)
    ElMessage.error(extractRequestErrorMessage(error, '优化Skill失败'))
  } finally {
    aiSkillOptimizing.value = false
  }
}

const saveAiSkillPreview = async () => {
  if (!aiGenerateForm.skill_id) {
    ElMessage.warning('请先选择Skill')
    return
  }
  if (!aiSkillPreview.value.trim()) {
    ElMessage.warning('请输入要保存的Skill内容')
    return
  }

  aiSkillSaving.value = true
  try {
    const currentSkill = aiSkills.value.find(item => item.id === aiGenerateForm.skill_id)
    const response = await updateAITestCaseGenerationSkill(aiGenerateForm.skill_id, {
      name: currentSkill?.name,
      description: currentSkill?.description || '',
      content: aiSkillPreview.value,
      is_default: currentSkill?.is_default ?? false,
      is_active: currentSkill?.is_active ?? true
    })
    const savedSkill = response.data
    const index = aiSkills.value.findIndex(item => item.id === savedSkill.id)
    if (index >= 0) {
      aiSkills.value[index] = savedSkill
    } else {
      aiSkills.value.push(savedSkill)
    }
    aiGenerateForm.skill_id = savedSkill.id
    aiSkillPreview.value = savedSkill.content || ''
    ElMessage.success('Skill已保存')
  } catch (error) {
    console.error('保存Skill失败:', error)
    ElMessage.error(extractRequestErrorMessage(error, '保存Skill失败'))
  } finally {
    aiSkillSaving.value = false
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

const clearSelectedTestCaseState = () => {
  selectedTestCase.value = null
  currentSteps.value = []
  selectedStepId.value = null
  checkedStepIds.value = []
  transactionCollapseState.value = {}
  executionResult.value = null
}

const removeTestCaseFromState = (testCaseId) => {
  const index = testCases.value.findIndex(tc => tc.id === testCaseId)
  if (index !== -1) {
    testCases.value.splice(index, 1)
  }

  selectedCaseIds.value = selectedCaseIds.value.filter(id => id !== testCaseId)
  if (selectedTestCase.value?.id === testCaseId) {
    clearSelectedTestCaseState()
  }
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
  collapseAllTransactionBlocks()
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
    if (hasTransaction(selectedStep)) {
      newStep.transaction_id = selectedStep.transaction_id
      newStep.transaction_name = selectedStep.transaction_name
      newStep.transaction_disabled = selectedStep.transaction_disabled === true
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
        movedStep.transaction_disabled = false
      }
    }
  }

  normalizeTransactionBlocks()
  console.log('步骤已重新排序')
}

const onActionTypeChange = (step) => {
  // 根据操作类型重置相关参数
  if (isCanvasAction(step.action_type)) {
    step.element_id = ''
    step.element_locator_strategy = ''
    step.element_locator_value = ''
    step.canvas_frame_selector = step.canvas_frame_selector || '#plt-workflow-iframe'
    step.canvas_hold_ms = Number(step.canvas_hold_ms ?? 300) || 300
    step.canvas_steps = Number(step.canvas_steps ?? 30) || 30
  }
  if (!needsInputValue(step.action_type)) {
    step.input_value = ''
  }
  if (step.action_type !== 'drag') {
    step.drag_target_element_id = ''
  }
  if (!needsElement(step.action_type)) {
    step.element_id = ''
    step.element_locator_strategy = ''
    step.element_locator_value = ''
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
  if (step.action_type !== 'scroll') {
    step.scroll_direction = ''
    step.scroll_start_x = null
    step.scroll_start_y = null
    step.scroll_target_x = null
    step.scroll_target_y = null
  }
  if (!isCanvasAction(step.action_type)) {
    step.canvas_frame_selector = '#plt-workflow-iframe'
    step.canvas_frame_url = ''
    step.canvas_page_index = null
    step.canvas_click_x = null
    step.canvas_click_y = null
    step.canvas_start_x = null
    step.canvas_start_y = null
    step.canvas_target_x = null
    step.canvas_target_y = null
    step.canvas_hold_ms = 300
    step.canvas_steps = 30
  }
}

const onElementChange = (step) => {
  // 元素变化时的处理
  const element = availableElements.value.find(e => e.id === step.element_id)
  if (element) {
    step.element_locator_strategy = getElementLocatorStrategy(element)
    step.element_locator_value = element.locator_value || ''
  }
  if (element && !step.description) {
    step.description = `${getActionTypeText(step.action_type)}${element.name}`
  }
}

const getElementLocatorStrategy = (element) => {
  return element?.locator_strategy?.name || element?.locator_strategy || 'css'
}

const getSelectedElementLocatorPlaceholder = (step) => {
  const element = availableElements.value.find(item => item.id === step?.element_id)
  return element?.locator_value || '选择元素后可手动修改定位表达式'
}

const getSelectedElementLabel = (elementId) => {
  const element = availableElements.value.find(item => item.id === elementId)
  if (!element) {
    return t('uiAutomation.testCase.elementPending')
  }

  return `${element.name} (${element.locator_value})`
}

const openElementSelector = async (step, field = 'element_id') => {
  currentSelectingStep.value = step
  currentSelectingField.value = field
  elementSelectorKeyword.value = ''
  showElementSelectorDialog.value = true

  if (!projectId.value) {
    return
  }

  elementSelectorLoading.value = true
  try {
    await refreshElementCatalogForCurrentProject({ clearBeforeLoad: false })
  } finally {
    elementSelectorLoading.value = false
  }
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

const isCanvasAction = (actionType) => {
  return ['canvasClick', 'canvasDrag'].includes(actionType)
}

const needsElement = (actionType) => {
  return !['wait', 'switchTab', 'screenshot', 'refreshCurrentPage', 'closeCurrentPage', 'canvasClick', 'canvasDrag'].includes(actionType)
}

const submitImportCaseSteps = () => {
  const sourceCase = testCases.value.find(item => String(item.id) === String(importCaseStepsForm.source_case_id))
  if (!sourceCase) {
    ElMessage.warning('\u8bf7\u9009\u62e9\u8981\u5bfc\u5165\u7684\u7528\u4f8b')
    return
  }

  const importedSteps = cloneImportedSteps(sourceCase.steps || [])
  if (!importedSteps.length) {
    ElMessage.warning('\u6240\u9009\u7528\u4f8b\u6ca1\u6709\u53ef\u5bfc\u5165\u7684\u6b65\u9aa4')
    return
  }

  if (needsImportTargetStep.value && !importCaseStepsForm.target_step_id) {
    ElMessage.warning('\u8bf7\u9009\u62e9\u76ee\u6807\u6b65\u9aa4')
    return
  }

  const insertIndex = getImportInsertIndex()
  if (insertIndex < 0) {
    ElMessage.warning('\u76ee\u6807\u6b65\u9aa4\u4e0d\u5b58\u5728\uff0c\u8bf7\u91cd\u65b0\u9009\u62e9')
    return
  }

  currentSteps.value.splice(insertIndex, 0, ...importedSteps)
  selectedStepId.value = importedSteps[0]?.id ?? null
  checkedStepIds.value = importedSteps.map(step => step.id)
  normalizeTransactionBlocks()
  allStepsExpanded.value = false
  showImportCaseStepsDialog.value = false

  ElMessage.success(`\u5df2\u5bfc\u5165 ${importedSteps.length} \u4e2a\u6b65\u9aa4\uff0c\u8bf7\u4fdd\u5b58\u7528\u4f8b`)
}

const expandAllSteps = () => {
  allStepsExpanded.value = !allStepsExpanded.value
  currentSteps.value.forEach(step => {
    step.expanded = allStepsExpanded.value
  })
}

const persistSelectedTestCase = async ({ showSuccess = true } = {}) => {
  if (!selectedTestCase.value) return
  normalizeTransactionBlocks()
  if (!validateCurrentSteps()) return

  try {
    const updateData = {
      ...selectedTestCase.value,
      steps: currentSteps.value.map(buildStepPayload)
    }

    const updateResponse = await updateTestCase(selectedTestCase.value.id, updateData)
    const detailResponse = await getTestCaseDetail(selectedTestCase.value.id).catch(() => null)
    const savedCase = detailResponse?.data || updateResponse?.data || updateData
    if (showSuccess) {
      ElMessage.success(t('uiAutomation.testCase.save.success'))
    }

    applySavedTestCaseToState(savedCase)
    return savedCase
  } catch (error) {
      console.error('保存测试用例失败:', error)
      ElMessage.error(extractRequestErrorMessage(error, t('uiAutomation.testCase.save.failed')))
    }
}

const saveTestCase = async () => {
  await persistSelectedTestCase()
}

const runTestCase = async (testCase) => {
  isRunning.value = true
  try {
    let executableCase = testCase
    if (selectedTestCase.value?.id === testCase?.id) {
      executableCase = await persistSelectedTestCase({ showSuccess: false })
      if (!executableCase) {
        return
      }
    }

    if (executionMode.value === 'local' && !selectedRunnerId.value) {
      ElMessage.warning('请先选择本地执行器')
      return
    }

    const modeText = headlessMode.value ? t('uiAutomation.testCase.runMode.headless') : t('uiAutomation.testCase.runMode.headed')
    ElMessage.info(t('uiAutomation.testCase.run.start', { engine: selectedEngine.value.toUpperCase(), browser: selectedBrowser.value.toUpperCase(), mode: modeText }))

    const response = await runTestCaseApi(executableCase.id, {
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
    removeTestCaseFromState(testCase.id)
    await loadTestCaseFolders()
    return

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

const handleBatchDelete = async () => {
  if (!selectedCaseIds.value.length) {
    ElMessage.warning(text.moveCasesEmpty)
    return
  }

  try {
    await ElMessageBox.confirm(
      text.batchDeleteConfirm.replace('{count}', selectedCaseIds.value.length),
      text.batchDeleteTitle,
      {
        confirmButtonText: t('uiAutomation.common.confirm'),
        cancelButtonText: t('uiAutomation.common.cancel'),
        type: 'warning'
      }
    )

    await batchDeleteTestCases({ ids: selectedCaseIds.value })
    selectedCaseIds.value = []
    clearSelectedTestCaseState()
    await Promise.all([
      loadTestCases(),
      loadTestCaseFolders()
    ])
    ElMessage.success(text.batchDeleteSuccess)
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      console.error('鎵归噺鍒犻櫎娴嬭瘯鐢ㄤ緥澶辫触:', error)
      ElMessage.error(extractRequestErrorMessage(error, text.batchDeleteFailed))
    }
  }
}

const deleteFolder = async (folder) => {
  try {
    await ElMessageBox.confirm(
      text.folderDeleteConfirm.replace('{name}', folder.name),
      text.folderDeleteTitle,
      {
        confirmButtonText: t('uiAutomation.common.confirm'),
        cancelButtonText: t('uiAutomation.common.cancel'),
        type: 'warning'
      }
    )

    folderDeletingId.value = folder.id
    await deleteTestCaseFolder(folder.id)

    if (folderFilter.value === String(folder.id)) {
      folderFilter.value = 'all'
    }
    if (testCaseForm.folder_id === folder.id) {
      testCaseForm.folder_id = null
    }
    if (moveForm.folder_id === folder.id) {
      moveForm.folder_id = null
    }
    if (aiGenerateForm.folder_id === folder.id) {
      aiGenerateForm.folder_id = null
    }

    await Promise.all([
      loadTestCases(),
      loadTestCaseFolders()
    ])
    ElMessage.success(text.folderDeleteSuccess)
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      console.error('鍒犻櫎鏂囦欢澶瑰け璐?', error)
      ElMessage.error(extractRequestErrorMessage(error, text.folderDeleteFailed))
    }
  } finally {
    folderDeletingId.value = null
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
      project: projectId.value
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
      data.steps = []
      const response = await createTestCase(data)
      ElMessage.success(t('uiAutomation.testCase.create.success'))
      testCases.value.push(response.data)
    }

    await Promise.all([
      loadTestCases(),
      loadTestCaseFolders()
    ])
    showCreateDialog.value = false
    editingTestCase.value = null
    resetForm()
  } catch (error) {
    console.error('保存测试用例失败:', error)
    ElMessage.error(extractRequestErrorMessage(error, t('uiAutomation.testCase.save.failed')))
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
    'canvasClick': '画布点击',
    'canvasDrag': '画布拖拽',
    'screenshot': t('uiAutomation.testCase.actionType.screenshot'),
    'assert': t('uiAutomation.testCase.actionType.assert'),
    'wait': t('uiAutomation.testCase.actionType.wait'),
    'switchTab': t('uiAutomation.testCase.actionSwitchTab'),
    'refreshCurrentPage': '刷新当前页',
    'closeCurrentPage': t('uiAutomation.testCase.actionCloseCurrentPage')
  }
  return textMap[actionType] || actionType
}

const getExecutionLogStatus = (step) => {
  if (step?.status) {
    return step.status
  }
  return step?.success ? 'passed' : 'failed'
}

const getExecutionLogTagType = (step) => {
  const status = getExecutionLogStatus(step)
  if (status === 'skipped') {
    return 'info'
  }
  return status === 'passed' ? 'success' : 'danger'
}

const getExecutionLogStatusText = (step) => {
  const status = getExecutionLogStatus(step)
  if (status === 'skipped') {
    return text.logSkipped
  }
  return status === 'passed' ? text.logPassed : text.logFailed
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
    'canvasClick': '画布点击',
    'canvasDrag': '画布拖拽',
    'screenshot': t('uiAutomation.testCase.actionText.screenshot'),
    'assert': t('uiAutomation.testCase.actionText.assert'),
    'wait': t('uiAutomation.testCase.actionText.wait'),
    'switchTab': t('uiAutomation.testCase.actionSwitchTab'),
    'refreshCurrentPage': '刷新当前页',
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

watch(showImportCaseStepsDialog, (visible) => {
  if (!visible) {
    importCaseStepsForm.source_case_id = null
    importCaseStepsForm.insert_mode = 'end'
    importCaseStepsForm.target_step_id = null
  }
})

watch(() => importCaseStepsForm.insert_mode, (mode) => {
  if (!['before', 'after'].includes(mode)) {
    importCaseStepsForm.target_step_id = null
    return
  }

  if (!currentSteps.value.length) {
    importCaseStepsForm.insert_mode = 'end'
    importCaseStepsForm.target_step_id = null
    return
  }

  if (!currentSteps.value.some(step => isSameStepId(step.id, importCaseStepsForm.target_step_id))) {
    importCaseStepsForm.target_step_id = currentSteps.value[0]?.id ?? null
  }
})

watch(() => aiGenerateForm.skill_id, (skillId) => {
  const skill = aiSkills.value.find(item => item.id === skillId)
  if (skill) {
    aiSkillPreview.value = skill.content || ''
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

watch([projectId, selectedBrowser, executionMode, selectedRunnerId], () => {
  closeScrollCoordinatePickerSession(true)
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
  closeScrollCoordinatePickerSession(true)
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

.transaction-block--disabled {
  border-color: #f3d19e;
  background: linear-gradient(90deg, #fff8ed 0%, #fff3df 100%);
}

.transaction-block--dragging {
  opacity: 0.55;
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
.transaction-block-icon,
.transaction-block-drag {
  color: #409eff;
}

.transaction-block-drag {
  cursor: grab;
}

.transaction-block--disabled .transaction-block-icon,
.transaction-block--disabled .transaction-block-toggle,
.transaction-block--disabled .transaction-block-drag {
  color: #e6a23c;
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

.step-item--disabled {
  border-style: dashed;
  border-color: #c0c4cc;
  background: #fcfcfc;
  opacity: 0.82;
}

.step-item--disabled .step-header {
  background: #f5f7fa;
}

.step-item--disabled .step-number {
  background: #909399;
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
  display: flex;
  align-items: center;
  gap: 8px;
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

.step-param--toggle {
  align-items: center;
}

.step-param label {
  width: 120px;
  font-weight: 500;
  color: #333;
}

.step-toggle {
  display: flex;
  align-items: center;
  gap: 10px;
}

.step-toggle-status {
  font-size: 13px;
  font-weight: 500;
}

.step-toggle-status.is-enabled {
  color: #67c23a;
}

.step-toggle-status.is-disabled {
  color: #909399;
}

.step-param-main {
  flex: 1;
  min-width: 0;
}

.step-locator-override {
  flex-basis: 100%;
}

.locator-override-row {
  display: flex;
  gap: 8px;
  width: 100%;
}

.scroll-config-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 8px;
}

.canvas-config-grid {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) minmax(110px, 140px) minmax(110px, 140px);
  gap: 8px;
}

.canvas-coordinate-summary {
  margin-top: 8px;
  color: #606266;
  font-size: 13px;
  line-height: 1.5;
}

.canvas-coordinate-arrow {
  margin: 0 8px;
  color: #909399;
}

.scroll-picker-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
  flex-wrap: wrap;
}

.scroll-picker-guide {
  margin-top: 10px;
  padding: 10px 12px;
  border-radius: 6px;
  background: #f5f7fa;
  border: 1px solid #e4e7ed;
}

.scroll-picker-guide__line {
  color: #606266;
  font-size: 12px;
  line-height: 1.6;
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

.log-step-number {
  color: #606266;
  font-size: 13px;
}

.log-action {
  font-weight: 500;
  color: #606266;
}

.log-desc {
  color: #909399;
  font-size: 14px;
}

.log-message {
  color: #909399;
  font-size: 13px;
  line-height: 1.6;
  background: #f4f4f5;
  padding: 8px 12px;
  border-radius: 4px;
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

.ai-generate-layout {
  display: grid;
  grid-template-columns: minmax(420px, 0.95fr) minmax(480px, 1.05fr);
  gap: 18px;
}

.ai-generate-config,
.ai-generate-preview {
  min-width: 0;
}

.ai-upload-field {
  width: 100%;
}

.ai-upload-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.ai-upload-tip {
  margin-top: 8px;
  color: #909399;
  font-size: 12px;
  line-height: 1.5;
}

.ai-file-info {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  color: #606266;
  font-size: 12px;
}

.ai-file-name {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ai-file-size {
  color: #909399;
}

.ai-skill-actions,
.ai-generate-actions {
  display: flex;
  gap: 10px;
  margin: 12px 0;
}

.ai-skill-router-tip {
  margin-bottom: 12px;
}

.ai-skill-module-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}

.ai-skill-module-table {
  margin-bottom: 8px;
}

.ai-skill-module-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}

.ai-skill-module-tip {
  color: #909399;
  font-size: 12px;
  line-height: 1.5;
}

.ai-preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  font-weight: 600;
}

.ai-route-summary {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
  color: #606266;
  font-size: 12px;
}

.ai-route-debug {
  margin-bottom: 12px;
  padding: 12px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  background: #fafafa;
}

.ai-route-meta,
.ai-route-tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.ai-route-meta {
  margin-bottom: 10px;
}

.ai-route-block + .ai-route-block {
  margin-top: 12px;
}

.ai-route-block-title {
  margin-bottom: 8px;
  color: #303133;
  font-size: 13px;
  font-weight: 600;
}

.ai-route-entity-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
  color: #606266;
}

.ai-route-entity-item {
  display: flex;
  gap: 8px;
  align-items: flex-start;
}

.ai-route-entity-key,
.ai-route-line-label {
  flex: 0 0 auto;
  color: #909399;
}

.ai-route-entity-value {
  word-break: break-all;
}

.ai-route-module-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ai-route-module-card {
  padding: 10px 12px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  background: white;
}

.ai-route-module-card-omitted {
  background: #fff9f5;
  border-color: #f7d7c1;
}

.ai-route-module-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 10px;
}

.ai-route-module-title {
  display: flex;
  flex-direction: column;
  gap: 4px;
  color: #303133;
  font-size: 13px;
  font-weight: 600;
}

.ai-route-module-code {
  color: #909399;
  font-size: 12px;
  font-weight: 400;
}

.ai-route-module-summary {
  margin-top: 8px;
  color: #606266;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
}

.ai-route-module-line {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  margin-top: 8px;
  font-size: 12px;
  color: #606266;
}

.ai-warning {
  margin-bottom: 12px;
}

.ai-step-preview {
  font-size: 12px;
  line-height: 1.6;
  color: #606266;
}

.folder-manage-list {
  margin-top: 8px;
  border-top: 1px solid #ebeef5;
  padding-top: 12px;
}

.folder-manage-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 240px;
  overflow-y: auto;
}

.folder-manage-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  background: #fafafa;
}

.folder-manage-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.folder-manage-name {
  color: #303133;
  font-size: 13px;
  font-weight: 600;
  word-break: break-all;
}

.folder-manage-count {
  color: #909399;
  font-size: 12px;
}

@media (max-width: 1180px) {
  .ai-generate-layout {
    grid-template-columns: 1fr;
  }

  .canvas-config-grid {
    grid-template-columns: 1fr;
  }
}
</style>
