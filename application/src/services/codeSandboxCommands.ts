import type { AutoInstallSpec, CodeFile, DetectedLanguage, ValidationCommand } from './codeSandboxTypes.ts'
import { isWindows, nodeExecutable } from './codeSandboxRuntime.ts'
import { detectPackageManager, findFile, hasExtension, hasPythonTests, parseJsonSafely } from './codeSandboxFiles.ts'

// ---------------------------------------------------------------------------
// Language-specific command builders
// ---------------------------------------------------------------------------

function buildNodeCommands(files: CodeFile[]): ValidationCommand[] {
  const packageFile = findFile(files, 'package.json')
  const packageJson = packageFile ? parseJsonSafely<{ packageManager?: string; scripts?: Record<string, string> }>(packageFile.content) : null
  const scripts = packageJson?.scripts || {}
  const manager = detectPackageManager(files, packageJson)
  const executable = nodeExecutable(manager)
  const commands: ValidationCommand[] = [
    { label: 'Installer les dependances', executable, args: ['install'], timeoutMs: 10 * 60_000 },
  ]

  for (const scriptName of ['build', 'test', 'lint']) {
    if (scripts[scriptName]) {
      commands.push({
        label: `Verifier ${scriptName}`,
        executable,
        args: manager === 'yarn' ? [scriptName] : ['run', scriptName],
        timeoutMs: 10 * 60_000,
      })
    }
  }

  return commands
}

function buildPythonCommands(files: CodeFile[]): ValidationCommand[] {
  const venvPython = isWindows() ? '.venv\\Scripts\\python.exe' : '.venv/bin/python'
  const commands: ValidationCommand[] = [
    { label: 'Creer le venv de sandbox', executable: 'python', args: ['-m', 'venv', '.venv'], timeoutMs: 3 * 60_000 },
  ]

  if (findFile(files, 'requirements.txt')) {
    commands.push({ label: 'Installer requirements', executable: venvPython, args: ['-m', 'pip', 'install', '-r', 'requirements.txt'], timeoutMs: 10 * 60_000 })
  } else if (findFile(files, 'pyproject.toml') || findFile(files, 'setup.py')) {
    commands.push({ label: 'Installer le projet', executable: venvPython, args: ['-m', 'pip', 'install', '-e', '.'], timeoutMs: 10 * 60_000 })
  }

  if (hasPythonTests(files)) {
    commands.push({ label: 'Installer pytest', executable: venvPython, args: ['-m', 'pip', 'install', 'pytest'], timeoutMs: 5 * 60_000 })
    commands.push({ label: 'Lancer pytest', executable: venvPython, args: ['-m', 'pytest'], timeoutMs: 10 * 60_000 })
  } else {
    commands.push({ label: 'Compiler le projet Python', executable: venvPython, args: ['-m', 'compileall', '.'], timeoutMs: 4 * 60_000 })
  }

  return commands
}

function buildRustCommands(): ValidationCommand[] {
  return [{ label: 'Verifier Cargo', executable: 'cargo', args: ['check'], timeoutMs: 10 * 60_000 }]
}

function buildGoCommands(): ValidationCommand[] {
  return [{ label: 'Lancer les tests Go', executable: 'go', args: ['test', './...'], timeoutMs: 10 * 60_000 }]
}

function buildJavaCommands(files: CodeFile[]): ValidationCommand[] {
  const hasMaven = !!findFile(files, 'pom.xml')
  const hasGradle = !!findFile(files, 'build.gradle') || !!findFile(files, 'build.gradle.kts')

  if (hasMaven) {
    return [{ label: 'Build Maven', executable: 'mvn', args: ['compile', '-q'], timeoutMs: 10 * 60_000 }]
  }
  if (hasGradle) {
    const gradle = isWindows() ? 'gradlew.bat' : './gradlew'
    return [{ label: 'Build Gradle', executable: gradle, args: ['build', '--quiet'], timeoutMs: 10 * 60_000 }]
  }

  // Plain .java files — find the main class name
  const mainFile = files.find((file) => file.name.endsWith('.java') && /public\s+static\s+void\s+main/.test(file.content))
  const mainClass = mainFile ? mainFile.name.replace(/\.java$/, '').replace(/.*[/\\]/, '') : 'Main'
  return [
    { label: 'Compiler Java', executable: 'javac', args: ['*.java'], timeoutMs: 5 * 60_000 },
    { label: 'Executer Java', executable: 'java', args: [mainClass], timeoutMs: 5 * 60_000 },
  ]
}

