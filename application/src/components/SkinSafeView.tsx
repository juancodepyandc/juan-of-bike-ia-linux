/**
 * SkinSafeView — defensive wrapper for the Aurora skin views.
 *
 * v82i (post-user-eradication-of-manga rule) : the previous implementation
 * fell back to the manga component on chunk-load failure. The user's hard
 * rule is "absolument plus cette interface" — so even a transient deploy
 * hash mismatch must NOT resurrect manga. SkinSafeView now renders a
 * neutral Aurora-styled "vue indisponible" panel and a Réessayer button
 * that retries the chunk import via window.location.reload(). The
 * `fallback` prop is kept for source-compat but is ignored.
 *
 * The fallback never throws — if the boundary itself is broken, the
 * top-level AppErrorBoundary catches it.
 */
import { Component, type ComponentType, type ErrorInfo, type ReactNode } from 'react'

type Props = {
  /** Legacy: a fallback component (typically the manga equivalent). Ignored
   *  since v82i — kept so existing call-sites don't need a churn diff. */
  fallback?: ComponentType
  /** Human label shown in the warning banner ("Conversation V1 Editorial") */
  skinLabel: string
  children: ReactNode
}

type State = {
  failed: boolean
  message: string
}

export default class SkinSafeView extends Component<Props, State> {
  state: State = { failed: false, message: '' }

  static getDerivedStateFromError(err: Error): State {
    return {
      failed: true,
      message: err.message || 'chunk load error',
    }
  }

  componentDidCatch(err: Error, info: ErrorInfo) {
    console.warn('[SkinSafeView] Aurora skin chunk failed:', err, info.componentStack)
  }

  private handleRetry = () => {
    // v82lk4 : avant de reload, on casse les chunks stales potentiels
    // — Service Worker + Cache API. Sans ça, le reload re-sert souvent
    // le même chunk cassé via le SW (boucle "Réessayer → même erreur").
    void (async () => {
      try {
        if ('caches' in window) {
          const keys = await caches.keys()
          await Promise.all(keys.map((k) => caches.delete(k)))
        }
      } catch { /* noop */ }
      try {
        if ('serviceWorker' in navigator) {
          const regs = await navigator.serviceWorker.getRegistrations()
          await Promise.all(regs.map((r) => r.unregister()))
        }
      } catch { /* noop */ }
      try {
        // Force navigation avec cache-buster — bypass du HTTP cache.
        const url = new URL(window.location.href)
        url.searchParams.set('_cb', String(Date.now()))
        window.location.href = url.toString()
      } catch {
        try { window.location.reload() } catch { /* noop */ }
      }
    })()
  }

  render() {
    if (this.state.failed) {
      return (
        <div style={{
          position: 'fixed', inset: 0,
          display: 'grid', placeItems: 'center',
          background: 'oklch(0.10 0.012 250 / 0.92)',
          zIndex: 100000,
          padding: '6vmin',
          fontFamily: 'Geist, ui-sans-serif, system-ui, sans-serif',
          color: 'oklch(0.92 0.02 60)',
          textAlign: 'center',
        }}>
          <div style={{
            maxWidth: 520,
            display: 'flex', flexDirection: 'column', gap: 16,
            border: '1px solid oklch(0.65 0.180 40 / 0.4)',
            borderRadius: 18,
            padding: '32px 36px',
            background: 'oklch(0.13 0.015 250 / 0.6)',
            backdropFilter: 'blur(18px)',
          }}>
            <div style={{
              fontFamily: '"Instrument Serif", Cormorant Garamond, ui-serif, serif',
              fontStyle: 'italic',
              fontSize: 32,
              letterSpacing: '-0.02em',
              color: 'oklch(0.65 0.180 40)',
              lineHeight: 1.1,
            }}>
              Skin <span style={{ fontWeight: 600 }}>{this.props.skinLabel}</span> indisponible
            </div>
            <div style={{ fontSize: 14, opacity: 0.78, lineHeight: 1.55 }}>
              Le chunk Aurora pour cette vue n'a pas pu charger. La piste la plus
              probable est un déploiement en cours ou un cache navigateur périmé.
              Recharger la page va re-demander le bundle frais.
            </div>
            <div style={{
              fontFamily: 'ui-monospace, "JetBrains Mono", monospace',
              fontSize: 11,
              opacity: 0.5,
              wordBreak: 'break-word',
            }} title={this.state.message}>
              {this.state.message}
            </div>
            <button
              type="button"
              onClick={this.handleRetry}
              style={{
                marginTop: 8,
                padding: '10px 22px',
                borderRadius: 999,
                border: '1px solid oklch(0.65 0.180 40 / 0.5)',
                background: 'oklch(0.65 0.180 40 / 0.12)',
                color: 'oklch(0.85 0.12 60)',
                fontFamily: 'inherit',
                fontSize: 13,
                letterSpacing: '0.04em',
                cursor: 'pointer',
              }}
            >
              Réessayer
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
