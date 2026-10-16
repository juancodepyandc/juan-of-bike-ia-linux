import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { emitGenerationFx, useGenerationFxEmitter, useGenerationFxResult } from '../components/generationFx/fxBus.ts'
import { waitForComfyImages, type ComfyImageOutput } from '../services/comfyJobMonitor.ts'
import { createFluxWorkflow, getAvailableStyles, type FluxStyle } from '../utils/fluxWorkflow.ts'
import { parseImageIntent, buildNegativePrompt, resolveReferenceDenoise, type ParsedImageIntent } from '../utils/imagePromptParser.ts'
import {
  assembleKontextInstruction,
  buildStagedKontextEditPlan,
  createFluxKontextWorkflow,
  resolveKontextModel,
  shouldUseStagedKontextEditPlan,
  type StitchDirection,
} from '../utils/fluxKontextWorkflow.ts'
import { translateEditInstructionToEnglish } from '../utils/kontextInstructionTranslator.ts'
import {
  detectSubjectToResearch,
  resolveSubjectReference,
  buildAppearanceClause,
} from '../services/selfInformedReference.ts'
import { findMultipleReferenceVisuals, type ReferenceSearchProfile } from '../services/referenceVisualResearch.ts'
import { analyzeImage } from '../services/visionService.ts'
import { VISION_LIVE_MODEL } from '../config/models.ts'
import {
  comfyuiGetHistory,
  comfyuiGetImage,
  comfyuiInterrupt,
  comfyuiQueuePrompt,
  comfyuiRequest,
  comfyuiUploadImage,
  ensureComfyUIRunning,
  freeGpuBeforeFlux,
  ollamaGenerate,
} from '../hooks/useTauri.ts'
import { useAppStore } from '../stores/appStore.ts'
import { useModuleHistoryStore } from '../stores/moduleHistoryStore.ts'
import { computeStreak } from '../utils/streak.ts'
import { useModuleDraftsStore } from '../stores/moduleDraftsStore.ts'
import { saveBlob, loadBlobUrl, pruneOldBlobs } from '../utils/blobStore.ts'
import { RANDOM_IMAGE_PROMPTS, pickRandom as pickRandomCreative } from '../utils/randomCreativePrompts.ts'
import { readHistory, pushHistory, removeHistoryEntry, type PromptHistoryEntry } from '../utils/promptHistory.ts'
import { buildPromptContractBlock, expandHumanImagePromptWithAI, parseBrief } from '../services/imagePromptBuilder.ts'
import {
  buildImageAutocorrectionContract,
  buildImageConversationContext,
  resolveImageConversationStyle,
} from '../services/imageConversationContract.ts'
import {
  claimImageGenerationLock,
  releaseImageGenerationLock,
  renewImageGenerationLock,
} from '../services/imageGenerationSafety.ts'
import type { ConversationSession } from '../stores/moduleHistoryStore.ts'
import { getBridgeUrl, isCloudRuntime, isTauriRuntime } from '../utils/runtime.ts'
import { acquireProject } from '../utils/projectAdmission.ts'


export type GeneratedCard = {
  id: string
  url: string
  prompt: string
  style: FluxStyle
  timestamp: number
  rotation: number
  seed?: number | null
  requestedStyle?: FluxStyle
  styleOverrideReason?: string | null
  sessionId?: string
}

export type QueueImagePromptOptions = {
  promptOverride?: string
  styleOverride?: FluxStyle
}

export type Character = 'natsu' | 'lucy'
export const PORTRAITS: Record<Character, string> = {
  natsu: '/fairy/natsu.png',
  lucy:  '/fairy/lucy.png',
}

export const DIMENSIONS = {
  square: { w: 1024, h: 1024, label: '1:1' },
  portrait: { w: 832, h: 1216, label: '2:3' },
  landscape: { w: 1216, h: 832, label: '3:2' },
} as const
export type DimensionId = keyof typeof DIMENSIONS

function readCharacter(): Character {
  try {
    const v = window.localStorage.getItem('ft-who')
    return v === 'lucy' ? 'lucy' : 'natsu'
  } catch { return 'natsu' }
}

function pickRotation() { return Math.random() * 6 - 3 }

// v86 : reprise conversationnelle. Chaque message assistant encode l'id du
// blob ([id:...]) pour reconstruire la galerie d'une session passee de facon
// robuste (loadBlobUrl survit au reload, l'URL blob non). Fallback sur l'URL
// inline si l'id manque (vieux messages) ou si le blob a ete elague.
const SESSION_IMG_ID_RE = /\[id:([^\]]+)\]/
const SESSION_IMG_URL_RE = /\[image:([^\]]+)\]/i
const SESSION_STYLE_RE = /\bstyle(?:_override)?:([a-z_]+)/i

async function buildSessionCards(session: ConversationSession): Promise<GeneratedCard[]> {
  const cards: GeneratedCard[] = []
  const messages = session.messages
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const m = messages[i]
    if (m.role !== 'assistant') continue
    const cardId = m.content.match(SESSION_IMG_ID_RE)?.[1]?.trim()
    const style = (m.content.match(SESSION_STYLE_RE)?.[1] as FluxStyle) || 'none'
    let promptSource = ''
    for (let j = i - 1; j >= 0; j -= 1) {
      if (messages[j].role === 'user') { promptSource = messages[j].content; break }
    }
    let url: string | null = null
    if (cardId) url = await loadBlobUrl(cardId)
    if (!url) {
      const candidate = m.content.match(SESSION_IMG_URL_RE)?.[1] || m.images?.[0] || null
      if (candidate) url = candidate
    }
    if (!url) continue
    cards.push({
      id: cardId || `sess-${session.id}-${m.timestamp}`,
      url,
      prompt: promptSource,
      style,
      timestamp: m.timestamp,
      rotation: pickRotation(),
    })
  }
  return cards
}

async function waitForComfyOutput(promptId: string, signal: AbortSignal): Promise<ComfyImageOutput[]> {
  return waitForComfyImages(promptId, signal, comfyuiGetHistory)
}

async function imageBlobLooksBlack(blob: Blob): Promise<boolean> {
  if (!blob || typeof createImageBitmap !== 'function') return false
  let bitmap: ImageBitmap | null = null
  try {
    bitmap = await createImageBitmap(blob)
    const canvas = document.createElement('canvas')
    canvas.width = 32
    canvas.height = 32
    const ctx = canvas.getContext('2d', { willReadFrequently: true })
    if (!ctx) return false
    ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
    const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data
    let sumLuma = 0
    let maxRgb = 0
    let count = 0
    for (let i = 0; i < data.length; i += 4) {
      const a = data[i + 3]
      if (a < 4) continue
      const r = data[i]
      const g = data[i + 1]
      const b = data[i + 2]
      sumLuma += 0.2126 * r + 0.7152 * g + 0.0722 * b
      maxRgb = Math.max(maxRgb, r, g, b)
      count += 1
    }
    return count > 0 && sumLuma / count < 2 && maxRgb < 8
  } catch {
    return false
  } finally {
    bitmap?.close()
  }
}

