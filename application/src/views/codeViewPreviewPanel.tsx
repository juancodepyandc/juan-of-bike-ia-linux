import { useEffect, useMemo, useRef, useState, type RefObject } from 'react'
import { Monitor, Smartphone, Tablet } from 'lucide-react'
import { parsePartialStreamFiles, buildLivePreviewHtml, webProjectFromFiles } from '../components/CodeProjectPreview'
import { intelligentlyElevateFiles } from '../services/codeOutputIntelligent'
import type { CodeFile } from '../services/codeOrchestrator'
import { isHeavyWebGLProject } from './codeViewPreviewHeuristics'

// ---------------------------------------------------------------------------
// Big live preview frame — dedicated to the large right panel. Watches the
// live stream from the orchestrator and refreshes the iframe as HTML/CSS/JS
// arrive, so the page visually evolves from blank → styled → interactive.
// ---------------------------------------------------------------------------

export type BigViewport = 'desktop' | 'tablet' | 'mobile'

// Physical device proportions used to size the chrome realistically.
// Width × height are the OUTER frame size. Padding carves the inner "screen" area.
const BIG_VIEWPORT_SPEC: Record<BigViewport, {
  width: number   // outer frame width in px
  height: number  // outer frame height in px
  pad: number     // frame bezel thickness
  radius: number  // outer corner radius
  notch: boolean
  chrome: 'none' | 'browser'
}> = {
  desktop: { width: 1440, height: 900, pad: 0,  radius: 14, notch: false, chrome: 'browser' },
  tablet:  { width: 760,  height: 1024, pad: 20, radius: 36, notch: false, chrome: 'none' },
  mobile:  { width: 360,  height: 720,  pad: 12, radius: 40, notch: true,  chrome: 'none' },
}

// Total bytes cap: beyond this, the preview recompute on every token is too
// expensive (split + regex + blob + iframe reload). We freeze the preview
// until generation finishes.
const LIVE_PREVIEW_TOTAL_CAP = 150_000