function buildCCommands(files: CodeFile[]): ValidationCommand[] {
  const hasMakefile = !!findFile(files, 'Makefile') || !!findFile(files, 'makefile')
  if (hasMakefile) {
    return [{ label: 'Build Make (C)', executable: 'make', args: [], timeoutMs: 5 * 60_000 }]
  }

  const outExe = isWindows() ? 'out.exe' : './out'
  const cFiles = files.filter((file) => file.name.endsWith('.c')).map((file) => file.name)

  return [
    { label: 'Compiler C (gcc)', executable: 'gcc', args: ['-o', isWindows() ? 'out.exe' : 'out', ...cFiles], timeoutMs: 5 * 60_000 },
    { label: 'Executer le binaire', executable: outExe, args: [], timeoutMs: 2 * 60_000 },
  ]
}

function buildCppCommands(files: CodeFile[]): ValidationCommand[] {
  const hasCmake = !!findFile(files, 'CMakeLists.txt')
  if (hasCmake) {
    return [
      { label: 'CMake configure', executable: 'cmake', args: ['-B', 'build', '-S', '.'], timeoutMs: 5 * 60_000 },
      { label: 'CMake build', executable: 'cmake', args: ['--build', 'build'], timeoutMs: 10 * 60_000 },
    ]
  }

  const outExe = isWindows() ? 'out.exe' : './out'
  const cppFiles = files.filter((file) => file.name.endsWith('.cpp') || file.name.endsWith('.cc')).map((file) => file.name)

  return [
    { label: 'Compiler C++ (g++)', executable: 'g++', args: ['-o', isWindows() ? 'out.exe' : 'out', ...cppFiles], timeoutMs: 5 * 60_000 },
    { label: 'Executer le binaire', executable: outExe, args: [], timeoutMs: 2 * 60_000 },
  ]
}

function buildBashCommands(files: CodeFile[]): ValidationCommand[] {
  const mainSh = files.find((file) => file.name.endsWith('.sh'))
  if (!mainSh) return []
  return [{ label: 'Executer le script Bash', executable: 'bash', args: [mainSh.name], timeoutMs: 5 * 60_000 }]
}

function buildRubyCommands(files: CodeFile[]): ValidationCommand[] {
  const commands: ValidationCommand[] = []
  if (findFile(files, 'Gemfile')) {
    commands.push({ label: 'Bundle install', executable: 'bundle', args: ['install'], timeoutMs: 10 * 60_000 })
  }
  const mainRb = files.find((file) => file.name === 'main.rb' || file.name.endsWith('.rb'))
  if (mainRb) {
    commands.push({ label: 'Executer Ruby', executable: 'ruby', args: [mainRb.name], timeoutMs: 5 * 60_000 })
  }
  return commands
}

function buildPhpCommands(files: CodeFile[]): ValidationCommand[] {
  const main = files.find((file) => file.name === 'index.php' || file.name === 'main.php' || file.name.endsWith('.php'))
  if (!main) return []
  return [{ label: 'Executer PHP', executable: 'php', args: [main.name], timeoutMs: 5 * 60_000 }]
}

