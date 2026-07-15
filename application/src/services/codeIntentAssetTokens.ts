// ---------------------------------------------------------------------------
// Asset intent tokens
// Extracted from codeIntent.ts during WS1 modularisation.
// ---------------------------------------------------------------------------

import { containsSignal, normalizeSignalText } from './codeIntentSignalUtils.ts'

export const PREMIUM_LOOK_TOKENS = [
  // FR
  'premium', 'haut de gamme', 'haut-de-gamme', 'elegant', 'sophistique', 'luxe', 'luxueux',
  'pro', 'professionnel', 'professionnelle', 'attirant', 'attirante', 'attractif', 'moderne',
  'design moderne', 'tendance', 'epure', 'soigne', 'chic', 'stylee', 'stylé', 'stylise',
  'immersif', 'impressionnant', 'impressionnante', 'travaille', 'fignole', 'wow', 'accrocheur',
  'editorial', 'studio', 'vitrine', 'showroom', 'agence',
  // EN
  'modern', 'clean', 'sleek', 'polished', 'high end', 'high-end', 'stunning', 'beautiful',
  'gorgeous', 'striking', 'award winning', 'award-winning', 'pixel perfect', 'pixel-perfect',
  // Style family
  'cyberpunk', 'minimaliste', 'glassmorphism', 'neumorphism', 'futuriste', 'retro', 'vintage',
  'art deco', 'art nouveau', 'brutaliste', 'brutalist', 'scandinave', 'japandi', 'bauhaus',
  'animation', 'animations', 'animee', 'anime', 'dynamique', 'interactif', 'interactive',
]

export const RESEARCH_TRIGGER_TOKENS = [
  'cherche', 'trouve', 'recherche', 'inspire-toi', 'inspires-toi', 'inspire toi', 'reference',
  'references', 'tendance', 'tendances', 'exemples reels', 'vrais exemples', 'comme sur',
  'look and feel', 'mood board', 'moodboard',
  'find', 'search', 'lookup', 'browse', 'inspired by', 'inspire',
]

export const IMAGE_TOKENS = [
  'image', 'images', 'photo', 'photos', 'picture', 'pictures', 'illustration', 'illustrations',
  'icone', 'icones', 'icon', 'icons', 'logo', 'logos', 'banner', 'banniere', 'hero image',
  'visuel', 'visuels', 'fond', 'background image', 'thumbnail', 'vignette',
]

export const THREED_TOKENS = [
  '3d', 'three.js', 'threejs', 'webgl', '3d model', 'modele 3d', 'rotation 3d', 'orbit control',
  'glb', 'gltf', 'canvas 3d', 'webgpu',
]

export const EFFECT_TOKENS = [
  'parallax', 'parallaxe', 'scroll', 'scrolly', 'scrolling', 'reveal', 'fade in', 'fade-in',
  'glow', 'neon', 'neonglow', 'blur', 'flou', 'hover', 'transition', 'transitions',
  'particles', 'particules', 'tilt', 'gradient animated', 'gradient anime',
  'gsap', 'framer', 'framer motion', 'lottie', 'rive',
  'cursor suiveur', 'custom cursor', 'smooth scroll', 'marquee',
  'carousel', 'carrousel', 'slider', 'timeline', 'accordeon', 'accordion',
]

export const COLOR_HEX_REGEX = /#[0-9a-f]{3,8}\b/gi

export function extractMentions(lower: string, dictionary: string[]): string[] {
  const hits: string[] = []
  for (const token of dictionary) {
    if (containsSignal(lower, token) && !hits.includes(token)) hits.push(token)
  }
  return hits
}

/**
 * Extract object / subject mentions that likely need a visual asset.
 * Heuristic: a small bag of concrete nouns commonly used in web briefs.
 */
export const CONCRETE_OBJECT_TOKENS = [
  // Transport
  'velo', 'bike', 'gravel', 'voiture', 'car', 'moto', 'motorcycle', 'camion', 'truck',
  'drone', 'avion', 'plane', 'bateau', 'boat', 'skate', 'skateboard', 'trottinette',
  // Tech product
  'iphone', 'smartphone', 'laptop', 'ordinateur portable', 'macbook', 'casque', 'headphone',
  'speaker', 'enceinte', 'camera', 'appareil photo', 'console', 'manette',
  // Food
  'cafe', 'pizza', 'burger', 'salade', 'sushi', 'cocktail', 'vin',
  // Living
  'chat', 'chien', 'cat', 'dog', 'fleur', 'plante', 'arbre', 'paysage',
  // Space
  'planete', 'lune', 'etoile', 'galaxie', 'ocean',
  // Fashion
  'montre', 'watch', 'sneaker', 'baskets', 'sac', 'bag',
  // Structures
  'maison', 'house', 'villa', 'cabane', 'tower', 'tour', 'pont', 'bridge', 'temple', 'chateau',
]

export function extractObjectMentions(prompt: string): string[] {
  const lower = normalizeSignalText(prompt)
  const hits = extractMentions(lower, CONCRETE_OBJECT_TOKENS)
  // Also try 2-3 word phrases between quotes (e.g. "Renault Clio 5").
  const quoted = prompt.match(/["'«»]([^"'«»]{3,40})["'«»]/g) || []
  for (const q of quoted) {
    const clean = q.replace(/["'«»]/g, '').trim()
    if (clean && !hits.includes(clean.toLowerCase())) hits.push(clean)
  }
  return hits.slice(0, 8)
}

export function buildResearchQueries(
  prompt: string,
  styleHints: string[],
  objectMentions: string[],
  wantsPremium: boolean,
): string[] {
  const queries: string[] = []
  const head = prompt.trim().split(/\s+/).slice(0, 6).join(' ')

  if (wantsPremium && head) {
    queries.push(`${head} web design 2025 award winning`)
    queries.push(`${head} modern layout inspiration`)
  }
  for (const obj of objectMentions.slice(0, 3)) {
    queries.push(`${obj} hero image`)
    queries.push(`${obj} product photography transparent background`)
  }
  for (const style of styleHints.slice(0, 2)) {
    queries.push(`${style} web design example`)
  }
  return Array.from(new Set(queries.map((q) => q.replace(/\s+/g, ' ').trim()))).filter(Boolean).slice(0, 6)
}

// ---------------------------------------------------------------------------
// Language + subject detection — so the LLM stops drifting off-topic
// ---------------------------------------------------------------------------
