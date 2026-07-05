import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Bot,
  Box,
  Code2,
  GraduationCap,
  Image as ImageIcon,
  Layers,
  Map as MapIcon,
  MessageCircle,
  Paintbrush,
  Search,
  Sparkles,
  Target,
  Video,
  Volume2,
  type LucideIcon,
} from 'lucide-react'
import { useAppStore } from '../stores/appStore'
import type { ModuleId } from '../types/app'

type Command = {
  id: string
  label: string
  description?: string
  keywords: string
  icon: LucideIcon
  section: 'Navigation' | 'Actions' | 'Systeme'
  action: () => void
  shortcut?: string
}

export default function CommandPalette() {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const setActiveModule = useAppStore((state) => state.setActiveModule)
  const inputRef = useRef<HTMLInputElement | null>(null)

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setOpen((value) => !value)
      } else if (event.key === 'Escape' && open) {
        setOpen(false)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open])

  useEffect(() => {
    if (open) {
      setQuery('')
      setSelectedIndex(0)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [open])

  const openModule = useCallback(
    (moduleId: ModuleId) => {
      setActiveModule(moduleId)
      setOpen(false)
    },
    [setActiveModule],
  )

  const openFullscreen = useCallback(() => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen?.().catch(() => undefined)
    } else {
      document.exitFullscreen?.().catch(() => undefined)
    }
    setOpen(false)
  }, [])

  const commands: Command[] = useMemo(
    () => [
      {
        id: 'nav-conversation',
        label: 'Copilote conversation',
        description: 'Chat LLM multi-etapes avec verification',
        keywords: 'copilote chat conversation parler reflechir',
        icon: MessageCircle,
        section: 'Navigation',
        action: () => openModule('conversation'),
      },
      {
        id: 'nav-voice',
        label: 'Chat vocal live',
        description: 'Parler a l IA avec avatar 3D',
        keywords: 'voix vocal audio micro parler avatar',
        icon: Volume2,
        section: 'Navigation',
        action: () => openModule('voice'),
      },
      {
        id: 'nav-image',
        label: 'Studio Image (FLUX)',
        description: 'Generer des images FLUX',
        keywords: 'image photo dessin flux comfyui rendu',
        icon: ImageIcon,
        section: 'Navigation',
        action: () => openModule('image'),
      },
      {
        id: 'nav-code',
        label: 'Atelier Code',
        description: 'Generation code modele expert avec preview',
        keywords: 'code programmation dev build application',
        icon: Code2,
        section: 'Navigation',
        action: () => openModule('code'),
      },
      {
        id: 'nav-video',
        label: 'Atelier Video (Wan 2.2)',
        description: 'Generer des videos T2V/I2V',
        keywords: 'video film animation motion wan',
        icon: Video,
        section: 'Navigation',
        action: () => openModule('video'),
      },
      {
        id: 'nav-drawing',
        label: 'Canvas Dessin',
        description: 'Croquis live avec rendu FLUX',
        keywords: 'dessin canvas croquis sketch paint',
        icon: Paintbrush,
        section: 'Navigation',
        action: () => openModule('drawing'),
      },
      {
        id: 'nav-3d',
        label: 'Atelier 3D (Hunyuan/Blender)',
        description: 'Generer des meshes 3D avec animations',
        keywords: '3d mesh modele blender hunyuan',
        icon: Box,
        section: 'Navigation',
        action: () => openModule('3d'),
      },
      {
        id: 'nav-academie',
        label: 'Academie',
        description: 'Quiz, cours, fiches, parcours',
        keywords: 'apprendre ecole cours quiz fiches parcours revision',
        icon: GraduationCap,
        section: 'Navigation',
        action: () => openModule('learning'),
      },
      {
        id: 'action-fiches',
        label: 'Creer un deck de fiches',
        description: 'Lancer la generation de fiches de revision',
        keywords: 'fiche deck revision leitner flashcard',
        icon: Layers,
        section: 'Actions',
        action: () => openModule('learning'),
      },
      {
        id: 'action-quiz',
        label: 'Lancer un quiz',
        description: 'Verifier tes connaissances',
        keywords: 'quiz qcm tester interroger',
        icon: Target,
        section: 'Actions',
        action: () => openModule('learning'),
      },
      {
        id: 'action-parcours',
        label: 'Tracer un parcours',
        description: 'Itineraire d apprentissage verrouille',
        keywords: 'parcours itineraire route path',
        icon: MapIcon,
        section: 'Actions',
        action: () => openModule('learning'),
      },
      {
        id: 'sys-fullscreen',
        label: 'Plein ecran / Exit plein ecran',
        description: 'Basculer le mode plein ecran',
        keywords: 'fullscreen plein ecran f11',
        icon: Sparkles,
        section: 'Systeme',
        action: openFullscreen,
      },
      {
        id: 'sys-reload',
        label: 'Recharger l application',
        description: 'Refresh complet du shell',
        keywords: 'reload refresh reboot',
        icon: Bot,
        section: 'Systeme',
        action: () => window.location.reload(),
      },
    ],
    [openModule, openFullscreen],
  )

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return commands
    return commands.filter((command) => {
      const haystack = `${command.label} ${command.description ?? ''} ${command.keywords}`.toLowerCase()
      return haystack.includes(needle)
    })
  }, [commands, query])

  useEffect(() => {
    setSelectedIndex(0)
  }, [query])

  const activeCommand = filtered[selectedIndex] ?? null

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setSelectedIndex((value) => Math.min(filtered.length - 1, value + 1))
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setSelectedIndex((value) => Math.max(0, value - 1))
    } else if (event.key === 'Enter') {
      event.preventDefault()
      activeCommand?.action()
    }
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[90] flex items-start justify-center bg-black/60 backdrop-blur-sm p-4 pt-[10vh]"
          onClick={() => setOpen(false)}
        >
          <motion.div
            initial={{ opacity: 0, y: -16, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -16, scale: 0.98 }}
            transition={{ duration: 0.18 }}
            onClick={(event) => event.stopPropagation()}
            className="flex w-full max-w-xl flex-col overflow-hidden rounded-2xl border border-aurora-border bg-aurora-surface shadow-2xl"
          >
            <div className="flex items-center gap-3 border-b border-aurora-border/40 px-4 py-3">
              <Search size={16} className="text-aurora-text-dim" />
              <input
                ref={inputRef}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Tape pour chercher un module ou une action..."
                className="flex-1 bg-transparent text-sm text-aurora-text outline-none placeholder:text-aurora-text-dim"
              />
              <kbd className="rounded border border-aurora-border bg-aurora-surface-2 px-1.5 py-0.5 text-[10px] text-aurora-text-dim">
                Esc
              </kbd>
            </div>

            <div className="max-h-[60vh] overflow-y-auto p-2">
              {filtered.length === 0 ? (
                <p className="py-10 text-center text-xs text-aurora-text-dim">Aucun resultat.</p>
              ) : (
                Object.entries(
                  filtered.reduce<Record<string, Command[]>>((acc, command) => {
                    acc[command.section] = acc[command.section] ?? []
                    acc[command.section].push(command)
                    return acc
                  }, {}),
                ).map(([section, list]) => (
                  <div key={section} className="mb-2 last:mb-0">
                    <p className="px-2 py-1 text-[9px] font-semibold uppercase tracking-[0.22em] text-aurora-text-dim">
                      {section}
                    </p>
                    {list.map((command) => {
                      const Icon = command.icon
                      const globalIndex = filtered.indexOf(command)
                      const isActive = globalIndex === selectedIndex
                      return (
                        <button
                          key={command.id}
                          onClick={() => command.action()}
                          onMouseEnter={() => setSelectedIndex(globalIndex)}
                          className={`flex w-full items-center gap-3 rounded-xl px-2 py-2 text-left transition-colors ${
                            isActive ? 'bg-aurora-accent/15 text-aurora-text' : 'text-aurora-text hover:bg-aurora-surface-2'
                          }`}
                        >
                          <div
                            className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${
                              isActive ? 'bg-aurora-accent/25 text-aurora-accent' : 'bg-aurora-surface-2 text-aurora-text-dim'
                            }`}
                          >
                            <Icon size={14} />
                          </div>
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-sm">{command.label}</p>
                            {command.description && (
                              <p className="truncate text-[11px] text-aurora-text-dim">{command.description}</p>
                            )}
                          </div>
                          {isActive && (
                            <kbd className="rounded border border-aurora-border bg-aurora-surface-2 px-1.5 py-0.5 text-[10px] text-aurora-text-dim">
                              ↵
                            </kbd>
                          )}
                        </button>
                      )
                    })}
                  </div>
                ))
              )}
            </div>

            <div className="flex items-center justify-between border-t border-aurora-border/40 bg-aurora-surface-2/50 px-4 py-2 text-[10px] text-aurora-text-dim">
              <div className="flex items-center gap-3">
                <span>
                  <kbd className="rounded border border-aurora-border bg-aurora-surface-2 px-1 py-0.5">↑</kbd>{' '}
                  <kbd className="rounded border border-aurora-border bg-aurora-surface-2 px-1 py-0.5">↓</kbd> naviguer
                </span>
                <span>
                  <kbd className="rounded border border-aurora-border bg-aurora-surface-2 px-1 py-0.5">↵</kbd> choisir
                </span>
              </div>
              <span>
                <kbd className="rounded border border-aurora-border bg-aurora-surface-2 px-1 py-0.5">Ctrl</kbd>{' '}
                <kbd className="rounded border border-aurora-border bg-aurora-surface-2 px-1 py-0.5">K</kbd> basculer
              </span>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
