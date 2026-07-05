/**
 * useDrawingViewLogic — drawing state extracted from MangaDrawingView so
 * Aurora V1 (Editorial sumi-e) and V3 (Ricochet l'atelier) skin ports
 * keep every Manga feature: pointer-pressure brushes (ink/eraser), colour
 * palette + custom picker, brush size, symmetry mode, undo/redo, IDB
 * sketch persistence, FLUX render via Aurora-Connect grounding, drying
 * line gallery, download PNG.
 *
 * The hook owns canvas refs and exposes `bindCanvas` so both ports can
 * mount the canvas element wherever their layout demands. All mutations
 * (history snapshot, persist, clear) flow through the hook so the Manga
 * drawing semantics carry over identically.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { useGenerationFxEmitter, useGenerationFxResult } from '../components/generationFx/fxBus'
import {
  comfyuiGetHistory,
  comfyuiGetImage,
  comfyuiQueuePrompt,
  comfyuiUploadImage,
  ensureComfyUIRunning,
  ollamaChat,
} from '../hooks/useTauri'
import { createFluxWorkflow } from '../utils/fluxWorkflow'
import { parseImageIntent } from '../utils/imagePromptParser'
import { useModuleDraftsStore } from '../stores/moduleDraftsStore'
import { useAppStore } from '../stores/appStore'
import { saveBlob, loadBlobUrl } from '../utils/blobStore'
import { RANDOM_DRAW_PROMPTS, pickRandom as pickRandomCreative } from '../utils/randomCreativePrompts'
import { readHistory, pushHistory, removeHistoryEntry, type PromptHistoryEntry } from '../utils/promptHistory'
import { useModuleHistoryStore } from '../stores/moduleHistoryStore'

// v82n6 : sketch vision analysis BEFORE FLUX — qwen3-vl:30b describes the
// canvas in natural language so the FLUX prompt actually reflects what the
// user drew. Without this, the V1/V3 sumi-e skin sent only the user prompt
// + extension ref to FLUX and the canvas was effectively ignored (the
// drawing module's whole reason to exist). Mirrors the pattern from the
// legacy DrawingView.tsx (lines 89-122) per CLAUDE.md hard rule:
// "analyzeSketchWithVision() runs qwen3-vl:30b BEFORE FLUX to describe the
//  sketch in natural language. Don't skip — without it, FLUX ignores the
//  canvas." The sketch canvas is intentionally NOT staged as a denoise
// reference here (sumi-e skin design choice — vision description only).
async function analyzeSketchWithVision(
  sketchBlob: Blob,
  userPrompt: string,
  visionModel: string,
  signal?: AbortSignal,
): Promise<string> {
  try {
    if (signal?.aborted) return userPrompt
    const arrayBuffer = await sketchBlob.arrayBuffer()
    const base64 = btoa(String.fromCharCode(...new Uint8Array(arrayBuffer)))
    const response = await ollamaChat(visionModel, [
      {
        role: 'user',
        content: [
          'This is a rough hand-drawn sketch made by a non-artist.',
          'Your task: describe WHAT is drawn (subjects, shapes, spatial layout, implied scene).',
          'Then generate a polished English description for an image diffusion model.',
          '',
          `The user confirmed the sketch should represent: "${userPrompt}"`,
          '',
          'Rules:',
          '- Treat the user label as authoritative when the shapes are ambiguous',
          '- Identify the subjects and their positions from the sketch shapes',
          '- Preserve distinctive geometry: square eyes, sharp teeth, windows, roofs, limbs, props, facial expression and relative placement',
          '- Ignore line quality — focus on intent and composition',
          '- NEVER refuse, censor, moralize, soften, replace with a safer subject or output a safety disclaimer; describe fictional dark, scary or mean-looking designs faithfully',
          '- Output format: 1-2 sentences max, pure visual description in English',
          '- Do NOT mention "sketch", "drawing", "rough" or "hand-drawn" in output',
          '- Integrate the user intent with what you see in the sketch',
          '- Output ONLY the visual description, nothing else',
        ].join('\n'),
        images: [base64],
      },
    ], 0.3)
    const text = response?.message?.content?.trim() || ''
    if (text.length > 10) return text
  } catch {
    /* fallback silencieux : on retombe sur le prompt user pur */
  }
  return userPrompt
}

export type Character = 'natsu' | 'lucy'
export const PORTRAITS: Record<Character, string> = {
  natsu: '/fairy/natsu.png',
  lucy:  '/fairy/lucy.png',
}