export function BigLivePreviewFrame({
  files,
  streamContent,
  isGenerating,
  iframeRef,
  viewport,
  onViewportChange,
}: {
  files: CodeFile[]
  streamContent: string
  isGenerating: boolean
  iframeRef: RefObject<HTMLIFrameElement | null>
  viewport: BigViewport
  onViewportChange: (mode: BigViewport) => void
}) {
  // Debounce the stream content so we don't re-parse + re-build HTML on every
  // single token. 600ms gives a smooth "building" sensation while dividing the
  // CPU cost by ~40× during active streaming.
  const [debouncedStream, setDebouncedStream] = useState(streamContent)
  useEffect(() => {
    if (!isGenerating) {
      setDebouncedStream(streamContent)
      return
    }
    const timer = setTimeout(() => setDebouncedStream(streamContent), 600)
    return () => clearTimeout(timer)
  }, [streamContent, isGenerating])

  const streamFiles = useMemo(
    () => (debouncedStream ? parsePartialStreamFiles(debouncedStream) : []),
    [debouncedStream],
  )
  const rawEffectiveFiles = files.length > 0 ? files : streamFiles
  // v82nu : safety net — intelligentlyElevateFiles fixes broken <img>
  // (PLACEHOLDER_SUBJECT_IMG markers that survived hydration), wires
  // buttons, and patches CSS bg-images. Same hook as AuroraV1CodeView.
  // Only runs once streaming is finished to avoid burning CPU per token.
  const effectiveFiles = useMemo(() => {
    if (isGenerating || rawEffectiveFiles.length === 0) return rawEffectiveFiles
    try {
      const adapted = rawEffectiveFiles.map((f) => ({
        path: f.name,
        content: f.content,
        language: f.language,
      }))
      const { files: out } = intelligentlyElevateFiles(adapted, '', '')
      return out.map((f) => ({
        name: f.path,
        content: f.content,
        language: f.language,
      })) as CodeFile[]
    } catch {
      return rawEffectiveFiles
    }
  }, [rawEffectiveFiles, isGenerating])

  // Total byte budget: if the project is too big or WebGL-heavy, we freeze
  // the live preview during generation and only render the finished files.
  const totalBytes = useMemo(
    () => effectiveFiles.reduce((sum, f) => sum + f.content.length, 0),
    [effectiveFiles],
  )
  const isHeavy = useMemo(() => isHeavyWebGLProject(effectiveFiles), [effectiveFiles])
  // v77n FIX UI FREEZE: pendant TOUTE generation, skip la live preview iframe.
  // Avant: la preview iframe se reconstruisait toutes les 600ms (debouncedStream
  // change), avec parsePartialStreamFiles + buildLivePreviewHtml + iframe srcdoc
  // de 50K+ chars. Sur un projet brand_landing avec shader/particles, ces
  // operations bloquaient le main thread JS pendant >5s, ce qui declenchait le
  // dialog Chrome 'Page ne repond pas — Attendre / Quitter'. L user n a aucun
  // feedback que ca avance.
  // Apres: la preview est PAUSEE pendant toute la generation. L user voit le
  // code en direct via l onglet Code (qui reste leger — un <pre> avec stream
  // text capped a 10K). La preview iframe arrive d un coup a la fin, ce qui
  // est plus snappy et plus surement memory-safe. Les anciens checks heavy/
  // total_cap sont conserves comme fallback pour les rares cas ou l user a
  // active manuellement le mode temps-reel (futur toggle).
  const shouldSkipLivePreview = isGenerating

  const canRender = !shouldSkipLivePreview && webProjectFromFiles(effectiveFiles)
  const html = useMemo(
    () => (canRender ? buildLivePreviewHtml(effectiveFiles) : null),
    [effectiveFiles, canRender],
  )

  // Keep the last rendered HTML alive: once we have produced something,
  // we never go back to the "building..." placeholder just because the stream
  // is momentarily empty (regeneration, rescue pass, etc.).
  const lastGoodHtmlRef = useRef<string | null>(null)
  if (html) lastGoodHtmlRef.current = html

  useEffect(() => {
    if (!iframeRef.current) return
    const fallbackIdle = '<!DOCTYPE html><html><body style="margin:0;background:#0d1117;color:#8b949e;font-family:system-ui;display:grid;place-items:center;height:100vh"><div>Lance une generation pour voir la page se construire ici.</div></body></html>'
    const fallbackBuilding = '<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8"><style>body{margin:0;background:#0d1117;color:#8b949e;font-family:system-ui,sans-serif;display:grid;place-items:center;height:100vh}div{text-align:center;max-width:32rem;padding:2rem}h2{color:#e6edf3;margin:0 0 .5rem;font-weight:600;font-size:15px}p{margin:.35rem 0;font-size:12px;line-height:1.5}span.dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:#7cf0a5;margin-right:.4rem;animation:p 1s infinite}@keyframes p{0%,100%{opacity:1}50%{opacity:.3}}</style></head><body><div><h2><span class="dot"></span>La page se construit...</h2><p>Le rendu apparaitra au fur et a mesure que le modele ecrit index.html, style.css et script.js.</p><p>Bascule sur l onglet <b>Code</b> pour voir le texte brut en direct.</p></div></body></html>'
    const fallbackHeavy = '<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8"><style>body{margin:0;background:#0d1117;color:#c9d1d9;font-family:system-ui,sans-serif;display:grid;place-items:center;height:100vh}div{text-align:center;max-width:32rem;padding:2rem}h2{color:#facc15;margin:0 0 .6rem;font-weight:600;font-size:15px}p{margin:.3rem 0;font-size:12px;line-height:1.5}</style></head><body><div><h2>Preview differee (projet lourd detecte)</h2><p>Ce projet utilise Three.js/WebGL ou depasse 150 KB cumules.</p><p>Le rendu live serait recalcule a chaque token et saturerait le GPU.</p><p>La preview s activera automatiquement des la fin de la generation.</p></div></body></html>'

    // Preference order:
    //  1. Fresh HTML just parsed from current files/stream.
    //  2. Last good HTML we ever managed to render (never regress to the placeholder).
    //  3. "heavy project" notice when live preview is paused.
    //  4. "building..." during generation.
    //  5. Idle message when no generation has been started.
    const payload = html
      ?? lastGoodHtmlRef.current
      ?? (shouldSkipLivePreview ? fallbackHeavy : isGenerating ? fallbackBuilding : fallbackIdle)

    // v77m fix bug critique OOM: switch de Blob URL -> srcdoc.
    // Avant: chaque update du payload creait une Blob + URL.createObjectURL,
    // revoquees uniquement dans le cleanup useEffect. Pendant un stream actif,
    // l effet se redeclenche au moins toutes les 600ms (debouncedStream change),
    // donc des dizaines de Blob URLs s accumulent avant que GC les libere.
    // Sur les projets Three.js/WebGL avec shader + textures, c est ce qui
    // saturait Chrome (OOM "Aïe aïe aïe" dans le tab tunnel).
    // srcdoc evite completement la creation de Blob — le HTML est inline dans
    // l attribut iframe, pas de URL a revoquer.
    iframeRef.current.srcdoc = payload
    iframeRef.current.removeAttribute('src')
  }, [html, isGenerating, iframeRef, shouldSkipLivePreview])

  const spec = BIG_VIEWPORT_SPEC[viewport]

  // Ensures every viewport (including desktop at 1440×900) auto-scales to fit
  // the visible area. The iframe still sees the real `spec.width × spec.height`
  // resolution so media queries trigger correctly.
  const frameWrapRef = useRef<HTMLDivElement>(null)
  const [frameScale, setFrameScale] = useState(1)

  useEffect(() => {
    const wrap = frameWrapRef.current
    if (!wrap) return
    const compute = () => {
      const availW = wrap.clientWidth - 32
      const availH = wrap.clientHeight - 32
      if (availW <= 0 || availH <= 0) return
      const s = Math.min(availW / spec.width, availH / spec.height, 1)
      setFrameScale(s < 0.2 ? 0.2 : s)
    }
    compute()
    const ro = new ResizeObserver(compute)
    ro.observe(wrap)
    window.addEventListener('resize', compute)
    return () => { ro.disconnect(); window.removeEventListener('resize', compute) }
  }, [viewport, spec.width, spec.height])

  return (
    <div className="flex flex-col h-full min-h-[32rem] bg-[#0d1117]">
      <div className="flex items-center justify-center gap-1 border-b border-black/5 bg-[#0a0f14] px-2 py-1.5">
        {(['desktop', 'tablet', 'mobile'] as const).map((mode) => {
          const Icon = mode === 'desktop' ? Monitor : mode === 'tablet' ? Tablet : Smartphone
          const label = mode === 'desktop' ? 'Desktop' : mode === 'tablet' ? 'Tablet' : 'Mobile'
          return (
            <button
              key={mode}
              onClick={() => onViewportChange(mode)}
              title={label}
              className={`flex h-6 items-center gap-1 rounded-md px-2 text-[10px] transition-colors ${
                viewport === mode
                  ? 'bg-aurora-accent/20 text-aurora-accent-light'
                  : 'text-aurora-text-dim hover:text-aurora-text'
              }`}
            >
              <Icon size={11} />
              <span>{label}</span>
            </button>
          )
        })}
      </div>
      <div
        ref={frameWrapRef}
        className="flex-1 flex items-center justify-center overflow-hidden min-h-[32rem]"
        style={{ background: 'var(--v4code-stage-bg, radial-gradient(circle at center, #1a1d22, #07080a))' }}
      >
        <div
          className="relative shrink-0 transition-[transform] duration-200 ease-out"
          style={{
            width: `${spec.width}px`,
            height: `${spec.height}px`,
            padding: `${spec.pad}px`,
            borderRadius: `${spec.radius}px`,
            background: spec.chrome === 'browser'
              ? 'linear-gradient(180deg,#2c2e33 0 44px,#fafafa 44px)'
              : 'linear-gradient(135deg,#1a1c22,#0a0b0e)',
            boxShadow: '0 30px 80px rgba(0,0,0,.55), inset 0 0 0 2px rgba(255,255,255,.05)',
            transform: `scale(${frameScale})`,
            transformOrigin: 'center center',
          }}
        >
          {spec.chrome === 'browser' && <BrowserChromeBar />}
          {spec.notch && (
            <div
              className="absolute left-1/2 -translate-x-1/2 z-10"
              style={{
                top: `${Math.round(spec.pad * 0.85)}px`,
                width: '110px',
                height: '26px',
                borderRadius: '18px',
                background: '#000',
                pointerEvents: 'none',
              }}
            />
          )}
          <iframe
            ref={iframeRef}
            title="Rendu live de la page"
            sandbox="allow-scripts allow-same-origin"
            className="block w-full h-full bg-white border-0"
            style={{
              borderRadius: spec.chrome === 'browser'
                ? '0 0 8px 8px'
                : `${Math.max(0, spec.radius - spec.pad * 0.5)}px`,
              marginTop: spec.chrome === 'browser' ? '44px' : 0,
              height: spec.chrome === 'browser' ? `calc(100% - 44px)` : '100%',
            }}
          />
        </div>
      </div>
    </div>
  )
}

function BrowserChromeBar() {
  return (
    <div
      className="absolute top-0 left-0 right-0 flex items-center gap-2 px-3"
      style={{
        height: '44px',
        borderRadius: '14px 14px 0 0',
        background: 'linear-gradient(180deg,#34363b,#26282d)',
        borderBottom: '1px solid rgba(0,0,0,.35)',
        pointerEvents: 'none',
      }}
    >
      <span style={{ display: 'inline-block', width: 12, height: 12, borderRadius: '50%', background: '#ff5f56' }} />
      <span style={{ display: 'inline-block', width: 12, height: 12, borderRadius: '50%', background: '#ffbd2e' }} />
      <span style={{ display: 'inline-block', width: 12, height: 12, borderRadius: '50%', background: '#27c93f' }} />
      <div
        className="ml-3 flex-1 flex items-center"
        style={{
          height: '26px',
          background: 'rgba(255,255,255,.08)',
          borderRadius: '999px',
          padding: '0 14px',
          fontSize: '11px',
          color: '#b6b8be',
          fontFamily: 'system-ui, sans-serif',
          letterSpacing: '.02em',
        }}
      >
        <span style={{ opacity: .55, marginRight: 6 }}>●</span>
        aurora-preview.local
      </div>
    </div>
  )
}
