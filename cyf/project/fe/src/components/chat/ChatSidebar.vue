<template>
  <div
    :class="['sidebar', { 'sidebar-collapsed': sidebarCollapsed, 'sidebar-mobile': isMobile }]"
    :style="{ width: sidebarCollapsed ? '0' : (isMobile ? '100%' : '350px') }"
  >
    <div class="sidebar-content">
      <el-button v-if="isMobile" class="sidebar-close-btn" :icon="Close" circle @click="sidebarCollapsed = true"/>
      <div class="model-selector" @click.stop>
        <h3>选择模型</h3>

        <!-- 厂商选择器 -->
        <div class="provider-selector">
          <el-select
            v-model="providerValue"
            placeholder="选择厂商"
            size="small"
            filterable
            clearable
            @change="handleProviderChange"
          >
            <el-option
              v-for="provider in providers"
              :key="provider"
              :label="provider"
              :value="provider"
            />
          </el-select>
        </div>

        <!-- 模型选择器 -->
        <div class="model-selector-wrapper">
          <el-select
            v-model="modelValue"
            placeholder="选择模型"
            size="small"
            filterable
            clearable
            :disabled="!providerValue"
            @change="handleModelChange"
          >
            <el-option
              v-for="model in filteredModels"
              :key="model.value"
              :value="model.value"
            >
              <span>{{ model.label }}</span>
              <el-tag v-if="model.recommend" size="small" type="warning" style="margin-left: 8px;">荐</el-tag>
            </el-option>
          </el-select>
        </div>
      </div>

      <!-- 显示选中模型的描述 -->
      <div class="dialog-history-section">
        <div v-if="currentModelDesc" class="model-description">
          <div class="model-desc-text">
            <el-icon><InfoFilled /></el-icon>
            <span>{{ currentModelDesc }}</span>
          </div>
        </div>
      </div>

      <!-- 对话历史 -->
      <div class="dialog-history">
        <div class="history-header">
          <h3>{{ t('chat.history') }}</h3>
          <div class="history-actions">
            <el-button
              v-if="editMode"
              icon="CircleClose"
              size="small"
              @click="exitEditMode"
              title="取消编辑"
            />
            <el-button
              v-else
              icon="Edit"
              size="small"
              @click="enterEditMode"
              title="编辑模式"
            />
            <el-button
              icon="Refresh"
              size="small"
              @click="refreshHistory"
              :loading="historyLoading"
              title="刷新"
            />
          </div>
        </div>

        <!-- 批量删除模式提示 -->
        <div v-if="editMode" class="edit-mode-hint">
          <el-checkbox
            v-model="selectAll"
            @change="toggleSelectAll"
          >
            全选 ({{ selectedDialogs.length }}/{{ dialogList.length }})
          </el-checkbox>
          <el-button
            type="danger"
            size="small"
            :disabled="selectedDialogs.length === 0"
            @click="confirmBatchDelete"
          >
            批量删除 ({{ selectedDialogs.length }})
          </el-button>
        </div>

        <el-scrollbar class="history-list">
          <div
            v-for="dialog in dialogList"
            :key="dialog.id"
            :class="[
              'history-item',
              { 'active': currentDialogId === dialog.id, 'selected': editMode && selectedDialogs.includes(dialog.id) }
            ]"
            @click="editMode ? toggleDialogSelection(dialog.id) : loadDialog(dialog.id)"
          >
            <el-checkbox
              v-if="editMode"
              v-model="selectedDialogs"
              :label="dialog.id"
              class="dialog-checkbox"
            />
            <div class="history-item-content">
              <!-- 使用tooltip显示超长文本 -->
              <el-tooltip :content="dialog.title" placement="right" :hide-after="50">
                <div class="history-title">{{ truncateText(dialog.title, 20) }}</div>
              </el-tooltip>
              <div class="history-meta">
                <el-tooltip :content="dialog.model" placement="right" :hide-after="50">
                  <span class="history-model">{{ truncateText(dialog.model, 12) }}</span>
                </el-tooltip>
                <span class="history-time">{{ formatDate(dialog.updateTime) }}</span>
              </div>
            </div>
            <div class="history-actions" v-if="!editMode">
              <el-button
                icon="EditPen"
                size="small"
                circle
                @click.stop="editDialogTitle(dialog)"
              />
              <el-button
                icon="Delete"
                size="small"
                circle
                type="danger"
                @click.stop="deleteDialog(dialog.id)"
              />
            </div>
          </div>

          <div v-if="dialogList.length === 0" class="no-dialogs">
            暂无对话历史
          </div>
        </el-scrollbar>
      </div>

      <!-- 设置面板 -->
      <div class="settings-panel">
        <h3>{{ t('chat.settings') }}</h3>

        <!-- 上下文设置 -->
        <div class="context-slider-wrapper">
          <div class="context-label">
            <span>{{ t('chat.contextCount') }}</span>
            <el-tag size="small" type="info">{{ contextCount }} 条</el-tag>
          </div>
          <el-slider v-model="contextCount" :min="0" :max="50" :step="1" :marks="{ 0: '0', 25: '25', 50: '50' }" />
          <div class="context-hint">设为0时仅发送当前消息</div>
        </div>

        <!-- 最大回复字数 -->
        <div class="context-slider-wrapper">
          <div class="context-label">
            <span>{{ t('chat.maxResponseChars') }}</span>
            <el-tag size="small" type="info">{{ maxResponseChars }} 字</el-tag>
          </div>
          <el-slider v-model="maxResponseChars" :min="500" :max="32000" :step="500"
            :marks="{ 500: '500', 8000: '8千', 30000: '3万' }" />
          <div class="context-hint">限制AI回复的最大长度</div>
        </div>
        <div class="setting-item">
          <el-switch
            v-model="streamEnabled"
            :active-text="t('chat.streamEnabled')"
            @change="handleSettingsChange"
          />
        </div>
      </div>

      <!-- 角色设定 -->
      <div class="role-setting">
        <h3>{{ t('chat.roleSetting') }}</h3>

        <div class="setting-item">
          <label>{{ t('chat.systemPrompt') }}</label>
          <el-input
            v-model="systemPrompt"
            type="textarea"
            :rows="4"
            :placeholder="t('chat.systemPromptPlaceholder')"
            @input="handleSettingsChange"
            :disabled="enhancedRoleEnabled && selectedEnhancedRole"
          />
        </div>

        <div class="preset-roles">
          <label>{{ t('chat.presetRoles') }}</label>
          <el-select
            v-model="selectedPresetRole"
            @change="applyPresetRole"
            :placeholder="t('chat.selectPresetRole')"
            :disabled="enhancedRoleEnabled && selectedEnhancedRole"
          >
            <el-option
              v-for="role in presetRoles"
              :key="role.value"
              :label="role.label"
              :value="role.value"
            />
          </el-select>
        </div>

        <div class="enhanced-role">
          <el-switch
            v-model="enhancedRoleEnabled"
            :active-text="t('chat.enhancedRole')"
            @change="handleSettingsChange"
          />
        </div>
      </div>

      <!-- 发送设置 -->
      <div class="send-setting">
        <h3>{{ t('chat.sendSetting') }}</h3>
        <el-radio-group
          v-model="sendPreference"
          @change="handleSettingsChange"
        >
          <el-radio label="enter">{{ t('chat.sendWithEnter') }}</el-radio>
          <el-radio label="ctrl_enter">{{ t('chat.sendWithCtrlEnter') }}</el-radio>
        </el-radio-group>
      </div>
    </div>
  </div>

  <!-- 移动端遮罩 -->
  <div
    v-if="isMobile && !sidebarCollapsed"
    class="mobile-sidebar-mask"
    @click="sidebarCollapsed = false"
  />
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { InfoFilled, Close } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import { ChatSidebarEmits, DialogItem, ChatSettings } from './types'
import { chatAPI } from '@/services/api'
import VersionService from '@/services/version'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
// 宏定义，无需引入
const model = defineModel({ required: true, type: Object })

