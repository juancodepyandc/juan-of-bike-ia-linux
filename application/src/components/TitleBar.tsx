import { useEffect, useState, type CSSProperties } from 'react'
import { Focus, Maximize2, Minimize2, Minus, Monitor, Square, X } from 'lucide-react'
import { useAppStore } from '../stores/appStore'
import { getRuntimeLabel, getRuntimeMode, isTauriRuntime } from '../utils/runtime'

type WindowControls = {
  minimize: () => Promise<void> | void
  toggleMaximize: () => Promise<void> | void
  close: () => Promise<void> | void
  setFullscreen: (value: boolean) => Promise<void> | void
  isFullscreen: () => Promise<boolean> | boolean
}

async function resolveWindowControls(): Promise<WindowControls | null> {
  if (!isTauriRuntime()) {
    return null
  }

  const { getCurrentWindow } = await import('@tauri-apps/api/window')
  const appWindow = getCurrentWindow()

  return {
    minimize: () => appWindow.minimize(),
    toggleMaximize: () => appWindow.toggleMaximize(),
    close: () => appWindow.close(),
    setFullscreen: (value) => appWindow.setFullscreen(value),
    isFullscreen: () => appWindow.isFullscreen(),
  }
}

async function toggleBrowserFullscreen() {
  if (!document.fullscreenElement) {
    await document.documentElement.requestFullscreen()
    return true
  }

  await document.exitFullscreen()
  return false
}

export default function TitleBar() {
  const runtimeMode = getRuntimeMode()
  const { focusMode, toggleFocusMode } = useAppStore()
  const [controls, setControls] = useState<WindowControls | null>(null)
  const [fullscreen, setFullscreen] = useState(false)

  useEffect(() => {
    let active = true

    resolveWindowControls()
      .then(async (nextControls) => {
        if (!active) return
        setControls(nextControls)
        if (nextControls) {
          const value = await nextControls.isFullscreen()
          if (active) setFullscreen(Boolean(value))
        }
      })
      .catch(() => {
        if (active) {
          setControls(null)
        }
      })

    return () => {
      active = false
    }
  }, [runtimeMode])

  useEffect(() => {
    if (isTauriRuntime()) {
      return
    }

    const handleChange = () => {
      setFullscreen(Boolean(document.fullscreenElement))
    }

    document.addEventListener('fullscreenchange', handleChange)
    return () => {
      document.removeEventListener('fullscreenchange', handleChange)
    }
  }, [])

  const handleToggleFullscreen = async () => {
    if (controls) {
      const next = !(await controls.isFullscreen())
      await controls.setFullscreen(next)
      setFullscreen(next)
      return
    }

    const next = await toggleBrowserFullscreen()
    setFullscreen(next)
  }

  const dragStyle = controls
    ? ({ WebkitAppRegion: 'drag' } as CSSProperties)
    : undefined

  const runtimeBadgeClass =
    runtimeMode === 'browser'
      ? 'border-aurora-yellow/30 bg-aurora-yellow/10 text-aurora-text'
      : 'border-aurora-green/30 bg-aurora-green/10 text-aurora-text'

  return (
    <div
      data-tauri-drag-region={runtimeMode === 'tauri' ? true : undefined}
      style={dragStyle}
      className="glass-strong flex min-h-[3.2rem] items-center justify-between gap-2 px-3 sm:min-h-[4.8rem] sm:gap-4 sm:px-4 md:px-5"
    >
      <div className="flex min-w-0 items-center gap-2 sm:gap-4">
        <div className="status-orb flex h-8 w-8 shrink-0 items-center justify-center text-white sm:h-12 sm:w-12">
          <Monitor size={14} className="sm:h-[18px] sm:w-[18px]" />
        </div>

        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
            <span className="truncate text-xs font-semibold uppercase tracking-[0.24em] text-aurora-text sm:text-sm md:text-base">
              Aurora IA
            </span>
            <span className={`rounded-full border px-2.5 py-1 text-[10px] font-medium mono-kicker ${runtimeBadgeClass}`}>
              {getRuntimeLabel()}
            </span>
            {focusMode && (
              <span className="rounded-full border border-aurora-cyan/30 bg-aurora-cyan/12 px-2.5 py-1 text-[10px] font-medium text-aurora-text mono-kicker">
                Focus
              </span>
            )}
          </div>
          <p className="mt-1 truncate text-[11px] text-aurora-text-dim">IA locale</p>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={toggleFocusMode}
          className={`rounded-full border px-3 py-2 text-[11px] transition-colors ${
            focusMode
              ? 'border-white/20 bg-white/[0.12] text-aurora-text'
              : 'border-white/10 bg-white/[0.04] text-aurora-text-muted hover:border-white/18 hover:text-aurora-text'
          }`}
          title="Mode focus"
        >
          <span className="inline-flex items-center gap-2">
            <Focus size={14} />
            <span className="hidden md:inline">Focus</span>
          </span>
        </button>

        <button
          onClick={() => void handleToggleFullscreen()}
          className={`rounded-full border px-3 py-2 text-[11px] transition-colors ${
            fullscreen
              ? 'border-white/20 bg-white/[0.12] text-aurora-text'
              : 'border-white/10 bg-white/[0.04] text-aurora-text-muted hover:border-white/18 hover:text-aurora-text'
          }`}
          title="Plein ecran"
        >
          <span className="inline-flex items-center gap-2">
            {fullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
            <span className="hidden md:inline">{fullscreen ? 'Quitter' : 'Plein ecran'}</span>
          </span>
        </button>

        {controls && (
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => void controls.minimize()}
              className="rounded-full border border-white/10 bg-white/[0.04] p-2 transition-colors hover:border-white/18"
              title="Reduire"
            >
              <Minus size={14} className="text-aurora-text" />
            </button>
            <button
              onClick={() => void controls.toggleMaximize()}
              className="rounded-full border border-white/10 bg-white/[0.04] p-2 transition-colors hover:border-white/18"
              title="Agrandir"
            >
              <Square size={12} className="text-aurora-text" />
            </button>
            <button
              onClick={() => void controls.close()}
              className="rounded-full border border-white/10 bg-white/[0.04] p-2 transition-colors hover:border-aurora-red"
              title="Fermer"
            >
              <X size={14} className="text-aurora-text" />
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
