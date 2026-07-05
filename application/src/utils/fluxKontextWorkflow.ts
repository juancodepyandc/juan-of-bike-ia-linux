/**
 * fluxKontextWorkflow - vraie modification d'image par instruction.
 *
 * FLUX.1 Kontext dev prend une image de reference et une instruction d'edition.
 * Le graphe suit le workflow ComfyUI FLUX actuel: UNETLoader -> ModelSamplingFlux
 * -> BasicScheduler/BasicGuider -> SamplerCustomAdvanced. Sans ModelSamplingFlux,
 * Comfy peut terminer sans erreur tout en decodant une image noire.
 */
import {
  IMAGE_CLIP_MODEL,
  IMAGE_T5_MODEL,
  IMAGE_VAE_MODEL,
} from '../config/models.ts'
import { hasHumanRemovalTarget, isHumanRemovalTarget, type ParsedImageIntent } from './imagePromptParser.ts'

/** Noms de fichiers UNET kontext reconnus, par ordre de preference. */
export const FLUX_KONTEXT_UNET_CANDIDATES = [
  'flux1-dev-kontext_fp8_scaled.safetensors',
  'flux1-kontext-dev-fp8.safetensors',
  'flux1-kontext-dev_fp8.safetensors',
  'flux1-kontext-dev.safetensors',
]

/** Resout le modele kontext parmi les UNET installes (object_info UNETLoader). */
export function resolveKontextModel(installedUnets: string[]): string | null {
  const normalized = installedUnets.map((name) => name.replace(/\\/g, '/'))
  for (const candidate of FLUX_KONTEXT_UNET_CANDIDATES) {
    const hit = normalized.find((name) => name.toLowerCase().endsWith(candidate.toLowerCase()))
    if (hit) return hit
  }
  const loose = normalized.find((name) => /kontext/i.test(name))
  return loose ?? null
}

function inferKontextWeightDtype(unetName: string) {
  const lower = unetName.toLowerCase()
  if (lower.includes('fp8_scaled') || lower.includes('fp8-scaled')) return 'default'
  if (lower.includes('fp8_e5m2')) return 'fp8_e5m2'
  if (lower.includes('fp8')) return 'fp8_e4m3fn'
  return 'default'
}

export interface BuildKontextInstructionOptions {
  /**
   * Coeur d'instruction deja traduit en anglais propre.
   * Quand fourni, les clauses restent generiques pour ne pas reinjecter
   * des cibles francaises que Kontext comprend moins bien.
   */
  englishCore?: string
}

const SHOULDER_PLACEMENT_RE = /\b(?:shoulder|epaule|epaule|[e\u00e9]paule)\b/i
const STANDALONE_ADDITION_RE = /\b(?:personnage|personne|humain|humaine|homme|femme|garcon|fille|adulte|enfant|jardinier|jardiniere|animal|chien|chat|robot|mascotte|character|person|human|man|woman|boy|girl|adult|child|gardener|animal|dog|cat|robot|mascot)\b/i
const RELOCATION_RE = /\b(d[e\u00e9]place|d[e\u00e9]placer|repositionne|repositionner|d[e\u00e9]cale|d[e\u00e9]caler|move|reposition|shift)\b/i
const REQUESTED_CONTACT_RE = /\b(?:touche|toucher|tient|tenir|attrape|attraper|saisit|saisir|main\s+sur|mains\s+sur|bras\s+sur|bras\s+autour|epaule|[e\u00e9]paule|contact|grip|grab|hold|holding|touch|hand\s+on|hands\s+on|arm\s+around|arms\s+around|shoulder)\b/i

function additionMentionsShoulder(intent: ParsedImageIntent): boolean {
  return intent.additions.some((addition) => SHOULDER_PLACEMENT_RE.test(addition))
}

function additionsIntroduceStandaloneSubject(additions: string[]): boolean {
  return additions.some((addition) => {
    const trimmed = addition.replace(/\s+/g, ' ').trim()
    return STANDALONE_ADDITION_RE.test(trimmed) || /^[A-ZÀ-Ÿ0-9]/u.test(trimmed)
  })
}

function requestAllowsContact(prompt: string, additions: string[] = []): boolean {
  return REQUESTED_CONTACT_RE.test([prompt, ...additions].join(' '))
}

