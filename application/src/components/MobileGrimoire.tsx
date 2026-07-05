/**
 * MobileGrimoire — mobile/tablet shell for juan of bike IA.
 * Metaphor: a living grimoire. Each page = a module adapted to small screens.
 * Swipe vertically between pages, companion orb floats, spine nav at bottom.
 *
 * Pages wire REAL stores (chat, academy, gamification, avatars) and REAL
 * services (conversationOrchestrator, characterForge, speakify). Nothing mock.
 */
import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useAcademyStore } from '../stores/academyStore'
import { useAppStore } from '../stores/appStore'
import { useChatStore } from '../stores/chatStore'
import { useGamificationStore } from '../stores/gamificationStore'
import { runConversationTurn } from '../services/conversationOrchestrator'
import { speakify } from '../utils/speakify'
import MarkdownPro from './MarkdownPro'
import { ensurePushPermission, pushPermissionState, subscribe as subscribeNotif } from '../utils/notificationBus'
import { detectInstallState, type InstallState } from '../utils/device'
import { useForgeQueueStore } from '../stores/forgeQueueStore'
import { useModuleDraftsStore } from '../stores/moduleDraftsStore'

const CharacterForgeOverlay = lazy(() => import('../views/CharacterForgeOverlay'))
const VoiceCopilotView = lazy(() => import('../views/VoiceCopilotView'))
const StudioRoster = lazy(() => import('./studio/Roster'))
const FightCloudBadge = lazy(() => import('./studio/FightCloudBadge'))

// Open-forge broadcast: any child page can dispatch this custom event and the
// root shell opens the Forge overlay with the supplied prompt. Keeps the
// overlay mounted above all pages so navigating doesn't unmount it (the queue
// keeps running in the background either way, but this way the progress UI
// stays visible even if the user flips to Académie while it thinks).
export function requestOpenForge(prompt: string = '') {
  window.dispatchEvent(new CustomEvent('aurora:open-forge', { detail: { prompt } }))
}

type Character = 'natsu' | 'lucy'
const PORTRAITS: Record<Character, string> = {
  natsu: '/fairy/natsu.png',
  lucy:  '/fairy/lucy.png',
}
function readCharacter(): Character {
  try {
    const v = window.localStorage.getItem('ft-who')
    return v === 'lucy' ? 'lucy' : 'natsu'
  } catch { return 'natsu' }
}

// ---------------------------------------------------------------------------
// Pages definition
// ---------------------------------------------------------------------------

type PageId = 'home' | 'chat' | 'create' | 'academy' | 'gallery' | 'canvas' | 'team'

const PAGES: { id: PageId; chapter: string; title: string }[] = [
  { id: 'home',    chapter: 'I · COUVERTURE',    title: 'GRIMOIRE' },
  { id: 'team',    chapter: 'II · COMPAGNIE',    title: 'L’ÉQUIPE' },
  { id: 'chat',    chapter: 'III · INCANTATIONS', title: 'CHAT' },
  { id: 'create',  chapter: 'IV · SORTILÈGES',   title: 'CRÉATION' },
  { id: 'academy', chapter: 'V · ANNALES',       title: 'ACADÉMIE' },
  { id: 'gallery', chapter: 'VI · INVOCATIONS',  title: 'GALERIE' },
  { id: 'canvas',  chapter: 'VII · CARTE',       title: 'CANVAS' },
]

// ---------------------------------------------------------------------------
// Root shell
// ---------------------------------------------------------------------------

