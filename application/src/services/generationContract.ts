import { ollamaChat } from '../hooks/useTauri'
import type { ModuleId } from '../types/app'
import { summarizePreparedContext, type PreparedContextFile } from '../utils/multimodalContext'

export type GenerationContract = {
  mode: 'create' | 'edit' | 'transform' | 'analyze' | 'research'
  editStrategy: 'fresh_create' | 'preserve_and_refine' | 'targeted_edit' | 'scene_transform'
  mustPreserve: string[]
  requestedChanges: string[]
  forbiddenChanges: string[]
  qualityPriorities: string[]
  colorConstraints: string[]
  spatialConstraints: string[]
  motionConstraints: string[]
  needsClarification: boolean
  clarificationQuestion: string | null
  shouldResearch: boolean
}

function uniqueStrings(values: string[]) {
  return Array.from(new Set(values.filter(Boolean)))
}

function detectEditLikePrompt(prompt: string) {
  const normalized = prompt.toLowerCase()
  return /\b(modifie|modifier|change|changer|edite|edit|retouche|retoucher|ajoute|ajouter|enleve|enlever|retire|retirer|supprime|supprimer|remove|replace|remplace|remplacer|preserve|conserve|garde|garder|color|colorie|colorer|deplace|deplacer|pose|action|mets|met|mettre|rends|rendre|fais|faire|ameliore|ameliorer|corrige|corriger|habille|coiffe|maquille|vieillis|rajeunis|agrandis|retrecis|eclaire|assombris|floute|recadre|tourne|inverse|zoom|upscale|stylise|sans le|sans la|sans les|avec un|avec une|donne.lui|donne.?lui|sur la|sur le|dans la|dans le|au dessus|en dessous|a cote|devant|derriere)\b/i.test(normalized)
}

function detectRefinementPrompt(prompt: string) {
  const normalized = prompt.toLowerCase()
  return /\b(ameliore|ameliorer|enhance|improve|upgrade|upscale|more realistic|plus realiste|plus réaliste|rendre realiste|rend realiste|quality|qualite|qualité|garde|conserve|preserve|same image|same photo|meme photo|meme image|plus net|plus detaille|plus precis|meilleure qualite|meilleure resolution|augmente la qualite|augmente la resolution|plus beau|plus propre|affine|peaufine|perfectionne|polish)\b/i.test(normalized)
}

function detectSceneTransformPrompt(prompt: string) {
  const normalized = prompt.toLowerCase()
  return /\b(change le decor|change de decor|change background|replace background|nouvelle scene|new scene|nouvel endroit|autre endroit|another place|change clothes|change outfit|change tenue|change pose|another action|autre action|met la a|place la a|place le a|place him|place her|place them|mets.?la? (a|dans|sur|devant|en)|deplace.?la? (vers|a|dans)|fond de|arriere.?plan|met.?le? dans|environnement|cadre|lieu|paysage|decor|contexte different|autre contexte|transporte|teleporte)\b/i.test(normalized)
}

function inferEditStrategy(prompt: string, files: PreparedContextFile[]) {
  const hasReference = files.some((file) => Boolean(file.imageBase64))
  if (!hasReference) {
    return 'fresh_create' as const
  }

  if (detectSceneTransformPrompt(prompt)) {
    return 'scene_transform' as const
  }

  if (detectRefinementPrompt(prompt)) {
    return 'preserve_and_refine' as const
  }

  if (detectEditLikePrompt(prompt)) {
    return 'targeted_edit' as const
  }

  return 'preserve_and_refine' as const
}

function extractConstraintMatches(prompt: string, pattern: RegExp) {
  return Array.from(new Set(
    Array.from(prompt.matchAll(pattern))
      .map((match) => match[1]?.trim())
      .filter(Boolean),
  ))
}