export function buildKontextInstruction(
  rawPrompt: string,
  intent: ParsedImageIntent | null | undefined,
  options: BuildKontextInstructionOptions = {},
): string {
  const englishCore = options.englishCore?.replace(/\s+/g, ' ').trim()
  const base = englishCore || rawPrompt.replace(/\s+/g, ' ').trim()
  if (!intent || !intent.isEditIntent) return base

  const targetFree = Boolean(englishCore)
  const parts: string[] = [base]

  switch (intent.editMode) {
    case 'remove_element':
      if (!targetFree && intent.removals.length > 0) {
        parts.push(`Remove ${intent.removals.join(' and ')} completely, reconstruct the area behind naturally`)
      } else if (targetFree) {
        parts.push('Remove the requested element completely, reconstruct the area behind naturally')
      }
      if (hasHumanRemovalTarget(intent.removals)) {
        parts.push('The removed target is a whole person or character: remove every visible part of that target, including head, face, hair, neck, torso, shoulders, arms, hands, all clothing, shirt fabric, straps, accessories, body outline, occlusion edges, contact shadows and any support area that belonged to that target')
        parts.push('Rebuild the revealed background and any visible parts of the remaining original subject naturally; the final image must contain no garment, shirt, strap or body remnant from the removed person')
        parts.push('Do not fill the removed area by enlarging the remaining person: no oversized shoulder, expanded chest, widened torso, stretched neck, new skin mass or invented anatomy; if the remaining body was not visible in the reference, use background or scene texture instead')
      }
      parts.push('no ghost outline, no leftover shadow')
      break
    case 'add_element':
      if (!targetFree && intent.additions.length > 0) {
        parts.push(`Add ${intent.additions.join(' and ')} integrated with matching perspective, scale and lighting`)
      } else if (targetFree) {
        parts.push('Integrate the requested new element naturally with matching perspective, scale and lighting')
      }
      if (additionsIntroduceStandaloneSubject(intent.additions)) {
        const allowsContact = requestAllowsContact(rawPrompt, intent.additions)
        parts.push('The requested addition must appear as a new separate visible subject, not as a modification of any existing person or object')
        parts.push(allowsContact
          ? 'The new subject is a complete second visible subject at the requested position, allowed to touch only the explicitly requested contact point'
          : 'The new subject is a complete second full-body subject standing on the ground at the requested position, separate from existing people and objects')
        parts.push('Only the new subject wears the requested clothes or accessories; existing people keep their original body, clothing, shoes, hands and pose unchanged')
        parts.push('Keep the original hose, tools, barbecue, water spray, objects and background unchanged; do not add substitute objects instead of the new subject')
      }
      break
    case 'replace_element':
      if (!targetFree) {
        for (const r of intent.replacements) {
          parts.push(`Replace ${r.from} with ${r.to}, fully integrated, the old element must not remain`)
        }
      } else {
        parts.push('Apply the requested replacement, fully integrated, the old element must not remain')
      }
      // Anti-debordement : la modification ne doit toucher QUE la cible. Sans ca,
      // un "mets le costume en rouge" teintait aussi le decor (l'encre partagee
      // d'un dessin au trait notamment). Formule positive-safe (pas de token corps).
      parts.push('Change strictly the targeted element only; every other area, object and background keeps its original colors and appearance')
      break
    case 'restyle':
      parts.push('Convert the visual style as requested while keeping the exact same composition, subjects and layout')
      break
    case 'background_change':
      parts.push('Change only the background, keep the foreground subject identical with matching light and contact shadows')
      break
    case 'color_lighting':
      parts.push('Adjust only colors and lighting, do not change shapes, content or composition')
      break
    case 'text_edit':
      parts.push('Render the requested text with crisp correct letters, change nothing else')
      break
    case 'composition_pose':
      parts.push('Apply the requested pose, position, relocation or framing with coherent perspective and shadows, preserve identity and untouched objects')
      if (RELOCATION_RE.test(rawPrompt)) {
        parts.push('For relocation, move only the requested target object; preserve its original size, shape, material, details and orientation as much as perspective allows')
        parts.push('Remove the target from its old location, reconstruct that old area naturally, and do not create any duplicate target')
      }
      break
    case 'repair_cleanup':
      parts.push('Fix defects and artifacts only, keep all content and texture authentic')
      break
    case 'upscale_detail':
      parts.push('Increase sharpness and readable detail without changing identity, pose or layout')
      break
    case 'scene_transform':
      parts.push('Transform the scene as requested but keep the main subject recognizable')
      break
    default:
      break
  }

  if (intent.editMode !== 'scene_transform' && intent.editMode !== 'restyle') {
    parts.push('Keep everything else unchanged: same identity, same composition, same camera angle, same style')
  }

  appendSecondaryOperationClauses(parts, intent, targetFree)

  return parts.join('. ')
}

function appendSecondaryOperationClauses(parts: string[], intent: ParsedImageIntent, targetFree: boolean): void {
  if (intent.editMode !== 'add_element' && intent.additions.length > 0) {
    if (targetFree) {
      parts.push('Also add the requested new element exactly as requested, integrated with matching perspective, scale, lighting and contact shadows')
    } else {
      parts.push(`Also add ${intent.additions.join(' and ')} exactly as requested, integrated with matching perspective, scale, lighting and contact shadows`)
    }
    if (hasHumanRemovalTarget(intent.removals) && additionMentionsShoulder(intent)) {
      parts.push('Because a person was removed, attach the added shoulder element to the visible remaining original subject on the requested shoulder, never on the removed person\'s former shirt, body, shoulder, shadow or leftover fabric')
      parts.push('Keep the remaining subject\'s shoulder morphology exactly at its original size; the added element must be scaled to the real shoulder, not supported by an enlarged or newly invented shoulder')
      parts.push('The added shoulder element must be readable at natural shoulder scale, not a tiny sticker, charm or distant floating detail')
    }
  }

  if (intent.editMode !== 'remove_element' && intent.removals.length > 0) {
    if (targetFree) {
      parts.push('Also remove the requested old element completely, with no ghost outline or leftover shadow')
    } else {
      parts.push(`Also remove ${intent.removals.join(' and ')} completely, with no ghost outline or leftover shadow`)
    }
  }

  if (intent.editMode !== 'replace_element' && intent.replacements.length > 0) {
    for (const replacement of intent.replacements) {
      if (targetFree) {
        parts.push('Also apply the requested replacement fully; the old element must not remain')
      } else {
        parts.push(`Also replace ${replacement.from} with ${replacement.to}; the old element must not remain`)
      }
    }
  }
}

export interface AssembleKontextInstructionInput {
  /** Demande brute de l'utilisateur (repli si la traduction a echoue). */
  rawPrompt: string
  intent: ParsedImageIntent | null | undefined
  /** Coeur d'edition deja traduit en anglais propre (kontextInstructionTranslator). */
  englishCore?: string
  /** Clause d'apparence pour une entite nommee (namedEntityEnrichment). */
  entityClause?: string
  /** Vrai quand un second visuel sert de SOURCE a injecter dans l'image de base. */
  injection?: boolean
}

/**
 * Source UNIQUE de l'instruction Kontext, partagee par l'UI et la CLI.
 *
 * CRITIQUE : le graphe Kontext n'a AUCUN canal de conditioning negatif
 * (CLIPTextEncode -> FluxGuidance -> ReferenceLatent -> BasicGuider, positif
 * uniquement). Tout mot envoye au CLIPTextEncode devient donc du guidage
 * POSITIF. Injecter ici les "contrats" de l'orchestrateur image (qui listent
 * "shoulders, chest volume, body proportions, enlarge, anatomy, torso"...) les
 * transforme en cible a RENDRE : c'est ce qui rendait le sujet plus musclé
 * lors d'un simple ajout de personnage. On garde donc l'instruction MINIMALE :
 * coeur d'edition traduit + apparence de l'entite + clauses de preservation
 * generees par buildKontextInstruction. Rien d'autre. L'UI et la CLI passent
 * exactement les memes entrees ici -> resultat identique des deux cotes.
 */