export default function MobileGrimoire() {
  // Persist the current page so mobile Safari's aggressive BFCache / tab
  // reload doesn't dump users back onto the cover. Clamped to page range on
  // hydration in case the saved value came from an older build.
  const [pageIdx, setPageIdx] = useState<number>(() => {
    if (typeof window === 'undefined') return 0
    try {
      const n = parseInt(window.localStorage.getItem('ft-grimoire-page') || '0', 10)
      return Number.isFinite(n) && n >= 0 ? n : 0
    } catch { return 0 }
  })
  useEffect(() => {
    try { window.localStorage.setItem('ft-grimoire-page', String(pageIdx)) } catch { /* noop */ }
  }, [pageIdx])
  const [turning, setTurning] = useState(false)
  const [bubble, setBubble] = useState<string | null>(
    'Bonjour. Deux doigts pour changer de page, un doigt pour scroller.',
  )
  const [notifs, setNotifs] = useState<Array<{ id: number; seal: string; text: string; tone?: 'ok'|'err'|'info' }>>([])
  const [voiceOpen, setVoiceOpen] = useState(false)
  const [forgeOpen, setForgeOpen] = useState(false)
  const [forgePrompt, setForgePrompt] = useState<string>('')
  const [who, setWho] = useState<Character>(readCharacter)
  const queueJobs = useForgeQueueStore((s) => s.jobs)
  const activeForgeJobs = queueJobs.filter((j) => j.status === 'running' || j.status === 'queued')
  const pendingForgeResults = queueJobs.filter((j) => j.status === 'done' && !j.saved).length
  useEffect(() => {
    const sync = () => setWho(readCharacter())
    window.addEventListener('storage', sync)
    const poll = window.setInterval(sync, 1000)
    return () => { window.removeEventListener('storage', sync); window.clearInterval(poll) }
  }, [])

  const rootRef = useRef<HTMLDivElement>(null)
  const bubbleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Two-finger swipe tracking. Scroll with one finger stays native.
  // We only arm the gesture AFTER two fingers have been down for 80+ ms (so
  // the user didn't just brush the screen), and only commit the page turn if
  // both fingers moved together at least 70px in a consistent direction.
  const gestureRef = useRef<{
    active: boolean
    armed: boolean
    startT: number
    startY: number
    startX: number
    maxTouches: number
  }>({ active: false, armed: false, startT: 0, startY: 0, startX: 0, maxTouches: 0 })
  const armTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const setActiveModule = useAppStore((s) => s.setActiveModule)

  // Companion line per page
  useEffect(() => {
    // v82n1 : `forge` removed (not in PageId), `gallery` added so the
    // record covers every PAGES entry. Was causing a runtime
    // `undefined` bubble on the gallery page.
    const lines: Record<PageId, string> = {
      home:    'Le grimoire te reconnaît. Choisis un sort.',
      team:    'Sept compagnons. Tape un visage pour entrer dans son module.',
      chat:    'Parle-moi. Je réponds sur la plume.',
      create:  'Quatre arts. Lequel veux-tu ouvrir ?',
      academy: 'Tes quêtes en cours attendent.',
      gallery: 'Tes invocations passées reposent ici.',
      canvas:  'Vue complète du royaume.',
    }
    setBubble(lines[PAGES[pageIdx].id])
    if (bubbleTimerRef.current) clearTimeout(bubbleTimerRef.current)
    bubbleTimerRef.current = setTimeout(() => setBubble(null), 4200)
    return () => { if (bubbleTimerRef.current) clearTimeout(bubbleTimerRef.current) }
  }, [pageIdx])

  // Listen to `aurora:open-forge` events dispatched by any child page.
  useEffect(() => {
    const onOpen = (e: Event) => {
      const detail = (e as CustomEvent<{ prompt?: string }>).detail || {}
      setForgePrompt(detail.prompt || '')
      setForgeOpen(true)
    }
    window.addEventListener('aurora:open-forge', onOpen)
    return () => window.removeEventListener('aurora:open-forge', onOpen)
  }, [])

  // Real event-driven ink notifications — subscribe to the bus, no random cycle.
  useEffect(() => {
    const unsub = subscribeNotif((ev) => {
      setNotifs((n) => [
        ...n,
        {
          id: ev.id,
          seal: ev.seal || (ev.tone === 'err' ? '✖' : ev.tone === 'ok' ? '✦' : '·'),
          text: ev.body ? `${ev.title} — ${ev.body}` : ev.title,
          tone: ev.tone,
        },
      ])
      // Auto-dismiss after 5s for non-error, 9s for errors
      const ttl = ev.tone === 'err' ? 9000 : 5000
      window.setTimeout(() => setNotifs((n) => n.filter((x) => x.id !== ev.id)), ttl)
    })
    // NOTE: notification permission is NOT requested on mount — browsers
    // (Chrome/Safari/Brave/Edge) only honor requestPermission() from a user
    // gesture. A visible chip below lets the user opt in with a tap.
    return () => { unsub() }
  }, [])

  // Track system push permission + install state (iOS PWA detection)
  const [notifPerm, setNotifPerm] = useState<ReturnType<typeof pushPermissionState>>(pushPermissionState)
  const [install, setInstall] = useState<InstallState>(detectInstallState)
  const [iosDialogOpen, setIosDialogOpen] = useState(false)
  const [iosDialogDismissed, setIosDialogDismissed] = useState<boolean>(() => {
    try { return localStorage.getItem('ios_install_dismissed') === '1' } catch { return false }
  })
  useEffect(() => {
    const sync = () => {
      setNotifPerm(pushPermissionState())
      setInstall(detectInstallState())
    }
    window.addEventListener('focus', sync)
    const iv = window.setInterval(sync, 3000)
    return () => { window.removeEventListener('focus', sync); window.clearInterval(iv) }
  }, [])
  const askNotif = async () => {
    // iOS Safari/Chrome: Notification API only works when installed as PWA.
    // Show the install guide instead of a useless permission prompt.
    if (install.platform === 'ios' && !install.standalone) {
      setIosDialogOpen(true)
      return
    }
    // CRITICAL: call Notification.requestPermission() SYNCHRONOUSLY inside
    // this user-gesture handler. Any `await` before the call makes some
    // browsers (Chromium pre-2023, all Safari versions) silently ignore it.
    if (typeof Notification === 'undefined') {
      setBubble('Ce navigateur ne supporte pas les notifications système.')
      return
    }
    try {
      const immediate = Notification.requestPermission((p) => {
        // Legacy callback-style Safari
        setNotifPerm(p)
        setBubble(p === 'granted' ? 'Notifications activées ✓' : p === 'denied' ? 'Notifications refusées' : '…')
      })
      if (immediate && typeof (immediate as Promise<NotificationPermission>).then === 'function') {
        const perm = await (immediate as Promise<NotificationPermission>)
        setNotifPerm(perm)
        setBubble(perm === 'granted' ? 'Notifications activées ✓' : perm === 'denied' ? 'Notifications refusées par le navigateur' : 'Permission en attente…')
      }
    } catch (err) {
      setBubble(`Erreur notif : ${err instanceof Error ? err.message : String(err)}`)
    }
  }
  const dismissIos = () => {
    setIosDialogDismissed(true)
    setIosDialogOpen(false)
    try { localStorage.setItem('ios_install_dismissed', '1') } catch { /* ignore */ }
  }

  const turnTo = useCallback((idx: number) => {
    if (idx < 0 || idx >= PAGES.length) return
    setTurning(true)
    setPageIdx(idx)
    window.setTimeout(() => setTurning(false), 700)
  }, [])

  // Two-finger gesture for page turn. One-finger is always left untouched so
  // native scroll works inside any `.g-content-scroll` container.
  //
  // Robustness:
  //  - touches.length must reach 2 and stay ≥ 2 for at least 80ms before we
  //    arm (avoids brushes / accidental second-finger glances)
  //  - we track maxTouches across the gesture; anything below 2 aborts
  //  - at touch-end both fingers must still be present (releasing only one
  //    finger with the other still down does NOT trigger a page turn)
  //  - minimum 70px movement, clearly dominant in one axis (> 1.4×)
  const onTouchStart = (e: React.TouchEvent) => {
    if (e.touches.length >= 2) {
      const t0 = e.touches[0]
      const t1 = e.touches[1]
      gestureRef.current = {
        active: true, armed: false,
        startT: Date.now(),
        startY: (t0.clientY + t1.clientY) / 2,
        startX: (t0.clientX + t1.clientX) / 2,
        maxTouches: e.touches.length,
      }
      if (armTimerRef.current) clearTimeout(armTimerRef.current)
      armTimerRef.current = setTimeout(() => {
        if (gestureRef.current.active) gestureRef.current.armed = true
      }, 80)
    } else {
      gestureRef.current.active = false
      gestureRef.current.armed = false
    }
  }
  const onTouchMove = (e: React.TouchEvent) => {
    if (!gestureRef.current.active) return
    gestureRef.current.maxTouches = Math.max(gestureRef.current.maxTouches, e.touches.length)
    // If user lifted one finger before we committed, abandon immediately
    if (e.touches.length < 2) {
      gestureRef.current.active = false
      gestureRef.current.armed = false
      if (armTimerRef.current) { clearTimeout(armTimerRef.current); armTimerRef.current = null }
      return
    }
    // Prevent browser scroll only while a 2-finger swipe is armed
    if (e.touches.length >= 2 && gestureRef.current.armed) {
      if (e.cancelable) e.preventDefault()
    }
  }
  const onTouchEnd = (e: React.TouchEvent) => {
    if (!gestureRef.current.active) return
    const wasArmed = gestureRef.current.armed
    gestureRef.current.active = false
    gestureRef.current.armed = false
    if (armTimerRef.current) { clearTimeout(armTimerRef.current); armTimerRef.current = null }
    if (!wasArmed) return
    // Require the user to lift both fingers together for the page turn — a
    // single-finger release with the other still down does NOT count.
    if (e.changedTouches.length < 2) return
    const ct = e.changedTouches
    const endY = (ct[0].clientY + ct[1].clientY) / 2
    const endX = (ct[0].clientX + ct[1].clientX) / 2
    const dy = endY - gestureRef.current.startY
    const dx = endX - gestureRef.current.startX
    const dur = Date.now() - gestureRef.current.startT
    if (dur > 1400) return // gesture too long, abandon
    const MIN = 70
    if (Math.abs(dy) > MIN && Math.abs(dy) > Math.abs(dx) * 1.4) {
      if (dy < 0) turnTo(pageIdx + 1)
      else        turnTo(pageIdx - 1)
    } else if (Math.abs(dx) > MIN && Math.abs(dx) > Math.abs(dy) * 1.4) {
      if (dx < 0) turnTo(pageIdx + 1)
      else        turnTo(pageIdx - 1)
    }
  }

  const current = PAGES[pageIdx]

  return (
    <div className="g-root" ref={rootRef}
      onTouchStart={onTouchStart} onTouchMove={onTouchMove} onTouchEnd={onTouchEnd}>
      <GrimoireParticles />

      {/* Top band */}
      <div className="g-topband">
        <span className="chapter">{current.chapter}</span>
        <span className="pagenum">
          {String(pageIdx + 1).padStart(2, '0')} / {String(PAGES.length).padStart(2, '0')}
        </span>
      </div>

      {/* Sticky iOS install banner — iOS Safari/Chrome can only expose the
          Notification API once the page lives on the home screen. Apple's
          rule, not ours. Banner sits ABOVE everything, impossible to miss. */}
      {install.platform === 'ios' && !install.standalone && !iosDialogDismissed && (
        <div
          onClick={() => setIosDialogOpen(true)}
          style={{
            position: 'fixed', top: 0, left: 0, right: 0, zIndex: 160,
            background: 'linear-gradient(180deg, var(--g-gold) 0%, var(--g-gold-bright) 100%)',
            color: 'var(--g-ink)', borderBottom: '3px solid var(--g-ink)',
            padding: '10px 14px 8px',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10,
            fontFamily: 'Inter, system-ui, sans-serif', fontSize: 12, fontWeight: 600,
            boxShadow: '0 4px 18px rgba(0,0,0,0.4)',
            animation: 'g-bubble-in 0.4s cubic-bezier(.5,0,.3,1.5)',
          }}>
          <span style={{ flex: 1, lineHeight: 1.3 }}>
            📲 <b>Installe l'app</b> pour recevoir les notifications de fin de génération
            <span style={{ display: 'block', fontSize: 10, fontWeight: 400, opacity: 0.8 }}>
              iOS bloque les notifications tant que la page n'est pas sur l'écran d'accueil
            </span>
          </span>
          <button
            onClick={(e) => { e.stopPropagation(); setIosDialogOpen(true) }}
            style={{
              padding: '6px 10px',
              background: 'var(--g-blood)', color: 'var(--g-paper)',
              border: '2px solid var(--g-ink)', boxShadow: '2px 2px 0 var(--g-ink)',
              fontFamily: 'Bangers, cursive', fontSize: 11, letterSpacing: 1.5,
              borderRadius: 4, cursor: 'pointer',
            }}>
            COMMENT
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); dismissIos() }}
            aria-label="Ignorer"
            style={{
              width: 22, height: 22, borderRadius: '50%',
              background: 'transparent', color: 'var(--g-ink)',
              border: '1.5px solid var(--g-ink)', cursor: 'pointer',
              fontSize: 12, fontWeight: 800, lineHeight: 1,
            }}>
            ×
          </button>
        </div>
      )}

      {/* Notification chip — shape depends on platform:
          • iOS non-standalone → offers the "Ajouter à l'écran d'accueil" guide
          • everywhere else with permission default → real requestPermission()
          Kept PROMINENT + pulsing until the user answers, so it cannot be
          missed on any browser. */}
      {((install.needsPwaInstall && !iosDialogDismissed) || notifPerm === 'default') && (
        <button
          onClick={askNotif}
          style={{
            position: 'absolute', top: 38, right: 12, zIndex: 70,
            padding: '6px 12px',
            background: install.needsPwaInstall ? 'var(--g-gold)' : 'var(--g-blood)',
            color: install.needsPwaInstall ? 'var(--g-ink)' : 'var(--g-paper)',
            border: '2px solid var(--g-ink)', boxShadow: '3px 3px 0 var(--g-ink)',
            fontFamily: 'Bangers, cursive', fontSize: 11, letterSpacing: 1.5,
            borderRadius: 999, cursor: 'pointer',
            animation: 'g-petal-glow 2.2s ease-in-out infinite',
          }}
          title={install.needsPwaInstall
            ? 'iOS : installe la PWA pour recevoir les notifications'
            : "Recevoir une notif quand une forge est terminée, même hors de l'app"}>
          {install.needsPwaInstall ? '📲 INSTALLE L\'APP' : '🔔 ACTIVER NOTIFS'}
        </button>
      )}

      {/* iOS install guide — step-by-step instructions for Safari + Chrome iOS */}
      {iosDialogOpen && (
        <div
          onClick={dismissIos}
          style={{
            position: 'fixed', inset: 0, zIndex: 150,
            background: 'rgba(10,6,2,0.88)', backdropFilter: 'blur(4px)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20,
          }}>
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              width: '100%', maxWidth: 360,
              background: 'var(--g-paper)', color: 'var(--g-ink)',
              border: '3px solid var(--g-ink)', boxShadow: '5px 5px 0 var(--g-ink)',
              padding: '22px 20px', borderRadius: 8,
              fontFamily: 'Inter, sans-serif',
            }}>
            <div style={{
              fontFamily: 'Bangers, cursive', fontSize: 22, letterSpacing: 2, marginBottom: 8,
              color: 'var(--g-blood)',
            }}>
              📲 INSTALLE L'APP
            </div>
            <p style={{ fontSize: 12, lineHeight: 1.5, margin: '0 0 14px' }}>
              iOS (Safari + Chrome) n'autorise les notifications système que quand la page est
              installée sur l'écran d'accueil.
            </p>
            <ol style={{
              margin: '0 0 14px', paddingLeft: 22,
              fontSize: 13, lineHeight: 1.6, color: 'var(--g-ink-soft)',
            }}>
              <li>Tape le bouton <b>Partager</b> <span style={{ color: 'var(--g-blood)' }}>⎋</span> en bas de Safari
                <span style={{ fontSize: 11, color: 'var(--g-muted)' }}> (sur Chrome iOS : icône flèche en haut à droite)</span>.</li>
              <li>Choisis <b>« Sur l'écran d'accueil »</b>.</li>
              <li>Confirme, puis ouvre la nouvelle icône Juan of Bike depuis l'accueil.</li>
              <li>Reviens dans la Galerie, tape à nouveau 🔔 <b>ACTIVER NOTIFS</b>.</li>
            </ol>
            <p style={{ fontSize: 10, color: 'var(--g-muted)', margin: '0 0 14px' }}>
              Tes forges en cours sont sauvegardées après chaque étape : tu peux fermer l'app,
              réouvrir plus tard, la pipeline reprend où elle en était.
            </p>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button onClick={dismissIos}
                style={{
                  padding: '6px 12px',
                  background: 'var(--g-ink)', color: 'var(--g-paper)',
                  border: '2px solid var(--g-ink)', boxShadow: '2px 2px 0 var(--g-gold)',
                  fontFamily: 'Bangers, cursive', fontSize: 12, letterSpacing: 1.5, borderRadius: 4,
                }}>
                OK, JE L'INSTALLE
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Ink-scroll notifications */}
      <div className="g-notifs">
        {notifs.map((n) => (
          <div key={n.id} className="g-notif-scroll">
            <div className="g-notif-seal">{n.seal}</div>
            <span>{n.text}</span>
          </div>
        ))}
      </div>

      {/* Page turn flash */}
      <div className={`g-pageturn-fx ${turning ? 'on' : ''}`} />

      {/* Current page */}
      <div className="g-page" key={current.id} style={{ animation: 'g-bubble-in .5s' }}>
        <div className="g-corner g-corner-tl" />
        <div className="g-corner g-corner-tr" />
        <div className="g-corner g-corner-bl" />
        <div className="g-corner g-corner-br" />
        <div className="g-content">
          {current.id === 'home'    && <HomePage onTurn={turnTo} />}
          {current.id === 'team'    && (
            <Suspense fallback={<div style={{padding:24, color:'var(--g-ink-soft, #6b5840)', fontFamily:'Inter, sans-serif'}}>L'équipe se réveille…</div>}>
              <StudioRoster onPick={(_persona, page, _module) => {
                const idx = PAGES.findIndex((p) => p.id === page)
                if (idx >= 0) turnTo(idx)
              }} />
            </Suspense>
          )}
          {current.id === 'chat'    && <ChatPage onOpenVoice={() => setVoiceOpen(true)} />}
          {current.id === 'create'  && <CreatePage onOpenModule={(id) => { setActiveModule(id); }} />}
          {current.id === 'academy' && <AcademyPage />}
          {current.id === 'gallery' && <GalleryPage />}
          {current.id === 'canvas'  && <CanvasPage onOpenModule={(id) => setActiveModule(id)} />}
        </div>
      </div>

      {/* FightCloud badge — appears whenever a forge job is running, taps
          to open the forge overlay. Cartoon overlay re-uses the studio
          avatar a10-* keyframes already auto-injected by ./studio/Roster. */}
      <Suspense fallback={null}>
        <FightCloudBadge onOpen={() => setForgeOpen(true)} />
      </Suspense>

      {/* Companion orb — shows the actual Natsu/Lucy PP */}
      <div className="g-companion">
        {bubble && <div className="g-companion-bubble">{bubble}</div>}
        <button
          type="button"
          className="g-companion-orb g-companion-portrait"
          aria-label={`Copilote ${who}`}
          onClick={() => {
            const next: Character = who === 'natsu' ? 'lucy' : 'natsu'
            try { window.localStorage.setItem('ft-who', next) } catch { /* ignore */ }
            setWho(next)
            setBubble(next === 'natsu' ? 'Feu vif — à toi.' : 'Invocation prête.')
          }}>
          <img src={PORTRAITS[who]} alt={who} />
        </button>
      </div>

      {/* Spine nav */}
      <div className="g-spine">
        <button className="g-spine-cmd" onClick={() => turnTo(0)}>⌘ CENTRE</button>
        <div className="g-spine-strip">
          {PAGES.map((p, i) => (
            <div key={p.id}
              className={`g-spine-dot ${i === pageIdx ? 'active' : ''}`}
              onClick={() => turnTo(i)} />
          ))}
        </div>
        <div className="g-spine-labels">
          {PAGES.map((p, i) => (
            <span key={p.id} className={i === pageIdx ? 'active' : ''}>{p.title}</span>
          ))}
        </div>
      </div>

      {/* Voice copilot overlay (shared with desktop VoiceCopilotView) */}
      {voiceOpen && (
        <div className="fixed inset-0 z-[90] bg-black/95">
          <Suspense fallback={<div className="p-6 text-white/70">Copilote vocal…</div>}>
            <VoiceCopilotView onClose={() => setVoiceOpen(false)} />
          </Suspense>
        </div>
      )}

      {/* Global Forge overlay — lives at the root so page changes don't
          unmount it. Controlled via the `aurora:open-forge` custom event. */}
      {forgeOpen && (
        <Suspense fallback={null}>
          <CharacterForgeOverlay
            open={forgeOpen}
            initialPrompt={forgePrompt}
            onClose={() => { setForgeOpen(false); setForgePrompt('') }}
          />
        </Suspense>
      )}

      {/* Floating pill when a Forge job is running / pending results */}
      {(activeForgeJobs.length > 0 || pendingForgeResults > 0) && !forgeOpen && (
        <button
          onClick={() => setForgeOpen(true)}
          className="fixed z-[70]"
          style={{
            bottom: 104, left: 14,
            padding: '6px 10px',
            background: activeForgeJobs.length > 0 ? 'var(--g-blood)' : 'var(--g-gold)',
            color: activeForgeJobs.length > 0 ? 'var(--g-paper)' : 'var(--g-ink)',
            border: '2px solid var(--g-ink)',
            boxShadow: '2px 2px 0 var(--g-ink)',
            fontFamily: 'Bangers, cursive',
            fontSize: 11, letterSpacing: 1.5, borderRadius: 999,
            animation: activeForgeJobs.length > 0 ? 'g-petal-glow 1.8s ease-in-out infinite' : undefined,
          }}
          title="Ouvrir la Forge">
          {activeForgeJobs.length > 0
            ? `🔮 ${activeForgeJobs.length} forge${activeForgeJobs.length > 1 ? 's' : ''} en cours`
            : `✦ ${pendingForgeResults} à enregistrer`}
        </button>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Particles — same as reference design
// ---------------------------------------------------------------------------

function GrimoireParticles() {
  const parts = useMemo(
    () => Array.from({ length: 14 }, () => ({
      left: Math.random() * 100,
      top: 60 + Math.random() * 40,
      delay: Math.random() * 6,
      duration: 4 + Math.random() * 4,
    })),
    [],
  )
  return (
    <>
      {parts.map((p, i) => (
        <div key={i} className="g-particle"
          style={{
            left: `${p.left}%`, top: `${p.top}%`,
            animationDelay: `${p.delay}s`, animationDuration: `${p.duration}s`,
          }} />
      ))}
    </>
  )
}

// ---------------------------------------------------------------------------
// Home — radial wheel + daily journal
// ---------------------------------------------------------------------------

function HomePage({ onTurn }: { onTurn: (idx: number) => void }) {
  const xp = useGamificationStore((s) => s.xp)
  const level = useGamificationStore((s) => s.level)
  const streak = useGamificationStore((s) => s.streak)
  const categories = useAcademyStore((s) => s.categories)
  const chatMsgs = useChatStore((s) => s.messages.length)

  const petals = [
    { goto: 1, icon: '💬', label: 'Chat',     angle: -90, hot: chatMsgs === 0 },
    { goto: 2, icon: '✨', label: 'Créer',    angle: -30 },
    { goto: 3, icon: '📖', label: 'Académie', angle:  30 },
    { goto: 4, icon: '🔮', label: 'Galerie',  angle:  90 },
    { goto: 5, icon: '🗺',  label: 'Canvas',   angle: 150 },
    { goto: 1, icon: '🎤', label: 'Voice',    angle: 210 },
  ]
  const R = 100
  const totalItems = categories.reduce((n, c) => n + (c.items?.length || 0), 0)

  return (
    <div className="g-home">
      <h1 className="g-home-hero">JUAN OF BIKE</h1>
      <div className="g-home-sub">grimoire · niveau {level} · {xp} xp</div>

      <div className="g-wheel">
        <div className="g-wheel-ring" />
        <div className="g-wheel-ring-2" />
        {petals.map((m, i) => {
          const rad = (m.angle * Math.PI) / 180
          const x = Math.cos(rad) * R
          const y = Math.sin(rad) * R
          return (
            <div key={i} className={`g-petal ${m.hot ? 'hot' : ''}`}
              style={{ transform: `translate(calc(-50% + ${x}px), calc(-50% + ${y}px))` }}
              onClick={() => onTurn(m.goto)}>
              <span style={{ fontSize: 26 }}>{m.icon}</span>
              <span className="g-petal-label">{m.label}</span>
            </div>
          )
        })}
        <div className="g-seal">
          <svg className="g-seal-star" viewBox="0 0 48 48" fill="currentColor">
            <path d="M24 2 L29 18 L46 18 L32 28 L37 44 L24 34 L11 44 L16 28 L2 18 L19 18 Z" />
          </svg>
        </div>
      </div>

      <div className="g-home-status">
        <h5>JOURNAL DU JOUR</h5>
        <div className="g-home-status-row"><span>streak</span><b>{streak} {streak > 1 ? 'jours' : 'jour'}</b></div>
        <div className="g-home-status-row"><span>fiches disponibles</span><b>{totalItems}</b></div>
        <div className="g-home-status-row"><span>conversations</span><b>{chatMsgs}</b></div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Chat — real chatStore + streaming orchestrator
// ---------------------------------------------------------------------------

function ChatPage({ onOpenVoice }: { onOpenVoice: () => void }) {
  const {
    messages, isStreaming, streamContent,
    addMessage, setStreaming, setStreamContent, appendStreamContent,
    startRun, setRunStage, setRunAnalysis, setRunVerification, finishRun, failRun,
    clearMessages, popLastAssistantTurn,
  } = useChatStore()
  const mainModel = useAppStore((s) => s.mainModel)
  // Draft persisted across reloads (per-module slot 'conversation')
  const chatDraft = useModuleDraftsStore((s) => s.drafts.conversation?.prompt || '')
  const setChatDraft = useModuleDraftsStore((s) => s.setDraft)
  const clearChatDraft = useModuleDraftsStore((s) => s.clearDraft)
  const [draft, setDraftLocal] = useState(chatDraft)
  useEffect(() => setDraftLocal(chatDraft), [chatDraft])
  const setDraft = (v: string) => {
    setDraftLocal(v)
    setChatDraft('conversation', { prompt: v })
  }
  const [attachments, setAttachments] = useState<Array<{ id: string; name: string; size: number; type: string; text?: string }>>([])
  const [narratingId, setNarratingId] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const frVoiceRef = useRef<SpeechSynthesisVoice | null>(null)

  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight
  }, [messages.length, streamContent])

  // Cache a french voice so narrate() plays with natural prosody
  useEffect(() => {
    if (!('speechSynthesis' in window)) return
    const pick = () => {
      const voices = window.speechSynthesis.getVoices()
      if (!voices.length) return
      const fr =
        voices.find((v) => /^fr-FR$/i.test(v.lang)) ||
        voices.find((v) => /^fr[-_]/i.test(v.lang)) ||
        voices.find((v) => /fr/i.test(v.lang))
      if (fr) frVoiceRef.current = fr
    }
    pick()
    window.speechSynthesis.addEventListener('voiceschanged', pick)
    return () => window.speechSynthesis.removeEventListener('voiceschanged', pick)
  }, [])

  const narrate = (text: string, id: string) => {
    if (!('speechSynthesis' in window)) return
    if (narratingId === id) { window.speechSynthesis.cancel(); setNarratingId(null); return }
    const prepared = speakify(text)
    if (!prepared.trim()) return
    window.speechSynthesis.cancel()
    const chunks = prepared.split(/\n{2,}|(?<=[.!?])\s+(?=[A-ZÀ-Ö])/g).map((s) => s.trim()).filter(Boolean)
    setNarratingId(id)
    const speakNext = (i: number) => {
      if (i >= chunks.length) { setNarratingId((cur) => (cur === id ? null : cur)); return }
      const u = new SpeechSynthesisUtterance(chunks[i])
      u.lang = 'fr-FR'; u.rate = 0.98
      if (frVoiceRef.current) u.voice = frVoiceRef.current
      u.onend = () => speakNext(i + 1)
      u.onerror = () => setNarratingId((cur) => (cur === id ? null : cur))
      window.speechSynthesis.speak(u)
    }
    speakNext(0)
  }
  useEffect(() => () => { try { window.speechSynthesis.cancel() } catch { /* ignore */ } }, [])

  const TEXT_LIKE = /\.(txt|md|markdown|json|csv|tsv|log|xml|yaml|yml|ini|conf|py|js|ts|tsx|jsx|html|css|scss|sh|bash|zsh|c|h|cpp|hpp|java|go|rs|rb|php|sql|toml)$/i
  const onFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? [])
    if (files.length === 0) return
    const next = [] as typeof attachments
    for (const f of files) {
      const canRead = f.type.startsWith('text/') || TEXT_LIKE.test(f.name) || f.type === 'application/json'
      let text: string | undefined
      if (canRead) {
        try {
          text = await f.text()
          if (text.length > 200000) text = text.slice(0, 200000) + '\n\n[... tronqué ...]'
        } catch { /* ignore */ }
      }
      next.push({
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        name: f.name, size: f.size, type: f.type || 'application/octet-stream', text,
      })
    }
    setAttachments((prev) => [...prev, ...next])
    e.target.value = ''
  }

  const onSend = async () => {
    const text = draft.trim()
    if ((!text && attachments.length === 0) || isStreaming) return
    setDraft('')
    clearChatDraft('conversation')
    abortRef.current?.abort()
    abortRef.current = new AbortController()

    let composed = text
    if (attachments.length > 0) {
      const blocks = attachments
        .filter((a) => a.text)
        .map((a) => `--- FICHIER JOINT : ${a.name} ---\n${a.text}\n--- FIN ${a.name} ---`)
        .join('\n\n')
      composed = blocks ? (text ? `${text}\n\n${blocks}` : blocks) : text
      setAttachments([])
    }
    const payload = composed || text

    addMessage({ role: 'user', content: payload })
    setStreaming(true)
    setStreamContent('')
    startRun()
    try {
      const result = await runConversationTurn({
        model: mainModel,
        messages: [...messages, { id: 'u', role: 'user', content: payload, timestamp: Date.now() }],
        userInput: payload,
        voiceMode: false,
        signal: abortRef.current.signal,
        onEvent: (ev) => {
          if (ev.type === 'stage') setRunStage(ev.stage, ev.label, ev.detail, ev.progress, ev.timelineStatus)
          else if (ev.type === 'analysis') setRunAnalysis(ev.analysis)
          else if (ev.type === 'verification') setRunVerification(ev.verification)
        },
        onToken: (tok) => appendStreamContent(tok),
      })
      addMessage({ role: 'assistant', content: result.finalText })
      finishRun()
      setStreamContent('')
    } catch (err) {
      if ((err as Error)?.name === 'AbortError') { setStreamContent(''); return }
      const detail = err instanceof Error ? err.message : String(err)
      failRun(detail)
      addMessage({ role: 'assistant', content: `⚠️ ${detail}` })
    } finally {
      setStreaming(false)
    }
  }

  const onRegenerate = () => {
    const lastText = popLastAssistantTurn()
    if (lastText) { setDraft(lastText); void onSend() }
  }

  return (
    <>
      <h1 className="g-title">CHAT</h1>
      <div className="g-subtitle" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span>ollama · {(mainModel || '').split('/').pop()} · streaming</span>
        <span style={{ display: 'inline-flex', gap: 6 }}>
          <button
            onClick={() => requestOpenForge('')}
            title="Forge un personnage"
            style={{
              fontFamily: 'Bangers, cursive', letterSpacing: 1.5, fontSize: 11,
              padding: '2px 8px', background: 'var(--g-blood)', color: 'var(--g-paper)',
              border: '2px solid var(--g-ink)', boxShadow: '1.5px 1.5px 0 var(--g-ink)',
            }}>
            🔮 FORGE
          </button>
          <button
            onClick={() => { if (window.confirm('Effacer la conversation ?')) { window.speechSynthesis.cancel(); setNarratingId(null); clearMessages() } }}
            title="Effacer"
            style={{
              fontFamily: 'Bangers, cursive', letterSpacing: 1.5, fontSize: 11,
              padding: '2px 8px', background: 'var(--g-paper)', color: 'var(--g-ink)',
              border: '2px solid var(--g-ink)', boxShadow: '1.5px 1.5px 0 var(--g-ink)',
            }}>
            ✕ CLEAR
          </button>
        </span>
      </div>

      <div
        className="g-chat-scroll g-content-scroll"
        ref={listRef}
        style={{ height: `calc(100% - ${attachments.length > 0 ? 130 : 72}px)` }}
      >
        {messages.length === 0 && (
          <div className="g-msg ai">
            <span className="glow" />
            Te voilà. Que cherchons-nous aujourd'hui ?
          </div>
        )}
        {messages.map((m, i) => {
          const id = String(m.id ?? m.timestamp ?? i)
          const isAsst = m.role === 'assistant'
          return (
            <div key={m.id || i} className={`g-msg ${isAsst ? 'ai' : 'user'}`}>
              {isAsst && <span className="glow" />}
              {isAsst
                ? <MarkdownPro content={m.content} idPrefix={`g-${id}`} />
                : m.content}
              {isAsst && (
                <div style={{ marginTop: 6, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  <button
                    onClick={() => narrate(m.content, id)}
                    style={{
                      fontFamily: 'JetBrains Mono, monospace', fontSize: 9, padding: '2px 6px',
                      border: '1.5px solid var(--g-ink)',
                      background: narratingId === id ? 'var(--g-blood)' : 'var(--g-paper)',
                      color: narratingId === id ? 'var(--g-paper)' : 'var(--g-ink)',
                      borderRadius: 999, letterSpacing: 1,
                    }}>
                    {narratingId === id ? 'STOP' : 'LIRE'}
                  </button>
                  <button
                    onClick={() => { void navigator.clipboard.writeText(m.content) }}
                    style={{
                      fontFamily: 'JetBrains Mono, monospace', fontSize: 9, padding: '2px 6px',
                      border: '1.5px solid var(--g-ink)', background: 'var(--g-paper)',
                      color: 'var(--g-ink)', borderRadius: 999, letterSpacing: 1,
                    }}>
                    COPIER
                  </button>
                  {i === messages.length - 1 && (
                    <button
                      onClick={onRegenerate}
                      style={{
                        fontFamily: 'JetBrains Mono, monospace', fontSize: 9, padding: '2px 6px',
                        border: '1.5px solid var(--g-ink)', background: 'var(--g-paper)',
                        color: 'var(--g-ink)', borderRadius: 999, letterSpacing: 1,
                      }}>
                      REGEN
                    </button>
                  )}
                </div>
              )}
            </div>
          )
        })}
        {isStreaming && (
          <div className="g-msg ai">
            <span className="glow" />
            {streamContent || '…'}
          </div>
        )}
      </div>

      {attachments.length > 0 && (
        <div
          style={{
            position: 'absolute', left: 0, right: 0, bottom: 52,
            display: 'flex', gap: 6, flexWrap: 'wrap',
            padding: '6px 0',
            borderTop: '1px dashed var(--g-ink)',
          }}>
          {attachments.map((a) => (
            <span
              key={a.id}
              style={{
                fontFamily: 'JetBrains Mono, monospace', fontSize: 9, padding: '2px 8px',
                background: a.text ? 'var(--g-blood)' : 'var(--g-paper-dark)',
                color: a.text ? 'var(--g-paper)' : 'var(--g-ink)',
                border: '1.5px solid var(--g-ink)', borderRadius: 999,
                display: 'inline-flex', alignItems: 'center', gap: 6,
              }}>
              📎 {a.name}
              <button
                onClick={() => setAttachments((p) => p.filter((x) => x.id !== a.id))}
                style={{
                  border: 'none', background: 'transparent', cursor: 'pointer', fontSize: 11,
                  color: 'inherit', padding: 0,
                }}>✕</button>
            </span>
          ))}
        </div>
      )}

      <input ref={fileInputRef} type="file" multiple hidden onChange={onFileChange} />

      <div className="g-chat-input">
        <button
          className="g-chat-send"
          style={{ background: 'var(--g-gold)', color: 'var(--g-ink)' }}
          onClick={() => fileInputRef.current?.click()}
          title="Joindre un fichier">📎</button>
        <button
          className="g-chat-send"
          style={{ background: 'var(--g-ink)' }}
          onClick={onOpenVoice}
          title="Copilote vocal">🎤</button>
        <input
          placeholder="prononce ton sort…"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); void onSend() } }}
          disabled={isStreaming}
        />
        <button className="g-chat-send" onClick={() => void onSend()}
          disabled={isStreaming || (!draft.trim() && attachments.length === 0)}>↗</button>
      </div>

    </>
  )
}

