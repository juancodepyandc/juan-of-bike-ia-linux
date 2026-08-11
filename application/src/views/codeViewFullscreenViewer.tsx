import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import {
  ArrowLeft, ChevronsDownUp, Eye, FileCode2, FolderTree, PanelLeftClose, PanelLeftOpen, X,
} from 'lucide-react'
import CodeFileTree from '../components/CodeFileTree'
import { buildLivePreviewHtml } from '../components/CodeProjectPreview'
import {
  buildCodeFileTree,
  collectDirectoryPaths,
  formatCodeFileSize,
} from '../services/codeFileTreeModel'
import type { CodeFile } from '../services/codeOrchestrator'

const CodeMirrorViewer = lazy(() => import('../components/CodeMirrorViewer'))

// ---------------------------------------------------------------------------
// Viewer plein ecran du projet genere: arborescence a gauche, rendu a droite.
//
// Contraintes tenues ici:
//  - z-[120] minimum: l'overlay FX de generation est OPAQUE a z-118. En dessous,
//    ce viewer serait invisible.
//  - la SCENE (`stage`) reste MONTEE en permanence: consulter une source pose un
//    calque par-dessus au lieu de demonter l'iframe. Demonter l'iframe la
//    rendrait blanche (le srcdoc est pose par un effet qui ne se rejouerait pas).
//  - srcdoc uniquement, jamais de Blob URL (cause d'OOM, cf. codeViewPreviewPanel).
// ---------------------------------------------------------------------------

const TREE_MIN_WIDTH = 190
const TREE_MAX_WIDTH = 560
const TREE_DEFAULT_WIDTH = 288

export function CodeFullscreenViewer({
  files,
  toolbar,
  stage,
  onExit,
}: {
  files: CodeFile[]
  /** Barre d'outils du panneau (viewports, onglet, reduire) — reutilisee telle quelle. */
  toolbar: ReactNode
  /** La scene de rendu, montee une seule fois par le panneau proprietaire de l'iframe. */
  stage: ReactNode
  onExit: () => void
}) {
  const [treeOpen, setTreeOpen] = useState(true)
  const [treeWidth, setTreeWidth] = useState(TREE_DEFAULT_WIDTH)
  const [selected, setSelected] = useState<number | null>(null)
  const [collapsedDirs, setCollapsedDirs] = useState<ReadonlySet<string>>(() => new Set())

  const selectedFile = selected !== null ? files[selected] ?? null : null

  // Echap: ferme d'abord la source ouverte, puis seulement le plein ecran.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      if (selectedFile) setSelected(null)
      else onExit()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [selectedFile, onExit])

  // Un fichier retire par une regeneration ne doit pas laisser un calque fantome.
  useEffect(() => {
    if (selected !== null && selected >= files.length) setSelected(null)
  }, [files.length, selected])

  const allDirs = useMemo(() => collectDirectoryPaths(buildCodeFileTree(files)), [files])
  const everythingCollapsed = allDirs.length > 0 && allDirs.every((path) => collapsedDirs.has(path))

  const toggleDirectory = useCallback((path: string) => {
    setCollapsedDirs((previous) => {
      const next = new Set(previous)
      if (next.has(path)) next.delete(path)
      else next.add(path)
      return next
    })
  }, [])

  const toggleAllDirectories = useCallback(() => {
    setCollapsedDirs(everythingCollapsed ? new Set() : new Set(allDirs))
  }, [everythingCollapsed, allDirs])

  const totalSize = useMemo(
    () => files.reduce((sum, file) => sum + file.content.length, 0),
    [files],
  )

  const dragRef = useRef<{ startX: number; startWidth: number } | null>(null)
  const onResizeStart = useCallback((event: React.PointerEvent<HTMLDivElement>) => {
    dragRef.current = { startX: event.clientX, startWidth: treeWidth }
    event.currentTarget.setPointerCapture(event.pointerId)
  }, [treeWidth])
  const onResizeMove = useCallback((event: React.PointerEvent<HTMLDivElement>) => {
    const drag = dragRef.current
    if (!drag) return
    const next = drag.startWidth + (event.clientX - drag.startX)
    setTreeWidth(Math.min(TREE_MAX_WIDTH, Math.max(TREE_MIN_WIDTH, next)))
  }, [])
  const onResizeEnd = useCallback((event: React.PointerEvent<HTMLDivElement>) => {
    dragRef.current = null
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }
  }, [])

  return (
    <div className="fixed inset-0 z-[120] flex flex-col bg-[#0d1117]">
      {toolbar}
      <div className="flex min-h-0 flex-1">
        {treeOpen ? (
          <aside
            className="flex min-h-0 shrink-0 flex-col border-r border-white/5 bg-[#0a0f14]"
            style={{ width: `${treeWidth}px` }}
          >
            <div className="flex items-center gap-1.5 border-b border-white/5 px-3 py-2 text-[10px] uppercase tracking-[0.16em] text-aurora-text-dim">
              <FolderTree size={12} />
              <span className="truncate">
                {files.length} fichier{files.length > 1 ? 's' : ''} · {formatCodeFileSize(totalSize)}
              </span>
              <button
                onClick={toggleAllDirectories}
                title={everythingCollapsed ? 'Deplier tous les dossiers' : 'Replier tous les dossiers'}
                className="ml-auto rounded p-1 text-aurora-text-dim transition-colors hover:bg-white/5 hover:text-aurora-text"
              >
                <ChevronsDownUp size={12} />
              </button>
              <button
                onClick={() => setTreeOpen(false)}
                title="Masquer l arborescence — le rendu prend toute la largeur"
                className="rounded p-1 text-aurora-text-dim transition-colors hover:bg-white/5 hover:text-aurora-text"
              >
                <PanelLeftClose size={12} />
              </button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto p-2">
              <CodeFileTree
                files={files}
                activeFile={selected ?? -1}
                onSelectFile={setSelected}
                showSize
                collapsedPaths={collapsedDirs}
                onToggleDirectory={toggleDirectory}
              />
            </div>
          </aside>
        ) : (
          <button
            onClick={() => setTreeOpen(true)}
            title="Afficher l arborescence du projet"
            className="flex w-9 shrink-0 flex-col items-center gap-2 border-r border-white/5 bg-[#0a0f14] py-3 text-aurora-text-dim transition-colors hover:text-aurora-text"
          >
            <PanelLeftOpen size={14} />
            <span className="text-[9px] [writing-mode:vertical-rl]">Fichiers ({files.length})</span>
          </button>
        )}

        {treeOpen && (
          <div
            onPointerDown={onResizeStart}
            onPointerMove={onResizeMove}
            onPointerUp={onResizeEnd}
            onPointerCancel={onResizeEnd}
            onDoubleClick={() => setTreeWidth(TREE_DEFAULT_WIDTH)}
            title="Glisser pour redimensionner — double-clic pour reinitialiser"
            className="w-1 shrink-0 cursor-col-resize bg-white/5 transition-colors hover:bg-aurora-accent/50"
          />
        )}

        {/* La scene reste montee en permanence; la source vient PAR-DESSUS. */}
        <section className="relative flex min-w-0 flex-1 flex-col">
          {stage}
          {selectedFile && (
            <SourceOverlay
              file={selectedFile}
              files={files}
              onClose={() => setSelected(null)}
            />
          )}
        </section>
      </div>
    </div>
  )
}

