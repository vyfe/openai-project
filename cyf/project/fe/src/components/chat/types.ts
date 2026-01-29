// 共享类型定义
export interface Message {
  id?: number
  role: 'user' | 'assistant' | 'system'
  content: string
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