/**
 * Character Forge — 8-step pipeline (cf. BRIEF-CLAUDE-CODE.md).
 *
 * Chaque étape consomme un vrai backend local :
 *   1-3  Ollama (modèle texte)              → character_meta, traits, rig.yaml
 *   4-6  generate_avatar.py + ComfyUI/FLUX  → reference_portrait + features
 *   7    assemble côté TS à partir des sorties des étapes 01-06
 *   8    retour au caller (UI) qui publie dans la galerie sur « Enregistrer »
 *
 * Pas de mock. Si un backend manque, l'étape renvoie `status: 'skipped'` avec
 * une raison lisible, l'UI l'affiche tel quel. La pipeline continue tant que
 * les étapes critiques 01-04 ont abouti.
 */
import { ollamaChat } from '../hooks/useTauri.ts'
import type { OllamaMessage } from '../types/app.ts'
import { getBridgeUrl } from '../utils/runtime.ts'
import { fetchPythonJob, launchPythonJob, waitForPythonJob } from './pythonJobClient.ts'

export type ForgeStepId =
  | 'intent' | 'traits' | 'rig_plan' | 'reference'
  | 'expressions' | 'segment' | 'assemble' | 'publish'

export type ForgeStepStatus = 'pending' | 'running' | 'done' | 'skipped' | 'error'

export interface ForgeStep {
  id: ForgeStepId
  label: string
  status: ForgeStepStatus
  detail?: string
  startedAt?: number
  endedAt?: number
}

export const FORGE_STEPS: Pick<ForgeStep, 'id' | 'label'>[] = [
  { id: 'intent',       label: '01 · Intention & lore' },
  { id: 'traits',       label: '02 · Analyse des traits signature' },
  { id: 'rig_plan',     label: '03 · Plan de rig sur-mesure' },
  { id: 'reference',    label: '04 · Génération portrait canonique' },
  { id: 'expressions',  label: '05 · Variations d\'expression' },
  { id: 'segment',      label: '06 · Détection faciale & calques' },
  { id: 'assemble',     label: '07 · Assemblage du rig' },
  { id: 'publish',      label: '08 · Prêt à enregistrer' },
]

export interface CharacterMeta {
  id: string
  display_name: string
  franchise: string | null
  creator: string | null
  created_at: string
  style_hint: string
  router_model: 'flux-dev' | 'illustrious' | 'pony' | 'sdxl'
}

export interface CharacterTraits {
  has_human_face: boolean
  skin_tone: string | null
  eyes: { type: string; left?: string; right?: string } | null
  mouth: { type: string; permanent?: boolean; teeth_visible?: boolean } | null
  eyebrows: string | null
  hair: string | null
  headwear: { type: string; colors?: string[] } | null
  signature_elements: string[]
  forbidden_elements: string[]
}

export interface RigLayer {
  id: string
  z: number
  kind: 'static' | 'phonemes' | 'float_and_contract' | 'float_and_rotate' |
        'rigid_swing' | 'fx_triggered' | 'blink_eyelid' | 'brow_raise' |
        'hair_sway' | 'custom'
  variants?: string[]
  trigger?: string
}

export interface RigPlan {
  character_id: string
  style: string
  base_model: string
  layers: RigLayer[]
  anim_rules: Record<string, Record<string, unknown>>
  forbidden: string[]
}

export interface ForgeLayerFile {
  layerId: string
  /** URL served by the bridge (/avatars/.../NN_layer.png) */
  url: string
  /** GroundingDINO prompt used to extract this layer */
  prompt: string
}

export interface ForgeResult {
  meta: CharacterMeta
  traits: CharacterTraits
  rig: RigPlan
  /** URL (absolute or /api/... path) of the canonical portrait. */
  portraitUrl: string
  /** Feature landmarks detected by the vision model, if any. */
  features: Record<string, unknown> | null
  /** Movement archetype inferred for the avatar. */
  animationMode: 'humanoid' | 'creature' | 'robot' | 'abstract'
  researchBrief: string
  howTheySpeak: string
  /** When generate_avatar.py produced additional variations. */
  variationUrls: string[]
  /** PNG layers extracted via SAM2+BiRefNet+LaMa (step 06). */
  layerFiles: ForgeLayerFile[]
  /** Base portrait with animated regions inpainted (LaMa). */
  baseLayerUrl: string | null
  steps: ForgeStep[]
}

type StepEmit = (step: ForgeStepId, patch: Partial<ForgeStep>) => void

