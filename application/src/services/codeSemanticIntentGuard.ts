// ---------------------------------------------------------------------------
// codeSemanticIntentGuard — empeche le classifieur LLM de renverser une
// detection lexicale solide avec une hallucination.
//
// Observe en run reel: le prompt « landing page premium pour la marque
// Mercedes-Benz, hero anime, section specs, formulaire de contact, responsive »
// a ete classe `ide` (editeur de code) par le modele semantique, avec une
// confiance au-dessus du seuil. `runIntentPhase` acceptait ce verdict SANS
// aucun controle et remplacait l heuristique, qui avait pourtant repondu
// `static_web` — la bonne reponse.
//
// L impact n est pas cosmetique: le projectType pilote l archetype design, le
// contrat de livraison (index.html obligatoire ou non), les directives, les
// commandes dev/build et les templates. Un `ide` a la place d un `static_web`
// produit une page sans page d entree et un design d editeur de code.
//
// Pire, c est non deterministe: le MEME prompt a garde `static_web` sur un run
// (classifieur en timeout) et bascule sur `ide` au run suivant. Deux livraisons
// differentes pour une demande identique, quel que soit le canal.
//
// Le classifieur semantique reste utile — il couvre les types exotiques que les
// regex ne voient pas (compiler, os_kernel, embedded, distributed_system). La
// regle retenue ne le desactive donc pas: elle lui interdit seulement de
// contredire une heuristique confiante SANS le moindre indice lexical.
// ---------------------------------------------------------------------------

import { normalizeSignalText } from './codeIntentSignalUtils.ts'
import type { CodeIntent, CodeProjectType } from './codeIntentTypes.ts'

/**
 * Types que l heuristique produit quand elle n a rien reconnu de precis. Dans
 * ce cas le modele semantique apporte de l information: on le laisse decider.
 */
const LOW_INFORMATION_TYPES = new Set<CodeProjectType>(['unknown', 'script'])

type Family =
  | 'web' | 'api' | 'cli' | 'desktop' | 'mobile' | 'library'
  | 'game' | 'system' | 'data' | 'tool' | 'misc'

const FAMILY_OF: Partial<Record<CodeProjectType, Family>> = {
  static_web: 'web', spa_react: 'web', spa_vue: 'web', spa_angular: 'web', spa_svelte: 'web',
  ssr_nextjs: 'web', ssr_nuxt: 'web', ssr_remix: 'web',
  fullstack_mern: 'web', fullstack_nextjs: 'web', fullstack_django: 'web', fullstack_rails: 'web',
  api_express: 'api', api_fastapi: 'api', api_django: 'api', api_flask: 'api',
  api_spring: 'api', api_gin: 'api', api_actix: 'api', api_dotnet: 'api',
  cli_node: 'cli', cli_python: 'cli', cli_rust: 'cli', cli_go: 'cli', cli_cpp: 'cli',
  desktop_electron: 'desktop', desktop_tauri: 'desktop', desktop_app: 'desktop',
  mobile_rn: 'mobile', mobile_flutter: 'mobile', mobile_ios: 'mobile', mobile_android: 'mobile',
  library_npm: 'library', library_pypi: 'library', library_crate: 'library',
  game_web: 'game', game_unity: 'game', engine_3d: 'game',
  system_c: 'system', system_cpp: 'system', system_rust: 'system',
  os_kernel: 'system', compiler: 'system', distributed_system: 'system',
  embedded_esp32: 'system', embedded_arduino: 'system',
  data_python: 'data', devops_docker: 'data',
  ide: 'tool',
  script: 'misc', unknown: 'misc',
}

export function codeProjectFamily(type: CodeProjectType): Family {
  return FAMILY_OF[type] ?? 'misc'
}

/**
 * Indices lexicaux exiges pour qu un basculement de famille soit credible.
 * Volontairement larges (FR + EN) : le but n est pas de re-implementer la
 * classification, seulement d exiger qu au moins UN mot du prompt aille dans le
 * sens du verdict du modele.
 */
