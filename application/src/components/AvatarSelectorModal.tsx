import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { X, Plus, Check, Trash2, FolderOpen } from 'lucide-react'
import type { AvatarEntry } from '../types/app.ts'

interface Props {
  open: boolean
  onClose: () => void
  onSelect: (avatar: AvatarEntry) => void
  onGenerateIn3D: (prompt: string) => void
  onImportFromSaves: () => void
  onRemove?: (id: string) => void
  avatars: AvatarEntry[]
  selectedId: string
}

export default function AvatarSelectorModal({
  open, onClose, onSelect, onGenerateIn3D, onImportFromSaves, onRemove, avatars, selectedId,
}: Props) {
  const [prompt, setPrompt] = useState('')
  const [showPrompt, setShowPrompt] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)

  if (!open) return null

  return (
    <AnimatePresence>
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
        onClick={onClose}>
        <motion.div initial={{ scale: 0.92, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
          transition={{ type: 'spring', damping: 25, stiffness: 300 }}
          onClick={e => e.stopPropagation()}
          className="w-full max-w-sm rounded-2xl border border-white/10 bg-[#12121f] p-4 shadow-2xl">

          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-white">Avatars</h3>
            <button onClick={onClose} className="p-1 rounded-lg hover:bg-white/10 text-white/50"><X size={16} /></button>
          </div>

          {/* Grille avatars */}
          <div className="grid grid-cols-3 gap-2 mb-3">
            {avatars.map(av => (
              <div key={av.id} className="relative group">
                <button onClick={() => { onSelect(av); onClose() }}
                  className={`w-full flex flex-col items-center gap-1 rounded-xl p-2 transition-all ${
                    selectedId === av.id ? 'bg-indigo-500/20 border-2 border-indigo-400/50' : 'bg-white/[0.04] border border-white/[0.06] hover:bg-white/[0.08]'
                  }`}>
                  <div className="w-14 h-14 rounded-lg overflow-hidden bg-gradient-to-br from-indigo-500/20 to-purple-500/20 flex items-center justify-center">
                    {av.type === 'live2d-flux' && av.thumbnail ? (
                      <img src={av.thumbnail} alt={av.label} className="h-full w-full object-cover" />
                    ) : (
                      <span className="text-xl">
                        {av.type === 'vrm' ? '👩'
                          : av.type === 'procedural' ? '🧑'
                          : av.type === 'image-2d' ? '🖼️'
                          : av.type === 'live2d-flux' ? '✨'
                          : '🗿'}
                      </span>
                    )}
                  </div>
                  <span className="text-[9px] text-white/70 truncate max-w-full">{av.label}</span>
                  <span className="text-[7px] text-white/30 uppercase">{av.type}</span>
                  {selectedId === av.id && (
                    <div className="absolute top-0.5 right-0.5 h-4 w-4 rounded-full bg-indigo-500 flex items-center justify-center">
                      <Check size={8} className="text-white" />
                    </div>
                  )}
                </button>
                {!av.builtIn && onRemove && (
                  <button onClick={e => { e.stopPropagation(); setConfirmDelete(av.id) }}
                    className="absolute -top-1 -left-1 h-5 w-5 rounded-full bg-red-500/70 items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-500 hidden group-hover:flex">
                    <Trash2 size={10} className="text-white" />
                  </button>
                )}
              </div>
            ))}
          </div>

          {/* Actions */}
          <div className="space-y-2">
            {/* Importer depuis saves 3D */}
            <button onClick={() => { onImportFromSaves(); onClose() }}
              className="w-full flex items-center gap-2 rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-white/60 hover:bg-white/[0.06]">
              <FolderOpen size={14} />
              <span>Importer depuis mes modeles 3D</span>
            </button>

            {/* Generer un avatar */}
            <button onClick={() => setShowPrompt(!showPrompt)}
              className="w-full flex items-center gap-2 rounded-lg border border-dashed border-indigo-400/30 bg-indigo-500/5 px-3 py-2 text-xs text-indigo-300 hover:bg-indigo-500/10">
              <Plus size={14} />
              <span>Generer un nouveau personnage</span>
            </button>

            <AnimatePresence>
              {showPrompt && (
                <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }}>
                  <p className="text-[10px] text-white/40 mb-1">Decris le personnage. Il sera genere dans le module 3D.</p>
                  <div className="flex gap-2">
                    <input type="text" value={prompt} onChange={e => setPrompt(e.target.value)}
                      placeholder="Ex: Tete de Barbe Noire de One Piece"
                      className="flex-1 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-xs text-white placeholder-white/30 focus:border-indigo-400/40 focus:outline-none"
                      onKeyDown={e => {
                        if (e.key === 'Enter' && prompt.trim()) { onGenerateIn3D(prompt.trim()); setPrompt(''); setShowPrompt(false); onClose() }
                      }} />
                    <button onClick={() => { if (prompt.trim()) { onGenerateIn3D(prompt.trim()); setPrompt(''); setShowPrompt(false); onClose() } }}
                      disabled={!prompt.trim()}
                      className="rounded-lg bg-indigo-500/20 border border-indigo-400/30 px-3 py-2 text-xs text-indigo-300 hover:bg-indigo-500/30 disabled:opacity-40">
                      Lancer
                    </button>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Confirmation suppression */}
          <AnimatePresence>
            {confirmDelete && (
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 10 }}
                className="mt-3 rounded-xl border border-red-400/20 bg-red-500/10 p-3">
                <p className="text-xs text-red-200 mb-2">Supprimer cet avatar definitivement ?</p>
                <div className="flex gap-2 justify-end">
                  <button onClick={() => setConfirmDelete(null)} className="rounded-lg px-3 py-1.5 text-xs text-white/60 hover:bg-white/10">Annuler</button>
                  <button onClick={() => { if (confirmDelete && onRemove) { onRemove(confirmDelete); setConfirmDelete(null) } }}
                    className="rounded-lg bg-red-500/30 border border-red-400/30 px-3 py-1.5 text-xs text-red-200 hover:bg-red-500/50">Supprimer</button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}
