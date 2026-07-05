/**
 * v82he : indicateur connexion global, floating top-right.
 * Petit dot coloré visible sur toutes les vues qui poll le bridge
 * toutes les 15s (silent — pas de re-render des modules).
 *
 * - Vert : tous services OK (bridge + ollama + comfy).
 * - Jaune : bridge OK mais 1+ service down.
 * - Rouge : bridge down.
 * - Gris pulsing : initial / poll en cours.
 *
 * Tooltip détaillé au hover (CSS title) : nom + latence par service.
 * Click → scroll vers Settings ou ouvre directement.
 *
 * Bottom-left est déjà occupé par HelpFab (v82gc) → top-right.
 */
import { useEffect, useRef, useState } from 'react'
import { pushTransition } from '../utils/serviceTransitions'
import { useNotificationStore } from '../stores/notificationStore'

type Tick = { ok: boolean; ms: number }
type Statuses = { bridge: Tick | null; ollama: Tick | null; comfy: Tick | null }

// v82hh : préférence audio cue (toggle via menu).
const AUDIO_KEY = 'aurora-conn-audio-v1'
function readAudioPref(): boolean {
  if (typeof window === 'undefined') return false
  try {
    const raw = window.localStorage.getItem(AUDIO_KEY)
    return raw === '1' || raw === 'true'
  } catch { return false }
}
function writeAudioPref(v: boolean): void {
  if (typeof window === 'undefined') return
  try { window.localStorage.setItem(AUDIO_KEY, v ? '1' : '0') } catch { /* swallow */ }
}

// v82hh : tone simple sinusoïde via Web Audio. Frequencies différentes
//   pour up (notif positive 880Hz) vs down (alerte 220Hz).
function playTone(freq: number, durationMs = 180): void {
  if (typeof window === 'undefined') return
  try {
    const Ctx: typeof AudioContext = window.AudioContext
      || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
    if (!Ctx) return
    const ctx = new Ctx()
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.type = 'sine'
    osc.frequency.value = freq
    gain.gain.value = 0.10
    // Fade-out exponentiel pour éviter le clic.
    gain.gain.setValueAtTime(0.10, ctx.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + durationMs / 1000)
    osc.connect(gain).connect(ctx.destination)
    osc.start()
    osc.stop(ctx.currentTime + durationMs / 1000)
    // Cleanup ctx après le tone (évite leak sur Safari).
    window.setTimeout(() => { void ctx.close().catch(() => undefined) }, durationMs + 200)
  } catch { /* ignore */ }
}

// v82li : comfy a un timeout court + retiré du polling routine quand
// 3 échecs consécutifs (backoff). Stop le spam 504 dans la console qui
// noie les vrais events et la perception "rien ne marche".
const ENDPOINTS: Array<{ id: keyof Statuses; path: string; timeoutMs: number }> = [
  { id: 'bridge', path: '/api/agents/list', timeoutMs: 3500 },
  { id: 'ollama', path: '/proxy/ollama/api/tags', timeoutMs: 3500 },
  { id: 'comfy', path: '/proxy/comfy/system_stats', timeoutMs: 1200 },
]