export function useImageViewLogic() {
  const [who, setWho] = useState<Character>(readCharacter)
  useEffect(() => {
    const t = window.setInterval(() => setWho(readCharacter()), 800)
    return () => window.clearInterval(t)
  }, [])

  // v83 : TOUTES les categories exposees — le slice(0, 10) historique cachait
  // sketch, comic, minimalist, cyberpunk, fantasy et retro dans l'UI.
  const styles = useMemo(() => getAvailableStyles(), [])
  // v83+ : modele LLM pour traduire l'instruction d'edition FR->EN avant Kontext.
  const mainModel = useAppStore((s) => s.mainModel)
  const imgDraft = useModuleDraftsStore((s) => s.drafts.image)
  const setImgDraft = useModuleDraftsStore((s) => s.setDraft)

  const [prompt, setPrompt] = useState<string>(() => imgDraft?.prompt ?? '')
  const [negPrompt, setNegPrompt] = useState<string>(() => (imgDraft?.options?.negPrompt as string) ?? '')
  const [showNeg, setShowNeg] = useState<boolean>(() => Boolean((imgDraft?.options?.negPrompt as string) ?? ''))
  const [style, setStyle] = useState<FluxStyle>(() => ((imgDraft?.style as FluxStyle) ?? 'none'))

  useEffect(() => {
    const id = window.setTimeout(() => {
      setImgDraft('image', { prompt, style, options: { negPrompt } })
    }, 200)
    return () => window.clearTimeout(id)
  }, [prompt, style, negPrompt, setImgDraft])

  const [refPreview, setRefPreview] = useState<string | null>(null)
  const [refFilename, setRefFilename] = useState<string | null>(null)
  const [refDenoise, setRefDenoise] = useState(0.7)
  const [refUploading, setRefUploading] = useState(false)
  // v87 : seconde reference = SOURCE d'extraction. Quand elle est presente,
  // l'edition devient une INJECTION multi-image (element de la 2e image inseré
  // dans la 1re via ImageStitch + Kontext). Necessite le moteur Kontext.
  const [refPreview2, setRefPreview2] = useState<string | null>(null)
  const [refFilename2, setRefFilename2] = useState<string | null>(null)
  const [refUploading2, setRefUploading2] = useState(false)
  const [seed, setSeed] = useState<string>(() => (imgDraft?.options?.seed as string) ?? '')
  const [batch, setBatch] = useState<1 | 2 | 3 | 4>(() => ((imgDraft?.options?.batch as 1|2|3|4) ?? 1))
  const [dimensions, setDimensions] = useState<DimensionId>(() =>
    ((imgDraft?.options?.dimensions as DimensionId) ?? 'square')
  )
  useEffect(() => {
    setImgDraft('image', { options: { seed, batch, dimensions } })
  }, [seed, batch, dimensions, setImgDraft])

  const [images, setImages] = useState<GeneratedCard[]>([])
  const [current, setCurrent] = useState<GeneratedCard | null>(null)
  const imageHistorySessions = useModuleHistoryStore((s) => s.sessions)
  const activeImageSessionId = useModuleHistoryStore((s) => s.activeSessionId.image)
  const activeImageSession = useMemo(
    () => useModuleHistoryStore.getState().getActiveSession('image'),
    [activeImageSessionId, imageHistorySessions],
  )
  const recentImageMessages = useMemo(
    () => activeImageSession.messages.slice(-8),
    [activeImageSession],
  )
  const imageStreak = useMemo(() => {
    const ts: number[] = []
    const legacyHist = useModuleHistoryStore.getState().histories['image'] || []
    for (const m of legacyHist) {
      if (m.role === 'assistant' && m.timestamp) ts.push(m.timestamp)
    }
    for (const s of imageHistorySessions) {
      if (s.module !== 'image') continue
      for (const m of s.messages) {
        if (m.role === 'assistant' && m.timestamp) ts.push(m.timestamp)
      }
    }
    return computeStreak(ts)
  }, [imageHistorySessions])
  const [history, setHistory] = useState<PromptHistoryEntry[]>(() => readHistory('image'))
  // v86 : la galerie reflete TOUJOURS la session cible. Session avec images
  // recuperables → elles reapparaissent ; nouvelle session vide → le canvas
  // se vide (vraie bascule de conversation, pas un cumul d'images orphelines).
  const restoreSessionGallery = useCallback(async (session: ConversationSession) => {
    const cards = await buildSessionCards(session)
    setImages(cards.slice(0, 24))
    setCurrent(cards[0] ?? null)
  }, [])
  const onImageSessionChange = useCallback((session: ConversationSession) => {
    // v86 : ouvrir une session de l'historique = VRAIE reprise conversationnelle,
    // plus un simple copier-coller du prompt. On restaure la galerie de cette
    // session (les images reapparaissent, le fil "Continuite active" se met a
    // jour) et on laisse le prompt vide pour CONTINUER l'edition : le prochain
    // message edite l'image courante restauree (Kontext reprend `current`).
    setPrompt('')
    void restoreSessionGallery(session)
  }, [restoreSessionGallery])
  const recallPrompt = useCallback((entry: PromptHistoryEntry) => {
    const sessionId = typeof entry.meta?.sessionId === 'string' ? entry.meta.sessionId : null
    const session = useModuleHistoryStore.getState().openPromptSession('image', entry.prompt, sessionId)
    onImageSessionChange(session)
    if (entry.meta?.style && typeof entry.meta.style === 'string') {
      setStyle(entry.meta.style as FluxStyle)
    }
  }, [onImageSessionChange])
  const removeHistory = useCallback((p: string) => {
    setHistory(removeHistoryEntry('image', p))
  }, [])

  useEffect(() => {
    const id = window.setTimeout(() => {
      const meta = images.map(({ url: _url, ...rest }) => rest)
      setImgDraft('image', { scratch: { gallery: meta } })
    }, 250)
    return () => window.clearTimeout(id)
  }, [images, setImgDraft])

  useEffect(() => {
    let alive = true
    const meta = (imgDraft?.scratch?.gallery as Array<Omit<GeneratedCard, 'url'>> | undefined) ?? []
    if (meta.length === 0) return
    ;(async () => {
      const hydrated: GeneratedCard[] = []
      for (const m of meta) {
        const url = await loadBlobUrl(m.id)
        if (url) hydrated.push({ ...m, url })
      }
      if (alive && hydrated.length > 0) {
        setImages(hydrated)
        setCurrent(hydrated[0])
      }
    })()
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const [resumeBanner, setResumeBanner] = useState<{ minutes: number; text: string } | null>(null)
  useEffect(() => {
    let alive = true
    const raw = (() => { try { return localStorage.getItem('aurora.pendingComfyPrompt.v1') } catch { return null } })()
    if (!raw) return
    let pending: { promptId: string; prompt: string; style: FluxStyle; runSeed: number | null; rotation: number; startedAt: number } | null = null
    try { pending = JSON.parse(raw) } catch { pending = null }
    if (!pending?.promptId) {
      try { localStorage.removeItem('aurora.pendingComfyPrompt.v1') } catch {}
      return
    }
    const elapsedMin = Math.max(0, Math.round((Date.now() - pending.startedAt) / 60_000))
    setResumeBanner({ minutes: elapsedMin, text: pending.prompt })
    const stable = pending
    const controller = new AbortController()
    ;(async () => {
      try {
        const [first] = await waitForComfyOutput(stable.promptId, controller.signal)
        const blob = await comfyuiGetImage(first.filename, first.subfolder)
        if (!alive) return
        if (await imageBlobLooksBlack(blob)) throw new Error('Rendu noir détecté pendant la reprise.')
        const cardId = `img-resume-${Date.now()}`
        const url = await saveBlob(cardId, blob, 'image')
        if (!alive) return
        const card: GeneratedCard = {
          id: cardId, url, prompt: stable.prompt, style: stable.style,
          timestamp: Date.now(), rotation: stable.rotation, seed: stable.runSeed,
        }
        setImages((prev) => [card, ...prev].slice(0, 24))
        setCurrent(card)
        try {
          const currentPending = JSON.parse(localStorage.getItem('aurora.pendingComfyPrompt.v1') || 'null')
          if (currentPending?.promptId === stable.promptId) localStorage.removeItem('aurora.pendingComfyPrompt.v1')
        } catch {}
        setResumeBanner(null)
      } catch (error) {
        if (alive && !controller.signal.aborted) {
          setError(error instanceof Error ? error.message : String(error))
          setResumeBanner(null)
        }
      }
    })()
    return () => { alive = false; controller.abort() }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const [inpaintOpen, setInpaintOpen] = useState(false)
  const [upscaling, setUpscaling] = useState(false)
  const upscaleCurrent = async (scale: 2 | 4 | 8 | 16) => {
    if (!current || upscaling) return
    setUpscaling(true)
    setNotice(
      scale === 16
        ? 'Super-Résolution 16K Ultra-Master (16384px · Pyramide 2 Octaves) en cours…'
        : scale === 8
          ? 'Super-Résolution 8K UHD (8192px) en cours…'
          : `Super-Résolution ${scale}× en cours…`,
    )
    try {
      const mod = await import('../utils/upscaleImage')
      const { url, method, width, height } = await mod.upscaleAuto(current.url, scale)
      const label = scale === 16 ? '16K' : scale === 8 ? '8K' : `x${scale}`
      try {
        const blob = await fetch(url).then((r) => r.blob())
        const newId = `${current.id}-${label}-${method}`
        const savedUrl = await saveBlob(newId, blob, 'image')
        const card: GeneratedCard = { ...current, id: newId, url: savedUrl }
        setImages((prev) => [card, ...prev].slice(0, 24))
        setCurrent(card)
      } catch {
        const card: GeneratedCard = { ...current, id: `${current.id}-${label}-${method}`, url }
        setImages((prev) => [card, ...prev].slice(0, 24))
        setCurrent(card)
      }
      setNotice(`Super-Résolution ${label} terminée : ${width}×${height} px (${method})`)
    } catch (err) {
      console.warn('[upscale]', err)
      setError(err instanceof Error ? err.message : String(err))
    } finally { setUpscaling(false) }
  }

  const applyInpaint = async (newUrl: string) => {
    if (!current) return
    const newId = `inpaint-${Date.now()}`
    try {
      const blob = await fetch(newUrl).then((r) => r.blob())
      const savedUrl = await saveBlob(newId, blob, 'image')
      const card: GeneratedCard = { ...current, id: newId, url: savedUrl }
      setImages((prev) => [card, ...prev].slice(0, 24))
      setCurrent(card)
    } catch {
      const card: GeneratedCard = { ...current, id: newId, url: newUrl }
      setImages((prev) => [card, ...prev].slice(0, 24))
      setCurrent(card)
    }
  }

  const [generating, setGenerating] = useState(false)
  const [progress, setProgress] = useState<string>('')
  const [progressPct, setProgressPct] = useState<number>(0)
  const [currentStep, setCurrentStep] = useState<number>(0)
  const [lastSavedPath, setLastSavedPath] = useState<string | null>(null)
  const [lastExpandedNote, setLastExpandedNote] = useState<string | null>(null)
  useGenerationFxEmitter('image', generating, progress || undefined, progressPct > 0 ? progressPct / 100 : undefined)
  useGenerationFxResult('image', generating, current?.url)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const generationLockRef = useRef(false)
  const activeLockTokenRef = useRef<string | null>(null)
  const activeJobIdRef = useRef<string | null>(null)
  const activeProjectFinishRef = useRef<((status: 'completed' | 'failed' | 'stopped') => Promise<void>) | null>(null)

  const reportImageStep = useCallback((step: 1 | 2 | 3 | 4 | 5, pct: number, label: string, logLine?: string) => {
    const clampedPct = Math.max(2, Math.min(100, Math.round(pct)))
    const stepPrefix = /^Étape\s+\d\/5/i.test(label) ? label : `Étape ${step}/5 · ${label}`
    setCurrentStep(step)
    setProgressPct(clampedPct)
    setProgress(stepPrefix)
    emitGenerationFx('image', {
      active: true,
      phase: stepPrefix,
      progress: clampedPct / 100,
      logLine: logLine ?? stepPrefix,
    })
    const jobId = activeJobIdRef.current
    const mappedPhase = step <= 2 ? 'prepare' : step <= 4 ? 'generate' : 'cleanup'
    if (jobId) {
      useAppStore.getState().setGenerationJob(jobId, {
        status: 'running',
        phase: mappedPhase,
        progress: clampedPct,
        detail: stepPrefix,
      })
    }
    useAppStore.getState().setRuntimeTask({
      active: true,
      module: 'image',
      phase: mappedPhase,
      detail: stepPrefix,
      progress: clampedPct,
    })
  }, [])

  // v83 : moteur d'edition reel. FLUX.1 Kontext dev (instruction editing,
  // preserve identite/composition) si le UNET kontext est installe, sinon
  // fallback img2img latent — approximatif et annonce comme tel dans l'UI.
  const [editEngine, setEditEngine] = useState<'kontext' | 'img2img'>('img2img')
  const kontextRef = useRef<{ checked: boolean; model: string | null }>({ checked: false, model: null })
  const lastEngineRef = useRef<'dev' | 'kontext' | null>(null)
  const detectKontextModel = useCallback(async (): Promise<string | null> => {
    if (kontextRef.current.checked) return kontextRef.current.model
    try {
      const info = await comfyuiRequest('/object_info/UNETLoader') as {
        UNETLoader?: { input?: { required?: { unet_name?: [string[]] } } }
      }
      const names = info?.UNETLoader?.input?.required?.unet_name?.[0]
      const model = resolveKontextModel(Array.isArray(names) ? names : [])
      kontextRef.current = { checked: true, model }
      setEditEngine(model ? 'kontext' : 'img2img')
      return model
    } catch {
      // ComfyUI pas encore joignable — on ne cache pas l'echec, on retentera
      // au moment de la generation (apres ensureComfyUIRunning).
      return null
    }
  }, [])
  useEffect(() => { void detectKontextModel() }, [detectKontextModel])

  const uploadReferenceFile = async (file: File) => {
    const { validateImageFile } = await import('../utils/textFileExtract')
    const sizeErr = validateImageFile(file)
    if (sizeErr) { setError(sizeErr); return }
    setRefUploading(true)
    setError(null)
    try {
      const up = await ensureComfyUIRunning()
      if (!up.ok) throw new Error(up.error || 'ComfyUI indisponible')
      const res = await comfyuiUploadImage(file, `ref_${Date.now()}_${file.name}`)
      setRefFilename(res.name)
      setRefPreview(URL.createObjectURL(file))
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setRefUploading(false)
    }
  }
  const onUploadReference = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    try {
      await uploadReferenceFile(file)
    } finally {
      e.target.value = ''
    }
  }
  const clearReference = () => {
    if (refPreview) URL.revokeObjectURL(refPreview)
    setRefPreview(null)
    setRefFilename(null)
  }

  // v87 : seconde reference (source d'extraction multi-image).
  const uploadSourceFile = async (file: File) => {
    const { validateImageFile } = await import('../utils/textFileExtract')
    const sizeErr = validateImageFile(file)
    if (sizeErr) { setError(sizeErr); return }
    setRefUploading2(true)
    setError(null)
    try {
      const up = await ensureComfyUIRunning()
      if (!up.ok) throw new Error(up.error || 'ComfyUI indisponible')
      const res = await comfyuiUploadImage(file, `src_${Date.now()}_${file.name}`)
      setRefFilename2(res.name)
      setRefPreview2(URL.createObjectURL(file))
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setRefUploading2(false)
    }
  }
  const onUploadSource = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    try {
      await uploadSourceFile(file)
    } finally {
      e.target.value = ''
    }
  }
  const clearSource = () => {
    if (refPreview2) URL.revokeObjectURL(refPreview2)
    setRefPreview2(null)
    setRefFilename2(null)
  }

  const { pushMessage } = useModuleHistoryStore()

  const randomImagePreset = useCallback(() => {
    const stylesAvail = getAvailableStyles().map((s) => s.id) as FluxStyle[]
    if (stylesAvail.length === 0) return null
    const nextStyle = pickRandomCreative(stylesAvail, style)
    const nextPrompt = pickRandomCreative(RANDOM_IMAGE_PROMPTS)
    setStyle(nextStyle)
    setPrompt(nextPrompt)
    return { promptOverride: nextPrompt, styleOverride: nextStyle } satisfies QueueImagePromptOptions
  }, [style])

  const queuePrompt = useCallback(async (options: QueueImagePromptOptions = {}) => {
    const text = (options.promptOverride ?? prompt).trim()
    const styleForRun = options.styleOverride ?? style
    if (!text || generationLockRef.current) return
    const lockToken = claimImageGenerationLock(text)
    if (!lockToken) {
      setNotice('Un rendu image est déjà en cours dans Aurora. Utilise le bouton « Arrêter » ou « Reprendre à neuf » pour repartir proprement.')
      return
    }
    activeLockTokenRef.current = lockToken
    const lockHeartbeat = setInterval(() => renewImageGenerationLock(lockToken), 60_000)
    generationLockRef.current = true
    setError(null)
    setNotice(null)
    setLastSavedPath(null)
    setGenerating(true)
    abortRef.current = new AbortController()
    const ac = abortRef.current
    let finalProgressAfterCleanup = ''

    const jobId = `image_${Date.now().toString(36)}`
    activeJobIdRef.current = jobId
    useAppStore.getState().addGenerationJob({
      id: jobId,
      module: 'image',
      title: `Rendu Image FLUX (${styleForRun === 'none' ? 'auto' : styleForRun}) — « ${text.slice(0, 80)} »`,
      status: 'running',
      phase: 'prepare',
      progress: 5,
      detail: 'Étape 1/5 · Vérification de ComfyUI & préparation de la mission…',
      services: ['comfyui'],
      model: mainModel || 'FLUX.1',
      createdAt: Date.now(),
      startedAt: Date.now(),
      finishedAt: null,
      error: null,
      history: [],
    })
    useAppStore.getState().setRuntimeTask({
      active: true,
      module: 'image',
      title: `Image FLUX · « ${text.slice(0, 72)} »`,
      phase: 'prepare',
      detail: 'Étape 1/5 · Vérification de ComfyUI & préparation de la mission…',
      progress: 5,
      startedAt: Date.now(),
      finishedAt: null,
      services: ['comfyui'],
      error: null,
    })

    // Enregistrement de la mission dans la file d'attente PC (non-bloquant si hors-ligne)
    activeProjectFinishRef.current = null
    void acquireProject(
      {
        request_id: jobId,
        module: 'image',
        title: `Image · ${text.slice(0, 110)}`,
        model: mainModel || 'FLUX.1',
      },
      (waitMsg) => {
        if (!ac.signal.aborted) {
          reportImageStep(1, 6, waitMsg, waitMsg)
        }
      },
      ac.signal,
    ).then((finishFn) => {
      if (ac.signal.aborted) {
        void finishFn('stopped').catch(() => {})
      } else {
        activeProjectFinishRef.current = finishFn
      }
    }).catch(() => {
      // Ne jamais bloquer le rendu local si l'API /api/projects est indisponible
    })

    reportImageStep(1, 8, 'Analyse du prompt & vérification de ComfyUI…', 'Étape 1/5 démarrée : vérification du serveur ComfyUI')

    try {
      const up = await ensureComfyUIRunning()
      if (!up.ok) throw new Error(up.error || 'ComfyUI indisponible')

      const hasReferenceCandidate = Boolean(refFilename || current)
      const intent = parseImageIntent(text, { hasReference: hasReferenceCandidate })
      const cleanedText = intent.cleanedPrompt
      const activeSessionAtStart = useModuleHistoryStore.getState().getActiveSession('image')
      const previousMessages = useModuleHistoryStore.getState().getRecentMessages('image', 6)
      const conversationContext = buildImageConversationContext(previousMessages)
      const styleResolution = resolveImageConversationStyle({
        style: styleForRun,
        prompt: text,
        hasReference: hasReferenceCandidate,
        isEditIntent: intent.isEditIntent,
      })
      const effectiveStyle = styleResolution.style
      const sessionContract = buildImageAutocorrectionContract({
        prompt: text,
        hasReference: hasReferenceCandidate,
        conversationContext,
      })

      // Si une image de référence est présente (reproduction "fais-moi ce personnage"
      // ou modification/changement de style), on extrait ses caractéristiques visuelles
      // réelles via Vision avant d'enrichir le prompt pour ne rien halluciner.
      let referenceVisionSummary = ''
      const refUrlForVision = refPreview || (current && (intent.isEditIntent || intent.editMode === 'replicate') ? current.url : null)
      if (refUrlForVision && !ac.signal.aborted) {
        try {
          reportImageStep(1, 12, 'Analyse visuelle du personnage / sujet de référence…', 'Inspection Vision de l’image de référence pour fidélité maximale')
          const refResp = await fetch(refUrlForVision, { signal: ac.signal })
          if (refResp.ok) {
            const refBlob = await refResp.blob()
            const visionRes = await analyzeImage(
              { kind: 'blob', data: refBlob },
              {
                task: 'describe_reference',
                userPrompt: `Exact visual appearance, character traits, outfit, colors, pose, and composition for: ${text}`,
                language: 'fr',
                preferQuality: false,
                signal: ac.signal,
              },
            )
            if (visionRes?.description) {
              referenceVisionSummary = visionRes.description
            }
          }
        } catch {
          // Best-effort vision analysis
        }
      }

      reportImageStep(
        1,
        16,
        'Développement IA du prompt (sujet, décor cohérent & lumière)…',
        'Enrichissement intelligent de la demande humaine (aucun fond laissé vide)',
      )
      const humanExpansion = await expandHumanImagePromptWithAI(cleanedText, {
        mode: intent.editMode === 'replicate'
          ? 'replicate'
          : intent.isEditIntent
            ? (styleForRun !== 'none' ? 'style_transfer' : 'edit')
            : 'create',
        requestedStyle: effectiveStyle,
        hasReference: hasReferenceCandidate,
        referenceVisionSummary,
        conversationContext,
        generateText: mainModel ? (p) => ollamaGenerate(mainModel, p, { signal: ac.signal }) : undefined,
      })
      setLastExpandedNote(humanExpansion.sceneCompletionNote)

      const promptContract = buildPromptContractBlock(parseBrief(text))
      const workflowPrompt = [
        humanExpansion.expandedPrompt,
        promptContract,
        sessionContract,
      ].filter(Boolean).join('\n\n')

      if (styleResolution.overrideReason) {
        reportImageStep(1, 19, styleResolution.overrideReason, styleResolution.overrideReason)
      }

      const mergedNegative = buildNegativePrompt(negPrompt, intent.removals)
      const editDenoise = resolveReferenceDenoise(intent, refDenoise, effectiveStyle)
      const targetToResearch = detectSubjectToResearch(text, intent)

      let groundedReference: { filename: string; denoise?: number } | null = refFilename
        ? {
            filename: refFilename,
            denoise: intent.isEditIntent ? editDenoise : refDenoise,
          }
        : null

      if (!groundedReference && current && (intent.isEditIntent || refFilename2)) {
        try {
          reportImageStep(2, 23, 'Préparation de l’image actuelle comme référence…', 'Étape 2/5 : chargement de l’image courante comme référence')
          const response = await fetch(current.url, { signal: ac.signal })
          if (response.ok) {
            const blob = await response.blob()
            const file = new File([blob], `aurora_current_${Date.now()}.png`, { type: blob.type || 'image/png' })
            const uploaded = await comfyuiUploadImage(file)
            if (uploaded?.name) groundedReference = { filename: uploaded.name, denoise: editDenoise }
          }
        } catch {
        }
      }

      // iter32 (quête 10/10): l'auto-référence web n'est déclenchée que pour
      // un sujet SPÉCIFIQUE nommé (targetToResearch — personnage/objet à
      // rendre fidèlement) ou un mode replicate explicite.
      if (!groundedReference && (intent.editMode === 'replicate' || (targetToResearch !== null && !intent.isEditIntent))) {
        try {
          reportImageStep(2, 26, 'Recherche de référence visuelle vérifiée…', 'Étape 2/5 : recherche de référence visuelle pour le sujet nommé')
          let foundBlob: Blob | null = null
          try {
            const { searchReferenceImages } = await import('../services/auroraExtensionBridge')
            const refResult = await searchReferenceImages(cleanedText, { limit: 1, signal: ac.signal })
            if (refResult.ok && refResult.data.length > 0) {
              const response = await fetch(refResult.data[0].url, { signal: ac.signal })
              if (response.ok) foundBlob = await response.blob()
            }
          } catch {}

          if (!foundBlob) {
            const { findBestReferenceVisual } = await import('../services/referenceVisualResearch')
            const selection = await findBestReferenceVisual({
              prompt: cleanedText,
              model: VISION_LIVE_MODEL,
              queries: [cleanedText],
            })
            if (selection?.blob) foundBlob = selection.blob
          }

          if (foundBlob) {
            const file = new File([foundBlob], `aurora_ref_${Date.now()}.png`, { type: foundBlob.type || 'image/png' })
            const uploaded = await comfyuiUploadImage(file)
            if (uploaded?.name) groundedReference = { filename: uploaded.name, denoise: intent.editMode === 'replicate' ? 0.30 : 0.40 }
          }
        } catch {}
      }

      const parsedSeed = seed.trim() ? Number(seed.trim()) : null
      const baseSeed = (parsedSeed !== null && !Number.isNaN(parsedSeed)) ? parsedSeed : null

      // v88 : AUTO-INFORMATION. Pour un sujet SPÉCIFIQUE (personnage/objet nommé à
      // ajouter, ou environnement/lieu nommé pour une scène), Aurora s'informe au
      // lieu d'inventer : elle recherche une VRAIE référence (image vérifiée
      // "bon sujet" par le modèle vision + description vision précise). L'image
      // trouvée d'un sujet à AJOUTER devient la 2e référence Kontext (injection
      // stitch) → fidélité réelle, fini le "Jax lapin violet générique". Tout
      // ceci AVANT le swap mémoire FLUX (comme la traduction).
      let entityClause = ''
      let autoSecondReference: string | null = null
      if (targetToResearch) {
        const target = targetToResearch
        if (target) {
          try {
            const resolved = await resolveSubjectReference(target, {
              fetchReferenceImages: async (queries, profile) => {
                const selections = await findMultipleReferenceVisuals({
                  prompt: profile.subjectLabel,
                  model: VISION_LIVE_MODEL,
                  queries,
                  profile: profile as unknown as ReferenceSearchProfile,
                  maxResults: 3,
                })
                const refs: Array<{ comfyFilename: string | null; blob: Blob; sourceUrl?: string; score?: number }> = []
                for (const selection of selections) {
                  if (!selection?.blob) continue
                  try {
                    const file = new File([selection.blob], `autoref_${Date.now()}_${refs.length}.png`, { type: selection.blob.type || 'image/png' })
                    const up = await comfyuiUploadImage(file)
                    refs.push({ comfyFilename: up?.name ?? null, blob: selection.blob, sourceUrl: selection.pageUrl, score: selection.score })
                  } catch {
                    refs.push({ comfyFilename: null, blob: selection.blob, sourceUrl: selection.pageUrl, score: selection.score })
                  }
                }
                return refs
              },
              fetchReferenceImage: async (queries, profile) => {
                const selection = (await findMultipleReferenceVisuals({
                  prompt: profile.subjectLabel,
                  model: VISION_LIVE_MODEL,
                  queries,
                  profile: profile as unknown as ReferenceSearchProfile,
                  maxResults: 1,
                }))[0]
                if (!selection?.blob) return null
                try {
                  const file = new File([selection.blob], `autoref_${Date.now()}.png`, { type: selection.blob.type || 'image/png' })
                  const up = await comfyuiUploadImage(file)
                  return { comfyFilename: up?.name ?? null, blob: selection.blob, sourceUrl: selection.pageUrl, score: selection.score }
                } catch {
                  return { comfyFilename: null, blob: selection.blob, sourceUrl: selection.pageUrl, score: selection.score }
                }
              },
              describeReferenceImage: async (ref, t, signal) => {
                if (!ref.blob) return ''
                const res = await analyzeImage(
                  { kind: 'blob', data: ref.blob },
                  { task: 'describe_reference', userPrompt: `the exact visual appearance of ${t.searchLabel || t.subject}`, language: 'fr', preferQuality: false, signal },
                )
                return res?.description ?? ''
              },
              generate: (m, p) => ollamaGenerate(m, p, { signal: ac.signal }),
              textModel: mainModel,
              signal: ac.signal,
              onProgress: setProgress,
            })
            if (resolved.appearanceDescription) entityClause = buildAppearanceClause(target, resolved.appearanceDescription)
            // NB: pas d'AUTO-stitch de l'image trouvée — un sujet isolé sur fond
            // neutre fait "collapser" Kontext (il recrache la référence au lieu
            // d'éditer la base). La description consensus précise suffit en
            // mono-image et PRÉSERVE la scène. Le stitch reste pour le 2e slot manuel.
            void autoSecondReference
            if (resolved.advisory) setNotice(resolved.advisory)
          } catch {
            // best effort : on continue la generation sans enrichissement
          }
        }
      }

      // v87 : injection multi-image — référence MANUELLE (2e slot) OU image
      // AUTO-RECHERCHÉE du sujet à ajouter. Déclenche le stitch même sans verbe
      // d'ajout explicite. Requiert une base + le moteur Kontext.
      const effectiveSecondReference = refFilename2 || autoSecondReference
      const injection = Boolean(effectiveSecondReference && groundedReference)
      const wantsKontextEdit = intent.isEditIntent || injection

      // v83 : edition reelle. Si l'intention est un edit (ou une injection) ET
      // qu'une reference existe ET que le UNET Kontext est installe → workflow
      // Kontext (instruction editing, denoise 1.0 via ReferenceLatent). Sinon
      // fallback img2img legacy avec son contrat de denoise.
      const kontextModel = (groundedReference && wantsKontextEdit)
        ? await detectKontextModel()
        : null
      const useKontext = Boolean(kontextModel && groundedReference && wantsKontextEdit)

      // v83 : swap dev ↔ kontext = 2 UNET de 11-16 GB. Sans /free, ComfyUI
      // garde l'ancien en cache RAM pendant le chargement du nouveau.
      // v83+ : FLUX.1 Kontext n'obeit bien qu'en ANGLAIS. On traduit l'instruction
      // d'edition FR->EN AVANT le swap memoire (donc avant que Kontext occupe la
      // VRAM) — lexique deterministe pour les cas courants, LLM seulement si du
      // francais subsiste. Sans ca, "ajoute un noeud papillon" etait ignore.
      let kontextEnglishCore: string | undefined
      if (useKontext) {
        reportImageStep(2, 29, 'Traduction de la demande d’édition (moteur Kontext)…', 'Étape 2/5 : traduction de l’instruction pour FLUX.1 Kontext')
        try {
          kontextEnglishCore = await translateEditInstructionToEnglish(text, {
            generate: (m, p) => ollamaGenerate(m, p, { signal: ac.signal }),
            model: mainModel,
            signal: ac.signal,
          })
        } catch {
          kontextEnglishCore = undefined
        }
      }

      let stagedReplacementPlan: ReturnType<typeof buildStagedKontextEditPlan> | null = null
      if (useKontext && groundedReference && shouldUseStagedKontextEditPlan(intent, { rawPrompt: text, injection })) {
        reportImageStep(2, 31, 'Planification multi-étage : suppression, reconstruction, placement…', 'Étape 2/5 : planification multi-étage Kontext')
        let removeEnglishCore: string | undefined
        let addEnglishCore: string | undefined
        try {
          removeEnglishCore = await translateEditInstructionToEnglish(
            `suppression complete de ${intent.removals.join(' et ')}`,
            {
              generate: (m, p) => ollamaGenerate(m, p, { signal: ac.signal }),
              model: mainModel,
              signal: ac.signal,
            },
          )
        } catch {
          removeEnglishCore = undefined
        }
        try {
          addEnglishCore = await translateEditInstructionToEnglish(
            `ajoute ${intent.additions.join(' et ')}`,
            {
              generate: (m, p) => ollamaGenerate(m, p, { signal: ac.signal }),
              model: mainModel,
              signal: ac.signal,
            },
          )
        } catch {
          addEnglishCore = undefined
        }
        stagedReplacementPlan = buildStagedKontextEditPlan({
          rawPrompt: text,
          intent,
          englishCore: kontextEnglishCore,
          removeEnglishCore,
          addEnglishCore,
          entityClause,
        })
      }

      const engine: 'dev' | 'kontext' = useKontext ? 'kontext' : 'dev'
      reportImageStep(2, 34, 'Libération mémoire GPU avant diffusion FLUX…', 'Étape 2/5 terminée : bascule VRAM vers ComfyUI FLUX')
      await freeGpuBeforeFlux(Array.from(new Set([mainModel].filter(Boolean))))
      lastEngineRef.current = engine

      try {
        const lastMessage = activeSessionAtStart.messages[activeSessionAtStart.messages.length - 1]
        if (!(lastMessage?.role === 'user' && lastMessage.content.trim() === text)) {
          pushMessage('image', { role: 'user', content: text })
        }
      } catch {
      }

      for (let k = 0; k < batch; k++) {
        if (ac.signal.aborted) break
        const runSeed = baseSeed !== null
          ? (baseSeed + k * 10007) % 1_000_000_000_000_000
          : Math.floor(Math.random() * 900_000_000_000_000) + 100_000_000_000_000 + k * 10007
        reportImageStep(
          3,
          36,
          batch > 1 ? `Construction du workflow FLUX (${k + 1}/${batch})…` : 'Construction du workflow FLUX (28 pas)…',
          `Étape 3/5 : lancement du graphe FLUX (seed ${runSeed})`,
        )
        const dim = DIMENSIONS[dimensions]
        let blob: Blob | null = null
        let comfyFilename: string | undefined
        if (useKontext && groundedReference && kontextModel && stagedReplacementPlan) {
          let activeReferenceFilename = groundedReference.filename
          for (let stageIndex = 0; stageIndex < stagedReplacementPlan.stages.length; stageIndex += 1) {
            const stage = stagedReplacementPlan.stages[stageIndex]
            reportImageStep(
              4,
              81 + stageIndex * 4,
              batch > 1 ? `${stage.progressLabel} (${k + 1}/${batch})` : stage.progressLabel,
              `Étape 4/5 : ${stage.label}`,
            )
            const stageWorkflow = createFluxKontextWorkflow({
              instruction: stage.instruction,
              referenceFilename: activeReferenceFilename,
              secondReferenceFilename: null,
              stitchDirection: 'right',
              unetName: kontextModel,
              filenamePrefix: `aurora_stage_${Date.now()}_${k}_stage${stageIndex + 1}`,
              seed: runSeed !== null ? runSeed + stageIndex : null,
              steps: 28,
              width: dim.w,
              height: dim.h,
            })
            const queueResponse = await comfyuiQueuePrompt(stageWorkflow)
            const parsed = typeof queueResponse === 'string' ? JSON.parse(queueResponse) : queueResponse
            const promptId = parsed?.prompt_id as string | undefined
            if (!promptId) throw new Error('ComfyUI n\'a pas retourné de prompt_id')

            try {
              localStorage.setItem('aurora.pendingComfyPrompt.v1', JSON.stringify({
                promptId,
                prompt: `${text}\n${stage.label}`,
                style: effectiveStyle,
                runSeed: runSeed !== null ? runSeed + stageIndex : null,
                rotation: pickRotation(),
                startedAt: Date.now(),
              }))
            } catch {
            }

            reportImageStep(
              4,
              83 + stageIndex * 4,
              batch > 1 ? `${stage.label} ${k + 1}/${batch} — diffusion en cours…` : `${stage.label} — diffusion en cours…`,
            )
            const filenames = await waitForComfyOutput(promptId, ac.signal)
            const first = filenames[0]
            const stageBlob = await comfyuiGetImage(first.filename, first.subfolder)
            comfyFilename = first.filename
            if (await imageBlobLooksBlack(stageBlob)) {
              throw new Error('Rendu noir detecte pendant le workflow multi-etage Kontext.')
            }
            if (stageIndex < stagedReplacementPlan.stages.length - 1) {
              const stagedFile = new File(
                [stageBlob],
                `aurora_stage_${Date.now()}_${k}_${stageIndex + 1}.png`,
                { type: stageBlob.type || 'image/png' },
              )
              const uploaded = await comfyuiUploadImage(stagedFile)
              if (!uploaded?.name) throw new Error('ComfyUI n\'a pas accepte l\'image intermediaire du workflow multi-etage')
              activeReferenceFilename = uploaded.name
            } else {
              blob = stageBlob
            }
          }
        }

        let pendingPromptId: string | undefined
        if (!blob) {
        const workflow = useKontext && groundedReference && kontextModel
          ? createFluxKontextWorkflow({
              instruction: assembleKontextInstruction({
                rawPrompt: text,
                intent,
                englishCore: kontextEnglishCore,
                entityClause,
                injection,
              }),
              referenceFilename: groundedReference.filename,
              secondReferenceFilename: injection ? effectiveSecondReference : null,
              stitchDirection: 'right',
              unetName: kontextModel,
              filenamePrefix: `aurora_image_${Date.now()}_${k}`,
              seed: runSeed,
              steps: 28,
              width: dim.w,
              height: dim.h,
            })
          : createFluxWorkflow({
              prompt: [workflowPrompt, entityClause].filter(Boolean).join('\n\n'),
              negativePrompt: mergedNegative,
              style: effectiveStyle,
              width: dim.w,
              height: dim.h,
              steps: 28,
              filenamePrefix: `aurora_image_${Date.now()}_${k}`,
              referenceImage: groundedReference,
              seed: runSeed,
              editIntent: intent,
            })

        reportImageStep(
          useKontext ? 4 : 3,
          useKontext ? 82 : 38,
          useKontext
            ? (batch > 1 ? `Édition Kontext ${k + 1}/${batch} — envoi à ComfyUI…` : 'Édition Kontext (modification réelle sans hallucination)…')
            : (batch > 1 ? `Diffusion FLUX ${k + 1}/${batch} — envoi à ComfyUI…` : 'Diffusion FLUX — envoi du workflow 28 pas à ComfyUI…'),
        )
        const queueResponse = await comfyuiQueuePrompt(workflow)
        const parsed = typeof queueResponse === 'string' ? JSON.parse(queueResponse) : queueResponse
        const promptId = parsed?.prompt_id as string | undefined
        if (!promptId) throw new Error('ComfyUI n\'a pas retourné de prompt_id')
        pendingPromptId = promptId

        try {
          localStorage.setItem('aurora.pendingComfyPrompt.v1', JSON.stringify({
            promptId, prompt: text, style: effectiveStyle, runSeed, rotation: pickRotation(), startedAt: Date.now(),
          }))
        } catch {
        }

        reportImageStep(
          useKontext ? 4 : 3,
          useKontext ? 85 : 42,
          batch > 1 ? `Diffusion FLUX (${k + 1}/${batch}) — calcul des 28 pas…` : 'Diffusion FLUX en cours (28 pas neuronaux)…',
          `Exécution ComfyUI #${promptId.slice(0, 8)} en cours`,
        )
        const filenames = await waitForComfyOutput(promptId, ac.signal)

        reportImageStep(
          5,
          93,
          batch > 1 ? `Décodage VAE & récupération de l'image ${k + 1}/${batch}…` : 'Décodage VAE & contrôle qualité anti-écran-noir…',
          'Étape 5/5 : récupération du PNG et vérification d’intégrité',
        )
        const first = filenames[0]
        blob = await comfyuiGetImage(first.filename, first.subfolder)
        comfyFilename = first.filename
        }
        if (!blob) throw new Error('Aucune image produite par le workflow')
        // v83 : pixel art authentique garanti — FLUX seul produit du pseudo
        // pixel art (grille irreguliere, degrades). Post-process mecanique :
        // downsample grille entiere + palette indexee + upscale nearest.
        if (effectiveStyle === 'pixel_art') {
          try {
            reportImageStep(5, 95, 'Verrouillage pixel art (grille + palette)…', 'Post-traitement grille pixel-art authentique')
            const mod = await import('../utils/pixelArtEnforcer')
            blob = await mod.enforcePixelArtBlob(blob, mod.parsePixelArtOptions(text))
          } catch {
            // jamais bloquer la livraison pour un post-process
          }
        }
        if (await imageBlobLooksBlack(blob)) {
          throw new Error('Rendu noir detecte: ComfyUI a termine sans erreur mais le PNG est inutilisable. Aurora a libere la memoire; relance avec moins de batch/steps ou verifie les logs Comfy.')
        }
        const cardId = `img-${Date.now()}-${k}`
        const url = await saveBlob(cardId, blob, 'image')
        try {
          const pending = JSON.parse(localStorage.getItem('aurora.pendingComfyPrompt.v1') || 'null')
          if (pendingPromptId && pending?.promptId === pendingPromptId) {
            localStorage.removeItem('aurora.pendingComfyPrompt.v1')
          }
        } catch {}
        const card: GeneratedCard = {
          id: cardId, url,
          prompt: text,
          style: effectiveStyle,
          requestedStyle: styleForRun !== effectiveStyle ? styleForRun : undefined,
          styleOverrideReason: styleResolution.overrideReason,
          timestamp: Date.now(),
          rotation: pickRotation(),
          seed: runSeed,
          sessionId: activeSessionAtStart.id,
        }
        setImages((prev) => [card, ...prev].slice(0, 24))
        setCurrent(card)
        void pruneOldBlobs('image', 24)

        try {
          const styleNote = styleForRun !== effectiveStyle ? ` requested_style:${styleForRun} style_override:${effectiveStyle}` : ` style:${effectiveStyle}`
          const overrideNote = styleResolution.overrideReason ? ` reason:${styleResolution.overrideReason}` : ''
          const engineNote = stagedReplacementPlan ? 'kontext-staged' : (useKontext ? 'kontext' : 'img2img')
          pushMessage('image', {
            role: 'assistant',
            content: `[image:${url}][id:${cardId}]${styleNote}${runSeed !== null ? ` seed:${runSeed}` : ''}${intent.isEditIntent ? ` edit:${intent.editMode} engine:${engineNote}` : ''}${overrideNote}`,
            images: [url],
          })
        } catch {
        }

        // Persistance disque unifiée : output/image/creations/ (fini la dispersion
        // confuse entre assets, decor, perso, edits, etc.) + sous-dossier de session.
        try {
          if (typeof window !== 'undefined' && comfyFilename) {
            const persistContext = (!isTauriRuntime() && isCloudRuntime()) ? 'tunnel' : 'ui'
            const bridge = getBridgeUrl()
            reportImageStep(5, 98, 'Sauvegarde dans le dossier unifié output/image/creations/…')
            const persistResp = await fetch(`${bridge}/api/image/persist`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                filename: comfyFilename,
                context: persistContext,
                sessionId: activeSessionAtStart?.id || 'general',
                mode: intent.isEditIntent ? intent.editMode : 'creation',
                prompt: text,
                timestamp: Date.now(),
              }),
            })
            if (persistResp.ok) {
              const persistData = await persistResp.json().catch(() => null)
              if (persistData?.saved_rel) {
                setLastSavedPath(persistData.saved_rel as string)
              }
            }
          }
        } catch {
        }
      }

      setProgress('Étape 5/5 · Terminé')
      setProgressPct(100)
      finalProgressAfterCleanup = 'Prêt'
      const activeSession = useModuleHistoryStore.getState().getActiveSession('image')
      setHistory(pushHistory('image', text, { style: effectiveStyle, sessionId: activeSession.id, requestedStyle: styleForRun }))
      if (batch === 1) setPrompt('')
      if (activeJobIdRef.current) {
        useAppStore.getState().setGenerationJob(activeJobIdRef.current, {
          status: 'done',
          phase: 'done',
          progress: 100,
          finishedAt: Date.now(),
          detail: 'Étape 5/5 · Image générée et sauvegardée dans output/image/creations/',
        })
      }
      useAppStore.getState().setRuntimeTask({
        active: false,
        module: 'image',
        phase: 'done',
        detail: 'Image générée avec succès.',
        progress: 100,
        finishedAt: Date.now(),
      })
      const finishOk = activeProjectFinishRef.current as ((status: 'completed' | 'failed' | 'stopped') => Promise<void>) | null
      if (finishOk) {
        void finishOk('completed').catch(() => {})
        activeProjectFinishRef.current = null
      }
    } catch (err) {
      if ((err as Error)?.name === 'AbortError' || ac.signal.aborted) {
        setProgress('Arrêté')
        setProgressPct(0)
        finalProgressAfterCleanup = 'Arrêté'
        if (activeJobIdRef.current) {
          useAppStore.getState().setGenerationJob(activeJobIdRef.current, {
            status: 'cancelled',
            phase: 'done',
            progress: 100,
            finishedAt: Date.now(),
            detail: 'Génération arrêtée par l’utilisateur.',
          })
        }
        useAppStore.getState().resetRuntimeTask()
        const finishStopped = activeProjectFinishRef.current as ((status: 'completed' | 'failed' | 'stopped') => Promise<void>) | null
        if (finishStopped) {
          void finishStopped('stopped').catch(() => {})
          activeProjectFinishRef.current = null
        }
      } else {
        const msg = err instanceof Error ? err.message : String(err)
        setError(msg)
        setProgress('')
        setProgressPct(0)
        if (activeJobIdRef.current) {
          useAppStore.getState().setGenerationJob(activeJobIdRef.current, {
            status: 'error',
            phase: 'error',
            progress: 100,
            finishedAt: Date.now(),
            error: msg,
            detail: msg,
          })
        }
        useAppStore.getState().setRuntimeTask({
          active: false,
          module: 'image',
          phase: 'error',
          detail: msg,
          error: msg,
          finishedAt: Date.now(),
        })
        const finishFailed = activeProjectFinishRef.current as ((status: 'completed' | 'failed' | 'stopped') => Promise<void>) | null
        if (finishFailed) {
          void finishFailed('failed').catch(() => {})
          activeProjectFinishRef.current = null
        }
      }
    } finally {
      // Libérer immédiatement le verrou et l'état UI AVANT le nettoyage mémoire GPU
      // pour que le bouton Arrêter / Reprendre à neuf soit instantané et ne bloque jamais.
      clearInterval(lockHeartbeat)
      releaseImageGenerationLock(lockToken)
      activeLockTokenRef.current = null
      generationLockRef.current = false
      abortRef.current = null
      setGenerating(false)
      setCurrentStep(0)
      setProgress(finalProgressAfterCleanup)
      void freeGpuBeforeFlux(Array.from(new Set([mainModel].filter(Boolean)))).catch(() => {})
    }
  }, [prompt, style, pushMessage, negPrompt, refFilename, refFilename2, refPreview, refDenoise, seed, batch, dimensions, current, detectKontextModel, mainModel, reportImageStep])

  const onStop = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    try { localStorage.removeItem('aurora.pendingComfyPrompt.v1') } catch {}
    setResumeBanner(null)
    if (activeLockTokenRef.current) {
      releaseImageGenerationLock(activeLockTokenRef.current)
      activeLockTokenRef.current = null
    } else {
      try { localStorage.removeItem('aurora.image.lock.v1') } catch {}
    }
    generationLockRef.current = false
    setGenerating(false)
    setCurrentStep(0)
    setProgressPct(0)
    setProgress('Arrêté — prêt à relancer')
    emitGenerationFx('image', { active: false })
    if (activeJobIdRef.current) {
      useAppStore.getState().setGenerationJob(activeJobIdRef.current, {
        status: 'cancelled',
        phase: 'done',
        progress: 100,
        finishedAt: Date.now(),
        detail: 'Génération arrêtée immédiatement par l’utilisateur.',
      })
    }
    useAppStore.getState().resetRuntimeTask()
    const finishStopNow = activeProjectFinishRef.current as ((status: 'completed' | 'failed' | 'stopped') => Promise<void>) | null
    if (finishStopNow) {
      void finishStopNow('stopped').catch(() => {})
      activeProjectFinishRef.current = null
    }
    void comfyuiInterrupt()
  }, [])

  // Écoute le bouton "■ Arrêter la génération" de l'animation plein écran (GenerationFxHost)
  // ainsi que le bouton d'arrêt depuis "Projets et file d'attente" (ProjectsPanel).
  useEffect(() => {
    const onFxStop = (ev: Event) => {
      const mod = (ev as CustomEvent<{ module?: string }>)?.detail?.module
      if (!mod || mod === 'image') {
        onStop()
      }
    }
    window.addEventListener('aurora-fx-stop', onFxStop)
    return () => window.removeEventListener('aurora-fx-stop', onFxStop)
  }, [onStop])

  // "Reprendre à neuf" : arrête tout calcul en cours, purge la file ComfyUI,
  // nettoie les références/erreurs et ouvre une session vierge propre.
  const resetWorkspaceClean = useCallback(() => {
    onStop()
    if (refPreview) URL.revokeObjectURL(refPreview)
    if (refPreview2) URL.revokeObjectURL(refPreview2)
    setRefPreview(null)
    setRefFilename(null)
    setRefPreview2(null)
    setRefFilename2(null)
    setError(null)
    setProgress('')
    setProgressPct(0)
    setCurrentStep(0)
    setLastExpandedNote(null)
    const newSessionId = useModuleHistoryStore.getState().createSession('image')
    const newSession = useModuleHistoryStore.getState().sessions.find((s) => s.id === newSessionId)
    if (newSession) {
      setImages([])
      setCurrent(null)
    }
    setNotice('Atelier remis à neuf : génération précédente interrompue, références nettoyées et dossier unifié (output/image/creations/) prêt.')
  }, [onStop, refPreview, refPreview2])

  const downloadCurrent = useCallback(async () => {
    if (!current) return
    const { downloadImageUniversal } = await import('../utils/imageDownload')
    await downloadImageUniversal(current)
  }, [current])

  const previewIntent: ParsedImageIntent = useMemo(
    () => parseImageIntent(prompt, { hasReference: Boolean(refFilename || current) }),
    [current, prompt, refFilename],
  )
  const previewStyleResolution = useMemo(
    () => resolveImageConversationStyle({
      style,
      prompt,
      hasReference: Boolean(refFilename || current),
      isEditIntent: previewIntent.isEditIntent,
    }),
    [current, prompt, refFilename, style, previewIntent],
  )

  const effectiveDenoise: number | null = useMemo(() => {
    if (!refFilename && !(current && previewIntent.isEditIntent)) return null
    return previewIntent.isEditIntent
      ? resolveReferenceDenoise(previewIntent, refDenoise, previewStyleResolution.style)
      : refDenoise
  }, [current, refFilename, refDenoise, previewStyleResolution.style, previewIntent])

  return {
    who,
    styles,
    prompt, setPrompt,
    negPrompt, setNegPrompt, showNeg, setShowNeg,
    style, setStyle,
    seed, setSeed,
    batch, setBatch,
    dimensions, setDimensions,
    refPreview, refFilename, refDenoise, setRefDenoise, refUploading,
    onUploadReference, clearReference,
    uploadReferenceFile,
    // v87 : seconde reference (source d'extraction multi-image)
    refPreview2, refFilename2, refUploading2,
    onUploadSource, clearSource, uploadSourceFile,
    images, current, setCurrent,
    generating, progress, progressPct, currentStep, lastSavedPath, lastExpandedNote,
    error, notice, setNotice,
    queuePrompt, onStop, resetWorkspaceClean,
    randomImagePreset,
    downloadCurrent,
    inpaintOpen, setInpaintOpen, applyInpaint,
    upscaleCurrent, upscaling,
    resumeBanner,
    previewIntent,
    effectiveDenoise,
    styleOverrideReason: previewStyleResolution.overrideReason,
    editEngine,
    history, recallPrompt, removeHistory,
    imageStreak,
    activeImageSession,
    recentImageMessages,
    onImageSessionChange,
  }
}

