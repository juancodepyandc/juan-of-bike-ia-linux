// ---------------------------------------------------------------------------
// codeDesignResearch — etape 1.6 du pipeline.
// Recherche en ligne des references visuelles SPECIFIQUES a l archetype detecte
// (Awwwards / SiteInspire / Dribbble / Behance / Land-book) + injecte un brief
// d inspiration concret dans le contexte du Codeur. Combine:
//   1. Knowledge base in-memory (references curees, palettes connues, libs)
//   2. Aurora web-search service (archetype + sujet)
//   3. Ollama synthesis pour fusionner refs + sujet en directives concretes.
// ---------------------------------------------------------------------------

import { CODE_SINGLE_MODEL } from '../config/models'
import { resilientOllamaGenerate } from './ollamaResilience'
import type { CodeIntent } from './codeIntent'
import { detectDesignArchetype, type DesignArchetype } from './codeDesignDirectives'
import { searchCodeWebReferences } from './codeWebResearchClient.ts'

const DESIGN_RESEARCH_TIMEOUT_MS = 22_000
const PER_QUERY_TIMEOUT_MS = 10_000

// ---------------------------------------------------------------------------
// Knowledge base — curated references per archetype.
// Pas d invention: ces sites existent vraiment et sont des references actuelles
// dans la communaute design. Ils servent d ancres pour les recherches.
// ---------------------------------------------------------------------------

type ArchetypeKB = {
  inspirationSites: string[]
  searchAnchors: string[]
  paletteHints: string[]
  knownLibs: string[]
}

