// ---------------------------------------------------------------------------
// codeTestToolchainContract — la file produit des tests, elle doit produire de
// quoi les compiler et les lancer.
//
// Mesure sur le run 1191 (livrable reel, 39 fichiers): le pipeline a ecrit
// `src/tests/App.test.tsx`, `HomePage.test.tsx` et `Navigation.test.tsx`, et le
// manifeste declarait bien `jest` — mais PAS ses types. Le script `lint` du
// projet lance `tsc --noEmit`, qui compile donc les tests:
//
//   src/tests/Navigation.test.tsx(5,1):  TS2582 Cannot find name 'describe'.
//   src/tests/Navigation.test.tsx(23,3): TS2582 Cannot find name 'test'.
//   src/tests/Navigation.test.tsx(30,5): TS2304 Cannot find name 'expect'.
//
// tsc NOMME lui-meme le correctif: « Try `npm i --save-dev @types/jest` ». Rien
// a deviner, donc rien a confier a un modele.
//
// Deuxieme defaut du meme manifeste, plus couteux et jamais diagnostique:
//
//   "test": "jest --watchAll"
//
// `--watchAll` NE REND JAMAIS LA MAIN. Dans un sandbox non interactif, cette
// etape ne peut que consommer son delai entier puis etre tuee — et un pas tue
// est exactement le pas muet que ce module vient de rendre audible. On ne
// laisse pas une commande de veille dans un plan de validation automatique.
//
// C est la famille deja fermee deux fois ici (binaires manquants, codegen sans
// generateur): la file emet un fichier dont le CONTRAT n est pas satisfait. La
// reponse est la meme — completer le contrat, mecaniquement.
// ---------------------------------------------------------------------------

import type { CodeFile } from './codeSandboxTypes.ts'

export type TestRunner = 'jest' | 'vitest' | 'mocha' | null

const TEST_FILE_PATTERN = /(?:^|\/)(?:__tests__\/.*|.*\.(?:test|spec))\.(?:[cm]?[jt]sx?)$/i

export function isTestFile(name: string): boolean {
  return TEST_FILE_PATTERN.test(name.replace(/\\/g, '/'))
}

export function hasTestFiles(files: CodeFile[]): boolean {
  return files.some((file) => isTestFile(file.name))
}

/** Types fournis par le lanceur lui-meme: rien a ajouter dans ces cas. */
const RUNNER_SELF_TYPED: Record<string, boolean> = { vitest: true, jest: false, mocha: false }

/** Paquet de types qui declare `describe` / `test` / `expect` en global. */
export const RUNNER_TYPES_PACKAGE: Record<string, string> = {
  jest: '@types/jest',
  mocha: '@types/mocha',
}

export function detectTestRunner(manifest: Record<string, unknown>): TestRunner {
  const declared = new Set<string>()
  for (const section of ['dependencies', 'devDependencies'] as const) {
    const deps = manifest[section]
    if (deps && typeof deps === 'object' && !Array.isArray(deps)) {
      for (const name of Object.keys(deps as Record<string, unknown>)) declared.add(name)
    }
  }
  const scripts = manifest.scripts && typeof manifest.scripts === 'object'
    ? (manifest.scripts as Record<string, unknown>)
    : {}
  const testScript = typeof scripts.test === 'string' ? scripts.test : ''

  for (const runner of ['vitest', 'jest', 'mocha'] as const) {
    if (declared.has(runner) || new RegExp(`\\b${runner}\\b`).test(testScript)) return runner
  }
  return null
}

/**
 * Reecrit un script de test qui NE REND PAS LA MAIN.
 *
 * On ne touche qu aux drapeaux de veille connus, et on n invente aucune option:
 * `vitest` sans sous-commande observe par defaut, d ou `vitest run`.
 */
export function makeTestScriptNonWatching(script: string): string {
  if (!script) return script
  let next = script
    .replace(/\s--watchAll(?:=true)?\b/g, '')
    .replace(/\s--watch\b(?!-)/g, '')
    .replace(/\s-w\b/g, '')
    .trim()
  if (/\bvitest\b/.test(next) && !/\bvitest\s+(?:run|related|bench)\b/.test(next)) {
    next = next.replace(/\bvitest\b/, 'vitest run')
  }
  return next
}

export type TestToolchainFix = {
  addDevDependencies: Record<string, string>
  testScript: string | null
  notes: string[]
}

/**
 * Ce qui MANQUE au manifeste pour que les tests emis compilent et se terminent.
 *
 * Ne propose rien si aucun test n a ete emis, et ne remplace jamais une
 * declaration existante — on complete, on ne redecide pas a la place du modele.
 */
export function planTestToolchainFix(
  files: CodeFile[],
  manifest: Record<string, unknown>,
): TestToolchainFix | null {
  if (!hasTestFiles(files)) return null

  const runner = detectTestRunner(manifest)
  if (!runner) return null

  const addDevDependencies: Record<string, string> = {}
  const notes: string[] = []

  const typesPackage = RUNNER_TYPES_PACKAGE[runner]
  if (typesPackage && !RUNNER_SELF_TYPED[runner]) {
    const devDeps = manifest.devDependencies && typeof manifest.devDependencies === 'object'
      ? (manifest.devDependencies as Record<string, unknown>)
      : {}
    const deps = manifest.dependencies && typeof manifest.dependencies === 'object'
      ? (manifest.dependencies as Record<string, unknown>)
      : {}
    if (!(typesPackage in devDeps) && !(typesPackage in deps)) {
      addDevDependencies[typesPackage] = runner === 'jest' ? '^29.5.14' : '^10.0.10'
      notes.push(
        `${typesPackage} ajoute: des fichiers de test sont livres et \`tsc\` ne connait ni describe ni expect sans lui`,
      )
    }
  }

  const scripts = manifest.scripts && typeof manifest.scripts === 'object'
    ? (manifest.scripts as Record<string, unknown>)
    : {}
  const currentTestScript = typeof scripts.test === 'string' ? scripts.test : ''
  const nextTestScript = makeTestScriptNonWatching(currentTestScript)
  const testScript = nextTestScript && nextTestScript !== currentTestScript ? nextTestScript : null
  if (testScript) {
    notes.push(
      `script test: \`${currentTestScript}\` -> \`${testScript}\` (un mode veille ne rend jamais la main dans un sandbox)`,
    )
  }

  if (Object.keys(addDevDependencies).length === 0 && !testScript) return null
  return { addDevDependencies, testScript, notes }
}

/** Applique le plan au manifeste. Fonction pure. */
export function applyTestToolchainFix(
  manifest: Record<string, unknown>,
  fix: TestToolchainFix,
): Record<string, unknown> {
  const next = { ...manifest }
  if (Object.keys(fix.addDevDependencies).length > 0) {
    const devDeps = next.devDependencies && typeof next.devDependencies === 'object' && !Array.isArray(next.devDependencies)
      ? { ...(next.devDependencies as Record<string, unknown>) }
      : {}
    for (const [name, spec] of Object.entries(fix.addDevDependencies)) {
      if (!(name in devDeps)) devDeps[name] = spec
    }
    next.devDependencies = devDeps
  }
  if (fix.testScript) {
    const scripts = next.scripts && typeof next.scripts === 'object' && !Array.isArray(next.scripts)
      ? { ...(next.scripts as Record<string, unknown>) }
      : {}
    scripts.test = fix.testScript
    next.scripts = scripts
  }
  return next
}
