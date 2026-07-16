import type { CodeIntent } from './codeIntent.ts'
import type { CodeFile } from './codeOrchestrator.ts'
import type { CodeSandboxResult } from './codeSandbox.ts'
import { isLLMRefusal } from './codeLLMRefusal.ts'
import {
  isVersionBelow,
  type LocalNodeManifest,
  readManifestDependencySpec,
  sanitizeGeneratedFiles,
  stripFormattingArtifacts,
  tryParseJson,
} from './codeGeneratedFileSanitizer.ts'
import { getGeneratedNodeDependencySpec } from './codeGeneratedDependencyPolicy.ts'

const DOCUMENTATION_EXTENSIONS = new Set(['md', 'txt', 'doc', 'docx', 'pdf', 'rtf'])
const WEB_CODE_EXTENSIONS = new Set(['html', 'htm', 'css', 'scss', 'less', 'js', 'jsx', 'ts', 'tsx', 'vue', 'svelte', 'astro'])
const API_CODE_EXTENSIONS = new Set(['py', 'js', 'ts', 'go', 'rs', 'java', 'rb', 'php', 'cs', 'ex', 'kt'])
const WEB_RUNTIME_MANIFESTS = new Set([
  'go.mod',
  'go.sum',
  'pom.xml',
  'build.gradle',
  'build.gradle.kts',
  'composer.json',
  'gemfile',
  'requirements.txt',
  'manage.py',
])

export function isSyntheticFallbackFile(name: string): boolean {
  const normalized = name.replace(/\\/g, '/').toLowerCase()
  return /^(?:module|script|style|page|bloc)-\d+\.[a-z0-9]+$/.test(normalized)
    || /^output\.[a-z0-9]+$/.test(normalized)
    || /^reponse\.(?:txt|text|md)$/.test(normalized)
}

export function validateStructuredFiles(files: CodeFile[]): string | null {
  for (const file of files) {
    const normalized = file.name.replace(/\\/g, '/').toLowerCase()
    if (!normalized.endsWith('.json')) continue

    const parsed = tryParseJson(stripFormattingArtifacts(file.content))
    if (!parsed) {
      return `${file.name} n est pas un JSON valide. Les fichiers machine comme package.json doivent etre du JSON pur, sans backticks markdown ni texte parasite.`
    }

    if (normalized === 'package.json') {
      const packageName = parsed.name
      if (typeof packageName !== 'string' || packageName.trim().length === 0) {
        return 'package.json est present mais son champ "name" est invalide ou vide.'
      }
    }
  }

  return null
}

function upsertGeneratedFile(files: CodeFile[], nextFile: CodeFile) {
  const normalizedTarget = nextFile.name.replace(/\\/g, '/').toLowerCase()
  const existingIndex = files.findIndex((file) => file.name.replace(/\\/g, '/').toLowerCase() === normalizedTarget)
  if (existingIndex < 0) {
    return [...files, nextFile]
  }

  return files.map((file, index) => (index === existingIndex ? nextFile : file))
}

export function isTypeScriptCompatibilityFailure(rawOutput: string) {
  return /ReferenceNode\.d\.ts|PropertyNode\.d\.ts|@types\/three|type parameter declaration expected|error TS1139|error TS6046|Unknown compiler option 'allowImportingTsExtensions'|moduleResolution' option must be/i.test(rawOutput)
}

