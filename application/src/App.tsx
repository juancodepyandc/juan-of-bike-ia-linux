import { Suspense, lazy, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Sparkles } from 'lucide-react'
import ModuleErrorBoundary from './components/ModuleErrorBoundary.tsx'
import PrivilegeBootstrapDialog from './components/PrivilegeBootstrapDialog.tsx'
import ToastContainer from './components/ToastContainer.tsx'
import { SpatialCanvas, SPATIAL_MODULES } from './components/SpatialCanvas.tsx'
import AuroraV1AppShell from './components/AuroraV1AppShell.tsx'
import AuroraCommandPalette from './components/AuroraCommandPalette.tsx'
import ScrollToTop from './components/ScrollToTop.tsx'
import HelpFab from './components/HelpFab.tsx'
import ConnectionIndicator from './components/ConnectionIndicator.tsx'
import VoiceQuickToggle from './components/VoiceQuickToggle.tsx'
import { reloadFresh } from './utils/buildRecovery.ts'
// v82aq : direct lazy import for the voice overlay (need onClose prop
// which pickView's wrapper doesn't expose).
// v82ay : skin-aware voice overlay. aurora_v1 → AuroraV1VoiceView
// (editorial sphere/waveforms entry, then VoiceCopilotView live with
// every feature wired). aurora_v3 → AuroraV3VoiceView (Studio MK III
// brushed-metal, also delegates to VoiceCopilotView). manga →
// VoiceCopilotView directly. Each accepts onClose so the entry-mode
// X button or the live-session close hook collapses the overlay.
const VoiceOverlayManga = lazy(() => import('./views/VoiceCopilotView'))
const VoiceOverlayV1 = lazy(() => import('./views/AuroraV1VoiceView'))
const VoiceOverlayV3 = lazy(() => import('./views/AuroraV3VoiceView'))
import MobileGrimoire from './components/MobileGrimoire.tsx'
import { readUiSkin } from './utils/uiSkin.ts'
import { isTauriRuntime } from './utils/runtime.ts'
import SkinSafeView from './components/SkinSafeView.tsx'

// v81o: skin-aware mobile shell. Manga keeps the legacy MobileGrimoire
// (cover/canvas/create/chat/voice/forge pages, two-finger swipe nav,
// ink scrolls, voice overlay, character forge). Aurora V1/V3 ports
// re-skin the *cover* and tap-delegate to MobileGrimoire so feature
// parity holds.
const LAZY_MOBILE_V1 = lazy(() => import('./components/AuroraV1MobileShell'))
const LAZY_MOBILE_V3 = lazy(() => import('./components/AuroraV3MobileShell'))
const LAZY_AGENT_SCENE = lazy(() => import('./components/AuroraAgentScene'))
const LAZY_API_EMBED_PANEL = lazy(() => import('./components/ApiEmbedPanel'))
const LAZY_V4_SHELL = lazy(() => import('./components/AuroraV4AppShell'))
const LAZY_GENERATION_FX = lazy(() => import('./components/generationFx/GenerationFxHost'))

// v81s: render-time skin resolution so vite emits dedicated chunks for
// both Aurora mobile shells (vs the previous IIFE that ran once at module
// eval and let vite tree-shake the un-taken branches when the build-time
// skin was manga).
function MobileShell() {
  const skin = readUiSkin()
  if (skin === 'aurora_v1') {
    return (
      <SkinSafeView fallback={MobileGrimoire} skinLabel="Mobile Editorial">
        <LAZY_MOBILE_V1 />
      </SkinSafeView>
    )
  }
  if (skin === 'aurora_v3') {
    return (
      <SkinSafeView fallback={MobileGrimoire} skinLabel="Mobile Ricochet">
        <LAZY_MOBILE_V3 />
      </SkinSafeView>
    )
  }
  return <MobileGrimoire />
}
import GlobalSearch from './components/GlobalSearch.tsx'
import SettingsPanel from './components/SettingsPanel.tsx'
import KeyboardCheatsheet from './components/KeyboardCheatsheet.tsx'
import CoworkOverlay from './components/CoworkOverlay.tsx'
import { useCoworkStore } from './stores/coworkStore.ts'
import { useDeviceKind } from './utils/device.ts'
import {
  DEFAULT_CODE_MODEL,
  DEFAULT_MAIN_MODEL,
  DEFAULT_VISION_MODEL,
  selectAdaptivePrimaryModel,
  selectAdaptiveVisionModel,
} from './config/models.ts'
import { useRuntimeTelemetry } from './hooks/useRuntimeTelemetry.ts'
import { useLinuxRuntimeFirstRun } from './hooks/useLinuxRuntimeFirstRun.ts'
import {
  checkServiceStatus,
  detectHardware,
  getHostPrivilegeStatus,
  ollamaListModels,
  restartApplicationAsAdmin,
  runtimeInspectServices,
} from './hooks/useTauri.ts'
import { useAppStore } from './stores/appStore.ts'
import { useChatStore } from './stores/chatStore.ts'
import { useFlashcardsStore } from './stores/flashcardsStore.ts'
import { useGamificationStore } from './stores/gamificationStore.ts'
import { useLearningSessionStore } from './stores/learningSessionStore.ts'
import { useModuleHistoryStore } from './stores/moduleHistoryStore.ts'
import type { HostPrivilegeStatus, ModuleId } from './types/app.ts'
import { pickView } from './utils/uiSkinViews.ts'
// v82lk9 : Aurora Team — 8 agents IA personnalisés (1 par module),
// V3 only. Mascot SVG cartoon animé + Team Manager pour éditer
// nom/voix/sysprompt. Voir application/src/services/auroraAgents.ts.
import AuroraAgentMascot from './components/AuroraAgentMascot.tsx'
import AuroraV3TeamManager from './views/AuroraV3TeamManager.tsx'
import { scanInstalledBrowsers, detectCurrentBrowser } from './services/coworkBrowserDetect.ts'

const ConversationView = pickView({
  manga:     () => import('./views/MangaChatView'),
  aurora_v1: () => import('./views/AuroraV1ChatView'),
  aurora_v3: () => import('./views/AuroraV3ChatView'),
  aurora_v4: () => import('./views/AuroraV4ChatView'),
})
const ImageView = pickView({
  manga:     () => import('./views/MangaImageView'),
  aurora_v1: () => import('./views/AuroraV1ImageView'),
  aurora_v3: () => import('./views/AuroraV3ImageView'),
  aurora_v4: () => import('./views/AuroraV4ImageView'),
})
const CodeView = pickView({
  manga:     () => import('./views/CodeView'),
  aurora_v1: () => import('./views/AuroraV1CodeView'),
  aurora_v3: () => import('./views/AuroraV3CodeView'),
  aurora_v4: () => import('./views/CodeView'),
})
const DrawingView = pickView({
  manga:     () => import('./views/MangaDrawingView'),
  aurora_v1: () => import('./views/AuroraV1DrawingView'),
  aurora_v3: () => import('./views/AuroraV3DrawingView'),
  aurora_v4: () => import('./views/AuroraV4DrawingView'),
})
const ModelView = pickView({
  manga:     () => import('./views/ModelView'),
  aurora_v1: () => import('./views/AuroraV13DView'),
  aurora_v3: () => import('./views/AuroraV13DView'),
  aurora_v4: () => import('./views/ModelView'),
})
const LearningView = pickView({
  manga:     () => import('./views/AuroraV1AcademyView'),
  aurora_v1: () => import('./views/AuroraV1AcademyView'),
  aurora_v3: () => import('./views/AuroraV1AcademyView'),
  aurora_v4: () => import('./views/AuroraV4AcademyView'),
})
const VoiceCopilotView = pickView({
  manga:     () => import('./views/VoiceCopilotView'),
  aurora_v3: () => import('./views/AuroraV3VoiceView'),
  aurora_v4: () => import('./views/VoiceCopilotView'),
})
const CyberView = pickView({
  manga:     () => import('./views/MangaCyberView'),
  aurora_v1: () => import('./views/AuroraV1CyberView'),
  aurora_v3: () => import('./views/AuroraV1CyberView'),
  aurora_v4: () => import('./views/AuroraV4CyberView'),
})