export function assembleKontextInstruction(input: AssembleKontextInstructionInput): string {
  const { rawPrompt, intent, englishCore, entityClause, injection } = input
  const clause = entityClause?.replace(/\s+/g, ' ').trim() || ''
  if (injection) {
    return buildKontextInjectionInstruction(rawPrompt, intent, { englishCore, entityClause: clause })
  }
  const base = [rawPrompt, clause].filter(Boolean).join('\n\n')
  // buildKontextInstruction utilise englishCore COMME base quand il est fourni
  // (et ignore alors `base`) : on doit donc y ranger aussi la clause d'apparence.
  const core = englishCore
    ? [englishCore, clause].filter(Boolean).join('\n\n')
    : undefined
  return buildKontextInstruction(base, intent, { englishCore: core })
}

export interface StagedReplacementInput {
  /** Sujet à RETIRER (FR brut), ex "l'homme à droite". */
  from: string
  /** Nouveau sujet + position (FR brut), ex "Happy de Fairy Tail sur l'épaule de la femme". */
  to: string
  /** Coeurs traduits EN (facultatifs). */
  removeEnglishCore?: string
  addEnglishCore?: string
  /** Clause d'apparence du nouveau sujet (issue de la recherche auto-informée). */
  entityClause?: string
}

export type StagedReplacementStageId =
  | 'remove_target'
  | 'reconstruct_support'
  | 'replace_target'
  | 'pose_expression'
  | 'change_background'
  | 'apply_style'
  | 'place_new_subject'
  | 'render_text'
  | 'verify_and_repair'

export interface StagedReplacementStage {
  id: StagedReplacementStageId
  label: string
  progressLabel: string
  instruction: string
  successCriteria: string[]
  rejectIf: string[]
}

export interface StagedReplacementPlan {
  mode: 'staged-human-removal-addition' | 'staged-kontext-edit'
  stages: StagedReplacementStage[]
  /** Instruction de la PASSE 1 : retirer le sujet + reconstruire la zone. */
  removeInstruction: string
  /** Instruction de la PASSE 2 : ajouter le nouveau sujet à la position. */
  reconstructInstruction: string
  addInstruction: string
  validationChecklist: string[]
}

/**
 * Remplacer un HUMAIN (ou gros sujet de premier plan) par un autre personnage à
 * une position précise est trop pour un seul passe Kontext (il garde l'ancien et
 * colle le nouveau en sticker, ou laisse un trou / une « grosse épaule »). On
 * DÉCOMPOSE en deux passes — c'est l'« intelligence » : (1) supprimer + reconstruire
 * proprement, (2) ajouter le nouveau sujet (fidèle, à sa position) sur l'image
 * nettoyée. Les deux instructions sont construites ici (source unique UI/CLI) ;
 * l'orchestration des 2 jobs ComfyUI est faite côté runtime.
 */
