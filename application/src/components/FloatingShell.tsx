import { useEffect, useMemo, useRef, useState } from 'react'
import { motion, useMotionValue, useSpring, useTransform, type MotionValue } from 'framer-motion'
import {
  Box,
  Code2,
  Command as CommandIcon,
  GraduationCap,
  Image as ImageIcon,
  MessageSquare,
  Paintbrush,
  Search,
  Settings,
  Sidebar as SidebarIcon,
  Sparkles,
  Video,
  Zap,
  type LucideIcon,
} from 'lucide-react'
import { useAppStore } from '../stores/appStore.ts'
import type { ModuleId } from '../types/app.ts'

interface ModuleDef {
  id: ModuleId
  label: string
  icon: LucideIcon
  shortcut: string
  color: string
}

const MODULES: ModuleDef[] = [
  { id: 'conversation', label: 'Chat', icon: MessageSquare, shortcut: '1', color: 'var(--color-mod-conv)' },
  { id: 'image', label: 'Image', icon: ImageIcon, shortcut: '2', color: 'var(--color-mod-image)' },
  { id: 'code', label: 'Code', icon: Code2, shortcut: '3', color: 'var(--color-mod-code)' },
  { id: 'video', label: 'Vidéo', icon: Video, shortcut: '4', color: 'var(--color-mod-video)' },
  { id: 'drawing', label: 'Dessin', icon: Paintbrush, shortcut: '5', color: 'var(--color-mod-drawing)' },
  { id: '3d', label: '3D', icon: Box, shortcut: '6', color: 'var(--color-mod-3d)' },
  { id: 'learning', label: 'Académie', icon: GraduationCap, shortcut: '7', color: 'var(--color-mod-learn)' },
]

// ============================================================
// DOCK ITEM — magnifies when mouse is close (macOS dock)
// ============================================================

function DockItem({
  mouseX,
  module,
  isActive,
  onClick,
}: {
  mouseX: MotionValue<number>
  module: ModuleDef
  isActive: boolean
  onClick: () => void
}) {
  const ref = useRef<HTMLButtonElement>(null)
  const Icon = module.icon

  const distance = useTransform(mouseX, (val) => {
    const rect = ref.current?.getBoundingClientRect() ?? { x: 0, width: 0 }
    return val - (rect.x + rect.width / 2)
  })

  const widthTransform = useTransform(distance, [-140, 0, 140], [44, 66, 44])
  const width = useSpring(widthTransform, { mass: 0.1, stiffness: 170, damping: 14 })

  return (
    <motion.button
      ref={ref}
      style={
        {
          width,
          height: width,
          ['--mod-color' as string]: module.color,
        } as unknown as React.CSSProperties & Record<string, string>
      }
      onClick={onClick}
      className={`dock-icon ${isActive ? 'is-active' : ''}`}
      aria-label={module.label}
    >
      <motion.div
        style={{ width: useTransform(width, (w) => Math.min(20, w * 0.36)) }}
        className="flex items-center justify-center"
      >
        <Icon size={18} strokeWidth={isActive ? 2.4 : 2} />
      </motion.div>
      <span className="dock-tooltip">
        {module.label}
        <kbd>⌘{module.shortcut}</kbd>
      </span>
    </motion.button>
  )
}

// ============================================================
// FLOATING DOCK
// ============================================================

export function FloatingDock({
  activeModule,
  onSelect,
  onOpenCommand,
  ollamaOk,
  comfyOk,
}: {
  activeModule: ModuleId
  onSelect: (id: ModuleId) => void
  onOpenCommand: () => void
  ollamaOk: boolean
  comfyOk: boolean
}) {
  const mouseX = useMotionValue(Infinity)

  return (
    <div className="dock-container safe-bottom">
      <motion.div
        initial={{ y: 30, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ delay: 0.15, type: 'spring', stiffness: 260, damping: 24 }}
        className="dock-pill"
        onMouseMove={(e) => mouseX.set(e.pageX)}
        onMouseLeave={() => mouseX.set(Infinity)}
      >
        <button
          onClick={onOpenCommand}
          className="dock-primary"
          aria-label="Command palette (⌘K)"
        >
          <CommandIcon size={18} strokeWidth={2.5} />
          <span className="dock-tooltip">Command palette<kbd>⌘K</kbd></span>
        </button>

        <div className="dock-divider" />

        {MODULES.map((m) => (
          <DockItem
            key={m.id}
            mouseX={mouseX}
            module={m}
            isActive={m.id === activeModule}
            onClick={() => onSelect(m.id)}
          />
        ))}

        <div className="dock-divider" />

        <div className="dock-status">
          <span className={`dock-status-dot ${ollamaOk ? 'is-ok' : ''}`} title={`Ollama ${ollamaOk ? 'actif' : 'hors ligne'}`} />
          <span className={`dock-status-dot ${comfyOk ? 'is-ok' : ''}`} title={`ComfyUI ${comfyOk ? 'actif' : 'hors ligne'}`} />
        </div>
      </motion.div>
    </div>
  )
}

