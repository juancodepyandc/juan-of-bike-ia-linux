/**
 * codeDesignReference — public facade for premium design reference prompts.
 * Heavy static references live in sibling modules so this file stays focused
 * on composing the prompt block consumed by the Code module.
 */

import { PREMIUM_HTML_REFERENCE } from './codeDesignReferenceHtml.ts'
import { THREE_D_SCENE_REFERENCE } from './codeDesignReferenceThree.ts'
import { SUBJECT_VARIANTS, detectSubjectVariant, type SubjectVariant } from './codeDesignReferenceSubjects.ts'
import { CODE_THREE_CDN_VERSION } from './codeRuntimeDependencies.ts'

export { PREMIUM_HTML_REFERENCE } from './codeDesignReferenceHtml.ts'
export { THREE_D_SCENE_REFERENCE } from './codeDesignReferenceThree.ts'
export { detectSubjectVariant } from './codeDesignReferenceSubjects.ts'
export type { SubjectVariant } from './codeDesignReferenceSubjects.ts'

/**
 * Build the design reference snippet to inject into the codeur prompt.
 * The LLM is told this is the LEVEL expected — not a copy-paste source.
 *
 * v68: optionally append subject-specific section guidance based on the
 * detected variant from the user prompt.
 *
 * v71: `forcedVariant` lets the brand-anchor path pin the reference to the
 * `brand_landing` variant regardless of what the prompt would have detected
 * on its own ("article Coca Cola" alone does not trigger any variant).
 */
