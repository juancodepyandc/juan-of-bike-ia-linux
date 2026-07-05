// === AVATAR ===
// - vrm / glb-morphs / glb-static: 3D via Three.js
// - image-2d: image statique simple (pas d animation)
// - procedural: tete 3D generee par code (low-cost)
// - live2d-flux: image FLUX 2D animee (blink, lip-sync, respiration) -- ressemblance fidele
// - talking-video: MP4 pre-genere par SadTalker (animation realiste tete+levres+yeux) -- meilleur realisme
export type AvatarType = 'vrm' | 'glb-morphs' | 'glb-static' | 'image-2d' | 'procedural' | 'live2d-flux' | 'talking-video'

/**
 * Mode d animation du personnage -- detecte automatiquement via character_research.py.
 * - humanoid: visage humain classique (yeux + bouche fermee au repos, ouvre pour parler)
 * - creature: gueule large a machoire (crocs visibles, ouverture verticale importante)
 * - robot: pas de bouche organique, ecran/LED/visor qui pulse selon l audio
 * - abstract: entite sans traits faciaux fixes, deformation/glow globale sur parole
 */
export type AvatarAnimationMode = 'humanoid' | 'creature' | 'robot' | 'abstract'

export interface AvatarEntry {
  id: string
  label: string
  type: AvatarType
  path: string
  thumbnail: string | null
  builtIn: boolean
  createdAt: number | null
  /** Pour type 'live2d-flux': JSON stringifie des coords yeux/bouche detectees par qwen3-vl */
  features?: string | null
  /** Mode d animation adapte au personnage (humanoid par defaut). Evite d animer une bouche humaine sur un robot. */
  animationMode?: AvatarAnimationMode
  /** Brief canonique du personnage (ex: "pink spiky hair, black eyes, tan skin, white scarf") pour re-generation */
  researchBrief?: string
  /** Description courte de COMMENT le personnage parle (ex: "wide jaw with fangs", "LED strip pulses") */
  howTheySpeak?: string
}

// === HARDWARE ===
export interface HardwareProfile {
  os: string
  cpu: string
  cores: number
  ram_gb: number
  gpu: string
  vram_gb: number
  vram_free_gb: number
}

export interface HostRuntimeResources {
  total_ram_gb: number
  free_ram_gb: number
  memory_pressure: 'low' | 'medium' | 'high' | 'critical'
}

export interface ServiceStatus {
  ollama: boolean
  comfyui: boolean
}

export type RuntimeServiceId = 'ollama' | 'comfyui'

export interface RuntimeServiceInfo {
  id: RuntimeServiceId
  label: string
  available: boolean
  running: boolean
  startedByApp: boolean
  progress: number
  detail: string
  path: string | null
  processId: number | null
}

export interface RuntimeProgressEvent {
  service: RuntimeServiceId
  status: 'checking' | 'starting' | 'warming' | 'ready' | 'releasing' | 'stopped' | 'error'
  progress: number
  detail: string
}

export interface HostPrivilegeStatus {
  platform: string
  isAdmin: boolean
  canElevate: boolean
  detail: string
}

export interface LinuxRuntimeCheckItem {
  id: string
  label: string
  required: boolean
  ready: boolean
  detail: string
  path: string | null
}

export interface LinuxRuntimeCheckReport {
  platform: string
  isLinux: boolean
  ready: boolean
  needsInstall: boolean
  workspacePath: string | null
  markerPath: string | null
  logPath: string | null
  installCommand: string | null
  detail: string
  items: LinuxRuntimeCheckItem[]
}

export interface RuntimeTaskState {
  active: boolean
  module: ModuleId | null
  title: string
  phase: 'idle' | 'prepare' | 'generate' | 'cleanup' | 'done' | 'error'
  detail: string
  progress: number
  startedAt: number | null
  finishedAt: number | null
  services: RuntimeServiceId[]
  error: string | null
  history: Array<{
    id: string
    phase: 'idle' | 'prepare' | 'generate' | 'cleanup' | 'done' | 'error'
    detail: string
    progress: number
    timestamp: number
  }>
}

export interface GenerationJobState {
  id: string
  module: ModuleId
  title: string
  detail: string
  progress: number
  phase: 'idle' | 'prepare' | 'generate' | 'cleanup' | 'done' | 'error'
  status: 'queued' | 'running' | 'done' | 'error' | 'cancelled'
  services: RuntimeServiceId[]
  model: string | null
  createdAt: number
  startedAt: number | null
  finishedAt: number | null
  error: string | null
  history: Array<{
    id: string
    phase: 'idle' | 'prepare' | 'generate' | 'cleanup' | 'done' | 'error'
    detail: string
    progress: number
    timestamp: number
  }>
}

