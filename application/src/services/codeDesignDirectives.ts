// ---------------------------------------------------------------------------
// codeDesignDirectives — eleve TOUS les projets visuels au niveau premium.
// Selectionne un archetype design et renvoie un bloc d instructions tres
// concret pour le Codeur (sections obligatoires, libs CDN, effets a livrer,
// patterns visuels d elite). L objectif: meme un prompt court doit produire
// un rendu digne d Awwwards / Apple / Linear / Stripe / Vercel.
// ---------------------------------------------------------------------------

import type { CodeIntent, CodeProjectType } from './codeIntent'
import { matchesAnyHint, normalizeHintText } from './codePromptHints.ts'

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
  | 'data_dense_enterprise'  // enterprise dense — tables, filters, charts, detail drawers
  | 'ide_code_editor'        // IDE / code editor — file tree, editor, terminal
  | 'os_shell'               // OS / shell visual — terminal, boot log, status
  | 'default_premium'       // fallback — premium generique

const VISUAL_PROJECT_TYPES: CodeProjectType[] = [
  'static_web', 'spa_react', 'spa_vue', 'spa_angular', 'spa_svelte',
  'ssr_nextjs', 'ssr_nuxt', 'ssr_remix',
  'fullstack_mern', 'fullstack_nextjs', 'fullstack_django', 'fullstack_rails',
  'desktop_electron', 'desktop_tauri', 'mobile_rn', 'mobile_flutter',
  'game_web',
  'mobile_ios', 'mobile_android', 'desktop_app', 'ide',
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

const DATA_DENSE_HINTS = [
  'data dense', 'dense data', 'tableau dense', 'table dense', 'data grid',
  'datagrid', 'spreadsheet', 'tableur', 'backoffice', 'back office',
  'erp', 'crm', 'operations', 'ops', 'inventory', 'stock', 'tickets',
]

const IDE_HINTS = [
  'ide', 'code editor', 'editeur de code', 'éditeur de code', 'monaco',
  'vscode', 'vs code', 'file tree', 'terminal integre', 'terminal intégré',
]

const OS_SHELL_HINTS = [
  'os shell', 'terminal os', 'kernel shell', 'boot log', 'noyau', 'system console',
  'console systeme', 'console système', 'qemu screen',
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

/**
 * Un indice compte s il est un MOT ENTIER et qu il n est pas NIE.
 *
 * Run 1161, brief reel d une brulerie de cafe lyonnaise. L ancien test etait
 * `text.includes(hint)`, et l indice `'ide'` est tombe dans le mot « idee »:
 *
 *   « …trouve mieux si t'as une IDEe), et direct en dessous nos cafes… »
 *
 * -> archetype `ide_code_editor`, et la design-spec a exige de cette brulerie la
 * palette violet sombre d un editeur de code.
 *
 * Meme brief, seconde faute: « on n'est PAS un truc minimaliste blanc
 * scandinave » contient « minimaliste » — comme REFUS. Compter l occurrence,
 * c est lire un refus comme une commande (motif du run 1021).
 */
function hasAny(text: string, hints: string[]): boolean {
  return matchesAnyHint(text, hints)
}

export function detectDesignArchetype(prompt: string, intent: CodeIntent): DesignArchetype {
  const text = normalizeHintText(prompt)
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
  if (intent.projectType === 'ide' || hasAny(text, IDE_HINTS)) {
    return 'ide_code_editor'
  }
  if (intent.projectType === 'os_kernel' || hasAny(text, OS_SHELL_HINTS)) {
    return 'os_shell'
  }

  // Style hints take priority on visual archetypes.
  // `styleHints` peut manquer sur un assetPlan partiel: l optional chaining doit
  // porter sur le tableau lui-meme, sinon `.some` leve un TypeError et fait
  // tomber toute la detection d archetype (donc la generation).
  if (hasAny(text, BRUTALIST_HINTS) || ap?.styleHints?.some((s) => BRUTALIST_HINTS.includes(s))) {
    return 'minimal_brutalist'
  }

  if (hasAny(text, SCROLL_3D_HINTS) || (ap?.wants3D && intent.projectType === 'static_web')) {
    return 'scroll_3d_journey'
  }

  if (hasAny(text, DATA_DENSE_HINTS)) return 'data_dense_enterprise'
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
