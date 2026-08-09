// ---------------------------------------------------------------------------
// codeProjectTypeStackContract — le type de projet detecte devient CONTRAIGNANT.
//
// Defaut observe en run reel: l intention est `static_web`, et l architecte
// rend un plan Next.js (`src/app/layout.tsx`, `next.config.js`,
// `tailwind.config.ts`) sans `index.html`. Deux mecanismes s additionnaient.
//
// 1. Le prompt de planification ne fait qu INFORMER: « Projet detecte:
//    static_web ». Puis il demande « quelles sont les meilleures
//    librairies/outils/patterns » et « les solutions les plus modernes », ce qui
//    invite explicitement le modele a choisir une stack — donc a contredire le
//    type detecte.
//
// 2. Le score de selection (`scoreArchitecturePlan`) recompense PLUS de
//    fichiers, PLUS de dependances, PLUS de scripts. Un candidat Next.js
//    obtient donc mecaniquement un meilleur score qu un candidat statique
//    correct. Le mauvais plan gagnait par construction.
//
// Ce module rend le type contraignant des deux cotes: un bloc de contrat pour
// le prompt, et une mesure de conformite deterministe pour la selection. La
// non-conformite est PENALISEE, jamais rejetee: si tous les candidats derivent,
// mieux vaut le moins mauvais qu aucun plan.
// ---------------------------------------------------------------------------

import type { CodeArchitecturePlan } from './codeArchitecturePlan.ts'
import { requiredEntryFilesForProject } from './codeArchitecturePlanEntryContract.ts'
import type { CodeIntent, CodeProjectType } from './codeIntentTypes.ts'

/** Marqueurs de fichiers qui trahissent une stack incompatible avec le type. */
const FORBIDDEN_MARKERS: Partial<Record<CodeProjectType, RegExp[]>> = {
  static_web: [
    /(^|\/)next\.config\.[cm]?[jt]s$/i,
    /(^|\/)nuxt\.config\.[cm]?[jt]s$/i,
    /(^|\/)remix\.config\.[cm]?[jt]s$/i,
    /(^|\/)angular\.json$/i,
    /(^|\/)src\/app\/(layout|page)\.[jt]sx?$/i,
    /(^|\/)pages\/_app\.[jt]sx?$/i,
  ],
  game_web: [
    /(^|\/)next\.config\.[cm]?[jt]s$/i,
    /(^|\/)src\/app\/(layout|page)\.[jt]sx?$/i,
  ],
  cli_python: [/(^|\/)package\.json$/i, /(^|\/)index\.html$/i],
  cli_node: [/(^|\/)index\.html$/i],
  api_fastapi: [/(^|\/)index\.html$/i],
  api_flask: [/(^|\/)index\.html$/i],
}

/** Description courte de la stack imposee, pour le prompt. */
const STACK_SENTENCE: Partial<Record<CodeProjectType, string>> = {
  static_web:
    'HTML/CSS/JS natifs servis tels quels. AUCUN framework applicatif (pas de Next.js, Nuxt, Remix, Angular), AUCUN routeur applicatif, AUCUNE etape de build obligatoire. La page doit s ouvrir directement depuis `index.html`.',
  game_web:
    'HTML/CSS/JS natifs avec `<canvas>`. Aucun framework applicatif; la boucle de jeu est du JS direct.',
  spa_react: 'React avec un point d entree `index.html` + `package.json`. Pas de SSR.',
  spa_vue: 'Vue avec un point d entree `index.html` + `package.json`. Pas de SSR.',
  ssr_nextjs: 'Next.js avec `package.json`. Le routeur applicatif est attendu ici.',
  cli_python: 'Python en ligne de commande. Aucun fichier web, aucun `package.json`.',
  cli_node: 'Node en ligne de commande. Aucun fichier HTML.',
}

export type ProjectTypeConformity = {
  conform: boolean
  violations: string[]
  missingEntryFiles: string[]
}

/**
 * Mesure deterministe: le plan respecte-t-il le type de projet detecte ?
 */
export function checkPlanProjectTypeConformity(
  plan: CodeArchitecturePlan,
  intent: CodeIntent,
): ProjectTypeConformity {
  const type = intent.projectType
  const paths = plan.files.map((file) => file.path.replace(/\\/g, '/'))

  const forbidden = FORBIDDEN_MARKERS[type] ?? []
  const violations = paths.filter((path) => forbidden.some((re) => re.test(path)))

  const entries = requiredEntryFilesForProject(type)
  const missingEntryFiles = entries.filter(
    (entry) => !paths.some((p) => p.toLowerCase() === entry.toLowerCase()),
  )

  // Le plan qui se declare d un autre type que l intention est une derive nette.
  if (plan.projectType && plan.projectType !== type) {
    violations.push(`plan.projectType=${plan.projectType}`)
  }

  return {
    conform: violations.length === 0 && missingEntryFiles.length === 0,
    violations,
    missingEntryFiles,
  }
}

/**
 * Penalite de score pour non-conformite.
 *
 * Calibree pour renverser le biais structurel du scoreur, qui recompense les
 * plans les plus lourds: un plan Next.js pour un `static_web` ne doit plus
 * pouvoir battre un plan statique correct simplement parce qu il a plus de
 * fichiers et plus de dependances.
 */
export function projectTypeConformityPenalty(
  plan: CodeArchitecturePlan,
  intent: CodeIntent,
): number {
  const report = checkPlanProjectTypeConformity(plan, intent)
  return report.violations.length * 40 + report.missingEntryFiles.length * 25
}

/**
 * Bloc de contrat injecte dans le prompt de planification.
 *
 * Le type cesse d etre une information et devient une contrainte, avec ses
 * fichiers d entree obligatoires et ses interdits explicites.
 */
export function buildProjectTypeStackContract(intent: CodeIntent): string {
  const type = intent.projectType
  const entries = requiredEntryFilesForProject(type)
  const sentence = STACK_SENTENCE[type]
  const forbidden = FORBIDDEN_MARKERS[type] ?? []

  const lines = [
    '## TYPE DE PROJET — CONTRAINTE, PAS SUGGESTION',
    '',
    `Le type de projet est IMPOSE: \`${type}\`. Il a ete determine en amont et tu ne peux pas en changer.`,
    'Le champ `projectType` de ton JSON doit valoir EXACTEMENT cette valeur.',
  ]
  if (sentence) lines.push(`Stack imposee: ${sentence}`)
  if (entries.length > 0) {
    lines.push(
      `Fichiers d entree OBLIGATOIRES dans \`files\`: ${entries.map((e) => `\`${e}\``).join(', ')}. Un plan sans eux est rejete.`,
    )
  }
  if (forbidden.length > 0) {
    lines.push(
      'INTERDIT pour ce type: tout fichier de configuration ou de routage d un framework applicatif etranger a la stack imposee (par exemple `next.config.js`, `src/app/layout.tsx`, `angular.json`).',
    )
  }
  lines.push(
    '',
    'La question « quelle est la stack la plus moderne » ne s applique QU A L INTERIEUR de cette contrainte:',
    'tu choisis les meilleures pratiques, les effets et la qualite du code, jamais un autre type de projet.',
  )
  return lines.join('\n')
}
