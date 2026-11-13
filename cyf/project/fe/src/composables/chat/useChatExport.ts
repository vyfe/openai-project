// 对话截图 / 选中消息导出。
// 从 ChatContent.vue 拆出，依赖消息容器、消息列表与主题。
import { ElMessage, ElMessageBox } from 'element-plus'
import type { Ref } from 'vue'
import type { FormData } from '@/utils/main'
import { extractFileUrls, isImageUrl } from './messageUtils'
import type { ChatMessage } from './types'

const enableExportDebug = true

const logExportStep = (step: string, details?: Record<string, unknown>) => {
  if (!enableExportDebug) return
  const payload = details ? ` ${JSON.stringify(details)}` : ''
  console.info(`[export] ${step}${payload}`)
}

const buildPreviewHtml = (imageUrl: string, filename: string) => {
  return `<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>对话截图预览</title>
    <style>
      body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; background: #0f1115; color: #e5e7eb; }
      .bar { position: sticky; top: 0; z-index: 10; display: flex; gap: 12px; align-items: center; padding: 12px 16px; background: rgba(15, 17, 21, 0.9); backdrop-filter: blur(10px); border-bottom: 1px solid rgba(255,255,255,0.08); }
      .title { font-size: 14px; opacity: 0.9; flex: 1; }
      .btn { display: inline-flex; align-items: center; gap: 6px; padding: 8px 14px; border-radius: 8px; background: #aa6624; color: #fff; text-decoration: none; font-size: 14px; }
      .btn.secondary { background: #374151; }
      .container { padding: 16px; display: flex; justify-content: center; }
      img { max-width: 100%; height: auto; box-shadow: 0 12px 40px rgba(0,0,0,0.4); border-radius: 8px; }
    </style>
  </head>
  <body>
    <div class="bar">
      <div class="title">截图已生成，可直接下载或右键保存</div>
      <a class="btn" href="${imageUrl}" download="${filename}">下载图片</a>
      <a class="btn secondary" href="${imageUrl}" target="_blank" rel="noopener">新标签打开</a>
    </div>
    <div class="container">
      <img src="${imageUrl}" alt="截图预览" />
    </div>
  </body>
</html>`
}

const schedulePreviewCleanup = (previewUrl: string, imageUrl: string) => {
  setTimeout(() => {
    URL.revokeObjectURL(previewUrl)
    if (imageUrl.startsWith('blob:')) {
      URL.revokeObjectURL(imageUrl)
    }
  }, 120000)
}

const openPreview = (imageUrl: string, filename: string) => {
  const previewHtml = buildPreviewHtml(imageUrl, filename)
  const previewBlob = new Blob([previewHtml], { type: 'text/html' })
  const previewUrl = URL.createObjectURL(previewBlob)
  const previewWindow = window.open(previewUrl, '_blank')
  if (!previewWindow) {
    ElMessageBox.confirm('浏览器拦截了预览弹窗，请允许此站点弹窗后重试。', '弹窗被拦截', {
      confirmButtonText: '我已允许，重试',
      cancelButtonText: '取消',
      type: 'warning',
      closeOnClickModal: false,
    })
      .then(() => {
        const retryWindow = window.open(previewUrl, '_blank')
        if (!retryWindow) {
          ElMessage.warning('仍然无法打开预览窗口，请检查浏览器弹窗设置')
          return
        }
        retryWindow.opener = null
        schedulePreviewCleanup(previewUrl, imageUrl)
        ElMessage.success('已打开预览，可右键保存')
      })
      .catch(() => {
        URL.revokeObjectURL(previewUrl)
      })
    return false
  }
  previewWindow.opener = null

  schedulePreviewCleanup(previewUrl, imageUrl)
  return true
}

