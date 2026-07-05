import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import VoicePushToTalk from '../components/VoicePushToTalk'
import { AnimatePresence, motion } from 'framer-motion'
import { Brush, Download, Eraser, Eye, Loader2, Palette, RotateCcw, Sparkles, StopCircle } from 'lucide-react'
import {
  comfyuiGetHistory,
  comfyuiGetImage,
  comfyuiQueuePrompt,
  ensureComfyUIRunning,
} from '../hooks/useTauri'
import { createFluxWorkflow } from '../utils/fluxWorkflow'
import { useModuleDraftsStore } from '../stores/moduleDraftsStore'
import { saveBlob, loadBlobUrl } from '../utils/blobStore'

type Character = 'natsu' | 'lucy'
const PORTRAITS: Record<Character, string> = {
  natsu: '/fairy/natsu.png',
  lucy:  '/fairy/lucy.png',
}

type BrushMode = 'ink' | 'eraser'

type DryingSheet = {
  id: string
  sketchUrl: string
  renderUrl: string | null
  prompt: string
  ts: number
}

function readCharacter(): Character {
  try { return window.localStorage.getItem('ft-who') === 'lucy' ? 'lucy' : 'natsu' }
  catch { return 'natsu' }
}

async function waitForComfyOutput(promptId: string, signal: AbortSignal): Promise<string[]> {
  const maxMs = 4 * 60 * 1000
  const startedAt = Date.now()
  while (Date.now() - startedAt < maxMs) {
    if (signal.aborted) throw new DOMException('Aborted', 'AbortError')
    try {
      const hist = await comfyuiGetHistory(promptId)
      if (hist && typeof hist === 'object') {
        const payload = Object.values(hist)[0] as any
        const outputs = payload?.outputs
        if (outputs) {
          const filenames: string[] = []
          for (const node of Object.values(outputs) as any[]) {
            if (node?.images && Array.isArray(node.images)) {
              for (const img of node.images) {
                if (img?.filename) filenames.push(img.filename as string)
              }
            }
          }
          if (filenames.length > 0) return filenames
        }
      }
    } catch { /* keep polling */ }
    await new Promise((r) => setTimeout(r, 1400))
  }
  throw new Error("ComfyUI: timeout (4 min)")
}

