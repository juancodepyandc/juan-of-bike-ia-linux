import { useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  ArrowLeft,
  Box,
  Code2,
  GraduationCap,
  Image as ImageIcon,
  MessageSquare,
  Monitor,
  Paintbrush,
  Search,
  Shield,
  Smartphone,
  Sparkles,
  Video,
  type LucideIcon,
} from 'lucide-react'
import { useAppStore } from '../stores/appStore'
import { useCoworkStore } from '../stores/coworkStore'
import type { ModuleId } from '../types/app'
import GeneratedDownloads from './GeneratedDownloads'
import { useDeviceKind } from '../utils/device'
import { useCoworkLiveCounters } from '../hooks/useCoworkLiveCounters'
import { readUiSkin } from '../utils/uiSkin'

// =============================================================================
// MODULE META (labels, kickers, colors) — used by GuildBoard, Dock, Slash
// =============================================================================

interface ModuleMeta {
  id: ModuleId
  label: string
  kicker: string
  icon: LucideIcon
  color: string
  shortcut: string
  rank: 'S' | 'A' | 'B' | 'C'
  metricLabel: string
  reward: string
}

const MODULES: ModuleMeta[] = [
  { id: 'conversation', label: 'Chat',     kicker: 'Copilote IA',            icon: MessageSquare,  color: 'var(--color-mod-conv)',    shortcut: '1', rank: 'A', metricLabel: 'messages', reward: '+40 XP' },
  { id: 'image',        label: 'Image',    kicker: 'Studio FLUX',            icon: ImageIcon,      color: 'var(--color-mod-image)',   shortcut: '2', rank: 'S', metricLabel: 'générées', reward: '+80 XP' },
  { id: 'code',         label: 'Code',     kicker: 'Pipeline build',         icon: Code2,          color: 'var(--color-mod-code)',    shortcut: '3', rank: 'A', metricLabel: 'projets',  reward: '+50 XP' },
  { id: 'video',        label: 'Vidéo',    kicker: 'Motion Wan2.2',          icon: Video,          color: 'var(--color-mod-video)',   shortcut: '4', rank: 'B', metricLabel: 'clips',    reward: '+30 XP' },
  { id: 'drawing',      label: 'Dessin',   kicker: 'Canvas · sketch2img',    icon: Paintbrush,     color: 'var(--color-mod-drawing)', shortcut: '5', rank: 'B', metricLabel: 'croquis',  reward: '+30 XP' },
  { id: '3d',           label: '3D',       kicker: 'Mesh · Rig',             icon: Box,            color: 'var(--color-mod-3d)',      shortcut: '6', rank: 'A', metricLabel: 'meshes',   reward: '+60 XP' },
  { id: 'cyber',        label: 'Cyber',    kicker: 'Crypto · réseau · CTF',  icon: Shield,         color: 'var(--color-mod-video)',   shortcut: '7', rank: 'S', metricLabel: 'défis',    reward: '+90 XP' },
  { id: 'learning',     label: 'Académie', kicker: 'Labs · quiz · parcours', icon: GraduationCap,  color: 'var(--color-mod-learn)',   shortcut: '8', rank: 'S', metricLabel: 'xp total', reward: 'niveau UP' },
]

// SFX onomatopoeias per module × character (Natsu fire / Lucy stars)
const MODULE_SFX: Record<ModuleId, { natsu: [string, string]; lucy: [string, string] }> = {
  conversation: { natsu: ['', ''], lucy: ['', ''] },
  image:        { natsu: ['DON !!', 'BOOM'], lucy: ['KIRA ★', 'SHINE'] },
  code:         { natsu: ['GUOOH !', 'CLACK'], lucy: ['GATE !', 'CLICK'] },
  video:        { natsu: ['ACTION !', 'DRAMA'] as [string, string], lucy: ['ACTION !', 'STAGE'] as [string, string] },
  drawing:      { natsu: ['ZWOOSH', 'PAF'], lucy: ['SWISH', 'HOSHI'] },
  '3d':         { natsu: ['FORGE !', 'DON'], lucy: ['SUMMON', 'STAR'] },
  cyber:        { natsu: ['HACK !', 'ZAP'], lucy: ['OPEN !', 'KEY'] },
  learning:     { natsu: ['LEARN !', 'POW'], lucy: ['ÉTOILE', 'SHINE'] },
  voice:        { natsu: ['VOICE !', 'BOOM'], lucy: ['CHANT !', 'BELL'] },
}

// =============================================================================
// CHARACTER (Natsu / Lucy) — persisted to localStorage
// =============================================================================

type Character = 'natsu' | 'lucy'

const CHAR_KEY = 'ft-who'

