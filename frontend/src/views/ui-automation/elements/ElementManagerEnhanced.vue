<template>
  <div class="element-manager">
    <div class="element-layout">
      <!-- 宸︿晶椤甸潰鏍?-->
      <div class="sidebar" :style="{ width: `${sidebarWidth}px` }">
        <div class="sidebar-header">
          <el-select v-model="selectedProject" :placeholder="$t('common.selectProject')" @change="onProjectChange">
            <el-option
              v-for="project in projects"
              :key="project.id"
              :label="project.name"
              :value="project.id"
            />
          </el-select>
          <div class="header-actions">
            <el-button type="primary" size="small" @click="showCreatePageDialog = true" :title="$t('uiAutomation.element.createPage')">
              <el-icon><Folder /></el-icon>
            </el-button>
            <el-button type="success" size="small" @click="createEmptyElement" :title="$t('uiAutomation.element.addElement')">
              <el-icon><Plus /></el-icon>
            </el-button>
          </div>
        </div>

        <div class="page-tree">
          <el-tree
            ref="treeRef"
            :key="treeKey"
            :data="treeData"
            :props="treeProps"
            node-key="treeKey"
            show-checkbox
            :default-checked-keys="checkedElementTreeKeys"
            :expand-on-click-node="false"
            :default-expanded-keys="expandedKeys"
            @check="handleTreeCheck"
            @node-click="onNodeClick"
            @node-contextmenu="onNodeRightClick"
            @node-expand="onNodeExpand"
            @node-collapse="onNodeCollapse"
          >
            <template #default="{ node, data }">
              <div class="tree-node">
                <el-icon v-if="data.type === 'page'">
                  <Folder />
                </el-icon>
                <el-icon v-else>
                  <Document />
                </el-icon>

                <!-- 椤甸潰鍚嶇О缂栬緫 -->
                <div v-if="data.type === 'page' && editingNodeId === data.id" class="node-edit">
                  <el-input
                    v-model="editingNodeName"
                    size="small"
                    @blur="savePageName"
                    @keyup.enter="savePageName"
                    @keyup.esc="cancelEdit"
                    ref="editInputRef"
                  />
                </div>

                <!-- 鏅€氭樉绀烘ā寮?-->
                <span v-else class="node-label">{{ node.label }}</span>

                <span v-if="data.type === 'element'" class="element-type-tag" :class="data.element_type?.toLowerCase()">
                  {{ getElementTypeLabel(data.element_type) }}
                </span>
              </div>
            </template>
          </el-tree>
        </div>
      </div>

      <div
        class="sidebar-resizer"
        role="separator"
        aria-orientation="vertical"
        tabindex="0"
        @mousedown="startSidebarResize"
        @keydown="handleSidebarResizeKeydown"
      />

      <!-- 鍙充晶鍏冪礌璇︽儏 -->
      <div class="main-content">
        <div class="content-toolbar">
          <el-button :disabled="!selectedProject" @click="openImportDialog">导入文件</el-button>
          <el-button :disabled="!selectedElementCount" @click="handleExportSelectedElement">导出选中元素</el-button>
          <el-button :disabled="!selectedProject" @click="handleExportAllElements">导出全部元素</el-button>
          <el-button :disabled="!selectedElementCount" @click="openTransferDialog('selected')">复制选中元素</el-button>
          <el-button :disabled="!selectedProject" @click="openTransferDialog('all')">复制全部元素</el-button>
        </div>
        <div v-if="!selectedElement" class="empty-state">
          <el-empty :description="$t('uiAutomation.element.emptyElementTip')">
            <el-button type="primary" @click="createEmptyElement">{{ $t('uiAutomation.element.createNewElement') }}</el-button>
          </el-empty>
        </div>

        <div v-else class="element-detail">
          <!-- 鍏冪礌鍩烘湰淇℃伅 -->
          <div class="element-header">
            <div class="element-info">
              <el-form ref="elementHeaderFormRef" :model="selectedElement" :rules="elementHeaderRules" inline>
                <el-form-item prop="name" :label="$t('uiAutomation.element.elementName')" required>
                  <el-input
                    v-model="selectedElement.name"
                    :placeholder="$t('uiAutomation.element.elementNamePlaceholder')"
                    style="width: 300px"
                    @blur="validateHeaderField('name')"
                  />
                </el-form-item>
                <el-form-item :label="$t('uiAutomation.element.elementType')">
                  <el-select v-model="selectedElement.element_type" :placeholder="$t('uiAutomation.element.elementType')" style="width: 120px;">
                    <el-option :label="$t('uiAutomation.element.elementTypes.button')" value="BUTTON" />
                    <el-option :label="$t('uiAutomation.element.elementTypes.input')" value="INPUT" />
                    <el-option :label="$t('uiAutomation.element.elementTypes.link')" value="LINK" />
                    <el-option :label="$t('uiAutomation.element.elementTypes.dropdown')" value="DROPDOWN" />
                    <el-option :label="$t('uiAutomation.element.elementTypes.checkbox')" value="CHECKBOX" />
                    <el-option :label="$t('uiAutomation.element.elementTypes.radio')" value="RADIO" />
                    <el-option :label="$t('uiAutomation.element.elementTypes.text')" value="TEXT" />
                    <el-option :label="$t('uiAutomation.element.elementTypes.image')" value="IMAGE" />
                    <el-option :label="$t('uiAutomation.element.elementTypes.table')" value="TABLE" />
                    <el-option :label="$t('uiAutomation.element.elementTypes.form')" value="FORM" />
                    <el-option :label="$t('uiAutomation.element.elementTypes.modal')" value="MODAL" />
                  </el-select>
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" @click="saveElement" :loading="saving" ref="saveButtonRef">
                    {{ $t('uiAutomation.common.save') }}
                  </el-button>
                </el-form-item>
              </el-form>
            </div>
          </div>

          <!-- 鍏冪礌閰嶇疆 -->
          <div class="element-form">
            <el-form ref="elementFormRef" :key="formKey" :model="selectedElement" :rules="elementRules" label-width="100px">
              <el-row :gutter="20">
                <el-col :span="12">
                  <el-form-item :label="$t('uiAutomation.element.page')">
                    <el-tree-select
                      v-model="selectedElement.group_id"
                      :data="pageTreeOptions"
                      :props="pageSelectProps"
                      node-key="id"
                      check-strictly
                      clearable
                      filterable
                      default-expand-all
                      :render-after-expand="false"
                      :placeholder="$t('uiAutomation.element.selectPage')"
                      style="width: 100%"
                      @change="handleElementPageChange"
                    />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item :label="$t('uiAutomation.element.componentName')">
                    <el-input v-model="selectedElement.component_name" :placeholder="$t('uiAutomation.element.componentNamePlaceholder')" />
                  </el-form-item>
                </el-col>
              </el-row>

              <el-row :gutter="20">
                <el-col :span="12">
                  <el-form-item :label="$t('uiAutomation.element.locatorStrategy')" prop="locator_strategy_id" required>
                    <el-select
                      v-model="selectedElement.locator_strategy_id"
                      :key="`strategy-${formKey}-${selectedElement.locator_strategy_id || 'null'}`"
                      :placeholder="$t('uiAutomation.element.rules.strategyRequired')"
                      value-key="id"
                      @blur="validateField('locator_strategy_id')"
                    >
                      <el-option
                        v-for="strategy in locatorStrategies"
                        :key="strategy.id"
                        :label="strategy.name"
                        :value="strategy.id"
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item :label="$t('uiAutomation.element.waitTimeout') + '(' + $t('uiAutomation.element.waitTimeoutUnit') + ')'">
                    <el-input-number v-model="selectedElement.wait_timeout" :min="1" :max="60" style="width: 100%" />
                  </el-form-item>
                </el-col>
              </el-row>

              <el-row :gutter="20">
                <el-col :span="12">
                  <el-form-item :label="$t('uiAutomation.element.forceAction')">
                    <el-switch
                      v-model="selectedElement.force_action"
                      :active-text="$t('uiAutomation.element.forceActionEnabled')"
                      :inactive-text="$t('uiAutomation.element.forceActionDisabled')"
                    />
                    <div class="form-help-text" style="margin-top: 5px;">
                      {{ $t('uiAutomation.element.forceActionTip') }}
                    </div>
                  </el-form-item>
                </el-col>
              </el-row>

              <el-form-item :label="$t('uiAutomation.element.locatorExpression')" prop="locator_value" required>
                <el-input v-model="selectedElement.locator_value" :placeholder="$t('uiAutomation.element.locatorExpressionPlaceholder')" @blur="validateField('locator_value')" />
                <div class="form-help-text">
                  {{ $t('uiAutomation.element.locatorTip.title') }}<br>
                  - {{ $t('uiAutomation.element.locatorTip.id') }}<br>
                  - {{ $t('uiAutomation.element.locatorTip.css') }}<br>
                  - {{ $t('uiAutomation.element.locatorTip.xpath') }}<br>
                  - {{ $t('uiAutomation.element.locatorTip.parameterized') }}
                  <code>${text}</code> / <code>${date}</code> /
                  <code>//span[text()='${text}']</code><br>
                  - {{ $t('uiAutomation.element.locatorTip.other') }}
                </div>
              </el-form-item>

              <el-form-item :label="$t('uiAutomation.common.description')">
                <el-input v-model="selectedElement.description" type="textarea" :rows="3" :placeholder="$t('uiAutomation.element.descriptionPlaceholder')" />
              </el-form-item>
            </el-form>
          </div>
        </div>
      </div>
    </div>

    <!-- 鍒涘缓椤甸潰瀵硅瘽妗?-->
    <el-dialog v-model="showCreatePageDialog" :title="$t('uiAutomation.element.createPageTitle')" width="500px" :close-on-click-modal="false">
      <el-form ref="pageFormRef" :model="pageForm" :rules="pageRules" label-width="100px">
        <el-form-item :label="$t('uiAutomation.element.pageName')" prop="name">
          <el-input v-model="pageForm.name" :placeholder="$t('uiAutomation.element.pageNamePlaceholder')" />
        </el-form-item>
        <el-form-item :label="$t('uiAutomation.element.parentPage')">
          <el-tree-select
            v-model="pageForm.parent_page"
            :data="pageTreeOptions"
            :props="pageSelectProps"
            node-key="id"
            check-strictly
            clearable
            filterable
            default-expand-all
            :render-after-expand="false"
            :placeholder="$t('uiAutomation.element.selectParentPage')"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item :label="$t('uiAutomation.common.description')" prop="description">
          <el-input v-model="pageForm.description" type="textarea" :rows="3" :placeholder="$t('uiAutomation.element.descriptionPlaceholder')" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showCreatePageDialog = false">{{ $t('uiAutomation.common.cancel') }}</el-button>
        <el-button type="primary" @click="createPage">{{ $t('uiAutomation.common.confirm') }}</el-button>
      </template>
    </el-dialog>

    <!-- 鍙抽敭鑿滃崟 -->
    <ul v-show="showContextMenu" class="context-menu" :style="{ left: contextMenuX + 'px', top: contextMenuY + 'px' }">
      <li @click="addContextElement">{{ $t('uiAutomation.element.contextMenu.addElement') }}</li>
      <!-- 鍙湁鍦ㄦ櫘閫氶〉闈㈣妭鐐逛笅鎵嶆樉绀?鏂板瀛愰〉闈?閫夐」 -->
      <li v-if="rightClickedNode && rightClickedNode.type === 'page' && rightClickedNode.id !== 'unassigned'" @click="addSubPage">
        {{ $t('uiAutomation.element.contextMenu.addSubPage') }}
      </li>
      <!-- "鏈叧鑱旈〉闈?鑺傜偣涓嶆樉绀虹紪杈戝拰鍒犻櫎閫夐」 -->
      <li v-if="rightClickedNode && rightClickedNode.id !== 'unassigned'" @click="editNode">
        {{ $t('uiAutomation.element.contextMenu.edit') }}
      </li>
      <li v-if="rightClickedNode && rightClickedNode.id !== 'unassigned'" @click="deleteNode">
        {{ $t('uiAutomation.element.contextMenu.delete') }}
      </li>
    </ul>

    <!-- 缂栬緫椤甸潰瀵硅瘽妗?-->
    <el-dialog v-model="showEditPageDialog" :title="$t('uiAutomation.element.editPageTitle')" width="500px" :close-on-click-modal="false">
      <el-form ref="editPageFormRef" :model="editPageForm" :rules="pageRules" label-width="100px">
        <el-form-item :label="$t('uiAutomation.element.pageName')" prop="name">
          <el-input v-model="editPageForm.name" :placeholder="$t('uiAutomation.element.pageNamePlaceholder')" />
        </el-form-item>
        <el-form-item :label="$t('uiAutomation.element.parentPage')">
          <el-tree-select
            v-model="editPageForm.parent_page"
            :data="editableParentPageTreeOptions"
            :props="pageSelectProps"
            node-key="id"
            check-strictly
            clearable
            filterable
            default-expand-all
            :render-after-expand="false"
            :placeholder="$t('uiAutomation.element.selectParentPage')"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item :label="$t('uiAutomation.common.description')" prop="description">
          <el-input v-model="editPageForm.description" type="textarea" :rows="3" :placeholder="$t('uiAutomation.element.descriptionPlaceholder')" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showEditPageDialog = false">{{ $t('uiAutomation.common.cancel') }}</el-button>
        <el-button type="primary" @click="updatePage">{{ $t('uiAutomation.common.save') }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showImportDialog" title="导入元素" width="520px" :close-on-click-modal="false">
      <el-form label-width="100px">
        <el-form-item label="目标项目">
          <el-select v-model="importTargetProject" placeholder="请选择目标项目" style="width: 100%">
            <el-option
              v-for="project in projects"
              :key="project.id"
              :label="project.name"
              :value="project.id"
            />
          </el-select>
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
        <el-form-item label="覆盖已存在">
          <el-switch v-model="importOverwrite" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showImportDialog = false">取消</el-button>
        <el-button type="primary" :loading="importing" @click="submitImportFile">开始导入</el-button>
      </template>
    </el-dialog>
    <el-dialog v-model="showTransferDialog" title="复制元素到项目" width="520px" :close-on-click-modal="false">
      <el-form label-width="100px">
        <el-form-item label="来源项目">
          <span>{{ currentProjectName || '-' }}</span>
        </el-form-item>
        <el-form-item label="复制范围">
          <span>{{ transferScopeLabel }}</span>
        </el-form-item>
        <el-form-item label="目标项目">
          <el-select v-model="transferTargetProject" placeholder="请选择目标项目" style="width: 100%">
            <el-option
              v-for="project in projects"
              :key="project.id"
              :label="project.name"
              :value="project.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="覆盖已存在">
          <el-switch v-model="transferOverwrite" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showTransferDialog = false">取消</el-button>
        <el-button type="primary" :loading="transferring" @click="submitTransfer">开始复制</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus, FolderAdd, Document, Search, Edit, Delete,
  Folder, Document as DocumentIcon, Operation, DocumentCopy, ArrowDown
} from '@element-plus/icons-vue'
import {
  getUiProjects,
  getElements,
  createElement,
  getElementDetail,
  updateElement,
  deleteElement,
  getElementTree,
  getElementGroupTree,
  getElementGroups,
  createElementGroup,
  updateElementGroup,
  deleteElementGroup,
  getLocatorStrategies,
  exportElements,
  importElements,
  validateElementLocator,
  generateElementSuggestions
} from '@/api/ui_automation'
import { useUiAutomationStore } from '@/stores/uiAutomation'

