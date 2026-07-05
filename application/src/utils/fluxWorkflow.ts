import {
  IMAGE_CLIP_MODEL,
  IMAGE_T5_MODEL,
  IMAGE_UNET_MODEL,
  IMAGE_VAE_MODEL,
} from '../config/models.ts'
import { hasHumanRemovalTarget, type ParsedImageIntent } from './imagePromptParser.ts'

export type FluxStyle =
  | 'realistic'
  | 'technical_render'
  | 'anime'
  | 'manga'
  | 'oil_painting'
  | 'watercolor'
  | 'pixel_art'
  | 'concept_art'
  | 'minimalist'
  | 'sketch'
  | 'cinematic'
  | 'comic'
  | 'cyberpunk'
  | 'fantasy'
  | 'retro'
  | 'none'

interface StyleConfig {
  promptPrefix: string
  promptSuffix: string
  guidance: number
  steps: number | null
  sampler: string
  scheduler: string
  editDenoise: number
}

const STYLE_PRESETS: Record<FluxStyle, StyleConfig> = {
  realistic: {
    promptPrefix: 'photorealistic RAW photograph, shot on Canon EOS R5, 85mm f/1.4 lens, available light, unretouched,',
    promptSuffix: ', razor sharp natural focus, genuine directional lighting with real soft shadows and hard shadow edges, true-to-life materials, subtle film grain, real lens imperfections chromatic aberration and bokeh, real human skin texture with visible pores fine lines moles and blemishes, authentic fabric weave and thread detail, realistic metal reflections with environment mapping, real glass caustics, subsurface scattering on skin and wax and leaves, micro-texture on every surface wood grain leather creases concrete roughness, natural color grading without oversaturation, ABSOLUTELY NO AI smoothing NO plastic skin NO airbrush NO uncanny valley NO waxy look NO blurry details NO oversharpening NO HDR glow, preserve exact facial features bone structure and identity, no morphing no distortion no symmetry forcing, imperfect human asymmetry is beautiful and required',
    guidance: 5.5,
    steps: 32,
    sampler: 'dpmpp_2m',
    scheduler: 'normal',
    editDenoise: 0.12,
  },
  technical_render: {
    promptPrefix: 'technical product render, engineering visualization, neutral studio lighting,',
    promptSuffix: ', precise hard-surface edges, isolated subject, faithful proportions, fixed frame and moving subassemblies clearly separated, visible connectors and routing when relevant, no decorative clutter, no cinematic bokeh, no exploded view unless explicitly requested, clean native detail, no muddy textures, no blocky pixels',
    guidance: 5.4,
    steps: 38,
    sampler: 'dpmpp_2m',
    scheduler: 'normal',
    editDenoise: 0.18,
  },
  anime: {
    promptPrefix: 'anime key visual, high quality anime illustration,',
    promptSuffix: ', on-model character fidelity, crisp linework, clean cel shading, readable costume details, expressive but controlled colors, no muddy textures, no accidental pixelation',
    guidance: 4.3,
    steps: 34,
    sampler: 'dpmpp_2m',
    scheduler: 'normal',
    editDenoise: 0.52,
  },
  manga: {
    promptPrefix: 'manga artwork, black and white manga panel,',
    promptSuffix: ', ink drawing, dramatic contrast, clean screentones',
    guidance: 4.5,
    steps: null,
    sampler: 'euler',
    scheduler: 'simple',
    editDenoise: 0.62,
  },
  oil_painting: {
    promptPrefix: 'oil painting masterpiece,',
    promptSuffix: ', rich brushstrokes, gallery quality, fine art finish',
    guidance: 4.0,
    steps: null,
    sampler: 'dpmpp_2m',
    scheduler: 'normal',
    editDenoise: 0.6,
  },
  watercolor: {
    promptPrefix: 'watercolor painting,',
    promptSuffix: ', soft washes, transparent layers, delicate paper texture',
    guidance: 3.8,
    steps: null,
    sampler: 'euler',
    scheduler: 'simple',
    editDenoise: 0.56,
  },
  pixel_art: {
    promptPrefix: 'authentic low resolution pixel art sprite, Aseprite style, indexed palette,',
    promptSuffix: ', hard square pixels, visible integer pixel grid, nearest-neighbor upscale look, no anti-aliasing, no smooth gradients, limited 16 color palette, readable silhouette at 32x32, crisp 1px outlines, retro game asset finish',
    guidance: 5.8,
    steps: 36,
    sampler: 'euler',
    scheduler: 'simple',
    editDenoise: 0.68,
  },
  concept_art: {
    promptPrefix: 'professional concept art,',
    promptSuffix: ', cinematic composition, strong lighting, production ready polish',
    guidance: 3.5,
    steps: null,
    sampler: 'dpmpp_2m',
    scheduler: 'normal',
    editDenoise: 0.58,
  },
  minimalist: {
    promptPrefix: 'minimalist design,',
    promptSuffix: ', clean shapes, negative space, refined composition',
    guidance: 3.0,
    steps: null,
    sampler: 'euler',
    scheduler: 'simple',
    editDenoise: 0.5,
  },
  sketch: {
    promptPrefix: 'pencil sketch, hand drawn,',
    promptSuffix: ', graphite texture, clean linework, readable construction',
    guidance: 4.0,
    steps: null,
    sampler: 'euler',
    scheduler: 'simple',
    editDenoise: 0.46,
  },
  cinematic: {
    promptPrefix: 'cinematic still frame, movie scene,',
    promptSuffix: ', dramatic lighting, cinematic composition, film grade finish',
    guidance: 3.5,
    steps: null,
    sampler: 'dpmpp_2m',
    scheduler: 'normal',
    editDenoise: 0.6,
  },
  comic: {
    promptPrefix: 'comic book art,',
    promptSuffix: ', bold outlines, graphic impact, readable action composition',
    guidance: 4.0,
    steps: null,
    sampler: 'euler',
    scheduler: 'simple',
    editDenoise: 0.6,
  },
  cyberpunk: {
    promptPrefix: 'cyberpunk artwork,',
    promptSuffix: ', neon atmosphere, futuristic materials, controlled density',
    guidance: 3.8,
    steps: null,
    sampler: 'dpmpp_2m',
    scheduler: 'normal',
    editDenoise: 0.64,
  },
  fantasy: {
    promptPrefix: 'fantasy artwork,',
    promptSuffix: ', epic atmosphere, magical lighting, polished world building',
    guidance: 3.8,
    steps: null,
    sampler: 'dpmpp_2m',
    scheduler: 'normal',
    editDenoise: 0.6,
  },
  retro: {
    promptPrefix: 'retro vintage style,',
    promptSuffix: ', nostalgic palette, analog finish, controlled grain',
    guidance: 3.5,
    steps: null,
    sampler: 'euler',
    scheduler: 'simple',
    editDenoise: 0.54,
  },
  none: {
    promptPrefix: '',
    promptSuffix: '',
    guidance: 3.5,
    steps: null,
    sampler: 'dpmpp_2m',
    scheduler: 'normal',
    editDenoise: 0.34,
  },
}