// ============================================================
// MINI HEADER
// ============================================================

export function MiniHeader({
  activeModule,
  focusMode,
  onToggleFocus,
  onToggleRail,
  railVisible,
  onOpenSettings,
}: {
  activeModule: ModuleId
  focusMode: boolean
  onToggleFocus: () => void
  onToggleRail?: () => void
  railVisible?: boolean
  onOpenSettings?: () => void
}) {
  const def = MODULES.find((m) => m.id === activeModule)
  if (!def) return null
  const Icon = def.icon

  if (focusMode) return null

  return (
    <motion.header
      initial={{ y: -12, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ delay: 0.05, type: 'spring', stiffness: 300, damping: 28 }}
      className="mini-header"
      data-tauri-drag-region
    >
      <div
        className="h-6 w-6 rounded-full flex items-center justify-center shrink-0"
        style={{
          background: 'linear-gradient(135deg, var(--color-aurora-brand-soft), var(--color-aurora-brand-dim))',
          boxShadow: 'inset 0 1px 0 0 rgba(255,255,255,0.2), 0 1px 2px rgba(0,0,0,0.3)',
        }}
      >
        <Sparkles size={11} className="text-[#1b1510]" strokeWidth={2.5} />
      </div>
      <div className="mini-header-title">
        <span className="text-[var(--color-aurora-text-muted)]">Aurora</span>
        <span className="mini-header-sep">/</span>
        <motion.span
          key={def.id}
          initial={{ opacity: 0, y: -4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.24, ease: [0.32, 0.72, 0, 1] }}
          className="flex items-center gap-1.5"
          style={{ color: def.color }}
        >
          <Icon size={11} strokeWidth={2.5} />
          {def.label}
        </motion.span>
      </div>
      <div className="mini-header-actions">
        {onToggleRail && (
          <button
            onClick={onToggleRail}
            className="mini-header-btn"
            title={railVisible ? 'Masquer le panneau' : 'Afficher le panneau'}
          >
            <SidebarIcon size={12} />
          </button>
        )}
        <button
          onClick={onToggleFocus}
          className="mini-header-btn"
          title="Mode focus (Esc)"
        >
          <Zap size={12} />
        </button>
        {onOpenSettings && (
          <button onClick={onOpenSettings} className="mini-header-btn" title="Réglages">
            <Settings size={12} />
          </button>
        )}
      </div>
    </motion.header>
  )
}

// ============================================================
// COMMAND CENTER — morphs from dock primary
// ============================================================

type CommandAction = {
  id: string
  label: string
  hint?: string
  icon: LucideIcon
  section: string
  action: () => void
  keywords: string
}