// 鍥介檯鍖?
const { t } = useI18n()
const uiAutomationStore = useUiAutomationStore()

// 鍝嶅簲寮忔暟鎹?
const projects = ref([])
const selectedProject = ref('')
const pages = ref([])
const locatorStrategies = ref([])
const treeData = ref([])
const selectedElement = ref(null)
const checkedElementIds = ref([])
const expandedKeys = ref([])
const treeKey = ref(0) // 鐢ㄤ簬寮哄埗閲嶆柊娓叉煋鏍戠粍浠?
const formKey = ref(0) // 鐢ㄤ簬寮哄埗閲嶆柊娓叉煋琛ㄥ崟缁勪欢

// 琛ㄥ崟寮曠敤
const treeRef = ref(null)
const pageFormRef = ref(null)
const editPageFormRef = ref(null)
const elementFormRef = ref(null)
const elementHeaderFormRef = ref(null)
const showImportDialog = ref(false)
const showTransferDialog = ref(false)
const importFile = ref(null)
const importOverwrite = ref(false)
const importTargetProject = ref('')
const importing = ref(false)
const transferring = ref(false)
const transferOverwrite = ref(false)
const transferTargetProject = ref('')
const transferScope = ref('all')
const SIDEBAR_WIDTH_STORAGE_KEY = 'ui-automation-element-sidebar-width'
const SIDEBAR_MIN_WIDTH = 280
const SIDEBAR_MAX_WIDTH = 720
const sidebarWidth = ref(300)
let sidebarResizeHandlers = null