// ---------------------------------------------------------------------------
// Create — 2×2 of creative modules (image, video, code, drawing)
// ---------------------------------------------------------------------------

import type { ModuleId } from '../types/app'
function CreatePage({ onOpenModule }: { onOpenModule: (id: ModuleId) => void }) {
  const arts: Array<{ id: ModuleId; name: string; sub: string; tag: string; preview: string }> = [
    { id: 'image',   name: 'Image',  sub: 'flux · styles multiples',  tag: 'S', preview: 'ouvrir atelier' },
    { id: 'video',   name: 'Vidéo',  sub: 'wan2.2 · T2V/I2V',          tag: 'B', preview: 'projecteur' },
    { id: 'code',    name: 'Code',   sub: 'modele expert · cartes',   tag: 'A', preview: 'collection' },
    { id: 'drawing', name: 'Dessin', sub: 'canvas · sketch2img',      tag: 'B', preview: 'twin panels' },
    { id: 'cyber',   name: 'Cyber',  sub: 'dojo · katas + lab',       tag: 'A', preview: '8 katas' },
    { id: '3d',      name: '3D',     sub: 'holographic turntable',    tag: 'S', preview: 'turntable' },
  ]
  return (
    <>
      <h1 className="g-title">SORTILÈGES</h1>
      <div className="g-subtitle">arts créatifs · tape pour entrer</div>
      <div className="g-content-scroll" style={{ maxHeight: 'calc(100% - 64px)' }}>
        <div className="g-creative-grid">
          {arts.map((a) => (
            <button key={a.id} className="g-creative-card" onClick={() => onOpenModule(a.id)}>
              <span className="tag">rang {a.tag}</span>
              <h4>{a.name}</h4>
              <p>{a.sub}</p>
              <div className="g-creative-preview">{a.preview}</div>
            </button>
          ))}
        </div>
      </div>
    </>
  )
}