function SourceOverlay({
  file,
  files,
  onClose,
}: {
  file: CodeFile
  files: CodeFile[]
  onClose: () => void
}) {
  const isHtml = /\.(html|htm)$/i.test(file.name)
  const [mode, setMode] = useState<'source' | 'preview'>('source')
  useEffect(() => { setMode('source') }, [file.name])

  // Apercu d'un .html precis: on reordonne la liste pour que CE fichier devienne
  // l'entree lue par le constructeur existant (il prend le premier .html), sans
  // toucher au chemin de build. Les CSS/JS freres restent donc inlines.
  const htmlPreview = useMemo(() => {
    if (!isHtml || mode !== 'preview') return null
    const others = files.filter((candidate) => candidate.name !== file.name)
    return buildLivePreviewHtml([file, ...others])
  }, [isHtml, mode, file, files])

  return (
    <div className="absolute inset-0 z-10 flex flex-col bg-[#091116]">
      <div className="flex shrink-0 items-center gap-2 border-b border-white/5 bg-[#0a0f14] px-3 py-2">
        <FileCode2 size={13} className="shrink-0 text-aurora-accent-light" />
        <span className="truncate text-[12px] text-aurora-text" title={file.name}>{file.name}</span>
        <span className="shrink-0 font-mono text-[10px] text-aurora-text-dim">
          {formatCodeFileSize(file.content.length)}
        </span>
        {isHtml && (
          <div className="ml-2 flex shrink-0 items-center rounded-lg border border-white/10 p-0.5">
            {(['source', 'preview'] as const).map((value) => (
              <button
                key={value}
                onClick={() => setMode(value)}
                className={`flex h-5 items-center gap-1 rounded px-2 text-[10px] transition-colors ${
                  mode === value
                    ? 'bg-aurora-accent/20 text-aurora-accent-light'
                    : 'text-aurora-text-dim hover:text-aurora-text'
                }`}
              >
                {value === 'source' ? <FileCode2 size={10} /> : <Eye size={10} />}
                <span>{value === 'source' ? 'Source' : 'Apercu'}</span>
              </button>
            ))}
          </div>
        )}
        <button
          onClick={onClose}
          title="Revenir au rendu live (Echap)"
          className="ml-auto flex h-6 shrink-0 items-center gap-1 rounded-md px-2 text-[10px] text-aurora-text-dim transition-colors hover:bg-white/5 hover:text-aurora-text"
        >
          <ArrowLeft size={11} />
          <span>Retour au rendu</span>
        </button>
        <button
          onClick={onClose}
          title="Fermer la source"
          className="shrink-0 rounded p-1 text-aurora-text-dim transition-colors hover:bg-white/5 hover:text-aurora-text"
        >
          <X size={12} />
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-auto">
        {mode === 'preview' && isHtml ? (
          htmlPreview ? (
            <iframe
              key={file.name}
              title={`Apercu de ${file.name}`}
              sandbox="allow-scripts allow-same-origin"
              srcDoc={htmlPreview}
              className="h-full w-full border-0 bg-white"
            />
          ) : (
            <p className="px-5 py-5 text-[12px] text-aurora-text-dim">
              Ce fichier HTML est vide — rien a afficher en apercu.
            </p>
          )
        ) : (
          <Suspense fallback={<pre className="px-5 py-5 text-[13px] text-aurora-text-dim">Chargement de CodeMirror...</pre>}>
            <CodeMirrorViewer
              code={file.content}
              language={file.language ?? file.name}
              showLineNumbers
            />
          </Suspense>
        )}
      </div>
    </div>
  )
}
