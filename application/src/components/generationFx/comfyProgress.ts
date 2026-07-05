type ProgressCb = (frac: number, label?: string) => void

export function watchComfyProgress(onProgress: ProgressCb): () => void {
  if (typeof window === 'undefined' || typeof WebSocket === 'undefined') return () => {}
  let ws: WebSocket | null = null
  let closed = false
  try {
    const httpBase = (() => {
      try {
        const stored = window.localStorage.getItem('aurora-comfy-url')
        if (stored) return stored
      } catch { /* ignore */ }
      return 'http://127.0.0.1:8188'
    })()
    const wsUrl = httpBase.replace(/^http/, 'ws').replace(/\/$/, '') + '/ws?clientId=aurora-fx-' + Math.random().toString(36).slice(2, 10)
    ws = new WebSocket(wsUrl)
    ws.onmessage = (ev) => {
      if (closed || typeof ev.data !== 'string') return
      try {
        const msg = JSON.parse(ev.data) as { type?: string; data?: { value?: number; max?: number; node?: string | null } }
        if (msg.type === 'progress' && msg.data && typeof msg.data.value === 'number' && typeof msg.data.max === 'number' && msg.data.max > 0) {
          onProgress(Math.min(1, msg.data.value / msg.data.max), `Diffusion · étape ${msg.data.value}/${msg.data.max}`)
        }
      } catch { /* frame non-JSON (binaire preview) */ }
    }
    ws.onerror = () => { /* fallback silencieux sur la progression simulée */ }
  } catch { /* ignore */ }
  return () => {
    closed = true
    try { ws?.close() } catch { /* ignore */ }
  }
}
