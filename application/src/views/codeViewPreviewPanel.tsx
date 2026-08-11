import { useEffect, useMemo, useRef, useState, type RefObject } from 'react'
import { ExternalLink, Maximize2, Minimize2, Monitor, Smartphone, Tablet } from 'lucide-react'
import { parsePartialStreamFiles, buildLivePreviewHtml, webProjectFromFiles } from '../components/CodeProjectPreview'
import { LIVE_PREVIEW_TOTAL_CAP_BYTES, shouldPauseLivePreviewDuringGeneration } from '../services/codeLivePreviewPolicy'
import { intelligentlyElevateFiles } from '../services/codeOutputIntelligent'
import type { CodeFile } from '../services/codeOrchestrator'
import { isHeavyWebGLProject } from './codeViewPreviewHeuristics'
import { CodeFullscreenViewer } from './codeViewFullscreenViewer'
import { PreviewStage, type BigViewport } from './codeViewPreviewStage'

// ---------------------------------------------------------------------------
// Big live preview frame — dedicated to the large right panel. Watches the
// live stream from the orchestrator and refreshes the iframe as HTML/CSS/JS
// arrive, so the page visually evolves from blank → styled → interactive.
//
// Deux modes, UNE seule scene (`PreviewStage`) et UN seul iframe:
//  - compact: barre d'outils + scene, exactement comme avant.
//  - plein ecran: `CodeFullscreenViewer` ajoute l'arborescence du projet a
//    gauche, redimensionnable et repliable.
// ---------------------------------------------------------------------------

export type { BigViewport } from './codeViewPreviewStage'

// Total bytes cap: beyond this, the preview recompute on every token is too
// expensive (split + regex + blob + iframe reload). We freeze the preview
// until generation finishes.
const LIVE_PREVIEW_TOTAL_CAP = LIVE_PREVIEW_TOTAL_CAP_BYTES

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
  const shouldSkipLivePreview = shouldPauseLivePreviewDuringGeneration({
    isGenerating,
    totalBytes,
    isHeavy,
    byteCap: LIVE_PREVIEW_TOTAL_CAP,
  })

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

  // Plein ecran: le simulateur compact est illisible (le cadre 1440x900 scale a
  // ~0.35 dans le panneau etroit). Le mode plein ecran donne tout le viewport au
  // rendu ET pose l'arborescence du projet a cote -> l'utilisateur voit VRAIMENT
  // la page a une taille utilisable et peut naviguer dans les fichiers livres.
  const [isFullscreen, setIsFullscreen] = useState(false)
  const lastPayloadRef = useRef<string>('')

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
    lastPayloadRef.current = payload
    // `isFullscreen` EST une dependance reelle: basculer de mode remonte l iframe
    // (elle change de parent dans l arbre React). Sans ce re-declenchement, la
    // nouvelle iframe resterait BLANCHE — le srcdoc est pose imperativement.
  }, [html, isGenerating, iframeRef, shouldSkipLivePreview, isFullscreen])

  const openInNewTab = () => {
    const payload = lastPayloadRef.current
    if (!payload) return
    const win = window.open('', '_blank')
    if (win) { win.document.open(); win.document.write(payload); win.document.close() }
  }

  const toolbar = (
    <div className="flex items-center justify-between gap-1 border-b border-black/5 bg-[#0a0f14] px-2 py-1.5">
      <div className="flex items-center gap-1">
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
      <div className="flex items-center gap-1">
        <button
          onClick={openInNewTab}
          title="Ouvrir le rendu dans un nouvel onglet (taille reelle)"
          className="flex h-6 items-center gap-1 rounded-md px-2 text-[10px] text-aurora-text-dim transition-colors hover:bg-white/5 hover:text-aurora-text"
        >
          <ExternalLink size={11} />
          <span>Onglet</span>
        </button>
        <button
          onClick={() => setIsFullscreen((v) => !v)}
          title={isFullscreen ? 'Quitter le plein ecran (Echap)' : 'Agrandir le viewer en plein ecran (arborescence + rendu)'}
          className={`flex h-6 items-center gap-1 rounded-md px-2 text-[10px] transition-colors ${
            isFullscreen
              ? 'bg-aurora-accent/20 text-aurora-accent-light'
              : 'text-aurora-text-dim hover:bg-white/5 hover:text-aurora-text'
          }`}
        >
          {isFullscreen ? <Minimize2 size={11} /> : <Maximize2 size={11} />}
          <span>{isFullscreen ? 'Reduire' : 'Agrandir'}</span>
        </button>
      </div>
    </div>
  )

  const stage = <PreviewStage viewport={viewport} iframeRef={iframeRef} />

  if (isFullscreen) {
    return (
      <CodeFullscreenViewer
        files={effectiveFiles}
        toolbar={toolbar}
        stage={stage}
        onExit={() => setIsFullscreen(false)}
      />
    )
  }

  return (
    <div className="flex flex-col h-full min-h-[36rem] bg-[#0d1117]">
      {toolbar}
      {stage}
    </div>
  )
}
