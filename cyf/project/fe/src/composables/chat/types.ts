// 聊天消息的共享类型定义。
// 从 ChatContent.vue 拆出，供 composables 与组件复用。
import type { MessagePart } from '@/components/chat/types'

export type { MessagePart }

export type MessageFinishReason = 'stop' | 'length' | 'content_filter' | 'tool_calls'

export interface ChatMessage {
  type: 'user' | 'ai'
  content: string
  time: string
  /** 多模态部件 */
  parts?: MessagePart[]
  /** 用户消息附带的本地文件（仅未上传完成时存在） */
  file?: File
  /** 附件 / 图片链接 */
  url?: string
  /** 是否为错误占位消息 */
  isError?: boolean
  finishReason?: MessageFinishReason
  /** 是否因长度截断，用于展示“继续生成” */
  isTruncated?: boolean
  /** 是否被勾选，用于批量导出 / 删除 */
  selected?: boolean
}

/** 兼容旧数据的角色设置字段。 */
export interface RoleSetting {
  enhanced_role_enabled?: boolean
  system_prompt_id?: number | string | null
  active_enhanced_group?: string
  selected_enhanced_role?: string
  system_prompt?: string
  active_role_id?: string
}

/** 发送给后端的对话消息。 */
export interface DialogMessage {
  role: string
  content: string
  url?: string
  time?: string
  parts?: MessagePart[]
}

/** 单次请求的上下文快照选项。 */
export interface ChatStreamOptions {
  isRetry?: boolean
  originalIndex?: number
  isContinue?: boolean
  imageSize?: string
}