function inferColorConstraints(prompt: string) {
  return extractConstraintMatches(
    prompt,
    /\b(?:color(?:e|er|iser|ized)?|couleur(?:s)?|en couleur|colored?)\s+(?:de|des|du|d'|for|to|with)?\s*([^,.;\n]+)/gi,
  )
}

function inferSpatialConstraints(prompt: string) {
  return extractConstraintMatches(
    prompt,
    /\b(?:met(?:tre)?|place(?:r)?|deplace(?:r)?|positionne(?:r)?|pose)\s+([^,.;\n]+)/gi,
  )
}

function inferMotionConstraints(prompt: string) {
  return extractConstraintMatches(
    prompt,
    /\b(?:action|mouvement|movement|motion|rotation|rotat(?:e|ing)|tourne(?:r|ment)?|oscillat(?:e|ion)|gliss(?:e|er|ement)|translation|linear(?:e)?|ouvre(?:r|ment)?|ferme(?:r|ture)?|extend|retract|rig|animation|animate|charniere|hinge|articulation)\s*([^,.;\n]+)/gi,
  )
}

function hasAmbiguousMultipleReferences(files: PreparedContextFile[], prompt: string) {
  const imageCount = files.filter((file) => Boolean(file.imageBase64)).length
  if (imageCount < 2) {
    return false
  }

  return !/\b(premiere|premier|first|second|deuxieme|deuxième|both|les deux|combine|fusion|mixe|mix)\b/i.test(prompt)
}

function detectMechanicalPrompt(prompt: string) {
  const normalized = prompt.toLowerCase()
  return /\b(mecanique|mechanical|gear|engrenage|engine|moteur|robot|armature|piston|bearing|roulement|assembly|assemblage|cad|blueprint|schema technique|technical|hard surface|hard-surface|chassis|frame|suspension|transmission|belt|courroie|pulley|poulie|gearbox|reducteur|reducer|shaft|axe|cam|came|lever|levier|linkage|bielle|hinge|charniere|verin|v[eé]rin|cylinder|hydraulic|hydraulique|pneumatic|pneumatique)\b/i.test(normalized)
}

function detectCharacterReferencePrompt(prompt: string) {
  const normalized = prompt.toLowerCase()
  return /\b(personnage|character|anime|manga|hero|heros|h[eé]ros|heroine|heroïne|protagonist|waifu|villain|cosplay|cartoon|comic|bd|illustration)\b/i.test(normalized)
}

function detectPixelStylePrompt(prompt: string) {
  const normalized = prompt.toLowerCase()
  return /\b(pixel art|pixel-art|sprite|8 bit|8-bit|16 bit|16-bit|retro game|voxel)\b/i.test(normalized)
}

function detectElectricalPrompt(prompt: string) {
  const normalized = prompt.toLowerCase()
  return /\b(cable|cables|wire|wiring|wire harness|harness|faisceau|connector|connecteur|psu|alimentation|pcie|atx|sata|usb|ethernet|motherboard|carte mere|gpu|electrique|electrical|pcb|circuit|routing|cable management|bundle)\b/i.test(normalized)
}

function detectTechnicalSystemPrompt(prompt: string) {
  return detectMechanicalPrompt(prompt) || detectElectricalPrompt(prompt)
}

function inferTechnicalMotionConstraints(prompt: string) {
  const normalized = prompt.toLowerCase()
  const constraints: string[] = []

  if (/\b(belt|courroie|pulley|poulie)\b/i.test(normalized)) {
    constraints.push(
      'belt loop stays continuous and taut around aligned pulleys',
      'frame and supports stay static while the belt path and pulleys remain readable',
    )
  }

  if (/\b(gear|engrenage|gearbox|reducteur|reducer)\b/i.test(normalized)) {
    constraints.push(
      'meshing gears keep consistent contact and axle alignment',
      'gear train remains readable as rigid rotating parts, not soft bending shapes',
    )
  }

  if (/\b(verin|v[eé]rin|cylinder|hydraulic|hydraulique|pneumatic|pneumatique|actuator)\b/i.test(normalized)) {
    constraints.push(
      'rod motion stays coaxial with the cylinder body',
      'base mount stays fixed while the rod and clevis express linear travel',
    )
  }

  if (/\b(hinge|charniere|pivot|linkage|bielle|lever|levier|cam|came)\b/i.test(normalized)) {
    constraints.push(
      'pivot axes and linkage order stay readable',
      'moving links stay distinct from the fixed frame and support brackets',
    )
  }

  if (/\b(cable|cables|wire|wiring|wire harness|harness|faisceau|routing|cable management|bundle)\b/i.test(normalized)) {
    constraints.push(
      'respect cable routing, connector endpoints and plausible bend radius',
      'avoid impossible wire intersections, floating strands or disconnected terminations',
    )
  }

  return uniqueStrings(constraints)
}

function shouldRunFallbackResearch(prompt: string) {
  const normalized = prompt.toLowerCase()
  return /\b(personne|celebrite|celebrity|who is|qui est|marque|brand|entreprise|company|reference reelle|real world|existing|existant|datasheet|fiche technique|specification|connector|connecteur|bearing|roulement|moteur|engine|pcie|atx|usb|ethernet)\b/i.test(normalized)
    || detectTechnicalSystemPrompt(normalized)
}

function defaultForbiddenChanges(module: ModuleId, prompt = '') {
  const common = [
    'no subject duplication',
    'no extra limbs or broken anatomy',
    'no random text or watermark',
    'no scene teleportation unless explicitly requested',
  ]
  const isTechnicalSystem = detectTechnicalSystemPrompt(prompt)
  const isReferenceCharacter = detectCharacterReferencePrompt(prompt)
  const isPixelStyle = detectPixelStylePrompt(prompt)

  if (module === 'video') {
    return uniqueStrings([
      ...common,
      'no identity drift between frames',
      'no pose discontinuity or chaotic camera jumps',
      ...(isTechnicalSystem ? [
        'no impossible mechanical articulation',
        'no warped rigid parts or changing part count between frames',
      ] : []),
    ])
  }

  if (module === '3d') {
    return uniqueStrings([
      ...common,
      'no floating disconnected parts',
      'no cluttered background in the reconstruction reference',
      ...(isTechnicalSystem ? [
        'no melted hard-surface edges',
        'no impossible joins, misaligned symmetry or drifting proportions',
        'no broken routing, drifting connectors or merged moving subassemblies',
      ] : []),
    ])
  }

  if (module === 'image' || module === 'drawing') {
    return uniqueStrings([
      ...common,
      ...(!isPixelStyle ? ['no pixelation, mosaic artifacts or compression blocks'] : []),
      ...(isReferenceCharacter ? ['no identity drift on recognizable character traits'] : []),
      ...(isTechnicalSystem ? ['no warped hard-surface geometry or implausible routing'] : []),
    ])
  }

  return uniqueStrings([
    ...common,
    ...(isTechnicalSystem ? ['no warped hard-surface geometry or implausible routing'] : []),
  ])
}

function defaultQualityPriorities(module: ModuleId, prompt = '') {
  const isMechanical = detectMechanicalPrompt(prompt)
  const isElectrical = detectElectricalPrompt(prompt)
  const isTechnicalSystem = isMechanical || isElectrical
  const isReferenceCharacter = detectCharacterReferencePrompt(prompt)
  const isPixelStyle = detectPixelStylePrompt(prompt)
  switch (module) {
    case 'image':
    case 'drawing':
      return uniqueStrings([
        'faithful composition',
        'clear materials and lighting',
        'strict respect of explicit colors',
        ...(!isPixelStyle ? ['high-resolution clean edges', 'no blocky pixels or compression artifacts'] : []),
        ...(isReferenceCharacter ? ['recognizable character identity', 'preserved iconic traits and costume cues'] : []),
        ...(isMechanical ? ['hard-surface fidelity', 'clean edge definition', 'technical part alignment'] : []),
        ...(isElectrical ? ['clean cable routing', 'connector readability', 'plausible bundle organization'] : []),
      ])
    case 'video':
      return uniqueStrings([
        'stable motion',
        'identity continuity',
        'coherent limb placement',
        'clean temporal consistency',
        ...(isTechnicalSystem ? ['mechanical articulation continuity', 'preserved rigid-part alignment', 'no structural drift over time'] : []),
      ])
    case '3d':
      return uniqueStrings([
        'readable silhouette',
        'clean geometry',
        'reference-faithful structure',
        ...(isMechanical ? ['hard-surface edge fidelity', 'mechanical symmetry', 'assembly coherence'] : []),
        ...(isElectrical ? ['routing fidelity', 'connector separation', 'bundle readability'] : []),
        ...(isTechnicalSystem ? ['moving versus fixed part readability', 'functional layout fidelity'] : []),
      ])
    case 'code':
      return ['functional output', 'sandbox validation before confirmation', 'no placeholder code']
    case 'learning':
      return ['precise factual grounding', 'level-appropriate pedagogy', 'faithful use of attached documents']
    default:
      return ['high fidelity to the request']
  }
}

function parseContractJson(text: string): Partial<GenerationContract> | null {
  const match = text.match(/\{[\s\S]*\}/)
  if (!match) {
    return null
  }

  try {
    return JSON.parse(match[0]) as Partial<GenerationContract>
  } catch {
    return null
  }
}

function fallbackContract(module: ModuleId, prompt: string, files: PreparedContextFile[]): GenerationContract {
  const hasImageReference = files.some((file) => Boolean(file.imageBase64))
  const editStrategy = inferEditStrategy(prompt, files)
  const multipleReferenceAmbiguity = hasAmbiguousMultipleReferences(files, prompt)
  const inferredMotionConstraints = uniqueStrings([
    ...inferMotionConstraints(prompt),
    ...inferTechnicalMotionConstraints(prompt),
  ])

  return {
    mode: hasImageReference && editStrategy !== 'fresh_create' ? 'edit' : 'create',
    editStrategy,
    mustPreserve: hasImageReference
      ? ['main identity from the reference', 'camera framing unless explicitly changed', 'subject count unless explicitly changed']
      : [],
    requestedChanges: [prompt.trim()].filter(Boolean),
    forbiddenChanges: defaultForbiddenChanges(module, prompt),
    qualityPriorities: defaultQualityPriorities(module, prompt),
    colorConstraints: inferColorConstraints(prompt),
    spatialConstraints: inferSpatialConstraints(prompt),
    motionConstraints: module === 'video' || module === '3d' ? inferredMotionConstraints : [],
    needsClarification: multipleReferenceAmbiguity,
    clarificationQuestion: multipleReferenceAmbiguity
      ? 'Tu as joint plusieurs references visuelles. Laquelle doit servir de base principale pour le rendu ?'
      : null,
    shouldResearch: shouldRunFallbackResearch(prompt),
  }
}

export async function analyzeGenerationContract({
  module,
  prompt,
  model,
  files,
}: {
  module: ModuleId
  prompt: string
  model: string
  files: PreparedContextFile[]
}) {
  const images = files.flatMap((file) => file.imageBase64 ? [file.imageBase64] : [])
  const documentContext = summarizePreparedContext(files)
  const fallback = fallbackContract(module, prompt, files)

  try {
    const response = await ollamaChat(model, [
      {
        role: 'system',
        content: [
          '/no_think',
          `You are a contract extractor for the ${module} module.`,
          'Return only valid JSON with this shape:',
          '{"mode":"create|edit|transform|analyze|research","editStrategy":"fresh_create|preserve_and_refine|targeted_edit|scene_transform","mustPreserve":["..."],"requestedChanges":["..."],"forbiddenChanges":["..."],"qualityPriorities":["..."],"colorConstraints":["..."],"spatialConstraints":["..."],"motionConstraints":["..."],"needsClarification":true,"clarificationQuestion":"...","shouldResearch":false}',
          'If a reference image or document is present, distinguish strictly between what must stay unchanged and what must be edited.',
          'If the user asks for a realism upgrade on an existing image, choose editStrategy=preserve_and_refine.',
          'If the user asks to change only specific elements inside a reference, choose editStrategy=targeted_edit.',
          'If the user asks to move the subject to another place, change the whole environment or rewrite the scene, choose editStrategy=scene_transform.',
          'If the user asks for realism, prioritize believable materials, textures, anatomy, lighting and physical coherence.',
          'If explicit colors are given, they are non-negotiable.',
          'If action, placement or pose details are explicit, extract them into spatialConstraints or motionConstraints.',
          'CONTEXT UNDERSTANDING: Interpret the full user intent, not just keywords:',
          '  - "enleve le chapeau" = remove hat, inpaint hair naturally (mode=edit, editStrategy=targeted_edit, requestedChanges=["remove hat and inpaint hair"])',
          '  - "mets un fond de plage" = replace background with beach (mode=edit, editStrategy=scene_transform)',
          '  - "fais-la sourire" = change facial expression to smile (mode=edit, editStrategy=targeted_edit)',
          '  - "rends ca plus realiste" = enhance realism (mode=edit, editStrategy=preserve_and_refine)',
          '  - "sans le chapeau" = same as "enleve le chapeau"',
          '  - "avec des lunettes" = add glasses (mode=edit, editStrategy=targeted_edit)',
          'REMOVAL is a first-class edit operation: when the user says "enleve/retire/supprime/sans", the requestedChanges must specify what to remove AND that the gap should be inpainted naturally.',
          'If the request is ambiguous for a multi-subject or identity-sensitive edit, set needsClarification=true and ask one precise question IN FRENCH.',
          'IMPORTANT: For the code module, ALMOST NEVER set needsClarification=true. Instead, make the best assumption and document it in requestedChanges. Only ask for clarification if the prompt is truly incomprehensible (less than 3 words with no context).',
          'IMPORTANT: If you set needsClarification=true, the clarificationQuestion MUST be in FRENCH, MUST be specific (never "could you clarify?"), and MUST offer 2-3 concrete options.',
          'BAD clarification: "Could you please clarify what you want?" or "Pouvez-vous preciser?"',
          'GOOD clarification: "Tu veux: (1) un dashboard admin avec sidebar + routing, (2) une landing page avec sections, ou (3) une SPA avec navigation tabs?"',
          'Do not invent extra requested changes.',
        ].join('\n'),
      },
      {
        role: 'user',
        content: [
          `Prompt: ${prompt}`,
          documentContext ? `Document context:\n${documentContext}` : 'Document context: none',
        ].join('\n\n'),
        images: images.length > 0 ? images.slice(0, 4) : undefined,
      },
    ], 0.05)

    const parsed = parseContractJson(response?.message?.content || '')
    if (!parsed) {
      return fallback
    }

    return {
      mode: parsed.mode || fallback.mode,
      editStrategy: parsed.editStrategy || fallback.editStrategy,
      mustPreserve: uniqueStrings(parsed.mustPreserve?.filter(Boolean) || fallback.mustPreserve),
      requestedChanges: uniqueStrings(parsed.requestedChanges?.filter(Boolean) || fallback.requestedChanges),
      forbiddenChanges: uniqueStrings([
        ...(parsed.forbiddenChanges?.filter(Boolean) || []),
        ...fallback.forbiddenChanges,
      ]),
      qualityPriorities: uniqueStrings([
        ...(parsed.qualityPriorities?.filter(Boolean) || []),
        ...fallback.qualityPriorities,
      ]),
      colorConstraints: uniqueStrings(parsed.colorConstraints?.filter(Boolean) || fallback.colorConstraints),
      spatialConstraints: uniqueStrings(parsed.spatialConstraints?.filter(Boolean) || fallback.spatialConstraints),
      motionConstraints: uniqueStrings(parsed.motionConstraints?.filter(Boolean) || fallback.motionConstraints),
      needsClarification: parsed.needsClarification ?? fallback.needsClarification,
      clarificationQuestion: (parsed.needsClarification ?? fallback.needsClarification)
        ? parsed.clarificationQuestion || fallback.clarificationQuestion || 'Quelle partie exacte dois-je modifier en priorite ?'
        : null,
      shouldResearch: parsed.shouldResearch ?? fallback.shouldResearch,
    } satisfies GenerationContract
  } catch {
    return fallback
  }
}

export function buildGenerationContractSection(contract: GenerationContract) {
  return [
    `Execution mode: ${contract.mode}`,
    `Edit strategy: ${contract.editStrategy}`,
    contract.mustPreserve.length > 0 ? `Must preserve:\n${contract.mustPreserve.map((item) => `- ${item}`).join('\n')}` : '',
    contract.requestedChanges.length > 0 ? `Requested changes:\n${contract.requestedChanges.map((item) => `- ${item}`).join('\n')}` : '',
    contract.forbiddenChanges.length > 0 ? `Forbidden changes:\n${contract.forbiddenChanges.map((item) => `- ${item}`).join('\n')}` : '',
    contract.qualityPriorities.length > 0 ? `Quality priorities:\n${contract.qualityPriorities.map((item) => `- ${item}`).join('\n')}` : '',
    contract.colorConstraints.length > 0 ? `Color constraints:\n${contract.colorConstraints.map((item) => `- ${item}`).join('\n')}` : '',
    contract.spatialConstraints.length > 0 ? `Spatial constraints:\n${contract.spatialConstraints.map((item) => `- ${item}`).join('\n')}` : '',
    contract.motionConstraints.length > 0 ? `Motion constraints:\n${contract.motionConstraints.map((item) => `- ${item}`).join('\n')}` : '',
    contract.needsClarification && contract.clarificationQuestion ? `Clarification required: ${contract.clarificationQuestion}` : '',
  ].filter(Boolean).join('\n\n')
}
