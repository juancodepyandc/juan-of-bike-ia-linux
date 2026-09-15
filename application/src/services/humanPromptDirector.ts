/**
 * AuroraIA Human Prompt Director & Intent Intelligence System
 * 
 * Transforms raw user requests into rich, evocative, natural language Art Director prompts.
 * Eliminates robotic keyword soup ("masterpiece, 8k, highly detailed, trending on artstation")
 * in favor of cohesive photographic, artistic, and game-development prose.
 */

export type ImageIntentCategory =
  | 'photo_realistic'
  | 'game_asset_pixel_art'
  | 'game_asset_isometric'
  | 'game_asset_icon_ui'
  | 'game_asset_texture'
  | 'game_asset_3d_prop'
  | 'stylized_pixar_3d'
  | 'stylized_anime_ghibli'
  | 'stylized_manga_ink'
  | 'stylized_cyberpunk'
  | 'stylized_oil_painting'
  | 'stylized_watercolor'
  | 'concept_art_production'
  | 'creative_custom'

export type HumanPromptResult = {
  category: ImageIntentCategory
  title: string
  humanPrompt: string
  negativePrompt: string
  aspectRatio: '1:1' | '16:9' | '9:16' | '4:3' | '3:2' | '2:3' | '21:9'
  width: number
  height: number
  steps: number
  guidance: number
  gameAssetMeta?: {
    assetType: 'sprite' | 'isometric_building' | 'ui_icon' | 'tileable_texture' | 'item_prop'
    isolatedBackground: boolean
    gridSize?: number
    pixelScale?: number
  }
  suggestedDirectory: string
  qualityChecklist: string[]
}

const CATEGORY_RESOLUTIONS: Record<string, { width: number; height: number; ar: HumanPromptResult['aspectRatio'] }> = {
  square: { width: 1024, height: 1024, ar: '1:1' },
  landscape: { width: 1216, height: 832, ar: '3:2' },
  wide_landscape: { width: 1344, height: 768, ar: '16:9' },
  cinemascope: { width: 1536, height: 640, ar: '21:9' },
  portrait: { width: 832, height: 1216, ar: '2:3' },
  vertical_story: { width: 768, height: 1344, ar: '9:16' },
  standard_photo: { width: 1152, height: 896, ar: '4:3' },
}

/**
 * Detect the exact intent category from natural language user input.
 */
export function detectIntentCategory(rawText: string): ImageIntentCategory {
  const text = rawText.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')

  // 1. Game Assets
  if (/\b(pixel art|pixelart|pixel-art|sprite|spritesheet|tileset|8.?bit|16.?bit|aseprite|rpg maker|gameboy|snes|nes)\b/.test(text)) {
    return 'game_asset_pixel_art'
  }
  if (/\b(isometrique|isometric|iso prop|iso building|diorama|simcity|diablo view)\b/.test(text)) {
    return 'game_asset_isometric'
  }
  if (/\b(icone|icon|item|potion|inventory|loot|competence|skill icon|hud|ui asset|inventaire|badge)\b/.test(text)) {
    return 'game_asset_icon_ui'
  }
  if (/\b(seamless|tileable|motif repetable|sol carrelage|pbr texture|albedo map|texture de sol|texture de mur)\b/.test(text)) {
    return 'game_asset_texture'
  }
  if (/\b(texture)\b/.test(text) && !/\b(texture de peau|skin texture|texture du visage|texture des cheveux)\b/.test(text) && /\b(sol|mur|pave|pierre|bois|metal|pbr|seamless|tile)\b/.test(text)) {
    return 'game_asset_texture'
  }
  if (/\b(asset 3d|game prop|low poly prop|game asset|asset jeu|modele pour jeu)\b/.test(text)) {
    return 'game_asset_3d_prop'
  }

  // 2. Stylized & Animation
  if (/\b(pixar|disney|animation 3d|dreamworks|personnage 3d stylise|caricature 3d)\b/.test(text)) {
    return 'stylized_pixar_3d'
  }
  if (/\b(anime|ghibli|shinkai|makoto|cel.?shad|cleankey|japonais animation|dessin anime)\b/.test(text)) {
    return 'stylized_anime_ghibli'
  }
  if (/\b(manga|noir et blanc|encre|screentone|trame|planche manga|shonen|seinen)\b/.test(text)) {
    return 'stylized_manga_ink'
  }
  if (/\b(cyberpunk|neon noir|futuriste neon|blade runner|synthwave)\b/.test(text)) {
    return 'stylized_cyberpunk'
  }
  if (/\b(huile|oil painting|peinture a l huile|toile de maitre|caravaggio|rembrandt)\b/.test(text)) {
    return 'stylized_oil_painting'
  }
  if (/\b(aquarelle|watercolor|lavis|papier grain)\b/.test(text)) {
    return 'stylized_watercolor'
  }
  if (/\b(concept art|matte painting|production art|decor epique|cle visual)\b/.test(text)) {
    return 'concept_art_production'
  }

  // 3. Photo-Realistic
  if (/\b(photo|photographie|photorealiste|realiste|portrait|85mm|canon|nikon|sony|raw photo|documentaire|street photography|argentique)\b/.test(text)) {
    return 'photo_realistic'
  }

  return 'photo_realistic'
}

