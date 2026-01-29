import { ref, reactive } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import hljs from 'highlight.js'
import { Message } from './types'

export function useChat() {
  // 消息相关状态
  const messages = reactive<Message[]>([])
  const inputMessage = ref('')
  const isLoading = ref(false)

  // 对话相关状态
  const dialogTitle = ref('')
  const currentDialogId = ref<number | null>(null)

  // 消息相关的业务逻辑
  const addMessage = (message: Message) => {
    messages.push(message)
  }

  const updateMessage = (index: number, content: string) => {
    if (messages[index]) {
      messages[index].content = content
    }
  }

  const setLoading = (index: number, loading: boolean) => {
    if (messages[index]) {
      messages[index].loading = loading
    }
  }

  const setError = (index: number, error: boolean) => {
    if (messages[index]) {
      messages[index].error = error
    }
  }

  // 对话相关的业务逻辑
  const setDialogTitle = (title: string) => {
    dialogTitle.value = title
  }

  const setCurrentDialogId = (id: number | null) => {
    currentDialogId.value = id
  }

  const clearMessages = () => {
    messages.splice(0, messages.length)
  }

  const clearCurrentSession = () => {
    clearMessages()
    dialogTitle.value = ''
    currentDialogId.value = null
  }

  // 发送消息的逻辑（简化版，具体实现需根据实际API调用调整）
  const sendMessage = async (message: string, model: string, settings: any) => {
    if (!message.trim()) return

    // 添加用户消息
    const userMessage: Message = {
      role: 'user',
      content: message,
      timestamp: new Date()
    }
    addMessage(userMessage)

    // 显示加载状态
    const assistantMessageIndex = messages.length
    const assistantMessage: Message = {
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      loading: true
    }
    addMessage(assistantMessage)

    isLoading.value = true

    try {
      // 这里应该是实际的API调用逻辑
      // 模拟API响应
      setTimeout(() => {
        const response = `模拟的助手回复：${message}`
        updateMessage(assistantMessageIndex, response)
        setLoading(assistantMessageIndex, false)
        isLoading.value = false
      }, 1000)
    } catch (error) {
      setError(assistantMessageIndex, true)
      setLoading(assistantMessageIndex, false)
      isLoading.value = false
      throw error
    }
  }

  // 加载对话内容
  const loadDialogContent = async (id: number) => {
    // 模拟加载对话内容
    console.log(`Loading dialog content for id: ${id}`)
    // 这里应该是实际的API调用来获取对话内容
  }

  // 初始化marked以支持代码高亮和安全HTML处理
  marked.setOptions({
    highlight: function(code, lang) {
      const language = hljs.getLanguage(lang) ? lang : 'plaintext';
      return hljs.highlight(code, { language }).value;
    },
    langPrefix: 'hljs language-',
  });

  // Markdown渲染函数
  const renderMarkdown = (text: string) => {
    if (!text) return ''
    const html = marked(text)
    return DOMPurify.sanitize(html)
  }

  return {
    // 状态
    messages,
    inputMessage,
    isLoading,
    dialogTitle,
    currentDialogId,

    // 方法
    addMessage,
    updateMessage,
    setLoading,
    setError,
    setDialogTitle,
    setCurrentDialogId,
    clearMessages,
    clearCurrentSession,
    sendMessage,
    loadDialogContent,
    renderMarkdown
  }
}