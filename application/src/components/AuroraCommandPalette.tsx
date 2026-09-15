/**
 * AuroraCommandPalette — global ⌘K module switcher.
 *
 * Mounted at the App root so it works on every skin (manga, V1, V3).
 * V3 has no Sidebar by design — this gives the user a discoverable
 * way to jump between modules without violating the source's
 * "zéro shell partagé" principle (it's invisible until ⌘K is pressed).
 *
 * Re-uses the .slash-* CSS classes from globals.css (originally for
 * SpatialCanvas's SlashCommand) so the visual treatment is consistent.
 */
import { useEffect, useMemo, useRef, useState, type MouseEvent } from 'react'
import { motion } from 'framer-motion'
import {
  Box, Code2, GraduationCap, Image as ImageIcon, MessageSquare,
  Mic, Paintbrush, Search, Shield, Sparkles, Video,
  type LucideIcon,
} from 'lucide-react'
import { useCoworkStore } from '../stores/coworkStore.ts'
import type { ModuleId } from '../types/app.ts'

type PaletteEntry = {
  id: ModuleId | 'cowork'
  label: string
  kicker: string
  icon: LucideIcon
  color: string
  kbd: string
}

// v82gg : module visités récemment, max 5, pour shortcut switch.
const RECENTS_KEY = 'aurora-palette-recents-v1'
const RECENTS_MAX = 5

function readRecents(): Array<ModuleId | 'cowork'> {
  if (typeof window === 'undefined') return []
  try {
    const raw = window.localStorage.getItem(RECENTS_KEY)
    if (!raw) return []
    const arr = JSON.parse(raw)
    return Array.isArray(arr)
      ? arr.filter((x): x is ModuleId | 'cowork' => typeof x === 'string')
      : []
  } catch { return [] }
}

function pushRecent(id: ModuleId | 'cowork') {
  if (typeof window === 'undefined') return
  try {
    const cur = readRecents().filter((m) => m !== id)
    const next = [id, ...cur].slice(0, RECENTS_MAX)
    window.localStorage.setItem(RECENTS_KEY, JSON.stringify(next))
  } catch { /* swallow */ }
}

// v82gh : modules épinglés en tête de palette (★ stable, indépendant des récents).
const PINNED_KEY = 'aurora-palette-pinned-v1'

function readPinned(): Array<ModuleId | 'cowork'> {
  if (typeof window === 'undefined') return []
  try {
    const raw = window.localStorage.getItem(PINNED_KEY)
    if (!raw) return []
    const arr = JSON.parse(raw)
    return Array.isArray(arr)
      ? arr.filter((x): x is ModuleId | 'cowork' => typeof x === 'string')
      : []
  } catch { return [] }
}

function togglePinned(id: ModuleId | 'cowork'): Array<ModuleId | 'cowork'> {
  const cur = readPinned()
  const next = cur.includes(id) ? cur.filter((m) => m !== id) : [...cur, id]
  try { window.localStorage.setItem(PINNED_KEY, JSON.stringify(next)) } catch { /* swallow */ }
  return next
}