const PORTRAITS: Record<Character, string> = {
  natsu: '/fairy/natsu.png',
  lucy:  '/fairy/lucy.png',
}

const HERO_COPY: Record<Character, { kicker: string; titlePart1: string; titleAccent: string; sub: string }> = {
  natsu: {
    kicker: 'GUILDE FAIRY TAIL',
    titlePart1: 'Choisis ta',
    titleAccent: 'quête !',
    sub: "Chaque module est un job pris au tableau. Double-clic sur une affiche pour l'accepter. J'suis tout feu tout flamme — on y va !",
  },
  lucy: {
    kicker: 'GUILDE FAIRY TAIL',
    titlePart1: 'Pioche une',
    titleAccent: 'clé !',
    sub: "Chaque module est une Porte Stellaire. Double-clic sur une affiche pour l'ouvrir. Je suis prête à t'invoquer le bon esprit.",
  },
}

const COMPANION_LINES: Record<Character, Partial<Record<ModuleId, string>>> = {
  natsu: {
    conversation: "Balance ta question, j'suis chaud patate !",
    image:        "Karyū no Hōkō sur la toile !",
    code:         "On file droit dans le code, Happy tient la barre.",
    video:        "Action ! J'mets le feu à la pellicule.",
    drawing:      "Ton croquis prend vie — étincelles garanties.",
    '3d':         "Un mesh brûlant sort du four !",
    cyber:        "Chiffrement ? J'brûle les pare-feux moi.",
    learning:     "Quiz time ! Donne-moi tout ton XP.",
  },
  lucy: {
    conversation: "Ouvre-toi, Porte de l'Informatique !",
    image:        "Invoque-moi la plus belle des esquisses.",
    code:         "Virgo m'a appris à ranger le code avec soin.",
    video:        "Je trace le scénario, tu regardes les étoiles.",
    drawing:      "Chaque trait est une constellation.",
    '3d':         "On sculpte dans la lumière stellaire.",
    cyber:        "Taurus protège nos clés, ne crains rien.",
    learning:     "Nouvelle leçon, nouvelle constellation.",
  },
}

function useCharacter(): [Character, (c: Character) => void] {
  const [who, setWho] = useState<Character>(() => {
    if (typeof window === 'undefined') return 'natsu'
    const saved = window.localStorage.getItem(CHAR_KEY)
    return saved === 'lucy' ? 'lucy' : 'natsu'
  })
  useEffect(() => {
    try { window.localStorage.setItem(CHAR_KEY, who) } catch { /* noop */ }
  }, [who])
  return [who, setWho]
}

// =============================================================================
// MANGA HEADER — chips, title badge, character toggle, zoom hint
// =============================================================================

function MangaHeader({ who, onChangeWho, ollamaOk, comfyOk, installedCount }: {
  who: Character
  onChangeWho: (c: Character) => void
  ollamaOk: boolean
  comfyOk: boolean
  installedCount: number
}) {
  const device = useDeviceKind()
  // Probe the Python bridge every 30s so users always see its real state —
  // it's the service that fails first in Cloud tunnel mode, and Forge/Vision
  // can't work without it. Lazy import to keep the core chunk small.
  const [bridgeOk, setBridgeOk] = useState<boolean | null>(null)
  useEffect(() => {
    let alive = true
    const tick = async () => {
      try {
        const mod = await import('../services/pythonJobClient')
        const ok = await mod.isBridgeReachable()
        if (alive) setBridgeOk(ok)
      } catch { if (alive) setBridgeOk(false) }
    }
    void tick()
    const id = window.setInterval(tick, 30_000)
    return () => { alive = false; window.clearInterval(id) }
  }, [])
  const deviceLabel =
    device.kind === 'mobile' ? 'Mobile'
    : device.kind === 'tablet' ? 'Tablette'
    : 'PC'
  const DeviceIcon = device.kind === 'desktop' ? Monitor : Smartphone
  // v82q : the host header always rendered the manga "× Fairy Tail · Natsu/Lucy"
  // flag and character toggle, even on aurora_v1/aurora_v3 skins. That violated
  // the user's "absolument plus cette interface" rule at the host level.
  // Hide manga-only chrome when not on the manga skin.
  const isManga = readUiSkin() === 'manga'
  return (
    <header className="as-header">
      <div className="as-header-left">
        <span className="as-header-status-chip" title={`${device.width}×${device.height} · ${device.touch ? 'touch' : 'no-touch'} · ${device.platform || 'n/a'}`}>
          <DeviceIcon size={11} strokeWidth={2.4} /> {deviceLabel}
        </span>
        <span className="as-header-status-chip">
          <span className={`as-header-status-dot ${ollamaOk ? 'is-ok' : ''}`} /> Ollama
        </span>
        <span className="as-header-status-chip">
          <span className={`as-header-status-dot ${comfyOk ? 'is-ok' : ''}`} /> ComfyUI
        </span>
        <span className="as-header-status-chip"
          title={bridgeOk === false
            ? 'Bridge Python injoignable — démarre-le sur port 3001'
            : bridgeOk === true
              ? 'Bridge Python joignable'
              : 'Bridge Python : vérification…'}>
          <span className={`as-header-status-dot ${bridgeOk ? 'is-ok' : bridgeOk === false ? 'is-err' : ''}`} /> Bridge
        </span>
        <span className="as-header-status-chip">
          <span className="as-header-status-dot" /> {installedCount} modèles
        </span>
      </div>

      <div className="as-header-center">
        <span className="as-title-badge">juan of bike IA</span>
        {isManga && (
          <span className="as-header-flag">× Fairy Tail · {who === 'natsu' ? 'Natsu' : 'Lucy'}</span>
        )}
      </div>

      <div className="as-header-right">
        {isManga && (
          <div className="ft-char-toggle">
            <button
              type="button"
              className={`ft-char-toggle-btn ${who === 'natsu' ? 'is-active' : ''}`}
              onClick={() => onChangeWho('natsu')}
            >Natsu</button>
            <button
              type="button"
              className={`ft-char-toggle-btn ${who === 'lucy' ? 'is-active' : ''}`}
              onClick={() => onChangeWho('lucy')}
            >Lucy</button>
          </div>
        )}
      </div>
    </header>
  )
}

