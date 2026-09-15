import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Activity,
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
import type { CodeFile } from '../services/codeOrchestrator.ts'
import type { CodeSandboxResult } from '../services/codeSandbox.ts'
import type { DevServerState } from '../services/codeDevServer.ts'
import {
  runCodeSimulationLab,
  type CodeSimulationLabReport,
} from '../services/codeSimulationLab.ts'
import {
  buildWorkspaceStats,
  ErrorPanel,
  formatBytes,
  LogPanel,
  SimulationPanel,
  SummaryPanel,
  VirtualizedProjectTree,
} from './codeViewWorkspacePanels.tsx'

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
  const [simulationReport, setSimulationReport] = useState<CodeSimulationLabReport | null>(null)
  const [simulationError, setSimulationError] = useState<string | null>(null)
  const [simulationRunning, setSimulationRunning] = useState(false)
  const lastSimulationUrlRef = useRef<string | null>(null)
  const stats = useMemo(() => buildWorkspaceStats(files, consoleOutput), [files, consoleOutput])

  useEffect(() => {
    const url = devServerState.running ? devServerState.url : null
    if (!url || lastSimulationUrlRef.current === url) return
    lastSimulationUrlRef.current = url
    const controller = new AbortController()
    setSimulationRunning(true)
    setSimulationError(null)
    void runCodeSimulationLab({ url, waitMs: 1200, signal: controller.signal })
      .then((report) => setSimulationReport(report))
      .catch((err) => {
        if (controller.signal.aborted) return
        setSimulationError(err instanceof Error ? err.message : String(err))
      })
      .finally(() => {
        if (!controller.signal.aborted) setSimulationRunning(false)
      })
    return () => controller.abort()
  }, [devServerState.running, devServerState.url])

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
      className={`min-w-0 max-w-full overflow-hidden rounded-[1.4rem] border border-aurora-border/35 bg-aurora-surface/65 ${
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

      <div className="flex flex-wrap gap-1 border-b border-aurora-border/20 px-2 py-2 sm:flex-nowrap sm:overflow-x-auto">
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
          <SimulationPanel
            report={simulationReport}
            running={simulationRunning}
            error={simulationError}
            devServerUrl={devServerState.url}
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