// ---------------------------------------------------------------------------
// Gallery — saved avatars (Forge outputs) + recent generations
// ---------------------------------------------------------------------------

function GalleryPage() {
  const avatars = useAppStore((s) => s.avatarList)
  const selectedId = useAppStore((s) => s.selectedAvatarId)
  const setSelectedAvatar = useAppStore((s) => s.setSelectedAvatar)
  const removeAvatar = useAppStore((s) => s.removeAvatar)
  const custom = avatars.filter((a) => !a.builtIn)
  const builtin = avatars.filter((a) => a.builtIn)
  return (
    <>
      <h1 className="g-title">INVOCATIONS</h1>
      <div className="g-subtitle">tes esprits forgés · tape pour sélectionner</div>
      <div className="g-content-scroll" style={{ maxHeight: 'calc(100% - 72px)' }}>
        {custom.length === 0 ? (
          <div style={{
            padding: 14, textAlign: 'center', color: 'var(--g-muted)',
            fontFamily: 'JetBrains Mono, monospace', fontSize: 11,
            border: '1px dashed var(--g-ink)', background: 'rgba(26,15,5,0.04)', marginBottom: 12,
          }}>
            Aucun esprit forgé.<br />Tape INVOQUER pour ouvrir la Forge.
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 14 }}>
            {custom.map((av) => (
              <div key={av.id} style={{
                padding: 8, background: 'var(--g-paper)',
                border: `2px solid ${selectedId === av.id ? 'var(--g-blood)' : 'var(--g-ink)'}`,
                boxShadow: '2px 2px 0 var(--g-ink)', position: 'relative',
              }}>
                <button onClick={() => setSelectedAvatar(av.id)}
                  style={{
                    width: '100%', background: 'transparent', border: 'none', cursor: 'pointer',
                    display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
                  }}>
                  <div style={{
                    width: '100%', aspectRatio: '1 / 1', background: 'var(--g-paper-dark)',
                    border: '1px solid var(--g-ink)', overflow: 'hidden',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 28,
                  }}>
                    {av.thumbnail ? <img src={av.thumbnail} alt={av.label} style={{ width: '100%', height: '100%', objectFit: 'cover' }} /> : '✨'}
                  </div>
                  <span style={{
                    fontFamily: 'Bangers, cursive', fontSize: 12, letterSpacing: 1,
                    color: 'var(--g-ink)', textAlign: 'center',
                  }}>{av.label}</span>
                  <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 8, color: 'var(--g-muted)' }}>
                    {av.animationMode || av.type}
                  </span>
                </button>
                <button onClick={() => removeAvatar(av.id)}
                  style={{
                    position: 'absolute', top: -6, right: -6, width: 20, height: 20,
                    borderRadius: '50%', border: '2px solid var(--g-ink)', background: 'var(--g-blood)',
                    color: 'var(--g-paper)', fontSize: 10, cursor: 'pointer',
                  }} title="Supprimer">✕</button>
              </div>
            ))}
          </div>
        )}

        <button onClick={() => requestOpenForge('')}
          style={{
            width: '100%', padding: 12, background: 'var(--g-blood)',
            color: 'var(--g-paper)', border: '2px solid var(--g-ink)',
            fontFamily: 'Bangers, cursive', fontSize: 16, letterSpacing: 2,
            boxShadow: '3px 3px 0 var(--g-ink)', cursor: 'pointer', marginBottom: 14,
          }}>
          🔮 INVOQUER UN NOUVEL ESPRIT
        </button>

        {builtin.length > 0 && (
          <>
            <div className="g-divider" />
            <div style={{
              fontFamily: 'JetBrains Mono, monospace', fontSize: 9, letterSpacing: 1.5,
              color: 'var(--g-muted)', textTransform: 'uppercase', marginBottom: 6,
            }}>
              Esprits fondamentaux
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {builtin.map((av) => (
                <button key={av.id} onClick={() => setSelectedAvatar(av.id)}
                  style={{
                    padding: '4px 10px', background: selectedId === av.id ? 'var(--g-gold-bright)' : 'var(--g-paper)',
                    border: '2px solid var(--g-ink)', fontFamily: 'Bangers, cursive', fontSize: 11,
                    letterSpacing: 1, cursor: 'pointer', color: 'var(--g-ink)',
                  }}>
                  {av.label}
                </button>
              ))}
            </div>
          </>
        )}
      </div>

    </>
  )
}

