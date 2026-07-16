import type { CodeIntent } from './codeIntent'
import { auroraPythonExecutable } from './codePythonEnvironment'

export type DevCommandSpec = {
  executable: string
  args: string[]
  readyPattern: RegExp
  defaultPort: number
}

export function isWindows(): boolean {
  return typeof navigator !== 'undefined' && /windows/i.test(navigator.userAgent)
}

function npmExecutable(): string {
  return isWindows() ? 'npm.cmd' : 'npm'
}

export function getDevCommandSpec(intent: CodeIntent): DevCommandSpec | null {
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
