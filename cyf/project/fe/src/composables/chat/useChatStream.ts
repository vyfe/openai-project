// 聊天请求链路：发送 / 流式接收 / 取消 / 重试 / 续写 / 上下文拼装。
// 从 ChatContent.vue 拆出，所有外部状态通过 options 注入，便于单测。
import { nextTick, type Ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { chatAPI } from '@/services/api'
import { normalizeFileUrl } from '@/services/backendUrl'
import type { FormData } from '@/utils/main'
import {
  extractFileUrls,
  getCurrentDateTime,
  getCurrentTime,
  isImageUrl,
  sanitizeDialogTitle,
} from './messageUtils'
import type { TranslateFn } from './useChatMessageActions'
import type { ChatMessage, ChatStreamOptions, DialogMessage, RoleSetting } from './types'

interface UseChatStreamOptions {
  messages: ChatMessage[]
  formData: FormData
  isLoading: Ref<boolean>
  inputMessage: Ref<string>
  getSessionKey: () => string
  sessionAbortControllers: Ref<Record<string, AbortController | null>>
  sessionRequestIds: Ref<Record<string, string | null>>
  sessionAiIndexes: Ref<Record<string, number | null>>
  sessionWaitingTimers: Ref<Record<string, number | null>>
  sessionWaitingShown: Ref<Record<string, boolean>>
  sessionLoadingStore: Ref<Record<string, boolean>>
  setSessionLoading: (sessionKey: string, loading: boolean) => void
  mutateSessionMessages: (sessionKey: string, mutator: (target: ChatMessage[]) => void) => void
  buildRoleSetting: () => RoleSetting
  setContextUsage: (usage?: { total_tokens?: number }) => void
  scrollToBottom: () => void
  scrollToBottomOnNewMessage: () => void
  onDialogCreated: (sessionKey: string, dialogId: number) => void
  onRefreshHistory: () => void
  t: TranslateFn
  welcomeMessage: string
}

export function useChatStream(options: UseChatStreamOptions) {
  const {
    messages,
    formData,
    isLoading,
    inputMessage,
    getSessionKey,
    sessionAbortControllers,
    sessionRequestIds,
    sessionAiIndexes,
    sessionWaitingTimers,
    sessionWaitingShown,
    sessionLoadingStore,
    setSessionLoading,
    mutateSessionMessages,
    buildRoleSetting,
    setContextUsage,
    scrollToBottom,
    scrollToBottomOnNewMessage,
    onDialogCreated,
    onRefreshHistory,
    t,
    welcomeMessage,
  } = options

  const generateRequestId = () => {
    if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
      return crypto.randomUUID()
    }
    return `req_${Date.now()}_${Math.random().toString(16).slice(2)}`
  }

  const clearWaitingChoiceTimer = () => {
    const sessionKey = getSessionKey()
    const timerId = sessionWaitingTimers.value[sessionKey]
    if (timerId) {
      clearTimeout(timerId)
      sessionWaitingTimers.value[sessionKey] = null
    }
  }

  const startWaitingChoiceTimer = () => {
    const sessionKey = getSessionKey()
    clearWaitingChoiceTimer()
    sessionWaitingShown.value[sessionKey] = false
    sessionWaitingTimers.value[sessionKey] = window.setTimeout(async () => {
      if (!sessionLoadingStore.value[sessionKey] || sessionWaitingShown.value[sessionKey]) return
      sessionWaitingShown.value[sessionKey] = true
      try {
        await ElMessageBox.confirm(
          t('chat.streamWaitTimeoutMessage'),
          t('chat.streamWaitTimeoutTitle'),
          {
            confirmButtonText: t('chat.continueWait'),
            cancelButtonText: t('chat.stopStream'),
            type: 'warning',
            closeOnClickModal: false,
          },
        )
      } catch {
        await handleStopStream('timeout')
      }
    }, 30000)
  }

  const handleStopStream = async (reason: 'user' | 'timeout' = 'user') => {
    const sessionKey = getSessionKey()
    const activeController = sessionAbortControllers.value[sessionKey]
    if (!activeController) return
    const requestId = sessionRequestIds.value[sessionKey]
    activeController.abort()
    sessionAbortControllers.value[sessionKey] = null
    sessionRequestIds.value[sessionKey] = null
    clearWaitingChoiceTimer()

    try {
      if (requestId) {
        await chatAPI.cancelChatStream(requestId)
      }
    } catch (error) {
      console.error('终止流式请求失败:', error)
    }

    const activeAiIdx = sessionAiIndexes.value[sessionKey]
    if (activeAiIdx !== null && activeAiIdx !== undefined && messages[activeAiIdx]) {
      const message = messages[activeAiIdx]
      message.isError = true
      if (!message.content) {
        message.content = t('chat.streamStopped')
      }
    }

    isLoading.value = false

    if (reason === 'user') {
      ElMessage.info(t('chat.streamStopped'))
    }
  }

  /** 过滤错误、空回复、截断消息，保留正常对话用于下一次请求。 */
  const filterAbnormalMessages = (
    list: ChatMessage[],
    filterOptions: { excludeIndex?: number; includeCurrent?: boolean } = {},
  ) => {
    return list.filter((msg, msgIndex) => {
      if (msg.type === 'ai' && msg.content === welcomeMessage) {
        return true
      }
      if (filterOptions.excludeIndex !== undefined && msgIndex === filterOptions.excludeIndex) {
        return filterOptions.includeCurrent || false
      }
      if (msg.isError) return false
      if (msg.type === 'ai' && msg.content === '') return false
      if (msg.isTruncated) return false
      return true
    })
  }

  /** 从消息快照构建后端对话数组。 */
  const buildDialogArrayFromSnapshot = (
    snapshot: ChatMessage[],
    currentMessage: string,
    currentTime?: string,
  ): DialogMessage[] => {
    const dialogArray: DialogMessage[] = []

    // system 消息由后端根据 system_prompt_id 获取；未启用增强角色时才用本地提示词
    if (!formData.enhancedRoleEnabled && formData.systemPrompt && formData.systemPrompt.trim()) {
      dialogArray.push({ role: 'system', content: formData.systemPrompt.trim() })
    }

    if (formData.contextCount === 0) {
      dialogArray.push({ role: 'user', content: currentMessage, time: currentTime || getCurrentDateTime() })
      return dialogArray
    }

    const validMessages = snapshot.filter(
      (msg) =>
        (msg.type === 'user' || msg.type === 'ai') &&
        msg.content !== welcomeMessage,
    )
    const messagesToInclude = validMessages.slice(-formData.contextCount)

    for (const msg of messagesToInclude) {
      const dialogMsg: DialogMessage = {
        role: msg.type === 'user' ? 'user' : 'assistant',
        content: msg.content,
        url: msg.url || '',
        time: msg.time,
      }
      if (msg.parts && msg.parts.length > 0) {
        dialogMsg.parts = msg.parts
      }
      dialogArray.push(dialogMsg)
    }

    dialogArray.push({ role: 'user', content: currentMessage, time: currentTime || getCurrentDateTime() })
    return dialogArray
  }

  /** 当前消息是否是正在流式接收的那条 AI 消息。 */
  const isStreaming = (index: number) => {
    const message = messages[index]
    if (!message || message.type !== 'ai') return false
    const lastAiMessageIndex = messages.reduce((lastIndex, msg, idx) => {
      return msg.type === 'ai' ? idx : lastIndex
    }, -1)
    return index === lastAiMessageIndex && isLoading.value
  }

  // 通用 API 调用：图片模型、流式、非流式共用
  const callApi = async (
    userMessage: ChatMessage,
    contextSnapshot: ChatMessage[],
    requestOptions: ChatStreamOptions = {},
  ) => {
    const { isRetry = false, originalIndex, isContinue = false, imageSize = '1024x1024' } = requestOptions
    let wasUserAborted = false
    const requestSessionKey = getSessionKey()
    const roleSetting = buildRoleSetting()

    setSessionLoading(requestSessionKey, true)

    try {
      const isImageModel = formData.selectedModelType === 2

      if (isImageModel) {
        const aiResponse: any = await chatAPI.sendImageGeneration(
          formData.selectedModel,
          userMessage.content,
          'single',
          buildDialogArrayFromSnapshot(contextSnapshot, userMessage.content, userMessage.time),
          formData.dialogTitle,
          imageSize,
          formData.currentDialogId || 0,
          formData.enhancedRoleEnabled ? formData.systemPromptId : undefined,
          roleSetting,
        )

        let responseContent = ''

        if (typeof aiResponse === 'object') {
          if (aiResponse.url) {
            responseContent = aiResponse.url
          } else if (aiResponse.content && aiResponse.content.context) {
            const context = aiResponse.content.context
            if (Array.isArray(context) && context.length > 0) {
              const assistantMsg = context.find((msg: any) => msg.role === 'assistant')
              if (assistantMsg && assistantMsg.url) {
                responseContent = assistantMsg.url
              }
            }
          }

          if (aiResponse.dialog_id && !formData.currentDialogId) {
            onDialogCreated(requestSessionKey, Number(aiResponse.dialog_id))
            formData.currentDialogId = aiResponse.dialog_id
            if (!formData.dialogTitle.trim()) {
              formData.dialogTitle = `对话 ${aiResponse.dialog_id}`
            }
          }

          if (responseContent) {
            const finalUrl = responseContent
            if (isImageUrl(finalUrl)) {
              responseContent = `[FILE_URL:${finalUrl}]`
            } else {
              responseContent = `文件链接: ${finalUrl}`
            }
          } else {
            responseContent = JSON.stringify(aiResponse)
          }
        } else {
          responseContent = String(aiResponse)
        }

        const imageMsgBase: ChatMessage = {
          type: 'ai',
          content: responseContent,
          time: aiResponse?.time || getCurrentTime(),
        }
        if (aiResponse?.parts) {
          imageMsgBase.parts = aiResponse.parts
        }
        if (isRetry && originalIndex !== undefined) {
          messages.splice(originalIndex, 1, imageMsgBase)
        } else {
          let finalUrl = ''
          if (responseContent.startsWith('[FILE_URL:') && responseContent.endsWith(']')) {
            finalUrl = responseContent.substring(10, responseContent.length - 1)
          }
          imageMsgBase.url = finalUrl
          messages.push(imageMsgBase)
        }
      } else if (formData.streamEnabled) {
        let aiMessageIndex: number

        if (isRetry && originalIndex !== undefined) {
          messages[originalIndex] = {
            type: 'ai',
            content: '',
            time: getCurrentTime(),
          }
          aiMessageIndex = originalIndex
        } else {
          aiMessageIndex = messages.length
          messages.push({
            type: 'ai',
            content: '',
            time: getCurrentTime(),
          })
        }

        const requestId = generateRequestId()
        const abortController = new AbortController()
        sessionAbortControllers.value[requestSessionKey] = abortController
        sessionRequestIds.value[requestSessionKey] = requestId
        sessionAiIndexes.value[requestSessionKey] = aiMessageIndex
        startWaitingChoiceTimer()

        // 用发送前的快照构建上下文，避免异步过程中 messages 继续变化
        const dialogArray = buildDialogArrayFromSnapshot(
          contextSnapshot,
          userMessage.content,
          userMessage.time,
        )

        await chatAPI.sendChatStream(
          formData.selectedModel,
          userMessage.content,
          (content, done, finishReason, response) => {
            if (response?.part) {
              mutateSessionMessages(requestSessionKey, (targetMessages) => {
                if (!targetMessages[aiMessageIndex]) return
                if (!targetMessages[aiMessageIndex].parts) {
                  targetMessages[aiMessageIndex].parts = []
                }
                targetMessages[aiMessageIndex].parts!.push(response.part)
              })
              return
            }
            // 工具调用状态仅用于协议层通知，具体搜索结果通过 part 事件展示
            if (response?.type === 'tool_status') {
              return
            }

            mutateSessionMessages(requestSessionKey, (targetMessages) => {
              if (!targetMessages[aiMessageIndex]) {
                targetMessages[aiMessageIndex] = {
                  type: 'ai',
                  content: '',
                  time: getCurrentTime(),
                }
              }
              targetMessages[aiMessageIndex].content = `${targetMessages[aiMessageIndex].content || ''}${content || ''}`
            })
            if (done) {
              if (response?.usage) {
                setContextUsage(response.usage)
              }
              setSessionLoading(requestSessionKey, false)
              clearWaitingChoiceTimer()
              sessionAbortControllers.value[requestSessionKey] = null
              sessionRequestIds.value[requestSessionKey] = null
              sessionAiIndexes.value[requestSessionKey] = null
              mutateSessionMessages(requestSessionKey, (targetMessages) => {
                if (!targetMessages[aiMessageIndex]) return
                if (finishReason === 'length') {
                  targetMessages[aiMessageIndex].finishReason = 'length'
                  targetMessages[aiMessageIndex].isTruncated = true
                } else if (targetMessages[aiMessageIndex].content === '') {
                  targetMessages[aiMessageIndex].isError = true
                }
                if (response?.time) {
                  targetMessages[aiMessageIndex].time = response.time
                }
                if (response?.parts) {
                  targetMessages[aiMessageIndex].parts = response.parts
                }
              })

              if (response && response.dialog_id) {
                onDialogCreated(requestSessionKey, Number(response.dialog_id))
                if (requestSessionKey === getSessionKey() && !formData.currentDialogId) {
                  formData.currentDialogId = response.dialog_id
                  if (!formData.dialogTitle.trim()) {
                    formData.dialogTitle = `对话 ${response.dialog_id}`
                  }
                }
              }
            }
            if (requestSessionKey === getSessionKey() && formData.isScrolledToBottom) {
              nextTick(() => {
                scrollToBottom()
              })
            }
          },
          formData.contextCount > 0 ? 'multi' : 'single',
          dialogArray,
          formData.dialogTitle,
          Math.round(formData.maxResponseChars * 1.2 + 30),
          formData.enhancedRoleEnabled ? formData.systemPromptId : undefined,
          roleSetting,
          requestId,
          abortController.signal,
          formData.enabledTools,
        )
      } else {
        let aiMessageIndex: number

        if (isRetry && originalIndex !== undefined) {
          messages[originalIndex] = {
            type: 'ai',
            content: '',
            time: getCurrentTime(),
          }
          aiMessageIndex = originalIndex
        } else {
          aiMessageIndex = messages.length
          messages.push({
            type: 'ai',
            content: '',
            time: getCurrentTime(),
          })
        }

        const dialogArray = buildDialogArrayFromSnapshot(
          contextSnapshot,
          userMessage.content,
          userMessage.time,
        )

        const response: any = await chatAPI.sendChat(
          formData.selectedModel,
          userMessage.content,
          formData.contextCount > 0 ? 'multi' : 'single',
          dialogArray,
          formData.dialogTitle,
          Math.round(formData.maxResponseChars * 1.2 + 30),
          formData.enhancedRoleEnabled ? formData.systemPromptId : undefined,
          roleSetting,
          formData.enabledTools,
        )

        if (response.usage) {
          setContextUsage(response.usage)
        }
        mutateSessionMessages(requestSessionKey, (targetMessages) => {
          if (!targetMessages[aiMessageIndex]) return
          targetMessages[aiMessageIndex].content = response.content
          if (response.time) {
            targetMessages[aiMessageIndex].time = response.time
          }
          if (response.parts) {
            targetMessages[aiMessageIndex].parts = response.parts
          }
          if (response.finish_reason === 'length') {
            targetMessages[aiMessageIndex].finishReason = 'length'
            targetMessages[aiMessageIndex].isTruncated = true
          }
        })

        if (response.dialog_id) {
          onDialogCreated(requestSessionKey, Number(response.dialog_id))
          if (requestSessionKey === getSessionKey() && !formData.currentDialogId) {
            formData.currentDialogId = response.dialog_id
            if (!formData.dialogTitle.trim()) {
              formData.dialogTitle = `对话 ${response.dialog_id}`
            }
          }
        }

        setSessionLoading(requestSessionKey, false)
        if (requestSessionKey === getSessionKey()) {
          nextTick(() => {
            scrollToBottom()
          })
        }
      }
    } catch (error: any) {
      console.error(isRetry ? '重试API Error:' : 'API Error:', error)

      if (error?.name === 'AbortError') {
        wasUserAborted = true
        return
      }

      let errorMessage = isRetry ? '重试失败，请稍后再次重试' : '获取AI回复失败，请重试'
      if (error.response) {
        errorMessage = isRetry
          ? `重试失败: ${error.response.data?.msg || error.response.statusText}`
          : `错误: ${error.response.data?.msg || error.response.statusText}`
      } else if (error.request) {
        errorMessage = '网络请求失败，请检查后端服务是否正常运行'
      } else if (error.message) {
        errorMessage = isRetry ? `重试失败: ${error.message}` : error.message
      }

      if (isRetry && originalIndex !== undefined) {
        messages.splice(originalIndex, 0, {
          type: 'ai',
          content: errorMessage,
          time: getCurrentTime(),
          isError: true,
        })
      } else {
        messages.push({
          type: 'ai',
          content: errorMessage,
          time: getCurrentTime(),
          isError: true,
        })
      }
    } finally {
      setSessionLoading(requestSessionKey, false)
      clearWaitingChoiceTimer()
      sessionAbortControllers.value[requestSessionKey] = null
      sessionRequestIds.value[requestSessionKey] = null
      sessionAiIndexes.value[requestSessionKey] = null
      await nextTick()
      scrollToBottomOnNewMessage()

      if (!isRetry && !isContinue && !wasUserAborted) {
        onRefreshHistory()
      }
    }
  }

  // InputArea 的发送事件
  const handleSendMessage = async (message: string, file?: File, imageSize?: string) => {
    if (!message.trim()) return
    if (!formData.selectedModel) {
      ElMessage.warning('请先选择一个模型')
      return
    }
    const isImageModel = formData.selectedModelType === 2

    let processedMessage = message
    let finalImageSize = imageSize || '1024x1024'

    // 把上一条 AI 消息里的附件 URL 带进本次请求
    let lastAiMessageIndex = -1
    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i]
      if (msg.type === 'ai' && msg.content && msg.content !== welcomeMessage) {
        lastAiMessageIndex = i
        break
      }
    }

    if (lastAiMessageIndex !== -1) {
      const lastAiMessage = messages[lastAiMessageIndex]
      if (lastAiMessage.url) {
        processedMessage = processedMessage + '\n[FILE_URL:' + lastAiMessage.url + ']'
      } else {
        const fileUrls = extractFileUrls(lastAiMessage.content)
        if (fileUrls.length > 0) {
          const fileUrlMatches = lastAiMessage.content.match(/\[FILE_URL:[^\]]+\]/g)
          if (fileUrlMatches) {
            processedMessage = processedMessage + '\n' + fileUrlMatches.join('\n')
          }
        }
      }
    }

    if (isImageModel) {
      const imageSizeMatch = message.match(/\[IMAGE_SIZE:(.+?)\]/)
      if (imageSizeMatch) {
        finalImageSize = imageSizeMatch[1]
        processedMessage = processedMessage.replace(/\[IMAGE_SIZE:(.+?)\]/, '').trim()
      }
    }

    // 清掉重试 / 继续生成这类异常消息
    const normalMessages = filterAbnormalMessages(messages)
    if (normalMessages.length !== messages.length) {
      messages.splice(0, messages.length, ...normalMessages)
    }

    const userMessage: ChatMessage = {
      type: 'user',
      content: processedMessage,
      time: getCurrentDateTime(),
      file: file || undefined,
    }

    const contextSnapshot = [...messages]
    messages.push(userMessage)

    if (!formData.dialogTitle.trim()) {
      const cleanTitle = sanitizeDialogTitle(processedMessage)
      formData.dialogTitle = cleanTitle.length > 50 ? cleanTitle.substring(0, 50) + '...' : cleanTitle
    }

    await nextTick()
    scrollToBottomOnNewMessage()

    if (isImageModel) {
      try {
        isLoading.value = true
        const roleSetting = buildRoleSetting()
        const aiResponse: any = await chatAPI.sendImageGeneration(
          formData.selectedModel,
          processedMessage,
          formData.contextCount > 0 ? 'multi' : 'single',
          buildDialogArrayFromSnapshot(contextSnapshot, processedMessage, userMessage.time),
          formData.dialogTitle,
          finalImageSize,
          formData.currentDialogId || 0,
          formData.enhancedRoleEnabled ? formData.systemPromptId : undefined,
          roleSetting,
        )

        let responseContent = ''
        let imageUrl = ''

        if (typeof aiResponse === 'object') {
          if (aiResponse.url) {
            imageUrl = normalizeFileUrl(aiResponse.url)
            responseContent = aiResponse.desc || '图片已生成'

            if (aiResponse.dialog_id && !formData.currentDialogId) {
              onDialogCreated(getSessionKey(), Number(aiResponse.dialog_id))
              formData.currentDialogId = aiResponse.dialog_id
              if (!formData.dialogTitle.trim()) {
                formData.dialogTitle = `对话 ${aiResponse.dialog_id}`
              }
            }
          } else {
            responseContent = JSON.stringify(aiResponse)
          }
        } else {
          responseContent = String(aiResponse)
        }

        const imgMsg: ChatMessage = {
          type: 'ai',
          content: responseContent,
          url: imageUrl,
          time: aiResponse?.time || getCurrentTime(),
        }
        if (aiResponse?.parts) {
          imgMsg.parts = aiResponse.parts
        }
        messages.push(imgMsg)
      } catch (error: any) {
        console.error('图片生成API Error:', error)
        let errorMessage = '图片生成失败，请重试'
        if (error.response) {
          errorMessage = `错误: ${error.response.data?.msg || error.response.statusText}`
        } else if (error.request) {
          errorMessage = '网络请求失败，请检查后端服务是否正常运行'
        } else if (error.message) {
          errorMessage = error.message
        }

        messages.push({
          type: 'ai',
          content: errorMessage,
          time: getCurrentTime(),
          isError: true,
        })
      } finally {
        isLoading.value = false
        await nextTick()
        scrollToBottomOnNewMessage()
        onRefreshHistory()
      }
    } else {
      await callApi(userMessage, contextSnapshot, { imageSize: finalImageSize })
    }
  }

  /** 重试某条 AI 消息（重发它上一条用户消息）。 */
  const retryMessage = async (index: number) => {
    if (index < 0 || index >= messages.length || messages[index].type !== 'ai') {
      return
    }

    const currentMessageToRetry = messages[index]
    const normalMessages = filterAbnormalMessages(messages, { excludeIndex: index, includeCurrent: true })
    if (normalMessages.length !== messages.length) {
      messages.splice(0, messages.length, ...normalMessages)
    }

    const newIndexOfRetryMessage = messages.indexOf(currentMessageToRetry)
    if (newIndexOfRetryMessage === -1) {
      ElMessage.error('重试的消息不存在')
      return
    }

    let userMessageIndex = -1
    for (let i = newIndexOfRetryMessage - 1; i >= 0; i--) {
      if (messages[i].type === 'user') {
        userMessageIndex = i
        break
      }
    }

    if (userMessageIndex === -1) {
      ElMessage.error('找不到对应的问题消息，无法重试')
      return
    }

    const userMessage = messages[userMessageIndex]
    messages.splice(newIndexOfRetryMessage, 1)
    const contextSnapshot = messages.slice(0, newIndexOfRetryMessage)

    await callApi(userMessage, contextSnapshot, {
      isRetry: true,
      originalIndex: newIndexOfRetryMessage,
    })

    ElMessage.success('消息重试成功')
  }

  /** 继续生成被截断的回复。 */
  const continueGeneration = async (index: number) => {
    if (formData.contextCount < 3) {
      ElMessageBox.alert('请将携带历史消息数量设置为3或更高，以支持连续续写功能', '提示', {
        confirmButtonText: '确定',
      })
      return
    }

    if (isLoading.value) return

    const truncatedMessage = messages[index]
    if (!truncatedMessage || !truncatedMessage.isTruncated) return

    const currentMessageToContinue = messages[index]
    const normalMessages = filterAbnormalMessages(messages, { excludeIndex: index, includeCurrent: true })
    if (normalMessages.length !== messages.length) {
      messages.splice(0, messages.length, ...normalMessages)
    }

    const newIndexOfContinueMessage = messages.indexOf(currentMessageToContinue)
    if (newIndexOfContinueMessage === -1) {
      ElMessage.error('继续生成的消息不存在')
      return
    }

    const userMessage: ChatMessage = {
      type: 'user',
      content: '请继续生成未完成的内容，直接从上次中断的地方继续，不要重复已生成的内容。',
      time: getCurrentDateTime(),
    }

    const contextSnapshot = messages.slice(0, newIndexOfContinueMessage + 1)

    await callApi(userMessage, contextSnapshot, { isContinue: true })
  }

  const isLatestAiMessage = (index: number) => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].type === 'ai') {
        return i === index
      }
    }
    return false
  }

  const canRetryLastExchange = () => {
    if (isLoading.value) return false
    if (messages.length < 2) return false
    const lastTwo = messages.slice(-2)
    return lastTwo[0]?.type === 'user' && lastTwo[1]?.type === 'ai'
  }

  const retryLastExchange = async () => {
    if (!canRetryLastExchange()) {
      ElMessage.warning('没有可重试的对话记录')
      return
    }
    const lastUserMessage = messages[messages.length - 2]
    if (lastUserMessage?.type === 'user') {
      inputMessage.value = lastUserMessage.content || ''
    }
    messages.splice(messages.length - 2, 2)
    await nextTick()
    scrollToBottomOnNewMessage()
  }

  return {
    handleSendMessage,
    handleStopStream,
    retryMessage,
    continueGeneration,
    retryLastExchange,
    canRetryLastExchange,
    isStreaming,
    isLatestAiMessage,
    buildDialogArrayFromSnapshot,
  }
}
