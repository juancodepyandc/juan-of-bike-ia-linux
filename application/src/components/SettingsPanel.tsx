/**
 * SettingsPanel — slide-in right drawer, triggered by Ctrl/⌘ + ,
 * Lets the user change models, toggle device, see keyboard shortcuts,
 * clear per-module data, and inspect runtime state without digging into
 * the wizard.
 */
import React, { useEffect, useMemo, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { getBridgeUrl, isTauriRuntime } from '../utils/runtime.ts'
import { useAppStore } from '../stores/appStore.ts'
import { useChatStore } from '../stores/chatStore.ts'
import { useForgeQueueStore } from '../stores/forgeQueueStore.ts'
import { useGamificationStore } from '../stores/gamificationStore.ts'
import { useModuleDraftsStore } from '../stores/moduleDraftsStore.ts'
import { ensurePushPermission, pushPermissionState } from '../utils/notificationBus.ts'
import { detectInstallState } from '../utils/device.ts'
import { ollamaPullModelStream, type PullProgress } from '../hooks/useTauri.ts'
import { useCalendarStore } from '../stores/calendarStore.ts'
import { applyTheme, readTheme, type ThemeId } from '../utils/theme.ts'
import { applyUiSkin, readUiSkin, UI_SKIN_LABELS, USER_PICKABLE_SKINS, type UiSkinId } from '../utils/uiSkin.ts'
import { generationFxEnabled, setGenerationFxEnabled } from './generationFx/fxBus.ts'
import { readHistory, removeHistoryEntry, clearHistory, type PromptHistoryEntry } from '../utils/promptHistory.ts'
import { usePromptLibraryStore } from '../stores/promptLibraryStore.ts'
import { readTransitions, clearTransitions } from '../utils/serviceTransitions.ts'
import { useModuleStreak } from '../hooks/useModuleStreak.ts'
import { useCyberLeaderboardStore } from '../stores/cyberLeaderboardStore.ts'
import { useAcademyLeaderboardStore } from '../stores/academyLeaderboardStore.ts'
import { computeStreak } from '../utils/streak.ts'

const SHORTCUTS = [
  { combo: 'Ctrl / ⌘ + K', action: 'Recherche globale' },
  { combo: 'Ctrl / ⌘ + ,', action: 'Ouvrir les réglages' },
  { combo: 'Ctrl / ⌘ + Entrée', action: 'Envoyer un message (dans le chat)' },
  { combo: '⇧ + Entrée', action: 'Nouvelle ligne dans la saisie' },
  { combo: 'Esc', action: 'Fermer un panneau / overlay' },
  { combo: '2 doigts (mobile)', action: 'Changer de page grimoire' },
]

function FxToggleButton() {
  const [on, setOn] = useState(generationFxEnabled())
  return (
    <button type="button" className={`sp-btn ${on ? 'is-primary' : ''}`}
      style={{ width: '100%', margin: 0 }}
      onClick={() => { const next = !on; setOn(next); setGenerationFxEnabled(next) }}>
      {on ? 'Activées — les mascottes travaillent en scène' : 'Désactivées — indicateurs discrets seulement'}
    </button>
  )
}

export default function SettingsPanel() {
  const [open, setOpen] = useState(false)
  const [expanded, setExpanded] = useState<'models' | 'shortcuts' | 'data' | 'notif' | 'calendar'>('models')
  const events = useCalendarStore((s) => s.events)
  const feedUrl = useCalendarStore((s) => s.feedUrl)
  const setFeedUrl = useCalendarStore((s) => s.setFeedUrl)
  const importIcs = useCalendarStore((s) => s.importIcs)
  const clearAllCal = useCalendarStore((s) => s.clearAll)
  const [icsBusy, setIcsBusy] = useState(false)
  const [icsError, setIcsError] = useState<string | null>(null)
  const [theme, setTheme] = useState<ThemeId>(readTheme)
  const pickTheme = (t: ThemeId) => { setTheme(t); applyTheme(t) }
  const [uiSkin, setUiSkin] = useState<UiSkinId>(readUiSkin)
  const [skinReloading, setSkinReloading] = useState(false)
  // v81q+v81u: auto-reload after skin pick with a brief overlay so the
  // 220ms window doesn't feel like a UI freeze. The overlay paints the
  // newly-picked skin's accent palette so the user sees the visual
  // language of the destination before the page refreshes.
  const pickUiSkin = (s: UiSkinId) => {
    const previous = readUiSkin()
    setUiSkin(s)
    applyUiSkin(s)
    if (s !== previous) {
      setSkinReloading(true);
      // v82jo : fix "skin switch reste blanc". Cause : le service worker
      // de notifications cache les chunks de l'ancien skin, et au reload
      // le navigateur sert les vieux chunks qui ne matchent plus le
      // boot-script data-ui-skin → render mismatch + page blanche.
      // Solution : clear all caches API + unregister SW transients avant
      // reload, puis force navigation vers URL avec cache-buster.
      // Le ; au-dessus est CRITIQUE : sans, JS parse "setSkinReloading(true)(...)".
      (async () => {
        try {
          if ('caches' in window) {
            const keys = await caches.keys()
            await Promise.all(keys.map((k) => caches.delete(k)))
          }
        } catch { /* noop */ }
        // Cache-buster query string force le navigateur à re-fetch index.html
        // (et donc les nouveaux module preloads).
        try {
          const url = new URL(window.location.href)
          url.searchParams.set('skin', s)
          url.searchParams.set('_t', String(Date.now()))
          window.location.href = url.toString()
        } catch {
          window.location.reload()
        }
      })()
    }
  }

  const onIcsFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setIcsBusy(true); setIcsError(null)
    try {
      const text = await file.text()
      const n = importIcs(text, file.name)
      if (n === 0) setIcsError('Aucun événement VEVENT trouvé dans ce fichier')
    } catch (err) {
      setIcsError(err instanceof Error ? err.message : String(err))
    } finally {
      setIcsBusy(false)
      e.target.value = ''
    }
  }
  // v82jc : passe par le bridge Python pour bypass CORS (Pronote /
  //   ÉcoleDirecte / Skolengo bloquent tous les fetch cross-origin).
  //   Fallback direct si bridge indispo.
  const fetchFeed = async () => {
    if (!feedUrl?.trim()) return
    setIcsBusy(true); setIcsError(null)
    try {
      // Try via bridge proxy first (no CORS).
      let text: string | null = null
      try {
        const { getBridgeUrl } = await import('../utils/runtime')
        const proxy = await fetch(`${getBridgeUrl()}/api/calendar/fetch-ics`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url: feedUrl }),
        })
        if (proxy.ok) {
          const data = await proxy.json() as { ok?: boolean; text?: string; error?: string }
          if (data.ok && typeof data.text === 'string') {
            text = data.text
          } else if (data.error) {
            throw new Error(data.error)
          }
        }
      } catch (proxyErr) {
        // bridge indispo OU error explicite → on tente le direct fetch (legacy)
        // mais on garde le message d'erreur si c'était un error explicite (pas
        // network).
        const msg = proxyErr instanceof Error ? proxyErr.message : ''
        if (msg && !msg.toLowerCase().includes('failed to fetch')) {
          throw proxyErr
        }
      }
      // Direct fetch fallback uniquement si proxy n'a rien retourné.
      if (text === null) {
        const r = await fetch(feedUrl, { cache: 'no-store' })
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        text = await r.text()
      }
      const n = importIcs(text, 'feed')
      if (n === 0) setIcsError('Flux ICS vide ou non parsable')
    } catch (err) {
      setIcsError(err instanceof Error ? err.message : String(err))
    } finally { setIcsBusy(false) }
  }
  const [pullName, setPullName] = useState('')
  const [pullProgress, setPullProgress] = useState<PullProgress | null>(null)
  const [pullError, setPullError] = useState<string | null>(null)
  const [pulling, setPulling] = useState(false)

  const startPull = async () => {
    const name = pullName.trim()
    if (!name || pulling) return
    setPulling(true); setPullError(null); setPullProgress({ status: 'connexion…' })
    try {
      await ollamaPullModelStream(name, (p) => setPullProgress(p))
      setPullProgress({ status: 'success' })
      // The model list refreshes via appStore on next interval — but nudge it
      // immediately for instant feedback
      window.dispatchEvent(new Event('storage'))
    } catch (err) {
      setPullError(err instanceof Error ? err.message : String(err))
    } finally {
      setPulling(false)
    }
  }

  const mainModel    = useAppStore((s) => s.mainModel)
  const visionModel  = useAppStore((s) => s.visionModel)
  const installedModels = useAppStore((s) => s.installedModels)
  const setMainModel    = useAppStore((s) => s.setMainModel)
  const setVisionModel  = useAppStore((s) => s.setVisionModel)

  const clearChat  = useChatStore((s) => s.clearMessages)
  const chatLen    = useChatStore((s) => s.messages.length)
  const forgeJobs  = useForgeQueueStore((s) => s.jobs.length)
  const xp         = useGamificationStore((s) => s.xp)
  const level      = useGamificationStore((s) => s.level)
  const drafts     = useModuleDraftsStore((s) => s.drafts)
  const clearDraft = useModuleDraftsStore((s) => s.clearDraft)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === ',') {
        e.preventDefault(); setOpen((v) => !v)
      } else if (open && e.key === 'Escape') {
        setOpen(false)
      }
    }
    const onOpenEvent = () => setOpen(true)
    window.addEventListener('keydown', onKey)
    window.addEventListener('aurora:open-settings', onOpenEvent)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('aurora:open-settings', onOpenEvent)
    }
  }, [open])

  const install = detectInstallState()
  const perm = pushPermissionState()

  if (!open) return null
  // Skin-reload overlay — paints the destination skin's accent so the
  // 360ms reload window feels intentional instead of a freeze.
  const reloadOverlay = skinReloading ? (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 99999,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      flexDirection: 'column', gap: 18,
      background: uiSkin === 'aurora_v1' ? 'oklch(0.10 0.012 250)'
        : uiSkin === 'aurora_v3' ? '#0a0204'
        : '#0c0a09',
      color: uiSkin === 'aurora_v1' ? 'oklch(0.65 0.180 40)'
        : uiSkin === 'aurora_v3' ? '#ff8080'
        : '#ff6a3d',
      fontFamily: uiSkin === 'aurora_v1'
        ? '"Instrument Serif", "Cormorant Garamond", serif'
        : uiSkin === 'aurora_v3'
        ? '"JetBrains Mono", "IBM Plex Mono", monospace'
        : 'system-ui, sans-serif',
      fontStyle: uiSkin === 'aurora_v1' ? 'italic' : 'normal',
      fontSize: 22, letterSpacing: uiSkin === 'aurora_v3' ? '0.3em' : '-0.01em',
      animation: 'sp-skin-fade 360ms ease-out',
    }}>
      <div style={{
        width: 60, height: 60, borderRadius: '50%',
        border: `3px solid currentColor`, borderTopColor: 'transparent',
        animation: 'sp-skin-spin 800ms linear infinite',
      }} />
      <div>
        {uiSkin === 'aurora_v1' && 'Bascule vers Editorial…'}
        {uiSkin === 'aurora_v3' && '◢ SWITCHING TO RICOCHET ◣'}
        {uiSkin === 'manga' && 'Bascule en cours…'}
      </div>
      <style>{`
        @keyframes sp-skin-fade { from { opacity: 0 } to { opacity: 1 } }
        @keyframes sp-skin-spin { to { transform: rotate(360deg) } }
      `}</style>
    </div>
  ) : null

  return createPortal(
    <>
    {reloadOverlay}
    <div className="sp-overlay" onClick={() => setOpen(false)}>
      <aside className="sp-panel" onClick={(e) => e.stopPropagation()}>
        <header className="sp-head">
          <div className="sp-kicker">RÉGLAGES</div>
          <div className="sp-title">juan of bike IA</div>
          <button type="button" className="sp-close" onClick={() => setOpen(false)} aria-label="Fermer">✕</button>
        </header>

        <nav className="sp-tabs">
          {([
            { id: 'models', label: 'Modèles' },
            { id: 'shortcuts', label: 'Raccourcis' },
            { id: 'notif', label: 'Notifications' },
            { id: 'calendar', label: 'Calendrier' },
            { id: 'data', label: 'Données' },
          ] as const).map((t) => (
            <button key={t.id} type="button"
              className={`sp-tab ${expanded === t.id ? 'is-active' : ''}`}
              onClick={() => setExpanded(t.id)}>
              {t.label}
            </button>
          ))}
        </nav>

        <div className="sp-body">
          {expanded === 'models' && (
            <>
              <div className="sp-sec">
                <label className="sp-label">Modèle principal</label>
                <select className="sp-select" value={mainModel} onChange={(e) => setMainModel(e.target.value)}>
                  <option value={mainModel}>{mainModel} (actuel)</option>
                  {installedModels.filter((m) => m !== mainModel).map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
                <div className="sp-hint">Utilisé pour chat, Academy, Forge (phases Ollama), grading, hints.</div>
              </div>
              <div className="sp-sec">
                <label className="sp-label">Modèle vision</label>
                <select className="sp-select" value={visionModel} onChange={(e) => setVisionModel(e.target.value)}>
                  <option value={visionModel}>{visionModel} (actuel)</option>
                  {installedModels.filter((m) => /vl|vision/i.test(m) && m !== visionModel).map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
                <div className="sp-hint">Analyse de la caméra, détection faciale Forge, description d'images en pièce jointe.</div>
              </div>
              <div className="sp-sec">
                <label className="sp-label">Thème</label>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {/* v82bb : 'manga' retiré du picker user-facing — la
                      terminologie héritée n'est plus exposée. Le type
                      ThemeId garde 'manga' pour compat. ascendante (les
                      vues manga internes lisent encore data-theme). Si
                      l'user était sur 'manga' avant cet update, le
                      label affiché sera vide pour cette valeur — il
                      doit re-cliquer sur sobre/dark/light pour fixer. */}
                  {(['sobre','dark','light'] as ThemeId[]).map((t) => (
                    <button key={t} type="button"
                      className={`sp-btn ${theme === t ? 'is-primary' : ''}`}
                      style={{ width: 'auto', margin: 0, padding: '4px 10px', fontSize: 11 }}
                      onClick={() => pickTheme(t)}>
                      {t}
                    </button>
                  ))}
                </div>
              </div>
              <div className="sp-sec">
                <label className="sp-label">UI complète</label>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {USER_PICKABLE_SKINS.map((s) => (
                    <button key={s} type="button"
                      className={`sp-btn ${uiSkin === s ? 'is-primary' : ''}`}
                      style={{ width: '100%', margin: 0, padding: '6px 10px',
                               fontSize: 11, textAlign: 'left',
                               display: 'flex', flexDirection: 'column',
                               alignItems: 'flex-start', gap: 2 }}
                      onClick={() => pickUiSkin(s)}>
                      <span style={{ fontWeight: 600 }}>{UI_SKIN_LABELS[s].title}</span>
                      <span style={{ fontSize: 10, opacity: 0.75 }}>
                        {UI_SKIN_LABELS[s].subtitle}
                      </span>
                    </button>
                  ))}
                </div>
                <div className="sp-hint" style={{ marginTop: 6 }}>
                  Aurora OS (dock orbital · Team Aurora), Editorial (sphère 3D ·
                  shell unifié) ou Ricochet (11 esthétiques par module).{' '}
                  <strong>L'app se recharge automatiquement</strong> après ton
                  choix. Hotkey : <kbd>⌘/Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>U</kbd>.
                </div>
              </div>
              <div className="sp-sec">
                <label className="sp-label">Animations de génération</label>
                <FxToggleButton />
                <div className="sp-hint" style={{ marginTop: 6 }}>
                  Pendant chaque vraie génération (image, code, vidéo, 3D…), une
                  scène animée du module s'affiche avec sa mascotte Team Aurora,
                  les phases réelles du pipeline et la progression. Zéro coût
                  quand rien ne génère.
                </div>
              </div>
              <div className="sp-sec">
                <label className="sp-label">API · Site externe</label>
                <button type="button" className="sp-btn" style={{ width: '100%', margin: 0 }}
                  onClick={() => window.dispatchEvent(new CustomEvent('aurora:open-api-panel'))}>
                  🔌 Embarquer Aurora dans mon site (clé + snippet)
                </button>
                <div className="sp-hint" style={{ marginTop: 6 }}>
                  Génère une clé sécurisée, colle le snippet : un mini-chat Aurora
                  apparaît sur ton site (comme le module Conversation), et tu peux
                  demander des <strong>GLB</strong> (boîtiers, composants…) par API.
                  Tout passe par ton tunnel local.
                </div>
              </div>
              <div className="sp-sec sp-small">
                {installedModels.length} modèles Ollama détectés localement
              </div>

              {/* v82cv : export bulk CSV des runs persistés. Utile
                  pour analyse externe (Excel, Sheets, Pandas) — l'user
                  récupère ses sessions historiques en plain CSV. */}
              <div className="sp-sec">
                <label className="sp-label">Export runs CSV</label>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  <button type="button" className="sp-btn"
                    style={{ width: 'auto', marginTop: 0 }}
                    onClick={() => {
                      try {
                        const raw = window.localStorage.getItem('aurora-academy-leaderboard-v1')
                        if (!raw) { window.alert('Aucun run Academy à exporter.'); return }
                        const parsed = JSON.parse(raw)
                        const runs = (parsed?.state?.runs || []) as Array<{
                          id: string; subject: string; mode: string; topic: string;
                          startedAt: number; endedAt: number; durationMs: number;
                          durationLimitSec: number; score: number; timeoutHit: boolean;
                          flashcardsConfidence?: number;
                        }>
                        if (runs.length === 0) { window.alert('Aucun run Academy à exporter.'); return }
                        const head = ['id', 'started_at', 'ended_at', 'duration_ms', 'duration_limit_sec', 'score', 'timeout_hit', 'subject', 'mode', 'topic', 'flashcards_confidence']
                        const esc = (v: string | number | boolean | undefined) =>
                          v === undefined ? '' : `"${String(v).replace(/"/g, '""')}"`
                        const lines = [head.join(','), ...runs.map((r) => [
                          esc(r.id), esc(new Date(r.startedAt).toISOString()),
                          esc(new Date(r.endedAt).toISOString()),
                          esc(r.durationMs), esc(r.durationLimitSec),
                          esc(r.score), esc(r.timeoutHit),
                          esc(r.subject), esc(r.mode), esc(r.topic),
                          esc(r.flashcardsConfidence ?? ''),
                        ].join(','))]
                        const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' })
                        const url = URL.createObjectURL(blob)
                        const a = document.createElement('a')
                        a.href = url
                        a.download = `aurora-academy-runs_${new Date().toISOString().slice(0, 10)}.csv`
                        document.body.appendChild(a); a.click(); document.body.removeChild(a)
                        URL.revokeObjectURL(url)
                      } catch (e) {
                        window.alert(`Export échoué : ${e instanceof Error ? e.message : String(e)}`)
                      }
                    }}>📊 Academy ({(() => {
                      try { const r = JSON.parse(window.localStorage.getItem('aurora-academy-leaderboard-v1') || '{}'); return r?.state?.runs?.length || 0 } catch { return 0 }
                    })()} runs)</button>
                  <button type="button" className="sp-btn"
                    style={{ width: 'auto', marginTop: 0 }}
                    onClick={() => {
                      try {
                        const raw = window.localStorage.getItem('aurora-cyber-leaderboard-v1')
                        if (!raw) { window.alert('Aucun run Cyber à exporter.'); return }
                        const parsed = JSON.parse(raw)
                        const runs = (parsed?.state?.runs || []) as Array<{
                          kataId: string; stage: number;
                          startedAt: number; endedAt: number; durationMs: number;
                          hintsTaken: number; flagsFound: number;
                          objectivesDone: number; totalObjectives: number; xpEarned: number;
                          mode?: string; score?: number; timeoutHit?: boolean;
                          durationLimitSec?: number;
                        }>
                        if (runs.length === 0) { window.alert('Aucun run Cyber à exporter.'); return }
                        const head = ['kata_id', 'stage', 'started_at', 'ended_at', 'duration_ms', 'hints_taken', 'flags_found', 'objectives_done', 'total_objectives', 'xp_earned', 'mode', 'score', 'timeout_hit', 'duration_limit_sec']
                        const esc = (v: string | number | boolean | undefined) =>
                          v === undefined ? '' : `"${String(v).replace(/"/g, '""')}"`
                        const lines = [head.join(','), ...runs.map((r) => [
                          esc(r.kataId), esc(r.stage),
                          esc(new Date(r.startedAt).toISOString()),
                          esc(new Date(r.endedAt).toISOString()),
                          esc(r.durationMs), esc(r.hintsTaken), esc(r.flagsFound),
                          esc(r.objectivesDone), esc(r.totalObjectives), esc(r.xpEarned),
                          esc(r.mode ?? ''), esc(r.score ?? ''), esc(r.timeoutHit ?? ''),
                          esc(r.durationLimitSec ?? ''),
                        ].join(','))]
                        const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' })
                        const url = URL.createObjectURL(blob)
                        const a = document.createElement('a')
                        a.href = url
                        a.download = `aurora-cyber-runs_${new Date().toISOString().slice(0, 10)}.csv`
                        document.body.appendChild(a); a.click(); document.body.removeChild(a)
                        URL.revokeObjectURL(url)
                      } catch (e) {
                        window.alert(`Export échoué : ${e instanceof Error ? e.message : String(e)}`)
                      }
                    }}>🛡 Cyber ({(() => {
                      try { const r = JSON.parse(window.localStorage.getItem('aurora-cyber-leaderboard-v1') || '{}'); return r?.state?.runs?.length || 0 } catch { return 0 }
                    })()} runs)</button>
                </div>
                <div className="sp-hint" style={{ marginTop: 4 }}>
                  CSV avec headers — ouvrable dans Excel / Sheets / pandas.
                  Timestamp ISO 8601, durations en ms.
                </div>
              </div>

              {/* v82cw : import CSV pour merge runs depuis backup. Permet à
                  l'user de restaurer ses leaderboards depuis un export
                  v82cv ou de consolider plusieurs sources. */}
              <div className="sp-sec">
                <label className="sp-label">Import CSV (merge avec dedup)</label>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  <label className="sp-btn" style={{ width: 'auto', marginTop: 0, cursor: 'pointer' }}>
                    📥 Import Academy CSV
                    <input type="file" accept=".csv,text/csv" style={{ display: 'none' }}
                      onChange={async (e) => {
                        const f = e.target.files?.[0]
                        e.target.value = ''
                        if (!f) return
                        try {
                          const txt = await f.text()
                          const lines = txt.split(/\r?\n/).filter((l) => l.trim().length > 0)
                          if (lines.length < 2) { window.alert('CSV vide ou sans données.'); return }
                          // Parse simpliste : split sur ',' qui ne sont pas dans des guillemets
                          const parseRow = (row: string) => {
                            const out: string[] = []; let cur = ''; let q = false
                            for (let i = 0; i < row.length; i++) {
                              const c = row[i]
                              if (c === '"') { if (q && row[i + 1] === '"') { cur += '"'; i++ } else { q = !q } }
                              else if (c === ',' && !q) { out.push(cur); cur = '' }
                              else cur += c
                            }
                            out.push(cur)
                            return out
                          }
                          const header = parseRow(lines[0]).map((s) => s.trim().toLowerCase())
                          const rows = lines.slice(1).map(parseRow)
                          const raw = window.localStorage.getItem('aurora-academy-leaderboard-v1')
                          const store = raw ? JSON.parse(raw) : { state: { runs: [] } }
                          const existing = (store?.state?.runs || []) as Array<{ id: string }>
                          const ids = new Set(existing.map((r) => r.id))
                          let imported = 0, skipped = 0
                          for (const row of rows) {
                            const obj: Record<string, string> = {}
                            for (let i = 0; i < header.length; i++) obj[header[i]] = row[i] || ''
                            if (!obj.id || ids.has(obj.id)) { skipped++; continue }
                            existing.push({
                              id: obj.id,
                              subject: obj.subject || '—',
                              mode: obj.mode || '—',
                              topic: obj.topic || '—',
                              startedAt: obj.started_at ? new Date(obj.started_at).getTime() : Date.now(),
                              endedAt: obj.ended_at ? new Date(obj.ended_at).getTime() : Date.now(),
                              durationMs: parseInt(obj.duration_ms || '0', 10),
                              durationLimitSec: parseInt(obj.duration_limit_sec || '0', 10),
                              score: parseInt(obj.score || '0', 10),
                              timeoutHit: obj.timeout_hit === 'true',
                              flashcardsConfidence: obj.flashcards_confidence
                                ? parseInt(obj.flashcards_confidence, 10) : undefined,
                            } as never)
                            ids.add(obj.id); imported++
                          }
                          window.localStorage.setItem('aurora-academy-leaderboard-v1', JSON.stringify({
                            state: { ...(store?.state || {}), runs: existing.slice(0, 200) },
                            version: store?.version ?? 0,
                          }))
                          window.alert(`Import Academy : ${imported} importé(s), ${skipped} doublon(s) ignoré(s). Recharge l'app pour voir.`)
                        } catch (err) {
                          window.alert(`Échec import : ${err instanceof Error ? err.message : String(err)}`)
                        }
                      }} />
                  </label>
                  <label className="sp-btn" style={{ width: 'auto', marginTop: 0, cursor: 'pointer' }}>
                    📥 Import Cyber CSV
                    <input type="file" accept=".csv,text/csv" style={{ display: 'none' }}
                      onChange={async (e) => {
                        const f = e.target.files?.[0]
                        e.target.value = ''
                        if (!f) return
                        try {
                          const txt = await f.text()
                          const lines = txt.split(/\r?\n/).filter((l) => l.trim().length > 0)
                          if (lines.length < 2) { window.alert('CSV vide ou sans données.'); return }
                          const parseRow = (row: string) => {
                            const out: string[] = []; let cur = ''; let q = false
                            for (let i = 0; i < row.length; i++) {
                              const c = row[i]
                              if (c === '"') { if (q && row[i + 1] === '"') { cur += '"'; i++ } else { q = !q } }
                              else if (c === ',' && !q) { out.push(cur); cur = '' }
                              else cur += c
                            }
                            out.push(cur)
                            return out
                          }
                          const header = parseRow(lines[0]).map((s) => s.trim().toLowerCase())
                          const rows = lines.slice(1).map(parseRow)
                          const raw = window.localStorage.getItem('aurora-cyber-leaderboard-v1')
                          const store = raw ? JSON.parse(raw) : { state: { runs: [] } }
                          const existing = (store?.state?.runs || []) as Array<{ kataId: string; startedAt: number }>
                          // Dedup Cyber : pas d'id stable, on use kataId+startedAt
                          const keys = new Set(existing.map((r) => `${r.kataId}|${r.startedAt}`))
                          let imported = 0, skipped = 0
                          for (const row of rows) {
                            const obj: Record<string, string> = {}
                            for (let i = 0; i < header.length; i++) obj[header[i]] = row[i] || ''
                            const startedAt = obj.started_at ? new Date(obj.started_at).getTime() : Date.now()
                            const kataId = obj.kata_id || '—'
                            const key = `${kataId}|${startedAt}`
                            if (keys.has(key)) { skipped++; continue }
                            existing.push({
                              kataId, stage: parseInt(obj.stage || '1', 10),
                              startedAt, endedAt: obj.ended_at ? new Date(obj.ended_at).getTime() : startedAt,
                              durationMs: parseInt(obj.duration_ms || '0', 10),
                              hintsTaken: parseInt(obj.hints_taken || '0', 10),
                              flagsFound: parseInt(obj.flags_found || '0', 10),
                              objectivesDone: parseInt(obj.objectives_done || '0', 10),
                              totalObjectives: parseInt(obj.total_objectives || '0', 10),
                              xpEarned: parseInt(obj.xp_earned || '0', 10),
                              mode: obj.mode || undefined,
                              score: obj.score ? parseInt(obj.score, 10) : undefined,
                              timeoutHit: obj.timeout_hit === 'true',
                              durationLimitSec: obj.duration_limit_sec ? parseInt(obj.duration_limit_sec, 10) : undefined,
                            } as never)
                            keys.add(key); imported++
                          }
                          window.localStorage.setItem('aurora-cyber-leaderboard-v1', JSON.stringify({
                            state: { ...(store?.state || {}), runs: existing.slice(0, 200) },
                            version: store?.version ?? 0,
                          }))
                          window.alert(`Import Cyber : ${imported} importé(s), ${skipped} doublon(s) ignoré(s). Recharge l'app pour voir.`)
                        } catch (err) {
                          window.alert(`Échec import : ${err instanceof Error ? err.message : String(err)}`)
                        }
                      }} />
                  </label>
                </div>
                <div className="sp-hint" style={{ marginTop: 4 }}>
                  Dedup : Academy par id, Cyber par (kata_id + started_at). Cap 200 runs/store.
                </div>
              </div>

              {/* v82cs : effacer les sessions persistées Academy + Cyber */}
              <div className="sp-sec">
                <label className="sp-label">Sessions sauvegardées</label>
                <button type="button" className="sp-btn"
                  style={{ width: 'auto', marginTop: 0 }}
                  onClick={() => {
                    if (typeof window === 'undefined') return
                    if (!window.confirm(
                      'Effacer les sessions sauvegardées Academy + Cyber + leaderboards ?\n\n'
                      + 'Cela retire :\n'
                      + '• Le sujet, mode, matière, leçon Academy en cours\n'
                      + '• Le kata, stage, posture, XP Cyber\n'
                      + '• Tous les runs des leaderboards (achievements perdus)\n\n'
                      + 'Action irréversible.',
                    )) return
                    try {
                      window.localStorage.removeItem('aurora-academy-session-v1')
                      window.localStorage.removeItem('aurora-cyber-session-v1')
                      window.localStorage.removeItem('aurora-academy-leaderboard-v1')
                      window.localStorage.removeItem('aurora-cyber-leaderboard-v1')
                      // v82dh : aussi clear le tracking achievements
                      window.localStorage.removeItem('aurora-achievements-seen-v1')
                      window.localStorage.removeItem('aurora-achievements-tiers-v1')
                      // v82dj : timestamps unlock
                      window.localStorage.removeItem('aurora-achievements-unlock-times-v1')
                    } catch { /* ignore */ }
                    window.location.reload()
                  }}>
                  ✕ Effacer mes sessions + leaderboards
                </button>
                <div className="sp-hint" style={{ marginTop: 4 }}>
                  Recharge l'app dans un état neutre. Les fichiers locaux ne sont pas touchés.
                </div>
              </div>
              {/* v82h2 : status live auto-polling 10s par service */}
              <ServicesLiveStatus />
              {/* v82jb : status Aurora-Connect Chrome extension */}
              <ExtensionStatusPanel />
              {/* v82hi : log historique des transitions services */}
              <ServiceTransitionsPanel />
              {/* v82ha : RAM browser + quota storage */}
              <BrowserResourcesPanel />
              {/* v82fy + v82fz + v82ga : ping bridge + ollama + comfyui + all */}
              <div className="sp-sec">
                <label className="sp-label">Ping services</label>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {/* v82ga : "Ping all" parallel + summary */}
                  <button type="button" className="sp-btn"
                    style={{ width: 'auto', marginTop: 0, fontWeight: 700 }}
                    onClick={async (e) => {
                      const btn = e.currentTarget
                      btn.textContent = '…'
                      btn.disabled = true
                      const services = [
                        { id: 'bridge', path: '/api/agents/list' },
                        { id: 'ollama', path: '/proxy/ollama/api/tags' },
                        { id: 'comfy', path: '/proxy/comfy/system_stats' },
                      ]
                      try {
                        const { getBridgeUrl } = await import('../utils/runtime')
                        const base = getBridgeUrl()
                        const results = await Promise.all(services.map(async ({ id, path }) => {
                          const t0 = performance.now()
                          try {
                            const res = await fetch(`${base}${path}`, {
                              signal: AbortSignal.timeout(5000),
                              cache: 'no-store',
                            })
                            return { id, ok: res.ok, ms: Math.round(performance.now() - t0), status: res.status }
                          } catch {
                            return { id, ok: false, ms: Math.round(performance.now() - t0), status: 0 }
                          }
                        }))
                        const okCount = results.filter((r) => r.ok).length
                        const slowest = Math.max(...results.map((r) => r.ms))
                        btn.textContent = `${okCount}/3 OK · max ${slowest}ms`
                      } catch (err) {
                        btn.textContent = `✗ ${err instanceof Error ? err.message.slice(0, 30) : 'fail'}`
                      } finally {
                        window.setTimeout(() => {
                          btn.textContent = '⚡ Ping all'
                          btn.disabled = false
                        }, 5000)
                      }
                    }}>
                    ⚡ Ping all
                  </button>
                  {([
                    { id: 'bridge', label: '🔁 Bridge', path: '/api/agents/list' },
                    { id: 'ollama', label: '🦙 Ollama', path: '/proxy/ollama/api/tags' },
                    { id: 'comfy', label: '🎨 ComfyUI', path: '/proxy/comfy/system_stats' },
                  ]).map(({ id, label, path }) => (
                    <button key={id} type="button" className="sp-btn"
                      style={{ width: 'auto', marginTop: 0 }}
                      onClick={async (e) => {
                        const btn = e.currentTarget
                        const orig = label
                        btn.textContent = '…'
                        btn.disabled = true
                        const t0 = performance.now()
                        try {
                          const { getBridgeUrl } = await import('../utils/runtime')
                          const url = `${getBridgeUrl()}${path}`
                          const res = await fetch(url, {
                            signal: AbortSignal.timeout(5000),
                            cache: 'no-store',
                          })
                          const ms = Math.round(performance.now() - t0)
                          btn.textContent = res.ok ? `✓ ${ms} ms` : `⚠ ${res.status} (${ms} ms)`
                        } catch (err) {
                          const ms = Math.round(performance.now() - t0)
                          btn.textContent = `✗ ${err instanceof Error ? err.message.slice(0, 30) : 'fail'} (${ms})`
                        } finally {
                          window.setTimeout(() => {
                            btn.textContent = orig
                            btn.disabled = false
                          }, 4000)
                        }
                      }}>
                      {label}
                    </button>
                  ))}
                </div>
                <div className="sp-hint" style={{ marginTop: 4 }}>
                  Mesure la latence vers chaque service. Bridge Flask
                  (port 3001), Ollama (port 11434 via proxy), ComfyUI
                  (port 8188 via proxy). 5s timeout chacun.
                </div>
              </div>
              {/* v82fx : toggle pour désactiver les daily tips */}
              <div className="sp-sec">
                <label className="sp-label">Astuces du jour</label>
                <button type="button" className="sp-btn"
                  style={{ width: 'auto', marginTop: 0 }}
                  onClick={() => {
                    if (typeof window === 'undefined') return
                    try {
                      const cur = window.localStorage.getItem('aurora-tips-enabled-v1')
                      const enabled = cur === null ? true : cur === '1' || cur === 'true'
                      window.localStorage.setItem('aurora-tips-enabled-v1', enabled ? '0' : '1')
                    } catch { /* ignore */ }
                    window.location.reload()
                  }}>
                  ↻ Bascule (recharge la page)
                </button>
                <div className="sp-hint" style={{ marginTop: 4 }}>
                  Les "💡 astuces" apparaissent dans les empty states des
                  modules. Désactive-les si elles te distraient. Réactivable
                  ici à tout moment.
                </div>
              </div>
              {/* v82fq : "À propos" — runtime mode + skin + git hash si dispo */}
              <div className="sp-sec">
                <label className="sp-label">À propos</label>
                <div style={{
                  padding: 8, borderRadius: 6,
                  background: 'var(--bg-card, rgba(255,255,255,0.04))',
                  border: '1px solid var(--line, rgba(255,255,255,0.18))',
                  fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
                  color: 'var(--fg-dim, #aaa)',
                  display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '4px 12px',
                  alignItems: 'baseline',
                }}>
                  <span style={{ color: 'var(--fg-mute, #777)' }}>Skin</span>
                  <span style={{ color: 'var(--fg, #f5f5f5)' }}>{uiSkin}</span>
                  <span style={{ color: 'var(--fg-mute, #777)' }}>Theme</span>
                  <span style={{ color: 'var(--fg, #f5f5f5)' }}>{theme}</span>
                  <span style={{ color: 'var(--fg-mute, #777)' }}>Runtime</span>
                  <span style={{ color: 'var(--fg, #f5f5f5)' }}>
                    {typeof window !== 'undefined' && window.__TAURI__ ? 'Tauri (desktop)'
                      : typeof window !== 'undefined' && /trycloudflare\.com$/i.test(window.location.hostname) ? 'Cloud (tunnel)'
                      : 'Browser (local)'}
                  </span>
                  <span style={{ color: 'var(--fg-mute, #777)' }}>Origine</span>
                  <span style={{ color: 'var(--fg, #f5f5f5)', wordBreak: 'break-all' }}>
                    {typeof window !== 'undefined' ? window.location.origin : '—'}
                  </span>
                  <span style={{ color: 'var(--fg-mute, #777)' }}>Modèle</span>
                  <span style={{ color: 'var(--fg, #f5f5f5)' }}>{mainModel}</span>
                  {/* v82j3 : itération approximative basée sur le compte
                      des entrées CHANGELOG visible dans le bundle (proxy
                      indirect — affichage stable seulement si bundle
                      build). */}
                  <span style={{ color: 'var(--fg-mute, #777)' }}>Build</span>
                  <span style={{ color: 'var(--fg, #f5f5f5)' }}
                    title={`Branch ${typeof __AURORA_BRANCH__ !== 'undefined' ? __AURORA_BRANCH__ : 'unknown'} · ${typeof __AURORA_BUILD_TS__ !== 'undefined' ? __AURORA_BUILD_TS__ : ''}`}>
                    {typeof __AURORA_COMMIT__ !== 'undefined' ? __AURORA_COMMIT__ : 'dev'} · 19 module chunks
                  </span>
                  <span style={{ color: 'var(--fg-mute, #777)' }}>UA</span>
                  <span style={{ color: 'var(--fg-dim, #aaa)', fontSize: 10, wordBreak: 'break-all' }}>
                    {typeof navigator !== 'undefined'
                      ? (navigator.userAgent.match(/Chrome\/[\d.]+|Firefox\/[\d.]+|Safari\/[\d.]+|Edg\/[\d.]+/)?.[0] ?? 'unknown')
                      : '—'}
                  </span>
                </div>
                {/* v82fr : bouton copy diagnostic formatté pour rapports */}
                <button type="button" className="sp-btn"
                  style={{ width: 'auto', marginTop: 6 }}
                  onClick={() => {
                    if (typeof window === 'undefined') return
                    const runtime = window.__TAURI__ ? 'Tauri (desktop)'
                      : /trycloudflare\.com$/i.test(window.location.hostname) ? 'Cloud (tunnel)'
                      : 'Browser (local)'
                    const block = [
                      '## Aurora diagnostic',
                      '',
                      `- Skin : ${uiSkin}`,
                      `- Theme : ${theme}`,
                      `- Runtime : ${runtime}`,
                      `- Origine : ${window.location.origin}`,
                      `- Modèle : ${mainModel}`,
                      `- Date : ${new Date().toISOString()}`,
                      `- UA : ${navigator.userAgent}`,
                    ].join('\n')
                    try { void navigator.clipboard.writeText(block) } catch { /* silent */ }
                  }}>
                  📋 Copier diagnostic markdown
                </button>
                <div className="sp-hint" style={{ marginTop: 4 }}>
                  Inclus dans les rapports de bug — copie-colle ces lignes pour aider au diagnostic.
                </div>
              </div>
              {/* v82fo + v82fp : URL tunnel courant + QR code mobile share */}
              <div className="sp-sec">
                <label className="sp-label">URL d'accès courante</label>
                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  <input type="text" readOnly
                    value={typeof window !== 'undefined' ? window.location.origin : ''}
                    onFocus={(e) => e.currentTarget.select()}
                    style={{
                      flex: 1, padding: '6px 8px', fontSize: 11,
                      background: 'var(--bg-card, rgba(255,255,255,0.04))',
                      color: 'var(--fg, #f5f5f5)',
                      border: '1px solid var(--line, rgba(255,255,255,0.18))',
                      borderRadius: 4,
                      fontFamily: 'var(--font-mono, monospace)',
                    }} />
                  <button type="button" className="sp-btn"
                    style={{ width: 'auto', marginTop: 0 }}
                    onClick={() => {
                      if (typeof window === 'undefined') return
                      try {
                        void navigator.clipboard.writeText(window.location.origin)
                      } catch { /* silent */ }
                    }}>
                    📋 Copier
                  </button>
                </div>
                {/* v82fp : QR code via api.qrserver.com pour scan mobile direct */}
                {typeof window !== 'undefined' && (
                  <div style={{
                    marginTop: 8, padding: 8, borderRadius: 6,
                    background: 'var(--bg-card, rgba(255,255,255,0.04))',
                    border: '1px dashed var(--line, rgba(255,255,255,0.18))',
                    display: 'flex', alignItems: 'center', gap: 12,
                  }}>
                    <img alt="QR code de l'URL"
                      src={`https://api.qrserver.com/v1/create-qr-code/?size=140x140&data=${encodeURIComponent(window.location.origin)}&bgcolor=ffffff&color=0c0a09&margin=4`}
                      width={140} height={140}
                      style={{ borderRadius: 4, background: '#fff' }} />
                    <div style={{ flex: 1, fontSize: 11, color: 'var(--fg-dim, #aaa)', lineHeight: 1.6 }}>
                      <div style={{ color: 'var(--fg, #f5f5f5)', fontWeight: 700, marginBottom: 4 }}>
                        Scan pour ouvrir
                      </div>
                      Pointe l'appareil photo de ton téléphone vers le QR pour ouvrir Aurora directement, sans taper l'URL.
                    </div>
                  </div>
                )}
                <div className="sp-hint" style={{ marginTop: 4 }}>
                  Partage cette URL pour ouvrir Aurora sur mobile ou un autre PC.
                  L'accès distant est géré par l'éditeur — rien à configurer ici.
                </div>
              </div>
              {/* v82em : reset prefs UI seulement (pas les runs/leaderboards) */}
              <div className="sp-sec">
                <label className="sp-label">Préférences UI</label>
                <button type="button" className="sp-btn"
                  style={{ width: 'auto', marginTop: 0 }}
                  onClick={() => {
                    if (typeof window === 'undefined') return
                    if (!window.confirm(
                      'Réinitialiser les préférences UI ?\n\n'
                      + 'Cela retire :\n'
                      + '• Notes Cyber active + leçon Academy active\n'
                      + '• Toggles affichage AchievementsPanel\n'
                      + '• Presets custom + objectif hebdo\n'
                      + '• Top milestones count + slash recent\n\n'
                      + 'Les runs / leaderboards / achievements unlocked sont préservés.',
                    )) return
                    try {
                      const keysToWipe = [
                        // v82en : milestones count
                        'aurora-top-milestones-count-v1',
                        // v82eo : prefs ladders/trend/ribbon/milestones
                        'aurora-achievements-display-prefs-v1',
                        // v82eq : presets custom user-définis
                        'aurora-achievements-display-custom-presets-v1',
                        // v82ea : weekly goal
                        'aurora-weekly-goal-v1',
                        // v82ej : slash LRU
                        'aurora-slash-recent-v1',
                        // v82er : notes Cyber
                        'aurora-cyber-notes-v1',
                        // v82fx : tips on/off
                        'aurora-tips-enabled-v1',
                      ]
                      for (const k of keysToWipe) {
                        window.localStorage.removeItem(k)
                      }
                    } catch { /* ignore */ }
                    window.location.reload()
                  }}>
                  ↻ Réinitialiser prefs UI
                </button>
                <div className="sp-hint" style={{ marginTop: 4 }}>
                  Réinit toggles AchievementsPanel + objectif hebdo + presets perso + slash recent. Runs et leaderboards préservés.
                </div>
              </div>
              {/* v82ic : panneau "Mes streaks" agrégé 7 modules */}
              <StreaksPanel />
              {/* v82gu : panneau historique global multi-module agrégé */}
              <PromptHistoryPanel />
              {/* v82hd : panneau favoris persistants cross-module */}
              <FavoritesPanel />
              {/* v82gj : diagnostic stockage — taille par clé + delete individuel */}
              <StorageDiagnostic />
              {/* v82gi : export / import workspace (toutes les clés aurora-*) */}
              <div className="sp-sec">
                <label className="sp-label">Sauvegarde · Workspace</label>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  <button type="button" className="sp-btn"
                    style={{ width: 'auto', marginTop: 0 }}
                    onClick={() => {
                      if (typeof window === 'undefined') return
                      try {
                        const ls = window.localStorage
                        const out: Record<string, string> = {}
                        for (let i = 0; i < ls.length; i++) {
                          const k = ls.key(i)
                          if (k && k.startsWith('aurora')) {
                            const v = ls.getItem(k)
                            if (v !== null) out[k] = v
                          }
                        }
                        const payload = {
                          schema: 'aurora.workspace.v1',
                          exportedAt: new Date().toISOString(),
                          keyCount: Object.keys(out).length,
                          data: out,
                        }
                        const blob = new Blob([JSON.stringify(payload, null, 2)],
                          { type: 'application/json' })
                        const url = URL.createObjectURL(blob)
                        const a = document.createElement('a')
                        a.href = url
                        const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
                        a.download = `aurora-workspace-${stamp}.json`
                        a.click()
                        setTimeout(() => URL.revokeObjectURL(url), 1000)
                      } catch (err) {
                        window.alert('Export échoué : ' + (err as Error).message)
                      }
                    }}>
                    💾 Exporter workspace
                  </button>
                  <button type="button" className="sp-btn"
                    style={{ width: 'auto', marginTop: 0 }}
                    onClick={() => {
                      if (typeof window === 'undefined') return
                      const input = document.createElement('input')
                      input.type = 'file'
                      input.accept = '.json,application/json'
                      input.onchange = async () => {
                        const file = input.files?.[0]
                        if (!file) return
                        try {
                          const text = await file.text()
                          const parsed = JSON.parse(text)
                          if (parsed?.schema !== 'aurora.workspace.v1') {
                            window.alert('Schéma invalide : attendu aurora.workspace.v1')
                            return
                          }
                          const data = parsed.data
                          if (!data || typeof data !== 'object') {
                            window.alert('Données absentes ou corrompues.')
                            return
                          }
                          const keys = Object.keys(data).filter((k) => k.startsWith('aurora'))
                          if (keys.length === 0) {
                            window.alert('Aucune clé aurora-* dans le fichier.')
                            return
                          }
                          if (!window.confirm(
                            `Importer ${keys.length} clé(s) du workspace ?\n\n`
                            + 'Cela écrase les valeurs locales correspondantes.\n'
                            + 'Les autres clés (non présentes dans le fichier) sont préservées.\n\n'
                            + 'L\'app se recharge après import.',
                          )) return
                          for (const k of keys) {
                            const v = data[k]
                            if (typeof v === 'string') window.localStorage.setItem(k, v)
                          }
                          window.location.reload()
                        } catch (err) {
                          window.alert('Import échoué : ' + (err as Error).message)
                        }
                      }
                      input.click()
                    }}>
                    📥 Importer workspace
                  </button>
                </div>
                <div className="sp-hint" style={{ marginTop: 4 }}>
                  Backup JSON de toutes les clés <code>aurora-*</code> (prefs, runs, achievements, recents, pinned, notes…). Migration machine→machine ou rollback rapide.
                </div>
              </div>
              <div className="sp-sec">
                <label className="sp-label">Télécharger un modèle</label>
                <div style={{ display: 'flex', gap: 6 }}>
                  <input type="text" className="sp-select" style={{ flex: 1 }}
                    placeholder="ex: llama3.2, qwen3:14b, mistral, gemma3…"
                    value={pullName}
                    onChange={(e) => setPullName(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter' && !pulling) { e.preventDefault(); void startPull() } }}
                    disabled={pulling} />
                  <button type="button" className="sp-btn is-primary"
                    style={{ width: 'auto', marginTop: 0 }}
                    onClick={() => void startPull()}
                    disabled={pulling || !pullName.trim()}>
                    {pulling ? '…' : '↓ Pull'}
                  </button>
                </div>
                {pullProgress && (
                  <div className="sp-pull-progress">
                    <div className="sp-pull-status">
                      {pullProgress.status}
                      {typeof pullProgress.total === 'number' && typeof pullProgress.completed === 'number' && (
                        <span> · {(pullProgress.completed / 1024 / 1024).toFixed(1)} MB / {(pullProgress.total / 1024 / 1024).toFixed(1)} MB</span>
                      )}
                    </div>
                    <div className="sp-pull-bar">
                      <span style={{
                        width: typeof pullProgress.total === 'number' && pullProgress.total > 0 && typeof pullProgress.completed === 'number'
                          ? `${(pullProgress.completed / pullProgress.total) * 100}%`
                          : pullProgress.status === 'success' ? '100%'
                          : '10%',
                      }} />
                    </div>
                  </div>
                )}
                {pullError && <div className="sp-warn">⚠ {pullError}</div>}
              </div>
            </>
          )}

          {expanded === 'shortcuts' && (
            <div className="sp-sec">
              <ul className="sp-shortcuts">
                {SHORTCUTS.map((s) => (
                  <li key={s.combo}>
                    <kbd>{s.combo}</kbd>
                    <span>{s.action}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {expanded === 'notif' && (
            <div className="sp-sec">
              <div className="sp-row"><b>Plateforme</b><span>{install.platform}{install.standalone ? ' · PWA' : ''}</span></div>
              <div className="sp-row"><b>API Notification</b><span>{install.supportsNotification ? 'OK' : 'non supportée'}</span></div>
              <div className="sp-row"><b>Permission</b><span>{perm}</span></div>
              {install.needsPwaInstall && (
                <div className="sp-warn">iOS : installe l'app sur l'écran d'accueil pour débloquer les notifications.</div>
              )}
              {perm === 'default' && !install.needsPwaInstall && (
                <button type="button" className="sp-btn is-primary" onClick={() => void ensurePushPermission()}>
                  🔔 Autoriser les notifications
                </button>
              )}
            </div>
          )}

          {expanded === 'calendar' && (
            <>
              {/* v82jc : panneau Portails école avec icons + finder */}
              <SchoolPortalsPanel onPickUrl={(u) => setFeedUrl(u)} />
              {/* v82jw Phase 3 : panneau credentials auto-login */}
              <EntCredentialPanel />
              <div className="sp-sec">
                <label className="sp-label">Importer un fichier .ics</label>
                <input type="file" accept=".ics,text/calendar" onChange={onIcsFile} disabled={icsBusy} />
                <div className="sp-hint">
                  Pronote / ÉcoleDirecte / Google Calendar / Outlook exportent tous en ICS — fichier ou URL.
                </div>
              </div>
              <div className="sp-sec">
                <label className="sp-label">URL de flux ICS</label>
                <div style={{ display: 'flex', gap: 6 }}>
                  <input type="url" className="sp-select" style={{ flex: 1 }}
                    placeholder="https://…/edt.ics"
                    value={feedUrl || ''}
                    onChange={(e) => setFeedUrl(e.target.value || null)}
                    disabled={icsBusy} />
                  <button type="button" className="sp-btn is-primary"
                    style={{ width: 'auto', marginTop: 0 }}
                    onClick={() => void fetchFeed()}
                    disabled={icsBusy || !feedUrl}>
                    {icsBusy ? '…' : '↓ Sync'}
                  </button>
                </div>
              </div>
              {icsError && <div className="sp-warn">⚠ {icsError}</div>}
              <div className="sp-sec">
                <div className="sp-row"><b>Événements importés</b><span>{events.length}</span></div>
                {events.slice(0, 5).map((ev) => (
                  <div key={ev.id} style={{ fontSize: 11, padding: '3px 0', borderBottom: '1px dashed var(--ft-ink)' }}>
                    <b>{ev.title}</b>
                    <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 9, color: 'var(--ft-muted)', marginLeft: 6 }}>
                      {new Date(ev.start).toLocaleString('fr-FR', { weekday: 'short', day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
                    </span>
                    {ev.location && <span style={{ fontSize: 9, color: 'var(--ft-muted)', marginLeft: 6 }}>· {ev.location}</span>}
                  </div>
                ))}
                {events.length > 5 && <div className="sp-small">+{events.length - 5} autres</div>}
                {events.length > 0 && (
                  <button type="button" className="sp-btn" onClick={() => { if (window.confirm('Effacer tous les événements ?')) clearAllCal() }}>
                    🗑 Effacer le calendrier
                  </button>
                )}
              </div>
            </>
          )}

          {expanded === 'data' && (
            <>
              <div className="sp-sec">
                <div className="sp-row"><b>XP · niveau</b><span>{xp} xp · niv. {level}</span></div>
                <div className="sp-row"><b>Messages conversation</b><span>{chatLen}</span></div>
                <div className="sp-row"><b>Jobs Forge</b><span>{forgeJobs}</span></div>
                <div className="sp-row"><b>Drafts modules</b><span>{Object.keys(drafts).length}</span></div>
              </div>
              <div className="sp-sec">
                <button type="button" className="sp-btn is-primary" onClick={async () => {
                  const mod = await import('../utils/backup')
                  mod.downloadBackup()
                }}>💾 Exporter backup (JSON)</button>
                <input type="file" accept=".json,application/json" style={{ display: 'none' }} id="sp-restore-input"
                  onChange={async (e) => {
                    const f = e.target.files?.[0]
                    if (!f) return
                    if (!window.confirm('⚠ Restaurer ce backup va ÉCRASER tes données actuelles et recharger la page. Continuer ?')) { e.target.value = ''; return }
                    const mod = await import('../utils/backup')
                    const res = await mod.restoreFromFile(f)
                    if (res.error) { alert('Erreur : ' + res.error); return }
                    alert(`Restauré : ${res.restored} entrées (${res.skipped} ignorées). Rechargement…`)
                    window.location.reload()
                  }} />
                <button type="button" className="sp-btn" onClick={() => document.getElementById('sp-restore-input')?.click()}>
                  ↩ Restaurer un backup
                </button>
                <button type="button" className="sp-btn" onClick={() => {
                  if (window.confirm('Effacer TOUS les messages de la conversation ?')) clearChat()
                }}>🗑 Effacer conversations</button>
                <button type="button" className="sp-btn" onClick={() => {
                  Object.keys(drafts).forEach((k) => clearDraft(k as Parameters<typeof clearDraft>[0]))
                }}>🧹 Effacer drafts modules</button>
                <button type="button" className="sp-btn is-danger" onClick={() => {
                  if (window.confirm('⚠ Effacer TOUTES les données locales ? (modèles réinstallés Ollama conservés)')) {
                    try { localStorage.clear() } catch { /* ignore */ }
                    try { sessionStorage.clear() } catch { /* ignore */ }
                    window.location.reload()
                  }
                }}>⚠ Reset complet local</button>
              </div>
            </>
          )}
          {/* v82j7 : footer build hash inline (visible quel que soit
              le tab actif) */}
          <div style={{
            marginTop: 16, paddingTop: 8,
            borderTop: '1px solid var(--line-soft, rgba(255,255,255,0.06))',
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            fontSize: 9, fontFamily: 'var(--font-mono, monospace)',
            color: 'var(--fg-mute, #777)', letterSpacing: '0.05em',
          }}
            title={`Branch ${typeof __AURORA_BRANCH__ !== 'undefined' ? __AURORA_BRANCH__ : 'unknown'} · ${typeof __AURORA_BUILD_TS__ !== 'undefined' ? __AURORA_BUILD_TS__ : ''}`}>
            <span>Aurora {typeof __AURORA_COMMIT__ !== 'undefined' ? __AURORA_COMMIT__ : 'dev'}</span>
            <span>juan of bike IA</span>
          </div>
        </div>
      </aside>
    </div>
    </>,
    document.body,
  )
}

// v82gj : diagnostic stockage — affiche taille totale et top-10 clés aurora-*
//   avec delete individuel. Aide à identifier les clés gourmandes.
function StorageDiagnostic() {
  const [tick, setTick] = useState(0)
  const [showAll, setShowAll] = useState(false)
  const refresh = () => setTick((t) => t + 1)

  const stats = (() => {
    if (typeof window === 'undefined') return { entries: [] as Array<[string, number]>, total: 0, count: 0 }
    try {
      const ls = window.localStorage
      const out: Array<[string, number]> = []
      let total = 0
      for (let i = 0; i < ls.length; i++) {
        const k = ls.key(i)
        if (!k || !k.startsWith('aurora')) continue
        const v = ls.getItem(k) ?? ''
        // UTF-16 = 2 bytes/char, mais en JSON-string brut on est ASCII-ish.
        // Approximation byteLength via TextEncoder pour précision.
        const bytes = new TextEncoder().encode(v).byteLength + new TextEncoder().encode(k).byteLength
        out.push([k, bytes])
        total += bytes
      }
      out.sort((a, b) => b[1] - a[1])
      return { entries: out, total, count: out.length }
    } catch { return { entries: [] as Array<[string, number]>, total: 0, count: 0 } }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  })()
  // recompute on tick
  void tick

  const fmt = (b: number) => {
    if (b < 1024) return `${b} B`
    if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} kB`
    return `${(b / 1024 / 1024).toFixed(2)} MB`
  }

  const visible = showAll ? stats.entries : stats.entries.slice(0, 10)

  // v82gl : limite typique localStorage = 5 MB (Chrome/Firefox/Safari).
  // Affiche une bar de progression + warning si > 80%.
  const LIMIT_BYTES = 5 * 1024 * 1024
  const ratio = Math.min(1, stats.total / LIMIT_BYTES)
  const ratioPct = (ratio * 100).toFixed(1)
  const danger = ratio > 0.8
  const caution = ratio > 0.5 && !danger
  const barColor = danger ? 'oklch(0.62 0.20 25)' : caution ? 'oklch(0.78 0.16 80)' : 'oklch(0.70 0.13 145)'

  return (
    <div className="sp-sec">
      <label className="sp-label">Diagnostic stockage</label>
      <div style={{
        display: 'flex', justifyContent: 'space-between',
        fontSize: 11, fontFamily: 'var(--font-mono, monospace)',
        color: 'var(--fg-mute, #999)', marginBottom: 6,
      }}>
        <span>{stats.count} clé(s) aurora-*</span>
        <span>Total : {fmt(stats.total)} <span style={{ opacity: 0.6 }}>· {ratioPct}%</span></span>
      </div>
      {/* v82gl : bar de progression visuelle */}
      <div style={{
        height: 4, borderRadius: 2,
        background: 'var(--line-soft, rgba(255,255,255,0.10))',
        marginBottom: 8, overflow: 'hidden',
      }}>
        <div style={{
          width: `${ratio * 100}%`, height: '100%',
          background: barColor,
          transition: 'width .25s ease, background .25s ease',
        }} />
      </div>
      {danger && (
        <div style={{
          fontSize: 11, padding: '6px 8px', marginBottom: 8,
          borderRadius: 4, fontFamily: 'var(--font-mono, monospace)',
          background: 'oklch(0.62 0.20 25 / 0.12)',
          border: '1px solid oklch(0.62 0.20 25 / 0.4)',
          color: 'oklch(0.78 0.18 25)',
        }}>
          ⚠ Approche limite navigateur. Exporte le workspace puis supprime les clés volumineuses ci-dessous.
        </div>
      )}
      {stats.entries.length === 0 ? (
        <div className="sp-hint">Aucune clé aurora-* stockée.</div>
      ) : (
        <>
          <div style={{
            display: 'flex', flexDirection: 'column', gap: 2,
            maxHeight: 200, overflowY: 'auto',
            border: '1px solid var(--line-soft, rgba(255,255,255,0.08))',
            borderRadius: 4, padding: 4,
          }}>
            {visible.map(([k, bytes]) => (
              <div key={k} style={{
                display: 'grid', gridTemplateColumns: '1fr auto auto',
                gap: 8, alignItems: 'center', padding: '3px 6px',
                fontSize: 11, fontFamily: 'var(--font-mono, monospace)',
                borderRadius: 3,
              }}>
                <span style={{
                  whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                  color: 'var(--fg, #f5f5f5)',
                }} title={k}>{k}</span>
                <span style={{
                  color: 'var(--fg-mute, #888)',
                  fontVariantNumeric: 'tabular-nums',
                }}>{fmt(bytes)}</span>
                <button type="button"
                  onClick={() => {
                    if (!window.confirm(`Supprimer la clé "${k}" ?\n${fmt(bytes)} libérés.`)) return
                    try { window.localStorage.removeItem(k); refresh() } catch { /* noop */ }
                  }}
                  title="Supprimer cette clé"
                  style={{
                    width: 22, height: 22,
                    border: '1px solid var(--line, rgba(255,255,255,0.18))',
                    background: 'transparent', cursor: 'pointer',
                    color: 'var(--fg-mute, #888)', borderRadius: 3,
                    fontSize: 11, padding: 0,
                  }}>×</button>
              </div>
            ))}
          </div>
          {stats.entries.length > 10 && (
            <button type="button"
              onClick={() => setShowAll((v) => !v)}
              style={{
                marginTop: 6, fontSize: 10,
                background: 'transparent', border: 'none',
                color: 'var(--accent, #c8a96a)', cursor: 'pointer',
                fontFamily: 'var(--font-mono, monospace)', padding: 0,
              }}>
              {showAll ? `↑ Masquer (${stats.entries.length - 10} cachées)` : `↓ Afficher tout (${stats.entries.length - 10} de plus)`}
            </button>
          )}
          <div className="sp-hint" style={{ marginTop: 4 }}>
            Top par taille. Clic <code>×</code> supprime une clé spécifique. Limite navigateur ≈ 5–10 MB.
          </div>
        </>
      )}
    </div>
  )
}

// v82gu : panneau historique global multi-module — aggrège les 5
//   prompt-history persistants (image, code, drawing, video, 3d) en
//   une vue unique avec filtre par module + delete individuel + clear.
type HistoryRow = PromptHistoryEntry & { module: string }
const HISTORY_MODULES = ['image', 'code', 'drawing', 'video', '3d'] as const
type HistoryModule = typeof HISTORY_MODULES[number]
const MODULE_LABELS: Record<HistoryModule, string> = {
  image: 'Image', code: 'Code', drawing: 'Dessin', video: 'Vidéo', '3d': '3D',
}

// v82gz : surligne les match du search dans le prompt (case-insensitive).
function highlightMatch(text: string, q: string): ReactNode {
  if (!q) return text
  const idx = text.toLowerCase().indexOf(q)
  if (idx === -1) return text
  const before = text.slice(0, idx)
  const match = text.slice(idx, idx + q.length)
  const after = text.slice(idx + q.length)
  return (
    <>
      {before}
      <mark style={{
        background: 'oklch(0.78 0.16 80 / 0.35)',
        color: 'inherit', padding: '0 1px', borderRadius: 2,
      }}>{match}</mark>
      {highlightMatch(after, q)}
    </>
  )
}

function PromptHistoryPanel() {
  const [tick, setTick] = useState(0)
  const [filter, setFilter] = useState<HistoryModule | 'all'>('all')
  const [copiedKey, setCopiedKey] = useState<string | null>(null)
  // v82gx : recherche fulltext sur le prompt + module label.
  const [search, setSearch] = useState('')
  const setActiveModule = useAppStore((s) => s.setActiveModule)
  const setDraft = useModuleDraftsStore((s) => s.setDraft)

  // v82gv : copy clipboard avec feedback ✓ 1.5s
  const copyToClipboard = (key: string, prompt: string) => {
    if (typeof navigator === 'undefined' || !navigator.clipboard) return
    navigator.clipboard.writeText(prompt).then(() => {
      setCopiedKey(key)
      window.setTimeout(() => setCopiedKey(null), 1500)
    }).catch(() => { /* swallow */ })
  }

  // v82gw : recall direct → setDraft module-cible + setActiveModule.
  //   Mappe le module 'drawing' → ModuleId 'drawing', etc.
  const recallTo = (m: HistoryModule, prompt: string) => {
    // ModuleId est == HistoryModule pour les 5 modules génératifs.
    setDraft(m as 'image' | 'code' | 'drawing' | 'video' | '3d', { prompt })
    setActiveModule(m as 'image' | 'code' | 'drawing' | 'video' | '3d')
  }

  const all: HistoryRow[] = (() => {
    const out: HistoryRow[] = []
    for (const m of HISTORY_MODULES) {
      for (const e of readHistory(m)) out.push({ ...e, module: m })
    }
    out.sort((a, b) => b.ts - a.ts)
    return out
  })()
  void tick

  // v82gx : applique d'abord filter module, ensuite search (case-insensitive).
  const byModule = filter === 'all' ? all : all.filter((r) => r.module === filter)
  const q = search.trim().toLowerCase()
  const filtered = q
    ? byModule.filter((r) =>
        r.prompt.toLowerCase().includes(q)
        || (MODULE_LABELS[r.module as HistoryModule] ?? r.module).toLowerCase().includes(q),
      )
    : byModule
  const counts: Record<HistoryModule | 'all', number> = {
    all: all.length,
    image: 0, code: 0, drawing: 0, video: 0, '3d': 0,
  }
  for (const r of all) counts[r.module as HistoryModule]++

  const fmtTs = (ts: number) => {
    const d = new Date(ts)
    const today = new Date().toDateString()
    if (d.toDateString() === today) return d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
    return d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' })
  }

  return (
    <div className="sp-sec">
      <label className="sp-label">Historique prompts global</label>
      {/* Filter chips par module */}
      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 6 }}>
        {(['all', ...HISTORY_MODULES] as Array<HistoryModule | 'all'>).map((m) => (
          <button key={m} type="button"
            onClick={() => setFilter(m)}
            style={{
              padding: '3px 8px', fontSize: 10,
              fontFamily: 'var(--font-mono, monospace)',
              border: filter === m
                ? '1px solid var(--accent, #c8a96a)'
                : '1px solid var(--line, rgba(255,255,255,0.12))',
              background: filter === m
                ? 'var(--accent-soft, rgba(200,169,106,0.12))'
                : 'transparent',
              color: filter === m ? 'var(--accent, #c8a96a)' : 'var(--fg-mute, #888)',
              borderRadius: 3, cursor: 'pointer',
            }}>
            {m === 'all' ? 'Tous' : MODULE_LABELS[m]} ({counts[m]})
          </button>
        ))}
      </div>
      {/* v82gx : recherche fulltext */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 6, alignItems: 'center' }}>
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="🔎 chercher dans les prompts…"
          style={{
            flex: 1, padding: '4px 8px', fontSize: 11,
            background: 'var(--bg-card, rgba(255,255,255,0.04))',
            color: 'var(--fg, #f5f5f5)',
            border: '1px solid var(--line, rgba(255,255,255,0.18))',
            borderRadius: 3,
            fontFamily: 'var(--font-mono, monospace)', outline: 'none',
          }} />
        {search && (
          <button type="button" onClick={() => setSearch('')}
            title="Effacer le filtre"
            style={{
              padding: '3px 8px', fontSize: 10,
              background: 'transparent',
              border: '1px solid var(--line, rgba(255,255,255,0.18))',
              color: 'var(--fg-mute, #888)', borderRadius: 3,
              cursor: 'pointer', fontFamily: 'var(--font-mono, monospace)',
            }}>×</button>
        )}
        <span style={{
          fontSize: 9, color: 'var(--fg-mute, #777)',
          fontFamily: 'var(--font-mono, monospace)',
          fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap',
        }}>{filtered.length} / {byModule.length}</span>
      </div>
      {filtered.length === 0 ? (
        <div className="sp-hint">Aucun prompt en historique pour ce filtre.</div>
      ) : (
        <>
          <div style={{
            maxHeight: 220, overflowY: 'auto',
            border: '1px solid var(--line-soft, rgba(255,255,255,0.08))',
            borderRadius: 4, padding: 4,
            display: 'flex', flexDirection: 'column', gap: 2,
          }}>
            {filtered.map((r) => {
              const rowKey = `${r.module}::${r.prompt}`
              const isCopied = copiedKey === rowKey
              return (
              <div key={rowKey} style={{
                display: 'grid', gridTemplateColumns: '52px 1fr 44px 22px 22px',
                gap: 6, alignItems: 'center', padding: '3px 6px',
                fontSize: 11, fontFamily: 'var(--font-mono, monospace)',
              }}>
                <span style={{
                  color: 'var(--fg-mute, #888)',
                  textTransform: 'uppercase', fontSize: 9,
                  letterSpacing: '0.1em',
                }}>{MODULE_LABELS[r.module as HistoryModule] ?? r.module}</span>
                {/* v82gw : click prompt → switch module + setDraft */}
                {/* v82gz : highlight match search */}
                <button type="button"
                  onClick={() => recallTo(r.module as HistoryModule, r.prompt)}
                  title={`${r.prompt}\nClic = ouvrir ${MODULE_LABELS[r.module as HistoryModule]} avec ce prompt`}
                  style={{
                    background: 'transparent', border: 'none', padding: 0,
                    color: 'var(--fg, #f5f5f5)', cursor: 'pointer', textAlign: 'left',
                    fontFamily: 'inherit', fontSize: 'inherit',
                    whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                  }}>{q ? highlightMatch(r.prompt, q) : r.prompt}</button>
                <span style={{
                  color: 'var(--fg-mute, #888)', fontSize: 9,
                  fontVariantNumeric: 'tabular-nums', textAlign: 'right',
                }}>{fmtTs(r.ts)}</span>
                {/* v82gv : copy clipboard avec feedback ✓ */}
                <button type="button"
                  onClick={() => copyToClipboard(rowKey, r.prompt)}
                  title="Copier le prompt"
                  style={{
                    width: 22, height: 22,
                    border: '1px solid var(--line, rgba(255,255,255,0.18))',
                    background: isCopied ? 'oklch(0.70 0.13 145 / 0.20)' : 'transparent',
                    cursor: 'pointer',
                    color: isCopied ? 'oklch(0.78 0.16 145)' : 'var(--fg-mute, #888)',
                    borderRadius: 3, fontSize: 10, padding: 0,
                    transition: 'background .15s ease, color .15s ease',
                  }}>{isCopied ? '✓' : '⎘'}</button>
                <button type="button"
                  onClick={() => {
                    removeHistoryEntry(r.module, r.prompt)
                    setTick((t) => t + 1)
                  }}
                  title="Retirer cet item"
                  style={{
                    width: 22, height: 22,
                    border: '1px solid var(--line, rgba(255,255,255,0.18))',
                    background: 'transparent', cursor: 'pointer',
                    color: 'var(--fg-mute, #888)', borderRadius: 3,
                    fontSize: 11, padding: 0,
                  }}>×</button>
              </div>
              )
            })}
          </div>
          <div style={{ display: 'flex', gap: 6, marginTop: 6, flexWrap: 'wrap' }}>
            <button type="button" className="sp-btn"
              style={{ width: 'auto', marginTop: 0 }}
              onClick={() => {
                if (!window.confirm(
                  filter === 'all'
                    ? `Vider l'historique de tous les modules ? (${all.length} prompts perdus)`
                    : `Vider l'historique du module "${MODULE_LABELS[filter as HistoryModule]}" ? (${counts[filter]} prompts perdus)`,
                )) return
                if (filter === 'all') for (const m of HISTORY_MODULES) clearHistory(m)
                else clearHistory(filter)
                setTick((t) => t + 1)
              }}>
              ↺ {filter === 'all' ? 'Tout vider' : `Vider ${MODULE_LABELS[filter as HistoryModule]}`}
            </button>
            {/* v82gy : export CSV de la sélection courante (filtered) */}
            <button type="button" className="sp-btn"
              style={{ width: 'auto', marginTop: 0 }}
              disabled={filtered.length === 0}
              onClick={() => {
                if (filtered.length === 0) return
                try {
                  // CSV escape : quote + double-up internal quotes.
                  const esc = (v: string) => `"${v.replace(/"/g, '""')}"`
                  const lines: string[] = ['module,prompt,timestamp_iso,timestamp_unix']
                  for (const r of filtered) {
                    const iso = new Date(r.ts).toISOString()
                    lines.push([
                      esc(r.module),
                      esc(r.prompt),
                      esc(iso),
                      String(r.ts),
                    ].join(','))
                  }
                  const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' })
                  const url = URL.createObjectURL(blob)
                  const a = document.createElement('a')
                  a.href = url
                  const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
                  const scope = filter === 'all' ? 'all' : filter
                  a.download = `aurora-history-${scope}-${stamp}.csv`
                  a.click()
                  setTimeout(() => URL.revokeObjectURL(url), 1000)
                } catch (err) {
                  window.alert('Export CSV échoué : ' + (err as Error).message)
                }
              }}>
              📊 Exporter CSV ({filtered.length})
            </button>
          </div>
        </>
      )}
      <div className="sp-hint" style={{ marginTop: 4 }}>
        Agrège les 5 modules génératifs. Cap 12 par module · LRU sur succès.
      </div>
    </div>
  )
}

// v82h2 : status live des services backend (Bridge Flask / Ollama / ComfyUI)
//   avec auto-polling 10s. Dot vert/orange/rouge + latence ms.
type ServiceStatus = { ok: boolean | null; ms: number | null; status: number | null }
const SERVICES = [
  { id: 'bridge', label: 'Bridge', path: '/api/agents/list' },
  { id: 'ollama', label: 'Ollama', path: '/proxy/ollama/api/tags' },
  { id: 'comfy', label: 'ComfyUI', path: '/proxy/comfy/system_stats' },
] as const

function ServicesLiveStatus() {
  const [statuses, setStatuses] = useState<Record<string, ServiceStatus>>({
    bridge: { ok: null, ms: null, status: null },
    ollama: { ok: null, ms: null, status: null },
    comfy: { ok: null, ms: null, status: null },
  })
  const [lastTick, setLastTick] = useState<number | null>(null)
  // v82h3 : sparkline 12 derniers ticks par service.
  const SPARK_MAX = 12
  const [sparks, setSparks] = useState<Record<string, Array<{ ms: number | null; ok: boolean }>>>({
    bridge: [], ollama: [], comfy: [],
  })

  useEffect(() => {
    let mounted = true
    let timer: number | null = null

    const probe = async () => {
      try {
        const { getBridgeUrl } = await import('../utils/runtime')
        const base = getBridgeUrl()
        const results = await Promise.all(SERVICES.map(async ({ id, path }) => {
          const t0 = performance.now()
          try {
            const res = await fetch(`${base}${path}`, {
              signal: AbortSignal.timeout(4000),
              cache: 'no-store',
            })
            return { id, ok: res.ok, ms: Math.round(performance.now() - t0), status: res.status }
          } catch {
            return { id, ok: false, ms: Math.round(performance.now() - t0), status: 0 }
          }
        }))
        if (!mounted) return
        const next: Record<string, ServiceStatus> = {}
        for (const r of results) next[r.id] = { ok: r.ok, ms: r.ms, status: r.status }
        setStatuses(next)
        setLastTick(Date.now())
        // v82h3 : append au sparkline ring buffer (cap SPARK_MAX).
        setSparks((prev) => {
          const out: typeof prev = { ...prev }
          for (const r of results) {
            const cur = prev[r.id] ?? []
            out[r.id] = [...cur, { ms: r.ok ? r.ms : null, ok: r.ok }].slice(-SPARK_MAX)
          }
          return out
        })
      } catch { /* ignore */ }
    }

    probe()
    timer = window.setInterval(probe, 10000)
    return () => {
      mounted = false
      if (timer !== null) window.clearInterval(timer)
    }
  }, [])

  const dotColor = (s: ServiceStatus) => {
    if (s.ok === null) return 'oklch(0.55 0.02 250)'
    if (!s.ok) return 'oklch(0.62 0.20 25)'
    if (s.ms !== null && s.ms > 1500) return 'oklch(0.78 0.16 80)'
    return 'oklch(0.70 0.15 145)'
  }
  const fmtMs = (ms: number | null) => ms === null ? '—' : `${ms}ms`
  const sinceTick = lastTick === null ? '—' : `${Math.round((Date.now() - lastTick) / 1000)}s`

  return (
    <div className="sp-sec">
      <label className="sp-label">Statut services (live)</label>
      <div style={{
        display: 'flex', flexDirection: 'column', gap: 4,
        padding: 6, borderRadius: 4,
        background: 'var(--bg-card, rgba(255,255,255,0.03))',
        border: '1px solid var(--line-soft, rgba(255,255,255,0.06))',
      }}>
        {SERVICES.map(({ id, label }) => {
          const s = statuses[id]
          const spark = sparks[id] ?? []
          // v82h3 : sparkline col — 12 cells flex, height 14px,
          //   bar height = (ms / max) * 14, color OK=vert / down=rouge.
          const sparkMax = Math.max(50, ...spark.map((p) => p.ms ?? 0))
          return (
            <div key={id} style={{
              display: 'grid', gridTemplateColumns: '12px 1fr 78px auto auto',
              gap: 8, alignItems: 'center', fontSize: 11,
              fontFamily: 'var(--font-mono, monospace)',
            }}>
              <span style={{
                display: 'inline-block', width: 8, height: 8,
                borderRadius: '50%', background: dotColor(s),
                boxShadow: s.ok ? `0 0 6px ${dotColor(s)}` : 'none',
                transition: 'background .3s ease, box-shadow .3s ease',
              }} />
              <span style={{ color: 'var(--fg, #f5f5f5)' }}>{label}</span>
              {/* v82h3 : sparkline 12 cells */}
              <div style={{
                display: 'flex', alignItems: 'flex-end', gap: 1,
                height: 14, width: 78,
              }} title={`${spark.length}/${SPARK_MAX} ticks · max ${Math.round(sparkMax)}ms`}>
                {Array.from({ length: SPARK_MAX }).map((_, i) => {
                  const idx = spark.length - SPARK_MAX + i
                  const p = idx >= 0 ? spark[idx] : null
                  const h = p && p.ms !== null ? Math.max(1, (p.ms / sparkMax) * 14) : (p && !p.ok ? 14 : 1)
                  const c = !p ? 'var(--line-soft, rgba(255,255,255,0.05))'
                    : p.ok ? (p.ms !== null && p.ms > 1500 ? 'oklch(0.78 0.16 80)' : 'oklch(0.70 0.13 145)')
                    : 'oklch(0.62 0.20 25)'
                  return (
                    <span key={i} style={{
                      flex: 1, height: h, background: c,
                      borderRadius: 1, opacity: p ? 1 : 0.4,
                      transition: 'height .25s ease, background .25s ease',
                    }} />
                  )
                })}
              </div>
              <span style={{
                color: 'var(--fg-mute, #888)',
                fontVariantNumeric: 'tabular-nums', fontSize: 10,
              }}>{fmtMs(s.ms)}</span>
              <span style={{
                color: s.ok ? 'oklch(0.78 0.10 145)' :
                  s.ok === false ? 'oklch(0.78 0.18 25)' : 'var(--fg-mute, #888)',
                fontSize: 10,
              }}>{s.ok === null ? '…' : s.ok ? 'OK' : (s.status === 0 ? 'KO' : `HTTP ${s.status}`)}</span>
            </div>
          )
        })}
      </div>
      <div className="sp-hint" style={{ marginTop: 4 }}>
        Auto-poll 10s · timeout 4s par service · vert = OK rapide, jaune = lent (&gt;1.5s), rouge = down. Dernier check il y a {sinceTick}.
      </div>
    </div>
  )
}

// v82ha : panneau ressources navigateur — heap JS via performance.memory
//   (Chromium only, fallback gracieux) + storage quota via
//   navigator.storage.estimate(). Polling 5s.
type BrowserResources = {
  heapUsed: number | null
  heapTotal: number | null
  heapLimit: number | null
  storageUsed: number | null
  storageQuota: number | null
}

interface PerformanceMemoryShim {
  usedJSHeapSize: number
  totalJSHeapSize: number
  jsHeapSizeLimit: number
}

function BrowserResourcesPanel() {
  const [res, setRes] = useState<BrowserResources>({
    heapUsed: null, heapTotal: null, heapLimit: null,
    storageUsed: null, storageQuota: null,
  })

  useEffect(() => {
    let mounted = true
    let timer: number | null = null

    const probe = async () => {
      const next: BrowserResources = {
        heapUsed: null, heapTotal: null, heapLimit: null,
        storageUsed: null, storageQuota: null,
      }
      // performance.memory non standard — Chromium only.
      try {
        const mem = (performance as unknown as { memory?: PerformanceMemoryShim }).memory
        if (mem && typeof mem.usedJSHeapSize === 'number') {
          next.heapUsed = mem.usedJSHeapSize
          next.heapTotal = mem.totalJSHeapSize
          next.heapLimit = mem.jsHeapSizeLimit
        }
      } catch { /* ignore */ }
      // storage estimate — Standard sur Chrome/FF/Safari modernes.
      try {
        if (navigator.storage && navigator.storage.estimate) {
          const est = await navigator.storage.estimate()
          next.storageUsed = est.usage ?? null
          next.storageQuota = est.quota ?? null
        }
      } catch { /* ignore */ }
      if (mounted) setRes(next)
    }
    probe()
    timer = window.setInterval(probe, 5000)
    return () => {
      mounted = false
      if (timer !== null) window.clearInterval(timer)
    }
  }, [])

  const fmt = (b: number | null) => {
    if (b === null) return '—'
    if (b < 1024) return `${b} B`
    if (b < 1024 * 1024) return `${(b / 1024).toFixed(0)} kB`
    if (b < 1024 * 1024 * 1024) return `${(b / 1024 / 1024).toFixed(1)} MB`
    return `${(b / 1024 / 1024 / 1024).toFixed(2)} GB`
  }
  const pct = (a: number | null, b: number | null) =>
    a === null || b === null || b === 0 ? null : (a / b) * 100

  const heapPct = pct(res.heapUsed, res.heapLimit)
  const storagePct = pct(res.storageUsed, res.storageQuota)
  const heapAvail = (performance as unknown as { memory?: PerformanceMemoryShim }).memory !== undefined

  return (
    <div className="sp-sec">
      <label className="sp-label">Ressources navigateur</label>
      <div style={{
        display: 'flex', flexDirection: 'column', gap: 6,
        padding: 6, borderRadius: 4,
        background: 'var(--bg-card, rgba(255,255,255,0.03))',
        border: '1px solid var(--line-soft, rgba(255,255,255,0.06))',
        fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
      }}>
        {/* Heap JS */}
        {heapAvail ? (
          <div>
            <div style={{
              display: 'flex', justifyContent: 'space-between',
              fontSize: 10, color: 'var(--fg-mute, #999)',
            }}>
              <span>Heap JS</span>
              <span style={{ fontVariantNumeric: 'tabular-nums' }}>
                {fmt(res.heapUsed)} / {fmt(res.heapLimit)}
                {heapPct !== null && ` · ${heapPct.toFixed(1)}%`}
              </span>
            </div>
            <div style={{
              height: 4, marginTop: 4, borderRadius: 2,
              background: 'var(--line-soft, rgba(255,255,255,0.08))',
              overflow: 'hidden',
            }}>
              <div style={{
                width: `${heapPct ?? 0}%`, height: '100%',
                background: heapPct && heapPct > 80
                  ? 'oklch(0.62 0.20 25)'
                  : heapPct && heapPct > 50
                  ? 'oklch(0.78 0.16 80)'
                  : 'oklch(0.70 0.13 145)',
                transition: 'width .25s ease, background .25s ease',
              }} />
            </div>
          </div>
        ) : (
          <div style={{ fontSize: 10, color: 'var(--fg-mute, #777)' }}>
            Heap JS · indisponible (browser non-Chromium)
          </div>
        )}
        {/* Storage quota (IDB + localStorage + caches) */}
        {res.storageQuota !== null ? (
          <div>
            <div style={{
              display: 'flex', justifyContent: 'space-between',
              fontSize: 10, color: 'var(--fg-mute, #999)',
            }}>
              <span>Storage (IDB + LS + caches)</span>
              <span style={{ fontVariantNumeric: 'tabular-nums' }}>
                {fmt(res.storageUsed)} / {fmt(res.storageQuota)}
                {storagePct !== null && ` · ${storagePct.toFixed(2)}%`}
              </span>
            </div>
            <div style={{
              height: 4, marginTop: 4, borderRadius: 2,
              background: 'var(--line-soft, rgba(255,255,255,0.08))',
              overflow: 'hidden',
            }}>
              <div style={{
                width: `${Math.min(100, storagePct ?? 0)}%`, height: '100%',
                background: 'oklch(0.70 0.13 200)',
                transition: 'width .25s ease',
              }} />
            </div>
          </div>
        ) : (
          <div style={{ fontSize: 10, color: 'var(--fg-mute, #777)' }}>
            Storage quota · indisponible (navigator.storage)
          </div>
        )}
      </div>
      <div className="sp-hint" style={{ marginTop: 4 }}>
        Auto-poll 5s. Heap JS = mémoire Aurora dans cet onglet (Chromium only). Storage = total IDB + localStorage + service-worker caches.
      </div>
    </div>
  )
}

// v82hd : panneau favoris cross-module — browse les prompts sauvés
//   via FavoriteButton (v82hb-c), filter par module, recall via switch+
//   setDraft, supprimer par item.
const FAV_MODULES: Array<{ id: HistoryModule | 'all'; label: string }> = [
  { id: 'all', label: 'Tous' },
  { id: 'image', label: 'Image' },
  { id: 'code', label: 'Code' },
  { id: 'drawing', label: 'Dessin' },
  { id: 'video', label: 'Vidéo' },
  { id: '3d', label: '3D' },
]

function FavoritesPanel() {
  const { prompts, deletePrompt, incrementUseCount } = usePromptLibraryStore()
  const [filter, setFilter] = useState<HistoryModule | 'all'>('all')
  const [search, setSearch] = useState('')
  const setActiveModule = useAppStore((s) => s.setActiveModule)
  const setDraft = useModuleDraftsStore((s) => s.setDraft)

  const byModule = filter === 'all'
    ? prompts.filter((p) => HISTORY_MODULES.includes(p.module as HistoryModule))
    : prompts.filter((p) => p.module === filter)
  const q = search.trim().toLowerCase()
  const filtered = q
    ? byModule.filter((p) =>
        p.prompt.toLowerCase().includes(q)
        || (p.tags ?? []).some((t) => t.toLowerCase().includes(q)),
      )
    : byModule
  // Tri desc par useCount puis par savedAt récent.
  const sorted = [...filtered].sort((a, b) => {
    if (b.useCount !== a.useCount) return b.useCount - a.useCount
    return b.savedAt - a.savedAt
  })

  const counts: Record<HistoryModule | 'all', number> = {
    all: 0, image: 0, code: 0, drawing: 0, video: 0, '3d': 0,
  }
  for (const p of prompts) {
    if (HISTORY_MODULES.includes(p.module as HistoryModule)) {
      counts[p.module as HistoryModule]++
      counts.all++
    }
  }

  const recallTo = (m: HistoryModule, prompt: string, id: string) => {
    incrementUseCount(id)
    setDraft(m as 'image' | 'code' | 'drawing' | 'video' | '3d', { prompt })
    setActiveModule(m as 'image' | 'code' | 'drawing' | 'video' | '3d')
  }

  return (
    <div className="sp-sec">
      <label className="sp-label">★ Mes prompts favoris</label>
      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 6 }}>
        {FAV_MODULES.map(({ id, label }) => (
          <button key={id} type="button"
            onClick={() => setFilter(id)}
            style={{
              padding: '3px 8px', fontSize: 10,
              fontFamily: 'var(--font-mono, monospace)',
              border: filter === id
                ? '1px solid oklch(0.78 0.16 80)'
                : '1px solid var(--line, rgba(255,255,255,0.12))',
              background: filter === id
                ? 'oklch(0.78 0.16 80 / 0.12)'
                : 'transparent',
              color: filter === id ? 'oklch(0.78 0.16 80)' : 'var(--fg-mute, #888)',
              borderRadius: 3, cursor: 'pointer',
            }}>
            {label} ({counts[id]})
          </button>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 6, marginBottom: 6, alignItems: 'center' }}>
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="🔎 chercher dans les favoris…"
          style={{
            flex: 1, padding: '4px 8px', fontSize: 11,
            background: 'var(--bg-card, rgba(255,255,255,0.04))',
            color: 'var(--fg, #f5f5f5)',
            border: '1px solid var(--line, rgba(255,255,255,0.18))',
            borderRadius: 3,
            fontFamily: 'var(--font-mono, monospace)', outline: 'none',
          }} />
        <span style={{
          fontSize: 9, color: 'var(--fg-mute, #777)',
          fontFamily: 'var(--font-mono, monospace)',
          fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap',
        }}>{sorted.length} / {byModule.length}</span>
      </div>
      {sorted.length === 0 ? (
        <div className="sp-hint">Aucun favori. Clique ★ favori dans une vue module pour en créer.</div>
      ) : (
        <div style={{
          maxHeight: 260, overflowY: 'auto',
          border: '1px solid var(--line-soft, rgba(255,255,255,0.08))',
          borderRadius: 4, padding: 4,
          display: 'flex', flexDirection: 'column', gap: 2,
        }}>
          {sorted.map((p) => (
            <div key={p.id} style={{
              display: 'grid', gridTemplateColumns: '52px 1fr 36px 22px',
              gap: 6, alignItems: 'center', padding: '3px 6px',
              fontSize: 11, fontFamily: 'var(--font-mono, monospace)',
            }}>
              <span style={{
                color: 'var(--fg-mute, #888)',
                textTransform: 'uppercase', fontSize: 9,
                letterSpacing: '0.1em',
              }}>{MODULE_LABELS[p.module as HistoryModule] ?? p.module}</span>
              <button type="button"
                onClick={() => recallTo(p.module as HistoryModule, p.prompt, p.id)}
                title={`${p.prompt}${p.tags?.length ? `\n[${p.tags.join(', ')}]` : ''}\nClic = ouvrir avec ce prompt`}
                style={{
                  background: 'transparent', border: 'none', padding: 0,
                  color: 'var(--fg, #f5f5f5)', cursor: 'pointer', textAlign: 'left',
                  fontFamily: 'inherit', fontSize: 'inherit',
                  whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                }}>{q ? highlightMatch(p.prompt, q) : p.prompt}</button>
              <span style={{
                color: 'var(--fg-mute, #888)', fontSize: 9,
                fontVariantNumeric: 'tabular-nums', textAlign: 'right',
              }} title="Nombre d'utilisations (recall)">{p.useCount}×</span>
              <button type="button"
                onClick={() => {
                  if (window.confirm(`Supprimer ce favori ?\n${p.prompt.slice(0, 80)}…`)) {
                    deletePrompt(p.id)
                  }
                }}
                title="Supprimer ce favori"
                style={{
                  width: 22, height: 22,
                  border: '1px solid var(--line, rgba(255,255,255,0.18))',
                  background: 'transparent', cursor: 'pointer',
                  color: 'var(--fg-mute, #888)', borderRadius: 3,
                  fontSize: 11, padding: 0,
                }}>×</button>
            </div>
          ))}
        </div>
      )}
      <div className="sp-hint" style={{ marginTop: 4 }}>
        Triés par usage décroissant puis date. Clic sur un prompt → ouvre le module et y injecte le draft (incrémente useCount).
      </div>
      {/* v82ig + v82ih : export / import JSON library favoris */}
      <div style={{ display: 'flex', gap: 6, marginTop: 6, flexWrap: 'wrap' }}>
        <button type="button" className="sp-btn"
          style={{ width: 'auto', marginTop: 0 }}
          disabled={prompts.length === 0}
          onClick={() => {
            try {
              const payload = {
                schema: 'aurora.favorites.v1',
                exportedAt: new Date().toISOString(),
                count: prompts.length,
                prompts,
              }
              const blob = new Blob([JSON.stringify(payload, null, 2)],
                { type: 'application/json' })
              const url = URL.createObjectURL(blob)
              const a = document.createElement('a')
              a.href = url
              const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
              a.download = `aurora-favorites-${stamp}.json`
              a.click()
              setTimeout(() => URL.revokeObjectURL(url), 1000)
            } catch (err) {
              window.alert('Export favoris échoué : ' + (err as Error).message)
            }
          }}>
          💾 Exporter favoris JSON ({prompts.length})
        </button>
        <button type="button" className="sp-btn"
          style={{ width: 'auto', marginTop: 0 }}
          onClick={() => {
            const input = document.createElement('input')
            input.type = 'file'
            input.accept = '.json,application/json'
            input.onchange = async () => {
              const file = input.files?.[0]
              if (!file) return
              try {
                const text = await file.text()
                const parsed = JSON.parse(text)
                if (parsed?.schema !== 'aurora.favorites.v1') {
                  window.alert('Schéma invalide : attendu aurora.favorites.v1')
                  return
                }
                const incoming = parsed.prompts
                if (!Array.isArray(incoming)) {
                  window.alert('Données absentes ou corrompues.')
                  return
                }
                const valid = incoming.filter((p: unknown): p is { module: string; prompt: string; tags?: string[]; parameters?: Record<string, unknown>; fidelityScore?: number; useCount?: number } =>
                  typeof p === 'object' && p !== null
                  && typeof (p as { module: unknown }).module === 'string'
                  && typeof (p as { prompt: unknown }).prompt === 'string',
                )
                if (valid.length === 0) {
                  window.alert('Aucun favori valide dans le fichier.')
                  return
                }
                // Dédupe : skip si (module, prompt) existe déjà.
                const existingKeys = new Set(prompts.map((p) => `${p.module}::${p.prompt}`))
                const newOnes = valid.filter((p) => !existingKeys.has(`${p.module}::${p.prompt}`))
                if (newOnes.length === 0) {
                  window.alert(`${valid.length} favori(s) trouvés mais tous déjà présents.`)
                  return
                }
                if (!window.confirm(
                  `Importer ${newOnes.length} nouveau(x) favori(s) ?\n\n`
                  + `(${valid.length - newOnes.length} doublon(s) ignoré(s))`,
                )) return
                const { addPrompt } = usePromptLibraryStore.getState()
                for (const p of newOnes) {
                  addPrompt({
                    module: p.module as 'image' | 'code' | 'drawing' | 'video' | '3d' | 'conversation' | 'voice' | 'cyber' | 'learning',
                    prompt: p.prompt,
                    fidelityScore: typeof p.fidelityScore === 'number' ? p.fidelityScore : 90,
                    parameters: p.parameters ?? {},
                    tags: Array.isArray(p.tags) ? p.tags : [p.module],
                  })
                }
                window.alert(`✓ ${newOnes.length} favori(s) importé(s).`)
              } catch (err) {
                window.alert('Import favoris échoué : ' + (err as Error).message)
              }
            }
            input.click()
          }}>
          📥 Importer favoris JSON
        </button>
      </div>
    </div>
  )
}

// v82hi : panneau historique transitions services (UP/DOWN events)
//   logguées par ConnectionIndicator. Read-only, clear all bouton.
function ServiceTransitionsPanel() {
  const [tick, setTick] = useState(0)
  const items = readTransitions()
  void tick

  const fmtTs = (ts: number): string => {
    const d = new Date(ts)
    const today = new Date().toDateString()
    const time = d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    return d.toDateString() === today
      ? time
      : `${d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' })} ${time}`
  }

  return (
    <div className="sp-sec">
      <label className="sp-label">Historique transitions services</label>
      {items.length === 0 ? (
        <div className="sp-hint">Aucune transition enregistrée. Les changements UP↔DOWN seront loggués ici.</div>
      ) : (
        <>
          <div style={{
            maxHeight: 180, overflowY: 'auto',
            border: '1px solid var(--line-soft, rgba(255,255,255,0.08))',
            borderRadius: 4, padding: 4,
            display: 'flex', flexDirection: 'column', gap: 2,
          }}>
            {items.map((t, i) => (
              <div key={i} style={{
                display: 'grid', gridTemplateColumns: '94px 36px 1fr',
                gap: 6, alignItems: 'center', padding: '3px 6px',
                fontSize: 11, fontFamily: 'var(--font-mono, monospace)',
              }}>
                <span style={{
                  color: 'var(--fg-mute, #888)',
                  fontSize: 10, fontVariantNumeric: 'tabular-nums',
                }}>{fmtTs(t.ts)}</span>
                <span style={{
                  fontSize: 10, fontWeight: 700,
                  color: t.kind === 'up' ? 'oklch(0.78 0.16 145)' : 'oklch(0.78 0.18 25)',
                }}>{t.kind === 'up' ? '▲ UP' : '▼ DOWN'}</span>
                <span style={{
                  color: 'var(--fg, #f5f5f5)',
                  whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                  fontSize: 10,
                }}>
                  {t.kind === 'down' && t.downList && t.downList.length > 0
                    ? `services down : ${t.downList.join(', ')}`
                    : t.kind === 'up'
                    ? 'tous services rétablis'
                    : 'transition'}
                </span>
              </div>
            ))}
          </div>
          <button type="button" className="sp-btn"
            style={{ width: 'auto', marginTop: 6 }}
            onClick={() => {
              if (!window.confirm(`Vider l'historique des transitions ? (${items.length} entrées perdues)`)) return
              clearTransitions()
              setTick((t) => t + 1)
            }}>
            ↺ Vider l'historique
          </button>
        </>
      )}
      <div className="sp-hint" style={{ marginTop: 4 }}>
        Cap 30 entrées · ring-buffer · log écrit par ConnectionIndicator quand un service passe down ou que tous se rétablissent.
      </div>
    </div>
  )
}

// v82ic : panneau "Mes streaks" agrégé — 7 modules génératifs/educational.
//   Image, Drawing, Code, Video, 3D via useModuleStreak.
//   Cyber, Academy via leur leaderboard store + computeStreak direct.
function StreaksPanel() {
  // Modules backed by moduleHistoryStore.
  const imageStreak = useModuleStreak('image')
  const drawingStreak = useModuleStreak('drawing')
  const codeStreak = useModuleStreak('code')
  const videoStreak = useModuleStreak('video')
  const threeDStreak = useModuleStreak('3d')
  // Modules backed by leaderboard store (timestamps from runs).
  const cyberRuns = useCyberLeaderboardStore((s) => s.runs)
  const academyRuns = useAcademyLeaderboardStore((s) => s.runs)
  const cyberStreak = useMemo(
    () => computeStreak(cyberRuns.map((r) => r.endedAt || r.startedAt)),
    [cyberRuns],
  )
  const academyStreak = useMemo(
    () => computeStreak(academyRuns.map((r) => r.endedAt || r.startedAt)),
    [academyRuns],
  )

  const rows: Array<{ id: string; label: string; current: number; longest: number }> = [
    { id: 'image', label: 'Image', current: imageStreak.current, longest: imageStreak.longest },
    { id: 'drawing', label: 'Dessin', current: drawingStreak.current, longest: drawingStreak.longest },
    { id: 'code', label: 'Code', current: codeStreak.current, longest: codeStreak.longest },
    { id: 'video', label: 'Vidéo', current: videoStreak.current, longest: videoStreak.longest },
    { id: '3d', label: '3D', current: threeDStreak.current, longest: threeDStreak.longest },
    { id: 'cyber', label: 'Cyber', current: cyberStreak.current, longest: cyberStreak.longest },
    { id: 'academy', label: 'Académie', current: academyStreak.current, longest: academyStreak.longest },
  ]
  // Tri desc par current.
  const sorted = [...rows].sort((a, b) => b.current - a.current || b.longest - a.longest)
  const totalCurrent = rows.reduce((s, r) => s + r.current, 0)
  const bestModule = rows.reduce((best, r) => r.longest > best.longest ? r : best, rows[0])

  return (
    <div className="sp-sec">
      <label className="sp-label">🔥 Mes streaks</label>
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        fontSize: 11, fontFamily: 'var(--font-mono, monospace)',
        color: 'var(--fg-mute, #999)', marginBottom: 6,
      }}>
        <span>Total actuel : {totalCurrent}j cumulés</span>
        {bestModule.longest > 0 && (
          <span title="Module avec le plus long streak all-time">🏆 {bestModule.label} {bestModule.longest}j</span>
        )}
      </div>
      <div style={{
        display: 'flex', flexDirection: 'column', gap: 2,
        padding: 4, borderRadius: 4,
        background: 'var(--bg-card, rgba(255,255,255,0.03))',
        border: '1px solid var(--line-soft, rgba(255,255,255,0.06))',
      }}>
        {sorted.map((r) => {
          const isHot = r.current >= 7
          const isRecord = r.current > 0 && r.current === r.longest
          return (
            <div key={r.id} style={{
              display: 'grid', gridTemplateColumns: '70px 1fr 60px',
              gap: 8, alignItems: 'center', padding: '3px 6px',
              fontSize: 11, fontFamily: 'var(--font-mono, monospace)',
            }}>
              <span style={{
                color: 'var(--fg, #f5f5f5)',
                opacity: r.current > 0 ? 1 : 0.5,
              }}>{r.label}</span>
              {/* Mini bar gauge — width proportional au longest. */}
              <div style={{
                height: 4, borderRadius: 2,
                background: 'var(--line-soft, rgba(255,255,255,0.08))',
                overflow: 'hidden', position: 'relative',
              }}>
                <div style={{
                  width: r.longest > 0 ? `${Math.min(100, (r.current / Math.max(7, r.longest)) * 100)}%` : '0%',
                  height: '100%',
                  background: isHot ? 'oklch(0.78 0.16 80)' : 'oklch(0.70 0.13 145)',
                  transition: 'width .25s ease',
                }} />
              </div>
              <span style={{
                fontVariantNumeric: 'tabular-nums', textAlign: 'right',
                color: isHot ? 'oklch(0.78 0.16 80)' : 'var(--fg-mute, #888)',
              }}>
                {r.current}j{isRecord && r.current >= 7 ? ' 🏆' : r.longest > r.current ? `/${r.longest}` : ''}
              </span>
            </div>
          )
        })}
      </div>
      <div className="sp-hint" style={{ marginTop: 4 }}>
        Streak = jours consécutifs avec au moins une activité dans le module. 🏆 si current = record et ≥ 7j.
      </div>
      {/* v82id : export CSV des streaks pour archive / partage */}
      <button type="button" className="sp-btn"
        style={{ width: 'auto', marginTop: 6 }}
        disabled={totalCurrent === 0 && bestModule.longest === 0}
        onClick={() => {
          try {
            const esc = (v: string) => `"${v.replace(/"/g, '""')}"`
            const lines: string[] = ['module,current_streak_days,longest_streak_days']
            for (const r of rows) {
              lines.push([esc(r.label), String(r.current), String(r.longest)].join(','))
            }
            const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' })
            const url = URL.createObjectURL(blob)
            const a = document.createElement('a')
            a.href = url
            const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
            a.download = `aurora-streaks-${stamp}.csv`
            a.click()
            setTimeout(() => URL.revokeObjectURL(url), 1000)
          } catch (err) {
            window.alert('Export CSV échoué : ' + (err as Error).message)
          }
        }}>
        📊 Exporter streaks CSV
      </button>
    </div>
  )
}

