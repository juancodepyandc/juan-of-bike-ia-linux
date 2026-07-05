import { useEffect, useMemo, useRef, useState } from 'react'

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

// Exported so the big viewer can build the same live preview HTML.
export function buildLivePreviewHtml(files: CodeFile[]): string | null {
  return buildPreviewHtml(files)
}

export function webProjectFromFiles(files: CodeFile[]): boolean {
  return isWebProject(files)
}

// ---------------------------------------------------------------------------
// Static web preview — inline CSS/JS into HTML
// ---------------------------------------------------------------------------

function isWebProject(files: CodeFile[]) {
  // A web project is anything we can put in a blob iframe: an HTML file,
  // or at least CSS + JS that we can wrap with a minimal bootstrap document.
  return files.some((f) => /\.(html|htm)$/i.test(f.name))
      || files.some((f) => /\.(css|scss|less|js|mjs|ts|tsx|jsx)$/i.test(f.name) && f.content.trim().length > 0)
}

function escapeRegex(str: string) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function stripFileBasename(name: string): string {
  const withoutDir = name.replace(/\\/g, '/').split('/').pop() || name
  return withoutDir
}

/**
 * Replace any <img src="./assets/..."> (or other unresolved relative paths)
 * with a REAL image URL: `source.unsplash.com/…?query=<alt text>` so the
 * preview shows actual relevant photos instead of colored placeholders.
 * A gradient SVG stays as the ultimate fallback inside <img onerror="...">.
 */
/**
 * v82ns : when a small/distilled LLM hallucinates, it often loops on a
 * single SVG primitive (the captured Tag Heuer page had `<rect x="180"
 * y="180" width="40" height="40">` repeated 50+ times in a row). The
 * spam pollutes the rendered preview AND wastes generation budget. We
 * collapse runs of ≥3 identical adjacent SVG primitives down to one,
 * stripping the noise without changing the visual intent.
 */
function collapseRepeatedSvgElements(html: string): string {
  // Targets: <rect …/>, <circle …/>, <line …/>, <path …/>, <ellipse …/>
  // Only when 3+ adjacent identical elements appear (LLM hallucination).
  return html.replace(
    /(<(rect|circle|line|path|ellipse|polygon)\b[^>]*\/?>)((?:\s*\1){2,})/g,
    (_m, single) => single,
  )
}

