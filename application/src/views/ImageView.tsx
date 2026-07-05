import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  AlertCircle,
  BookOpen,
  ChevronDown,
  Download,
  Image as ImageIcon,
  Loader2,
  RefreshCw,
  Sliders,
  Sparkles,
  Wand2,
  X,
} from 'lucide-react'
import ClarificationDialog from '../components/ClarificationDialog'
import type { ClarificationRequest } from '../components/ClarificationDialog'
import ContextFilesField from '../components/ContextFilesField'
import VoicePushToTalk from '../components/VoicePushToTalk'
import ModuleAssetPackCard from '../components/ModuleAssetPackCard'
import ConnectorRecommendationsPanel from '../components/ConnectorRecommendationsPanel'
import PromptLibraryPanel from '../components/PromptLibraryPanel'
import SessionSwitcher from '../components/SessionSwitcher'
import SaveDialog from '../components/SaveDialog'
import type { SaveDialogData } from '../components/SaveDialog'
import { buildImageModuleAssets } from '../config/moduleAssetPacks'
import { AUXILIARY_ANALYSIS_MODEL, IMAGE_MODEL_PACK_LABEL } from '../config/models'
import { useAppStore } from '../stores/appStore'
import { usePromptLibraryStore } from '../stores/promptLibraryStore'
import {
  comfyuiGetHistory,
  comfyuiGetImage,
  comfyuiQueuePrompt,
  ensureComfyUIRunning,
  freeGpuBeforeFlux,
  fsReadBinary,
  fsWriteBinary,
  getWorkspacePath,
  toAssetUrl,
} from '../hooks/useTauri'
import { StudioDiagnosticsPanel, StudioHero } from '../components/StudioHero'
import { useManagedRuntime } from '../hooks/useManagedRuntime'
import { useModuleAssetPack } from '../hooks/useModuleAssetPack'
import { useStudioDiagnostics } from '../hooks/useStudioDiagnostics'
import { createFluxWorkflow, getAvailableStyles, type FluxStyle } from '../utils/fluxWorkflow'
import { extractComfyPromptId, waitForComfyResult } from '../utils/comfyui'
import { prepareTaskIntelligence } from '../services/taskIntelligence'
import { analyzeImage } from '../services/visionService'
import { getErrorMessage } from '../utils/errors'
import { isCloudRuntime, isTauriRuntime } from '../utils/runtime'
import { useGenerationRecovery } from '../hooks/useGenerationRecovery'
import { useGenerationTrackerStore } from '../stores/generationTrackerStore'
import RecoveryBanner from '../components/RecoveryBanner'
import { prepareContextFiles } from '../utils/multimodalContext'
import { pickPrimaryImageFile, stageBlobToComfyInput, stageBrowserFileToComfyInput } from '../utils/referenceMedia'
import type { GenerationContract } from '../services/generationContract'
import { findBestReferenceVisual } from '../services/referenceVisualResearch'
import { useModuleHistoryStore, type ConversationSession } from '../stores/moduleHistoryStore'
import { recommendPlacement } from '../services/imageCompositionRules'
import { buildPrompt, buildPromptContractBlock, parseBrief } from '../services/imagePromptBuilder'
import { diffPrompts } from '../services/imagePromptDiff'
import LyraCharacter from '../components/voice/LyraCharacter'
import { parseImageIntent, resolveReferenceDenoise, type ParsedImageIntent } from '../utils/imagePromptParser'

function promptSlug(text: string, maxLen = 28): string {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '').slice(0, maxLen) || 'aurora'
}

type GeneratedImage = {
  id: string
  url: string
  prompt: string
  style: FluxStyle
  timestamp: number
  storage: 'workspace' | 'memory'
}

function releaseMemoryImage(image: GeneratedImage) {
  if (image.storage === 'memory') {
    URL.revokeObjectURL(image.url)
  }
}

function buildConversationContext(history: Array<{ role: 'user' | 'assistant'; content: string }>) {
  return history
    .slice(-4)
    .map((message) => `${message.role.toUpperCase()}: ${message.content.replace(/\s+/g, ' ').trim().slice(0, 220)}`)
    .join('\n')
}

function looksLikeStoredImage(path: string) {
  return /\.(png|jpe?g|webp)$/i.test(path)
}

function findSessionImages(session: ConversationSession) {
  const generated: GeneratedImage[] = []

  for (let index = session.messages.length - 1; index >= 0; index -= 1) {
    const message = session.messages[index]
    const promptSource = [...session.messages.slice(0, index)].reverse().find((entry) => entry.role === 'user')?.content || message.content

    for (const imagePath of (message.images || []).filter(looksLikeStoredImage)) {
      generated.push({
        id: `${session.id}-${message.timestamp}-${imagePath}`,
        url: toAssetUrl(imagePath),
        prompt: promptSource,
        style: 'none',
        timestamp: message.timestamp,
        storage: 'workspace',
      })
    }
  }

  return generated
}

function findLatestSessionImagePath(session: ConversationSession) {
  for (let index = session.messages.length - 1; index >= 0; index -= 1) {
    const imagePath = session.messages[index].images?.find(looksLikeStoredImage)
    if (imagePath) {
      return imagePath
    }
  }

  return null
}

function resolveImageRenderPlan({
  prompt,
  selectedStyle,
  width,
  height,
  steps,
  hasReference,
  contract,
}: {
  prompt: string
  selectedStyle: FluxStyle
  width: number
  height: number
  steps: number
  hasReference: boolean
  contract: GenerationContract
}) {
  const normalized = prompt.toLowerCase()
  const wantsAnime = /\b(anime|manga|personnage|character|hero|heros|h[eé]ros|heroine|heroïne|waifu|villain)\b/i.test(normalized)
  const wantsTechnical = /\b(cable|connecteur|connector|mecanique|mechanical|component|composant|courroie|belt|poulie|pulley|verin|v[eé]rin|gear|engrenage|bearing|roulement)\b/i.test(normalized)
  const wantsPixelStyle = /\b(pixel art|pixel-art|sprite|8 bit|8-bit|16 bit|16-bit|voxel)\b/i.test(normalized)
  const effectiveStyle: FluxStyle = selectedStyle === 'none'
    ? wantsTechnical ? 'technical_render' : wantsAnime ? 'anime' : 'none'
    : selectedStyle
  const targetResolution = hasReference ? 1152 : wantsAnime || wantsTechnical ? 1024 : 768
  const targetSteps = hasReference
    ? Math.max(steps, contract.editStrategy === 'preserve_and_refine' ? 40 : 38)
    : wantsAnime ? Math.max(steps, 36) : wantsTechnical ? Math.max(steps, 38) : Math.max(steps, 30)

  return {
    style: effectiveStyle,
    width: Math.max(width, targetResolution),
    height: Math.max(height, targetResolution),
    steps: wantsPixelStyle ? steps : targetSteps,
  }
}

function buildAutoReferenceQueries(prompt: string, webSearchTerms: string[], requestedChanges: string[]) {
  const normalized = prompt.toLowerCase()
  const promptSpecificQueries: string[] = []

  if (/\b(anime|manga|personnage|character|hero|heros|h[eÃ©]ros|heroine|heroÃ¯ne|waifu|villain|pokemon|digimon)\b/i.test(normalized)) {
    promptSpecificQueries.push(`${prompt} official character design`)
    promptSpecificQueries.push(`${prompt} anime character key visual`)
  }

  if (/\b(component|composant|piece|part|cable|connector|connecteur|courroie|belt|poulie|pulley|verin|v[eÃ©]rin|gear|engrenage|bearing|roulement)\b/i.test(normalized)) {
    promptSpecificQueries.push(`${prompt} isolated reference photo`)
    promptSpecificQueries.push(`${prompt} dimensions size measurements`)
  }

  return Array.from(new Set([
    prompt,
    ...webSearchTerms,
    ...requestedChanges,
    ...promptSpecificQueries,
  ].map((query) => query.trim()).filter(Boolean))).slice(0, 6)
}

function shouldAutoResearchReference(prompt: string, contract: GenerationContract, isVerifiable: boolean) {
  const normalized = prompt.toLowerCase()
  const looksReferenceSensitive = /\b(personnage|character|anime|manga|hero|heros|h[eé]ros|waifu|villain|reference|existant|existing|modele reel|real object|component|composant|cable|connecteur|connector|courroie|belt|poulie|pulley|verin|v[eé]rin|gear|engrenage|bearing|roulement)\b/i.test(normalized)
  return contract.mode === 'create' && (contract.shouldResearch || isVerifiable || looksReferenceSensitive)
}

function getReferenceEditConfig(style: FluxStyle, steps: number, contract: GenerationContract, options: { touchesText?: boolean; repeatCount?: number; imageIntent?: ParsedImageIntent } = {}) {
  const isRealistic = style === 'realistic' || style === 'none'
  const bump = Math.min(0.25, (options.repeatCount ?? 0) * 0.08)
  const intentDenoise = options.imageIntent?.isEditIntent
    ? resolveReferenceDenoise(options.imageIntent, 0.35, style)
    : null
  const intentSteps = options.imageIntent?.isEditIntent
    ? Math.max(steps, steps + options.imageIntent.editContract.stepsBoost)
    : steps

  if (options.touchesText) {
    return {
      denoise: Math.min(0.86, Math.max(intentDenoise ?? 0, isRealistic ? 0.55 : 0.65) + bump),
      steps: Math.max(intentSteps, 38),
    }
  }

  if (intentDenoise !== null) {
    return {
      denoise: Math.min(0.86, intentDenoise + bump),
      steps: intentSteps,
    }
  }

  switch (contract.editStrategy) {
    case 'preserve_and_refine':
      return {
        denoise: (isRealistic ? 0.12 : 0.18) + bump,
        steps: Math.max(steps, 34),
      }
    case 'targeted_edit':
      return {
        denoise: (isRealistic ? 0.42 : 0.50) + bump,
        steps: Math.max(steps, 38),
      }
    case 'scene_transform':
      return {
        denoise: (isRealistic ? 0.62 : 0.70) + bump,
        steps: Math.max(steps, 38),
      }
    default:
      return {
        denoise: bump > 0 ? Math.max(0.2, bump) : undefined,
        steps,
      }
  }
}