/**
 * Human-like Art Director prompt synthesis.
 */
export function directHumanPrompt(rawInput: string): HumanPromptResult {
  const category = detectIntentCategory(rawInput)
  const cleanInput = rawInput.trim().replace(/^[\s,;.-]+|[\s,;.-]+$/g, '')

  switch (category) {
    case 'photo_realistic':
      return buildPhotorealisticPrompt(cleanInput)
    case 'game_asset_pixel_art':
      return buildPixelArtPrompt(cleanInput)
    case 'game_asset_isometric':
      return buildIsometricAssetPrompt(cleanInput)
    case 'game_asset_icon_ui':
      return buildGameIconPrompt(cleanInput)
    case 'game_asset_texture':
      return buildTileableTexturePrompt(cleanInput)
    case 'game_asset_3d_prop':
      return buildGamePropPrompt(cleanInput)
    case 'stylized_pixar_3d':
      return buildPixar3DPrompt(cleanInput)
    case 'stylized_anime_ghibli':
      return buildAnimeGhibliPrompt(cleanInput)
    case 'stylized_manga_ink':
      return buildMangaInkPrompt(cleanInput)
    case 'stylized_cyberpunk':
      return buildCyberpunkPrompt(cleanInput)
    case 'stylized_oil_painting':
      return buildOilPaintingPrompt(cleanInput)
    case 'stylized_watercolor':
      return buildWatercolorPrompt(cleanInput)
    case 'concept_art_production':
      return buildConceptArtPrompt(cleanInput)
    default:
      return buildPhotorealisticPrompt(cleanInput)
  }
}

