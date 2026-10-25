export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename.replace(/[\\/:*?"<>|]/g, '_')
  link.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export function formatDuration(seconds: number | null) {
  if (seconds === null || !Number.isFinite(seconds)) return '时长未返回'
  const total = Math.round(seconds)
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`
}

export const MAX_AUDIO_FILE_BYTES = 20 * 1024 * 1024

/** 校验音频文件的扩展名与大小。 */
export function checkAudioFile(file: File, extensions: string[], label: string) {
  const allowed = extensions.some(ext => file.name.toLowerCase().endsWith(`.${ext}`))
  if (!allowed || file.size > MAX_AUDIO_FILE_BYTES) {
    throw new Error(`请选择不超过 20 MB 的 ${label}。`)
  }
}

/** 用浏览器解码音频读取时长；无法解码时抛错，避免把无效文件提交到后端。 */
export function readAudioDuration(file: File, timeoutMs = 15000): Promise<number> {
  return new Promise((resolve, reject) => {
    const audio = new Audio()
    const url = URL.createObjectURL(file)
    const cleanup = () => { clearTimeout(timer); audio.removeAttribute('src'); audio.load(); URL.revokeObjectURL(url) }
    const timer = window.setTimeout(() => { cleanup(); reject(new Error('读取音频时长超时，请更换文件。')) }, timeoutMs)
    audio.onloadedmetadata = () => { const value = audio.duration; cleanup(); resolve(value) }
    audio.onerror = () => { cleanup(); reject(new Error('浏览器无法读取该音频的时长，请改用 MP3 或 WAV。')) }
    audio.src = url
  })
}