// 定义 emits
const emit = defineEmits<ChatSidebarEmits>()

// 国际化
const { t } = useI18n()

// 组件内状态(同步自外部)
const selectedModel = computed({ get: () => model.value.selectedModel, set: v => model.value.selectedModel = v })
const contextCount = computed({ get: () => model.value.contextCount, set: v => model.value.contextCount = v})
const maxResponseChars = computed({ get: () => model.value.maxResponseChars, set: v => model.value.maxResponseChars = v})
const streamEnabled = computed({ get: () => model.value.streamEnabled, set: v => model.value.streamEnabled = v})
const systemPrompt = computed({ get:  () => model.value.systemPrompt, set: v => model.value.systemPrompt = v })
const sendPreference = computed({ get: () => model.value.sendPreference, set: v => model.value.sendPreference = v})
// 添加侧边栏折叠状态
const sidebarCollapsed = computed({ get: () => model.value.sidebarCollapsed, set: v => model.value.sidebarCollapsed = v})
// 是否移动端，主框架控制
const isMobile = computed(() => model.value.isMobile)
// 组件内状态(私有)

const selectedPresetRole = ref('')
const dialogList = ref<DialogItem[]>([])
const historyLoading = ref(false)
// 增强角色相关状态
const enhancedRoleEnabled = ref(JSON.parse(localStorage.getItem('enhancedRoleEnabled') || 'false'))
const enhancedRoleGroups = ref<Record<string, Array<{role_name: string, role_desc: string, role_content: string}>>>({})
const activeEnhancedGroup = ref(localStorage.getItem('activeEnhancedGroup') || '')
const selectedEnhancedRole = ref(localStorage.getItem('selectedEnhancedRole') || '')
const loadingEnhancedRoles = ref(false)
// 编辑模式状态
const editMode = ref(false)
const selectedDialogs = ref<number[]>([])
const selectAll = ref(false)


