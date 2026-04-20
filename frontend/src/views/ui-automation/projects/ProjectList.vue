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
            <el-select
              v-model="statusFilter"
              :placeholder="$t('uiAutomation.project.statusFilter')"
              clearable
              @change="handleFilter"
            >
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
            <el-link type="primary" @click="goToProjectDetail(row.id)">
              {{ row.name }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column prop="description" :label="$t('uiAutomation.common.description')" min-width="240" show-overflow-tooltip />
        <el-table-column prop="status" :label="$t('uiAutomation.common.status')" width="110">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ getStatusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="base_url" :label="$t('uiAutomation.project.baseUrl')" min-width="220" show-overflow-tooltip />
        <el-table-column prop="owner.username" :label="$t('uiAutomation.project.owner')" width="120" />
        <el-table-column :label="$t('uiAutomation.project.teamMembers')" width="220">
          <template #default="{ row }">
            <div class="member-cell">
              <el-tag size="small" type="info">
                {{ $t('uiAutomation.project.memberCountText', { count: row.members?.length || 0 }) }}
              </el-tag>
              <span class="member-preview">
                {{ formatMemberPreview(row.members) }}
              </span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" :label="$t('uiAutomation.common.createTime')" width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="updated_at" :label="$t('uiAutomation.common.updateTime')" width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.updated_at) }}
          </template>
        </el-table-column>
        <el-table-column :label="$t('uiAutomation.common.operation')" width="220" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="goToProjectDetail(row.id)">
              <el-icon><View /></el-icon>
              {{ $t('uiAutomation.common.view') }}
            </el-button>
            <el-button v-if="canManageProject(row)" size="small" @click="editProject(row)">
              <el-icon><Edit /></el-icon>
              {{ $t('uiAutomation.common.edit') }}
            </el-button>
            <el-button
              v-if="canManageProject(row)"
              size="small"
              type="danger"
              @click="deleteProject(row)"
            >
              <el-icon><Delete /></el-icon>
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

    <el-dialog
      v-model="showCreateDialog"
      :title="$t('uiAutomation.project.createProject')"
      width="640px"
      :close-on-click-modal="false"
      @closed="resetCreateForm"
    >
      <el-form ref="createFormRef" :model="createForm" :rules="formRules" label-width="100px">
        <el-form-item :label="$t('uiAutomation.project.projectName')" prop="name">
          <el-input v-model="createForm.name" :placeholder="$t('uiAutomation.project.rules.nameRequired')" />
        </el-form-item>
        <el-form-item :label="$t('uiAutomation.project.projectDesc')" prop="description">
          <el-input
            v-model="createForm.description"
            type="textarea"
            :rows="3"
            :placeholder="$t('uiAutomation.project.projectDesc')"
          />
        </el-form-item>
        <el-form-item :label="$t('uiAutomation.common.status')" prop="status">
          <el-select v-model="createForm.status" :placeholder="$t('uiAutomation.project.rules.selectStatus')">
            <el-option :label="$t('uiAutomation.status.notStarted')" value="NOT_STARTED" />
            <el-option :label="$t('uiAutomation.status.inProgress')" value="IN_PROGRESS" />
            <el-option :label="$t('uiAutomation.status.completed')" value="COMPLETED" />
          </el-select>
        </el-form-item>
        <el-form-item :label="$t('uiAutomation.project.baseUrl')" prop="base_url">
          <el-input v-model="createForm.base_url" :placeholder="$t('uiAutomation.project.rules.baseUrlRequired')" />
        </el-form-item>
        <el-form-item :label="$t('uiAutomation.project.browserResolution')">
          <el-row :gutter="12" class="resolution-row">
            <el-col :span="12">
              <el-form-item prop="browser_width" class="resolution-item">
                <el-input-number
                  v-model="createForm.browser_width"
                  :min="MIN_BROWSER_WIDTH"
                  :max="MAX_BROWSER_WIDTH"
                  :placeholder="$t('uiAutomation.project.browserWidth')"
                  controls-position="right"
                  style="width: 100%"
                />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item prop="browser_height" class="resolution-item">
                <el-input-number
                  v-model="createForm.browser_height"
                  :min="MIN_BROWSER_HEIGHT"
                  :max="MAX_BROWSER_HEIGHT"
                  :placeholder="$t('uiAutomation.project.browserHeight')"
                  controls-position="right"
                  style="width: 100%"
                />
              </el-form-item>
            </el-col>
          </el-row>
        </el-form-item>
        <el-form-item :label="$t('uiAutomation.project.teamMembers')" prop="member_ids">
          <el-select
            v-model="createForm.member_ids"
            multiple
            filterable
            collapse-tags
            collapse-tags-tooltip
            :placeholder="$t('uiAutomation.project.selectMembers')"
          >
            <el-option
              v-for="user in memberOptions"
              :key="user.id"
              :label="formatUserLabel(user)"
              :value="user.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="全局变量">
          <div class="global-variables-editor">
            <div
              v-for="(item, index) in createForm.global_variables"
              :key="`create-var-${index}`"
              class="global-variable-row"
            >
              <el-input v-model="item.name" placeholder="变量名，如 baseUrl" />
              <el-input v-model="item.value" placeholder="变量值" />
              <el-input v-model="item.description" placeholder="描述，可选" />
              <el-button type="danger" plain @click="removeGlobalVariable(createForm, index)">删除</el-button>
            </div>
            <el-button plain @click="addGlobalVariable(createForm)">新增变量</el-button>
            <div class="form-tip">当前项目中的所有 UI 自动化测试用例都可以使用 `${变量名}` 引用这里定义的变量。</div>
          </div>
        </el-form-item>
        <div class="form-tip">{{ $t('uiAutomation.project.ownerOnlyTip') }}</div>
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
          <el-button type="primary" :loading="submitting" @click="handleCreate">
            {{ $t('uiAutomation.common.confirm') }}
          </el-button>
        </span>
      </template>
    </el-dialog>

    <el-dialog
      v-model="showEditDialog"
      :title="$t('uiAutomation.project.editProject')"
      width="640px"
      :close-on-click-modal="false"
      @closed="resetEditForm"
    >
      <el-form ref="editFormRef" :model="editForm" :rules="formRules" label-width="100px">
        <el-form-item :label="$t('uiAutomation.project.projectName')" prop="name">
          <el-input v-model="editForm.name" :placeholder="$t('uiAutomation.project.rules.nameRequired')" />
        </el-form-item>
        <el-form-item :label="$t('uiAutomation.project.projectDesc')" prop="description">
          <el-input
            v-model="editForm.description"
            type="textarea"
            :rows="3"
            :placeholder="$t('uiAutomation.project.projectDesc')"
          />
        </el-form-item>
        <el-form-item :label="$t('uiAutomation.common.status')" prop="status">
          <el-select v-model="editForm.status" :placeholder="$t('uiAutomation.project.rules.selectStatus')">
            <el-option :label="$t('uiAutomation.status.notStarted')" value="NOT_STARTED" />
            <el-option :label="$t('uiAutomation.status.inProgress')" value="IN_PROGRESS" />
            <el-option :label="$t('uiAutomation.status.completed')" value="COMPLETED" />
          </el-select>
        </el-form-item>
        <el-form-item :label="$t('uiAutomation.project.baseUrl')" prop="base_url">
          <el-input v-model="editForm.base_url" :placeholder="$t('uiAutomation.project.rules.baseUrlRequired')" />
        </el-form-item>
        <el-form-item :label="$t('uiAutomation.project.browserResolution')">
          <el-row :gutter="12" class="resolution-row">
            <el-col :span="12">
              <el-form-item prop="browser_width" class="resolution-item">
                <el-input-number
                  v-model="editForm.browser_width"
                  :min="MIN_BROWSER_WIDTH"
                  :max="MAX_BROWSER_WIDTH"
                  :placeholder="$t('uiAutomation.project.browserWidth')"
                  controls-position="right"
                  style="width: 100%"
                />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item prop="browser_height" class="resolution-item">
                <el-input-number
                  v-model="editForm.browser_height"
                  :min="MIN_BROWSER_HEIGHT"
                  :max="MAX_BROWSER_HEIGHT"
                  :placeholder="$t('uiAutomation.project.browserHeight')"
                  controls-position="right"
                  style="width: 100%"
                />
              </el-form-item>
            </el-col>
          </el-row>
        </el-form-item>
        <el-form-item :label="$t('uiAutomation.project.teamMembers')" prop="member_ids">
          <el-select
            v-model="editForm.member_ids"
            multiple
            filterable
            collapse-tags
            collapse-tags-tooltip
            :placeholder="$t('uiAutomation.project.selectMembers')"
          >
            <el-option
              v-for="user in memberOptions"
              :key="user.id"
              :label="formatUserLabel(user)"
              :value="user.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="全局变量">
          <div class="global-variables-editor">
            <div
              v-for="(item, index) in editForm.global_variables"
              :key="`edit-var-${index}`"
              class="global-variable-row"
            >
              <el-input v-model="item.name" placeholder="变量名，如 baseUrl" />
              <el-input v-model="item.value" placeholder="变量值" />
              <el-input v-model="item.description" placeholder="描述，可选" />
              <el-button type="danger" plain @click="removeGlobalVariable(editForm, index)">删除</el-button>
            </div>
            <el-button plain @click="addGlobalVariable(editForm)">新增变量</el-button>
            <div class="form-tip">当前项目中的所有 UI 自动化测试用例都可以使用 `${变量名}` 引用这里定义的变量。</div>
          </div>
        </el-form-item>
        <div class="form-tip">{{ $t('uiAutomation.project.ownerOnlyTip') }}</div>
        <el-form-item :label="$t('uiAutomation.project.startDate')" prop="start_date">
          <el-date-picker v-model="editForm.start_date" type="date" :placeholder="$t('uiAutomation.project.selectDate')" />
        </el-form-item>
        <el-form-item :label="$t('uiAutomation.project.endDate')" prop="end_date">
          <el-date-picker v-model="editForm.end_date" type="date" :placeholder="$t('uiAutomation.project.selectDate')" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showEditDialog = false">{{ $t('uiAutomation.common.cancel') }}</el-button>
          <el-button type="primary" :loading="submitting" @click="handleEdit">
            {{ $t('uiAutomation.common.confirm') }}
          </el-button>
        </span>
      </template>
    </el-dialog>

    <el-dialog v-model="showDetailDialog" :title="$t('uiAutomation.project.projectDetail')" width="720px">
      <div v-if="currentProjectDetail" class="project-detail">
        <el-descriptions bordered :column="1">
          <el-descriptions-item :label="$t('uiAutomation.project.projectName')">
            {{ currentProjectDetail.name }}
          </el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.project.projectDesc')">
            {{ currentProjectDetail.description || $t('uiAutomation.project.noDescription') }}
          </el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.common.status')">
            <el-tag :type="getStatusType(currentProjectDetail.status)">
              {{ getStatusText(currentProjectDetail.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.project.baseUrl')">
            {{ currentProjectDetail.base_url }}
          </el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.project.browserResolution')">
            {{ currentProjectDetail.browser_width }} x {{ currentProjectDetail.browser_height }}
          </el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.project.owner')">
            {{ currentProjectDetail.owner?.username || $t('uiAutomation.project.none') }}
          </el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.project.teamMembers')">
            <div v-if="currentProjectDetail.members?.length" class="member-tags">
              <el-tag
                v-for="member in currentProjectDetail.members"
                :key="member.id"
                size="small"
              >
                {{ formatUserLabel(member) }}
              </el-tag>
            </div>
            <span v-else>{{ $t('uiAutomation.project.noMembers') }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="全局变量">
            <div v-if="currentProjectDetail.global_variables?.length" class="global-variable-tags">
              <div
                v-for="(item, index) in currentProjectDetail.global_variables"
                :key="`detail-var-${index}`"
                class="global-variable-display"
              >
                <el-tag type="success">{{ '${' + item.name + '}' }}</el-tag>
                <span>{{ item.value || '-' }}</span>
                <span v-if="item.description" class="variable-description">{{ item.description }}</span>
              </div>
            </div>
            <span v-else>未配置</span>
          </el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.project.startDate')">
            {{ currentProjectDetail.start_date ? formatDateOnly(currentProjectDetail.start_date) : $t('uiAutomation.project.notSet') }}
          </el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.project.endDate')">
            {{ currentProjectDetail.end_date ? formatDateOnly(currentProjectDetail.end_date) : $t('uiAutomation.project.notSet') }}
          </el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.common.createTime')">
            {{ formatDateTime(currentProjectDetail.created_at) }}
          </el-descriptions-item>
          <el-descriptions-item :label="$t('uiAutomation.common.updateTime')">
            {{ formatDateTime(currentProjectDetail.updated_at) }}
          </el-descriptions-item>
        </el-descriptions>

        <div class="detail-tip">
          {{ $t('uiAutomation.project.collaborationTip') }}
        </div>
      </div>
      <div v-else class="empty-state">
        {{ $t('uiAutomation.common.loading') }}
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showDetailDialog = false">{{ $t('uiAutomation.common.close') }}</el-button>
          <el-button
            v-if="currentProjectDetail && canManageProject(currentProjectDetail)"
            type="primary"
            @click="editProject(currentProjectDetail)"
          >
            {{ $t('uiAutomation.common.edit') }}
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Edit, Plus, Search, View } from '@element-plus/icons-vue'
import { createUiProject, deleteUiProject, getUiProjects, getUiUsers, updateUiProject } from '@/api/ui_automation'
import { useUserStore } from '@/stores/user'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const userStore = useUserStore()
const DEFAULT_BROWSER_WIDTH = 1920
const DEFAULT_BROWSER_HEIGHT = 1060
const MIN_BROWSER_WIDTH = 320
const MIN_BROWSER_HEIGHT = 240
const MAX_BROWSER_WIDTH = 7680
const MAX_BROWSER_HEIGHT = 4320

const createEmptyGlobalVariable = () => ({
  name: '',
  value: '',
  description: ''
})

const cloneGlobalVariables = (items = []) => {
  return (items || []).map(item => ({
    name: item?.name || '',
    value: item?.value || '',
    description: item?.description || ''
  }))
}

const buildDefaultForm = () => ({
  name: '',
  description: '',
  status: 'IN_PROGRESS',
  base_url: '',
  browser_width: DEFAULT_BROWSER_WIDTH,
  browser_height: DEFAULT_BROWSER_HEIGHT,
  member_ids: [],
  global_variables: [],
  start_date: null,
  end_date: null
})

const projects = ref([])
const users = ref([])
const loading = ref(false)
const submitting = ref(false)
const total = ref(0)
const searchText = ref('')
const statusFilter = ref('')
const showCreateDialog = ref(false)
const showEditDialog = ref(false)
const showDetailDialog = ref(false)
const createFormRef = ref(null)
const editFormRef = ref(null)
const currentEditId = ref(null)
const currentProjectDetail = ref(null)

const pagination = reactive({
  currentPage: 1,
  pageSize: 10
})

const createForm = reactive(buildDefaultForm())
const editForm = reactive(buildDefaultForm())

const currentUserId = computed(() => userStore.user?.id || null)
const memberOptions = computed(() => users.value.filter(user => user.id !== currentUserId.value))

const formRules = computed(() => ({
  name: [
    { required: true, message: t('uiAutomation.project.rules.nameRequired'), trigger: 'blur' },
    { min: 2, max: 200, message: t('uiAutomation.project.rules.nameLength'), trigger: 'blur' }
  ],
  base_url: [
    { required: true, message: t('uiAutomation.project.rules.baseUrlRequired'), trigger: 'blur' },
    { type: 'url', message: t('uiAutomation.project.rules.baseUrlInvalid'), trigger: 'blur' }
  ],
  browser_width: [
    { required: true, type: 'number', message: t('uiAutomation.project.rules.browserWidthRequired'), trigger: 'change' },
    { type: 'number', min: MIN_BROWSER_WIDTH, max: MAX_BROWSER_WIDTH, message: t('uiAutomation.project.rules.browserWidthRange'), trigger: 'change' }
  ],
  browser_height: [
    { required: true, type: 'number', message: t('uiAutomation.project.rules.browserHeightRequired'), trigger: 'change' },
    { type: 'number', min: MIN_BROWSER_HEIGHT, max: MAX_BROWSER_HEIGHT, message: t('uiAutomation.project.rules.browserHeightRange'), trigger: 'change' }
  ]
}))

const formatDateTime = (value) => {
  if (!value) return ''
  return new Date(value).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

const formatDateOnly = (value) => {
  if (!value) return ''
  return new Date(value).toLocaleDateString('zh-CN')
}

const formatDateToISO = (date) => {
  if (!date) return null
  return new Date(date).toISOString().split('T')[0]
}

const formatUserLabel = (user) => {
  if (!user) return ''
  return user.email ? `${user.username} (${user.email})` : user.username
}

const formatMemberPreview = (members = []) => {
  if (!members.length) {
    return t('uiAutomation.project.noMembers')
  }
  const names = members.slice(0, 2).map(member => member.username).join(', ')
  return members.length > 2 ? `${names}...` : names
}

const getStatusType = (status) => {
  const statusMap = {
    NOT_STARTED: 'warning',
    IN_PROGRESS: 'primary',
    COMPLETED: 'success'
  }
  return statusMap[status] || 'default'
}

const getStatusText = (status) => {
  const statusKey = {
    NOT_STARTED: 'notStarted',
    IN_PROGRESS: 'inProgress',
    COMPLETED: 'completed'
  }[status]
  return statusKey ? t(`uiAutomation.status.${statusKey}`) : status
}

const canManageProject = (project) => project?.owner?.id === currentUserId.value

const addGlobalVariable = (form) => {
  form.global_variables.push(createEmptyGlobalVariable())
}

const removeGlobalVariable = (form, index) => {
  form.global_variables.splice(index, 1)
}

const loadProjects = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.currentPage,
      page_size: pagination.pageSize
    }

    if (searchText.value) {
      params.search = searchText.value
    }

    if (statusFilter.value) {
      params.status = statusFilter.value
    }

    const response = await getUiProjects(params)
    projects.value = response.data.results || response.data
    total.value = response.data.count || projects.value.length
  } catch (error) {
    ElMessage.error(t('uiAutomation.project.messages.loadFailed'))
    console.error('Failed to load UI automation projects:', error)
  } finally {
    loading.value = false
  }
}

const loadUsers = async () => {
  try {
    const response = await getUiUsers()
    users.value = response.data.results || response.data
  } catch (error) {
    ElMessage.error(t('uiAutomation.project.messages.loadUsersFailed'))
    console.error('Failed to load users:', error)
  }
}

const resetCreateForm = () => {
  Object.assign(createForm, buildDefaultForm())
  createFormRef.value?.clearValidate()
}

const resetEditForm = () => {
  currentEditId.value = null
  Object.assign(editForm, buildDefaultForm())
  editFormRef.value?.clearValidate()
}

const handleSearch = () => {
  pagination.currentPage = 1
  loadProjects()
}

const handleFilter = () => {
  pagination.currentPage = 1
  loadProjects()
}

const handleSizeChange = (size) => {
  pagination.pageSize = size
  loadProjects()
}

const handleCurrentChange = (current) => {
  pagination.currentPage = current
  loadProjects()
}

const goToProjectDetail = (id) => {
  const project = projects.value.find(item => item.id === id)
  if (!project) {
    ElMessage.error(t('uiAutomation.project.messages.notFound'))
    return
  }
  currentProjectDetail.value = project
  showDetailDialog.value = true
}

const editProject = (project) => {
  if (!canManageProject(project)) {
    ElMessage.error(t('uiAutomation.project.messages.ownerOnlyAction'))
    return
  }

  currentEditId.value = project.id
  Object.assign(editForm, {
    name: project.name,
    description: project.description,
    status: project.status,
    base_url: project.base_url,
    browser_width: project.browser_width ?? DEFAULT_BROWSER_WIDTH,
    browser_height: project.browser_height ?? DEFAULT_BROWSER_HEIGHT,
    member_ids: (project.members || []).map(member => member.id),
    global_variables: cloneGlobalVariables(project.global_variables),
    start_date: project.start_date ? new Date(project.start_date) : null,
    end_date: project.end_date ? new Date(project.end_date) : null
  })
  showDetailDialog.value = false
  showEditDialog.value = true
}

const deleteProject = async (project) => {
  if (!canManageProject(project)) {
    ElMessage.error(t('uiAutomation.project.messages.ownerOnlyAction'))
    return
  }

  try {
    await ElMessageBox.confirm(
      t('uiAutomation.project.messages.deleteConfirm'),
      t('uiAutomation.common.warning'),
      {
        confirmButtonText: t('uiAutomation.common.confirm'),
        cancelButtonText: t('uiAutomation.common.cancel'),
        type: 'warning'
      }
    )

    await deleteUiProject(project.id)
    ElMessage.success(t('uiAutomation.project.messages.deleteSuccess'))
    if (currentProjectDetail.value?.id === project.id) {
      showDetailDialog.value = false
      currentProjectDetail.value = null
    }
    loadProjects()
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(t('uiAutomation.project.messages.deleteFailed'))
    console.error('Failed to delete project:', error)
  }
}

const handleCreate = async () => {
  const valid = await createFormRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    const projectData = {
      ...createForm,
      member_ids: [...createForm.member_ids],
      global_variables: cloneGlobalVariables(createForm.global_variables),
      start_date: formatDateToISO(createForm.start_date),
      end_date: formatDateToISO(createForm.end_date)
    }

    await createUiProject(projectData)
    ElMessage.success(t('uiAutomation.project.messages.createSuccess'))
    showCreateDialog.value = false
    resetCreateForm()
    loadProjects()
  } catch (error) {
    ElMessage.error(t('uiAutomation.project.messages.createFailed'))
    console.error('Failed to create project:', error)
  } finally {
    submitting.value = false
  }
}

const handleEdit = async () => {
  const valid = await editFormRef.value?.validate().catch(() => false)
  if (!valid || !currentEditId.value) return

  submitting.value = true
  try {
    const projectData = {
      ...editForm,
      member_ids: [...editForm.member_ids],
      global_variables: cloneGlobalVariables(editForm.global_variables),
      start_date: formatDateToISO(editForm.start_date),
      end_date: formatDateToISO(editForm.end_date)
    }

    await updateUiProject(currentEditId.value, projectData)
    ElMessage.success(t('uiAutomation.project.messages.updateSuccess'))
    showEditDialog.value = false
    resetEditForm()
    loadProjects()
  } catch (error) {
    ElMessage.error(t('uiAutomation.project.messages.updateFailed'))
    console.error('Failed to update project:', error)
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  if (!userStore.user?.id) {
    await userStore.fetchProfile()
  }
  await Promise.all([loadProjects(), loadUsers()])
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

.member-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.member-preview {
  color: #606266;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.member-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.global-variables-editor {
  width: 100%;
}

.resolution-row {
  width: 100%;
}

.resolution-item {
  margin-bottom: 0;
}

.global-variable-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr auto;
  gap: 8px;
  margin-bottom: 8px;
}

.global-variable-tags {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.global-variable-display {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.variable-description {
  color: #909399;
}

.form-tip,
.detail-tip {
  margin: 4px 0 18px;
  color: #909399;
  font-size: 13px;
  line-height: 1.6;
}

.empty-state {
  color: #909399;
  text-align: center;
  padding: 24px 0;
}
</style>
