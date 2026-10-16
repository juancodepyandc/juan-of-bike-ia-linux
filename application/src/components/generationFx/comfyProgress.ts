type ProgressCb = (frac: number, label?: string, logLine?: string) => void

export function watchComfyProgress(onProgress: ProgressCb): () => void {
  if (typeof window === 'undefined' || typeof WebSocket === 'undefined') return () => {}
  let ws: WebSocket | null = null
  let closed = false
  let lastLoggedStep = -1
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
          const step = msg.data.value
          const max = msg.data.max
          const rawRatio = Math.min(1, step / max)
          // Map diffusion progress into overall pipeline [0.36 .. 0.86] (Phase 3/5 Diffusion FLUX)
          const overallFrac = 0.36 + rawRatio * 0.50
          const stepPct = Math.round(rawRatio * 100)
          const label = `Étape 3/5 · Diffusion FLUX — pas ${step}/${max} (${stepPct}%)`
          const shouldLog = step === 1 || step === max || step - lastLoggedStep >= 4
          if (shouldLog) lastLoggedStep = step
          onProgress(
            overallFrac,
            label,
            shouldLog ? `Diffusion neuronale FLUX : pas ${step}/${max} (${stepPct}%)` : undefined,
          )
        } else if (msg.type === 'executed' && msg.data?.node) {
          onProgress(0.92, 'Étape 5/5 · Finalisation — Décodage VAE & vérification qualité', 'Décodage VAE haute fidélité terminé')
        }
      } catch { /* frame non-JSON (binaire preview) */ }
    }
    ws.onerror = () => { /* fallback silencieux sur la progression pilotée */ }
  } catch { /* ignore */ }
  return () => {
    closed = true
    try { ws?.close() } catch { /* ignore */ }
  }
}

