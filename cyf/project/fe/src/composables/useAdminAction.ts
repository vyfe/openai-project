import { ElMessage, ElMessageBox } from 'element-plus'

type MessageResolver = (fallback: string) => string

const resolveMessage = (error: any, fallback: string) => {
  return error?.response?.data?.msg || error?.message || fallback
}

export function useAdminAction(messageResolver: MessageResolver) {
  const runAction = async <T>(
    action: () => Promise<T>,
    options: {
      successText?: string
      errorFallbackText: string
      onSuccess?: (result: T) => void | Promise<void>
    }
  ) => {
    try {
      const result = await action()
      if (options.successText) {
        ElMessage.success(options.successText)
      }
      if (options.onSuccess) {
        await options.onSuccess(result)
      }
      return result
    } catch (error: any) {
      ElMessage.error(resolveMessage(error, messageResolver(options.errorFallbackText)))
      throw error
    }
  }

  const runConfirmedAction = async <T>(
    confirmConfig: {
      message: string
      title: string
      confirmButtonText: string
      cancelButtonText: string
      type?: 'warning' | 'info' | 'success' | 'error'
      distinguishCancelAndClose?: boolean
    },
    action: () => Promise<T>,
    options: {
      successText?: string
      errorFallbackText: string
      ignoreCancel?: boolean
      onSuccess?: (result: T) => void | Promise<void>
      onCancel?: (error: any) => void | Promise<void>
    }
  ) => {
    try {
      await ElMessageBox.confirm(confirmConfig.message, confirmConfig.title, {
        confirmButtonText: confirmConfig.confirmButtonText,
        cancelButtonText: confirmConfig.cancelButtonText,
        type: confirmConfig.type || 'warning',
        distinguishCancelAndClose: confirmConfig.distinguishCancelAndClose
      })
      return await runAction(action, options)
    } catch (error: any) {
      if (error === 'cancel' || error === 'close') {
        if (options.onCancel) {
          await options.onCancel(error)
          return
        }
        if (options.ignoreCancel) {
          return
        }
      }
      if (error !== 'cancel' && error !== 'close') {
        throw error
      }
    }
  }

  return {
    runAction,
    runConfirmedAction
  }
}