// 通过formData同步后不使用
const handleSettingsChange = () => {
  // // 同步设置到父组件并保存到localStorage
  // const settings: ChatSettings = {
  //   contextCount: contextCount.value,
  //   maxResponseChars: maxResponseChars.value,
  //   streamEnabled: streamEnabled.value,
  //   systemPrompt: systemPrompt.value,
  //   sendPreference: sendPreference.value
  // }
  // emit('settings-change', settings)
}

const loadDialog = (dialogId: number) => {
  emit('load-dialog', dialogId)
  // 在移动端上加载对话后，自动折叠侧边栏
  if (isMobile.value) {
    sidebarCollapsed.value = true
  }
}

const applyPresetRole = (roleKey: string) => {
  const role = rolePresets.value.find(r => r.id === roleKey)
  if (role) {
    systemPrompt.value = role.prompt
    handleSettingsChange()
  }
}

// 计算属性：当前对话ID
const currentDialogId = computed(() => model.value.currentDialogId)

// 预设角色列表
const presetRoles = computed(() => {
  return rolePresets.value.map(role => ({
    value: role.id,
    label: role.name
  }))
})

// 加载对话历史
const loadDialogHistory = async () => {
  if (!authStore.user) {
    ElMessage.warning('请先登录')
    return
  }

  historyLoading.value = true
  try {
    const response: any = await chatAPI.getDialogHistory()
    if (response && response.content) {
      // 转换后端返回的数据为组件期望的格式
      dialogList.value = response.content.map((item: any) => ({
        id: item.id,
        title: item.dialog_name,
        model: item.modelname,
        createTime: item.start_date,
        updateTime: item.last_updated || item.start_date
      }))
      // ElMessage.success(`加载了 ${response.content.length} 条历史对话`)
    } else {
      dialogList.value = []
      ElMessage.info('暂无历史对话')
    }
  } catch (error: any) {
    console.error('加载对话历史错误:', error)
    ElMessage.error('加载对话历史失败')
  } finally {
    historyLoading.value = false
  }
}

// 刷新历史
const refreshHistory = () => {
  loadDialogHistory()
}