function buildPhotorealisticPrompt(subject: string): HumanPromptResult {
  const isPortrait = /\b(portrait|visage|femme|homme|personne|regard|fille|garcon|ingenieure?|artisan|docteur|modele|chef)\b/i.test(subject)
  const isLandscape = /\b(paysage|montagne|foret|mer|plage|ciel|horizon|ville|rue)\b/i.test(subject)

  const res = isPortrait
    ? CATEGORY_RESOLUTIONS.portrait
    : isLandscape
    ? CATEGORY_RESOLUTIONS.landscape
    : CATEGORY_RESOLUTIONS.square

  const prompt = isPortrait
    ? `An authentic editorial documentary portrait of ${subject}. Natural daylight illumination with soft directional shadows that accentuate real skin texture, fine pores, subtle natural imperfections, and expressive eyes with clear corneal reflections. Captured on an 85mm prime lens at f/2.0 with a gentle shallow depth of field, delicate optical bokeh in the background, and true-to-life color fidelity. No artificial airbrushing, no plastic skin smoothing, genuine human presence.`
    : `A genuine documentary-grade photograph capturing ${subject}. Natural atmospheric lighting with believable specular highlights, authentic surface textures, and physical contact shadows. Shot with professional 35mm optical glass, capturing realistic depth, tactile material micro-textures, and organic tonal gradients without oversaturation or synthetic HDR effects.`

  return {
    category: 'photo_realistic',
    title: `Photographie Réaliste - ${subject.slice(0, 32)}`,
    humanPrompt: prompt,
    negativePrompt: 'plastic skin, airbrushed, cartoon, 3d render, CGI, doll face, fake smooth texture, oversaturated, unnatural glow, extra limbs, deformed anatomy, blurry, low resolution, watermark, signature',
    aspectRatio: res.ar,
    width: res.width,
    height: res.height,
    steps: 28,
    guidance: 4.2,
    suggestedDirectory: 'photos',
    qualityChecklist: [
      'Texture de peau et matières organiques naturelles',
      'Éclairage cohérent avec ombres de contact physiques',
      'Aucun lissage plastique ni effet filtre IA',
      'Profondeur optique réaliste (bokeh naturel)',
    ],
  }
}

function buildPixelArtPrompt(subject: string): HumanPromptResult {
  const res = CATEGORY_RESOLUTIONS.square

  const prompt = `A clean, authentic 16-bit video game pixel art sprite representing ${subject}. Hand-crafted pixel clusters on a strict integer grid, readable silhouette, limited indexed color palette (16 to 32 colors max), crisp 1-pixel outlines, and deliberate dithering on shadows. Isolated on a clean solid neutral background for seamless sprite cutting and game engine integration. No subpixel blurring, no anti-aliased gradients, pure retro gaming aesthetic.`

  return {
    category: 'game_asset_pixel_art',
    title: `Pixel Art Sprite - ${subject.slice(0, 32)}`,
    humanPrompt: prompt,
    negativePrompt: 'anti-aliasing, vector smoothing, 3d render, photorealistic, blurred pixels, soft gradients, messy noise, watermark',
    aspectRatio: res.ar,
    width: res.width,
    height: res.height,
    steps: 28,
    guidance: 5.5,
    gameAssetMeta: {
      assetType: 'sprite',
      isolatedBackground: true,
      gridSize: 32,
      pixelScale: 4,
    },
    suggestedDirectory: 'game_assets',
    qualityChecklist: [
      'Grille de pixels entière et nette',
      'Palette de couleurs indexée rétro',
      'Silhouette immédiatement lisible en jeu',
      'Fond neutre isolé prêt à détourer',
    ],
  }
}

function buildIsometricAssetPrompt(subject: string): HumanPromptResult {
  const res = CATEGORY_RESOLUTIONS.square

  const prompt = `A game-ready 3D isometric asset of ${subject}, designed for an RTS or tactical RPG game. True 30-degree orthographic isometric angle, stylized hand-painted PBR textures, clean readable geometric volumes, and clear directional key lighting casting a soft grounded contact shadow. Centered in frame and isolated on a solid neutral backdrop with generous margins for easy game sprite extraction.`

  return {
    category: 'game_asset_isometric',
    title: `Asset Isométrique - ${subject.slice(0, 32)}`,
    humanPrompt: prompt,
    negativePrompt: 'perspective distortion, wide angle lens, fish eye, cut off edges, cluttered background, realistic photo, motion blur, watermark',
    aspectRatio: res.ar,
    width: res.width,
    height: res.height,
    steps: 28,
    guidance: 4.8,
    gameAssetMeta: {
      assetType: 'isometric_building',
      isolatedBackground: true,
    },
    suggestedDirectory: 'game_assets',
    qualityChecklist: [
      'Angle orthographique isométrique 30° strict',
      'Silhouette propre et volumes lisibles',
      'Ombre portée au sol cohérente',
      'Sujet centré et isolé sans coupure',
    ],
  }
}

