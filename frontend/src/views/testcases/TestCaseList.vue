<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">{{ $t('testcase.title') }}</h1>
      <div class="header-actions">
        <el-button
          v-if="selectedTestCases.length > 0"
          type="warning"
          @click="openMoveDialog(selectedTestCases)"
        >
          {{ $t('testcase.moveToFolder') }} ({{ selectedTestCases.length }})
        </el-button>
        <el-button
          v-if="selectedTestCases.length > 0"
          type="danger"
          @click="batchDeleteTestCases"
          :disabled="isDeleting"
        >
          <el-icon><Delete /></el-icon>
          {{ $t('testcase.batchDelete') }} ({{ selectedTestCases.length }})
        </el-button>
        <el-button type="success" @click="exportToExcel">
          <el-icon><Download /></el-icon>
          {{ $t('testcase.exportExcel') }}
        </el-button>
        <el-button type="primary" @click="$router.push('/ai-generation/testcases/create')">
          <el-icon><Plus /></el-icon>
          {{ $t('testcase.newCase') }}
        </el-button>
      </div>
    </div>

    <div class="content-card">
      <aside class="folder-panel">
        <div class="folder-panel-header">
          <div>
            <div class="folder-title">{{ $t('testcase.caseFolders') }}</div>
            <div class="folder-subtitle">{{ $t('testcase.folderHelpText') }}</div>
          </div>
          <el-button text type="primary" @click="openCreateFolderDialog">
            {{ $t('testcase.newFolder') }}
          </el-button>
        </div>

        <div class="folder-list">
          <button
            type="button"
            class="folder-item"
            :class="{ active: selectedFolderFilter === 'all' }"
            @click="selectFolder('all')"
          >
            <span>{{ $t('testcase.allCases') }}</span>
          </button>
          <button
            type="button"
            class="folder-item"
            :class="{ active: selectedFolderFilter === 'ungrouped' }"
            @click="selectFolder('ungrouped')"
          >
            <span>{{ $t('testcase.ungroupedCases') }}</span>
          </button>
          <button
            v-for="folder in folders"
            :key="folder.id"
            type="button"
            class="folder-item"
            :class="{ active: selectedFolderFilter === String(folder.id) }"
            @click="selectFolder(String(folder.id))"
          >
            <div class="folder-item-main">
              <span class="folder-name">{{ folder.name }}</span>
              <el-tag size="small" type="info">{{ folder.testcase_count || 0 }}</el-tag>
            </div>
            <div v-if="!projectFilter && folder.project?.name" class="folder-project">
              {{ folder.project.name }}
            </div>
          </button>
          <div v-if="folders.length === 0" class="folder-empty">
            {{ $t('testcase.noFolders') }}
          </div>
        </div>
      </aside>

      <section class="main-panel">
        <div class="filter-bar">
          <el-row :gutter="16">
            <el-col :xl="7" :lg="8" :md="10" :sm="12" :xs="24">
              <el-input
                v-model="searchText"
                :placeholder="$t('testcase.searchPlaceholder')"
                clearable
                @input="handleSearch"
              >
                <template #prefix>
                  <el-icon><Search /></el-icon>
                </template>
              </el-input>
            </el-col>
            <el-col :xl="5" :lg="6" :md="7" :sm="12" :xs="24">
              <el-select
                v-model="projectFilter"
                :placeholder="$t('testcase.relatedProject')"
                clearable
                filterable
                @change="handleProjectFilterChange"
              >
                <el-option
                  v-for="project in projects"
                  :key="project.id"
                  :label="project.name"
                  :value="project.id"
                />
              </el-select>
            </el-col>
            <el-col :xl="4" :lg="5" :md="7" :sm="12" :xs="24">
              <el-select
                v-model="priorityFilter"
                :placeholder="$t('testcase.priorityFilter')"
                clearable
                @change="handleFilter"
              >
                <el-option :label="$t('testcase.low')" value="low" />
                <el-option :label="$t('testcase.medium')" value="medium" />
                <el-option :label="$t('testcase.high')" value="high" />
                <el-option :label="$t('testcase.critical')" value="critical" />
              </el-select>
            </el-col>
            <el-col :xl="8" :lg="5" :md="24" :sm="12" :xs="24">
              <div class="current-folder">
                {{ $t('testcase.currentFolder') }}: {{ currentFolderLabel }}
              </div>
            </el-col>
          </el-row>
        </div>

        <div class="table-container">
          <el-table
            ref="tableRef"
            :data="testcases"
            v-loading="loading"
            style="width: 100%"
            height="100%"
            @selection-change="handleSelectionChange"
          >
            <el-table-column type="selection" width="55" />
            <el-table-column
              type="index"
              :label="$t('testcase.serialNumber')"
              width="80"
              :index="getSerialNumber"
            />
            <el-table-column prop="title" :label="$t('testcase.caseTitle')" min-width="220">
              <template #default="{ row }">
                <el-link @click="goToTestCase(row.id)" type="primary">
                  {{ row.title }}
                </el-link>
              </template>
            </el-table-column>
            <el-table-column prop="folder.name" :label="$t('testcase.folder')" width="160">
              <template #default="{ row }">
                {{ row.folder?.name || $t('testcase.ungroupedCases') }}
              </template>
            </el-table-column>
            <el-table-column prop="project.name" :label="$t('testcase.relatedProject')" width="150">
              <template #default="{ row }">
                {{ row.project?.name || '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="versions" :label="$t('testcase.relatedVersions')" width="200">
              <template #default="{ row }">
                <div v-if="row.versions && row.versions.length > 0" class="version-tags">
                  <el-tag
                    v-for="version in row.versions.slice(0, 2)"
                    :key="version.id"
                    size="small"
                    :type="version.is_baseline ? 'warning' : 'info'"
                    class="version-tag"
                  >
                    {{ version.name }}
                  </el-tag>
                  <el-tooltip v-if="row.versions.length > 2" :content="getVersionsTooltip(row.versions)">
                    <el-tag size="small" type="info" class="version-tag">
                      +{{ row.versions.length - 2 }}
                    </el-tag>
                  </el-tooltip>
                </div>
                <span v-else class="no-version">{{ $t('testcase.noVersion') }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="priority" :label="$t('testcase.priority')" width="100">
              <template #default="{ row }">
                <el-tag :class="`priority-tag ${row.priority}`">
                  {{ getPriorityText(row.priority) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="test_type" :label="$t('testcase.testType')" width="120">
              <template #default="{ row }">
                {{ getTypeText(row.test_type) }}
              </template>
            </el-table-column>
            <el-table-column prop="author.username" :label="$t('testcase.author')" width="120" />
            <el-table-column prop="created_at" :label="$t('testcase.createdAt')" width="180">
              <template #default="{ row }">
                {{ formatDate(row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column :label="$t('project.actions')" width="220" fixed="right">
              <template #default="{ row }">
                <el-button size="small" @click="openMoveDialog([row])">
                  {{ $t('testcase.move') }}
                </el-button>
                <el-button size="small" @click="editTestCase(row)">
                  {{ $t('common.edit') }}
                </el-button>
                <el-button size="small" type="danger" @click="deleteTestCase(row)">
                  {{ $t('common.delete') }}
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div class="pagination-container">
          <el-pagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :page-sizes="[15, 25, 35, 50, 100]"
            :total="total"
            layout="total, sizes, prev, pager, next"
            @current-change="handlePageChange"
            @size-change="handleSizeChange"
          />
        </div>
      </section>
    </div>

    <el-dialog
      v-model="createFolderDialogVisible"
      :title="$t('testcase.newFolder')"
      width="420px"
    >
      <el-form label-width="90px">
        <el-form-item :label="$t('testcase.project')">
          <el-select
            v-model="createFolderForm.project_id"
            :placeholder="$t('testcase.selectProject')"
            filterable
          >
            <el-option
              v-for="project in projects"
              :key="project.id"
              :label="project.name"
              :value="project.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item :label="$t('testcase.folderName')">
          <el-input
            v-model="createFolderForm.name"
            :placeholder="$t('testcase.folderNamePlaceholder')"
            maxlength="100"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createFolderDialogVisible = false">{{ $t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="createFolderSubmitting" @click="submitCreateFolder">
          {{ $t('common.confirm') }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="moveDialogVisible"
      :title="$t('testcase.moveToFolder')"
      width="420px"
    >
      <div class="move-dialog-tip">
        {{ $t('testcase.moveTip', { count: moveTargetTestcaseIds.length }) }}
      </div>
      <el-form label-width="90px">
        <el-form-item :label="$t('testcase.targetFolder')">
          <el-select v-model="moveForm.folder_id" clearable>
            <el-option :label="$t('testcase.ungroupedCases')" :value="null" />
            <el-option
              v-for="folder in moveFolderOptions"
              :key="folder.id"
              :label="folder.name"
              :value="folder.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="moveDialogVisible = false">{{ $t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="moving" @click="submitMove">
          {{ $t('common.confirm') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Download, Plus, Search } from '@element-plus/icons-vue'
import dayjs from 'dayjs'
import * as XLSX from 'xlsx'

import api from '@/utils/api'

const { t } = useI18n()
const router = useRouter()

const tableRef = ref()
const loading = ref(false)
const isDeleting = ref(false)
const moving = ref(false)
const createFolderSubmitting = ref(false)

const testcases = ref([])
const folders = ref([])
const projects = ref([])
const selectedTestCases = ref([])
const moveFolderOptions = ref([])

const currentPage = ref(1)
const pageSize = ref(15)
const total = ref(0)
const searchText = ref('')
const projectFilter = ref('')
const priorityFilter = ref('')
const selectedFolderFilter = ref('all')

const createFolderDialogVisible = ref(false)
const moveDialogVisible = ref(false)
const moveTargetTestcaseIds = ref([])

const createFolderForm = reactive({
  project_id: null,
  name: ''
})

const moveForm = reactive({
  folder_id: null
})

const currentFolderLabel = computed(() => {
  if (selectedFolderFilter.value === 'all') {
    return t('testcase.allCases')
  }
  if (selectedFolderFilter.value === 'ungrouped') {
    return t('testcase.ungroupedCases')
  }
  const folder = folders.value.find(item => String(item.id) === selectedFolderFilter.value)
  if (!folder) {
    return t('testcase.allCases')
  }
  return projectFilter.value
    ? folder.name
    : `${folder.project?.name || t('testcase.noProject')} / ${folder.name}`
})

const normalizeListResponse = (response) => response.data.results || response.data || []

const clearTableSelection = () => {
  selectedTestCases.value = []
  tableRef.value?.clearSelection?.()
}

const fetchProjects = async () => {
  try {
    const response = await api.get('/projects/list/')
    projects.value = normalizeListResponse(response)
  } catch (error) {
    ElMessage.error(t('testcase.fetchProjectsFailed'))
  }
}

const fetchFolders = async (projectId = projectFilter.value) => {
  try {
    const params = {}
    if (projectId) {
      params.project = projectId
    }
    const response = await api.get('/testcases/folders/', { params })
    folders.value = normalizeListResponse(response)
  } catch (error) {
    folders.value = []
    ElMessage.error(t('testcase.fetchFoldersFailed'))
  }
}

const fetchProjectFolders = async (projectId) => {
  if (!projectId) {
    return []
  }
  const response = await api.get('/testcases/folders/', { params: { project: projectId } })
  return normalizeListResponse(response)
}

const fetchTestCases = async () => {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value,
      search: searchText.value || undefined,
      project: projectFilter.value || undefined,
      priority: priorityFilter.value || undefined
    }

    if (selectedFolderFilter.value !== 'all') {
      params.folder_filter = selectedFolderFilter.value
    }

    const response = await api.get('/testcases/', { params })
    testcases.value = response.data.results || []
    total.value = response.data.count || 0
  } catch (error) {
    ElMessage.error(t('testcase.fetchListFailed'))
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  currentPage.value = 1
  fetchTestCases()
}

const handleFilter = () => {
  currentPage.value = 1
  fetchTestCases()
}

const handleProjectFilterChange = async () => {
  selectedFolderFilter.value = 'all'
  currentPage.value = 1
  clearTableSelection()
  await fetchFolders()
  await fetchTestCases()
}

const handlePageChange = () => {
  fetchTestCases()
}

const handleSizeChange = () => {
  currentPage.value = 1
  fetchTestCases()
}

const selectFolder = (folderFilter) => {
  selectedFolderFilter.value = folderFilter
  currentPage.value = 1
  clearTableSelection()
  fetchTestCases()
}

const goToTestCase = (id) => {
  router.push(`/ai-generation/testcases/${id}`)
}

const editTestCase = (testcase) => {
  router.push(`/ai-generation/testcases/${testcase.id}/edit`)
}

const handleSelectionChange = (selection) => {
  selectedTestCases.value = selection
}

const getSerialNumber = (index) => {
  return (currentPage.value - 1) * pageSize.value + index + 1
}

const deleteTestCase = async (testcase) => {
  try {
    await ElMessageBox.confirm(t('testcase.deleteConfirm'), t('common.warning'), {
      confirmButtonText: t('common.confirm'),
      cancelButtonText: t('common.cancel'),
      type: 'warning'
    })

    await api.delete(`/testcases/${testcase.id}/`)
    ElMessage.success(t('testcase.deleteSuccess'))
    clearTableSelection()
    await fetchFolders()
    fetchTestCases()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(t('testcase.deleteFailed'))
    }
  }
}

const batchDeleteTestCases = async () => {
  if (selectedTestCases.value.length === 0) {
    ElMessage.warning(t('testcase.selectFirst'))
    return
  }

  try {
    await ElMessageBox.confirm(
      t('testcase.batchDeleteConfirm', { count: selectedTestCases.value.length }),
      t('common.warning'),
      {
        confirmButtonText: t('common.confirm'),
        cancelButtonText: t('common.cancel'),
        type: 'warning'
      }
    )

    isDeleting.value = true
    let successCount = 0
    let failCount = 0

    for (const testcase of selectedTestCases.value) {
      try {
        await api.delete(`/testcases/${testcase.id}/`)
        successCount += 1
      } catch (error) {
        failCount += 1
        console.error(`Delete test case ${testcase.id} failed:`, error)
      }
    }

    if (successCount > 0) {
      if (failCount > 0) {
        ElMessage.success(t('testcase.batchDeletePartialSuccess', { successCount, failCount }))
      } else {
        ElMessage.success(t('testcase.batchDeleteSuccess', { successCount }))
      }
    } else {
      ElMessage.error(t('testcase.batchDeleteFailed'))
    }

    clearTableSelection()
    await fetchFolders()
    fetchTestCases()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Batch delete failed:', error)
      ElMessage.error(t('testcase.batchDeleteError'))
    }
  } finally {
    isDeleting.value = false
  }
}

const openCreateFolderDialog = () => {
  createFolderForm.project_id = projectFilter.value || null
  createFolderForm.name = ''
  createFolderDialogVisible.value = true
}

const submitCreateFolder = async () => {
  if (!createFolderForm.project_id) {
    ElMessage.warning(t('testcase.projectRequired'))
    return
  }
  if (!createFolderForm.name.trim()) {
    ElMessage.warning(t('testcase.folderNameRequired'))
    return
  }

  createFolderSubmitting.value = true
  try {
    const response = await api.post('/testcases/folders/', {
      project_id: createFolderForm.project_id,
      name: createFolderForm.name.trim()
    })

    const createdFolder = response.data
    if (createdFolder.project?.id && projectFilter.value !== createdFolder.project.id) {
      projectFilter.value = createdFolder.project.id
    }

    createFolderDialogVisible.value = false
    selectedFolderFilter.value = String(createdFolder.id)
    ElMessage.success(t('testcase.createFolderSuccess'))
    await fetchFolders(projectFilter.value)
    await fetchTestCases()
  } catch (error) {
    ElMessage.error(
      error?.response?.data?.name?.[0] ||
      error?.response?.data?.project_id?.[0] ||
      t('testcase.createFolderFailed')
    )
  } finally {
    createFolderSubmitting.value = false
  }
}

const openMoveDialog = async (rows) => {
  const targetRows = rows || []
  if (targetRows.length === 0) {
    ElMessage.warning(t('testcase.selectFirst'))
    return
  }

  const projectIds = [...new Set(targetRows.map(item => item.project?.id).filter(Boolean))]
  if (projectIds.length > 1) {
    ElMessage.warning(t('testcase.moveSameProjectOnly'))
    return
  }

  try {
    moveFolderOptions.value = await fetchProjectFolders(projectIds[0])
    moveTargetTestcaseIds.value = targetRows.map(item => item.id)
    moveForm.folder_id = targetRows.length === 1 ? (targetRows[0].folder_id ?? null) : null
    moveDialogVisible.value = true
  } catch (error) {
    ElMessage.error(t('testcase.fetchFoldersFailed'))
  }
}

const submitMove = async () => {
  moving.value = true
  try {
    await api.post('/testcases/move/', {
      testcase_ids: moveTargetTestcaseIds.value,
      folder_id: moveForm.folder_id
    })
    moveDialogVisible.value = false
    clearTableSelection()
    ElMessage.success(t('testcase.moveSuccess'))
    await fetchFolders()
    await fetchTestCases()
  } catch (error) {
    ElMessage.error(
      error?.response?.data?.folder_id?.[0] ||
      error?.response?.data?.testcase_ids?.[0] ||
      t('testcase.moveFailed')
    )
  } finally {
    moving.value = false
  }
}

const getPriorityText = (priority) => {
  const textMap = {
    low: t('testcase.low'),
    medium: t('testcase.medium'),
    high: t('testcase.high'),
    critical: t('testcase.critical')
  }
  return textMap[priority] || priority
}

const getTypeText = (type) => {
  const textMap = {
    functional: t('testcase.functional'),
    integration: t('testcase.integration'),
    api: t('testcase.api'),
    ui: t('testcase.ui'),
    performance: t('testcase.performance'),
    security: t('testcase.security')
  }
  return textMap[type] || '-'
}

const formatDate = (dateString) => {
  return dayjs(dateString).format('YYYY-MM-DD HH:mm')
}

const getVersionsTooltip = (versions) => {
  return versions
    .map(version => `${version.name}${version.is_baseline ? ` (${t('testcase.baseline')})` : ''}`)
    .join('、')
}

const convertBrToNewline = (text) => {
  if (!text) return ''
  return text.replace(/<br\s*\/?>/gi, '\n')
}

const exportToExcel = async () => {
  try {
    loading.value = true
    let testCasesToExport = []

    if (selectedTestCases.value.length > 0) {
      testCasesToExport = selectedTestCases.value
    } else {
      const exportPageSize = 100
      let page = 1
      let hasMore = true
      const allData = []

      while (hasMore) {
        const params = {
          page,
          page_size: exportPageSize,
          search: searchText.value || undefined,
          project: projectFilter.value || undefined,
          priority: priorityFilter.value || undefined
        }

        if (selectedFolderFilter.value !== 'all') {
          params.folder_filter = selectedFolderFilter.value
        }

        const response = await api.get('/testcases/', { params })
        const results = response.data.results || []
        allData.push(...results)

        if (results.length < exportPageSize) {
          hasMore = false
        } else {
          page += 1
        }
      }

      testCasesToExport = allData
    }

    if (testCasesToExport.length === 0) {
      ElMessage.warning(t('testcase.noDataToExport'))
      return
    }

    const workbook = XLSX.utils.book_new()
    const worksheetData = [[
      t('testcase.excelNumber'),
      t('testcase.excelTitle'),
      t('testcase.excelFolder'),
      t('testcase.excelProject'),
      t('testcase.excelVersions'),
      t('testcase.excelPreconditions'),
      t('testcase.excelSteps'),
      t('testcase.excelExpectedResult'),
      t('testcase.excelPriority'),
      t('testcase.excelTestType'),
      t('testcase.excelAuthor'),
      t('testcase.excelCreatedAt')
    ]]

    testCasesToExport.forEach((testcase, index) => {
      const versions = testcase.versions?.length
        ? testcase.versions
            .map(version => `${version.name}${version.is_baseline ? `(${t('testcase.baseline')})` : ''}`)
            .join('、')
        : t('testcase.noVersion')

      worksheetData.push([
        `TC${String(index + 1).padStart(3, '0')}`,
        testcase.title || '',
        testcase.folder?.name || t('testcase.ungroupedCases'),
        testcase.project?.name || '',
        versions,
        convertBrToNewline(testcase.preconditions || ''),
        convertBrToNewline(testcase.steps || ''),
        convertBrToNewline(testcase.expected_result || ''),
        getPriorityText(testcase.priority),
        getTypeText(testcase.test_type),
        testcase.author?.username || '',
        formatDate(testcase.created_at)
      ])
    })

    const worksheet = XLSX.utils.aoa_to_sheet(worksheetData)
    worksheet['!cols'] = [
      { wch: 15 },
      { wch: 30 },
      { wch: 20 },
      { wch: 20 },
      { wch: 25 },
      { wch: 30 },
      { wch: 40 },
      { wch: 30 },
      { wch: 10 },
      { wch: 15 },
      { wch: 15 },
      { wch: 20 }
    ]

    XLSX.utils.book_append_sheet(workbook, worksheet, t('testcase.excelSheetName'))
    const fileName = t('testcase.excelFileName', { date: new Date().toISOString().slice(0, 10) })
    XLSX.writeFile(workbook, fileName)
    ElMessage.success(t('testcase.exportSuccess'))
  } catch (error) {
    console.error('Export test cases failed:', error)
    ElMessage.error(t('testcase.exportFailed'))
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await fetchProjects()
  await fetchFolders()
  await fetchTestCases()
})
</script>

<style lang="scss" scoped>
.page-container {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  padding: 20px;
  box-sizing: border-box;
  background: #f5f7fa;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
}

.page-title {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: #303133;
}

.header-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.content-card {
  display: flex;
  gap: 20px;
  flex: 1;
  min-height: 0;
}

.folder-panel,
.main-panel {
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
}

.folder-panel {
  width: 280px;
  display: flex;
  flex-direction: column;
  padding: 18px;
  min-height: 0;
}

.folder-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 16px;
}

.folder-title {
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
}

.folder-subtitle {
  margin-top: 4px;
  font-size: 12px;
  color: #6b7280;
  line-height: 1.5;
}

.folder-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow-y: auto;
}

.folder-item {
  width: 100%;
  padding: 12px 14px;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  background: #fff;
  text-align: left;
  cursor: pointer;
  transition: all 0.2s ease;
}

.folder-item:hover {
  border-color: #cbd5e1;
  background: #f8fafc;
}

.folder-item.active {
  border-color: #409eff;
  background: #ecf5ff;
}

.folder-item-main {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.folder-name {
  color: #111827;
  font-weight: 500;
  word-break: break-all;
}

.folder-project {
  margin-top: 6px;
  font-size: 12px;
  color: #6b7280;
}

.folder-empty {
  padding: 16px 12px;
  color: #909399;
  text-align: center;
}

.main-panel {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
  min-height: 0;
}

.filter-bar {
  padding: 20px 20px 14px;
  border-bottom: 1px solid #ebeef5;
}

.current-folder {
  display: flex;
  align-items: center;
  min-height: 32px;
  color: #475569;
  font-size: 13px;
}

.table-container {
  flex: 1;
  min-height: 0;
  padding: 0 20px;

  :deep(.el-table) {
    height: 100% !important;
  }

  :deep(.el-table__body-wrapper) {
    overflow-y: auto !important;
  }
}

.pagination-container {
  padding: 18px 20px 20px;
  border-top: 1px solid #ebeef5;
  display: flex;
  justify-content: center;
}

.priority-tag {
  &.low {
    color: #67c23a;
  }

  &.medium {
    color: #e6a23c;
  }

  &.high {
    color: #f56c6c;
  }

  &.critical {
    color: #f56c6c;
    font-weight: bold;
  }
}

.version-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.version-tag {
  margin: 0;
}

.no-version {
  color: #909399;
  font-size: 12px;
  font-style: italic;
}

.move-dialog-tip {
  margin-bottom: 12px;
  color: #606266;
  line-height: 1.6;
}

@media (max-width: 1100px) {
  .content-card {
    flex-direction: column;
  }

  .folder-panel {
    width: 100%;
  }
}

@media (max-width: 768px) {
  .page-container {
    padding: 12px;
  }

  .page-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .header-actions {
    width: 100%;
  }

  .filter-bar {
    padding: 16px;
  }

  .table-container {
    padding: 0 12px;
  }

  .pagination-container {
    padding: 16px 12px;
  }
}
</style>