// ---------------------------------------------------------------------------
// Ollama helpers — structured JSON via a strict system prompt.
// ---------------------------------------------------------------------------

async function ollamaJson<T>(
  model: string,
  systemPrompt: string,
  userPrompt: string,
  signal?: AbortSignal,
): Promise<T> {
  const messages: OllamaMessage[] = [
    { role: 'system', content: systemPrompt },
    { role: 'user',   content: userPrompt },
  ]
  const res = await ollamaChat(model, messages, 0.25, { num_ctx: 8192, signal })
  const raw = (res?.message?.content ?? '').trim()
  // Accept ```json ... ``` fences or bare objects
  const fence = raw.match(/```(?:json)?\s*([\s\S]+?)```/)
  const body = (fence ? fence[1] : raw).trim()
  const first = body.indexOf('{')
  const last  = body.lastIndexOf('}')
  const jsonStr = first !== -1 && last !== -1 ? body.slice(first, last + 1) : body
  return JSON.parse(jsonStr) as T
}

const SYS_INTENT = `Tu es l'étage "intent & lore" du pipeline Character Forge de l'app AuroraIA.
Tu reçois UN prompt utilisateur (nom de personnage + éventuellement l'œuvre) et tu retournes un JSON STRICT, pas de prose, pas de markdown.
Schéma attendu :
{
  "display_name": string,
  "franchise": string | null,
  "creator": string | null,
  "style_hint": string,   // ex: "cartoon-3d-theatrical", "anime-cel-shaded", "cinematic-photoreal", "toon-soft", "mascot-flat"
  "router_model": "flux-dev" | "illustrious" | "pony" | "sdxl"
}
Choix du router :
- anime / manga / cel-shading / Bocchi / JJK / Tokyo Ghoul → "illustrious"
- cartoon 3D théâtral / mascot / Caine-type / Gooseworx / non-humain stylisé → "pony"
- réaliste / cinéma / prompt inconnu / personnage unique → "flux-dev"
- tout le reste → "sdxl"
Ne devine RIEN d'autre (pas de traits, pas de rig). Juste ce schéma.`

const SYS_TRAITS = `Tu es l'étage "trait analysis" du pipeline Character Forge.
Tu reçois un nom de personnage + son character_meta. Tu listes les features signature ET les éléments INTERDITS.
RÈGLE CRITIQUE : si le personnage n'a pas d'yeux humains, pas de peau, pas de sourcils, tu mets null/false à ces champs. Tu N'INVENTES PAS une structure standard "2 yeux / 1 bouche / 2 sourcils" si ce n'est pas le cas.
Retour JSON STRICT conforme :
{
  "has_human_face": boolean,
  "skin_tone": string | null,
  "eyes": { "type": string, "left"?: string, "right"?: string } | null,
  "mouth": { "type": string, "permanent"?: boolean, "teeth_visible"?: boolean } | null,
  "eyebrows": string | null,
  "hair": string | null,
  "headwear": { "type": string, "colors"?: string[] } | null,
  "signature_elements": string[],   // 2-6 items max, ex: ["floating_eyes","permanent_smile","monochrome_face"]
  "forbidden_elements": string[]    // ce qui NE doit JAMAIS apparaître sur ce perso, ex: ["eyelid","eyebrow","skin_shading"]
}
Aucune prose, aucun markdown, uniquement l'objet JSON.`

const SYS_RIG = `Tu es l'étage "custom rig plan" du pipeline Character Forge.
Tu reçois character_meta + traits. Tu produis un plan de rig SUR MESURE (pas un gabarit générique).
Règles :
- Chaque layer est soit statique, soit animé avec un kind explicite.
- Tu ne crées PAS de layer pour un élément présent dans forbidden_elements.
- Si le perso n'a pas d'yeux classiques (ex. étoile/croissant), tu utilises kind="float_and_contract" ou "float_and_rotate" au lieu de "blink_eyelid".
- Le layer "mouth" a toujours kind="phonemes" si la bouche existe, avec variants ["rest","A","O","E","M"].
- Au minimum 3 layers avec kind != "static", sinon le perso ne bougera pas.
- "anim_rules" doit contenir les règles utilisables par le player runtime : blink, breath, talk, excited (quand pertinents).
Retour JSON STRICT conforme :
{
  "layers": [{ "id": string, "z": number, "kind": string, "variants"?: string[], "trigger"?: string }],
  "anim_rules": { [ruleName]: object },
  "forbidden": string[]
}
Aucune prose, aucun markdown, uniquement l'objet JSON.`

