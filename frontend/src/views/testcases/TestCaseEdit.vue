<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">{{ $t('testcase.edit') }}</h1>
    </div>

    <div class="card-container" v-if="!loading">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item :label="$t('testcase.caseTitle')" prop="title">
          <el-input v-model="form.title" :placeholder="$t('testcase.caseTitlePlaceholder')" />
        </el-form-item>

        <el-form-item :label="$t('testcase.caseDescription')" prop="description">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="4"
            :placeholder="$t('testcase.caseDescriptionPlaceholder')"
          />
        </el-form-item>

        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item :label="$t('testcase.project')" prop="project_id">
              <el-select
                v-model="form.project_id"
                :placeholder="$t('testcase.selectProject')"
                clearable
                filterable
                @change="onProjectChange"
              >
                <el-option
                  v-for="project in projects"
                  :key="project.id"
                  :label="project.name"
                  :value="project.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item :label="$t('testcase.folder')">
              <el-select
                v-model="form.folder_id"
                :placeholder="$t('testcase.selectFolder')"
                clearable
                filterable
                :disabled="!form.project_id"
              >
                <el-option
                  v-for="folder in projectFolders"
                  :key="folder.id"
                  :label="folder.name"
                  :value="folder.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item :label="$t('testcase.priority')" prop="priority">
              <el-select v-model="form.priority" :placeholder="$t('testcase.selectPriority')">
                <el-option :label="$t('testcase.low')" value="low" />
                <el-option :label="$t('testcase.medium')" value="medium" />
                <el-option :label="$t('testcase.high')" value="high" />
                <el-option :label="$t('testcase.critical')" value="critical" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item :label="$t('testcase.testType')" prop="test_type">
              <el-select v-model="form.test_type" :placeholder="$t('testcase.selectTestType')">
                <el-option :label="$t('testcase.functional')" value="functional" />
                <el-option :label="$t('testcase.integration')" value="integration" />
                <el-option :label="$t('testcase.api')" value="api" />
                <el-option :label="$t('testcase.ui')" value="ui" />
                <el-option :label="$t('testcase.performance')" value="performance" />
                <el-option :label="$t('testcase.security')" value="security" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="16">
            <el-form-item :label="$t('testcase.relatedVersions')">
              <el-select
                v-model="form.version_ids"
                :placeholder="$t('testcase.selectVersions')"
                multiple
                clearable
                filterable
              >
                <el-option
                  v-for="version in projectVersions"
                  :key="version.id"
                  :label="version.name + (version.is_baseline ? ' (' + $t('testcase.baseline') + ')' : '')"
                  :value="version.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item :label="$t('testcase.preconditions')" prop="preconditions">
          <el-input
            v-model="form.preconditions"
            type="textarea"
            :rows="3"
            :placeholder="$t('testcase.preconditionsPlaceholder')"
          />
        </el-form-item>

        <el-form-item :label="$t('testcase.steps')" prop="steps">
          <el-input
            v-model="form.steps"
            type="textarea"
            :rows="6"
            maxlength="1000"
            show-word-limit
            :placeholder="$t('testcase.stepsPlaceholder')"
          />
        </el-form-item>

        <el-form-item :label="$t('testcase.expectedResult')" prop="expected_result">
          <el-input
            v-model="form.expected_result"
            type="textarea"
            :rows="3"
            :placeholder="$t('testcase.expectedResultPlaceholder')"
          />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="handleSubmit" :loading="submitting">
            {{ $t('testcase.saveChanges') }}
          </el-button>
          <el-button @click="$router.back()">{{ $t('common.cancel') }}</el-button>
        </el-form-item>
      </el-form>
    </div>

    <div class="card-container" v-else>
      <el-skeleton :rows="10" animated />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'

import api from '@/utils/api'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const formRef = ref()
const loading = ref(true)
const submitting = ref(false)
const projects = ref([])
const projectVersions = ref([])
const projectFolders = ref([])