const ENTRIES: PaletteEntry[] = [
  { id: 'cowork',       label: 'Cowork',       kicker: 'Orchestrator multi-agents', icon: Sparkles,      color: 'oklch(0.70 0.150 40)',  kbd: '⌘`' },
  { id: 'conversation', label: 'Conversation', kicker: 'Copilote IA',                icon: MessageSquare, color: 'oklch(0.72 0.120 200)', kbd: '⌘1' },
  { id: 'image',        label: 'Image',        kicker: 'Studio FLUX',                icon: ImageIcon,     color: 'oklch(0.70 0.140 320)', kbd: '⌘2' },
  { id: 'code',         label: 'Code',         kicker: 'Pipeline build',             icon: Code2,         color: 'oklch(0.72 0.120 145)', kbd: '⌘3' },
  { id: 'video',        label: 'Vidéo',        kicker: 'Wan2.2 cinema',              icon: Video,         color: 'oklch(0.68 0.130 260)', kbd: '⌘4' },
  { id: 'drawing',      label: 'Dessin',       kicker: 'Canvas + sketch2img',        icon: Paintbrush,    color: 'oklch(0.62 0.140 30)',  kbd: '⌘5' },
  { id: '3d',           label: '3D',           kicker: 'Mesh + rig',                 icon: Box,           color: 'oklch(0.74 0.130 60)',  kbd: '⌘6' },
  { id: 'cyber',        label: 'Cyber',        kicker: 'Crypto · réseau · CTF',      icon: Shield,        color: 'oklch(0.70 0.130 130)', kbd: '⌘7' },
  { id: 'learning',     label: 'Academy',      kicker: 'Labs · quiz · parcours',     icon: GraduationCap, color: 'oklch(0.74 0.110 90)',  kbd: '⌘8' },
  { id: 'voice',        label: 'Voice',        kicker: 'Studio vocal',               icon: Mic,           color: 'oklch(0.72 0.140 350)', kbd: '⌘V' },
]