// 格式化日期
const formatDate = (dateString: string) => {
  const date = new Date(dateString)
  const now = new Date()
  const diffTime = Math.abs(now.getTime() - date.getTime())
  const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24))

  if (diffDays === 0) {
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  } else if (diffDays < 7) {
    return `${diffDays}天前`
  } else {
    return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
  }
}

// 截断文本
const truncateText = (text: string, maxLength: number) => {
  if (!text) return ''
  return text.length > maxLength ? text.substring(0, maxLength) + '...' : text
}

// 进入编辑模式
const enterEditMode = () => {
  editMode.value = true
  selectedDialogs.value = []
  selectAll.value = false
}

// 退出编辑模式
const exitEditMode = () => {
  editMode.value = false
  selectedDialogs.value = []
  selectAll.value = false
}

// 切换对话选择
const toggleDialogSelection = (dialogId: number) => {
  const index = selectedDialogs.value.indexOf(dialogId)
  if (index > -1) {
    selectedDialogs.value.splice(index, 1)
  } else {
    selectedDialogs.value.push(dialogId)
  }
  updateSelectAllState()
}

// 更新全选状态
const updateSelectAllState = () => {
  selectAll.value = selectedDialogs.value.length === dialogList.value.length && dialogList.value.length > 0
}

// 切换全选
const toggleSelectAll = () => {
  if (selectAll.value) {
    selectedDialogs.value = []
  } else {
    selectedDialogs.value = dialogList.value.map(dialog => dialog.id)
  }
}

// 确认批量删除
const confirmBatchDelete = async () => {
  if (selectedDialogs.value.length === 0) {
    ElMessage.warning('请至少选择一个对话')
    return
  }

  try {
    const response: any = await chatAPI.deleteDialogs(selectedDialogs.value)
    if (response && response.success) {
      ElMessage.success(`批量删除成功，共删除 ${response.deleted_count} 条`)
      exitEditMode()
      // 刷新对话历史
      await loadDialogHistory()
      // 如果当前对话被删除，清空聊天内容
      if (model.value.currentDialogId && selectedDialogs.value.includes(model.value.currentDialogId)) {
        emit('update:currentDialogId', null)
      }
    } else {
      ElMessage.error('批量删除失败')
    }
  } catch (error: any) {
    console.error('批量删除错误:', error)
    ElMessage.error('批量删除失败')
  }
}

// 删除单个对话
const deleteDialog = async (dialogId: number) => {
  try {
    const response: any = await chatAPI.deleteDialogs([dialogId])
    if (response && response.success) {
      ElMessage.success('对话删除成功')
      // 刷新对话历史
      await loadDialogHistory()
      // 如果当前对话被删除，清空聊天内容
      if (model.value.currentDialogId === dialogId) {
        emit('update:currentDialogId', null)
      }
    } else {
      ElMessage.error('删除对话失败')
    }
  } catch (error: any) {
    console.error('删除对话错误:', error)
    ElMessage.error('删除对话失败')
  }
}

// 编辑对话标题
const editDialogTitle = (dialog: DialogItem) => {
  ElMessageBox.prompt('请输入新的对话标题', '编辑标题', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    inputValue: dialog.title,
    inputValidator: (value) => {
      if (!value || value.trim().length === 0) {
        return '标题不能为空'
      }
      if (value.length > 100) {
        return '标题长度不能超过100个字符'
      }
      return true
    }
  }).then(async ({ value }) => {
    try {
      const response: any = await chatAPI.updateDialogTitle(dialog.id, value.trim())
      if (response && response.success) {
        ElMessage.success('标题更新成功')
        // 更新本地数据
        const dialogToUpdate = dialogList.value.find(d => d.id === dialog.id)
        if (dialogToUpdate) {
          dialogToUpdate.title = value.trim()
        }
      } else {
        ElMessage.error(response.msg || '更新标题失败')
      }
    } catch (error: any) {
      console.error('更新标题错误:', error)
      ElMessage.error('更新标题失败')
    }
  }).catch(() => {
    // 用户取消操作
  })
}

