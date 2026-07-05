import type { CoworkAction, CoworkActionEvent, CoworkActionKind } from './coworkTypes.ts'

export type CoworkProjectArtifactKind =
  | 'image'
  | 'model3d'
  | 'game'
  | 'code'
  | 'video'
  | 'audio'
  | 'document'
  | 'data'
  | 'other'

export type CoworkProjectArtifactStatus = 'planned' | 'generating' | 'ready' | 'failed'
export type CoworkProjectStageStatus = 'running' | 'ok' | 'warn' | 'error'

export type CoworkProjectArtifact = {
  id: string
  kind: CoworkProjectArtifactKind
  label: string
  status: CoworkProjectArtifactStatus
  version: number
  createdAt: number
  updatedAt: number
  active?: boolean
  path?: string
  url?: string
  previewUrl?: string
  sourcePrompt?: string
  sourceAction?: string
  connector?: string
  action?: string
  summary?: string
  parentIds?: string[]
  supersedesId?: string
}

export type CoworkProjectStage = {
  id: string
  label: string
  status: CoworkProjectStageStatus
  startedAt: number
  endedAt?: number
  durationMs?: number
  detail?: string
  actionKind?: CoworkActionKind | string
  module?: string
}

export type CoworkProjectThread = {
  version: number
  updatedAt: number
  brief?: string
  activeArtifactId?: string
  artifacts: CoworkProjectArtifact[]
  stages: CoworkProjectStage[]
  notes: string[]
}

type ActionRecord = {
  action: CoworkAction
  startedAt: number
  endedAt?: number
  ok?: boolean
  output?: string
  error?: string
  message?: string
}

const THREAD_VERSION = 1
const STORAGE_KEY = 'cowork:project-thread-v1'
const MAX_ARTIFACTS = 28
const MAX_STAGES = 40
const MAX_NOTES = 18

export function createEmptyCoworkProjectThread(): CoworkProjectThread {
  return {
    version: THREAD_VERSION,
    updatedAt: Date.now(),
    artifacts: [],
    stages: [],
    notes: [],
  }
}

export function normalizeCoworkProjectThread(input: unknown): CoworkProjectThread {
  if (!input || typeof input !== 'object') return createEmptyCoworkProjectThread()
  const value = input as Partial<CoworkProjectThread>
  return {
    version: THREAD_VERSION,
    updatedAt: typeof value.updatedAt === 'number' ? value.updatedAt : Date.now(),
    brief: typeof value.brief === 'string' ? value.brief : undefined,
    activeArtifactId: typeof value.activeArtifactId === 'string' ? value.activeArtifactId : undefined,
    artifacts: Array.isArray(value.artifacts)
      ? value.artifacts.map(normalizeArtifact).filter(Boolean).slice(-MAX_ARTIFACTS) as CoworkProjectArtifact[]
      : [],
    stages: Array.isArray(value.stages)
      ? value.stages.map(normalizeStage).filter(Boolean).slice(-MAX_STAGES) as CoworkProjectStage[]
      : [],
    notes: Array.isArray(value.notes)
      ? value.notes.filter((note): note is string => typeof note === 'string').slice(-MAX_NOTES)
      : [],
  }
}

export function loadCoworkProjectThread(storageKey = STORAGE_KEY): CoworkProjectThread {
  try {
    if (typeof localStorage === 'undefined') return createEmptyCoworkProjectThread()
    const raw = localStorage.getItem(storageKey)
    if (!raw) return createEmptyCoworkProjectThread()
    return normalizeCoworkProjectThread(JSON.parse(raw))
  } catch {
    return createEmptyCoworkProjectThread()
  }
}

export function saveCoworkProjectThread(thread: CoworkProjectThread, storageKey = STORAGE_KEY): void {
  try {
    if (typeof localStorage === 'undefined') return
    localStorage.setItem(storageKey, JSON.stringify(sanitizeThreadForStorage(thread)))
  } catch {
    // localStorage quota or private mode: project memory remains in-memory.
  }
}

export function clearCoworkProjectThread(storageKey = STORAGE_KEY): CoworkProjectThread {
  try {
    if (typeof localStorage !== 'undefined') localStorage.removeItem(storageKey)
  } catch {
    // ignore
  }
  return createEmptyCoworkProjectThread()
}