const FAMILY_EVIDENCE: Record<Family, string[]> = {
  web: [
    'site', 'web', 'page', 'landing', 'html', 'css', 'front', 'frontend',
    'react', 'vue', 'angular', 'svelte', 'next', 'nuxt', 'remix', 'dashboard',
    'portfolio', 'blog', 'boutique', 'ecommerce', 'responsive', 'navigateur',
  ],
  api: [
    'api', 'rest', 'graphql', 'endpoint', 'backend', 'serveur', 'server',
    'microservice', 'express', 'fastapi', 'django', 'flask', 'spring', 'webhook',
  ],
  cli: [
    'cli', 'ligne de commande', 'command line', 'terminal', 'script shell',
    'outil en ligne', 'argparse', 'commande',
  ],
  desktop: [
    'desktop', 'bureau', 'electron', 'tauri', 'application native',
    'logiciel windows', 'logiciel mac', 'fenetre', 'application de bureau',
  ],
  mobile: [
    'mobile', 'android', 'ios', 'iphone', 'smartphone', 'react native',
    'flutter', 'application mobile', 'apk', 'play store', 'app store',
  ],
  library: [
    'librairie', 'library', 'bibliotheque', 'package', 'module npm',
    'paquet pypi', 'crate', 'sdk', 'publier sur npm',
  ],
  game: [
    'jeu', 'game', 'gameplay', 'joueur', 'player', 'score', 'niveau', 'level',
    'sprite', 'unity', 'godot', 'moteur 3d', 'engine', 'pong', 'arcade',
  ],
  system: [
    'kernel', 'noyau', 'os ', 'systeme d exploitation', 'operating system',
    'bootloader', 'compilateur', 'compiler', 'lexer', 'parser', 'ast',
    'interpreteur', 'interpreter', 'bare metal', 'embarque', 'embedded',
    'esp32', 'arduino', 'firmware', 'microcontroleur', 'distribue',
    'distributed', 'consensus', 'raft', 'driver', 'assembleur', 'assembly',
  ],
  data: [
    'data', 'donnees', 'csv', 'pandas', 'dataset', 'etl', 'notebook',
    'machine learning', 'docker', 'kubernetes', 'ci/cd', 'pipeline de donnees',
  ],
  tool: [
    'ide', 'editeur de code', 'code editor', 'vscode', 'vs code', 'monaco',
    'file tree', 'arborescence de fichiers', 'terminal integre', 'debugger',
    'coloration syntaxique', 'syntax highlighting',
  ],
  misc: [],
}

export type SemanticIntentDecision = {
  accept: boolean
  reason:
    | 'same_type'
    | 'heuristic_low_information'
    | 'same_family'
    | 'cross_family_corroborated'
    | 'cross_family_unsupported'
}

/**
 * Decide si le verdict du classifieur semantique doit remplacer l heuristique.
 *
 * Le modele garde la main quand il apporte de l information (heuristique muette)
 * ou quand il affine dans la meme famille (static_web -> spa_react). Il la perd
 * quand il change de famille sans qu un seul mot du prompt ne le soutienne.
 */
export function decideSemanticIntentOverride(args: {
  prompt: string
  heuristic: CodeIntent
  semantic: CodeIntent
}): SemanticIntentDecision {
  const heuristicType = args.heuristic.projectType
  const semanticType = args.semantic.projectType

  if (heuristicType === semanticType) return { accept: true, reason: 'same_type' }
  if (LOW_INFORMATION_TYPES.has(heuristicType)) {
    return { accept: true, reason: 'heuristic_low_information' }
  }

  const heuristicFamily = codeProjectFamily(heuristicType)
  const semanticFamily = codeProjectFamily(semanticType)
  if (heuristicFamily === semanticFamily) return { accept: true, reason: 'same_family' }

  const text = normalizeSignalText(args.prompt)
  const evidence = FAMILY_EVIDENCE[semanticFamily] ?? []
  const corroborated = evidence.some((token) => text.includes(token))
  return corroborated
    ? { accept: true, reason: 'cross_family_corroborated' }
    : { accept: false, reason: 'cross_family_unsupported' }
}