const GLOBAL_VISUAL_RULES = [
  'single dominant subject',
  'clean composition',
  'clear focal hierarchy',
  'coherent perspective',
  'controlled background',
  'polished finish',
  'no watermark',
  'no random text',
  'no unintended duplicated objects',
  'NEVER split the image into multiple panels or views',
  'NEVER render side-by-side left and right views on the same image',
  'NEVER generate a multi-view composite sheet',
  'NEVER show the same subject from two different angles in one image',
  'the entire frame must show ONE single continuous view of ONE subject',
  'no mirror copies',
  'no tiled character turnarounds',
]

const STYLE_QUALITY_RULES: Record<FluxStyle, string[]> = {
  realistic: [
    'real camera response, not a render',
    'physically plausible materials with correct roughness, specular highlights and contact shadows',
    'natural imperfections kept visible: pores, hair strands, dust, fabric weave, scratches and tiny asymmetries',
    'no beauty filter, no wax skin, no synthetic over-cleaning',
  ],
  technical_render: [
    'clean CAD-like silhouette without organic melting',
    'functional part separation, readable joints, fasteners, cables and connection points',
    'neutral lighting that reveals form instead of hiding geometry',
    'dimensionally plausible hard-surface construction',
  ],
  anime: [
    'clean anime key visual finish with stable line weight',
    'expressive eyes, readable hair masses, on-model face and costume',
    'controlled cel shading with crisp shadow shapes',
    'no photoreal skin pores, no muddy painterly texture',
  ],
  manga: [
    'confident ink line hierarchy',
    'clean screentone patterns, black fills and white reserves',
    'readable panel-like action without splitting the image into multiple panels',
    'no accidental color unless the prompt explicitly asks for color',
  ],
  oil_painting: [
    'visible oil paint body and brush direction',
    'layered glazing, impasto highlights and canvas grain',
    'painterly edges with clear value structure',
    'no digital airbrush flatness',
  ],
  watercolor: [
    'transparent pigment washes and natural blooms',
    'paper tooth visible through the paint',
    'soft edges mixed with a few deliberate crisp accents',
    'no plastic gradient, no vector-flat fill',
  ],
  pixel_art: [
    'authentic low resolution design language',
    'every edge follows an integer pixel grid',
    'clusters and silhouette readable at game sprite size',
    'palette ramps are deliberate, not smooth gradients',
  ],
  concept_art: [
    'production concept art with clear focal path',
    'strong value grouping, depth layering and material callouts',
    'worldbuilding details serve the subject instead of cluttering the frame',
    'finished enough to guide a production artist',
  ],
  minimalist: [
    'few elements, strong spacing, deliberate negative space',
    'simple geometry with balanced scale relationships',
    'premium editorial restraint, no decorative clutter',
    'edges and alignment stay crisp',
  ],
  sketch: [
    'visible graphite pressure variation',
    'construction lines stay intentional and readable',
    'clean contours with confident hatching',
    'handmade texture without dirty smudges',
  ],
  cinematic: [
    'motivated light source and believable shadow direction',
    'cinema still composition with foreground, midground and background depth',
    'filmic color grade, subtle grain and lens character',
    'no collage look, no trailer-poster overprocessing',
  ],
  comic: [
    'bold ink outlines and controlled halftone or cel shadows',
    'clear action silhouette and graphic impact',
    'anatomy readable in comic-book proportions',
    'no muddy painterly rendering',
  ],
  cyberpunk: [
    'neon light interacts with wet surfaces, metal and glass',
    'futuristic details stay readable instead of becoming random noise',
    'high contrast atmosphere with controlled color accents',
    'no neon soup, no illegible clutter',
  ],
  fantasy: [
    'mythic atmosphere with coherent costume, props and environment logic',
    'magic effects illuminate nearby surfaces believably',
    'clear subject hierarchy despite rich worldbuilding',
    'no random symbols, no overstuffed background',
  ],
  retro: [
    'period-accurate palette, grain, print texture or analog aging',
    'nostalgic finish without fake dirt covering the subject',
    'graphic shapes and typography-like balance without random text',
    'controlled color fade and vignette',
  ],
  none: [
    'select the strongest visual language implied by the prompt',
    'make the result feel finished, intentional and faithful to the request',
  ],
}