export function useChatExport(
  messages: ChatMessage[],
  messagesContainer: Ref<HTMLElement | undefined>,
  formData: FormData,
) {
  /** 导出对话截屏（长截图）。 */
  const exportConversationScreenshot = async (options: { skipImageCheck?: boolean } = {}) => {
    const exportStart = performance.now()
    logExportStep('start', { t: exportStart })
    const downloadFilename = `conversation_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.jpeg`
    // 先通过 DOM 查询获取容器，确保在任何情况下都能获取到
    let messagesContainerEl = document.querySelector('.messages-container') as HTMLElement | null

    if (!messagesContainerEl && messagesContainer.value) {
      messagesContainerEl = messagesContainer.value
    }

    if (!messagesContainerEl) {
      ElMessage.error('无法找到对话容器')
      return
    }

    // 检查页面中是否存在图片，如果有则弹出警告
    if (!options.skipImageCheck) {
      const images = messagesContainerEl.querySelectorAll('img.attachment-preview')
      if (images.length > 0) {
        ElMessageBox.alert('当前页面包含图片，暂不支持导出含图片的对话截图。请移除图片后再尝试导出。', '提示', {
          confirmButtonText: '确定',
          type: 'warning',
        })
        return
      }
    }

    // 用于存储需要隐藏的元素，以便在截图后恢复
    const hiddenElements: HTMLElement[] = []

    try {
      // 检测是否为移动设备，如果是则应用更快的导出设置
      const isMobileDevice = window.innerWidth < 768

      // 动态导入 html-to-image 库
      const htmlToImageModule = await import('html-to-image')
      const { toJpeg } = htmlToImageModule
      logExportStep('lib_ready', { t: performance.now() })

      // 添加截图模式类，以应用备用字体样式
      document.body.classList.add('screenshot-mode')

      // 保存原始样式
      const originalStyles = {
        overflow: messagesContainerEl.style.overflow,
        maxHeight: messagesContainerEl.style.maxHeight,
        height: messagesContainerEl.style.height,
        position: messagesContainerEl.style.position,
        flex: messagesContainerEl.style.flex,
      }

      const scrollHeight = messagesContainerEl.scrollHeight

      // 设置父容器样式，确保子元素完全展开
      const parent = messagesContainerEl.parentElement
      const parentOriginalStyles: Partial<CSSStyleDeclaration> = {}
      if (parent) {
        parentOriginalStyles.overflow = parent.style.overflow
        parentOriginalStyles.height = parent.style.height
        parentOriginalStyles.maxHeight = parent.style.maxHeight
        parent.style.overflow = 'visible'
        parent.style.height = 'auto'
        parent.style.maxHeight = 'none'
      }

      messagesContainerEl.style.overflow = 'visible'
      messagesContainerEl.style.maxHeight = 'none'
      messagesContainerEl.style.height = `${scrollHeight}px`
      messagesContainerEl.style.flex = 'none'
      messagesContainerEl.style.position = 'relative'

      const waitTime = 100
      await new Promise((resolve) => setTimeout(resolve, waitTime))
      logExportStep('dom_ready', { t: performance.now(), waitTime })

      const pixelRatio = 2
      const quality = 1.5

      const loadingMessage = ElMessage({
        message: isMobileDevice ? '正在导出截图，请稍候...' : '正在导出截图...',
        type: 'info',
        duration: 0,
      })

      const fullHeight = Math.max(messagesContainerEl.scrollHeight, messagesContainerEl.offsetHeight)

      const captureOptions = {
        cacheBust: true,
        pixelRatio,
        skipFonts: false,
        style: {
          overflow: 'visible',
          maxHeight: 'none',
          height: `${fullHeight}px`,
          width: `${messagesContainerEl.offsetWidth}px`,
          filter: 'contrast(110%)',
          fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
        },
        backgroundColor: formData.isDarkTheme ? '#000000' : '#efefef',
        quality,
        filter: (node: Node) => {
          if (!(node instanceof HTMLElement)) return true
          return !node.closest('.back-to-top-btn-normal') && !node.closest('.back-to-top-btn')
        },
      }

      const { toBlob } = htmlToImageModule
      let downloadUrl = ''

      if (toBlob) {
        const blob = await toBlob(messagesContainerEl, captureOptions)
        if (blob) {
          downloadUrl = URL.createObjectURL(blob)
          logExportStep('blob_ready', { t: performance.now(), size: blob.size })
        }
      }

      if (!downloadUrl) {
        const dataUrl = await toJpeg(messagesContainerEl, captureOptions)
        downloadUrl = dataUrl
        logExportStep('dataurl_ready', { t: performance.now(), length: dataUrl.length })
      }

      loadingMessage.close()

      hiddenElements.forEach((el) => {
        el.style.visibility = 'visible'
      })

      if (parent) {
        parent.style.overflow = parentOriginalStyles.overflow || ''
        parent.style.height = parentOriginalStyles.height || ''
        parent.style.maxHeight = parentOriginalStyles.maxHeight || ''
      }

      messagesContainerEl.style.overflow = originalStyles.overflow
      messagesContainerEl.style.maxHeight = originalStyles.maxHeight
      messagesContainerEl.style.height = originalStyles.height
      messagesContainerEl.style.position = originalStyles.position
      messagesContainerEl.style.flex = originalStyles.flex

      document.body.classList.remove('screenshot-mode')

      logExportStep('preview_prompt', { t: performance.now() })
      try {
        await ElMessageBox({
          title: '截图已生成',
          message: '截图已生成，点击“预览”在新标签页打开，可右键另存为。',
          showCancelButton: true,
          confirmButtonText: '预览',
          cancelButtonText: '取消',
          type: 'success',
          closeOnClickModal: false,
          beforeClose: (action, _instance, done) => {
            if (action === 'confirm') {
              logExportStep('preview_confirm', { t: performance.now() })
              const opened = openPreview(downloadUrl, downloadFilename)
              if (opened) {
                logExportStep('preview_opened', { t: performance.now() })
                ElMessage.success('已打开预览，可右键保存')
                logExportStep('toast_shown', {
                  t: performance.now(),
                  cost: Math.round(performance.now() - exportStart),
                })
              }
            } else {
              logExportStep('preview_cancel', { t: performance.now() })
              if (downloadUrl.startsWith('blob:')) {
                URL.revokeObjectURL(downloadUrl)
              }
            }
            done()
          },
        })
      } catch {
        // ignore cancel
      }
    } catch (error) {
      console.error('导出截图失败:', error)
      console.error('错误详情:', JSON.stringify(error, null, 2))

      try {
        document.body.classList.remove('screenshot-mode')
        hiddenElements.forEach((el) => {
          el.style.visibility = 'visible'
        })
      } catch (cleanupError) {
        console.error('清理截图状态时出错:', cleanupError)
      }

      let errorMessage = '导出截图失败，请稍后重试'
      if (error instanceof Error) {
        errorMessage = `导出截图失败: ${error.message}`
      }
      ElMessage.error(errorMessage)
    }
  }

  /** 导出勾选的消息；未勾选时退化为整段截图。 */
  const exportSelectedMessages = async () => {
    const selectedMessages = messages.filter((msg) => msg.selected)

    if (selectedMessages.length === 0) {
      await exportConversationScreenshot()
      return
    }

    const hasImages = selectedMessages.some((msg) => {
      if (msg.url && isImageUrl(msg.url)) return true
      return extractFileUrls(msg.content).some((url) => isImageUrl(url))
    })

    if (hasImages) {
      ElMessageBox.alert(
        '选中的消息中包含图片，暂不支持导出含图片的消息。请取消选择包含图片的消息后再尝试导出。',
        '提示',
        {
          confirmButtonText: '确定',
          type: 'warning',
        },
      )
      return
    }

    const messagesContainerEl = messagesContainer.value
    if (!messagesContainerEl) {
      ElMessage.error('无法找到对话容器')
      return
    }

    const messageElements = messagesContainerEl.querySelectorAll('.message')
    const hiddenElements: { el: HTMLElement; originalDisplay: string }[] = []

    try {
      messageElements.forEach((el, index) => {
        const msg = messages[index]
        if (msg && !msg.selected) {
          const htmlEl = el as HTMLElement
          hiddenElements.push({ el: htmlEl, originalDisplay: htmlEl.style.display || '' })
          htmlEl.style.display = 'none'
        }
      })

      const checkboxes = messagesContainerEl.querySelectorAll('.message-checkbox')
      checkboxes.forEach((cb) => {
        const htmlEl = cb as HTMLElement
        hiddenElements.push({ el: htmlEl, originalDisplay: htmlEl.style.display || '' })
        htmlEl.style.visibility = 'hidden'
      })

      const backToTopBtns = messagesContainerEl.querySelectorAll('.back-to-top-btn-normal')
      backToTopBtns.forEach((btn) => {
        hiddenElements.push({
          el: btn as HTMLElement,
          originalDisplay: (btn as HTMLElement).style.display || '',
        })
        ;(btn as HTMLElement).style.display = 'none'
      })

      await exportConversationScreenshot({ skipImageCheck: true })
    } catch (error) {
      console.error('导出失败:', error)
      ElMessage.error('导出失败，请稍后重试')
    } finally {
      hiddenElements.forEach(({ el, originalDisplay }) => {
        if (el.style.visibility === 'hidden') {
          el.style.visibility = ''
        } else {
          el.style.display = originalDisplay
        }
      })
    }
  }

  return { exportConversationScreenshot, exportSelectedMessages }
}