// =============================================================================
// AURORA HOME BOARD — editorial home grid for aurora_v1 / aurora_v3 skins.
// Replaces GuildBoard's manga rank-S/A/B/C quest cards + "TABLEAU DES QUÊTES"
// + Natsu/Lucy hero portrait + DON!!/KIRA★ SFX with a design-source-faithful
// editorial module grid (no manga branding). v82r.
// =============================================================================

function AuroraHomeBoard({ onActivateModule, getModuleStats }: {
  onActivateModule: (id: ModuleId) => void
  getModuleStats: (id: ModuleId) => { value: string | number; sublabel?: string; tags?: string[]; caption?: string }
}) {
  const skin = readUiSkin()
  const isV3 = skin === 'aurora_v3'
  return (
    <div
      className={isV3 ? undefined : 'grain'}
      style={{
        height: '100%', overflow: 'auto', position: 'relative',
        background: 'var(--bg, #0c0a09)', color: 'var(--fg, #f5f5f5)',
        fontFamily: 'var(--font-sans, system-ui)',
        padding: isV3 ? '32px 32px 80px' : '56px 64px 80px',
      }}
    >
      {/* Header band */}
      <div style={{
        display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between',
        gap: 24, flexWrap: 'wrap', marginBottom: 36,
        borderBottom: '1px solid var(--line, rgba(255,255,255,0.12))',
        paddingBottom: 24,
      }}>
        <div>
          <div style={{
            fontFamily: 'var(--font-mono, ui-monospace, monospace)', fontSize: 11,
            letterSpacing: '0.18em', textTransform: 'uppercase',
            color: 'var(--fg-mute, #888)', marginBottom: 12,
          }}>
            <span style={{
              display: 'inline-block', width: 8, height: 8, borderRadius: 99,
              background: 'var(--ember-500, #ff6a3d)', marginRight: 8,
              boxShadow: '0 0 12px var(--ember-500, #ff6a3d)',
              verticalAlign: 'middle',
            }} />
            Aurora · session locale · {new Date().toTimeString().slice(0, 5)}
          </div>
          <div style={{
            fontFamily: 'var(--font-display, "Cormorant Garamond", serif)',
            fontStyle: 'italic', fontWeight: 400, letterSpacing: '-0.02em',
            lineHeight: 0.95, fontSize: isV3 ? 56 : 80,
            color: 'var(--fg, #f5f5f5)',
          }}>
            {isV3 ? 'polyphonie' : <>Choisis<br/><em style={{ color: 'var(--ember-500, #ff6a3d)' }}>un module</em></>}
          </div>
          <p style={{
            marginTop: 18, maxWidth: 560,
            fontSize: 14.5, lineHeight: 1.55,
            color: 'var(--fg-dim, #aaa)',
          }}>
            {isV3
              ? '11 identités, une par module — chaque atelier a son aesthetic.'
              : 'Huit modules — conversation, image, code, vidéo, dessin, 3D, cyber, académie. Tout local, tout connecté à ta session.'}
          </p>
        </div>
      </div>

      {/* Module grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
        gap: 18,
      }}>
        {MODULES.map((m) => {
          const stats = getModuleStats(m.id)
          const Icon = m.icon
          const tags = (stats.tags || []).slice(0, 2)
          return (
            <button
              key={m.id}
              type="button"
              onClick={() => onActivateModule(m.id)}
              style={{
                position: 'relative',
                textAlign: 'left',
                padding: '20px 22px 18px',
                background: 'var(--bg-card, rgba(255,255,255,0.03))',
                border: '1px solid var(--line, rgba(255,255,255,0.12))',
                borderRadius: 14,
                cursor: 'pointer',
                color: 'var(--fg, #f5f5f5)',
                fontFamily: 'inherit',
                overflow: 'hidden',
                transition: 'border-color 160ms ease, transform 160ms ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'var(--ember-500, #ff6a3d)'
                e.currentTarget.style.transform = 'translateY(-2px)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'var(--line, rgba(255,255,255,0.12))'
                e.currentTarget.style.transform = 'translateY(0)'
              }}
            >
              {/* Module aura blob */}
              <div style={{
                position: 'absolute', top: -30, right: -30,
                width: 110, height: 110, borderRadius: '50%',
                background: `radial-gradient(circle at 35% 35%, ${m.color}, transparent 70%)`,
                opacity: 0.35, pointerEvents: 'none',
              }} />
              {/* Eyebrow */}
              <div style={{
                fontFamily: 'var(--font-mono, ui-monospace, monospace)', fontSize: 10,
                letterSpacing: '0.14em', textTransform: 'uppercase',
                color: 'var(--fg-mute, #888)',
                display: 'flex', alignItems: 'center', gap: 8,
                marginBottom: 14,
              }}>
                <span style={{
                  width: 7, height: 7, borderRadius: 99, background: m.color,
                  boxShadow: `0 0 10px ${m.color}`,
                }} />
                {m.kicker}
                <span style={{ flex: 1 }} />
                <span style={{ color: 'var(--fg-mute, #777)' }}>⌘{m.shortcut}</span>
              </div>
              {/* Icon */}
              <div style={{
                width: 36, height: 36, borderRadius: 8,
                background: 'var(--bg-raised, rgba(255,255,255,0.04))',
                border: '1px solid var(--line-soft, rgba(255,255,255,0.08))',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: m.color, marginBottom: 12,
              }}>
                <Icon size={18} strokeWidth={2.2} />
              </div>
              {/* Title */}
              <div style={{
                fontFamily: 'var(--font-display, "Cormorant Garamond", serif)',
                fontStyle: 'italic', fontSize: 28, letterSpacing: '-0.02em',
                lineHeight: 1, marginBottom: 6,
                color: 'var(--fg, #f5f5f5)',
              }}>
                {m.label}
              </div>
              {/* Caption */}
              <p style={{
                margin: '6px 0 14px', fontSize: 12.5, lineHeight: 1.5,
                color: 'var(--fg-dim, #aaa)',
                minHeight: 36,
              }}>
                {stats.caption || ''}
              </p>
              {/* Stats row */}
              <div style={{
                display: 'flex', gap: 6, flexWrap: 'wrap',
                fontFamily: 'var(--font-mono, ui-monospace, monospace)', fontSize: 10,
                letterSpacing: '0.06em',
              }}>
                <span style={{
                  padding: '3px 8px', borderRadius: 999,
                  border: '1px solid var(--line-soft, rgba(255,255,255,0.08))',
                  color: 'var(--fg-dim, #aaa)',
                  background: 'var(--bg-raised, rgba(255,255,255,0.02))',
                }}>{stats.value} {stats.sublabel || m.metricLabel}</span>
                {tags.map((t) => (
                  <span key={t} style={{
                    padding: '3px 8px', borderRadius: 999,
                    border: '1px solid var(--line-soft, rgba(255,255,255,0.08))',
                    color: 'var(--fg-dim, #aaa)',
                    background: 'var(--bg-raised, rgba(255,255,255,0.02))',
                  }}>{t}</span>
                ))}
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}

// =============================================================================
// GUILD BOARD — home landing with hero + quest grid (manga skin only)
// =============================================================================

function GuildBoard({ who, onActivateModule, getModuleStats }: {
  who: Character
  onActivateModule: (id: ModuleId) => void
  getModuleStats: (id: ModuleId) => { value: string | number; sublabel?: string; tags?: string[]; caption?: string }
}) {
  const copy = HERO_COPY[who]
  return (
    <div className="gb-root">
      <div className="gb-sfx-1">{who === 'natsu' ? 'DON !!' : 'KIRA ★'}</div>

      <div className="gb-hero">
        <div className="gb-hero-img-wrap">
          <div className="gb-hero-aura" />
          <img className="gb-hero-img" src={PORTRAITS[who]} alt={who} />
        </div>
        <div className="gb-hero-copy">
          <div className="gb-hero-kicker">{copy.kicker}</div>
          <h1 className="gb-hero-title">
            {copy.titlePart1} <span className="gb-hero-title-accent">{copy.titleAccent}</span>
          </h1>
          <p className="gb-hero-sub">{copy.sub}</p>
        </div>
      </div>

      <div className="gb-board-title">TABLEAU DES QUÊTES</div>

      <div className="gb-quests">
        {MODULES.map((m) => {
          const stats = getModuleStats(m.id)
          const Icon = m.icon
          const tags = (stats.tags || []).slice(0, 2)
          return (
            <article
              key={m.id}
              className="gb-quest"
              onClick={() => onActivateModule(m.id)}
              onDoubleClick={() => onActivateModule(m.id)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => { if (e.key === 'Enter') onActivateModule(m.id) }}
            >
              <span className={`gb-quest-rank r-${m.rank.toLowerCase()}`}>Rang {m.rank}</span>
              <div className="gb-quest-icon-box" style={{ color: m.color }}>
                <Icon size={26} strokeWidth={2.3} />
              </div>
              <div className="gb-quest-label">{m.kicker}</div>
              <h3 className="gb-quest-title">{m.label}</h3>
              <p className="gb-quest-desc">{stats.caption || ''}</p>
              <div className="gb-quest-stats">
                <span className="gb-quest-stat">{stats.value} {stats.sublabel || m.metricLabel}</span>
                {tags.map((t) => <span key={t} className="gb-quest-stat">{t}</span>)}
              </div>
              <div className="gb-quest-footer">
                <span className="gb-quest-reward">{m.reward}</span>
                <span className="gb-quest-kbd">⌘{m.shortcut}</span>
              </div>
            </article>
          )
        })}
      </div>
    </div>
  )
}

// =============================================================================
// DOCK — bottom-center manga pill with module icons
// =============================================================================

function MangaDock({ activeModule, onOpenModule, onCloseModule, isOpen }: {
  activeModule: ModuleId
  onOpenModule: (id: ModuleId) => void
  onCloseModule: () => void
  isOpen: boolean
}) {
  return (
    <div className="as-dock">
      <button
        type="button"
        className={`as-dock-icon ${!isOpen ? 'is-active' : ''}`}
        onClick={onCloseModule}
        title="Tableau (Esc)"
      >
        <Sparkles size={18} strokeWidth={2.3} />
      </button>
      <div className="as-dock-divider" />
      {MODULES.map((m) => {
        const Icon = m.icon
        const active = isOpen && activeModule === m.id
        return (
          <button
            key={m.id}
            type="button"
            className={`as-dock-icon ${active ? 'is-active' : ''}`}
            onClick={() => onOpenModule(m.id)}
            title={`${m.label} · ⌘${m.shortcut}`}
            style={active ? ({ '--mod-color': m.color } as React.CSSProperties) : undefined}
          >
            <Icon size={18} strokeWidth={2.3} />
          </button>
        )
      })}
    </div>
  )
}

// =============================================================================
// COMPANION — floating character portrait with speech bubble
// =============================================================================

function Companion({ who, activeModule, isOpen }: { who: Character; activeModule: ModuleId; isOpen: boolean }) {
  // v82q : the manga companion (Natsu/Lucy portrait + Fairy Tail quotes
  // like "Choisis une quête !" / "Une Porte à ouvrir ?") is one of the
  // most overtly manga elements on screen. Hide it when the user picked
  // an Aurora skin — they explicitly opted out of "cette interface".
  // The early return goes BEFORE any hook call so we don't violate
  // Rules of Hooks if the skin changes mid-session.
  const isManga = readUiSkin() === 'manga'
  const [visible, setVisible] = useState(false)
  const [line, setLine] = useState<string | null>(null)

  useEffect(() => {
    const lines = COMPANION_LINES[who]
    const text = isOpen ? (lines[activeModule] ?? null) : (who === 'natsu' ? 'Choisis une quête !' : 'Une Porte à ouvrir ?')
    setLine(text)
    setVisible(true)
    const t = window.setTimeout(() => setVisible(false), 5000)
    return () => window.clearTimeout(t)
  }, [who, activeModule, isOpen])

  // Conditional render goes here, AFTER all hook calls.
  if (!isManga) return null

  return (
    <div className="ft-companion">
      {visible && line && (
        <div className="ft-companion-bubble" onClick={() => setVisible(false)}>{line}</div>
      )}
      <div
        className="ft-companion-char"
        onClick={() => { setLine(COMPANION_LINES[who][activeModule] ?? line); setVisible(true) }}
      >
        <img src={PORTRAITS[who]} alt={who} />
      </div>
    </div>
  )
}

// =============================================================================
// SLASH COMMAND PALETTE
// =============================================================================

function SlashCommand({ open, position, onClose, onSelectModule }: {
  open: boolean
  position: { x: number; y: number }
  onClose: () => void
  onSelectModule: (id: ModuleId) => void
}) {
  const [query, setQuery] = useState('')
  const [idx, setIdx] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!open) return
    setQuery('')
    setIdx(0)
    setTimeout(() => inputRef.current?.focus(), 20)
  }, [open])

  const items = useMemo(() => {
    const q = query.trim().toLowerCase()
    return MODULES.filter((m) =>
      !q || m.label.toLowerCase().includes(q) || m.kicker.toLowerCase().includes(q),
    )
  }, [query])

  useEffect(() => {
    if (!open) return
    const h = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
      else if (e.key === 'ArrowDown') { e.preventDefault(); setIdx((i) => Math.min(items.length - 1, i + 1)) }
      else if (e.key === 'ArrowUp') { e.preventDefault(); setIdx((i) => Math.max(0, i - 1)) }
      else if (e.key === 'Enter') {
        e.preventDefault()
        const sel = items[idx]
        if (sel) { onSelectModule(sel.id); onClose() }
      }
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [open, items, idx, onClose, onSelectModule])

  if (!open) return null
  const maxX = window.innerWidth - 340
  const maxY = window.innerHeight - 380
  const px = Math.max(10, Math.min(maxX, position.x))
  const py = Math.max(10, Math.min(maxY, position.y))

  return (
    <motion.div
      initial={{ opacity: 0, y: -6, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.16, ease: [0.32, 0.72, 0, 1] }}
      className="slash-wrapper"
      style={{ left: px, top: py }}
    >
      <div className="slash-panel">
        <div className="slash-input-wrap">
          <Search size={14} className="text-[var(--ft-ink)]" strokeWidth={2} />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => { setQuery(e.target.value); setIdx(0) }}
            placeholder="Ouvrir un module…"
            className="slash-input"
            spellCheck={false}
          />
          <kbd>Esc</kbd>
        </div>
        <div className="slash-list">
          {items.length === 0 ? (
            <div className="px-4 py-6 text-center text-[12px] text-[var(--ft-muted)]">Aucun résultat</div>
          ) : items.map((m, i) => {
            const Icon = m.icon
            return (
              <div
                key={m.id}
                className={`slash-item ${i === idx ? 'is-selected' : ''}`}
                onMouseEnter={() => setIdx(i)}
                onClick={() => { onSelectModule(m.id); onClose() }}
              >
                <span className="icon" style={{ color: m.color }}>
                  <Icon size={13} strokeWidth={2.2} />
                </span>
                <span className="flex-1">{m.label}</span>
                <span className="text-[10px] text-[var(--ft-muted)]">{m.kicker}</span>
                <kbd>⌘{m.shortcut}</kbd>
              </div>
            )
          })}
        </div>
      </div>
    </motion.div>
  )
}