export function getAvailableStyles(): Array<{ id: FluxStyle; label: string }> {
  return [
    { id: 'none', label: 'Auto / Libre' },
    { id: 'realistic', label: 'Realiste / Photo' },
    { id: 'technical_render', label: 'Technique / Produit' },
    { id: 'anime', label: 'Anime' },
    { id: 'manga', label: 'Manga' },
    { id: 'cinematic', label: 'Cinematique' },
    { id: 'concept_art', label: 'Concept Art' },
    { id: 'oil_painting', label: 'Peinture a l huile' },
    { id: 'watercolor', label: 'Aquarelle' },
    { id: 'pixel_art', label: 'Pixel Art' },
    { id: 'sketch', label: 'Croquis' },
    { id: 'comic', label: 'Comic / BD' },
    { id: 'minimalist', label: 'Minimaliste' },
    { id: 'cyberpunk', label: 'Cyberpunk' },
    { id: 'fantasy', label: 'Fantasy' },
    { id: 'retro', label: 'Retro / Vintage' },
  ]
}

function normalizePrompt(prompt: string) {
  return prompt.replace(/\s+/g, ' ').trim()
}

function detectPromptTraits(prompt: string) {
  const normalized = normalizePrompt(prompt).toLowerCase()
  const wantsMonochrome = /\b(noir et blanc|black and white|monochrome|grayscale|greyscale|sans couleur)\b/i.test(normalized)
  const wantsColor = /\b(en couleur|couleur|couleurs|colorer|colorise|colorized|colorized|full color|colored|palette)\b/i.test(normalized)
  const wantsMajorRestyle = /\b(change|transform|transforme|transformer|replace|remplace|remplacer|nouvelle scene|new scene|nouvel endroit|another action|autre action|change pose|change clothes|change outfit|ajouter|enlever|remove|add)\b/i.test(normalized)
  const wantsSoftPreservation = /\b(conserve|garde|preserve|same|meme|identique|juste|simplement|ameliore|more realistic|plus realiste|plus réaliste)\b/i.test(normalized)

  const wantsPixelArt = /\b(pixel art|pixel-art|pixelart|sprite|tileset|aseprite|rpg maker|gameboy|game boy|gba|snes|nes|8 bit|8-bit|16 bit|16-bit|voxel)\b/i.test(normalized)
  const wantsAnimeCharacter = /\b(anime|manga|personnage|character|hero|heroine|villain|waifu|pokemon|digimon|cosplay)\b/i.test(normalized)
  const wantsMechanicalSubject = /\b(component|composant|piece|part|mecanique|mechanical|courroie|belt|poulie|pulley|gear|engrenage|verin|cylinder|bearing|roulement|cable|connector|connecteur|harness|faisceau)\b/i.test(normalized)
  const wantsExactReference = /\b(reference exacte|exact reference|official design|modele reel|real object|same subject|meme sujet|existing character|existing object)\b/i.test(normalized)
  const wantsFullBody = /\b(plein pied|plain pied|corps entier|full body|head[-\s]?to[-\s]?toe|entire body|figure entiere|figure enti[eè]re|des pieds a la tete|des pieds [aà] la t[eê]te)\b/i.test(normalized)

  return {
    wantsMonochrome,
    wantsColor,
    wantsMajorRestyle,
    wantsSoftPreservation,
    wantsPixelArt,
    wantsAnimeCharacter,
    wantsMechanicalSubject,
    wantsExactReference,
    wantsFullBody,
  }
}