// 瀵硅瘽妗嗘帶鍒?
const showCreatePageDialog = ref(false)
const showEditPageDialog = ref(false)

// 鍙抽敭鑿滃崟
const showContextMenu = ref(false)
const contextMenuX = ref(0)
const contextMenuY = ref(0)
const rightClickedNode = ref(null)

// 琛ㄥ崟鏁版嵁
const pageForm = reactive({
  name: '',
  description: '',
  parent_page: null
})

const editPageForm = reactive({
  id: null,
  name: '',
  description: '',
  parent_page: null
})

// 鏍戝舰缁勪欢閰嶇疆
const treeProps = {
  children: 'children',
  label: 'name',
  disabled: 'disabled'
}

const pageSelectProps = {
  value: 'id',
  label: 'name',
  children: 'children',
  disabled: 'disabled'
}

// 琛ㄥ崟楠岃瘉瑙勫垯
const pageRules = computed(() => ({
  name: [
    { required: true, message: t('uiAutomation.element.rules.pageNameRequired'), trigger: 'blur' }
  ]
}))

// 鍏冪礌琛ㄥ崟澶撮儴楠岃瘉瑙勫垯锛堝厓绱犲悕绉帮級
const elementHeaderRules = computed(() => ({
  name: [
    { required: true, message: t('uiAutomation.element.rules.nameRequired'), trigger: 'blur' },
    { min: 1, max: 200, message: t('uiAutomation.element.rules.nameLength'), trigger: 'blur' }
  ]
}))

// 鍏冪礌琛ㄥ崟楠岃瘉瑙勫垯
const elementRules = computed(() => ({
  locator_strategy_id: [
    { required: true, message: t('uiAutomation.element.rules.strategyRequired'), trigger: 'change' }
  ],
  locator_value: [
    { required: true, message: t('uiAutomation.element.rules.locatorRequired'), trigger: 'blur' },
    { min: 1, max: 500, message: t('uiAutomation.element.rules.locatorLength'), trigger: 'blur' }
  ]
}))

// 鑾峰彇鍏冪礌绫诲瀷鏍囩
const getElementTypeLabel = (type) => {
  const typeKey = type?.toLowerCase()
  const typeMap = {
    'button': t('uiAutomation.element.elementTypes.button'),
    'input': t('uiAutomation.element.elementTypes.input'),
    'link': t('uiAutomation.element.elementTypes.link'),
    'dropdown': t('uiAutomation.element.elementTypes.dropdown'),
    'checkbox': t('uiAutomation.element.elementTypes.checkbox'),
    'radio': t('uiAutomation.element.elementTypes.radio'),
    'text': t('uiAutomation.element.elementTypes.text'),
    'image': t('uiAutomation.element.elementTypes.image'),
    'table': t('uiAutomation.element.elementTypes.table'),
    'form': t('uiAutomation.element.elementTypes.form'),
    'modal': t('uiAutomation.element.elementTypes.modal')
  }
  return typeMap[typeKey] || type
}

// 鑾峰彇鎵€鏈夐〉闈?
const getAllPages = () => {
  const allPages = []

  const traverse = (nodes) => {
    nodes.forEach(node => {
      if (node.type === 'page') {
        allPages.push({
          id: node.id,
          name: node.name
        })
      }
      if (node.children) {
        traverse(node.children)
      }
    })
  }

  traverse(treeData.value)
  return allPages
}

// 鑾峰彇鎵€鏈夐〉闈紙闄や簡鎸囧畾ID鐨勯〉闈級
const getAllPagesExceptCurrent = (currentId) => {
  const allPages = []

  const traverse = (nodes) => {
    nodes.forEach(node => {
      if (node.type === 'page' && node.id !== currentId) {
        allPages.push({
          id: node.id,
          name: node.name
        })
      }
      if (node.children) {
        traverse(node.children)
      }
    })
  }

  traverse(treeData.value)
  return allPages
}

// 椤甸潰鍚嶇О缂栬緫鐩稿叧
const editingNodeId = ref(null)
const editingNodeName = ref('')
const editInputRef = ref(null)

// 鐘舵€?
const saving = ref(false)
const validating = ref(false)
const generating = ref(false)
const suggestions = ref([])

const currentProjectName = computed(() => {
  return projects.value.find(project => project.id === selectedProject.value)?.name || ''
})

const selectedElementCount = computed(() => checkedElementIds.value.length)

const checkedElementTreeKeys = computed(() => checkedElementIds.value.map(id => getElementTreeKey(id)))

const transferScopeLabel = computed(() => {
  if (transferScope.value === 'selected') {
    return `已勾选 ${selectedElementCount.value} 个元素`
  }
  return '当前项目全部元素'
})

const normalizeSidebarWidth = (value) => {
  const numericWidth = Number(value)
  if (!Number.isFinite(numericWidth)) {
    return 300
  }
  return Math.min(Math.max(Math.round(numericWidth), SIDEBAR_MIN_WIDTH), SIDEBAR_MAX_WIDTH)
}

const persistSidebarWidth = () => {
  if (typeof window === 'undefined') {
    return
  }
  window.localStorage.setItem(SIDEBAR_WIDTH_STORAGE_KEY, String(sidebarWidth.value))
}

const setSidebarWidth = (value) => {
  sidebarWidth.value = normalizeSidebarWidth(value)
  persistSidebarWidth()
}

const stopSidebarResize = () => {
  if (!sidebarResizeHandlers) {
    return
  }

  document.removeEventListener('mousemove', sidebarResizeHandlers.handleMouseMove)
  document.removeEventListener('mouseup', sidebarResizeHandlers.handleMouseUp)
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
  sidebarResizeHandlers = null
}

const startSidebarResize = (event) => {
  if (event.button !== 0) {
    return
  }

  const startX = event.clientX
  const startWidth = sidebarWidth.value

  const handleMouseMove = (moveEvent) => {
    const deltaX = moveEvent.clientX - startX
    setSidebarWidth(startWidth + deltaX)
  }

  const handleMouseUp = () => {
    stopSidebarResize()
  }

  stopSidebarResize()
  document.addEventListener('mousemove', handleMouseMove)
  document.addEventListener('mouseup', handleMouseUp)
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
  sidebarResizeHandlers = {
    handleMouseMove,
    handleMouseUp
  }
}

const handleSidebarResizeKeydown = (event) => {
  if (event.key === 'ArrowLeft') {
    event.preventDefault()
    setSidebarWidth(sidebarWidth.value - 24)
  } else if (event.key === 'ArrowRight') {
    event.preventDefault()
    setSidebarWidth(sidebarWidth.value + 24)
  }
}

const pageTreeOptions = computed(() => {
  const toPageOnlyTree = (nodes = []) => nodes
    .filter(node => node.type === 'page' && node.id !== 'unassigned')
    .map(node => ({
      id: node.id,
      name: node.name,
      description: node.description,
      parent_group: node.parent_group,
      disabled: false,
      children: toPageOnlyTree(node.children || [])
    }))

  return toPageOnlyTree(treeData.value)
})

const getPageTreeKey = (id) => `page-${id}`

const getElementTreeKey = (id) => `element-${id}`

const sameTreeId = (left, right) => String(left) === String(right)

const addExpandedKey = (key) => {
  if (key && !expandedKeys.value.includes(key)) {
    expandedKeys.value.push(key)
  }
}

const editableParentPageTreeOptions = computed(() => {
  const excludeCurrentPage = (nodes = [], currentId = editPageForm.id) => nodes
    .filter(node => node.id !== currentId)
    .map(node => ({
      ...node,
      children: excludeCurrentPage(node.children || [], currentId)
    }))

  return excludeCurrentPage(pageTreeOptions.value)
})

const buildPageTreeNodes = (groups = []) => groups.map(group => ({
  ...group,
  treeKey: getPageTreeKey(group.id),
  type: 'page',
  disabled: false,
  children: buildPageTreeNodes(group.children || [])
}))

