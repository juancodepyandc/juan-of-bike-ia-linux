import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  detectStructuredManifestIssue,
  getDependencySpecFromManifest,
  normalizeSandboxFiles,
  parseJsonSafely,
  sanitizeRelativePath,
  stripFormattingArtifacts,
} from '../services/codeSandboxFiles.ts'
import {
  buildCommandsForLanguage,
  detectDominantLanguage,
  generateLaunchSh,
  getRuntimeSpec,
} from '../services/codeSandboxCommands.ts'
import {
  autoInstallRuntime,
  getExecutableRuntimeSpec,
  isWindows,
  nodeExecutable,
} from '../services/codeSandboxRuntime.ts'
import {
  formatResolvedDependencySpecForTest,
  parseNpmTargetErrorForTest,
} from '../services/codeSandboxRegistryRepair.ts'
import {
  buildToolchainDiagnosticCommands,
  withToolchainDiagnostics,
} from '../services/codeToolchainDiagnostics.ts'
import type { CodeFile } from '../services/codeSandboxTypes.ts'

function file(name: string, content: string, language = 'text'): CodeFile {
  return { name, content, language }
}

function setUserAgent(userAgent: string) {
  Object.defineProperty(globalThis, 'navigator', {
    value: { userAgent },
    configurable: true,
  })
}

describe('codeSandboxFiles', () => {
  test('stripFormattingArtifacts retire think et fences imbriquees', () => {
    const cleaned = stripFormattingArtifacts('```json\n<think>ignore</think>\n```json\n{\"ok\":true}\n```\n```')
    assert.equal(cleaned, '{"ok":true}')
  })

  test('parseJsonSafely accepte un JSON fence et rejette un manifest invalide', () => {
    assert.deepEqual(parseJsonSafely('```json\n{\"name\":\"demo\"}\n```'), { name: 'demo' })
    assert.equal(parseJsonSafely('```json\n{\"name\":}\n```'), null)
  })

  test('normalizeSandboxFiles ajoute un tsconfig local pour isoler TypeScript', () => {
    const normalized = normalizeSandboxFiles([
      file('package.json', '{"name":"demo","dependencies":{"typescript":"^6.0.0"}}', 'json'),
      file('src/index.ts', 'export const value: number = 1', 'typescript'),
    ])

    assert.ok(normalized.files.some((candidate) => candidate.name === 'tsconfig.json'))
    assert.match(normalized.notes.join('\n'), /tsconfig\.json genere automatiquement/)
  })

  test('detectStructuredManifestIssue bloque package.json sans name', () => {
    assert.match(
      detectStructuredManifestIssue([file('package.json', '{"version":"1.0.0"}', 'json')]) ?? '',
      /name.*manquant|vide/,
    )
  })

  test('helpers manifest et chemins restent deterministes', () => {
    assert.equal(
      getDependencySpecFromManifest({ dependencies: { react: '^19.0.0' } }, 'react'),
      '^19.0.0',
    )
    assert.equal(sanitizeRelativePath('../src\\app.ts'), 'src/app.ts')
  })
})

