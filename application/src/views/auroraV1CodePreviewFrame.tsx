import { useEffect, useMemo, useRef, useState } from 'react'
import { instrumentPreviewHtml } from './auroraV1CodeHelpers'

type PreviewRuntimeMessage = {
  source?: string
  type?: 'ready' | 'error' | 'console'
  level?: string
  message?: string
  filename?: string
  lineno?: number
  colno?: number
  bodyTextLen?: number
  nodeCount?: number
  canvasCount?: number
  imageCount?: number
}

export function CodePreviewFrame({ html, title }: { html: string; title: string }) {
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const [ready, setReady] = useState(false)
  const [stalled, setStalled] = useState(false)
  const [runtimeMessages, setRuntimeMessages] = useState<PreviewRuntimeMessage[]>([])
  const [lastReadySignal, setLastReadySignal] = useState<PreviewRuntimeMessage | null>(null)
  const instrumentedHtml = useMemo(() => instrumentPreviewHtml(html), [html])

  useEffect(() => {
    setReady(false)
    setStalled(false)
    setRuntimeMessages([])
    setLastReadySignal(null)
    // v85h : longer grace window. External scripts (Tailwind CDN, Google Fonts)
    // can delay the iframe `load` past a couple seconds on a cold cache; the
    // native onLoad below clears `stalled` the instant the frame loads, so this
    // timer only fires for a genuinely stuck frame.
    const timer = window.setTimeout(() => setStalled(true), 9000)
    return () => window.clearTimeout(timer)
  }, [instrumentedHtml])

  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      // v85h : a sandboxed/opaque-origin srcdoc iframe does NOT reliably make
      // `event.source === iframe.contentWindow`, so that check silently dropped
      // every 'ready' signal → false "PREVIEW SANS SIGNAL" even though the page
      // rendered. The unique `data.source` marker is enough to identify our own
      // instrumented preview messages.
      const data = event.data as PreviewRuntimeMessage
      if (!data || data.source !== 'aurora-code-preview') return
      if (data.type === 'ready') {
        setReady(true)
        setStalled(false)
        setLastReadySignal(data)
        return
      }
      if (data.type === 'error' || data.type === 'console') {
        setRuntimeMessages((messages) => [...messages, data].slice(-5))
      }
    }
    window.addEventListener('message', onMessage)
    return () => window.removeEventListener('message', onMessage)
  }, [])

  const emptyRender = ready
    && (lastReadySignal?.bodyTextLen ?? 0) < 2
    && (lastReadySignal?.nodeCount ?? 0) <= 3
    && (lastReadySignal?.canvasCount ?? 0) === 0
    && (lastReadySignal?.imageCount ?? 0) === 0
  const topIssue = runtimeMessages[0]
  // v85h : once the frame has loaded (native onLoad OR 'ready' postMessage),
  // NEVER show the "sans signal" alarm — the 9s stall timer fires independently
  // and used to re-raise it even on a perfectly rendered page.
  const showStalled = stalled && !ready

  return (
    <div style={{ flex: 1, minHeight: 0, position: 'relative', background: '#fff' }}>
      <iframe
        ref={iframeRef}
        srcDoc={instrumentedHtml}
        title={title}
        // v85h : the native load event is the authoritative "the frame loaded"
        // signal — it always fires for srcdoc, unlike the postMessage which the
        // sandbox/source-check could drop. Clears the false "SANS SIGNAL" alarm.
        onLoad={() => { setStalled(false); setReady(true) }}
        // v82ns : keep srcdoc in an opaque origin. allow-scripts + forms are
        // enough for a runnable preview without letting generated links steer Aurora.
        sandbox="allow-scripts allow-forms allow-modals"
        style={{
          width: '100%',
          height: '100%',
          border: 'none',
          background: '#fff',
        }}
      />
      {(topIssue || showStalled || emptyRender) && (
        <div style={{
          position: 'absolute',
          left: 12,
          right: 12,
          bottom: 12,
          borderRadius: 8,
          padding: '10px 12px',
          background: topIssue ? 'oklch(0.20 0.05 25 / 0.96)' : 'oklch(0.20 0.04 70 / 0.94)',
          border: topIssue ? '1px solid oklch(0.62 0.18 25 / 0.65)' : '1px solid oklch(0.74 0.13 60 / 0.55)',
          color: topIssue ? 'oklch(0.86 0.12 25)' : 'oklch(0.88 0.12 70)',
          boxShadow: '0 12px 36px rgba(0,0,0,0.35)',
          fontFamily: 'var(--font-mono, monospace)',
          fontSize: 10.5,
          lineHeight: 1.45,
          pointerEvents: 'none',
        }}>
          <div style={{ textTransform: 'uppercase', letterSpacing: '0.12em', fontWeight: 700, marginBottom: 4 }}>
            {topIssue ? 'Preview runtime error' : showStalled ? 'Preview sans signal' : 'Preview vide detectee'}
          </div>
          <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
            {topIssue
              ? `${topIssue.message || 'Erreur runtime inconnue'}${topIssue.lineno ? ` (${topIssue.lineno}:${topIssue.colno ?? 0})` : ''}`
              : showStalled
                ? 'Le frame ne confirme pas son chargement. La generation continue d etre conservee, mais il faut corriger le runtime avant export.'
                : 'Le document charge mais ne peint quasiment rien. Aurora doit corriger le point d entree ou le contenu initial.'}
          </div>
        </div>
      )}
    </div>
  )
}