export default function ConnectionIndicator() {
  const [statuses, setStatuses] = useState<Statuses>({
    bridge: null, ollama: null, comfy: null,
  })
  const [polling, setPolling] = useState(false)
  // v82hf : pause polling utilisateur via right-click.
  const [paused, setPaused] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  // v82hh : audio cue toggle persistant.
  const [audioEnabled, setAudioEnabled] = useState<boolean>(() => readAudioPref())
  const probeRef = useRef<(() => Promise<void>) | null>(null)
  const mountedRef = useRef(false)
  // v82hh : ref des statuts précédents pour détecter les transitions.
  const prevAllOkRef = useRef<boolean | null>(null)

  useEffect(() => {
    mountedRef.current = true
    let timer: number | null = null

    // v82li : backoff counter — si comfy fail 3× d'affilée, on skip le
    // polling de comfy pendant 30s pour pas spammer 504.
    let comfyFailStreak = 0
    let comfySkipUntil = 0

    const probe = async () => {
      if (!mountedRef.current) return
      setPolling(true)
      try {
        const { getBridgeUrl } = await import('../utils/runtime')
        const base = getBridgeUrl()
        const now = Date.now()
        const skipComfy = now < comfySkipUntil
        const results = await Promise.all(ENDPOINTS.map(async ({ id, path, timeoutMs }) => {
          if (id === 'comfy' && skipComfy) {
            return { id, ok: false, ms: 0, skipped: true }
          }
          const t0 = performance.now()
          try {
            const res = await fetch(`${base}${path}`, {
              signal: AbortSignal.timeout(timeoutMs),
              cache: 'no-store',
            })
            const ok = res.ok
            if (id === 'comfy') {
              if (ok) comfyFailStreak = 0
              else {
                comfyFailStreak++
                if (comfyFailStreak >= 3) {
                  comfySkipUntil = Date.now() + 30000
                  console.info('[aurora] comfy 504 ×3 — backoff polling 30s')
                }
              }
            }
            return { id, ok, ms: Math.round(performance.now() - t0) }
          } catch {
            if (id === 'comfy') {
              comfyFailStreak++
              if (comfyFailStreak >= 3) {
                comfySkipUntil = Date.now() + 30000
              }
            }
            return { id, ok: false, ms: Math.round(performance.now() - t0) }
          }
        }))
        if (!mountedRef.current) return
        const next: Statuses = { bridge: null, ollama: null, comfy: null }
        for (const r of results) next[r.id] = { ok: r.ok, ms: r.ms }
        // v82hh : détection de transition all-ok pour audio cue + log.
        const newAllOk = next.bridge?.ok === true
          && next.ollama?.ok === true
          && next.comfy?.ok === true
        const prevAllOk = prevAllOkRef.current
        if (prevAllOk !== null && prevAllOk !== newAllOk) {
          const notifPush = useNotificationStore.getState().push
          if (newAllOk) {
            console.info('[aurora] services UP', next)
            if (audioEnabled) playTone(880, 180)
            pushTransition({ service: 'all', kind: 'up' })
            notifPush({
              level: 'success',
              message: 'Services Aurora rétablis',
              detail: 'Bridge, Ollama et ComfyUI répondent à nouveau.',
              duration: 4000,
            })
          } else {
            const downList = (['bridge', 'ollama', 'comfy'] as const)
              .filter((id) => next[id]?.ok === false)
            console.warn(`[aurora] service DOWN: ${downList.join(', ')}`, next)
            if (audioEnabled) playTone(220, 220)
            pushTransition({ service: 'all', kind: 'down', downList: [...downList] })
            notifPush({
              level: 'warning',
              message: `Service indisponible : ${downList.join(', ')}`,
              detail: 'Vérifie le bridge / les serveurs locaux. Les générations peuvent échouer.',
              duration: 7000,
            })
          }
        }
        prevAllOkRef.current = newAllOk
        setStatuses(next)
      } catch { /* ignore */ }
      finally { if (mountedRef.current) setPolling(false) }
    }
    probeRef.current = probe

    probe()
    if (!paused) timer = window.setInterval(probe, 15000)
    return () => {
      mountedRef.current = false
      if (timer !== null) window.clearInterval(timer)
    }
  }, [paused, audioEnabled])

  const bridge = statuses.bridge
  const others = [statuses.ollama, statuses.comfy].filter((s) => s !== null) as Tick[]
  const allOk = bridge?.ok === true && others.every((s) => s.ok)
  const bridgeDown = bridge?.ok === false
  const initial = bridge === null

  const color = initial
    ? 'oklch(0.55 0.02 250)'
    : bridgeDown
    ? 'oklch(0.62 0.20 25)'
    : allOk
    ? 'oklch(0.70 0.15 145)'
    : 'oklch(0.78 0.16 80)'

  // v82j6 : commit hash visible dans le title.
  const buildTag = typeof __AURORA_COMMIT__ !== 'undefined' ? __AURORA_COMMIT__ : 'dev'
  const title = initial
    ? `Vérification services Aurora… · build ${buildTag}`
    : `Bridge: ${bridge?.ok ? `OK ${bridge.ms}ms` : 'DOWN'}\n`
      + `Ollama: ${statuses.ollama?.ok ? `OK ${statuses.ollama.ms}ms` : statuses.ollama ? 'DOWN' : '—'}\n`
      + `ComfyUI: ${statuses.comfy?.ok ? `OK ${statuses.comfy.ms}ms` : statuses.comfy ? 'DOWN' : '—'}\n`
      + `\nbuild ${buildTag} · ${paused ? 'Polling EN PAUSE' : 'Auto-poll 15s'} · Clic = Settings · Clic-droit = menu`

  // v82hf : ferme le menu si l'user click ailleurs.
  useEffect(() => {
    if (!menuOpen) return
    const onDoc = (e: MouseEvent) => {
      const t = e.target as HTMLElement | null
      if (t && t.closest('[data-conn-menu]')) return
      setMenuOpen(false)
    }
    window.addEventListener('mousedown', onDoc)
    return () => window.removeEventListener('mousedown', onDoc)
  }, [menuOpen])

  // v82hj : Cmd+Shift+R / Ctrl+Shift+R = force refresh services
  //   (sans recharger toute la page comme F5).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key.toLowerCase() === 'r') {
        const tag = (e.target as HTMLElement | null)?.tagName
        const inField = tag === 'INPUT' || tag === 'TEXTAREA' || (e.target as HTMLElement | null)?.isContentEditable
        if (inField) return
        e.preventDefault()
        if (probeRef.current) void probeRef.current()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  // v82li : open settings handler ROBUSTE avec triple-fallback + diag.
  // Si le custom event échoue (rare mais possible si listener pas encore
  // monté), on retry après tick. Log explicite côté console pour que
  // l'user voie immédiatement dans DevTools que le click a bien fired.
  const openSettings = (ev?: React.MouseEvent | React.KeyboardEvent) => {
    ev?.preventDefault()
    ev?.stopPropagation()
    console.info('[aurora] settings button clicked — dispatching aurora:open-settings')
    try {
      window.dispatchEvent(new Event('aurora:open-settings'))
    } catch (e) {
      console.error('[aurora] dispatch failed:', e)
    }
    // Retry one tick later in case SettingsPanel just mounted.
    window.setTimeout(() => {
      const panelOpen = document.querySelector('.sp-label')
      if (!panelOpen) {
        console.warn('[aurora] panel not visible after dispatch, retrying...')
        window.dispatchEvent(new Event('aurora:open-settings'))
      } else {
        console.info('[aurora] panel opened OK')
      }
    }, 80)
  }

  // v82lk3 : le rond visible (gros disque jaune top-right) est retiré à la
  // demande user pour ne laisser que l'engrenage du topbar comme seul
  // accès Settings. Le polling continue silencieusement (toasts on
  // service down/up, console logs, raccourci Ctrl+Shift+R pour refresh).
  // Les variables openSettings / color / title / menuOpen / setMenuOpen /
  // probeRef / paused / audioEnabled / setAudioEnabled / setPaused /
  // setStatuses / setPolling restent référencées par les useEffect de
  // polling et keyboard, donc on ne les supprime pas — on rend juste
  // null pour la partie visible.
  void openSettings
  void color
  void title
  void menuOpen
  void setMenuOpen
  void probeRef
  void paused
  void audioEnabled
  void setAudioEnabled
  void setPaused
  void allOk
  void initial
  void polling
  return null
}
