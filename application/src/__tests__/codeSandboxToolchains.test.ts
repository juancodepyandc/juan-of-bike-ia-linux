// Chaines Kotlin/Swift dans le bac isole.
//
// La matrice de capacite a rendu l ecart visible: l HOTE sait compiler du
// Kotlin (APK signe de 610 Ko prouve), le SANDBOX non — il retombait sur
// `debian:bookworm-slim`, ou `kotlinc` n existe pas. Un projet Kotlin genere
// echouait sur « command not found »: pas parce que le code etait faux, mais
// parce que l outil n etait nulle part.

import assert from 'node:assert/strict'
import { describe, test } from 'node:test'
import { buildPodmanSandboxArgs } from '../services/codeSandboxIsolation.ts'
import {
  imageOverrideForToolchain,
  resolveToolRoot,
  toolchainMountForLanguage,
  toolchainPodmanArgs,
} from '../services/codeSandboxToolchains.ts'

const HOME = '/home/juan'

describe('chaines sandbox — resolution', () => {
  test('Kotlin et Swift pointent le dossier outils prive d Aurora', () => {
    const kotlin = toolchainMountForLanguage('kotlin', HOME)!
    assert.equal(kotlin.hostPath, '/home/juan/.local/share/auroraia/tools/kotlinc')
    assert.match(kotlin.binPath, /kotlinc\/bin$/)
    const swift = toolchainMountForLanguage('swift', HOME)!
    assert.match(swift.hostPath, /swift-5\.10\.1$/)
    assert.match(swift.binPath, /usr\/bin$/)
  })

  test('un langage deja couvert par son image ne monte rien', () => {
    for (const lang of ['node', 'python', 'rust', 'go', 'java', 'c']) {
      assert.equal(toolchainMountForLanguage(lang, HOME), null, lang)
    }
  })

  test('la racine des outils suit le dossier utilisateur', () => {
    assert.equal(resolveToolRoot('/home/x/'), '/home/x/.local/share/auroraia/tools')
  })

  test('Kotlin exige une JVM: l image est surchargee', () => {
    assert.match(imageOverrideForToolchain('kotlin') ?? '', /temurin/)
    assert.equal(imageOverrideForToolchain('node'), null)
  })
})

describe('chaines sandbox — montage podman', () => {
  test('le montage est en LECTURE SEULE et le PATH est etendu', () => {
    const args = toolchainPodmanArgs(toolchainMountForLanguage('kotlin', HOME))
    const volume = args[args.indexOf('--volume') + 1]
    assert.match(volume, /:ro$/, 'la chaine ne doit jamais etre montee en ecriture')
    const env = args[args.indexOf('--env') + 1]
    assert.match(env, /^PATH=\/opt\/aurora-toolchains\/kotlinc\/bin:/)
  })

  test('rien a monter => aucun argument ajoute', () => {
    assert.deepEqual(toolchainPodmanArgs(null), [])
  })

  test('la commande Kotlin complete embarque le montage et la bonne image', () => {
    const args = buildPodmanSandboxArgs(
      { label: 'Compiler Kotlin', executable: 'kotlinc', args: ['Main.kt'], timeoutMs: 1000 },
      'kotlin' as never,
      '/tmp/sandbox-x',
      undefined,
      { homeDir: HOME },
    )
    const joined = args.join(' ')
    assert.match(joined, /aurora-toolchains\/kotlinc:ro/)
    assert.match(joined, /eclipse-temurin:21/)
    assert.equal(args.includes('kotlinc'), true)
  })

  test('un projet Node ne recoit aucun montage supplementaire', () => {
    const args = buildPodmanSandboxArgs(
      { label: 'Installer', executable: 'npm', args: ['ci'], timeoutMs: 1000 },
      'node' as never,
      '/tmp/sandbox-y',
      undefined,
      { homeDir: HOME },
    )
    assert.equal(args.join(' ').includes('aurora-toolchains'), false)
  })
})