export function buildPremiumDesignReferenceBlock(promptHint?: string, forcedVariant?: string): string {
  // We slice the reference to keep token count reasonable (~2200 tokens).
  // The LLM does not need the full file: it needs the patterns.
  const reference = PREMIUM_HTML_REFERENCE
  const detected = promptHint ? detectSubjectVariant(promptHint) : null
  // Force the brand_landing variant when the orchestrator passed it — overrides
  // a weaker detection (e.g. landing) so brand pages always get brand sections.
  const variant: SubjectVariant = (forcedVariant && forcedVariant in SUBJECT_VARIANTS)
    ? (forcedVariant as Exclude<SubjectVariant, null>)
    : detected
  const subjectBlock = variant ? '\n\n' + SUBJECT_VARIANTS[variant].join('\n') : ''

  // v76: when 3d_scene is detected, swap PREMIUM_HTML_REFERENCE for the
  // Three.js starter — the LLM needs an actual working scene to mirror, not
  // a mesh-gradient landing page that has nothing to do with WebGL.
  const isThreeDScene = variant === '3d_scene'
  // v85c : slice the embedded reference HARD. The FULL PREMIUM_HTML_REFERENCE is
  // ~28.6k chars; embedding it verbatim pushed the CODEUR system prompt to
  // ~60k chars (~15k tokens) — larger than a safe 16 GB context window, so the
  // generation prompt got truncated and the model emitted nothing. The LLM
  // needs the PATTERNS (the bullets below) + a concrete TASTE, not the whole
  // file. A ~3000-char excerpt (head + hero + a section) conveys the level.
  const fullReference = isThreeDScene ? THREE_D_SCENE_REFERENCE : reference
  const usedReference = fullReference.length > 3000
    ? fullReference.slice(0, 3000) + '\n<!-- … extrait tronque : reproduis les PATTERNS ci-dessus avec TON contenu, ne copie pas ce HTML verbatim … -->'
    : fullReference
  const referenceLabel = isThreeDScene
    ? 'Voici un STARTER THREE.JS qui represente le NIVEAU exige sur toute scene 3D web.'
    : 'Voici un STARTER HTML qui represente le NIVEAU de design exige sur tout site/app que tu produis.'

  const patternBullets = isThreeDScene
    ? [
        `- ESM via importmap CDN jsdelivr (three@${CODE_THREE_CDN_VERSION} + addons)`,
        '- 5 lights minimum: HemisphereLight + DirectionalLight castShadow + 2 PointLights coloreees + SpotLight accent',
        '- Materials PBR uniquement (MeshPhysicalMaterial avec clearcoat, roughness, metalness)',
        '- PMREMGenerator + RoomEnvironment pour reflections offline',
        '- Post-processing: EffectComposer + RenderPass + UnrealBloomPass + OutputPass',
        '- 9+ objets distincts (jamais un seul mesh isole)',
        '- Animation delta-time via clock.getDelta() (pas de Date.now)',
        '- OrbitControls enableDamping autoRotate jusqu au premier clic',
        '- Raycaster pointermove pour highlight emissive',
        '- Sol PBR + scene.fog + scene.background harmonise',
      ]
    : [
        '- v82m7 — barre senior IC: oklch palette restreinte (UN seul accent), Inter Variable + Instrument Serif italic display + JetBrains Mono kicker',
        '- Easing tokens en CSS variables: --ease-out-expo, --ease-spring (cubic-bezier(0.32,0.72,0,1)), --ease-smooth. Durees 160/240/480ms',
        '- Grille 12-col explicite (grid-template-columns: repeat(12, minmax(0, 1fr))), col-span asymetriques (hero copy span-7 / visual span-5)',
        '- Container queries (@container (min-width: 880px)) en complement des media queries',
        '- View Transitions API (document.startViewTransition) pour le swap dark/light',
        '- Scroll-driven natif quand supporte: @supports (animation-timeline: view()) + animation-range: entry 0% entry 60%',
        '- Glassmorphism Apple/Linear: backdrop-filter blur(20px) saturate(180%) + inset 0 1px 0 oklch(1 0 0 / 0.06) signature',
        '- Mosaique inegale (.feature.large/medium/small/wide) — JAMAIS une grille auto-fit uniforme',
        '- Display headline italic serif highlighted (.em avec ::before en accent-soft skew-3deg) — pas un h1 bold scolaire',
        '- Stats editorialisees: chiffres en Instrument Serif italic + sup en JetBrains Mono accent',
        '- Hover scale 1.02 max + magnetic spring (transform max 18% du delta), JAMAIS scale 1.1',
        '- Cursor follow subtil (14px outline, mix-blend-mode: difference, lerp 0.18) — pas une fleche custom',
        '- Counter ease-out-expo (Math.pow(1-t,4)) + Number.toLocaleString pour les milliers',
        '- Footer dense 12-col (4+2+2+2 + footer-base mono uppercase)',
        '- prefers-reduced-motion respecte strict',
      ]

  return [
    '## REFERENCE DESIGN PREMIUM (NIVEAU MINIMUM ATTENDU)',
    '',
    referenceLabel,
    'Ne le copie PAS verbatim. ETUDIE les patterns suivants et reproduis-les avec ton propre contenu adapte au sujet:',
    ...patternBullets,
    '',
    variant === 'brand_landing'
      ? 'NOTE BRAND: les couleurs, typo et accents du starter ci-dessous (violet/cyan/ambre, Inter) NE SONT PAS adaptes pour une page de marque. Utilise le starter pour les patterns techniques (CSS variables, scroll reveal, animations) mais REMPLACE la palette et la typo par celles dictees par le bloc VERROUILLAGE SUJET en amont.'
      : '',
    '',
    '```html',
    usedReference,
    '```',
    subjectBlock,
    '',
    'IMPORTANT (v82m7 — barre senior IC):',
    '- Le starter ci-dessus est le NIVEAU MINIMUM. Tu peux le DEPASSER, jamais le sous-dimensionner.',
    '- Reprends les TOKENS (oklch palette, easing, spacing, type system). Adapte les VALEURS au sujet.',
    '- Si tu mets un seul accent oklch et que tu dois ajouter une couleur dataviz, prends une 2e teinte cousine — JAMAIS un primary+secondary+tertiary scolaire.',
    '- Utilise au moins UNE phrase Instrument Serif italic dans un display (hero h1 .em, ou cta-final h2 .em). Le contraste serif italic / sans-serif est la signature 2025-2026.',
    '- Headline avec un fond accent skew-3deg (.em::before) sur le mot fort: c est ce qui differencie le tutoriel du senior.',
    '- Mosaique inegale obligatoire sur les features (pas une grille uniforme auto-fit).',
    '- Hover scale max 1.02. Magnetic max 6-8px. Jamais plus.',
    '- Dark mode par defaut + view-transitions sur le swap.',
    '- Si un mot du brief impose une autre teinte (Coca rouge, Tesla blanc, Stripe purple), remplace l accent oklch par la teinte BRANDEE — mais garde le reste du systeme.',
    variant ? `- Pour ce projet TYPE ${variant.toUpperCase()}: respecte aussi les SECTIONS SPECIFIQUES listees ci-dessus.` : '',
  ].filter(Boolean).join('\n')
}
