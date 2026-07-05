/**
 * GlobalSearch — Ctrl+K / Cmd+K quick-finder across the whole app.
 *
 * Searches (fuzzy-ish, case-insensitive substring) :
 *   - Chat messages         (chatStore)
 *   - Academy items         (academyStore → category/subcat/item title + content)
 *   - Avatars               (appStore.avatarList)
 *   - Module shortcuts      (switch to conversation / image / etc.)
 *
 * Activating an item either navigates to it (setActiveModule) or opens the
 * right reader / conversation turn.
 *
 * Keyboard :
 *   Ctrl/⌘ + K   — open
 *   ↑ / ↓        — move selection
 *   Enter        — activate
 *   Esc          — close
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useAcademyStore } from '../stores/academyStore'
import { useAppStore } from '../stores/appStore'
import { useChatStore } from '../stores/chatStore'
import type { ModuleId } from '../types/app'

interface SearchHit {
  id: string
  kind: 'chat' | 'academy' | 'avatar' | 'module'
  title: string
  subtitle?: string
  onActivate: () => void
}

const MODULE_SHORTCUTS: Array<{ id: ModuleId; label: string; hint: string }> = [
  { id: 'conversation', label: 'Chat',        hint: 'Ouvrir la conversation' },
  { id: 'learning',     label: 'Académie',    hint: 'Ouvrir le module d\'apprentissage' },
  { id: 'image',        label: 'Image',       hint: 'Atelier FLUX' },
  { id: 'video',        label: 'Vidéo',       hint: 'Projecteur Wan2.2' },
  { id: 'code',         label: 'Code',        hint: 'Collection cartes de code' },
  { id: 'drawing',      label: 'Dessin',      hint: 'Sumi-e sketch2img' },
  { id: '3d',           label: '3D',          hint: 'Holographic turntable' },
  { id: 'cyber',        label: 'Cyber',       hint: 'Dojo des katas' },
  { id: 'voice',        label: 'Voice',       hint: 'Copilote vocal' },
]

export default function GlobalSearch() {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [sel, setSel] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

  const setActiveModule = useAppStore((s) => s.setActiveModule)
  const chatMessages   = useChatStore((s) => s.messages)
  const categories     = useAcademyStore((s) => s.categories)
  const avatars        = useAppStore((s) => s.avatarList)
  const setSelectedAvatar = useAppStore((s) => s.setSelectedAvatar)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault(); setOpen((v) => !v)
      } else if (open && e.key === 'Escape') {
        setOpen(false)
      }
    }
    const onOpenEvent = () => setOpen(true)
    window.addEventListener('keydown', onKey)
    window.addEventListener('aurora:open-global-search', onOpenEvent)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('aurora:open-global-search', onOpenEvent)
    }
  }, [open])

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 20)
  }, [open])

  const hits: SearchHit[] = useMemo(() => {
    const q = query.trim().toLowerCase()
    const results: SearchHit[] = []
    // Module shortcuts — always visible even with empty query
    for (const m of MODULE_SHORTCUTS) {
      if (!q || m.label.toLowerCase().includes(q) || m.hint.toLowerCase().includes(q)) {
        results.push({
          id: `mod-${m.id}`,
          kind: 'module',
          title: m.label,
          subtitle: m.hint,
          onActivate: () => { setActiveModule(m.id); setOpen(false) },
        })
      }
    }
    if (!q) return results.slice(0, 40)
    // Academy — titles + first 120 chars of content
    for (const cat of categories) {
      for (const item of cat.items) {
        if (item.title.toLowerCase().includes(q) || String(item.content).toLowerCase().includes(q)) {
          results.push({
            id: `ay-${item.id}`,
            kind: 'academy',
            title: item.title,
            subtitle: `${cat.name} · ${cat.subCategories.find((s) => s.id === item.subCategoryId)?.name || 'Académie'}`,
            onActivate: () => {
              setActiveModule('learning')
              window.dispatchEvent(new CustomEvent('ay-open-item', { detail: { itemId: item.id, categoryId: cat.id } }))
              setOpen(false)
            },
          })
        }
      }
    }
    // Chat — last 40 messages scanned
    const recent = chatMessages.slice(-40)
    for (let i = recent.length - 1; i >= 0; i--) {
      const msg = recent[i]
      if (msg.content && msg.content.toLowerCase().includes(q)) {
        results.push({
          id: `ct-${msg.id || i}`,
          kind: 'chat',
          title: msg.content.slice(0, 80),
          subtitle: `${msg.role === 'user' ? 'Tu' : 'IA'} · conversation`,
          onActivate: () => { setActiveModule('conversation'); setOpen(false) },
        })
        if (results.length > 40) break
      }
    }
    // Avatars
    for (const av of avatars) {
      if (av.label.toLowerCase().includes(q)) {
        results.push({
          id: `av-${av.id}`,
          kind: 'avatar',
          title: av.label,
          subtitle: `Avatar · ${av.type}`,
          onActivate: () => { setSelectedAvatar(av.id); setActiveModule('voice'); setOpen(false) },
        })
      }
    }
    return results.slice(0, 40)
  }, [query, chatMessages, categories, avatars, setActiveModule, setSelectedAvatar])

  useEffect(() => { setSel(0) }, [query])

  const onKeyInInput = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setSel((s) => Math.min(s + 1, Math.max(0, hits.length - 1))) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setSel((s) => Math.max(0, s - 1)) }
    else if (e.key === 'Enter') { e.preventDefault(); hits[sel]?.onActivate() }
  }

  if (!open) return null
  return createPortal(
    <div className="gs-overlay" onClick={() => setOpen(false)}>
      <div className="gs-panel" onClick={(e) => e.stopPropagation()}>
        <input
          ref={inputRef}
          className="gs-input"
          placeholder="Recherche · conversations, fiches, avatars, modules…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={onKeyInInput}
        />
        <div className="gs-results">
          {hits.length === 0 ? (
            <div className="gs-empty">Aucun résultat</div>
          ) : hits.map((h, i) => (
            <button
              key={h.id}
              type="button"
              className={`gs-hit kind-${h.kind} ${i === sel ? 'is-sel' : ''}`}
              onMouseEnter={() => setSel(i)}
              onClick={h.onActivate}>
              <span className="gs-hit-kind">{
                h.kind === 'chat' ? '💬' : h.kind === 'academy' ? '📘' : h.kind === 'avatar' ? '🪄' : '✦'
              }</span>
              <span className="gs-hit-text">
                <span className="gs-hit-title">{h.title}</span>
                {h.subtitle && <span className="gs-hit-subtitle">{h.subtitle}</span>}
              </span>
            </button>
          ))}
        </div>
        <div className="gs-foot">
          <span>↑↓ naviguer</span>
          <span>Entrée ouvrir</span>
          <span>Échap fermer</span>
        </div>
      </div>
    </div>,
    document.body,
  )
}
