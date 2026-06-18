<template>
  <div class="page-graph-manager">
    <div class="toolbar">
      <div class="toolbar-left">
        <el-select
          v-model="selectedProjectId"
          placeholder="选择UI项目"
          filterable
          class="project-select"
          @change="handleProjectChange"
        >
          <el-option
            v-for="project in projects"
            :key="project.id"
            :label="project.name"
            :value="project.id"
          />
        </el-select>
        <el-input
          v-model="searchText"
          placeholder="输入功能描述检索图谱路径和元素"
          clearable
          class="search-input"
          @keyup.enter="handleSearch"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-button :disabled="!selectedProjectId" @click="handleSearch">
          <el-icon><Search /></el-icon>
          检索
        </el-button>
      </div>
      <div class="toolbar-right">
        <el-button :disabled="!selectedProjectId" @click="openCrawlDialog()">
          <el-icon><Refresh /></el-icon>
          爬取页面结构
        </el-button>
        <el-button type="primary" :disabled="!currentGraph" @click="openCrawlDialog(currentGraph)">
          <el-icon><RefreshRight /></el-icon>
          重新爬取
        </el-button>
      </div>
    </div>

    <el-row :gutter="16" class="summary-row">
      <el-col :span="6">
        <div class="metric">
          <div class="metric-value">{{ currentGraph?.summary?.pages || currentGraph?.node_count || 0 }}</div>
          <div class="metric-label">页面节点</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="metric">
          <div class="metric-value">{{ currentGraph?.summary?.elements || currentGraph?.element_count || 0 }}</div>
          <div class="metric-label">页面元素</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="metric">
          <div class="metric-value">{{ currentGraph?.summary?.edges || currentGraph?.edge_count || 0 }}</div>
          <div class="metric-label">操作路径</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="metric">
          <div class="metric-value metric-status">
            <el-tag v-if="currentGraph" :type="coverageType(currentGraph)" effect="plain">{{ coverageText(currentGraph) }}</el-tag>
            <span v-else>-</span>
          </div>
          <div class="metric-label">覆盖状态</div>
        </div>
      </el-col>
    </el-row>

    <el-table
      :data="graphs"
      v-loading="graphLoading"
      class="graph-table"
      height="260"
      highlight-current-row
      @current-change="selectGraph"
    >
      <el-table-column prop="name" label="图谱名称" min-width="220" show-overflow-tooltip />
      <el-table-column prop="status" label="状态" width="110">
        <template #default="{ row }">
          <el-tooltip
            v-if="row.error_message || row.progress?.error_message || row.progress?.last_error"
            :content="row.error_message || row.progress?.error_message || row.progress?.last_error"
            placement="top"
          >
            <el-tag :type="statusType(row.status)">{{ statusText(row.status) }}</el-tag>
          </el-tooltip>
          <el-tag v-else :type="statusType(row.status)">{{ statusText(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="start_url" label="起始地址" min-width="260" show-overflow-tooltip />
      <el-table-column label="规模" width="180">
        <template #default="{ row }">
          {{ row.node_count || row.summary?.pages || 0 }} 页 /
          {{ row.element_count || row.summary?.elements || 0 }} 元素 /
          {{ row.edge_count || row.summary?.edges || 0 }} 路径
        </template>
      </el-table-column>
      <el-table-column label="覆盖" width="170">
        <template #default="{ row }">
          <el-tooltip :content="coverageMessage(row)" placement="top">
            <el-tag :type="coverageType(row)" effect="plain">{{ coverageText(row) }}</el-tag>
          </el-tooltip>
        </template>
      </el-table-column>
      <el-table-column label="进度" min-width="280" show-overflow-tooltip>
        <template #default="{ row }">
          <div class="progress-cell">
            <span>
              {{ progressVisited(row) }}/{{ progressDiscovered(row) }} 状态
              <span v-if="progressPending(row) > 0">· 待展开 {{ progressPending(row) }}</span>
              <span v-else>· 队列已清空</span>
              · {{ row.progress?.clicked_count || 0 }}/{{ row.progress?.max_actions || row.crawl_config?.max_actions || '-' }} 操作
            </span>
            <span class="progress-url">{{ coverageMessage(row) || row.error_message || row.progress?.error_message || row.progress?.last_error || row.progress?.current_url || '' }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="completed_at" label="完成时间" width="180">
        <template #default="{ row }">{{ formatTime(row.completed_at || row.updated_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="270" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click.stop="openCrawlDialog(row)">更新</el-button>
          <el-button
            v-if="canResumeGraph(row)"
            size="small"
            type="primary"
            @click.stop="openCrawlDialog(row, 'resume')"
          >
            继续
          </el-button>
          <el-button
            v-if="['pending', 'running'].includes(row.status)"
            size="small"
            type="warning"
            @click.stop="handleCancelGraph(row)"
          >
            取消
          </el-button>
          <el-button size="small" type="danger" @click.stop="handleDeleteGraph(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-tabs v-model="activeTab" class="detail-tabs" @tab-change="loadGraphDetails">
      <el-tab-pane label="Graph" name="graph">
        <div class="graph-canvas" v-loading="detailLoading">
          <div v-for="node in graphNodes" :key="node.id" class="graph-node">
            <div class="graph-node-header">
              <div class="graph-node-title">{{ node.title || node.path || node.url }}</div>
              <el-button size="small" text type="primary" @click="openEditDrawer('node', node)">编辑</el-button>
            </div>
            <div class="graph-node-path">{{ node.path || node.url }}</div>
            <div class="graph-node-section">
              <div class="graph-node-section-title">元素</div>
              <div class="graph-chip-list">
                <button
                  v-for="element in node.elements.slice(0, 12)"
                  :key="element.id"
                  class="graph-chip"
                  type="button"
                  @click="openEditDrawer('element', element)"
                >
                  {{ element.name }}
                </button>
                <span v-if="node.elements.length > 12" class="graph-more">+{{ node.elements.length - 12 }}</span>
              </div>
            </div>
            <div class="graph-node-section">
              <div class="graph-node-section-title">路径</div>
              <div class="graph-edge-list">
                <button
                  v-for="edge in node.edges"
                  :key="edge.id"
                  class="graph-edge"
                  type="button"
                  @click="openEditDrawer('edge', edge)"
                >
                  <span>{{ edge.trigger_text || edge.locator_value || 'click' }}</span>
                  <span>-> {{ edge.target_title || edge.target_path }}</span>
                </button>
                <span v-if="!node.edges.length" class="graph-empty">无出口</span>
              </div>
            </div>
          </div>
          <el-empty v-if="!graphNodes.length && !detailLoading" description="暂无图谱节点" />
        </div>
      </el-tab-pane>
      <el-tab-pane label="检索结果" name="search">
        <el-table :data="searchResults" v-loading="searchLoading" height="360">
          <el-table-column prop="kind" label="类型" width="100">
            <template #default="{ row }">
              <el-tag size="small" :type="resultType(row.kind)">{{ resultKindText(row.kind) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="命中内容" min-width="260" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-if="row.kind === 'edge'">{{ row.source }} -> {{ row.target }}</span>
              <span v-else-if="row.kind === 'element'">{{ row.page }} / {{ row.name }}</span>
              <span v-else>{{ row.title || row.path }}</span>
            </template>
          </el-table-column>
          <el-table-column label="定位/触发" min-width="320" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-if="row.kind === 'page'">{{ row.url }}</span>
              <span v-else>{{ row.trigger_text || row.name }} {{ row.locator_strategy }}={{ row.locator_value }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="score" label="分数" width="80" />
        </el-table>
      </el-tab-pane>
      <el-tab-pane label="页面节点" name="nodes">
        <el-table :data="nodes" v-loading="detailLoading" height="360">
          <el-table-column prop="title" label="页面标题" min-width="220" show-overflow-tooltip />
          <el-table-column prop="path" label="路径" min-width="220" show-overflow-tooltip />
          <el-table-column prop="url" label="URL" min-width="300" show-overflow-tooltip />
          <el-table-column prop="element_count" label="元素" width="90" />
          <el-table-column prop="outgoing_count" label="出口" width="90" />
        </el-table>
      </el-tab-pane>
      <el-tab-pane label="页面元素" name="elements">
        <el-table :data="elements" v-loading="detailLoading" height="360">
          <el-table-column prop="page_title" label="页面" min-width="180" show-overflow-tooltip />
          <el-table-column prop="name" label="元素" min-width="180" show-overflow-tooltip />
          <el-table-column prop="element_type" label="类型" width="100" />
          <el-table-column label="唯一/稳定" width="110">
            <template #default="{ row }">
              <el-tag v-if="row.is_unique" size="small" type="success">唯一</el-tag>
              <el-tag v-if="row.is_stable" size="small" type="primary">稳定</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="定位器" min-width="360" show-overflow-tooltip>
            <template #default="{ row }">{{ row.locator_strategy }}={{ row.locator_value }}</template>
          </el-table-column>
          <el-table-column prop="platform_element_id" label="元素库ID" width="100" />
        </el-table>
      </el-tab-pane>
      <el-tab-pane label="操作路径" name="edges">
        <el-table :data="edges" v-loading="detailLoading" height="360">
          <el-table-column label="来源" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">{{ row.source_title || row.source_path }}</template>
          </el-table-column>
          <el-table-column prop="trigger_text" label="操作" min-width="160" show-overflow-tooltip />
          <el-table-column label="目标" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">{{ row.target_title || row.target_path }}</template>
          </el-table-column>
          <el-table-column label="定位器" min-width="320" show-overflow-tooltip>
            <template #default="{ row }">{{ row.locator_strategy }}={{ row.locator_value }}</template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <el-dialog
      v-model="crawlDialogVisible"
      :title="crawlDialogTitle"
      width="720px"
      :close-on-click-modal="false"
    >
      <el-form :model="crawlForm" label-width="120px">
        <el-form-item label="图谱名称">
          <el-input v-model="crawlForm.name" placeholder="例如：生产环境页面图谱" />
        </el-form-item>
        <el-form-item label="起始地址">
          <el-input v-model="crawlForm.start_url" placeholder="默认使用项目基础URL" />
        </el-form-item>
        <el-form-item label="登录地址">
          <el-input v-model="crawlForm.login_url" placeholder="默认使用起始地址" />
        </el-form-item>
        <el-form-item label="附加入口">
          <el-input
            v-model="crawlForm.extra_start_urls"
            type="textarea"
            :rows="3"
            placeholder="可填写管理模式、工作台等补充入口地址，一行一个 URL"
          />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="账号">
              <el-input v-model="crawlForm.username" autocomplete="off" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="密码">
              <el-input v-model="crawlForm.password" type="password" show-password autocomplete="off" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="最大页面数">
              <el-input-number v-model="crawlForm.max_pages" :min="1" :max="1000" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="最大深度">
              <el-input-number v-model="crawlForm.max_depth" :min="1" :max="10" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="最大操作数">
              <el-input-number v-model="crawlForm.max_actions" :min="1" :max="10000" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="单页操作数">
              <el-input-number v-model="crawlForm.max_actions_per_page" :min="1" :max="300" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="运行时长">
              <el-input-number v-model="crawlForm.timeout_minutes" :min="1" :max="1440" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="失败重试">
              <el-input-number v-model="crawlForm.retry_count" :min="0" :max="5" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="高级定位">
          <el-input v-model="crawlForm.username_selector" placeholder="账号输入框CSS，可选" class="selector-input" />
          <el-input v-model="crawlForm.password_selector" placeholder="密码输入框CSS，可选" class="selector-input" />
          <el-input v-model="crawlForm.submit_selector" placeholder="登录按钮CSS，可选" />
        </el-form-item>
        <el-form-item label="选项">
          <el-checkbox v-model="crawlForm.headless">无头浏览器</el-checkbox>
          <el-checkbox v-model="crawlForm.sync_elements">同步唯一元素到元素库</el-checkbox>
          <el-checkbox v-model="crawlForm.allow_destructive_actions">允许点击危险操作</el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="crawlDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="crawlLoading" @click="submitCrawl">开始</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="editDrawerVisible" :title="editDrawerTitle" size="520px">
      <el-form :model="editForm" label-width="110px">
        <template v-if="editType === 'node'">
          <el-form-item label="页面标题">
            <el-input v-model="editForm.title" />
          </el-form-item>
          <el-form-item label="页面路径">
            <el-input v-model="editForm.path" />
          </el-form-item>
          <el-form-item label="关键词">
            <el-select v-model="editForm.keywords" multiple filterable allow-create default-first-option />
          </el-form-item>
          <el-form-item label="页面文本">
            <el-input v-model="editForm.page_text" type="textarea" :rows="6" />
          </el-form-item>
        </template>
        <template v-else-if="editType === 'element'">
          <el-form-item label="元素名称">
            <el-input v-model="editForm.name" />
          </el-form-item>
          <el-form-item label="元素类型">
            <el-input v-model="editForm.element_type" />
          </el-form-item>
          <el-form-item label="定位策略">
            <el-select v-model="editForm.locator_strategy" filterable allow-create>
              <el-option v-for="item in locatorStrategyOptions" :key="item" :label="item" :value="item" />
            </el-select>
          </el-form-item>
          <el-form-item label="定位表达式">
            <el-input v-model="editForm.locator_value" type="textarea" :rows="4" />
          </el-form-item>
          <el-form-item label="关键词">
            <el-select v-model="editForm.action_keywords" multiple filterable allow-create default-first-option />
          </el-form-item>
          <el-form-item label="状态">
            <el-checkbox v-model="editForm.is_unique">唯一</el-checkbox>
            <el-checkbox v-model="editForm.is_stable">稳定</el-checkbox>
          </el-form-item>
        </template>
        <template v-else-if="editType === 'edge'">
          <el-form-item label="操作文本">
            <el-input v-model="editForm.trigger_text" />
          </el-form-item>
          <el-form-item label="动作类型">
            <el-input v-model="editForm.action_type" />
          </el-form-item>
          <el-form-item label="定位策略">
            <el-select v-model="editForm.locator_strategy" filterable allow-create>
              <el-option v-for="item in locatorStrategyOptions" :key="item" :label="item" :value="item" />
            </el-select>
          </el-form-item>
          <el-form-item label="定位表达式">
            <el-input v-model="editForm.locator_value" type="textarea" :rows="4" />
          </el-form-item>
          <el-form-item label="关键词">
            <el-select v-model="editForm.keywords" multiple filterable allow-create default-first-option />
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="editDrawerVisible = false">取消</el-button>
        <el-button type="primary" :loading="editSaving" @click="saveGraphItem">保存</el-button>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, RefreshRight, Search } from '@element-plus/icons-vue'
import {
  cancelUIPageGraph,
  crawlUIPageGraph,
  deleteUIPageGraph,
  getUIPageGraphDetail,
  getUIPageGraphEdges,
  getUIPageGraphElements,
  getUIPageGraphNodes,
  getUIPageGraphs,
  getUiProjects,
  recrawlUIPageGraph,
  resumeUIPageGraph,
  searchUIPageGraph,
  updateUIPageGraphEdge,
  updateUIPageGraphElement,
  updateUIPageGraphNode
} from '@/api/ui_automation'
import { useUiAutomationStore } from '@/stores/uiAutomation'

const uiStore = useUiAutomationStore()
const projects = ref([])
const selectedProjectId = ref(uiStore.selectedProjectId ? Number(uiStore.selectedProjectId) : null)
const graphs = ref([])
const currentGraph = ref(null)
const graphLoading = ref(false)
const detailLoading = ref(false)
const crawlLoading = ref(false)
const editSaving = ref(false)
const searchLoading = ref(false)
const crawlDialogVisible = ref(false)
const editDrawerVisible = ref(false)
const activeTab = ref('graph')
const searchText = ref('')
const searchResults = ref([])
const nodes = ref([])
const elements = ref([])
const edges = ref([])
const editType = ref('')
const editId = ref(null)
let graphPollTimer = null
let detailRequestSeq = 0
const loadedDetailKey = ref('')
const locatorStrategyOptions = ['test-id', 'ID', 'name', 'CSS', 'XPath', 'text', 'placeholder', 'title', 'role', 'label']

const selectedProject = computed(() => projects.value.find((item) => String(item.id) === String(selectedProjectId.value)))
const editDrawerTitle = computed(() => {
  return {
    node: '编辑页面节点',
    element: '编辑页面元素',
    edge: '编辑操作路径'
  }[editType.value] || '编辑图谱'
})
const crawlDialogTitle = computed(() => {
  if (crawlForm.mode === 'resume') return '继续爬取页面图谱'
  return crawlForm.graph_id ? '重新爬取页面图谱' : '爬取页面图谱'
})
const graphNodes = computed(() => {
  const elementMap = new Map()
  const edgeMap = new Map()
  elements.value.forEach((item) => {
    const list = elementMap.get(item.page_node) || []
    list.push(item)
    elementMap.set(item.page_node, list)
  })
  edges.value.forEach((item) => {
    const list = edgeMap.get(item.source) || []
    list.push(item)
    edgeMap.set(item.source, list)
  })
  return nodes.value.map((node) => ({
    ...node,
    elements: elementMap.get(node.id) || [],
    edges: edgeMap.get(node.id) || []
  }))
})

const editForm = reactive({
  title: '',
  path: '',
  page_text: '',
  keywords: [],
  name: '',
  element_type: '',
  locator_strategy: '',
  locator_value: '',
  action_keywords: [],
  is_unique: false,
  is_stable: false,
  trigger_text: '',
  action_type: ''
})

const crawlForm = reactive({
  mode: 'crawl',
  graph_id: null,
  project: null,
  name: '',
  start_url: '',
  login_url: '',
  extra_start_urls: '',
  username: '',
  password: '',
  username_selector: '',
  password_selector: '',
  submit_selector: '',
  max_pages: 30,
  max_depth: 3,
  max_actions: 1000,
  max_actions_per_page: 80,
  timeout_minutes: 180,
  retry_count: 1,
  allow_destructive_actions: false,
  headless: true,
  sync_elements: true
})

onMounted(async () => {
  await loadProjects()
  if (selectedProjectId.value) {
    await loadGraphs()
  }
})

onBeforeUnmount(() => {
  stopGraphPolling()
})

async function loadProjects() {
  const response = await getUiProjects({ page_size: 1000 })
  projects.value = response.data?.results || response.data || []
  if (!selectedProjectId.value && projects.value.length) {
    selectedProjectId.value = projects.value[0].id
    uiStore.setSelectedProject(selectedProjectId.value)
  }
}

async function handleProjectChange(projectId) {
  uiStore.setSelectedProject(projectId)
  currentGraph.value = null
  activeTab.value = 'graph'
  clearGraphDetails()
  await loadGraphs()
}

async function loadGraphs() {
  if (!selectedProjectId.value) return
  graphLoading.value = true
  try {
    const response = await getUIPageGraphs({ project: selectedProjectId.value, page_size: 50 })
    graphs.value = response.data?.results || response.data || []
    const previousId = currentGraph.value?.id
    const nextGraph = graphs.value.find((item) => item.id === previousId)
      || graphs.value.find((item) => item.status === 'running')
      || graphs.value.find((item) => item.status === 'completed')
      || graphs.value[0]
      || null
    if (currentGraph.value?.id !== nextGraph?.id) {
      clearGraphDetails()
    }
    currentGraph.value = nextGraph
    if (currentGraph.value) {
      await loadGraphDetails({ force: true })
    }
    if (searchText.value) {
      await handleSearch()
    } else {
      activeTab.value = 'graph'
    }
    refreshGraphPolling()
  } finally {
    graphLoading.value = false
  }
}

async function refreshGraphsSilently() {
  if (!selectedProjectId.value) return
  const response = await getUIPageGraphs({ project: selectedProjectId.value, page_size: 50 })
  graphs.value = response.data?.results || response.data || []
  if (currentGraph.value?.id) {
    currentGraph.value = graphs.value.find((item) => item.id === currentGraph.value.id) || currentGraph.value
  }
  refreshGraphPolling()
}

function refreshGraphPolling() {
  const hasRunning = graphs.value.some((item) => ['pending', 'running'].includes(item.status))
  if (hasRunning) {
    startGraphPolling()
  } else {
    stopGraphPolling()
  }
}

function startGraphPolling() {
  if (graphPollTimer) return
  graphPollTimer = window.setInterval(() => {
    refreshGraphsSilently().catch(() => {})
  }, 5000)
}

function stopGraphPolling() {
  if (!graphPollTimer) return
  window.clearInterval(graphPollTimer)
  graphPollTimer = null
}

function selectGraph(row) {
  if (!row) return
  if (currentGraph.value?.id !== row.id) {
    clearGraphDetails()
  }
  currentGraph.value = row
  loadGraphDetails({ force: true })
}

function clearGraphDetails() {
  searchResults.value = []
  nodes.value = []
  elements.value = []
  edges.value = []
  loadedDetailKey.value = ''
}

function responseRows(response) {
  return response.data?.results || response.data || []
}

async function loadGraphDetails(options = {}) {
  if (!currentGraph.value) return
  const graphId = currentGraph.value.id
  const mode = activeTab.value
  if (mode === 'search') {
    if (searchText.value) {
      await handleSearch()
    }
    return
  }
  const detailKey = `${graphId}:${mode}`
  if (!options.force && loadedDetailKey.value === detailKey) return
  const requestSeq = ++detailRequestSeq
  detailLoading.value = true
  try {
    if (mode === 'graph') {
      const detailRes = await getUIPageGraphDetail(graphId, {
        mode: 'overview',
        node_limit: 300,
        element_per_node: 12,
        edge_per_node: 30
      })
      if (requestSeq !== detailRequestSeq) return
      nodes.value = detailRes.data?.nodes || []
      elements.value = detailRes.data?.elements || []
      edges.value = detailRes.data?.edges || []
      loadedDetailKey.value = detailKey
      return
    }
    const params = { graph: graphId, page_size: 1000 }
    if (mode === 'nodes') {
      const response = await getUIPageGraphNodes(params)
      if (requestSeq !== detailRequestSeq) return
      nodes.value = responseRows(response)
      loadedDetailKey.value = detailKey
      return
    }
    if (mode === 'elements') {
      const response = await getUIPageGraphElements(params)
      if (requestSeq !== detailRequestSeq) return
      elements.value = responseRows(response)
      loadedDetailKey.value = detailKey
      return
    }
    if (mode === 'edges') {
      const response = await getUIPageGraphEdges(params)
      if (requestSeq !== detailRequestSeq) return
      edges.value = responseRows(response)
      loadedDetailKey.value = detailKey
    }
  } finally {
    if (requestSeq === detailRequestSeq) {
      detailLoading.value = false
    }
  }
}

async function handleSearch() {
  if (!selectedProjectId.value) return
  searchLoading.value = true
  activeTab.value = 'search'
  try {
    const response = await searchUIPageGraph({
      project: selectedProjectId.value,
      graph_id: currentGraph.value?.id,
      query: searchText.value,
      limit: 120
    })
    searchResults.value = response.data?.results || []
  } finally {
    searchLoading.value = false
  }
}

function openCrawlDialog(graph = null, mode = 'recrawl') {
  const project = selectedProject.value
  const isResume = mode === 'resume'
  const savedConfig = graph?.crawl_config || {}
  const savedProgress = graph?.progress || {}
  crawlForm.mode = graph ? mode : 'crawl'
  crawlForm.graph_id = graph?.id || null
  crawlForm.project = selectedProjectId.value
  crawlForm.name = graph ? (isResume ? graph.name : `${graph.name}-更新`) : `${project?.name || 'UI项目'}页面图谱`
  crawlForm.start_url = graph?.start_url || project?.base_url || ''
  crawlForm.login_url = graph?.login_url || graph?.start_url || project?.base_url || ''
  crawlForm.extra_start_urls = Array.isArray(savedConfig.extra_start_urls)
    ? savedConfig.extra_start_urls.join('\n')
    : (savedConfig.extra_start_urls || '')
  crawlForm.username = savedConfig.username || ''
  crawlForm.password = savedConfig.password || ''
  crawlForm.username_selector = savedConfig.username_selector || ''
  crawlForm.password_selector = savedConfig.password_selector || ''
  crawlForm.submit_selector = savedConfig.submit_selector || ''
  crawlForm.max_pages = savedConfig.max_pages || savedProgress.max_pages || 30
  crawlForm.max_depth = savedConfig.max_depth || savedProgress.max_depth || 3
  crawlForm.max_actions = savedConfig.max_actions || savedProgress.max_actions || 1000
  crawlForm.max_actions_per_page = savedConfig.max_actions_per_page || savedProgress.max_actions_per_page || 80
  crawlForm.timeout_minutes = savedConfig.timeout_minutes || savedProgress.timeout_minutes || 180
  crawlForm.retry_count = savedConfig.retry_count ?? 1
  crawlForm.allow_destructive_actions = savedConfig.allow_destructive_actions ?? false
  crawlForm.headless = savedConfig.headless ?? true
  crawlForm.sync_elements = savedConfig.sync_elements ?? true
  crawlDialogVisible.value = true
}

async function submitCrawl() {
  if (!selectedProjectId.value) return
  crawlLoading.value = true
  try {
    const payload = { ...crawlForm, project: selectedProjectId.value }
    let response
    if (crawlForm.mode === 'resume' && crawlForm.graph_id) {
      response = await resumeUIPageGraph(crawlForm.graph_id, payload)
    } else if (crawlForm.graph_id) {
      response = await recrawlUIPageGraph(crawlForm.graph_id, payload)
    } else {
      response = await crawlUIPageGraph(payload)
    }
    ElMessage.success(response.data?.message || '页面图谱爬取任务已提交')
    crawlDialogVisible.value = false
    await loadGraphs()
    startGraphPolling()
    activeTab.value = 'graph'
  } catch (error) {
    const message = error.response?.data?.error || error.response?.data?.detail || '页面图谱爬取失败'
    ElMessage.error(message)
  } finally {
    crawlLoading.value = false
  }
}

async function handleDeleteGraph(graph) {
  if (!graph?.id) return
  try {
    await ElMessageBox.confirm(
      `确认删除页面图谱“${graph.name}”？删除后会同时删除节点、元素和路径。`,
      '删除页面图谱',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
    const response = await deleteUIPageGraph(graph.id)
    ElMessage.success(response.data?.message || '页面图谱已删除')
    if (currentGraph.value?.id === graph.id) {
      currentGraph.value = null
      nodes.value = []
      elements.value = []
      edges.value = []
      searchResults.value = []
    }
    await loadGraphs()
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(error.response?.data?.detail || error.response?.data?.error || '页面图谱删除失败')
  }
}

async function handleCancelGraph(graph) {
  if (!graph?.id) return
  try {
    await ElMessageBox.confirm(
      `确认取消页面图谱“${graph.name}”的爬取任务？已爬取的数据会保留。`,
      '取消爬取',
      { type: 'warning', confirmButtonText: '取消爬取', cancelButtonText: '关闭' }
    )
    const response = await cancelUIPageGraph(graph.id)
    ElMessage.success(response.data?.message || '页面图谱爬取已取消')
    await loadGraphs()
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(error.response?.data?.detail || error.response?.data?.error || '取消页面图谱爬取失败')
  }
}

function resetEditForm() {
  Object.assign(editForm, {
    title: '',
    path: '',
    page_text: '',
    keywords: [],
    name: '',
    element_type: '',
    locator_strategy: '',
    locator_value: '',
    action_keywords: [],
    is_unique: false,
    is_stable: false,
    trigger_text: '',
    action_type: ''
  })
}

function openEditDrawer(type, item) {
  resetEditForm()
  editType.value = type
  editId.value = item.id
  if (type === 'node') {
    Object.assign(editForm, {
      title: item.title || '',
      path: item.path || '',
      page_text: item.page_text || '',
      keywords: Array.isArray(item.keywords) ? [...item.keywords] : []
    })
  } else if (type === 'element') {
    Object.assign(editForm, {
      name: item.name || '',
      element_type: item.element_type || '',
      locator_strategy: item.locator_strategy || '',
      locator_value: item.locator_value || '',
      action_keywords: Array.isArray(item.action_keywords) ? [...item.action_keywords] : [],
      is_unique: Boolean(item.is_unique),
      is_stable: Boolean(item.is_stable)
    })
  } else if (type === 'edge') {
    Object.assign(editForm, {
      trigger_text: item.trigger_text || '',
      action_type: item.action_type || 'click',
      locator_strategy: item.locator_strategy || '',
      locator_value: item.locator_value || '',
      keywords: Array.isArray(item.keywords) ? [...item.keywords] : []
    })
  }
  editDrawerVisible.value = true
}

function buildEditPayload() {
  if (editType.value === 'node') {
    return {
      title: editForm.title,
      path: editForm.path,
      page_text: editForm.page_text,
      keywords: editForm.keywords || []
    }
  }
  if (editType.value === 'element') {
    return {
      name: editForm.name,
      element_type: editForm.element_type,
      locator_strategy: editForm.locator_strategy,
      locator_value: editForm.locator_value,
      action_keywords: editForm.action_keywords || [],
      is_unique: Boolean(editForm.is_unique),
      is_stable: Boolean(editForm.is_stable)
    }
  }
  return {
    trigger_text: editForm.trigger_text,
    action_type: editForm.action_type || 'click',
    locator_strategy: editForm.locator_strategy,
    locator_value: editForm.locator_value,
    keywords: editForm.keywords || []
  }
}

async function saveGraphItem() {
  if (!editId.value || !editType.value) return
  editSaving.value = true
  try {
    const payload = buildEditPayload()
    if (editType.value === 'node') {
      await updateUIPageGraphNode(editId.value, payload)
    } else if (editType.value === 'element') {
      await updateUIPageGraphElement(editId.value, payload)
    } else {
      await updateUIPageGraphEdge(editId.value, payload)
    }
    ElMessage.success('图谱已更新')
    editDrawerVisible.value = false
    await loadGraphDetails()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '图谱更新失败')
  } finally {
    editSaving.value = false
  }
}

function statusType(status) {
  return {
    completed: 'success',
    running: 'warning',
    failed: 'danger',
    pending: 'info',
    timeout: 'danger',
    cancelled: 'info'
  }[status] || 'info'
}

function statusText(status) {
  return {
    completed: '已完成',
    running: '运行中',
    failed: '失败',
    pending: '等待中',
    timeout: '已超时',
    cancelled: '已取消'
  }[status] || status
}

function graphCoverage(row) {
  if (row?.progress?.coverage_status || row?.progress?.pending_state_count !== undefined) return row.progress
  return row?.summary?.coverage || row?.crawl_state?.coverage || row?.progress || {}
}

function progressDiscovered(row) {
  const coverage = graphCoverage(row)
  return Number(coverage.discovered_state_count ?? row?.node_count ?? row?.summary?.pages ?? 0)
}

function progressVisited(row) {
  const coverage = graphCoverage(row)
  const visited = Number(coverage.visited_state_count ?? coverage.visited_count ?? 0)
  if (visited > 0) return visited
  if (row?.status === 'completed' && progressPending(row) === 0) {
    return progressDiscovered(row)
  }
  return visited
}

function progressPending(row) {
  const coverage = graphCoverage(row)
  const pending = coverage.pending_state_count ?? coverage.queued_count
  if (pending !== undefined && pending !== null) return Math.max(0, Number(pending) || 0)
  return Math.max(0, progressDiscovered(row) - Number(coverage.visited_state_count || 0))
}

function coverageStatus(row) {
  const coverage = graphCoverage(row)
  if (coverage.coverage_status) return coverage.coverage_status
  if (['failed'].includes(row?.status)) return 'failed'
  if (['timeout', 'cancelled'].includes(row?.status)) return 'incomplete'
  if (row?.status === 'running') return 'running'
  if (row?.status === 'completed') return progressPending(row) > 0 ? 'incomplete' : 'unknown'
  return 'unknown'
}

function coverageType(row) {
  return {
    complete: 'success',
    limited: 'warning',
    incomplete: 'warning',
    running: 'primary',
    failed: 'danger',
    unknown: 'info'
  }[coverageStatus(row)] || 'info'
}

function coverageText(row) {
  return {
    complete: '覆盖完成',
    limited: '达到上限',
    incomplete: '可继续',
    running: '爬取中',
    failed: '覆盖失败',
    unknown: '待确认'
  }[coverageStatus(row)] || '待确认'
}

function coverageMessage(row) {
  const coverage = graphCoverage(row)
  if (coverage.coverage_message) return coverage.coverage_message
  if (row?.error_message || coverage.error_message || coverage.last_error) {
    return row?.error_message || coverage.error_message || coverage.last_error
  }
  const pending = progressPending(row)
  if (coverageStatus(row) === 'incomplete' && pending > 0) {
    return `仍有 ${pending} 个已发现状态未展开，建议继续爬取`
  }
  if (coverageStatus(row) === 'limited') {
    return '已达到页面数或操作数上限，可能仍有页面未爬取'
  }
  if (coverageStatus(row) === 'complete') {
    return '待展开队列已清空，未触达上限'
  }
  return row?.progress?.current_url || ''
}

function canResumeGraph(row) {
  return ['failed', 'timeout', 'cancelled'].includes(row?.status)
    || row?.status === 'completed'
    || progressPending(row) > 0
}

function resultType(kind) {
  return {
    page: 'info',
    edge: 'warning',
    element: 'success'
  }[kind] || 'info'
}

function resultKindText(kind) {
  return {
    page: '页面',
    edge: '路径',
    element: '元素'
  }[kind] || kind
}

function formatTime(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}
</script>

<style scoped>
.page-graph-manager {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.project-select {
  width: 240px;
}

.search-input {
  width: 360px;
}

.summary-row {
  margin: 0;
}

.metric {
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 14px 16px;
  background: #fff;
}

.metric-value {
  font-size: 24px;
  font-weight: 700;
  line-height: 1.2;
  color: #1f2937;
}

.metric-label {
  margin-top: 4px;
  font-size: 13px;
  color: #6b7280;
}

.metric-status {
  display: flex;
  align-items: center;
  min-height: 29px;
}

.graph-table,
.detail-tabs {
  background: #fff;
}

.progress-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  font-size: 12px;
  line-height: 1.35;
}

.progress-url {
  overflow: hidden;
  color: #6b7280;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.graph-canvas {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 12px;
  min-height: 360px;
  max-height: 520px;
  overflow: auto;
  padding: 12px;
  border: 1px solid #e5e7eb;
}

.graph-node {
  min-width: 0;
  border: 1px solid #d8dee8;
  border-radius: 6px;
  background: #fff;
  padding: 12px;
}

.graph-node-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.graph-node-title {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 600;
  color: #1f2937;
}

.graph-node-path {
  margin-top: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  color: #6b7280;
}

.graph-node-section {
  margin-top: 10px;
}

.graph-node-section-title {
  margin-bottom: 6px;
  font-size: 12px;
  font-weight: 600;
  color: #374151;
}

.graph-chip-list,
.graph-edge-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.graph-chip,
.graph-edge {
  max-width: 100%;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  background: #f9fafb;
  color: #374151;
  cursor: pointer;
  font-size: 12px;
}

.graph-chip {
  height: 26px;
  padding: 0 8px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.graph-edge {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  min-height: 28px;
  padding: 5px 8px;
  text-align: left;
}

.graph-chip:hover,
.graph-edge:hover {
  border-color: #409eff;
  color: #1d4ed8;
}

.graph-more,
.graph-empty {
  font-size: 12px;
  color: #6b7280;
}

.selector-input {
  margin-bottom: 8px;
}
</style>