// 预设角色设定列表
const rolePresets = ref<Array<{id: string, name: string, prompt: string}>>([
  { id: 'default', name: '默认', prompt: '' },
  { id: 'translator', name: '翻译', prompt: '你是一个专业的翻译助手，擅长中英文互译，注重语义准确和表达流畅。' },
  { id: 'writer', name: '写作', prompt: '你是一个专业的写作助手，擅长文章润色、创意写作和文案编辑。' }
])

// 新增：模型选择相关的状态
const providerValue = ref<string>('')
const modelValue = ref<string>('')
const providers = ref<string[]>([])
const currentModelDesc = ref<string>('')
// 添加模型&分组模型数据
const models = ref<Array<{ group: string, label: string, value: string, recommend?: boolean, model_desc?: string }>>([])
const groupedModels = ref<Record<string, Array<{ label: string, value: string, recommend?: boolean, model_desc?: string }>>>({});

// 计算属性：根据当前选择的厂商过滤模型
const filteredModels = computed(() => {
  if (!providerValue.value) return []
  // 根据当前选择的厂商过滤模型，并按推荐状态排序
  const providerModels = models.value.filter(model => {
    // 检查模型值是否包含厂商名称
    return model.value.toLowerCase().includes(providerValue.value.toLowerCase()) ||
           model.label.toLowerCase().includes(providerValue.value.toLowerCase())
  })

  // 按推荐状态排序：推荐的模型在前面
  return providerModels.sort((a, b) => {
    if (a.recommend && !b.recommend) return -1
    if (!a.recommend && b.recommend) return 1
    return 0
  })
})

// 更新厂商列表
const updateProviders = () => {
  // 从模型列表中提取厂商名称（基于模型值中的前缀）
  const uniqueProviders = new Set<string>()

  models.value.forEach(model => {
    const lowerValue = model.value.toLowerCase()

    // 按优先级匹配厂商前缀
    if (lowerValue.includes('gpt')) {
      uniqueProviders.add('gpt')
    } else if (lowerValue.includes('gemini')) {
      uniqueProviders.add('gemini')
    } else if (lowerValue.includes('qwen')) {
      uniqueProviders.add('qwen')
    } else if (lowerValue.includes('nano-banana')) {
      uniqueProviders.add('nano-banana')
    } else if (lowerValue.includes('deepseek')) {
      uniqueProviders.add('deepseek')
    } else {
      // 如果没有匹配到预定义的厂商，使用第一个单词作为厂商
      const firstPart = model.value.split('-')[0]
      if (firstPart && firstPart.length > 1) {
        uniqueProviders.add(firstPart)
      }
    }
  })

  providers.value = Array.from(uniqueProviders).sort()
}

// 处理厂商选择变化
const handleProviderChange = (value: string) => {
  // 当厂商改变时，清空已选择的模型
  modelValue.value = ''
  // 如果值被清空，也清空selectedModel
  if (!value) {
    selectedModel.value = ''
  }
}

// 处理模型选择变化
const handleModelChange = (value: string) => {
  // 更新主selectedModel变量
  selectedModel.value = value

  // 更新当前模型描述
  const selectedModelObj = models.value.find(model => model.value === value)
  currentModelDesc.value = selectedModelObj?.model_desc || ''
}

// 从localStorage加载自定义角色
const loadCustomRoles = () => {
  const saved = localStorage.getItem('customRoles')
  if (saved) {
    try {
      const customRoles = JSON.parse(saved)
      // 追加到预设角色后面
      rolePresets.value.push(...customRoles)
    } catch (e) {
      console.error('加载自定义角色失败:', e)
    }
  }
}

