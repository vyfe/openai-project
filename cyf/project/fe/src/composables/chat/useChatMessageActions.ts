// 消息级操作：勾选、复制、删除。
// 从 ChatContent.vue 拆出，只依赖消息数组与 i18n。
import { computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { ComposerTranslation } from 'vue-i18n'
import { getCopyText } from './messageUtils'
import type { ChatMessage } from './types'

export type TranslateFn = ComposerTranslation

export function useChatMessageActions(messages: ChatMessage[], t: TranslateFn) {
  const selectedCount = computed(() => messages.filter((msg) => msg.selected).length)

  const toggleMessageSelection = (index: number, selected: boolean) => {
    if (index >= 0 && index < messages.length) {
      messages[index].selected = selected
    }
  }

  /** 复制消息内容到剪贴板，带 execCommand 回退。 */
  const copyMessageContent = async (content: string) => {
    try {
      await navigator.clipboard.writeText(content)
      ElMessage.success('内容已复制到剪贴板')
    } catch (err) {
      console.error('复制失败:', err)
      try {
        const textArea = document.createElement('textarea')
        textArea.value = content
        document.body.appendChild(textArea)
        textArea.select()
        let successful = false
        if (navigator.clipboard && window.isSecureContext) {
          await navigator.clipboard.writeText(content)
          successful = true
        } else {
          successful = document.execCommand('copy')
        }
        document.body.removeChild(textArea)
        if (successful) {
          ElMessage.success('内容已复制到剪贴板')
        } else {
          throw new Error('复制失败')
        }
      } catch (fallbackErr) {
        console.error('复制失败:', fallbackErr)
        ElMessage.error('复制失败，请手动选择内容')
      }
    }
  }

  /** 代码块右上角的复制按钮通过事件委托处理。 */
  const handleMessageContainerClick = async (event: Event) => {
    const target = event.target as HTMLElement | null
    if (!target) return
    const copyBtn = target.closest('.code-copy-btn') as HTMLElement | null
    if (!copyBtn) return
    event.preventDefault()
    const encoded = copyBtn.getAttribute('data-code') || ''
    let rawCode = encoded
    try {
      rawCode = decodeURIComponent(encoded)
    } catch {
      rawCode = encoded
    }
    await copyMessageContent(rawCode)
  }

  /** 删除单条消息；欢迎消息不可删除。 */
  const deleteMessage = (index: number) => {
    if (index < 0 || index >= messages.length) return
    const welcomeMessage = t('chat.aiWelcomeMessage')
    if (messages[index].content === welcomeMessage && messages[index].type === 'ai') {
      ElMessage.warning(t('chat.cannotDeleteWelcomeMessage'))
      return
    }
    messages.splice(index, 1)
    ElMessage.success('消息已删除')
  }

  /** 批量删除勾选消息；欢迎消息自动跳过。 */
  const deleteSelectedMessages = async () => {
    const totalSelected = selectedCount.value
    if (totalSelected === 0) return

    try {
      await ElMessageBox.confirm(
        t('chat.batchDeleteConfirm', { count: totalSelected }),
        t('chat.batchDelete'),
        {
          confirmButtonText: t('chat.confirm'),
          cancelButtonText: t('chat.cancel'),
          type: 'warning',
        },
      )
    } catch {
      return
    }

    const welcomeMessage = t('chat.aiWelcomeMessage')
    const selectedIndexes = messages
      .map((msg, idx) => (msg.selected ? idx : -1))
      .filter((idx) => idx >= 0)
      .sort((a, b) => b - a)

    let deletedCount = 0
    let skippedWelcome = false

    selectedIndexes.forEach((idx) => {
      const msg = messages[idx]
      if (!msg) return
      if (msg.type === 'ai' && msg.content === welcomeMessage) {
        skippedWelcome = true
        msg.selected = false
        return
      }
      messages.splice(idx, 1)
      deletedCount += 1
    })

    messages.forEach((msg) => {
      if (msg.selected) msg.selected = false
    })

    if (deletedCount > 0) {
      ElMessage.success(t('chat.batchDeleteSuccess', { count: deletedCount }))
    }
    if (skippedWelcome) {
      ElMessage.warning(t('chat.cannotDeleteWelcomeMessage'))
    }
  }

  return {
    selectedCount,
    toggleMessageSelection,
    copyMessageContent,
    handleMessageContainerClick,
    deleteMessage,
    deleteSelectedMessages,
    getCopyText,
  }
}
