import {
  IMAGE_CLIP_MODEL,
  IMAGE_PANO360_LORA_MODEL,
  IMAGE_T5_MODEL,
  IMAGE_UNET_MODEL,
  IMAGE_UPSCALER_MODEL,
  IMAGE_VAE_MODEL,
} from '../config/models.ts'
import { hasHumanRemovalTarget, type ParsedImageIntent } from './imagePromptParser.ts'

export type FluxStyle =
  | 'realistic'
  | 'landscape'
  | 'scene_environment'
  | 'panorama_360'
  | 'macro_8k'
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
    guidance: 4.5,
    steps: 34,
    sampler: 'euler',
    scheduler: 'simple',
    editDenoise: 0.12,
  },
  landscape: {
    promptPrefix: 'photorealistic medium-format landscape photograph, shot on Hasselblad X2D 100C, 24mm f/8 wide-angle prime lens, hyperfocal distance focus from foreground to infinity, unretouched RAW,',
    promptSuffix: ', razor-sharp foreground terrain micro-textures (rock fissures, moss, water ripples, individual leaves and grass blades), coherent midground depth and atmospheric perspective, realistic sky and volumetric clouds, physically accurate natural sunlight and shadow falloff, true-to-life water reflections and caustics, natural color grading without artificial HDR halo, edge-to-edge optical sharpness',
    guidance: 4.5,
    steps: 34,
    sampler: 'euler',
    scheduler: 'simple',
    editDenoise: 0.25,
  },
  scene_environment: {
    promptPrefix: 'photorealistic architectural and environmental scene photograph, shot on 35mm f/5.6 rectilinear prime lens, full-scene global illumination, unretouched RAW,',
    promptSuffix: ', accurate perspective geometry and vertical lines, complete foreground midground and background storytelling with zero empty zones, authentic PBR surface micro-textures (stone, brushed metal, weathered wood grain, glass reflections, fabric weave), natural bounce light, realistic ambient occlusion and contact shadows',
    guidance: 4.5,
    steps: 34,
    sampler: 'euler',
    scheduler: 'simple',
    editDenoise: 0.24,
  },
  panorama_360: {
    promptPrefix: 'ultra-wide 360 panoramic environment vista, 16mm rectilinear cinema lens, expansive horizon and deep environmental storytelling,',
    promptSuffix: ', continuous panoramic coherence across the entire frame, rich foreground and distant horizon detail, volumetric atmosphere, natural directional lighting, seamless spatial continuity',
    guidance: 4.5,
    steps: 34,
    sampler: 'euler',
    scheduler: 'simple',
    editDenoise: 0.3,
  },
  macro_8k: {
    promptPrefix: 'extreme macro photograph, 100mm f/2.8 1:1 Macro lens, focus-stacked ultra-high acuity, studio micro-lighting, unretouched RAW,',
    promptSuffix: ', sub-millimeter surface relief, crystalline facets, individual fibers, pores and micro-scratches, authentic anisotropic reflections and subsurface scattering, razor-sharp edge-to-edge clarity, zero synthetic blur',
    guidance: 4.8,
    steps: 36,
    sampler: 'euler',
    scheduler: 'simple',
    editDenoise: 0.18,
  },
  technical_render: {
    promptPrefix: 'technical product render, engineering visualization, neutral studio lighting,',
    promptSuffix: ', precise hard-surface edges, isolated subject, faithful proportions, fixed frame and moving subassemblies clearly separated, visible connectors and routing when relevant, no decorative clutter, no cinematic bokeh, no exploded view unless explicitly requested, clean native detail, no muddy textures, no blocky pixels',
    guidance: 4.8,
    steps: 34,
    sampler: 'euler',
    scheduler: 'simple',
    editDenoise: 0.18,
  },
  anime: {
    promptPrefix: 'anime key visual, high quality anime illustration,',
    promptSuffix: ', on-model character fidelity, crisp linework, clean cel shading, readable costume details, expressive but controlled colors, no muddy textures, no accidental pixelation',
    guidance: 4.3,
    steps: 30,
    sampler: 'euler',
    scheduler: 'simple',
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
    sampler: 'euler',
    scheduler: 'simple',
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
    guidance: 3.8,
    steps: null,
    sampler: 'euler',
    scheduler: 'simple',
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
    guidance: 3.8,
    steps: null,
    sampler: 'euler',
    scheduler: 'simple',
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
    sampler: 'euler',
    scheduler: 'simple',
    editDenoise: 0.64,
  },
  fantasy: {
    promptPrefix: 'fantasy artwork,',
    promptSuffix: ', epic atmosphere, magical lighting, polished world building',
    guidance: 3.8,
    steps: null,
    sampler: 'euler',
    scheduler: 'simple',
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
    guidance: 3.8,
    steps: null,
    sampler: 'euler',
    scheduler: 'simple',
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
  'no unrequested watermark or signature',
  'no unrequested lettering, text, labels, logos, captions or 3D print branding; do not copy text from reference examples unless explicitly requested',
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
    'real camera response, not a synthetic render',
    'physically plausible materials with correct roughness, specular highlights and contact shadows',
    'natural micro-imperfections kept visible across every surface in the frame',
    'no beauty filter, no plastic smoothing, no synthetic over-cleaning',
  ],
  landscape: [
    'medium-format optical clarity from immediate foreground to distant horizon',
    'physically accurate atmospheric scattering, natural sunlight and cloud volume',
    'crisp natural micro-textures on rock, foliage, bark, soil, snow and water surfaces',
    'no empty sky voids, no smeared distant mountains, no artificial oversaturation',
  ],
  scene_environment: [
    'rectilinear architectural and spatial perspective with coherent vanishing points',
    'complete foreground, midground and background environmental storytelling',
    'physically based material response on stone, wood, glass, metal and textiles',
    'natural global illumination, bounce light and realistic ambient occlusion',
  ],
  panorama_360: [
    'expansive ultra-wide panoramic field of view with continuous horizon line',
    'deep spatial layering from foreground anchors to far distance',
    'coherent directional lighting across the entire panoramic sweep',
  ],
  macro_8k: [
    'focus-stacked 1:1 macro acuity with sub-millimeter surface relief',
    'individual fibers, crystalline facets, micro-pores and anisotropic reflections clearly resolved',
    'physically accurate subsurface scattering and micro-shadows',
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
    { id: 'none', label: 'Auto / Libre (FLUX.2)' },
    { id: 'realistic', label: 'Réaliste / Photo RAW' },
    { id: 'landscape', label: 'Paysage & Nature Photoréaliste' },
    { id: 'scene_environment', label: 'Scène & Architecture Réaliste' },
    { id: 'panorama_360', label: 'Panorama Grand Angle 360°' },
    { id: 'macro_8k', label: 'Macro & Texture Pure 8K' },
    { id: 'cinematic', label: 'Cinématique Film 65mm' },
    { id: 'technical_render', label: 'Technique / Produit CAO' },
    { id: 'concept_art', label: 'Concept Art & Monde' },
    { id: 'anime', label: 'Anime' },
    { id: 'manga', label: 'Manga' },
    { id: 'oil_painting', label: 'Peinture à l’huile' },
    { id: 'watercolor', label: 'Aquarelle' },
    { id: 'pixel_art', label: 'Pixel Art' },
    { id: 'sketch', label: 'Croquis' },
    { id: 'comic', label: 'Comic / BD' },
    { id: 'minimalist', label: 'Minimaliste' },
    { id: 'cyberpunk', label: 'Cyberpunk' },
    { id: 'fantasy', label: 'Fantasy' },
    { id: 'retro', label: 'Rétro / Vintage' },
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
  const wantsLandscapeOrScene = /\b(paysage|landscape|montagne|mountain|foret|forêt|forest|ocean|océan|mer|sea|plage|beach|lac|lake|riviere|rivière|river|vallee|vallée|valley|desert|désert|canyon| cascade|waterfall|ville|city|cityscape|rue|ruelle|street|architecture|batiment|bâtiment|interieur|intérieur|interior|piece|chambre|salon|temple|chateau|château|castle|panorama|horizon|nature|campagne|jardin|garden|ciel|sky|aurore|sunset|sunrise|coucher de soleil)\b/i.test(normalized)
  const wantsHumanSubject = /\b(homme|femme|personne|personnage|portrait|visage|garcon|garçon|fille|enfant|guerrier|guerriere|man|woman|person|character|face|boy|girl|child|human|people|crowd)\b/i.test(normalized)

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
    wantsLandscapeOrScene,
    wantsHumanSubject,
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
    'finished readable detail across the entire frame',
    'no unintended duplicated objects',
  ]
  let promptPrefix = config.promptPrefix
  let promptSuffix = config.promptSuffix

  // Adaptation intelligente du mode Réaliste selon qu'il s'agit d'un paysage/scène, d'un objet ou d'un portrait
  if (style === 'realistic') {
    if (promptTraits.wantsLandscapeOrScene && !promptTraits.wantsHumanSubject) {
      promptPrefix = STYLE_PRESETS.landscape.promptPrefix
      promptSuffix = STYLE_PRESETS.landscape.promptSuffix
    } else if (promptTraits.wantsMechanicalSubject && !promptTraits.wantsHumanSubject) {
      promptPrefix = 'photorealistic medium-format RAW photograph, shot on Hasselblad X2D 100C, 50mm f/5.6 prime lens, natural studio or location lighting, unretouched,'
      promptSuffix = ', razor-sharp focus across the subject and environment, authentic physical materials (anodized metal, brushed steel, carbon fiber, glass caustics, rubber, wood grain), realistic reflections and contact shadows, zero plastic smoothing'
    }
  }

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
      'sharp boundaries and rich background depth',
    )
    if (promptTraits.wantsHumanSubject) {
      qualityRules.push('proportional anatomy', 'stable face and hands')
    }
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
    if (promptTraits.wantsHumanSubject) {
      qualityRules.push(
        'natural camera skin texture with pores and fine lines',
        'real fabric weave and material micro-texture',
      )
    } else if (promptTraits.wantsLandscapeOrScene) {
      qualityRules.push(
        'hyperfocal optical sharpness from foreground to distant horizon',
        'realistic atmospheric depth, foliage, water, stone and architectural micro-textures',
      )
    }
    qualityRules.push(
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
  referenceImage2?: {
    filename: string
  } | null
  negativePrompt?: string
  editIntent?: ParsedImageIntent | null
  upscaleTargetMaxEdge?: number | null
}