function patchUnresolvedImageSrcs(html: string): string {
  return html.replace(
    /<img([^>]*?)src=(["'])([^"']+)\2([^>]*)>/gi,
    (match, prefix, q, src, suffix) => {
      if (/^data:/i.test(src)) return match
      if (/^https?:\/\//i.test(src)) return match

      // Build a query from the alt attribute (the LLM usually describes the image there).
      const altMatch = match.match(/alt=(["'])([^"']*)\1/i)
      const altRaw = (altMatch?.[2] || '').trim()
      // If no alt, extract meaningful words from the path itself (e.g. hero-coca.jpg → "hero coca").
      const pathQuery = src.replace(/^[./]*/, '').replace(/\.[^.]+$/, '').replace(/[\-_/]+/g, ' ').trim()
      const query = (altRaw || pathQuery || 'hero').slice(0, 80)
      const encoded = encodeURIComponent(query)

      // Gradient fallback (only shown if Unsplash 404s / blocks CORS).
      const seed = Math.abs(query.split('').reduce((a: number, c: string) => a + c.charCodeAt(0) * 31, 0)) % 360
      const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 600"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="hsl(${seed}, 70%, 55%)"/><stop offset="1" stop-color="hsl(${(seed + 60) % 360}, 70%, 35%)"/></linearGradient></defs><rect width="800" height="600" fill="url(%23g)"/></svg>`
      const fallbackData = `data:image/svg+xml;utf8,${svg.replace(/#/g, '%23').replace(/"/g, '&quot;')}`

      // Real image first, gradient via onerror fallback. Unsplash Source is unauth, CORS-friendly for <img>.
      const realUrl = `https://source.unsplash.com/1600x900/?${encoded}`
      const altAttr = altRaw ? '' : ` alt="${query.replace(/"/g, '&quot;')}"`
      const onerror = ` onerror="this.onerror=null;this.src='${fallbackData}';"`
      return `<img${prefix}src=${q}${realUrl}${q}${suffix}${altAttr}${onerror}>`
    },
  )
}

function ensureHtmlScaffold(body: string): string {
  if (/<html[\s>]/i.test(body)) return body
  // The LLM gave us HTML fragments — wrap them so the iframe has <head>/<body>.
  return `<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Apercu</title></head><body>${body}</body></html>`
}

function buildPreviewHtml(files: CodeFile[]): string | null {
  const htmlFile = files.find((file) => /\.(html|htm)$/i.test(file.name))

  // Fallback scaffold when no HTML is present but CSS/JS exists — useful for the
  // early live preview moments where the LLM is still writing index.html.
  let html: string
  if (htmlFile) {
    html = htmlFile.content.trim()
    if (!html) return null
    html = ensureHtmlScaffold(html)
  } else {
    const hasCss = files.some((f) => /\.(css|scss|less)$/i.test(f.name))
    const hasJs = files.some((f) => /\.(js|mjs)$/i.test(f.name))
    if (!hasCss && !hasJs) return null
    html = '<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8"><title>Apercu</title></head><body><main id="root" style="padding:2rem;font-family:system-ui"></main></body></html>'
  }

  // --- Inject CSS, matching by basename so `style.css`, `./style.css`
  //     and `assets/css/style.css` all get resolved.
  for (const file of files) {
    if (!/\.(css|scss|less)$/i.test(file.name)) continue
    const base = escapeRegex(stripFileBasename(file.name))
    const linkPattern = new RegExp(`<link[^>]*href=["'][^"']*${base}["'][^>]*>`, 'gi')
    const styleBlock = `<style data-file="${file.name}">\n${file.content}\n</style>`
    if (linkPattern.test(html)) {
      html = html.replace(linkPattern, styleBlock)
    } else if (/<\/head>/i.test(html)) {
      html = html.replace(/<\/head>/i, `${styleBlock}\n</head>`)
    } else if (/<head[^>]*>/i.test(html)) {
      html = html.replace(/<head[^>]*>/i, (m) => `${m}\n${styleBlock}`)
    } else {
      html = styleBlock + html
    }
  }

  // --- Inject JS (same basename matching). Detect ES modules.
  for (const file of files) {
    if (!/\.(js|mjs)$/i.test(file.name)) continue
    const base = escapeRegex(stripFileBasename(file.name))
    const scriptPattern = new RegExp(`(<script[^>]*src=["'][^"']*${base}["'][^>]*>)\\s*</script>`, 'gi')
    const isModule = /^\s*import\s/m.test(file.content) || /export\s+(default|\{|const|function|class)/m.test(file.content)
    const scriptBlock = `<script${isModule ? ' type="module"' : ''} data-file="${file.name}">\n${file.content}\n</script>`
    if (scriptPattern.test(html)) {
      html = html.replace(scriptPattern, scriptBlock)
    } else if (/<\/body>/i.test(html)) {
      html = html.replace(/<\/body>/i, `${scriptBlock}\n</body>`)
    } else {
      html = html + scriptBlock
    }
  }

  // --- Swap broken relative <img src="..."> for pretty gradient SVGs so the
  //     iframe never displays a broken-image icon during the preview lifecycle.
  html = patchUnresolvedImageSrcs(html)

  // --- v82ns : collapse pathological SVG element repetition (LLM looped
  //     on a single primitive — captured Tag Heuer page had 50+ identical
  //     <rect>). Done last so the cleanup runs after CSS/JS injection.
  html = collapseRepeatedSvgElements(html)

  // --- Minimal body fallback so the page is never 100% empty. If the <body>
  //     is literally empty (LLM still writing, or HTML scaffold only), show a
  //     readable skeleton rather than a pure white page.
  if (/<body[^>]*>\s*<\/body>/i.test(html)) {
    html = html.replace(
      /<body([^>]*)>\s*<\/body>/i,
      (_m, attrs) => `<body${attrs}>\n<div style="min-height:100vh;display:grid;place-items:center;background:#0d1117;color:#c9d1d9;font-family:system-ui"><div style="text-align:center"><div style="font-size:14px;opacity:.85">Le modele ecrit la page...</div><div style="margin-top:.4rem;font-size:11px;opacity:.55">Les styles et le contenu vont apparaitre ici progressivement.</div></div></div>\n</body>`,
    )
  }

  return html
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