// ---------------------------------------------------------------------------
// Academy — real categories + stats
// ---------------------------------------------------------------------------

function AcademyPage() {
  const categories = useAcademyStore((s) => s.categories)
  const level = useGamificationStore((s) => s.level)
  const xp = useGamificationStore((s) => s.xp)
  const streak = useGamificationStore((s) => s.streak)
  const quizHistory = useGamificationStore((s) => s.quizHistory)
  const setActiveModule = useAppStore((s) => s.setActiveModule)

  const totalQuizzes = quizHistory.length
  const avgScore = totalQuizzes > 0
    ? Math.round((quizHistory.reduce((s, q) => s + (q.score / q.total), 0) / totalQuizzes) * 100)
    : 0

  const quests = categories.slice(0, 5).map((c, idx) => {
    const itemCount = c.items?.length || 0
    const subCount = c.subCategories?.length || 0
    const rank = idx < 2 ? 'S' : idx < 4 ? 'A' : 'B'
    return { id: c.id, t: c.name, s: `${subCount} sous-catégories · ${itemCount} fiches`, r: rank }
  })

  return (
    <>
      <h1 className="g-title">ANNALES</h1>
      <div className="g-subtitle">tes quêtes en cours</div>
      <div className="g-grimoire-stats">
        <div className="g-stat"><div className="g-stat-val">{level}</div><div className="g-stat-lbl">niveau</div></div>
        <div className="g-stat"><div className="g-stat-val">{xp}</div><div className="g-stat-lbl">xp total</div></div>
        <div className="g-stat"><div className="g-stat-val">{streak}j</div><div className="g-stat-lbl">streak</div></div>
        <div className="g-stat"><div className="g-stat-val">{avgScore}%</div><div className="g-stat-lbl">quiz</div></div>
      </div>
      <div className="g-divider" />
      <div className="g-content-scroll" style={{ maxHeight: 'calc(100% - 200px)' }}>
        {quests.length === 0 ? (
          <div style={{ textAlign: 'center', color: 'var(--g-muted)', fontFamily: 'JetBrains Mono, monospace', fontSize: 11, padding: 12 }}>
            Aucune quête encore. Ouvre l'Académie complète pour commencer.
          </div>
        ) : quests.map((q) => (
          <button key={q.id} className="g-quest" style={{ width: '100%', textAlign: 'left' }}
            onClick={() => setActiveModule('learning')}>
            <div>
              <div className="g-quest-t">{q.t}</div>
              <div className="g-quest-s">{q.s}</div>
            </div>
            <div className={`g-quest-rank ${q.r === 'S' ? 's' : ''}`}>{q.r}</div>
          </button>
        ))}
      </div>
    </>
  )
}