// 组件挂载时加载模型列表
onMounted(async () => {
  // 检查版本更新并处理缓存
  VersionService.checkAndHandleVersionChange();

  // 首先加载自定义角色
  loadCustomRoles()

  try {
    // 优先尝试获取分组模型列表
    const response: any = await chatAPI.getGroupedModels()
    if (response && response.success && response.grouped_models) {
      // 保存分组模型数据
      groupedModels.value = response.grouped_models;

      // 将分组模型展平为普通列表
      models.value = [];
      for (const [prefix, modelList] of Object.entries(response.grouped_models)) {
        (modelList as Array<any>).forEach((model: any) => {
          models.value.push({
            group: prefix,
            label: `${prefix}: ${model.label || model.id}`,
            value: model.id,
            recommend: model.recommend || false,
            model_desc: model.model_desc || ''
          });
        });
      }
    }
  } catch (error) {
    console.error('加载模型列表时出错:', error)
    // 设置默认模型列表作为备选
    models.value = [
      { group: 'gpt', label: 'GPT-4o mini', value: 'gpt-4o-mini', recommend: false, model_desc: '' },
      { group: 'gpt',label: 'GPT-4o', value: 'gpt-4o', recommend: false, model_desc: '' },
      { group: 'gpt',label: 'GPT-3.5-turbo', value: 'gpt-3.5-turbo', recommend: false, model_desc: '' }
    ]
  }

  // 更新供应商列表
  updateProviders()

  // 如果有保存的模型选择，设置对应的供应商和模型
  if (selectedModel.value) {
    // 根据选择的模型值找到对应的供应商
    const selectedModelInfo = models.value.find(model => model.value === selectedModel.value)
    if (selectedModelInfo) {
    
      providerValue.value = selectedModelInfo.group || ''
      modelValue.value = selectedModel.value

      // 设置当前模型描述
      currentModelDesc.value = selectedModelInfo.model_desc || ''
    }
  }

  // 注释掉从localStorage恢复对话标题的功能，实现每次刷新页面时标题栏都为空
  // const savedDialogTitle = localStorage.getItem('dialogTitle')
  // if (savedDialogTitle) {
  //   dialogTitle.value = savedDialogTitle
  // }

  // 从localStorage恢复发送键偏好
  const savedSendPreference = localStorage.getItem('sendPreference')
  if (savedSendPreference) {
    model.value.sendPreference = savedSendPreference
  }

  const savedActiveEnhancedGroup = localStorage.getItem('activeEnhancedGroup')
  if (savedActiveEnhancedGroup) {
    model.value.activeEnhancedGroup = savedActiveEnhancedGroup
  }

  const savedSelectedEnhancedRole = localStorage.getItem('selectedEnhancedRole')
  if (savedSelectedEnhancedRole) {
    model.value.selectedEnhancedRole = savedSelectedEnhancedRole
  }

  // 如果启用了增强角色，加载数据
  if (model.value.enhancedRoleEnabled) {
    await loadEnhancedRoles()
  }

  // 自动加载历史会话
  await loadDialogHistory()
})

// 加载增强角色数据
const loadEnhancedRoles = async () => {
  if (!enhancedRoleEnabled.value) return

  loadingEnhancedRoles.value = true
  try {
    const response: any = await chatAPI.getSystemPromptsByGroup()
    if (response && response.success && response.groups) {
      enhancedRoleGroups.value = response.groups

      // 如果还没有激活的分组或角色，自动选择第一个
      if (!activeEnhancedGroup.value && Object.keys(enhancedRoleGroups.value).length > 0) {
        const firstGroup = Object.keys(enhancedRoleGroups.value)[0]
        activeEnhancedGroup.value = firstGroup

        // 选择该分组的第一个角色
        if (enhancedRoleGroups.value[firstGroup] && enhancedRoleGroups.value[firstGroup].length > 0) {
          selectedEnhancedRole.value = enhancedRoleGroups.value[firstGroup][0].role_name

          // 不再应用所选角色的内容到systemPrompt，因为会在发送请求时根据enhancedRoleEnabled状态来决定使用哪个内容
          // 现在只需更新选择状态，具体的内容使用延迟到请求构建时
        }
      }
    } else {
      console.error('获取增强角色数据失败:', response?.msg)
    }
  } catch (error) {
    console.error('加载增强角色时出错:', error)
  } finally {
    loadingEnhancedRoles.value = false
  }
}