function buildGameIconPrompt(subject: string): HumanPromptResult {
  const res = CATEGORY_RESOLUTIONS.square

  const prompt = `A premium high-resolution video game UI inventory icon featuring ${subject}. Centered, floating slightly in perspective, with bold iconic silhouette, rich stylized materials (polished metal, glowing gems, or weathered leather), vibrant accent edge rim-lighting, and crisp defined contours. Isolated against a clean dark slate backdrop, optimized for RPG inventory slots and HUD action bars.`

  return {
    category: 'game_asset_icon_ui',
    title: `Icône de Jeu - ${subject.slice(0, 32)}`,
    humanPrompt: prompt,
    negativePrompt: 'photograph, cluttered scene, low contrast, cropped borders, blurry edges, extra items, text, numbers, watermark',
    aspectRatio: res.ar,
    width: res.width,
    height: res.height,
    steps: 28,
    guidance: 4.5,
    gameAssetMeta: {
      assetType: 'ui_icon',
      isolatedBackground: true,
    },
    suggestedDirectory: 'game_assets',
    qualityChecklist: [
      'Cadrage centré d\'icône avec marges',
      'Matières et reflets contrastés pour lisibilité en petite taille',
      'Fond uniforme prêt pour intégration UI',
      'Zéro artefact ou texte parasite',
    ],
  }
}

function buildTileableTexturePrompt(subject: string): HumanPromptResult {
  const res = CATEGORY_RESOLUTIONS.square

  const prompt = `A seamless, tileable game environment texture representing ${subject}. Orthographic top-down perpendicular perspective, completely flat even diffuse illumination without cast shadows or vignettes, consistent tactile surface details (roughness, grain, crevices), perfectly matching edge borders designed for continuous repeating pattern tiling in a 3D game engine.`

  return {
    category: 'game_asset_texture',
    title: `Texture Répétable - ${subject.slice(0, 32)}`,
    humanPrompt: prompt,
    negativePrompt: 'perspective angle, strong directional shadows, light falloff, vignette, isolated objects in center, non-repeating edges, blur',
    aspectRatio: res.ar,
    width: res.width,
    height: res.height,
    steps: 28,
    guidance: 4.5,
    gameAssetMeta: {
      assetType: 'tileable_texture',
      isolatedBackground: false,
    },
    suggestedDirectory: 'game_assets',
    qualityChecklist: [
      'Vue perpendiculaire plane sans angle',
      'Éclairage neutre et homogène sans ombres portées',
      'Bords continus pour raccord parfait',
    ],
  }
}

function buildGamePropPrompt(subject: string): HumanPromptResult {
  const res = CATEGORY_RESOLUTIONS.square

  const prompt = `A stylized 3D video game prop model of ${subject}, ready for Unreal Engine / Unity games. Clean stylized PBR material definition, readable form language, subtle edge wear and bevels, balanced color palette, rendered in a three-point studio lighting setup on a neutral grey background with clear ground contact shadow.`

  return {
    category: 'game_asset_3d_prop',
    title: `Prop 3D Stylisé - ${subject.slice(0, 32)}`,
    humanPrompt: prompt,
    negativePrompt: 'blurry, noise, photoreal skin, messy clutter, complex background, text, watermark',
    aspectRatio: res.ar,
    width: res.width,
    height: res.height,
    steps: 28,
    guidance: 4.5,
    gameAssetMeta: {
      assetType: 'item_prop',
      isolatedBackground: true,
    },
    suggestedDirectory: 'game_assets',
    qualityChecklist: [
      'Silhouettes et volumes stylisés bien définis',
      'Matières PBR lisibles',
      'Fond studio neutre isolé',
    ],
  }
}