function repairLocalTypeScriptCompatibility(files: CodeFile[], failingOutput: string) {
  if (!isTypeScriptCompatibilityFailure(failingOutput)) {
    return null
  }

  const packageFile = files.find((file) => file.name.replace(/\\/g, '/').toLowerCase() === 'package.json')
  if (!packageFile) {
    return null
  }

  const manifest = tryParseJson(stripFormattingArtifacts(packageFile.content)) as LocalNodeManifest | null
  if (!manifest) {
    return null
  }

  const currentTypeScriptSpec = readManifestDependencySpec(manifest, 'typescript')
  if (currentTypeScriptSpec && !isVersionBelow(currentTypeScriptSpec, 5, 2)) {
    return null
  }

  const nextManifest: LocalNodeManifest = {
    ...manifest,
    devDependencies: {
      ...((manifest.devDependencies && typeof manifest.devDependencies === 'object')
        ? manifest.devDependencies
        : {}),
      typescript: getGeneratedNodeDependencySpec('typescript'),
    },
  }

  const nextFiles = upsertGeneratedFile(files, {
    ...packageFile,
    content: `${JSON.stringify(nextManifest, null, 2)}\n`,
  })

  return {
    files: nextFiles,
    reason: currentTypeScriptSpec
      ? `mise a niveau automatique de TypeScript (${currentTypeScriptSpec} -> ${getGeneratedNodeDependencySpec('typescript')}) pour resoudre une incompatibilite compilateur/types`
      : `ajout automatique de TypeScript ${getGeneratedNodeDependencySpec('typescript')} pour resoudre une incompatibilite compilateur/types`,
  }
}

export function attemptLocalFileRepair(files: CodeFile[], sandboxResult: CodeSandboxResult) {
  const failingOutput = sandboxResult.steps
    .filter((step) => !step.ok)
    .map((step) => step.output)
    .join('\n')

  const sanitizedFiles = sanitizeGeneratedFiles(files)
  const changed = sanitizedFiles.some((file, index) =>
    file.name !== files[index]?.name || file.content !== files[index]?.content,
  )

  if (changed) {
    const structuredIssue = validateStructuredFiles(sanitizedFiles)
    if (!structuredIssue) {
      return {
        files: sanitizedFiles,
        reason: 'normalisation locale des fichiers machine et dependances declarees',
      }
    }
  }

  return repairLocalTypeScriptCompatibility(sanitizedFiles, failingOutput)
}