/**
 * Graphe unifié FLUX.2-dev haute précision :
 * - Modèle UNet : flux2-dev-Q4_K_M.gguf (20 Go)
 * - Encodeur texte : mistral_3_small_flux2_fp8.safetensors (18 Go, type: flux2)
 * - VAE : flux2-vae.safetensors
 * - Conditionnement de référence natif FLUX.2 via ReferenceLatent (1 ou 2 images)
 * - Guidage négatif réel via CFGGuider ou Flux2Scheduler
 * - Super-résolution neuronale optionnelle RealESRGAN_x4plus.pth (4K / 8K)
 */
export function createFluxWorkflow(options: FluxWorkflowOptions): Record<string, unknown> {
  const {
    prompt,
    width,
    height,
    steps,
    filenamePrefix,
    style = 'none',
    seed: seedOpt = null,
    referenceImage = null,
    referenceImage2 = null,
    negativePrompt = '',
    editIntent = null,
    upscaleTargetMaxEdge = null,
  } = options
  void IMAGE_CLIP_MODEL
  void IMAGE_PANO360_LORA_MODEL

  const augmentedPrompt = prompt
  const seed = seedOpt ?? Math.floor(Math.random() * 2 ** 32)
  const styleConfig = STYLE_PRESETS[style] || STYLE_PRESETS.none
  const baseSteps = styleConfig.steps ?? steps
  const effectiveSteps = referenceImage && editIntent?.isEditIntent
    ? Math.max(baseSteps, steps + editIntent.editContract.stepsBoost)
    : baseSteps
  const styledPrompt = buildStyledPrompt(augmentedPrompt, style, Boolean(referenceImage), editIntent)
  const referenceDenoise = referenceImage?.denoise ?? (referenceImage ? editIntent?.editContract.denoise ?? styleConfig.editDenoise : 1.0)
  const effectiveNegative = (negativePrompt || '').trim() ||
    'blurry, low detail, out of focus, plastic skin, airbrushed, waxy, deformed anatomy, extra fingers, mutated hands, watermark, signature, text overlay, split screen, multi-panel'

  const workflow: Record<string, unknown> = {
    '1': {
      class_type: 'CLIPLoader',
      inputs: {
        clip_name: IMAGE_T5_MODEL,
        type: 'flux2',
        device: 'cpu',
      },
    },
    '2': IMAGE_UNET_MODEL.toLowerCase().endsWith('.gguf')
      ? { class_type: 'UnetLoaderGGUF', inputs: { unet_name: IMAGE_UNET_MODEL } }
      : {
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
  let refLatentNode: [string, number] | null = null
  let refLatentNode2: [string, number] | null = null
  let nextNodeId = 5

  if (referenceImage) {
    const cleanRefName = referenceImage.filename.replace(/\\/g, '/').split('/').pop()!
    const loadId = String(nextNodeId++)
    workflow[loadId] = {
      class_type: 'LoadImage',
      inputs: { image: cleanRefName, upload: 'image' },
    }
    const scaleId = String(nextNodeId++)
    workflow[scaleId] = {
      class_type: 'ImageScale',
      inputs: {
        image: [loadId, 0],
        width,
        height,
        upscale_method: 'lanczos',
        crop: 'center',
      },
    }
    const encodeId = String(nextNodeId++)
    workflow[encodeId] = {
      class_type: 'VAEEncode',
      inputs: {
        pixels: [scaleId, 0],
        vae: ['3', 0],
      },
    }
    refLatentNode = [encodeId, 0]

    // Si denoise < 0.88 (retouche locale ou conservation stricte de la structure),
    // on part du latent de l'image de référence ; sinon on part d'un latent FLUX.2
    // vierge guidé par ReferenceLatent (reproduction / nouvelle pose / nouvelle scène).
    if (referenceDenoise < 0.88) {
      latentNode = [encodeId, 0]
    } else {
      const emptyId = String(nextNodeId++)
      workflow[emptyId] = {
        class_type: 'EmptyFlux2LatentImage',
        inputs: { width, height, batch_size: 1 },
      }
      latentNode = [emptyId, 0]
    }
  } else {
    const emptyId = String(nextNodeId++)
    workflow[emptyId] = {
      class_type: 'EmptyFlux2LatentImage',
      inputs: { width, height, batch_size: 1 },
    }
    latentNode = [emptyId, 0]
  }

  if (referenceImage2?.filename) {
    const cleanRef2 = referenceImage2.filename.replace(/\\/g, '/').split('/').pop()!
    const load2Id = String(nextNodeId++)
    workflow[load2Id] = {
      class_type: 'LoadImage',
      inputs: { image: cleanRef2, upload: 'image' },
    }
    const scale2Id = String(nextNodeId++)
    workflow[scale2Id] = {
      class_type: 'ImageScale',
      inputs: {
        image: [load2Id, 0],
        width,
        height,
        upscale_method: 'lanczos',
        crop: 'center',
      },
    }
    const encode2Id = String(nextNodeId++)
    workflow[encode2Id] = {
      class_type: 'VAEEncode',
      inputs: {
        pixels: [scale2Id, 0],
        vae: ['3', 0],
      },
    }
    refLatentNode2 = [encode2Id, 0]
  }

  const noiseNode = String(nextNodeId++)
  workflow[noiseNode] = {
    class_type: 'RandomNoise',
    inputs: { noise_seed: seed },
  }

  const sigmaNode = String(nextNodeId++)
  if (referenceImage && referenceDenoise < 0.88) {
    workflow[sigmaNode] = {
      class_type: 'BasicScheduler',
      inputs: {
        scheduler: styleConfig.scheduler,
        steps: effectiveSteps,
        denoise: referenceDenoise,
        model: ['4', 0],
      },
    }
  } else {
    workflow[sigmaNode] = {
      class_type: 'Flux2Scheduler',
      inputs: {
        steps: effectiveSteps,
        width,
        height,
      },
    }
  }

  const posTextNode = String(nextNodeId++)
  workflow[posTextNode] = {
    class_type: 'CLIPTextEncode',
    inputs: {
      clip: ['1', 0],
      text: styledPrompt,
    },
  }

  const negTextNode = String(nextNodeId++)
  workflow[negTextNode] = {
    class_type: 'CLIPTextEncode',
    inputs: {
      clip: ['1', 0],
      text: effectiveNegative,
    },
  }

  let positiveCond: [string, number] = [posTextNode, 0]
  let negativeCond: [string, number] = [negTextNode, 0]

  // Conditionnement ReferenceLatent natif FLUX.2 (verrouille l'identité et les détails de référence)
  if (refLatentNode) {
    const refPosId = String(nextNodeId++)
    workflow[refPosId] = {
      class_type: 'ReferenceLatent',
      inputs: { conditioning: positiveCond, latent: refLatentNode },
    }
    const refNegId = String(nextNodeId++)
    workflow[refNegId] = {
      class_type: 'ReferenceLatent',
      inputs: { conditioning: negativeCond, latent: refLatentNode },
    }
    positiveCond = [refPosId, 0]
    negativeCond = [refNegId, 0]
  }

  if (refLatentNode2) {
    const ref2PosId = String(nextNodeId++)
    workflow[ref2PosId] = {
      class_type: 'ReferenceLatent',
      inputs: { conditioning: positiveCond, latent: refLatentNode2 },
    }
    const ref2NegId = String(nextNodeId++)
    workflow[ref2NegId] = {
      class_type: 'ReferenceLatent',
      inputs: { conditioning: negativeCond, latent: refLatentNode2 },
    }
    positiveCond = [ref2PosId, 0]
    negativeCond = [ref2NegId, 0]
  }

  const guiderNode = String(nextNodeId++)
  workflow[guiderNode] = {
    class_type: 'CFGGuider',
    inputs: {
      model: ['4', 0],
      positive: positiveCond,
      negative: negativeCond,
      cfg: styleConfig.guidance,
    },
  }

  const samplerNode = String(nextNodeId++)
  workflow[samplerNode] = {
    class_type: 'KSamplerSelect',
    inputs: { sampler_name: styleConfig.sampler },
  }

  const latentOutputNode = String(nextNodeId++)
  workflow[latentOutputNode] = {
    class_type: 'SamplerCustomAdvanced',
    inputs: {
      noise: [noiseNode, 0],
      guider: [guiderNode, 0],
      sampler: [samplerNode, 0],
      sigmas: [sigmaNode, 0],
      latent_image: latentNode,
    },
  }

  const decodedImageNode = String(nextNodeId++)
  workflow[decodedImageNode] = {
    class_type: 'VAEDecode',
    inputs: { samples: [latentOutputNode, 0], vae: ['3', 0] },
  }

  let finalImageOutputNode = decodedImageNode

  // Super-résolution neuronale RealESRGAN_x4plus intégrée au graphe FLUX.2 (4K / 8K)
  if (upscaleTargetMaxEdge && upscaleTargetMaxEdge > Math.max(width, height)) {
    const scaleRatio = upscaleTargetMaxEdge / Math.max(width, height)
    const outW = Math.max(64, Math.round((width * scaleRatio) / 8) * 8)
    const outH = Math.max(64, Math.round((height * scaleRatio) / 8) * 8)
    const upscaleLoaderNode = String(nextNodeId++)
    workflow[upscaleLoaderNode] = {
      class_type: 'UpscaleModelLoader',
      inputs: { model_name: IMAGE_UPSCALER_MODEL },
    }
    const upscaledNode = String(nextNodeId++)
    workflow[upscaledNode] = {
      class_type: 'ImageUpscaleWithModel',
      inputs: { upscale_model: [upscaleLoaderNode, 0], image: [decodedImageNode, 0] },
    }
    const scaledNode = String(nextNodeId++)
    workflow[scaledNode] = {
      class_type: 'ImageScale',
      inputs: {
        image: [upscaledNode, 0],
        upscale_method: 'lanczos',
        width: outW,
        height: outH,
        crop: 'disabled',
      },
    }
    finalImageOutputNode = scaledNode
  }

  const saveNode = String(nextNodeId++)
  workflow[saveNode] = {
    class_type: 'SaveImage',
    inputs: { images: [finalImageOutputNode, 0], filename_prefix: filenamePrefix },
  }

  return workflow
}

export interface Flux2WorkflowOptions {
  prompt: string
  width: number
  height: number
  steps: number
  filenamePrefix: string
  seed?: number | null
  referenceImageFilename?: string
  negativePrompt?: string
}

/**
 * Graphe FLUX.2-dev (encodeur Mistral-3, Flux2Scheduler + SamplerCustomAdvanced).
 * Copie EXACTE du graphe backend flux_reference_synth.build_workflow, valide
 * end-to-end. L'ancien graphe FLUX.1 (DualCLIPLoader t5xxl+clip_l) casse sur ce
 * torch avec "Could not find schema for aten::matmul" au CLIPTextEncode — les
 * chemins 3D passent donc par FLUX.2, qui est aussi le maximum de qualite.
 */
export function createFlux2Workflow(options: Flux2WorkflowOptions): Record<string, unknown> {
  const {
    prompt, width, height, steps, filenamePrefix,
    seed: seedOpt = null, referenceImageFilename,
    negativePrompt = 'cropped, cut off, out of frame, partial view, close-up, truncated body, missing limbs, blurry, low detail',
  } = options
  const seed = seedOpt ?? Math.floor(Math.random() * 2 ** 32)
  const workflow: Record<string, unknown> = {
    // Modeles depuis la configuration — JAMAIS de nom en dur: ce graphe
    // demandait encore 'flux2_dev_fp8mixed' (le fichier tronque supprime) via
    // UNETLoader, alors que le poids reel est un .gguf que seul
    // UnetLoaderGGUF sait charger -> 400 "value_not_in_list" et generation
    // morte sans reference. Miroir exact du graphe Python (flux_reference_synth).
    '11': { class_type: 'CLIPLoader', inputs: { clip_name: IMAGE_T5_MODEL, type: 'flux2', device: 'cpu' } },
    '12': IMAGE_UNET_MODEL.toLowerCase().endsWith('.gguf')
      ? { class_type: 'UnetLoaderGGUF', inputs: { unet_name: IMAGE_UNET_MODEL } }
      : { class_type: 'UNETLoader', inputs: { unet_name: IMAGE_UNET_MODEL, weight_dtype: 'default' } },
    '10': { class_type: 'VAELoader', inputs: { vae_name: IMAGE_VAE_MODEL } },
    '6': { class_type: 'CLIPTextEncode', inputs: { clip: ['11', 0], text: prompt } },
    '33': { class_type: 'CLIPTextEncode', inputs: { clip: ['11', 0], text: negativePrompt } },
    '27': { class_type: 'EmptyFlux2LatentImage', inputs: { width, height, batch_size: 1 } },
    '40': { class_type: 'Flux2Scheduler', inputs: { steps, width, height } },
    '41': { class_type: 'KSamplerSelect', inputs: { sampler_name: 'euler' } },
    '26': { class_type: 'CFGGuider', inputs: { model: ['12', 0], positive: ['6', 0], negative: ['33', 0], cfg: 5.0 } },
    '42': { class_type: 'RandomNoise', inputs: { noise_seed: seed } },
    '31': { class_type: 'SamplerCustomAdvanced', inputs: { noise: ['42', 0], guider: ['26', 0], sampler: ['41', 0], sigmas: ['40', 0], latent_image: ['27', 0] } },
    '8': { class_type: 'VAEDecode', inputs: { samples: ['31', 0], vae: ['10', 0] } },
    '9': { class_type: 'SaveImage', inputs: { images: ['8', 0], filename_prefix: filenamePrefix } },
  }
  if (referenceImageFilename) {
    workflow['55'] = { class_type: 'LoadImage', inputs: { image: referenceImageFilename.replaceAll(String.fromCharCode(92), '/').split('/').pop()! } }
    workflow['59'] = { class_type: 'ImageScaleToTotalPixels', inputs: { image: ['55', 0], upscale_method: 'lanczos', megapixels: Math.min(1.5, width * height / 1000000), resolution_steps: 1 } }
    workflow['56'] = { class_type: 'VAEEncode', inputs: { pixels: ['59', 0], vae: ['10', 0] } }
    workflow['57'] = { class_type: 'ReferenceLatent', inputs: { conditioning: ['6', 0], latent: ['56', 0] } }
    workflow['58'] = { class_type: 'ReferenceLatent', inputs: { conditioning: ['33', 0], latent: ['56', 0] } }
    workflow['26'] = { class_type: 'CFGGuider', inputs: { model: ['12', 0], positive: ['57', 0], negative: ['58', 0], cfg: 5.0 } }
  }
  return workflow

}