const VIEW_MAP = {
  conversation: ConversationView,
  image: ImageView,
  code: CodeView,
  drawing: DrawingView,
  '3d': ModelView,
  learning: LearningView,
  voice: VoiceCopilotView,
  cyber: CyberView,
} as const

/**
 * Garde chaque module MONTE une fois visite (masque en display:none quand
 * inactif) au lieu de le demonter au changement de module. Consequence: aucun
 * etat volatil (generation en cours, flux/streamPreview, saisie) n'est perdu en
 * naviguant puis en revenant — uniforme pour TOUS les modules. La generation
 * async continue d'ecrire dans un composant TOUJOURS monte, et le retour
 * re-affiche l'etat live au lieu d'une vue vierge. Un module n'est monte qu'a sa
 * premiere visite (pas de cout initial pour les modules jamais ouverts).
 */
function PersistentModuleHost({
  active,
  render,
}: {
  active: ModuleId
  render: (id: ModuleId) => ReactNode
}) {
  const [mounted, setMounted] = useState<ModuleId[]>(() => [active])
  useEffect(() => {
    setMounted((prev) => (prev.includes(active) ? prev : [...prev, active]))
  }, [active])
  return (
    <>
      {mounted.map((id) => (
        <div key={id} data-aurora-module={id} style={{ display: id === active ? 'contents' : 'none' }}>
          {render(id)}
        </div>
      ))}
    </>
  )
}

function buildMachineSignature(hw: { os: string; cpu: string; cores: number; ram_gb: number; gpu: string }) {
  return `${hw.os}|${hw.cpu}|${hw.cores}|${Math.round(hw.ram_gb)}|${hw.gpu}`
}

function BootOverlay({
  visible,
  checkingConfig,
  hardwareReady,
  modelCount,
  servicesReady,
}: {
  visible: boolean
  checkingConfig: boolean
  hardwareReady: boolean
  modelCount: number
  servicesReady: boolean
}) {
  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.4, ease: [0.32, 0.72, 0, 1] }}
          className="fixed inset-0 z-[200] flex items-center justify-center"
          style={{ background: 'var(--color-aurora-bg)' }}
        >
          <div className="absolute inset-0 aurora-mesh opacity-80" />
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1, duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
            className="relative w-full max-w-md px-8"
          >
            <div className="flex flex-col items-center gap-5">
              <div
                className="h-14 w-14 rounded-[14px] flex items-center justify-center"
                style={{
                  background: 'linear-gradient(135deg, var(--color-aurora-brand-soft), var(--color-aurora-brand-dim))',
                  boxShadow: '0 8px 32px rgba(201,167,112,0.25), inset 0 1px 0 rgba(255,255,255,0.2)',
                }}
              >
                <Sparkles size={22} className="text-[#1b1510]" strokeWidth={2.5} />
              </div>
              <div className="text-center space-y-1">
                <h1 className="display-2 text-[var(--color-aurora-text-strong)]">Aurora</h1>
                <p className="caption">Copilote IA local</p>
              </div>
              <div className="w-full space-y-2 mt-4">
                <BootStep label="Configuration" done={!checkingConfig} />
                <BootStep label="Matériel détecté" done={hardwareReady} />
                <BootStep label={`${modelCount} modèle${modelCount > 1 ? 's' : ''}`} done={servicesReady || modelCount > 0} />
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

function BootStep({ label, done }: { label: string; done: boolean }) {
  return (
    <div className="flex items-center gap-3 px-3 py-2 rounded-[10px] surface-card-muted">
      <span className="relative flex items-center justify-center h-2.5 w-2.5">
        <span className={`h-1.5 w-1.5 rounded-full transition-all ${done ? 'bg-[var(--color-aurora-ok)]' : 'bg-[var(--color-aurora-text-faint)]'}`} />
        {!done && <span className="absolute inset-0 rounded-full bg-[var(--color-aurora-brand)] opacity-40 animate-ping" />}
      </span>
      <span className="text-[12px] font-medium text-[var(--color-aurora-text-muted)]">{label}</span>
      <span className="flex-1" />
      <span className="text-[11px] font-mono text-[var(--color-aurora-text-dim)]">{done ? '✓' : '…'}</span>
    </div>
  )
}