function promptAllowsMultipleSubjects(prompt: string, editIntent?: ParsedImageIntent | null) {
  const normalized = normalizePrompt(prompt).toLowerCase()
  const requestedText = [
    normalized,
    ...(editIntent?.additions ?? []),
    ...(editIntent?.editContract.requestedTargets ?? []),
  ].join(' ').toLowerCase()

  return Boolean(
    editIntent?.editMode === 'add_element'
    || /\b(deux|duo|groupe|group|two|together|ensemble|avec lui|avec elle|a cote|beside|compagnon|compagne|friend|ami|amie|copain|copine|amical|amitie|personnage|character|mascotte|mascot|personne|someone|enlace|hug|main sur l epaule|hand on shoulder|shoulder)\b/i.test(requestedText)
  )
}

function promptRequestsSocialInteraction(prompt: string, editIntent?: ParsedImageIntent | null) {
  const requestedText = [
    normalizePrompt(prompt).toLowerCase(),
    ...(editIntent?.additions ?? []),
    ...(editIntent?.editContract.requestedTargets ?? []),
  ].join(' ').toLowerCase()

  return /\b(friend|ami|amie|copain|copine|amical|amitie|together|ensemble|a cote|beside|hug|calin|enlace|main sur|hand on|arm around|epaule|shoulder|pose ensemble|proche|close)\b/i.test(requestedText)
}