// v82jb / v82jn : panneau status Aurora-Connect (Chrome extension).
//   v82jn : utilise /api/cowork/extension/status enrichi avec
//   active vs persisted distinction. L'extension reste "connue" 24h
//   même si elle ne poll plus l'instant — utile pour distinguer
//   "jamais installée" vs "installée mais offline temporairement".
//   Polling 15s (plus serré que 30s) pour reactivity.
type ExtStatus = {
  active: Array<{ extId: string; lastSeenAgoMs: number }>
  persisted: Array<{ extId: string; lastSeenAgoMs: number }>
  totalKnown: number
}

function ExtensionStatusPanel() {
  const [status, setStatus] = useState<ExtStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    let mounted = true
    let timer: number | null = null
    const probe = async () => {
      try {
        const { getBridgeUrl } = await import('../utils/runtime')
        const res = await fetch(`${getBridgeUrl()}/api/cowork/extension/status`, {
          signal: AbortSignal.timeout(3500),
          cache: 'no-store',
        })
        if (!res.ok) {
          if (mounted) {
            setStatus({ active: [], persisted: [], totalKnown: 0 })
            setError(`HTTP ${res.status}`)
          }
          return
        }
        const data = await res.json() as ExtStatus
        if (mounted) {
          setStatus(data)
          setError(null)
        }
      } catch (err) {
        if (mounted) {
          setStatus({ active: [], persisted: [], totalKnown: 0 })
          setError(err instanceof Error ? err.message.slice(0, 60) : 'fail')
        }
      }
    }
    probe()
    timer = window.setInterval(probe, 15000)
    return () => {
      mounted = false
      if (timer !== null) window.clearInterval(timer)
    }
  }, [tick])

  const activeCount = status?.active.length ?? 0
  const persistedCount = status?.persisted.length ?? 0
  const dotColor = !status ? 'oklch(0.55 0.02 250)'
    : activeCount > 0 ? 'oklch(0.70 0.15 145)'
    : persistedCount > 0 ? 'oklch(0.78 0.16 80)'
    : 'oklch(0.65 0.13 60)'

  const fmtAge = (ms: number): string => {
    if (ms < 60_000) return `il y a ${Math.floor(ms / 1000)}s`
    if (ms < 3_600_000) return `il y a ${Math.floor(ms / 60_000)}min`
    if (ms < 86_400_000) return `il y a ${Math.floor(ms / 3_600_000)}h`
    return `il y a ${Math.floor(ms / 86_400_000)}j`
  }

  return (
    <div className="sp-sec">
      <label className="sp-label">Aurora-Connect</label>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '6px 8px', borderRadius: 4,
        background: 'var(--bg-card, rgba(255,255,255,0.03))',
        border: '1px solid var(--line-soft, rgba(255,255,255,0.06))',
        fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
      }}>
        <span style={{
          display: 'inline-block', width: 8, height: 8,
          borderRadius: '50%', background: dotColor,
          boxShadow: activeCount > 0 ? `0 0 6px ${dotColor}` : 'none',
        }} />
        {status === null ? (
          <span style={{ color: 'var(--fg-mute, #888)' }}>Détection…</span>
        ) : activeCount > 0 ? (
          <span style={{ color: 'var(--fg, #f5f5f5)' }}>
            ✓ {activeCount} onglet{activeCount > 1 ? 's' : ''} actif{activeCount > 1 ? 's' : ''}
            {status.active[0] && ` · ${fmtAge(status.active[0].lastSeenAgoMs)}`}
          </span>
        ) : persistedCount > 0 ? (
          <span style={{ color: 'oklch(0.78 0.16 80)' }}>
            ⚠ {persistedCount} extension{persistedCount > 1 ? 's' : ''} connue{persistedCount > 1 ? 's' : ''}, en attente
            {status.persisted[0] && ` · ${fmtAge(status.persisted[0].lastSeenAgoMs)}`}
          </span>
        ) : (
          <span style={{ color: 'var(--fg-mute, #888)' }}>
            Extension jamais détectée{error ? ` · ${error}` : ''}
          </span>
        )}
        <span style={{ flex: 1 }} />
        <button type="button" onClick={() => setTick((t) => t + 1)}
          title="Re-tester maintenant"
          style={{
            padding: '2px 8px', fontSize: 10,
            background: 'transparent',
            border: '1px solid var(--line, rgba(255,255,255,0.18))',
            color: 'var(--fg-mute, #888)', borderRadius: 3,
            cursor: 'pointer', fontFamily: 'inherit',
          }}>↻</button>
      </div>
      <div className="sp-hint" style={{ marginTop: 4 }}>
        Aurora-Connect ouvre Cowork + reference search + active-tab read.
        {persistedCount > 0 && activeCount === 0 && (
          <> Extension installée mais inactive : ouvre un onglet pour qu'elle re-poll.</>
        )}
        {' '}Status auto 15s.
      </div>
    </div>
  )
}