export default function App() {
  const {
    activeModule,
    checkingConfig,
    focusMode,
    hardware,
    installedModels,
    profile,
    runtimeServices,
    services,
    setActiveModule,
    setCheckingConfig,
    setFocusMode,
    setHardware,
    setInstalledModels,
    setMainModel,
    setVisionModel,
    setProfile,
    setServices,
    setRuntimeServices,
    setWizardVisible,
  } = useAppStore()
  const [bootWasRunning, setBootWasRunning] = useState(false)
  const [bootVisible, setBootVisible] = useState(true)
  const [hostPrivileges, setHostPrivileges] = useState<HostPrivilegeStatus | null>(null)
  const [showPrivilegeDialog, setShowPrivilegeDialog] = useState(false)
  const [elevationPending, setElevationPending] = useState(false)
  const [elevationError, setElevationError] = useState<string | null>(null)
  // v82ah : `mountedModules` was a dead state — set on every module
  // switch but never read by any consumer. Each setState forced an extra
  // App re-render that propagated through ShellRouter / AppShell /
  // CommandPalette etc. Removing it cuts one re-render per click,
  // making module switches feel snappier.

  // Data for card metrics
  const messages = useChatStore((s) => s.messages)
  const { decks, cards } = useFlashcardsStore()
  const { xp, level, quizHistory } = useGamificationStore()
  // v84q — fix : le store expose `sessions: ConversationSession[]`, pas
  // `sessionsByModule`. On dérive le mapping localement pour les module cards.
  const allSessions = useModuleHistoryStore((s) => s.sessions)
  const historyByModule = useMemo(() => {
    const out: Partial<Record<ModuleId, typeof allSessions>> = {}
    for (const s of allSessions) {
      const mod = s.module as ModuleId
      if (!out[mod]) out[mod] = []
      out[mod]!.push(s)
    }
    return out
  }, [allSessions])

  useRuntimeTelemetry()
  useLinuxRuntimeFirstRun()

  // v82at : prefetch les chunks modules les plus probables après le premier
  // paint. En prod-mode (vite preview), chaque chunk est un fichier séparé
  // — la première activation d'un module déclenche un network roundtrip
  // qui retarde le clic. Pre-loader en idle callback : pendant que l'user
  // regarde la home, on charge en arrière-plan les vues du skin actif.
  // requestIdleCallback fallback sur setTimeout pour Safari/iOS.
  // v82k1 : skin-aware prefetch. Manga views n'étaient prefetchées que
  // pour rien (manga n'est pas dans USER_PICKABLE_SKINS). Pour aurora_v1
  // on préfetch les AuroraV1*View chunks. Pour manga on garde l'ancien
  // comportement. Pour aurora_v3 on préfetch les V3 chunks.
  useEffect(() => {
    const idle = (cb: () => void) => {
      const w = window as Window & { requestIdleCallback?: (cb: () => void, opts?: { timeout?: number }) => number }
      if (typeof w.requestIdleCallback === 'function') {
        w.requestIdleCallback(cb, { timeout: 2000 })
      } else {
        window.setTimeout(cb, 800)
      }
    }
    const skin = readUiSkin()
    idle(() => {
      void import('./views/VoiceCopilotView').catch(() => {})
      if (skin === 'aurora_v4') {
        void import('./views/AuroraV4ChatView').catch(() => {})
        void import('./views/AuroraV4ImageView').catch(() => {})
        void import('./views/CodeView').catch(() => {})
        void import('./views/AuroraV4CyberView').catch(() => {})
        void import('./views/AuroraV4DrawingView').catch(() => {})
      } else if (skin === 'aurora_v1') {
        void import('./views/AuroraV1ChatView').catch(() => {})
        void import('./views/AuroraV1ImageView').catch(() => {})
        void import('./views/AuroraV1CodeView').catch(() => {})
        void import('./views/AuroraV1CyberView').catch(() => {})
        void import('./views/AuroraV1DrawingView').catch(() => {})
      } else if (skin === 'aurora_v3') {
        void import('./views/AuroraV3CodeView').catch(() => {})
        void import('./views/AuroraV3AcademyView').catch(() => {})
      } else {
        // manga (théorique : skin filtré du picker, jamais sélectionnable user)
        void import('./views/CodeView').catch(() => {})
        void import('./views/MangaChatView').catch(() => {})
        void import('./views/MangaImageView').catch(() => {})
        void import('./views/MangaCyberView').catch(() => {})
        void import('./views/MangaDrawingView').catch(() => {})
      }
    })
    idle(() => {
      if (skin === 'aurora_v4') {
        void import('./views/AuroraV4AcademyView').catch(() => {})
        void import('./views/ModelView').catch(() => {})
      } else if (skin === 'aurora_v1') {
        void import('./views/AuroraV1AcademyView').catch(() => {})
        void import('./views/AuroraV13DView').catch(() => {})
      } else if (skin === 'aurora_v3') {
        void import('./views/AuroraV33DView').catch(() => {})
      } else {
        // manga
        void import('./views/ModelView').catch(() => {})
        void import('./views/MangaAcademyView').catch(() => {})
      }
    })
  }, [])

  // v82v : global module-switch shortcuts. They live up here at the
  // App root (not inside a shell) so they work on every skin —
  // including aurora_v3 which has no Sidebar at all. Cowork opens via
  // the cowork store, the rest call setActiveModule.
  // v82w : ⌘K opens AuroraCommandPalette (discoverable module switch
  // for V3 where there's no Sidebar at all).
  const [paletteOpen, setPaletteOpen] = useState(false)
  // v82aq : voice overlay state — voice is a sub-feature, not a module
  // page (appStore.setActiveModule remap 'voice' → 'conversation').
  const [voiceOverlayOpen, setVoiceOverlayOpen] = useState(false)

  useEffect(() => {
    const onOpen = () => setVoiceOverlayOpen(true)
    const onPalette = () => setPaletteOpen(true)
    window.addEventListener('aurora:open-voice-overlay', onOpen)
    window.addEventListener('aurora:open-command-palette', onPalette)
    return () => {
      window.removeEventListener('aurora:open-voice-overlay', onOpen)
      window.removeEventListener('aurora:open-command-palette', onPalette)
    }
  }, [])

  // iter31 : cross-module auto-open de la page parcours BAC. Quand la
  // génération parcours-bac termine alors que l'utilisateur est sur un
  // autre module (Image, Code, etc.), useAcademyViewLogic lève le
  // signal global. Ici on watch ce signal et on bascule sur 'learning'
  // — la vue Academy détecte le payload et auto-ouvre l'overlay
  // plein écran. Cela répond à la demande user : "tu vois cette espace
  // s'ouvre toute seule a la fin de la génération quoi que tu sois
  // dans d'autre module".
  const parcoursOverlayReady = useLearningSessionStore((s) => s.parcoursOverlay.ready)
  const consumeParcoursOverlay = useLearningSessionStore((s) => s.consumeParcoursOverlay)
  useEffect(() => {
    if (!parcoursOverlayReady) return
    // Bascule vers le module learning si on n'y est pas déjà — la vue
    // Academy fait le reste (auto-open de l'overlay full-screen). On
    // consomme tout de suite le signal pour ne pas re-piéger l'user.
    if (useAppStore.getState().activeModule !== 'learning') {
      setActiveModule('learning')
    }
    consumeParcoursOverlay()
  }, [parcoursOverlayReady, setActiveModule, consumeParcoursOverlay])
  useEffect(() => {
    const KBD: Record<string, ModuleId | 'cowork'> = {
      '`': 'cowork',
      '1': 'conversation',
      '2': 'image',
      '3': 'code',
      '5': 'drawing',
      '6': '3d',
      '7': 'cyber',
      '8': 'learning',
      'v': 'voice',
    }
    const handler = (e: KeyboardEvent) => {
      if (!(e.metaKey || e.ctrlKey)) return
      const target = e.target as HTMLElement | null
      const tag = target?.tagName?.toLowerCase()
      const inEditable = tag === 'input' || tag === 'textarea' || target?.isContentEditable
      if (e.key.toLowerCase() === 'k') {
        // v82x : skip on manga skin so we don't double-open with
        // SpatialCanvas's own SlashCommand listener. AuroraCommandPalette
        // is the V1/V3 path; SpatialCanvas's SlashCommand is manga.
        if (readUiSkin() === 'manga') return
        e.preventDefault()
        setPaletteOpen((v) => !v)
        return
      }
      if (inEditable) return
      const id = KBD[e.key.toLowerCase()]
      if (!id) return
      e.preventDefault()
      if (id === 'cowork') { useCoworkStore.getState().open(); return }
      if (id === 'voice') { setVoiceOverlayOpen(true); return }
      setActiveModule(id)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [setActiveModule])

  // v82gf : tracking précédent module pour Cmd+Shift+P swap.
  const previousModuleRef = useRef<ModuleId | null>(null)
  useEffect(() => {
    return () => { /* keep ref */ }
  }, [])
  useEffect(() => {
    // Track prev quand activeModule change
    const handler = (newMod: ModuleId, oldMod: ModuleId) => {
      if (newMod !== oldMod) previousModuleRef.current = oldMod
    }
    let prev = useAppStore.getState().activeModule
    const unsub = useAppStore.subscribe((state) => {
      const cur = state.activeModule
      if (cur !== prev) {
        handler(cur, prev)
        prev = cur
      }
    })
    return () => unsub()
  }, [])
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key.toLowerCase() === 'p') {
        e.preventDefault()
        const prev = previousModuleRef.current
        if (prev) setActiveModule(prev)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [setActiveModule])

  // v82ik : Cmd+J / Ctrl+J = focus first text input du module actuel
  //   (textarea ou <input type="text"> non-disabled). Cross-module
  //   discrétionnaire : Cmd+I cible le chat composer (refs explicites),
  //   Cmd+J est le générique pour Image / Code / Drawing / Video / 3D
  //   où chaque module a son propre input prompt.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'j' && !e.shiftKey && !e.altKey) {
        const tag = (e.target as HTMLElement | null)?.tagName?.toUpperCase()
        if (tag === 'INPUT' || tag === 'TEXTAREA') return
        // Cherche le premier input/textarea visible non-disabled dans le DOM.
        const candidates = document.querySelectorAll<HTMLInputElement | HTMLTextAreaElement>(
          'textarea:not([disabled]), input[type="text"]:not([disabled])',
        )
        for (const el of Array.from(candidates)) {
          // Skip si offsetParent null (caché via display:none).
          if (el.offsetParent === null) continue
          // Skip si l'élément est dans le SettingsPanel ou un overlay z-index élevé.
          const inOverlay = el.closest('[role="dialog"], .sp-panel, .kbd-panel')
          if (inOverlay) continue
          e.preventDefault()
          el.focus()
          // Sélection du contenu pour faciliter l'écrasement.
          if ('select' in el && typeof el.select === 'function') {
            try { el.select() } catch { /* noop */ }
          }
          return
        }
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  // v82gd : "g + letter" vim-style keyseq pour navigation modules.
  // Documenté dans KeyboardCheatsheet depuis longtemps mais pas
  // wiré jusqu'ici. Pendant 1.5s après "g" sans modifier hors input,
  // la prochaine key match un module.
  useEffect(() => {
    const G_MAP: Record<string, ModuleId | 'cowork'> = {
      c: 'conversation', i: 'image', o: 'code', d: 'drawing',
      t: '3d', a: 'learning', s: 'voice', y: 'cyber',
      // v82ge : "gg" double-tap → home/conversation (vim-style)
      g: 'conversation',
    }
    let pendingG = false
    let timeout: number | null = null
    const handler = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || e.shiftKey) return
      const target = e.target as HTMLElement | null
      const tag = target?.tagName?.toLowerCase()
      if (tag === 'input' || tag === 'textarea' || target?.isContentEditable) return
      const k = e.key.toLowerCase()
      if (!pendingG && k === 'g') {
        pendingG = true
        if (timeout) window.clearTimeout(timeout)
        timeout = window.setTimeout(() => { pendingG = false; timeout = null }, 1500)
        return
      }
      if (pendingG) {
        pendingG = false
        if (timeout) window.clearTimeout(timeout)
        timeout = null
        const id = G_MAP[k]
        if (id) {
          e.preventDefault()
          if (id === 'voice') { setVoiceOverlayOpen(true); return }
          if (id === 'cowork') return  // cowork = overlay separate
          setActiveModule(id as ModuleId)
        }
      }
    }
    window.addEventListener('keydown', handler)
    return () => {
      window.removeEventListener('keydown', handler)
      if (timeout) window.clearTimeout(timeout)
    }
  }, [setActiveModule])

  // v82n8 : swipe ONLY blocks at touchstart when target is in a
  // HORIZONTAL scroller (so Code preview h-scroll still works). The
  // vertical-scroller guard is GONE — vertical motion is rejected at
  // touchend by dx/dy ratio. User reported v82n7 was hijacking content
  // scrolls : "quand je swippe ça me change de module, pas du tout un
  // défilement". Plus the wheel listener now requires a STRONG
  // horizontal impulse (300px / 200ms) to avoid trackpad scroll on
  // long pages firing module switches.
  useEffect(() => {
    const SWIPE_ORDER: ModuleId[] = [
      'conversation', 'image', 'code', 'drawing', '3d', 'cyber', 'learning',
    ]
    const gesture = { active: false, startX: 0, startY: 0, startT: 0, multi: false }
    const isInEditable = (target: EventTarget | null) => {
      const el = target as HTMLElement | null
      if (!el) return false
      if (el.isContentEditable) return true
      const tag = el.tagName?.toLowerCase()
      if (tag === 'textarea' || tag === 'input' || tag === 'select') return true
      // Buttons + closest editable ancestors so typing isn't hijacked.
      return !!el.closest?.('textarea, input, select, [contenteditable="true"]')
    }
    // v82n8 : ONLY horizontal-scroller guard (vertical-scroller guard
    // was removed in v82n7 because it blocked all 1-finger swipes —
    // every module has some overflow-y ancestor). The horizontal one
    // is necessary so the Code preview's whiteSpace:pre overflow:auto
    // can be h-scrolled by touch instead of switching module.
    const isInHorizontalScroller = (target: EventTarget | null) => {
      let el = target as HTMLElement | null
      while (el && el !== document.body) {
        const cs = window.getComputedStyle(el)
        const ovX = cs.overflowX
        if ((ovX === 'auto' || ovX === 'scroll') && el.scrollWidth > el.clientWidth + 4) {
          return true
        }
        el = el.parentElement
      }
      return false
    }
    const switchByDelta = (dx: number) => {
      const cur = useAppStore.getState().activeModule
      const idx = SWIPE_ORDER.indexOf(cur)
      if (idx === -1) return
      // dx > 0 → swipe right → previous module ; dx < 0 → next module
      const next = SWIPE_ORDER[idx + (dx < 0 ? 1 : -1)]
      if (!next) return // edges of carousel — no wrap
      setActiveModule(next)
    }
    const onStart = (e: TouchEvent) => {
      if (e.touches.length === 0) return
      if (isInEditable(e.target)) {
        gesture.active = false
        return
      }
      const t0 = e.touches[0]
      const t1 = e.touches[1]
      const x = t1 ? (t0.clientX + t1.clientX) / 2 : t0.clientX
      const y = t1 ? (t0.clientY + t1.clientY) / 2 : t0.clientY
      gesture.active = true
      gesture.startX = x
      gesture.startY = y
      gesture.startT = Date.now()
      gesture.multi = e.touches.length >= 2
      // v82n8 : 1-finger inside horizontal scroller → don't activate so
      // native h-scroll wins (Code preview, wide tables, etc).
      if (!gesture.multi && isInHorizontalScroller(e.target)) {
        gesture.active = false
      }
    }
    const onEnd = (e: TouchEvent) => {
      if (!gesture.active) return
      gesture.active = false
      const ct = e.changedTouches
      if (ct.length === 0) return
      const endX = ct.length >= 2 ? (ct[0].clientX + ct[1].clientX) / 2 : ct[0].clientX
      const endY = ct.length >= 2 ? (ct[0].clientY + ct[1].clientY) / 2 : ct[0].clientY
      const dx = endX - gesture.startX
      const dy = endY - gesture.startY
      const dur = Date.now() - gesture.startT
      if (dur > 1200) return
      const MIN = 60 // v82n7 : 80 → 60, more responsive
      if (Math.abs(dx) < MIN) return
      // Strong horizontal dominance required so a slight diagonal scroll
      // doesn't accidentally switch module.
      if (Math.abs(dx) < Math.abs(dy) * 1.4) return
      switchByDelta(dx)
    }
    // v82n8 : trackpad 2-finger horizontal swipe — STRICTER impulse
    // detection so reading horizontal scroll inside content (like the
    // Code preview pre tag) doesn't fire module switch.
    //   - threshold 320px in 200ms (was 180/300)
    //   - |deltaY| < 15 cutoff (was 40)
    //   - skip when target is in a horizontal scroller (let it scroll)
    let wheelAcc = 0
    let wheelStart = 0
    let wheelDecay: number | null = null
    const onWheel = (e: WheelEvent) => {
      if (isInEditable(e.target)) return
      // Horizontal scroll inside a scrollable container → leave it alone.
      if (isInHorizontalScroller(e.target)) {
        wheelAcc = 0
        return
      }
      const now = Date.now()
      if (now - wheelStart > 200) {
        wheelAcc = 0
        wheelStart = now
      }
      // Any vertical motion at all resets the accumulator — strict so
      // diagonal scroll doesn't accumulate into a switch.
      if (Math.abs(e.deltaY) > 15) {
        wheelAcc = 0
        return
      }
      wheelAcc += e.deltaX
      if (Math.abs(wheelAcc) >= 320) {
        switchByDelta(-wheelAcc) // wheel deltaX > 0 = scroll right = "go forward" in carousel
        wheelAcc = 0
      }
      if (wheelDecay) window.clearTimeout(wheelDecay)
      wheelDecay = window.setTimeout(() => { wheelAcc = 0 }, 250) as unknown as number
    }
    window.addEventListener('touchstart', onStart, { passive: true })
    window.addEventListener('touchend', onEnd, { passive: true })
    window.addEventListener('wheel', onWheel, { passive: true })
    return () => {
      window.removeEventListener('touchstart', onStart)
      window.removeEventListener('touchend', onEnd)
      window.removeEventListener('wheel', onWheel)
      if (wheelDecay) window.clearTimeout(wheelDecay)
    }
  }, [setActiveModule])

  useEffect(() => {
    let cancelled = false

    async function boot() {
      setCheckingConfig(true)
      // v82af : boot was gated on the slowest of 4 service probes AND on
      // ollamaListModels (which can take seconds when Ollama is loading
      // models). UI stayed locked behind the boot screen even after the
      // 4 dots went green — user said "rien que le chargement avec la
      // configuration prend du temps même quand c'est vert".
      // Fix : every probe's setState fires AS SOON AS its own promise
      // resolves (no Promise.allSettled barrier). Ollama models list is
      // fire-and-forget. checkingConfig flips false after the cheapest
      // probe (services) so the UI unlocks fast ; the slower probes
      // continue populating in the background.
      const settled = { services: false, runtime: false, hw: false, priv: false }
      const maybeUnlock = () => {
        if (cancelled) return
        // unlock as soon as services OR runtime is back — that's the
        // shortest path to a usable shell. The other probes settle in.
        if (settled.services || settled.runtime) setCheckingConfig(false)
      }

      void checkServiceStatus().then((v) => {
        if (cancelled) return
        setServices(v); settled.services = true; maybeUnlock()
      }).catch(() => { settled.services = true; maybeUnlock() })

      void runtimeInspectServices().then((v) => {
        if (cancelled) return
        const mapped = v.reduce((acc, s) => { acc[s.id] = s; return acc }, {} as Record<'ollama' | 'comfyui', (typeof v)[number]>)
        setRuntimeServices(mapped); settled.runtime = true; maybeUnlock()
      }).catch(() => { settled.runtime = true; maybeUnlock() })

      void detectHardware().then((hw) => {
        if (cancelled) return
        setHardware(hw)
        const safeMain = selectAdaptivePrimaryModel(hw)
        if (safeMain !== DEFAULT_MAIN_MODEL) setMainModel(safeMain)
        const safeVision = selectAdaptiveVisionModel(hw)
        if (safeVision !== DEFAULT_VISION_MODEL) setVisionModel(safeVision)
        const sig = buildMachineSignature(hw)
        if (profile) {
          const known = profile.knownMachineSignatures || []
          const nextPref = profile.preferredMainModel === DEFAULT_MAIN_MODEL ? safeMain : profile.preferredMainModel
          if (!known.includes(sig)) {
            setProfile({
              ...profile,
              knownMachineSignatures: [...known, sig],
              machineSignature: sig,
              hardware: hw,
              preferredMainModel: nextPref,
              preferAdminMode: profile.preferAdminMode ?? true,
            })
            if (profile.wizardCompleted) setWizardVisible(true)
          } else if (profile.hardware?.ram_gb !== hw.ram_gb || profile.preferredMainModel !== nextPref || profile.preferAdminMode === undefined) {
            setProfile({
              ...profile,
              hardware: hw,
              preferredMainModel: nextPref,
              preferAdminMode: profile.preferAdminMode ?? true,
            })
          }
        } else {
          setProfile({
            name: 'Utilisateur',
            machineSignature: sig,
            knownMachineSignatures: [sig],
            wizardCompleted: false,
            hardware: hw,
            preferredMainModel: safeMain,
            preferredCodeModel: DEFAULT_CODE_MODEL,
            preferredVisionModel: safeVision,
            preferAdminMode: true,
            createdAt: new Date().toISOString(),
          })
        }
        settled.hw = true; maybeUnlock()
      }).catch(() => { settled.hw = true; maybeUnlock() })

      void getHostPrivilegeStatus().then((priv) => {
        if (cancelled) return
        setHostPrivileges(priv)
        setShowPrivilegeDialog(!priv.isAdmin)
        settled.priv = true; maybeUnlock()
      }).catch(() => {
        if (cancelled) return
        setHostPrivileges({ platform: 'unknown', isAdmin: false, canElevate: false, detail: '' })
        settled.priv = true; maybeUnlock()
      })

      // Fire-and-forget : models list shouldn't gate the shell.
      void ollamaListModels().then((modelsResp) => {
        if (cancelled) return
        if (modelsResp?.models) setInstalledModels(modelsResp.models.map((m: { name: string }) => m.name))
      }).catch(() => { /* ignore */ })

      // Hard fallback : if no probe returns within 4 s, unlock anyway so
      // a flaky bridge doesn't lock the user out forever.
      window.setTimeout(() => { if (!cancelled) setCheckingConfig(false) }, 4000)
    }

    void boot()
    const interval = window.setInterval(async () => {
      try { const next = await checkServiceStatus(); if (!cancelled) setServices(next) } catch { /* ignore */ }
    }, 30000)
    return () => { cancelled = true; window.clearInterval(interval) }
  }, [])

  useEffect(() => {
    if (checkingConfig) { setBootWasRunning(true); setBootVisible(true); return }
    if (!bootWasRunning) return
    // v82af : 700 ms artificial fade-out delay was a leftover that the
    // user explicitly flagged ("même quand c'est vert ça charge encore").
    // Hide the boot overlay immediately when the probes resolve.
    setBootVisible(false)
  }, [bootWasRunning, checkingConfig])

  const handlePrivilegeElevation = async () => {
    setElevationPending(true)
    setElevationError(null)
    try { await restartApplicationAsAdmin() }
    catch (e) { setElevationError(e instanceof Error ? e.message : 'Elevation echouee.') }
    finally { setElevationPending(false) }
  }

  // Build per-module stats
  const getModuleStats = useMemo(() => (id: ModuleId) => {
    const hist = historyByModule?.[id] ?? []
    switch (id) {
      case 'conversation':
        return {
          value: messages.length,
          caption: messages.length > 0
            ? `Dernier tour · ${messages[messages.length - 1].content.slice(0, 60)}…`
            : 'Ouvre une conversation avec le copilote local.',
          tags: ['streaming', 'Ollama', 'voix'],
        }
      case 'image':
        return { value: hist.length || 0, caption: 'FLUX · 15 styles · édition référence.', tags: ['FLUX', 'dev', 'SDXL'] }
      case 'code':
        return { value: hist.length || 0, caption: 'Pipeline modele expert avec auto-correction.', tags: ['22 langs', 'sandbox', 'preview'] }
      case 'drawing':
        return { value: hist.length || 0, caption: 'Canvas + rendu FLUX preserving sketch.', tags: ['sketch', 'vision'] }
      case '3d':
        return { value: hist.length || 0, caption: 'Hunyuan3D · DreamGaussian · rig Rigify.', tags: ['mesh', 'rig', 'photo'] }
      case 'learning':
        return {
          value: xp,
          sublabel: `niv. ${level} · xp`,
          caption: `${quizHistory.length} quiz · ${decks.length} decks · ${cards.length} fiches.`,
          tags: ['Duolingo', 'labs', 'parcours'],
        }
      case 'voice':
        return { value: '—', caption: 'Voxtral · Kokoro · avatars 3D.' }
      case 'cyber':
        return { value: hist.length || 0, caption: 'Crypto · réseau · forensics · CTF local.', tags: ['AES', 'nmap', 'hash', 'CTF'] }
      default:
        return { value: '—' }
    }
  }, [messages, historyByModule, xp, level, quizHistory, decks, cards])

  const renderModule = (id: ModuleId) => {
    const View = VIEW_MAP[id === 'video' ? 'conversation' : id]
    const meta = SPATIAL_MODULES.find((m) => m.id === id)
    return (
      <Suspense
        fallback={
          <div className="grid min-h-[24rem] place-items-center">
            <div className="surface-card-muted px-5 py-4 text-[13px] text-[var(--color-aurora-text-muted)]">
              Chargement du module…
            </div>
          </div>
        }
      >
        <ModuleErrorBoundary
          moduleKey={id}
          moduleLabel={meta?.label || id}
          onReturnHome={() => setActiveModule('conversation')}
        >
          <View />
        </ModuleErrorBoundary>
      </Suspense>
    )
  }

  return (
    <>
      <BootOverlay
        visible={bootVisible}
        checkingConfig={checkingConfig}
        hardwareReady={Boolean(hardware)}
        modelCount={installedModels.length}
        servicesReady={
          (services?.ollama || false) ||
          (services?.comfyui || false) ||
          (runtimeServices?.ollama?.available || false) ||
          (runtimeServices?.comfyui?.available || false) ||
          true
        }
      />
      <PrivilegeBootstrapDialog
        visible={showPrivilegeDialog}
        status={hostPrivileges}
        isElevating={elevationPending}
        error={elevationError}
        onElevate={handlePrivilegeElevation}
        onClose={() => { setShowPrivilegeDialog(false); setElevationError(null) }}
      />

      <ShellRouter
        activeModule={activeModule}
        focusMode={focusMode}
        setActiveModule={setActiveModule}
        setFocusMode={setFocusMode}
        getModuleStats={getModuleStats}
        renderModule={renderModule}
        openVoiceOverlay={() => setVoiceOverlayOpen(true)}
      />

      <ToastContainer />
      <GlobalSearch />
      <SettingsPanel />
      <Suspense fallback={null}><LAZY_GENERATION_FX /></Suspense>
      <Suspense fallback={null}><LAZY_API_EMBED_PANEL /></Suspense>
      <KeyboardCheatsheet />
      <ScrollToTop />
      <HelpFab />
      <ConnectionIndicator />
      <VoiceQuickToggle />
      <AuroraCommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        onSelect={(id) => {
          if (id === 'voice') { setVoiceOverlayOpen(true); return }
          setActiveModule(id)
        }}
      />

      {voiceOverlayOpen && (() => {
        const skin = readUiSkin()
        const VoiceOverlay =
          skin === 'aurora_v1' ? VoiceOverlayV1 :
          skin === 'aurora_v3' ? VoiceOverlayV3 :
          VoiceOverlayManga
        return (
          <div style={{
            position: 'fixed', inset: 0, zIndex: 200,
            background: 'var(--bg, #0c0a09)',
          }}>
            <Suspense fallback={
              <div style={{
                width: '100%', height: '100%',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: 'var(--fg-dim, #aaa)',
                fontFamily: 'var(--font-display, serif)', fontStyle: 'italic', fontSize: 24,
              }}>Aurora s'éveille…</div>
            }>
              <VoiceOverlay onClose={() => setVoiceOverlayOpen(false)} />
            </Suspense>
          </div>
        )
      })()}

      {/* Cowork takeover overlay — mounted at the App root so it works
          regardless of whether SpatialCanvas (desktop manga) or MobileGrimoire
          (small device) is the active shell. The store drives open/close. */}
      <CoworkRootMount focusMode={focusMode} onCloseFocusMode={() => setFocusMode(false)} />

      {/* Always-visible floating Cowork launcher (top-right). Works from
          any shell, any module, any device. */}
      <CoworkFloatingButton />

      {/* Silent boot scan : detects installed browsers + current browser,
          persists in localStorage so Settings can recommend instantly. */}
      <CoworkBootScan />
    </>
  )
}