export function buildStagedReplacementPlan(input: StagedReplacementInput): StagedReplacementPlan {
  const from = (input.from || 'the subject to replace').replace(/\s+/g, ' ').trim()
  const to = (input.to || 'the new element').replace(/\s+/g, ' ').trim()

  {
    const removeCore = (input.removeEnglishCore || `Remove ${from}`).replace(/\s+/g, ' ').trim()
    const removeInstruction = [
      'PASS 1 - REMOVAL ONLY.',
      removeCore,
      'Completely erase that target person: head, face, hair, neck, torso, shoulders, arms, hands, all clothing, shirt fabric, straps, accessories, body outline, occlusion edges, contact shadows and every support area that belonged to that target.',
      'Leave no silhouette, ghost, hole, leftover garment, shirt fragment, strap, sleeve, collar, body edge or old shadow.',
      'Do not add the replacement character yet. Do not create a new shoulder, chest, torso, neck or skin mass for the remaining person in this pass.',
      'Keep the remaining original subject, phone, face, sky, camera angle, colors and framing unchanged.',
    ].join('. ')

    const reconstructInstruction = [
      'PASS 2 - RECONSTRUCTION ONLY.',
      'Using the cleaned image from pass 1, rebuild the revealed scene and the real support area before adding any new character.',
      'Continue the sky and background naturally through the removed person area, with coherent lighting, edges, grain and perspective.',
      'Reconstruct only the remaining original subject parts that are physically supported by the reference.',
      'Keep the real shoulder, neck and upper body proportions; if the original shoulder was hidden, use background or sky rather than expanding anatomy.',
      'No oversized shoulder, expanded chest, widened torso, stretched neck, new skin mass, invented body support, pasted fabric or leftover shirt.',
      'Do not add the new character yet. Preserve the remaining subject identity, face, phone, pose and composition.',
    ].join(' ')

    const addCore = (input.addEnglishCore || `Add ${to}`).replace(/\s+/g, ' ').trim()
    const clause = input.entityClause?.replace(/\s+/g, ' ').trim()
    const addInstruction = [
      addCore,
      clause,
      'PASS 3 - PLACEMENT ONLY: add the requested new subject onto the already reconstructed image.',
      'If the added subject is a cartoon / anime / animated character, render it in its ORIGINAL flat 2D cel-shaded cartoon style with clean outlines, NOT as a realistic photographic creature.',
      'Place it directly on the visible remaining original subject at the requested spot (for a shoulder request: perched on the real shoulder beside the neck), never on the removed person\'s former shirt, body, shadow or leftover fabric.',
      'Scale it to the real body part: large enough to read as a small cat or character sitting on the shoulder, not a tiny sticker, charm or distant floating detail; also not so large that it deforms or hides the face.',
      'Do NOT enlarge or invent a new shoulder, chest, torso, neck or body support to hold it, and do NOT leave it floating detached in the sky.',
      'Match the photo lighting and add a soft contact shadow where it touches the person. Keep the rest of the image unchanged.',
    ].filter(Boolean).join('. ')

    const stages: StagedReplacementStage[] = [
      {
        id: 'remove_target',
        label: 'Suppression complete',
        progressLabel: 'Passe 1/3 - suppression complete du sujet et de ses vetements...',
        instruction: removeInstruction,
        successCriteria: [
          'removed target has no visible body, clothing, shirt, straps or shadow remnants',
          'remaining subject identity, face, phone, sky and framing are preserved',
          'no new character is present yet',
        ],
        rejectIf: [
          'any shirt, strap, torso, shoulder or body outline from the removed target remains',
          'the remaining subject anatomy was enlarged to fill the gap',
          'the new character already appears during removal',
        ],
      },
      {
        id: 'reconstruct_support',
        label: 'Reconstruction morphologie et decor',
        progressLabel: 'Passe 2/3 - reconstruction naturelle du decor et du support...',
        instruction: reconstructInstruction,
        successCriteria: [
          'revealed area is continuous with sky/background and photo lighting',
          'remaining shoulder/neck/upper body are plausible and not oversized',
          'there is still no added character',
        ],
        rejectIf: [
          'oversized shoulder, expanded chest, widened torso, stretched neck or invented support',
          'leftover shirt/fabric from the removed target',
          'obvious blurry inpaint patch or pasted texture',
        ],
      },
      {
        id: 'place_new_subject',
        label: 'Placement du nouveau personnage',
        progressLabel: 'Passe 3/3 - placement coherent du nouveau personnage...',
        instruction: addInstruction,
        successCriteria: [
          'new subject is identifiable and faithful to the requested named entity',
          'new subject sits on the requested real shoulder/body part with contact shadow',
          'scale is readable and physically plausible, not tiny and not oversized',
        ],
        rejectIf: [
          'new subject is generic, wrong identity or wrong style',
          'new subject floats, sits on removed clothing/body remnants, or uses an invented shoulder',
          'remaining subject face, shoulder or composition is deformed',
        ],
      },
    ]

    return {
      mode: 'staged-human-removal-addition',
      stages,
      removeInstruction,
      reconstructInstruction,
      addInstruction,
      validationChecklist: [
        'no removed-person body, shirt, straps, accessories or shadow remnants',
        'remaining subject morphology is natural: no oversized shoulder/chest/torso/neck',
        'new character is correct, readable, shoulder-scaled and physically anchored',
        'photo identity, face, phone, sky, framing and lighting remain stable',
      ],
    }
  }

  const removeCore = (input.removeEnglishCore || `Remove ${from}`).replace(/\s+/g, ' ').trim()
  const removeInstruction = [
    'PASS 1 - REMOVAL ONLY.',
    removeCore,
    'Completely erase that subject — head, face, hair, neck, torso, shoulders, arms, hands, ALL clothing and shirt fabric, straps, accessories, body outline, occlusion edges and contact shadows. Leave no silhouette, no ghost, no hole, no leftover garment or body part.',
    'Rebuild the entire area it occupied with a seamless, photo-coherent continuation of the surrounding scene (extend the sky and background), and rebuild any overlapped part of the remaining person naturally.',
    'Keep the remaining person and the rest of the scene exactly unchanged: same identity, same pose, same framing, same colors, same shoulder size.',
  ].join('. ')

  const addCore = (input.addEnglishCore || `Add ${to}`).replace(/\s+/g, ' ').trim()
  const addParts = [addCore]
  const clause = input.entityClause?.replace(/\s+/g, ' ').trim()
  if (clause) addParts.push(clause)
  addParts.push(
    'If the added subject is a cartoon / anime / animated character, render it in its ORIGINAL flat 2D cel-shaded cartoon style with clean outlines, NOT as a realistic photographic creature.',
    'Place it directly on the remaining person at the requested spot (e.g. perched on the shoulder beside the neck), scaled to the real body part; do NOT enlarge or invent a new shoulder, and do NOT leave it floating detached in the sky.',
    'Match the photo lighting and add a soft contact shadow where it touches the person. Keep the rest of the image unchanged.',
  )
  const addInstruction = addParts.join('. ')
  return {
    mode: 'staged-human-removal-addition',
    stages: [],
    removeInstruction,
    reconstructInstruction: removeInstruction,
    addInstruction,
    validationChecklist: [],
  }
}

export function shouldUseStagedReplacementPlan(
  intent: ParsedImageIntent | null | undefined,
  options: { injection?: boolean } = {},
): boolean {
  return Boolean(
    intent?.isEditIntent
      && !options.injection
      && intent.editMode === 'remove_element'
      && intent.removals.length > 0
      && intent.additions.length > 0
      && hasHumanRemovalTarget(intent.removals),
  )
}

export interface StagedKontextEditPlanInput {
  rawPrompt: string
  intent: ParsedImageIntent
  englishCore?: string
  removeEnglishCore?: string
  addEnglishCore?: string
  entityClause?: string
}

const STAGED_BACKGROUND_RE = /\b(background|decor|d[e\u00e9]cor|fond|arri[e\u00e8]re.?plan|environment|environnement|plage|beach|city|ville|forest|foret|for[e\u00ea]t|studio|room|chambre|sky|ciel)\b/i
const STAGED_BACKGROUND_PRESERVE_RE = /\b(?:garde|garder|keep|preserve|conserve|conserver)\b.{0,140}\b(?:background|decor|d[e\u00e9]cor|fond|arri[e\u00e8]re.?plan|environment|environnement)\b|\b(?:background|decor|d[e\u00e9]cor|fond|arri[e\u00e8]re.?plan|environment|environnement)\s+(?:inchang[e\u00e9]s?|identiques?|unchanged|same)\b/i
const STAGED_STYLE_RE = /\b(pixel art|pixel-art|anime|manga|watercolor|aquarelle|oil painting|peinture|comic|bd|sketch|croquis|cinematic|photoreal|realiste|r[e\u00e9]aliste|style)\b/i
const STAGED_POSE_EXPRESSION_RE = /\b(pose|assis|assise|debout|sitting|standing|expression|emotion|[e\u00e9]motion|sourire|souriant|souriante|smile|smiling|heureux|heureuse|happy|triste|sad|col[e\u00e8]re|angry|regard|look|eyes|yeux|main|hand|bras|arm|jambe|leg|tourne|turn|orientation|d[e\u00e9]place|d[e\u00e9]placer|repositionne|repositionner|d[e\u00e9]cale|d[e\u00e9]caler|move|reposition|shift)\b/i
const STAGED_TEXT_RE = /\b(text|texte|ecris|[e\u00e9]cris|write|inscription|pancarte|panneau|sign|label|logo|message)\b/i
const STAGED_COLOR_LIGHT_RE = /\b(color|couleur|lumi[e\u00e8]re|lighting|[e\u00e9]clairage|neon|n[e\u00e9]on|contrast|contraste|saturation|exposure|exposition)\b/i
const STAGED_NON_OBJECT_REPLACEMENT_TARGET_RE = /\b(fond|background|arri[e\u00e8]re.?plan|decor|d[e\u00e9]cor|environment|environnement|style|pose|expression|emotion|[e\u00e9]motion|lumi[e\u00e8]re|lighting|[e\u00e9]clairage|couleur|color)\b/i