function buildPixar3DPrompt(subject: string): HumanPromptResult {
  const res = CATEGORY_RESOLUTIONS.portrait

  const prompt = `A charming high-end 3D animated film render of ${subject} in modern Pixar / Disney feature animation style. Expressive character appeal with warm subsurface scattering skin, beautifully sculpted volumetric hair, big emotive eyes with glossy catchlights, rich tactile clothing fabric textures, illuminated by warm cinematic key lighting and soft complementary rim-light against a gently out-of-focus background.`

  return {
    category: 'stylized_pixar_3d',
    title: `Style Pixar 3D - ${subject.slice(0, 32)}`,
    humanPrompt: prompt,
    negativePrompt: 'flat 2d, sketch, realistic photograph, horror, uncanny valley, harsh shadows, low poly, blurry, watermark',
    aspectRatio: res.ar,
    width: res.width,
    height: res.height,
    steps: 28,
    guidance: 4.2,
    suggestedDirectory: 'stylized',
    qualityChecklist: [
      'Subsurface scattering chaleureux et doux',
      'Yeux expressifs et brillants',
      'Volumes de cheveux sculptés organiques',
      'Ambiance de long-métrage d\'animation haut de gamme',
    ],
  }
}

function buildAnimeGhibliPrompt(subject: string): HumanPromptResult {
  const res = CATEGORY_RESOLUTIONS.landscape

  const prompt = `A gorgeous anime key visual of ${subject}, inspired by classic Studio Ghibli and Makoto Shinkai films. Delicate precise linework, luminous hand-painted watercolor-like environment art, crisp cel-shaded character colors, vibrant atmospheric sky with volumetric clouds, and warm nostalgic sunlight filtering through the scene.`

  return {
    category: 'stylized_anime_ghibli',
    title: `Style Anime Ghibli - ${subject.slice(0, 32)}`,
    humanPrompt: prompt,
    negativePrompt: 'photorealistic, realistic skin pores, 3d CGI render, western cartoon, dark gritty, muddy textures, watermark',
    aspectRatio: res.ar,
    width: res.width,
    height: res.height,
    steps: 28,
    guidance: 4.2,
    suggestedDirectory: 'stylized',
    qualityChecklist: [
      'Lignes épurées et cel-shading soigné',
      'Arrière-plan peint riche et lumineux',
      'Atmosphère poétique et chaleureuse',
    ],
  }
}

function buildMangaInkPrompt(subject: string): HumanPromptResult {
  const res = CATEGORY_RESOLUTIONS.portrait

  const prompt = `A dynamic black and white manga splash illustration featuring ${subject}. Masterful traditional ink line hierarchy with bold contours and fine hatching, authentic screentone dot patterns for midtones, deep black ink fills, dynamic composition with expressive speedlines, strictly monochrome with crisp contrast.`

  return {
    category: 'stylized_manga_ink',
    title: `Manga Encre N&B - ${subject.slice(0, 32)}`,
    humanPrompt: prompt,
    negativePrompt: 'color, pastel, watercolor, 3d render, realistic photo, blurry gray wash, anti-aliased gradient, watermark',
    aspectRatio: res.ar,
    width: res.width,
    height: res.height,
    steps: 28,
    guidance: 4.8,
    suggestedDirectory: 'stylized',
    qualityChecklist: [
      'Noir et blanc strict avec trames lisibles',
      'Encrage dynamique avec hiérarchie des traits',
      'Contraste d\'impression manga professionnel',
    ],
  }
}