function buildTypeScriptStandaloneCommands(files: CodeFile[]): ValidationCommand[] {
  const npm = nodeExecutable('npm')
  const main = files.find((file) => file.name === 'main.ts' || file.name === 'index.ts' || file.name.endsWith('.ts'))
  if (!main) return []
  return [
    { label: 'Installer ts-node', executable: npm, args: ['install', '-g', 'ts-node', 'typescript'], timeoutMs: 5 * 60_000, optional: true },
    { label: 'Executer TypeScript', executable: 'npx', args: ['ts-node', main.name], timeoutMs: 5 * 60_000 },
  ]
}

function buildSqlCommands(files: CodeFile[]): ValidationCommand[] {
  const main = files.find((file) => file.name.endsWith('.sql'))
  if (!main) return []
  return [{ label: 'Valider SQL (sqlite3)', executable: 'sqlite3', args: [':memory:', `.read ${main.name}`], timeoutMs: 2 * 60_000 }]
}

function buildDartCommands(files: CodeFile[]): ValidationCommand[] {
  if (findFile(files, 'pubspec.yaml')) {
    return [
      { label: 'Dart pub get', executable: 'dart', args: ['pub', 'get'], timeoutMs: 5 * 60_000 },
      { label: 'Executer Dart', executable: 'dart', args: ['run'], timeoutMs: 5 * 60_000 },
    ]
  }
  const main = files.find((file) => file.name.endsWith('.dart'))
  if (!main) return []
  return [{ label: 'Executer Dart', executable: 'dart', args: [main.name], timeoutMs: 5 * 60_000 }]
}

function buildKotlinCommands(files: CodeFile[]): ValidationCommand[] {
  const kt = files.find((file) => file.name.endsWith('.kt'))
  if (!kt) return []
  return [
    { label: 'Compiler Kotlin', executable: 'kotlinc', args: [kt.name, '-include-runtime', '-d', 'out.jar'], timeoutMs: 10 * 60_000 },
    { label: 'Executer Kotlin', executable: 'java', args: ['-jar', 'out.jar'], timeoutMs: 5 * 60_000 },
  ]
}

function buildCSharpCommands(files: CodeFile[]): ValidationCommand[] {
  if (files.some((f) => f.name.endsWith('.csproj'))) {
    return [
      { label: 'Restaurer les dependances .NET', executable: 'dotnet', args: ['restore'], timeoutMs: 5 * 60_000 },
      { label: 'Build .NET', executable: 'dotnet', args: ['build', '--no-restore'], timeoutMs: 10 * 60_000 },
    ]
  }
  const main = files.find((f) => f.name.endsWith('.cs'))
  if (!main) return []
  return [{ label: 'Compiler C#', executable: 'dotnet-script', args: [main.name], timeoutMs: 5 * 60_000, optional: true }]
}

function buildSwiftCommands(files: CodeFile[]): ValidationCommand[] {
  if (findFile(files, 'Package.swift')) {
    return [{ label: 'Build Swift Package', executable: 'swift', args: ['build'], timeoutMs: 10 * 60_000 }]
  }
  const main = files.find((f) => f.name.endsWith('.swift'))
  if (!main) return []
  return [{ label: 'Executer Swift', executable: 'swift', args: [main.name], timeoutMs: 5 * 60_000 }]
}

function buildZigCommands(files: CodeFile[]): ValidationCommand[] {
  if (findFile(files, 'build.zig')) {
    return [{ label: 'Build Zig', executable: 'zig', args: ['build'], timeoutMs: 10 * 60_000 }]
  }
  const main = files.find((f) => f.name.endsWith('.zig'))
  if (!main) return []
  return [{ label: 'Executer Zig', executable: 'zig', args: ['run', main.name], timeoutMs: 5 * 60_000 }]
}

function buildLuaCommands(files: CodeFile[]): ValidationCommand[] {
  const main = files.find((f) => f.name.endsWith('.lua'))
  if (!main) return []
  return [{ label: 'Executer Lua', executable: 'lua', args: [main.name], timeoutMs: 5 * 60_000 }]
}