function normalizeForStaging(text: string): string {
  return text
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase()
}

function humanReplacementSources(intent: ParsedImageIntent): string[] {
  return actionableReplacements(intent)
    .filter((replacement) => isHumanRemovalTarget(replacement.from))
    .map((replacement) => replacement.from)
}

function actionableReplacements(intent: ParsedImageIntent) {
  return intent.replacements.filter((replacement) => !STAGED_NON_OBJECT_REPLACEMENT_TARGET_RE.test(replacement.from))
}

function stagedOperationFlags(input: StagedKontextEditPlanInput) {
  const normalized = normalizeForStaging(input.rawPrompt)
  const intent = input.intent
  const hasRemoval = intent.removals.length > 0
  const humanReplacement = humanReplacementSources(intent)
  const hasHumanStructuralRemoval = hasHumanRemovalTarget(intent.removals) || humanReplacement.length > 0
  const hasReplacement = actionableReplacements(intent).length > 0
  const hasAddition = intent.additions.length > 0
  const hasNewSubjectAddition = hasAddition && additionsIntroduceStandaloneSubject(intent.additions)
  const addOnlyNewSubject = hasNewSubjectAddition && !hasRemoval && !hasHumanStructuralRemoval && !hasReplacement
  const hasBackground = intent.editMode === 'background_change' || (STAGED_BACKGROUND_RE.test(normalized) && !STAGED_BACKGROUND_PRESERVE_RE.test(normalized))
  const hasStyle = intent.editMode === 'restyle' || (!addOnlyNewSubject && STAGED_STYLE_RE.test(normalized))
  const hasPoseExpression = intent.editMode === 'composition_pose' || (!addOnlyNewSubject && STAGED_POSE_EXPRESSION_RE.test(normalized))
  const hasText = intent.editMode === 'text_edit' || STAGED_TEXT_RE.test(normalized)
  const hasColorLight = intent.editMode === 'color_lighting' || STAGED_COLOR_LIGHT_RE.test(normalized)
  const structuralOps = [
    hasRemoval,
    hasReplacement,
    hasAddition,
    hasNewSubjectAddition,
    hasBackground,
    hasStyle,
    hasPoseExpression,
    hasText,
    hasColorLight,
  ].filter(Boolean).length
  return {
    hasRemoval,
    hasHumanStructuralRemoval,
    hasReplacement,
    hasAddition,
    hasBackground,
    hasStyle,
    hasPoseExpression,
    hasText,
    hasColorLight,
    structuralOps,
  }
}

export function shouldUseStagedKontextEditPlan(
  intent: ParsedImageIntent | null | undefined,
  options: { rawPrompt?: string; injection?: boolean } = {},
): boolean {
  if (!intent?.isEditIntent || options.injection) return false
  const flags = stagedOperationFlags({ rawPrompt: options.rawPrompt || '', intent })
  return Boolean(
    shouldUseStagedReplacementPlan(intent, options)
      || flags.hasHumanStructuralRemoval
      || flags.hasNewSubjectAddition
      || flags.structuralOps >= 2,
  )
}

function makeStage(
  id: StagedReplacementStageId,
  label: string,
  instruction: string,
  successCriteria: string[],
  rejectIf: string[],
): StagedReplacementStage {
  return {
    id,
    label,
    progressLabel: label,
    instruction,
    successCriteria,
    rejectIf,
  }
}

function finalizeStagedProgressLabels(stages: StagedReplacementStage[]): StagedReplacementStage[] {
  const total = stages.length
  return stages.map((stage, index) => ({
    ...stage,
    progressLabel: `Passe ${index + 1}/${total} - ${stage.label.toLowerCase()}...`,
  }))
}

