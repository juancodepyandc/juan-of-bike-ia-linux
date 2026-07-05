import { AlertCircle, Check, Loader2, RefreshCw, X } from 'lucide-react'
import type { GenerationRecoveryState, RecoveredResult } from '../hooks/useGenerationRecovery'
import type { TrackedGeneration } from '../stores/generationTrackerStore'

interface RecoveryBannerProps {
  recovery: GenerationRecoveryState
  /** Callback quand l'utilisateur veut relancer un stream interrompu */
  onRetry?: (gen: TrackedGeneration) => void
  /** Callback quand un resultat ComfyUI/Python est recupere */
  onRecovered?: (result: RecoveredResult) => void
}

export default function RecoveryBanner({ recovery, onRetry, onRecovered }: RecoveryBannerProps) {
  const { recovering, pendingRecoveries, recoveredResults, dismissRecovery } = recovery

  if (!recovering && pendingRecoveries.length === 0 && recoveredResults.length === 0) {
    return null
  }

  return (
    <div className="space-y-2 px-2 sm:px-4">
      {/* Recovery en cours */}
      {recovering && (
        <div className="flex items-center gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-300/90">
          <Loader2 size={14} className="shrink-0 animate-spin text-amber-400" />
          <span>Recuperation de la generation precedente en cours...</span>
        </div>
      )}

      {/* Streams interrompus — proposer Relancer / Ignorer */}
      {pendingRecoveries.map(gen => (
        <div
          key={gen.id}
          className="flex items-center justify-between gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-300/90"
        >
          <div className="flex items-center gap-2 min-w-0">
            <AlertCircle size={14} className="shrink-0 text-amber-400" />
            <span className="truncate">
              Generation interrompue: <span className="text-amber-200">{gen.prompt.slice(0, 80)}{gen.prompt.length > 80 ? '...' : ''}</span>
            </span>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            {onRetry && (
              <button
                onClick={() => { onRetry(gen); dismissRecovery(gen.id) }}
                className="flex items-center gap-1 rounded-lg bg-amber-500/25 px-2 py-1 text-[11px] text-amber-200 hover:bg-amber-500/40 transition-colors"
              >
                <RefreshCw size={11} />
                Relancer
              </button>
            )}
            <button
              onClick={() => dismissRecovery(gen.id)}
              className="flex items-center justify-center rounded-lg bg-white/5 p-1 text-white/40 hover:text-white/70 transition-colors"
            >
              <X size={12} />
            </button>
          </div>
        </div>
      ))}

      {/* Resultats recuperes */}
      {recoveredResults.map(result => (
        <div
          key={result.generation.id}
          className="flex items-center justify-between gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-300/90"
        >
          <div className="flex items-center gap-2 min-w-0">
            <Check size={14} className="shrink-0 text-emerald-400" />
            <span className="truncate">
              Generation recuperee : <span className="text-emerald-200">{result.generation.prompt.slice(0, 60)}</span>
            </span>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            {onRecovered && (
              <button
                onClick={() => { onRecovered(result); dismissRecovery(result.generation.id) }}
                className="flex items-center gap-1 rounded-lg bg-emerald-500/25 px-2 py-1 text-[11px] text-emerald-200 hover:bg-emerald-500/40 transition-colors"
              >
                Afficher
              </button>
            )}
            <button
              onClick={() => dismissRecovery(result.generation.id)}
              className="flex items-center justify-center rounded-lg bg-white/5 p-1 text-white/40 hover:text-white/70 transition-colors"
            >
              <X size={12} />
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}