// =============================================================================
// MAIN SPATIAL CANVAS (Fairy Tail edition)
// =============================================================================

export function SpatialCanvas({
  activeModule,
  focusMode,
  setActiveModule,
  setFocusMode,
  getModuleStats,
  renderModule,
}: {
  activeModule: ModuleId
  focusMode: boolean
  setActiveModule: (id: ModuleId) => void
  setFocusMode: (v: boolean) => void
  getModuleStats: (id: ModuleId) => { value: string | number; sublabel?: string; tags?: string[]; caption?: string }
  renderModule: (id: ModuleId) => React.ReactNode
}) {
  const [who, setWho] = useCharacter()
  // Persist `isOpen` so a page refresh keeps the user in the module they were
  // using (mobile Safari reload / tunnel reconnect / HMR). Falls back to
  // `focusMode` so older profiles still open to the right place.
  const [isOpen, setIsOpen] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false
    try {
      const saved = window.localStorage.getItem('ft-module-open')
      if (saved === '1') return true
      if (saved === '0') return false
    } catch { /* noop */ }
    return false
  })
  useEffect(() => {
    try { window.localStorage.setItem('ft-module-open', isOpen ? '1' : '0') } catch { /* noop */ }
  }, [isOpen])
  const [slashOpen, setSlashOpen] = useState(false)
  const [slashPos, setSlashPos] = useState({ x: 0, y: 0 })
  const [localFocus, setLocalFocus] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false
    return window.localStorage.getItem('ft-focus') === '1'
  })
  useEffect(() => {
    try { window.localStorage.setItem('ft-focus', localFocus ? '1' : '0') } catch { /* noop */ }
  }, [localFocus])

  const { services, runtimeServices, installedModels } = useAppStore()
  const ollamaOk = services?.ollama || runtimeServices?.ollama?.running || false
  const comfyOk = services?.comfyui || runtimeServices?.comfyui?.running || false

  const openModule = (id: ModuleId) => {
    setActiveModule(id)
    setIsOpen(true)
  }

  const closeModule = () => { setIsOpen(false) }

  // Open the active module whenever external callers (e.g. quick-nav hotkeys,
  // voice commands) flip focus mode on — otherwise `setActiveModule` alone
  // just highlights a card on the guild board, which isn't what users expect.
  useEffect(() => {
    if (focusMode && !isOpen) setIsOpen(true)
  }, [focusMode, activeModule, isOpen])

  // Keyboard shortcuts
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName
      const inInput = tag === 'INPUT' || tag === 'TEXTAREA'
      if (slashOpen) return

      if (e.key === 'Escape') {
        if (isOpen) { e.preventDefault(); closeModule(); return }
        if (focusMode) { setFocusMode(false); return }
      }
      if ((e.key === '/' && !inInput) || (e.key === 'k' && (e.metaKey || e.ctrlKey))) {
        e.preventDefault()
        setSlashPos({ x: window.innerWidth / 2 - 160, y: window.innerHeight / 2 - 180 })
        setSlashOpen(true)
      }
      if ((e.metaKey || e.ctrlKey) && /^[1-8]$/.test(e.key)) {
        const idx = parseInt(e.key, 10) - 1
        const target = MODULES[idx]
        if (target) { e.preventDefault(); openModule(target.id) }
      }
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [isOpen, slashOpen, focusMode])

  const currentMeta = MODULES.find((m) => m.id === activeModule)

  return (
    <div className="as-root" data-char={who} data-focus={localFocus ? 'true' : 'false'}>
      <MangaHeader
        who={who}
        onChangeWho={setWho}
        ollamaOk={ollamaOk}
        comfyOk={comfyOk}
        installedCount={installedModels.length}
      />

      <main className="as-main">
        {/* Home : aurora skins get the editorial AuroraHomeBoard,
            manga keeps the legacy GuildBoard with quest cards + Natsu/Lucy. */}
        {!isOpen && (
          readUiSkin() === 'manga'
            ? <GuildBoard who={who} onActivateModule={openModule} getModuleStats={getModuleStats} />
            : <AuroraHomeBoard onActivateModule={openModule} getModuleStats={getModuleStats} />
        )}

        {/* Fullscreen module */}
        <AnimatePresence>
          {isOpen && (
            <motion.div
              className="spatial-fullscreen"
              data-module={activeModule}
              data-sfx1={MODULE_SFX[activeModule]?.[who]?.[0] ?? ''}
              data-sfx2={MODULE_SFX[activeModule]?.[who]?.[1] ?? ''}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 12 }}
              transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
            >
              <div className="spatial-fullscreen-header">
                <button type="button" className="spatial-back-btn" onClick={closeModule}>
                  <ArrowLeft size={13} strokeWidth={2.2} />
                  Canvas
                  <span className="ml-2 text-[10px] font-mono">Esc</span>
                </button>
                {currentMeta && (
                  <div className="spatial-back-btn" style={{ cursor: 'default' }}>
                    <currentMeta.icon size={12} style={{ color: currentMeta.color }} strokeWidth={2.2} />
                    <span>{currentMeta.label}</span>
                  </div>
                )}
              </div>
              <div className="spatial-fullscreen-content">
                {renderModule(activeModule)}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      {/* Dock */}
      <MangaDock
        activeModule={activeModule}
        onOpenModule={openModule}
        onCloseModule={closeModule}
        isOpen={isOpen}
      />

      {/* Helper pill */}
      <div className="as-helper">
        <kbd>/</kbd> commander
        <span className="as-helper-sep">·</span>
        <kbd>⌘K</kbd> palette
        <span className="as-helper-sep">·</span>
        <kbd>2×</kbd> ouvrir
      </div>

      {/* Floating Cowork toggle (inside a module) — opens the universal
          Aurora takeover surface (CoworkOverlay). On Tauri the IA gets full
          system rights; on web it's limited to fetch/clipboard/voice.
          Live counters surface on the right of the button : extensions
          actives + evts mobile en attente, polled every 8s. */}
      {isOpen && <CoworkFloatingButton />}

      {/* Downloads drawer */}
      <GeneratedDownloads />

      {/* Companion */}
      <Companion who={who} activeModule={activeModule} isOpen={isOpen} />

      {/* Slash command */}
      <AnimatePresence>
        {slashOpen && (
          <>
            <div
              className="fixed inset-0 z-[105]"
              onClick={() => setSlashOpen(false)}
              onContextMenu={(e) => e.preventDefault()}
            />
            <SlashCommand
              open={slashOpen}
              position={slashPos}
              onClose={() => setSlashOpen(false)}
              onSelectModule={openModule}
            />
          </>
        )}
      </AnimatePresence>
    </div>
  )
}

