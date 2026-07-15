import { runWorkspaceCommand } from '../hooks/useTauri.ts'
import type { AutoInstallSpec } from './codeSandboxTypes.ts'

// ---------------------------------------------------------------------------
// OS helpers
// ---------------------------------------------------------------------------

export function isWindows(): boolean {
  return typeof navigator !== 'undefined' && /windows/i.test(navigator.userAgent)
}

export function nodeExecutable(name: 'npm' | 'pnpm' | 'yarn' | 'bun') {
  if (isWindows()) {
    if (name === 'bun') return 'bun.exe'
    return `${name}.cmd`
  }
  return name
}

// ---------------------------------------------------------------------------
// Runtime availability + auto-install
// ---------------------------------------------------------------------------

/** Returns true if the given command is available on PATH. */
export async function checkRuntimeAvailable(cmd: string, cwd: string): Promise<boolean> {
  const finder = isWindows() ? 'where' : 'which'
  const result = await runWorkspaceCommand(finder, [cmd], cwd, 10_000).catch(() => ({ ok: false, exitCode: 1, output: '', command: '' }))
  return result.ok
}

export async function autoInstallRuntime(spec: AutoInstallSpec, cwd: string): Promise<{ ok: boolean; output: string }> {
  if (isWindows() && spec.winget) {
    const result = await runWorkspaceCommand('winget', ['install', '--silent', '--accept-source-agreements', '--accept-package-agreements', spec.winget], cwd, 5 * 60_000)
    return { ok: result.ok, output: result.output }
  }

  const os = typeof navigator !== 'undefined' ? navigator.userAgent : ''

  if (/macintosh|mac os x/i.test(os) && spec.brew) {
    const result = await runWorkspaceCommand('brew', ['install', spec.brew], cwd, 5 * 60_000)
    return { ok: result.ok, output: result.output }
  }

  if (/linux/i.test(os) && spec.apt) {
    return {
      ok: false,
      output: [
        spec.message ?? 'Runtime systeme manquant.',
        `Installation systeme automatique desactivee sur Linux: paquet requis "${spec.apt}".`,
        'Installez le runtime hors generation, ou activez le futur sandbox conteneurise WS7.',
      ].join('\n'),
    }
  }

  if (spec.npm) {
    const npm = nodeExecutable('npm')
    const result = await runWorkspaceCommand(npm, ['install', '-g', ...spec.npm.split(' ')], cwd, 5 * 60_000)
    return { ok: result.ok, output: result.output }
  }

  return { ok: false, output: spec.message ?? 'Aucun installeur disponible pour ce runtime.' }
}

function isLocalExecutablePath(executable: string) {
  return executable.startsWith('./')
    || executable.startsWith('.\\')
    || executable.includes('/')
    || executable.includes('\\')
}

function normalizeExecutableName(executable: string) {
  return executable
    .trim()
    .replace(/\.cmd$/i, '')
    .replace(/\.bat$/i, '')
    .replace(/\.exe$/i, '')
    .toLowerCase()
}

export function getExecutableRuntimeSpec(executable: string): { cmd: string; install: AutoInstallSpec } | null {
  if (isLocalExecutablePath(executable)) return null

  switch (normalizeExecutableName(executable)) {
    case 'node':
    case 'npm':
    case 'npx':
      return {
        cmd: isWindows() ? 'node.exe' : 'node',
        install: {
          winget: 'OpenJS.NodeJS.LTS',
          apt: 'nodejs npm',
          brew: 'node',
          message: 'Installez Node.js LTS pour executer npm, npx et les scripts JavaScript.',
        },
      }
    case 'pnpm':
      return {
        cmd: isWindows() ? 'pnpm.cmd' : 'pnpm',
        install: { npm: 'pnpm', message: 'PNPM est requis pour cette validation.' },
      }
    case 'yarn':
      return {
        cmd: isWindows() ? 'yarn.cmd' : 'yarn',
        install: { npm: 'yarn', message: 'Yarn est requis pour cette validation.' },
      }
    case 'bun':
      return {
        cmd: isWindows() ? 'bun.exe' : 'bun',
        install: {
          winget: 'Oven-sh.Bun',
          brew: 'bun',
          message: 'Installez Bun pour executer cette stack.',
        },
      }
    case 'python':
    case 'pip':
    case 'pytest':
      return {
        cmd: 'python',
        install: {
          winget: 'Python.Python.3.12',
          apt: 'python3 python3-venv python3-pip',
          brew: 'python',
          message: 'Python 3 avec venv et pip est requis pour cette validation.',
        },
      }
    case 'cargo':
    case 'rustc':
      return {
        cmd: 'cargo',
        install: {
          winget: 'Rustlang.Rust.MSVC',
          apt: 'cargo rustc',
          brew: 'rust',
          message: 'Rust et Cargo sont requis pour cette validation.',
        },
      }
    case 'go':
      return {
        cmd: 'go',
        install: {
          winget: 'GoLang.Go',
          apt: 'golang-go',
          brew: 'go',
          message: 'Go est requis pour cette validation.',
        },
      }
    default:
      return null
  }
}