export function buildStagedKontextEditPlan(input: StagedKontextEditPlanInput): StagedReplacementPlan {
  const { intent } = input
  const flags = stagedOperationFlags(input)
  const stages: StagedReplacementStage[] = []
  const removalTargets = [...intent.removals, ...humanReplacementSources(intent)]
    .map((item) => item.replace(/\s+/g, ' ').trim())
    .filter(Boolean)
  const effectiveReplacements = actionableReplacements(intent)
  const replacementTargets = effectiveReplacements.map((item) => `${item.from} -> ${item.to}`)
  const additionTargets = intent.additions.map((item) => item.replace(/\s+/g, ' ').trim()).filter(Boolean)
  const clause = input.entityClause?.replace(/\s+/g, ' ').trim()

  if (flags.hasRemoval || flags.hasHumanStructuralRemoval) {
    const removeCore = (input.removeEnglishCore || `Remove ${removalTargets.join(' and ') || 'the requested removed targets'} completely`).replace(/\s+/g, ' ').trim()
    stages.push(makeStage(
      'remove_target',
      'Suppression stricte des cibles',
      [
        'PASS - REMOVAL ONLY.',
        removeCore,
        'Remove only the requested old targets at this stage; do not add replacements, do not change the background, do not apply style changes, and do not change pose or expression yet.',
        flags.hasHumanStructuralRemoval
          ? 'For every removed or replaced person/character, erase the full visible target: face, head, hair, neck, torso, shoulders, arms, hands, legs if visible, all clothing, shirt fabric, straps, accessories, body outline, occlusion edges and contact shadows.'
          : 'Erase the target fully, including all visible edges, shadows, reflections and occlusion traces.',
        'Keep untouched people, faces, hands, clothing, camera angle, lighting and composition stable.',
      ].filter(Boolean).join(' '),
      [
        'all requested old targets are gone',
        'no new requested element has been added early',
        'untouched identity, pose, framing and lighting are preserved',
      ],
      [
        'old target remnants, clothing, straps, shadows or silhouettes remain',
        'a later requested addition/replacement/style/background appears too early',
        'untouched anatomy or face changed during removal',
      ],
    ))
  }

  if (flags.hasRemoval || flags.hasHumanStructuralRemoval) {
    stages.push(makeStage(
      'reconstruct_support',
      'Reconstruction naturelle du support',
      [
        'PASS - RECONSTRUCTION ONLY.',
        'Using the cleaned image from the previous pass, rebuild the revealed background, occlusion edges and real support areas naturally before applying any new creative operation.',
        'Continue the surrounding scene with coherent perspective, lighting, grain and texture.',
        flags.hasHumanStructuralRemoval
          ? 'If a removed person was hiding anatomy, reconstruct only what is physically supported by the reference; if the original body part was not visible, use background or scene texture rather than inventing oversized anatomy.'
          : 'Do not introduce new subjects while reconstructing the cleared area.',
        'No oversized shoulders, expanded chest, widened torso, stretched neck, floating support, blurry patch, pasted fabric or old clothing remnant.',
      ].filter(Boolean).join(' '),
      [
        'revealed areas are coherent with the surrounding scene',
        'support anatomy remains plausible and not invented',
        'no later operation has been applied yet',
      ],
      [
        'blurry inpaint patch or pasted texture',
        'oversized/invented body support',
        'old clothing/body/shadow remnants remain',
      ],
    ))
  }

  if (flags.hasReplacement) {
    const replacementInstruction = effectiveReplacements.length
      ? `Replace exactly these targets: ${replacementTargets.join('; ')}.`
      : 'Apply the requested replacement exactly.'
    stages.push(makeStage(
      'replace_target',
      'Remplacement cible',
      [
        'PASS - REPLACEMENT ONLY.',
        replacementInstruction,
        clause,
        'The old target must not remain as a duplicate, ghost, clothing remnant or identity remnant.',
        'Integrate the replacement with coherent perspective, scale, lighting, contact shadows and occlusion.',
        'Do not change the background, final style, text, or pose/expression unless this replacement explicitly requires it.',
      ].filter(Boolean).join(' '),
      [
        'replacement target is present and identifiable',
        'old target is fully gone',
        'scale, lighting, shadows and occlusion are coherent',
      ],
      [
        'old and new target both remain',
        'replacement is generic, wrong identity or pasted',
        'unrequested areas changed during replacement',
      ],
    ))
  }

  if (flags.hasPoseExpression) {
    stages.push(makeStage(
      'pose_expression',
      'Pose, expression et emotion',
      [
        'PASS - POSE / EXPRESSION ONLY.',
        input.englishCore || input.rawPrompt,
        'Apply only the requested pose, gaze, expression, emotion or body-language changes to the intended subjects.',
        'Preserve identity, face structure, realistic anatomy, clothing continuity, background and already completed additions/replacements.',
        'No broken hands, extra limbs, warped neck, distorted shoulder, melted face, duplicate subject or new unrequested object.',
      ].join(' '),
      [
        'requested pose/expression/emotion is readable',
        'identity and anatomy remain stable',
        'no unrelated content is changed',
      ],
      [
        'emotion/expression is missing or contradictory',
        'hands, face, shoulders, neck or limbs are deformed',
        'background or subjects drift unexpectedly',
      ],
    ))
  }

  if (flags.hasBackground) {
    stages.push(makeStage(
      'change_background',
      'Changement de decor',
      [
        'PASS - BACKGROUND / ENVIRONMENT ONLY.',
        input.englishCore || input.rawPrompt,
        'Change only the requested background, decor or environment. Keep all foreground subjects, completed replacements, additions, faces, pose and clothing anchored and unchanged.',
        'Match perspective, horizon, lighting direction, color temperature, shadows and contact edges so the foreground belongs in the new scene.',
      ].join(' '),
      [
        'requested background/decor is visible',
        'foreground subjects remain stable and anchored',
        'lighting and perspective are coherent',
      ],
      [
        'old background still dominates when a new decor was requested',
        'foreground subject changed or detached',
        'background looks like a collage or flat poster',
      ],
    ))
  }

  if (flags.hasAddition) {
    const addCore = (input.addEnglishCore || `Add ${additionTargets.join(' and ') || 'the requested new elements'}`).replace(/\s+/g, ' ').trim()
    const standaloneSubjectAddition = additionsIntroduceStandaloneSubject(additionTargets)
    const allowsContact = standaloneSubjectAddition && requestAllowsContact(input.rawPrompt, additionTargets)
    stages.push(makeStage(
      'place_new_subject',
      'Ajout et placement des nouveaux elements',
      [
        'PASS - ADDITION / PLACEMENT ONLY.',
        addCore,
        clause,
        'Add each requested new element exactly as requested, including position, relation, scale, emotion and interaction.',
        standaloneSubjectAddition
          ? 'Create the requested person/character/animal/robot as an additional separate visible subject; do not turn any existing person, clothing, shoes, hose, tool, barbecue or object into the new subject.'
          : '',
        standaloneSubjectAddition && !allowsContact
          ? 'The new subject must be a complete second full-body subject standing on the ground at the requested position, separate from the existing man and separate from the barbecue.'
          : '',
        standaloneSubjectAddition && allowsContact
          ? 'The new subject must be a complete second visible subject at the requested position and perform the explicitly requested physical contact; only that contact point may change.'
          : '',
        standaloneSubjectAddition
          ? 'Only the new subject wears the requested clothes or accessories; the existing man keeps his original black shirt, grey shorts, dark lowered pants, original footwear/legs, hands, pose and hose exactly as in the source.'
          : '',
        standaloneSubjectAddition
          ? 'The final image keeps exactly the original barbecue setup only; do not add a second barbecue, grill, tool cart or substitute object instead of the requested new subject.'
          : '',
        standaloneSubjectAddition && !allowsContact
          ? 'Place the new subject on the grass/ground with natural scale, perspective, occlusion and contact shadow; do not attach it to the existing person or to the barbecue unless explicitly requested.'
          : 'Anchor additions physically to the requested person/object/surface with contact shadows and occlusion; do not let them float or sit on removed-target remnants.',
        standaloneSubjectAddition && allowsContact
          ? 'At the requested contact point, add believable hand placement, occlusion and contact shadow while preserving the surrounding anatomy, clothing and object shape.'
          : '',
        'If the added subject is a named cartoon/anime/game character, preserve its recognizable original visual identity and style rather than replacing it with a generic creature or person.',
        'Do not enlarge or invent body parts to support additions; use the real reconstructed support.',
      ].filter(Boolean).join(' '),
      [
        'all requested additions are present and identifiable',
        'positions and interactions match the request',
        'scale, contact shadows and occlusion are plausible',
      ],
      [
        'addition is missing, tiny, generic or wrong identity',
        'addition floats or sits on removed remnants',
        'support anatomy was enlarged or invented',
      ],
    ))
  }

  if (flags.hasStyle || flags.hasColorLight) {
    stages.push(makeStage(
      'apply_style',
      'Style, couleur et lumiere',
      [
        'PASS - STYLE / COLOR / LIGHTING ONLY.',
        input.englishCore || input.rawPrompt,
        'Apply the requested final style, color palette and lighting while preserving the completed content, exact subject count, identities, placements, text and composition.',
        'Style is a hard requirement, but it must not erase requested objects, flatten anatomy, simplify named characters, or undo previous passes.',
      ].join(' '),
      [
        'requested style/color/lighting is visible',
        'all previous requested content remains present',
        'identity, placement and subject count remain stable',
      ],
      [
        'style removes or simplifies requested content',
        'identity/face/character changes unexpectedly',
        'previous stages are undone',
      ],
    ))
  }

  if (flags.hasText) {
    stages.push(makeStage(
      'render_text',
      'Texte exact',
      [
        'PASS - TEXT ONLY.',
        input.englishCore || input.rawPrompt,
        'Render only the requested text or inscription with crisp correct letters, exact spelling, readable alignment and natural perspective on the requested surface.',
        'Do not alter subjects, background, style, pose or previously completed edits except the target text surface.',
      ].join(' '),
      [
        'requested text is legible and spelled correctly',
        'text appears on the requested surface',
        'nothing else changes during text pass',
      ],
      [
        'text is gibberish, misspelled or duplicated',
        'old text remains when replacement was requested',
        'unrelated content changes during text pass',
      ],
    ))
  }

  const validationChecklist = [
    'every requested operation from the original prompt is present, not simplified or silently skipped',
    flags.hasRemoval ? 'all removed targets and their shadows/remnants are gone' : '',
    flags.hasReplacement ? 'all replacements are complete with no old/new duplicates' : '',
    flags.hasAddition ? 'all additions are identifiable, correctly scaled, placed and physically anchored' : '',
    flags.hasPoseExpression ? 'requested pose, expression and emotion are readable with coherent anatomy' : '',
    flags.hasBackground ? 'requested background/decor is visible and foreground remains anchored' : '',
    flags.hasStyle || flags.hasColorLight ? 'requested style/color/lighting is applied without undoing content' : '',
    flags.hasText ? 'requested text is exact, readable and on the right surface' : '',
    'identity, face, hands, body proportions, perspective, lighting and composition remain coherent unless explicitly changed',
  ].filter(Boolean)

  stages.push(makeStage(
    'verify_and_repair',
    'Verification finale et auto-correction',
    [
      'FINAL VERIFICATION AND REPAIR PASS.',
      `Original request: ${input.englishCore || input.rawPrompt}`,
      `Checklist: ${validationChecklist.join(' | ')}.`,
      'Inspect the current image against the checklist. If any item is missing, too simplified, physically impossible, incorrectly placed, visually generic, or inconsistent with the request, repair only that failure now.',
      'Do not restart from scratch, do not add unrelated content, do not undo successful previous passes, and do not change untouched faces/identity/composition.',
    ].join(' '),
    [
      'all checklist items are satisfied',
      'no visible artifact from intermediate passes remains',
      'final image still matches the original request exactly',
    ],
    [
      'any requested change is missing or simplified',
      'unrequested drift appears after repair',
      'old remnants, anatomy errors, floating elements, wrong style, wrong text or wrong background remain',
    ],
  ))

  const finalizedStages = finalizeStagedProgressLabels(stages)
  const removeInstruction = finalizedStages.find((stage) => stage.id === 'remove_target')?.instruction ?? finalizedStages[0]?.instruction ?? ''
  const reconstructInstruction = finalizedStages.find((stage) => stage.id === 'reconstruct_support')?.instruction ?? removeInstruction
  const addInstruction = finalizedStages.find((stage) => stage.id === 'place_new_subject')?.instruction ?? finalizedStages[finalizedStages.length - 1]?.instruction ?? ''

  return {
    mode: flags.hasHumanStructuralRemoval && flags.hasAddition ? 'staged-human-removal-addition' : 'staged-kontext-edit',
    stages: finalizedStages,
    removeInstruction,
    reconstructInstruction,
    addInstruction,
    validationChecklist,
  }
}

