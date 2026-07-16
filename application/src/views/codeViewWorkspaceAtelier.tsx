import { useMemo, useState, type CSSProperties } from 'react'
import { List } from 'react-window'
import {
  Activity,
  AlertTriangle,
  Braces,
  Bug,
  Dock,
  Eye,
  FileCode2,
  FolderTree,
  Gauge,
  ListTree,
  PanelBottom,
  Terminal,
} from 'lucide-react'
import type { CodeFile } from '../services/codeOrchestrator'
import type { CodeSandboxResult } from '../services/codeSandbox'
import type { DevServerState } from '../services/codeDevServer'
import { supportsBrowserWorkspaceRuntime } from '../services/codeBrowserWorkspaceRuntime'

type AtelierTab = 'tree' | 'file' | 'preview' | 'logs' | 'errors' | 'perf' | 'simulations' | 'state'
type DockMode = 'left' | 'bottom' | 'hidden'

const TABS: Array<{ id: AtelierTab; label: string; icon: typeof FolderTree }> = [
  { id: 'tree', label: 'Arbo', icon: FolderTree },
  { id: 'file', label: 'Fichier', icon: FileCode2 },
  { id: 'preview', label: 'Preview', icon: Eye },
  { id: 'logs', label: 'Logs', icon: Terminal },
  { id: 'errors', label: 'Erreurs', icon: Bug },
  { id: 'perf', label: 'Perf', icon: Gauge },
  { id: 'simulations', label: 'Simu', icon: Activity },
  { id: 'state', label: 'Etats', icon: Braces },
]