// ---------------------------------------------------------------------------
// Main orchestrator
// ---------------------------------------------------------------------------

function nowIso(): string {
  return new Date().toISOString()
}

function slugify(s: string): string {
  return s.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '').slice(0, 60) || 'character'
}

/**
 * Optional "resume" payload handed to `runForgePipeline` so we can pick up a
 * job in progress after a page reload — each field, when present, lets the
 * pipeline SKIP the corresponding step.
 */
export interface ForgeResume {
  meta?: CharacterMeta
  traits?: CharacterTraits
  rig?: RigPlan
  portraitUrl?: string
  features?: Record<string, unknown> | null
  animationMode?: ForgeResult['animationMode']
  researchBrief?: string
  howTheySpeak?: string
  variationUrls?: string[]
  layerFiles?: ForgeLayerFile[]
  baseLayerUrl?: string | null
  /** jobId of the generate_avatar.py subprocess, if it was launched. Lets a
   * reload reconnect to a running / completed subprocess instead of
   * restarting it from scratch. */
  referenceJobId?: string
  /** jobId of the forge_layers.py subprocess (step 07 segmentation). */
  layersJobId?: string
}

/** Hook fired after each major step so the caller can persist the growing
 * partial result — so a reload mid-pipeline doesn't lose the work done. */
export type ForgeArtifactSink = (partial: Partial<ForgeResume>) => void

