import { Square } from 'lucide-react'
import type { UseCodeViewLogic } from '../hooks/useCodeViewLogic.ts'
import { GREEN } from './auroraV1CodeHelpers.ts'
import { Eyebrow } from './auroraV1CodePrimitives.tsx'

type FinalStats = {
  avg: number
  max: number
  tokens: number
  durationSec: number
} | null

export function AuroraV1CodeOutputHeader({
  code,
  finalStats,
  tokensPerSec,
  tpsHistory,
}: {
  code: UseCodeViewLogic
  finalStats: FinalStats
  tokensPerSec: number | null
  tpsHistory: number[]
}) {
  return (
    <div style={{
      padding: '14px 22px',
      borderBottom: '1px solid var(--line, rgba(255,255,255,0.12))',
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    }}>
      <Eyebrow dot={GREEN}>
        {code.streaming ? 'stream · live' : code.hasOutput ? 'output · ready' : 'output'}
      </Eyebrow>
      {code.streaming && (
        <button type="button" onClick={code.abort}
          title="Arrêter le streaming (Esc dans le composer)"
          style={{
            marginRight: 8, padding: '3px 8px',
            background: 'oklch(0.55 0.18 25 / 0.10)',
            color: 'oklch(0.78 0.16 25)',
            border: '1px solid oklch(0.55 0.18 25 / 0.45)',
            fontSize: 10, fontWeight: 700,
            fontFamily: 'var(--font-mono, monospace)',
            cursor: 'pointer', borderRadius: 4,
            letterSpacing: '0.05em', textTransform: 'uppercase',
            display: 'inline-flex', alignItems: 'center', gap: 5,
          }}>
          <Square size={9} fill="currentColor" /> Stop
        </button>
      )}
      <span style={{
        fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
        color: 'var(--fg-dim, #aaa)',
        display: 'inline-flex', alignItems: 'center', gap: 6,
      }}>
        {code.streaming && (
          <span style={{
            display: 'inline-block', width: 6, height: 6,
            borderRadius: '50%', background: GREEN,
            animation: 'aurora-pulse-code 1.2s ease-in-out infinite',
          }} />
        )}
        <span>
          {code.hasOutput || code.streaming
            ? `${code.model} · ${code.streamOutput.length} c. · ~${Math.ceil(code.streamOutput.length / 4)}t${
              code.streaming && tokensPerSec !== null && tokensPerSec > 0
                ? ` · ${tokensPerSec.toFixed(1)}t/s`
                : ''
            }${
              !code.streaming && finalStats !== null
                ? ` · avg ${finalStats.avg.toFixed(1)} · max ${finalStats.max.toFixed(1)} · ${finalStats.durationSec.toFixed(1)}s`
                : ''
            }`
            : code.model}
        </span>
        {code.streaming && tpsHistory.length >= 2 && (() => {
          const max = Math.max(1, ...tpsHistory)
          return (
            <div style={{
              display: 'flex', alignItems: 'flex-end', gap: 1,
              height: 12, width: 50,
            }} title={`tps history · last ${tpsHistory.length} samples · max ${max.toFixed(1)}t/s`}>
              {tpsHistory.map((value, index) => (
                <span key={index} style={{
                  flex: 1, height: Math.max(1, (value / max) * 12),
                  background: GREEN, borderRadius: 1, opacity: 0.85,
                }} />
              ))}
            </div>
          )
        })()}
        <style>{`
          @keyframes aurora-pulse-code {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.4; transform: scale(0.85); }
          }
        `}</style>
      </span>
    </div>
  )
}
