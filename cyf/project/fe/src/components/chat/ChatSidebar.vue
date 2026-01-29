<template>
  <div
    :class="['sidebar', { 'sidebar-collapsed': collapsed, 'sidebar-mobile': isMobile }]"
    :style="{ width: collapsed ? '0' : (isMobile ? '100%' : '300px') }"
  >
    <div class="sidebar-content">
      <!-- 模型选择 -->
      <div class="model-selector">
        <h3>{{ t('chat.model') }}</h3>
        <el-select
          v-model="selectedModel"
          class="model-select"
          @change="handleModelChange"
        >
          <el-option-group
            v-for="group in modelOptions"
            :key="group.vendor"
            :label="group.vendor"
          >
            <el-option
              v-for="model in group.models"
              :key="model.value"
              :label="model.label"
              :value="model.value"
            >
              <span>{{ model.label }}</span>
              <el-tooltip
                effect="dark"
                :content="model.description"
                placement="top"
              >
                <el-icon class="model-info-icon">
                  <InfoFilled />
                </el-icon>
              </el-tooltip>
            </el-option>
          </el-option-group>
        </el-select>

        <!-- 模型描述 -->
        <div class="model-description">
          {{ getModelDescription(selectedModel) }}
        </div>
      </div>

      <!-- 对话历史 -->
      <div class="dialog-history">
        <div class="history-header">
          <h3>{{ t('chat.history') }}</h3>
          <el-button
            icon="Refresh"
            size="small"
            @click="refreshHistory"
            :loading="historyLoading"
          />
        </div>
        <el-scrollbar class="history-list">
          <el-card
            v-for="dialog in dialogList"
            :key="dialog.id"
            :class="[
              'history-item',
              { 'active': currentDialogId === dialog.id }
            ]"
            @click="loadDialog(dialog.id)"
          >
            <div class="history-item-content">
              <div class="history-title">{{ dialog.title }}</div>
              <div class="history-meta">
                <span class="history-model">{{ dialog.model }}</span>
                <span class="history-time">{{ formatDate(dialog.updateTime) }}</span>
              </div>
            </div>
            <div class="history-actions">
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
          </el-card>
        </el-scrollbar>
      </div>

      <!-- 设置面板 -->
      <div class="settings-panel">
        <h3>{{ t('chat.settings') }}</h3>

        <!-- 上下文设置 -->
        <div class="setting-item">
          <label>{{ t('chat.contextCount') }}</label>
          <el-input-number
            v-model="contextCount"
            :min="0"
            :max="20"
            @change="handleSettingsChange"
          />
        </div>

        <div class="setting-item">
          <label>{{ t('chat.maxResponseChars') }}</label>
          <el-input-number
            v-model="maxResponseChars"
            :min="100"
            :max="10000"
            @change="handleSettingsChange"
          />
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
          />
        </div>

        <div class="preset-roles">
          <label>{{ t('chat.presetRoles') }}</label>
          <el-select
            v-model="selectedPresetRole"
            @change="applyPresetRole"
            :placeholder="t('chat.selectPresetRole')"
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
            v-model="useEnhancedRole"
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
    v-if="isMobile && !collapsed"
    class="mobile-sidebar-mask"
    @click="closeMobileSidebar"
  />
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { InfoFilled } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import { ChatSidebarProps, ChatSidebarEmits, DialogItem, ChatSettings } from './types'

// 接收 props
const props = defineProps<ChatSidebarProps>()

// 定义 emits
const emit = defineEmits<ChatSidebarEmits>()

// 国际化
const { t } = useI18n()

// 本地状态
const selectedModel = ref('')
const contextCount = ref(5)
const maxResponseChars = ref(2000)
const streamEnabled = ref(true)
const systemPrompt = ref('')
const sendPreference = ref<'enter' | 'ctrl_enter'>('enter')
const selectedPresetRole = ref('')
const useEnhancedRole = ref(false)
const dialogList = ref<DialogItem[]>([])
const historyLoading = ref(false)

