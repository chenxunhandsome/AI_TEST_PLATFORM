<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">{{ $t('uiAutomation.execution.title') }}</h1>
      <el-select v-model="projectId" :placeholder="$t('uiAutomation.common.selectProject')" style="width: 200px; margin-right: 15px" @change="onProjectChange">
        <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
      </el-select>
    </div>

    <div class="card-container">
      <div class="filter-bar">
        <el-form :inline="true" :model="queryParams" class="demo-form-inline">
          <el-form-item :label="$t('uiAutomation.common.search')">
            <el-input
              v-model="queryParams.search"
              :placeholder="$t('uiAutomation.execution.searchPlaceholder')"
              clearable
              @keyup.enter="handleSearch"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
          </el-form-item>
          <el-form-item :label="$t('uiAutomation.common.status')">
            <el-select v-model="queryParams.status" :placeholder="$t('uiAutomation.execution.statusFilter')" clearable>
              <el-option :label="$t('uiAutomation.status.pending')" value="pending" />
              <el-option :label="$t('uiAutomation.status.running')" value="running" />
              <el-option :label="$t('uiAutomation.status.passed')" value="passed" />
              <el-option :label="$t('uiAutomation.status.failed')" value="failed" />
              <el-option :label="$t('uiAutomation.status.error')" value="error" />
            </el-select>
          </el-form-item>
          <el-form-item :label="$t('uiAutomation.execution.browserFilter')">
            <el-select v-model="queryParams.browser" :placeholder="$t('uiAutomation.execution.browserFilter')" clearable>
              <el-option label="Chrome" value="chrome" />
              <el-option label="Firefox" value="firefox" />
              <el-option label="Safari" value="safari" />
              <el-option label="Edge" value="edge" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleSearch">{{ $t('uiAutomation.common.query') }}</el-button>
            <el-button @click="resetQuery">{{ $t('uiAutomation.common.reset') }}</el-button>
            <el-button
              type="danger"
              :disabled="selectedIds.length === 0"
              @click="handleBatchDelete"
            >
              {{ $t('uiAutomation.common.batchDelete') }}
            </el-button>
            <el-button @click="openCleanupDialog">
              <el-icon><Delete /></el-icon>
              清理设置
            </el-button>
          </el-form-item>
        </el-form>
      </div>

      <el-table :data="executions" v-loading="loading" style="width: 100%" @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="55" align="center" />
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="test_case_name" :label="$t('uiAutomation.execution.caseName')" min-width="200">
          <template #default="{ row }">
            <el-link @click="viewExecutionDetail(row)" type="primary">
              {{ row.test_case_name }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column :label="$t('uiAutomation.execution.relatedObject')" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="!row.test_suite" type="info" size="small">{{ $t('uiAutomation.execution.case') }}</el-tag>
            <el-tag v-else type="warning" size="small">{{ $t('uiAutomation.execution.suiteTag') }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" :label="$t('uiAutomation.execution.statusFilter')" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">{{ getStatusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="engine" :label="$t('uiAutomation.execution.testEngine')" width="120" align="center">
          <template #default="{ row }">
            {{ getEngineText(row.engine) }}
          </template>
        </el-table-column>
        <el-table-column prop="headless" :label="$t('uiAutomation.execution.executionMode')" width="100" align="center">
          <template #default="{ row }">
            {{ row.headless ? $t('uiAutomation.execution.headlessMode') : $t('uiAutomation.execution.headedMode') }}
          </template>
        </el-table-column>
        <el-table-column prop="browser" :label="$t('uiAutomation.execution.browserFilter')" width="100" align="center">
          <template #default="{ row }">
            {{ getBrowserText(row.browser) }}
          </template>
        </el-table-column>
        <el-table-column prop="created_by_name" :label="$t('uiAutomation.execution.executor')" width="120" align="center" />
        <el-table-column prop="started_at" :label="$t('uiAutomation.execution.startTime')" width="180" align="center">
          <template #default="{ row }">
            {{ formatDateTime(row.started_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="finished_at" :label="$t('uiAutomation.execution.endTime')" width="180" align="center">
          <template #default="{ row }">
            {{ formatDateTime(row.finished_at) }}
          </template>
        </el-table-column>
        <el-table-column :label="$t('uiAutomation.execution.duration')" width="120" align="center">
          <template #default="{ row }">
            {{ formatDuration(row.execution_time) }}
          </template>
        </el-table-column>
        <el-table-column :label="$t('uiAutomation.common.operation')" width="150" fixed="right" align="center">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="viewExecutionDetail(row)">
              <el-icon><View /></el-icon>
              {{ $t('uiAutomation.common.details') }}
            </el-button>
            <el-button
              v-if="row.status === 'failed' || row.status === 'error'"
              size="small"
              type="warning"
              link
              @click="showRerunDialog(row)"
            >
              <el-icon><Refresh /></el-icon>
              {{ $t('uiAutomation.common.rerun') }}
            </el-button>
            <el-button
              link
              type="danger"
              @click="handleDelete(row)"
            >
              {{ $t('uiAutomation.common.delete') }}
            </el-button>
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

    <!-- 执行详情对话框 -->
    <el-dialog v-model="showDetailDialog" :title="$t('uiAutomation.execution.executionDetail')" width="900px">
      <div v-if="currentExecution" class="execution-detail">
        <!-- 基本信息 -->
        <el-descriptions :column="2" border>
          <el-descriptions-item :label="$t('uiAutomation.execution.caseName')">{{ currentExecution.test_case_name }}</el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.execution.statusFilter')">
            <el-tag :type="getStatusType(currentExecution.status)">{{ getStatusText(currentExecution.status) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.execution.browserFilter')">{{ getBrowserText(currentExecution.browser) }}</el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.execution.executor')">{{ currentExecution.created_by_name }}</el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.execution.startTime')">{{ formatDateTime(currentExecution.started_at) }}</el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.execution.endTime')">{{ formatDateTime(currentExecution.finished_at) }}</el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.execution.duration')" :span="2">{{ formatDuration(currentExecution.execution_time) }}</el-descriptions-item>
        </el-descriptions>

        <!-- 执行结果选项卡 -->
        <el-tabs v-model="activeTab" class="execution-tabs" style="margin-top: 20px;">
          <!-- 执行日志 - 所有状态都显示 -->
          <el-tab-pane :label="$t('uiAutomation.execution.executionLogs')" name="logs">
            <div class="logs-container">
              <div v-if="currentExecution.execution_logs">
                <div v-for="(step, index) in parseExecutionLogs(currentExecution.execution_logs)" :key="index" class="log-item">
                  <div class="log-header">
                    <el-tag :type="step.success ? 'success' : 'danger'" size="small">
                      {{ $t('uiAutomation.execution.step') }} {{ step.step_number }}
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
              <el-empty v-else :description="$t('uiAutomation.execution.noLogs')" />
            </div>
          </el-tab-pane>

          <el-tab-pane label="步骤详情" name="stepDetails">
            <el-table :data="getCurrentStepDetails()" border style="width: 100%" max-height="520">
              <el-table-column prop="step_number" label="步骤" width="70" align="center" />
              <el-table-column label="状态" width="90" align="center">
                <template #default="{ row }">
                  <el-tag :type="row.status === 'passed' || row.success ? 'success' : row.status === 'skipped' ? 'info' : 'danger'" size="small">
                    {{ row.status === 'skipped' ? '跳过' : (row.status === 'passed' || row.success ? '通过' : '失败') }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="130">
                <template #default="{ row }">{{ getActionText(row.action_type) }}</template>
              </el-table-column>
              <el-table-column label="点击内容" min-width="150">
                <template #default="{ row }">{{ row.clicked_content || '-' }}</template>
              </el-table-column>
              <el-table-column label="输入内容" min-width="150">
                <template #default="{ row }">
                  <span class="detail-value">{{ row.input_content || '-' }}</span>
                </template>
              </el-table-column>
              <el-table-column label="操作元素" min-width="180">
                <template #default="{ row }">{{ row.element?.name || '-' }}</template>
              </el-table-column>
              <el-table-column label="定位器" min-width="240">
                <template #default="{ row }">
                  <div v-if="row.locator_value" class="locator-cell">
                    <el-tag size="small" type="info">{{ row.locator_strategy || 'css' }}</el-tag>
                    <span>{{ row.locator_value }}</span>
                  </div>
                  <span v-else>-</span>
                </template>
              </el-table-column>
              <el-table-column label="说明/错误" min-width="220">
                <template #default="{ row }">
                  <div>{{ row.description || '-' }}</div>
                  <div v-if="row.error" class="step-error-text">{{ row.error }}</div>
                </template>
              </el-table-column>
            </el-table>
            <el-empty v-if="getCurrentStepDetails().length === 0" description="暂无步骤详情" />
          </el-tab-pane>

          <!-- 失败截图 - 仅失败或错误状态显示 -->
          <el-tab-pane :label="$t('uiAutomation.execution.failedScreenshots')" name="screenshots" v-if="currentExecution.status === 'failed' || currentExecution.status === 'error'">
            <div class="screenshots-container">
              <div v-if="currentExecution.screenshots && currentExecution.screenshots.length > 0">
                <div v-for="(screenshot, index) in currentExecution.screenshots" :key="index" class="screenshot-item">
                  <h5>{{ screenshot.description || `${$t('uiAutomation.execution.screenshot')} ${index + 1}` }}</h5>
                  <!-- 检查截图URL是否有效 -->
                  <div v-if="screenshot.url" class="screenshot-wrapper">
                    <img
                      :src="screenshot.url"
                      :alt="screenshot.description"
                      class="screenshot-img"
                      @error="handleImageError($event, screenshot)"
                    />
                  </div>
                  <div v-else class="screenshot-error">
                    <el-icon><WarningFilled /></el-icon>
                    <span>{{ $t('uiAutomation.execution.screenshotFailed') }}{{ screenshot.error || $t('uiAutomation.execution.unknownReason') }}</span>
                  </div>
                  <p class="screenshot-time">{{ formatDateTime(screenshot.timestamp) }}</p>
                </div>
              </div>
              <el-empty v-else :description="$t('uiAutomation.execution.noScreenshots')" />
            </div>
          </el-tab-pane>

          <!-- 错误信息 - 仅失败或错误状态显示 -->
          <el-tab-pane :label="$t('uiAutomation.execution.errorInfo')" name="error" v-if="currentExecution.status === 'failed' || currentExecution.status === 'error'">
            <div class="errors-container">
              <div v-if="currentExecution.error_message" class="error-item">
                <div class="error-content">
                  <pre class="error-text">{{ currentExecution.error_message }}</pre>
                </div>
              </div>
              <el-empty v-else :description="$t('uiAutomation.execution.noError')" />
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>
      <template #footer>
        <el-button @click="showDetailDialog = false">{{ $t('uiAutomation.common.close') }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="cleanupDialogVisible" title="执行记录定时清理" width="520px">
      <el-form :model="cleanupForm" label-width="120px">
        <el-form-item label="启用自动清理">
          <el-switch v-model="cleanupForm.enabled" />
        </el-form-item>
        <el-form-item label="保留天数">
          <el-input-number v-model="cleanupForm.retention_days" :min="1" :max="3650" :step="1" style="width: 180px" />
          <span class="cleanup-tip">自动清理早于该天数的执行记录</span>
        </el-form-item>
        <el-form-item label="最后清理时间">
          <span>{{ formatDateTime(cleanupForm.last_cleaned_at) }}</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="cleanupDialogVisible = false">取消</el-button>
        <el-button type="warning" @click="handleCleanupNow" :loading="cleanupLoading">立即清理</el-button>
        <el-button type="primary" @click="saveCleanupSetting" :loading="cleanupLoading">保存设置</el-button>
      </template>
    </el-dialog>

    <!-- 重跑测试用例对话框 -->
    <el-dialog v-model="showRerunDialogVisible" :title="$t('uiAutomation.execution.rerunTitle')" width="500px">
      <el-form :model="rerunFormData" label-width="100px">
        <el-form-item :label="$t('uiAutomation.execution.testEngine')">
          <el-radio-group v-model="rerunFormData.engine">
            <el-radio label="playwright">Playwright</el-radio>
            <el-radio label="selenium">Selenium</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item :label="$t('uiAutomation.execution.browserFilter')">
          <el-select v-model="rerunFormData.browser" style="width: 100%">
            <el-option label="Chrome" value="chrome" />
            <el-option label="Firefox" value="firefox" />
            <el-option label="Safari" value="safari" />
            <el-option label="Edge" value="edge" />
          </el-select>
        </el-form-item>
        <el-form-item :label="$t('uiAutomation.execution.executionMode')">
          <el-radio-group v-model="rerunFormData.headless">
            <el-radio :label="false">{{ $t('uiAutomation.execution.headedMode') }}</el-radio>
            <el-radio :label="true">{{ $t('uiAutomation.execution.headlessMode') }}</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="执行位置">
          <el-radio-group v-model="rerunFormData.executionMode">
            <el-radio label="server">服务器执行</el-radio>
            <el-radio label="local">本机执行</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="rerunFormData.executionMode === 'local'" label="本地执行器">
          <el-select v-model="rerunFormData.runnerId" style="width: 100%" placeholder="选择本地执行器">
            <el-option
              v-for="runner in localRunners"
              :key="runner.id"
              :label="`${runner.name}${runner.hostname ? ` (${runner.hostname})` : ''}`"
              :value="runner.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRerunDialogVisible = false">{{ $t('uiAutomation.common.cancel') }}</el-button>
        <el-button type="primary" @click="handleRerun" :loading="rerunning">{{ $t('uiAutomation.execution.confirmRerun') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, View, WarningFilled, Refresh, Delete } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import {
  getTestCaseExecutions,
  getUiProjects,
  deleteTestCaseExecution,
  batchDeleteTestCaseExecutions,
  runTestCase,
  getLocalRunners,
  getExecutionCleanupSetting,
  updateExecutionCleanupSetting,
  cleanupTestCaseExecutionsNow
} from '@/api/ui_automation'
import { useUiAutomationStore } from '@/stores/uiAutomation'

const { t } = useI18n()
const uiAutomationStore = useUiAutomationStore()

// 项目和执行数据
const projects = ref([])
const projectId = ref('')
const executions = ref([])
const loading = ref(false)
const total = ref(0)
const pagination = reactive({
  currentPage: 1,
  pageSize: 20
})

// 搜索和筛选
const queryParams = reactive({
  project: undefined,
  search: '',
  status: '',
  browser: ''
})
const selectedIds = ref([])

// 详情对话框相关
const showDetailDialog = ref(false)
const activeTab = ref('logs')
const currentExecution = ref(null)

const cleanupDialogVisible = ref(false)
const cleanupLoading = ref(false)
const cleanupForm = reactive({
  enabled: false,
  retention_days: 30,
  last_cleaned_at: null
})

// 重跑对话框相关
const showRerunDialogVisible = ref(false)
const rerunning = ref(false)
const localRunners = ref([])
const rerunFormData = reactive({
  testCaseId: null,
  engine: 'playwright',
  browser: 'chrome',
  headless: false,
  executionMode: 'server',
  runnerId: null
})

// 格式化日期时间
const formatDateTime = (dateString) => {
  if (!dateString) return '-'
  const date = new Date(dateString)
  if (isNaN(date.getTime())) return '-'
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

// 处理图片加载错误
const handleImageError = (event, screenshot) => {
  console.error('Screenshot load failed:', screenshot)
  const img = event.target
  img.style.display = 'none'
  // Show error message after image
  const errorDiv = img.parentElement.querySelector('.img-load-error')
  if (!errorDiv) {
    const div = document.createElement('div')
    div.className = 'img-load-error'
    div.innerHTML = `
      <i class="el-icon-warning"></i>
      <span>${t('uiAutomation.execution.imageLoadFailed')}</span>
    `
    img.parentElement.appendChild(div)
  }
}

// 格式化持续时间（execution_time单位是秒）
const formatDuration = (seconds) => {
  if (!seconds && seconds !== 0) return '-'

  const totalSeconds = Math.floor(seconds)
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const secs = totalSeconds % 60

  if (hours > 0) {
    return `${hours}h ${minutes}m ${secs}s`
  } else if (minutes > 0) {
    return `${minutes}m ${secs}s`
  } else {
    return `${secs}s`
  }
}

// 获取状态样式
const getStatusType = (status) => {
  const statusMap = {
    'pending': 'info',
    'running': 'warning',
    'passed': 'success',
    'failed': 'danger',
    'error': 'danger'
  }
  return statusMap[status] || 'info'
}

// 获取状态文本
const getStatusText = (status) => {
  const statusMap = {
    'pending': t('uiAutomation.status.pending'),
    'running': t('uiAutomation.status.running'),
    'passed': t('uiAutomation.status.passed'),
    'failed': t('uiAutomation.status.failed'),
    'error': t('uiAutomation.status.error')
  }
  return statusMap[status] || status
}

// 获取浏览器文本
const getBrowserText = (browser) => {
  const browserMap = {
    'chrome': 'Chrome',
    'firefox': 'Firefox',
    'safari': 'Safari',
    'edge': 'Edge'
  }
  return browserMap[browser] || browser || 'Chrome'
}

// 获取测试引擎文本
const getEngineText = (engine) => {
  const engineMap = {
    'playwright': 'Playwright',
    'selenium': 'Selenium'
  }
  return engineMap[engine] || engine || 'Playwright'
}

// 获取操作类型文本
const getActionText = (actionType) => {
  const actionMap = {
    'click': t('uiAutomation.actionTypes.click'),
    'fill': t('uiAutomation.actionTypes.fill'),
    'fillAndEnter': t('uiAutomation.actionTypes.fillAndEnter'),
    'getText': t('uiAutomation.actionTypes.getText'),
    'waitFor': t('uiAutomation.actionTypes.waitFor'),
    'hover': t('uiAutomation.actionTypes.hover'),
    'scroll': t('uiAutomation.actionTypes.scroll'),
    'drag': '拖拽',
    'screenshot': t('uiAutomation.actionTypes.screenshot'),
    'assert': t('uiAutomation.actionTypes.assert'),
    'wait': t('uiAutomation.actionTypes.wait'),
    'refreshCurrentPage': '刷新当前页',
    'closeCurrentPage': t('uiAutomation.actionTypes.closeCurrentPage')
  }
  return actionMap[actionType] || actionType
}

// 解析执行日志
const parseExecutionLogs = (logs) => {
  if (!logs) return []
  try {
    return typeof logs === 'string' ? JSON.parse(logs) : logs
  } catch (e) {
    console.error('解析执行日志失败:', e)
    return []
  }
}

const getCurrentStepDetails = () => {
  if (!currentExecution.value) return []
  if (Array.isArray(currentExecution.value.step_details) && currentExecution.value.step_details.length > 0) {
    return currentExecution.value.step_details
  }
  return parseExecutionLogs(currentExecution.value.execution_logs)
}

const openCleanupDialog = async () => {
  if (!projectId.value) {
    ElMessage.warning('请先选择项目')
    return
  }
  cleanupDialogVisible.value = true
  cleanupLoading.value = true
  try {
    const response = await getExecutionCleanupSetting(projectId.value)
    Object.assign(cleanupForm, {
      enabled: response.data.enabled || false,
      retention_days: response.data.retention_days || 30,
      last_cleaned_at: response.data.last_cleaned_at || null
    })
  } catch (error) {
    ElMessage.error('加载清理设置失败')
    console.error('加载清理设置失败:', error)
  } finally {
    cleanupLoading.value = false
  }
}

const saveCleanupSetting = async () => {
  if (!projectId.value) return
  cleanupLoading.value = true
  try {
    const response = await updateExecutionCleanupSetting({
      project: projectId.value,
      enabled: cleanupForm.enabled,
      retention_days: cleanupForm.retention_days
    })
    Object.assign(cleanupForm, response.data)
    ElMessage.success('清理设置已保存')
  } catch (error) {
    ElMessage.error(error.response?.data?.retention_days?.[0] || error.response?.data?.error || '保存清理设置失败')
  } finally {
    cleanupLoading.value = false
  }
}

const handleCleanupNow = async () => {
  if (!projectId.value) return
  try {
    await ElMessageBox.confirm(
      `将删除 ${cleanupForm.retention_days} 天以前且非运行中的执行记录，是否继续？`,
      '确认清理',
      {
        confirmButtonText: '确认',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
  } catch {
    return
  }

  cleanupLoading.value = true
  try {
    const response = await cleanupTestCaseExecutionsNow({
      project: projectId.value,
      retention_days: cleanupForm.retention_days
    })
    cleanupForm.last_cleaned_at = response.data.last_cleaned_at
    ElMessage.success(response.data.message || `已清理 ${response.data.deleted_count || 0} 条执行记录`)
    await loadExecutions()
  } catch (error) {
    ElMessage.error(error.response?.data?.error || '清理执行记录失败')
  } finally {
    cleanupLoading.value = false
  }
}

// 加载项目列表
const loadProjects = async () => {
  try {
    const response = await getUiProjects({ page_size: 100 })
    projects.value = response.data.results || response.data
  } catch (error) {
    ElMessage.error(t('uiAutomation.project.messages.loadFailed'))
    console.error('获取项目列表失败:', error)
  }
}

const loadLocalRunnerList = async () => {
  try {
    const response = await getLocalRunners({ page_size: 100 })
    const runnerList = response.data.results || response.data || []
    localRunners.value = runnerList.filter(item => item.is_online)
    if (!rerunFormData.runnerId && localRunners.value.length > 0) {
      rerunFormData.runnerId = localRunners.value[0].id
    }
  } catch (error) {
    console.error('获取本地执行器列表失败:', error)
    localRunners.value = []
  }
}

// 加载执行列表
const loadExecutions = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.currentPage,
      page_size: pagination.pageSize,
      ...queryParams
    }

    // 添加项目筛选
    if (projectId.value) {
      params.project = projectId.value
    } else {
      params.project = undefined // Ensure project is undefined if not selected
    }

    const response = await getTestCaseExecutions(params)
    executions.value = response.data.results || response.data
    total.value = response.data.count || executions.value.length
  } catch (error) {
    ElMessage.error(t('uiAutomation.execution.messages.loadFailed'))
    console.error('获取执行列表失败:', error)
  } finally {
    loading.value = false
  }
}

// 项目变更处理
const onProjectChange = () => {
  uiAutomationStore.setSelectedProject(projectId.value)
  queryParams.search = ''
  queryParams.status = ''
  queryParams.browser = ''
  pagination.currentPage = 1
  loadExecutions()
}

// 搜索处理
const handleSearch = () => {
  pagination.currentPage = 1
  loadExecutions()
}

// 重置查询
const resetQuery = () => {
  queryParams.search = ''
  queryParams.status = ''
  queryParams.browser = ''
  pagination.currentPage = 1
  loadExecutions()
}

// 分页处理
const handleSizeChange = (val) => {
  pagination.pageSize = val
  pagination.currentPage = 1
  loadExecutions()
}

const handleCurrentChange = (val) => {
  pagination.currentPage = val
  loadExecutions()
}

// 表格多选
const handleSelectionChange = (selection) => {
  selectedIds.value = selection.map(item => item.id)
}

// 删除单个执行记录
const handleDelete = (row) => {
  ElMessageBox.confirm(t('uiAutomation.execution.messages.deleteConfirm'), t('uiAutomation.messages.confirm.tip'), {
    confirmButtonText: t('uiAutomation.common.confirm'),
    cancelButtonText: t('uiAutomation.common.cancel'),
    type: 'warning'
  }).then(async () => {
    try {
      await deleteTestCaseExecution(row.id)
      ElMessage.success(t('uiAutomation.execution.messages.deleteSuccess'))
      loadExecutions()
    } catch (error) {
      console.error('删除失败:', error)
      ElMessage.error(t('uiAutomation.execution.messages.deleteFailed'))
    }
  })
}

// 批量删除执行记录
const handleBatchDelete = () => {
  if (selectedIds.value.length === 0) return

  ElMessageBox.confirm(t('uiAutomation.execution.messages.batchDeleteConfirm', { count: selectedIds.value.length }), t('uiAutomation.messages.confirm.tip'), {
    confirmButtonText: t('uiAutomation.common.confirm'),
    cancelButtonText: t('uiAutomation.common.cancel'),
    type: 'warning'
  }).then(async () => {
    try {
      await batchDeleteTestCaseExecutions(selectedIds.value)
      ElMessage.success(t('uiAutomation.execution.messages.batchDeleteSuccess'))
      selectedIds.value = []
      loadExecutions()
    } catch (error) {
      console.error('批量删除失败:', error)
      ElMessage.error(t('uiAutomation.execution.messages.batchDeleteFailed'))
    }
  })
}

// 查看执行详情
const viewExecutionDetail = (execution) => {
  currentExecution.value = execution
  activeTab.value = 'logs'
  showDetailDialog.value = true
}

// 显示重跑对话框
const showRerunDialog = (execution) => {
  rerunFormData.testCaseId = execution.test_case
  rerunFormData.engine = execution.engine || 'playwright'
  rerunFormData.browser = execution.browser || 'chrome'
  rerunFormData.headless = execution.headless || false
  rerunFormData.executionMode = execution.execution_mode || 'server'
  rerunFormData.runnerId = execution.assigned_runner || localRunners.value[0]?.id || null
  showRerunDialogVisible.value = true
}

// 执行重跑
const handleRerun = async () => {
  if (!rerunFormData.testCaseId) {
    ElMessage.error(t('uiAutomation.execution.messages.invalidCaseId'))
    return
  }

  if (rerunFormData.executionMode === 'local' && !rerunFormData.runnerId) {
    ElMessage.error('请选择本地执行器')
    return
  }

  rerunning.value = true
  try {
    const response = await runTestCase(rerunFormData.testCaseId, {
      engine: rerunFormData.engine,
      browser: rerunFormData.browser,
      headless: rerunFormData.headless,
      execution_mode: rerunFormData.executionMode,
      runner_id: rerunFormData.executionMode === 'local' ? rerunFormData.runnerId : undefined
    })

    // 无论成功失败，都关闭弹框并刷新列表
    showRerunDialogVisible.value = false

    // 延迟一下再刷新，确保后端已经保存完成
    setTimeout(async () => {
      await loadExecutions()
    }, 500)

    // 根据返回结果显示消息
    if (response.data.queued) {
      ElMessage.success(response.data.message || '重跑任务已下发到本地执行器')
    } else if (response.data.success) {
      ElMessage.success(t('uiAutomation.execution.messages.rerunSuccess'))
    } else {
      ElMessage.warning(t('uiAutomation.execution.messages.rerunCompleteWithFailure') + ': ' + (response.data.errors?.[0]?.message || t('uiAutomation.execution.messages.viewDetails')))
    }
  } catch (error) {
    showRerunDialogVisible.value = false
    ElMessage.error(t('uiAutomation.execution.messages.rerunFailed') + ': ' + (error.response?.data?.message || error.message || t('uiAutomation.messages.error.unknown')))
    console.error('重跑失败:', error)
    // 即使失败也刷新列表，因为可能已经创建了执行记录
    setTimeout(async () => {
      await loadExecutions()
    }, 500)
  } finally {
    rerunning.value = false
  }
}

// 组件挂载时加载数据
onMounted(async () => {
  await loadProjects()
  await loadLocalRunnerList()
  if (projects.value.length > 0) {
    projectId.value = uiAutomationStore.resolveSelectedProjectId(projects.value)
  }
  await loadExecutions()
})
</script>

<style scoped lang="scss">
.page-container {
  padding: 20px;
  height: 100%;
  overflow-y: auto;
  background: #f5f5f5;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  background: white;
  padding: 20px;
  border-radius: 4px;
}

.page-title {
  margin: 0;
  font-size: 24px;
  color: #303133;
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

.execution-detail {
  .execution-tabs {
    margin-top: 20px;
  }

  .logs-container {
    max-height: 500px;
    overflow-y: auto;
    background: #f5f7fa;
    padding: 15px;
    border-radius: 4px;

    .log-item {
      margin-bottom: 15px;
      padding: 12px;
      background: white;
      border-radius: 4px;
      border-left: 3px solid #409eff;

      &:last-child {
        margin-bottom: 0;
      }

      .log-header {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 8px;

        .log-action {
          font-weight: 500;
          color: #606266;
        }

        .log-desc {
          color: #909399;
          font-size: 14px;
        }
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
    }
  }

  .screenshots-container {
    max-height: 600px;
    overflow-y: auto;
    padding: 10px;

    .screenshot-item {
      margin-bottom: 30px;
      text-align: center;

      h5 {
        margin: 0 0 15px 0;
        color: #303133;
        font-size: 14px;
      }

      .screenshot-wrapper {
        position: relative;
      }

      .screenshot-img {
        max-width: 100%;
        border: 1px solid #dcdfe6;
        border-radius: 4px;
        box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
      }

      .screenshot-error {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 12px 20px;
        background: #fef0f0;
        color: #f56c6c;
        border: 1px solid #fbc4c4;
        border-radius: 4px;
        font-size: 14px;

        .el-icon {
          font-size: 16px;
        }
      }

      .img-load-error {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 12px 20px;
        background: #fff7e6;
        color: #e6a23c;
        border: 1px solid #f5dab1;
        border-radius: 4px;
        font-size: 14px;
        margin-top: 10px;

        i {
          font-size: 16px;
        }
      }

      .screenshot-time {
        margin: 10px 0 0 0;
        color: #909399;
        font-size: 12px;
      }
    }
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

  .error-content {
    display: flex;
    flex-direction: column;
  }

  .error-text {
    margin: 0;
    padding: 15px;
    background: #2d2d2d;
    color: #ff6b6b;
    border-radius: 4px;
    font-family: 'Courier New', Courier, monospace;
    font-size: 13px;
    line-height: 1.6;
    white-space: pre-wrap;
    word-wrap: break-word;
    overflow-x: auto;
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
}

.locator-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  word-break: break-all;
}

.detail-value {
  white-space: pre-wrap;
  word-break: break-word;
}

.step-error-text {
  margin-top: 4px;
  color: #f56c6c;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-word;
}

.cleanup-tip {
  margin-left: 12px;
  color: #909399;
  font-size: 13px;
}
</style>