const TEXT_EDIT_PATTERNS = /\b(pancarte|panneau|affiche|ecriteau|inscription|slogan|logo ecrit|logo texte|texte sur|mot sur|lettre sur|ecrire|ecris|ecrit|marquer|marque|mentionner|mention|phrase|message|signe|enseigne|banderole|stiker|sticker|label|etiquette|title|caption|subtitle|headline|sign|board|billboard|write|text saying|message saying)\b/i

function computeRepeatCount(current: string, recentUserMessages: string[]): number {
  const norm = (s: string) => s.toLowerCase().replace(/\s+/g, ' ').trim()
  const c = norm(current)
  let count = 0
  for (let i = recentUserMessages.length - 1; i >= 0; i -= 1) {
    const past = norm(recentUserMessages[i])
    if (!past) continue
    const a = new Set(c.split(' '))
    const b = new Set(past.split(' '))
    let inter = 0
    for (const w of a) if (b.has(w)) inter += 1
    const union = a.size + b.size - inter
    const sim = union > 0 ? inter / union : 0
    if (sim >= 0.55) count += 1
    else break
  }
  return count
}

const EDIT_INTENT_PATTERNS = /(?:^|\b)(ajoute|ajouter|enleve|enlever|retire|retirer|supprime|supprimer|change|changer|modifie|modifier|remplace|remplacer|mets|met|mettre|rajoute|rajouter|deplace|deplacer|transforme|transformer|ameliore|ameliorer|corrige|corriger|rends?|rendre|fais|faire|depuis la|sur la|a la|sur le|a partir|au dessus|en dessous|a cote|devant|derriere|plus realiste|plus sombre|plus clair|plus lumineux|plus fonce|plus colore|plus detaille|plus net|plus flou|en noir et blanc|en couleur|zoom|recadre|tourne|inverse|miroir|reflet|meme image|meme photo|cette image|cette photo|la photo|l image|garde|conserve|preserve|maintiens|sans le|sans la|sans les|avec un|avec une|avec des|avec le|avec la|donne lui|donne-lui|habille|deshabille|coiffe|recoiffe|maquille|vieillis|rajeunis|grossis|amincis|agrandis|retrecis|eclaire|assombris|floute|defloute|pixelise|stylise|caricature|redimensionne|upscale|ameliore la qualite|augmente la resolution)/i

