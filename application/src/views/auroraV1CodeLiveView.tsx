import { lazy, Suspense } from 'react'
import { Copy, StopCircle, X } from 'lucide-react'
import type { UseCodeViewLogic } from '../hooks/useCodeViewLogic'

const CodeBlock = lazy(() => import('../components/CodeBlock'))

export function AuroraV1CodeLiveView({
  code,
  onClose,
}: {
  code: UseCodeViewLogic
  onClose: () => void
}) {
  return (
    <div className="aurora-v1-live-fade" style={{
      height: '100%', display: 'flex', flexDirection: 'column',
      background: 'var(--bg, #0c0a09)', color: 'var(--fg, #f5f5f5)',
      fontFamily: 'var(--font-sans, system-ui)', overflow: 'hidden',
    }}>
      <div style={{
        padding: '14px 24px', display: 'flex', alignItems: 'center', gap: 12,
        borderBottom: '1px solid var(--line, rgba(255,255,255,0.12))',
        background: 'linear-gradient(180deg, oklch(0.72 0.12 145 / 0.10), transparent)',
      }}>
        <span style={{
          fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
          letterSpacing: '0.18em', textTransform: 'uppercase',
          color: 'oklch(0.78 0.16 145)',
        }}>● Orchestrateur Code · {code.model}</span>
        <span style={{ flex: 1 }} />
        {code.streaming && (
          <button type="button" onClick={code.abort}
            style={{
              padding: '6px 12px', fontSize: 11,
              background: 'oklch(0.55 0.18 25 / 0.15)',
              color: 'oklch(0.78 0.16 25)',
              border: '1px solid oklch(0.78 0.16 25 / 0.45)',
              cursor: 'pointer', borderRadius: 6,
              display: 'inline-flex', alignItems: 'center', gap: 6,
            }}><StopCircle size={12} /> Stop</button>
        )}
        {code.streamOutput && !code.streaming && (
          <button type="button" onClick={() => {
            void navigator.clipboard?.writeText(code.streamOutput).catch(() => {})
          }}
            style={{
              padding: '6px 12px', fontSize: 11,
              background: 'transparent', color: 'var(--fg-dim, #aaa)',
              border: '1px solid var(--line, rgba(255,255,255,0.18))',
              cursor: 'pointer', borderRadius: 6,
              display: 'inline-flex', alignItems: 'center', gap: 6,
            }}><Copy size={12} /> Copier</button>
        )}
        <button type="button" onClick={onClose}
          style={{
            padding: '6px 12px', fontSize: 11,
            fontFamily: 'var(--font-mono, monospace)',
            background: 'transparent', color: 'var(--fg-dim, #aaa)',
            border: '1px solid var(--line, rgba(255,255,255,0.18))',
            cursor: 'pointer', borderRadius: 6,
            display: 'inline-flex', alignItems: 'center', gap: 6,
          }}><X size={12} /> Fermer</button>
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: 0, display: 'flex' }}>
        {!code.streamOutput && !code.streaming ? (
          <div style={{
            flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: 'var(--fg-mute, #888)',
            fontFamily: 'var(--font-display, serif)', fontStyle: 'italic', fontSize: 18,
          }}>
            Aucun code généré. Reviens à la chrome editorial pour saisir un brief.
          </div>
        ) : (
          <Suspense fallback={
            <pre style={{
              flex: 1, padding: 24, margin: 0, overflow: 'auto',
              fontFamily: 'var(--font-mono, monospace)', fontSize: 12,
              color: 'var(--fg, #f5f5f5)', whiteSpace: 'pre-wrap',
            }}>{code.streamOutput}</pre>
          }>
            <div style={{ flex: 1, padding: 24, overflow: 'auto' }}>
              <CodeBlock code={code.streamOutput} language={'typescript'} />
            </div>
          </Suspense>
        )}
      </div>
    </div>
  )
}
