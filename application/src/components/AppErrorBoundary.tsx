import { Component, Fragment, type ErrorInfo, type ReactNode } from 'react'
import { AlertTriangle, RefreshCcw, RotateCcw } from 'lucide-react'
import { motion } from 'framer-motion'
import { getRuntimeHint, getRuntimeLabel } from '../utils/runtime'
import { isChunkError, recoverFromStaleBuild } from '../utils/buildRecovery'

type Props = {
  children: ReactNode
}

type State = {
  hasError: boolean
  message: string
  recoveryKey: number
}

export default class AppErrorBoundary extends Component<Props, State> {
  state: State = {
    hasError: false,
    message: '',
    recoveryKey: 0,
  }

  static getDerivedStateFromError(error: Error): State {
    return {
      hasError: true,
      message: error.message || 'Erreur d interface inconnue',
      recoveryKey: 0,
    }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Aurora IA shell crash:', error, errorInfo)
    // Un chunk Vite mort (index.html périmé après déploiement) → re-render
    // ne fixe rien (il retentera le même chunk 404). Reload dur avec purge
    // caches/SW : ça, ça répare. (« charge à l'infini en changeant d'interface »)
    if (isChunkError(error)) recoverFromStaleBuild('errorBoundary: ' + error.message)
  }

  private handleRecover = () => {
    this.setState((state) => ({
      hasError: false,
      message: '',
      recoveryKey: state.recoveryKey + 1,
    }))
  }

  private handleClearRecoveryCache = () => {
    localStorage.removeItem('juan-bike-app-store')
    localStorage.removeItem('aurora-code-workspace')
    this.setState((state) => ({
      hasError: false,
      message: '',
      recoveryKey: state.recoveryKey + 1,
    }))
  }

  render() {
    if (!this.state.hasError) {
      return <Fragment key={this.state.recoveryKey}>{this.props.children}</Fragment>
    }

    return (
      <div className="min-h-screen bg-aurora-bg text-aurora-text overflow-hidden">
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-10 left-10 w-72 h-72 rounded-full bg-aurora-accent/10 blur-[120px]" />
          <div className="absolute bottom-10 right-10 w-80 h-80 rounded-full bg-aurora-cyan/10 blur-[140px]" />
        </div>

        <div className="relative z-10 min-h-screen flex items-center justify-center px-6 py-10">
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            className="max-w-2xl w-full glass rounded-[2rem] border border-aurora-border/50 p-8"
          >
            <div className="w-16 h-16 rounded-3xl gradient-accent flex items-center justify-center text-white glow-accent-strong">
              <AlertTriangle size={28} />
            </div>

            <div className="mt-6">
              <p className="text-xs uppercase tracking-[0.28em] text-aurora-text-dim">Recuperation interface</p>
              <h1 className="mt-2 text-3xl font-semibold gradient-text">
                L application a bloque, mais elle ne restera plus vide.
              </h1>
              <p className="mt-3 text-sm text-aurora-text-muted">
                Runtime actuel: {getRuntimeLabel()}. {getRuntimeHint()}
              </p>
            </div>

            <div className="mt-6 rounded-2xl bg-aurora-surface-2/80 border border-aurora-border/40 px-4 py-3">
              <p className="text-[11px] uppercase tracking-[0.22em] text-aurora-text-dim">Cause remontee</p>
              <p className="mt-2 text-sm text-aurora-text">{this.state.message}</p>
            </div>

            <div className="mt-6 flex flex-wrap gap-3">
              <button
                onClick={this.handleRecover}
                className="px-5 py-3 rounded-2xl gradient-accent text-white text-sm font-medium inline-flex items-center gap-2 glow-accent"
              >
                <RefreshCcw size={16} />
                Recuperer l interface
              </button>
              <button
                onClick={this.handleClearRecoveryCache}
                className="px-5 py-3 rounded-2xl bg-aurora-surface-2 border border-aurora-border/40 text-sm text-aurora-text inline-flex items-center gap-2 hover:border-aurora-accent/40 transition-colors"
              >
                <RotateCcw size={16} />
                Effacer le cache de reprise
              </button>
            </div>
          </motion.div>
        </div>
      </div>
    )
  }
}
