import assert from 'node:assert/strict'
import { describe, test } from 'node:test'

import {
  buildMergedStderrShellLine,
  describeCommand,
  isMergedStderrCommand,
  shellQuote,
  supportsStderrMerge,
  withMergedStderr,
} from '../services/codeCommandStderr.ts'
import {
  annotateStepOutput,
  describeExitCode,
  formatSilentStepDiagnostic,
  parseHostMemorySnapshot,
} from '../services/codeSandboxSilentStep.ts'
import { isNonDiagnosticFailure, isSandboxInfrastructureFailure } from '../services/codeInfrastructureFailure.ts'
import { parseNpmTargetErrorForTest } from '../services/codeSandboxRegistryRepair.ts'

describe('WS7 stderr fusionne — le pont ne transmet que stdout', () => {
  test('une commande simple devient un shell hote qui fusionne', () => {
    const merged = withMergedStderr({ executable: 'npm', args: ['install'] }, 'linux')
    assert.equal(merged.executable, 'sh')
    assert.equal(merged.args[0], '-c')
    assert.equal(merged.args[1], "exec 'npm' 'install' 2>&1")
  })

  test('les champs autres que le transport sont conserves', () => {
    const merged = withMergedStderr(
      { label: 'Installer les dependances', executable: 'npm', args: ['install'], timeoutMs: 600_000, optional: false },
      'linux',
    )
    assert.equal(merged.label, 'Installer les dependances')
    assert.equal(merged.timeoutMs, 600_000)
    assert.equal(merged.optional, false)
  })

  test('les arguments podman imbriques survivent au quoting', () => {
    // Cas reel: buildPodmanSandboxWorkspaceInitArgs passe un `sh -lc` contenant
    // `&&`, des accolades de `find -exec` et des chemins absolus.
    const inner = 'find /workspace -mindepth 1 -exec rm -rf -- {} + && cp -a /aurora-input/. /workspace/'
    const line = buildMergedStderrShellLine('podman', ['run', '--rm', 'sh', '-lc', inner])
    assert.match(line, /2>&1$/)
    assert.ok(line.includes(`'${inner}'`), 'la commande imbriquee reste litterale')
  })

  test('une apostrophe dans un argument ne casse pas le shell', () => {
    assert.equal(shellQuote("l'atelier"), "'l'\\''atelier'")
    const line = buildMergedStderrShellLine('echo', ["l'atelier"])
    assert.equal(line, "exec 'echo' 'l'\\''atelier' 2>&1")
  })

  test('la fusion est idempotente', () => {
    const once = withMergedStderr({ executable: 'npm', args: ['install'] }, 'linux')
    const twice = withMergedStderr(once, 'linux')
    assert.deepEqual(twice, once)
    assert.ok(isMergedStderrCommand(once))
  })

  test('Windows n est pas enveloppe dans un shell POSIX invente', () => {
    const command = { executable: 'npm.cmd', args: ['install'] }
    assert.equal(supportsStderrMerge('win32'), false)
    assert.deepEqual(withMergedStderr(command, 'win32'), command)
  })

  test('la commande affichee reste celle d origine, pas le transport', () => {
    assert.equal(describeCommand({ executable: 'npm', args: ['install'] }), 'npm install')
  })

  test('le message npm cherche par la reparation registre vit sur stderr', () => {
    // Mesure reelle (npm 10.9.8): stdout = 0 octet, stderr = 318 octets.
    // Sans fusion, parseNpmTargetError lisait une chaine vide.
    const stderrReel = [
      'npm error code ETARGET',
      'npm error notarget No matching version found for react@^99.0.0.',
    ].join('\n')
    assert.equal(parseNpmTargetErrorForTest(''), null)
    assert.deepEqual(parseNpmTargetErrorForTest(stderrReel), { packageName: 'react', requestedSpec: '^99.0.0' })
  })
})