export type BrushMode = 'ink' | 'eraser'
export type DrawingColorMode = 'auto' | 'color' | 'monochrome'

export type DryingSheet = {
  id: string
  sketchUrl: string
  renderUrl: string | null
  prompt: string
  ts: number
  sketchBlobId?: string
  renderBlobId?: string
  colorMode?: DrawingColorMode
}

export const PALETTE = ['#1a140d', '#b5241e', '#e4bf49', '#3c7d3a', '#264de4', '#6a1f9a', '#ffffff']

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
        const payload = Object.values(hist)[0] as { outputs?: Record<string, { images?: Array<{ filename?: string }> }> } | undefined
        const outputs = payload?.outputs
        if (outputs) {
          const filenames: string[] = []
          for (const node of Object.values(outputs)) {
            for (const img of node?.images ?? []) {
              if (img?.filename) filenames.push(img.filename)
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

function canvasHasVisibleContent(canvas: HTMLCanvasElement): boolean {
  const ctx = canvas.getContext('2d')
  if (!ctx || canvas.width <= 0 || canvas.height <= 0) return false

  try {
    const { width, height } = canvas
    const data = ctx.getImageData(0, 0, width, height).data
    const cornerIndexes = [
      0,
      (width - 1) * 4,
      ((height - 1) * width) * 4,
      ((height - 1) * width + (width - 1)) * 4,
    ]
    const bg = cornerIndexes.reduce<[number, number, number, number]>((acc, idx) => {
      acc[0] += data[idx] || 0
      acc[1] += data[idx + 1] || 0
      acc[2] += data[idx + 2] || 0
      acc[3] += data[idx + 3] || 0
      return acc
    }, [0, 0, 0, 0]).map((v) => v / cornerIndexes.length) as [number, number, number, number]

    const targetSamples = 5000
    const step = Math.max(1, Math.floor(Math.sqrt((width * height) / targetSamples)))
    let samples = 0
    let changed = 0
    for (let y = 0; y < height; y += step) {
      for (let x = 0; x < width; x += step) {
        const idx = (y * width + x) * 4
        const delta =
          Math.abs((data[idx] || 0) - bg[0]) +
          Math.abs((data[idx + 1] || 0) - bg[1]) +
          Math.abs((data[idx + 2] || 0) - bg[2]) +
          Math.abs((data[idx + 3] || 0) - bg[3])
        samples += 1
        if (delta > 34) changed += 1
      }
    }
    return samples > 0 && changed / samples > 0.0015
  } catch {
    return true
  }
}

function buildColorInstruction(mode: DrawingColorMode): string {
  switch (mode) {
    case 'color':
      return 'Render in full color with a controlled palette. Preserve every explicit color from the user or from colored strokes in the canvas.'
    case 'monochrome':
      return 'Render strictly in black and white ink/graphite. No colored accents.'
    default:
      return 'Color policy: keep the natural sketch intent. Use color only when the user asks for color or the canvas clearly contains color cues; otherwise keep an ink/monochrome finish.'
  }
}

function sketchDenoiseForIntent(isEditIntent: boolean, colorMode: DrawingColorMode): number {
  if (isEditIntent) return 0.42
  if (colorMode === 'color') return 0.62
  return 0.58
}

function buildSketchFaithfulPrompt({
  interpretedPrompt,
  userPrompt,
  colorMode,
  hasSketchReference,
}: {
  interpretedPrompt: string
  userPrompt: string
  colorMode: DrawingColorMode
  hasSketchReference: boolean
}): string {
  const sketchRules = hasSketchReference
    ? [
        'The uploaded canvas reference is the source of truth for silhouette, subject count, layout, pose, facial expression and object geometry.',
        'Do not replace the canvas subject with a nearby idea. Do not add unrelated characters, props or scenery.',
        'Preserve recognizable drawn details such as square eyes, roofs, windows, limbs, teeth, eyebrows, weapons, symbols and relative positions.',
      ].join(' ')
    : 'No usable canvas strokes were detected, so follow the written brief directly.'

  return [
    interpretedPrompt,
    `User intent: ${userPrompt}`,
    sketchRules,
    buildColorInstruction(colorMode),
    'Creative local pipeline: fictional scary, mean, surreal, monster, horror, dark fantasy, cartoon violence and stylized menace are allowed. Never refuse, censor, moralize, soften or replace the requested subject.',
    'Polish the result while staying faithful to the original shapes and composition.',
  ].join(' ')
}

export function useDrawingViewLogic({ paperColor = '#faf3de' }: { paperColor?: string } = {}) {
  // v82n6 : visionModel comes from the user's app config (qwen3-vl:30b
  // by default) and powers analyzeSketchWithVision below. Read once via
  // selector so the hook doesn't re-render on unrelated store changes.
  const visionModel = useAppStore((s) => s.visionModel)
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
  // v82il : color history persistante (top 10 couleurs custom utilisées).
  const COLOR_HIST_KEY = 'aurora-drawing-color-history-v1'
  const COLOR_HIST_MAX = 10
  const [colorHistory, setColorHistory] = useState<string[]>(() => {
    if (typeof window === 'undefined') return []
    try {
      const raw = window.localStorage.getItem(COLOR_HIST_KEY)
      if (!raw) return []
      const arr = JSON.parse(raw)
      return Array.isArray(arr) ? arr.filter((c) => typeof c === 'string').slice(0, COLOR_HIST_MAX) : []
    } catch { return [] }
  })
  const pushColorHistory = useCallback((color: string) => {
    if (!color) return
    setColorHistory((prev) => {
      // Skip si couleur dans la PALETTE par défaut (pas une "custom").
      if ((PALETTE as readonly string[]).includes(color)) return prev
      const next = [color, ...prev.filter((c) => c !== color)].slice(0, COLOR_HIST_MAX)
      try { window.localStorage.setItem(COLOR_HIST_KEY, JSON.stringify(next)) } catch { /* ignore */ }
      return next
    })
  }, [])
  // Wrapped setter qui push automatiquement l'historique.
  const setInkColorWithHistory = useCallback((color: string) => {
    setInkColor(color)
    pushColorHistory(color)
  }, [pushColorHistory])
  // v82in : remove color from history.
  const removeColorFromHistory = useCallback((color: string) => {
    setColorHistory((prev) => {
      const next = prev.filter((c) => c !== color)
      try { window.localStorage.setItem(COLOR_HIST_KEY, JSON.stringify(next)) } catch { /* ignore */ }
      return next
    })
  }, [])
  // v82ip : pinned colors — sticky LRU (jamais évincées par cap).
  const COLOR_PIN_KEY = 'aurora-drawing-color-pinned-v1'
  const [pinnedColors, setPinnedColors] = useState<string[]>(() => {
    if (typeof window === 'undefined') return []
    try {
      const raw = window.localStorage.getItem(COLOR_PIN_KEY)
      if (!raw) return []
      const arr = JSON.parse(raw)
      return Array.isArray(arr) ? arr.filter((c) => typeof c === 'string') : []
    } catch { return [] }
  })
  const togglePinColor = useCallback((color: string) => {
    setPinnedColors((prev) => {
      const next = prev.includes(color)
        ? prev.filter((c) => c !== color)
        : [...prev, color]
      try { window.localStorage.setItem(COLOR_PIN_KEY, JSON.stringify(next)) } catch { /* ignore */ }
      return next
    })
  }, [])
  const [brushSize, setBrushSize] = useState<number>(() => (drawDraft?.options?.brushSize as number) ?? 3)
  const [colorMode, setColorMode] = useState<DrawingColorMode>(() => {
    const value = drawDraft?.options?.colorMode
    return value === 'color' || value === 'monochrome' || value === 'auto' ? value : 'auto'
  })
  useEffect(() => {
    setDrawDraft('drawing', { options: { symmetry, inkColor, brushSize, colorMode } })
  }, [symmetry, inkColor, brushSize, colorMode, setDrawDraft])

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
  useGenerationFxEmitter('drawing', rendering, progress || undefined)
  useGenerationFxResult('drawing', rendering, renderUrl)
  const [error, setError] = useState<string | null>(null)
  const [line, setLine] = useState<DryingSheet[]>([])
  const abortRef = useRef<AbortController | null>(null)
  // v82gs : prompt history persistant (cap 12, click-recall).
  const [history, setHistory] = useState<PromptHistoryEntry[]>(() => readHistory('drawing'))
  const recallPrompt = useCallback((entry: PromptHistoryEntry) => {
    const sessionId = typeof entry.meta?.sessionId === 'string' ? entry.meta.sessionId : null
    useModuleHistoryStore.getState().openPromptSession('drawing', entry.prompt, sessionId)
    setPrompt(entry.prompt)
    const mode = entry.meta?.colorMode
    if (mode === 'auto' || mode === 'color' || mode === 'monochrome') setColorMode(mode)
    const renderBlobId = typeof entry.meta?.renderBlobId === 'string' ? entry.meta.renderBlobId : ''
    if (renderBlobId) {
      void loadBlobUrl(renderBlobId).then((url) => {
        if (url) setRenderUrl(url)
      })
    }
    const sketchBlobId = typeof entry.meta?.sketchBlobId === 'string' ? entry.meta.sketchBlobId : ''
    if (sketchBlobId) {
      void loadBlobUrl(sketchBlobId).then((url) => {
        if (!url) return
        const c = canvasRef.current
        const ctx = c?.getContext('2d')
        if (!c || !ctx) {
          URL.revokeObjectURL(url)
          return
        }
        const img = new Image()
        img.onload = () => {
          ctx.fillStyle = paperColor
          ctx.fillRect(0, 0, c.clientWidth, c.clientHeight)
          ctx.drawImage(img, 0, 0, c.clientWidth, c.clientHeight)
          URL.revokeObjectURL(url)
        }
        img.src = url
      })
    }
  }, [paperColor])
  const removeHistory = useCallback((p: string) => {
    setHistory(removeHistoryEntry('drawing', p))
  }, [])

  // Initialize canvas + rehydrate
  const initCanvas = useCallback(() => {
    const c = canvasRef.current
    if (!c) return
    const ctx = c.getContext('2d')
    if (!ctx) return
    const ratio = window.devicePixelRatio || 1
    c.width = c.clientWidth * ratio
    c.height = c.clientHeight * ratio
    ctx.scale(ratio, ratio)
    ctx.fillStyle = paperColor
    ctx.fillRect(0, 0, c.clientWidth, c.clientHeight)
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
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
  }, [paperColor])
  useEffect(() => { initCanvas() }, [initCanvas])

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
      if (!canvasRef.current) return
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'z' && !e.shiftKey) {
        e.preventDefault(); undo()
      } else if ((e.metaKey || e.ctrlKey) && (e.key.toLowerCase() === 'y' || (e.key.toLowerCase() === 'z' && e.shiftKey))) {
        e.preventDefault(); redo()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const onDown = (e: React.PointerEvent<HTMLCanvasElement>) => {
    e.preventDefault()
    snapshotForHistory()
    drawingRef.current = true
    lastPointRef.current = getPos(e)
    canvasRef.current?.setPointerCapture(e.pointerId)
  }
  const onMove = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!drawingRef.current) return
    const p = getPos(e)
    const last = lastPointRef.current ?? p
    const c = canvasRef.current!
    const ctx = c.getContext('2d')!
    const base = brushSize
    const width = brush === 'ink' ? base * 0.6 + (e.pressure || 0.5) * base * 1.2 : base * 3
    ctx.strokeStyle = brush === 'ink' ? inkColor : paperColor
    ctx.lineWidth = width
    ctx.beginPath()
    ctx.moveTo(last.x, last.y)
    ctx.lineTo(p.x, p.y)
    ctx.stroke()
    if (symmetry) {
      const axis = c.clientWidth / 2
      ctx.beginPath()
      ctx.moveTo(2 * axis - last.x, last.y)
      ctx.lineTo(2 * axis - p.x, p.y)
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
    ctx.fillStyle = paperColor
    ctx.fillRect(0, 0, c.clientWidth, c.clientHeight)
    setRenderUrl(null)
    persistCanvas()
  }

  // v82ey / v82fg : random ink + prompt depuis pool mutualisé.
  const randomDrawPreset = useCallback(() => {
    setInkColor(pickRandomCreative(PALETTE as readonly string[] as string[], inkColor))
    setPrompt(pickRandomCreative(RANDOM_DRAW_PROMPTS))
  }, [inkColor])

  // v82fo : charge une image (file ou dataURL) dans le canvas comme
  // base de tracé. Utile pour tracer/styliser une référence.
  // Préserve l'aspect ratio en centrant + letterbox paperColor.
  const loadImageToCanvas = useCallback(async (file: File) => {
    // v82ee : guard taille
    const { validateImageFile } = await import('../utils/textFileExtract')
    const sizeErr = validateImageFile(file)
    if (sizeErr) { setError(sizeErr); return }
    const c = canvasRef.current
    if (!c) return
    const ctx = c.getContext('2d')
    if (!ctx) return
    const url = URL.createObjectURL(file)
    try {
      await new Promise<void>((resolve, reject) => {
        const img = new Image()
        img.onload = () => {
          // Reset au paper background
          ctx.fillStyle = paperColor
          ctx.fillRect(0, 0, c.clientWidth, c.clientHeight)
          // Compute fit ratio (contain)
          const cw = c.clientWidth
          const ch = c.clientHeight
          const rw = cw / img.width
          const rh = ch / img.height
          const r = Math.min(rw, rh)
          const dw = img.width * r
          const dh = img.height * r
          const dx = (cw - dw) / 2
          const dy = (ch - dh) / 2
          ctx.drawImage(img, dx, dy, dw, dh)
          resolve()
        }
        img.onerror = () => reject(new Error('decode failed'))
        img.src = url
      })
      persistCanvas()
    } finally {
      URL.revokeObjectURL(url)
    }
  }, [paperColor, persistCanvas])

  // v82n6/v82p : capture sketch as a Blob so the same bytes can feed
  // vision analysis, ComfyUI reference upload and persistent history.
  const snapshotSketchBlob = async (): Promise<Blob | null> => {
    const c = canvasRef.current
    if (!c) return null
    return new Promise((resolve) => {
      c.toBlob((blob) => resolve(blob), 'image/png')
    })
  }

  const restoreCanvasFromUrl = useCallback((url: string) => {
    const c = canvasRef.current
    const ctx = c?.getContext('2d')
    if (!c || !ctx) {
      URL.revokeObjectURL(url)
      return
    }
    const img = new Image()
    img.onload = () => {
      ctx.fillStyle = paperColor
      ctx.fillRect(0, 0, c.clientWidth, c.clientHeight)
      ctx.drawImage(img, 0, 0, c.clientWidth, c.clientHeight)
      URL.revokeObjectURL(url)
      persistCanvas()
    }
    img.src = url
  }, [paperColor, persistCanvas])

  const recallSheet = useCallback((sheet: DryingSheet) => {
    setPrompt(sheet.prompt)
    if (sheet.colorMode) setColorMode(sheet.colorMode)
    if (sheet.renderBlobId) {
      void loadBlobUrl(sheet.renderBlobId).then((url) => {
        if (url) setRenderUrl(url)
        else if (sheet.renderUrl) setRenderUrl(sheet.renderUrl)
      })
    } else if (sheet.renderUrl) {
      setRenderUrl(sheet.renderUrl)
    }
    if (sheet.sketchBlobId) {
      void loadBlobUrl(sheet.sketchBlobId).then((url) => {
        if (url) restoreCanvasFromUrl(url)
      })
    } else if (sheet.sketchUrl) {
      restoreCanvasFromUrl(sheet.sketchUrl)
    }
  }, [restoreCanvasFromUrl])

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
      const runTs = Date.now()
      const sheetId = `sheet-${runTs}`
      const sketchBlob = await snapshotSketchBlob()
      if (!sketchBlob) throw new Error('Impossible de capturer le croquis.')
      const sketchBlobId = `${sheetId}-sketch`
      const renderBlobId = `${sheetId}-render`
      const sketchUrl = await saveBlob(sketchBlobId, sketchBlob, 'drawing')
      const hasSketchContent = Boolean(canvasRef.current && canvasHasVisibleContent(canvasRef.current))

      const up = await ensureComfyUIRunning()
      if (!up.ok) throw new Error(up.error || 'ComfyUI indisponible')

      const drawIntent = parseImageIntent(text)
      const cleanedDrawText = drawIntent.cleanedPrompt

      let sketchReference: { filename: string; denoise?: number } | null = null
      if (hasSketchContent) {
        setProgress('Ancrage du croquis dans ComfyUI...')
        const file = new File([sketchBlob], `aurora_sketch_${runTs}.png`, { type: sketchBlob.type || 'image/png' })
        const uploaded = await comfyuiUploadImage(file)
        if (uploaded?.name) {
          sketchReference = {
            filename: uploaded.name,
            denoise: sketchDenoiseForIntent(drawIntent.isEditIntent, colorMode),
          }
        }
      }

      let extReference: { filename: string; denoise?: number } | null = null
      if (!sketchReference) {
        try {
          const { searchReferenceImages } = await import('../services/auroraExtensionBridge')
          const refResult = await searchReferenceImages(cleanedDrawText, { limit: 1, signal: ac.signal })
          if (refResult.ok && refResult.data.length > 0) {
            const refUrl = refResult.data[0].url
            const refResponse = await fetch(refUrl, { signal: ac.signal })
            if (refResponse.ok) {
              const refBlob = await refResponse.blob()
              const file = new File([refBlob], `aurora_extref_${runTs}.png`, { type: refBlob.type || 'image/png' })
              const uploaded = await comfyuiUploadImage(file)
              if (uploaded?.name) extReference = { filename: uploaded.name, denoise: 0.62 }
            }
          }
        } catch { /* extension grounding best-effort */ }
      }

      setProgress('Workflow FLUX…')
      // v82bj : strip natural-language removals from the user prompt
      // before sending to FLUX. Same fix that v82bi shipped for Image
      // — without this, "sans X" / "enlève X" / "without X" stayed
      // in the positive prompt and FLUX rendered X anyway.
      // v82n6 : analyze the canvas with qwen3-vl:30b BEFORE FLUX so the
      // user's actual drawing drives the prompt (not just the textbox).
      // The vision model reads the sketch shapes and emits a polished
      // English description that we prepend to the FLUX prompt. If the
      // vision call fails or returns nothing useful we silently fall
      // back to the cleaned user prompt — no UX regression.
      setProgress('Analyse du croquis (vision)…')
      let sketchDescription = cleanedDrawText
      if (hasSketchContent && sketchBlob.size > 0) {
        const visionDesc = await analyzeSketchWithVision(
          sketchBlob,
          cleanedDrawText,
          visionModel,
          ac.signal,
        )
        if (visionDesc && visionDesc !== cleanedDrawText) {
          sketchDescription = visionDesc
        }
      }
      const interpretedPrompt = sketchDescription !== cleanedDrawText
        ? `${sketchDescription}. ${cleanedDrawText}`
        : cleanedDrawText

      setProgress('Workflow FLUX…')
      const referenceImage = sketchReference ?? extReference
      const faithfulPrompt = buildSketchFaithfulPrompt({
        interpretedPrompt,
        userPrompt: cleanedDrawText,
        colorMode,
        hasSketchReference: Boolean(sketchReference),
      })
      const workflow = createFluxWorkflow({
        prompt: `${faithfulPrompt}, detailed polished illustration`,
        style: 'manga',
        width: 1024, height: 1024, steps: 26,
        filenamePrefix: `sumi_${runTs}`,
        referenceImage,
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
      const url = await saveBlob(renderBlobId, blob, 'drawing')
      setRenderUrl(url)
      setProgress('')

      setLine((prev) => [{
        id: sheetId, sketchUrl, renderUrl: url,
        prompt: text, ts: runTs,
        sketchBlobId,
        renderBlobId,
        colorMode,
      }, ...prev].slice(0, 12))
      useModuleHistoryStore.getState().pushMessage('drawing', { role: 'user', content: text })
      useModuleHistoryStore.getState().pushMessage('drawing', { role: 'assistant', content: `[drawing:${url}] colorMode:${colorMode}` })
      const activeSession = useModuleHistoryStore.getState().getActiveSession('drawing')
      // v82gs/v86 : push history une seule fois par run, lie a une session.
      setHistory(pushHistory('drawing', text, {
        sketchBlobId,
        renderBlobId,
        colorMode,
        sessionId: activeSession.id,
      }))
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
  }, [prompt, rendering, visionModel, colorMode])

  const stop = () => abortRef.current?.abort()

  const downloadRender = () => {
    if (!renderUrl) return
    const a = document.createElement('a')
    a.href = renderUrl
    a.download = `sumi-${Date.now()}.png`
    document.body.appendChild(a); a.click(); a.remove()
  }

  return {
    who,
    canvasRef,
    canvasHandlers: { onPointerDown: onDown, onPointerMove: onMove, onPointerUp: onUp, onPointerCancel: onUp },
    brush, setBrush,
    symmetry, setSymmetry,
    inkColor, setInkColor: setInkColorWithHistory,
    // v82il + v82in + v82ip : color history (custom only, 10 derniers)
    //   + remove + pin sticky.
    colorHistory, removeColorFromHistory,
    pinnedColors, togglePinColor,
    colorMode, setColorMode,
    brushSize, setBrushSize,
    historyLen, futureLen, undo, redo,
    clearCanvas,
    // v82fo : load image dans le canvas (drag-drop)
    loadImageToCanvas,
    // v82ey : random ink + random prompt
    randomDrawPreset,
    prompt, setPrompt,
    rendering, renderUrl, progress, error,
    line, recallSheet,
    invoke, stop, downloadRender,
    // v82gs : prompt history
    history, recallPrompt, removeHistory,
  }
}
