import { nextTick, onBeforeUnmount, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useAdminAction } from '@/composables/useAdminAction'
import { downloadBlob } from '@/utils/media'

export type StudioTrack = {
  id: string
  title: string
  duration_seconds: number | null
  audio_url: string | null
  url_expired: boolean
}

export type StudioPageOptions = {
  /** 操作失败时的兜底文案。 */
  errorText: string
  /** 重新拉取页面数据的回调，操作后用于刷新。 */
  load: () => Promise<void>
  /** 拉取本地音频或正文，用于播放与下载。 */
  fetchAudio: (id: string, ext: 'mp3' | 'txt') => Promise<Blob>
  /** 播放器元素，由组件用模板 ref 绑定后传入。 */
  getPlayer: () => HTMLAudioElement | undefined
}

/** 音色与音乐两个面板共用的忙碌态、错误提示和播放器逻辑。 */
export function useStudioPage(options: StudioPageOptions) {
  const { runAction } = useAdminAction(text => text)
  const busy = ref('')
  const failure = ref('')
  const playing = ref<StudioTrack | null>(null)
  const playerUrl = ref('')

  async function action<T>(name: string, task: () => Promise<T>, refresh = false, successText?: string): Promise<T | undefined> {
    if (busy.value) return
    busy.value = name
    failure.value = ''
    try {
      return await runAction(task, { errorFallbackText: options.errorText, successText })
    } catch (error: any) {
      failure.value = error?.response?.data?.msg || error?.message || options.errorText
    } finally {
      if (refresh) {
        try { await options.load() } catch { /* 保留操作错误和已加载的页面，不自动重放云端操作。 */ }
      }
      busy.value = ''
    }
  }

  async function prepareAudio(row: StudioTrack, autoplay = false) {
    const blob = await options.fetchAudio(row.id, 'mp3')
    if (playerUrl.value) URL.revokeObjectURL(playerUrl.value)
    playerUrl.value = URL.createObjectURL(blob)
    playing.value = row
    await nextTick()
    if (autoplay) {
      // 音频无法解码时 play() 可能既不 resolve 也不 reject，不能让页面卡在处理中。
      const playback = options.getPlayer()?.play()
      if (playback) playback.catch(() => ElMessage.info('音频已载入，请点击播放'))
    }
  }

  async function download(row: StudioTrack, ext: 'mp3' | 'txt') {
    await action('download', async () => downloadBlob(await options.fetchAudio(row.id, ext), `${row.title}.${ext}`))
  }

  async function copyLink(row: StudioTrack) {
    if (!row.audio_url) return
    await action('copy', () => navigator.clipboard.writeText(row.audio_url!), false,
      row.url_expired ? '链接已复制；该临时链接已过期' : '音频链接已复制')
  }

  function clearPlayer() {
    if (playerUrl.value) URL.revokeObjectURL(playerUrl.value)
    playerUrl.value = ''
    playing.value = null
  }

  function date(value: string | null) {
    return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '尚未同步'
  }

  onBeforeUnmount(clearPlayer)

  return { busy, failure, playing, playerUrl, action, prepareAudio, download, copyLink, clearPlayer, date }
}
