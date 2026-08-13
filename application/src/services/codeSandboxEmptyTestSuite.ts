// ---------------------------------------------------------------------------
// codeSandboxEmptyTestSuite — une suite de tests ABSENTE n est pas une suite de
// tests en echec.
//
// Run 1091, mesure dans le conteneur reel:
//
//   $ npm run test        # "test": "vitest"
//   No test files found, exiting with code 1
//
// Le projet declare un script `test` mais ne contient aucun fichier de test.
// Le code de sortie 1 faisait echouer l etape « Verifier test », donc
// `isDeliveryRunnable` renvoyait false, donc `phase: 'error'` — pour TOUT projet
// qui declare un script de test sans en ecrire. La boucle de correction, elle,
// ne peut rien y faire: ecrire une suite de tests que le brief n a jamais
// demandee n est pas une correction, c est un autre projet.
//
// C est la meme regle que pour les preuves d isolation et le quota disque:
// **une porte ne condamne pas ce qu elle n a pas pu mesurer.** Un lanceur qui
// dit « je n ai trouvé aucun test » n a rien mesure du code livre.
//
// Ce qui NE change pas: un test qui existe et qui ECHOUE reste bloquant. On ne
// neutralise que l absence, jamais l echec.
// ---------------------------------------------------------------------------

/**
 * Signatures des lanceurs quand ils ne trouvent AUCUN test. Volontairement
 * etroites: chacune est un message ou le lanceur declare explicitement n avoir
 * rien execute. Aucune ne peut correspondre a un test rouge.
 */
const EMPTY_SUITE_PATTERNS: RegExp[] = [
  // vitest / jest
  /no test files found/i,
  /no tests found/i,
  /no test suites found/i,
  /found no test files/i,
  // pytest
  /no tests ran/i,
  /collected 0 items/i,
  // go
  /no test files/i,
  /\[no test files\]/i,
  // cargo
  /running 0 tests/i,
  // mocha / node:test
  /0 passing\b/i,
  /^#\s*tests\s+0$/im,
]

/** Le lanceur declare-t-il n avoir trouve aucun test a executer ? */
export function isEmptyTestSuiteOutput(output: string | null | undefined): boolean {
  const text = (output ?? '').trim()
  if (!text) return false
  return EMPTY_SUITE_PATTERNS.some((pattern) => pattern.test(text))
}

/** L etape est-elle une execution de suite de tests ? */
export function isTestCommandLabel(label: string | null | undefined): boolean {
  return /(^|\s)(verifier\s+test|tests?)(\s|$)|\btest\b/i.test(label ?? '')
}

export type EmptyTestSuiteVerdict = {
  /** Faut-il requalifier l etape en « non applicable » ? */
  notApplicable: boolean
  output: string
}

/**
 * Requalifie une etape de test ECHOUEE dont la sortie prouve qu aucun test n a
 * ete trouve. Toute autre sortie est laissee intacte: un test rouge reste rouge.
 */
export function reclassifyEmptyTestSuiteStep(args: {
  label: string
  ok: boolean
  output: string
}): EmptyTestSuiteVerdict {
  if (args.ok) return { notApplicable: false, output: args.output }
  if (!isTestCommandLabel(args.label)) return { notApplicable: false, output: args.output }
  if (!isEmptyTestSuiteOutput(args.output)) return { notApplicable: false, output: args.output }

  return {
    notApplicable: true,
    output: [
      'SUITE DE TESTS ABSENTE — non applicable.',
      'Le lanceur declare n avoir trouve aucun fichier de test: il n a donc rien mesure du code livre.',
      'Une suite absente n est pas une suite en echec, et aucune correction du code ne la ferait apparaitre.',
      'Un test qui existe et qui echoue reste, lui, bloquant.',
      '',
      args.output,
    ].join('\n'),
  }
}