/**
 * Instruction d'EXTRACTION/INJECTION multi-image : prendre un element (personne,
 * objet, decor, pose...) de la SECONDE image et l'inserer dans la PREMIERE.
 *
 * Technique officielle Kontext multi-image (BFL/ComfyUI) : les deux references
 * sont accolees par ImageStitch (image de base a GAUCHE, source a DROITE) puis
 * encodees comme reference unique. Le modele comprend alors "left image" (scene
 * a editer) vs "right image" (source visuelle). On lui interdit explicitement de
 * rendre un montage cote-a-cote — sinon il recopie l'entree stitchee telle quelle.
 */
export function buildKontextInjectionInstruction(
  rawPrompt: string,
  _intent: ParsedImageIntent | null | undefined,
  options: { englishCore?: string; entityClause?: string } = {},
): string {
  const core = (options.englishCore || rawPrompt).replace(/\s+/g, ' ').trim()
  const clause = options.entityClause?.replace(/\s+/g, ' ').trim() || ''
  const parts = [
    core,
    'The left image is the scene to edit; the right image is ONLY a visual source to copy the requested element from.',
    'Match the inserted element to the left scene: same perspective, relative scale, lighting direction, color temperature, shadows and grain, so it looks naturally part of the left scene, not a pasted cut-out.',
  ]
  if (clause) parts.push(clause)
  parts.push('Keep the left scene otherwise unchanged: same main subject, same identity, same composition, same background.')
  parts.push('Output ONE single image: only the edited left scene. Never produce a side-by-side, split or collage, and never keep the right image as a separate panel.')
  return parts.join(' ')
}

