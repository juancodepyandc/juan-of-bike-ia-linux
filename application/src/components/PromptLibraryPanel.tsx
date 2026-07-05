import { AnimatePresence, motion } from 'framer-motion'
import { BookOpen, Search, Trash2, X, Zap } from 'lucide-react'
import { useState } from 'react'
import type { ModuleId } from '../types/app'
import type { SavedPrompt } from '../stores/promptLibraryStore'
import { usePromptLibraryStore } from '../stores/promptLibraryStore'

type Props = {
  open: boolean
  onClose: () => void
  /** Current module — used to pre-filter the list */
  currentModule: ModuleId | 'all'
  /** Called when the user clicks "Utiliser" on a prompt */
  onUsePrompt: (prompt: string) => void
}

function ScoreBadge({ score }: { score: number }) {
  const color = score >= 90
    ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
    : score >= 70
      ? 'bg-amber-500/20 text-amber-400 border-amber-500/30'
      : 'bg-red-500/20 text-red-400 border-red-500/30'

  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold border ${color} tabular-nums`}>
      {score}
    </span>
  )
}

function PromptCard({
  prompt,
  onUse,
  onDelete,
}: {
  prompt: SavedPrompt
  onUse: () => void
  onDelete: () => void
}) {
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -6 }}
      className="group rounded-xl border border-white/[0.07] bg-white/[0.03] hover:bg-white/[0.06] p-3 transition-colors"
    >
      <div className="flex items-start gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 mb-1">
            <span className="text-[10px] uppercase tracking-wider text-white/30">{prompt.module}</span>
            <ScoreBadge score={prompt.fidelityScore} />
            {prompt.useCount > 0 && (
              <span className="text-[10px] text-white/20">×{prompt.useCount}</span>
            )}
          </div>
          <p className="text-xs text-white/70 line-clamp-3 leading-relaxed">{prompt.prompt}</p>
          {prompt.tags.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-1.5">
              {prompt.tags.map((tag) => (
                <span key={tag} className="text-[10px] px-1.5 py-0.5 rounded bg-white/[0.06] text-white/40">
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="flex flex-col gap-1 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            onClick={onUse}
            title="Utiliser ce prompt"
            className="p-1.5 rounded-lg bg-sky-500/20 hover:bg-sky-500/30 text-sky-400 transition-colors"
          >
            <Zap className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={onDelete}
            title="Supprimer"
            className="p-1.5 rounded-lg bg-red-500/10 hover:bg-red-500/20 text-red-400/60 hover:text-red-400 transition-colors"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </motion.div>
  )
}

export default function PromptLibraryPanel({ open, onClose, currentModule, onUsePrompt }: Props) {
  const { searchPrompts, deletePrompt, incrementUseCount } = usePromptLibraryStore()
  const [query, setQuery] = useState('')
  const [moduleFilter, setModuleFilter] = useState<ModuleId | 'all'>(currentModule)

  const results = searchPrompts(query, moduleFilter)

  function handleUse(prompt: SavedPrompt) {
    incrementUseCount(prompt.id)
    onUsePrompt(prompt.prompt)
    onClose()
  }

  const MODULE_OPTIONS: Array<{ value: ModuleId | 'all'; label: string }> = [
    { value: 'all', label: 'Tous' },
    { value: 'conversation', label: 'Chat' },
    { value: 'image', label: 'Image' },
    { value: 'code', label: 'Code' },
    { value: 'video', label: 'Vidéo' },
    { value: 'drawing', label: 'Dessin' },
    { value: '3d', label: '3D' },
    { value: 'learning', label: 'Académie' },
  ]

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0, x: 24 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: 24 }}
          transition={{ type: 'spring', stiffness: 340, damping: 30 }}
          className="fixed top-0 right-0 h-full w-80 z-40 flex flex-col border-l border-white/[0.07] bg-[#0e0e10] shadow-2xl"
        >
          {/* Header */}
          <div className="flex items-center gap-2 px-4 py-3.5 border-b border-white/[0.07]">
            <BookOpen className="w-4 h-4 text-violet-400" />
            <span className="text-sm font-medium text-white">Bibliothèque de prompts</span>
            <button
              onClick={onClose}
              className="ml-auto text-white/30 hover:text-white/60 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Search + filter */}
          <div className="px-3 pt-3 space-y-2">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-white/30 pointer-events-none" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Rechercher..."
                className="w-full pl-8 pr-3 py-2 rounded-lg bg-white/[0.05] border border-white/[0.08] text-xs text-white placeholder-white/30 focus:outline-none focus:border-white/20 transition-colors"
              />
            </div>

            <div className="flex flex-wrap gap-1">
              {MODULE_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setModuleFilter(opt.value)}
                  className={[
                    'px-2 py-0.5 rounded text-[10px] border transition-colors',
                    moduleFilter === opt.value
                      ? 'bg-violet-500/20 border-violet-500/40 text-violet-300'
                      : 'bg-white/[0.04] border-white/[0.06] text-white/40 hover:text-white/60',
                  ].join(' ')}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* List */}
          <div className="flex-1 overflow-y-auto px-3 py-3 space-y-2">
            {results.length === 0 ? (
              <div className="text-center py-12 text-xs text-white/25">
                {query ? 'Aucun résultat' : 'Aucun prompt sauvegardé'}
              </div>
            ) : (
              <AnimatePresence>
                {results.map((prompt) => (
                  <PromptCard
                    key={prompt.id}
                    prompt={prompt}
                    onUse={() => handleUse(prompt)}
                    onDelete={() => deletePrompt(prompt.id)}
                  />
                ))}
              </AnimatePresence>
            )}
          </div>

          <div className="px-4 py-2 border-t border-white/[0.05] text-[10px] text-white/20 text-center">
            {results.length} prompt{results.length !== 1 ? 's' : ''}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
