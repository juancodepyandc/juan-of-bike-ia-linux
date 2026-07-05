import { Component, Fragment, type ErrorInfo, type ReactNode } from 'react'
import { AlertTriangle, Home, RefreshCcw } from 'lucide-react'

type Props = {
  children: ReactNode
  moduleKey: string
  moduleLabel: string
  onReturnHome: () => void
}

type State = {
  hasError: boolean
  message: string
  recoveryKey: number
}

export default class ModuleErrorBoundary extends Component<Props, State> {
  state: State = {
    hasError: false,
    message: '',
    recoveryKey: 0,
  }

  static getDerivedStateFromError(error: Error): State {
    return {
      hasError: true,
      message: error.message || 'Erreur de module inconnue.',
      recoveryKey: 0,
    }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error(`[Aurora IA] module crash: ${this.props.moduleLabel}`, error, errorInfo)
  }

  componentDidUpdate(prevProps: Props) {
    if (prevProps.moduleKey !== this.props.moduleKey && this.state.hasError) {
      this.setState((state) => ({
        hasError: false,
        message: '',
        recoveryKey: state.recoveryKey + 1,
      }))
    }
  }

  private handleRetry = () => {
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
      <div className="flex h-full items-center justify-center px-6 py-8">
        <div className="w-full max-w-2xl rounded-[2rem] border border-aurora-border/45 glass p-8">
          <div className="flex h-16 w-16 items-center justify-center rounded-[1.6rem] gradient-accent text-white glow-accent">
            <AlertTriangle size={28} />
          </div>

          <p className="mt-6 text-[11px] uppercase tracking-[0.24em] text-aurora-text-dim">
            Recuperation du module
          </p>
          <h2 className="mt-2 text-3xl font-semibold gradient-text">
            {this.props.moduleLabel} a bloque, mais le shell reste vivant.
          </h2>
          <p className="mt-3 text-sm leading-relaxed text-aurora-text-muted">
            Le crash est contenu dans ce module. Tu peux relancer cette vue ou revenir au copilote sans redemarrer toute l application.
          </p>

          <div className="mt-6 rounded-2xl border border-aurora-border/40 bg-aurora-surface/80 px-4 py-3">
            <p className="text-[11px] uppercase tracking-[0.22em] text-aurora-text-dim">Erreur remontee</p>
            <p className="mt-2 text-sm text-aurora-text">{this.state.message}</p>
          </div>

          <div className="mt-6 flex flex-wrap gap-3">
            <button
              onClick={this.handleRetry}
              className="inline-flex items-center gap-2 rounded-2xl gradient-accent px-5 py-3 text-sm font-medium text-white glow-accent"
            >
              <RefreshCcw size={16} />
              Recharger le module
            </button>
            <button
              onClick={this.props.onReturnHome}
              className="inline-flex items-center gap-2 rounded-2xl border border-aurora-border/40 bg-aurora-surface-2 px-5 py-3 text-sm text-aurora-text hover:border-aurora-accent/35 transition-colors"
            >
              <Home size={16} />
              Revenir au copilote
            </button>
          </div>
        </div>
      </div>
    )
  }
}