describe('WS7 etape muette — instrumentee mais toujours non diagnostique', () => {
  const MEMINFO = [
    'MemTotal:       31999488 kB',
    'MemAvailable:    2103296 kB',
    'SwapFree:        1048576 kB',
    '--- pressure ---',
    'some avg10=42.11 avg60=30.00 avg300=12.00 total=1',
    'full avg10=10.00 avg60=5.00 avg300=1.00 total=1',
  ].join('\n')

  test('le releve /proc est lu, pas devine', () => {
    const snapshot = parseHostMemorySnapshot(MEMINFO)
    assert.equal(snapshot.memTotalKb, 31999488)
    assert.equal(snapshot.memAvailableKb, 2103296)
    assert.equal(snapshot.swapFreeKb, 1048576)
    assert.equal(snapshot.pressureSome10, 42.11)
  })

  test('un releve absent donne null, jamais une valeur inventee', () => {
    const snapshot = parseHostMemorySnapshot('rien du tout')
    assert.equal(snapshot.memAvailableKb, null)
    assert.equal(snapshot.pressureSome10, null)
  })

  test('les codes de sortie connus sont nommes, les autres rendus tels quels', () => {
    assert.match(describeExitCode(137), /SIGKILL/)
    assert.match(describeExitCode(125), /podman/)
    assert.match(describeExitCode(127), /introuvable/)
    assert.equal(describeExitCode(42), 'code 42')
    assert.match(describeExitCode(null), /inconnu/)
  })

  test('une etape muette instrumentee RESTE non diagnostique', () => {
    const text = formatSilentStepDiagnostic({
      label: 'Installer les dependances',
      exitCode: 137,
      snapshot: parseHostMemorySnapshot(MEMINFO),
      at: new Date('2026-08-17T09:00:00.000Z'),
    })
    assert.match(text, /SIGKILL/)
    assert.match(text, /2054 Mio/)
    assert.match(text, /some avg10 = 42\.11/)
    // Le point qui porte tout: instrumenter ne doit pas requalifier en defaut
    // de code une etape qui n a rien mesure.
    assert.ok(isNonDiagnosticFailure(text))
    assert.ok(isSandboxInfrastructureFailure({ ok: false, steps: [{ ok: false, output: text }] }))
  })

  test('une etape qui parle n est pas touchee', async () => {
    let called = 0
    const output = await annotateStepOutput({
      label: 'Compiler',
      output: 'src/App.tsx(3,1): error TS2304',
      ok: false,
      exitCode: 2,
      cwd: '/sandbox',
      runner: async () => { called += 1; return { ok: true, output: MEMINFO } },
    })
    assert.equal(output, 'src/App.tsx(3,1): error TS2304')
    assert.equal(called, 0, 'aucun releve inutile sur une etape qui a deja parle')
    assert.equal(isNonDiagnosticFailure(output), false)
  })

  test('une etape muette declenche le releve memoire', async () => {
    const output = await annotateStepOutput({
      label: 'Installer les dependances',
      output: '   \n  ',
      ok: false,
      exitCode: 137,
      cwd: '/sandbox',
      runner: async () => ({ ok: true, output: MEMINFO }),
    })
    assert.match(output, /^\[SORTIE VIDE\]/)
    assert.match(output, /Installer les dependances/)
    assert.match(output, /SIGKILL/)
  })

  test('un releve qui echoue ne casse pas l instrumentation', async () => {
    const output = await annotateStepOutput({
      label: 'Installer les dependances',
      output: '',
      ok: false,
      exitCode: 1,
      cwd: '/sandbox',
      runner: async () => { throw new Error('pont injoignable') },
    })
    assert.match(output, /releve impossible/)
    assert.ok(isNonDiagnosticFailure(output))
  })

  test('une etape muette A COTE d une erreur lisible ne blanchit rien', () => {
    const silent = formatSilentStepDiagnostic({ label: 'Installer', exitCode: 1, snapshot: null })
    assert.equal(
      isSandboxInfrastructureFailure({
        ok: false,
        steps: [
          { ok: false, output: silent },
          { ok: false, output: 'src/App.tsx(3,1): error TS2304' },
        ],
      }),
      false,
    )
  })
})
