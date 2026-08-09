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

import type { CodeIntent } from './codeIntent'
import { detectDesignArchetype } from './codeDesignDirectives.ts'
import { archetypeBlock } from './codeDesignDirectiveBlocks.ts'
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
export const EXECUTOR_QUALITY_CONTRACT_MAX_CHARS = 12_000
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

/**
 * Fichier de configuration / metadonnees: aucune directive esthetique n a de
 * sens dessus, et l y injecter gaspille du contexte a chaque appel.
 */
function isVisualTarget(target: ExecutorContractTarget): boolean {
  const p = target.path || ''
  if (CONFIG_BASENAME_RE.test(p)) return false
  return VISUAL_FILE_RE.test(p)
}

/**
 * Fichiers d entree obligatoires par type de projet. C est exactement ce qui
 * manquait au run Mercedes: le modele ne savait pas que `index.html` etait
 * non negociable pour un `static_web`.
 */
function requiredEntryFiles(intent: CodeIntent): string[] {
  switch (intent.projectType) {
    case 'static_web':
      return ['index.html']
    case 'spa_react':
    case 'spa_vue':
    case 'spa_angular':
    case 'spa_svelte':
      return ['index.html', 'package.json']
    case 'ssr_nextjs':
    case 'fullstack_nextjs':
      return ['package.json']
    case 'game_web':
      return ['index.html']
    default:
      return []
  }
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
 * Barre de qualite visuelle condensee. Version courte et haute densite du
 * contrat design complet: on garde les regles qui changent le rendu, on retire
 * la pedagogie.
 */
function buildVisualBar(target: ExecutorContractTarget): string {
  const lines = [
    '## BARRE DE QUALITE VISUELLE — NIVEAU INGENIEUR PRODUIT SENIOR',
    '- Reference: Linear / Vercel / Stripe / Arc / Apple. Un rendu type Bootstrap, theme WordPress ou tutoriel YouTube est un ECHEC et sera rejete.',
    '- UN SEUL accent chromatique (un second uniquement en focus state ou dataviz). Couleurs en `oklch()`/`hsl()`, jamais `red`/`blue` nommes.',
    '- Neutres: rampe teintee, jamais `#000` ni `#fff` purs sur les surfaces. Bordures `rgba(...,0.06-0.08)`, jamais `1px solid #ddd`.',
    '- Typographie: display tendu ou serif italic, body 14-16px line-height 1.55-1.65, mono uppercase letter-spacing 0.08em pour les kickers. Echelle 12/14/16/20/28/40/56/72/96.',
    '- Tracking negatif sur les gros titres (-0.04em au-dela de 56px). Mesure de ligne 60-70 caracteres sur la prose.',
  ]
  if (STYLE_FILE_RE.test(target.path) || MARKUP_FILE_RE.test(target.path)) {
    lines.push(
      '- Layout: grille 12 colonnes avec col-span ASYMETRIQUES (jamais `auto-fit` uniforme partout). Sections `padding-block: clamp(80px, 12vw, 160px)`.',
      '- Espacement par tokens 4-base et `gap` sur le parent — jamais un `margin-top: 10px` arbitraire.',
      '- Motion: easing tokens explicites (`cubic-bezier(0.16,1,0.3,1)`), 120-180ms en micro-hover, 240-360ms en reveal, hover scale 1.02 max, stagger 60-90ms.',
      '- Aucun ecran 100% plat: au moins un effet de profondeur (parallax multi-couches, mesh gradient blur, chevauchement z-index avec ombres composites).',
    )
  }
  return lines.join('\n')
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

/**
 * Construit le contrat qualite compact injecte dans le prompt SYSTEME de
 * l executor WS3, pour le fichier en cours de production.
 *
 * Ordre de priorite si le budget sature (le verrouillage sujet passe en
 * premier: la fidelite de marque est une regle dure du module).
 */
export function buildExecutorQualityContract(args: {
  intent: CodeIntent
  prompt: string
  target: ExecutorContractTarget
  maxChars?: number
}): string {
  const { intent, prompt, target } = args
  const visualProject = isVisualProject(intent.projectType)
  const visualTarget = visualProject && isVisualTarget(target)
  const budget = args.maxChars
    ?? (visualTarget ? EXECUTOR_QUALITY_CONTRACT_MAX_CHARS : EXECUTOR_QUALITY_CONTRACT_CONFIG_MAX_CHARS)

  const sections: string[] = []

  // 1. Verrouillage sujet/marque — regle dure, toujours en tete quand il
  // existe, mais seulement sur un fichier qui peut porter du contenu de marque
  // (markup, script, style). Un fichier de config ne porte ni copy ni palette.
  const subjectLock = visualTarget ? buildSubjectLockBlock(intent) : ''
  if (subjectLock) sections.push(subjectLock)

  // 2. Contrat de livraison — ce qui evite les regenerations pour entree absente.
  sections.push(buildDeliveryEssentials(intent))

  // 3+4. Esthetique: uniquement sur un fichier reellement visuel.
  if (visualTarget) {
    sections.push(buildVisualBar(target))
    const archetype = detectDesignArchetype(prompt, intent)
    const archetypeLines = archetypeBlock(archetype, intent)
    if (archetypeLines.length > 0) {
      sections.push([`## ARCHETYPE RETENU: ${archetype}`, ...archetypeLines].join('\n'))
    }
    if (SCRIPT_FILE_RE.test(target.path) || MARKUP_FILE_RE.test(target.path)) {
      sections.push(buildInteractivityContract())
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