export function CodeViewWorkspaceAtelier({
  files,
  activeFile,
  activeFileData,
  onSelectFile,
  consoleOutput,
  devServerState,
  error,
  isGenerating,
  progress,
  recoveryStatus,
  validationResult,
}: {
  files: CodeFile[]
  activeFile: number
  activeFileData: CodeFile | null
  onSelectFile: (index: number) => void
  consoleOutput: string
  devServerState: DevServerState
  error: string | null
  isGenerating: boolean
  progress: string
  recoveryStatus: string | null
  validationResult: CodeSandboxResult | null
}) {
  const [activeTab, setActiveTab] = useState<AtelierTab>('tree')
  const [dockMode, setDockMode] = useState<DockMode>('left')
  const stats = useMemo(() => buildWorkspaceStats(files, consoleOutput, validationResult), [files, consoleOutput, validationResult])

  if (dockMode === 'hidden') {
    return (
      <button
        type="button"
        onClick={() => setDockMode('left')}
        className="flex w-full items-center justify-center gap-2 rounded-[1.1rem] border border-aurora-border/35 bg-aurora-surface/65 px-3 py-2 text-[11px] text-aurora-text-dim hover:text-aurora-text"
        title="Rouvrir l atelier"
      >
        <Dock size={13} />
        <span>Atelier masque</span>
      </button>
    )
  }

  return (
    <section
      className={`overflow-hidden rounded-[1.4rem] border border-aurora-border/35 bg-aurora-surface/65 ${
        dockMode === 'bottom' ? 'xl:col-span-2' : ''
      }`}
    >
      <div className="flex items-center justify-between gap-2 border-b border-aurora-border/25 px-3 py-2">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-aurora-text-dim">
          <Dock size={13} />
          <span>Atelier</span>
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => setDockMode(dockMode === 'left' ? 'bottom' : 'left')}
            title={dockMode === 'left' ? 'Ancrer en bas' : 'Ancrer a gauche'}
            className="grid h-7 w-7 place-items-center rounded-lg text-aurora-text-dim hover:bg-white/[0.04] hover:text-aurora-text"
          >
            {dockMode === 'left' ? <PanelBottom size={13} /> : <ListTree size={13} />}
          </button>
          <button
            type="button"
            onClick={() => setDockMode('hidden')}
            title="Masquer"
            className="grid h-7 w-7 place-items-center rounded-lg text-aurora-text-dim hover:bg-white/[0.04] hover:text-aurora-text"
          >
            <Dock size={13} />
          </button>
        </div>
      </div>

      <div className="flex gap-1 overflow-x-auto border-b border-aurora-border/20 px-2 py-2">
        {TABS.map((tab) => {
          const Icon = tab.icon
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`flex h-7 shrink-0 items-center gap-1 rounded-lg px-2 text-[10px] transition-colors ${
                activeTab === tab.id
                  ? 'bg-aurora-accent/18 text-aurora-accent-light'
                  : 'text-aurora-text-dim hover:bg-white/[0.04] hover:text-aurora-text'
              }`}
            >
              <Icon size={12} />
              <span>{tab.label}</span>
            </button>
          )
        })}
      </div>

      <div className="min-h-[13rem] p-3">
        {activeTab === 'tree' && (
          <VirtualizedProjectTree
            files={files}
            activeFile={activeFile}
            onSelectFile={onSelectFile}
          />
        )}
        {activeTab === 'file' && (
          <SummaryPanel
            rows={[
              ['Fichier actif', activeFileData?.name || 'Aucun'],
              ['Langage', activeFileData?.language || 'inconnu'],
              ['Taille', activeFileData ? `${formatBytes(activeFileData.content.length)} / ${activeFileData.content.split('\n').length} lignes` : '-'],
              ['Total projet', `${files.length} fichiers / ${formatBytes(stats.totalBytes)}`],
            ]}
          />
        )}
        {activeTab === 'preview' && (
          <SummaryPanel
            rows={[
              ['Runtime iframe', stats.browserRuntime ? 'esbuild-wasm + import-map' : 'HTML statique / dev-server / console'],
              ['Dev-server', devServerState.running && devServerState.url ? devServerState.url : devServerState.process || 'inactif'],
              ['Generation', isGenerating ? 'active' : 'idle'],
              ['Progression', progress || '-'],
            ]}
          />
        )}
        {activeTab === 'logs' && (
          <LogPanel content={consoleOutput || 'Aucun log runtime pour le moment.'} />
        )}
        {activeTab === 'errors' && (
          <ErrorPanel error={error} validationResult={validationResult} />
        )}
        {activeTab === 'perf' && (
          <SummaryPanel
            rows={[
              ['Fichiers', String(files.length)],
              ['Taille totale', formatBytes(stats.totalBytes)],
              ['Plus gros fichier', stats.largestFile ? `${stats.largestFile.name} (${formatBytes(stats.largestFile.content.length)})` : '-'],
              ['Sandbox', validationResult ? (validationResult.ok ? 'OK' : 'ECHEC') : 'non lance'],
            ]}
          />
        )}
        {activeTab === 'simulations' && (
          <SummaryPanel
            rows={[
              ['Desktop', '1440x900, rendu iframe'],
              ['Tablet', '760x1024, cadre physique'],
              ['Mobile', '360x720, cadre physique'],
              ['Labo WS12', devServerState.running ? 'pret pour audit Playwright' : 'attend un serveur ou bundle iframe'],
            ]}
          />
        )}
        {activeTab === 'state' && (
          <SummaryPanel
            rows={[
              ['Generation', isGenerating ? 'en cours' : 'terminee/idle'],
              ['Recovery', recoveryStatus || 'aucun'],
              ['Validation', validationResult ? validationResult.summary : 'non disponible'],
              ['Logs', `${stats.logLines} lignes`],
            ]}
          />
        )}
      </div>
    </section>
  )
}

function VirtualizedProjectTree({
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

function ProjectTreeRow({
  index,
  style,
  rows,
  activeFile,
  onSelectFile,
  ariaAttributes,
}: {
  index: number
  style: CSSProperties
  rows: Array<{ index: number; path: string; depth: number; bytes: number }>
  activeFile: number
  onSelectFile: (index: number) => void
  ariaAttributes: { 'aria-posinset': number; 'aria-setsize': number; role: 'listitem' }
}) {
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

function SummaryPanel({ rows }: { rows: Array<[string, string]> }) {
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

function LogPanel({ content }: { content: string }) {
  return (
    <pre className="max-h-[14rem] overflow-auto rounded-xl border border-aurora-border/25 bg-[#091116] px-3 py-3 text-[11px] leading-5 text-aurora-text-dim whitespace-pre-wrap">
      <code>{content.split('\n').slice(-80).join('\n')}</code>
    </pre>
  )
}

function ErrorPanel({
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

function buildWorkspaceStats(files: CodeFile[], consoleOutput: string, validationResult: CodeSandboxResult | null) {
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

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 102.4) / 10} KB`
  return `${Math.round(bytes / 1024 / 102.4) / 10} MB`
}