// ---------------------------------------------------------------------------
// Canvas — map view with territories linking to modules
// ---------------------------------------------------------------------------

function CanvasPage({ onOpenModule }: { onOpenModule: (id: ModuleId) => void }) {
  return (
    <>
      <h1 className="g-title">CARTE</h1>
      <div className="g-subtitle">tes territoires actifs</div>
      <svg viewBox="0 0 300 400" style={{ width: '100%', height: 'auto', marginTop: 10 }}>
        <defs>
          <pattern id="g-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="6" stroke="#3d2a12" strokeWidth="0.8" />
          </pattern>
        </defs>
        <path d="M 20 340 Q 80 280 120 240 T 200 120 T 280 40" fill="none" stroke="#3d2a12" strokeWidth="2" strokeDasharray="4 4" />
        <path d="M 40 50 Q 100 100 150 140 T 260 220" fill="none" stroke="#3d2a12" strokeWidth="2" strokeDasharray="4 4" />

        <g style={{ cursor: 'pointer' }} onClick={() => onOpenModule('conversation')}>
          <circle cx="70" cy="80" r="38" fill="url(#g-hatch)" stroke="#1a0f05" strokeWidth="2" />
          <text x="70" y="85" textAnchor="middle" fontFamily="Bangers" fontSize="14" fill="#1a0f05">CHAT</text>
        </g>
        <g style={{ cursor: 'pointer' }} onClick={() => onOpenModule('voice')}>
          <circle cx="220" cy="110" r="32" fill="#b5241e" stroke="#1a0f05" strokeWidth="2" opacity="0.7" />
          <text x="220" y="115" textAnchor="middle" fontFamily="Bangers" fontSize="12" fill="#ecdcb0">FORGE</text>
        </g>
        <g style={{ cursor: 'pointer' }} onClick={() => onOpenModule('image')}>
          <rect x="40" y="200" width="80" height="60" fill="#c9a24b" stroke="#1a0f05" strokeWidth="2" transform="rotate(-5 80 230)" />
          <text x="80" y="236" textAnchor="middle" fontFamily="Bangers" fontSize="13" fill="#1a0f05">IMAGE</text>
        </g>
        <g style={{ cursor: 'pointer' }} onClick={() => onOpenModule('code')}>
          <circle cx="200" cy="240" r="28" fill="#ecdcb0" stroke="#1a0f05" strokeWidth="2" />
          <text x="200" y="245" textAnchor="middle" fontFamily="Bangers" fontSize="11" fill="#1a0f05">CODE</text>
        </g>
        <g style={{ cursor: 'pointer' }} onClick={() => onOpenModule('cyber')}>
          <polygon points="150,320 190,360 110,360" fill="#6a3b8c" stroke="#1a0f05" strokeWidth="2" opacity="0.8" />
          <text x="150" y="350" textAnchor="middle" fontFamily="Bangers" fontSize="11" fill="#ecdcb0">CYBER</text>
        </g>
        <g transform="translate(255, 340)">
          <circle r="22" fill="#ecdcb0" stroke="#1a0f05" strokeWidth="2" />
          <polygon points="0,-16 4,0 0,14 -4,0" fill="#b5241e" stroke="#1a0f05" />
          <text x="0" y="-18" textAnchor="middle" fontFamily="Bangers" fontSize="8">N</text>
        </g>
      </svg>
      <div className="g-divider" />
      <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: 'var(--g-muted)', textAlign: 'center' }}>
        TAPE UN TERRITOIRE POUR L'OUVRIR
      </div>
    </>
  )
}
