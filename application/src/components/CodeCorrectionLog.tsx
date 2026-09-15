import { AnimatePresence, motion } from 'framer-motion'
import {
  AlertTriangle,
  ArrowUpCircle,
  Check,
  Loader2,
  RefreshCw,
  Search,
  TrendingUp,
  Zap,
} from 'lucide-react'
import type { CorrectionPass } from '../services/codeAutoCorrection.ts'
import type { CodeIntent } from '../services/codeIntent.ts'

const LEVEL_LABELS: Record<string, { label: string; icon: typeof Zap; color: string }> = {
  initial: { label: 'Generation initiale', icon: Zap, color: 'text-blue-400' },
  quick_fix: { label: 'Correction rapide', icon: RefreshCw, color: 'text-yellow-400' },
  targeted_repair: { label: 'Reparation ciblee', icon: RefreshCw, color: 'text-orange-400' },
  partial_rewrite: { label: 'Reecriture partielle', icon: ArrowUpCircle, color: 'text-orange-500' },
  rewrite: { label: 'Reecriture complete', icon: ArrowUpCircle, color: 'text-red-400' },
  strategy_change: { label: 'Changement de strategie', icon: Search, color: 'text-red-500' },
}

function ScoreBar({ score, isRunning }: { score: number; isRunning: boolean }) {
  const color = score >= 100
    ? 'bg-green-500'
    : score >= 70
      ? 'bg-yellow-500'
      : score >= 40
        ? 'bg-orange-500'
        : score > 0
          ? 'bg-red-500'
          : 'bg-red-500/50'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 rounded-full bg-white/10 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ${color} ${isRunning ? 'animate-pulse' : ''}`}
          style={{ width: `${Math.max(3, Math.min(100, score))}%` }}
        />
      </div>
      <span className="text-[11px] tabular-nums font-medium text-aurora-text-dim w-8 text-right">{score}%</span>
    </div>
  )
}

function ScoreTrend({ log }: { log: CorrectionPass[] }) {
  if (log.length < 2) return null
  const prev = log[log.length - 2].score
  const curr = log[log.length - 1].score
  const diff = curr - prev
  if (diff === 0) return null
  return (
    <span className={`inline-flex items-center gap-0.5 text-[10px] ${diff > 0 ? 'text-green-400' : 'text-red-400'}`}>
      <TrendingUp size={10} className={diff < 0 ? 'rotate-180' : ''} />
      {diff > 0 ? '+' : ''}{diff}
    </span>
  )
}

export default function CodeCorrectionLog({
  correctionLog,
  intent,
  totalAttempts,
  finalScore,
  isRunning,
}: {
  correctionLog: CorrectionPass[]
  intent: CodeIntent | null
  totalAttempts: number
  finalScore: number
  isRunning?: boolean
}) {
  if (correctionLog.length === 0 && !isRunning) return null

  // Waiting state — generation started but no passes yet
  if (correctionLog.length === 0 && isRunning) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="rounded-[1.4rem] border border-aurora-accent/20 bg-aurora-surface/65 p-4"
      >
        <div className="flex items-center gap-2">
          <Loader2 size={14} className="animate-spin text-aurora-accent-light" />
          <span className="text-[11px] uppercase tracking-[0.2em] text-aurora-text-dim">
            Pipeline en cours...
          </span>
        </div>
        <p className="mt-2 text-[11px] text-aurora-text-muted">
          Generation du code, validation et auto-correction si besoin.
        </p>
      </motion.div>
    )
  }

  const isSuccess = finalScore >= 100
  const lastPass = correctionLog[correctionLog.length - 1]
  const isActive = isRunning && !isSuccess

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={`rounded-[1.4rem] border p-4 space-y-3 ${
        isActive
          ? 'border-aurora-accent/30 bg-aurora-accent/5'
          : isSuccess
            ? 'border-green-500/25 bg-green-500/5'
            : 'border-aurora-border/35 bg-aurora-surface/65'
      }`}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {isActive ? (
            <Loader2 size={14} className="animate-spin text-aurora-accent-light" />
          ) : isSuccess ? (
            <Check size={14} className="text-green-400" />
          ) : (
            <AlertTriangle size={14} className="text-yellow-400" />
          )}
          <span className="text-[11px] uppercase tracking-[0.2em] text-aurora-text-dim">
            {isActive ? 'Auto-correction en cours' : 'Pipeline auto-correction'}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <ScoreTrend log={correctionLog} />
          <span className="text-[11px] text-aurora-text-dim">
            {totalAttempts} passe{totalAttempts > 1 ? 's' : ''}
          </span>
          {intent && (
            <span className="rounded-full border border-aurora-border/30 bg-aurora-surface-2/50 px-2 py-0.5 text-[10px] text-aurora-text-dim">
              {intent.projectType.replace(/_/g, ' ')}
            </span>
          )}
        </div>
      </div>

      {/* Score bar */}
      <ScoreBar score={finalScore} isRunning={!!isActive} />

      {/* Status label */}
      <div className={`text-[11px] ${
        isActive
          ? 'text-aurora-accent-light'
          : isSuccess
            ? 'text-green-400'
            : finalScore >= 50
              ? 'text-yellow-400'
              : 'text-red-400'
      }`}>
        {isActive
          ? `Passe ${totalAttempts} en cours — ${lastPass ? LEVEL_LABELS[lastPass.strategy]?.label ?? 'correction' : 'validation'}...`
          : isSuccess
            ? 'QA PASS — Sandbox valide'
            : finalScore >= 50
              ? 'Validation partielle — ameliorations manuelles necessaires'
              : 'Echec validation — correction manuelle recommandee'}
      </div>

      {/* Correction passes */}
      <AnimatePresence>
        <div className="space-y-1.5">
          {correctionLog.map((pass, index) => {
            const levelInfo = LEVEL_LABELS[pass.strategy] || LEVEL_LABELS.initial
            const Icon = levelInfo.icon
            const isLastAndRunning = isActive && index === correctionLog.length - 1
            return (
              <motion.div
                key={`pass-${pass.attempt}`}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.04 }}
                className={`flex items-center gap-3 rounded-xl border px-3 py-2 ${
                  isLastAndRunning
                    ? 'border-aurora-accent/25 bg-aurora-accent/8'
                    : pass.resolved
                      ? 'border-green-500/20 bg-green-500/5'
                      : 'border-aurora-border/25 bg-aurora-surface-2/40'
                }`}
              >
                {isLastAndRunning ? (
                  <Loader2 size={12} className="animate-spin text-aurora-accent-light" />
                ) : (
                  <Icon size={12} className={levelInfo.color} />
                )}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[11px] text-aurora-text truncate">
                      #{pass.attempt} {levelInfo.label}
                    </span>
                    <span className={`text-[10px] font-medium ${pass.resolved ? 'text-green-400' : pass.score >= 50 ? 'text-yellow-400' : 'text-red-400'}`}>
                      {pass.resolved ? 'OK' : `${pass.score}%`}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-[10px] text-aurora-text-dim truncate">
                      {pass.modelUsed.split(':')[0]}
                    </span>
                    {pass.errors.length > 0 && (
                      <span className="text-[10px] text-aurora-text-dim">
                        {pass.errors.length} erreur{pass.errors.length > 1 ? 's' : ''}
                      </span>
                    )}
                  </div>
                </div>
              </motion.div>
            )
          })}
        </div>
      </AnimatePresence>

      {/* Last error details (collapsed by default) */}
      {!isSuccess && lastPass && lastPass.errors.length > 0 && !isActive && (
        <details className="group">
          <summary className="cursor-pointer text-[11px] text-aurora-text-dim hover:text-aurora-text transition-colors">
            Dernieres erreurs ({lastPass.errors.length})
          </summary>
          <div className="mt-2 space-y-1">
            {lastPass.errors.slice(0, 3).map((error, i) => (
              <pre
                key={`err-${i}`}
                className="overflow-auto rounded-lg border border-aurora-border/20 bg-[#091116] px-3 py-2 text-[10px] leading-4 text-red-300/80 whitespace-pre-wrap max-h-24"
              >
                {error.slice(0, 500)}
              </pre>
            ))}
          </div>
        </details>
      )}
    </motion.div>
  )
}
