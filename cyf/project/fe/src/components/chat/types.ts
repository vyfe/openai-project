// ===========================================================================
// 多模态消息协议 —— 统一 MessagePart 类型
// ===========================================================================

/** 消息部件的联合类型 */
export type MessagePart =
  | { type: 'text'; text: string }
  | { type: 'image'; url?: string; dataUrl?: string; alt?: string }
  | { type: 'file'; url: string; name?: string; mimeType?: string }
  | { type: 'tool_result'; name?: string; text?: string; data?: unknown }
  | { type: 'error'; message: string }

// 共享类型定义
export interface Message {
  id?: number
  role: 'user' | 'assistant' | 'system'
  content: string
  /** 多模态部件数组，优先于 content 用于渲染 */
  parts?: MessagePart[]
  timestamp: Date
  loading?: boolean
  error?: boolean
  imageUrls?: string[]
}

export interface ChatSettings {
  contextCount: number
  maxResponseChars: number
  streamEnabled: boolean
  systemPrompt: string
  sendPreference: 'enter' | 'ctrl_enter'
}

export interface DialogItem {
  id: number
  title: string
  model: string
  createTime: string
  updateTime: string
}

export interface ModelOption {
  vendor: string
  models: Array<{
    value: string
    label: string
    description: string
  }>
}

export interface ChatSidebarProps {
  collapsed: boolean
  isMobile: boolean
  currentDialogId: number | null
  selectedModel?: string
}

export interface ChatSidebarEmits {
  (e: 'update:collapsed', value: boolean): void
  (e: 'load-dialog', dialogId: number): void
  (e: 'model-change', model: string): void
  (e: 'settings-change', settings: ChatSettings): void
  (e: 'update:currentDialogId', id: number | null): void
}

export interface ChatContentProps {
  selectedModel: string
  contextCount: number
  maxResponseChars: number
  streamEnabled: boolean
  systemPrompt: string
  sendPreference: 'enter' | 'ctrl_enter'
  currentDialogId: number | null
  isMobile: boolean
}

export interface ChatContentEmits {
  (e: 'dialog-created', dialogId: number): void
  (e: 'refresh-history'): void
  (e: 'update:currentDialogId', id: number | null): void
}
// 定义 props
export interface Props {
  modelValue: string
  sendPreference?: 'enter' | 'ctrl_enter'
  isLoading?: boolean
  contextCount?: number
  enhancedRoleEnabled?: boolean
  systemPrompt?: string
  activeEnhancedGroup?: string
  selectedEnhancedRole?: string
  enhancedRoleGroups?: Record<string, any[]>
  selectedModel?: string
  selectedModelType?: number  // 添加模型类型参数
  selectedModelAllowNet?: boolean
  streamEnabled?: boolean
  maxResponseChars?: number
  dialogTitle?: string
  currentDialogId?: number | null
  isScrolledToBottom?: boolean
  isMobile?: boolean
  fontSize?: string
  systemPromptId?: number  // 新增：选中的系统提示词 ID
}

// 定义文件上传响应的类型
export interface FileUploadResponse {
  content?: string;
  msg?: string;
  [key: string]: any; // 允许其他属性
}