export default function ImageView() {
  const { runtimeServices, visionModel } = useAppStore()
  const { pushMessage, getRecentMessages, openPromptSession } = useModuleHistoryStore()
  const diagnostics = useStudioDiagnostics({ requiresComfyui: true, requiresOllama: true })
  const { executeWithRuntime } = useManagedRuntime()
  const { trackGeneration, completeGeneration, failGeneration } = useGenerationTrackerStore()
  const recovery = useGenerationRecovery('image')
  const [contextFiles, setContextFiles] = useState<File[]>([])
  const { pack: assetPack, preparePack } = useModuleAssetPack({
    module: 'image',
    title: 'Pack modele image',
    assets: buildImageModuleAssets(visionModel, runtimeServices.comfyui.path, contextFiles.length > 0),
  })
  const styles = useMemo(() => getAvailableStyles(), [])
  const [prompt, setPrompt] = useState('')
  const [selectedStyle, setSelectedStyle] = useState<FluxStyle>('none')
  const [width, setWidth] = useState(1024)
  const [height, setHeight] = useState(1024)
  const [steps, setSteps] = useState(28)
  const [isGenerating, setIsGenerating] = useState(false)
  const [progress, setProgress] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [images, setImages] = useState<GeneratedImage[]>([])
  const [selectedImage, setSelectedImage] = useState<GeneratedImage | null>(null)
  const [showSettings, setShowSettings] = useState(false)
  const [showStyles, setShowStyles] = useState(false)
  const [saveDialogData, setSaveDialogData] = useState<SaveDialogData | null>(null)
  const [promptLibraryOpen, setPromptLibraryOpen] = useState(false)
  const [clarification, setClarification] = useState<ClarificationRequest | null>(null)
  const [fullscreenImage, setFullscreenImage] = useState<GeneratedImage | null>(null)
  const [copyFeedback, setCopyFeedback] = useState(false)
  const { addPrompt } = usePromptLibraryStore()
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const activeTrackerIdRef = useRef<string | null>(null)
  const imagesRef = useRef<GeneratedImage[]>([])
  const lastGeneratedPathRef = useRef<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const [seed, setSeed] = useState<number | null>(null)
  const [fixedSeed, setFixedSeed] = useState(false)
  const [promptHistory, setPromptHistory] = useState<string[]>(() => {
    if (typeof window === 'undefined') return []
    try {
      const raw = window.localStorage.getItem('aurora.image.promptHistory')
      if (!raw) return []
      const parsed = JSON.parse(raw)
      return Array.isArray(parsed) ? parsed.slice(0, 8).filter((s): s is string => typeof s === 'string') : []
    } catch { return [] }
  })
  const pushPromptHistory = useCallback((p: string) => {
    if (!p || p.length < 4) return
    setPromptHistory((prev) => {
      const next = [p, ...prev.filter((x) => x !== p)].slice(0, 8)
      try { window.localStorage.setItem('aurora.image.promptHistory', JSON.stringify(next)) } catch {}
      return next
    })
  }, [])

  const [seedHistory, setSeedHistory] = useState<number[]>(() => {
    if (typeof window === 'undefined') return []
    try {
      const raw = window.localStorage.getItem('aurora.image.seedHistory')
      if (!raw) return []
      const parsed = JSON.parse(raw)
      return Array.isArray(parsed) ? parsed.slice(0, 8).filter((n): n is number => typeof n === 'number') : []
    } catch { return [] }
  })
  const pushSeedHistory = useCallback((s: number) => {
    setSeedHistory((prev) => {
      const next = [s, ...prev.filter((p) => p !== s)].slice(0, 8)
      try { window.localStorage.setItem('aurora.image.seedHistory', JSON.stringify(next)) } catch {}
      return next
    })
  }, [])
  const [genPct, setGenPct] = useState(0)
  imagesRef.current = images

  const hydrateSession = useCallback((session: ConversationSession) => {
    const sessionImages = findSessionImages(session)
    setImages(sessionImages)
    setSelectedImage(sessionImages[0] || null)
    lastGeneratedPathRef.current = findLatestSessionImagePath(session)
    setProgress('')
    setError(null)
  }, [])

  useEffect(() => {
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current)
      }

      imagesRef.current.forEach(releaseMemoryImage)
    }
  }, [])

  useEffect(() => {
    hydrateSession(useModuleHistoryStore.getState().getActiveSession('image'))
  }, [hydrateSession])

  const activeStyleLabel = styles.find((style) => style.id === selectedStyle)?.label || 'Auto / Libre'
  const activeOllamaModel = contextFiles.length > 0 ? visionModel : AUXILIARY_ANALYSIS_MODEL
  const canGenerate = Boolean(prompt.trim()) && !isGenerating && !diagnostics.blockingReason
  const recentMessages = getRecentMessages('image', 6)

  const generate = useCallback(async () => {
    if (!prompt.trim() || isGenerating) return

    if (diagnostics.blockingReason) {
      setError(diagnostics.blockingReason)
      return
    }

    const currentPrompt = prompt.trim()
    const conversationHistory = getRecentMessages('image', 6)
    setIsGenerating(true)
    setError(null)
    setProgress('Analyse du prompt visuel...')
    setGenPct(0)
    abortRef.current = new AbortController()

    try {
      await executeWithRuntime({
        module: 'image',
        title: 'Generation image',
        services: ['ollama', 'comfyui'],
        ollamaModel: activeOllamaModel,
        prepare: async ({ setPhase }) => {
          await preparePack(setPhase)
          setProgress('Verification de ComfyUI...')
          setPhase('Verification de ComfyUI...', 33)
          let comfyStart = await ensureComfyUIRunning()
          let retryCount = 0
          while (!comfyStart.ok && retryCount < 2) {
            retryCount += 1
            setProgress(`ComfyUI pas encore actif, tentative ${retryCount + 1}/3...`)
            setPhase(`Demarrage ComfyUI (tentative ${retryCount + 1}/3)...`, 33)
            await new Promise((resolve) => setTimeout(resolve, 3000))
            comfyStart = await ensureComfyUIRunning()
          }
          if (!comfyStart.ok) {
            throw new Error(
              comfyStart.error
              || 'ComfyUI ne repond pas. Sur le cloud verifiez que start.sh a bien demarre ComfyUI sur le port 8188. En local, lance ComfyUI manuellement (main.py --port 8188) ou verifie que le chemin COMFYUI_DIR est correct.',
            )
          }
        },
        job: async ({ setPhase }) => {
          const preparedContext = contextFiles.length > 0 ? await prepareContextFiles(contextFiles) : []
          const conversationContext = buildConversationContext(conversationHistory)
          const promptWithHistory = conversationContext
            ? `${currentPrompt}\n\nContexte recent module image:\n${conversationContext}`
            : currentPrompt
          const primaryImageFile = pickPrimaryImageFile(contextFiles)
          const comfyuiPath = runtimeServices.comfyui.path
          if (primaryImageFile && !comfyuiPath) {
            throw new Error('Chemin ComfyUI introuvable pour exploiter l image de reference.')
          }

          let visionReferenceAnalysis = ''
          if (primaryImageFile) {
            setProgress('Analyse detaillee de la reference (Qwen3-VL)...')
            setPhase('Analyse vision de la reference...', 40)
            try {
              const analysis = await analyzeImage(
                { kind: 'blob', data: primaryImageFile },
                {
                  task: 'describe_reference',
                  userPrompt: currentPrompt,
                  language: 'fr',
                  preferQuality: true,
                  signal: abortRef.current?.signal,
                },
              )
              if (analysis.description && analysis.description.length > 20) {
                visionReferenceAnalysis = analysis.description
                setProgress(`Reference analysee (${analysis.modelUsed}, ${Math.round(analysis.durationMs / 100) / 10}s)`)
              }
            } catch (err) {
              console.warn('[ImageView] Vision reference analysis failed:', err)
            }
          }

          const hasEditIntent = !primaryImageFile && EDIT_INTENT_PATTERNS.test(currentPrompt)
          const autoReusePath = hasEditIntent && lastGeneratedPathRef.current && comfyuiPath
            ? lastGeneratedPathRef.current
            : null

          if (autoReusePath) {
            setProgress('Reprise automatique de la derniere image generee comme reference...')
            setPhase('Reprise automatique de la derniere image comme reference...', 36)
          }

          const referenceImage = primaryImageFile && comfyuiPath
            ? await (async () => {
              setProgress('Preparation de l image de reference...')
              setPhase('Preparation de l image de reference...', 38)
              return stageBrowserFileToComfyInput(primaryImageFile, comfyuiPath, 'juan_bike_image_ref')
            })()
            : autoReusePath && comfyuiPath
              ? await (async () => {
                  setProgress('Reprise de la derniere image...')
                  setPhase('Copie de l image precedente pour edition...', 38)
                  const bytes = await fsReadBinary(autoReusePath)
                  const blob = new Blob([new Uint8Array(bytes)], { type: 'image/png' })
                  return stageBlobToComfyInput(blob, comfyuiPath, 'juan_bike_reuse')
                })()
              : null
          const touchesBodyNotFace = /\b(pose|position|tenue|vetement|habit|bras|main|jambe|corps|debout|assis|allonge|accroupi|tourne|penche|leve|baisse|croise|ecarte|marche|court|danse|saute|bouge|geste|mouvement|clothing|outfit|posture|stance|standing|sitting|walking|running|arm|leg|hand|body)\b/i.test(currentPrompt)
          const touchesFace = /\b(visage|tete|face|expression|sourire|souris|yeux|nez|bouche|cheveux|barbe|moustache|lunettes|maquillage|regard|frown|smile|eyes|hair|head|face|makeup|glasses)\b/i.test(currentPrompt)

          const referenceAwarePrompt = referenceImage
            ? [
              promptWithHistory,
              visionReferenceAnalysis
                ? [
                    '',
                    '## REFERENCE DESCRIPTION (Qwen3-VL high-fidelity analysis):',
                    visionReferenceAnalysis,
                    '',
                    'Use the description above as the GROUND TRUTH for the subject identity.',
                    'When the user asks to modify something, preserve all OTHER attributes listed above pixel-for-pixel.',
                  ].join('\n')
                : '',
              '',
              'REFERENCE EDIT CONTRACT — STRICT RULES:',
              '',
              '## IDENTITY LOCK',
              'The reference image IS the subject. Do NOT generate a new person, object or scene.',
              'Work ONLY on modifying this exact image. The result must be recognizably the SAME subject.',
              '',
              '## FACE AND HEAD PROTECTION',
              touchesBodyNotFace && !touchesFace
                ? 'CRITICAL: This edit targets the BODY/POSE/CLOTHING — the FACE and HEAD must remain PIXEL-PERFECT IDENTICAL. Do NOT alter facial features, skin texture, hair, expression, eye color, facial structure, head shape, or any facial detail. The face must look like a copy-paste from the original.'
                : 'Preserve facial identity: bone structure, eye shape, nose, mouth, skin texture, facial proportions must remain recognizably the same person.',
              '',
              '## PRESERVATION DEFAULTS',
              'Unless the user EXPLICITLY asks to change it, preserve:',
              '- Camera angle and framing',
              '- Lighting direction and quality',
              '- Background and scene layout',
              '- Color palette and mood',
              '- Subject count and relative positions',
              '- Skin texture, pores, wrinkles, blemishes (for realistic)',
              '',
              '## MODIFICATION TYPES',
              '- ADD: Insert new elements WITHOUT altering existing ones',
              '- REMOVE: Erase specified elements, inpaint the gap naturally with coherent continuation',
              '- MODIFY: Change specific attributes (color, size, position, expression, clothing) — ONLY those elements, everything else stays identical',
              '- TRANSFORM: Style/lighting/mood change across the whole image while preserving identity',
              '- ENHANCE: Increase quality, realism, detail without changing content',
              '',
              '## CONTEXT UNDERSTANDING',
              'Interpret the user intent from context:',
              '- "fais-la sourire" = change ONLY the expression to a smile, keep EVERYTHING else',
              '- "mets un fond de plage" = replace ONLY the background with beach',
              '- "enleve le chapeau" = remove hat, inpaint hair naturally',
              '- "change sa position" = change body pose, keep face IDENTICAL',
              '- "habille-la en rouge" = change clothing color, keep face and body proportions',
              '',
              '## SPATIAL COHERENCE',
              'Keep anatomy anatomically correct. No extra limbs, no broken joints, no morphed fingers.',
              'Shadows must match the light source. Perspective must be consistent.',
              'No random artifacts, no duplicated elements, no floating objects.',
            ].join('\n')
            : promptWithHistory

          const taskContext = await prepareTaskIntelligence({
            module: 'image',
            prompt: referenceAwarePrompt,
            model: visionModel,
            files: preparedContext,
            setPhase,
            phaseBase: 42,
            phaseSpan: 16,
          })

          if (taskContext.clarificationQuestion) {
            setPhase('Clarification utilisateur requise avant edition image.', 50)
            const userAnswer = await new Promise<string | null>((resolve) => {
              setClarification({ question: taskContext.clarificationQuestion!, onRespond: resolve })
            })
            setClarification(null)
            if (userAnswer) {
              taskContext.enrichedPrompt = `${taskContext.enrichedPrompt}\n\nPrecision utilisateur: ${userAnswer}`
              taskContext.generationPrompt = `${taskContext.generationPrompt}\n\nUser clarification: ${userAnswer}`
            }
          }

          let activeReference = referenceImage
          let autoReferenceSummary = ''

          if (!activeReference && comfyuiPath && shouldAutoResearchReference(currentPrompt, taskContext.generationContract, taskContext.analysis.isVerifiable)) {
            setProgress('Recherche d une reference visuelle fiable...')
            setPhase('Recherche d une reference visuelle fiable...', 50)
            const candidate = await findBestReferenceVisual({
              prompt: currentPrompt,
              model: visionModel,
              queries: buildAutoReferenceQueries(currentPrompt, taskContext.analysis.webSearchTerms, taskContext.generationContract.requestedChanges),
            })
            if (candidate) {
              const stagedReference = await stageBlobToComfyInput(candidate.blob, comfyuiPath, 'juan_bike_auto_ref')
              activeReference = stagedReference
              autoReferenceSummary = `Reference externe retenue: ${candidate.title} (${candidate.width}x${candidate.height})`
            }
          }

          const renderPlan = resolveImageRenderPlan({
            prompt: currentPrompt,
            selectedStyle,
            width,
            height,
            steps,
            hasReference: Boolean(activeReference),
            contract: taskContext.generationContract,
          })

          const requestedTextMatch = currentPrompt.match(/(?:ecri[st]?|ecrire|texte|mot|phrase|message|mention)[^"'«»:]{0,40}["'«"]([^"'«»]{1,80})["'»"]/i)
          const requestedText = requestedTextMatch?.[1]?.trim() || ''
          const textEditBlock = TEXT_EDIT_PATTERNS.test(currentPrompt)
            ? [
                '',
                'TEXT EDIT — CRITICAL:',
                '- The user wants to change the WRITTEN text shown on the sign/banner/logo/label in the image.',
                requestedText
                  ? `- The NEW exact text that must appear verbatim: "${requestedText}". Render it clearly, readable, centered on the sign, in a legible sans-serif if possible.`
                  : '- Extract the target text from the user request and render it clearly, readable, centered on the sign in a legible sans-serif.',
                '- Completely erase/replace the previous inscription. Do NOT keep any letter of the old text.',
                '- Only the sign surface changes — the rest of the scene (character, pose, background, lighting) stays identical.',
                '',
              ].join('\n')
            : ''

          const strengthenedPrompt = [
            taskContext.generationPrompt,
            '',
            buildPromptContractBlock(parseBrief(currentPrompt)),
            textEditBlock,
            '',
            'STRICT QUALITY GUARDRAILS — MANDATORY:',
            '- ZERO deformation: correct human anatomy (5 fingers per hand, proportional limbs, no extra/missing body parts, no duplicated limbs, no fused fingers)',
            '- ZERO face distortion: eyes at same height, symmetrical features, pupils aligned, no melting/warping of facial structure, no twin faces, no drifting jaw',
            '- ZERO text corruption: any readable text (signs, labels, UI) must use real glyphs — no scribbles, no gibberish, no half-letters',
            '- no blocky pixels, no mosaic artifacts, no JPEG compression noise, no color banding, no moire',
            '- clean sharp edges, stable line art, coherent face proportions, proper perspective and vanishing points',
            '- correct spatial relationships: objects do not float, shadows match light source direction, ground plane is consistent, reflections are plausible',
            '- fabric and material textures must be coherent (no smudged patterns, no random texture mixing, weave direction consistent)',
            '- physically plausible lighting: coherent color temperature per scene, believable shadows and specular highlights',
            '- correct count of objects and subjects as described in the prompt — no random extra copies',
            '- backgrounds must stay coherent with the subject — no random collage of unrelated scenes, no cut-outs',
            autoReferenceSummary ? `- ${autoReferenceSummary}` : '',
            '',
            'NEGATIVE TRAITS TO AVOID: ugly, blurry, low quality, watermark, signature, extra fingers, mutated hands, poorly drawn face, malformed limbs, bad anatomy, cropped, worst quality, low-res, jpeg artifacts, text artifacts, draft sketch, overexposed, underexposed.',
          ].filter(Boolean).join('\n')

          const imageIntent = parseImageIntent(currentPrompt, { hasReference: Boolean(activeReference) })
          const touchesText = TEXT_EDIT_PATTERNS.test(currentPrompt)

          const recentUserPrompts = conversationHistory
            .filter((m) => m.role === 'user')
            .map((m) => m.content)
            .slice(0, -1)
          const repeatCount = computeRepeatCount(currentPrompt, recentUserPrompts)

          const referenceEditConfig = activeReference
            ? getReferenceEditConfig(renderPlan.style, renderPlan.steps, taskContext.generationContract, {
                touchesText,
                repeatCount,
                imageIntent,
              })
            : { denoise: undefined, steps: renderPlan.steps }

          if (touchesText || repeatCount > 0) {
            const hint = touchesText
              ? 'Edition de texte sur image — denoise augmente'
              : `Reiteration detectee (${repeatCount}x) — denoise augmente pour forcer un changement visible`
            setProgress(hint)
            setPhase(hint, 55)
          }

          pushMessage('image', { role: 'user', content: currentPrompt })

          setProgress(activeReference ? 'Construction du workflow FLUX d edition...' : 'Construction du workflow FLUX...')
          setPhase(activeReference ? 'Construction du workflow FLUX d edition...' : 'Construction du workflow FLUX...', 52)
          const workflow = createFluxWorkflow({
            prompt: strengthenedPrompt,
            width: renderPlan.width,
            height: renderPlan.height,
            steps: referenceEditConfig.steps,
            filenamePrefix: promptSlug(currentPrompt),
            style: renderPlan.style,
            seed: fixedSeed ? (seed ?? Math.floor(Math.random() * 2 ** 32)) : null,
            referenceImage: activeReference ? { filename: activeReference.filename, denoise: referenceEditConfig.denoise } : null,
            editIntent: imageIntent,
          })

          if (fixedSeed && seed != null) pushSeedHistory(seed)
          pushPromptHistory(currentPrompt)

          setProgress(activeReference ? 'Envoi de l edition referencee vers ComfyUI...' : 'Envoi vers ComfyUI...')
          setPhase(activeReference ? 'Edition referencee en cours dans ComfyUI...' : 'Envoi du workflow vers ComfyUI...', 62)

          await freeGpuBeforeFlux(Array.from(new Set([visionModel, AUXILIARY_ANALYSIS_MODEL].filter(Boolean))))

          let queueResult: Record<string, unknown>
          try {
            queueResult = await comfyuiQueuePrompt(workflow)
          } catch (queueErr) {
            const errMsg = queueErr instanceof Error ? queueErr.message : String(queueErr)
            if (activeReference && (errMsg.includes('400') || errMsg.includes('validation') || errMsg.includes('Invalid image'))) {
              setProgress('Reference invalide — auto-correction: generation sans reference...')
              setPhase('Auto-correction: generation sans reference...', 64)
              const fallbackWorkflow = createFluxWorkflow({
                prompt: strengthenedPrompt,
                width: renderPlan.width,
                height: renderPlan.height,
                steps: renderPlan.steps,
                filenamePrefix: promptSlug(currentPrompt),
                style: renderPlan.style,
                seed: fixedSeed ? (seed ?? Math.floor(Math.random() * 2 ** 32)) : null,
                referenceImage: null,
              })
              await freeGpuBeforeFlux(Array.from(new Set([visionModel, AUXILIARY_ANALYSIS_MODEL].filter(Boolean))))
              queueResult = await comfyuiQueuePrompt(fallbackWorkflow)
            } else {
              throw queueErr
            }
          }
          const promptId = extractComfyPromptId(queueResult)

          activeTrackerIdRef.current = trackGeneration({
            module: 'image',
            type: 'comfyui',
            prompt: currentPrompt,
            startedAt: Date.now(),
            comfyPromptId: promptId,
          })
          const trackerId = activeTrackerIdRef.current

          setProgress('Generation en cours...')
          setPhase('Rendu en cours sur ComfyUI...', 72)
          const abortPromise = new Promise<never>((_, reject) => {
            abortRef.current?.signal.addEventListener('abort', () => reject(new Error('Generation annulee')))
          })
          const result = await Promise.race([
            waitForComfyResult(promptId, {
              getHistory: comfyuiGetHistory,
              onProgress: (pct, detail) => {
                setProgress(detail)
                setGenPct(Math.round(pct * 100))
                setPhase(detail, Math.min(90, 72 + Math.round(pct * 0.18)))
              },
              timeoutMs: 300_000,
            }),
            abortPromise,
          ])

          setProgress('Recuperation du rendu...')
          setPhase('Recuperation du rendu final...', 84)
          const blob = await comfyuiGetImage(result.filename, result.subfolder)
          const timestamp = Date.now()
          let imageUrl = ''
          let storage: GeneratedImage['storage'] = 'memory'

          let savedOutputPath = ''
          if (isTauriRuntime()) {
            const workspacePath = await getWorkspacePath()
            const outputPath = `${workspacePath}/output/images/juan_bike_img_${timestamp}.png`
            savedOutputPath = outputPath
            const bytes = Array.from(new Uint8Array(await blob.arrayBuffer()))
            await fsWriteBinary(outputPath, bytes)
            imageUrl = toAssetUrl(outputPath)
            storage = 'workspace'
          } else {
            imageUrl = URL.createObjectURL(blob)
          }

          const nextImage: GeneratedImage = {
            id: `img-${timestamp}`,
            url: imageUrl,
            prompt: currentPrompt,
            style: renderPlan.style,
            timestamp,
            storage,
          }

          completeGeneration(trackerId, {
            resultPath: savedOutputPath || undefined,
            resultFilename: result.filename
              ? `style ${renderPlan.style}, ${result.filename}`
              : `style ${renderPlan.style}`,
          })

          if (comfyuiPath && result.filename) {
            lastGeneratedPathRef.current = `${comfyuiPath.replace(/\\/g, '/')}/output/${result.subfolder ? result.subfolder + '/' : ''}${result.filename}`
          }

          setImages((previous) => {
            const evicted = previous.slice(23)
            evicted.forEach(releaseMemoryImage)
            return [nextImage, ...previous.slice(0, 23)]
          })
          setSelectedImage(nextImage)
          pushMessage('image', {
            role: 'assistant',
            content: [
              `Rendu image ${renderPlan.style}.`,
              autoReferenceSummary,
              taskContext.researchContext ? 'Recherche native appliquee.' : '',
            ].filter(Boolean).join(' '),
            images: storage === 'workspace' && savedOutputPath ? [savedOutputPath] : undefined,
          })
          setProgress('Image generee, chargement de la galerie puis liberation des ressources...')
          setPhase('Image chargee, liberation des ressources...', 94)
          if (storage === 'workspace' && savedOutputPath) {
            setSaveDialogData({
              module: 'image',
              sourcePath: savedOutputPath,
              prompt: currentPrompt,
              fidelityScore: 90,
              parameters: { width: renderPlan.width, height: renderPlan.height, steps: referenceEditConfig.steps, style: renderPlan.style, autoReferenceSummary },
            })
          }
        },
      })
    } catch (generationError) {
      if (activeTrackerIdRef.current) {
        failGeneration(activeTrackerIdRef.current, getErrorMessage(generationError))
        activeTrackerIdRef.current = null
      }
      setError(getErrorMessage(generationError, 'Le module image a echoue sans detail exploitable.'))
      setProgress('')
    } finally {
      setIsGenerating(false)
      setGenPct(0)
      abortRef.current = null
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
    }
  }, [activeOllamaModel, contextFiles, diagnostics.blockingReason, executeWithRuntime, fixedSeed, getRecentMessages, height, isGenerating, preparePack, prompt, pushMessage, runtimeServices.comfyui.path, seed, selectedStyle, steps, visionModel, width])

  const downloadImage = useCallback((image: GeneratedImage, format: 'png' | 'jpeg' | 'webp' = 'png') => {
    const ext = format === 'jpeg' ? 'jpg' : format
    const filename = `juan-bike-${image.style}-${image.timestamp}.${ext}`
    const applyFormatConversion = async (sourceUrl: string) => {
      try {
        const response = await fetch(sourceUrl)
        const blob = await response.blob()
        if (format === 'png' && blob.type === 'image/png') {
          return blob
        }
        const bitmap = await createImageBitmap(blob)
        const canvas = document.createElement('canvas')
        canvas.width = bitmap.width
        canvas.height = bitmap.height
        const ctx = canvas.getContext('2d')
        if (!ctx) return blob
        if (format !== 'png') {
          ctx.fillStyle = '#091116'
          ctx.fillRect(0, 0, canvas.width, canvas.height)
        }
        ctx.drawImage(bitmap, 0, 0)
        const mime = format === 'jpeg' ? 'image/jpeg' : format === 'webp' ? 'image/webp' : 'image/png'
        const converted: Blob | null = await new Promise((resolve) =>
          canvas.toBlob((value) => resolve(value), mime, format === 'png' ? undefined : 0.93),
        )
        return converted ?? blob
      } catch {
        return null
      }
    }

    void (async () => {
      const blob = await applyFormatConversion(image.url)
      if (!blob) {
        window.open(image.url, '_blank')
        return
      }
      const blobUrl = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = blobUrl
      anchor.download = filename
      anchor.click()
      setTimeout(() => URL.revokeObjectURL(blobUrl), 1000)
    })()
  }, [])

  const downloadAllAsZip = useCallback(async () => {
    if (imagesRef.current.length === 0) return
    const { default: JSZip } = await import('jszip')
    const zip = new JSZip()
    const entries = imagesRef.current
    await Promise.all(entries.map(async (image, index) => {
      try {
        const response = await fetch(image.url)
        const blob = await response.blob()
        const ext = blob.type === 'image/png' ? 'png' : blob.type === 'image/jpeg' ? 'jpg' : blob.type === 'image/webp' ? 'webp' : 'png'
        const rank = String(index + 1).padStart(2, '0')
        const slug = promptSlug(image.prompt, 40)
        zip.file(`${rank}_${slug}_${image.timestamp}.${ext}`, blob)
      } catch {
      }
    }))
    const metadata = entries.map((image) => ({
      id: image.id,
      prompt: image.prompt,
      style: image.style,
      timestamp: image.timestamp,
    }))
    zip.file('metadata.json', JSON.stringify(metadata, null, 2))
    const blob = await zip.generateAsync({ type: 'blob' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `aurora-image-gallery-${Date.now()}.zip`
    anchor.click()
    setTimeout(() => URL.revokeObjectURL(url), 1500)
  }, [])

  const copyImageToClipboard = useCallback(async (image: GeneratedImage) => {
    try {
      const response = await fetch(image.url)
      const blob = await response.blob()
      const pngBlob = blob.type === 'image/png' ? blob : await (async () => {
        const bitmap = await createImageBitmap(blob)
        const canvas = document.createElement('canvas')
        canvas.width = bitmap.width
        canvas.height = bitmap.height
        const ctx = canvas.getContext('2d')
        if (!ctx) return blob
        ctx.drawImage(bitmap, 0, 0)
        return await new Promise<Blob>((resolve, reject) => {
          canvas.toBlob((value) => (value ? resolve(value) : reject(new Error('conversion PNG impossible'))), 'image/png')
        })
      })()
      if ('ClipboardItem' in window) {
        await navigator.clipboard.write([new ClipboardItem({ 'image/png': pngBlob })])
        setCopyFeedback(true)
        window.setTimeout(() => setCopyFeedback(false), 1600)
      }
    } catch {
    }
  }, [])

  const handleRegenerateSelected = useCallback(() => {
    if (!selectedImage) return
    setPrompt(selectedImage.prompt)
    setSelectedStyle(selectedImage.style)
    requestAnimationFrame(() => {
      void generate()
    })
  }, [generate, selectedImage])

  return (
    <div className="relative min-h-full flex flex-col">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute inset-0 aurora-mesh opacity-40" />
        <div className="absolute -top-40 -right-20 h-80 w-80 rounded-full bg-violet-500/20 blur-3xl" />
        <div className="absolute -bottom-40 -left-20 h-80 w-80 rounded-full bg-fuchsia-500/15 blur-3xl" />
      </div>
      <div className="relative">
      {isCloudRuntime() && runtimeServices.comfyui.available && !runtimeServices.comfyui.running && (
        <div className="mx-2 mb-3 mt-2 flex items-start gap-2 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300/90 sm:mx-6">
          <AlertCircle size={15} className="mt-0.5 shrink-0 text-emerald-400" />
          <span>
            ComfyUI installe — demarrage automatique a la premiere generation.
          </span>
        </div>
      )}
      <RecoveryBanner
        recovery={recovery}
        onRecovered={(result) => {
          if (result.url) {
            const recovered: GeneratedImage = {
              id: `rec-${Date.now()}`,
              url: result.url,
              prompt: result.generation.prompt,
              style: 'none',
              timestamp: Date.now(),
              storage: 'memory',
            }
            setImages(prev => [recovered, ...prev])
            setSelectedImage(recovered)
          }
        }}
      />
      <ClarificationDialog request={clarification} />
      <SaveDialog
        data={saveDialogData}
        onClose={() => setSaveDialogData(null)}
        onSaved={(savedPath) => {
          addPrompt({
            module: 'image',
            prompt: saveDialogData?.prompt ?? prompt,
            fidelityScore: saveDialogData?.fidelityScore ?? 90,
            parameters: saveDialogData?.parameters ?? {},
            tags: ['image'],
          })
          setSaveDialogData(null)
          setProgress(`Résultat sauvegardé: ${savedPath}`)
        }}
      />
      <PromptLibraryPanel
        open={promptLibraryOpen}
        onClose={() => setPromptLibraryOpen(false)}
        currentModule="image"
        onUsePrompt={(p) => setPrompt(p)}
      />
      <StudioHero
        icon={ImageIcon}
        eyebrow="Studio image"
        title="Rendu image net, suivi et persistant."
        description="Le module image sait maintenant creer depuis le texte ou editer une reference jointe en preservant l identite, le cadrage et les couleurs explicites, avec un suivi local lisible pendant la generation."
        diagnostics={diagnostics}
        stats={[
          { label: 'Pack', value: IMAGE_MODEL_PACK_LABEL },
          { label: 'Runtime', value: diagnostics.runtimeLabel, tone: 'good' },
          { label: 'Style actif', value: activeStyleLabel },
          {
            label: 'ComfyUI',
            value: runtimeServices.comfyui.running ? 'Actif' : runtimeServices.comfyui.available ? 'Auto-start' : 'Absent',
            tone: runtimeServices.comfyui.running ? 'good' : runtimeServices.comfyui.available ? 'default' : 'warn',
          },
        ]}
      />

      <div className="grid gap-3 px-2 pb-6 pt-3 sm:gap-4 sm:px-6 sm:pb-8 sm:pt-4 2xl:grid-cols-[23rem_minmax(0,1fr)]">
        <div className="2xl:sticky 2xl:top-4 self-start w-full overflow-y-auto overscroll-contain scroll-shell max-h-[60vh] sm:max-h-[calc(100vh-12rem)] rounded-[1.4rem] sm:rounded-[1.8rem] border border-aurora-border/40 bg-aurora-surface/55 p-3 sm:p-4 space-y-3 sm:space-y-4">
          <div className="rounded-[1.4rem] border border-aurora-border/35 bg-aurora-surface-2/70 p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-[11px] uppercase tracking-[0.22em] text-aurora-text-dim">Prompt</p>
                <p className="mt-2 text-sm text-aurora-text">
                  Decris la scene, la matiere, l eclairage et l intention visuelle.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPromptLibraryOpen(true)}
                  title="Bibliothèque de prompts"
                  className="flex h-8 w-8 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] hover:bg-white/[0.09] text-white/40 hover:text-violet-400 transition-colors"
                >
                  <BookOpen size={14} />
                </button>
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl gradient-accent text-white">
                  <Sparkles size={18} />
                </div>
              </div>
            </div>

            <textarea
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              placeholder="Ex: velo gravel orange atelier, eclairage studio, fond mineral, rendu propre et haut de gamme"
              rows={5}
              className="mt-4 w-full resize-none rounded-2xl border border-aurora-border bg-aurora-bg/60 px-3 py-3 text-sm text-aurora-text outline-none transition-colors focus:border-aurora-accent/45"
            />
            <div className="mt-2 flex items-center gap-2">
              <VoicePushToTalk
                onTranscript={(text) => setPrompt((prev) => (prev.trim() ? `${prev}, ${text}` : text))}
                label="Dicter ton prompt image"
                size={36}
              />
              <span className="text-[11px] text-aurora-text-dim">Dicte ce que tu veux voir.</span>
            </div>
            {promptHistory.length > 0 && (
              <div className="mt-2">
                <div className="text-[10px] uppercase tracking-wider text-aurora-text-dim mb-1">Prompts récents (clic pour réutiliser)</div>
                <div className="flex flex-wrap gap-1.5">
                  {promptHistory.map((p, i) => (
                    <button
                      key={i}
                      type="button"
                      onClick={() => { openPromptSession('image', p); setPrompt(p) }}
                      title={p}
                      className="rounded-md border border-white/10 bg-white/[0.03] px-2 py-0.5 text-[10px] font-mono text-aurora-text-dim hover:text-aurora-text max-w-[200px] truncate"
                    >
                      {p.slice(0, 38)}{p.length > 38 ? '…' : ''}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="rounded-[1.4rem] border border-aurora-border/35 bg-aurora-surface-2/60 p-3">
            <button
              onClick={() => setShowStyles((value) => !value)}
              className="flex w-full items-center justify-between rounded-2xl border border-aurora-border/35 bg-aurora-surface/75 px-3 py-3 text-left"
            >
              <div>
                <p className="text-[11px] uppercase tracking-[0.2em] text-aurora-text-dim">Style</p>
                <p className="mt-1 text-sm text-aurora-text">{activeStyleLabel}</p>
              </div>
              <ChevronDown size={16} className={`text-aurora-text-dim transition-transform ${showStyles ? 'rotate-180' : ''}`} />
            </button>

            <AnimatePresence>
              {showStyles && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="mt-3 grid grid-cols-2 gap-2"
                >
                  {styles.map((style) => (
                    <button
                      key={style.id}
                      onClick={() => {
                        setSelectedStyle(style.id)
                        setShowStyles(false)
                      }}
                      className={`rounded-xl px-3 py-2 text-left text-xs transition-colors ${
                        selectedStyle === style.id
                          ? 'gradient-accent text-white'
                          : 'bg-aurora-surface text-aurora-text-dim hover:text-aurora-text'
                      }`}
                    >
                      {style.label}
                    </button>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          <SessionSwitcher
            module="image"
            onSessionChange={(session) => {
              hydrateSession(session)
              setContextFiles([])
              setPrompt('')
              setSelectedStyle('none')
              setError(null)
              setProgress('')
            }}
          />

          {recentMessages.length > 0 && (
            <div className="rounded-[1.2rem] border border-aurora-border/30 bg-aurora-surface/55 px-3 py-3">
              <p className="text-[11px] uppercase tracking-[0.18em] text-aurora-text-dim">Continuite active</p>
              <p className="mt-2 text-xs leading-relaxed text-aurora-text">
                {recentMessages[recentMessages.length - 1]?.content?.slice(0, 180) || 'Historique charge.'}
              </p>
            </div>
          )}

          <ContextFilesField
            files={contextFiles}
            onFilesChange={setContextFiles}
            accept=".png,.jpg,.jpeg,.webp,.gif,.pdf,.txt,.md,.json,.csv,.tsv,.xlsx,.xls,.xlsm"
            hint="Ajoute references visuelles, PDF ou notes pour guider le rendu."
          />

          <ModuleAssetPackCard pack={assetPack} />
          <ConnectorRecommendationsPanel module="image" compact />

          <CompositionAdvisorCard width={width} height={height} />

          <PromptBuilderCard userPrompt={prompt} />

          <div className="rounded-[1.4rem] border border-aurora-border/35 bg-aurora-surface-2/60 p-3">
            <button
              onClick={() => setShowSettings((value) => !value)}
              className="flex items-center gap-2 text-xs text-aurora-text-dim hover:text-aurora-text transition-colors"
            >
              <Sliders size={14} />
              <span>Parametres de rendu</span>
              <ChevronDown size={12} className={`transition-transform ${showSettings ? 'rotate-180' : ''}`} />
            </button>

            <AnimatePresence>
              {showSettings && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="mt-3 space-y-3"
                >
                  <div>
                    <label className="mb-1 block text-[11px] text-aurora-text-dim">Format</label>
                    <div className="grid grid-cols-6 gap-1.5">
                      {([
                        { id: 'square', label: '1:1', w: 1024, h: 1024 },
                        { id: 'portrait34', label: '3:4', w: 1024, h: 1280 },
                        { id: 'portrait916', label: '9:16', w: 768, h: 1344 },
                        { id: 'landscape43', label: '4:3', w: 1280, h: 1024 },
                        { id: 'wide169', label: '16:9', w: 1536, h: 864 },
                        { id: 'cinema219', label: '21:9', w: 1680, h: 720 },
                      ] as const).map((preset) => {
                        const active = width === preset.w && height === preset.h
                        const max = 18
                        const r = preset.w / preset.h
                        const rw = r >= 1 ? max : max * r
                        const rh = r >= 1 ? max / r : max
                        return (
                          <button
                            key={preset.id}
                            type="button"
                            onClick={() => { setWidth(preset.w); setHeight(preset.h) }}
                            className={`flex flex-col items-center gap-1 rounded-xl px-1.5 py-1.5 transition-colors ${active ? 'bg-aurora-accent/20 border border-aurora-accent/55 text-aurora-accent-light' : 'bg-aurora-surface text-aurora-text-dim hover:text-aurora-text border border-aurora-border'}`}
                            title={`${preset.w}×${preset.h}`}
                          >
                            <svg width={max} height={max} viewBox={`0 0 ${max} ${max}`} aria-hidden="true">
                              <rect
                                x={(max - rw) / 2}
                                y={(max - rh) / 2}
                                width={rw}
                                height={rh}
                                fill={active ? 'currentColor' : 'rgba(255,255,255,0.45)'}
                                stroke={active ? 'currentColor' : 'rgba(255,255,255,0.25)'}
                                strokeWidth="0.8"
                                rx="1.2"
                              />
                            </svg>
                            <span className="text-[10px] font-mono">{preset.label}</span>
                          </button>
                        )
                      })}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="mb-1 block text-[11px] text-aurora-text-dim">Largeur</label>
                      <select
                        value={width}
                        onChange={(event) => setWidth(Number(event.target.value))}
                        className="w-full rounded-xl border border-aurora-border bg-aurora-surface px-3 py-2 text-xs text-aurora-text outline-none"
                      >
                        {[512, 768, 1024, 1280, 1536].map((value) => (
                          <option key={value} value={value}>{value}px</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="mb-1 block text-[11px] text-aurora-text-dim">Hauteur</label>
                      <select
                        value={height}
                        onChange={(event) => setHeight(Number(event.target.value))}
                        className="w-full rounded-xl border border-aurora-border bg-aurora-surface px-3 py-2 text-xs text-aurora-text outline-none"
                      >
                        {[512, 768, 1024, 1280, 1536].map((value) => (
                          <option key={value} value={value}>{value}px</option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div>
                    <div className="mb-1 flex items-center justify-between text-[11px] text-aurora-text-dim">
                      <span>Passes de denoise</span>
                      <span>{steps}</span>
                    </div>
                    <input
                      type="range"
                      min={10}
                      max={50}
                      value={steps}
                      onChange={(event) => setSteps(Number(event.target.value))}
                      className="w-full accent-aurora-accent"
                    />
                  </div>

                  <div>
                    <div className="mb-1 flex items-center justify-between text-[11px] text-aurora-text-dim">
                      <span>Seed</span>
                      <button
                        onClick={() => {
                          const next = !fixedSeed
                          setFixedSeed(next)
                          if (next && seed === null) setSeed(Math.floor(Math.random() * 2 ** 32))
                        }}
                        className="rounded-lg border border-aurora-border/50 bg-aurora-surface px-2 py-0.5 text-[10px] text-aurora-text-dim hover:text-aurora-text transition-colors"
                      >
                        {fixedSeed ? 'Fixe' : 'Aleatoire'}
                      </button>
                    </div>
                    {fixedSeed && (
                      <>
                        <input
                          type="number"
                          min={0}
                          max={4294967295}
                          value={seed ?? 0}
                          onChange={(event) => setSeed(Number(event.target.value))}
                          className="w-full rounded-xl border border-aurora-border bg-aurora-surface px-3 py-2 text-xs text-aurora-text outline-none"
                        />
                        {seedHistory.length > 0 && (
                          <div className="mt-2">
                            <div className="text-[10px] uppercase tracking-wider text-aurora-text-dim mb-1">Seeds récents</div>
                            <div className="flex flex-wrap gap-1.5">
                              {seedHistory.map((s) => (
                                <button
                                  key={s}
                                  type="button"
                                  onClick={() => setSeed(s)}
                                  title={`Réutiliser seed ${s}`}
                                  className={`rounded-md border px-2 py-0.5 text-[10px] font-mono transition-colors ${
                                    seed === s
                                      ? 'border-aurora-accent/60 bg-aurora-accent/15 text-aurora-accent-light'
                                      : 'border-white/10 bg-white/[0.03] text-aurora-text-dim hover:text-aurora-text'
                                  }`}
                                >
                                  {s}
                                </button>
                              ))}
                            </div>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          <div className="flex items-center gap-3">
            <div style={{ width: 56, height: 68, flexShrink: 0 }}>
              <LyraCharacter
                phase={isGenerating ? 'thinking' : prompt.length > 8 ? 'speaking' : 'idle'}
                emotion={isGenerating ? 'focus' : prompt.length > 8 ? 'happy' : 'curious'}
                accent="#ff8c42"
                size={56}
                amplitude={isGenerating ? 0.5 : 0}
              />
            </div>
            <button
              onClick={() => void generate()}
              disabled={!canGenerate}
              className={`flex flex-1 items-center justify-center gap-2 rounded-[1.4rem] px-4 py-3 text-sm font-medium transition-all ${
                canGenerate
                  ? 'gradient-accent text-white glow-accent'
                  : 'bg-aurora-surface-2 text-aurora-text-dim opacity-60 cursor-not-allowed'
              }`}
            >
              {isGenerating ? (
                <>
                  <Loader2 size={18} className="animate-spin" />
                  <span>{genPct > 0 ? `${genPct}%` : 'Generation...'}</span>
                </>
              ) : (
                <>
                  <Wand2 size={18} />
                  <span>Generer le rendu</span>
                </>
              )}
            </button>
            {isGenerating && (
              <button
                onClick={() => abortRef.current?.abort()}
                className="flex items-center justify-center rounded-[1.4rem] border border-aurora-red/40 bg-aurora-red/10 px-4 py-3 text-aurora-red hover:bg-aurora-red/20 transition-colors"
                title="Annuler la generation"
              >
                <X size={18} />
              </button>
            )}
          </div>

          {(error || progress) && (
            <div className="space-y-3">
              {progress && (
                <div className="rounded-2xl border border-aurora-border/40 bg-aurora-surface/70 px-4 py-3">
                  <div className="flex items-center justify-between">
                    <p className="text-[11px] uppercase tracking-[0.2em] text-aurora-text-dim">Etat courant</p>
                    {genPct > 0 && isGenerating && (
                      <span className="text-[11px] font-medium text-aurora-accent">{genPct}%</span>
                    )}
                  </div>
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

          <StudioDiagnosticsPanel diagnostics={diagnostics} title="Preflight image" />
        </div>

        <div className="min-w-0 rounded-[1.8rem] border border-aurora-border/40 bg-aurora-surface/45 overflow-hidden">
          <div className="border-b border-aurora-border/30 px-5 py-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-[11px] uppercase tracking-[0.22em] text-aurora-text-dim">Sortie</p>
                <h2 className="mt-1 text-lg font-semibold text-aurora-text">Viewer image local</h2>
              </div>

              {selectedImage && (
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    onClick={() => downloadImage(selectedImage, 'png')}
                    className="inline-flex items-center gap-1.5 rounded-xl border border-aurora-border/40 bg-aurora-surface-2 px-3 py-2 text-xs text-aurora-text hover:border-aurora-accent/35 transition-colors"
                    title="Telecharger PNG"
                  >
                    <Download size={14} />
                    PNG
                  </button>
                  <button
                    onClick={() => downloadImage(selectedImage, 'jpeg')}
                    className="inline-flex items-center gap-1.5 rounded-xl border border-aurora-border/40 bg-aurora-surface-2 px-3 py-2 text-xs text-aurora-text hover:border-aurora-accent/35 transition-colors"
                    title="Telecharger JPG"
                  >
                    <Download size={14} />
                    JPG
                  </button>
                  <button
                    onClick={() => downloadImage(selectedImage, 'webp')}
                    className="inline-flex items-center gap-1.5 rounded-xl border border-aurora-border/40 bg-aurora-surface-2 px-3 py-2 text-xs text-aurora-text hover:border-aurora-accent/35 transition-colors"
                    title="Telecharger WEBP"
                  >
                    <Download size={14} />
                    WEBP
                  </button>
                  <button
                    onClick={() => void copyImageToClipboard(selectedImage)}
                    className={`inline-flex items-center gap-1.5 rounded-xl border px-3 py-2 text-xs transition-colors ${
                      copyFeedback
                        ? 'border-aurora-green/40 bg-aurora-green/10 text-aurora-green'
                        : 'border-aurora-border/40 bg-aurora-surface-2 text-aurora-text hover:border-aurora-accent/35'
                    }`}
                    title="Copier l image dans le presse-papiers"
                  >
                    <ImageIcon size={14} />
                    {copyFeedback ? 'Copiee !' : 'Copier'}
                  </button>
                  <button
                    onClick={() => setFullscreenImage(selectedImage)}
                    className="inline-flex items-center gap-1.5 rounded-xl border border-aurora-border/40 bg-aurora-surface-2 px-3 py-2 text-xs text-aurora-text hover:border-aurora-accent/35 transition-colors"
                    title="Voir en plein ecran"
                  >
                    ⤢ Plein
                  </button>
                  <button
                    onClick={handleRegenerateSelected}
                    className="inline-flex items-center gap-1.5 rounded-xl border border-aurora-border/40 bg-aurora-surface-2 px-3 py-2 text-xs text-aurora-text hover:border-aurora-accent/35 transition-colors"
                  >
                    <RefreshCw size={14} />
                    Relancer
                  </button>
                </div>
              )}
            </div>
          </div>

          <div className="flex min-h-[34rem] flex-col">
            <div className="flex min-h-[28rem] flex-1 items-center justify-center p-6">
              {selectedImage ? (
                <motion.div
                  initial={{ opacity: 0, scale: 0.98 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="relative w-full h-full rounded-[2rem] border border-aurora-border/35 bg-[#0c161b] overflow-hidden"
                >
                  <div className="absolute inset-0 pointer-events-none">
                    <div className="absolute -top-8 left-12 h-48 w-48 rounded-full bg-aurora-accent/10 blur-[100px]" />
                    <div className="absolute bottom-0 right-0 h-56 w-56 rounded-full bg-aurora-cyan/10 blur-[120px]" />
                  </div>
                  <img
                    src={selectedImage.url}
                    alt={selectedImage.prompt}
                    onClick={() => setFullscreenImage(selectedImage)}
                    className="relative z-[1] h-full w-full cursor-zoom-in object-contain"
                  />
                  <div className="absolute left-3 right-3 bottom-3 z-[2] rounded-[1rem] border border-aurora-border/35 bg-aurora-surface/85 px-3 py-2 backdrop-blur-xl sm:left-5 sm:right-5 sm:bottom-5 sm:rounded-[1.4rem] sm:px-4 sm:py-3">
                    <p className="text-xs text-aurora-text line-clamp-2 sm:text-sm">{selectedImage.prompt}</p>
                    <p className="mt-1 text-[10px] text-aurora-text-dim sm:text-[11px]">
                      {styles.find((style) => style.id === selectedImage.style)?.label || 'Auto / Libre'}
                      {' / '}
                      {new Date(selectedImage.timestamp).toLocaleTimeString('fr-FR')}
                    </p>
                  </div>
                </motion.div>
              ) : (
                <div className="text-center">
                  <div className="mx-auto flex h-24 w-24 items-center justify-center rounded-[1.8rem] border border-aurora-border bg-aurora-surface-2">
                    <ImageIcon size={42} className="text-aurora-text-dim" />
                  </div>
                  <p className="mt-4 text-sm text-aurora-text-muted">
                    Lance un rendu pour remplir la galerie et afficher l image finale ici.
                  </p>
                </div>
              )}
            </div>

            {images.length > 0 && (
              <div className="border-t border-aurora-border/30 px-5 py-4">
                <div className="mb-3 flex items-center justify-between">
                  <p className="text-[11px] uppercase tracking-[0.22em] text-aurora-text-dim">
                    Galerie locale ({images.length})
                  </p>
                  <button
                    onClick={() => void downloadAllAsZip()}
                    className="inline-flex items-center gap-1.5 rounded-xl border border-aurora-border/50 bg-aurora-surface-2 px-3 py-1.5 text-[11px] text-aurora-text-dim hover:text-aurora-text transition-colors"
                    title="Telecharger toute la galerie en ZIP avec metadata.json"
                  >
                    <Download size={12} />
                    <span>Galerie ZIP</span>
                  </button>
                </div>
                <div className="flex gap-3 overflow-x-auto pb-1">
                  {images.map((image) => (
                    <div key={image.id} className="shrink-0 flex flex-col items-center gap-1">
                      <button
                        onClick={() => setSelectedImage(image)}
                        className={`group relative h-24 w-24 overflow-hidden rounded-2xl border transition-all ${
                          selectedImage?.id === image.id
                            ? 'border-aurora-accent glow-accent'
                            : 'border-aurora-border/40 hover:border-aurora-border-light'
                        }`}
                      >
                        <img src={image.url} alt="" className="h-full w-full object-cover transition-transform group-hover:scale-105" />
                      </button>
                      <button
                        onClick={() => { setPrompt(image.prompt); setSelectedStyle(image.style) }}
                        className="rounded-full border border-white/8 bg-white/[0.04] px-2 py-0.5 text-[9px] text-aurora-text-dim hover:border-aurora-accent/30 hover:text-aurora-text transition-colors"
                        title={image.prompt}
                      >
                        Reutiliser
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {fullscreenImage && (
        <div
          className="fixed inset-0 z-40 flex items-center justify-center bg-black/92 backdrop-blur-sm p-4"
          onClick={() => setFullscreenImage(null)}
        >
          <div
            className="relative max-h-full max-w-full"
            onClick={(event) => event.stopPropagation()}
          >
            <img
              src={fullscreenImage.url}
              alt={fullscreenImage.prompt}
              className="max-h-[90vh] max-w-[92vw] rounded-2xl shadow-2xl"
            />
            <div className="absolute inset-x-4 bottom-4 rounded-2xl border border-aurora-border/40 bg-aurora-surface/80 px-4 py-3 backdrop-blur-xl">
              <p className="text-sm text-aurora-text line-clamp-2">{fullscreenImage.prompt}</p>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <button
                  onClick={() => downloadImage(fullscreenImage, 'png')}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-aurora-border/40 bg-aurora-surface-2 px-3 py-1.5 text-[11px] text-aurora-text hover:border-aurora-accent/35"
                >
                  <Download size={12} />
                  PNG
                </button>
                <button
                  onClick={() => downloadImage(fullscreenImage, 'jpeg')}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-aurora-border/40 bg-aurora-surface-2 px-3 py-1.5 text-[11px] text-aurora-text hover:border-aurora-accent/35"
                >
                  <Download size={12} />
                  JPG
                </button>
                <button
                  onClick={() => downloadImage(fullscreenImage, 'webp')}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-aurora-border/40 bg-aurora-surface-2 px-3 py-1.5 text-[11px] text-aurora-text hover:border-aurora-accent/35"
                >
                  <Download size={12} />
                  WEBP
                </button>
                <button
                  onClick={() => { setPrompt(fullscreenImage.prompt); setSelectedStyle(fullscreenImage.style); setFullscreenImage(null) }}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-aurora-border/40 bg-aurora-surface-2 px-3 py-1.5 text-[11px] text-aurora-text hover:border-aurora-accent/35"
                >
                  <RefreshCw size={12} />
                  Reutiliser
                </button>
                <span className="ml-auto text-[10px] text-aurora-text-dim">
                  {styles.find((style) => style.id === fullscreenImage.style)?.label || 'Auto'}
                  {' · '}
                  {new Date(fullscreenImage.timestamp).toLocaleString('fr-FR')}
                </span>
              </div>
            </div>
            <button
              onClick={() => setFullscreenImage(null)}
              className="absolute -top-2 -right-2 rounded-full border border-aurora-border bg-aurora-surface-2 p-2 text-aurora-text-dim hover:text-aurora-red shadow-lg"
              aria-label="Fermer"
            >
              <X size={16} />
            </button>
          </div>
        </div>
      )}
      </div>
    </div>
  )
}

function PromptBuilderCard({ userPrompt }: { userPrompt: string }) {
  const [customNegative, setCustomNegative] = useState<string>(() => {
    if (typeof window === 'undefined') return ''
    try { return window.localStorage.getItem('aurora.image.customNegative') || '' } catch { return '' }
  })
  useEffect(() => {
    try { window.localStorage.setItem('aurora.image.customNegative', customNegative) } catch {}
  }, [customNegative])
  const trimmed = userPrompt.trim()
  if (!trimmed) {
    return (
      <div className="rounded-[1.4rem] border border-aurora-border/35 bg-aurora-surface-2/60 p-4">
        <p className="text-[11px] uppercase tracking-[0.22em] text-aurora-text-dim">Prompt builder expert</p>
        <p className="mt-2 text-[12px] text-aurora-text-dim italic">
          Tape une description ci-dessus — Aurora décompose en sujet + composition + lumière + style + qualifiers FLUX, puis livre le prompt prêt-à-injecter avec négatif et plan d'upscale.
        </p>
      </div>
    )
  }
  const brief = parseBrief(trimmed)
  const built = buildPrompt(brief)
  const chips: Array<{ label: string; value: string; tone: string }> = []
  chips.push({ label: 'sujet', value: brief.subject.slice(0, 40), tone: 'sky' })
  if (brief.style) chips.push({ label: 'style', value: brief.style, tone: 'violet' })
  if (brief.lighting) chips.push({ label: 'lumière', value: brief.lighting, tone: 'amber' })
  if (brief.composition) chips.push({ label: 'composition', value: brief.composition, tone: 'emerald' })
  if (brief.mood) chips.push({ label: 'mood', value: brief.mood, tone: 'rose' })
  if (brief.aspectRatio) chips.push({ label: 'ratio', value: brief.aspectRatio, tone: 'cyan' })
  if (brief.highResolution) chips.push({ label: 'upscale', value: 'realesrgan x4', tone: 'lime' })
  if (brief.paletteHints && brief.paletteHints.length > 0) {
    chips.push({ label: 'palette', value: brief.paletteHints.join(' · '), tone: 'fuchsia' })
  }
  const toneClass: Record<string, string> = {
    sky: 'bg-sky-500/15 text-sky-200 border-sky-500/30',
    violet: 'bg-violet-500/15 text-violet-200 border-violet-500/30',
    amber: 'bg-amber-500/15 text-amber-200 border-amber-500/30',
    emerald: 'bg-emerald-500/15 text-emerald-200 border-emerald-500/30',
    rose: 'bg-rose-500/15 text-rose-200 border-rose-500/30',
    cyan: 'bg-cyan-500/15 text-cyan-200 border-cyan-500/30',
    lime: 'bg-lime-500/15 text-lime-200 border-lime-500/30',
    fuchsia: 'bg-fuchsia-500/15 text-fuchsia-200 border-fuchsia-500/30',
  }
  const copy = (text: string) => navigator.clipboard.writeText(text).catch(() => undefined)
  return (
    <div className="rounded-[1.4rem] border border-aurora-border/35 bg-aurora-surface-2/60 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-[11px] uppercase tracking-[0.22em] text-aurora-text-dim">Prompt builder expert</p>
        <span className="text-[10px] text-aurora-text-dim font-mono">{built.width}×{built.height}</span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {chips.map((c, i) => (
          <span key={i} className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[10px] font-mono ${toneClass[c.tone] ?? toneClass.sky}`}>
            <span className="opacity-70 uppercase">{c.label}</span>
            <span>{c.value}</span>
          </span>
        ))}
      </div>
      <div>
        <div className="flex items-center justify-between mb-1">
          <span className="text-[10px] uppercase tracking-wider text-aurora-text-dim">Positive (FLUX-ready)</span>
          <button
            onClick={() => copy(built.positive)}
            className="text-[10px] rounded bg-white/5 border border-white/10 px-2 py-0.5 hover:bg-white/10 text-aurora-text-dim"
          >copier</button>
        </div>
        <div className="rounded-md bg-black/40 border border-white/5 p-2 text-[11px] font-mono text-aurora-text break-words max-h-28 overflow-auto">
          {built.positive}
        </div>
      </div>
      <div>
        <div className="flex items-center justify-between mb-1">
          <span className="text-[10px] uppercase tracking-wider text-aurora-text-dim">Negative (auto)</span>
          <button
            onClick={() => copy(`${built.negative}${customNegative.trim() ? `, ${customNegative.trim()}` : ''}`)}
            className="text-[10px] rounded bg-white/5 border border-white/10 px-2 py-0.5 hover:bg-white/10 text-aurora-text-dim"
          >copier</button>
        </div>
        <div className="rounded-md bg-black/30 border border-white/5 p-2 text-[10px] font-mono text-rose-200/80 break-words max-h-20 overflow-auto">
          {built.negative}
        </div>
        <div className="mt-2">
          <div className="text-[10px] uppercase tracking-wider text-aurora-text-dim mb-1">Negative custom (tu ajoutes)</div>
          <input
            id="image-custom-negative"
            name="imageCustomNegative"
            type="text"
            value={customNegative}
            onChange={(e) => setCustomNegative(e.target.value)}
            placeholder="ex. blurry, deformed, low quality, extra fingers"
            className="w-full rounded-md bg-black/30 border border-white/10 px-2 py-1 text-[11px] text-rose-200/85 font-mono outline-none focus:border-rose-500/40"
          />
        </div>
      </div>
      <PromptDiffPreview before={trimmed} after={built.positive} />
    </div>
  )
}

function PromptDiffPreview({ before, after }: { before: string; after: string }) {
  const diff = useMemo(() => diffPrompts(before, after), [before, after])
  if (diff.added.length === 0 && diff.removed.length === 0) return null
  return (
    <div className="rounded-md bg-black/30 border border-white/5 p-2 text-[10px]">
      <div className="flex items-center justify-between mb-1">
        <span className="uppercase tracking-wider text-aurora-text-dim">Aurora ajoute / retire</span>
        <span className="text-aurora-text-dim font-mono">∆ {Math.round(diff.changeRatio * 100)}%</span>
      </div>
      {diff.added.length > 0 && (
        <div className="mb-1">
          <span className="text-emerald-300/80 mr-1">+</span>
          {diff.added.map((s, i) => (
            <span key={i} className="inline-block mr-1 mb-1 rounded bg-emerald-500/15 border border-emerald-500/30 px-1.5 py-0.5 font-mono text-emerald-200">
              {s.raw}
            </span>
          ))}
        </div>
      )}
      {diff.removed.length > 0 && (
        <div>
          <span className="text-rose-300/80 mr-1">−</span>
          {diff.removed.map((s, i) => (
            <span key={i} className="inline-block mr-1 mb-1 rounded bg-rose-500/15 border border-rose-500/30 px-1.5 py-0.5 font-mono text-rose-200 line-through">
              {s.raw}
            </span>
          ))}
        </div>
      )}
      <p className="mt-1 text-aurora-text-dim italic text-[10px]">{diff.summary}</p>
    </div>
  )
}

function CompositionAdvisorCard({ width, height }: { width: number; height: number }) {
  const aspect = width / Math.max(1, height)
  const style: 'portrait' | 'landscape' | 'classic' | 'cinematic' =
    aspect > 1.6 ? 'cinematic'
      : aspect < 0.8 ? 'portrait'
        : aspect > 1.1 ? 'landscape'
          : 'classic'
  const placement = recommendPlacement(style)

  const W = 160
  const H = Math.round((160 * height) / width)
  return (
    <div className="rounded-[1.4rem] border border-aurora-border/35 bg-aurora-surface-2/60 p-3">
      <p className="text-[11px] uppercase tracking-[0.22em] text-aurora-text-dim">Composition</p>
      <div className="mt-2 flex items-start gap-3">
        <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} className="rounded-md bg-black/50 border border-white/10 shrink-0">
          <rect x="0" y="0" width={W} height={H} fill="transparent" />
          <line x1={W / 3} y1="0" x2={W / 3} y2={H} stroke="rgba(255,255,255,0.18)" strokeDasharray="2 2" />
          <line x1={(W * 2) / 3} y1="0" x2={(W * 2) / 3} y2={H} stroke="rgba(255,255,255,0.18)" strokeDasharray="2 2" />
          <line x1="0" y1={H / 3} x2={W} y2={H / 3} stroke="rgba(255,255,255,0.18)" strokeDasharray="2 2" />
          <line x1="0" y1={(H * 2) / 3} x2={W} y2={(H * 2) / 3} stroke="rgba(255,255,255,0.18)" strokeDasharray="2 2" />
          <path d={`M 0 ${H} Q ${W * 0.62} ${H} ${W * 0.62} ${H * 0.38} T ${W} 0`} stroke="rgba(251,191,36,0.45)" fill="none" />
          <circle cx={placement.x * W} cy={placement.y * H} r="5" fill="rgba(248,113,113,0.95)" stroke="white" strokeWidth="1.5" />
          <text x={placement.x * W + 8} y={placement.y * H + 4} fontSize="9" fill="white" fontFamily="monospace">sujet</text>
        </svg>
        <div className="text-[11px] text-aurora-text">
          <div>
            <span className="text-aurora-text-dim">Cadrage : </span>
            <span className="text-aurora-text font-medium">{style}</span>
          </div>
          <div className="mt-1">
            <span className="text-aurora-text-dim">Ratio : </span>
            <span className="font-mono">{aspect.toFixed(2)}:1</span>
          </div>
          <div className="mt-1">
            <span className="text-aurora-text-dim">Sujet : </span>
            <span className="font-mono">({placement.x.toFixed(2)}, {placement.y.toFixed(2)})</span>
          </div>
          <p className="mt-2 text-[10px] text-aurora-text-dim leading-snug">
            {style === 'cinematic' && 'Format large : sujet 4:6 horizontalement, ligne basse. Espace pour panoramique.'}
            {style === 'portrait' && 'Visage à 40% de la hauteur, pas centré pile — lead-room au-dessus.'}
            {style === 'landscape' && 'Horizon dans le tiers bas — ciel dominant, profondeur via les diagonales.'}
            {style === 'classic' && 'Sujet sur intersection des tiers haut-gauche : règle des tiers, équilibre dynamique.'}
          </p>
        </div>
      </div>
    </div>
  )
}