// 模型选项
const modelOptions = computed(() => [
  {
    vendor: 'OpenAI',
    models: [
      { value: 'gpt-4o', label: 'GPT-4o', description: '最新的高性能模型' },
      { value: 'gpt-4o-mini', label: 'GPT-4o mini', description: '高效经济型模型' },
      { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo', description: '快速响应模型' }
    ]
  },
  {
    vendor: 'Image Generation',
    models: [
      { value: 'dall-e-3', label: 'DALL-E 3', description: '高质量图像生成' }
    ]
  }
])

// 预设角色
const presetRoles = [
  { value: 'assistant', label: '助手' },
  { value: 'translator', label: '翻译家' },
  { value: 'writer', label: '作家' },
  { value: 'programmer', label: '程序员' }
]

// 获取模型描述
const getModelDescription = (model: string) => {
  for (const group of modelOptions.value) {
    const modelInfo = group.models.find(m => m.value === model)
    if (modelInfo) {
      return modelInfo.description
    }
  }
  return ''
}

// 处理模型变化
const handleModelChange = (value: string) => {
  selectedModel.value = value
  emit('model-change', value)

  // 如果当前没有对话或当前对话不是基于此模型，则创建新的对话
  if (!props.currentDialogId) {
    emit('update:currentDialogId', null)
  }
}

// 刷新历史
const refreshHistory = async () => {
  historyLoading.value = true
  try {
    // 这里应该是实际的API调用来获取对话历史
    // 模拟数据
    dialogList.value = [
      { id: 1, title: '项目讨论', model: 'gpt-4o', createTime: '2024-01-01', updateTime: '2024-01-01' },
      { id: 2, title: '代码审查', model: 'gpt-3.5-turbo', createTime: '2024-01-02', updateTime: '2024-01-02' },
      { id: 3, title: '文档编写', model: 'gpt-4o-mini', createTime: '2024-01-03', updateTime: '2024-01-03' }
    ]
  } catch (error) {
    ElMessage.error('加载对话历史失败')
  } finally {
    historyLoading.value = false
  }
}

// 加载对话
const loadDialog = (dialogId: number) => {
  emit('load-dialog', dialogId)
}

// 编辑对话标题
const editDialogTitle = (dialog: DialogItem) => {
  ElMessageBox.prompt('请输入新的对话标题', '编辑标题', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    inputValue: dialog.title
  }).then(({ value }) => {
    // 这里应该是实际的API调用来更新对话标题
    console.log(`更新对话 ${dialog.id} 的标题为: ${value}`)
    refreshHistory()
  })
}

// 删除对话
const deleteDialog = async (dialogId: number) => {
  try {
    await ElMessageBox.confirm(
      '确定要删除这个对话吗？',
      '删除对话',
      { type: 'warning' }
    )

    // 这里应该是实际的API调用来删除对话
    console.log(`删除对话: ${dialogId}`)
    if (props.currentDialogId === dialogId) {
      emit('update:currentDialogId', null)
    }
    refreshHistory()
    ElMessage.success('删除成功')
  } catch {
    // 用户取消操作
  }
}

// 应用预设角色
const applyPresetRole = (roleValue: string) => {
  const rolePrompts: Record<string, string> = {
    assistant: '你是一个有用的助手，能够回答各种问题并提供帮助。',
    translator: '你是一个专业的翻译家，能够准确翻译各种语言的文本。',
    writer: '你是一个有才华的作家，能够创作各种类型的文本内容。',
    programmer: '你是一个经验丰富的程序员，能够帮助解决编程问题。'
  }

  systemPrompt.value = rolePrompts[roleValue] || ''
  handleSettingsChange()
}

// 处理设置变化
const handleSettingsChange = () => {
  const settings: ChatSettings = {
    contextCount: contextCount.value,
    maxResponseChars: maxResponseChars.value,
    streamEnabled: streamEnabled.value,
    systemPrompt: systemPrompt.value,
    sendPreference: sendPreference.value
  }
  emit('settings-change', settings)
}

// 关闭移动端侧边栏
const closeMobileSidebar = () => {
  emit('update:collapsed', true)
}

// 格式化日期
const formatDate = (dateString: string) => {
  const date = new Date(dateString)
  return date.toLocaleDateString()
}

// 初始化
onMounted(() => {
  refreshHistory()
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

.model-select {
  width: 100%;
}

.model-info-icon {
  margin-left: 8px;
  color: var(--el-text-color-secondary);
  cursor: pointer;
}

.model-description {
  margin-top: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
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

.history-time {}

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