// ===========================================================================
// CoworkFloatingButton — floating "Cowork" pill with live counters that show:
//   - nb of Aurora-Connect browser extensions polling (= reachable browsers)
//   - nb of pending mobile events (iOS/Tasker waiting to be dispatched)
// Counters refresh every 8s via useCoworkLiveCounters; hidden when 0.
// ===========================================================================
function CoworkFloatingButton() {
  const counters = useCoworkLiveCounters(true)

  // Color-code the extension badge based on freshness :
  //   < 60 s    → green   (actively polling, healthy)
  //   60-120 s  → amber   (idle but should reconnect)
  //   > 120 s   → red     (stale, bridge thinks extension is gone)
  //   no data   → grey    (never connected this session)
  // v26 : seuils elargis 30/60 -> 60/120 pour match le nouveau bridge GC
  // window 120s. L extension polle toutes les ~30s mais un cycle rate (blip
  // reseau / SW dorment / self-watch reload) peut atteindre 60-90s, donc 60s
  // comme seuil green strict afficherait amber a tort.
  const extFreshMs = counters.freshestExtensionMs
  const extColor = !counters.hasData
    ? { bg: '#52525b', fg: '#fafafa', border: '#27272a' }
    : counters.extensionsCount === 0
      ? { bg: '#ef4444', fg: '#fef2f2', border: '#7f1d1d' }      // 0 ext = red
      : (extFreshMs ?? 999_999) < 60_000
        ? { bg: '#22c55e', fg: '#062012', border: '#052010' }    // green
        : (extFreshMs ?? 999_999) < 120_000
          ? { bg: '#fbbf24', fg: '#1a1308', border: '#1a1308' }  // amber
          : { bg: '#ef4444', fg: '#fef2f2', border: '#7f1d1d' }  // red

  const tooltipParts = [`Mode Cowork — Aurora prend la main`]
  if (counters.hasData) {
    if (counters.extensionsCount > 0 && extFreshMs !== null) {
      tooltipParts.push(`${counters.extensionsCount} extension${counters.extensionsCount > 1 ? 's' : ''} (poll il y a ${(extFreshMs / 1000).toFixed(0)}s)`)
    } else {
      tooltipParts.push('Aucune extension Aurora-Connect detectee')
    }
  }
  if (counters.hasData && counters.mobileEventsCount > 0) {
    tooltipParts.push(`${counters.mobileEventsCount} evt mobile en attente`)
  }

  return (
    <button
      type="button"
      className="manga-focus-btn"
      onClick={() => useCoworkStore.getState().toggle()}
      title={tooltipParts.join(' · ')}
      style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
    >
      <Sparkles size={13} strokeWidth={2.4} />
      <span>Cowork</span>
      {/* Extension status pill — always shown once we have data, color-coded
          by freshness so you instantly see if Aurora-Connect is alive. */}
      {counters.hasData && (
        <span
          aria-label={`${counters.extensionsCount} extensions, freshness ${extFreshMs ?? 'n/a'}ms`}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            minWidth: 18,
            height: 18,
            padding: '0 5px',
            borderRadius: 999,
            background: extColor.bg,
            color: extColor.fg,
            fontSize: 10,
            fontWeight: 700,
            lineHeight: 1,
            border: `1.5px solid ${extColor.border}`,
          }}
        >
          {counters.extensionsCount}
        </span>
      )}
      {counters.hasData && counters.mobileEventsCount > 0 && (
        <span
          aria-label={`${counters.mobileEventsCount} evts mobile en attente`}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            minWidth: 18,
            height: 18,
            padding: '0 5px',
            borderRadius: 999,
            background: '#fbbf24',
            color: '#1a1308',
            fontSize: 10,
            fontWeight: 700,
            lineHeight: 1,
            border: '1.5px solid #1a1308',
          }}
        >
          {counters.mobileEventsCount}
        </span>
      )}
    </button>
  )
}

// Export for App.tsx consumers — same shape as before
export const SPATIAL_MODULES = MODULES