const ARCHETYPE_KB: Record<DesignArchetype, ArchetypeKB> = {
  apple_product: {
    inspirationSites: [
      'apple.com/airpods-pro',
      'apple.com/iphone-15-pro',
      'nothing.tech/products/phone-2',
      'studio.design',
      'rauno.me',
    ],
    searchAnchors: [
      'apple product page exploded view scroll',
      'product anatomy hotspots web design',
      'product page scroll cinematic awwwards',
      'apple style scrollytelling product reveal',
    ],
    paletteHints: ['#fafafa', '#0a0a0b', '#86868b', '#0066cc'],
    knownLibs: ['three.js', 'gsap ScrollTrigger', 'lenis', 'split-type'],
  },
  narrative_landing: {
    inspirationSites: [
      'stripe.com',
      'linear.app',
      'vercel.com',
      'resend.com',
      'plain.com',
    ],
    searchAnchors: [
      'modern saas landing page 2025',
      'gradient mesh hero section design',
      'bento grid landing page',
      'awwwards landing page premium',
    ],
    paletteHints: ['#0d1117', '#7c3aed', '#3b82f6', '#22c55e'],
    knownLibs: ['gsap', 'ScrollTrigger', 'Lenis'],
  },
  dashboard_dataviz: {
    inspirationSites: [
      'linear.app',
      'vercel.com/dashboard',
      'plane.so',
      'cron.com',
      'arc.net',
    ],
    searchAnchors: [
      'modern admin dashboard ui design',
      'glassmorphism analytics dashboard',
      'bento grid dashboard layout',
      'dataviz dashboard inspiration 2025',
    ],
    paletteHints: ['#0e0e11', '#a78bfa', '#22d3ee', '#fbbf24'],
    knownLibs: ['Chart.js', 'D3', 'Lucide icons'],
  },
  portfolio_immersive: {
    inspirationSites: [
      'awwwards.com',
      'cssdesignawards.com',
      'siteInspire.com',
      'fwa.com',
      'tobiaswittwer.com',
    ],
    searchAnchors: [
      'awwwards portfolio webgl',
      'creative agency website award winning',
      'portfolio design 2025 immersive',
      'studio website webgl distortion',
    ],
    paletteHints: ['#000000', '#ffffff', '#ff0000'],
    knownLibs: ['three.js', 'GSAP', 'Lenis', 'OGL'],
  },
  ecommerce_premium: {
    inspirationSites: [
      'aimeleondore.com',
      'bose.com',
      'allbirds.com',
      'tracksmith.com',
      'patagonia.com',
    ],
    searchAnchors: [
      'premium ecommerce product page design',
      'editorial fashion store website',
      'product page galerie zoom interactive',
      'shopify premium theme design 2025',
    ],
    paletteHints: ['#fafafa', '#1a1a1a', '#c8a96a'],
    knownLibs: ['GSAP', 'Swiper', 'Lenis'],
  },
  saas_marketing: {
    inspirationSites: [
      'linear.app',
      'attio.com',
      'tella.tv',
      'cal.com',
      'cron.com',
    ],
    searchAnchors: [
      'modern saas pricing page design',
      'b2b product page premium 2025',
      'saas landing page bento grid features',
      'awwwards saas page',
    ],
    paletteHints: ['#0d0d0f', '#5b8def', '#22c55e'],
    knownLibs: ['gsap', 'lottie', 'rive'],
  },
  editorial_story: {
    inspirationSites: [
      'pudding.cool',
      'theverge.com/features',
      'nytimes.com',
      'bloomberg.com/graphics',
    ],
    searchAnchors: [
      'editorial long form scroll story',
      'pudding cool style article web',
      'newspaper interactive feature design',
      'editorial typography web 2025',
    ],
    paletteHints: ['#fafafa', '#1a1a1a', '#c0392b'],
    knownLibs: ['scrollama', 'd3', 'gsap'],
  },
  scroll_3d_journey: {
    inspirationSites: [
      'igloo.inc',
      'active.theory',
      'unseen.co',
      'lusion.co',
      'rauno.me',
    ],
    searchAnchors: [
      'pinned scroll three.js website',
      'webgl scroll cinematic experience',
      'awwwards three.js scroll story',
      'scroll triggered camera three.js',
    ],
    paletteHints: ['#000000', '#0a0a0b', '#ec4899'],
    knownLibs: ['three.js', 'GSAP ScrollTrigger', 'Lenis', 'EffectComposer'],
  },
  microsite_event: {
    inspirationSites: [
      'reactconf.com',
      'thefwa.com',
      'youfest.fr',
      'hackathon.com',
    ],
    searchAnchors: [
      'event microsite festival landing',
      'conference website design 2025',
      'festival lineup grid design',
      'concert event website inspiration',
    ],
    paletteHints: ['#0d0d1a', '#ec4899', '#fbbf24'],
    knownLibs: ['gsap', 'lenis'],
  },
  minimal_brutalist: {
    inspirationSites: [
      'brutalistwebsites.com',
      'bauhaus-movement.com',
      'isamtype.com',
    ],
    searchAnchors: [
      'brutalist web design 2025',
      'editorial swiss style website',
      'minimalist mono typography web',
    ],
    paletteHints: ['#000000', '#ffffff', '#ff0000'],
    knownLibs: ['none', 'css only'],
  },
  mobile_native_premium: {
    inspirationSites: [
      'mobbin.com',
      'apple.com/ios',
      'linear.app/mobile',
    ],
    searchAnchors: [
      'mobile app design ios premium 2025',
      'react native premium ui',
      'flutter premium design',
    ],
    paletteHints: ['#0d0d1a', '#7c3aed'],
    knownLibs: ['react-native-reanimated', 'gorhom bottom sheet'],
  },
  desktop_native_app: {
    inspirationSites: [
      'linear.app',
      'arc.net',
      'cron.com',
    ],
    searchAnchors: [
      'desktop app ui design modern 2025',
      'tauri electron premium design',
      'native app sidebar dashboard',
    ],
    paletteHints: ['#0d0d11', '#5b8def'],
    knownLibs: ['lucide', 'cmdk'],
  },
  game_visual_premium: {
    inspirationSites: [
      'js13kgames.com',
      'arcade.makecode.com',
    ],
    searchAnchors: [
      'canvas game juicy effects',
      'web game neon visuals',
      'browser game particles screen shake',
    ],
    paletteHints: ['#0a0a0b', '#ec4899', '#22d3ee'],
    knownLibs: ['none — vanilla canvas + Web Audio'],
  },
  data_dense_enterprise: {
    inspirationSites: [
      'linear.app',
      'retable.io',
      'airtable.com',
      'attio.com',
      'grafana.com',
    ],
    searchAnchors: [
      'data dense enterprise table UI design',
      'admin data grid dashboard UX',
      'operations backoffice dense interface',
      'enterprise app table filters drawer design',
    ],
    paletteHints: ['#0f172a', '#2563eb', '#14b8a6', '#f8fafc'],
    knownLibs: ['TanStack Table', 'D3', 'Chart.js', 'Lucide icons'],
  },
  ide_code_editor: {
    inspirationSites: [
      'code.visualstudio.com',
      'zed.dev',
      'cursor.com',
      'replit.com',
      'stackblitz.com',
    ],
    searchAnchors: [
      'modern IDE UI file tree editor terminal',
      'code editor interface design command palette',
      'developer tool dark UI workspace',
      'terminal panel status bar IDE UX',
    ],
    paletteHints: ['#0d1117', '#1f6feb', '#2ea043', '#f0f6fc'],
    knownLibs: ['CodeMirror 6', 'Monaco editor', 'xterm.js', 'cmdk'],
  },
  os_shell: {
    inspirationSites: [
      'gnome.org',
      'kde.org',
      'wezfurlong.org/wezterm',
      'warp.dev',
      'system76.com/pop',
    ],
    searchAnchors: [
      'operating system shell UI boot console design',
      'terminal dashboard process monitor UI',
      'kernel boot log interface typography',
      'system monitor console design',
    ],
    paletteHints: ['#020617', '#22c55e', '#38bdf8', '#e2e8f0'],
    knownLibs: ['xterm.js', 'Canvas 2D', 'WebGL terminal effects'],
  },
  default_premium: {
    inspirationSites: [
      'awwwards.com',
      'godly.website',
      'siteInspire.com',
    ],
    searchAnchors: [
      'modern web design 2025 premium',
      'awwwards site of the day',
      'godly best modern web designs',
    ],
    paletteHints: ['#0d0d11', '#7c3aed'],
    knownLibs: ['gsap', 'lenis'],
  },
}