function buildCyberpunkPrompt(subject: string): HumanPromptResult {
  const res = CATEGORY_RESOLUTIONS.landscape

  const prompt = `A cinematic cyberpunk visual scene capturing ${subject}. Drenched in vivid neon lights (electric cyan, magenta, and deep amber) reflecting off rain-slicked asphalt, dense architectural layers with holographic advertisements, atmospheric steam and volumetric haze, moody noir contrast with rich dark shadows.`

  return {
    category: 'stylized_cyberpunk',
    title: `Cyberpunk Neon - ${subject.slice(0, 32)}`,
    humanPrompt: prompt,
    negativePrompt: 'daylight, cartoon, pastel, flat illustration, low contrast, washed out colors, blurry, watermark',
    aspectRatio: res.ar,
    width: res.width,
    height: res.height,
    steps: 28,
    guidance: 4.2,
    suggestedDirectory: 'stylized',
    qualityChecklist: [
      'Reflets néon dynamiques sur surfaces mouillées/métalliques',
      'Atmosphère volumique et brume',
      'Profondeur urbaine dense et lisible',
    ],
  }
}

function buildOilPaintingPrompt(subject: string): HumanPromptResult {
  const res = CATEGORY_RESOLUTIONS.standard_photo

  const prompt = `A masterful classical oil painting on linen canvas depicting ${subject}. Rich textured impasto brushwork following the contours of the form, dramatic chiaroscuro illumination reminiscent of Caravaggio and Rembrandt, deep glazed transparent shadows, and authentic craquelure and canvas grain texture.`

  return {
    category: 'stylized_oil_painting',
    title: `Peinture à l'Huile - ${subject.slice(0, 32)}`,
    humanPrompt: prompt,
    negativePrompt: 'digital art, smooth airbrush, vector flat, photograph, 3d render, plastic look, watermark',
    aspectRatio: res.ar,
    width: res.width,
    height: res.height,
    steps: 28,
    guidance: 4.0,
    suggestedDirectory: 'stylized',
    qualityChecklist: [
      'Matière de peinture à l\'huile et coups de pinceau visibles',
      'Chiaroscuro profond et contrastes classiques',
      'Texture de toile et patine authentique',
    ],
  }
}

function buildWatercolorPrompt(subject: string): HumanPromptResult {
  const res = CATEGORY_RESOLUTIONS.landscape

  const prompt = `An exquisite traditional watercolor painting on cold-press textured cotton paper depicting ${subject}. Delicate transparent pigment washes, soft wet-on-wet color blooms, natural granulation along the water edges, white paper reserves for specular highlights, and graceful calligraphic brush accents.`

  return {
    category: 'stylized_watercolor',
    title: `Aquarelle Fine - ${subject.slice(0, 32)}`,
    humanPrompt: prompt,
    negativePrompt: 'digital flat, hard vector outlines, oil impasto, 3d render, plastic gradient, photograph, watermark',
    aspectRatio: res.ar,
    width: res.width,
    height: res.height,
    steps: 28,
    guidance: 3.8,
    suggestedDirectory: 'stylized',
    qualityChecklist: [
      'Transparence des lavis et fusions d\'eau naturelles',
      'Grain du papier aquarelle visible',
      'Réserves de blanc du papier pour la lumière',
    ],
  }
}

function buildConceptArtPrompt(subject: string): HumanPromptResult {
  const res = CATEGORY_RESOLUTIONS.wide_landscape

  const prompt = `An epic production concept art matte painting of ${subject}. Cinematic widescreen composition with breathtaking scale, dramatic golden atmospheric lighting cutting through fog and clouds, clear foreground-to-background spatial depth layering, and production-ready architectural and environmental design.`

  return {
    category: 'concept_art_production',
    title: `Concept Art Épique - ${subject.slice(0, 32)}`,
    humanPrompt: prompt,
    negativePrompt: 'amateur sketch, blurry, flat lighting, messy composition, low resolution, watermark, signature',
    aspectRatio: res.ar,
    width: res.width,
    height: res.height,
    steps: 28,
    guidance: 4.0,
    suggestedDirectory: 'stylized',
    qualityChecklist: [
      'Composition cinématographique avec grande échelle',
      'Éclairage et atmosphère dramatiques',
      'Profondeur de plan lisible (avant/moyen/arrière plan)',
    ],
  }
}
