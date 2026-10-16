// ---------------------------------------------------------------------------
// codeExecutorQualityContract — dit au CODEUR quel est le niveau exige.
//
// Pourquoi ce module existe. Quand WS3 est devenu le moteur de generation, la
// boucle « un appel modele par fichier » a remplace l ancien appel unique, et
// `buildCodeurSystemPrompt` (contrat design, verrouillage sujet/marque, contrat
// d interactivite, contrat de livraison) est devenu ORPHELIN: son seul appelant
// restant, `getSystemPromptForRole`, n a plus aucun appelant de production. Le
// prompt systeme reellement envoye au modele pendant la generation etait donc
// reduit a huit lignes de plomberie « produis des actions JSON ».
//
// Consequence mesuree: le modele ignorait la barre de qualite. Un run reel sur
// « landing page premium Mercedes-Benz » a produit 14 fichiers SANS index.html
// — le contrat de livraison ne lui avait jamais ete transmis — et a brule une
// passe de regeneration complete pour s en apercevoir apres coup.
//
// Ce module reinjecte l essentiel, mais PAS en recopiant le prompt codeur
// complet: il fait 42 000 caracteres (~10 600 tokens) et WS3 appelle le modele
// UNE FOIS PAR FICHIER. Sur un projet de 9 fichiers cela ajouterait ~95 000
// tokens de prompt systeme, avec num_ctx=24 576 et un modele de 18,6 Go sur un
// GPU de 16 Go: swap garanti, donc crash. On livre donc un contrat COMPACT,
// cible sur le fichier en cours et borne par un budget de caracteres.
// ---------------------------------------------------------------------------

import type { CodeIntent } from './codeIntent.ts'
import { detectDesignArchetype } from './codeDesignDirectives.ts'
import { archetypeBlock, autoDepsBlock, depthDirectivesBlock, typographyContractBlock } from './codeDesignDirectiveBlocks.ts'
import { requiredEntryFilesForProject } from './codeArchitecturePlanEntryContract.ts'
import { buildSubjectLockBlock } from './codeSubjectPromptContract.ts'
import { isVisualProject } from './codeSystemPromptContracts.ts'

/**
 * Budget du contrat qualite ajoute au prompt systeme, par fichier.
 *
 * Deux regimes, parce que le cout se paie a CHAQUE appel modele (un par
 * fichier) et que num_ctx vaut 24 576:
 *  - fichier visuel: 12 000 caracteres (~3 000 tokens). Assez pour le
 *    verrouillage marque COMPLET — il porte le contrat PLACEHOLDER_SUBJECT_IMG
 *    et la recette shader Fresnel que la gate de fidelite verifie ensuite —
 *    plus l archetype et l interactivite. Reste 3,5x moins cher que les 42 000
 *    caracteres du prompt codeur complet.
 *  - fichier de configuration: le strict minimum. Un `tsconfig.json` n a que
 *    faire d une palette de marque, et lui envoyer 1 600 tokens par appel est
 *    du contexte brule.
 */
export const EXECUTOR_QUALITY_CONTRACT_MAX_CHARS = 18_500
export const EXECUTOR_QUALITY_CONTRACT_BACKEND_MAX_CHARS = 8_500
export const EXECUTOR_QUALITY_CONTRACT_CONFIG_MAX_CHARS = 1_200

/** Coupe sur une frontiere de ligne: tronquer au milieu d une regle la rend fausse. */
function capBlock(text: string, max: number): string {
  if (text.length <= max) return text
  const cut = text.slice(0, max)
  const lastBreak = cut.lastIndexOf('\n')
  return (lastBreak > max * 0.5 ? cut.slice(0, lastBreak) : cut).trimEnd()
}

const VISUAL_FILE_RE = /\.(html?|css|scss|sass|less|jsx?|tsx?|vue|svelte|astro)$/i
const STYLE_FILE_RE = /\.(css|scss|sass|less)$/i
const SCRIPT_FILE_RE = /\.(jsx?|tsx?|vue|svelte|astro)$/i
const MARKUP_FILE_RE = /\.html?$/i
const BACKEND_EXT_RE = /\.(py|rs|go|java|kt|cs|rb|php|sql|prisma|graphql|proto)$/i
const BACKEND_PATH_RE = /(^|\/)(api|server|backend|routes?|controllers?|services?|repositories|db|database|models?|schema|middleware|workers?|handlers?|store|engine)(\/|\.|-|_|$)/i