// Manual school portal shortcuts for calendar/ICS setup. Pronote academic
// import lives in the dedicated panel below, so this stays clearly secondary.
type SchoolPortal = {
  id: string
  label: string
  icon: string                   // emoji or 1-2 chars
  finderUrl: (q: string) => string
  hint: string                   // ce que l'user doit faire après login
}

const SCHOOL_PORTALS: SchoolPortal[] = [
  {
    id: 'pronote',
    label: 'Pronote',
    icon: '📘',
    // Index-education n'expose pas de finder publique — Google search
    // "pronote {établissement}" est en pratique le meilleur path qui
    // mène vers le bon Pronote (chaque établissement a son sous-domaine).
    finderUrl: (q) => q
      ? `https://www.google.com/search?q=${encodeURIComponent(`pronote ${q}`)}`
      : 'https://www.index-education.com/fr/pronote.php',
    hint: 'Connecte-toi sur Pronote, puis va dans : Mon compte (en haut à droite) → Onglet "Sécurité" → "Activer la génération du lien iCal" → copie l\'URL fournie ici. C\'est l\'URL ICS, PAS la page menu.',
  },
  {
    id: 'ecoledirecte',
    label: 'ÉcoleDirecte',
    icon: '🏫',
    finderUrl: (q) => q
      ? `https://www.google.com/search?q=${encodeURIComponent(`ecoledirecte ${q}`)}`
      : 'https://www.ecoledirecte.com/',
    hint: 'Connecte-toi, va dans : Mon compte → Emploi du temps → bouton iCal en haut à droite → copie l\'URL.',
  },
  {
    id: 'skolengo',
    label: 'Skolengo',
    icon: '🎓',
    finderUrl: (q) => q
      ? `https://www.google.com/search?q=${encodeURIComponent(`skolengo ${q}`)}`
      : 'https://www.skolengo.com/',
    hint: 'Skolengo → Mon agenda → ⋮ menu → "Exporter / iCal" → URL.',
  },
  {
    id: 'idf',
    label: 'ENT Île-de-France',
    icon: '🗼',
    finderUrl: () => 'https://ent.iledefrance.fr/',
    hint: 'monlycee.net / ENT77 → Calendrier → ⚙ → "Obtenir le lien iCal".',
  },
  {
    id: 'google',
    label: 'Google Calendar',
    icon: 'G',
    finderUrl: () => 'https://calendar.google.com/',
    hint: 'Google Calendar → mon agenda → ⚙ → "Intégrer l\'agenda" → URL secrète au format iCal.',
  },
]

