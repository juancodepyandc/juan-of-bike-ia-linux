import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import {
  AlertCircle,
  Circle as CircleIcon,
  Download,
  Eraser,
  Loader2,
  Minus,
  Paintbrush,
  Palette,
  Pipette,
  RefreshCw,
  Save,
  Sparkles,
  Square as SquareIcon,
  Undo2,
  Redo2,
} from 'lucide-react'
import ClarificationDialog from '../components/ClarificationDialog.tsx'
import type { ClarificationRequest } from '../components/ClarificationDialog.tsx'
import ContextFilesField from '../components/ContextFilesField.tsx'
import VoicePushToTalk from '../components/VoicePushToTalk.tsx'
import ModuleAssetPackCard from '../components/ModuleAssetPackCard.tsx'
import ConnectorRecommendationsPanel from '../components/ConnectorRecommendationsPanel.tsx'
import { buildDrawingModuleAssets } from '../config/moduleAssetPacks.ts'
import { AUXILIARY_ANALYSIS_MODEL, IMAGE_MODEL_PACK_LABEL } from '../config/models.ts'
import { useAppStore } from '../stores/appStore.ts'
import {
  comfyuiGetHistory,
  comfyuiGetImage,
  comfyuiQueuePrompt,
  ensureComfyUIRunning,
  freeGpuBeforeFlux,
  fsWriteBinary,
  getWorkspacePath,
  ollamaChat,
  toAssetUrl,
} from '../hooks/useTauri.ts'
import { StudioDiagnosticsPanel, StudioHero } from '../components/StudioHero.tsx'
import { useManagedRuntime } from '../hooks/useManagedRuntime.ts'
import { useModuleAssetPack } from '../hooks/useModuleAssetPack.ts'
import { useStudioDiagnostics } from '../hooks/useStudioDiagnostics.ts'
import { prepareTaskIntelligence } from '../services/taskIntelligence.ts'
import type { GenerationContract } from '../services/generationContract.ts'
import { createFluxWorkflow, getAvailableStyles, type FluxStyle } from '../utils/fluxWorkflow.ts'
import { extractComfyPromptId, waitForComfyResult } from '../utils/comfyui.ts'
import { getErrorMessage } from '../utils/errors.ts'
import { useGenerationRecovery } from '../hooks/useGenerationRecovery.ts'
import { useGenerationTrackerStore } from '../stores/generationTrackerStore.ts'
import RecoveryBanner from '../components/RecoveryBanner.tsx'
import { isTauriRuntime } from '../utils/runtime.ts'
import { prepareContextFiles } from '../utils/multimodalContext.ts'
import { stageBlobToComfyInput } from '../utils/referenceMedia.ts'
import { polylineToBeziers, rdp } from '../services/drawingCurveSmoothing.ts'
import { generateHarmony, hexToRgb, wcagContrast } from '../services/drawingColorTools.ts'
import LyraCharacter from '../components/voice/LyraCharacter.tsx'

function canvasBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('Timeout: capture du croquis trop longue.')), 10000)
    canvas.toBlob((blob) => {
      clearTimeout(timer)
      if (blob) {
        resolve(blob)
        return
      }

      reject(new Error('Impossible de capturer le croquis.'))
    }, 'image/png')
  })
}

function getSketchEditDenoise(contract: GenerationContract) {
  // Denoise tres eleve: le croquis est un GUIDE spatial tres lache.
  // FLUX doit INTERPRETER et AMELIORER, pas reproduire les traits.
  switch (contract.editStrategy) {
    case 'preserve_and_refine':
      return 0.88
    case 'targeted_edit':
      return 0.92
    case 'scene_transform':
      return 0.97
    default:
      return 0.94
  }
}

/**
 * Analyse le croquis avec le modele vision pour deviner ce qui est dessine.
 * Retourne une description EN propre prete pour la diffusion.
 */
async function analyzeSketchWithVision(sketchBlob: Blob, userPrompt: string, visionModel: string): Promise<string> {
  try {
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
          `The user wants: "${userPrompt}"`,
          '',
          'Rules:',
          '- Identify the subjects and their positions from the sketch shapes',
          '- Ignore line quality — focus on intent and composition',
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
    // Fallback silencieux
  }
  return userPrompt
}