export async function runForgePipeline(
  prompt: string,
  textModel: string,
  opts: {
    onStep: StepEmit
    onStatus: (msg: string, pct?: number) => void
    signal?: AbortSignal
    /** If set, pipeline reuses these artifacts and skips the matching steps. */
    resume?: ForgeResume
    /** Called as soon as each major artifact is produced; use to persist. */
    onArtifact?: ForgeArtifactSink
  },
): Promise<ForgeResult> {
  const { onStep, onStatus, signal, resume, onArtifact } = opts
  const mkStep = (id: ForgeStepId, patch: Partial<ForgeStep>) => onStep(id, patch)
  const save = (p: Partial<ForgeResume>) => { try { onArtifact?.(p) } catch { /* ignore */ } }

  // Pre-parse natural-language removals ("sans cape", "sans masque") → merge into forbidden_elements.
  const { parseImageIntent } = await import('../utils/imagePromptParser')
  const forgeIntent = parseImageIntent(prompt)
  const promptForLLM = forgeIntent.cleanedPrompt

  // --- 01 intent -----------------------------------------------------------
  let meta: CharacterMeta
  if (resume?.meta) {
    meta = resume.meta
    mkStep('intent', { status: 'done', detail: `↻ repris : ${meta.display_name}`, endedAt: Date.now() })
  } else {
    mkStep('intent', { status: 'running', detail: 'Lecture du prompt…', startedAt: Date.now() })
    const metaRaw = await ollamaJson<Omit<CharacterMeta, 'id' | 'created_at'>>(
      textModel, SYS_INTENT, promptForLLM, signal,
    )
    const characterId = `${slugify(metaRaw.display_name || promptForLLM)}_v${Date.now().toString(36)}`
    meta = {
      id: characterId,
      display_name: metaRaw.display_name,
      franchise: metaRaw.franchise ?? null,
      creator: metaRaw.creator ?? null,
      created_at: nowIso(),
      style_hint: metaRaw.style_hint,
      router_model: metaRaw.router_model,
    }
    mkStep('intent', { status: 'done', detail: `${meta.display_name} · ${meta.style_hint} · router=${meta.router_model}`, endedAt: Date.now() })
    save({ meta })
  }
  const characterId = meta.id

  // --- 02 traits -----------------------------------------------------------
  let traits: CharacterTraits
  if (resume?.traits) {
    traits = resume.traits
    mkStep('traits', { status: 'done', detail: `↻ repris : signature ${(traits.signature_elements || []).length} items`, endedAt: Date.now() })
  } else {
    mkStep('traits', { status: 'running', detail: 'Détection des features signature…', startedAt: Date.now() })
    traits = await ollamaJson<CharacterTraits>(
      textModel, SYS_TRAITS,
      `prompt="${promptForLLM}"\ncharacter_meta=${JSON.stringify(meta)}`,
      signal,
    )
    // v82bl : merge parser-detected removals into forbidden_elements
    // (defense-in-depth on top of LLM output). Dedup case-insensitive.
    if (forgeIntent.removals.length > 0) {
      const existing = new Set((traits.forbidden_elements || []).map((s) => s.toLowerCase()))
      const merged = [...(traits.forbidden_elements || [])]
      for (const r of forgeIntent.removals) {
        if (!existing.has(r.toLowerCase())) merged.push(r)
      }
      traits = { ...traits, forbidden_elements: merged }
    }
    const trimSignature = (traits.signature_elements || []).slice(0, 6).join(', ')
    mkStep('traits', { status: 'done', detail: `Signature: ${trimSignature || '—'}`, endedAt: Date.now() })
    save({ traits })
  }

  // --- 03 rig plan ---------------------------------------------------------
  let rig: RigPlan
  if (resume?.rig) {
    rig = resume.rig
    mkStep('rig_plan', { status: 'done', detail: `↻ repris : ${rig.layers.length} layers`, endedAt: Date.now() })
  } else {
    mkStep('rig_plan', { status: 'running', detail: 'Assemblage du plan de rig…', startedAt: Date.now() })
    const rigSkeleton = await ollamaJson<Omit<RigPlan, 'character_id' | 'style' | 'base_model'>>(
      textModel, SYS_RIG,
      `character_meta=${JSON.stringify(meta)}\ntraits=${JSON.stringify(traits)}`,
      signal,
    )
    rig = {
      character_id: characterId,
      style: meta.style_hint,
      base_model: meta.router_model,
      layers: rigSkeleton.layers || [],
      anim_rules: rigSkeleton.anim_rules || {},
      forbidden: rigSkeleton.forbidden || traits.forbidden_elements || [],
    }
    const movingLayers = rig.layers.filter((l) => l.kind !== 'static').length
    mkStep('rig_plan', { status: 'done', detail: `${rig.layers.length} layers · ${movingLayers} animés`, endedAt: Date.now() })
    save({ rig })
  }

  // --- 04-06 reference + expressions + segment via generate_avatar.py ------
  // If the portrait is already on disk (we persisted the URL after a prior
  // run), skip the python subprocess entirely and move straight to segment.
  if (resume?.portraitUrl) {
    mkStep('reference',   { status: 'done', detail: '↻ repris : portrait déjà généré', endedAt: Date.now() })
    mkStep('expressions', { status: 'done', detail: '↻ repris', endedAt: Date.now() })
    mkStep('segment',     { status: resume.features ? 'done' : 'pending', endedAt: resume.features ? Date.now() : undefined })
  }
  // On subscribe aux PROGRESS: émis par le script et on remappe vers nos étapes.
  const needReference = !resume?.portraitUrl
  if (needReference) {
    mkStep('reference',   { status: 'running', detail: 'Lancement de ComfyUI (FLUX/Illustrious)…', startedAt: Date.now() })
    mkStep('expressions', { status: 'pending' })
    mkStep('segment',     { status: 'pending' })
  }

  const ts = Date.now()
  const filename = `forge-${characterId}-${ts}.png`
  const outputRel = `public/avatars/${filename}`
  let currentStep: ForgeStepId = 'reference'
  let portraitUrl: string
  let refPath: string
  let animationMode: ForgeResult['animationMode']
  let researchBrief: string
  let howTheySpeak: string
  let variationUrls: string[]

  if (resume?.portraitUrl) {
    // Skip python subprocess: reuse persisted portrait.
    portraitUrl = resume.portraitUrl
    refPath = portraitUrl.startsWith('/') ? `public${portraitUrl}` : portraitUrl
    animationMode = resume.animationMode || 'humanoid'
    researchBrief = resume.researchBrief || ''
    howTheySpeak = resume.howTheySpeak || ''
    variationUrls = resume.variationUrls || []
  } else {
    const onProgressLine = (raw: string) => {
      if (!raw.startsWith('PROGRESS:')) return
      const match = raw.match(/^PROGRESS:(\d+):(.*)$/)
      if (!match) return
      const pct = parseInt(match[1], 10)
      const detail = match[2].trim()
      onStatus(detail, pct)
      let nextStep: ForgeStepId = currentStep
      if (pct < 55) nextStep = 'reference'
      else if (pct < 85) nextStep = 'expressions'
      else nextStep = 'segment'
      if (nextStep !== currentStep) {
        mkStep(currentStep, { status: 'done', endedAt: Date.now() })
        mkStep(nextStep, { status: 'running', detail, startedAt: Date.now() })
        currentStep = nextStep
      } else {
        mkStep(currentStep, { detail })
      }
    }

    // RESUME: if a previous run persisted a jobId, try to reconnect to it
    // before re-launching — the subprocess may have finished on the bridge
    // while our tab was dead.
    let jobId = resume?.referenceJobId
    if (jobId) {
      const existing = await fetchPythonJob(jobId)
      if (existing.status === 'unknown') {
        // Bridge gc'd it or we never had it. Drop and re-launch below.
        jobId = undefined
        save({ referenceJobId: undefined })
        mkStep('reference', { detail: '↻ ancien job perdu par le bridge — nouveau lancement' })
      } else {
        mkStep('reference', { detail: `↻ reconnexion job ${jobId.slice(0, 6)}…` })
      }
    }
    if (!jobId) {
      jobId = await launchPythonJob(
        'python-services/generate_avatar.py',
        ['--prompt', prompt, '--output', outputRel, '--image-only'],
      )
      // Persist the jobId IMMEDIATELY so a reload a millisecond later can
      // still find the subprocess.
      save({ referenceJobId: jobId })
    }

    const finalStatus = await waitForPythonJob(jobId, { onProgress: onProgressLine })
    const pythonResult = {
      output: finalStatus.output,
      error: finalStatus.error,
      exitCode: finalStatus.exitCode,
    }

    // Parse the tail JSON line (générateur émet un JSON sur stdout à la fin)
    const allOutput = (pythonResult.output || '') + '\n' + (pythonResult.error || '')
    const jsonLine = allOutput.split('\n').filter((l) => l.trim().startsWith('{')).pop()
    if (pythonResult.exitCode !== 0 || !jsonLine) {
      const meaningful = allOutput
        .split('\n')
        .map((l) => l.trim())
        .filter((l) => l.length > 0 && !l.startsWith('PROGRESS:'))
        .slice(-6)
        .join(' | ')
        .slice(0, 360)
      const reason = meaningful || `exit=${pythonResult.exitCode}`
      throw new Error(`generate_avatar.py a échoué — ${reason}`)
    }
    const parsed = JSON.parse(jsonLine) as {
      ok: boolean
      error?: string
      refImage?: string
      path?: string
      animation_mode?: string
      research_brief?: string
      how_they_speak?: string
      variations?: string[]
    }
    if (!parsed.ok) throw new Error(parsed.error || 'Generation avortée')

    refPath = parsed.refImage || parsed.path || outputRel
    portraitUrl = refPath.startsWith('/')
      ? refPath
      : `/${refPath.replace(/^public\//, '')}`
    animationMode = (['humanoid', 'creature', 'robot', 'abstract'].includes(parsed.animation_mode || '')
      ? parsed.animation_mode
      : 'humanoid') as ForgeResult['animationMode']
    researchBrief = parsed.research_brief || ''
    howTheySpeak = parsed.how_they_speak || ''
    variationUrls = Array.isArray(parsed.variations) ? parsed.variations : []

    mkStep(currentStep, { status: 'done', detail: `Portrait prêt · mode ${animationMode}`, endedAt: Date.now() })
    save({ portraitUrl, animationMode, researchBrief, howTheySpeak, variationUrls })
  }

  // --- detect features via vision (already done internally by script if available) ---
  let features: Record<string, unknown> | null = resume?.features ?? null
  if (resume?.features === undefined) {
    try {
      mkStep('segment', { status: 'running', detail: 'Analyse faciale Qwen3-VL…' })
      const bridge = getBridgeUrl()
      const imgUrl = bridge && portraitUrl.startsWith('/') ? `${bridge}${portraitUrl}` : portraitUrl
      const imgResp = await fetch(imgUrl)
      if (imgResp.ok) {
        const blob = await imgResp.blob()
        const mod = await import('./visionService')
        const detected = await mod.detectFacialFeatures({ kind: 'blob', data: blob })
        if (detected?.hasFace) features = detected as unknown as Record<string, unknown>
      }
      mkStep('segment', {
        status: features ? 'done' : 'skipped',
        detail: features
          ? 'Landmarks détectés'
          : 'Aucun visage humain détecté (normal pour un perso non-humain)',
        endedAt: Date.now(),
      })
      save({ features: features || null })
    } catch (err) {
      mkStep('segment', {
        status: 'skipped',
        detail: `Vision indispo: ${err instanceof Error ? err.message : String(err)}`,
        endedAt: Date.now(),
      })
      save({ features: null })
    }
  }

  // --- 07 assemble --------------------------------------------------------
  rig.anim_rules['_animation_mode'] = { mode: animationMode }
  const layerFiles: ForgeLayerFile[] = resume?.layerFiles ? [...resume.layerFiles] : []
  let baseLayerUrl: string | null = resume?.baseLayerUrl ?? null
  const alreadySegmented = layerFiles.length > 0
  if (alreadySegmented) {
    mkStep('assemble', {
      status: 'done',
      detail: `↻ repris : ${layerFiles.length} calques déjà extraits`,
      endedAt: Date.now(),
    })
  } else {
    mkStep('assemble', { status: 'running', detail: 'Segmentation SAM2 + BiRefNet + LaMa…', startedAt: Date.now() })
  try {
    const rigRel = `public/avatars/${characterId}_rig.json`
    const outRel = `public/avatars/${characterId}_layers`
    // Rig write is a tiny blocking script — launch + wait directly.
    const rigJobId = await launchPythonJob(
      'python-services/forge_write_rig.py',
      ['--out', rigRel, '--rig', JSON.stringify(rig)],
    )
    const rigWriteRes = await waitForPythonJob(rigJobId)
    if (rigWriteRes.exitCode !== 0) {
      throw new Error(`rig write failed: ${rigWriteRes.error || 'exit ' + rigWriteRes.exitCode}`)
    }

    const onSegProgress = (raw: string) => {
      if (!raw.startsWith('PROGRESS:')) return
      const match = raw.match(/^PROGRESS:(\d+):(.*)$/)
      if (match) {
        mkStep('assemble', { detail: match[2].trim() })
        onStatus(match[2].trim(), parseInt(match[1], 10))
      }
    }

    // RESUME: same pattern as reference — reconnect to a prior segmentation
    // job if the bridge still remembers it.
    let segJobId = resume?.layersJobId
    if (segJobId) {
      const existing = await fetchPythonJob(segJobId)
      if (existing.status === 'unknown') {
        segJobId = undefined
        save({ layersJobId: undefined })
      }
    }
    if (!segJobId) {
      segJobId = await launchPythonJob(
        'python-services/forge_layers.py',
        ['--portrait', refPath, '--rig', rigRel, '--out', outRel],
      )
      save({ layersJobId: segJobId })
    }
    const segResult = await waitForPythonJob(segJobId, { onProgress: onSegProgress })
    const segAllOut = (segResult.output || '') + '\n' + (segResult.error || '')
    const segJsonLine = segAllOut.split('\n').filter((l) => l.trim().startsWith('{')).pop()
    if (segResult.exitCode === 0 && segJsonLine) {
      const segJson = JSON.parse(segJsonLine) as {
        ok: boolean; error?: string;
        layers?: Array<{ layer: string; ok: boolean; path?: string; prompt?: string }>;
        base?: string | null;
      }
      if (segJson.ok) {
        for (const l of segJson.layers || []) {
          if (l.ok && l.path) {
            // Convert public/ path to served URL
            const url = l.path.replace(/\\/g, '/').replace(/^.*?public\//, '/')
            layerFiles.push({ layerId: l.layer, url, prompt: l.prompt || '' })
          }
        }
        if (segJson.base) {
          baseLayerUrl = segJson.base.replace(/\\/g, '/').replace(/^.*?public\//, '/')
        }
      }
    }
  } catch (err) {
    // Non-fatal: if segmentation fails we still publish a one-layer avatar
    mkStep('assemble', { detail: `layers skip: ${err instanceof Error ? err.message : String(err)}` })
  }

    mkStep('assemble', {
      status: 'done',
      detail: layerFiles.length > 0
        ? `${layerFiles.length} calques PNG extraits${baseLayerUrl ? ' + base inpainted' : ''}`
        : `rig.json prêt (${rig.layers.length} layers, segmentation ignorée)`,
      endedAt: Date.now(),
    })
    save({ layerFiles, baseLayerUrl })
  }

  // --- 08 publish (UI does the save on "Enregistrer") ---------------------
  mkStep('publish', { status: 'done', detail: 'En attente de ton validation', endedAt: Date.now() })

  return {
    meta,
    traits,
    rig,
    portraitUrl,
    features,
    animationMode,
    researchBrief,
    howTheySpeak,
    variationUrls,
    layerFiles,
    baseLayerUrl,
    steps: [], // will be filled by the UI from its local state
  }
}