const findPageNodeById = (nodes, targetId) => {
  for (const node of nodes) {
    if (sameTreeId(node.id, targetId)) {
      return node
    }
    if (node.children?.length) {
      const matchedNode = findPageNodeById(node.children, targetId)
      if (matchedNode) {
        return matchedNode
      }
    }
  }
  return null
}

const getPageNameById = (pageId) => {
  if (!pageId) {
    return ''
  }

  const flatPage = pages.value.find(page => sameTreeId(page.id, pageId))
  if (flatPage?.name) {
    return flatPage.name
  }

  return findPageNodeById(pageTreeOptions.value, pageId)?.name || ''
}

const normalizeElementForEditing = (elementData) => {
  if (!elementData) {
    return null
  }

  const groupId = elementData.group_id ?? elementData.group?.id ?? null
  return {
    ...elementData,
    group_id: groupId,
    page: groupId ? (getPageNameById(groupId) || elementData.group?.name || elementData.page || '') : ''
  }
}

const buildElementPayload = (elementData) => {
  const groupId = elementData.group_id || null

  return {
    name: elementData.name,
    element_type: elementData.element_type,
    page: groupId ? getPageNameById(groupId) : '',
    component_name: elementData.component_name,
    description: elementData.description,
    locator_strategy_id: elementData.locator_strategy_id,
    locator_value: elementData.locator_value,
    wait_timeout: elementData.wait_timeout,
    force_action: elementData.force_action,
    project_id: selectedProject.value,
    group_id: groupId
  }
}


// 灏嗗叧閿彉閲忔毚闇插埌window瀵硅薄锛屾柟渚垮湪鎺у埗鍙拌皟璇?
const exposeToWindow = () => {
  if (typeof window !== 'undefined') {
    window.ELEMENTS_DEBUG = {
      treeData,
      projects,
      selectedElement,
      loadElementTree,
      treeRef: typeof treeRef !== 'undefined' ? treeRef : null,
      expandedKeys,
      pages,
      $vm: { // 褰撳墠缁勪欢瀹炰緥
        treeData: treeData.value,
        projects: projects.value,
        pages: pages.value,
        expandedKeys: expandedKeys.value
      }
    }
    console.log('=== Vue缁勪欢璋冭瘯淇℃伅宸叉毚闇?===')
    console.log('Debug helpers exposed on window')
    console.log('鎺у埗鍙板彲鐩存帴璁块棶:')
    console.log('  window.ELEMENTS_DEBUG.treeData')
    console.log('  window.ELEMENTS_DEBUG.projects')
    console.log('  window.ELEMENTS_DEBUG.selectedElement')
    console.log('==============================')
  }
}

// 缁勪欢鎸傝浇
onMounted(async () => {
  console.log('=== 缁勪欢鎸傝浇寮€濮?===')

  if (typeof window !== 'undefined') {
    setSidebarWidth(window.localStorage.getItem(SIDEBAR_WIDTH_STORAGE_KEY) || sidebarWidth.value)
  }

  await loadProjects()
  await loadLocatorStrategies()

  console.log('椤圭洰鏁伴噺:', projects.value.length)
  console.log('瀹氫綅绛栫暐:', locatorStrategies.value.length)

  if (projects.value.length > 0) {
    console.log('璁剧疆鍒濆椤圭洰涓?', projects.value[0].id)
    selectedProject.value = uiAutomationStore.resolveSelectedProjectId(projects.value)
    await onProjectChange()
    console.log('onProjectChange瀹屾垚')
  }

  // 鏆撮湶璋冭瘯淇℃伅
  exposeToWindow()

  console.log('=== 缁勪欢鎸傝浇瀹屾垚 ===')
})

onUnmounted(() => {
  stopSidebarResize()
})

// 鍔犺浇椤圭洰鍒楄〃
const loadProjects = async () => {
  try {
    const response = await getUiProjects()
    projects.value = response.data?.results || response.data || []
  } catch (error) {
    console.error('鑾峰彇椤圭洰鍒楄〃澶辫触:', error)
  }
}

// 鎻愪緵鎺у埗鍙拌皟璇曞府鍔╁嚱鏁?
const debugTree = () => {
  if (typeof window !== 'undefined') {
    console.log('=== 鏍戞暟鎹皟璇?===')
    console.log('treeData:', treeData.value)
    console.log('椤甸潰瀵硅薄:',
      treeData.value.map(p => ({
        id: p.id,
        name: p.name,
        type: p.type,
        children: p.children?.length || 0,
        elementChildren: p.children?.filter(c => c.type === 'element').map(e => e.name) || []
      }))
    )

    // 鎵惧嚭鎵€鏈夊厓绱?
    const allElements = []
    const findElements = (nodes, parent) => {
      nodes.forEach(node => {
        if (node.type === 'element') {
          allElements.push({
            name: node.name,
            id: node.id,
            parent: parent
          })
        } else if (node.type === 'page' && node.children) {
          findElements(node.children, node.name)
        }
      })
    }
    findElements(treeData.value, null)
    console.log('鎵€鏈夊厓绱?', allElements)

    // 鏆撮湶鍒皐indow
    window.debugTreeData = debugTree
    console.log('璋冭瘯鍑芥暟宸叉寕杞藉埌 window.debugTreeData()')
    console.log('===============================')
  }
}

// 鍔犺浇瀹氫綅绛栫暐
const loadLocatorStrategies = async () => {
  try {
    const response = await getLocatorStrategies()
    locatorStrategies.value = response.data?.results || response.data || []
  } catch (error) {
    console.error('鑾峰彇瀹氫綅绛栫暐澶辫触:', error)
  }
}

// 鍔犺浇椤甸潰锛堝垎缁勶級
const loadPages = async () => {
  if (!selectedProject.value) return

  try {
    const response = await getElementGroups({ project: selectedProject.value })
    pages.value = response.data?.results || response.data || []
  } catch (error) {
    console.error('鑾峰彇椤甸潰澶辫触:', error)
  }
}

// 鍔犺浇椤甸潰鏍戠粨鏋?
const loadPageTree = async () => {
  if (!selectedProject.value) return

  try {
    const response = await getElementGroupTree({ project: selectedProject.value })
    treeData.value = buildPageTreeNodes(response.data || [])
  } catch (error) {
    console.error('鑾峰彇椤甸潰鏍戝け璐?', error)
    treeData.value = []
  }
}