export function updateCoworkProjectThreadFromEvents(
  previous: CoworkProjectThread | undefined,
  args: {
    userPrompt: string
    assistantReply?: string
    events: CoworkActionEvent[]
    attachedImageDescriptions?: string[]
  },
): CoworkProjectThread {
  const now = Date.now()
  const base = normalizeCoworkProjectThread(previous)
  const records = extractActionRecords(args.events)
  const prompt = clean(args.userPrompt)
  const notes = [...base.notes]
  if (prompt) {
    notes.push(`User: ${compact(prompt, 180)}`)
  }
  const assistantReply = clean(args.assistantReply || '')
  if (assistantReply) {
    notes.push(`Aurora: ${compact(assistantReply, 220)}`)
  }
  for (const desc of args.attachedImageDescriptions ?? []) {
    if (desc.trim()) notes.push(`Image jointe: ${compact(desc, 220)}`)
  }

  let artifacts = base.artifacts.map((artifact) => ({ ...artifact, parentIds: artifact.parentIds ? [...artifact.parentIds] : undefined }))
  const stages = [...base.stages, ...records.map(recordToStage)].slice(-MAX_STAGES)

  for (const record of records) {
    const artifact = inferArtifactFromRecord(record, artifacts, prompt, assistantReply)
    if (!artifact) continue
    const supersedesId = artifact.supersedesId
    if (supersedesId) {
      artifacts = artifacts.map((existing) =>
        existing.id === supersedesId ? { ...existing, active: false, updatedAt: now } : existing,
      )
    }
    artifacts = artifacts.map((existing) =>
      artifact.active && existing.id !== artifact.id
        ? { ...existing, active: false }
        : existing,
    )
    artifacts.push(artifact)
    notes.push(`${artifactLabel(artifact.kind)} ${artifact.label} -> ${artifact.status}${artifact.path ? ` (${artifact.path})` : ''}`)
  }

  artifacts = dedupeArtifacts(artifacts).slice(-MAX_ARTIFACTS)
  const activeArtifactId = pickActiveArtifactId(artifacts, base.activeArtifactId)
  if (activeArtifactId) {
    artifacts = artifacts.map((artifact) => ({ ...artifact, active: artifact.id === activeArtifactId }))
  }

  return {
    version: THREAD_VERSION,
    updatedAt: now,
    brief: inferBrief(prompt, base.brief),
    activeArtifactId,
    artifacts,
    stages,
    notes: uniqueTail(notes, MAX_NOTES),
  }
}

export function diffCoworkProjectArtifacts(
  before: CoworkProjectThread | undefined,
  after: CoworkProjectThread,
): CoworkProjectArtifact[] {
  const oldIds = new Set((before?.artifacts ?? []).map((artifact) => artifact.id))
  return after.artifacts.filter((artifact) => !oldIds.has(artifact.id))
}

export function buildCoworkProjectThreadSection(thread?: CoworkProjectThread): string {
  const state = normalizeCoworkProjectThread(thread)
  const readyArtifacts = state.artifacts.filter((artifact) => artifact.status === 'ready')
  const active = state.activeArtifactId
    ? state.artifacts.find((artifact) => artifact.id === state.activeArtifactId)
    : readyArtifacts[readyArtifacts.length - 1]

  const lines = [
    '## Fil projet Cowork',
    state.brief ? `Brief courant: ${state.brief}` : 'Brief courant: aucun projet persistant encore detecte.',
  ]

  if (active) {
    lines.push(`Artefact actif: ${formatArtifactForPrompt(active)}.`)
  } else {
    lines.push('Artefact actif: aucun. Si la demande commence une creation, cree le premier artefact et rends son chemin/apercu.')
  }

  if (readyArtifacts.length > 0) {
    lines.push('Artefacts utilisables (du plus ancien au plus recent):')
    for (const artifact of readyArtifacts.slice(-8)) {
      lines.push(`- ${formatArtifactForPrompt(artifact)}`)
    }
  }

  if (state.notes.length > 0) {
    lines.push('Historique projet resume:')
    for (const note of state.notes.slice(-6)) lines.push(`- ${note}`)
  }

  lines.push(
    '',
    'Regles de fil projet:',
    '- Les mots "celui-ci", "ca", "ce modele", "cette image", "la deuxieme", "la version modifiee" pointent vers l artefact actif ou vers la derniere version ready du bon type.',
    '- Quand l utilisateur demande une modification d une generation, produis une nouvelle version et considere cette nouvelle version comme reference active pour les etapes suivantes.',
    '- Image -> 3D: si une image active existe, transmets son chemin comme image_path/source_image quand le connecteur le supporte, et conserve le prompt/description comme contraintes de fidelite.',
    '- 3D/image -> jeu: ne te limite pas au personnage. Cree ou demande au module Code de creer le gameplay, les controles, les assets necessaires, les tests/build, et verifie le resultat.',
    '- Reference connue vs inconnue: si le user exige une ressemblance fidele a une personne/marque/personnage connu et qu aucune reference fiable n existe, cherche une reference ou pose une seule question ciblee. Si le user demande une creation originale, comble les blancs creativement.',
    '- Avant finish sur une chaine creative, il faut au minimum: artefact genere ou fichier cree, chemin/preview mentionne, dependances entre versions respectees, verification ou raison precise si la verification est impossible.',
  )

  return lines.join('\n')
}

