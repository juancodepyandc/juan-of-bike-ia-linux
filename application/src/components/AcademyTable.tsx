/**
 * AcademyTable — render a parsed markdown table with sticky header,
 * row highlight, and click-to-copy. v82bw.
 */
import { useState } from 'react'
import { Copy, Check } from 'lucide-react'
import type { AcademyTable as TableData } from '../hooks/useAcademyViewLogic.ts'

const GOLD = 'oklch(0.74 0.11 90)'

interface Props {
  data: TableData
}

export default function AcademyTable({ data }: Props) {
  const [hover, setHover] = useState<number | null>(null)
  const [copied, setCopied] = useState(false)

  const copyAll = async () => {
    const lines: string[] = []
    lines.push('| ' + data.headers.join(' | ') + ' |')
    lines.push('|' + data.headers.map(() => '---').join('|') + '|')
    for (const r of data.rows) lines.push('| ' + r.join(' | ') + ' |')
    try {
      await navigator.clipboard.writeText(lines.join('\n'))
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1200)
    } catch { /* noop */ }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <div style={{
        display: 'flex', gap: 8, alignItems: 'center',
        fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
        color: 'var(--fg-dim, #aaa)',
      }}>
        <span style={{ color: GOLD }}>{data.rows.length} ligne(s) · {data.headers.length} col(s)</span>
        <span style={{ flex: 1 }} />
        <button type="button" onClick={copyAll}
          style={{
            padding: '3px 8px', fontSize: 10,
            background: copied ? 'oklch(0.72 0.12 145)' : 'transparent',
            color: copied ? '#0a0a0a' : 'var(--fg-dim, #aaa)',
            border: '1px solid var(--line, rgba(255,255,255,0.12))',
            borderRadius: 4, cursor: 'pointer',
            display: 'inline-flex', alignItems: 'center', gap: 4,
            fontFamily: 'var(--font-mono, monospace)',
          }}>
          {copied ? <><Check size={10} /> copié</> : <><Copy size={10} /> markdown</>}
        </button>
      </div>
      <div style={{
        maxHeight: 320, overflow: 'auto',
        border: '1px solid var(--line, rgba(255,255,255,0.12))',
        borderRadius: 6,
      }}>
        <table style={{
          width: '100%', borderCollapse: 'collapse',
          fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
          color: 'var(--fg, #f5f5f5)',
        }}>
          <thead style={{
            position: 'sticky', top: 0,
            background: 'var(--bg-raised, rgba(0,0,0,0.4))',
            backdropFilter: 'blur(6px)',
          }}>
            <tr>
              {data.headers.map((h, i) => (
                <th key={i} style={{
                  padding: '8px 10px', textAlign: 'left',
                  borderBottom: `1px solid ${GOLD}`,
                  fontFamily: 'var(--font-mono, monospace)',
                  fontSize: 10, fontWeight: 700, letterSpacing: '0.14em',
                  color: GOLD, textTransform: 'uppercase',
                  whiteSpace: 'nowrap',
                }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row, i) => (
              <tr key={i}
                onMouseEnter={() => setHover(i)}
                onMouseLeave={() => setHover(null)}
                style={{
                  background: hover === i ? `${GOLD}10` : 'transparent',
                  transition: 'background 100ms ease',
                }}>
                {row.map((cell, j) => (
                  <td key={j} style={{
                    padding: '6px 10px',
                    borderBottom: '1px dashed var(--line-soft, rgba(255,255,255,0.06))',
                    verticalAlign: 'top',
                    color: j === 0 ? 'var(--fg, #f5f5f5)' : 'var(--fg-dim, #aaa)',
                    fontWeight: j === 0 ? 600 : 400,
                  }}>{cell}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