describe('codeSandboxCommands', () => {
  test('detectDominantLanguage priorise les manifests structurants', () => {
    assert.equal(detectDominantLanguage([file('package.json', '{"name":"app"}', 'json')]), 'node')
    assert.equal(detectDominantLanguage([file('pyproject.toml', '[project]\nname = "app"', 'toml')]), 'python')
    assert.equal(detectDominantLanguage([file('main.rs', 'fn main() {}', 'rust')]), 'unknown')
  })

  test('generateLaunchSh produit un start.sh Linux pour Node', () => {
    const launch = generateLaunchSh([
      file('package.json', '{"name":"app","scripts":{"dev":"vite"}}', 'json'),
    ], 'node')

    assert.equal(launch?.name, 'start.sh')
    assert.match(launch?.content ?? '', /^#!\/usr\/bin\/env bash/)
    assert.match(launch?.content ?? '', /npm run dev/)
  })

  test('buildCommandsForLanguage construit install puis scripts npm', () => {
    const commands = buildCommandsForLanguage('node', [
      file('package.json', '{"name":"app","scripts":{"build":"vite build","test":"node --test"}}', 'json'),
    ])

    assert.deepEqual(commands.map((command) => command.label), [
      'Installer les dependances',
      'Verifier build',
      'Verifier test',
    ])
  })

  test('getRuntimeSpec expose les runtimes sans commande de generation', () => {
    assert.equal(getRuntimeSpec('python')?.cmd, 'python')
    assert.equal(getRuntimeSpec('unknown'), null)
  })

  test('diagnostics toolchain ajoutent tsc optionnel apres npm install', () => {
    const files = [
      file('package.json', '{"name":"app","dependencies":{"typescript":"^6.0.0"}}', 'json'),
      file('src/index.ts', 'export const x: number = 1', 'typescript'),
    ]
    const commands = withToolchainDiagnostics('node', files, buildCommandsForLanguage('node', files))

    assert.deepEqual(commands.map((command) => command.label), [
      'Installer les dependances',
      'Diagnostic tsc --noEmit',
    ])
    assert.equal(commands[1].executable, isWindows() ? 'npx.cmd' : 'npx')
    assert.deepEqual(commands[1].args, ['tsc', '--noEmit', '--pretty', 'false'])
    assert.equal(commands[1].optional, true)
  })

  test('diagnostics toolchain ajoutent ruff dans le venv Python', () => {
    const diagnostics = buildToolchainDiagnosticCommands('python', [
      file('main.py', 'print("ok")', 'python'),
    ])

    assert.equal(diagnostics.length, 1)
    assert.equal(diagnostics[0].label, 'Diagnostic ruff')
    assert.deepEqual(diagnostics[0].args, ['-m', 'ruff', 'check', '.'])
    assert.equal(diagnostics[0].optional, true)
  })

  test('diagnostics toolchain ajoutent cargo clippy pour Rust', () => {
    const diagnostics = buildToolchainDiagnosticCommands('rust', [
      file('Cargo.toml', '[package]\nname="demo"\nversion="0.1.0"', 'toml'),
      file('src/main.rs', 'fn main() {}', 'rust'),
    ])

    assert.equal(diagnostics.length, 1)
    assert.equal(diagnostics[0].label, 'Diagnostic cargo clippy')
    assert.deepEqual(diagnostics[0].args, ['clippy', '--all-targets', '--all-features', '--', '-D', 'warnings'])
    assert.equal(diagnostics[0].optional, true)
  })
})

describe('codeSandboxRuntime', () => {
  test('nodeExecutable suit la plateforme detectee', () => {
    setUserAgent('Windows NT 10.0')
    assert.equal(isWindows(), true)
    assert.equal(nodeExecutable('npm'), 'npm.cmd')

    setUserAgent('Linux x86_64')
    assert.equal(isWindows(), false)
    assert.equal(nodeExecutable('npm'), 'npm')
  })

  test('getExecutableRuntimeSpec ignore les chemins locaux et normalise npm.cmd', () => {
    assert.equal(getExecutableRuntimeSpec('./node_modules/.bin/vite'), null)
    assert.equal(getExecutableRuntimeSpec('npm.cmd')?.cmd, 'node')
  })

  test('autoInstallRuntime bloque les installs systeme Linux sans lancer de commande privilegiee', async () => {
    setUserAgent('Linux x86_64')
    const result = await autoInstallRuntime({
      apt: 'nodejs npm',
      message: 'Node.js requis.',
    }, '/tmp/aurora-sandbox-test')

    assert.equal(result.ok, false)
    assert.match(result.output, /Installation systeme automatique desactivee/)
    assert.doesNotMatch(result.output, /sudo|apt-get/)
  })
})

describe('codeSandboxRegistryRepair', () => {
  test('parseNpmTargetErrorForTest extrait le paquet et la version demandee', () => {
    assert.deepEqual(
      parseNpmTargetErrorForTest('npm ERR! No matching version found for @types/react@18.999.0.'),
      { packageName: '@types/react', requestedSpec: '18.999.0' },
    )
  })

  test('formatResolvedDependencySpecForTest conserve le prefixe de semver utile', () => {
    assert.equal(formatResolvedDependencySpecForTest('^99.0.0', '19.2.1'), '^19.2.1')
    assert.equal(formatResolvedDependencySpecForTest('~99.0.0', '19.2.1'), '~19.2.1')
    assert.equal(formatResolvedDependencySpecForTest('>=99.0.0', '19.2.1'), '^19.2.1')
    assert.equal(formatResolvedDependencySpecForTest('99.0.0', '19.2.1'), '19.2.1')
  })
})