function buildElixirCommands(files: CodeFile[]): ValidationCommand[] {
  if (findFile(files, 'mix.exs')) {
    return [
      { label: 'Mix deps.get', executable: 'mix', args: ['deps.get'], timeoutMs: 5 * 60_000 },
      { label: 'Mix compile', executable: 'mix', args: ['compile'], timeoutMs: 10 * 60_000 },
    ]
  }
  const main = files.find((f) => f.name.endsWith('.exs') || f.name.endsWith('.ex'))
  if (!main) return []
  return [{ label: 'Executer Elixir', executable: 'elixir', args: [main.name], timeoutMs: 5 * 60_000 }]
}

function buildHaskellCommands(files: CodeFile[]): ValidationCommand[] {
  if (findFile(files, 'stack.yaml')) {
    return [{ label: 'Stack build', executable: 'stack', args: ['build'], timeoutMs: 10 * 60_000 }]
  }
  const main = files.find((f) => f.name.endsWith('.hs'))
  if (!main) return []
  return [
    { label: 'Compiler Haskell', executable: 'ghc', args: ['-o', 'out', main.name], timeoutMs: 10 * 60_000 },
    { label: 'Executer Haskell', executable: isWindows() ? 'out.exe' : './out', args: [], timeoutMs: 5 * 60_000 },
  ]
}

function buildScalaCommands(files: CodeFile[]): ValidationCommand[] {
  if (findFile(files, 'build.sbt')) {
    return [{ label: 'SBT compile', executable: 'sbt', args: ['compile'], timeoutMs: 10 * 60_000 }]
  }
  const main = files.find((f) => f.name.endsWith('.scala'))
  if (!main) return []
  return [{ label: 'Executer Scala', executable: 'scala', args: [main.name], timeoutMs: 5 * 60_000 }]
}

function buildRCommands(files: CodeFile[]): ValidationCommand[] {
  const main = files.find((f) => /\.[rR]$/.test(f.name))
  if (!main) return []
  return [{ label: 'Executer R', executable: 'Rscript', args: [main.name], timeoutMs: 5 * 60_000 }]
}

function buildPowerShellCommands(files: CodeFile[]): ValidationCommand[] {
  const main = files.find((f) => /\.(ps1|psm1)$/i.test(f.name))
  if (!main) return []
  // pwsh (PowerShell Core, cross-platform) is the modern default. On Windows
  // we fall back to powershell.exe (Windows PowerShell 5.1) if pwsh is absent.
  const exe = isWindows() ? 'pwsh' : 'pwsh'
  return [
    {
      label: 'Executer PowerShell',
      executable: exe,
      args: ['-NoProfile', '-NonInteractive', '-File', main.name],
      timeoutMs: 5 * 60_000,
    },
  ]
}

// ---------------------------------------------------------------------------
// Auto-generation d'un launcher local si le LLM ne l'a pas inclus.
// Sur Linux, on produit start.sh. Aucun .bat n'est ajoute automatiquement.
// ---------------------------------------------------------------------------

export function generateLaunchSh(files: CodeFile[], lang: DetectedLanguage): CodeFile | null {
  const hasLaunchScript = files.some((f) => /^(start|launch|lancement)\.(sh|bat)$/i.test(f.name.replace(/.*[/\\]/, '')))
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
        } catch { /* ignore parse error */ }
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
      const mainPy = files.find((f) => /main\.py$/i.test(f.name)) || files.find((f) => /app\.py$/i.test(f.name))
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
      script = [
        '#!/usr/bin/env bash',
        'set -euo pipefail',
        'cd "$(dirname "$0")"',
        'npx ts-node index.ts',
      ].join('\n')
      break
    default:
      return null
  }

  return { name: 'start.sh', language: 'bash', content: script }
}