export type ExecutorContractTarget = {
  path: string
  language?: string | null
  role?: string | null
}

/**
 * Fichiers outillage qui portent l extension d un fichier source sans en etre
 * un: `vite.config.ts`, `tailwind.config.js`, `eslintrc.cjs`... Aucun rendu ne
 * depend d eux, donc aucune directive esthetique ne doit y etre payee.
 */
const CONFIG_BASENAME_RE =
  /(^|\/)(vite|vitest|rollup|webpack|next|nuxt|svelte|astro|tailwind|postcss|babel|jest|playwright|eslint|prettier|metro|capacitor)\.config\.[cm]?[jt]sx?$|(^|\/)\.?eslintrc\.[cm]?[jt]s$/i

const PURE_CONFIG_FILE_RE = /\.(json|ya?ml|toml|ini|env|lock|md|txt)$/i

/**
 * Fichier de configuration / metadonnees: aucune directive esthetique n a de
 * sens dessus, et l y injecter gaspille du contexte a chaque appel.
 */
function isVisualTarget(target: ExecutorContractTarget): boolean {
  const p = target.path || ''
  if (CONFIG_BASENAME_RE.test(p)) return false
  return VISUAL_FILE_RE.test(p)
}

function isBackendOrServiceTarget(intent: CodeIntent, target: ExecutorContractTarget): boolean {
  const p = target.path || ''
  if (CONFIG_BASENAME_RE.test(p) || PURE_CONFIG_FILE_RE.test(p)) return false
  if (BACKEND_EXT_RE.test(p) || BACKEND_PATH_RE.test(p)) return true
  if (target.role && /backend|api|server|service|database|controller|worker|engine/i.test(target.role)) return true
  if (!isVisualProject(intent.projectType) && /\.(ts|js|mjs|cjs)$/i.test(p)) return true
  return false
}

/**
 * Fichiers d entree obligatoires par type de projet. C est exactement ce qui
 * manquait au run Mercedes: le modele ne savait pas que `index.html` etait
 * non negociable pour un `static_web`.
 *
 * Source de verite partagee avec la reparation du plan d architecture: deux
 * listes divergentes produiraient un plan et un contrat qui se contredisent.
 */
function requiredEntryFiles(intent: CodeIntent): string[] {
  return requiredEntryFilesForProject(intent.projectType)
}