function buildReferenceEditRules(editIntent: ParsedImageIntent | null | undefined, style: FluxStyle): string[] {
  const base = [
    'reference image is the editable source, not a loose inspiration',
    'preserve the main identity, subject count, camera angle and scene layout unless the request explicitly changes them',
    'apply only the requested edits to the reference image',
    'unchanged regions stay stable, clean and coherent',
  ]

  if (!editIntent || editIntent.editMode === 'create') return base

  const modeRules: Record<string, string[]> = {
    add_element: [
      'new elements are integrated with matching perspective, scale, contact shadows and reflections',
      'do not duplicate the main subject while adding the requested detail',
    ],
    remove_element: [
      'the removed area is naturally inpainted with plausible background, texture and lighting',
      'no ghost outline, no remaining shadow, no cut-out edge, no blurry patch',
    ],
    replace_element: [
      'the replacement is fully integrated and the old element does not remain as a second version',
      'lighting, scale and material response match the reference scene',
    ],
    restyle: [
      'change the visual medium while preserving the same composition and recognizable subject',
      'style transformation is strong and intentional, not a weak filter',
    ],
    background_change: [
      'foreground subject stays preserved while the environment changes',
      'new background perspective, contact shadows and color temperature match the subject',
    ],
    color_lighting: [
      'geometry and identity remain unchanged while palette, light and mood are adjusted',
      'avoid inventing new objects while changing color or lighting',
    ],
    repair_cleanup: [
      'repair artifacts and defects while keeping authentic texture and content',
      'do not erase important details through over-smoothing',
    ],
    upscale_detail: [
      'increase readable detail and sharpness without changing identity, pose or layout',
      'micro-detail must look native, not oversharpened',
    ],
    composition_pose: [
      'apply the requested pose, expression, framing or composition with coherent anatomy',
      'protect face identity and avoid broken hands or warped limbs',
    ],
    scene_transform: [
      'larger scene changes are allowed, but key reference anchors and identity remain recognizable',
      'new scene must be one coherent continuous view',
    ],
    text_edit: [
      'text edits require crisp letters, correct placement and no random extra wording',
      'protect non-text parts of the reference while regenerating the text region',
    ],
    preserve_refine: [
      'refine quality, lighting and materials while preserving content almost exactly',
      'avoid changing clothes, face, pose, background or object count',
    ],
  }

  const pixelRules = style === 'pixel_art'
    ? ['when converting to pixel art, rebuild forms as real pixel clusters and never as a smoothed painting']
    : []
  const personRemovalRules = editIntent.editMode === 'remove_element' && hasHumanRemovalTarget(editIntent.removals)
    ? [
        'when removing a person or character, remove the whole visible target: face, body, clothing, shirt fabric, straps, accessories, shadows and contact edges',
        'do not leave garments, torso volume, shoulders, straps or fabric from the removed person behind; reconstruct the scene or remaining subject underneath naturally',
        'do not replace the removed person with enlarged anatomy from the remaining subject: no oversized shoulder, expanded chest, widened torso, stretched neck or new skin mass; use background texture when the body was not visible in the reference',
      ]
    : []

  return [
    ...base,
    `edit mode: ${editIntent.editContract.label}`,
    ...editIntent.editContract.preserveLines,
    ...personRemovalRules,
    ...editIntent.editContract.promptLines,
    ...(modeRules[editIntent.editMode] ?? []),
    ...pixelRules,
  ]
}