export interface OllamaMessage {
  role: 'system' | 'user' | 'assistant'
  content: string
  images?: string[]
}

export interface OllamaModel {
  name: string
  size: number
  digest: string
  modified_at: string
}

export type ModuleId =
  | 'conversation'
  | 'image'
  | 'code'
  | 'video'
  | 'drawing'
  | '3d'
  | 'learning'
  | 'voice'
  | 'cyber'

export interface ModuleConfig {
  id: ModuleId
  label: string
  icon: string
  description: string
  color: string
}

export interface GenerationResult {
  ok: boolean
  path?: string
  error?: string
  elapsed_seconds?: number
  validation?: {
    ok: boolean
    reason: string | null
    summary: string
    metrics: Record<string, number>
    thumbnail_path?: string | null
  }
}

export type ModuleAssetKind = 'ollama_model' | 'hf_file' | 'hf_snapshot' | 'python_runtime'

export type ModuleAssetStatus = 'idle' | 'scanning' | 'downloading' | 'warming' | 'ready' | 'error'

export interface ModuleAssetDefinition {
  id: string
  label: string
  kind: ModuleAssetKind
  target: string
  detail: string
  repoId?: string
  filename?: string
  destination?: string | null
  allowPatterns?: string[]
  prepareMode?: string
}

export interface ModuleAssetState extends ModuleAssetDefinition {
  status: ModuleAssetStatus
  progress: number
  path: string | null
  lastCheckedAt: number | null
  error: string | null
}

export interface ModuleAssetPackState {
  module: ModuleId
  title: string
  detail: string
  status: 'idle' | 'running' | 'ready' | 'error'
  progress: number
  assets: ModuleAssetState[]
  lastCheckedAt: number | null
  lastError: string | null
}

export type PromptNature = 'real_world' | 'fictional' | 'technical' | 'educational' | 'creative_blend'

export interface RealityAnalysis {
  nature: PromptNature
  subject: string[]
  isVerifiable: boolean
  complexityScore: number
  requiresWebValidation: boolean
  consistencyRules: string[]
  fidelityTarget: 98
  webSearchTerms: string[]
}

export interface UserProgress {
  xp: number
  level: number
  streak: number
  badges: string[]
  completedTopics: string[]
}

export interface QuizQuestion {
  id: string
  question: string
  options: string[]
  correctIndex: number
  explanation: string
  difficulty: 'easy' | 'medium' | 'hard'
  topic: string
}

export interface UserProfile {
  name: string
  machineSignature: string
  knownMachineSignatures: string[]
  wizardCompleted: boolean
  hardware?: HardwareProfile
  preferredMainModel: string
  preferredCodeModel: string
  preferredVisionModel: string
  preferAdminMode?: boolean
  createdAt: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: number
  thinking?: string
  images?: string[]
  /** User can mark important messages to keep them visible when they prune. */
  pinned?: boolean
  /** Set when the user has edited the content after creation. */
  edited?: boolean
}

export type AssistantStage =
  | 'idle'
  | 'understand'
  | 'plan'
  | 'draft'
  | 'verify'
  | 'refine'
  | 'done'
  | 'blocked'
  | 'error'

export interface AssistantTurnAnalysis {
  objective: string
  userIntent: string
  constraints: string[]
  responsePlan: string[]
  responseChecklist: string[]
  missingInformation: string[]
  askBeforeAnswer: string | null
  answerStyle: string
  riskFlags: string[]
  realityMode: PromptNature
}

export interface AssistantTurnVerification {
  score: number
  confidence: number
  verdict: 'ready' | 'refine' | 'blocked'
  summary: string
  strengths: string[]
  corrections: string[]
  unsupportedClaims: string[]
  missingPoints: string[]
}

export interface AssistantTimelineItem {
  id: string
  stage: AssistantStage
  label: string
  detail: string
  status: 'running' | 'done' | 'error'
  timestamp: number
}

export interface AssistantRunState {
  stage: AssistantStage
  label: string
  detail: string
  progress: number
  startedAt: number | null
  finishedAt: number | null
  analysis: AssistantTurnAnalysis | null
  verification: AssistantTurnVerification | null
  timeline: AssistantTimelineItem[]
  lastError: string | null
}