export function CommandCenter({
  open,
  onClose,
  onSelectModule,
}: {
  open: boolean
  onClose: () => void
  onSelectModule: (id: ModuleId) => void
}) {
  const [query, setQuery] = useState('')
  const [idx, setIdx] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

  const items = useMemo<CommandAction[]>(() => {
    const navItems: CommandAction[] = MODULES.map((m) => ({
      id: `nav:${m.id}`,
      label: `Ouvrir ${m.label}`,
      hint: `⌘${m.shortcut}`,
      icon: m.icon,
      section: 'Navigation',
      keywords: `${m.label.toLowerCase()} module ${m.id}`,
      action: () => {
        onSelectModule(m.id)
        onClose()
      },
    }))
    return navItems
  }, [onSelectModule, onClose])

  const filtered = useMemo(() => {
    if (!query.trim()) return items
    const q = query.toLowerCase().trim()
    return items.filter((it) => it.label.toLowerCase().includes(q) || it.keywords.includes(q))
  }, [query, items])

  const grouped = useMemo(() => {
    const byS: Record<string, CommandAction[]> = {}
    for (const it of filtered) {
      if (!byS[it.section]) byS[it.section] = []
      byS[it.section].push(it)
    }
    return byS
  }, [filtered])

  useEffect(() => {
    if (!open) return
    setQuery('')
    setIdx(0)
    setTimeout(() => inputRef.current?.focus(), 20)
  }, [open])

  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
      else if (e.key === 'ArrowDown') {
        e.preventDefault()
        setIdx((i) => Math.min(filtered.length - 1, i + 1))
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        setIdx((i) => Math.max(0, i - 1))
      } else if (e.key === 'Enter') {
        e.preventDefault()
        filtered[idx]?.action()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, filtered, idx, onClose])

  if (!open) return null
  return (
    <>
      <motion.div
        className="command-backdrop"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.18 }}
        onClick={onClose}
      />
      <motion.div
        className="command-panel"
        initial={{ opacity: 0, scale: 0.92, y: -12 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ type: 'spring', stiffness: 320, damping: 28 }}
      >
            <div className="command-input-wrap">
              <Search size={16} className="text-[var(--color-aurora-text-muted)] shrink-0" strokeWidth={2} />
              <input
                ref={inputRef}
                type="text"
                value={query}
                onChange={(e) => { setQuery(e.target.value); setIdx(0) }}
                placeholder="Rechercher module, action, cours…"
                className="command-input"
                spellCheck={false}
              />
              <kbd>Esc</kbd>
            </div>
            <div className="command-list">
              {filtered.length === 0 ? (
                <div className="command-empty">Aucun résultat pour « {query} »</div>
              ) : (
                Object.entries(grouped).map(([section, sectionItems]) => (
                  <div key={section}>
                    <div className="command-section-label">{section}</div>
                    {sectionItems.map((it) => {
                      const globalIdx = filtered.indexOf(it)
                      const Icon = it.icon
                      return (
                        <div
                          key={it.id}
                          onMouseEnter={() => setIdx(globalIdx)}
                          onClick={it.action}
                          className={`command-item ${globalIdx === idx ? 'is-selected' : ''}`}
                        >
                          <span className="icon-wrap">
                            <Icon size={14} strokeWidth={2} />
                          </span>
                          <span className="label">{it.label}</span>
                          {it.hint && <kbd>{it.hint}</kbd>}
                        </div>
                      )
                    })}
                  </div>
                ))
              )}
        </div>
      </motion.div>
    </>
  )
}

// ============================================================
// FLOATING SHELL — Entire shell
// ============================================================

export function FloatingShell({
  activeModule,
  focusMode,
  onToggleFocus,
  onSelectModule,
  railSlot,
  children,
}: {
  activeModule: ModuleId
  focusMode: boolean
  onToggleFocus: () => void
  onSelectModule: (id: ModuleId) => void
  railSlot?: React.ReactNode
  children: React.ReactNode
}) {
  const [commandOpen, setCommandOpen] = useState(false)
  const [railVisible, setRailVisible] = useState(true)
  const { services, runtimeServices } = useAppStore()
  const ollamaOk = services?.ollama || runtimeServices?.ollama?.running || false
  const comfyOk = services?.comfyui || runtimeServices?.comfyui?.running || false

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setCommandOpen((o) => !o)
      }
      if ((e.metaKey || e.ctrlKey) && !e.shiftKey && /^[1-7]$/.test(e.key)) {
        const idx = parseInt(e.key, 10) - 1
        const target = MODULES[idx]?.id
        if (target) {
          e.preventDefault()
          onSelectModule(target)
        }
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onSelectModule])

  return (
    <div className="relative flex h-dvh w-screen overflow-hidden" style={{ background: 'var(--color-aurora-bg)' }}>
      <MiniHeader
        activeModule={activeModule}
        focusMode={focusMode}
        onToggleFocus={onToggleFocus}
        onToggleRail={railSlot ? () => setRailVisible((v) => !v) : undefined}
        railVisible={railVisible}
      />

      <div className="flex-1 flex min-h-0 relative">
        <main
          className={`relative flex-1 min-w-0 min-h-0 overflow-hidden transition-all duration-300 ${
            focusMode ? 'pt-4' : 'pt-[60px]'
          }`}
          style={{ paddingBottom: focusMode ? 16 : 80 }}
        >
          <div className="h-full overflow-y-auto overflow-x-hidden scroll-shell px-0">
            {children}
          </div>
        </main>

        {!focusMode && railVisible && railSlot && (
          <motion.aside
            initial={{ x: 20, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 20, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 280, damping: 28 }}
            className="hidden xl:block w-[280px] shrink-0 overflow-y-auto scroll-shell border-l border-[var(--color-aurora-border)]"
            style={{ background: 'var(--color-aurora-bg-2)', paddingTop: 60, paddingBottom: 80 }}
          >
            {railSlot}
          </motion.aside>
        )}
      </div>

      {!focusMode && (
        <FloatingDock
          activeModule={activeModule}
          onSelect={onSelectModule}
          onOpenCommand={() => setCommandOpen(true)}
          ollamaOk={ollamaOk}
          comfyOk={comfyOk}
        />
      )}

      <CommandCenter
        open={commandOpen}
        onClose={() => setCommandOpen(false)}
        onSelectModule={onSelectModule}
      />
    </div>
  )
}

export const FLOATING_MODULES = MODULES