// 鍔犺浇鍏冪礌鏍?
const loadElementTree = async () => {
  if (!selectedProject.value) {
    treeData.value = []
    return
  }

  try {
    // 骞惰鍔犺浇椤甸潰鏍戝拰鍏冪礌
    const [pageTreeResponse, elementsResponse] = await Promise.all([
      getElementGroupTree({ project: selectedProject.value }),
      getElementTree({ project: selectedProject.value })
    ])

    const pageNodes = buildPageTreeNodes(pageTreeResponse.data || [])

    // 璋冭瘯淇℃伅 - 妫€鏌PI杩斿洖鐨勫畬鏁村搷搴旂粨鏋?
    console.log('=== 鍔犺浇鍏冪礌鏍戣皟璇?===')
    console.log('椤甸潰鏍戝搷搴?', pageTreeResponse)
    console.log('鍏冪礌鍝嶅簲:', elementsResponse)

    // 鎵撳嵃鍘熷鏁版嵁杩涜鍒嗘瀽
    console.log('椤甸潰鏍戝師濮嬫暟鎹?', JSON.parse(JSON.stringify(pageTreeResponse.data || []), null, 2))

    const elements = elementsResponse.data?.results || elementsResponse.data || []
    console.log('鎻愬彇鐨勫厓绱犲垪琛?', elements)

    // 鑾峰彇鎵€鏈夐〉闈㈢殑ID锛岀敤浜庤皟璇?
    const pageIds = pageNodes.map(page => page.id)
    console.log('椤甸潰ID鍒楄〃:', pageIds)

    // 灏嗗厓绱犳坊鍔犲埌瀵瑰簲椤甸潰涓?
    const attachedElementIds = new Set()

    const attachElementsToPages = (pages) => {
      pages.forEach(page => {
        // 鎵惧埌灞炰簬褰撳墠椤甸潰鐨勫厓绱?
        const pageElements = elements.filter(element => sameTreeId(element.group_id, page.id))
        console.log(`Page ${page.name} (ID: ${page.id}) matched ${pageElements.length} elements`, pageElements)

        const elementNodes = pageElements.map(element => {
          attachedElementIds.add(element.id)
          return {
            ...element,
            treeKey: getElementTreeKey(element.id),
            type: 'element',
            disabled: false
          }
        })

        // 灏嗗厓绱犳坊鍔犲埌椤甸潰鐨勫瓙鑺傜偣涓?
        page.children = page.children ? [...page.children, ...elementNodes] : [...elementNodes]
        console.log(`Page ${page.name} now has ${page.children.filter(c => c.type === 'element').length} element children`)

        // 閫掑綊澶勭悊瀛愰〉闈?
        if (page.children) {
          attachElementsToPages(page.children.filter(child => child.type === 'page'))
        }
      })
    }

    attachElementsToPages(pageNodes)

    // 娣诲姞鏈叧鑱旈〉闈㈢殑鍏冪礌鍒?鏈叧鑱旈〉闈?鑺傜偣
    // 鍖呮嫭锛?. group_id 涓?null/undefined 鐨勫厓绱?
    //       2. group_id 鎸囧悜鐨勯〉闈笉瀛樺湪鐨勫厓绱?
    const unassignedElements = elements.filter(element => {
      // 濡傛灉娌℃湁group_id锛岃偗瀹氭槸鏈叧鑱旂殑
      if (!element.group_id) {
        return true
      }
      // 濡傛灉鏈塯roup_id浣嗘病鏈夎娣诲姞鍒颁换浣曢〉闈紙椤甸潰涓嶅瓨鍦級锛屼篃绠楁湭鍏宠仈
      return !attachedElementIds.has(element.id)
    })

    console.log('鏈叧鑱旈〉闈㈢殑鍏冪礌:', unassignedElements)

    if (unassignedElements.length > 0) {
      const unassignedPage = {
        id: 'unassigned',
        treeKey: getPageTreeKey('unassigned'),
        name: 'Unassigned',
        type: 'page',
        disabled: false,
        children: unassignedElements.map(element => ({
          ...element,
          treeKey: getElementTreeKey(element.id),
          type: 'element',
          disabled: false
        }))
      }
      pageNodes.unshift(unassignedPage) // 娣诲姞鍒板垪琛ㄦ渶鍓嶉潰
      console.log(`Added ${unassignedElements.length} unassigned elements to the unassigned node`)
      // 榛樿灞曞紑鏈叧鑱旈〉闈㈣妭鐐?
      addExpandedKey(getPageTreeKey('unassigned'))
    }

    console.log('鏈€缁坱reeData:', pageNodes)
    treeData.value = pageNodes
    const collectElementIds = (nodes, target = new Set()) => {
      nodes.forEach(node => {
        if (node.type === 'element') {
          target.add(node.id)
        }
        if (node.children?.length) {
          collectElementIds(node.children, target)
        }
      })
      return target
    }
    const availableElementIds = collectElementIds(pageNodes)
    checkedElementIds.value = checkedElementIds.value.filter(id => availableElementIds.has(id))

    // 灏唗reeData鏆撮湶鍒皐indow锛屾柟渚垮湪鎺у埗鍙拌皟璇?
    if (typeof window !== 'undefined') {
      window.vue_treeData = treeData.value
      console.log('treeData宸叉寕杞藉埌window.vue_treeData锛屽彲鍦ㄦ帶鍒跺彴鏌ョ湅')
      console.log('褰撳墠treeData缁撴瀯:', JSON.parse(JSON.stringify(treeData.value)).map(p => ({
        name: p.name,
        id: p.id,
        children: p.children?.filter(c => c.type === 'element').length || 0
      })))
    }
    await nextTick()
    treeRef.value?.setCheckedKeys(checkedElementTreeKeys.value)
  } catch (error) {
    console.error('鑾峰彇鍏冪礌鏍戝け璐?', error)
    treeData.value = []
  }
}

// 椤圭洰鍒囨崲
const onProjectChange = async () => {
  uiAutomationStore.setSelectedProject(selectedProject.value)
  selectedElement.value = null
  checkedElementIds.value = []
  suggestions.value = []

  console.log('=== 椤圭洰鍒囨崲璋冭瘯 ===')
  console.log('褰撳墠椤圭洰ID:', selectedProject.value)

  await Promise.all([
    loadPages(),
    loadElementTree()
  ])

  console.log('椤圭洰鍒囨崲瀹屾垚锛屾鏌reeData:', treeData.value)
  console.log('treeData闀垮害:', treeData.value.length)
  if (treeData.value.length > 0) {
    console.log('绗竴椤典俊鎭?', {
      id: treeData.value[0].id,
      name: treeData.value[0].name,
      type: treeData.value[0].type,
      children: treeData.value[0].children?.length || 0
    })
  }

  // 椤圭洰鍒囨崲鏃跺己鍒跺埛鏂版爲
  treeKey.value += 1
}

const handleTreeCheck = () => {
  checkedElementIds.value = (treeRef.value?.getCheckedNodes(false, false) || [])
    .filter(node => node.type === 'element')
    .map(node => node.id)
}

// 鍒涘缓绌哄厓绱?
const createEmptyElement = () => {
  selectedElement.value = {
    name: '',
    element_type: 'BUTTON',
    group_id: null,
    page: '',
    component_name: '',
    locator_strategy_id: null, // 浣跨敤null鑰屼笉鏄┖瀛楃涓?
    locator_value: '',
    wait_timeout: 5,
    force_action: false,  // 寮哄埗鎿嶄綔閫夐」锛岄粯璁ょ鐢?
    description: ''
  }
}

const handleElementPageChange = (groupId) => {
  if (!selectedElement.value) {
    return
  }

  selectedElement.value.group_id = groupId || null
  selectedElement.value.page = getPageNameById(groupId)
}

const getDefaultTargetProjectId = (sourceProjectId = selectedProject.value) => {
  const otherProject = projects.value.find(project => project.id !== sourceProjectId)
  return otherProject?.id || sourceProjectId || projects.value[0]?.id || ''
}

