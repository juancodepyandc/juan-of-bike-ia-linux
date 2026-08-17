import assert from 'node:assert/strict'
import { describe, test } from 'node:test'

import {
  isNpmNoiseLine,
  isResourceExhaustionOutput,
  normalizeNpmStepOutput,
  stripNpmNoise,
} from '../services/codeNpmDiagnostics.ts'
import { isNonDiagnosticFailure, isSandboxInfrastructureFailure } from '../services/codeInfrastructureFailure.ts'
import {
  applyTestToolchainFix,
  detectTestRunner,
  hasTestFiles,
  makeTestScriptNonWatching,
  planTestToolchainFix,
} from '../services/codeTestToolchainContract.ts'
import { parseCodeFiles } from '../services/codeGeneratedFileParser.ts'
import { isStructuredProjectEmission, serializeProjectTreeEmission } from '../services/codeProjectEmission.ts'

// Sortie npm REELLE du run 1191 (passe 3), recopiee du flux NDJSON.
const NPM_WARN_ONLY = [
  'npm warn deprecated inflight@1.0.6: This module is not supported, and leaks memory. Do not use it.',
  'npm warn deprecated glob@7.2.3: Old versions of glob are not supported, and contain widely publicized security vulnerabilities.',
  'npm notice',
  'npm notice New major version of npm available! 10.9.8 -> 12.0.2',
  'npm notice',
  'npm error A complete log of this run can be found in: /home/aurora/.npm/_logs/2026-08-17T22_34_47_270Z-debug-0.log',
].join('\n')

// Sortie npm REELLE du run 1191 (passe 2): la vraie cause etait la, lisible.
const NPM_ENOSPC = [
  'npm warn deprecated inflight@1.0.6: This module is not supported, and leaks memory.',
  'npm error code ENOSPC',
  'npm error syscall write',
  'npm error errno -28',
  'npm error nospc ENOSPC: no space left on device, write',
  'npm error nospc There appears to be insufficient space on your system to finish.',
  'npm notice',
].join('\n')

describe('run 1191 — le bruit npm n est pas une erreur', () => {
  test('warn et notice sont reconnus comme du bruit, pas les erreurs', () => {
    assert.ok(isNpmNoiseLine('npm warn deprecated glob@7.2.3: Old versions...'))
    assert.ok(isNpmNoiseLine('npm notice New major version of npm available!'))
    assert.ok(isNpmNoiseLine('npm error A complete log of this run can be found in: /x.log'))
    assert.equal(isNpmNoiseLine('npm error code ENOSPC'), false)
    assert.equal(isNpmNoiseLine("npm error notarget No matching version found for react@^99.0.0."), false)
    assert.equal(isNpmNoiseLine('src/App.tsx(3,1): error TS2304'), false)
  })

  test('une sortie faite QUE d avertissements ne decrit aucun defaut', () => {
    const { text, removed } = stripNpmNoise(NPM_WARN_ONLY)
    assert.equal(text, '')
    assert.equal(removed, 6)
    const normalized = normalizeNpmStepOutput({ output: NPM_WARN_ONLY, ok: false })
    // Le point exact qui a brule trois passes du run 1191: le modele recevait
    // « inflight@1.0.6 et glob@7.2.3 » et croyait devoir les corriger.
    assert.doesNotMatch(normalized, /inflight/)
    assert.doesNotMatch(normalized, /glob@7\.2\.3/)
    assert.ok(isNonDiagnosticFailure(normalized), 'aucune correction ne peut en sortir')
  })

  test('une etape qui a REUSSI garde sa sortie intacte', () => {
    const ok = normalizeNpmStepOutput({ output: NPM_WARN_ONLY, ok: true })
    assert.equal(ok, NPM_WARN_ONLY)
  })

  test('une vraie erreur npm traverse le filtre sans etre touchee', () => {
    const reel = 'npm error code ETARGET\nnpm error notarget No matching version found for react@^99.0.0.'
    const normalized = normalizeNpmStepOutput({ output: `npm warn deprecated glob@7.2.3\n${reel}`, ok: false })
    assert.match(normalized, /No matching version found for react@\^99\.0\.0/)
    assert.equal(isNonDiagnosticFailure(normalized), false)
  })

  test('ENOSPC est une panne de RESSOURCE, pas un defaut du code livre', () => {
    assert.ok(isResourceExhaustionOutput(NPM_ENOSPC))
    const normalized = normalizeNpmStepOutput({ output: NPM_ENOSPC, ok: false })
    assert.match(normalized, /RESSOURCE HOTE EPUISEE/)
    // La consequence qui compte: la boucle s arrete au lieu de demander neuf
    // fois au modele de reparer un disque plein.
    assert.ok(isSandboxInfrastructureFailure({ ok: false, steps: [{ ok: false, output: normalized }] }))
  })
})