export function previewUrlForCoworkArtifact(artifact: CoworkProjectArtifact): string {
  const value = artifact.previewUrl || artifact.url || artifact.path || ''
  if (!value) return ''
  if (/^(https?:|data:|blob:|file:|\/api\/|\/proxy\/)/i.test(value)) return value
  const normalized = value.replace(/\\/g, '/')
  if (/^[A-Za-z]:\//.test(normalized)) return encodeURI(`file:///${normalized}`)
  return encodeURI(normalized)
}

export function artifactLabel(kind: CoworkProjectArtifactKind): string {
  switch (kind) {
    case 'image': return 'Image'
    case 'model3d': return 'Modele 3D'
    case 'game': return 'Jeu'
    case 'code': return 'Code'
    case 'video': return 'Video'
    case 'audio': return 'Audio'
    case 'document': return 'Document'
    case 'data': return 'Donnees'
    default: return 'Artefact'
  }
}

function normalizeArtifact(input: unknown): CoworkProjectArtifact | null {
  if (!input || typeof input !== 'object') return null
  const a = input as Partial<CoworkProjectArtifact>
  if (typeof a.id !== 'string' || typeof a.kind !== 'string' || typeof a.label !== 'string') return null
  return {
    id: a.id,
    kind: normalizeArtifactKind(a.kind),
    label: a.label,
    status: normalizeArtifactStatus(a.status),
    version: typeof a.version === 'number' && Number.isFinite(a.version) ? a.version : 1,
    createdAt: typeof a.createdAt === 'number' ? a.createdAt : Date.now(),
    updatedAt: typeof a.updatedAt === 'number' ? a.updatedAt : Date.now(),
    active: Boolean(a.active),
    path: typeof a.path === 'string' ? a.path : undefined,
    url: typeof a.url === 'string' ? a.url : undefined,
    previewUrl: typeof a.previewUrl === 'string' ? trimHugeDataUrl(a.previewUrl) : undefined,
    sourcePrompt: typeof a.sourcePrompt === 'string' ? a.sourcePrompt : undefined,
    sourceAction: typeof a.sourceAction === 'string' ? a.sourceAction : undefined,
    connector: typeof a.connector === 'string' ? a.connector : undefined,
    action: typeof a.action === 'string' ? a.action : undefined,
    summary: typeof a.summary === 'string' ? a.summary : undefined,
    parentIds: Array.isArray(a.parentIds) ? a.parentIds.filter((id): id is string => typeof id === 'string') : undefined,
    supersedesId: typeof a.supersedesId === 'string' ? a.supersedesId : undefined,
  }
}

function normalizeStage(input: unknown): CoworkProjectStage | null {
  if (!input || typeof input !== 'object') return null
  const s = input as Partial<CoworkProjectStage>
  if (typeof s.id !== 'string' || typeof s.label !== 'string') return null
  return {
    id: s.id,
    label: s.label,
    status: normalizeStageStatus(s.status),
    startedAt: typeof s.startedAt === 'number' ? s.startedAt : Date.now(),
    endedAt: typeof s.endedAt === 'number' ? s.endedAt : undefined,
    durationMs: typeof s.durationMs === 'number' ? s.durationMs : undefined,
    detail: typeof s.detail === 'string' ? s.detail : undefined,
    actionKind: typeof s.actionKind === 'string' ? s.actionKind : undefined,
    module: typeof s.module === 'string' ? s.module : undefined,
  }
}

function extractActionRecords(events: CoworkActionEvent[]): ActionRecord[] {
  const records: ActionRecord[] = []
  for (const ev of events) {
    const parsed = parseEventAction(ev.detail)
    if (parsed) {
      records.push({
        action: parsed,
        startedAt: ev.at,
        message: ev.message,
      })
      continue
    }
    if (!ev.actionKind) continue
    const pending = findLastPendingRecord(records, ev.actionKind)
    if (!pending) continue
    if (ev.kind === 'success') {
      pending.ok = true
      pending.endedAt = ev.at
      pending.output = ev.detail || ev.message
    } else if (ev.kind === 'error') {
      pending.ok = false
      pending.endedAt = ev.at
      pending.error = ev.detail || ev.message
    }
  }
  return records
}

function findLastPendingRecord(records: ActionRecord[], kind: CoworkActionKind | string): ActionRecord | undefined {
  for (let i = records.length - 1; i >= 0; i -= 1) {
    const record = records[i]
    if (record.action.kind === kind && record.ok === undefined) return record
  }
  return undefined
}

function parseEventAction(detail?: string): CoworkAction | null {
  if (!detail || !detail.trim().startsWith('{')) return null
  try {
    const parsed = JSON.parse(detail) as unknown
    if (!parsed || typeof parsed !== 'object') return null
    const kind = (parsed as { kind?: unknown }).kind
    return typeof kind === 'string' ? parsed as CoworkAction : null
  } catch {
    return null
  }
}

function recordToStage(record: ActionRecord): CoworkProjectStage {
  const endedAt = record.endedAt
  return {
    id: stableId('stage', `${record.startedAt}-${record.action.kind}-${record.message || ''}`),
    label: stageLabel(record.action),
    status: record.ok === false ? 'error' : record.ok === true ? 'ok' : 'running',
    startedAt: record.startedAt,
    endedAt,
    durationMs: endedAt ? Math.max(0, endedAt - record.startedAt) : undefined,
    detail: compact(record.output || record.error || record.message || '', 180),
    actionKind: record.action.kind,
    module: record.action.kind === 'connector' ? record.action.connector : undefined,
  }
}

function inferArtifactFromRecord(
  record: ActionRecord,
  artifacts: CoworkProjectArtifact[],
  userPrompt: string,
  assistantReply: string,
): CoworkProjectArtifact | null {
  if (record.ok === false) return null
  const action = record.action
  const now = record.endedAt ?? Date.now()
  if (action.kind === 'connector') {
    const params = action.params ?? {}
    const text = [
      userPrompt,
      String(record.output || ''),
      stringParam(params, 'prompt'),
      stringParam(params, 'target'),
      stringParam(params, 'output_path'),
    ].filter(Boolean).join('\n')
    const kind = inferConnectorArtifactKind(action.connector, action.action, text)
    if (!kind) return null
    let paths = extractArtifactReferences(text, kind)
    if (paths.length === 0 && assistantReply) {
      paths = extractArtifactReferences(assistantReply, kind)
    }
    const primary = paths[0]
    const revision = isRevisionIntent(userPrompt) || action.action === 'img2img' || action.action === 'rebake' || action.action === 'animate'
    const previous = revision ? latestReadyArtifact(artifacts, kind) : undefined
    const parents = inferParentIds(artifacts, kind, action.connector, action.action, params, userPrompt)
    const version = nextVersionForKind(artifacts, kind)
    return {
      id: stableId('art', `${now}-${kind}-${primary?.value || text.slice(0, 80)}`),
      kind,
      label: buildArtifactLabel(kind, userPrompt, version),
      status: 'ready',
      version,
      createdAt: now,
      updatedAt: now,
      active: true,
      path: primary?.isUrl ? undefined : primary?.value,
      url: primary?.isUrl ? primary.value : undefined,
      previewUrl: kind === 'image' ? primary?.value : undefined,
      sourcePrompt: compact(stringParam(params, 'prompt') || userPrompt, 500),
      sourceAction: `connector:${action.connector}.${action.action}`,
      connector: action.connector,
      action: action.action,
      summary: compactArtifactSummary(record.output || '', kind),
      parentIds: parents.length > 0 ? parents : undefined,
      supersedesId: previous?.id,
    }
  }

  if (action.kind === 'write_file') {
    const kind = inferKindFromPath(action.path)
    if (!kind) return null
    const version = nextVersionForKind(artifacts, kind)
    const previous = isRevisionIntent(userPrompt) ? latestReadyArtifact(artifacts, kind) : undefined
    return {
      id: stableId('art', `${now}-${kind}-${action.path}`),
      kind,
      label: buildArtifactLabel(kind, userPrompt, version),
      status: 'ready',
      version,
      createdAt: now,
      updatedAt: now,
      active: true,
      path: action.path,
      previewUrl: kind === 'image' ? action.path : undefined,
      sourcePrompt: compact(userPrompt, 500),
      sourceAction: 'write_file',
      summary: compactArtifactSummary(record.output || `Fichier cree: ${action.path}`, kind),
      parentIds: inferParentIds(artifacts, kind, '', '', {}, userPrompt),
      supersedesId: previous?.id,
    }
  }

  return null
}

function inferConnectorArtifactKind(connector: string, action: string, text: string): CoworkProjectArtifactKind | null {
  const normalized = normalize(text)
  if (connector === 'aurora_image') return 'image'
  if (connector === 'aurora_3d') return 'model3d'
  if (connector === 'aurora_video') return 'video'
  if (connector === 'aurora_voice') return 'audio'
  if (connector === 'aurora_code') return /\b(jeu|game|gameplay|phaser|three\.?js|canvas|personnage principal)\b/.test(normalized) ? 'game' : 'code'
  if (connector === 'aurora_drawing') return 'image'
  if (connector === 'aurora_learning') return 'document'
  if (/generate|create|compose|export|write/i.test(action)) {
    if (/\b(jeu|game)\b/.test(normalized)) return 'game'
    if (/\b(image|photo|png|jpg|visuel)\b/.test(normalized)) return 'image'
    if (/\b(3d|glb|mesh|modele)\b/.test(normalized)) return 'model3d'
    if (/\b(video|mp4)\b/.test(normalized)) return 'video'
  }
  return null
}

function inferKindFromPath(path: string): CoworkProjectArtifactKind | null {
  const ext = path.split(/[?#]/)[0].split('.').pop()?.toLowerCase() || ''
  if (['png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp'].includes(ext)) return 'image'
  if (['glb', 'gltf', 'obj', 'fbx', 'blend'].includes(ext)) return 'model3d'
  if (['mp4', 'webm', 'mov', 'mkv'].includes(ext)) return 'video'
  if (['wav', 'mp3', 'ogg', 'flac'].includes(ext)) return 'audio'
  if (['html', 'css', 'js', 'jsx', 'ts', 'tsx', 'py', 'rs', 'go', 'json'].includes(ext)) return /\b(game|jeu)\b/i.test(path) ? 'game' : 'code'
  if (['pdf', 'docx', 'md', 'txt', 'pptx', 'xlsx'].includes(ext)) return 'document'
  if (['csv', 'jsonl', 'parquet'].includes(ext)) return 'data'
  return null
}

function extractArtifactReferences(text: string, preferredKind?: CoworkProjectArtifactKind): Array<{ value: string; isUrl: boolean }> {
  const refs: Array<{ value: string; isUrl: boolean }> = []
  const seen = new Set<string>()
  const pathPattern = /(?:https?:\/\/[^\s"'<>]+|\/api\/[^\s"'<>]+|[A-Za-z]:[\\/][^\s"'<>]+|\/[^\s"'<>]+|(?:\.\/)?(?:output|public|dist|src|app|application)[\\/][^\s"'<>]+)\.(?:png|jpe?g|webp|gif|bmp|glb|gltf|obj|fbx|blend|mp4|webm|mov|mkv|wav|mp3|ogg|flac|html|css|jsx?|tsx?|py|rs|go|json|pdf|docx|md|txt|pptx|xlsx|csv|zip)/gi
  for (const match of text.matchAll(pathPattern)) {
    const value = cleanupReference(match[0])
    if (!value || seen.has(value)) continue
    const kind = inferKindFromPath(value) || 'other'
    if (preferredKind && kind !== preferredKind && !(preferredKind === 'game' && kind === 'code')) continue
    seen.add(value)
    refs.push({ value, isUrl: /^(https?:|\/api\/)/i.test(value) })
  }
  return refs
}

function inferParentIds(
  artifacts: CoworkProjectArtifact[],
  kind: CoworkProjectArtifactKind,
  connector: string,
  action: string,
  params: Record<string, unknown>,
  prompt: string,
): string[] {
  const parents: string[] = []
  for (const key of ['image_path', 'source_image', 'glb_path', 'model_path', 'asset_path']) {
    const value = stringParam(params, key)
    if (!value) continue
    const match = artifacts.find((artifact) => artifact.path === value || artifact.url === value || artifact.previewUrl === value)
    if (match) parents.push(match.id)
  }
  const wantsImplicit = /\b(celui|celle|ce modele|cette image|ca|version|deuxieme|reference|personnage)\b/i.test(prompt)
  if (connector === 'aurora_image' && action === 'img2img') {
    const activeImage = latestReadyArtifact(artifacts, 'image')
    if (activeImage) parents.push(activeImage.id)
  }
  if (kind === 'model3d') {
    const activeImage = latestReadyArtifact(artifacts, 'image')
    if (activeImage && (wantsImplicit || parents.length === 0)) parents.push(activeImage.id)
  }
  if (kind === 'game') {
    const activeModel = latestReadyArtifact(artifacts, 'model3d')
    const activeImage = latestReadyArtifact(artifacts, 'image')
    if (activeModel && (wantsImplicit || parents.length === 0)) parents.push(activeModel.id)
    if (!activeModel && activeImage && (wantsImplicit || parents.length === 0)) parents.push(activeImage.id)
  }
  return [...new Set(parents)]
}

function latestReadyArtifact(artifacts: CoworkProjectArtifact[], kind?: CoworkProjectArtifactKind): CoworkProjectArtifact | undefined {
  const list = artifacts.filter((artifact) => artifact.status === 'ready' && (!kind || artifact.kind === kind))
  return list[list.length - 1]
}

function nextVersionForKind(artifacts: CoworkProjectArtifact[], kind: CoworkProjectArtifactKind): number {
  return Math.max(0, ...artifacts.filter((artifact) => artifact.kind === kind).map((artifact) => artifact.version || 1)) + 1
}

function pickActiveArtifactId(artifacts: CoworkProjectArtifact[], current?: string): string | undefined {
  const explicit = artifacts.find((artifact) => artifact.active && artifact.status === 'ready')
  if (explicit) return explicit.id
  const currentArtifact = current ? artifacts.find((artifact) => artifact.id === current && artifact.status === 'ready') : undefined
  if (currentArtifact) return currentArtifact.id
  const ready = artifacts.filter((artifact) => artifact.status === 'ready')
  return ready.length > 0 ? ready[ready.length - 1].id : undefined
}

function dedupeArtifacts(artifacts: CoworkProjectArtifact[]): CoworkProjectArtifact[] {
  const byKey = new Map<string, CoworkProjectArtifact>()
  for (const artifact of artifacts) {
    const key = artifact.path || artifact.url || artifact.id
    byKey.set(key, artifact)
  }
  return [...byKey.values()]
}

function buildArtifactLabel(kind: CoworkProjectArtifactKind, prompt: string, version: number): string {
  const topic = extractTopic(prompt)
  return `${artifactLabel(kind)} v${version}${topic ? ` - ${topic}` : ''}`
}

function formatArtifactForPrompt(artifact: CoworkProjectArtifact): string {
  const ref = artifact.path || artifact.url || artifact.previewUrl || '(chemin non expose)'
  const parents = artifact.parentIds?.length ? ` parents=${artifact.parentIds.join(',')}` : ''
  const supersedes = artifact.supersedesId ? ` remplace=${artifact.supersedesId}` : ''
  return `[${artifact.id}] ${artifactLabel(artifact.kind)} v${artifact.version} ${artifact.status} path=${ref}${parents}${supersedes}`
}

function stageLabel(action: CoworkAction): string {
  if (action.kind === 'connector') {
    if (action.connector === 'aurora_image') return action.action === 'img2img' ? 'Modifie une image' : 'Genere une image'
    if (action.connector === 'aurora_3d') return 'Genere ou ajuste un modele 3D'
    if (action.connector === 'aurora_code') return 'Construit le projet/code'
    if (action.connector === 'aurora_video') return 'Compose une video'
    return `Connecteur ${action.connector}.${action.action}`
  }
  if (action.kind === 'write_file') return `Cree ${lastPathPart(action.path)}`
  if (action.kind === 'edit_file') return `Modifie ${lastPathPart(action.path)}`
  if (action.kind === 'read_file') return `Verifie ${lastPathPart(action.path)}`
  if (action.kind === 'shell') return `Teste avec ${action.command}`
  if (action.kind === 'think' || action.kind === 'think_long') return action.topic
  return action.kind
}

function sanitizeThreadForStorage(thread: CoworkProjectThread): CoworkProjectThread {
  const normalized = normalizeCoworkProjectThread(thread)
  return {
    ...normalized,
    artifacts: normalized.artifacts.map((artifact) => ({
      ...artifact,
      previewUrl: trimHugeDataUrl(artifact.previewUrl),
      summary: artifact.summary ? compactArtifactSummary(artifact.summary, artifact.kind, true) : undefined,
      sourcePrompt: artifact.sourcePrompt ? compact(artifact.sourcePrompt, 600) : undefined,
    })),
  }
}

function normalizeArtifactKind(kind: string): CoworkProjectArtifactKind {
  return ['image', 'model3d', 'game', 'code', 'video', 'audio', 'document', 'data', 'other'].includes(kind)
    ? kind as CoworkProjectArtifactKind
    : 'other'
}

function normalizeArtifactStatus(status: unknown): CoworkProjectArtifactStatus {
  return status === 'planned' || status === 'generating' || status === 'failed' ? status : 'ready'
}

function normalizeStageStatus(status: unknown): CoworkProjectStageStatus {
  return status === 'error' || status === 'warn' || status === 'running' ? status : 'ok'
}

function isRevisionIntent(prompt: string): boolean {
  return /\b(modifie|modifier|change|changer|retouche|retoucher|corrige|corriger|ameliore|ameliorer|refais|refaire|version|deuxieme|2e|v2|plus|moins|garde|remplace|remplacer)\b/i.test(normalize(prompt))
}

function inferBrief(prompt: string, previous?: string): string | undefined {
  if (!prompt) return previous
  return compact(prompt, 160)
}

function extractTopic(prompt: string): string {
  const cleanPrompt = clean(prompt)
    .replace(/^(cree|creer|genere|generer|fais|faire|modifie|modifier|modele|modelise|transforme|construis|developpe)\b\s*/i, '')
    .replace(/\b(image|photo|modele 3d|3d|jeu|game|video|code)\b/gi, '')
    .replace(/\s+/g, ' ')
    .trim()
  return compact(cleanPrompt, 44)
}

function stringParam(params: Record<string, unknown>, key: string): string {
  const value = params[key]
  return typeof value === 'string' ? value : ''
}

function cleanupReference(value: string): string {
  return value.replace(/[),.;\]}]+$/g, '').replace(/^["'`]+|["'`]+$/g, '')
}

function stableId(prefix: string, seed: string): string {
  let hash = 0
  for (let i = 0; i < seed.length; i += 1) {
    hash = (Math.imul(31, hash) + seed.charCodeAt(i)) | 0
  }
  return `${prefix}_${Math.abs(hash).toString(36)}`
}

function lastPathPart(path: string): string {
  const parts = path.replace(/\\/g, '/').split('/').filter(Boolean)
  return parts.length > 0 ? parts[parts.length - 1] : path
}

function trimHugeDataUrl(value?: string): string | undefined {
  if (!value) return undefined
  if (value.startsWith('data:') && value.length > 120_000) return undefined
  return value
}

function uniqueTail(values: string[], max: number): string[] {
  const out: string[] = []
  for (const value of values) {
    const cleanValue = clean(value)
    if (!cleanValue) continue
    if (out[out.length - 1] === cleanValue) continue
    out.push(cleanValue)
  }
  return out.slice(-max)
}

function compact(value: string, max: number): string {
  const c = clean(value)
  return c.length > max ? `${c.slice(0, max - 1)}...` : c
}

function compactArtifactSummary(value: string, kind: CoworkProjectArtifactKind, forStorage = false): string {
  const max = kind === 'code' || kind === 'game'
    ? (forStorage ? 40_000 : 80_000)
    : (forStorage ? 1_200 : 2_000)
  const prepared = kind === 'code' || kind === 'game' ? value.trim() : clean(value)
  return prepared.length > max ? `${prepared.slice(0, max - 1)}...` : prepared
}

function clean(value: string): string {
  return value.replace(/\s+/g, ' ').trim()
}

function normalize(value: string): string {
  return clean(value)
    .toLowerCase()
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
}
