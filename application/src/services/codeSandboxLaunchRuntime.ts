import { findFile } from './codeSandboxFiles.ts'
import { isWindows } from './codeSandboxRuntime.ts'
import type { AutoInstallSpec, CodeFile, DetectedLanguage } from './codeSandboxTypes.ts'

export function generateLaunchSh(files: CodeFile[], lang: DetectedLanguage): CodeFile | null {
  const hasLaunchScript = files.some((file) => /^(start|launch|lancement)\.(sh|bat)$/i.test(file.name.replace(/.*[/\\]/, '')))
  if (hasLaunchScript) return null

  let script = ''
  switch (lang) {
    case 'node': {
      const manifest = findFile(files, 'package.json')
      let devScript = 'npm start'
      if (manifest) {
        try {
          const parsed = JSON.parse(manifest.content)
          if (parsed.scripts?.dev) devScript = 'npm run dev'
          else if (parsed.scripts?.start) devScript = 'npm start'
          else if (parsed.scripts?.serve) devScript = 'npm run serve'
          else if (parsed.main) devScript = `node ${parsed.main}`
        } catch { /* invalid manifests are handled by validation */ }
      }
      script = [
        '#!/usr/bin/env bash',
        'set -euo pipefail',
        'cd "$(dirname "$0")"',
        'command -v npm >/dev/null 2>&1 || { echo "Node.js avec npm est requis." >&2; exit 1; }',
        'npm install',
        devScript,
      ].join('\n')
      break
    }
    case 'python': {
      const mainPy = files.find((file) => /main\.py$/i.test(file.name)) || files.find((file) => /app\.py$/i.test(file.name))
      const entry = mainPy ? mainPy.name.replace(/\\/g, '/') : 'main.py'
      const hasRequirements = !!findFile(files, 'requirements.txt')
      script = [
        '#!/usr/bin/env bash',
        'set -euo pipefail',
        'cd "$(dirname "$0")"',
        'command -v python >/dev/null 2>&1 || { echo "Python est requis." >&2; exit 1; }',
        ...(hasRequirements ? ['python -m pip install -r requirements.txt'] : []),
        `python ${entry}`,
      ].join('\n')
      break
    }
    case 'rust':
      script = '#!/usr/bin/env bash\nset -euo pipefail\ncd "$(dirname "$0")"\ncargo run'
      break
    case 'go':
      script = '#!/usr/bin/env bash\nset -euo pipefail\ncd "$(dirname "$0")"\ngo run .'
      break
    case 'java':
      script = '#!/usr/bin/env bash\nset -euo pipefail\ncd "$(dirname "$0")"\njavac *.java && java Main'
      break
    case 'c':
      script = '#!/usr/bin/env bash\nset -euo pipefail\ncd "$(dirname "$0")"\ngcc -o out *.c && ./out'
      break
    case 'cpp':
      script = '#!/usr/bin/env bash\nset -euo pipefail\ncd "$(dirname "$0")"\ng++ -o out *.cpp && ./out'
      break
    case 'typescript-standalone':
      script = '#!/usr/bin/env bash\nset -euo pipefail\ncd "$(dirname "$0")"\nnpx ts-node index.ts'
      break
    default:
      return null
  }

  return { name: 'start.sh', language: 'bash', content: script }
}

export function getRuntimeSpec(lang: DetectedLanguage): { cmd: string; install: AutoInstallSpec } | null {
  switch (lang) {
    case 'node':
      return {
        cmd: isWindows() ? 'node.exe' : 'node',
        install: {
          winget: 'OpenJS.NodeJS.LTS',
          apt: 'nodejs npm',
          brew: 'node',
          message: 'Installez Node.js LTS pour executer cette stack.',
        },
      }
    case 'python':
      return {
        cmd: 'python',
        install: {
          winget: 'Python.Python.3.12',
          apt: 'python3 python3-venv python3-pip',
          brew: 'python',
          message: 'Python 3 avec venv et pip est requis pour cette validation.',
        },
      }
    case 'rust':
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
    case 'java':
    case 'kotlin':
      return { cmd: 'java', install: { winget: 'Microsoft.OpenJDK.21', apt: 'openjdk-21-jdk', brew: 'openjdk@21' } }
    case 'c':
    case 'cpp':
      return {
        cmd: isWindows() ? 'gcc' : 'g++',
        install: {
          winget: 'GnuWin32.GnuWin32',
          apt: 'build-essential',
          brew: 'gcc',
          message: 'Installez GCC/G++ ou Visual Studio Build Tools.',
        },
      }
    case 'bash':
      return { cmd: 'bash', install: { message: 'Bash est disponible nativement sur Linux/Mac. Sur Windows, activez WSL.' } }
    case 'ruby':
      return { cmd: 'ruby', install: { winget: 'RubyInstallerTeam.Ruby.3.3', apt: 'ruby', brew: 'ruby' } }
    case 'php':
      return { cmd: 'php', install: { winget: 'PHP.PHP', apt: 'php', brew: 'php' } }
    case 'dart':
      return { cmd: 'dart', install: { winget: 'Google.Dart', apt: 'dart', brew: 'dart' } }
    case 'sql':
      return { cmd: 'sqlite3', install: { winget: 'SQLite.SQLite', apt: 'sqlite3', brew: 'sqlite3' } }
    case 'typescript-standalone':
      return { cmd: 'npx', install: { npm: 'ts-node typescript' } }
    case 'csharp':
      return { cmd: 'dotnet', install: { winget: 'Microsoft.DotNet.SDK.8', apt: 'dotnet-sdk-8.0', brew: 'dotnet' } }
    case 'swift':
      return { cmd: 'swift', install: { apt: 'swift', brew: 'swift', message: 'Installez Swift depuis swift.org.' } }
    case 'zig':
      return { cmd: 'zig', install: { winget: 'zig.zig', apt: 'zig', brew: 'zig' } }
    case 'lua':
      return { cmd: 'lua', install: { winget: 'DEVCOM.Lua', apt: 'lua5.4', brew: 'lua' } }
    case 'elixir':
      return { cmd: 'elixir', install: { winget: 'ElixirLang.Elixir', apt: 'elixir', brew: 'elixir' } }
    case 'haskell':
      return { cmd: 'ghc', install: { apt: 'ghc', brew: 'ghc', message: 'Installez GHC via ghcup.haskell.org.' } }
    case 'scala':
      return { cmd: 'scala', install: { brew: 'scala', message: 'Installez Scala via sdkman ou coursier.' } }
    case 'r':
      return { cmd: 'Rscript', install: { winget: 'RProject.R', apt: 'r-base', brew: 'r' } }
    case 'powershell':
      return {
        cmd: 'pwsh',
        install: {
          winget: 'Microsoft.PowerShell',
          apt: 'powershell',
          brew: 'powershell',
          message: 'PowerShell 7+ (pwsh) requis. Sur Windows, Windows PowerShell 5.1 est natif mais pwsh est preferable.',
        },
      }
    default:
      return null
  }
}