const SCHOOL_QUERY_KEY = 'aurora-school-finder-query-v1'

function SchoolPortalsPanel({ onPickUrl }: { onPickUrl: (url: string) => void }) {
  const desktopNative = isTauriRuntime()
  const [query, setQuery] = useState<string>(() => {
    if (typeof window === 'undefined') return ''
    try { return window.localStorage.getItem(SCHOOL_QUERY_KEY) ?? '' } catch { return '' }
  })
  const [activeHint, setActiveHint] = useState<string | null>(null)

  useEffect(() => {
    try { window.localStorage.setItem(SCHOOL_QUERY_KEY, query) } catch { /* ignore */ }
  }, [query])

  // Re-use ExtensionStatusPanel detection logic (same endpoint, lightweight here)
  const [extOk, setExtOk] = useState<boolean | null>(null)
  useEffect(() => {
    if (desktopNative) {
      setExtOk(true)
      return
    }
    let mounted = true
    const probe = async () => {
      try {
        const { getBridgeUrl } = await import('../utils/runtime')
        const res = await fetch(`${getBridgeUrl()}/api/cowork/extension/list`, {
          signal: AbortSignal.timeout(3500), cache: 'no-store',
        })
        if (!mounted) return
        if (res.ok) {
          const data = await res.json() as { extensions?: unknown[] }
          setExtOk(Array.isArray(data.extensions) && data.extensions.length > 0)
        } else setExtOk(false)
      } catch { if (mounted) setExtOk(false) }
    }
    probe()
    const t = window.setInterval(probe, 30000)
    return () => { mounted = false; window.clearInterval(t) }
  }, [desktopNative])

  const onPortalClick = (p: SchoolPortal) => {
    const q = query.trim()
    if (!q && p.finderUrl.length > 0 && /q=\$\{/.test(p.finderUrl.toString())) {
      // Le portail a un placeholder de query mais l'user n'a rien tapé.
      // On lui demande au lieu d'ouvrir une page sans contexte.
      const v = window.prompt(`Établissement + ville pour ${p.label} ?`, '')
      if (!v) return
      setQuery(v.trim())
      window.open(p.finderUrl(v.trim()), '_blank', 'noopener,noreferrer')
    } else {
      window.open(p.finderUrl(q), '_blank', 'noopener,noreferrer')
    }
    setActiveHint(p.hint)
  }

  return (
    <div className="sp-sec">
      <label className="sp-label">Portails école — agenda manuel</label>
      {!desktopNative && extOk === false && (
        <div style={{
          padding: '6px 8px', borderRadius: 4, marginBottom: 6,
          fontSize: 11, fontFamily: 'var(--font-mono, monospace)',
          background: 'oklch(0.78 0.16 80 / 0.10)',
          color: 'oklch(0.78 0.16 80)',
          border: '1px solid oklch(0.78 0.16 80 / 0.45)',
        }}>
          ⚠ Extension navigateur non détectée. Ce bloc est seulement pour ouvrir un portail et récupérer un calendrier ICS manuel.
        </div>
      )}
      <div style={{ display: 'flex', gap: 6, marginBottom: 6 }}>
        <input type="text"
          className="sp-select"
          style={{ flex: 1 }}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Recherche portail manuel (ex : Lycée Voltaire, Paris)" />
      </div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {SCHOOL_PORTALS.map((p) => (
          <button key={p.id} type="button"
            onClick={() => onPortalClick(p)}
            title={`Ouvrir ${p.label} dans un nouvel onglet · ${p.hint}`}
            style={{
              flex: '1 1 calc(50% - 3px)', minWidth: 110,
              padding: '8px 10px',
              display: 'flex', alignItems: 'center', gap: 8,
              background: 'var(--bg-card, rgba(255,255,255,0.04))',
              color: 'var(--fg, #f5f5f5)',
              border: '1px solid var(--line, rgba(255,255,255,0.18))',
              borderRadius: 6, cursor: 'pointer',
              fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
              textAlign: 'left',
              transition: 'background .15s ease, border-color .15s ease',
            }}>
            <span style={{ fontSize: 16 }}>{p.icon}</span>
            <span>{p.label}</span>
          </button>
        ))}
      </div>
      {activeHint && (
        <div className="sp-hint" style={{ marginTop: 6 }}>
          💡 {activeHint}
        </div>
      )}
      <div className="sp-hint" style={{ marginTop: 4 }}>
        Raccourci manuel pour l’agenda ICS. Pour importer les cours, devoirs, notes et fichiers, utilise le bloc Connexion école / ENT — import académique.
      </div>
    </div>
  )
}

// School account setup. The user enters school + city, chooses the matching
// portal, then provides credentials. Desktop uses a native web session;
// browser mode stores credentials in the encrypted Aurora-Connect vault.
type SchoolCandidate = {
  adapterId: string
  systemLabel: string
  name: string
  url: string
  loginUrl: string
  uai: string
  city: string
  source?: string
  score: number
}

const EDUCATION_SYSTEM_OPTIONS = [
  { id: 'auto', label: 'Auto' },
  { id: 'pronote', label: 'Pronote' },
  { id: 'ecoledirecte', label: 'ÉcoleDirecte' },
  { id: 'skolengo', label: 'Skolengo / ENT régional' },
  { id: 'ent-idf', label: 'ENT / MonLycée' },
] as const

function educationSystemLabel(adapterId: string): string {
  return EDUCATION_SYSTEM_OPTIONS.find((option) => option.id === adapterId)?.label || adapterId
}

function guessEducationAdapterId(url: string, fallback = 'pronote'): string {
  const value = url.toLowerCase()
  if (value.includes('ecoledirecte')) return 'ecoledirecte'
  if (value.includes('skolengo') || value.includes('monbureaunumerique') || value.includes('kosmos')) return 'skolengo'
  if (value.includes('monlycee') || value.includes('iledefrance') || value.includes('ent.')) return 'ent-idf'
  if (value.includes('index-education') || value.includes('pronote')) return 'pronote'
  return fallback === 'auto' ? 'pronote' : fallback
}

async function parseJsonResponse<T>(response: Response): Promise<{ data?: T; error?: string }> {
  const text = await response.text()
  if (!text.trim()) return { data: {} as T }
  try {
    return { data: JSON.parse(text) as T }
  } catch {
    const preview = text.replace(/\s+/g, ' ').slice(0, 180)
    return { error: `Réponse bridge illisible (${response.status}). ${preview || 'Aucun détail.'}` }
  }
}

function EntCredentialPanel() {
  const desktopNative = isTauriRuntime()
  const [schoolName, setSchoolName] = React.useState('')
  const [city, setCity] = React.useState('')
  const [preferredAdapterId, setPreferredAdapterId] = React.useState<string>('auto')
  const [searching, setSearching] = React.useState(false)
  const [candidates, setCandidates] = React.useState<SchoolCandidate[]>([])
  const [searchErr, setSearchErr] = React.useState<string | null>(null)
  const [selected, setSelected] = React.useState<SchoolCandidate | null>(null)
  const [manualLoginUrl, setManualLoginUrl] = React.useState('')
  const [username, setUsername] = React.useState('')
  const [password, setPassword] = React.useState('')
  const [savingCreds, setSavingCreds] = React.useState(false)
  const [saveResult, setSaveResult] = React.useState<string | null>(null)
  const [extStatus, setExtStatus] = React.useState<{ active: boolean; lastSeenAgoMs?: number; extId?: string }>({ active: false })
  // Settings owns the school import flow so the user has one clear place to configure it.
  const [savedSiteKey, setSavedSiteKey] = React.useState<string | null>(null)
  const [savedAdapterId, setSavedAdapterId] = React.useState<string>('pronote')
  const [scrapeBusy, setScrapeBusy] = React.useState(false)
  const [scrapeStep, setScrapeStep] = React.useState<string | null>(null)
  const [scrapeResult, setScrapeResult] = React.useState<string | null>(null)

  // Browser mode uses Aurora-Connect. Desktop app mode uses the native bridge.
  React.useEffect(() => {
    if (desktopNative) {
      setExtStatus({ active: true, extId: 'desktop-native', lastSeenAgoMs: 0 })
      return
    }
    const tick = async () => {
      try {
        const r = await fetch(`${getBridgeUrl()}/api/cowork/extension/list`, {
          signal: AbortSignal.timeout(3000),
        })
        const parsed = await parseJsonResponse<{ extensions?: Array<{ extId: string; lastSeenAgoMs: number }> }>(r)
        if (parsed.error || !parsed.data) {
          setExtStatus({ active: false })
          return
        }
        const data = parsed.data
        const ext = data.extensions?.[0]
        if (ext && ext.lastSeenAgoMs < 30000) {
          setExtStatus({ active: true, lastSeenAgoMs: ext.lastSeenAgoMs, extId: ext.extId })
        } else {
          setExtStatus({ active: false })
        }
      } catch { setExtStatus({ active: false }) }
    }
    void tick()
    const id = window.setInterval(tick, 3000)
    return () => window.clearInterval(id)
  }, [desktopNative])

  const discover = async () => {
    if (!schoolName.trim()) { setSearchErr('Nom d\'établissement requis'); return }
    setSearching(true)
    setCandidates([])
    setSearchErr(null)
    setSelected(null)
    try {
      const r = await fetch(`${getBridgeUrl()}/api/ent/discover-school`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          schoolName: schoolName.trim(),
          city: city.trim(),
          adapter: preferredAdapterId === 'auto' ? '' : preferredAdapterId,
        }),
        signal: AbortSignal.timeout(15000),
      })
      const parsed = await parseJsonResponse<{ ok?: boolean; candidates?: SchoolCandidate[]; error?: string; message?: string }>(r)
      if (parsed.error || !parsed.data) {
        setSearchErr(parsed.error || 'Bridge indisponible')
        return
      }
      const data = parsed.data
      if (!data.ok) {
        setSearchErr(data.error || 'Recherche impossible pour le moment. Tu peux entrer l’URL de connexion manuellement.')
        return
      }
      const nextCandidates = data.candidates || []
      setCandidates(nextCandidates)
      setSelected(nextCandidates[0] || null)
      if (nextCandidates.length === 0) {
        setSearchErr(data.message || 'Aucun portail fiable trouvé automatiquement. Entre l’URL de connexion de ton ENT ci-dessous pour continuer.')
      }
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Erreur réseau'
      setSearchErr(message.includes('timeout') ? 'Bridge trop lent ou indisponible pendant la découverte. Tu peux entrer l’URL de connexion manuellement.' : message)
    } finally {
      setSearching(false)
    }
  }

  const useManualPortal = () => {
    const loginUrl = manualLoginUrl.trim()
    if (!/^https?:\/\//i.test(loginUrl)) {
      setSearchErr('Entre une URL de connexion complète, par exemple https://...') 
      return
    }
    const adapterId = guessEducationAdapterId(loginUrl, preferredAdapterId)
    const manual: SchoolCandidate = {
      adapterId,
      systemLabel: educationSystemLabel(adapterId),
      name: schoolName.trim() || 'Portail scolaire manuel',
      url: loginUrl,
      loginUrl,
      uai: 'manual',
      city: city.trim(),
      source: 'manual',
      score: 0.5,
    }
    setCandidates((prev) => [manual, ...prev.filter((candidate) => candidate.loginUrl !== loginUrl)])
    setSelected(manual)
    setSearchErr(null)
  }

  const saveCredsAndLaunch = async () => {
    if (!selected || !username.trim() || !password) {
      setSaveResult('⚠ Sélectionne un établissement + remplis username + password')
      return
    }
    if (!desktopNative && (!extStatus.active || !extStatus.extId)) {
      setSaveResult('⚠ Aurora-Connect non détectée. Active l\'extension navigateur.')
      return
    }
    setSavingCreds(true)
    setSaveResult(null)
    try {
      // Desktop mode runs through the local bridge. Browser mode stores the
      // credentials in the extension vault and then launches the scrape.
      const adapterId = selected.adapterId || guessEducationAdapterId(selected.loginUrl, preferredAdapterId)
      const siteToken = (selected.uai || selected.name || new URL(selected.loginUrl).hostname)
        .toLowerCase()
        .replace(/[^a-z0-9_-]+/g, '-')
        .replace(/^-+|-+$/g, '') || 'manual'
      const siteKey = `${adapterId}-${siteToken}`
      if (desktopNative) {
        setScrapeBusy(true)
        setScrapeStep('desktop: ouverture session web native')
        const { runNativeEntPipeline } = await import('../services/entCredentialBridge')
        const { ENT_ADAPTERS } = await import('../services/entAdapters')
        const adapter = ENT_ADAPTERS.find((a) => a.id === adapterId)
        if (!adapter) {
          setSaveResult(`⚠ Connecteur ${adapterId} introuvable`)
          return
        }
        const result = await runNativeEntPipeline({
          adapter,
          loginUrl: selected.loginUrl,
          username: username.trim(),
          password,
          sections: ['devoirs', 'notes', 'agenda', 'fichiers'],
          profileKey: siteKey,
        })
        if (!result.ok) {
          const reason = result.reason
          let msg = result.error || 'Echec session web native'
          if (reason === 'captcha') msg = 'CAPTCHA detecte. Complete dans la fenetre ouverte puis relance.'
          else if (reason === 'mfa') msg = 'Double-facteur detecte. Entre le code dans la fenetre ouverte puis relance.'
          setSaveResult(`⚠ ${msg}`)
          return
        }
        const total = Object.values(result.sectionResults).length
        const ok = Object.values(result.sectionResults).filter((r) => r.ok).length
        const items = Object.values(result.sectionResults).reduce((sum, r) => sum + (r.itemsCount || 0), 0)
        setSaveResult(`✓ Session native terminee : ${ok}/${total} sections importees, ${items} items.`)
        setScrapeResult(`✓ ${ok}/${total} sections importees · ${items} items`)
        setSavedSiteKey(null)
        setPassword('')
        return
      }
      const r = await fetch(`${getBridgeUrl()}/api/cowork/extension/dispatch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          extId: extStatus.extId,
          kind: 'vault-add',
          payload: {
            siteKey,
            entry: {
              loginUrl: selected.loginUrl,
              username: username.trim(),
              password,
              label: selected.name,
              adapterId,
              schoolName: schoolName.trim(),
              city: city.trim() || selected.city,
              candidateUrls: candidates.map((c) => c.loginUrl),
            },
          },
        }),
      })
      const parsed = await parseJsonResponse<{ ok?: boolean; error?: string }>(r)
      if (parsed.error || !parsed.data) {
        setSaveResult(`⚠ ${parsed.error || 'Bridge indisponible'}`)
        return
      }
      const data = parsed.data
      if (!data.ok) {
        setSaveResult(`⚠ ${data.error || 'Vault locked. Déverrouille via l\'icône extension.'}`)
        return
      }
      setSaveResult(`✓ Credentials enregistrés pour ${selected.name}.`)
      setSavedSiteKey(siteKey)
      setSavedAdapterId(adapterId)
      // Clear password from memory.
      setPassword('')
    } catch (e) {
      setSaveResult(`⚠ ${e instanceof Error ? e.message : 'Erreur'}`)
    } finally {
      setSavingCreds(false)
      if (desktopNative) {
        setScrapeBusy(false)
        setScrapeStep(null)
      }
    }
  }

  return (
    <div className="sp-sec">
      <label className="sp-label">🔐 Connexion école / ENT — import académique</label>

      {/* Runtime status */}
      <div style={{
        padding: '8px 10px', borderRadius: 4,
        background: extStatus.active ? 'oklch(0.65 0.13 145 / 0.10)' : 'oklch(0.55 0.18 25 / 0.10)',
        border: `1px solid ${extStatus.active ? 'oklch(0.65 0.13 145 / 0.45)' : 'oklch(0.55 0.18 25 / 0.45)'}`,
        fontSize: 11, marginBottom: 8,
        display: 'flex', alignItems: 'center', gap: 8,
      }}>
        <span style={{
          width: 8, height: 8, borderRadius: '50%',
          background: extStatus.active ? 'oklch(0.65 0.18 145)' : 'oklch(0.55 0.18 25)',
          boxShadow: extStatus.active ? '0 0 6px oklch(0.65 0.18 145)' : 'none',
        }} />
        <span style={{ flex: 1 }}>
          {desktopNative ? (
            <>
              Mode app desktop : <strong>session web native</strong>
              <span style={{ color: 'var(--fg-mute, #888)', marginLeft: 6 }}>
                (pas d'extension navigateur requise)
              </span>
            </>
          ) : (
            <>
              Extension navigateur : <strong>{extStatus.active ? 'connectée' : 'absente'}</strong>
            </>
          )}
          {!desktopNative && extStatus.active && extStatus.lastSeenAgoMs !== undefined && (
            <span style={{ color: 'var(--fg-mute, #888)', marginLeft: 6 }}>
              (ping il y a {Math.round((extStatus.lastSeenAgoMs || 0) / 1000)}s)
            </span>
          )}
        </span>
      </div>

      {/* Step 1 : discovery */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 8 }}>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          <select value={preferredAdapterId} onChange={(e) => setPreferredAdapterId(e.target.value)}
            style={{
              flex: '0 0 145px', padding: '6px 10px', fontSize: 12,
              background: 'var(--bg-card, rgba(255,255,255,0.04))',
              color: 'var(--fg, #f5f5f5)',
              border: '1px solid var(--line, rgba(255,255,255,0.18))',
              borderRadius: 4,
            }}>
            {EDUCATION_SYSTEM_OPTIONS.map((option) => (
              <option key={option.id} value={option.id}>{option.label}</option>
            ))}
          </select>
          <input type="text" value={schoolName} onChange={(e) => setSchoolName(e.target.value)}
            placeholder="Établissement (ex : Jules Renard)"
            style={{
              flex: '2 1 180px', padding: '6px 10px', fontSize: 12,
              background: 'var(--bg-card, rgba(255,255,255,0.04))',
              color: 'var(--fg, #f5f5f5)',
              border: '1px solid var(--line, rgba(255,255,255,0.18))',
              borderRadius: 4,
            }} />
          <input type="text" value={city} onChange={(e) => setCity(e.target.value)}
            placeholder="Ville"
            style={{
              flex: '1 1 110px', padding: '6px 10px', fontSize: 12,
              background: 'var(--bg-card, rgba(255,255,255,0.04))',
              color: 'var(--fg, #f5f5f5)',
              border: '1px solid var(--line, rgba(255,255,255,0.18))',
              borderRadius: 4,
            }} />
          <button type="button" onClick={() => void discover()}
            disabled={searching || !schoolName.trim()}
            style={{
              padding: '6px 14px', fontSize: 11, fontWeight: 600,
              background: searching ? 'transparent' : 'oklch(0.74 0.13 60 / 0.20)',
              color: 'oklch(0.78 0.16 60)',
              border: '1px solid oklch(0.74 0.13 60 / 0.55)',
              borderRadius: 4, cursor: searching || !schoolName.trim() ? 'not-allowed' : 'pointer',
              opacity: searching || !schoolName.trim() ? 0.5 : 1,
            }}>
            {searching ? '⏳' : '🔎 Trouver'}
          </button>
        </div>
        {searchErr && (
          <div style={{ fontSize: 11, color: 'oklch(0.78 0.16 25)' }}>{searchErr}</div>
        )}
      </div>

      {/* Step 2 : choose candidate */}
      {candidates.length > 0 && (
        <div style={{ marginBottom: 8 }}>
          <div style={{ fontSize: 10, color: 'var(--fg-mute, #888)', marginBottom: 4, letterSpacing: '0.14em', textTransform: 'uppercase' }}>
            {candidates.length} portail(s) trouvé(s) — sélectionne le tien
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 200, overflowY: 'auto' }}>
            {candidates.map((c) => (
              <button key={c.loginUrl} type="button" onClick={() => setSelected(c)}
                style={{
                  padding: '6px 10px', fontSize: 11, textAlign: 'left',
                  background: selected?.loginUrl === c.loginUrl
                    ? 'oklch(0.74 0.13 60 / 0.20)'
                    : 'var(--bg-card, rgba(255,255,255,0.03))',
                  color: 'var(--fg, #f5f5f5)',
                  border: `1px solid ${selected?.loginUrl === c.loginUrl ? 'oklch(0.74 0.13 60 / 0.55)' : 'var(--line-soft, rgba(255,255,255,0.08))'}`,
                  borderRadius: 4, cursor: 'pointer',
                }}>
                <div style={{ fontWeight: 600 }}>{c.systemLabel || educationSystemLabel(c.adapterId)} · {c.name}</div>
                <div style={{ fontSize: 10, color: 'var(--fg-mute, #888)', fontFamily: 'var(--font-mono, monospace)' }}>
                  {c.uai && c.uai !== 'manual' ? `UAI ${c.uai} · ` : ''}{c.loginUrl}
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 8 }}>
        <div style={{ fontSize: 10, color: 'var(--fg-mute, #888)', letterSpacing: '0.14em', textTransform: 'uppercase' }}>
          URL manuelle si l’annuaire ne trouve pas ton portail
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <input type="url" value={manualLoginUrl} onChange={(e) => setManualLoginUrl(e.target.value)}
            placeholder="URL de connexion ENT / Pronote / ÉcoleDirecte"
            style={{
              flex: 1, padding: '6px 10px', fontSize: 12,
              background: 'var(--bg-card, rgba(255,255,255,0.04))',
              color: 'var(--fg, #f5f5f5)',
              border: '1px solid var(--line, rgba(255,255,255,0.18))',
              borderRadius: 4,
            }} />
          <button type="button" onClick={useManualPortal}
            disabled={!manualLoginUrl.trim()}
            style={{
              padding: '6px 12px', fontSize: 11, fontWeight: 600,
              background: manualLoginUrl.trim() ? 'oklch(0.74 0.13 60 / 0.20)' : 'transparent',
              color: 'oklch(0.78 0.16 60)',
              border: '1px solid oklch(0.74 0.13 60 / 0.55)',
              borderRadius: 4,
              cursor: manualLoginUrl.trim() ? 'pointer' : 'not-allowed',
              opacity: manualLoginUrl.trim() ? 1 : 0.5,
            }}>
            Utiliser cette URL
          </button>
        </div>
      </div>

      {/* Step 3 : enter creds */}
      {selected && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 8 }}>
          <div style={{ fontSize: 10, color: 'var(--fg-mute, #888)', letterSpacing: '0.14em', textTransform: 'uppercase' }}>
            Identifiants {selected.systemLabel || educationSystemLabel(selected.adapterId)} · {selected.name}
          </div>
          <input type="text" value={username} onChange={(e) => setUsername(e.target.value)}
            placeholder="Identifiant"
            style={{
              padding: '6px 10px', fontSize: 12,
              background: 'var(--bg-card, rgba(255,255,255,0.04))',
              color: 'var(--fg, #f5f5f5)',
              border: '1px solid var(--line, rgba(255,255,255,0.18))',
              borderRadius: 4,
            }} />
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
            placeholder="Mot de passe"
            style={{
              padding: '6px 10px', fontSize: 12,
              background: 'var(--bg-card, rgba(255,255,255,0.04))',
              color: 'var(--fg, #f5f5f5)',
              border: '1px solid var(--line, rgba(255,255,255,0.18))',
              borderRadius: 4,
            }} />
          <button type="button" onClick={() => void saveCredsAndLaunch()}
            disabled={savingCreds || !username.trim() || !password || (!desktopNative && !extStatus.active)}
            style={{
              padding: '8px 14px', fontSize: 12, fontWeight: 600,
              background: 'oklch(0.65 0.13 145 / 0.20)',
              color: 'oklch(0.78 0.16 145)',
              border: '1px solid oklch(0.65 0.13 145 / 0.55)',
              borderRadius: 4,
              cursor: savingCreds || !username.trim() || !password || (!desktopNative && !extStatus.active) ? 'not-allowed' : 'pointer',
              opacity: savingCreds || !username.trim() || !password || (!desktopNative && !extStatus.active) ? 0.5 : 1,
            }}>
            {savingCreds
              ? (desktopNative ? '⏳ Import natif en cours...' : '⏳ Enregistrement...')
              : (desktopNative ? '🧭 Lancer l’import scolaire natif' : '🔒 Enregistrer dans le vault Aurora-Connect')}
          </button>
          {saveResult && (
            <div style={{
              fontSize: 11, padding: '6px 10px', borderRadius: 4,
              background: saveResult.startsWith('✓') ? 'oklch(0.65 0.13 145 / 0.10)' : 'oklch(0.55 0.18 25 / 0.10)',
              border: `1px solid ${saveResult.startsWith('✓') ? 'oklch(0.65 0.13 145 / 0.45)' : 'oklch(0.55 0.18 25 / 0.45)'}`,
              color: saveResult.startsWith('✓') ? 'oklch(0.78 0.16 145)' : 'oklch(0.78 0.16 25)',
            }}>{saveResult}</div>
          )}
        </div>
      )}

      {/* Browser-only second step after credentials are saved in the extension vault. */}
      {!desktopNative && savedSiteKey && (
        <div style={{
          marginTop: 10, padding: 10, borderRadius: 6,
          background: 'oklch(0.65 0.18 145 / 0.06)',
          border: '1px solid oklch(0.65 0.18 145 / 0.30)',
        }}>
          <div style={{ fontSize: 10, color: 'var(--fg-mute, #888)', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 6 }}>
            Lancer le scrape scolaire
          </div>
          <button type="button"
            disabled={scrapeBusy || !extStatus.active}
            onClick={async () => {
              if (!extStatus.extId || !savedSiteKey) return
              setScrapeBusy(true)
              setScrapeResult(null)
              try {
                const { fullPipeline } = await import('../services/entCredentialBridge')
                const { ENT_ADAPTERS } = await import('../services/entAdapters')
                const adapter = ENT_ADAPTERS.find((a) => a.id === savedAdapterId)
                if (!adapter) {
                  setScrapeResult('⚠ Adapter inconnu')
                  setScrapeBusy(false)
                  return
                }
                const result = await fullPipeline({
                  extId: extStatus.extId,
                  siteKey: savedSiteKey,
                  adapter,
                  sections: ['devoirs', 'notes', 'agenda'],
                  onProgress: (step, detail) => setScrapeStep(`${step}: ${detail || ''}`),
                })
                if (!result.ok) {
                  const reason = result.loginResult.reason
                  let msg = result.loginResult.message || 'Échec'
                  if (reason === 'captcha') msg = '⚠ CAPTCHA détecté — complète manuellement puis relance'
                  else if (reason === 'mfa') msg = '⚠ Double-facteur détecté'
                  else if (reason === 'vault_locked') msg = '🔒 Vault verrouillé. Déverrouille via icône extension.'
                  setScrapeResult(msg)
                } else {
                  const total = Object.values(result.sectionResults).length
                  const ok = Object.values(result.sectionResults).filter((r) => r.ok).length
                  const items = Object.values(result.sectionResults)
                    .reduce((s, r) => s + (r.itemsCount || 0), 0)
                  setScrapeResult(`✓ ${ok}/${total} sections importées · ${items} items`)
                }
              } catch (e) {
                setScrapeResult(`⚠ ${e instanceof Error ? e.message : 'Erreur'}`)
              } finally {
                setScrapeBusy(false)
                setScrapeStep(null)
              }
            }}
            style={{
              padding: '8px 14px', fontSize: 12, fontWeight: 600,
              background: scrapeBusy ? 'transparent' : 'oklch(0.74 0.13 60 / 0.20)',
              color: 'oklch(0.78 0.16 60)',
              border: '1px solid oklch(0.74 0.13 60 / 0.55)',
              borderRadius: 4,
              cursor: scrapeBusy || !extStatus.active ? 'not-allowed' : 'pointer',
              opacity: scrapeBusy || !extStatus.active ? 0.5 : 1,
            }}>
            {scrapeBusy ? '⏳ Scrape en cours...' : '🚀 Auto-login + Scrape devoirs/notes/agenda'}
          </button>
          {scrapeStep && (
            <div style={{ fontSize: 10, color: 'var(--fg-mute, #888)', marginTop: 6 }}>
              {scrapeStep}
            </div>
          )}
          {scrapeResult && (
            <div style={{
              fontSize: 11, padding: '6px 10px', borderRadius: 4,
              marginTop: 6,
              background: scrapeResult.startsWith('✓') ? 'oklch(0.65 0.13 145 / 0.10)' : 'oklch(0.55 0.18 25 / 0.10)',
              border: `1px solid ${scrapeResult.startsWith('✓') ? 'oklch(0.65 0.13 145 / 0.45)' : 'oklch(0.55 0.18 25 / 0.45)'}`,
              color: scrapeResult.startsWith('✓') ? 'oklch(0.78 0.16 145)' : 'oklch(0.78 0.16 25)',
            }}>{scrapeResult}</div>
          )}
        </div>
      )}

      <div className="sp-hint" style={{ marginTop: 4 }}>
        {desktopNative
          ? 'Dans l’app, le mot de passe est envoyé au bridge local uniquement pour cette session. La fenêtre native garde les cookies de connexion pour importer et télécharger les ressources.'
          : 'Dans le navigateur, le mot de passe est chiffré AES-GCM 256 dans l’extension. Tout le flow scolaire vit ici dans Paramètres.'}
      </div>
    </div>
  )
}