// ---------------------------------------------------------------------------
// Web search — reuse the search infra of codeResearch with a longer timeout
// budget when the goal is design research (more sources = better synthesis).
// ---------------------------------------------------------------------------

async function searchOneQuery(query: string): Promise<string[]> {
  return searchCodeWebReferences(query, { limit: 6, timeoutMs: PER_QUERY_TIMEOUT_MS })
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export type DesignResearchOutput = {
  archetype: DesignArchetype
  inspirationSites: string[]
  searchSnippets: string[]
  synthesisBrief: string
  /** Telemetry: which queries were executed (for the UI / debug surface). */
  executedQueries: string[]
}

/**
 * Run the design research pass. Returns:
 *  - the detected archetype
 *  - curated inspiration sites
 *  - web snippets pulled per archetype + subject
 *  - an Ollama-synthesized brief (1-page) the Codeur uses as inspiration
 *
 * All steps are time-boxed and non-blocking — if every search fails the
 * function still returns a valuable knowledge-base brief.
 */
export async function runDesignResearch(
  prompt: string,
  intent: CodeIntent,
  model: string = CODE_SINGLE_MODEL,
): Promise<DesignResearchOutput> {
  const archetype = detectDesignArchetype(prompt, intent)
  const kb = ARCHETYPE_KB[archetype]
  const subject = intent.assetPlan?.subject?.canonical || intent.assetPlan?.objectMentions?.[0] || ''

  // Build queries: archetype anchors + subject hybrid + brand if any.
  const queries = new Set<string>()
  for (const anchor of kb.searchAnchors) queries.add(anchor)
  if (subject) {
    queries.add(`${subject} product website inspiration`)
    queries.add(`${subject} hero section design 2025`)
  }
  const finalQueries = Array.from(queries).slice(0, 5)

  // Run searches in parallel with a global cap.
  const start = Date.now()
  const results = await Promise.allSettled(
    finalQueries.map((q) => searchOneQuery(q)),
  )
  const allSnippets: string[] = []
  for (const r of results) {
    if (r.status === 'fulfilled') {
      for (const snippet of r.value) {
        if (allSnippets.length < 14 && !allSnippets.includes(snippet)) {
          allSnippets.push(snippet)
        }
      }
    }
  }
  const elapsed = Date.now() - start

  // Synthesize a brief — even if the web returned nothing, the LLM uses the KB
  // and its own knowledge to produce inspiration concrete pour le Codeur.
  const synthesisPrompt = [
    'Tu es un Design Director senior. Tu prepares un brief inspiration pour un developpeur d elite.',
    `Archetype design: ${archetype.replace(/_/g, ' ')}.`,
    subject ? `Sujet: ${subject}.` : '',
    `Reference sites curees: ${kb.inspirationSites.join(', ')}.`,
    `Palette suggeree: ${kb.paletteHints.join(', ')}.`,
    `Librairies recommandees: ${kb.knownLibs.join(', ')}.`,
    '',
    allSnippets.length > 0
      ? `Snippets trouves en ligne:\n${allSnippets.slice(0, 8).map((s, i) => `${i + 1}. ${s}`).join('\n')}`
      : 'Aucun snippet web exploitable — utilise tes connaissances KB.',
    '',
    'Produis un brief clair en 8-12 lignes:',
    '- 3 references visuelles concretes (sites ou patterns) avec ce qu on doit emprunter (atmosphere, layout, palette, animation).',
    '- 4-6 elements visuels OBLIGATOIRES (hero, sections phare, micro-interactions specifiques).',
    '- 2-3 librairies CDN a inclure et leur role.',
    '- 1 piege courant a eviter pour ce type de page.',
    '',
    'Reponds en francais, precis, non generique. Pas d introduction, pas de conclusion.',
  ].filter(Boolean).join('\n')

  let synthesisBrief = ''
  try {
    const remaining = Math.max(8_000, DESIGN_RESEARCH_TIMEOUT_MS - elapsed)
    const response = await resilientOllamaGenerate(model, synthesisPrompt, {
      timeoutMs: remaining,
    })
    synthesisBrief = response?.response?.trim() || ''
  } catch {
    synthesisBrief = ''
  }

  // Fallback brief — if Ollama is down, still return a usable KB brief so the
  // Codeur receives concrete guidance.
  if (!synthesisBrief) {
    synthesisBrief = [
      `Inspiration ${archetype.replace(/_/g, ' ')}:`,
      `- Sites references: ${kb.inspirationSites.slice(0, 3).join(', ')}.`,
      `- Palette de depart (a moduler): ${kb.paletteHints.join(', ')}.`,
      `- Librairies a brancher: ${kb.knownLibs.join(', ')}.`,
      subject ? `- Sujet a illustrer: ${subject}.` : '',
      '- Vise un rendu studio premium (pas tutoriel).',
    ].filter(Boolean).join('\n')
  }

  return {
    archetype,
    inspirationSites: kb.inspirationSites,
    searchSnippets: allSnippets,
    synthesisBrief,
    executedQueries: finalQueries,
  }
}

/**
 * Serialise the research result into a system-prompt-friendly block.
 * Inserted by the orchestrator BETWEEN the existing best practices and the
 * planning phase — it focuses on visual direction, not technical patterns.
 */
export function serializeDesignResearch(research: DesignResearchOutput): string {
  return [
    `## RECHERCHE DESIGN — ARCHETYPE ${research.archetype.toUpperCase()}`,
    '',
    research.synthesisBrief,
    '',
    `Sites references curees (a etudier mentalement avant de coder): ${research.inspirationSites.join(', ')}.`,
    research.searchSnippets.length > 0
      ? `\nExtraits web (${research.searchSnippets.length} snippet(s)):\n${research.searchSnippets.slice(0, 6).map((s, i) => `${i + 1}. ${s}`).join('\n')}`
      : '',
    '',
    'INSTRUCTION: tu N AS PAS le droit de copier ces sites au pixel. Tu T INSPIRES (atmosphere, hierarchie typographique, mouvements, palette). Adapte au sujet de l utilisateur.',
  ].filter(Boolean).join('\n')
}