function buildStyledPrompt(prompt: string, style: FluxStyle, hasReferenceImage = false, editIntent?: ParsedImageIntent | null): string {
  const config = STYLE_PRESETS[style] || STYLE_PRESETS.none
  const normalizedPrompt = normalizePrompt(prompt)
  const promptTraits = detectPromptTraits(normalizedPrompt)
  const allowsMultipleSubjects = promptAllowsMultipleSubjects(normalizedPrompt, editIntent)
  const wantsSocialInteraction = promptRequestsSocialInteraction(normalizedPrompt, editIntent)
  const qualityRules = [
    'single coherent continuous image',
    'clear composition',
    'coherent perspective',
    'finished readable detail',
    'no unintended duplicated objects',
  ]
  let promptPrefix = config.promptPrefix
  let promptSuffix = config.promptSuffix

  if (allowsMultipleSubjects) {
    qualityRules.push(
      'allow every requested added element',
      'include every requested person, character or object in the same continuous scene',
      'preserve the original main subject while integrating additions',
      'matching scale, occlusion, contact shadows and lighting',
    )
  }

  if (wantsSocialInteraction) {
    qualityRules.push(
      'make the requested relationship legible through pose, spacing, gaze and natural contact',
      'relationship or emotion legible',
      'physically plausible hand, arm and shoulder placement',
    )
  }

  if (!promptTraits.wantsPixelArt) {
    qualityRules.push(
      'native high-resolution detail',
      'proportional anatomy',
      'stable face and hands',
      'sharp subject boundaries',
    )
  } else {
    qualityRules.push(
      'authentic pixel art, not a painting',
      'hard square pixels only',
      'integer-aligned pixel grid',
      'nearest-neighbor scaling',
      'limited indexed palette',
      'no anti-aliasing',
      'silhouette readable at small sprite size',
    )
  }

  qualityRules.push(...(STYLE_QUALITY_RULES[style] ?? STYLE_QUALITY_RULES.none))

  if (promptTraits.wantsAnimeCharacter || style === 'anime') {
    qualityRules.push(
      'recognizable iconic hairstyle and costume cues',
      'on-model anime face proportions',
      'clean line art with stable outlines',
      'hands, eyes and facial features stay coherent and readable',
    )
  }

  if (promptTraits.wantsMechanicalSubject || style === 'technical_render') {
    qualityRules.push(
      'respect dimensional relationships between parts',
      'fixed supports stay fixed',
      'moving or routed parts remain mechanically plausible',
      'belts stay aligned and tensioned when present',
      'connectors terminate at plausible endpoints',
    )
  }

  if (style === 'realistic') {
    qualityRules.push(
      'natural camera skin texture',
      'real fabric weave and material micro-texture',
      'physically plausible materials',
      'natural directional lighting and contact shadows',
    )
  }

  if (style === 'technical_render') {
    qualityRules.push(
      'rigid parts keep crisp boundaries and readable silhouettes',
      'moving parts and fixed supports stay visually separable',
      'mechanical systems respect plausible alignment, axes and contact relationships',
      'cables and harnesses follow plausible routing, bend radius and connector endpoints',
    )
  }

  if (style === 'manga') {
    if (promptTraits.wantsColor && !promptTraits.wantsMonochrome) {
      promptPrefix = 'manga illustration, colored manga artwork,'
      promptSuffix = ', dynamic ink lines, cel shading, vivid but controlled color palette, readable costume colors'
    } else {
      promptSuffix = ', ink drawing, dramatic contrast, clean screentones, black and white only'
    }
  }

  if (style === 'sketch') {
    if (promptTraits.wantsColor && !promptTraits.wantsMonochrome) {
      promptPrefix = 'hand drawn colored sketch,'
      promptSuffix = ', preserved linework, marker and pencil texture, readable color accents'
    } else {
      promptSuffix = ', graphite texture, preserved linework, monochrome drawing'
    }
  }

  if (promptTraits.wantsMonochrome) {
    qualityRules.push('strict black and white output')
  } else if (promptTraits.wantsColor) {
    qualityRules.push('respect every explicit color instruction from the prompt')
  }

  if (hasReferenceImage) {
    qualityRules.push(...buildReferenceEditRules(editIntent, style))
  }

  if (promptTraits.wantsExactReference) {
    qualityRules.push('favor exact subject fidelity over stylistic invention')
  }

  if (promptTraits.wantsFullBody) {
    qualityRules.push(
      'entire subject visible from head to toe',
      'feet, hands, head and full silhouette stay inside the frame',
      'camera far enough for a full-body view, no cropped limbs, no cropped top of head',
    )
  }

  const qualitySuffix = Array.from(new Set(qualityRules))
    .join(', ')
    .slice(0, 1800)

  if (style === 'none') {
    return [normalizedPrompt, qualitySuffix].filter(Boolean).join(', ')
  }

  return [promptPrefix, normalizedPrompt, qualitySuffix, promptSuffix].filter(Boolean).join(', ')
}

function inferFluxWeightDtype(unetName: string) {
  const lowerName = unetName.toLowerCase()
  if (lowerName.includes('fp8_e5m2')) {
    return 'fp8_e5m2'
  }

  if (lowerName.includes('fp8')) {
    return 'default'
  }

  return 'default'
}

export type FluxWorkflowOptions = {
  prompt: string
  width: number
  height: number
  steps: number
  filenamePrefix: string
  style?: FluxStyle
  seed?: number | null
  referenceImage?: {
    filename: string
    denoise?: number
  } | null
  negativePrompt?: string
  editIntent?: ParsedImageIntent | null
}