function buildDeliveryEssentials(intent: CodeIntent): string {
  const entries = requiredEntryFiles(intent)
  const lines = [
    '## CONTRAT DE LIVRAISON — NON NEGOCIABLE',
    '- Chaque fichier que tu ecris est COMPLET et fonctionnel: aucun TODO, aucun placeholder, aucun "// reste du code".',
    '- Le projet doit s executer sans retouche humaine.',
  ]
  if (entries.length > 0) {
    lines.push(
      `- Ce projet est un \`${intent.projectType}\`: le livrable DOIT contenir ${entries.map((e) => `\`${e}\``).join(' et ')}. Sans ce(s) fichier(s) la livraison est REJETEE automatiquement.`,
      '- Si le fichier en cours est cette entree, il doit reellement charger les styles et scripts du projet (balises <link>/<script> vers les chemins reellement produits).',
    )
  }
  return lines.join('\n')
}

/**
 * Barre de qualite visuelle condensee. S applique aussi aux composants
 * `.tsx`/`.jsx`/`.vue`/`.svelte` ou 90% du layout et du style React/SPA est ecrit.
 */
function buildVisualBar(target: ExecutorContractTarget): string {
  const lines = [
    '## BARRE DE QUALITE VISUELLE — NIVEAU INGENIEUR PRODUIT SENIOR (AWWWARDS / LINEAR / STRIPE / APPLE)',
    '- Reference: Linear / Vercel / Stripe / Raycast / Apple. Un rendu plat, Bootstrap, theme WordPress ou tutoriel debutant est un ECHEC et sera rejete.',
    '- UN SEUL accent chromatique (un second uniquement en focus state ou dataviz). Couleurs en `oklch()`/`hsl()` ou variables CSS `--color-*`, jamais `red`/`blue` nommes.',
    '- Neutres: rampe teintee profonde (ex. `#090b10` -> `#11151f` -> `#181e2c`), jamais `#000` ni `#fff` purs sur les surfaces. Bordures speculaires `1px solid rgba(255,255,255,0.08)` + highlight interne `inset 0 1px 0 rgba(255,255,255,0.08)`.',
    '- Typographie: display tendu ou serif editorial, body 14-16px line-height 1.55-1.65, mono uppercase letter-spacing 0.08em pour les kickers et metriques (`font-variant-numeric: tabular-nums`). Echelle 12/14/16/20/28/40/56/72/96.',
    '- Tracking negatif sur les gros titres (-0.04em au-dela de 56px). Mesure de ligne 60-70 caracteres sur la prose.',
  ]
  if (STYLE_FILE_RE.test(target.path) || MARKUP_FILE_RE.test(target.path) || SCRIPT_FILE_RE.test(target.path)) {
    lines.push(
      '- Layout architectural: grille Bento 12 colonnes avec col-span ASYMETRIQUES (ex. 7+5, 8+4, 4+4+4 — jamais une grille `auto-fit` monotone de cartes identiques). Sections `padding-block: clamp(80px, 10vw, 150px)`.',
      '- Espacement par tokens 4-base et `gap` sur le parent — jamais un `margin-top: 10px` arbitraire.',
      '- Profondeur multi-couches obligatoire: mesh gradient radial floute en arriere-plan (`filter: blur(80px)`), surfaces glassmorphism (`backdrop-filter: blur(20px) saturate(160%)`), ombres composites multi-couches (`0 1px 2px rgba(0,0,0,0.35), 0 20px 48px -12px rgba(0,0,0,0.55)`).',
    )
  }
  return lines.join('\n')
}

/**
 * Contrat de Motion Design & Choregraphie Physique.
 * Corrige les interfaces statiques ou scolaires en imposant une vraie physique
 * de ressort, des cascades d entree, un spotlight magnetique au pointeur et des
 * boucles `requestAnimationFrame` fluides a 60/120 fps.
 */
function buildMotionDesignChoreographyContract(target: ExecutorContractTarget): string {
  if (!VISUAL_FILE_RE.test(target.path)) return ''
  return [
    '## CONTRAT DE MOTION DESIGN & CHOREGRAPHIE PHYSIQUE (60/120 FPS)',
    '- Courbes physiques obligatoires (JAMAIS `linear` ni `ease` par defaut sur l UI):',
    '  • Reveal / Entree: `cubic-bezier(0.16, 1, 0.3, 1)` (380-560ms)',
    '  • Micro-interaction / Hover / Press: `cubic-bezier(0.22, 1, 0.36, 1)` (150-220ms)',
    '  • Ressort / Badge / Toggle: `cubic-bezier(0.34, 1.56, 0.64, 1)` (260-340ms)',
    '- Choregraphie d entree en cascade (Staggered Reveal): chaque liste, grille Bento ou groupe de KPI anime son apparition avec `@keyframes auroraRevealUp` (`from { opacity: 0; transform: translate3d(0, 18px, 0) scale(0.985); } to { opacity: 1; transform: translate3d(0, 0, 0) scale(1); }`) et un delai progressif `animation-delay: calc(var(--stagger-index, 0) * 65ms)`.',
    '- Micro-interactions magnetiques & Spotlight au pointeur: sur les cartes Bento / Hero, trace la position du curseur (`onMouseMove` -> `--mouse-x`, `--mouse-y`) pour afficher un halo speculaire radial (`radial-gradient(420px circle at var(--mouse-x, 50%) var(--mouse-y, 50%), rgba(255,255,255,0.08), transparent 70%)`) et une elevation subtile `transform: translateY(-3px) scale(1.01)`.',
    '- Animations continues & Compteurs Temps Reel: utilise `requestAnimationFrame` avec interpolation amortie (`current += (target - current) * 0.12`) pour les compteurs numeriques, jauges, curseurs ou graphiques vivants — avec `cancelAnimationFrame` propre au demontage.',
    '- Dataviz & SVG vivants: anime le trace des courbes SVG via `stroke-dasharray` / `stroke-dashoffset`, ajoute un `<linearGradient>` d aire sous la courbe et un point lumineux interactif au survol.',
    '- Performance GPU & Accessibilite: n anime QUE `transform` (`translate3d`, `scale`, `rotate`) et `opacity` (zero reflow `top`/`left`/`width`/`height`). Respecte `@media (prefers-reduced-motion: reduce)`.',
  ].join('\n')
}

