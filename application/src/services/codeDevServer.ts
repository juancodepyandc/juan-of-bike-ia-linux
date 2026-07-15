// ---------------------------------------------------------------------------
// Code Dev Server Management â€” Start/stop dev servers for live preview
// Handles port detection, background process lifecycle, health checks
// ---------------------------------------------------------------------------

import { fsReadText, runWorkspaceCommand, spawnWorkspaceCommand } from '../hooks/useTauri'
import type { CodeIntent } from './codeIntent'
import { auroraPythonExecutable } from './codePythonEnvironment'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type DevServerState = {
  running: boolean
  port: number | null
  url: string | null
  process: 'starting' | 'ready' | 'stopped' | 'error'
  error: string | null
  rootPath: string | null
}

type DevServerLogPaths = {
  stdout: string | null
  stderr: string | null
}

// ---------------------------------------------------------------------------
// Port detection from output
// ---------------------------------------------------------------------------

const PORT_PATTERNS = [
  /(?:localhost|127\.0\.0\.1|0\.0\.0\.0):(\d{4,5})/,
  /port\s*[:=]\s*(\d{4,5})/i,
  /running\s+(?:on|at)\s+.*:(\d{4,5})/i,
  /http:\/\/[^:]+:(\d{4,5})/,
  /Local:\s+http:\/\/[^:]+:(\d{4,5})/,
  /Network:\s+http:\/\/[^:]+:(\d{4,5})/,
]

function detectPortFromOutput(output: string): number | null {
  for (const pattern of PORT_PATTERNS) {
    const match = pattern.exec(output)
    if (match) {
      const port = parseInt(match[1], 10)
      if (port >= 1024 && port <= 65535) return port
    }
  }
  return null
}

// ---------------------------------------------------------------------------
// Framework-specific dev command builders
// ---------------------------------------------------------------------------

function isWindows(): boolean {
  return typeof navigator !== 'undefined' && /windows/i.test(navigator.userAgent)
}

function npmExecutable(): string {
  return isWindows() ? 'npm.cmd' : 'npm'
}

type DevCommandSpec = {
  executable: string
  args: string[]
  readyPattern: RegExp
  defaultPort: number
}

function getDevCommandSpec(intent: CodeIntent): DevCommandSpec | null {
  const npm = npmExecutable()

  switch (intent.projectType) {
    case 'spa_react':
    case 'spa_vue':
    case 'spa_svelte':
    case 'ssr_nextjs':
    case 'ssr_nuxt':
    case 'ssr_remix':
    case 'fullstack_mern':
    case 'fullstack_nextjs':
    case 'library_npm':
    case 'cli_node':
    case 'desktop_electron':
    case 'game_web':
      return {
        executable: npm,
        args: ['run', 'dev'],
        readyPattern: /ready|compiled|started|Local:/i,
        defaultPort: 5173,
      }

    case 'spa_angular':
      return {
        executable: 'npx',
        args: ['ng', 'serve', '--port', '4200'],
        readyPattern: /Compiled successfully|listening/i,
        defaultPort: 4200,
      }

    case 'api_fastapi':
      return {
        executable: auroraPythonExecutable(),
        args: ['-m', 'uvicorn', 'main:app', '--reload', '--port', '8000'],
        readyPattern: /Uvicorn running|Started server/i,
        defaultPort: 8000,
      }

    case 'api_django':
    case 'fullstack_django':
      return {
        executable: auroraPythonExecutable(),
        args: ['manage.py', 'runserver', '8000'],
        readyPattern: /Starting development server/i,
        defaultPort: 8000,
      }

    case 'api_flask':
      return {
        executable: auroraPythonExecutable(),
        args: ['-m', 'flask', 'run', '--port', '5000'],
        readyPattern: /Running on/i,
        defaultPort: 5000,
      }

    case 'api_express':
      return {
        executable: npm,
        args: ['run', 'dev'],
        readyPattern: /listening|started|running/i,
        defaultPort: 3000,
      }

    case 'api_gin':
    case 'cli_go':
      return {
        executable: 'go',
        args: ['run', '.'],
        readyPattern: /Listening|Started/i,
        defaultPort: 8080,
      }

    case 'api_actix':
    case 'cli_rust':
    case 'system_rust':
      return {
        executable: 'cargo',
        args: ['run'],
        readyPattern: /Listening|Started|Running/i,
        defaultPort: 8080,
      }

    case 'fullstack_rails':
      return {
        executable: 'rails',
        args: ['server', '-p', '3000'],
        readyPattern: /Listening|Booting|Puma starting/i,
        defaultPort: 3000,
      }

    case 'api_spring':
      return {
        executable: isWindows() ? 'mvnw.cmd' : './mvnw',
        args: ['spring-boot:run'],
        readyPattern: /Started.*Application|Tomcat started/i,
        defaultPort: 8080,
      }

    case 'api_dotnet':
      return {
        executable: 'dotnet',
        args: ['run'],
        readyPattern: /Now listening|Content root path/i,
        defaultPort: 5000,
      }

    default:
      return null
  }
}

// ---------------------------------------------------------------------------
// Dev server lifecycle
// ---------------------------------------------------------------------------

let activeServerState: DevServerState = {
  running: false,
  port: null,
  url: null,
  process: 'stopped',
  error: null,
  rootPath: null,
}

let activeServerPid: number | null = null
let activeServerLogs: DevServerLogPaths | null = null

export function getDevServerState(): DevServerState {
  return { ...activeServerState }
}

function buildDevServerLogPaths(rootPath: string): DevServerLogPaths {
  const stamp = Date.now()
  return {
    stdout: `${rootPath}/.aurora/dev-server-${stamp}.out.log`,
    stderr: `${rootPath}/.aurora/dev-server-${stamp}.err.log`,
  }
}