export default function DrawingView() {
  const { runtimeServices, visionModel } = useAppStore()
  const diagnostics = useStudioDiagnostics({ requiresComfyui: true, requiresOllama: true })
  const { executeWithRuntime } = useManagedRuntime()
  const [contextFiles, setContextFiles] = useState<File[]>([])
  const { pack: assetPack, preparePack } = useModuleAssetPack({
    module: 'drawing',
    title: 'Pack modele drawing',
    assets: buildDrawingModuleAssets(visionModel, runtimeServices.comfyui.path, contextFiles.length > 0),
  })
  const styles = useMemo(() => getAvailableStyles().slice(0, 8), [])
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const contextRef = useRef<CanvasRenderingContext2D | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const activeTrackerIdRef = useRef<string | null>(null)
  const historyRef = useRef<ImageData[]>([])
  const historyIndexRef = useRef(-1)
  const dragStartRef = useRef<{ x: number; y: number } | null>(null)
  const snapshotRef = useRef<ImageData | null>(null)
  const strokePointsRef = useRef<Array<{ x: number; y: number }>>([])
  const { trackGeneration, completeGeneration, failGeneration } = useGenerationTrackerStore()
  const recovery = useGenerationRecovery('drawing')
  const [isDrawing, setIsDrawing] = useState(false)
  const [brushSize, setBrushSize] = useState(5)
  const [brushColor, setBrushColor] = useState('#ffffff')
  const [brushOpacity, setBrushOpacity] = useState(1)
  const [tool, setTool] = useState<'brush' | 'eraser' | 'line' | 'rect' | 'circle' | 'picker'>('brush')
  const [smoothMode, setSmoothMode] = useState(false)
  const [smoothEpsilon, setSmoothEpsilon] = useState(1.2)
  const [gridMode, setGridMode] = useState<'none' | 'thirds' | 'golden' | 'center'>('none')
  const [historyVersion, setHistoryVersion] = useState(0)
  const [prompt, setPrompt] = useState('')
  const [selectedStyle, setSelectedStyle] = useState<FluxStyle>('none')
  const [isGenerating, setIsGenerating] = useState(false)
  const [progress, setProgress] = useState('')
  const [generatedUrl, setGeneratedUrl] = useState<string | null>(null)
  const [sketchUrl, setSketchUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [clarification, setClarification] = useState<ClarificationRequest | null>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    canvas.width = 1024
    canvas.height = 640

    const context = canvas.getContext('2d')
    if (!context) return

    context.fillStyle = '#091116'
    context.fillRect(0, 0, canvas.width, canvas.height)
    context.lineCap = 'round'
    context.lineJoin = 'round'
    contextRef.current = context
    // Initialise history with a blank baseline
    historyRef.current = [context.getImageData(0, 0, canvas.width, canvas.height)]
    historyIndexRef.current = 0
    setHistoryVersion((value) => value + 1)
  }, [])

  // v84c — Autosave : snapshot canvas en localStorage toutes les 30s (limit 5).
  useEffect(() => {
    const id = window.setInterval(() => {
      const canvas = canvasRef.current
      if (!canvas) return
      try {
        // Skip si tout vide (= initial fill #091116 plein).
        const ctx = canvas.getContext('2d')
        if (!ctx) return
        const dataUrl = canvas.toDataURL('image/jpeg', 0.6)
        const key = 'aurora.drawing.autosaves'
        const raw = window.localStorage.getItem(key)
        const list: Array<{ at: number; dataUrl: string }> = raw ? JSON.parse(raw) : []
        // Skip si snapshot identique au dernier (image vide ou pas de changement).
        if (list.length > 0 && list[0].dataUrl === dataUrl) return
        list.unshift({ at: Date.now(), dataUrl })
        const trimmed = list.slice(0, 5)
        window.localStorage.setItem(key, JSON.stringify(trimmed))
      } catch {/* localStorage plein, skip silencieux */}
    }, 30000)
    return () => clearInterval(id)
  }, [])

  const pushHistory = useCallback(() => {
    const canvas = canvasRef.current
    const context = contextRef.current
    if (!canvas || !context) return
    const snap = context.getImageData(0, 0, canvas.width, canvas.height)
    const stack = historyRef.current
    const nextIndex = historyIndexRef.current + 1
    stack.splice(nextIndex)
    stack.push(snap)
    if (stack.length > 30) stack.shift()
    historyIndexRef.current = stack.length - 1
    setHistoryVersion((value) => value + 1)
  }, [])

  const undo = useCallback(() => {
    const context = contextRef.current
    if (!context) return
    if (historyIndexRef.current <= 0) return
    historyIndexRef.current -= 1
    context.putImageData(historyRef.current[historyIndexRef.current], 0, 0)
    setHistoryVersion((value) => value + 1)
  }, [])

  const redo = useCallback(() => {
    const context = contextRef.current
    if (!context) return
    if (historyIndexRef.current >= historyRef.current.length - 1) return
    historyIndexRef.current += 1
    context.putImageData(historyRef.current[historyIndexRef.current], 0, 0)
    setHistoryVersion((value) => value + 1)
  }, [])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null
      const tag = target?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') {
        event.preventDefault()
        if (event.shiftKey) redo()
        else undo()
      } else if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'y') {
        event.preventDefault()
        redo()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [undo, redo])

  const canUndo = useMemo(() => historyIndexRef.current > 0, [historyVersion])
  const canRedo = useMemo(() => historyIndexRef.current < historyRef.current.length - 1, [historyVersion])

  useEffect(() => {
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current)
      }
    }
  }, [])

  const colors = ['#ffffff', '#f87171', '#fb923c', '#fbbf24', '#34d399', '#22d3ee', '#60a5fa', '#c084fc', '#000000']
  const activeOllamaModel = contextFiles.length > 0 ? visionModel : AUXILIARY_ANALYSIS_MODEL
  const canGenerate = Boolean(prompt.trim()) && !isGenerating && !diagnostics.blockingReason

  const getPoint = (event: React.PointerEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current
    if (!canvas) return null

    const rect = canvas.getBoundingClientRect()
    const scaleX = canvas.width / rect.width
    const scaleY = canvas.height / rect.height

    return {
      x: (event.clientX - rect.left) * scaleX,
      y: (event.clientY - rect.top) * scaleY,
    }
  }

  const handlePointerDown = (event: React.PointerEvent<HTMLCanvasElement>) => {
    const context = contextRef.current
    const canvas = canvasRef.current
    const point = getPoint(event)
    if (!context || !canvas || !point) return

    if (tool === 'picker') {
      const pixel = context.getImageData(Math.max(0, Math.min(canvas.width - 1, Math.floor(point.x))), Math.max(0, Math.min(canvas.height - 1, Math.floor(point.y))), 1, 1).data
      const toHex = (value: number) => value.toString(16).padStart(2, '0')
      const hex = `#${toHex(pixel[0])}${toHex(pixel[1])}${toHex(pixel[2])}`
      setBrushColor(hex)
      setTool('brush')
      return
    }

    canvas.setPointerCapture(event.pointerId)
    setIsDrawing(true)
    dragStartRef.current = point

    if (tool === 'brush' || tool === 'eraser') {
      context.globalCompositeOperation = tool === 'eraser' ? 'destination-out' : 'source-over'
      context.globalAlpha = tool === 'eraser' ? 1 : brushOpacity
      context.strokeStyle = brushColor
      context.fillStyle = brushColor
      context.lineWidth = brushSize
      context.beginPath()
      context.moveTo(point.x, point.y)
      if (smoothMode && tool === 'brush') {
        snapshotRef.current = context.getImageData(0, 0, canvas.width, canvas.height)
        strokePointsRef.current = [{ x: point.x, y: point.y }]
      }
    } else {
      // snapshot for shape preview
      snapshotRef.current = context.getImageData(0, 0, canvas.width, canvas.height)
    }
  }

  const handlePointerMove = (event: React.PointerEvent<HTMLCanvasElement>) => {
    if (!isDrawing || !contextRef.current) return
    const point = getPoint(event)
    if (!point) return

    const context = contextRef.current
    if (tool === 'brush' || tool === 'eraser') {
      context.lineTo(point.x, point.y)
      context.stroke()
      if (smoothMode && tool === 'brush') strokePointsRef.current.push({ x: point.x, y: point.y })
    } else if (snapshotRef.current && dragStartRef.current) {
      context.putImageData(snapshotRef.current, 0, 0)
      context.globalCompositeOperation = 'source-over'
      context.globalAlpha = brushOpacity
      context.strokeStyle = brushColor
      context.lineWidth = brushSize
      context.beginPath()
      if (tool === 'line') {
        context.moveTo(dragStartRef.current.x, dragStartRef.current.y)
        context.lineTo(point.x, point.y)
        context.stroke()
      } else if (tool === 'rect') {
        const w = point.x - dragStartRef.current.x
        const h = point.y - dragStartRef.current.y
        context.strokeRect(dragStartRef.current.x, dragStartRef.current.y, w, h)
      } else if (tool === 'circle') {
        const dx = point.x - dragStartRef.current.x
        const dy = point.y - dragStartRef.current.y
        const radius = Math.sqrt(dx * dx + dy * dy)
        context.arc(dragStartRef.current.x, dragStartRef.current.y, radius, 0, Math.PI * 2)
        context.stroke()
      }
    }
  }

  const stopDrawing = (event?: React.PointerEvent<HTMLCanvasElement>) => {
    if (event) {
      canvasRef.current?.releasePointerCapture(event.pointerId)
    }
    if (isDrawing) {
      // Smooth-mode brush : remplace le tracé brut par une version RDP + Bezier.
      if (smoothMode && tool === 'brush' && snapshotRef.current && strokePointsRef.current.length >= 3) {
        const ctx = contextRef.current
        if (ctx) {
          ctx.putImageData(snapshotRef.current, 0, 0)
          const simplified = rdp(strokePointsRef.current, smoothEpsilon)
          const curves = polylineToBeziers(simplified)
          ctx.globalCompositeOperation = 'source-over'
          ctx.globalAlpha = brushOpacity
          ctx.strokeStyle = brushColor
          ctx.lineWidth = brushSize
          ctx.beginPath()
          if (curves.length > 0) {
            ctx.moveTo(curves[0].start.x, curves[0].start.y)
            for (const c of curves) {
              ctx.bezierCurveTo(c.control1.x, c.control1.y, c.control2.x, c.control2.y, c.end.x, c.end.y)
            }
            ctx.stroke()
          }
        }
      }
      pushHistory()
    }
    strokePointsRef.current = []
    setIsDrawing(false)
    dragStartRef.current = null
    snapshotRef.current = null
    if (contextRef.current) {
      contextRef.current.globalCompositeOperation = 'source-over'
      contextRef.current.globalAlpha = 1
    }
  }

  const clearCanvas = () => {
    const context = contextRef.current
    const canvas = canvasRef.current
    if (!context || !canvas) return

    context.globalCompositeOperation = 'source-over'
    context.globalAlpha = 1
    context.fillStyle = '#091116'
    context.fillRect(0, 0, canvas.width, canvas.height)
    setGeneratedUrl(null)
    setSketchUrl(null)
    pushHistory()
  }

  const exportSketch = useCallback(async (format: 'png' | 'jpeg' = 'png') => {
    const canvas = canvasRef.current
    if (!canvas) return

    const mime = format === 'jpeg' ? 'image/jpeg' : 'image/png'
    const quality = format === 'jpeg' ? 0.92 : undefined
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob((value) => resolve(value), mime, quality))
    if (!blob) return
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `juan-bike-sketch-${Date.now()}.${format === 'jpeg' ? 'jpg' : 'png'}`
    anchor.click()
    URL.revokeObjectURL(url)
  }, [])

  const generate = useCallback(async () => {
    if (!prompt.trim() || isGenerating) return

    if (diagnostics.blockingReason) {
      setError(diagnostics.blockingReason)
      return
    }

    const canvas = canvasRef.current
    if (!canvas) {
      setError('Canvas introuvable.')
      return
    }

    setIsGenerating(true)
    setError(null)
    setProgress('Capture du croquis...')

    try {
      await executeWithRuntime({
        module: 'drawing',
        title: 'Generation dessin',
        services: ['ollama', 'comfyui'],
        ollamaModel: activeOllamaModel,
        prepare: async ({ setPhase }) => {
          await preparePack(setPhase)
          setPhase('Verification de ComfyUI...', 33)
          const comfyStart = await ensureComfyUIRunning()
          if (!comfyStart.ok) {
            throw new Error(comfyStart.error || 'ComfyUI non disponible.')
          }
        },
        job: async ({ setPhase }) => {
          const sketchBlob = await canvasBlob(canvas)
          const timestamp = Date.now()
          const preparedContext = contextFiles.length > 0 ? await prepareContextFiles(contextFiles) : []
          const comfyuiPath = runtimeServices.comfyui.path
          if (!comfyuiPath) {
            throw new Error('Chemin ComfyUI introuvable pour exploiter le croquis comme reference.')
          }
          const stagedSketch = await stageBlobToComfyInput(sketchBlob, comfyuiPath, 'juan_bike_sketch_ref')

          setPhase('Archivage du croquis source...', 42)
          if (isTauriRuntime()) {
            const workspacePath = await getWorkspacePath()
            const sketchPath = `${workspacePath}/output/drawings/juan_bike_sketch_${timestamp}.png`
            const sketchBytes = Array.from(new Uint8Array(await sketchBlob.arrayBuffer()))
            await fsWriteBinary(sketchPath, sketchBytes)
            setSketchUrl(toAssetUrl(sketchPath))
          } else {
            setSketchUrl(URL.createObjectURL(sketchBlob))
          }

          setProgress('Analyse du croquis par le modele vision...')
          setPhase('Analyse du croquis par IA vision...', 55)
          const sketchDescription = await analyzeSketchWithVision(sketchBlob, prompt, visionModel)

          setProgress('Generation du rendu interprete...')
          setPhase('Construction du rendu a partir du brief...', 60)
          // Le prompt combine la description vision du croquis + l'intention utilisateur
          const interpretedPrompt = sketchDescription !== prompt
            ? `${sketchDescription}. ${prompt}`
            : prompt
          const taskContext = await prepareTaskIntelligence({
            module: 'drawing',
            prompt: interpretedPrompt,
            model: visionModel,
            files: preparedContext,
            setPhase,
            phaseBase: 60,
            phaseSpan: 14,
          })

          if (taskContext.clarificationQuestion) {
            setPhase('Clarification utilisateur requise avant rendu drawing.', 64)
            const userAnswer = await new Promise<string | null>((resolve) => {
              setClarification({ question: taskContext.clarificationQuestion!, onRespond: resolve })
            })
            setClarification(null)
            if (userAnswer) {
              taskContext.enrichedPrompt = `${taskContext.enrichedPrompt}\n\nPrecision utilisateur: ${userAnswer}`
              taskContext.generationPrompt = `${taskContext.generationPrompt}\n\nUser clarification: ${userAnswer}`
            }
          }
          const workflow = createFluxWorkflow({
            prompt: taskContext.generationPrompt,
            width: 1024,
            height: 640,
            steps: 20,
            filenamePrefix: 'juan_bike_draw',
            style: selectedStyle,
            referenceImage: { filename: stagedSketch.filename, denoise: getSketchEditDenoise(taskContext.generationContract) },
          })

          // VRAM hygiene before FLUX: evict the sketch-analysis vision model
          // and the auxiliary analyzer so UNet + T5 XXL have their ~22 GiB of
          // reservation on the 16 GB card without OOM.
          await freeGpuBeforeFlux(Array.from(new Set([visionModel, AUXILIARY_ANALYSIS_MODEL].filter(Boolean))))
          const queueResult = await comfyuiQueuePrompt(workflow)
          const promptId = extractComfyPromptId(queueResult)

          // Tracker la generation pour recovery apres refresh
          activeTrackerIdRef.current = trackGeneration({
            module: 'drawing',
            type: 'comfyui',
            prompt,
            startedAt: Date.now(),
            comfyPromptId: promptId,
          })
          const trackerId = activeTrackerIdRef.current

          setPhase('Rendu en cours sur ComfyUI...', 72)
          const result = await waitForComfyResult(promptId, {
            getHistory: comfyuiGetHistory,
            onProgress: (pct, detail) => {
              setPhase(detail, Math.min(88, 72 + Math.round(pct * 0.16)))
            },
            timeoutMs: 300_000,
          })

          setProgress('Recuperation de l image finale...')
          setPhase('Recuperation du rendu final...', 86)
          const imageBlob = await comfyuiGetImage(result.filename, result.subfolder)

          let savedOutputPath = ''
          if (isTauriRuntime()) {
            const workspacePath = await getWorkspacePath()
            const outputPath = `${workspacePath}/output/drawings/juan_bike_draw_${timestamp}.png`
            savedOutputPath = outputPath
            const bytes = Array.from(new Uint8Array(await imageBlob.arrayBuffer()))
            await fsWriteBinary(outputPath, bytes)
            setGeneratedUrl(toAssetUrl(outputPath))
          } else {
            setGeneratedUrl(URL.createObjectURL(imageBlob))
          }

          // Marquer la generation comme terminee dans le tracker (avec contexte vocal)
          completeGeneration(trackerId, {
            resultPath: savedOutputPath || undefined,
            resultFilename: result.filename || undefined,
          })

          setProgress('Croquis capture, rendu charge, liberation des ressources...')
          setPhase('Croquis et rendu archives, liberation des ressources...', 94)
        },
      })
    } catch (generationError) {
      if (activeTrackerIdRef.current) {
        failGeneration(activeTrackerIdRef.current, getErrorMessage(generationError))
        activeTrackerIdRef.current = null
      }
      setError(getErrorMessage(generationError, 'Le module dessin a echoue sans detail exploitable. Consulte le suivi runtime et la file de jobs.'))
      setProgress('')
    } finally {
      setIsGenerating(false)
      setPrompt('')
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
    }
  }, [activeOllamaModel, contextFiles, diagnostics.blockingReason, executeWithRuntime, isGenerating, preparePack, prompt, runtimeServices.comfyui.path, selectedStyle, visionModel])

  return (
    <div className="relative min-h-full flex flex-col">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute inset-0 aurora-mesh opacity-35" />
        <div className="absolute -top-40 -right-20 h-80 w-80 rounded-full bg-pink-500/15 blur-3xl" />
        <div className="absolute -bottom-40 -left-20 h-80 w-80 rounded-full bg-rose-500/15 blur-3xl" />
      </div>
      <div className="relative">
      <ClarificationDialog request={clarification} />
      <RecoveryBanner recovery={recovery} />
      <StudioHero
        icon={Paintbrush}
        eyebrow="Atelier dessin"
        title="Croquis local, iteration visible, rendu IA propre."
        description="Le croquis est capture, archive et utilise comme vraie base spatiale pour guider le rendu IA sans perdre la silhouette, la pose et les couleurs explicites demandees."
        diagnostics={diagnostics}
        stats={[
          { label: 'Pack', value: IMAGE_MODEL_PACK_LABEL },
          {
            label: 'ComfyUI',
            value: runtimeServices.comfyui.running ? 'Actif' : runtimeServices.comfyui.available ? 'Auto-start' : 'Absent',
            tone: runtimeServices.comfyui.running ? 'good' : runtimeServices.comfyui.available ? 'default' : 'warn',
          },
          { label: 'Brosse', value: `${brushSize}px` },
          { label: 'Style', value: styles.find((style) => style.id === selectedStyle)?.label || 'Auto / Libre' },
        ]}
      />

      <div className="grid gap-3 px-2 pb-6 pt-3 sm:gap-4 sm:px-6 sm:pb-8 sm:pt-4 2xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="min-w-0 rounded-[1.4rem] sm:rounded-[1.8rem] border border-aurora-border/40 bg-aurora-surface/45 overflow-hidden">
          <div className="border-b border-aurora-border/30 px-5 py-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-[11px] uppercase tracking-[0.22em] text-aurora-text-dim">Canvas studio</p>
                <h2 className="mt-1 text-lg font-semibold text-aurora-text">Croquis et comparaison</h2>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <button
                  onClick={undo}
                  disabled={!canUndo}
                  title="Annuler (Ctrl+Z)"
                  className="inline-flex items-center gap-1.5 rounded-2xl border border-aurora-border/40 bg-aurora-surface-2 px-3 py-2 text-sm text-aurora-text hover:border-aurora-accent/35 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  <Undo2 size={16} />
                </button>
                <button
                  onClick={redo}
                  disabled={!canRedo}
                  title="Refaire (Ctrl+Y)"
                  className="inline-flex items-center gap-1.5 rounded-2xl border border-aurora-border/40 bg-aurora-surface-2 px-3 py-2 text-sm text-aurora-text hover:border-aurora-accent/35 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  <Redo2 size={16} />
                </button>
                <button
                  onClick={clearCanvas}
                  className="inline-flex items-center gap-2 rounded-2xl border border-aurora-border/40 bg-aurora-surface-2 px-4 py-2 text-sm text-aurora-text hover:border-aurora-accent/35 transition-colors"
                >
                  <Eraser size={16} />
                  Effacer
                </button>
                <button
                  onClick={() => void exportSketch()}
                  className="inline-flex items-center gap-2 rounded-2xl border border-aurora-border/40 bg-aurora-surface-2 px-4 py-2 text-sm text-aurora-text hover:border-aurora-accent/35 transition-colors"
                >
                  <Save size={16} />
                  PNG
                </button>
                <button
                  onClick={() => void exportSketch('jpeg')}
                  className="inline-flex items-center gap-2 rounded-2xl border border-aurora-border/40 bg-aurora-surface-2 px-4 py-2 text-sm text-aurora-text hover:border-aurora-accent/35 transition-colors"
                >
                  <Download size={16} />
                  JPG
                </button>
              </div>
            </div>
          </div>

          <div className="grid min-h-[36rem] gap-4 p-5 xl:grid-cols-2">
            <div className="rounded-[1.8rem] border border-aurora-border/35 bg-[#091116] p-4">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.2em] text-aurora-text-dim">Croquis live</p>
                  <p className="mt-1 text-sm text-aurora-text">Dessine au stylet, a la souris ou au trackpad.</p>
                </div>
                <div className="inline-flex items-center gap-2 rounded-full border border-aurora-border/40 bg-aurora-surface/60 px-3 py-1.5 text-[11px] text-aurora-text-dim">
                  <Paintbrush size={12} />
                  <span>{brushSize}px</span>
                </div>
              </div>

              <div className="overflow-hidden rounded-[1.4rem] border border-aurora-border/35 relative">
                <canvas
                  ref={canvasRef}
                  className="w-full touch-none cursor-crosshair"
                  style={{ aspectRatio: '16 / 10' }}
                  onPointerDown={handlePointerDown}
                  onPointerMove={handlePointerMove}
                  onPointerUp={stopDrawing}
                  onPointerLeave={stopDrawing}
                />
                <DrawingGridOverlay mode={gridMode} />
                {/* v84g — Lyra coach flottant en bas-gauche du canvas */}
                <div className="absolute left-3 bottom-3 pointer-events-none opacity-80" style={{ width: 64, height: 76 }}>
                  <LyraCharacter
                    phase={isDrawing ? 'speaking' : 'idle'}
                    emotion={isGenerating ? 'focus' : isDrawing ? 'happy' : 'curious'}
                    accent="#67d2ff"
                    size={64}
                    amplitude={isDrawing ? 0.6 : 0}
                  />
                </div>
              </div>
              <DrawingGridToggle mode={gridMode} onChange={setGridMode} />
            </div>

            <div className="rounded-[1.8rem] border border-aurora-border/35 bg-aurora-surface/60 p-4">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.2em] text-aurora-text-dim">Comparaison</p>
                  <p className="mt-1 text-sm text-aurora-text">Le croquis et le rendu restent visibles cote a cote.</p>
                </div>
                {generatedUrl && (
                  <a
                    href={generatedUrl}
                    download
                    className="inline-flex items-center gap-2 rounded-2xl border border-aurora-border/40 bg-aurora-surface-2 px-4 py-2 text-sm text-aurora-text hover:border-aurora-accent/35 transition-colors"
                  >
                    <Download size={16} />
                    Telecharger
                  </a>
                )}
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="rounded-[1.4rem] border border-aurora-border/35 bg-aurora-bg/65 p-3">
                  <p className="text-[11px] uppercase tracking-[0.18em] text-aurora-text-dim">Croquis capture</p>
                  <div className="mt-3 flex min-h-56 items-center justify-center overflow-hidden rounded-2xl border border-aurora-border/30 bg-aurora-surface-2">
                    {sketchUrl ? (
                      <img src={sketchUrl} alt="Croquis capture" className="h-full w-full object-contain" />
                    ) : (
                      <p className="px-4 text-center text-xs text-aurora-text-dim">Le croquis capture apparaitra ici lors de la premiere generation.</p>
                    )}
                  </div>
                </div>

                <div className="rounded-[1.4rem] border border-aurora-border/35 bg-aurora-bg/65 p-3">
                  <p className="text-[11px] uppercase tracking-[0.18em] text-aurora-text-dim">Rendu IA</p>
                  <div className="mt-3 flex min-h-56 items-center justify-center overflow-hidden rounded-2xl border border-aurora-border/30 bg-aurora-surface-2">
                    {generatedUrl ? (
                      <motion.img
                        initial={{ opacity: 0, scale: 0.98 }}
                        animate={{ opacity: 1, scale: 1 }}
                        src={generatedUrl}
                        alt="Rendu IA"
                        className="h-full w-full object-contain"
                      />
                    ) : (
                      <p className="px-4 text-center text-xs text-aurora-text-dim">Le rendu apparaitra ici apres la generation ComfyUI.</p>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="2xl:sticky 2xl:top-4 self-start w-full overflow-y-auto scroll-shell max-h-[calc(100vh-12rem)] rounded-[1.8rem] border border-aurora-border/40 bg-aurora-surface/55 p-4 space-y-4">
          <div className="rounded-[1.4rem] border border-aurora-border/35 bg-aurora-surface-2/70 p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-[11px] uppercase tracking-[0.22em] text-aurora-text-dim">Brief</p>
                <p className="mt-2 text-sm text-aurora-text">Decris ce que tu veux voir emerger de ton croquis.</p>
              </div>
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl gradient-accent text-white">
                <Sparkles size={18} />
              </div>
            </div>

            <textarea
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              placeholder="Ex: concept de velo urbain compact, lignes propres, vue trois quarts, lumiere douce"
              rows={5}
              className="mt-4 w-full resize-none rounded-2xl border border-aurora-border bg-aurora-bg/60 px-3 py-3 text-sm text-aurora-text outline-none transition-colors focus:border-aurora-accent/45"
            />
            <div className="mt-2 flex items-center gap-2">
              <VoicePushToTalk
                onTranscript={(text) => setPrompt((prev) => (prev.trim() ? `${prev}, ${text}` : text))}
                label="Dicter ton brief dessin"
                size={36}
              />
              <span className="text-[11px] text-aurora-text-dim">Dicte ce que tu veux voir dessiné.</span>
            </div>
          </div>

          <div className="rounded-[1.4rem] border border-aurora-border/35 bg-aurora-surface-2/60 p-4 space-y-4">
            <div>
              <div className="flex items-center justify-between mb-2">
                <p className="text-[11px] uppercase tracking-[0.22em] text-aurora-text-dim">Outils</p>
                <DrawingShortcutsButton />
              </div>
              <DrawingAutosaveButton onRestore={(dataUrl) => {
                const canvas = canvasRef.current
                const ctx = contextRef.current
                if (!canvas || !ctx) return
                const img = new Image()
                img.onload = () => {
                  ctx.fillStyle = '#091116'
                  ctx.fillRect(0, 0, canvas.width, canvas.height)
                  ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
                  pushHistory()
                }
                img.src = dataUrl
              }} />
              <div className="mt-3 grid grid-cols-6 gap-1.5">
                {([
                  { id: 'brush' as const, icon: Paintbrush, label: 'Pinceau' },
                  { id: 'eraser' as const, icon: Eraser, label: 'Gomme' },
                  { id: 'line' as const, icon: Minus, label: 'Ligne' },
                  { id: 'rect' as const, icon: SquareIcon, label: 'Carre' },
                  { id: 'circle' as const, icon: CircleIcon, label: 'Cercle' },
                  { id: 'picker' as const, icon: Pipette, label: 'Pipette' },
                ]).map(({ id, icon: Icon, label }) => (
                  <button
                    key={id}
                    onClick={() => setTool(id)}
                    title={label}
                    className={`flex flex-col items-center gap-0.5 rounded-xl border px-2 py-2 text-[9px] transition-colors ${
                      tool === id ? 'border-aurora-accent/60 bg-aurora-accent/15 text-aurora-accent' : 'border-aurora-border/40 bg-aurora-surface-2 text-aurora-text-dim hover:text-aurora-text'
                    }`}
                  >
                    <Icon size={14} />
                    <span>{label}</span>
                  </button>
                ))}
              </div>
            </div>

            <div>
              <p className="text-[11px] uppercase tracking-[0.22em] text-aurora-text-dim">Palette</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {colors.map((color) => (
                  <button
                    key={color}
                    onClick={() => setBrushColor(color)}
                    className={`h-8 w-8 rounded-full border-2 transition-transform ${brushColor === color ? 'scale-110 border-white' : 'border-transparent'}`}
                    style={{ backgroundColor: color }}
                  />
                ))}
                <label
                  className={`inline-flex h-8 w-8 cursor-pointer items-center justify-center rounded-full border-2 transition-transform ${
                    colors.includes(brushColor) ? 'border-transparent' : 'scale-110 border-white'
                  }`}
                  style={{ backgroundColor: colors.includes(brushColor) ? 'transparent' : brushColor, backgroundImage: colors.includes(brushColor) ? 'conic-gradient(from 0deg, #ff6a3d, #ffd166, #4dd5a4, #37c7bf, #7fb7ff, #c084fc, #ff6a3d)' : undefined }}
                  title="Couleur personnalisee"
                >
                  <input
                    type="color"
                    value={brushColor}
                    onChange={(event) => setBrushColor(event.target.value)}
                    className="h-0 w-0 opacity-0"
                  />
                  <Palette size={14} className="text-white mix-blend-difference" />
                </label>
              </div>
              <DrawingBrushPresets
                onPick={(p) => {
                  setBrushSize(p.size)
                  setBrushOpacity(p.opacity)
                  setTool('brush')
                  setBrushColor(p.color)
                  setSmoothMode(p.smooth)
                }}
              />
              <DrawingHarmonySuggester baseColor={brushColor} onPick={setBrushColor} />
            </div>

            <div>
              <div className="mb-1 flex items-center justify-between text-[11px] text-aurora-text-dim">
                <span>Taille du trait</span>
                <span>{brushSize}px</span>
              </div>
              <input
                type="range"
                min={1}
                max={80}
                value={brushSize}
                onChange={(event) => setBrushSize(Number(event.target.value))}
                className="w-full accent-aurora-accent"
              />
            </div>

            <div>
              <div className="mb-1 flex items-center justify-between text-[11px] text-aurora-text-dim">
                <span>Opacite</span>
                <span>{Math.round(brushOpacity * 100)}%</span>
              </div>
              <input
                type="range"
                min={0.1}
                max={1}
                step={0.05}
                value={brushOpacity}
                onChange={(event) => setBrushOpacity(Number(event.target.value))}
                className="w-full accent-aurora-accent"
              />
            </div>
            <div className="mt-4 rounded-xl border border-aurora-border/30 bg-aurora-surface/40 p-3">
              <label className="flex items-center gap-2 text-[12px] text-aurora-text cursor-pointer">
                <input
                  id="drawing-smooth-mode"
                  name="smoothMode"
                  type="checkbox"
                  checked={smoothMode}
                  onChange={(e) => setSmoothMode(e.target.checked)}
                  className="accent-aurora-accent"
                />
                <span>Lissage RDP + Bézier</span>
                <span className="ml-auto text-[10px] text-aurora-text-dim">{smoothMode ? 'actif' : 'off'}</span>
              </label>
              {smoothMode && (
                <div className="mt-2">
                  <div className="flex justify-between text-[10px] text-aurora-text-dim mb-1">
                    <span>Epsilon</span>
                    <span>{smoothEpsilon.toFixed(1)}</span>
                  </div>
                  <input
                    type="range"
                    min={0.2}
                    max={4}
                    step={0.1}
                    value={smoothEpsilon}
                    onChange={(e) => setSmoothEpsilon(Number(e.target.value))}
                    className="w-full accent-aurora-accent"
                  />
                  <p className="text-[10px] text-aurora-text-dim mt-1">
                    Plus haut = trait plus simplifié et lisse. Appliqué à la fin du tracé.
                  </p>
                </div>
              )}
            </div>
          </div>

          <div className="rounded-[1.4rem] border border-aurora-border/35 bg-aurora-surface-2/60 p-4">
            <p className="text-[11px] uppercase tracking-[0.22em] text-aurora-text-dim">Style</p>
            <div className="mt-3 grid grid-cols-2 gap-2">
              {styles.map((style) => (
                <button
                  key={style.id}
                  onClick={() => setSelectedStyle(style.id)}
                  className={`rounded-xl px-3 py-2 text-left text-xs transition-colors ${
                    selectedStyle === style.id
                      ? 'gradient-accent text-white'
                      : 'bg-aurora-surface text-aurora-text-dim hover:text-aurora-text'
                  }`}
                >
                  {style.label}
                </button>
              ))}
            </div>
          </div>

          <ContextFilesField
            files={contextFiles}
            onFilesChange={setContextFiles}
            accept=".png,.jpg,.jpeg,.webp,.gif,.pdf,.txt,.md,.json,.csv,.tsv,.xlsx,.xls,.xlsm"
            hint="Ajoute references visuelles ou documents pour orienter le rendu du croquis."
          />

          <ModuleAssetPackCard pack={assetPack} />
          <ConnectorRecommendationsPanel module="drawing" compact />

          <button
            onClick={() => void generate()}
            disabled={!canGenerate}
            className={`flex w-full items-center justify-center gap-2 rounded-[1.4rem] px-4 py-3 text-sm font-medium transition-all ${
              canGenerate
                ? 'gradient-accent text-white glow-accent'
                : 'bg-aurora-surface-2 text-aurora-text-dim opacity-60 cursor-not-allowed'
            }`}
          >
            {isGenerating ? (
              <>
                <Loader2 size={18} className="animate-spin" />
                <span>{progress || 'Generation...'}</span>
              </>
            ) : (
              <>
                <Palette size={18} />
                <span>Capturer et generer</span>
              </>
            )}
          </button>

          {(progress || error) && (
            <div className="space-y-3">
              {progress && (
                <div className="rounded-2xl border border-aurora-border/40 bg-aurora-surface/70 px-4 py-3">
                  <p className="text-[11px] uppercase tracking-[0.2em] text-aurora-text-dim">Etat courant</p>
                  <p className="mt-2 text-sm text-aurora-text">{progress}</p>
                </div>
              )}

              {error && (
                <div className="flex items-start gap-2 rounded-2xl border border-aurora-red/25 bg-aurora-red/10 px-3 py-3">
                  <AlertCircle size={16} className="mt-0.5 shrink-0 text-aurora-red" />
                  <p className="text-xs leading-relaxed text-aurora-red">{error}</p>
                </div>
              )}
            </div>
          )}

          <div className="rounded-[1.4rem] border border-aurora-border/35 bg-aurora-surface-2/60 p-4">
            <div className="flex items-start gap-2">
              <RefreshCw size={16} className="mt-0.5 text-aurora-accent" />
              <div>
                <p className="text-sm text-aurora-text">Clarification importante</p>
                <p className="mt-1 text-xs leading-relaxed text-aurora-text-dim">
                  Le croquis pilote maintenant aussi le denoise du workflow FLUX. Les references jointes continuent d enrichir le brief, mais la geometrie de base vient bien du sketch capture.
                </p>
              </div>
            </div>
          </div>

          <StudioDiagnosticsPanel diagnostics={diagnostics} title="Preflight dessin" />
        </div>
      </div>
      </div>
    </div>
  )
}

