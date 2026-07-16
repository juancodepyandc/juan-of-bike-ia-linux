import type { CodeFile, DetectedLanguage, ValidationCommand } from './codeSandboxTypes.ts'
import { isWindows, nodeExecutable } from './codeSandboxRuntime.ts'
import { detectPackageManager, findFile, hasExtension, hasPythonTests, parseJsonSafely } from './codeSandboxFiles.ts'
import { AURORA_PYTHON_ENV_DIR, auroraPythonExecutable } from './codePythonEnvironment.ts'

export { generateLaunchSh, getRuntimeSpec } from './codeSandboxLaunchRuntime.ts'

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
  const python = auroraPythonExecutable()
  const commands: ValidationCommand[] = [
    { label: 'Creer environnement Python Aurora', executable: 'python', args: ['-m', 'venv', AURORA_PYTHON_ENV_DIR], timeoutMs: 3 * 60_000 },
  ]

  if (findFile(files, 'requirements.txt')) {
    commands.push({ label: 'Installer requirements', executable: python, args: ['-m', 'pip', 'install', '-r', 'requirements.txt'], timeoutMs: 10 * 60_000 })
  } else if (findFile(files, 'pyproject.toml') || findFile(files, 'setup.py')) {
    commands.push({ label: 'Installer le projet', executable: python, args: ['-m', 'pip', 'install', '-e', '.'], timeoutMs: 10 * 60_000 })
  }

  if (hasPythonTests(files)) {
    commands.push({ label: 'Installer pytest', executable: python, args: ['-m', 'pip', 'install', 'pytest'], timeoutMs: 5 * 60_000 })
    commands.push({ label: 'Lancer pytest', executable: python, args: ['-m', 'pytest'], timeoutMs: 10 * 60_000 })
  } else {
    commands.push({ label: 'Compiler le projet Python', executable: python, args: ['-m', 'compileall', '.'], timeoutMs: 4 * 60_000 })
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
