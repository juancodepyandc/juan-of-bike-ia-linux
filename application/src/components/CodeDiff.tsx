/**
 * CodeDiff — simple unified diff viewer for before/after code strings.
 * Used by the Code module to show the modification an IA cast proposes,
 * and by future Drawing / Forge rig-editor flows.
 */
import { useMemo } from 'react'
import { diffLines, diffStats } from '../utils/simpleDiff'

export default function CodeDiff({
  before, after, filename,
}: {
  before: string
  after: string
  filename?: string
}) {
  const lines = useMemo(() => diffLines(before, after), [before, after])
  const stats = diffStats(lines)

  return (
    <div className="code-diff">
      <div className="code-diff-head">
        <span className="code-diff-name">{filename || 'diff'}</span>
        <span className="code-diff-stats">
          <span className="is-add">+{stats.added}</span>
          <span className="is-del">−{stats.removed}</span>
          <span className="is-eq">={stats.unchanged}</span>
        </span>
      </div>
      <pre className="code-diff-body">
        {lines.map((l, i) => (
          <div key={i} className={`code-diff-line op-${l.op}`}>
            <span className="code-diff-gutter">
              <span className="col-old">{l.oldLine ?? ''}</span>
              <span className="col-new">{l.newLine ?? ''}</span>
            </span>
            <span className="code-diff-marker">{l.op === 'add' ? '+' : l.op === 'del' ? '−' : ' '}</span>
            <span className="code-diff-text">{l.text || ' '}</span>
          </div>
        ))}
      </pre>
    </div>
  )
}
