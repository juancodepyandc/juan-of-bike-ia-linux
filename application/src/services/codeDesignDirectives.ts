// ---------------------------------------------------------------------------
// codeDesignDirectives — eleve TOUS les projets visuels au niveau premium.
// Selectionne un archetype design et renvoie un bloc d instructions tres
// concret pour le Codeur (sections obligatoires, libs CDN, effets a livrer,
// patterns visuels d elite). L objectif: meme un prompt court doit produire
// un rendu digne d Awwwards / Apple / Linear / Stripe / Vercel.
// ---------------------------------------------------------------------------

import type { CodeIntent, CodeProjectType } from './codeIntent'
import {
  archetypeBlock,
  autoDepsBlock,
  buildCommonPremiumBaseline,
  depthDirectivesBlock,
} from './codeDesignDirectiveBlocks.ts'

export type DesignArchetype =
  | 'apple_product'         // produit physique, hotspots, exploded view, scrub 3D
  | 'narrative_landing'     // landing premium classique, hero immersif, scrollytelling
  | 'dashboard_dataviz'     // dashboard / admin / analytics — glassmorphism + bento + charts
  | 'portfolio_immersive'   // portfolio creative / agence — WebGL background + marquee
  | 'ecommerce_premium'     // store/shop — product cards, gallery zoom, sticky cart
  | 'saas_marketing'        // saas / agence — comparison tables, animated counters
  | 'editorial_story'       // article / blog premium — drop cap, columns, scroll progress
  | 'scroll_3d_journey'     // experience scroll 3D — pinned, scrub, camera path
  | 'microsite_event'       // event / festival — countdown, lineup, agenda
  | 'minimal_brutalist'     // brutalist / raw / minimal
  | 'mobile_native_premium' // mobile RN / Flutter — gestures, blur header, sheets
  | 'desktop_native_app'    // Tauri / Electron app — title bar, menus, panels
  | 'game_visual_premium'   // jeu web — palette neon, particles, screen shake
  | 'default_premium'       // fallback — premium generique

const VISUAL_PROJECT_TYPES: CodeProjectType[] = [
  'static_web', 'spa_react', 'spa_vue', 'spa_angular', 'spa_svelte',
  'ssr_nextjs', 'ssr_nuxt', 'ssr_remix',
  'fullstack_mern', 'fullstack_nextjs', 'fullstack_django', 'fullstack_rails',
  'desktop_electron', 'desktop_tauri', 'mobile_rn', 'mobile_flutter',
  'game_web',
]

export function isVisualProject(intent: CodeIntent): boolean {
  return VISUAL_PROJECT_TYPES.includes(intent.projectType)
}

// ---------------------------------------------------------------------------
// Archetype detection — lexical heuristic, no LLM
// ---------------------------------------------------------------------------

const APPLE_PRODUCT_HINTS = [
  // Tech devices
  'ecouteur', 'ecouteurs', 'casque', 'casques', 'airpods', 'headphone', 'earphone',
  'iphone', 'smartphone', 'samsung', 'pixel phone', 'macbook', 'laptop', 'ipad',
  'apple watch', 'montre connectee', 'smartwatch', 'gopro', 'drone', 'console',
  'manette', 'controller', 'camera', 'appareil photo', 'objectif',
  // Vehicles
  'voiture', 'auto', 'car ', 'moto', 'motorcycle', 'velo', 'bike', 'gravel',
  'trottinette', 'scooter', 'skate', 'skateboard', 'avion',
  // Wearables / objects
  'sneaker', 'sneakers', 'chaussure', 'baskets', 'sac', 'sac a dos',
  'parfum', 'perfume', 'whisky', 'biere', 'vin', 'cafe',
  // Composition / anatomy keywords
  'composition', 'composer', 'compose', 'piece', 'pieces', 'decoupe', 'decoupes',
  'anatomie', 'anatomy', 'exploded', 'exploded view', 'eclate', 'vue eclatee',
  'specs', 'specifications', 'caracteristiques techniques',
]

const DASHBOARD_HINTS = [
  'dashboard', 'tableau de bord', 'admin', 'panel', 'console admin',
  'analytics', 'metrics', 'metriques', 'kpi', 'reporting', 'monitoring',
  'crm', 'erp', 'cms', 'back office', 'backoffice',
]

const PORTFOLIO_HINTS = [
  'portfolio', 'agency', 'agence', 'studio', 'designer', 'photographe',
  'creative', 'creatif', 'showcase', 'gallery', 'works', 'projets cv',
  'mes travaux', 'my work',
]

const ECOMMERCE_HINTS = [
  'ecommerce', 'e-commerce', 'shop', 'store', 'boutique', 'panier',
  'cart', 'checkout', 'product page', 'fiche produit', 'catalog',
  'stripe checkout',
]

const SAAS_HINTS = [
  'saas', 'plateforme', 'platform', 'service en ligne', 'outil en ligne',
  'pricing', 'tarification', 'subscription', 'abonnement', 'feature page',
]

const EDITORIAL_HINTS = [
  'article', 'blog', 'magazine', 'journal', 'editorial', 'long form',
  'long-form', 'lecture longue', 'storytelling', 'recit', 'temoignage',
]

