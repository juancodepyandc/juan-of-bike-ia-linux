import { useEffect, useMemo, useRef, useState } from 'react'
import { buildPreviewHtml, isWebProject } from './codeProjectPreviewHtml'
export { buildLivePreviewHtml, webProjectFromFiles } from './codeProjectPreviewHtml'

// Heavy project detection — prevents recomputing + reloading the iframe on
// every token when the project is Three.js/WebGL (GPU killer) or simply too
// large. This is what caused "page crash vers 90%" on Three.js game projects.
function isHeavyWebGLProject(files: CodeFile[]): boolean {
  for (const f of files) {
    if (f.content.length > 80_000) return true
    const head = f.content.slice(0, 4000).toLowerCase()
    if (/three\.js|three\.module|from\s+['"]three['"]/.test(head)) return true
    if (/webglrenderer|getcontext\(\s*['"]webgl/.test(head)) return true
  }
  return false
}

const SIDE_PREVIEW_TOTAL_CAP = 150_000
import {
  Eye,
  EyeOff,
  Maximize2,
  Minimize2,
  Monitor,
  Smartphone,
  Tablet,
  RefreshCw,
  Globe,
  Terminal,
  ExternalLink,
} from 'lucide-react'
import type { DevServerState } from '../services/codeDevServer'

type CodeFile = {
  name: string
  language: string
  content: string
}

type ViewportMode = 'desktop' | 'tablet' | 'mobile'

const VIEWPORT_SIZES: Record<ViewportMode, { width: string; label: string }> = {
  desktop: { width: '100%', label: 'Desktop' },
  tablet: { width: '768px', label: 'Tablet' },
  mobile: { width: '375px', label: 'Mobile' },
}

// ---------------------------------------------------------------------------
// Stream parser — extract partial files from a live "--- FICHIER: ..." stream
// so a live preview can refresh as HTML/CSS/JS are still being written.
// Exported so the big code viewer can reuse it without duplicating the logic.
// ---------------------------------------------------------------------------

export function parsePartialStreamFiles(raw: string): CodeFile[] {
  if (!raw) return []
  const parts = raw.split(/---\s*(?:FICHIER|FILE):\s*(.+?)\s*---/i)
  if (parts.length < 3) return []
  const files: CodeFile[] = []
  for (let i = 1; i < parts.length; i += 2) {
    const name = parts[i]?.trim()
    if (!name) continue
    let body = parts[i + 1] || ''
    body = body.replace(/^\s*```[\w.+-]*\r?\n/, '')
    // v82ns : LLMs sometimes emit a corrupted closing fence ("`---"
    // single backtick + dashes) instead of the proper "```" triple
    // backtick. Accept any of: \n```, \n`---, \n``---, \n---``` so the
    // body never includes a stray fence remnant at the end.
    const closingMatch = body.match(/\n[`'"]{1,3}-{0,4}\s*$|\n-{2,}[`'"]{0,3}\s*$|\n```/)
    if (closingMatch && closingMatch.index !== undefined) {
      body = body.slice(0, closingMatch.index)
    }
    const ext = name.split('.').pop()?.toLowerCase() || 'txt'
    const lang =
      ext === 'html' || ext === 'htm' ? 'html'
      : ext === 'css' || ext === 'scss' ? 'css'
      : ext === 'js' || ext === 'mjs' ? 'javascript'
      : ext === 'ts' || ext === 'tsx' ? 'typescript'
      : ext
    files.push({ name, language: lang, content: body.trimStart() })
  }
  return files
}

// ---------------------------------------------------------------------------
// Console preview — for CLI/backend projects
// ---------------------------------------------------------------------------

function ConsolePreview({ output, expanded }: { output: string; expanded: boolean }) {
  return (
    <div className={`bg-[#0d1117] font-mono ${expanded ? 'h-[calc(100%-3rem)]' : 'h-[22rem]'} overflow-auto`}>
      <div className="flex items-center gap-2 border-b border-white/10 px-4 py-2">
        <Terminal size={12} className="text-green-400" />
        <span className="text-[11px] text-green-400">Console output</span>
      </div>
      <pre className="px-4 py-3 text-[12px] leading-5 text-gray-300 whitespace-pre-wrap">
        {output || 'En attente de la sortie console...'}
      </pre>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Dev server preview — iframe pointing to localhost
// ---------------------------------------------------------------------------

function DevServerPreview({
  serverState,
  expanded,
  viewportMode,
}: {
  serverState: DevServerState
  expanded: boolean
  viewportMode: ViewportMode
}) {
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const [refreshKey, setRefreshKey] = useState(0)
  const viewport = VIEWPORT_SIZES[viewportMode]

  if (!serverState.running || !serverState.url) {
    return (
      <div className={`grid place-items-center bg-[#0d1117] ${expanded ? 'h-[calc(100%-3rem)]' : 'h-[22rem]'}`}>
        <div className="text-center space-y-3">
          <Globe size={28} className="mx-auto text-aurora-text-dim animate-pulse" />
          <p className="text-sm text-aurora-text-dim">
            {serverState.process === 'starting'
              ? 'Demarrage du serveur de dev...'
              : serverState.error
                ? `Erreur: ${serverState.error}`
                : 'Serveur de dev non demarre'}
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className={`bg-white ${expanded ? 'h-[calc(100%-3rem)]' : 'h-[22rem]'} flex justify-center`}>
      <iframe
        ref={iframeRef}
        key={refreshKey}
        title="Dev server preview"
        src={serverState.url}
        sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
        className="h-full border-0 transition-[width] duration-300"
        style={{ width: viewport.width, maxWidth: '100%' }}
        onLoad={() => {
          // Force refresh on navigation
          setRefreshKey((k) => k)
        }}
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function CodeProjectPreview({
  files,
  devServerState,
  consoleOutput,
  previewType,
}: {
  files: CodeFile[]
  devServerState?: DevServerState
  consoleOutput?: string
  previewType?: 'dev_server' | 'iframe_static' | 'iframe_bundled' | 'console' | 'none'
}) {
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const [previewVisible, setPreviewVisible] = useState(true)
  const [expanded, setExpanded] = useState(false)
  const [viewportMode, setViewportMode] = useState<ViewportMode>('desktop')
  const [refreshKey, setRefreshKey] = useState(0)

  // Debounce `files` so heavy setFiles cascades during generation do not
  // trigger a buildPreviewHtml recompute every token. 600ms is imperceptible
  // to the user but cuts regex + blob cost by ~40×.
  const [debouncedFiles, setDebouncedFiles] = useState(files)
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedFiles(files), 600)
    return () => clearTimeout(timer)
  }, [files])

  const totalBytes = useMemo(
    () => debouncedFiles.reduce((sum, f) => sum + f.content.length, 0),
    [debouncedFiles],
  )
  const heavy = useMemo(() => isHeavyWebGLProject(debouncedFiles), [debouncedFiles])
  // Skip the inlined static preview for heavy projects — they'll use the dev
  // server iframe instead once it starts. Prevents the GPU/render thrash.
  const skipStatic = totalBytes > SIDE_PREVIEW_TOTAL_CAP || heavy

  const canStaticPreview = useMemo(() => !skipStatic && isWebProject(debouncedFiles), [debouncedFiles, skipStatic])
  const previewHtml = useMemo(() => canStaticPreview ? buildPreviewHtml(debouncedFiles) : null, [debouncedFiles, canStaticPreview])

  const activePreviewMode = useMemo(() => {
    if (previewType === 'dev_server' && devServerState?.running) return 'dev_server'
    if (previewType === 'console' && consoleOutput) return 'console'
    if (canStaticPreview) return 'iframe_static'
    if (consoleOutput) return 'console'
    return 'none'
  }, [previewType, devServerState, consoleOutput, canStaticPreview])

  useEffect(() => {
    if (!iframeRef.current || !previewHtml || activePreviewMode !== 'iframe_static') return
    const blob = new Blob([previewHtml], { type: 'text/html' })
    const url = URL.createObjectURL(blob)
    iframeRef.current.src = url
    return () => URL.revokeObjectURL(url)
  }, [previewHtml, refreshKey, activePreviewMode])

  if (activePreviewMode === 'none') return null

  const modeLabel = activePreviewMode === 'dev_server'
    ? 'Dev server'
    : activePreviewMode === 'console'
      ? 'Console'
      : 'Preview statique'

  return (
    <div className={`rounded-[1.6rem] border border-aurora-border/35 bg-aurora-surface/65 overflow-hidden ${expanded ? 'fixed inset-4 z-50' : ''}`}>
      {/* Header */}
      <div className="flex items-center justify-between border-b border-aurora-border/25 px-4 py-2.5">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.2em] text-aurora-text-dim">
          {activePreviewMode === 'dev_server' ? <Globe size={13} /> : activePreviewMode === 'console' ? <Terminal size={13} /> : <Eye size={13} />}
          <span>{modeLabel}</span>
          {activePreviewMode === 'dev_server' && devServerState?.url && (
            <span className="ml-1 text-aurora-accent-light">{devServerState.url}</span>
          )}
        </div>

        <div className="flex items-center gap-1.5">
          {activePreviewMode !== 'console' && (
            <>
              {(['desktop', 'tablet', 'mobile'] as const).map((mode) => {
                const Icon = mode === 'desktop' ? Monitor : mode === 'tablet' ? Tablet : Smartphone
                return (
                  <button
                    key={mode}
                    onClick={() => setViewportMode(mode)}
                    title={VIEWPORT_SIZES[mode].label}
                    className={`flex h-7 w-7 items-center justify-center rounded-lg transition-colors ${
                      viewportMode === mode
                        ? 'bg-aurora-accent/20 text-aurora-accent-light'
                        : 'text-aurora-text-dim hover:text-aurora-text'
                    }`}
                  >
                    <Icon size={12} />
                  </button>
                )
              })}
              <div className="mx-1 h-4 w-px bg-aurora-border/30" />
            </>
          )}

          {/* Refresh */}
          <button
            onClick={() => setRefreshKey((k) => k + 1)}
            title="Rafraichir"
            className="flex h-7 w-7 items-center justify-center rounded-lg text-aurora-text-dim hover:text-aurora-text transition-colors"
          >
            <RefreshCw size={12} />
          </button>

          {/* External link for dev server */}
          {activePreviewMode === 'dev_server' && devServerState?.url && (
            <a
              href={devServerState.url}
              target="_blank"
              rel="noopener noreferrer"
              title="Ouvrir dans le navigateur"
              className="flex h-7 w-7 items-center justify-center rounded-lg text-aurora-text-dim hover:text-aurora-text transition-colors"
            >
              <ExternalLink size={12} />
            </a>
          )}

          {/* Toggle visibility */}
          <button
            onClick={() => setPreviewVisible((prev) => !prev)}
            className="flex h-7 w-7 items-center justify-center rounded-lg border border-aurora-border/30 bg-aurora-surface-2/60 text-aurora-text-dim hover:text-aurora-text transition-colors"
          >
            {previewVisible ? <EyeOff size={12} /> : <Eye size={12} />}
          </button>

          {/* Expand */}
          <button
            onClick={() => setExpanded((prev) => !prev)}
            className="flex h-7 w-7 items-center justify-center rounded-lg border border-aurora-border/30 bg-aurora-surface-2/60 text-aurora-text-dim hover:text-aurora-text transition-colors"
          >
            {expanded ? <Minimize2 size={12} /> : <Maximize2 size={12} />}
          </button>
        </div>
      </div>

      {/* Content */}
      {previewVisible && (
        <>
          {activePreviewMode === 'dev_server' && devServerState && (
            <DevServerPreview
              serverState={devServerState}
              expanded={expanded}
              viewportMode={viewportMode}
            />
          )}

          {activePreviewMode === 'console' && (
            <ConsolePreview output={consoleOutput || ''} expanded={expanded} />
          )}

          {activePreviewMode === 'iframe_static' && previewHtml && (
            <div className={`bg-white ${expanded ? 'h-[calc(100%-3rem)]' : 'h-[22rem]'} flex justify-center`}>
              <iframe
                ref={iframeRef}
                key={refreshKey}
                title="Apercu du projet"
                sandbox="allow-scripts allow-same-origin"
                className="h-full border-0 transition-[width] duration-300"
                style={{ width: VIEWPORT_SIZES[viewportMode].width, maxWidth: '100%' }}
              />
            </div>
          )}
        </>
      )}
    </div>
  )
}