/**
 * Contrat d Ingenierie Backend, Performance & Architecture Robuste.
 * Livre aux fichiers serveur, API, services metier, stores et fullstack.
 */
function buildBackendEngineeringContract(intent: CodeIntent, target: ExecutorContractTarget): string {
  const isFullstackOrApiProject = /^(api_|fullstack_|ssr_)/.test(intent.projectType)
  if (!isBackendOrServiceTarget(intent, target) && !isFullstackOrApiProject) {
    return ''
  }
  return [
    '## CONTRAT D INGENIERIE BACKEND, PERFORMANCE & ARCHITECTURE HAUTE FIABILITE',
    '- Validation stricte aux frontieres: valide et type chaque payload entrant (parametres, query, body) avant toute logique metier. Retourne un statut HTTP precis (`400`/`422` validation, `401`/`403` auth, `404` ressource, `409` conflit, `500` interne) avec une enveloppe JSON uniforme `{ ok: boolean, data?: T, error?: { code: string, message: string, details?: unknown } }`.',
    '- Zero erreur silencieuse: interdiction absolue des blocs `catch {}` vides. Journalise le contexte et propage une erreur structuree.',
    '- Performance algorithmique & I/O non-bloquant:',
    '  • Indexe les collections en memoire par `Map<Id, Entity>` / `Set` pour des lectures en O(1) (jamais de `.find()` imbriques en O(N^2) dans une boucle).',
    '  • Execute les operations I/O independantes en parallele (`Promise.all` / `asyncio.gather`) avec timeout explicite (`AbortSignal.timeout`).',
    '  • Pagine toute route de liste (`limit` borne, `offset` ou `cursor`, `total`) et supporte le tri/filtrage cote serveur.',
    '  • Prevois un cache memoire (TTL ou LRU) ou memoisation sur les calculs lourds et agregations.',
    '- Securite & Coherence des donnees: requetes SQL/base 100% parametrees (zero concatenation de chaines), assainissement des entrees, mutations atomiques/idempotentes, en-tetes CORS propres et endpoint de sante/telemetrie (`/api/health` ou equivalent) retournant latence et etat reel.',
  ].join('\n')
}

/**
 * Contrat d interactivite v89b: la panne la plus frequente est un controle dont
 * la logique existe mais qui ne repeint jamais le DOM.
 */
function buildInteractivityContract(): string {
  return [
    '## CONTRAT D INTERACTIVITE — LES CONTROLES DOIVENT REELLEMENT FONCTIONNER',
    '- Tout handler qui mute des donnees (`sort`, `filter`, `splice`, `push`, changement d etat) DOIT appeler la fonction de rendu a la fin. Trier un tableau sans repeindre la vue = BUG: a l ecran rien ne bouge.',
    '- Toute donnee "temps reel"/`setInterval` boucle vraiment ET met a jour le DOM a chaque tick (valeurs ET graphiques redessines).',
    '- Chaque `<canvas>` obtient son contexte et est reellement DESSINE. Chaque conteneur rempli par JS est peuple au chargement, jamais laisse vide.',
    '- Avant de finir: pour chaque feature demandee, verifie "au clic / a la saisie, l ecran change-t-il vraiment ?". Si non, la feature est incomplete.',
  ].join('\n')
}

const TYPED_FILE_RE = /\.(tsx?|mtsx?)$/i