export default function AuroraCommandPalette({
  open, onClose, onSelect,
}: {
  open: boolean
  onClose: () => void
  onSelect: (id: ModuleId) => void
}) {
  const [query, setQuery] = useState('')
  const [idx, setIdx] = useState(0)
  const [recents, setRecents] = useState<Array<ModuleId | 'cowork'>>(() => readRecents())
  const [pinned, setPinned] = useState<Array<ModuleId | 'cowork'>>(() => readPinned())
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!open) return
    setQuery('')
    setIdx(0)
    setRecents(readRecents())
    setPinned(readPinned())
    setTimeout(() => inputRef.current?.focus(), 20)
  }, [open])

  const items = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (q) {
      return ENTRIES.filter((e) =>
        e.label.toLowerCase().includes(q) || e.kicker.toLowerCase().includes(q),
      )
    }
    // v82gh : ordre query-vide = pinned → récents (hors pinned) → reste.
    const pinnedSet = new Set(pinned)
    const pinnedItems = pinned.flatMap((id) => {
      const found = ENTRIES.find((e) => e.id === id)
      return found ? [found] : []
    })
    if (recents.length === 0 && pinnedItems.length === 0) return ENTRIES
    const recentTrim = recents.slice(0, 3).filter((id) => !pinnedSet.has(id))
    const recentSet = new Set(recentTrim)
    const recentItems = recentTrim.flatMap((id) => {
      const found = ENTRIES.find((e) => e.id === id)
      return found ? [found] : []
    })
    const rest = ENTRIES.filter((e) => !pinnedSet.has(e.id) && !recentSet.has(e.id))
    return [...pinnedItems, ...recentItems, ...rest]
  }, [query, recents, pinned])

  // v82gh : compte des sections pour les headers visuels.
  const pinnedCount = useMemo(() => {
    if (query.trim()) return 0
    return pinned.flatMap((id) => ENTRIES.find((e) => e.id === id) ? [id] : []).length
  }, [query, pinned])
  const recentCount = useMemo(() => {
    if (query.trim()) return 0
    const pinnedSet = new Set(pinned)
    const recentSet = new Set(recents.slice(0, 3).filter((id) => !pinnedSet.has(id)))
    let count = 0
    for (let i = pinnedCount; i < items.length; i++) {
      if (recentSet.has(items[i].id)) count++
      else break
    }
    return count
  }, [query, recents, pinned, items, pinnedCount])

  const handleTogglePin = (id: ModuleId | 'cowork', e: MouseEvent) => {
    e.stopPropagation()
    setPinned(togglePinned(id))
  }

  useEffect(() => {
    if (!open) return
    const h = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { e.preventDefault(); onClose() }
      else if (e.key === 'ArrowDown') { e.preventDefault(); setIdx((i) => Math.min(items.length - 1, i + 1)) }
      else if (e.key === 'ArrowUp') { e.preventDefault(); setIdx((i) => Math.max(0, i - 1)) }
      else if (e.key === 'Enter') {
        e.preventDefault()
        const sel = items[idx]
        if (sel) { handleSelect(sel.id); onClose() }
      }
    }
    window.addEventListener('keydown', h, true)
    return () => window.removeEventListener('keydown', h, true)
  }, [open, items, idx, onClose])

  const handleSelect = (id: ModuleId | 'cowork') => {
    pushRecent(id)
    if (id === 'cowork') {
      useCoworkStore.getState().open()
      return
    }
    onSelect(id)
  }

  if (!open) return null

  return (
    <>
      {/* backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed', inset: 0,
          background: 'rgba(0,0,0,0.35)',
          backdropFilter: 'blur(2px)',
          zIndex: 9998,
        }}
      />
      <motion.div
        initial={{ opacity: 0, y: -6, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.16, ease: [0.32, 0.72, 0, 1] }}
        style={{
          position: 'fixed',
          top: 'min(20vh, 180px)',
          left: '50%',
          transform: 'translateX(-50%)',
          width: 'min(640px, 92vw)',
          zIndex: 9999,
          fontFamily: 'var(--font-sans, system-ui)',
        }}>
        <div style={{
          background: 'var(--bg-raised, oklch(0.13 0.013 250))',
          border: '1px solid var(--line, rgba(255,255,255,0.12))',
          borderRadius: 14,
          boxShadow: '0 32px 80px rgba(0,0,0,0.55), 0 4px 12px rgba(0,0,0,0.4)',
          overflow: 'hidden',
        }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10,
            padding: '14px 18px',
            borderBottom: '1px solid var(--line-soft, rgba(255,255,255,0.06))',
          }}>
            <Search size={14} color="var(--fg-mute, #888)" strokeWidth={2} />
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => { setQuery(e.target.value); setIdx(0) }}
              placeholder="Ouvrir un module…"
              spellCheck={false}
              style={{
                flex: 1, background: 'transparent', border: 'none', outline: 'none',
                color: 'var(--fg, #f5f5f5)',
                fontFamily: 'inherit', fontSize: 14,
              }} />
            <kbd style={{
              fontFamily: 'var(--font-mono, monospace)', fontSize: 10,
              color: 'var(--fg-mute, #888)',
              border: '1px solid var(--line, rgba(255,255,255,0.12))',
              padding: '2px 6px', borderRadius: 4,
            }}>Esc</kbd>
          </div>
          <div style={{ maxHeight: 420, overflowY: 'auto', padding: 6 }}>
            {items.length === 0 ? (
              <div style={{
                padding: 24, textAlign: 'center', fontSize: 12,
                color: 'var(--fg-mute, #777)',
              }}>Aucun résultat</div>
            ) : items.map((e, i) => {
              const Icon = e.icon
              const sel = i === idx
              const showPinHeader = pinnedCount > 0 && i === 0
              const showRecentsHeader = recentCount > 0 && i === pinnedCount
              const showRestHeader = (pinnedCount > 0 || recentCount > 0) && i === pinnedCount + recentCount
              const isPinned = pinned.includes(e.id)
              return (
                <div key={e.id}>
                  {showPinHeader && (
                    <div style={{
                      padding: '6px 12px 4px', fontSize: 9,
                      fontFamily: 'var(--font-mono, monospace)',
                      letterSpacing: '0.22em', textTransform: 'uppercase',
                      color: 'var(--fg-mute, #777)',
                    }}>★ Épinglés</div>
                  )}
                  {showRecentsHeader && (
                    <div style={{
                      padding: '8px 12px 4px', fontSize: 9,
                      fontFamily: 'var(--font-mono, monospace)',
                      letterSpacing: '0.22em', textTransform: 'uppercase',
                      color: 'var(--fg-mute, #777)',
                    }}>↻ Récents</div>
                  )}
                  {showRestHeader && (
                    <div style={{
                      padding: '8px 12px 4px', fontSize: 9,
                      fontFamily: 'var(--font-mono, monospace)',
                      letterSpacing: '0.22em', textTransform: 'uppercase',
                      color: 'var(--fg-mute, #777)',
                    }}>Modules</div>
                  )}
                <button
                  type="button"
                  onMouseEnter={() => setIdx(i)}
                  onClick={() => { handleSelect(e.id); onClose() }}
                  style={{
                    display: 'grid', gridTemplateColumns: '32px 1fr 24px auto', gap: 12,
                    width: '100%', alignItems: 'center',
                    padding: '10px 12px', borderRadius: 10,
                    background: sel ? 'var(--bg-card, rgba(255,255,255,0.04))' : 'transparent',
                    border: sel
                      ? '1px solid var(--line, rgba(255,255,255,0.12))'
                      : '1px solid transparent',
                    color: 'var(--fg, #f5f5f5)',
                    cursor: 'pointer', textAlign: 'left',
                    fontFamily: 'inherit',
                    transition: 'all .12s ease',
                  }}>
                  <span style={{
                    width: 32, height: 32, borderRadius: 8,
                    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                    background: sel ? e.color : 'var(--bg-card, rgba(255,255,255,0.04))',
                    color: sel ? 'var(--ink-1000, #0a0a0a)' : e.color,
                    boxShadow: sel ? `0 0 16px ${e.color}` : 'none',
                  }}>
                    <Icon size={16} strokeWidth={2.2} />
                  </span>
                  <span>
                    <div style={{ fontSize: 13, fontWeight: 500, lineHeight: 1.2 }}>{e.label}</div>
                    <div style={{
                      fontSize: 11, color: 'var(--fg-mute, #888)', marginTop: 2,
                      fontFamily: 'var(--font-mono, ui-monospace, monospace)',
                    }}>{e.kicker}</div>
                  </span>
                  <span
                    aria-label={isPinned ? 'Désépingler ce module' : 'Épingler ce module'}
                    title={isPinned ? 'Désépingler' : 'Épingler en tête'}
                    onClick={(ev) => handleTogglePin(e.id, ev)}
                    style={{
                      width: 24, height: 24, display: 'inline-flex',
                      alignItems: 'center', justifyContent: 'center',
                      cursor: 'pointer', fontSize: 14,
                      color: isPinned ? 'oklch(0.85 0.16 80)' : 'var(--fg-mute, #777)',
                      opacity: isPinned ? 1 : (sel ? 0.7 : 0.35),
                      transition: 'opacity .12s ease, color .12s ease',
                    }}>{isPinned ? '★' : '☆'}</span>
                  <kbd style={{
                    fontFamily: 'var(--font-mono, monospace)', fontSize: 10,
                    color: sel ? 'var(--fg, #f5f5f5)' : 'var(--fg-mute, #777)',
                    border: '1px solid var(--line, rgba(255,255,255,0.12))',
                    padding: '2px 6px', borderRadius: 4,
                  }}>{e.kbd}</kbd>
                </button>
                </div>
              )
            })}
          </div>
          <div style={{
            display: 'flex', gap: 14, padding: '8px 14px',
            borderTop: '1px solid var(--line-soft, rgba(255,255,255,0.06))',
            fontFamily: 'var(--font-mono, ui-monospace, monospace)', fontSize: 10,
            color: 'var(--fg-mute, #777)',
          }}>
            <span>↑↓ naviguer</span>
            <span>↵ ouvrir</span>
            <span>★ épingler</span>
            <span style={{ flex: 1 }} />
            {/* v82j9 : commit hash visible footer palette */}
            <span title={`Build · ${typeof __AURORA_BRANCH__ !== 'undefined' ? __AURORA_BRANCH__ : 'unknown'}`}
              style={{ opacity: 0.55 }}>
              {typeof __AURORA_COMMIT__ !== 'undefined' ? __AURORA_COMMIT__ : 'dev'}
            </span>
            <span>Esc fermer</span>
          </div>
        </div>
      </motion.div>
    </>
  )
}