// v84c — Bouton autosave : liste les snapshots, restore au clic.
function DrawingAutosaveButton({ onRestore }: { onRestore: (dataUrl: string) => void }) {
  const [open, setOpen] = useState(false)
  const [snaps, setSnaps] = useState<Array<{ at: number; dataUrl: string }>>([])
  useEffect(() => {
    if (!open) return
    try {
      const raw = window.localStorage.getItem('aurora.drawing.autosaves')
      setSnaps(raw ? JSON.parse(raw) : [])
    } catch { setSnaps([]) }
  }, [open])
  return (
    <div className="relative mt-2">
      <button
        onClick={() => setOpen((v) => !v)}
        className="text-[10px] rounded-md bg-white/[0.03] border border-white/10 px-2 py-0.5 font-mono text-aurora-text-dim hover:text-aurora-text"
        title="Restaurer un autosave"
      >
        ⏱ autosave ({snaps.length})
      </button>
      {open && (
        <div className="absolute top-7 left-0 z-50 w-64 rounded-xl border border-aurora-border/40 bg-aurora-surface/95 p-3 shadow-2xl backdrop-blur">
          <div className="mb-2 flex items-center justify-between">
            <p className="text-[10px] uppercase tracking-wider text-aurora-text-dim">Snapshots récents</p>
            <button onClick={() => setOpen(false)} className="text-aurora-text-dim hover:text-aurora-text" aria-label="Fermer">×</button>
          </div>
          {snaps.length === 0 ? (
            <p className="text-[11px] text-aurora-text-dim italic">
              Aucun snapshot. Aurora capture toutes les 30s pendant que tu dessines.
            </p>
          ) : (
            <div className="grid grid-cols-2 gap-1.5">
              {snaps.map((s, i) => (
                <button
                  key={i}
                  onClick={() => { onRestore(s.dataUrl); setOpen(false) }}
                  title={`Restaurer · ${new Date(s.at).toLocaleTimeString('fr-FR')}`}
                  className="overflow-hidden rounded-md border border-white/10 hover:border-aurora-accent/50 transition-colors"
                >
                  <img src={s.dataUrl} alt="snapshot" className="w-full h-16 object-cover" />
                  <div className="px-1 py-0.5 text-[9px] font-mono text-aurora-text-dim text-left">
                    {new Date(s.at).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// v83y — Overlay SVG de grille de composition (rule of thirds / golden / centré).
function DrawingGridOverlay({ mode }: { mode: 'none' | 'thirds' | 'golden' | 'center' }) {
  if (mode === 'none') return null
  return (
    <svg
      viewBox="0 0 100 62.5"
      preserveAspectRatio="none"
      className="pointer-events-none absolute inset-0 w-full h-full"
      aria-hidden="true"
    >
      {mode === 'thirds' && (
        <>
          <line x1={100/3} y1="0" x2={100/3} y2="62.5" stroke="rgba(255,255,255,0.35)" strokeWidth="0.15" />
          <line x1={(100*2)/3} y1="0" x2={(100*2)/3} y2="62.5" stroke="rgba(255,255,255,0.35)" strokeWidth="0.15" />
          <line x1="0" y1={62.5/3} x2="100" y2={62.5/3} stroke="rgba(255,255,255,0.35)" strokeWidth="0.15" />
          <line x1="0" y1={(62.5*2)/3} x2="100" y2={(62.5*2)/3} stroke="rgba(255,255,255,0.35)" strokeWidth="0.15" />
        </>
      )}
      {mode === 'golden' && (
        <>
          {/* φ = 1.618 → 1/φ = 0.618. Trace 4 lignes 0.382 et 0.618. */}
          <line x1={100*0.382} y1="0" x2={100*0.382} y2="62.5" stroke="rgba(251,191,36,0.45)" strokeWidth="0.15" />
          <line x1={100*0.618} y1="0" x2={100*0.618} y2="62.5" stroke="rgba(251,191,36,0.45)" strokeWidth="0.15" />
          <line x1="0" y1={62.5*0.382} x2="100" y2={62.5*0.382} stroke="rgba(251,191,36,0.45)" strokeWidth="0.15" />
          <line x1="0" y1={62.5*0.618} x2="100" y2={62.5*0.618} stroke="rgba(251,191,36,0.45)" strokeWidth="0.15" />
          {/* Spirale stylisée */}
          <path d="M 0 62.5 Q 61.8 62.5 61.8 23.85 T 100 0" stroke="rgba(251,191,36,0.55)" strokeWidth="0.2" fill="none" />
        </>
      )}
      {mode === 'center' && (
        <>
          <line x1="50" y1="0" x2="50" y2="62.5" stroke="rgba(255,255,255,0.4)" strokeWidth="0.15" strokeDasharray="2 1.5" />
          <line x1="0" y1="31.25" x2="100" y2="31.25" stroke="rgba(255,255,255,0.4)" strokeWidth="0.15" strokeDasharray="2 1.5" />
          <circle cx="50" cy="31.25" r="0.6" fill="rgba(255,255,255,0.7)" />
        </>
      )}
    </svg>
  )
}

function DrawingGridToggle({
  mode,
  onChange,
}: {
  mode: 'none' | 'thirds' | 'golden' | 'center'
  onChange: (m: 'none' | 'thirds' | 'golden' | 'center') => void
}) {
  const opts: Array<{ id: 'none' | 'thirds' | 'golden' | 'center'; label: string }> = [
    { id: 'none', label: 'aucune' },
    { id: 'thirds', label: 'tiers' },
    { id: 'golden', label: 'φ doré' },
    { id: 'center', label: 'centré' },
  ]
  return (
    <div className="mt-2 flex items-center gap-1.5">
      <span className="text-[10px] uppercase tracking-wider text-aurora-text-dim mr-2">Grille</span>
      {opts.map((o) => (
        <button
          key={o.id}
          onClick={() => onChange(o.id)}
          className={`rounded-md border px-2 py-0.5 text-[10px] font-mono transition-colors ${
            mode === o.id
              ? 'border-aurora-accent/55 bg-aurora-accent/15 text-aurora-accent-light'
              : 'border-white/10 bg-white/[0.03] text-aurora-text-dim hover:text-aurora-text'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

// v83u — Bouton + popover qui révèle les raccourcis clavier dessin.
function DrawingShortcutsButton() {
  const [open, setOpen] = useState(false)
  const shortcuts = [
    { keys: 'B', desc: 'Pinceau' },
    { keys: 'E', desc: 'Gomme' },
    { keys: 'L', desc: 'Ligne' },
    { keys: 'R', desc: 'Rectangle' },
    { keys: 'C', desc: 'Cercle' },
    { keys: 'I', desc: 'Pipette' },
    { keys: '[ / ]', desc: 'Taille −/+' },
    { keys: 'Cmd+Z', desc: 'Undo' },
    { keys: 'Cmd+Shift+Z', desc: 'Redo' },
    { keys: 'S', desc: 'Smooth toggle' },
    { keys: '?', desc: 'Afficher cette aide' },
  ]
  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        title="Raccourcis clavier (?)"
        className="rounded-md border border-white/10 bg-white/[0.03] px-2 py-0.5 text-[10px] font-mono text-aurora-text-dim hover:text-aurora-text"
      >
        ⌘ ?
      </button>
      {open && (
        <div className="absolute top-7 right-0 z-50 w-56 rounded-xl border border-aurora-border/40 bg-aurora-surface/95 p-3 shadow-2xl backdrop-blur">
          <div className="mb-2 flex items-center justify-between">
            <p className="text-[10px] uppercase tracking-wider text-aurora-text-dim">Raccourcis dessin</p>
            <button
              onClick={() => setOpen(false)}
              className="text-aurora-text-dim hover:text-aurora-text"
              aria-label="Fermer"
            >×</button>
          </div>
          <ul className="space-y-1">
            {shortcuts.map((s, i) => (
              <li key={i} className="flex items-center justify-between text-[11px]">
                <code className="rounded bg-black/40 border border-white/10 px-1.5 py-0.5 font-mono text-[10px] text-aurora-accent-light">{s.keys}</code>
                <span className="text-aurora-text">{s.desc}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

// v83p — Presets de pinceau professionnels : sumi (encre japonaise),
// aquarelle (translucide doux), manga ink (haut contraste), sketch
// graphite (mine légère). Un clic applique size/opacity/color/smooth.
function DrawingBrushPresets({ onPick }: { onPick: (p: { size: number; opacity: number; color: string; smooth: boolean }) => void }) {
  const presets = [
    { id: 'sumi',     label: 'Sumi · 墨',    size: 18, opacity: 0.92, color: '#0b0a08', smooth: true,  swatch: '#0b0a08' },
    { id: 'aquarelle', label: 'Aquarelle',   size: 28, opacity: 0.35, color: '#67a9c2', smooth: true,  swatch: '#9bc8d7' },
    { id: 'manga',    label: 'Manga ink',    size: 4,  opacity: 1.0,  color: '#000000', smooth: true,  swatch: '#000000' },
    { id: 'graphite', label: 'Sketch graph.',size: 3,  opacity: 0.55, color: '#444', smooth: false, swatch: '#666' },
    { id: 'marker',   label: 'Marker plein', size: 14, opacity: 0.95, color: '#ff6a3d', smooth: false, swatch: '#ff6a3d' },
    { id: 'highlight',label: 'Surligneur',   size: 22, opacity: 0.4,  color: '#fff066', smooth: false, swatch: '#fff066' },
  ]
  return (
    <div className="mt-3 rounded-xl border border-aurora-border/25 bg-black/15 p-2">
      <div className="text-[10px] uppercase tracking-wider text-aurora-text-dim mb-2">Brush presets</div>
      <div className="grid grid-cols-3 gap-1.5">
        {presets.map((p) => (
          <button
            key={p.id}
            onClick={() => onPick({ size: p.size, opacity: p.opacity, color: p.color, smooth: p.smooth })}
            className="flex items-center gap-1.5 rounded-md border border-white/10 bg-white/[0.03] px-2 py-1 text-[10px] text-aurora-text-dim hover:bg-white/[0.08] hover:text-aurora-text transition-colors"
          >
            <span style={{ background: p.swatch }} className="h-3 w-3 rounded-full border border-white/30 shrink-0" />
            <span className="truncate">{p.label}</span>
          </button>
        ))}
      </div>
    </div>
  )
}

// v83j — Harmonies de couleur dérivées du brushColor courant.
// Affiche 6 schemes complémentaire/analogue/triadique/tétradique/split/mono,
// chaque scheme cliquable pour switch instantané la palette active.
function DrawingHarmonySuggester({ baseColor, onPick }: { baseColor: string; onPick: (hex: string) => void }) {
  const schemes: Array<{ key: 'complementary' | 'analogous' | 'triadic' | 'tetradic' | 'split-complementary' | 'monochromatic'; label: string }> = [
    { key: 'complementary', label: 'complément.' },
    { key: 'analogous', label: 'analogue' },
    { key: 'triadic', label: 'triade' },
    { key: 'tetradic', label: 'tétrade' },
    { key: 'split-complementary', label: 'split-comp' },
    { key: 'monochromatic', label: 'mono' },
  ]
  // Contrast WCAG vs blanc et noir pour aider à choisir lisibilité.
  const rgb = hexToRgb(baseColor)
  const ratioWhite = rgb ? wcagContrast(rgb, { r: 255, g: 255, b: 255 }) : 0
  const ratioBlack = rgb ? wcagContrast(rgb, { r: 0, g: 0, b: 0 }) : 0
  return (
    <div className="mt-3 rounded-xl border border-aurora-border/25 bg-black/20 p-2 text-[10px]">
      <div className="flex items-center justify-between mb-1.5">
        <span className="uppercase tracking-wider text-aurora-text-dim">Harmonies</span>
        <span className="font-mono text-aurora-text-dim">
          contraste · #fff {ratioWhite.toFixed(1)} · #000 {ratioBlack.toFixed(1)}
        </span>
      </div>
      <div className="space-y-1">
        {schemes.map((s) => {
          const colors = generateHarmony(baseColor, s.key)
          return (
            <div key={s.key} className="flex items-center gap-1.5">
              <span className="w-20 shrink-0 text-aurora-text-dim">{s.label}</span>
              <div className="flex gap-1 flex-1">
                {colors.map((c, i) => (
                  <button
                    key={i}
                    onClick={() => onPick(c)}
                    title={c}
                    style={{ background: c }}
                    className="h-5 w-5 rounded-sm border border-white/15 cursor-pointer hover:scale-110 transition-transform"
                  />
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
