<template>
  <!-- 侧边栏 -->
  <transition name="sidebar-slide">
    <div v-show="!formData.sidebarCollapsed" class="chat-sidebar" :class="{ 'sidebar-mobile': formData.isMobile }">
      <el-button v-if="formData.isMobile" class="sidebar-close-btn" :icon="Close" circle @click="formData.sidebarCollapsed = true" />
      <div class="model-selector" @click.stop>
        <h3>{{ t('chat.selectProvider') }}</h3>
        <div class="provider-selector">
          <el-select v-model="formData.providerValue" :placeholder="t('chat.selectProvider')" size="small" filterable clearable
            @change="handleProviderChange">
            <el-option v-for="provider in formData.providers" :key="provider" :label="provider" :value="provider" />
          </el-select>
        </div>
        <h3>{{ t('chat.selectModel') }}</h3>
        <div class="model-selector">
          <el-select v-model="formData.modelValue" :placeholder="t('chat.selectModel')" size="small" filterable clearable
            :disabled="!formData.providerValue" @change="handleModelChange">
            <el-option v-for="model in filteredModels" :key="model.value" :value="model.value">
              <span>{{ model.label }}</span>
              <el-tag v-if="model.recommend" size="small" type="warning" class="ml-2">{{ t('chat.recommended') }}</el-tag>
            </el-option>
          </el-select>
        </div>
      </div>
      <div class="dialog-history-section">
        <!-- 显示选中模型的描述 -->
        <div v-if="formData.currentModelDesc" class="model-description">
          <div class="model-desc-text">
            <el-icon>
              <InfoFilled />
            </el-icon>
            <span>{{ formData.currentModelDesc }}</span>
          </div>
        </div>
      </div>

      <div class="dialog-history-section">
        <div class="history-section-header">
          <h3>{{ t('chat.history') }}</h3>
          <div class="history-actions">
            <el-button type="default" size="small" text @click="loadDialogHistory" :loading="formData.loadingHistory" class="text-gray-700 dark:text-gray-300 hover:bg-transparent">
              {{ t('chat.refreshHistory') }}
            </el-button>
            <el-button v-if="!isEditMode" type="default" size="small" text @click="enterEditMode" class="text-blue-500 hover:bg-transparent">
              {{ t('chat.edit') }}
            </el-button>
            <div v-else class="edit-mode-actions">
              <el-button type="danger" text size="small" :disabled="selectedDialogs.length === 0"
                @click="confirmBatchDelete" class="text-red-500 hover:bg-transparent disabled:opacity-50 disabled:cursor-not-allowed">
                {{ t('chat.delete') }} ({{ selectedDialogs.length }})
              </el-button>
              <el-button type="default" size="small" text @click="exitEditMode" class="text-blue-500 hover:bg-transparent">
                {{ t('chat.cancel') }}
              </el-button>
            </div>
          </div>
        </div>

        <div class="dialog-list">
          <div v-for="dialog in formData.dialogHistory" :key="dialog.id" class="dialog-item"
            :class="{ 'selected': isEditMode && selectedDialogs.includes(dialog.id) }"
            @click="isEditMode ? toggleSelectDialog(dialog.id) : loadDialogContent(dialog.id)">
            <el-checkbox v-if="isEditMode" v-model="selectedDialogs" :label="dialog.id" @click.stop
              class="dialog-checkbox" />
            <div class="dialog-content" @click.stop="!isEditMode && loadDialogContent(dialog.id)">
              <el-tooltip :content="dialog.dialog_name" :disabled="!shouldShowTooltip(dialog.dialog_name, 'title')"
                placement="top" popper-class="custom-dark-tooltip">
                <div class="dialog-title" :style="{ maxWidth: '100%' }">
                  {{ dialog.dialog_name }}
                </div>
              </el-tooltip>
              <div class="dialog-info">
                <el-tooltip :content="dialog.modelname" :disabled="!shouldShowTooltip(dialog.modelname, 'model')"
                  placement="top" popper-class="custom-dark-tooltip">
                  <div class="dialog-model" :style="{ maxWidth: '80px' }">
                    {{ dialog.modelname }}
                  </div>
                </el-tooltip>
                <div class="dialog-date">{{ dialog.start_date }}</div>
              </div>
            </div>
            <el-popconfirm v-if="!isEditMode" title="确定要删除这个对话吗？" confirm-button-text="确定" cancel-button-text="取消"
              @confirm="confirmSingleDelete(dialog.id)" @cancel.stop>
              <template #reference>
                <el-button v-if="!isEditMode" class="delete-btn" :icon="Delete" circle size="small" text @click.stop />
              </template>
            </el-popconfirm>
          </div>
          <div v-if="formData.dialogHistory.length === 0" class="no-dialogs">
            暂无历史对话
          </div>
        </div>
      </div>

      <!-- 上下文设置部分 -->
      <div class="context-settings-section">
        <h3>{{ t('chat.contextSettings') }}</h3>
        <div class="context-slider-wrapper">
          <div class="context-label">
            <span>{{ t('chat.carryHistory') }}</span>
            <el-tag size="small" type="info">{{ formData.contextCount }} {{ t('chat.units') }}</el-tag>
          </div>
          <el-slider v-model="formData.contextCount" :min="0" :max="50" :step="1" :marks="{ 0: '0', 25: '25', 50: '50' }" />
          <div class="context-hint">{{ t('chat.setZeroToSendCurrentOnly') }}</div>
        </div>

        <!-- 最大回复字数 -->
        <div class="context-slider-wrapper">
          <div class="context-label">
            <span>{{ t('chat.maxResponseCharsReference') }}</span>
            <el-tag size="small" type="info">{{ formData.maxResponseChars }} {{ t('chat.characters') }}</el-tag>
          </div>
          <el-slider v-model="formData.maxResponseChars" :min="500" :max="32000" :step="500"
            :marks="{ 500: '500', 8000: '8千', 30000: '3万' }" />
          <div class="context-hint">{{ t('chat.aiReplyLengthLimit') }}</div>
        </div>

        <!-- 流式输出开关 -->
        <div class="context-switch-wrapper">
          <div class="context-label">
            <span>{{ t('chat.characterByCharacterOutput') }}</span>
            <el-switch v-model="formData.streamEnabled" :active-text="t('chat.enable')" :inactive-text="t('chat.disable')" size="default" />
          </div>
          <div class="context-hint">{{ t('chat.characterByCharacterOutputHint') }}</div>
        </div>
      </div>

      <!-- 角色设定部分 -->
      <div class="system-prompt-section">
        <h3>{{ t('chat.roleSettingTitle') }}</h3>
        <el-input v-model="formData.systemPrompt" type="textarea" :rows="3" :disabled="formData.enhancedRoleEnabled"
          :placeholder="t('chat.systemPromptPlaceholderSidebar')" resize="vertical" @blur="handleSystemPromptBlur" />
        <div class="system-prompt-hint">{{ t('chat.aiBehaviorHint') }}</div>

        <!-- 角色设定选项卡 - 当启用增强角色时禁用 -->
        <div :class="{ 'role-tabs': true, 'disabled': formData.enhancedRoleEnabled }">
          <div v-for="role in formData.rolePresets" :key="role.id" class="role-tab"
            :class="{ active: formData.activeRoleId === role.id }">
            <span @click="switchRole(role)">{{ role.name }}</span>
            <div class="role-tab-actions" v-if="!['default', 'programmer', 'translator', 'writer'].includes(role.id)">
              <el-dropdown trigger="click" @command="(command: string) => handleRoleAction(command, role.id)">
                <el-button text size="small" class="role-action-btn">
                  <el-icon>
                    <MoreFilled />
                  </el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="rename">
                      <el-icon>
                        <EditPen />
                      </el-icon>
                      {{ t('chat.rename') }}
                    </el-dropdown-item>
                    <el-dropdown-item command="delete" divided>
                      <el-icon>
                        <Delete />
                      </el-icon>
                      {{ t('chat.delete') }}
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </div>
          <div class="role-tab add-tab" @click="addCustomRole">
            <el-icon>
              <Plus />
            </el-icon>
          </div>
        </div>

        <!-- 增强角色选择 -->
        <div class="enhanced-role-section">
          <div class="enhanced-role-toggle">
            <el-checkbox v-model="formData.enhancedRoleEnabled" @change="handleEnhancedRoleToggle">
              {{ t('chat.enableEnhancedRole') }}
            </el-checkbox>
            <el-icon v-if="loadingEnhancedRoles" class="is-loading">
              <Loading />
            </el-icon>
          </div>

          <!-- 增强角色界面，只有在启用时才显示 -->
          <div v-if="formData.enhancedRoleEnabled" class="enhanced-role-interface">
            <!-- 分组标签 -->
            <el-tabs v-model="formData.activeEnhancedGroup" type="card" @tab-change="handleGroupChange">
              <el-tab-pane v-for="(roles, groupName) in formData.enhancedRoleGroups" :key="groupName" :label="groupName"
                :name="groupName">
              </el-tab-pane>
            </el-tabs>

            <!-- 角色列表 -->
            <div v-if="formData.activeEnhancedGroup && formData.enhancedRoleGroups[formData.activeEnhancedGroup]" class="enhanced-role-list">
              <el-radio-group v-model="formData.selectedEnhancedRole" @change="handleEnhancedRoleSelect">
                <div v-for="role in formData.enhancedRoleGroups[formData.activeEnhancedGroup]" :key="role.role_name"
                  class="enhanced-role-item">
                  <el-radio :value="role.role_name" border class="enhanced-role-radio">
                    <div class="role-info">
                      <div class="role-name">{{ role.role_name }}</div>
                      <div class="role-desc">{{ role.role_desc }}</div>
                    </div>
                  </el-radio>
                </div>
              </el-radio-group>
            </div>
          </div>
        </div>
      </div>

      <!-- 发送键偏好设置 -->
      <div class="send-preference-section">
        <h3>{{ t('chat.sendSetting') }}</h3>
        <div class="send-preference-wrapper">
          <el-switch v-model="formData.sendPreference" :active-value="'enter'" :inactive-value="'ctrl_enter'"
            :active-text="t('chat.enterToSend')" :inactive-text="t('chat.ctrlEnterToSend')" />
          <div class="send-preference-hint">
            {{ t('chat.currentSendMethod') }}{{ formData.sendPreference === 'enter' ? t('chat.currentSendMethodEnter') : t('chat.currentSendMethodCtrlEnter') }}
          </div>
        </div>
      </div>
    </div>
  </transition>

  <!-- 移动端遮罩 -->
  <div v-if="formData.isMobile && !formData.sidebarCollapsed" class="mobile-sidebar-mask" @click="formData.sidebarCollapsed = true" />
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useI18n } from 'vue-i18n'
import {

  Delete,
  Plus,
  Close,
  MoreFilled,
  EditPen,
  Loading,
  InfoFilled,
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { chatAPI } from '@/services/api'
import { FormData } from '@/utils/main'
import 'highlight.js/styles/github-dark.css'
import 'katex/dist/katex.min.css'
import VersionService from '@/services/version'

// 定义 props 和 emits
const props = defineProps<{
  modelValue: FormData
}>()

const emit = defineEmits<{
  'update:modelValue': [value: any]
  'load-dialog': [dialogId: number]
  'clear-session': [value: any]
  'refresh-history': []
}>()

// Component-specific state (not shared through formData)
const messagesContainer = ref<HTMLElement>()

// 控制是否显示回到顶部按钮
const showBackToTop = ref(false)

// 用于检测软键盘是否激活的状态
const isKeyboardVisible = ref(false)
// Access formData through props.modelValue

// 使用从父组件传递过来的props访问formData，如果不存在则返回一个空对象
const formData = (props.modelValue || {}) as FormData

// 添加对话历史管理的本地状态
const isEditMode = ref(false)
const selectedDialogs = ref<number[]>([])

// TODO(human): 添加发送键偏好设置，默认为 'ctrl_enter'，表示使用Ctrl+Enter发送；若为 'enter' 则直接按Enter发送
// 实现逻辑应该在发送消息的函数中根据这个设置来决定是监听Ctrl+Enter还是Enter键

// 切换角色函数
const switchRole = (role: { id: string, name: string, prompt: string }) => {
  formData.activeRoleId = role.id
  formData.systemPrompt = role.prompt
  localStorage.setItem('activeRoleId', role.id)
  localStorage.setItem('systemPrompt', role.prompt) // 同时保存当前prompt到localStorage
}

// 添加自定义角色函数
const addCustomRole = () => {
  // 添加自定义角色的逻辑
  const newId = `custom_${Date.now()}`
  formData.rolePresets.push({
    id: newId,
    name: '自定义',
    prompt: formData.systemPrompt
  })
  formData.activeRoleId = newId
  localStorage.setItem('activeRoleId', newId)
  localStorage.setItem('systemPrompt', formData.systemPrompt) // 同时保存当前prompt到localStorage
  saveCustomRoles() // 保存自定义角色
}

// 处理系统提示词输入框失焦事件
const handleSystemPromptBlur = () => {
  // 更新当前选中角色的prompt内容
  const currentRole = formData.rolePresets.find(r => r.id === formData.activeRoleId)
  if (currentRole && !['default', 'programmer', 'translator', 'writer'].includes(currentRole.id)) {
    currentRole.prompt = formData.systemPrompt
    saveCustomRoles() // 保存自定义角色
  }
}

// 加载增强角色数据
const loadEnhancedRoles = async () => {
  if (!formData.enhancedRoleEnabled) return

  loadingEnhancedRoles.value = true
  try {
    const response: any = await chatAPI.getSystemPromptsByGroup()
    if (response && response.success && response.groups) {
      formData.enhancedRoleGroups = response.groups

      // 如果还没有激活的分组或角色，自动选择第一个
      if (!formData.activeEnhancedGroup && Object.keys(formData.enhancedRoleGroups).length > 0) {
        const firstGroup = Object.keys(formData.enhancedRoleGroups)[0]
        formData.activeEnhancedGroup = firstGroup

        // 选择该分组的第一个角色
        if (formData.enhancedRoleGroups[firstGroup] && formData.enhancedRoleGroups[firstGroup].length > 0) {
          formData.selectedEnhancedRole = formData.enhancedRoleGroups[firstGroup][0].role_name

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

// 处理增强角色启用状态切换
const handleEnhancedRoleToggle = (enabled: boolean) => {
  formData.enhancedRoleEnabled = enabled
  localStorage.setItem('enhancedRoleEnabled', JSON.stringify(enabled))

  if (enabled) {
    // 启用增强角色时，只需要更新状态，不在这里修改systemPrompt
    // systemPrompt值将在发送请求时根据enhancedRoleEnabled状态来决定使用哪个内容
    // 加载数据并准备使用第一个角色
    loadEnhancedRoles()
  } else {
    // 禁用增强角色时，也不需要恢复原来的预设角色内容到systemPrompt
    // 因为现在是在请求时根据状态来决定使用哪个内容
  }
}

// 处理增强角色分组切换
const handleGroupChange = (groupName: string) => {
  formData.activeEnhancedGroup = groupName
  localStorage.setItem('activeEnhancedGroup', groupName)

  // 选择该分组的第一个角色
  if (formData.enhancedRoleGroups[groupName] && formData.enhancedRoleGroups[groupName].length > 0) {
    formData.selectedEnhancedRole = formData.enhancedRoleGroups[groupName][0].role_name

    // 不再应用所选角色的内容到systemPrompt，因为会在发送请求时根据enhancedRoleEnabled状态来决定使用哪个内容
    // 现在只需更新选择状态，具体的内容使用延迟到请求构建时

    // 保存到localStorage
    localStorage.setItem('selectedEnhancedRole', formData.selectedEnhancedRole)
  }
}

// 处理增强角色选择
const handleEnhancedRoleSelect = (roleName: string) => {
  formData.selectedEnhancedRole = roleName
  localStorage.setItem('selectedEnhancedRole', roleName)

  // 不再应用所选角色的内容到systemPrompt，因为会在发送请求时根据enhancedRoleEnabled状态来决定使用哪个内容
  // 现在只需更新选择状态，具体的内容使用延迟到请求构建时
}

// 重命名角色函数
const renameRole = (roleId: string) => {
  const role = formData.rolePresets.find(r => r.id === roleId)
  if (role) {
    const newName = prompt('请输入新的角色名称:', role.name)
    if (newName && newName.trim()) {
      role.name = newName.trim()
      // 如果当前角色被重命名，则更新本地存储
      if (formData.activeRoleId === roleId) {
        localStorage.setItem('activeRoleId', roleId)
      }
      saveCustomRoles() // 保存自定义角色
    }
  }
}

// 保存自定义角色到localStorage
const saveCustomRoles = () => {
  const customRoles = formData.rolePresets.filter(
    role => !['default', 'programmer', 'translator', 'writer'].includes(role.id)
  )
  localStorage.setItem('customRoles', JSON.stringify(customRoles))
}

// 处理厂商选择变化
const handleProviderChange = (value: string) => {
  // 当厂商改变时，清空已选择的模型
  formData.modelValue = ''
  // 如果值被清空，也清空selectedModel
  if (!value) {
    formData.selectedModel = ''
  }
}

// 处理模型选择变化
const handleModelChange = (value: string) => {
  // 更新主selectedModel变量
  formData.selectedModel = value

  // 更新当前模型描述
  const selectedModelObj = formData.models.find(model => model.value === value)
  formData.currentModelDesc = selectedModelObj?.model_desc || ''
  formData.selectedModelType = selectedModelObj?.model_type || 1
}

// 更新厂商列表
const updateProviders = () => {
  // 从模型列表中提取厂商名称（基于模型值中的前缀）
  const uniqueProviders = new Set<string>()

  formData.models.forEach(model => {
    uniqueProviders.add(model.group)
  })

  formData.providers = Array.from(uniqueProviders).sort()
}

const filteredModels = computed(() => {
  if (!formData.providerValue) return []
  // 根据当前选择的厂商过滤模型，并按推荐状态排序
  const providerModels = formData.models.filter(model => {
    // 检查模型值是否包含厂商名称
    return model.value.toLowerCase().includes(formData.providerValue.toLowerCase()) ||
           model.label.toLowerCase().includes(formData.providerValue.toLowerCase())
  })

  // 按推荐状态排序：推荐的模型在前面
  return providerModels.sort((a, b) => {
    if (a.recommend && !b.recommend) return -1
    if (!a.recommend && b.recommend) return 1
    return 0
  })
})

// 删除角色函数
const deleteRole = (roleId: string) => {
  // 只允许删除自定义角色，不允许删除预设角色
  if (['default', 'programmer', 'translator', 'writer'].includes(roleId)) {
    ElMessage.warning('不能删除预设角色')
    return
  }

  const roleIndex = formData.rolePresets.findIndex(r => r.id === roleId)
  if (roleIndex !== -1) {
    const roleName = formData.rolePresets[roleIndex].name
    ElMessageBox.confirm(
      `确定要删除角色 "${roleName}" 吗？`,
      '删除角色',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    ).then(() => {
      formData.rolePresets.splice(roleIndex, 1)
      saveCustomRoles() // 保存自定义角色

      // 如果删除的是当前选中的角色，则切换到默认角色
      if (formData.activeRoleId === roleId) {
        const defaultRole = formData.rolePresets.find(r => r.id === 'default')
        if (defaultRole) {
          switchRole(defaultRole)
        }
      }

      ElMessage.success('角色已删除')
    }).catch(() => {
      // 用户取消删除
    })
  }
}

// 从localStorage加载自定义角色
const loadCustomRoles = () => {
  const saved = localStorage.getItem('customRoles')
  if (saved && formData.rolePresets) {
    try {
      // 追加到预设角色后面
      const customRoles = JSON.parse(saved)
      if (Array.isArray(customRoles) && customRoles.length > 0) {
        // 避免重复添加相同ID的角色
        const existingIds = new Set(formData.rolePresets.map(role => role.id))
        const uniqueCustomRoles = customRoles.filter(role => !existingIds.has(role.id))

        formData.rolePresets.push(...uniqueCustomRoles)
      }
    } catch (e) {
      console.error('加载自定义角色失败:', e)
    }
  }
}

// 处理角色操作
const handleRoleAction = (command: string, roleId: string) => {
  switch (command) {
    case 'rename':
      renameRole(roleId)
      break
    case 'delete':
      deleteRole(roleId)
      break
    default:
      console.warn(`Unknown role command: ${command}`)
      break
  }
}

// 添加级联选择器状态变量
const cascaderValue = ref<string[]>([])
const cascaderOptions = ref<any[]>([])

// 将原始模型列表转换为级联选项
const convertModelsToCascaderOptions = (modelList: Array<{ label: string, value: string }>) => {
  // 使用真实获取的分组数据
  if (Object.keys(formData.groupedModels).length > 0) {
    // 如果已有分组数据，直接使用
    return Object.entries(formData.groupedModels)
      .filter(([_, models]) => models.length > 0) // 只包含有模型的分组
      .map(([groupName, models]) => ({
        value: groupName,
        label: groupName.charAt(0).toUpperCase() + groupName.slice(1), // 首字母大写
        children: (models as any[]).map(model => ({
          value: model.id,
          label: model.label || model.id
        }))
      }));
  } else {
    // 回退到按关键词匹配的方式
    const prefixes = ['gpt', 'gemini', 'qwen', 'nano-banana', 'deepseek'];

    // 按前缀分组模型
    const grouped: Record<string, { label: string, value: string }[]> = {};

    // 初始化分组
    prefixes.forEach(prefix => {
      grouped[prefix] = [];
    });

    // 分类模型
    modelList.forEach(model => {
      const lowerValue = model.value.toLowerCase();
      let matched = false;

      // 按优先级匹配前缀
      for (const prefix of prefixes) {
        if (lowerValue.includes(prefix)) {
          grouped[prefix].push(model);
          matched = true;
          break;
        }
      }

      // 如果没有匹配到任何前缀，放入"其他"分组
      if (!matched) {
        if (!grouped['other']) {
          grouped['other'] = [];
        }
        grouped['other'].push(model);
      }
    });

    // 生成级联选项
    return Object.entries(grouped)
      .filter(([_, models]) => models.length > 0) // 只包含有模型的分组
      .map(([groupName, models]) => {
        // 显示友好名称
        let displayName = groupName;
        if (groupName === 'other') displayName = '其他';

        return {
          value: groupName,
          label: displayName.charAt(0).toUpperCase() + displayName.slice(1), // 首字母大写
          children: models.map(model => ({
            value: model.value,
            label: model.label || model.value
          }))
        }
      });
  }
}

// 监听模型列表变化，自动生成级联选项
watch(() => formData.models, (newModels) => {
  if (newModels && newModels.length > 0) {
    cascaderOptions.value = convertModelsToCascaderOptions(newModels)
    // 新增：同步 cascaderValue
    if (formData.selectedModel) {
      for (const group of cascaderOptions.value) {
        const modelOption = group.children.find((child: any) => child.value === formData.selectedModel)
        if (modelOption) {
          cascaderValue.value = [group.value, modelOption.value]
          break
        }
      }
    }
  }
}, { deep: true })

// 监听selectedModel变化，同步更新级联选择器
watch(() => formData.selectedModel, (newValue) => {
  if (newValue) {
    // 找到对应的分组和模型
    for (const group of cascaderOptions.value) {
      const modelOption = group.children.find((child: any) => child.value === newValue)
      if (modelOption) {
        cascaderValue.value = [group.value, modelOption.value]
        return
      }
    }
  } else {
    cascaderValue.value = []
  }
})

// Component-specific reactive state that isn't shared through formData and needs initialization
const loadingEnhancedRoles = ref(false)

// 使用国际化
const { t } = useI18n()


// 加载对话历史
const loadDialogHistory = async () => {
  if (!useAuthStore().user) {
    ElMessage.warning('请先登录')
    return
  }

  formData.loadingHistory = true
  try {
    const response: any = await chatAPI.getDialogHistory()
    if (response && response.content) {
      formData.dialogHistory = response.content
      // 设置最新的对话ID为当前对话ID
      if (response.content.length > 0) {
        formData.currentDialogId = response.content[0].id
        formData.dialogTitle = response.content[0].dialog_name || ''
      }
      // ElMessage.success(`加载了 ${response.content.length} 条历史对话`)
    } else {
      formData.dialogHistory = []
      ElMessage.info('暂无历史对话')
    }
  } catch (error: any) {
    console.error('加载对话历史错误:', error)
    ElMessage.error('加载对话历史失败')
  } finally {
    formData.loadingHistory = false
  }
}

// 清空当前会话
const clearCurrentSession = () => {
  // 清空对话标题和当前对话ID
  formData.dialogTitle = ''
  formData.currentDialogId = null
  ElMessage.success('已开启新会话')

  // 通知父组件或ChatContent组件清空消息
  emit('clear-session', {})
}

// 加载特定对话内容
const loadDialogContent = async (dialogId: number) => {
  if (!useAuthStore().user) {
    ElMessage.warning('请先登录')
    return
  }
  const dialogItem = formData.dialogHistory.find(d => d.id === dialogId)
  if (dialogItem) {
    formData.dialogTitle = dialogItem.dialog_name
    
    // 根据历史对话的模型信息更新当前模型选择
    if (dialogItem.modelname) {
      const targetModel = formData.models.find(model =>
        model.value === dialogItem.modelname ||
        model.label === dialogItem.modelname
      )
      
      if (targetModel) {
        // 更新供应商选择
        formData.providerValue = targetModel.group
        // 更新模型选择
        formData.modelValue = targetModel.value
        formData.selectedModel = targetModel.value
        // 更新模型描述
        formData.currentModelDesc = targetModel.model_desc || ''
        formData.selectedModelType = targetModel.model_type || 1
      } else {
        console.warn(`未找到匹配的模型: ${dialogItem.modelname}`)
      }
    }
  }
  // 通知父组件或ChatContent组件加载对话内容
  emit('load-dialog', dialogId)
}

// 检测移动设备
const checkMobile = () => {
  const wasMobile = formData.isMobile;
  formData.isMobile = window.innerWidth < 768

  // 只在首次检测到移动设备或从桌面切换到移动设备时折叠侧边栏
  // 避免在移动端键盘弹出/隐藏时重复折叠侧边栏
  if (formData.isMobile && !wasMobile) {
    formData.sidebarCollapsed = true
  }
}

// 处理软键盘显示/隐藏
const handleResize = () => {
  // 检测是否为移动设备上的键盘变化
  const currentIsMobile = window.innerWidth < 768
  if (currentIsMobile) {
    // 使用屏幕高度变化来判断键盘是否弹出
    const screenHeight = window.screen.height
    const windowHeight = window.innerHeight

    // 如果窗口高度明显小于屏幕高度，很可能是因为键盘弹出了
    const likelyKeyboardVisible = screenHeight - windowHeight > 150

    if (likelyKeyboardVisible !== isKeyboardVisible.value) {
      isKeyboardVisible.value = likelyKeyboardVisible

      // 如果键盘弹出，延时滚动到底部确保输入框和按钮可见
      if (likelyKeyboardVisible) {
        setTimeout(() => {
          scrollToBottom()
        }, 300) // 给一点时间让键盘完全弹出
      }
    }
  }
}

const scrollToBottom = () => {
  if (messagesContainer.value && formData.isScrolledToBottom) {
    // 只有在用户已经滚动到底部时才继续滚动
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

// 监听滚动事件，判断用户是否滚动到了底部
const handleScroll = () => {
  if (messagesContainer.value) {
    const { scrollTop, scrollHeight, clientHeight } = messagesContainer.value
    // 如果距离底部小于50像素，则认为是在底部
    formData.isScrolledToBottom = scrollHeight - scrollTop - clientHeight < 50

    // 控制回到顶部按钮的显示：当滚动位置超过一屏时显示
    showBackToTop.value = scrollTop > clientHeight

    // 如果软键盘弹出，自动保持滚动到底部
    if (isKeyboardVisible.value) {
      scrollToBottom()
    }
  }
}


// 进入编辑模式
const enterEditMode = () => {
  isEditMode.value = true
  selectedDialogs.value = []
}

// 退出编辑模式
const exitEditMode = () => {
  isEditMode.value = false
  selectedDialogs.value = []
}

// 切换选择对话
const toggleSelectDialog = (dialogId: number) => {
  const index = selectedDialogs.value.indexOf(dialogId)
  if (index > -1) {
    selectedDialogs.value.splice(index, 1)
  } else {
    selectedDialogs.value.push(dialogId)
  }
}

// 通用删除对话功能
const deleteDialogs = async (dialogIds: number[]) => {
  try {
    const response: any = await chatAPI.deleteDialogs(dialogIds)
    if (response && response.success) {
      ElMessage.success(`${dialogIds.length === 1 ? '对话' : '批量'}删除成功，共删除 ${response.deleted_count} 条`)

      // 如果是批量删除，退出编辑模式
      if (dialogIds.length > 1) {
        exitEditMode()
      }

      // 刷新对话历史
      await loadDialogHistory()

      // 检查当前会话是否被删除，如果是则清空聊天内容
      const currentDialog = formData.dialogHistory.find(d => d.dialog_name === formData.dialogTitle)
      if (currentDialog && dialogIds.includes(currentDialog.id)) {
        clearCurrentSession()
      }
    } else {
      ElMessage.error(`${dialogIds.length === 1 ? '删除对话' : '批量删除'}失败`)
    }
  } catch (error: any) {
    console.error(`${dialogIds.length === 1 ? '删除对话' : '批量删除'}错误:`, error)
    ElMessage.error(`${dialogIds.length === 1 ? '删除对话' : '批量删除'}失败`)
  }
}

// 确认单个删除
const confirmSingleDelete = async (dialogId: number) => {
  await deleteDialogs([dialogId])
}

// 确认批量删除
const confirmBatchDelete = async () => {
  if (selectedDialogs.value.length === 0) {
    ElMessage.warning('请至少选择一个对话')
    return
  }

  await deleteDialogs(selectedDialogs.value)
}

// 通用事件监听器管理函数
const addEventListeners = () => {
  // 添加移动端检测和事件监听
  checkMobile()
  window.addEventListener('resize', checkMobile)

  // 添加resize事件监听器以处理软键盘弹出/收起
  window.addEventListener('resize', handleResize)

  // 添加滚动事件监听器
  if (messagesContainer.value) {
    messagesContainer.value.addEventListener('scroll', handleScroll)
    // 初始化滚动位置状态
    handleScroll()
  }
}

const removeEventListeners = () => {
  window.removeEventListener('resize', checkMobile)
  window.removeEventListener('resize', handleResize) // 移除软键盘检测监听器
  // 移除滚动事件监听器
  if (messagesContainer.value) {
    messagesContainer.value.removeEventListener('scroll', handleScroll)
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
      formData.groupedModels = response.grouped_models;

      // 将分组模型展平为普通列表
      formData.models = [];
      for (const [prefix, modelList] of Object.entries(response.grouped_models)) {
        (modelList as Array<any>).forEach((model: any) => {
          formData.models.push({
            group: prefix,
            label: `${prefix}: ${model.label || model.id}`,
            value: model.id,
            recommend: model.recommend || false,
            model_desc: model.model_desc || '',
            model_type: model.model_type || 1,
          });
        });
      }
    } else {
      // 如果获取分组模型失败，回退到普通模型列表
      const normalResponse: any = await chatAPI.getModels();
      if (normalResponse && normalResponse.success && normalResponse.models) {
        formData.models = normalResponse.models.map((model: any) => ({
          label: model.label,
          value: model.id,
          recommend: model.recommend || false,
          model_desc: model.model_desc || '',
          model_type: model.model_type || 1,
        }));
      } else {
        console.error('获取模型列表失败:', response?.msg || normalResponse?.msg)
        // 设置默认模型列表作为备选
        formData.models = [
          { group: "gpt", label: 'GPT-4o mini', value: 'gpt-4o-mini', recommend: false, model_desc: '', model_type: 1 },
          { group: "gpt", label: 'GPT-4o', value: 'gpt-4o', recommend: false, model_desc: '', model_type: 1 },
          { group: "gpt", label: 'GPT-3.5-turbo', value: 'gpt-3.5-turbo', recommend: false, model_desc: '', model_type: 1 }
        ]
      }
    }
  } catch (error) {
    console.error('加载模型列表时出错:', error)
    // 设置默认模型列表作为备选
    formData.models = [
      { group: "gpt", label: 'GPT-4o mini', value: 'gpt-4o-mini', recommend: false, model_desc: '' },
      { group: "gpt", label: 'GPT-4o', value: 'gpt-4o', recommend: false, model_desc: '' },
      { group: "gpt", label: 'GPT-3.5-turbo', value: 'gpt-3.5-turbo', recommend: false, model_desc: '' }
    ]
  }

  // 更新供应商列表
  updateProviders()

  // 如果有保存的模型选择，设置对应的供应商和模型
  if (formData.selectedModel) {
    // 根据选择的模型值找到对应的供应商
    const selectedModelInfo = formData.models.find(model => model.value === formData.selectedModel)
    if (selectedModelInfo) {
      formData.providerValue = selectedModelInfo.group
      formData.modelValue = formData.selectedModel

      // 设置当前模型描述
      formData.currentModelDesc = selectedModelInfo.model_desc || ''
    }
  }

  // 注释掉从localStorage恢复对话标题的功能，实现每次刷新页面时标题栏都为空
  // const savedDialogTitle = localStorage.getItem('dialogTitle')
  // if (savedDialogTitle) {
  //   formData.dialogTitle = savedDialogTitle
  // }

  // 从localStorage恢复发送键偏好
  const savedSendPreference = localStorage.getItem('sendPreference')
  if (savedSendPreference) {
    formData.sendPreference = savedSendPreference
  }

  // 从localStorage恢复增强角色设置
  const savedEnhancedRoleEnabled = localStorage.getItem('enhancedRoleEnabled')
  if (savedEnhancedRoleEnabled) {
    formData.enhancedRoleEnabled = JSON.parse(savedEnhancedRoleEnabled)
  }

  const savedActiveEnhancedGroup = localStorage.getItem('activeEnhancedGroup')
  if (savedActiveEnhancedGroup) {
    formData.activeEnhancedGroup = savedActiveEnhancedGroup
  }

  const savedSelectedEnhancedRole = localStorage.getItem('selectedEnhancedRole')
  if (savedSelectedEnhancedRole) {
    formData.selectedEnhancedRole = savedSelectedEnhancedRole
  }

  // 如果启用了增强角色，加载数据
  if (formData.enhancedRoleEnabled) {
    await loadEnhancedRoles()
  }

  // 自动加载历史会话
  await loadDialogHistory()

  // 添加事件监听器
  addEventListeners()
})

// 组件卸载时移除事件监听
onUnmounted(() => {
  removeEventListeners()
})

/**
 * 判断是否应该显示tooltip
 * @param text 文本内容
 * @param type 类型（title 或 model）
 * @returns 是否显示tooltip
 */
const shouldShowTooltip = (text: string, type: 'title' | 'model') => {
  // 对于对话标题，如果长度超过30个字符则显示tooltip
  if (type === 'title') {
    return text && text.length > 20
  }
  // 对于模型名称，如果长度超过15个字符则显示tooltip
  else if (type === 'model') {
    return text && text.length > 12
  }
  return false
}

</script>

<style scoped>
@import '@/styles/chat-sidebar.css';
</style>
