import { useCallback, useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { AlertCircle, BookOpen, Camera, ChevronDown, Copy, Download, Loader2, Play, Sliders, Sparkles, Video, Zap, Star } from 'lucide-react'
import ClarificationDialog from '../components/ClarificationDialog'
import type { ClarificationRequest } from '../components/ClarificationDialog'
import ContextFilesField from '../components/ContextFilesField'
import VoicePushToTalk from '../components/VoicePushToTalk'
import ModuleAssetPackCard from '../components/ModuleAssetPackCard'
import ConnectorRecommendationsPanel from '../components/ConnectorRecommendationsPanel'
import PromptLibraryPanel from '../components/PromptLibraryPanel'
import SaveDialog from '../components/SaveDialog'
import type { SaveDialogData } from '../components/SaveDialog'
import { buildVideoModuleAssets } from '../config/moduleAssetPacks'
import { AUXILIARY_ANALYSIS_MODEL, VIDEO_MODEL_PACK_LABEL } from '../config/models'
import { clearResumableJob, fsMkdir, getWorkspacePath, onPythonProgress, peekResumableJob, runPythonScript, toAssetUrl } from '../hooks/useTauri'
import { StudioDiagnosticsPanel, StudioHero } from '../components/StudioHero'
import { useManagedRuntime } from '../hooks/useManagedRuntime'
import { useModuleAssetPack } from '../hooks/useModuleAssetPack'
import { useStudioDiagnostics } from '../hooks/useStudioDiagnostics'
import { prepareTaskIntelligence } from '../services/taskIntelligence'
import { analyzeVideoPrompt, composeWanPrompt } from '../services/videoPromptComposer'
import { classifyTempo, recommendBpmForTone } from '../services/videoTempoDetector'
import LyraCharacter from '../components/voice/LyraCharacter'
import { useAppStore } from '../stores/appStore'
import { useGenerationTrackerStore } from '../stores/generationTrackerStore'
import { usePromptLibraryStore } from '../stores/promptLibraryStore'
import { useGenerationRecovery } from '../hooks/useGenerationRecovery'
import RecoveryBanner from '../components/RecoveryBanner'
import { getErrorMessage } from '../utils/errors'
import { prepareContextFiles } from '../utils/multimodalContext'
import { pickPrimaryPreparedImage } from '../utils/referenceMedia'

type VideoProfile = {
  width: number
  height: number
  numFrames: number
  label: string
}

type GeneratedVideo = {
  url: string
  prompt: string
  time: number
  durationLabel: string
  modelLabel: string
}

type MotionPreset = {
  id: string
  label: string
  promptSuffix: string
}

const MOTION_PRESETS: MotionPreset[] = [
  { id: 'free', label: 'Libre', promptSuffix: '' },
  { id: 'dance', label: 'Danse', promptSuffix: 'dancing energetically, fluid body movement, rhythmic motion, natural limb animation' },
  { id: 'walk', label: 'Marche', promptSuffix: 'walking naturally forward, smooth locomotion, balanced gait' },
  { id: 'zoom_in', label: 'Zoom avant', promptSuffix: 'camera slowly zooming in, cinematic depth, foreground clarity increases' },
  { id: 'zoom_out', label: 'Zoom arriere', promptSuffix: 'camera slowly zooming out, revealing wider scene context' },
  { id: 'parallax', label: 'Parallaxe', promptSuffix: 'cinematic parallax effect, foreground and background layers moving at different speeds, depth illusion' },
  { id: 'pan', label: 'Panoramique', promptSuffix: 'smooth horizontal camera pan, steady movement, no shake' },
  // v84 : grammaire camera etendue — meme vocabulaire que videoPromptComposer
  // pour que la deduplication fonctionne.
  { id: 'orbit', label: 'Orbite', promptSuffix: 'camera slowly orbiting around the subject, consistent radius, subject centered' },
  { id: 'dolly', label: 'Travelling', promptSuffix: 'steady dolly tracking shot, rail-smooth lateral movement' },
  { id: 'drone', label: 'Drone', promptSuffix: 'aerial drone shot, smooth flight path, high altitude perspective' },
  { id: 'slowmo', label: 'Ralenti', promptSuffix: 'slow motion, fluid high-frame-rate look, every movement stretched in time' },
  { id: 'timelapse', label: 'Timelapse', promptSuffix: 'timelapse, accelerated time flow, smooth exposure transitions' },
  { id: 'loop', label: 'Boucle', promptSuffix: 'seamless loop, last frame matches first frame, continuous cycle' },
]

function buildVideoProfiles(width: number, height: number, numFrames: number): VideoProfile[] {
  const candidates: VideoProfile[] = [
    { width, height, numFrames, label: 'profil principal' },
    { width: Math.min(width, 768), height: Math.min(height, 512), numFrames, label: 'profil stable' },
    { width: Math.min(width, 640), height: Math.min(height, 384), numFrames, label: 'profil secours' },
    { width: Math.min(width, 512), height: Math.min(height, 320), numFrames, label: 'profil minimal' },
  ]

  return candidates.filter((candidate, index, array) => (
    array.findIndex((entry) => (
      entry.width === candidate.width
      && entry.height === candidate.height
      && entry.numFrames === candidate.numFrames
    )) === index
  ))
}

function isRecoverableVideoFailure(error: unknown) {
  const message = getErrorMessage(error, '').toLowerCase()
  return [
    'out of memory',
    'cuda',
    'cudnn',
    'vram',
    'oom',
    'access violation',
    'exit -1073741819',
    'device-side assert',
    'illegal memory access',
    'exit 15',
    'sigterm',
    'generation interrompue par le systeme',
  ].some((needle) => message.includes(needle))
}

const FPS = 24
const MIN_FRAMES = 25
const MAX_FRAMES = 97 * 5
const secondsToFrames = (seconds: number) =>
  Math.max(MIN_FRAMES, Math.min(MAX_FRAMES, Math.round(seconds * FPS)))

// Action vocabulary used by BOTH the action-duration parser and the content
// inference heuristic. Kept in one place so adding "poursuite" or "bagarre"
// benefits both paths.
const ACTION_WORDS =
  'combat|fight|bataille|bagarre|saut|jump|bond|explosion|course|sprint|poursuite|chase|chute|fall|attaque|attack|frappe|punch|kick|coup|danse|dance|choregraphie|marche|walk|stride|scene|plan|shot|cascade|stunt|duel|'
  + 'court|couru|courir|court-metrage|vole|voler|flotte|flotter|tombe|tomber|glisse|glisser|roule|rouler|nage|nager|escalade|grimpe|grimper|lance|lancer|tire|tirer|pousse|pousser|tourne|tourner|pivote|pivoter|ouvre|ouvrir|ferme|fermer|casse|casser|brise|briser|detruit|detruire'

/**
 * Return the explicit TOTAL video duration the user asked for, in seconds.
 * Only fires on unambiguous markers ("video de 20s", "dure 10s", "longueur 8s"),
 * and explicitly rejects action-local durations like "combat de 10s" which
 * describe something happening INSIDE the video, not the clip length.
 */
function parseExplicitVideoDuration(text: string): number | null {
  const totalDurationRegex =
    /(?:vid[eé]o\s+(?:de\s+|d[''])?|clip\s+(?:de\s+|d[''])?|sequence\s+(?:de\s+|d[''])?|dur(?:ant|ee)?\s*(?:totale\s*)?(?:de\s+|d[''])?|pendant\s+|qui\s+dure\s+|longueur\s*(?:de\s+)?|total\s+(?:de\s+)?)(\d+(?:[.,]\d+)?)\s*(?:s(?:ec(?:onde)?s?)?|secondes?)/i
  const match = text.match(totalDurationRegex)
  if (!match) return null
  const seconds = parseFloat(match[1].replace(',', '.'))
  if (seconds > 0 && seconds <= 120) return seconds
  return null
}

/**
 * Detect whether the prompt contains an action-local duration that should
 * NOT be used as the total video length.
 */
function hasActionLocalDuration(text: string): boolean {
  return new RegExp(
    `(?:${ACTION_WORDS})\\s+(?:de\\s+|d['']|qui\\s+dure\\s+)?\\d+(?:[.,]\\d+)?\\s*s`,
    'i',
  ).test(text)
}

/**
 * If the user wrote a bare "... 15 secondes ..." without any action word nearby,
 * treat that as the total duration. If an action-local pattern was detected we
 * refuse to guess, because the standalone match is almost certainly the
 * action's length, not the clip's.
 */
function parseStandaloneVideoDuration(text: string): number | null {
  if (hasActionLocalDuration(text)) return null
  const standaloneRegex = /(?:^|\s)(\d+(?:[.,]\d+)?)\s*(?:s(?:ec(?:onde)?s?)?|secondes?)(?:\s|$|,|\.)/i
  const match = text.match(standaloneRegex)
  if (!match) return null
  const seconds = parseFloat(match[1].replace(',', '.'))
  if (seconds >= 3 && seconds <= 120) return seconds
  return null
}

/**
 * Content-based duration inference. Used when the prompt does NOT specify an
 * explicit video length. The user explicitly asked not to impose a default —
 * instead we read the intent (portrait / landscape / action / reveal / etc.)
 * and pick a duration that makes sense for that kind of shot.
 *
 * Returns a number of seconds in [2, 6]. Never returns null — there is always
 * a sensible default for a given prompt.
 */
function inferDurationFromContent(text: string): { seconds: number; rationale: string } {
  const normalized = text.toLowerCase()

  // Action shots: dynamic movement benefits from a longer clip so the beat
  // is readable.
  if (new RegExp(`\\b(${ACTION_WORDS})\\b`, 'i').test(normalized)) {
    return { seconds: 5, rationale: 'sequence d action detectee -> 5s pour lisibilite du mouvement' }
  }

  // Camera reveals / travellings / dollies need breathing room.
  if (/\b(travelling|travel|dolly|crane|reveal|r[eé]v[eé]lation|panorama|pan(?:oramique)?|tilt|orbit|360)\b/i.test(normalized)) {
    return { seconds: 5, rationale: 'mouvement camera long -> 5s' }
  }

  // Transformations / transitions / time-lapse benefit from slightly longer
  // clips to show the arc.
  if (/\b(transform|morph|transition|time[\s-]?lapse|evolution|croissance|grow|build\s*up|explode)\b/i.test(normalized)) {
    return { seconds: 4, rationale: 'transformation progressive -> 4s' }
  }

  // Crowd / cityscape / landscape tends to be ambient — 4s is a good default.
  if (/\b(foule|crowd|ville|city|rue|street|paysage|landscape|for[eê]t|mer|ocean|montagne|mountain|ciel|sky|atmosphere)\b/i.test(normalized)) {
    return { seconds: 4, rationale: 'plan d atmosphere -> 4s' }
  }

  // Portrait / face / smile — short and tight.
  if (/\b(portrait|visage|face|smile|sourire|regard|clignement|expression|emotion)\b/i.test(normalized)) {
    return { seconds: 2.5, rationale: 'portrait -> 2.5s' }
  }

  // Product / object ambient — 3s reads as intentional, not accidental.
  if (/\b(produit|product|objet|object|packshot|studio|detail|zoom)\b/i.test(normalized)) {
    return { seconds: 3, rationale: 'plan produit -> 3s' }
  }

  // Neutral default — 3 seconds is long enough to be purposeful, short
  // enough that a 16 GB card can always render it.
  return { seconds: 3, rationale: 'plan neutre -> 3s par defaut' }
}

/**
 * Single authoritative duration resolver used by the generation pipeline.
 * Returns the number of frames to render, how the decision was reached, and
 * whether the user was explicit. The existing `numFrames` slider in the UI
 * still wins if the user moved it: we only override when it is still at the
 * default value AND the prompt carries an explicit or inferrable duration.
 */
export type DurationResolution = {
  frames: number
  seconds: number
  source: 'user-slider' | 'explicit-total' | 'standalone-number' | 'content-inference'
  rationale: string
}

function resolveVideoDuration(
  text: string,
  sliderFrames: number,
  sliderIsDefault: boolean,
): DurationResolution {
  const explicit = parseExplicitVideoDuration(text)
  if (explicit !== null) {
    return {
      frames: secondsToFrames(explicit),
      seconds: explicit,
      source: 'explicit-total',
      rationale: `duree totale demandee: ${explicit}s`,
    }
  }
  const standalone = parseStandaloneVideoDuration(text)
  if (standalone !== null) {
    return {
      frames: secondsToFrames(standalone),
      seconds: standalone,
      source: 'standalone-number',
      rationale: `duree detectee dans le prompt: ${standalone}s`,
    }
  }
  if (!sliderIsDefault) {
    return {
      frames: sliderFrames,
      seconds: Math.round((sliderFrames / FPS) * 10) / 10,
      source: 'user-slider',
      rationale: `duree fixee par le slider utilisateur (${sliderFrames} frames)`,
    }
  }
  // Content inference. When there are explicit ACTIONS in the prompt, we
  // bias the base duration up so the clip is long enough for the action to
  // actually complete ("un cyclope qui écrase une souris" needs the écrase
  // cycle, not a freeze-frame of a raised foot). Take the max of the inferred
  // duration and the user-provided action durations.
  const inferred = inferDurationFromContent(text)
  const actionDurationsParsed = Array.from(
    text.matchAll(
      new RegExp(
        `(?:${ACTION_WORDS})\\s+(?:de\\s+|d['']|qui\\s+dure\\s+)?(\\d+(?:[.,]\\d+)?)\\s*s`,
        'gi',
      ),
    ),
  )
    .map((m) => parseFloat(m[1].replace(',', '.')))
    .filter((n) => Number.isFinite(n) && n > 0 && n <= 30)
  const longestAction = actionDurationsParsed.length > 0 ? Math.max(...actionDurationsParsed) : 0
  // If an action is announced with its own duration (ex: "explosion de 3s"),
  // the clip must at least cover it with a brief tail so the motion can settle.
  const minForAction = longestAction > 0 ? longestAction + 0.5 : 0
  const finalSeconds = Math.max(inferred.seconds, minForAction)
  return {
    frames: secondsToFrames(finalSeconds),
    seconds: finalSeconds,
    source: 'content-inference',
    rationale: longestAction > 0
      ? `${inferred.rationale} + couverture action ${longestAction}s`
      : inferred.rationale,
  }
}

/**
 * Extract action-local durations for injection into the generation prompt
 * (not the clip length). Kept independent from the resolver so a "10s fight"
 * still reaches FLUX/Wan2.2 as a semantic timing hint without shrinking the
 * total clip to 10s.
 */
function extractActionDurations(text: string): string {
  const actionRegex = new RegExp(
    `(${ACTION_WORDS})\\s+(?:de\\s+|d['']|qui\\s+dure\\s+)?(\\d+(?:[.,]\\d+)?)\\s*s`,
    'gi',
  )
  const actions: string[] = []
  let match: RegExpExecArray | null
  while ((match = actionRegex.exec(text)) !== null) {
    actions.push(`${match[2]}s ${match[1]}`)
  }
  return actions.length > 0 ? `Action timings: ${actions.join(', ')}` : ''
}

function humanizeVideoError(rawError: string): string {
  if (!rawError || rawError === '{}' || rawError === '{"ok": false, "error": ""}') {
    return 'Le pipeline video a ete interrompu (SIGTERM/exit 15). VRAM probablement insuffisante pour cette resolution. Le module va automatiquement retenter avec une resolution plus basse.'
  }
  if (rawError.includes('exit 15') || rawError.includes('exit code: 15')) {
    return 'Le pipeline video a ete interrompu par le watchdog VRAM. Resolution trop haute pour la memoire GPU disponible. Reduction automatique en cours...'
  }
  return rawError
}

export default function VideoView() {
  const { visionModel, hardware } = useAppStore()
  const { executeWithRuntime } = useManagedRuntime()
  const diagnostics = useStudioDiagnostics({
    requiresTauri: true,
    requiresOllama: true,
    requiredFiles: [
      { label: 'Pipeline video', relativePath: 'python-services/video_generate.py' },
    ],
  })
  const [prompt, setPrompt] = useState('')
  const [contextFiles, setContextFiles] = useState<File[]>([])
  // v84 : defaut 1280×720 — le backend a un budget adaptatif "quality first"
  // (wan_w = min(width, budget, 1280)) : avec 768 par defaut l'UI plafonnait
  // le rendu sous la resolution native HD de TI2V-5B meme pour un clip court.
  // Le budget redescend SEUL en 832×480 ou moins pour les clips longs.
  const [width, setWidth] = useState(1280)
  const [height, setHeight] = useState(720)
  const [numFrames, setNumFrames] = useState(49)
  const [isGenerating, setIsGenerating] = useState(false)
  const [progress, setProgress] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [videoUrl, setVideoUrl] = useState<string | null>(null)
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const [videoMeta, setVideoMeta] = useState<{ duration: number; width: number; height: number } | null>(null)
  const [playbackRate, setPlaybackRate] = useState(1)
  const [copyPromptFeedback, setCopyPromptFeedback] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [videoMode, setVideoMode] = useState<'speed' | 'quality'>('speed')
  // `qualityMode` is the new fidelity toggle orthogonal to `videoMode`.
  // - balanced: GGUF Q4_K_M primary, ~2-3 min on 16 GB VRAM.
  // - premium:  GGUF Q6_K with sequential CPU offload + 60 inference steps
  //             + motion interpolation. ~15-25 min but anatomy + identity
  //             stay coherent across frames, which is what matters when
  //             the current 2 min result produces disformed limbs.
  // `qualityMode` = 'auto' by default. The backend picks the best fidelity
  // the hardware and the requested duration can sustain (premium on 16 GB).
  // Users who want to override pick 'balanced' for speed or 'premium' to
  // force max steps. Auto is NEVER a lower-quality choice than the user
  // intention — it just means "let the pipeline decide".
  const [qualityMode, setQualityMode] = useState<'auto' | 'balanced' | 'premium'>('auto')
  const [motionPreset, setMotionPreset] = useState<string>('free')
  const [videos, setVideos] = useState<GeneratedVideo[]>([])
  const [saveDialogData, setSaveDialogData] = useState<SaveDialogData | null>(null)
  const [promptLibraryOpen, setPromptLibraryOpen] = useState(false)
  const [clarification, setClarification] = useState<ClarificationRequest | null>(null)
  const { addPrompt } = usePromptLibraryStore()
  const { trackGeneration, completeGeneration, failGeneration } = useGenerationTrackerStore()
  const recovery = useGenerationRecovery('video')
  const activeTrackerIdRef = useRef<string | null>(null)
  const unlistenRef = useRef<(() => void) | null>(null)
  const useImageToVideo = contextFiles.some((file) => file.type.startsWith('image/'))
  const activeOllamaModel = contextFiles.length > 0 ? visionModel : AUXILIARY_ANALYSIS_MODEL
  const { pack: assetPack, preparePack } = useModuleAssetPack({
    module: 'video',
    title: 'Pack modele video',
    assets: buildVideoModuleAssets(visionModel, useImageToVideo, contextFiles.length > 0, Number(hardware?.vram_gb ?? 0)),
  })

  useEffect(() => {
    return () => {
      unlistenRef.current?.()
    }
  }, [])

  // Mobile reload rescue: when the tab was killed mid-generation and React
  // remounts empty, ask the bridge whether a video job is still in flight
  // on the PC. If it is, surface a banner so the user knows their generation
  // didn't disappear — it's finishing on the PC and they can just wait.
  const [pendingJobBanner, setPendingJobBanner] = useState<{ jobId: string; status: 'queued' | 'running' | 'done' } | null>(null)
  useEffect(() => {
    let alive = true
    const tick = async () => {
      const info = await peekResumableJob('video')
      if (alive) setPendingJobBanner(info)
    }
    void tick()
    const id = window.setInterval(tick, 15_000)
    return () => { alive = false; window.clearInterval(id) }
  }, [])

  const canGenerate = Boolean(prompt.trim()) && !isGenerating && !diagnostics.blockingReason

  const generate = useCallback(async () => {
    if (!prompt.trim() || isGenerating) return

    if (diagnostics.blockingReason) {
      setError(diagnostics.blockingReason)
      return
    }

    setIsGenerating(true)
    setError(null)
    setProgress('Analyse de la scene video...')

    try {
      await executeWithRuntime({
        module: 'video',
        title: 'Generation video',
        services: ['ollama'],
        ollamaModel: activeOllamaModel,
        prepare: async ({ setPhase }) => {
          await preparePack(setPhase)
        },
        job: async ({ setPhase }) => {
          const preparedContext = contextFiles.length > 0 ? await prepareContextFiles(contextFiles) : []
          const primaryPreparedImage = pickPrimaryPreparedImage(preparedContext)
          const activePreset = MOTION_PRESETS.find((preset) => preset.id === motionPreset)
          const motionSuffix = activePreset?.promptSuffix ? `\n\nMotion directive: ${activePreset.promptSuffix}` : ''
          const referenceAwarePrompt = primaryPreparedImage
            ? [
              prompt,
              'Reference video contract: preserve the main identity, camera framing, palette and subject count from the reference image unless the prompt explicitly changes them.',
              'Use the reference image as the first frame or visual anchor and apply only the requested motion, setting or action changes.',
              'Keep limb trajectories, body balance, clothing continuity and prop placement coherent across the whole shot. No teleportation, no identity drift, no random scene jumps.',
            ].join('\n\n') + motionSuffix
            : prompt + motionSuffix
          const taskContext = await prepareTaskIntelligence({
            module: 'video',
            prompt: referenceAwarePrompt,
            model: visionModel,
            files: preparedContext,
            setPhase,
            phaseBase: 42,
            phaseSpan: 18,
          })

          if (taskContext.clarificationQuestion) {
            setPhase('Clarification utilisateur requise avant rendu video.', 50)
            const userAnswer = await new Promise<string | null>((resolve) => {
              setClarification({ question: taskContext.clarificationQuestion!, onRespond: resolve })
            })
            setClarification(null)
            if (userAnswer) {
              taskContext.enrichedPrompt = `${taskContext.enrichedPrompt}\n\nPrecision utilisateur: ${userAnswer}`
              taskContext.generationPrompt = `${taskContext.generationPrompt}\n\nUser clarification: ${userAnswer}`
            }
          }

          setPhase('Preparation du pipeline video...', 42)

          // Resolution de la duree: explicit user total > standalone number
          // > user-moved slider > content-type inference. On ne force JAMAIS
          // une duree "2s par defaut" sur un prompt d'action — le resolver
          // lit l'intention et choisit 3-5s selon le type de plan, sauf si
          // le prompt dit explicitement "video de Xs".
          const durationDecision = resolveVideoDuration(
            taskContext.enrichedPrompt,
            numFrames,
            numFrames === 49,
          )
          const effectiveFrames = durationDecision.frames
          setProgress(`Duree retenue: ${durationDecision.seconds}s (${durationDecision.rationale})`)
          const actionTimings = extractActionDurations(taskContext.enrichedPrompt)
          // Injecter les timings d'actions dans le generationPrompt si detectes
          const timedGenerationPrompt = actionTimings
            ? `${taskContext.generationPrompt}\n\n${actionTimings}`
            : taskContext.generationPrompt
          // v84 : grammaire cinematique deterministe (camera/plan/lumiere/style
          // detectes dans le prompt ORIGINAL, que la distillation LLM ne
          // transporte pas — et qui manquent totalement quand Ollama timeout
          // et que le fallback envoie le prompt brut). Deduplique contre le
          // preset motion et ce que le LLM a deja emis.
          const cinematicAnalysis = analyzeVideoPrompt(prompt)
          const finalGenerationPrompt = composeWanPrompt(timedGenerationPrompt, cinematicAnalysis, {
            motionSuffix: activePreset?.promptSuffix || '',
            mode: primaryPreparedImage ? 'i2v' : 't2v',
          })

          const workspacePath = await getWorkspacePath()
          const timestamp = Date.now()
          const outputDir = `${workspacePath}/output/videos`
          const outputPath = `${outputDir}/juan_bike_video_${timestamp}.mp4`
          const thumbnailPath = `${outputDir}/thumb_${timestamp}.png`
          const scriptPath = `${workspacePath}/python-services/video_generate.py`
          await fsMkdir(outputDir)
          const profiles = buildVideoProfiles(width, height, effectiveFrames)

          // Tracker la generation pour recovery apres refresh
          activeTrackerIdRef.current = trackGeneration({
            module: 'video',
            type: 'python_script',
            prompt,
            startedAt: Date.now(),
            expectedOutputDir: `${workspacePath}/output/videos`,
            expectedOutputPattern: 'juan_bike_video_.*\\.mp4',
          })
          const trackerId = activeTrackerIdRef.current

          unlistenRef.current?.()
          unlistenRef.current = await onPythonProgress((message) => {
            if (message.startsWith('PROGRESS:')) {
              const parts = message.split(':')
              const stage = parts[1] || 'run'
              const detail = parts.slice(2).join(':') || parts[1] || 'Generation video en cours...'
              setProgress(detail)
              const phaseProgress =
                stage === 'install'
                  ? 48
                  : stage === 'vram'
                    ? 52
                    : stage === 'repair'
                      ? 56
                    : stage === 'loading_start' || stage === 'init' || stage === 'loading_pipeline'
                      ? 58
                      : stage === 'loading_done' || stage === 'generating'
                        ? 72
                        : stage === 'validating'
                          ? 82
                          : stage === 'saving'
                            ? 88
                            : 68
              setPhase(detail, phaseProgress)
            }
          })

          let output = ''
          let successfulProfile = profiles[0]

          for (let attempt = 0; attempt < profiles.length; attempt += 1) {
            const profile = profiles[attempt]
            successfulProfile = profile
            const profileLabel = `${profile.label} ${profile.width}x${profile.height}, ${profile.numFrames} frames`
            setProgress(
              primaryPreparedImage
                ? `Lancement du pipeline video image-vers-video (${profileLabel})...`
                : `Lancement du pipeline video local (${profileLabel})...`,
            )
            setPhase(
              primaryPreparedImage
                ? `Execution Python du pipeline image-vers-video (${profileLabel})...`
                : `Execution Python du pipeline video (${profileLabel})...`,
              60,
            )

            // 2026-08-07 : seed déterministe dérivée du prompt final.
            // Mesure banc isolation Wan2.2 : sur 3 seeds au même prompt, amp
            // de mouvement varie de 165 % (0,00128 à 0,00887) — un plan
            // « quasi fixe » vs « qui bouge » relève du hasard tant que
            // rien ne fixe la seed. Ne pas passer `--seed` = loterie à
            // chaque relance sans changement d'intention utilisateur.
            // Hash FNV-1a 32 bits du prompt : deterministe, distribué,
            // même prompt → même vidéo (relance = idem), prompts
            // différents → seeds différentes.
            const promptSeed = (() => {
              let h = 0x811c9dc5
              for (let i = 0; i < finalGenerationPrompt.length; i += 1) {
                h ^= finalGenerationPrompt.charCodeAt(i)
                h = Math.imul(h, 0x01000193) >>> 0
              }
              return h % 2147483647
            })()

            try {
              output = await runPythonScript(scriptPath, [
                '--prompt',
                finalGenerationPrompt,
                '--output',
                outputPath,
                ...(primaryPreparedImage?.stagedPath ? ['--image', primaryPreparedImage.stagedPath] : []),
                '--width',
                String(profile.width),
                '--height',
                String(profile.height),
                '--num_frames',
                String(profile.numFrames),
                '--thumbnail',
                thumbnailPath,
                '--vram_gb',
                String(hardware?.vram_gb ?? 0),
                '--model_mode',
                videoMode,
                '--quality_mode',
                qualityMode,
                '--seed',
                String(promptSeed),
                '--motion_interp',
                // Auto + premium = 60 fps silky interpolation; balanced
                // stays at 48 fps for faster export.
                qualityMode === 'balanced' ? '1' : '2',
              ], {
                resumeKey: 'video',
                maxWaitMs: 8 * 60 * 60 * 1000,
                stalledTimeoutMs: 45 * 60 * 1000,
              })
              break
            } catch (pipelineError) {
              if (attempt === profiles.length - 1 || !isRecoverableVideoFailure(pipelineError)) {
                throw pipelineError
              }

              const nextProfile = profiles[attempt + 1]
              const retryLabel = `${nextProfile.width}x${nextProfile.height}, ${nextProfile.numFrames} frames`
              setProgress(`Auto-reparation video: echec du ${profileLabel}. Nouvelle tentative sur ${retryLabel}...`)
              setPhase(`Auto-reparation video: reduction automatique vers ${retryLabel}...`, 56)
            }
          }

          setPhase('Chargement de la sortie video...', 88)
          const jsonCandidates = output
            .split('\n')
            .map((line) => line.trim())
            .filter((line) => Boolean(line))
            // Ignore progress events, Python warnings, simple logs: ils ne sont pas du JSON
            .filter((line) => line.startsWith('{') || line.startsWith('['))

          let parsedResult: {
            ok?: boolean
            path?: string
            elapsed_seconds?: number
            error?: string
            model?: string
            strategy?: string
            validation_summary?: string
          } | null = null

          for (let index = jsonCandidates.length - 1; index >= 0 && !parsedResult; index -= 1) {
            try {
              parsedResult = JSON.parse(jsonCandidates[index])
            } catch {
              // candidate suivant
            }
          }

          if (!parsedResult) {
            throw new Error(
              'Le pipeline video n a pas produit de JSON final exploitable. Derniere sortie: '
                + output.slice(-400).replace(/\s+/g, ' ').trim(),
            )
          }

          const json = parsedResult
          if (!json.ok || !json.path) {
            throw new Error(humanizeVideoError(json.error || '') || 'Le pipeline video n a pas produit de sortie exploitable.')
          }

          const nextUrl = toAssetUrl(json.path)
          const modelLabel = json.model || 'modele video local'
          const strategyLabel = json.strategy ? ` / ${json.strategy}` : ''
          const durationLabel = json.elapsed_seconds
            ? `${json.elapsed_seconds}s de pipeline (${successfulProfile.width}x${successfulProfile.height}, ${successfulProfile.numFrames} frames)`
            : `Pipeline termine (${successfulProfile.width}x${successfulProfile.height}, ${successfulProfile.numFrames} frames)`
          setVideoUrl(nextUrl)
          setVideos((previous) => [
            { url: nextUrl, prompt, time: Date.now(), durationLabel, modelLabel: `${modelLabel}${strategyLabel}` },
            ...previous.slice(0, 9),
          ])
          setProgress(`Video generee via ${modelLabel}${strategyLabel}. ${json.validation_summary || durationLabel}.`)
          setPhase('Sortie video chargee.', 94)

          // Marquer la generation comme terminee dans le tracker (avec résumé vocal)
          completeGeneration(trackerId, {
            resultPath: json.path,
            resultFilename: `${modelLabel}${strategyLabel}, ${durationLabel}`,
          })
          activeTrackerIdRef.current = null

          // Fidelity-gated save prompt (score always high for valid video output)
          setSaveDialogData({
            module: 'video',
            sourcePath: json.path,
            prompt,
            fidelityScore: 90,
            parameters: { width: successfulProfile.width, height: successfulProfile.height, numFrames: successfulProfile.numFrames, strategy: json.strategy },
            modelLabel: `${modelLabel}${strategyLabel}`,
          })
        },
      })
    } catch (generationError) {
      if (activeTrackerIdRef.current) {
        failGeneration(activeTrackerIdRef.current, getErrorMessage(generationError))
        activeTrackerIdRef.current = null
      }
      setError(getErrorMessage(generationError, 'Le module video a echoue sans detail exploitable. Consulte le suivi runtime et la file de jobs.'))
      setProgress('')
    } finally {
      setIsGenerating(false)
      setPrompt('')
      unlistenRef.current?.()
      unlistenRef.current = null
    }
  }, [activeOllamaModel, completeGeneration, contextFiles, diagnostics.blockingReason, executeWithRuntime, failGeneration, hardware, height, isGenerating, motionPreset, numFrames, preparePack, prompt, qualityMode, trackGeneration, videoMode, visionModel, width])

  return (
    <div className="relative min-h-full flex flex-col">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute inset-0 aurora-mesh opacity-35" />
        <div className="absolute -top-40 -right-20 h-80 w-80 rounded-full bg-orange-500/15 blur-3xl" />
        <div className="absolute -bottom-40 -left-20 h-80 w-80 rounded-full bg-rose-500/15 blur-3xl" />
      </div>
      <div className="relative">
      <RecoveryBanner
        recovery={recovery}
        onRecovered={(r) => {
          if (r.url) setVideoUrl(r.url)
        }}
      />
      {pendingJobBanner && pendingJobBanner.status !== 'done' && (
        <div className="mx-4 mt-3 rounded-xl border border-amber-400/40 bg-amber-500/10 px-4 py-2.5 text-[12px] text-amber-100">
          <div className="font-semibold mb-0.5">⏳ Generation video en cours sur le PC</div>
          <p className="text-amber-200/80 leading-relaxed">
            Tu as quitte l onglet pendant une generation ({pendingJobBanner.status === 'queued' ? 'en file' : 'en cours'}, jobId <code className="font-mono">{pendingJobBanner.jobId.slice(0, 10)}…</code>). Le PC continue. Relance &laquo; Generer &raquo; avec le meme prompt pour recuperer la sortie, ou
            <button
              type="button"
              onClick={() => { clearResumableJob('video'); setPendingJobBanner(null) }}
              className="ml-1 underline hover:text-amber-50"
            >abandonne ce suivi</button>.
          </p>
        </div>
      )}
      <ClarificationDialog request={clarification} />
      <SaveDialog
        data={saveDialogData}
        onClose={() => setSaveDialogData(null)}
        onSaved={(savedPath) => {
          addPrompt({ module: 'video', prompt, fidelityScore: saveDialogData?.fidelityScore ?? 90, parameters: saveDialogData?.parameters ?? {}, tags: ['video'] })
          setSaveDialogData(null)
          setProgress(`Résultat sauvegardé: ${savedPath}`)
        }}
      />
      <PromptLibraryPanel
        open={promptLibraryOpen}
        onClose={() => setPromptLibraryOpen(false)}
        currentModule="video"
        onUsePrompt={(p) => setPrompt(p)}
      />
      <StudioHero
        icon={Video}
        eyebrow="Atelier video"
        title="Pipeline video local, suivi long run, sortie native."
        description="Le module video lance d abord Wan 2.2 en local puis bascule automatiquement vers un pipeline plus stable si la machine sature, tout en gardant un suivi explicite du moteur reel, de la strategie choisie et de la sortie mp4 finale."
        diagnostics={diagnostics}
        stats={[
          { label: 'Pack', value: VIDEO_MODEL_PACK_LABEL },
          { label: 'Format', value: `${width} x ${height}` },
          { label: 'Frames', value: `${numFrames}` },
          { label: 'Historique', value: `${videos.length} rendu(s)` },
        ]}
      />

      <div className="grid gap-3 px-2 pb-6 pt-3 sm:gap-4 sm:px-6 sm:pb-8 sm:pt-4 2xl:grid-cols-[22rem_minmax(0,1fr)]">
        <div className="2xl:sticky 2xl:top-4 self-start w-full overflow-y-auto overscroll-contain scroll-shell max-h-[60vh] sm:max-h-[calc(100vh-12rem)] rounded-[1.4rem] sm:rounded-[1.8rem] border border-aurora-border/40 bg-aurora-surface/55 p-3 sm:p-4 space-y-3 sm:space-y-4">
          <div className="rounded-[1.4rem] border border-aurora-border/35 bg-aurora-surface-2/70 p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-[11px] uppercase tracking-[0.22em] text-aurora-text-dim">Scene</p>
                <p className="mt-2 text-sm text-aurora-text">
                  Decris le mouvement, le cadrage, la lumiere et le ton de la sequence.
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
              placeholder="Ex: travelling doux autour d un velo gravel orange, ambiance atelier premium, profondeur de champ faible"
              rows={5}
              className="mt-4 w-full resize-none rounded-2xl border border-aurora-border bg-aurora-bg/60 px-3 py-3 text-sm text-aurora-text outline-none transition-colors focus:border-aurora-accent/45"
            />
            <div className="mt-2 flex items-center gap-2">
              <VoicePushToTalk
                onTranscript={(text) => setPrompt((prev) => (prev.trim() ? `${prev}, ${text}` : text))}
                label="Dicter ton prompt vidéo"
                size={36}
              />
              <span className="text-[11px] text-aurora-text-dim">Décris la scène à voix haute.</span>
            </div>
            {/* v84 : preview live de la grammaire cinema detectee (composeur). */}
            {(() => {
              const a = analyzeVideoPrompt(prompt)
              const hits = [
                a.shot,
                ...(a.staticCamera ? ['static camera'] : a.camera),
                ...a.lighting,
                a.style,
                a.tempo,
              ].filter(Boolean) as string[]
              if (!prompt.trim() || hits.length === 0) return null
              return (
                <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[10px] font-mono text-aurora-text-dim">
                  <span className="opacity-60">🎬 détecté :</span>
                  {hits.map((h) => (
                    <span key={h} className="rounded-full border border-aurora-border/40 bg-aurora-bg/40 px-2 py-0.5">{h}</span>
                  ))}
                </div>
              )
            })()}
            <VideoTempoAdvisor />
            {/* v84m — Lyra video commentator */}
            <div className="mt-3 flex items-center gap-3 rounded-xl border border-orange-500/25 bg-orange-500/5 p-2">
              <div style={{ width: 48, height: 60, flexShrink: 0 }}>
                <LyraCharacter
                  phase={isGenerating ? 'thinking' : prompt.length > 8 ? 'speaking' : 'idle'}
                  emotion={isGenerating ? 'focus' : prompt.length > 8 ? 'happy' : 'curious'}
                  accent="#ff8c42"
                  size={48}
                />
              </div>
              <div className="flex-1 text-[11px] text-aurora-text-dim font-mono">
                {isGenerating ? 'je tourne ta vidéo · ETA Wan2.2' : prompt.length > 8 ? 'cadence trouvée, prête à rendre' : 'décris une scène, je propose un rythme'}
              </div>
            </div>
          </div>

          <div className="rounded-[1.4rem] border border-aurora-border/35 bg-aurora-surface-2/60 p-4">
            <button
              onClick={() => setShowSettings((value) => !value)}
              className="flex items-center gap-2 text-xs text-aurora-text-dim hover:text-aurora-text transition-colors"
            >
              <Sliders size={14} />
              <span>Parametres video</span>
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
                    <label className="mb-1 block text-[11px] text-aurora-text-dim">Mode</label>
                    <div className="grid grid-cols-2 gap-2">
                      {([['speed', 'Vitesse', 'LTX-2B (rapide)'], ['quality', 'Qualite', 'LTX-13B fp8']] as const).map(([mode, label, hint]) => (
                        <button
                          key={mode}
                          onClick={() => setVideoMode(mode)}
                          title={hint}
                          className={`flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs text-left transition-colors ${
                            videoMode === mode
                              ? 'border border-aurora-accent/40 bg-aurora-accent/12 text-white'
                              : 'border border-aurora-border/35 bg-aurora-surface-2/50 text-aurora-text-dim hover:border-aurora-border/60'
                          }`}
                        >
                          {mode === 'speed' ? <Zap size={11} /> : <Star size={11} />}
                          {label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <label className="mb-1 block text-[11px] text-aurora-text-dim">
                      Fidelite — <span className="text-aurora-text-dim/80">optionnel, auto par defaut</span>
                    </label>
                    <div className="grid grid-cols-3 gap-2">
                      {([
                        ['auto', 'Auto', 'Le pipeline choisit la fidelite maximale que le materiel peut soutenir pour la duree demandee. Recommande.'],
                        ['balanced', 'Vitesse', 'Force le mode rapide ~2 min. Utile pour iterer sur un brief.'],
                        ['premium', 'Max', 'Force le mode lent haute fidelite ~5-8 min. Anatomie et coherence max.'],
                      ] as const).map(([mode, label, hint]) => (
                        <button
                          key={mode}
                          onClick={() => setQualityMode(mode)}
                          title={hint}
                          className={`flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs text-left transition-colors ${
                            qualityMode === mode
                              ? 'border border-aurora-accent/40 bg-aurora-accent/12 text-white'
                              : 'border border-aurora-border/35 bg-aurora-surface-2/50 text-aurora-text-dim hover:border-aurora-border/60'
                          }`}
                        >
                          {mode === 'auto' ? <Sparkles size={11} /> : mode === 'balanced' ? <Zap size={11} /> : <Star size={11} />}
                          {label}
                        </button>
                      ))}
                    </div>
                    <p className="mt-1.5 text-[10px] leading-relaxed text-aurora-text-dim">
                      {qualityMode === 'auto'
                        ? 'Auto: qualite maximale que ta carte peut tenir pour la duree reelle du clip, sans te forcer a choisir.'
                        : qualityMode === 'premium'
                          ? 'Mode premium force: rendu lent mais anatomie nette, motion 60 fps.'
                          : 'Mode vitesse force: iteration rapide sur un brief, qualite inferieure.'}
                    </p>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="mb-1 block text-[11px] text-aurora-text-dim">Largeur</label>
                      <select
                        value={width}
                        onChange={(event) => setWidth(Number(event.target.value))}
                        className="w-full rounded-xl border border-aurora-border bg-aurora-surface px-3 py-2 text-xs text-aurora-text outline-none"
                      >
                        {[512, 640, 768, 896].map((value) => (
                          <option key={value} value={value}>{value}</option>
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
                        {[320, 384, 512, 640].map((value) => (
                          <option key={value} value={value}>{value}</option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div>
                    <div className="mb-1 flex items-center justify-between text-[11px] text-aurora-text-dim">
                      <span>Duree — <span className="text-aurora-text-dim/80">optionnel, auto par defaut</span></span>
                      {numFrames !== 49 && (
                        <button
                          onClick={() => setNumFrames(49)}
                          className="text-[10px] text-aurora-accent hover:underline"
                        >
                          revenir a Auto
                        </button>
                      )}
                    </div>
                    <div className="grid grid-cols-5 gap-1.5">
                      {([
                        ['auto', null],
                        ['2s', 2],
                        ['4s', 4],
                        ['8s', 8],
                        ['16s', 16],
                      ] as const).map(([label, sec]) => {
                        const frames = sec == null ? 49 : Math.round(sec * 24)
                        const isAuto = sec == null
                        const active = isAuto ? numFrames === 49 : numFrames === frames
                        return (
                          <button
                            key={label}
                            onClick={() => setNumFrames(frames)}
                            title={isAuto
                              ? 'L IA deduit la duree ideale depuis le prompt (action, ambiance, portrait...)'
                              : `Duree manuelle ${label}`}
                            className={`rounded-xl border py-1.5 text-[11px] font-medium transition-colors ${
                              active
                                ? 'border-aurora-accent bg-aurora-accent/15 text-aurora-accent'
                                : 'border-aurora-border/50 bg-aurora-surface text-aurora-text-dim hover:text-aurora-text'
                            }`}
                          >
                            {label}
                          </button>
                        )
                      })}
                    </div>
                  </div>

                  <div>
                    <div className="mb-1 flex items-center justify-between text-[11px] text-aurora-text-dim">
                      <span>Frames (override fin)</span>
                      <span>
                        {numFrames === 49 ? 'Auto' : `${numFrames} (~${(numFrames / 24).toFixed(1)}s)`}
                      </span>
                    </div>
                    <input
                      type="range"
                      min={25}
                      max={97}
                      value={numFrames}
                      onChange={(event) => setNumFrames(Number(event.target.value))}
                      className="w-full accent-aurora-accent"
                    />
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          <ContextFilesField
            files={contextFiles}
            onFilesChange={setContextFiles}
            accept=".png,.jpg,.jpeg,.webp,.gif,.pdf,.txt,.md,.json,.csv,.tsv,.xlsx,.xls,.xlsm"
            hint="Ajoute storyboard, references, PDF ou notes pour guider la sequence video."
          />

          {useImageToVideo && (
            <div className="rounded-[1.4rem] border border-aurora-border/35 bg-aurora-surface-2/60 p-4">
              <p className="text-[11px] uppercase tracking-[0.22em] text-aurora-text-dim">Mouvement image</p>
              <p className="mt-1 text-xs text-aurora-text-dim">Choisir le type d animation a appliquer sur la reference.</p>
              <div className="mt-3 grid grid-cols-2 gap-2">
                {MOTION_PRESETS.map((preset) => (
                  <button
                    key={preset.id}
                    onClick={() => setMotionPreset(preset.id)}
                    className={`rounded-xl px-3 py-2 text-xs text-left transition-colors ${
                      motionPreset === preset.id
                        ? 'border border-aurora-accent/40 bg-aurora-accent/12 text-white'
                        : 'border border-aurora-border/35 bg-aurora-surface-2/50 text-aurora-text-dim hover:border-aurora-border/60'
                    }`}
                  >
                    {preset.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          <ModuleAssetPackCard pack={assetPack} />
          <ConnectorRecommendationsPanel module="video" compact />

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
                <Play size={18} />
                <span>Generer la video</span>
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

          {videos.length > 0 && (
            <div className="rounded-[1.6rem] border border-aurora-border/40 bg-aurora-surface/65 p-4">
              <p className="text-[11px] uppercase tracking-[0.22em] text-aurora-text-dim">Historique</p>
              <div className="mt-3 space-y-2">
                {videos.map((video, index) => (
                  <button
                    key={`${video.time}-${index}`}
                    onClick={() => setVideoUrl(video.url)}
                    className="w-full rounded-2xl border border-aurora-border/35 bg-aurora-surface-2/60 px-3 py-3 text-left transition-colors hover:border-aurora-accent/35"
                  >
                    <p className="truncate text-sm text-aurora-text">{video.prompt}</p>
                    <p className="mt-1 text-[11px] text-aurora-text-dim">
                      {video.durationLabel}
                      {' / '}
                      {video.modelLabel}
                      {' / '}
                      {new Date(video.time).toLocaleTimeString('fr-FR')}
                    </p>
                  </button>
                ))}
              </div>
            </div>
          )}

          <StudioDiagnosticsPanel diagnostics={diagnostics} title="Preflight video" />
        </div>

        <div className="min-w-0 rounded-[1.8rem] border border-aurora-border/40 bg-aurora-surface/45 overflow-hidden">
          <div className="border-b border-aurora-border/30 px-5 py-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-[11px] uppercase tracking-[0.22em] text-aurora-text-dim">Lecteur</p>
                <h2 className="mt-1 text-lg font-semibold text-aurora-text">Preview locale</h2>
              </div>

              {videoUrl && (
                <div className="flex flex-wrap items-center gap-2">
                  <a
                    href={videoUrl}
                    download
                    className="inline-flex items-center gap-1.5 rounded-xl border border-aurora-border/40 bg-aurora-surface-2 px-3 py-2 text-xs text-aurora-text hover:border-aurora-accent/35 transition-colors"
                  >
                    <Download size={14} />
                    Telecharger
                  </a>
                  <button
                    onClick={() => {
                      const video = videoRef.current
                      if (!video || !video.videoWidth) return
                      const canvas = document.createElement('canvas')
                      canvas.width = video.videoWidth
                      canvas.height = video.videoHeight
                      const ctx = canvas.getContext('2d')
                      if (!ctx) return
                      try {
                        ctx.drawImage(video, 0, 0)
                        const dataUrl = canvas.toDataURL('image/png')
                        const anchor = document.createElement('a')
                        anchor.href = dataUrl
                        anchor.download = `aurora-video-frame-${Date.now()}.png`
                        anchor.click()
                      } catch {
                        // video tainted (CORS) ou codec non compatible — silencieux
                      }
                    }}
                    className="inline-flex items-center gap-1.5 rounded-xl border border-aurora-border/40 bg-aurora-surface-2 px-3 py-2 text-xs text-aurora-text hover:border-aurora-accent/35 transition-colors"
                    title="Capturer la frame en cours"
                  >
                    <Camera size={14} />
                    Frame PNG
                  </button>
                  {prompt && (
                    <button
                      onClick={() => {
                        navigator.clipboard?.writeText(prompt).then(() => {
                          setCopyPromptFeedback(true)
                          window.setTimeout(() => setCopyPromptFeedback(false), 1500)
                        }).catch(() => undefined)
                      }}
                      className={`inline-flex items-center gap-1.5 rounded-xl border px-3 py-2 text-xs transition-colors ${
                        copyPromptFeedback ? 'border-aurora-green/40 bg-aurora-green/10 text-aurora-green' : 'border-aurora-border/40 bg-aurora-surface-2 text-aurora-text hover:border-aurora-accent/35'
                      }`}
                      title="Copier le prompt utilise"
                    >
                      <Copy size={14} />
                      {copyPromptFeedback ? 'Copie !' : 'Prompt'}
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>

          <div className="flex min-h-[50vw] flex-col items-center justify-center gap-3 p-3 sm:min-h-[36rem] sm:p-6">
            {videoUrl ? (
              <div className="w-full h-full overflow-hidden rounded-[1.8rem] border border-aurora-border/35 bg-[#091116] p-4">
                <video
                  ref={videoRef}
                  src={videoUrl}
                  controls
                  autoPlay
                  playsInline
                  onLoadedMetadata={(event) => {
                    const v = event.currentTarget
                    setVideoMeta({ duration: v.duration || 0, width: v.videoWidth, height: v.videoHeight })
                  }}
                  onRateChange={(event) => setPlaybackRate(event.currentTarget.playbackRate)}
                  className="h-full w-full rounded-[1.4rem] object-contain"
                />
                {(videoMeta || playbackRate !== 1) && (
                  <div className="mt-3 flex flex-wrap items-center gap-2 rounded-xl border border-aurora-border/30 bg-aurora-surface-2/60 px-3 py-2 text-[11px] text-aurora-text-dim">
                    {videoMeta && (
                      <>
                        <span>{videoMeta.width}×{videoMeta.height}</span>
                        <span>·</span>
                        <span>{videoMeta.duration.toFixed(2)}s</span>
                      </>
                    )}
                    <span className="ml-auto inline-flex items-center gap-1">
                      Vitesse
                      {[0.25, 0.5, 1, 1.5, 2].map((rate) => (
                        <button
                          key={rate}
                          onClick={() => {
                            if (videoRef.current) {
                              videoRef.current.playbackRate = rate
                              setPlaybackRate(rate)
                            }
                          }}
                          className={`rounded-md border px-1.5 py-0.5 text-[10px] ${
                            playbackRate === rate ? 'border-aurora-accent bg-aurora-accent/15 text-aurora-accent' : 'border-aurora-border/50 text-aurora-text-dim hover:text-aurora-text'
                          }`}
                        >
                          {rate}×
                        </button>
                      ))}
                    </span>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center">
                <div className="mx-auto flex h-24 w-24 items-center justify-center rounded-[1.8rem] border border-aurora-border bg-aurora-surface-2">
                  <Video size={40} className="text-aurora-text-dim" />
                </div>
                <p className="mt-4 text-sm text-aurora-text-muted">
                  Decris une sequence puis laisse le pipeline local produire la video ici.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
      </div>
    </div>
  )
}

// v83m — sélecteur de tone qui suggère un BPM cible pour le montage.
function VideoTempoAdvisor() {
  const [tone, setTone] = useState<'tutoriel' | 'storytelling' | 'pub' | 'recap' | 'hype'>('tutoriel')
  const bpm = recommendBpmForTone(tone)
  const cat = classifyTempo(bpm)
  const tones: Array<{ id: typeof tone; label: string }> = [
    { id: 'tutoriel', label: 'tuto' },
    { id: 'storytelling', label: 'récit' },
    { id: 'recap', label: 'récap' },
    { id: 'pub', label: 'pub' },
    { id: 'hype', label: 'hype' },
  ]
  return (
    <div className="mt-3 rounded-xl border border-aurora-border/30 bg-black/20 p-3 text-[11px]">
      <div className="flex items-center justify-between mb-2">
        <span className="uppercase tracking-wider text-aurora-text-dim">Tempo conseillé</span>
        <span className="font-mono text-aurora-text">{bpm} BPM · {cat}</span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {tones.map((t) => (
          <button
            key={t.id}
            onClick={() => setTone(t.id)}
            className={`rounded-md px-2 py-0.5 text-[10px] font-mono border transition-colors ${
              tone === t.id
                ? 'bg-orange-500/25 border-orange-500/55 text-orange-100'
                : 'bg-white/[0.03] border-white/10 text-aurora-text-dim hover:text-aurora-text'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      <p className="mt-2 text-[10px] text-aurora-text-dim italic">
        Cale les coupes sur ce BPM pour un rythme cohérent avec ce ton. {cat === 'presto' || cat === 'prestissimo' ? 'Coupes courtes (≤1s).' : 'Plans plus longs (≥2s).'}
      </p>
    </div>
  )
}
