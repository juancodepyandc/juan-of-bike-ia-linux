import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  Box,
  ChevronLeft,
  ChevronRight,
  Code2,
  Command,
  GraduationCap,
  Image as ImageIcon,
  MessageSquare,
  Paintbrush,
  Search,
  Settings,
  Sparkles,
  Video,
  Zap,
  type LucideIcon,
} from 'lucide-react'
import { useAppStore } from '../stores/appStore'
import { useCoworkStore } from '../stores/coworkStore'
import type { ModuleId } from '../types/app'
import CoworkOverlay from './CoworkOverlay'

// v81t: AppShell.tsx is *orphaned dead code* — none of its exports
// (Sidebar, Topbar, AppShell, SHELL_MODULES) are imported anywhere.
// The live shell is in App.tsx (SpatialCanvas + MobileShell + CoworkRootMount).
// I had wired the skin-swap CoworkLauncher here in v81n, then realised it
// did nothing. The actual skin-swap lives in App.tsx CoworkRootMount.
// Keeping AppShell file around in case it's revived but stripping the
// stale skin import to avoid confusion when grep-auditing.

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

function ServiceDot({ ok, label }: { ok: boolean; label: string }) {
  return (
    <div className="flex items-center gap-2" title={`${label} · ${ok ? 'actif' : 'hors ligne'}`}>
      <span className="relative flex items-center justify-center w-2 h-2">
        <span
          className={`h-1.5 w-1.5 rounded-full transition-colors ${ok ? 'bg-[var(--color-aurora-ok)]' : 'bg-[var(--color-aurora-text-faint)]'}`}
        />
        {ok && (
          <span className="absolute inset-0 rounded-full bg-[var(--color-aurora-ok)] opacity-30 animate-ping" />
        )}
      </span>
      <span className="text-[11px] font-medium text-[var(--color-aurora-text-muted)]">{label}</span>
    </div>
  )
}