function typeContractBlock(): string[] {
  return [
    '## CONTRAT DE TYPAGE & FIABILITE (ce fichier)',
    '- Annote TOUT parametre de fonction et de rappel, y compris dans .map/.filter/.reduce/.sort et les gestionnaires d evenements. Aucun parametre implicitement `any`.',
    '- Rendre un composant, c est honorer son interface: passe EXACTEMENT les props qu elle declare — aucune requise omise, aucune non declaree ajoutee. Si la donnee existe deja dans ce fichier, passe-la; sinon rends la prop optionnelle a la declaration.',
    '- Les donnees d exemple et l interface qui les type s ecrivent ENSEMBLE et au meme moment: tout champ present dans la donnee figure dans l interface, et reciproquement.',
    '- Une union de statuts se compare toujours a ses propres valeurs, jamais a un libelle affiche. Garde les valeurs techniques dans une seule langue et traduis pour l affichage.',
    '- Pour les timers React/browser, type avec `ReturnType<typeof setInterval>` ou `number` (jamais le namespace `NodeJS.Timeout`).',
    '- Pour les graphiques/dataviz, privilégie des visualisations vectorielles directes en pur SVG/React ou CSS (autonomes, réactives et sans dépendance tierce complexe).',
  ]
}

export function buildExecutorQualityContract(args: {
  intent: CodeIntent
  prompt: string
  target: ExecutorContractTarget
  maxChars?: number
}): string {
  const { intent, prompt, target } = args
  const visualProject = isVisualProject(intent.projectType)
  const visualTarget = visualProject && isVisualTarget(target)
  const backendTarget = isBackendOrServiceTarget(intent, target)
  const budget = args.maxChars
    ?? (visualTarget
      ? EXECUTOR_QUALITY_CONTRACT_MAX_CHARS
      : backendTarget
        ? EXECUTOR_QUALITY_CONTRACT_BACKEND_MAX_CHARS
        : EXECUTOR_QUALITY_CONTRACT_CONFIG_MAX_CHARS)

  const sections: string[] = []

  // 1. Verrouillage sujet/marque — regle dure, toujours en tete quand il
  // existe, mais seulement sur un fichier qui peut porter du contenu de marque
  // (markup, script, style). Un fichier de config ne porte ni copy ni palette.
  const subjectLock = visualTarget ? buildSubjectLockBlock(intent) : ''
  if (subjectLock) sections.push(subjectLock)

  // 2. Contrat de livraison — ce qui evite les regenerations pour entree absente.
  sections.push(buildDeliveryEssentials(intent))

  // 2bis. Typage: place AVANT les blocs esthetiques pour ne pas etre tronque
  // par le budget — c est ce qui arrivait aux seuils typographiques.
  if (TYPED_FILE_RE.test(target.path)) sections.push(typeContractBlock().join('\n'))

  // 2ter. Contrat Backend Haute Performance & Architecture (si fichier backend/service/API ou projet fullstack/api)
  const backendContract = buildBackendEngineeringContract(intent, target)
  if (backendContract) sections.push(backendContract)

  // 3+4. Esthetique & Motion Design: sur tout fichier visuel (.html, .css, .tsx, .jsx, .vue, .svelte).
  if (visualTarget) {
    if (MARKUP_FILE_RE.test(target.path) || STYLE_FILE_RE.test(target.path) || SCRIPT_FILE_RE.test(target.path)) {
      sections.push(typographyContractBlock().join('\n'))
    }
    sections.push(buildVisualBar(target))
    const motionContract = buildMotionDesignChoreographyContract(target)
    if (motionContract) sections.push(motionContract)
    const archetype = detectDesignArchetype(prompt, intent)
    const archetypeLines = archetypeBlock(archetype, intent)
    if (archetypeLines.length > 0) {
      sections.push([`## ARCHETYPE RETENU: ${archetype}`, ...archetypeLines].join('\n'))
    }
    const depth = depthDirectivesBlock(intent)
    if (depth.length > 0) sections.push(depth.join('\n'))
    if (SCRIPT_FILE_RE.test(target.path) || MARKUP_FILE_RE.test(target.path)) {
      sections.push(buildInteractivityContract())
      sections.push(autoDepsBlock().join('\n'))
    }
  }

  // Assemblage borne: on ajoute section par section tant que le budget tient,
  // et on coupe la derniere sur une frontiere de ligne.
  const out: string[] = []
  let used = 0
  for (const section of sections) {
    if (used >= budget) break
    const remaining = budget - used
    const piece = section.length <= remaining ? section : capBlock(section, remaining)
    if (!piece.trim()) continue
    out.push(piece)
    used += piece.length + 2
  }
  return out.join('\n\n')
}