const SCROLL_3D_HINTS = [
  'scrollytelling', 'scroll story', 'experience scroll', 'experience immersive',
  'voyage immersif', 'immersive journey', 'cinematic', 'cinematique',
  'scroll 3d', 'scroll cinematic', 'sticky scroll', 'pinned scroll',
]

const EVENT_HINTS = [
  'evenement', 'event', 'festival', 'conference', 'meetup', 'sommet',
  'salon', 'expo', 'concert', 'tournoi', 'tournament',
]

const BRUTALIST_HINTS = [
  'brutalist', 'brutaliste', 'raw', 'minimal', 'minimaliste',
  'mono', 'monospace', 'editorial swiss', 'swiss design',
]

const NUMBERS_DEPTH_HINTS = [
  '3d', 'three.js', 'webgl', 'webgpu', 'parallax', 'parallaxe',
  'depth', 'profondeur', 'layer', 'couches', 'isometric',
]

function lower(text: string): string {
  // Strip combining diacritics so "écouteur" matches "ecouteur" tokens. Using
  // the explicit ̀-ͯ range avoids encoding ambiguity in the source.
  return text.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
}

function hasAny(text: string, hints: string[]): boolean {
  for (const hint of hints) {
    if (text.includes(hint)) return true
  }
  return false
}

export function detectDesignArchetype(prompt: string, intent: CodeIntent): DesignArchetype {
  const text = lower(prompt)
  const ap = intent.assetPlan

  // Mobile / desktop / game / API-only get their own dedicated archetypes.
  if (intent.projectType === 'mobile_rn' || intent.projectType === 'mobile_flutter') {
    return 'mobile_native_premium'
  }
  if (intent.projectType === 'desktop_tauri' || intent.projectType === 'desktop_electron') {
    return 'desktop_native_app'
  }
  if (intent.projectType === 'game_web') {
    return 'game_visual_premium'
  }

  // Style hints take priority on visual archetypes.
  if (hasAny(text, BRUTALIST_HINTS) || ap?.styleHints.some((s) => BRUTALIST_HINTS.includes(s))) {
    return 'minimal_brutalist'
  }

  if (hasAny(text, SCROLL_3D_HINTS) || (ap?.wants3D && intent.projectType === 'static_web')) {
    return 'scroll_3d_journey'
  }

  if (hasAny(text, DASHBOARD_HINTS)) return 'dashboard_dataviz'
  if (hasAny(text, ECOMMERCE_HINTS)) return 'ecommerce_premium'
  if (hasAny(text, SAAS_HINTS)) return 'saas_marketing'
  if (hasAny(text, PORTFOLIO_HINTS)) return 'portfolio_immersive'
  if (hasAny(text, EVENT_HINTS)) return 'microsite_event'
  if (hasAny(text, EDITORIAL_HINTS)) return 'editorial_story'

  // A concrete physical product (or a brand that sells one) → apple-style page.
  const mentionsConcreteObject =
    hasAny(text, APPLE_PRODUCT_HINTS)
    || (ap?.objectMentions ?? []).some((obj) => APPLE_PRODUCT_HINTS.includes(obj.toLowerCase()))
    || ap?.subject?.source === 'brand'

  if (mentionsConcreteObject) return 'apple_product'

  return 'narrative_landing'
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export function buildDesignDirectives(prompt: string, intent: CodeIntent): string {
  if (!isVisualProject(intent)) return ''

  const archetype = detectDesignArchetype(prompt, intent)
  const lines = [
    ...buildCommonPremiumBaseline(),
    '',
    ...archetypeBlock(archetype, intent),
    '',
    ...depthDirectivesBlock(intent),
    '',
    ...autoDepsBlock(),
    '',
    `## ARCHETYPE RETENU: ${archetype}`,
    '- Reste fidele aux sections et aux effets listes ci-dessus.',
    '- Tu peux DEPASSER ces standards (plus de sections, plus d effets) mais jamais les sous-dimensionner.',
  ]
  return lines.filter((line) => line !== undefined).join('\n')
}

/** Short label for telemetry / debug surfaces. */
export function describeDesignArchetype(archetype: DesignArchetype): string {
  switch (archetype) {
    case 'apple_product': return 'Apple-style product page (anatomy + scroll narrative)'
    case 'narrative_landing': return 'Premium narrative landing'
    case 'dashboard_dataviz': return 'Dashboard / dataviz'
    case 'portfolio_immersive': return 'Immersive portfolio'
    case 'ecommerce_premium': return 'Ecommerce premium'
    case 'saas_marketing': return 'SaaS marketing page'
    case 'editorial_story': return 'Editorial long-form story'
    case 'scroll_3d_journey': return 'Pinned 3D scroll journey'
    case 'microsite_event': return 'Event microsite'
    case 'minimal_brutalist': return 'Minimal brutalist'
    case 'mobile_native_premium': return 'Mobile native premium'
    case 'desktop_native_app': return 'Desktop native app'
    case 'game_visual_premium': return 'Game web premium juice'
    default: return 'Default premium'
  }
}