const getDownloadFilename = (contentDisposition, fallbackName) => {
  if (!contentDisposition) {
    return fallbackName
  }

  const utf8Match = /filename\*=UTF-8''([^;]+)/i.exec(contentDisposition)
  if (utf8Match?.[1]) {
    return decodeURIComponent(utf8Match[1])
  }

  const plainMatch = /filename="?([^"]+)"?/i.exec(contentDisposition)
  if (plainMatch?.[1]) {
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

const fetchElementManifest = async (ids = []) => {
  const response = await exportElements({
    project: selectedProject.value,
    ids: ids.join(',')
  })
  const blob = response.data instanceof Blob
    ? response.data
    : new Blob([response.data], { type: response.headers['content-type'] || 'application/json' })
  const manifestText = await blob.text()

  return {
    manifest: JSON.parse(manifestText),
    blob,
    filename: getDownloadFilename(
      response.headers['content-disposition'],
      `ui-elements-project-${selectedProject.value}.json`
    )
  }
}

const openImportDialog = () => {
  if (!selectedProject.value) {
    ElMessage.warning('请先选择项目')
    return
  }

  importFile.value = null
  importOverwrite.value = false
  importTargetProject.value = getDefaultTargetProjectId()
  showImportDialog.value = true
}

const handleImportFileChange = (file) => {
  importFile.value = file.raw
}

const handleImportFileRemove = () => {
  importFile.value = null
}

const submitImportFile = async () => {
  if (!importTargetProject.value) {
    ElMessage.warning('请选择目标项目')
    return
  }

  if (!importFile.value) {
    ElMessage.warning('请先选择导入文件')
    return
  }

  importing.value = true
  try {
    const formData = new FormData()
    formData.append('project', importTargetProject.value)
    formData.append('overwrite', importOverwrite.value ? '1' : '0')
    formData.append('file', importFile.value)

    const response = await importElements(formData)
    const summary = response.data?.summary || {}
    ElMessage.success(`导入成功，新增 ${summary.created || 0} 个，更新 ${summary.updated || 0} 个，复用 ${summary.reused || 0} 个`)
    showImportDialog.value = false

    if (String(importTargetProject.value) === String(selectedProject.value)) {
      await Promise.all([loadPages(), loadElementTree()])
      treeKey.value += 1
    }
  } catch (error) {
    console.error('Import elements failed:', error)
    ElMessage.error(error.response?.data?.detail || error.response?.data?.message || '导入失败')
  } finally {
    importing.value = false
  }
}

const handleExportSelectedElement = async () => {
  if (!selectedElementCount.value) {
    ElMessage.warning('请先勾选要导出的元素')
    return
  }

  try {
    const { blob, filename } = await fetchElementManifest(checkedElementIds.value)
    downloadBlob(blob, filename)
    ElMessage.success('导出成功')
  } catch (error) {
    console.error('Export current element failed:', error)
    ElMessage.error('导出失败')
  }
}

const handleExportAllElements = async () => {
  if (!selectedProject.value) {
    ElMessage.warning('请先选择项目')
    return
  }

  try {
    const { blob, filename } = await fetchElementManifest([])
    downloadBlob(blob, filename)
    ElMessage.success('导出成功')
  } catch (error) {
    console.error('Export all elements failed:', error)
    ElMessage.error('导出失败')
  }
}

const openTransferDialog = (scope) => {
  if (!selectedProject.value) {
    ElMessage.warning('请先选择项目')
    return
  }

  if (scope === 'selected' && !selectedElementCount.value) {
    ElMessage.warning('请先勾选要复制的元素')
    return
  }

  transferScope.value = scope
  transferOverwrite.value = false
  transferTargetProject.value = getDefaultTargetProjectId()
  showTransferDialog.value = true
}

const submitTransfer = async () => {
  if (!transferTargetProject.value) {
    ElMessage.warning('请选择目标项目')
    return
  }

  const exportIds = transferScope.value === 'selected' && selectedElementCount.value
    ? checkedElementIds.value
    : []

  transferring.value = true
  try {
    const { manifest } = await fetchElementManifest(exportIds)
    const formData = new FormData()
    formData.append('project', transferTargetProject.value)
    formData.append('overwrite', transferOverwrite.value ? '1' : '0')
    formData.append('manifest', JSON.stringify(manifest))

    const response = await importElements(formData)
    const summary = response.data?.summary || {}
    ElMessage.success(`复制成功，新增 ${summary.created || 0} 个，更新 ${summary.updated || 0} 个，复用 ${summary.reused || 0} 个`)
    showTransferDialog.value = false

    if (String(transferTargetProject.value) === String(selectedProject.value)) {
      await Promise.all([loadPages(), loadElementTree()])
      treeKey.value += 1
    }
  } catch (error) {
    console.error('Copy elements to project failed:', error)
    ElMessage.error(error.response?.data?.detail || error.response?.data?.message || '复制失败')
  } finally {
    transferring.value = false
  }
}

// 楠岃瘉鍗曚釜瀛楁锛堢敤浜庡け鐒﹂獙璇侊級
const validateField = async (field) => {
  if (!elementFormRef.value) return
  try {
    await elementFormRef.value.validateField(field)
  } catch (error) {
    // 楠岃瘉澶辫触锛屼笉闇€瑕佸仛浠讳綍澶勭悊锛岄敊璇細鑷姩鏄剧ず
  }
}

// 楠岃瘉澶撮儴琛ㄥ崟瀛楁锛堝厓绱犲悕绉帮級
const validateHeaderField = async (field) => {
  if (!elementHeaderFormRef.value) return
  try {
    await elementHeaderFormRef.value.validateField(field)
  } catch (error) {
    // 楠岃瘉澶辫触锛屼笉闇€瑕佸仛浠讳綍澶勭悊锛岄敊璇細鑷姩鏄剧ず
  }
}

// 楠岃瘉鏁翠釜鍏冪礌琛ㄥ崟
const validateElementForm = async () => {
  const results = await Promise.allSettled([
    elementHeaderFormRef.value?.validate() ?? Promise.resolve(),
    elementFormRef.value?.validate() ?? Promise.resolve()
  ])

  // 妫€鏌ユ槸鍚︽湁楠岃瘉澶辫触鐨勬儏鍐?
  const hasFailed = results.some(result => result.status === 'rejected')
  return !hasFailed
}

// 鍒涘缓椤甸潰
const createPage = async () => {
  const validate = await pageFormRef.value.validate()
  if (!validate) return

  try {
    // 鏋勫缓鍒涘缓椤甸潰鐨勫弬鏁帮紝姝ｇ‘澶勭悊鐖堕〉闈㈠弬鏁?
    const pageData = {
      name: pageForm.name,
      description: pageForm.description,
      project: selectedProject.value
    }

    // 鍙湁褰撶埗椤甸潰ID瀛樺湪涓斾笉涓虹┖鏃舵墠娣诲姞parent_group瀛楁
    if (pageForm.parent_page) {
      pageData.parent_group = pageForm.parent_page
    }

    await createElementGroup(pageData)

    ElMessage.success(t('uiAutomation.element.messages.pageCreateSuccess'))
    showCreatePageDialog.value = false

    // 閲嶇疆琛ㄥ崟
    Object.assign(pageForm, {
      name: '',
      description: '',
      parent_page: null
    })

    // 閲嶆柊鍔犺浇椤甸潰鍜屾爲
    await Promise.all([
      loadPages(),
      loadElementTree()
    ])

    // 寮哄埗鍒锋柊鏍戠粍浠?
    treeKey.value += 1
  } catch (error) {
    console.error('鍒涘缓椤甸潰澶辫触:', error)
    ElMessage.error(t('uiAutomation.element.messages.pageCreateFailed'))
  }
}

// 鑺傜偣鐐瑰嚮
const onNodeClick = async (data) => {
  if (data.type === 'element') {
    try {
      const response = await getElementDetail(data.id)
      selectedElement.value = normalizeElementForEditing(response.data)

      // 寮哄埗鍒锋柊琛ㄥ崟锛岀‘淇濅笅鎷夋姝ｇ‘鏄剧ず
      formKey.value += 1
      console.log('鐐瑰嚮鑺傜偣鏃秄ormKey鏇存柊涓?', formKey.value)
    } catch (error) {
      console.error('鑾峰彇鍏冪礌璇︽儏澶辫触:', error)
    }
  }
}

// 鑺傜偣鍙抽敭鐐瑰嚮
const onNodeRightClick = (event, data) => {
  console.log('Node right click event:', event, 'Data:', data)
  event.preventDefault()

  // 闅愯棌鐜版湁鑿滃崟
  showContextMenu.value = false

  // 璁剧疆鍙抽敭鐐瑰嚮鐨勮妭鐐?
  rightClickedNode.value = data
  console.log('Set right clicked node:', data)

  // 璁剧疆鑿滃崟浣嶇疆
  contextMenuX.value = event.clientX
  contextMenuY.value = event.clientY

  // 鏄剧ず鑿滃崟
  showContextMenu.value = true
  console.log('Show context menu at:', contextMenuX.value, contextMenuY.value)

  // 娣诲姞鍏ㄥ眬鐐瑰嚮鐩戝惉鍣ㄤ互闅愯棌鑿滃崟
  const hideMenu = () => {
    console.log('Hide context menu')
    showContextMenu.value = false
    document.removeEventListener('click', hideMenu)
  }

  // 寤惰繜娣诲姞鐩戝惉鍣紝閬垮厤绔嬪嵆瑙﹀彂
  setTimeout(() => {
    document.addEventListener('click', hideMenu)
  }, 100)
}

// 鑺傜偣灞曞紑
const onNodeExpand = (data) => {
  addExpandedKey(data.treeKey)
}

// 鑺傜偣鏀惰捣
const onNodeCollapse = (data) => {
  const index = expandedKeys.value.indexOf(data.treeKey)
  if (index > -1) {
    expandedKeys.value.splice(index, 1)
  }
}

// 淇濆瓨鍏冪礌
const saveElement = async () => {
  if (!selectedElement.value) return

  // 楠岃瘉琛ㄥ崟
  const isValid = await validateElementForm()
  if (!isValid) {
    ElMessage.error(t('uiAutomation.element.messages.saveFailed'))
    return
  }

  try {
    saving.value = true
    console.log('=== 淇濆瓨鍏冪礌璋冭瘯 ===')
    console.log('褰撳墠閫変腑鐨勫厓绱?', selectedElement.value)

    if (selectedElement.value.id) {
      const elementUpdateData = buildElementPayload(selectedElement.value)

      console.log('鏇存柊鍏冪礌鏁版嵁:', elementUpdateData)
      await updateElement(selectedElement.value.id, elementUpdateData)

      // 閲嶆柊鑾峰彇瀹屾暣鐨勫厓绱犺鎯呬互纭繚鎵€鏈夊叧鑱斿瓧娈垫纭樉绀?
      const detailResponse = await getElementDetail(selectedElement.value.id)
      selectedElement.value = normalizeElementForEditing(detailResponse.data)
      console.log('鏇存柊鍚庤幏鍙栧埌瀹屾暣鍏冪礌璇︽儏:', selectedElement.value)
      console.log('locator_strategy_id鍊?', selectedElement.value.locator_strategy_id, '绫诲瀷:', typeof selectedElement.value.locator_strategy_id)
      console.log('locator_strategy瀵硅薄:', selectedElement.value.locator_strategy)
      console.log('褰撳墠locatorStrategies:', locatorStrategies.value)
      console.log('locatorStrategies涓槸鍚﹀寘鍚玦d=' + selectedElement.value.locator_strategy_id + ':',
        locatorStrategies.value.find(s => s.id === selectedElement.value.locator_strategy_id))

      // 寮哄埗鍒锋柊琛ㄥ崟锛岀‘淇濅笅鎷夋姝ｇ‘鏄剧ず
      formKey.value += 1
      console.log('formKey鏇存柊涓?', formKey.value)

      // 浣跨敤nextTick纭繚DOM鏇存柊
      await nextTick()
      console.log('DOM宸叉洿鏂帮紝褰撳墠涓嬫媺妗嗙粦瀹氬€?', selectedElement.value.locator_strategy_id)

      ElMessage.success(t('uiAutomation.element.messages.saveSuccess'))
    } else {
      const elementData = buildElementPayload(selectedElement.value)

      console.log('鍒涘缓鍏冪礌鐨勬暟鎹?', elementData)
      const response = await createElement(elementData)
      console.log('鍒涘缓鍝嶅簲:', response)

      // 閲嶆柊鑾峰彇瀹屾暣鐨勫厓绱犺鎯呬互纭繚鎵€鏈夊叧鑱斿瓧娈垫纭樉绀?
      const detailResponse = await getElementDetail(response.data.id)
      selectedElement.value = normalizeElementForEditing(detailResponse.data)
      console.log('鑾峰彇鍒板畬鏁村厓绱犺鎯?', selectedElement.value)
      console.log('locator_strategy_id鍊?', selectedElement.value.locator_strategy_id, '绫诲瀷:', typeof selectedElement.value.locator_strategy_id)
      console.log('locator_strategy瀵硅薄:', selectedElement.value.locator_strategy)
      console.log('褰撳墠locatorStrategies:', locatorStrategies.value)
      console.log('locatorStrategies涓槸鍚﹀寘鍚玦d=' + selectedElement.value.locator_strategy_id + ':',
        locatorStrategies.value.find(s => s.id === selectedElement.value.locator_strategy_id))
      console.log('el-select缁戝畾鐨勫€?', selectedElement.value.locator_strategy_id)

      // 寮哄埗鍒锋柊琛ㄥ崟锛岀‘淇濅笅鎷夋姝ｇ‘鏄剧ず
      formKey.value += 1
      console.log('formKey鏇存柊涓?', formKey.value)

      // 浣跨敤nextTick纭繚DOM鏇存柊
      await nextTick()
      console.log('DOM宸叉洿鏂帮紝褰撳墠涓嬫媺妗嗙粦瀹氬€?', selectedElement.value.locator_strategy_id)

      ElMessage.success(t('uiAutomation.element.messages.createSuccess'))
    }

    // 閲嶆柊鍔犺浇鏍?
    console.log('寮€濮嬮噸鏂板姞杞藉厓绱犳爲...')
    await loadElementTree()
    console.log('Element tree reloaded')

    // 寮哄埗閲嶆柊娓叉煋鏍戠粍浠?
    treeKey.value += 1
    console.log('鏍戠粍浠秌ey鏇存柊涓?', treeKey.value)

    // 寮哄埗瑙﹀彂Vue鏇存柊鍜屾爲缁勪欢鍒锋柊
    nextTick(() => {
      console.log('nextTick - 妫€鏌reeData:', treeData.value)
      console.log('treeRef:', treeRef.value)

      // 灞曞紑鏂板垱寤哄厓绱犳墍鍦ㄧ殑椤甸潰鑺傜偣
      if (selectedElement.value && selectedElement.value.group_id) {
        console.log('灞曞紑鍏冪礌鎵€鍦ㄩ〉闈?', selectedElement.value.group_id)
        const groupTreeKey = getPageTreeKey(selectedElement.value.group_id)
        addExpandedKey(groupTreeKey)
      }

      console.log('鏍戞暟鎹洿鏂板畬鎴愶紝褰撳墠expandedKeys:', expandedKeys.value)
    })
  } catch (error) {
    console.error('淇濆瓨鍏冪礌澶辫触:', error)
    ElMessage.error(t('uiAutomation.element.messages.saveFailed') + ': ' + (error.response?.data?.message || error.message || t('uiAutomation.messages.error.unknown')))
  } finally {
    saving.value = false
  }
}

// 楠岃瘉鍏冪礌
const validateElement = async () => {
  if (!selectedElement.value) return

  try {
    validating.value = true
    const response = await validateElementLocator(selectedElement.value.id)
    const result = response.data

    if (result.is_valid) {
      ElMessage.success(t('uiAutomation.element.messages.validateSuccess'))
    } else {
      ElMessage.error(`${t('uiAutomation.element.messages.validateFailed')}: ${result.validation_message}`)
    }
  } catch (error) {
    ElMessage.error(t('uiAutomation.element.messages.validateFailed'))
    console.error('楠岃瘉鍏冪礌澶辫触:', error)
  } finally {
    validating.value = false
  }
}

// 鐢熸垚寤鸿
const generateSuggestions = async () => {
  if (!selectedElement.value) return

  try {
    generating.value = true
    const response = await generateElementSuggestions(selectedElement.value.id)
    suggestions.value = response.data.suggestions
  } catch (error) {
    console.error('鐢熸垚寤鸿澶辫触:', error)
  } finally {
    generating.value = false
  }
}

// 淇濆瓨椤甸潰鍚嶇О
const savePageName = () => {
  // TODO: 瀹炵幇椤甸潰鍚嶇О淇濆瓨
  editingNodeId.value = null
}

// 鍙栨秷缂栬緫
const cancelEdit = () => {
  editingNodeId.value = null
}

// 鍙抽敭鑿滃崟鎿嶄綔鍑芥暟
// 鏂板鍏冪礌
const addContextElement = () => {
  console.log('Add context element clicked')
  showContextMenu.value = false
  createEmptyElement()

  // 濡傛灉鍙抽敭鐐瑰嚮鐨勬槸椤甸潰鑺傜偣锛岃缃厓绱犵殑椤甸潰
  if (rightClickedNode.value && rightClickedNode.value.type === 'page') {
    // 鐗规畩澶勭悊锛氬鏋滄槸"鏈叧鑱旈〉闈?鑺傜偣锛屼笉璁剧疆page鍜実roup_id
    if (rightClickedNode.value.id === 'unassigned') {
      console.log('鍦ㄦ湭鍏宠仈椤甸潰鑺傜偣涓嬫坊鍔犲厓绱狅紝涓嶈缃畃age鍜実roup_id')
      return
    }

    if (selectedElement.value) {
      selectedElement.value.page = rightClickedNode.value.name
      // 鍚屾椂璁剧疆group_id锛岀‘淇濆厓绱犺兘姝ｇ‘鍏宠仈鍒伴〉闈?
      selectedElement.value.group_id = rightClickedNode.value.id
    }
  }
}

// 鏂板瀛愰〉闈?
const addSubPage = () => {
  console.log('Add sub page clicked')
  showContextMenu.value = false

  // 绂佹鍦?鏈叧鑱旈〉闈?鑺傜偣涓嬪垱寤哄瓙椤甸潰
  if (rightClickedNode.value && rightClickedNode.value.id === 'unassigned') {
    ElMessage.warning('未关联页面节点下不能创建子页面')
    return
  }

  showCreatePageDialog.value = true

  // 濡傛灉鍙抽敭鐐瑰嚮鐨勬槸椤甸潰鑺傜偣锛岃缃埗椤甸潰
  if (rightClickedNode.value && rightClickedNode.value.type === 'page') {
    pageForm.parent_page = rightClickedNode.value.id
  }
}

// 缂栬緫鑺傜偣
const editNode = async () => {
  console.log('Edit node clicked, rightClickedNode:', rightClickedNode.value)
  showContextMenu.value = false

  if (!rightClickedNode.value) {
    console.log('No right clicked node')
    return
  }

  console.log('Editing node:', rightClickedNode.value)
  console.log('Node type:', rightClickedNode.value.type)

  // 绂佹缂栬緫"鏈叧鑱旈〉闈?鑺傜偣
  if (rightClickedNode.value.id === 'unassigned') {
    ElMessage.warning('未关联页面节点不能编辑')
    return
  }

  if (rightClickedNode.value.type === 'page') {
    // 缂栬緫椤甸潰
    console.log('Editing page node')
    editPageForm.id = rightClickedNode.value.id
    editPageForm.name = rightClickedNode.value.name
    editPageForm.description = rightClickedNode.value.description || ''
    editPageForm.parent_page = rightClickedNode.value.parent_group || null
    console.log('Set edit page form data:', editPageForm)
    console.log('Setting showEditPageDialog to true')
    showEditPageDialog.value = true
    console.log('showEditPageDialog value:', showEditPageDialog.value)
  } else if (rightClickedNode.value.type === 'element') {
    console.log('Editing element node')
    // 缂栬緫鍏冪礌 - 閫氳繃API鑾峰彇瀹屾暣鐨勫厓绱犺鎯咃紝閬垮厤浣跨敤鏍戣妭鐐圭殑澶嶆潅鏁版嵁
    try {
      const response = await getElementDetail(rightClickedNode.value.id)
      selectedElement.value = normalizeElementForEditing(response.data)
      console.log('Set selected element for editing via API:', selectedElement.value)

      // 寮哄埗鍒锋柊琛ㄥ崟锛岀‘淇濅笅鎷夋姝ｇ‘鏄剧ず
      formKey.value += 1
      console.log('缂栬緫鏃秄ormKey鏇存柊涓?', formKey.value)
    } catch (error) {
      console.error('鑾峰彇鍏冪礌璇︽儏澶辫触:', error)
      ElMessage.error(t('uiAutomation.element.messages.getDetailFailed'))
    }
  } else {
    console.log('Unknown node type:', rightClickedNode.value.type)
  }
}

// 鍒犻櫎鑺傜偣
const deleteNode = async () => {
  console.log('Delete node clicked, rightClickedNode:', rightClickedNode.value)
  showContextMenu.value = false

  if (!rightClickedNode.value) return

  // 绂佹鍒犻櫎"鏈叧鑱旈〉闈?鑺傜偣
  if (rightClickedNode.value.id === 'unassigned') {
    ElMessage.warning('未关联页面节点不能删除')
    return
  }

  try {
    await ElMessageBox.confirm(
      t('uiAutomation.element.messages.confirmDeleteNode', { name: rightClickedNode.value.name }),
      t('uiAutomation.common.confirmDelete'),
      {
        type: 'warning',
        confirmButtonText: t('uiAutomation.common.confirm'),
        cancelButtonText: t('uiAutomation.common.cancel')
      }
    )

    console.log('Deleting node:', rightClickedNode.value)

    if (rightClickedNode.value.type === 'page') {
      // 鍒犻櫎椤甸潰锛堝垎缁勶級
      console.log('Calling deleteElementGroup with id:', rightClickedNode.value.id)
      await deleteElementGroup(rightClickedNode.value.id)
      ElMessage.success(t('uiAutomation.element.messages.pageDeleteSuccess'))
    } else if (rightClickedNode.value.type === 'element') {
      // 鍒犻櫎鍏冪礌
      console.log('Calling deleteElement with id:', rightClickedNode.value.id)
      await deleteElement(rightClickedNode.value.id)
      ElMessage.success(t('uiAutomation.element.messages.deleteSuccess'))
      // 濡傛灉褰撳墠閫変腑鐨勬槸琚垹闄ょ殑鍏冪礌锛屾竻绌洪€変腑
      if (selectedElement.value && selectedElement.value.id === rightClickedNode.value.id) {
        selectedElement.value = null
      }
    }

    console.log('Reload data after deletion')

    // 閲嶆柊鍔犺浇鏁版嵁
    await Promise.all([
      loadPages(),
      loadElementTree()
    ])

    // 寮哄埗鍒锋柊鏍戠粍浠?
    treeKey.value += 1
  } catch (error) {
    if (error !== 'cancel') {
      console.error('鍒犻櫎澶辫触:', error)
      ElMessage.error(t('uiAutomation.element.messages.deleteFailed'))
    }
  }
}

// 鏇存柊椤甸潰
const updatePage = async () => {
  console.log('Update page function called')
  console.log('Edit page form ref:', editPageFormRef.value)

  if (!editPageFormRef.value) {
    console.log('No edit page form ref')
    return
  }

  const validate = await editPageFormRef.value.validate()
  console.log('Validation result:', validate)
  if (!validate) {
    console.log('Validation failed')
    return
  }

  console.log('Updating page with data:', editPageForm)

  try {
    // 鏋勫缓鏇存柊椤甸潰鐨勫弬鏁帮紝姝ｇ‘澶勭悊鐖堕〉闈㈠弬鏁?
    const pageData = {
      name: editPageForm.name,
      description: editPageForm.description,
      project: selectedProject.value
    }

    // 鍙湁褰撶埗椤甸潰ID瀛樺湪涓斾笉涓虹┖鏃舵墠娣诲姞parent_group瀛楁
    // 濡傛灉鐖堕〉闈D涓簄ull锛岃〃绀哄彇娑堢埗椤甸潰鍏宠仈
    if (editPageForm.parent_page !== undefined) {
      pageData.parent_group = editPageForm.parent_page
    }

    await updateElementGroup(editPageForm.id, pageData)

    ElMessage.success(t('uiAutomation.element.messages.pageUpdateSuccess'))
    showEditPageDialog.value = false

    // 閲嶆柊鍔犺浇椤甸潰鍜屾爲
    await Promise.all([
      loadPages(),
      loadElementTree()
    ])

    // 寮哄埗鍒锋柊鏍戠粍浠?
    treeKey.value += 1
  } catch (error) {
    console.error('鏇存柊椤甸潰澶辫触:', error)
    ElMessage.error(t('uiAutomation.element.messages.pageUpdateFailed'))
  }
}
</script>

<style scoped>
.element-manager {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.element-layout {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.sidebar {
  flex: 0 0 auto;
  border-right: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
  background: #f5f7fa;
  min-width: 0;
}

.sidebar-resizer {
  width: 8px;
  cursor: col-resize;
  background: linear-gradient(to right, rgba(228, 231, 237, 0), rgba(228, 231, 237, 0.9), rgba(228, 231, 237, 0));
  transition: background-color 0.2s ease;
}

.sidebar-resizer:hover,
.sidebar-resizer:focus {
  background: linear-gradient(to right, rgba(64, 158, 255, 0), rgba(64, 158, 255, 0.85), rgba(64, 158, 255, 0));
  outline: none;
}

.sidebar-header {
  padding: 15px;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-actions {
  display: flex;
  gap: 5px;
  margin-left: auto;
}

.page-tree {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
}

.tree-node {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 5px 0;
}

.node-label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.element-type-tag {
  font-size: 12px;
  padding: 2px 6px;
  border-radius: 4px;
  background-color: #ecf5ff;
  color: #409eff;
}

.main-content {
  flex: 1;
  min-width: 0;
  overflow: auto;
  padding: 20px;
}

.content-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 20px;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.element-header {
  margin-bottom: 20px;
  padding-bottom: 20px;
  border-bottom: 1px solid #e4e7ed;
}

.element-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.element-form {
  margin-top: 20px;
}

.form-help-text {
  font-size: 12px;
  color: #909399;
  margin-top: 5px;
}

/* 鍙抽敭鑿滃崟鏍峰紡 */
.context-menu {
  position: fixed;
  z-index: 9999;
  background: white;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  padding: 5px 0;
  margin: 0;
  list-style: none;
  min-width: 120px;
}

.context-menu li {
  padding: 8px 15px;
  cursor: pointer;
  font-size: 14px;
  color: #606266;
}

.context-menu li:hover {
  background-color: #f5f7fa;
  color: #409eff;
}
</style>