async function readLogTail(path: string | null, maxChars = 12_000) {
  if (!path) return ''

  try {
    const content = await fsReadText(path)
    return content.length > maxChars ? content.slice(-maxChars) : content
  } catch {
    return ''
  }
}

async function resolveDevServerUrl(
  spec: DevCommandSpec,
  logs: DevServerLogPaths | null,
): Promise<{ url: string | null; port: number | null; logOutput: string }> {
  let port = spec.defaultPort
  let logOutput = ''

  for (let attempt = 0; attempt < 12; attempt += 1) {
    const stdout = await readLogTail(logs?.stdout ?? null)
    const stderr = await readLogTail(logs?.stderr ?? null)
    logOutput = [stdout, stderr].filter(Boolean).join('\n')

    const detectedPort = detectPortFromOutput(logOutput)
    if (detectedPort) {
      port = detectedPort
    }

    const url = `http://localhost:${port}`
    const isReady = await checkServerHealth(url, 1)
    if (isReady || spec.readyPattern.test(logOutput)) {
      return { url, port, logOutput }
    }

    await new Promise((resolve) => setTimeout(resolve, 1500))
  }

  return { url: null, port: null, logOutput }
}

/**
 * Start a dev server for the given project.
 * Returns the detected URL or null if the server couldn't start.
 */
export async function startDevServer(
  rootPath: string,
  intent: CodeIntent,
  onStateChange?: (state: DevServerState) => void,
): Promise<string | null> {
  if (activeServerState.running || activeServerPid) {
    await stopDevServer()
  }

  const spec = getDevCommandSpec(intent)
  if (!spec) return null

  activeServerState = {
    running: false,
    port: null,
    url: null,
    process: 'starting',
    error: null,
    rootPath,
  }
  onStateChange?.(getDevServerState())

  try {
    const logs = buildDevServerLogPaths(rootPath)
    activeServerLogs = logs

    const spawned = await spawnWorkspaceCommand(
      spec.executable,
      spec.args,
      rootPath,
      logs.stdout,
      logs.stderr,
    )
    activeServerPid = spawned.pid

    const resolved = await resolveDevServerUrl(spec, activeServerLogs)
    if (resolved.url && resolved.port) {
      activeServerState = {
        running: true,
        port: resolved.port,
        url: resolved.url,
        process: 'ready',
        error: null,
        rootPath,
      }
      onStateChange?.(getDevServerState())
      return resolved.url
    }

    activeServerState = {
      running: false,
      port: null,
      url: null,
      process: 'error',
      error: resolved.logOutput
        ? `Le serveur de dev n a pas confirme son demarrage. Journal recent:\n${resolved.logOutput.slice(-1200)}`
        : 'Le serveur de dev n a pas confirme son demarrage.',
      rootPath,
    }
    onStateChange?.(getDevServerState())
    return null
  } catch (error) {
    activeServerState = {
      running: false,
      port: null,
      url: null,
      process: 'error',
      error: error instanceof Error ? error.message : 'Echec du demarrage du serveur',
      rootPath,
    }
    onStateChange?.(getDevServerState())
    return null
  }
}

async function checkServerHealth(url: string, maxRetries: number): Promise<boolean> {
  for (let index = 0; index < maxRetries; index += 1) {
    try {
      const response = await fetch(url, {
        method: 'HEAD',
        signal: AbortSignal.timeout(2000),
      })
      if (response.ok || response.status < 500) return true
    } catch {
      // Server not ready yet.
    }

    await new Promise((resolve) => setTimeout(resolve, 2000))
  }

  return false
}

/**
 * Stop the active dev server.
 * Waits to confirm process is actually killed to prevent resource leaks.
 */
export async function stopDevServer(): Promise<void> {
  if (!activeServerState.running && !activeServerPid) return

  const port = activeServerState.port

  if (activeServerPid) {
    try {
      if (isWindows()) {
        await runWorkspaceCommand(
          'powershell',
          ['-Command', `Stop-Process -Id ${activeServerPid} -Force -ErrorAction SilentlyContinue`],
          '.',
          8000,
        )
      } else {
        await runWorkspaceCommand(
          'bash',
          ['-c', `kill -9 ${activeServerPid} 2>/dev/null || true`],
          '.',
          5000,
        )
      }
    } catch {
      // Best effort only.
    }
  }

  if (port) {
    try {
      if (isWindows()) {
        await runWorkspaceCommand(
          'powershell',
          ['-Command', `Get-NetTCPConnection -LocalPort ${port} -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }`],
          '.',
          8000,
        )

        try {
          await runWorkspaceCommand(
            'powershell',
            ['-Command', `$c = Get-NetTCPConnection -LocalPort ${port} -ErrorAction SilentlyContinue; if ($c) { exit 1 } else { exit 0 }`],
            '.',
            3000,
          )
        } catch {
          try {
            await runWorkspaceCommand(
              'powershell',
              ['-Command', `Get-NetTCPConnection -LocalPort ${port} -ErrorAction SilentlyContinue | ForEach-Object { taskkill /F /PID $_.OwningProcess 2>$null }`],
              '.',
              5000,
            )
          } catch {
            console.warn(`[DevServer] Could not kill process on port ${port} - may still be running`)
          }
        }
      } else {
        await runWorkspaceCommand(
          'bash',
          ['-c', `lsof -ti:${port} | xargs kill -9 2>/dev/null || true`],
          '.',
          5000,
        )
      }
    } catch {
      // Best effort only.
    }
  }

  activeServerPid = null
  activeServerLogs = null
  activeServerState = {
    running: false,
    port: null,
    url: null,
    process: 'stopped',
    error: null,
    rootPath: null,
  }
}