// 监听contextCount变化并持久化
watch(contextCount, (newVal) => {
  localStorage.setItem('contextCount', newVal.toString())
})

// 监听maxResponseChars变化并持久化
watch(maxResponseChars, (newVal) => {
  localStorage.setItem('maxResponseChars', newVal.toString())
})

// 添加监听 sidebarCollapsed 变化并同步到父组件
watch(sidebarCollapsed, (newVal) => {
  emit('update:collapsed', newVal)
})

// 监听 sendPreference 变化并持久化
watch(sendPreference, (newVal) => {
  localStorage.setItem('sendPreference', newVal)
})

// 监听 streamEnabled 变化并持久化
watch(streamEnabled, (newVal) => {
  localStorage.setItem('streamEnabled', JSON.stringify(newVal))
})

// 监听 enhancedRoleEnabled 变化并持久化
watch(enhancedRoleEnabled, (newVal) => {
  localStorage.setItem('enhancedRoleEnabled', JSON.stringify(newVal))
})

// 监听selectedModel的变化，同步到providerValue和modelValue
watch(selectedModel, (newVal) => {
  localStorage.setItem('selectedModel', newVal)
  if (newVal && newVal !== selectedModel.value) {
    selectedModel.value = newVal

    // 根据选择的模型值找到对应的厂商
    const selectedModelInfo = models.value.find(model => model.value === newVal)
    if (selectedModelInfo) {
      providerValue.value = selectedModelInfo.group || ''
      modelValue.value = newVal

      // 设置当前模型描述
      currentModelDesc.value = selectedModelInfo.model_desc || ''
    }
  }
})
</script>

<style scoped>
.sidebar {
  height: 100%;
  border-right: 1px solid var(--el-border-color);
  transition: all 0.3s ease;
  overflow: hidden;
  position: relative;
  background: var(--el-bg-color);
}

.sidebar.sidebar-collapsed {
  width: 0 !important;
}

.sidebar.sidebar-mobile {
  position: fixed;
  top: 0;
  left: 0;
  z-index: 1000;
  height: 100vh;
}

.sidebar-content {
  padding: 20px;
  height: 100%;
  overflow-y: auto;
}

.model-selector {
  margin-bottom: 24px;
}

.model-selector h3 {
  margin: 0 0 12px 0;
  font-size: 16px;
  font-weight: 600;
}

.provider-selector {
  margin-bottom: 12px;
}

.provider-selector :deep(.el-select),
.model-selector-wrapper :deep(.el-select) {
  width: 100%;
}

.model-description {
  margin-top: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.model-desc-text {
  display: flex;
  align-items: center;
  gap: 4px;
}

.sidebar-close-btn {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 1001;
}

.dialog-history {
  margin-bottom: 24px;
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.history-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.history-list {
  height: 200px;
}

.history-item {
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 0.3s;
}

.history-item:hover {
  transform: translateX(4px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.history-item.active {
  border: 2px solid var(--el-color-primary);
  background-color: var(--el-color-primary-light-9);
}

.history-item-content {
  flex: 1;
}

.history-title {
  font-weight: 500;
  margin-bottom: 4px;
}

.history-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.history-model {
  background: var(--el-bg-color-page);
  padding: 2px 6px;
  border-radius: 4px;
}

.history-time {
  /* 为历史时间添加基本样式 */
  font-size: 11px;
  color: var(--el-text-color-secondary);
}

.history-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.3s;
}

.history-item:hover .history-actions {
  opacity: 1;
}

.settings-panel,
.role-setting,
.send-setting {
  margin-bottom: 24px;
}

.settings-panel h3,
.role-setting h3,
.send-setting h3 {
  margin: 0 0 16px 0;
  font-size: 16px;
  font-weight: 600;
}

.setting-item {
  margin-bottom: 16px;
}

.setting-item label {
  display: block;
  margin-bottom: 6px;
  font-size: 14px;
  color: var(--el-text-color-regular);
}

.preset-roles {
  margin-bottom: 16px;
}

.enhanced-role {
  margin-bottom: 0;
}

.mobile-sidebar-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 999;
}
</style>