import { AnimatePresence, motion } from 'framer-motion'
import { Archive, Check, FolderOpen, X } from 'lucide-react'
import { useState } from 'react'
import type { CodeFileEntry, SaveRequest } from '../services/saveSystem.ts'
import { exportAsZip, saveAndExportZip, saveToWorkspace } from '../services/saveSystem.ts'

export type SaveDialogData = Omit<SaveRequest, 'module'> & {
  module: SaveRequest['module']
  codeFiles?: CodeFileEntry[]
}

type Props = {
  data: SaveDialogData | null
  onClose: () => void
  onSaved?: (savedPath: string) => void
}

type SaveState = 'idle' | 'saving' | 'done' | 'error'

export default function SaveDialog({ data, onClose, onSaved }: Props) {
  const [saveState, setSaveState] = useState<SaveState>('idle')
  const [savedPath, setSavedPath] = useState<string>('')
  const [errorMessage, setErrorMessage] = useState<string>('')

  async function handleWorkspace() {
    if (!data) return
    setSaveState('saving')
    const result = await saveToWorkspace({ ...data, codeFiles: data.codeFiles })
    if (result.ok) {
      setSavedPath(result.savedPath)
      setSaveState('done')
      onSaved?.(result.savedPath)
    } else {
      setErrorMessage(result.error ?? 'Erreur inconnue')
      setSaveState('error')
    }
  }

  async function handleZip() {
    if (!data) return
    setSaveState('saving')
    const result = await saveAndExportZip({ ...data, codeFiles: data.codeFiles })
    if (result.ok) {
      setSavedPath(result.savedPath)
      setSaveState('done')
      onSaved?.(result.savedPath)
    } else {
      setErrorMessage(result.error ?? 'Erreur inconnue')
      setSaveState('error')
    }
  }

  function handleClose() {
    setSaveState('idle')
    setSavedPath('')
    setErrorMessage('')
    onClose()
  }

  const scoreColor = data && data.fidelityScore >= 90
    ? 'text-emerald-400'
    : data && data.fidelityScore >= 70
      ? 'text-amber-400'
      : 'text-red-400'

  return (
    <AnimatePresence>
      {data && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
          onClick={(e) => { if (e.target === e.currentTarget) handleClose() }}
        >
          <motion.div
            initial={{ scale: 0.92, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.92, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 340, damping: 30 }}
            className="relative w-full max-w-md mx-4 rounded-2xl border border-white/10 bg-[#0e0e10] p-6 shadow-2xl"
          >
            <button
              onClick={handleClose}
              className="absolute top-4 right-4 text-white/40 hover:text-white/70 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>

            {saveState === 'done' ? (
              <div className="text-center space-y-3">
                <div className="w-12 h-12 rounded-full bg-emerald-500/20 flex items-center justify-center mx-auto">
                  <Check className="w-6 h-6 text-emerald-400" />
                </div>
                <p className="text-white font-medium">Résultat sauvegardé</p>
                <p className="text-xs text-white/40 break-all">{savedPath}</p>
                <button
                  onClick={handleClose}
                  className="mt-2 px-4 py-2 rounded-lg bg-white/10 hover:bg-white/15 text-sm text-white transition-colors"
                >
                  Fermer
                </button>
              </div>
            ) : saveState === 'error' ? (
              <div className="text-center space-y-3">
                <p className="text-red-400 font-medium">Erreur lors de la sauvegarde</p>
                <p className="text-xs text-white/40">{errorMessage}</p>
                <button
                  onClick={() => setSaveState('idle')}
                  className="px-4 py-2 rounded-lg bg-white/10 hover:bg-white/15 text-sm text-white transition-colors"
                >
                  Réessayer
                </button>
              </div>
            ) : (
              <>
                <div className="mb-5 space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs uppercase tracking-widest text-white/30">Sauvegarder le résultat</span>
                    <span className={`ml-auto text-sm font-bold tabular-nums ${scoreColor}`}>
                      {data.fidelityScore}/100
                    </span>
                  </div>
                  <p className="text-sm text-white/70 line-clamp-2">{data.prompt}</p>
                </div>

                <div className="space-y-3">
                  <button
                    onClick={handleWorkspace}
                    disabled={saveState === 'saving'}
                    className="flex items-center gap-3 w-full px-4 py-3 rounded-xl border border-white/10 bg-white/[0.04] hover:bg-white/[0.08] transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-left"
                  >
                    <FolderOpen className="w-5 h-5 text-sky-400 shrink-0" />
                    <div>
                      <p className="text-sm font-medium text-white">Workspace local</p>
                      <p className="text-xs text-white/40">Dossier dédié avec métadonnées et prompt</p>
                    </div>
                  </button>

                  <button
                    onClick={handleZip}
                    disabled={saveState === 'saving'}
                    className="flex items-center gap-3 w-full px-4 py-3 rounded-xl border border-white/10 bg-white/[0.04] hover:bg-white/[0.08] transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-left"
                  >
                    <Archive className="w-5 h-5 text-violet-400 shrink-0" />
                    <div>
                      <p className="text-sm font-medium text-white">Export ZIP portable</p>
                      <p className="text-xs text-white/40">Archive téléchargeable pour un autre appareil</p>
                    </div>
                  </button>

                  <button
                    onClick={handleClose}
                    disabled={saveState === 'saving'}
                    className="w-full px-4 py-2 rounded-xl text-sm text-white/40 hover:text-white/60 transition-colors disabled:opacity-50"
                  >
                    Ignorer
                  </button>
                </div>

                {saveState === 'saving' && (
                  <div className="mt-4 text-center text-xs text-white/40 animate-pulse">
                    Sauvegarde en cours...
                  </div>
                )}
              </>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
