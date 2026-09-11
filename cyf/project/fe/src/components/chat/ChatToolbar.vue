<template>
  <div class="chat-toolbar">
    <!-- 在桌面端显示完整toolbar，在移动端显示抽屉切换按钮 -->
    <div v-if="!formData.isMobile" class="toolbar-desktop">
      <!-- 对话标题编辑区域 -->
      <div class="dialog-title-editor">
        <el-input v-model="formData.dialogTitle" :placeholder="t('chat.enterDialogTitle')" size="small"/>
        <el-button v-if="formData.currentDialogId" type="success" size="small" @click="$emit('update-dialog-title')"
          class="update-title-btn" :disabled="!formData.dialogTitle.trim()">
          {{ t('chat.updateDialogTitle') }}
        </el-button>
      </div>

      <!-- 字体大小控制 -->
      <div class="font-size-controls" :data-value="fontSize">
        <span class="font-size-label">{{ t('chat.fontSizeLabel') }}:</span>
        <div class="font-size-selector">
          <div class="font-size-slider-bg"></div>
          <div class="font-size-options">
            <div
              class="font-size-option"
              :class="{ active: fontSize === 'small' }"
              @click="$emit('update-font-size', 'small')"
            >
              {{ t('chat.small') }}
            </div>
            <div
              class="font-size-option"
              :class="{ active: fontSize === 'medium' }"
              @click="$emit('update-font-size', 'medium')"
            >
              {{ t('chat.medium') }}
            </div>
            <div
              class="font-size-option"
              :class="{ active: fontSize === 'large' }"
              @click="$emit('update-font-size', 'large')"
            >
              {{ t('chat.large') }}
            </div>
          </div>
        </div>
      </div>

      <el-tooltip :content="contextWindowHint" placement="top">
        <el-button
          class="context-window-card"
          :class="{ 'context-window-card--hot': isContextWindowHigh }"
          size="small"
          :loading="handoffLoading"
          :disabled="!canTriggerHandoff"
          @click="$emit('handle-handoff')"
        >
          <span class="context-window-card__label">上下文窗口</span>
          <span class="context-window-card__value">{{ formattedContextTokens }}</span>
        </el-button>
      </el-tooltip>

      <div class="action-buttons">
        <el-button type="warning" size="small" @click="$emit('clear-session')">
          <el-icon><CirclePlus /></el-icon>
          {{ t('chat.openAnotherSession') }}
        </el-button>

        <el-button type="primary" size="small" @click="$emit('export-selected')" :disabled="!hasMessages">
          <el-icon><Download /></el-icon>
          {{ selectedCount > 0 ? `${t('chat.exportSelected')} (${selectedCount})` : t('chat.exportScreenshot') }}
        </el-button>

        <el-button type="danger" size="small" @click="$emit('delete-selected')" :disabled="selectedCount === 0">
          <el-icon><Delete /></el-icon>
          {{ selectedCount > 0 ? `${t('chat.batchDelete')} (${selectedCount})` : t('chat.batchDelete') }}
        </el-button>

        <el-tooltip :content="t('chat.exportHint')" placement="top">
          <el-button class="export-hint-btn" circle text size="small" :aria-label="t('chat.exportHint')" :title="t('chat.exportHint')">
            <el-icon><InfoFilled /></el-icon>
          </el-button>
        </el-tooltip>
      </div>
    </div>

    <!-- 移动端：显示抽屉切换按钮 -->
    <div v-else class="toolbar-mobile">
      <div v-if="showBackToTop" class="back-to-top-btn" @click="$emit('scroll-to-top')">
        <el-icon><Top /></el-icon>
      </div>
      <div class="back-to-top-btn input-btn" @click="$emit('toggle-mobile-input')">
        <el-icon>
          <component :is="showMobileInput ? View : ChatDotSquare" />
        </el-icon>
      </div>
      <el-button type="warning" size="default" :aria-label="t('chat.openAnotherSession')" :title="t('chat.openAnotherSession')" @click="$emit('clear-session')" class="back-to-top-btn new-session-btn">
        <el-icon><CirclePlus /></el-icon>
      </el-button>
      <el-button :icon="Menu" size="default" circle :aria-label="t('chat.openToolbar')" :title="t('chat.openToolbar')" @click="showToolbarDrawer = true" class="mobile-toolbar-btn" />
    </div>

    <!-- 移动端抽屉菜单 -->
    <el-drawer v-if="formData.isMobile" v-model="showToolbarDrawer" title="工具栏" direction="rtl" size="80%"
      :destroy-on-close="true" :close-on-click-modal="true">
      <div class="mobile-toolbar-content">
        <div class="dialog-title-editor">
          <span class="mobile-form-label">{{ t('chat.dialogTitle') }}</span>
          <el-input v-model="formData.dialogTitle" :placeholder="t('chat.enterDialogTitle')" size="default" />
          <el-button v-if="formData.currentDialogId" type="success" size="default" @click="$emit('update-dialog-title')"
            class="update-title-btn-mobile" :disabled="!formData.dialogTitle.trim()">
            {{ t('chat.updateDialogTitle') }}
          </el-button>
        </div>

        <div class="font-size-controls" :data-value="fontSize">
          <span class="mobile-form-label">{{ t('chat.fontSizeLabel') }}</span>
          <div class="font-size-selector">
            <div class="font-size-slider-bg"></div>
            <div class="font-size-options">
              <div class="font-size-option" :class="{ active: fontSize === 'small' }" @click="$emit('update-font-size', 'small')">{{ t('chat.small') }}</div>
              <div class="font-size-option" :class="{ active: fontSize === 'medium' }" @click="$emit('update-font-size', 'medium')">{{ t('chat.medium') }}</div>
              <div class="font-size-option" :class="{ active: fontSize === 'large' }" @click="$emit('update-font-size', 'large')">{{ t('chat.large') }}</div>
            </div>
          </div>
        </div>

        <div class="action-buttons">
          <el-button class="context-window-card context-window-card--drawer"
            :class="{ 'context-window-card--hot': isContextWindowHigh }"
            size="default" :loading="handoffLoading" :disabled="!canTriggerHandoff"
            @click="$emit('handle-handoff')">
            <span class="context-window-card__label">上下文窗口</span>
            <span class="context-window-card__value">{{ formattedContextTokens }}</span>
          </el-button>
          <el-button type="primary" size="default" @click="$emit('export-selected')" :disabled="!hasMessages" class="drawer-button">
            <el-icon><Download /></el-icon>
            {{ selectedCount > 0 ? `${t('chat.exportSelected')} (${selectedCount})` : t('chat.exportScreenshot') }}
          </el-button>
          <el-button type="danger" size="default" @click="$emit('delete-selected')" :disabled="selectedCount === 0" class="drawer-button">
            <el-icon><Delete /></el-icon>
            {{ selectedCount > 0 ? `${t('chat.batchDelete')} (${selectedCount})` : t('chat.batchDelete') }}
          </el-button>
        </div>
        <div class="export-hint">{{ t('chat.exportHint') }}</div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  InfoFilled, Menu, Top, View, ChatDotSquare,
  CirclePlus, Download, Delete,
} from '@element-plus/icons-vue'
import type { FormData } from '@/utils/main'

const { t } = useI18n()

defineProps<{
  formData: FormData
  fontSize: string
  formattedContextTokens: string
  isContextWindowHigh: boolean
  handoffLoading: boolean
  canTriggerHandoff: boolean
  contextWindowHint: string
  hasMessages: boolean
  selectedCount: number
  showBackToTop: boolean
  showMobileInput: boolean
}>()

defineEmits<{
  'update-font-size': [size: string]
  'update-dialog-title': []
  'handle-handoff': []
  'clear-session': []
  'export-selected': []
  'delete-selected': []
  'toggle-mobile-input': []
  'scroll-to-top': []
}>()

const showToolbarDrawer = ref(false)
</script>

<style>
@import '@/styles/chat-toolbar.css';
</style>