export function Sidebar({
  collapsed,
  onToggleCollapse,
  onOpenCommand,
}: {
  collapsed: boolean
  onToggleCollapse: () => void
  onOpenCommand: () => void
}) {
  const { activeModule, setActiveModule, services, runtimeServices, installedModels } = useAppStore()

  const ollamaOk = services?.ollama || runtimeServices?.ollama?.running || false
  const comfyOk = services?.comfyui || runtimeServices?.comfyui?.running || false

  return (
    <motion.aside
      layout
      initial={false}
      animate={{ width: collapsed ? 64 : 232 }}
      transition={{ type: 'spring', stiffness: 320, damping: 32 }}
      className="relative flex shrink-0 flex-col gap-2 px-2 py-3"
      style={{
        background: 'var(--color-aurora-bg-2)',
        borderRight: '1px solid var(--color-aurora-border)',
      }}
    >
      {/* Brand */}
      <div className="flex items-center gap-2.5 px-2 py-2 mb-1">
        <div
          className="h-8 w-8 rounded-[10px] flex items-center justify-center shrink-0"
          style={{
            background: 'linear-gradient(135deg, var(--color-aurora-brand-soft), var(--color-aurora-brand-dim))',
            boxShadow: 'inset 0 1px 0 0 rgba(255,255,255,0.2), 0 1px 2px rgba(0,0,0,0.3)',
          }}
        >
          <Sparkles size={14} className="text-[#1b1510]" strokeWidth={2.5} />
        </div>
        {!collapsed && (
          <motion.div
            initial={{ opacity: 0, x: -4 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -4 }}
            className="overflow-hidden"
          >
            <div className="text-[13px] font-semibold leading-tight text-[var(--color-aurora-text-strong)] tracking-tight">Aurora</div>
            <div className="text-[10px] font-medium text-[var(--color-aurora-text-dim)] leading-tight">IA locale</div>
          </motion.div>
        )}
      </div>

      {/* Command K */}
      <button
        onClick={onOpenCommand}
        className="group flex items-center gap-2 px-2 py-1.5 rounded-[10px] border border-[var(--color-aurora-border)] bg-[var(--color-aurora-surface)] text-left transition-all hover:border-[var(--color-aurora-border-strong)] hover:bg-[var(--color-aurora-surface-2)]"
      >
        <Search size={14} className="text-[var(--color-aurora-text-dim)] shrink-0" strokeWidth={2} />
        {!collapsed && (
          <>
            <span className="flex-1 text-[12px] text-[var(--color-aurora-text-dim)] group-hover:text-[var(--color-aurora-text-muted)]">Rechercher…</span>
            <kbd>⌘K</kbd>
          </>
        )}
      </button>

      {/* Nav */}
      <nav className="flex flex-col gap-0.5 mt-2">
        {!collapsed && (
          <div className="overline px-2 mb-1">Modules</div>
        )}
        {MODULES.map((m) => {
          const Icon = m.icon
          const isActive = m.id === activeModule
          return (
            <motion.button
              key={m.id}
              layout="position"
              onClick={() => setActiveModule(m.id)}
              className={`sidebar-item ${isActive ? 'is-active' : ''}`}
              style={isActive ? ({ ['--mod-color' as string]: m.color }) : undefined}
              title={collapsed ? m.label : undefined}
            >
              <span className="icon-wrap relative">
                <Icon size={15} strokeWidth={isActive ? 2.4 : 2} />
                {isActive && (
                  <motion.span
                    layoutId="sidebar-active-dot"
                    className="absolute -left-[10px] top-1/2 -translate-y-1/2 h-3.5 w-[2.5px] rounded-full"
                    style={{ background: m.color }}
                    transition={{ type: 'spring', stiffness: 380, damping: 30 }}
                  />
                )}
              </span>
              {!collapsed && (
                <>
                  <span className="flex-1 truncate">{m.label}</span>
                  <kbd className="opacity-0 group-hover:opacity-100 transition-opacity">⌘{m.shortcut}</kbd>
                </>
              )}
            </motion.button>
          )
        })}
      </nav>

      <div className="flex-1" />

      {/* Footer — services + collapse */}
      <div className="px-2 py-2 flex flex-col gap-2 border-t border-[var(--color-aurora-border)]">
        {!collapsed ? (
          <>
            <div className="flex items-center justify-between px-1">
              <ServiceDot ok={ollamaOk} label="Ollama" />
              <span className="text-[10px] font-medium text-[var(--color-aurora-text-faint)]">{installedModels.length} modèles</span>
            </div>
            <ServiceDot ok={comfyOk} label="ComfyUI" />
          </>
        ) : (
          <div className="flex flex-col gap-1.5 items-center">
            <span className={`h-1.5 w-1.5 rounded-full ${ollamaOk ? 'bg-[var(--color-aurora-ok)]' : 'bg-[var(--color-aurora-text-faint)]'}`} title="Ollama" />
            <span className={`h-1.5 w-1.5 rounded-full ${comfyOk ? 'bg-[var(--color-aurora-ok)]' : 'bg-[var(--color-aurora-text-faint)]'}`} title="ComfyUI" />
          </div>
        )}
      </div>

      {/* Collapse toggle */}
      <button
        onClick={onToggleCollapse}
        className="btn-icon mx-auto"
        title={collapsed ? 'Étendre' : 'Réduire'}
      >
        {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
      </button>
    </motion.aside>
  )
}

export function Topbar({
  activeModule,
  focusMode,
  onToggleFocus,
  rightSlot,
}: {
  activeModule: ModuleId
  focusMode: boolean
  onToggleFocus: () => void
  rightSlot?: React.ReactNode
}) {
  const moduleDef = MODULES.find((m) => m.id === activeModule)
  if (!moduleDef || focusMode) return null
  const Icon = moduleDef.icon

  return (
    <motion.header
      initial={{ opacity: 0, y: -6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22, ease: [0.32, 0.72, 0, 1] }}
      className="flex items-center gap-2 h-12 px-3 shrink-0"
      style={{
        background: 'var(--color-aurora-bg-2)',
        borderBottom: '1px solid var(--color-aurora-border)',
      }}
    >
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 min-w-0">
        <div
          className="h-7 w-7 rounded-[8px] flex items-center justify-center shrink-0 border border-[var(--color-aurora-border)]"
          style={{ background: 'var(--color-aurora-surface-2)', color: moduleDef.color }}
        >
          <Icon size={14} strokeWidth={2.2} />
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-1.5 text-[11px] text-[var(--color-aurora-text-dim)] leading-none">
            <span>Aurora</span>
            <ChevronRight size={10} />
            <span className="text-[var(--color-aurora-text-muted)]">{moduleDef.label}</span>
          </div>
        </div>
      </div>

      <div className="flex-1" />

      {rightSlot}

      <button
        onClick={onToggleFocus}
        className="btn-icon"
        title={focusMode ? 'Sortir du mode Cowork (Esc)' : 'Mode Cowork — Aurora prend la main'}
      >
        <Zap size={14} />
      </button>
      <button className="btn-icon" title="Réglages">
        <Settings size={14} />
      </button>
    </motion.header>
  )
}

export function AppShell({
  activeModule,
  focusMode,
  onToggleFocus,
  onOpenCommand,
  children,
}: {
  activeModule: ModuleId
  focusMode: boolean
  onToggleFocus: () => void
  onOpenCommand: () => void
  children: React.ReactNode
}) {
  const [collapsed, setCollapsed] = useState(false)
  // Auto-collapse on small viewports
  useEffect(() => {
    const check = () => setCollapsed(window.innerWidth < 900)
    check()
    window.addEventListener('resize', check)
    return () => window.removeEventListener('resize', check)
  }, [])

  return (
    <div className="relative flex h-dvh w-screen overflow-hidden" style={{ background: 'var(--color-aurora-bg)' }}>
      {/* Sidebar */}
      {!focusMode && (
        <Sidebar
          collapsed={collapsed}
          onToggleCollapse={() => setCollapsed((c) => !c)}
          onOpenCommand={onOpenCommand}
        />
      )}

      {/* Main area */}
      <div className="relative flex-1 flex flex-col min-w-0 overflow-hidden">
        <Topbar activeModule={activeModule} focusMode={focusMode} onToggleFocus={onToggleFocus} />
        <main className="relative flex-1 min-h-0 overflow-hidden">
          {children}
        </main>
      </div>

      {/* COWORK OVERLAY — Aurora takeover surface. Open via either:
            (a) the legacy focusMode toggle in the Topbar, or
            (b) useCoworkStore.getState().open() from anywhere (manga UI
                Focus button, command palette, slash command, etc.). */}
      <CoworkLauncher focusMode={focusMode} onCloseFocusMode={onToggleFocus} />
    </div>
  )
}

function CoworkLauncher({ focusMode, onCloseFocusMode }: { focusMode: boolean; onCloseFocusMode: () => void }) {
  const isCoworkOpen = useCoworkStore((s) => s.isOpen)
  const closeCowork = useCoworkStore((s) => s.close)
  const open = isCoworkOpen || focusMode

  const handleClose = () => {
    if (isCoworkOpen) closeCowork()
    if (focusMode) onCloseFocusMode()
  }

  // Dead-code launcher — see top-of-file note. Real skin-swap is in
  // App.tsx CoworkRootMount.
  return <CoworkOverlay open={open} onClose={handleClose} />
}

export const SHELL_MODULES = MODULES