export default function MangaDrawingView() {
  const [who, setWho] = useState<Character>(readCharacter)
  useEffect(() => {
    const t = window.setInterval(() => setWho(readCharacter()), 800)
    return () => window.clearInterval(t)
  }, [])

  const canvasRef = useRef<HTMLCanvasElement>(null)
  const drawingRef = useRef<boolean>(false)
  const lastPointRef = useRef<{ x: number; y: number } | null>(null)
  const drawDraft = useModuleDraftsStore((s) => s.drafts.drawing)
  const setDrawDraft = useModuleDraftsStore((s) => s.setDraft)
  const [brush, setBrush] = useState<BrushMode>('ink')
  const [symmetry, setSymmetry] = useState<boolean>(() => Boolean(drawDraft?.options?.symmetry))
  const [inkColor, setInkColor] = useState<string>(() => (drawDraft?.options?.inkColor as string) ?? '#1a140d')
  const [brushSize, setBrushSize] = useState<number>(() => (drawDraft?.options?.brushSize as number) ?? 3)
  const PALETTE = ['#1a140d', '#b5241e', '#e4bf49', '#3c7d3a', '#264de4', '#6a1f9a', '#ffffff']
  useEffect(() => {
    setDrawDraft('drawing', { options: { symmetry, inkColor, brushSize } })
  }, [symmetry, inkColor, brushSize, setDrawDraft])
  // Undo / redo stack — we snapshot the canvas to an ImageData right before
  // every new stroke starts, so Ctrl+Z rewinds one stroke at a time.
  const historyRef = useRef<ImageData[]>([])
  const futureRef  = useRef<ImageData[]>([])
  const [historyLen, setHistoryLen] = useState(0)
  const [futureLen, setFutureLen] = useState(0)
  const MAX_HISTORY = 40
  const [prompt, setPrompt] = useState<string>(() => drawDraft?.prompt ?? '')
  useEffect(() => {
    const id = window.setTimeout(() => setDrawDraft('drawing', { prompt }), 200)
    return () => window.clearTimeout(id)
  }, [prompt, setDrawDraft])
  const [rendering, setRendering] = useState(false)
  const [renderUrl, setRenderUrl] = useState<string | null>(null)
  const [progress, setProgress] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [line, setLine] = useState<DryingSheet[]>([])
  const abortRef = useRef<AbortController | null>(null)

  // Initialize canvas with paper background — and rehydrate any sketch saved
  // from a previous session so a refresh never wipes the user's work.
  useEffect(() => {
    const c = canvasRef.current
    if (!c) return
    const ctx = c.getContext('2d')
    if (!ctx) return
    const ratio = window.devicePixelRatio || 1
    c.width = c.clientWidth * ratio
    c.height = c.clientHeight * ratio
    ctx.scale(ratio, ratio)
    ctx.fillStyle = '#faf3de'
    ctx.fillRect(0, 0, c.clientWidth, c.clientHeight)
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'

    // Rehydrate previous sketch (if any) once the canvas is sized
    ;(async () => {
      const url = await loadBlobUrl('drawing-sketch')
      if (!url) return
      const img = new Image()
      img.onload = () => {
        ctx.drawImage(img, 0, 0, c.clientWidth, c.clientHeight)
        URL.revokeObjectURL(url)
      }
      img.src = url
    })()
  }, [])

  // Snapshot the canvas to IDB whenever the user releases a stroke, so the
  // drawing survives a page reload. Debounced so continuous scribbling
  // doesn't hammer IDB — only the final frame of an idle period is saved.
  const saveCanvasTimerRef = useRef<number | null>(null)
  const persistCanvas = useCallback(() => {
    if (saveCanvasTimerRef.current !== null) window.clearTimeout(saveCanvasTimerRef.current)
    saveCanvasTimerRef.current = window.setTimeout(() => {
      const c = canvasRef.current
      if (!c) return
      c.toBlob((blob) => {
        if (!blob) return
        void saveBlob('drawing-sketch', blob, 'drawing')
      }, 'image/png')
    }, 600)
  }, [])

  const getPos = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const c = canvasRef.current
    if (!c) return { x: 0, y: 0 }
    const rect = c.getBoundingClientRect()
    return { x: e.clientX - rect.left, y: e.clientY - rect.top }
  }

  const snapshotForHistory = () => {
    const c = canvasRef.current
    if (!c) return
    const ctx = c.getContext('2d')
    if (!ctx) return
    const snap = ctx.getImageData(0, 0, c.width, c.height)
    historyRef.current.push(snap)
    if (historyRef.current.length > MAX_HISTORY) historyRef.current.shift()
    futureRef.current = []
    setHistoryLen(historyRef.current.length)
    setFutureLen(0)
  }
  const restoreImage = (img: ImageData) => {
    const c = canvasRef.current
    if (!c) return
    const ctx = c.getContext('2d')
    if (!ctx) return
    ctx.putImageData(img, 0, 0)
  }
  const undo = () => {
    const c = canvasRef.current
    if (!c || historyRef.current.length === 0) return
    const ctx = c.getContext('2d')
    if (!ctx) return
    const current = ctx.getImageData(0, 0, c.width, c.height)
    const prev = historyRef.current.pop()!
    futureRef.current.push(current)
    restoreImage(prev)
    setHistoryLen(historyRef.current.length)
    setFutureLen(futureRef.current.length)
  }
  const redo = () => {
    const c = canvasRef.current
    if (!c || futureRef.current.length === 0) return
    const ctx = c.getContext('2d')
    if (!ctx) return
    const current = ctx.getImageData(0, 0, c.width, c.height)
    const next = futureRef.current.pop()!
    historyRef.current.push(current)
    restoreImage(next)
    setHistoryLen(historyRef.current.length)
    setFutureLen(futureRef.current.length)
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // Only intercept when the drawing canvas is in the viewport
      if (!canvasRef.current) return
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'z' && !e.shiftKey) {
        e.preventDefault(); undo()
      } else if ((e.metaKey || e.ctrlKey) && (e.key.toLowerCase() === 'y' || (e.key.toLowerCase() === 'z' && e.shiftKey))) {
        e.preventDefault(); redo()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const onDown = (e: React.PointerEvent<HTMLCanvasElement>) => {
    e.preventDefault()
    snapshotForHistory()   // capture state BEFORE the stroke starts
    drawingRef.current = true
    lastPointRef.current = getPos(e)
    const c = canvasRef.current!
    c.setPointerCapture(e.pointerId)
  }
  const onMove = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!drawingRef.current) return
    const p = getPos(e)
    const last = lastPointRef.current ?? p
    const c = canvasRef.current!
    const ctx = c.getContext('2d')!
    const base = brushSize
    const width = brush === 'ink' ? base * 0.6 + (e.pressure || 0.5) * base * 1.2 : base * 3
    ctx.strokeStyle = brush === 'ink' ? inkColor : '#faf3de'
    ctx.lineWidth = width
    ctx.beginPath()
    ctx.moveTo(last.x, last.y)
    ctx.lineTo(p.x, p.y)
    ctx.stroke()
    // Symmetry mode: mirror the stroke across the vertical center axis
    if (symmetry) {
      const axis = c.clientWidth / 2
      const mirroredLast = { x: 2 * axis - last.x, y: last.y }
      const mirroredP = { x: 2 * axis - p.x, y: p.y }
      ctx.beginPath()
      ctx.moveTo(mirroredLast.x, mirroredLast.y)
      ctx.lineTo(mirroredP.x, mirroredP.y)
      ctx.stroke()
    }
    lastPointRef.current = p
  }
  const onUp = (e: React.PointerEvent<HTMLCanvasElement>) => {
    drawingRef.current = false
    lastPointRef.current = null
    try { canvasRef.current?.releasePointerCapture(e.pointerId) } catch { /* ignore */ }
    persistCanvas()
  }

  const clearCanvas = () => {
    const c = canvasRef.current
    if (!c) return
    const ctx = c.getContext('2d')
    if (!ctx) return
    ctx.fillStyle = '#faf3de'
    ctx.fillRect(0, 0, c.clientWidth, c.clientHeight)
    setRenderUrl(null)
    persistCanvas() // snapshot the now-blank canvas so reload shows a fresh sheet
  }

  const snapshotSketch = async (): Promise<string> => {
    const c = canvasRef.current!
    return new Promise((resolve) => {
      c.toBlob((blob) => {
        if (!blob) return resolve('')
        resolve(URL.createObjectURL(blob))
      }, 'image/png')
    })
  }

  const invoke = useCallback(async () => {
    const text = prompt.trim()
    if (!text || rendering) return
    setError(null)
    setRendering(true)
    setRenderUrl(null)
    setProgress('ComfyUI…')
    abortRef.current = new AbortController()
    const ac = abortRef.current
    try {
      const sketchUrl = await snapshotSketch()

      const up = await ensureComfyUIRunning()
      if (!up.ok) throw new Error(up.error || 'ComfyUI indisponible')

      // Reference grounding via Aurora Connect when extension is online: pull
      // a real reference image of the requested subject so the rendered sumi-e
      // composition stays faithful to it. Best-effort: skipped silently when
      // the extension is absent or the fetch fails.
      let extReference: { filename: string; denoise?: number } | null = null
      try {
        const { searchReferenceImages } = await import('../services/auroraExtensionBridge')
        const refResult = await searchReferenceImages(text, { limit: 1, signal: ac.signal })
        if (refResult.ok && refResult.data.length > 0) {
          const refUrl = refResult.data[0].url
          const refResponse = await fetch(refUrl, { signal: ac.signal })
          if (refResponse.ok) {
            const { comfyuiUploadImage } = await import('../hooks/useTauri')
            const refBlob = await refResponse.blob()
            const file = new File([refBlob], `aurora_extref_${Date.now()}.png`, { type: refBlob.type || 'image/png' })
            const uploaded = await comfyuiUploadImage(file)
            if (uploaded?.name) extReference = { filename: uploaded.name, denoise: 0.62 }
          }
        }
      } catch { /* extension grounding best-effort */ }

      setProgress('Workflow FLUX…')
      const workflow = createFluxWorkflow({
        prompt: `${text}, inspired by inked sketch, sumi-e style, detailed`,
        style: 'manga',
        width: 1024,
        height: 1024,
        steps: 26,
        filenamePrefix: `sumi_${Date.now()}`,
        referenceImage: extReference,
      })

      setProgress('Envoi…')
      const q = await comfyuiQueuePrompt(workflow)
      const parsed = typeof q === 'string' ? JSON.parse(q) : q
      const promptId = parsed?.prompt_id as string | undefined
      if (!promptId) throw new Error('Pas de prompt_id')

      setProgress('Rendu… (30–90s)')
      const [first] = await waitForComfyOutput(promptId, ac.signal)
      setProgress('Récupération…')
      const blob = await comfyuiGetImage(first)
      const url = URL.createObjectURL(blob)
      setRenderUrl(url)
      setProgress('')

      setLine((prev) => [{
        id: `sheet-${Date.now()}`,
        sketchUrl,
        renderUrl: url,
        prompt: text,
        ts: Date.now(),
      }, ...prev].slice(0, 12))
    } catch (err) {
      if ((err as Error)?.name === 'AbortError') setProgress('Annulé')
      else {
        const msg = err instanceof Error ? err.message : String(err)
        setError(msg)
        setProgress('')
      }
    } finally {
      setRendering(false)
    }
  }, [prompt, rendering])

  const stop = () => abortRef.current?.abort()

  const downloadRender = () => {
    if (!renderUrl) return
    const a = document.createElement('a')
    a.href = renderUrl
    a.download = `sumi-${Date.now()}.png`
    document.body.appendChild(a)
    a.click()
    a.remove()
  }

  return (
    <div className="mw-root">
      {/* Washi drying line (past works) */}
      <div className="mw-line">
        <div className="mw-line-rope" />
        {line.length === 0 ? (
          <div className="mw-line-empty">— ligne de séchage vierge —</div>
        ) : (
          line.map((sheet, i) => (
            <motion.div
              key={sheet.id}
              className="mw-sheet"
              initial={{ y: -16, opacity: 0, rotate: 0 }}
              animate={{ y: 0, opacity: 1, rotate: (i % 2 === 0 ? -3 : 2) }}
              style={{ left: `${(i * 170) + 24}px` }}
              title={sheet.prompt}
            >
              <div className="mw-sheet-peg" />
              <div className="mw-sheet-twin">
                {sheet.sketchUrl && <img src={sheet.sketchUrl} alt="sketch" />}
                {sheet.renderUrl && <img src={sheet.renderUrl} alt="rendu" />}
              </div>
              <div className="mw-sheet-caption">{sheet.prompt.slice(0, 40)}</div>
            </motion.div>
          ))
        )}
      </div>

      {/* Twin stage */}
      <div className="mw-stage">
        {/* Left: inkstone + sketch canvas */}
        <div className="mw-side mw-side-ink">
          <div className="mw-side-head">
            <Brush size={15} strokeWidth={2.4} />
            <span>PIERRE À ENCRE</span>
          </div>
          <div className="mw-canvas-wrap">
            <canvas
              ref={canvasRef}
              className={`mw-canvas ${brush}`}
              onPointerDown={onDown}
              onPointerMove={onMove}
              onPointerUp={onUp}
              onPointerCancel={onUp}
            />
            <div className="mw-canvas-corner">SUMI-E · 和</div>
          </div>
          <div className="mw-tools">
            <button type="button" className={`mw-tool ${brush === 'ink' ? 'is-active' : ''}`} onClick={() => setBrush('ink')}>
              <Brush size={13} strokeWidth={2.4} /> Encre
            </button>
            <button type="button" className={`mw-tool ${brush === 'eraser' ? 'is-active' : ''}`} onClick={() => setBrush('eraser')}>
              <Eraser size={13} strokeWidth={2.4} /> Gomme
            </button>
            <button type="button" className="mw-tool" onClick={undo} disabled={historyLen === 0}
              title="Annuler (Ctrl+Z)">
              ↶ Undo{historyLen > 0 ? ` (${historyLen})` : ''}
            </button>
            <button type="button" className="mw-tool" onClick={redo} disabled={futureLen === 0}
              title="Rétablir (Ctrl+Y)">
              ↷ Redo{futureLen > 0 ? ` (${futureLen})` : ''}
            </button>
            <button type="button" className={`mw-tool ${symmetry ? 'is-active' : ''}`}
              onClick={() => setSymmetry((v) => !v)}
              title="Symétrie verticale (chaque trait est miroité)">
              ⇄ Symétrie
            </button>
            <label className="mw-tool mw-tool-slider" title="Taille du pinceau">
              <span>●</span>
              <input type="range" min={1} max={12} step={0.5} value={brushSize}
                onChange={(e) => setBrushSize(Number(e.target.value))} />
              <span className="mw-tool-val">{brushSize.toFixed(1)}</span>
            </label>
            <div className="mw-palette" role="group" aria-label="Couleurs d'encre">
              {PALETTE.map((c) => (
                <button
                  key={c}
                  type="button"
                  className={`mw-color ${inkColor === c ? 'is-active' : ''}`}
                  style={{ background: c }}
                  onClick={() => { setInkColor(c); setBrush('ink') }}
                  title={c}
                  aria-label={`Couleur ${c}`}
                />
              ))}
              <label className="mw-color mw-color-custom" title="Couleur personnalisée">
                <input
                  type="color"
                  value={inkColor}
                  onChange={(e) => { setInkColor(e.target.value); setBrush('ink') }}
                />
                <span>+</span>
              </label>
            </div>
            <button type="button" className="mw-tool" onClick={clearCanvas} title="Nouvelle feuille">
              <RotateCcw size={13} strokeWidth={2.4} /> Feuille
            </button>
          </div>
        </div>

        {/* Magic arrow */}
        <div className={`mw-arrow ${rendering ? 'is-active' : ''}`} aria-hidden="true">
          <svg viewBox="0 0 60 180" preserveAspectRatio="none">
            <path
              d="M 30 10 L 30 140 L 10 140 L 30 170 L 50 140 L 30 140"
              fill="var(--ft-accent)"
              stroke="var(--ft-ink)"
              strokeWidth="3"
              strokeLinejoin="round"
            />
          </svg>
          <span className="mw-arrow-sfx">{rendering ? 'FLUX !' : 'INVOQUE'}</span>
        </div>

        {/* Right: washi result */}
        <div className="mw-side mw-side-render">
          <div className="mw-side-head">
            <Eye size={15} strokeWidth={2.4} />
            <span>WASHI — VISION</span>
          </div>
          <div className="mw-washi">
            <AnimatePresence mode="wait">
              {renderUrl ? (
                <motion.img
                  key="render"
                  src={renderUrl}
                  alt="rendu FLUX"
                  className="mw-washi-img"
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.35 }}
                />
              ) : rendering ? (
                <motion.div
                  key="busy"
                  className="mw-washi-busy"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                >
                  <Loader2 size={36} strokeWidth={2.2} className="mw-spin" />
                  <div className="mw-washi-busy-line">{progress || 'Invocation…'}</div>
                </motion.div>
              ) : (
                <motion.div key="idle" className="mw-washi-idle">
                  <img src={PORTRAITS[who]} alt={who} className="mw-washi-portrait" />
                  <div className="mw-washi-idle-banner">
                    {who === 'natsu' ? 'TRACE, J\'ALLUME APRÈS' : 'TRACE, JE RÉVÈLE'}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
            {renderUrl && (
              <button type="button" className="mw-download" onClick={downloadRender}>
                <Download size={13} strokeWidth={2.4} /> PNG
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Incantation strip */}
      <div className="mw-spell">
        <div className="mw-spell-inkwell">
          <Palette size={14} strokeWidth={2.4} />
        </div>
        <textarea
          className="mw-spell-input"
          rows={2}
          placeholder="Donne ton intention. Mon pinceau invoquera l'image depuis ton trait."
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); void invoke() }
          }}
          disabled={rendering}
        />
        <VoicePushToTalk
          onTranscript={(t) => setPrompt((prev) => (prev?.trim() ? `${prev}, ${t}` : t))}
          label="Dicter ton intention de dessin"
          size={30}
          variant="ghost"
        />
        {rendering ? (
          <button type="button" className="mw-spell-btn is-stop" onClick={stop}>
            <StopCircle size={14} strokeWidth={2.4} /> Stop
          </button>
        ) : (
          <button type="button" className="mw-spell-btn" onClick={() => void invoke()} disabled={!prompt.trim()}>
            <Sparkles size={14} strokeWidth={2.4} /> {who === 'natsu' ? 'EMBRASER' : 'INVOQUER'}
          </button>
        )}
      </div>
      {error && <div className="mw-error">⚠ {error}</div>}
    </div>
  )
}