export function validateOutputMatchesIntent(files: CodeFile[], intent: CodeIntent): string | null {
  if (files.length === 0) return 'Aucun fichier genere.'

  const refusalFile = files.find((file) => isLLMRefusal(file.content))
  if (refusalFile) {
    return `Le fichier "${refusalFile.name}" contient un refus du modele au lieu de code source. Le modele doit GENERER du code, pas s excuser.`
  }

  const normalizedNames = files.map((file) => file.name.replace(/\\/g, '/').toLowerCase())

  const allDocs = files.every((file) => {
    const ext = file.name.split('.').pop()?.toLowerCase() || ''
    return DOCUMENTATION_EXTENSIONS.has(ext)
  })
  if (allDocs) {
    return 'Tous les fichiers sont des documents (md, txt) — aucun code source. Le module doit produire des FICHIERS DE CODE, pas de documentation.'
  }

  const allGeneric = files.every((file) => isSyntheticFallbackFile(file.name))
  if (allGeneric) {
    return 'Les fichiers ont des noms generiques (bloc-1, module-2, script-3) — le protocole structure AURORA_CODE_VFS/1 n a pas fourni de chemins reels. Regenere avec des chemins comme package.json, index.html, src/App.tsx.'
  }

  const structuredIssue = validateStructuredFiles(files)
  if (structuredIssue) {
    return structuredIssue
  }

  if (intent.projectType === 'desktop_tauri') {
    const hasTauriFolder = normalizedNames.some((name) => name.startsWith('src-tauri/'))
    const hasCargoManifest = normalizedNames.some((name) => name === 'src-tauri/cargo.toml')
    const hasTauriConfig = normalizedNames.some((name) => name === 'src-tauri/tauri.conf.json')
    const hasRustEntry = normalizedNames.some((name) => /^src-tauri\/src\/.+\.rs$/i.test(name))
    const hasFrontendEntry = normalizedNames.some((name) =>
      name === 'package.json'
      || name === 'index.html'
      || /^src\/.+\.(ts|tsx|js|jsx|html|css)$/i.test(name),
    )

    if (!hasTauriFolder || !hasCargoManifest || !hasTauriConfig || !hasRustEntry || !hasFrontendEntry) {
      return 'Projet desktop Tauri detecte mais la sortie ne contient pas une vraie structure applicative native complete (frontend + src-tauri + Rust + config Tauri).'
    }
  }

  if (intent.projectType === 'desktop_electron') {
    const hasPackageJson = normalizedNames.includes('package.json')
    const hasElectronMain = normalizedNames.some((name) =>
      /(^|\/)(main|electron\.main|background)\.(js|ts)$/i.test(name),
    )
    const hasRenderer = normalizedNames.some((name) =>
      name === 'index.html'
      || /^src\/.+\.(ts|tsx|js|jsx|html|css)$/i.test(name),
    )

    if (!hasPackageJson || !hasElectronMain || !hasRenderer) {
      return 'Projet desktop Electron detecte mais la sortie ne contient pas une vraie structure desktop complete (package.json + process principal Electron + renderer).'
    }
  }

  const isWebProject = intent.projectType.startsWith('spa_')
    || intent.projectType.startsWith('ssr_')
    || intent.projectType === 'static_web'
    || intent.projectType === 'game_web'

  if (isWebProject) {
    const unexpectedRuntimeFiles = normalizedNames.filter((name) =>
      name.startsWith('src-tauri/')
      || WEB_RUNTIME_MANIFESTS.has(name)
      || name.endsWith('.go')
      || name.endsWith('.rs'),
    )

    if (!intent.projectType.startsWith('fullstack_') && unexpectedRuntimeFiles.length > 0) {
      return `Projet web detecte (${intent.projectType}) mais la sortie embarque des runtimes hors sujet (${unexpectedRuntimeFiles.slice(0, 3).join(', ')}). Regenerer un vrai projet web, pas du Go/Rust/backend parasite.`
    }

    const hasWebFile = files.some((file) => {
      const ext = file.name.split('.').pop()?.toLowerCase() || ''
      return WEB_CODE_EXTENSIONS.has(ext)
    })
    if (!hasWebFile) {
      return `Projet web detecte (${intent.projectType}) mais aucun fichier web (html, css, js, tsx...) trouve. Genere les vrais fichiers source du projet.`
    }

    if (intent.projectType === 'static_web') {
      const hasIndexHtml = normalizedNames.includes('index.html')
      const hasFrameworkWebEntry = normalizedNames.some((name) =>
        /\.(astro|vue|svelte)$/i.test(name)
        || /^src\/pages\//i.test(name)
        || /astro\.config\.(mjs|js|ts)$/i.test(name))
      const hasRuntimeReadyJavascript = normalizedNames.some((name) => /\.(js|mjs|cjs)$/i.test(name))
      const hasRawTypeScriptOnly = normalizedNames.some((name) => /\.(ts|tsx)$/i.test(name)) && !hasRuntimeReadyJavascript

      if (!hasIndexHtml && !hasFrameworkWebEntry) {
        return 'Page web statique detectee mais `index.html` est absent. La preview et le lancement navigateur ont besoin d un vrai point d entree HTML.'
      }

      if (hasRawTypeScriptOnly && !hasFrameworkWebEntry) {
        return 'Page web statique detectee mais la sortie contient du TypeScript brut sans JavaScript transpile. Fournis une page HTML/CSS/JS directement executable.'
      }
    }

    if (intent.projectType.startsWith('spa_') || intent.projectType.startsWith('ssr_')) {
      const hasPackageManifest = normalizedNames.some((name) => name.endsWith('package.json'))
      if (!hasPackageManifest) {
        return `Projet ${intent.projectType} detecte mais aucun package.json n est present. Le dev server et la preview ne pourront pas demarrer correctement.`
      }
    }
  }

  const isApiProject = intent.projectType.startsWith('api_') || intent.projectType.startsWith('fullstack_')
  if (isApiProject) {
    const hasCodeFile = files.some((file) => {
      const ext = file.name.split('.').pop()?.toLowerCase() || ''
      return API_CODE_EXTENSIONS.has(ext)
    })
    if (!hasCodeFile) {
      return `Projet API detecte (${intent.projectType}) mais aucun fichier code serveur trouve. Genere les vrais fichiers source.`
    }
  }

  const avgContentLength = files.reduce((sum, file) => sum + file.content.length, 0) / files.length
  if (avgContentLength < 50 && files.length <= 2) {
    return 'Les fichiers generes sont trop courts (< 50 caracteres en moyenne) — probablement des stubs. Genere du code complet et fonctionnel.'
  }

  return null
}