const form = reactive({
  title: '',
  description: '',
  project_id: null,
  folder_id: null,
  priority: 'medium',
  test_type: 'functional',
  preconditions: '',
  steps: '',
  expected_result: '',
  version_ids: []
})

const rules = {
  title: [
    { required: true, message: computed(() => t('testcase.titleRequired')), trigger: 'blur' },
    { min: 5, max: 500, message: computed(() => t('testcase.titleLength')), trigger: 'blur' }
  ],
  project_id: [
    { required: true, message: computed(() => t('testcase.projectRequired')), trigger: 'change' }
  ],
  expected_result: [
    { required: true, message: computed(() => t('testcase.expectedResultRequired')), trigger: 'blur' }
  ],
  steps: [
    { max: 1000, message: computed(() => t('testcase.stepsMaxLength')), trigger: 'blur' }
  ]
}

const normalizeListResponse = (response) => response.data.results || response.data || []

const convertBrToNewline = (text) => {
  if (!text) return ''
  return text.replace(/<br\s*\/?>/gi, '\n')
}

const convertNewlineToBr = (text) => {
  if (!text) return ''
  return text.replace(/\n/g, '<br>')
}

const fetchProjects = async () => {
  try {
    const response = await api.get('/projects/list/')
    projects.value = normalizeListResponse(response)
  } catch (error) {
    ElMessage.error(t('testcase.fetchProjectsFailed'))
  }
}

const fetchProjectVersions = async (projectId) => {
  if (!projectId) {
    projectVersions.value = []
    return
  }

  try {
    const response = await api.get(`/versions/projects/${projectId}/versions/`)
    projectVersions.value = response.data || []
  } catch (error) {
    projectVersions.value = []
    ElMessage.error(t('testcase.fetchVersionsFailed'))
  }
}

const fetchProjectFolders = async (projectId) => {
  if (!projectId) {
    projectFolders.value = []
    return
  }

  try {
    const response = await api.get('/testcases/folders/', { params: { project: projectId } })
    projectFolders.value = normalizeListResponse(response)
  } catch (error) {
    projectFolders.value = []
    ElMessage.error(t('testcase.fetchFoldersFailed'))
  }
}

const onProjectChange = async (projectId) => {
  form.version_ids = []
  form.folder_id = null
  await Promise.all([
    fetchProjectVersions(projectId),
    fetchProjectFolders(projectId)
  ])
}

const fetchTestCase = async () => {
  try {
    const response = await api.get(`/testcases/${route.params.id}/`)
    const testcase = response.data

    form.title = testcase.title
    form.description = testcase.description
    form.project_id = testcase.project?.id || null
    form.folder_id = testcase.folder_id ?? null
    form.priority = testcase.priority
    form.test_type = testcase.test_type
    form.preconditions = convertBrToNewline(testcase.preconditions || '')
    form.expected_result = convertBrToNewline(testcase.expected_result || '')
    form.steps = convertBrToNewline(testcase.steps || '')
    form.version_ids = testcase.versions ? testcase.versions.map(version => version.id) : []

    if (form.project_id) {
      await Promise.all([
        fetchProjectVersions(form.project_id),
        fetchProjectFolders(form.project_id)
      ])
    }

    loading.value = false
  } catch (error) {
    ElMessage.error(t('testcase.fetchDetailFailed'))
    router.back()
  }
}

const handleSubmit = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    submitting.value = true
    try {
      const submitData = {
        ...form,
        preconditions: convertNewlineToBr(form.preconditions || ''),
        steps: convertNewlineToBr(form.steps || ''),
        expected_result: convertNewlineToBr(form.expected_result || '')
      }

      await api.put(`/testcases/${route.params.id}/`, submitData)
      ElMessage.success(t('testcase.updateSuccess'))
      router.push(`/ai-generation/testcases/${route.params.id}`)
    } catch (error) {
      ElMessage.error(t('testcase.updateFailed'))
      console.error('Submit error:', error)
    } finally {
      submitting.value = false
    }
  })
}

onMounted(async () => {
  await fetchProjects()
  await fetchTestCase()
})
</script>