function CoworkFloatingButton() {
  const isOpen = useCoworkStore((s) => s.isOpen)
  const toggle = useCoworkStore((s) => s.toggle)
  const { extConnected, mobileConnected, extCount, mobileEvents } = useCoworkConnectionStatus()

  if (isOpen) return null
  // v82aa : hide on aurora skins where cowork is reachable via the
  // Sidebar (aurora_v1) and the ⌘K palette + ⌘` shortcut (both v1+v3).
  // The floating purple button on top-right was a visible duplicate the
  // user complained about. Manga keeps it because SpatialCanvas's dock
  // doesn't surface cowork prominently.
  if (readUiSkin() !== 'manga') return null

  const dot = (color: string, on: boolean, label: string, count?: number) => (
    <span
      title={`${label} ${on ? 'connecte' : 'hors ligne'}${count !== undefined ? ` · ${count}` : ''}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 3,
      }}
    >
      <span
        style={{
          width: 6, height: 6, borderRadius: 6, background: on ? color : 'rgba(255,255,255,0.2)',
          boxShadow: on ? `0 0 6px ${color}` : 'none',
        }}
      />
      {count !== undefined && count > 0 && (
        <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.9)', fontWeight: 700, lineHeight: 1 }}>
          {count}
        </span>
      )}
    </span>
  )

  return (
    <button
      type="button"
      onClick={() => toggle()}
      title="Cowork — Aurora prend la main"
      style={{
        position: 'fixed',
        top: 16,
        right: 16,
        zIndex: 150,
        display: 'inline-flex',
        alignItems: 'center',
        gap: 8,
        padding: '8px 14px',
        borderRadius: 999,
        background: 'linear-gradient(135deg, #8b5cf6, #6366f1)',
        color: '#fff',
        fontSize: 12,
        fontWeight: 600,
        border: '1px solid rgba(255,255,255,0.18)',
        boxShadow: '0 6px 20px rgba(99,102,241,0.45)',
        cursor: 'pointer',
      }}
    >
      <Sparkles size={13} strokeWidth={2.4} />
      Cowork
      <span style={{ display: 'inline-flex', gap: 3, alignItems: 'center', marginLeft: 4 }}>
        {dot('#22d3ee', extConnected, 'Extension navigateur', extCount)}
        {dot('#a78bfa', mobileConnected, 'Pont mobile · evts <60s', mobileEvents)}
      </span>
    </button>
  )
}

// ---------------------------------------------------------------------------
// useCoworkConnectionStatus — polls the bridge for active extensions and
// mobile clients. Refreshes every 6s. Used by the floating Cowork button to
// surface connection state visually.
// ---------------------------------------------------------------------------

function useCoworkConnectionStatus() {
  const [extConnected, setExtConnected] = useState(false)
  const [mobileConnected, setMobileConnected] = useState(false)
  const [extCount, setExtCount] = useState(0)
  const [mobileEvents, setMobileEvents] = useState(0)

  useEffect(() => {
    let cancelled = false
    const tick = async () => {
      try {
        const { getBridgeUrl } = await import('./utils/runtime')
        const root = getBridgeUrl()
        const [extResp, mobileResp] = await Promise.allSettled([
          fetch(`${root}/api/cowork/extension/list`, { signal: AbortSignal.timeout(4000) }),
          fetch(`${root}/api/cowork/mobile/events`, { signal: AbortSignal.timeout(4000) }),
        ])
        if (cancelled) return
        if (extResp.status === 'fulfilled' && extResp.value.ok) {
          const d = await extResp.value.json() as { extensions?: Array<unknown> }
          const n = d.extensions?.length ?? 0
          setExtConnected(n > 0)
          setExtCount(n)
        }
        if (mobileResp.status === 'fulfilled' && mobileResp.value.ok) {
          const d = await mobileResp.value.json() as { events?: Array<{ at?: number }> }
          const events = d.events ?? []
          const last = events.length ? events[events.length - 1] : null
          const fresh = last?.at ? (Date.now() / 1000 - last.at) < 300 : false
          setMobileConnected(fresh)
          // Count events in the last 60s as "in-flight" inbound activity
          const recent = events.filter((e) => e.at && (Date.now() / 1000 - e.at) < 60).length
          setMobileEvents(recent)
        }
      } catch { /* offline */ }
    }
    tick()
    const id = window.setInterval(tick, 6000)
    return () => { cancelled = true; window.clearInterval(id) }
  }, [])

  return { extConnected, mobileConnected, extCount, mobileEvents }
}

// ---------------------------------------------------------------------------
// Boot scan — at app startup, silently scan installed browsers via the
// bridge and persist the recommendation in localStorage so the Settings
// dialog shows it instantly without re-scanning every time.
// ---------------------------------------------------------------------------

function CoworkBootScan() {
  useEffect(() => {
    // v83 — cowork is app-only ; skip the browser scan entirely in web.
    if (!isTauriRuntime()) return
    let cancelled = false
    const run = async () => {
      try {
        const [installed, current] = await Promise.all([
          scanInstalledBrowsers(),
          Promise.resolve(detectCurrentBrowser()),
        ])
        if (cancelled) return
        const payload = {
          at: Date.now(),
          current: current.id,
          installed: installed.map((b) => b.id),
          recommendation: current.id !== 'unknown' ? current.id : (installed[0]?.id ?? 'chrome'),
        }
        try {
          localStorage.setItem('cowork:browser-scan', JSON.stringify(payload))
        } catch { /* quota */ }
      } catch { /* silently fail */ }
    }
    // Small delay so we don't slow down boot; the value is needed when user
    // opens Settings, not at first paint.
    const id = window.setTimeout(run, 1500)
    return () => { cancelled = true; window.clearTimeout(id) }
  }, [])
  return null
}

// v81s: skin-aware cowork launcher (the *actual* live mount point — the
// twin in AppShell.tsx turned out to be dead code, never imported).
// Manga renders the full CoworkOverlay (events, plan, audit, ConfirmDialog).
// Aurora V1/V3 swap the surface with their skin chrome — they still talk
// to the same useCoworkStore, but skin-specific orchestration sub-panels
// haven't been ported yet (the "Console technique" button inside V1/V3
// jumps back to the manga overlay if needed).
// v82lk4 : helper retry pour lazy() — si le dynamic import échoue
// (cache stale, network blip, HMR mid-build), on attend 200ms et on
// retente UNE fois avant de propager l'erreur à SkinSafeView. Évite
// le flash "Skin Cowork Ricochet indisponible" sur transient.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function lazyRetry<T extends { default: React.ComponentType<any> }>(factory: () => Promise<T>) {
  return lazy(() =>
    factory().catch((err: unknown) => {
      console.warn('[aurora] lazy import failed, retrying once:', err)
      return new Promise<T>((resolve, reject) => {
        setTimeout(() => factory().then(resolve, reject), 200)
      })
    }),
  )
}
// v83 — single dedicated coworker workspace (replaces the decorative V1/V3
// radar HUDs as the cowork surface). The old AuroraV1/V3CoworkView files stay
// in the repo but are no longer the live mount.
const LAZY_COWORK_DEDICATED = lazyRetry(() => import('./views/AuroraCoworkView'))

function CoworkRootMount({ focusMode, onCloseFocusMode }: { focusMode: boolean; onCloseFocusMode: () => void }) {
  const isCoworkOpen = useCoworkStore((s) => s.isOpen)
  const closeCowork = useCoworkStore((s) => s.close)
  const open = isCoworkOpen || focusMode

  if (!open) return null

  const handleClose = () => {
    if (isCoworkOpen) closeCowork()
    if (focusMode) onCloseFocusMode()
  }

  // v83 — the dedicated coworker workspace is now THE cowork surface on every
  // skin (the decorative V1/V3 radar HUDs no longer hide the real console).
  // AuroraCoworkView is a full-window workspace built on the proven pipeline ;
  // it embeds the complete technical console so ZERO feature is lost.
  return (
    <SkinSafeView fallback={() => <CoworkOverlay open={open} onClose={handleClose} />} skinLabel="Cowork">
      <Suspense fallback={null}>
        <LAZY_COWORK_DEDICATED open={open} onClose={handleClose} />
      </Suspense>
    </SkinSafeView>
  )
}

// v82lk6 : dock minimal flottant pour aurora_v3 (Ricochet). Le design
// d'origine voulait "zéro shell partagé" — chaque module rendu fullscreen
// sans nav. Mais avec ~10 modules et seulement quelques uns portés
// complètement vers V3, l'utilisateur se retrouve coincé sans moyen de
// changer de module ou de revenir à Editorial. Ce dock est posé au-dessus
// du module en bas-centre, paper-style, avec :
//   • module shortcuts (chat, image, video, code, draw, 3d, cyber, learn)
//   • bouton "Editorial v1" pour bascule rapide vers le skin complet
// Pas tap-able sur les modules eux-mêmes (pointer-events isolés sur dock).
const V3_DOCK_MODULES: ReadonlyArray<{ id: ModuleId; label: string; glyph: string }> = [
  { id: 'conversation', label: 'Chat',     glyph: '◐' },
  { id: 'image',        label: 'Image',    glyph: '◉' },
  { id: 'code',         label: 'Code',     glyph: '⌘' },
  { id: 'drawing',      label: 'Dessin',   glyph: '墨' },
  { id: '3d',           label: '3D',       glyph: '◇' },
  { id: 'learning',     label: 'Academy',  glyph: '∎' },
  { id: 'cyber',        label: 'Cyber',    glyph: '※' },
]
function V3FloatingDock({ activeModule, setActiveModule, teamOpen, onToggleTeam }: {
  activeModule: ModuleId
  setActiveModule: (id: ModuleId) => void
  teamOpen: boolean
  onToggleTeam: () => void
}) {
  return (
    <div className="aurora-v3-dock" role="navigation" aria-label="Modules Aurora">
      {V3_DOCK_MODULES.map((m) => {
        const active = !teamOpen && activeModule === m.id
        return (
          <button
            key={m.id}
            type="button"
            onClick={() => setActiveModule(m.id)}
            title={m.label}
            aria-label={m.label}
            aria-current={active ? 'page' : undefined}
            className={`aurora-v3-dock-btn ${active ? 'is-active' : ''}`}
          >
            <span aria-hidden="true" className="aurora-v3-dock-glyph">{m.glyph}</span>
            <span className="aurora-v3-dock-label">{m.label}</span>
          </button>
        )
      })}
      <span className="aurora-v3-dock-sep" aria-hidden="true" />
      {/* v82lk9 : bouton TEAM ouvre AuroraV3TeamManager (8 agents IA) */}
      <button
        type="button"
        onClick={onToggleTeam}
        title="Manager d'équipe — voir et configurer les 8 agents IA"
        aria-label="Ouvrir le Manager d'équipe"
        aria-current={teamOpen ? 'page' : undefined}
        className={`aurora-v3-dock-btn ${teamOpen ? 'is-active' : ''}`}
      >
        <span aria-hidden="true" className="aurora-v3-dock-glyph">★</span>
        <span className="aurora-v3-dock-label">Team</span>
      </button>
      <span className="aurora-v3-dock-sep" aria-hidden="true" />
      <button
        type="button"
        onClick={() => {
          try {
            window.localStorage.setItem('aurora-ui-skin', 'aurora_v1')
          } catch { /* noop */ }
          // reloadFresh : cache-bust + purge caches → pas d'index.html périmé
          // ⇒ pas de « charge à l'infini » en repassant sur Editorial.
          try { reloadFresh() } catch { window.location.reload() }
        }}
        title="Repasser sur Editorial (skin complet, tous modules)"
        aria-label="Repasser sur Editorial"
        className="aurora-v3-dock-escape"
      >
        ↩ <span className="aurora-v3-dock-label">EDITORIAL</span>
      </button>
    </div>
  )
}

// v82lk9 : wrapper pour le rendu aurora_v3 — gère le toggle TeamManager,
// le mascot floating, et le module fade-in. Sortie en composant séparé
// pour pouvoir utiliser useState (teamOpen + mascotState) dont
// ShellRouter aurait besoin sinon en plus de ses autres états.
function V3DesktopWrapper(props: ShellRouterProps) {
  const [teamOpen, setTeamOpen] = useState(false)
  // mascotState peut être driven plus tard par les modules eux-mêmes
  // (générer un event 'aurora-agent-state' avec detail.state). Pour
  // l'instant : idle par défaut, le user peut tester les autres états
  // depuis le Team Manager via les preview buttons.
  const [mascotState, setMascotState] = useState<'idle' | 'thinking' | 'working' | 'done' | 'error'>('idle')

  useEffect(() => {
    const onState = (ev: Event) => {
      const detail = (ev as CustomEvent<{ state?: typeof mascotState }>).detail
      if (detail?.state) setMascotState(detail.state)
    }
    window.addEventListener('aurora-agent-state', onState)
    return () => window.removeEventListener('aurora-agent-state', onState)
  }, [])

  // v82lke : module content padding-bottom pour pas être caché
  // sous la scene-stage (280px desktop, 200px mobile). Quand le user
  // est dans Team Manager, on cache la scène (pas pertinente).
  // v82s-studio fix : wrapper bg en transparent (au lieu de cream
  // !important) pour que la couleur du module choisi s'étende jusqu'en
  // bas de l'écran et ne soit pas coupée par un strip beige sous la
  // scène-stage. Le body en index.html porte déjà la couleur de fond
  // dark de référence ; le backdrop V3 décore au-dessus.
  return (
    <div style={{
      width: '100%', height: '100vh', minHeight: '100vh',
      background: 'transparent', color: 'var(--fg, #1c1614)',
      overflow: 'hidden', position: 'relative',
    }}>
      <div className="aurora-v3-backdrop" aria-hidden="true" />
      <div
        key={teamOpen ? 'team' : 'modules'}
        className="aurora-v3-module"
        style={{
          // v82s-studio fix #3 : 84px = hauteur du dock flottant
          // (≈50px) + offset bottom (16px) + marge respiratoire (18px).
          // Plus de strip 180px qui exposait le wrapper cream — le
          // dock flotte sur la fin du module sans cacher le contenu.
          paddingBottom: teamOpen ? 0 : 84,
          background: 'var(--bg, #0e0e0e)',
        }}
      >
        {teamOpen ? <AuroraV3TeamManager /> : <PersistentModuleHost active={props.activeModule} render={props.renderModule} />}
      </div>

      {/* v82s-studio iter12 : la scène-personnage est REVENUE — l'agent du
          module EST dans son décor de travail (Lyra à son bureau, Atlas sur
          chantier…), mais avec les avatars SVG VIVANTS de la v10 (respiration,
          clignement, mèches qui suivent) au lieu d'images statiques, et la
          bande scène est REMONTÉE au-dessus du dock flottant (CSS
          .aurora-v3-scene { bottom: 64px }) + pointer-events:none de bout en
          bout → la figure « pose » au-dessus du dock, sans rien tronquer ni
          voler de clic. Clic sur le personnage : voir le bouton « Team » du
          dock (la scène est décorative). */}
      {!teamOpen && (
        <div className="aurora-v3-scene">
          <Suspense fallback={null}>
            <LAZY_AGENT_SCENE
              moduleId={props.activeModule}
              state={mascotState}
              voiceActive={false}
              onAgentClick={() => setTeamOpen(true)}
            />
          </Suspense>
        </div>
      )}

      {/* Quand TeamManager est ouvert, on garde un mascot mini en bas
          pour pouvoir revenir à un module. */}
      {teamOpen && (
        <div className="aurora-v3-mascot-floater" style={{
          position: 'fixed', bottom: 78, right: 16, zIndex: 850,
        }}>
          <AuroraAgentMascot
            moduleId="conversation"
            state="idle"
            size={76}
            showLabel={false}
            showScene={false}
            onClick={() => setTeamOpen(false)}
          />
        </div>
      )}

      <V3FloatingDock
        activeModule={props.activeModule}
        setActiveModule={(id) => { setTeamOpen(false); props.setActiveModule(id) }}
        teamOpen={teamOpen}
        onToggleTeam={() => setTeamOpen((v) => !v)}
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// ShellRouter — picks MobileGrimoire vs SpatialCanvas based on device detection.
// The active sub-module (opened from Create / Canvas / Chat on mobile) still
// mounts via `renderModule` in an overlay so mobile users can access the full
// desktop module while we progressively mobile-adapt each one.
// ---------------------------------------------------------------------------

type ShellRouterProps = {
  activeModule: ModuleId
  focusMode: boolean
  setActiveModule: (id: ModuleId) => void
  setFocusMode: (v: boolean) => void
  getModuleStats: (id: ModuleId) => { value: string | number; sublabel?: string; tags?: string[]; caption?: string }
  renderModule: (id: ModuleId) => ReactNode
  openVoiceOverlay?: () => void
}

function ShellRouter(props: ShellRouterProps) {
  const device = useDeviceKind()
  const isSmall = device.kind === 'mobile' || device.kind === 'tablet'

  // On a small device, the six Grimoire pages ARE the shell. Opening a
  // sub-module (image/video/code/drawing/cyber/3d) from Create/Canvas flips
  // `focusMode` on and we overlay the desktop view full-screen until dismissed.
  const [subModuleOpen, setSubModuleOpen] = useState<ModuleId | null>(null)

  useEffect(() => {
    if (!isSmall) return
    const NATIVE_MOBILE: ModuleId[] = ['conversation', 'learning', 'voice']
    if (NATIVE_MOBILE.includes(props.activeModule)) {
      setSubModuleOpen(null)
      return
    }
    // Any other module on mobile triggers the sub-module overlay
    setSubModuleOpen(props.activeModule)
  }, [props.activeModule, isSmall])

  if (!isSmall) {
    const skin = readUiSkin()
    if (skin === 'aurora_v4') {
      return (
        <Suspense fallback={
          <div style={{
            position: 'fixed', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: '#05070D', color: '#8B93A7', fontSize: 14,
          }}>Aurora OS s'éveille…</div>
        }>
          <LAZY_V4_SHELL
            activeModule={props.activeModule}
            onActivateModule={(id) => {
              if (id === 'cowork') {
                useCoworkStore.getState().open()
                return
              }
              if (id === 'voice') {
                props.openVoiceOverlay?.()
                return
              }
              props.setActiveModule(id as ModuleId)
            }}
          >
            <PersistentModuleHost active={props.activeModule} render={props.renderModule} />
          </LAZY_V4_SHELL>
        </Suspense>
      )
    }
    if (skin === 'aurora_v1') {
      return (
        <AuroraV1AppShell
          activeModule={props.activeModule}
          onActivateModule={(id) => {
            if (id === 'cowork') {
              useCoworkStore.getState().open()
              return
            }
            if (id === 'voice') {
              // v82aq : voice n'est pas un module-page (appStore.setActiveModule
              // remap 'voice' → 'conversation' historiquement). On ouvre
              // VoiceCopilotView comme un overlay fullscreen via voiceOverlay
              // store, comme Cowork.
              props.openVoiceOverlay?.()
              return
            }
            props.setActiveModule(id as ModuleId)
          }}
        >
          <PersistentModuleHost active={props.activeModule} render={props.renderModule} />
        </AuroraV1AppShell>
      )
    }
    if (skin === 'aurora_v3') {
      // v82lk5 : fix "page bug — bas noir" sur aurora_v3.
      //  • height: 100% s'effondrait à hauteur-de-contenu (320px) parce
      //    que le parent ShellRouter n'a pas de height explicite, donc
      //    100% résolvait à `auto`. Résultat : sous le ChatView le user
      //    voyait le fallback #0c0a09 dark sur tout le bas du viewport.
      //  • Fallback bg #0c0a09 dark était mal choisi : aurora_v3 (Ricochet)
      //    a un design paper-notebook hardcodé (#f0e9d9 dans
      //    AuroraV3ChatView). Mettre la même teinte en fallback colle
      //    naturellement avec le contenu et masque l'écart.
      // Désormais : 100vh ⇒ toujours plein écran ; bg paper ⇒ pas de
      // void noir si le module ne fill pas (cas mobile / loader / route
      // vide / scroll bounce).
      return <V3DesktopWrapper {...props} />
    }
    return (
      <SpatialCanvas
        activeModule={props.activeModule}
        focusMode={props.focusMode}
        setActiveModule={props.setActiveModule}
        setFocusMode={props.setFocusMode}
        getModuleStats={props.getModuleStats}
        renderModule={props.renderModule}
      />
    )
  }

  return (
    <>
      <Suspense fallback={null}>
        <MobileShell />
      </Suspense>
      {subModuleOpen && (
        <div className="fixed inset-0 z-[120] flex flex-col bg-[var(--color-aurora-bg,_#0a0a0c)]">
          <div className="flex items-center justify-between border-b border-white/10 px-3 py-2 shrink-0">
            <button
              onClick={() => { setSubModuleOpen(null); props.setActiveModule('conversation') }}
              className="flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.06] px-3 py-1.5 text-[11px] text-white/70 hover:bg-white/[0.12]"
            >← Retour au grimoire</button>
            <span className="text-[11px] uppercase tracking-[0.18em] text-white/50">{subModuleOpen}</span>
            <span className="w-[120px]" />
          </div>
          <div className="flex-1 overflow-auto">
            {props.renderModule(subModuleOpen)}
          </div>
        </div>
      )}
    </>
  )
}
