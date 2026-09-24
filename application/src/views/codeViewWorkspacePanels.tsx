import { useMemo } from 'react'
import { List, type RowComponentProps } from 'react-window'
import { AlertTriangle, FileCode2 } from 'lucide-react'
import type { CodeFile } from '../services/codeOrchestrator.ts'
import type { CodeSandboxResult } from '../services/codeSandbox.ts'
import { supportsBrowserWorkspaceRuntime } from '../services/codeBrowserWorkspaceRuntime.ts'

export function VirtualizedProjectTree({
  files,
  activeFile,
  onSelectFile,
}: {
  files: CodeFile[]
  activeFile: number
  onSelectFile: (index: number) => void
}) {
  const rows = useMemo(
    () => files
      .map((file, index) => ({
        index,
        path: file.name.replace(/\\/g, '/'),
        depth: Math.max(0, file.name.replace(/\\/g, '/').split('/').length - 1),
        bytes: file.content.length,
      }))
      .sort((a, b) => a.path.localeCompare(b.path)),
    [files],
  )

  if (!rows.length) {
    return (
      <div className="grid h-[12rem] place-items-center rounded-xl border border-dashed border-aurora-border/35 text-center text-xs text-aurora-text-dim">
        Arborescence en attente de fichiers.
      </div>
    )
  }

  return (
    <List
      rowComponent={ProjectTreeRow}
      rowCount={rows.length}
      rowHeight={28}
      rowProps={{ rows, activeFile, onSelectFile }}
      overscanCount={16}
      defaultHeight={250}
      style={{ height: '14rem', width: '100%' }}
    />
  )
}

type ProjectTreeRowData = {
  rows: Array<{ index: number; path: string; depth: number; bytes: number }>
  activeFile: number
  onSelectFile: (index: number) => void
}

function ProjectTreeRow({
  index,
  style,
  rows,
  activeFile,
  onSelectFile,
  ariaAttributes,
}: RowComponentProps<ProjectTreeRowData>) {
  const row = rows[index]
  if (!row) return null
  const isActive = row.index === activeFile
  return (
    <button
      {...ariaAttributes}
      type="button"
      onClick={() => onSelectFile(row.index)}
      style={{ ...style, paddingLeft: `${8 + row.depth * 12}px` }}
      className={`flex w-full items-center gap-2 rounded-lg px-2 text-left text-[11px] ${
        isActive ? 'bg-aurora-accent/15 text-aurora-accent-light' : 'text-aurora-text-muted hover:bg-white/[0.04] hover:text-aurora-text'
      }`}
    >
      <FileCode2 size={13} className="shrink-0" />
      <span className="min-w-0 flex-1 truncate">{row.path}</span>
      <span className="shrink-0 text-[10px] text-aurora-text-dim">{formatBytes(row.bytes)}</span>
    </button>
  )
}

export function SummaryPanel({ rows }: { rows: Array<[string, string]> }) {
  return (
    <div className="space-y-2">
      {rows.map(([label, value]) => (
        <div key={label} className="rounded-xl border border-aurora-border/25 bg-aurora-bg/25 px-3 py-2">
          <p className="text-[10px] uppercase tracking-[0.16em] text-aurora-text-dim">{label}</p>
          <p className="mt-1 break-words text-xs text-aurora-text">{value}</p>
        </div>
      ))}
    </div>
  )
}

export function LogPanel({ content }: { content: string }) {
  return (
    <pre className="max-h-[14rem] overflow-auto rounded-xl border border-aurora-border/25 bg-[#091116] px-3 py-3 text-[11px] leading-5 text-aurora-text-dim whitespace-pre-wrap">
      <code>{content.split('\n').slice(-80).join('\n')}</code>
    </pre>
  )
}

export function ErrorPanel({
  error,
  validationResult,
}: {
  error: string | null
  validationResult: CodeSandboxResult | null
}) {
  const failedSteps = validationResult?.steps.filter((step) => !step.ok) ?? []
  if (!error && failedSteps.length === 0) {
    return (
      <div className="grid h-[12rem] place-items-center rounded-xl border border-aurora-green/20 bg-aurora-green/10 text-center text-xs text-aurora-green">
        Aucun echec connu dans l etat courant.
      </div>
    )
  }
  return (
    <div className="space-y-2">
      {error && (
        <div className="rounded-xl border border-aurora-red/25 bg-aurora-red/10 px-3 py-2 text-xs text-aurora-red">
          <AlertTriangle size={13} className="mb-1" />
          {error}
        </div>
      )}
      {failedSteps.map((step) => (
        <div key={`${step.label}-${step.command}`} className="rounded-xl border border-aurora-red/25 bg-aurora-red/10 px-3 py-2">
          <p className="text-xs text-aurora-red">{step.label}</p>
          <p className="mt-1 text-[10px] text-aurora-text-dim">{step.command}</p>
        </div>
      ))}
    </div>
  )
}

export function buildWorkspaceStats(files: CodeFile[], consoleOutput: string) {
  const totalBytes = files.reduce((sum, file) => sum + file.content.length, 0)
  const largestFile = files.reduce<CodeFile | null>(
    (largest, file) => (!largest || file.content.length > largest.content.length ? file : largest),
    null,
  )
  return {
    totalBytes,
    largestFile,
    logLines: consoleOutput ? consoleOutput.split('\n').length : 0,
    browserRuntime: supportsBrowserWorkspaceRuntime(files),
  }
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 102.4) / 10} KB`
  return `${Math.round(bytes / 1024 / 102.4) / 10} MB`
}