export type StitchDirection = 'right' | 'down' | 'left' | 'up'

export type FluxKontextWorkflowOptions = {
  /** Instruction d'edition complete (voir buildKontextInstruction). */
  instruction: string
  /** Image source uploadee dans l'input ComfyUI (LoadImage). Image de BASE/destination. */
  referenceFilename: string
  /**
   * Seconde image (SOURCE de l'element a extraire) pour l'injection multi-image.
   * Quand fournie, les deux references sont accolees par ImageStitch avant
   * encodage : la base reste a gauche (haut), la source a droite (bas).
   */
  secondReferenceFilename?: string | null
  /** Direction d'accolage ImageStitch quand secondReferenceFilename est fourni. Defaut 'right'. */
  stitchDirection?: StitchDirection
  /** Nom du UNET kontext resolu via resolveKontextModel. */
  unetName: string
  filenamePrefix: string
  seed?: number | null
  /** 20 par defaut (template officiel). */
  steps?: number
  /** 2.5 par defaut: au-dela le modele sur-modifie, en-deca il ignore l'edit. */
  guidance?: number
  /** Canvas de sortie. Doit suivre le ratio de reference pour eviter les deformations. */
  width?: number
  height?: number
}

export function createFluxKontextWorkflow(options: FluxKontextWorkflowOptions): Record<string, unknown> {
  const {
    instruction,
    referenceFilename,
    secondReferenceFilename = null,
    stitchDirection = 'right',
    unetName,
    filenamePrefix,
    seed: seedOpt = null,
    steps = 20,
    guidance = 2.5,
    width = 1024,
    height = 1024,
  } = options
  const seed = seedOpt ?? Math.floor(Math.random() * 2 ** 32)
  const imageName = referenceFilename.replace(/\\/g, '/').split('/').pop()!
  const secondImageName = secondReferenceFilename
    ? secondReferenceFilename.replace(/\\/g, '/').split('/').pop()!
    : null

  // Multi-image : on accole base (gauche) + source (droite) par ImageStitch et
  // c'est l'image accolee qui alimente FluxKontextImageScale. Mono-image : la
  // reference de base alimente directement le scale (comportement historique).
  const scaleSource: [string, number] = secondImageName ? ['20', 0] : ['5', 0]

  const graph: Record<string, unknown> = {
    '1': {
      class_type: 'DualCLIPLoader',
      inputs: {
        clip_name1: IMAGE_T5_MODEL,
        clip_name2: IMAGE_CLIP_MODEL,
        type: 'flux',
        device: 'default',
      },
    },
    '2': {
      class_type: 'UNETLoader',
      inputs: {
        unet_name: unetName,
        weight_dtype: inferKontextWeightDtype(unetName),
      },
    },
    '3': {
      class_type: 'ModelSamplingFlux',
      inputs: {
        model: ['2', 0],
        max_shift: 1.15,
        base_shift: 0.5,
        width,
        height,
      },
    },
    '4': {
      class_type: 'VAELoader',
      inputs: { vae_name: IMAGE_VAE_MODEL },
    },
    '5': {
      class_type: 'LoadImage',
      inputs: { image: imageName, upload: 'image' },
    },
    '6': {
      class_type: 'FluxKontextImageScale',
      inputs: { image: scaleSource },
    },
    '7': {
      class_type: 'VAEEncode',
      inputs: { pixels: ['6', 0], vae: ['4', 0] },
    },
    '8': {
      class_type: 'CLIPTextEncode',
      inputs: { clip: ['1', 0], text: instruction },
    },
    '9': {
      class_type: 'FluxGuidance',
      inputs: { conditioning: ['8', 0], guidance },
    },
    '10': {
      class_type: 'ReferenceLatent',
      inputs: { conditioning: ['9', 0], latent: ['7', 0] },
    },
    '11': {
      class_type: 'EmptySD3LatentImage',
      inputs: { width, height, batch_size: 1 },
    },
    '12': {
      class_type: 'RandomNoise',
      inputs: { noise_seed: seed },
    },
    '13': {
      class_type: 'BasicScheduler',
      inputs: {
        model: ['3', 0],
        scheduler: 'simple',
        steps,
        denoise: 1.0,
      },
    },
    '14': {
      class_type: 'BasicGuider',
      inputs: { model: ['3', 0], conditioning: ['10', 0] },
    },
    '15': {
      class_type: 'KSamplerSelect',
      inputs: { sampler_name: 'euler' },
    },
    '16': {
      class_type: 'SamplerCustomAdvanced',
      inputs: {
        noise: ['12', 0],
        guider: ['14', 0],
        sampler: ['15', 0],
        sigmas: ['13', 0],
        latent_image: ['11', 0],
      },
    },
    '17': {
      class_type: 'VAEDecode',
      inputs: { samples: ['16', 0], vae: ['4', 0] },
    },
    '18': {
      class_type: 'SaveImage',
      inputs: { images: ['17', 0], filename_prefix: filenamePrefix },
    },
  }

  if (secondImageName) {
    graph['19'] = {
      class_type: 'LoadImage',
      inputs: { image: secondImageName, upload: 'image' },
    }
    graph['20'] = {
      class_type: 'ImageStitch',
      inputs: {
        image1: ['5', 0],
        image2: ['19', 0],
        direction: stitchDirection,
        match_image_size: true,
        spacing_width: 0,
        spacing_color: 'white',
      },
    }
  }

  return graph
}