describe('run 1191 — la file emet des tests, elle emet leur outillage', () => {
  const TEST_FILES = [
    { name: 'src/tests/Navigation.test.tsx', language: 'typescript', content: 'describe("x", () => {})' },
    { name: 'package.json', language: 'json', content: '{}' },
  ]

  test('un fichier de test est reconnu sous ses formes usuelles', () => {
    assert.ok(hasTestFiles(TEST_FILES))
    assert.ok(hasTestFiles([{ name: 'src/__tests__/App.tsx', language: 'ts', content: '' }]))
    assert.ok(hasTestFiles([{ name: 'a/b.spec.ts', language: 'ts', content: '' }]))
    assert.equal(hasTestFiles([{ name: 'src/App.tsx', language: 'ts', content: '' }]), false)
    // « latest.ts » contient « test » — il ne doit pas etre pris pour un test.
    assert.equal(hasTestFiles([{ name: 'src/latest.ts', language: 'ts', content: '' }]), false)
  })

  test('le lanceur est lu dans le manifeste, jamais choisi a la place du modele', () => {
    assert.equal(detectTestRunner({ devDependencies: { jest: '^29.7.0' } }), 'jest')
    assert.equal(detectTestRunner({ devDependencies: { vitest: '^2' } }), 'vitest')
    assert.equal(detectTestRunner({ scripts: { test: 'jest --ci' } }), 'jest')
    assert.equal(detectTestRunner({ devDependencies: { react: '^19' } }), null)
  })

  test('un script de test en veille ne rend jamais la main: il est reecrit', () => {
    assert.equal(makeTestScriptNonWatching('jest --watchAll'), 'jest')
    assert.equal(makeTestScriptNonWatching('jest --watch'), 'jest')
    assert.equal(makeTestScriptNonWatching('vitest'), 'vitest run')
    assert.equal(makeTestScriptNonWatching('vitest run'), 'vitest run')
    // On ne touche pas a un script deja terminal.
    assert.equal(makeTestScriptNonWatching('jest --ci --passWithNoTests'), 'jest --ci --passWithNoTests')
  })

  test('le manifeste REEL du run 1191 est complete', () => {
    // Recopie exacte des champs en cause du livrable run 1191.
    const manifest = {
      scripts: { dev: 'vite', build: 'tsc && vite build', test: 'jest --watchAll' },
      dependencies: { react: '^19.0.0' },
      devDependencies: { jest: '^29.7.0', typescript: '^5.6.2' },
    }
    const fix = planTestToolchainFix(TEST_FILES, manifest)
    assert.ok(fix)
    assert.equal(fix.addDevDependencies['@types/jest'], '^29.5.14')
    assert.equal(fix.testScript, 'jest')

    const next = applyTestToolchainFix(manifest, fix) as typeof manifest
    assert.equal(next.devDependencies['@types/jest'], '^29.5.14')
    assert.equal(next.scripts.test, 'jest')
    // On complete, on ne redecide pas: le reste est intact.
    assert.equal(next.devDependencies.typescript, '^5.6.2')
    assert.equal(next.scripts.build, 'tsc && vite build')
  })

  test('rien a faire quand aucun test n est emis, ou que tout est deja la', () => {
    assert.equal(planTestToolchainFix([{ name: 'src/App.tsx', language: 'ts', content: '' }], { devDependencies: { jest: '^29' } }), null)
    assert.equal(
      planTestToolchainFix(TEST_FILES, {
        scripts: { test: 'jest --ci' },
        devDependencies: { jest: '^29.7.0', '@types/jest': '^29.5.0' },
      }),
      null,
    )
    // vitest fournit ses propres types: rien a ajouter.
    const vitestFix = planTestToolchainFix(TEST_FILES, { scripts: { test: 'vitest run' }, devDependencies: { vitest: '^2' } })
    assert.equal(vitestFix, null)
  })
})

describe('run 1191 — l apostrophe assainie sur TOUS les chemins d ecriture', () => {
  // Emission structuree = le chemin des passes de correction, qui rendait le
  // contenu BRUT alors que le chemin heritier assainissait.
  // On serialise avec l EMETTEUR REEL du module, jamais avec une fixture
  // ecrite a la main: ma premiere version inventait des marqueurs
  // (`AURORA_PROJECT_TREE`) qu aucun code ne produit. Elle retombait donc sur
  // le chemin heritier — celui qui assainissait deja — et le test passait pour
  // la MAUVAISE RAISON, en laissant le vrai trou ouvert.
  function structuredEmission(path: string, content: string): string {
    return serializeProjectTreeEmission([{ path, content, language: 'typescript' }])
  }

  test('la fixture emprunte bien le chemin STRUCTURE', () => {
    assert.ok(isStructuredProjectEmission(structuredEmission('src/x.ts', 'const a = 1\n')))
  })

  test('les deux apostrophes reelles du run 1191 sont echappees a l analyse', () => {
    const brut = [
      'export const cafes = [',
      "  { notes: ['agrumes', 'fleur d'oranger'], location: 'Presqu'île' },",
      ']',
    ].join('\n')
    const files = parseCodeFiles(structuredEmission('src/components/FeaturedCoffees.tsx', brut))
    assert.equal(files.length, 1, 'le fichier doit ressortir de l emission structuree')
    assert.match(files[0].content, /fleur d\\'oranger/)
    assert.match(files[0].content, /Presqu\\'île/)
  })

  test('un fichier deja correct traverse inchange', () => {
    const propre = "export const x = ['fleur d\\'oranger']\n"
    const files = parseCodeFiles(structuredEmission('src/x.ts', propre))
    assert.equal(files.length, 1)
    assert.equal(files[0].content.trim(), propre.trim())
  })
})