export function detectDominantLanguage(files: CodeFile[]): DetectedLanguage {
  if (findFile(files, 'package.json')) return 'node'
  if (findFile(files, 'pyproject.toml') || findFile(files, 'requirements.txt') || findFile(files, 'setup.py') || hasExtension(files, '.py')) return 'python'
  if (findFile(files, 'Cargo.toml')) return 'rust'
  if (findFile(files, 'go.mod')) return 'go'
  if (findFile(files, 'pom.xml') || findFile(files, 'build.gradle') || findFile(files, 'build.gradle.kts') || hasExtension(files, '.java')) return 'java'
  if (hasExtension(files, '.kt')) return 'kotlin'
  if (hasExtension(files, '.cpp') || hasExtension(files, '.cc') || findFile(files, 'CMakeLists.txt')) return 'cpp'
  if (hasExtension(files, '.c') && !hasExtension(files, '.cpp')) return 'c'
  if (hasExtension(files, '.sh')) return 'bash'
  if (findFile(files, 'Gemfile') || hasExtension(files, '.rb')) return 'ruby'
  if (hasExtension(files, '.php')) return 'php'
  if (hasExtension(files, '.dart') || findFile(files, 'pubspec.yaml')) return 'dart'
  if (hasExtension(files, '.sql')) return 'sql'
  if (hasExtension(files, '.cs') || findFile(files, 'Program.cs')) return 'csharp'
  if (hasExtension(files, '.swift')) return 'swift'
  if (hasExtension(files, '.zig') || findFile(files, 'build.zig')) return 'zig'
  if (hasExtension(files, '.lua')) return 'lua'
  if (hasExtension(files, '.ex') || hasExtension(files, '.exs') || findFile(files, 'mix.exs')) return 'elixir'
  if (hasExtension(files, '.hs') || findFile(files, 'stack.yaml')) return 'haskell'
  if (hasExtension(files, '.scala') || findFile(files, 'build.sbt')) return 'scala'
  if (hasExtension(files, '.r') || hasExtension(files, '.R')) return 'r'
  if (hasExtension(files, '.ps1') || hasExtension(files, '.psm1')) return 'powershell'
  // TypeScript standalone (no package.json — handled above via node)
  if (findFile(files, 'tsconfig.json') || hasExtension(files, '.ts')) return 'typescript-standalone'
  return 'unknown'
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
      return {
        cmd: 'java',
        install: { winget: 'Microsoft.OpenJDK.21', apt: 'openjdk-21-jdk', brew: 'openjdk@21' },
      }
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
      return {
        cmd: 'bash',
        install: { message: 'Bash est disponible nativement sur Linux/Mac. Sur Windows, activez WSL.' },
      }
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

export function buildCommandsForLanguage(lang: DetectedLanguage, files: CodeFile[]): ValidationCommand[] {
  switch (lang) {
    case 'node': return buildNodeCommands(files)
    case 'python': return buildPythonCommands(files)
    case 'rust': return buildRustCommands()
    case 'go': return buildGoCommands()
    case 'java': return buildJavaCommands(files)
    case 'kotlin': return buildKotlinCommands(files)
    case 'c': return buildCCommands(files)
    case 'cpp': return buildCppCommands(files)
    case 'bash': return buildBashCommands(files)
    case 'ruby': return buildRubyCommands(files)
    case 'php': return buildPhpCommands(files)
    case 'dart': return buildDartCommands(files)
    case 'sql': return buildSqlCommands(files)
    case 'typescript-standalone': return buildTypeScriptStandaloneCommands(files)
    case 'csharp': return buildCSharpCommands(files)
    case 'swift': return buildSwiftCommands(files)
    case 'zig': return buildZigCommands(files)
    case 'lua': return buildLuaCommands(files)
    case 'elixir': return buildElixirCommands(files)
    case 'haskell': return buildHaskellCommands(files)
    case 'scala': return buildScalaCommands(files)
    case 'r': return buildRCommands(files)
    case 'powershell': return buildPowerShellCommands(files)
    default: return []
  }
}