export function createFluxWorkflow(options: FluxWorkflowOptions): Record<string, unknown> {
  const { prompt, width, height, steps, filenamePrefix, style = 'none', seed: seedOpt = null, referenceImage = null, negativePrompt = '', editIntent = null } = options
  void negativePrompt
  const augmentedPrompt = prompt
  const seed = seedOpt ?? Math.floor(Math.random() * 2 ** 32)
  const styleConfig = STYLE_PRESETS[style] || STYLE_PRESETS.none
  const baseSteps = styleConfig.steps ?? steps
  const effectiveSteps = referenceImage && editIntent?.isEditIntent
    ? Math.max(baseSteps, steps + editIntent.editContract.stepsBoost)
    : baseSteps
  const styledPrompt = buildStyledPrompt(augmentedPrompt, style, Boolean(referenceImage), editIntent)
  const referenceDenoise = referenceImage?.denoise ?? (referenceImage ? editIntent?.editContract.denoise ?? styleConfig.editDenoise : 1.0)
  const workflow: Record<string, unknown> = {
    '1': {
      class_type: 'DualCLIPLoader',
      inputs: {
        clip_name1: IMAGE_T5_MODEL,
        clip_name2: IMAGE_CLIP_MODEL,
        type: 'flux',
      },
    },
    '2': {
      class_type: 'UNETLoader',
      inputs: {
        unet_name: IMAGE_UNET_MODEL,
        weight_dtype: inferFluxWeightDtype(IMAGE_UNET_MODEL),
      },
    },
    '3': {
      class_type: 'VAELoader',
      inputs: { vae_name: IMAGE_VAE_MODEL },
    },
    '4': {
      class_type: 'ModelSamplingFlux',
      inputs: {
        model: ['2', 0],
        max_shift: 1.15,
        base_shift: 0.5,
        width,
        height,
      },
    },
  }

  let latentNode: [string, number]
  let nextNodeId = 5

  if (referenceImage) {
    workflow[String(nextNodeId)] = {
      class_type: 'LoadImage',
      inputs: {
        image: referenceImage.filename.replace(/\\/g, '/').split('/').pop()!,
        upload: 'image',
      },
    }
    nextNodeId += 1
    workflow[String(nextNodeId)] = {
      class_type: 'ImageScale',
      inputs: {
        image: [String(nextNodeId - 1), 0],
        width,
        height,
        upscale_method: 'lanczos',
        crop: 'center',
      },
    }
    nextNodeId += 1
    workflow[String(nextNodeId)] = {
      class_type: 'VAEEncode',
      inputs: {
        pixels: [String(nextNodeId - 1), 0],
        vae: ['3', 0],
      },
    }
    latentNode = [String(nextNodeId), 0]
    nextNodeId += 1
  } else {
    workflow[String(nextNodeId)] = {
      class_type: 'EmptySD3LatentImage',
      inputs: { width, height, batch_size: 1 },
    }
    latentNode = [String(nextNodeId), 0]
    nextNodeId += 1
  }

  workflow[String(nextNodeId)] = {
    class_type: 'RandomNoise',
    inputs: { noise_seed: seed },
  }
  const noiseNode = String(nextNodeId)
  nextNodeId += 1

  workflow[String(nextNodeId)] = {
    class_type: 'BasicScheduler',
    inputs: {
      scheduler: styleConfig.scheduler,
      steps: effectiveSteps,
      denoise: referenceDenoise,
      model: ['4', 0],
    },
  }
  const sigmaNode = String(nextNodeId)
  nextNodeId += 1

  workflow[String(nextNodeId)] = {
    class_type: 'CLIPTextEncode',
    inputs: {
      clip: ['1', 0],
      text: styledPrompt,
    },
  }
  const clipTextNode = String(nextNodeId)
  nextNodeId += 1

  workflow[String(nextNodeId)] = {
    class_type: 'FluxGuidance',
    inputs: {
      conditioning: [clipTextNode, 0],
      guidance: styleConfig.guidance,
    },
  }
  const conditioningNode = String(nextNodeId)
  nextNodeId += 1

  workflow[String(nextNodeId)] = {
    class_type: 'BasicGuider',
    inputs: { model: ['4', 0], conditioning: [conditioningNode, 0] },
  }
  const guiderNode = String(nextNodeId)
  nextNodeId += 1

  workflow[String(nextNodeId)] = {
    class_type: 'KSamplerSelect',
    inputs: { sampler_name: styleConfig.sampler },
  }
  const samplerNode = String(nextNodeId)
  nextNodeId += 1

  workflow[String(nextNodeId)] = {
    class_type: 'SamplerCustomAdvanced',
    inputs: {
      noise: [noiseNode, 0],
      guider: [guiderNode, 0],
      sampler: [samplerNode, 0],
      sigmas: [sigmaNode, 0],
      latent_image: latentNode,
    },
  }
  const latentOutputNode = String(nextNodeId)
  nextNodeId += 1

  workflow[String(nextNodeId)] = {
    class_type: 'VAEDecode',
    inputs: { samples: [latentOutputNode, 0], vae: ['3', 0] },
  }
  const imageNode = String(nextNodeId)
  nextNodeId += 1

  workflow[String(nextNodeId)] = {
    class_type: 'SaveImage',
    inputs: { images: [imageNode, 0], filename_prefix: filenamePrefix },
  }

  return workflow
}
