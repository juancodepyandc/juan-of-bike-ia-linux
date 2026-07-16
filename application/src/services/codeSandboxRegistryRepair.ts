import { runWorkspaceCommand } from '../hooks/useTauri.ts'
import type { CodeFile, CodeSandboxStepResult, ValidationCommand } from './codeSandboxTypes.ts'
import {
  findFile,
  getDependencySpecFromManifest,
  parseJsonSafely,
  writeSandboxFiles,
  type NodePackageManifest,
} from './codeSandboxFiles.ts'

type RegistryTarget = {
  packageName: string
  requestedSpec: string
}

type RegistryRepairOptions = {
  buildRegistryLookupCommand: (packageName: string) => ValidationCommand
  runCommand?: typeof runWorkspaceCommand
  writeFiles?: typeof writeSandboxFiles
  afterWrite?: () => Promise<CodeSandboxStepResult[] | void>
}

// MEMORY-SAFE: LRU-like cache with max entries to prevent unbounded growth
const NPM_VERSION_CACHE = new Map<string, string[]>()
const NPM_VERSION_CACHE_MAX = 50

function npmCacheSet(key: string, value: string[]) {
  if (NPM_VERSION_CACHE.size >= NPM_VERSION_CACHE_MAX) {
    // Remove oldest entry (first inserted)
    const firstKey = NPM_VERSION_CACHE.keys().next().value
    if (firstKey !== undefined) NPM_VERSION_CACHE.delete(firstKey)
  }
  NPM_VERSION_CACHE.set(key, value)
}

function isRemoteDependencySpec(spec: string) {
  const normalized = spec.trim().toLowerCase()
  return normalized === ''
    || normalized === '*'
    || normalized === 'latest'
    || normalized.startsWith('workspace:')
    || normalized.startsWith('file:')
    || normalized.startsWith('link:')
    || normalized.startsWith('git+')
    || normalized.startsWith('git://')
    || normalized.startsWith('github:')
    || normalized.startsWith('http://')
    || normalized.startsWith('https://')
    || normalized.startsWith('npm:')
}

function splitRegistryTarget(specifier: string): RegistryTarget | null {
  const cleaned = specifier.trim().replace(/[.'"]+$/g, '')
  const splitIndex = cleaned.lastIndexOf('@')
  if (splitIndex <= 0 || splitIndex >= cleaned.length - 1) {
    return null
  }

  return {
    packageName: cleaned.slice(0, splitIndex),
    requestedSpec: cleaned.slice(splitIndex + 1),
  }
}

function parseNpmTargetError(output: string): RegistryTarget | null {
  const match = output.match(/No matching version found for ([^\s]+)\.?/i)
  if (!match) {
    return null
  }
  return splitRegistryTarget(match[1])
}

function parseSemver(version: string) {
  const match = version.trim().match(/^v?(\d+)\.(\d+)\.(\d+)(?:[-+][\w.-]+)?$/)
  if (!match) {
    return null
  }
  return {
    major: Number(match[1]),
    minor: Number(match[2]),
    patch: Number(match[3]),
    raw: version.trim(),
    prerelease: /-/.test(version.trim()),
  }
}

function compareSemver(left: string, right: string) {
  const a = parseSemver(left)
  const b = parseSemver(right)
  if (!a || !b) return left.localeCompare(right)
  if (a.major !== b.major) return a.major - b.major
  if (a.minor !== b.minor) return a.minor - b.minor
  if (a.patch !== b.patch) return a.patch - b.patch
  if (a.prerelease === b.prerelease) return 0
  return a.prerelease ? -1 : 1
}

function parseRequestedMajor(spec: string) {
  const match = spec.match(/(\d+)(?:\.\d+)?(?:\.\d+)?/)
  if (!match) {
    return null
  }
  return Number(match[1])
}

function inferPreferredMajor(
  dependencyName: string,
  requestedSpec: string,
  manifest: NodePackageManifest,
) {
  const requestedMajor = parseRequestedMajor(requestedSpec)
  if (requestedMajor !== null) {
    return requestedMajor
  }

  if (dependencyName === '@types/react') {
    return parseRequestedMajor(getDependencySpecFromManifest(manifest, 'react') || '')
  }

  if (dependencyName === '@types/react-dom') {
    return parseRequestedMajor(getDependencySpecFromManifest(manifest, 'react-dom') || '')
      ?? parseRequestedMajor(getDependencySpecFromManifest(manifest, 'react') || '')
  }

  return null
}

function choosePublishedVersion(
  versions: string[],
  dependencyName: string,
  requestedSpec: string,
  manifest: NodePackageManifest,
) {
  const parsedVersions = versions
    .map((version) => parseSemver(version))
    .filter((value): value is NonNullable<typeof value> => Boolean(value))
    .filter((value) => !value.prerelease)
    .sort((left, right) => compareSemver(left.raw, right.raw))

  if (parsedVersions.length === 0) {
    return null
  }

  const preferredMajor = inferPreferredMajor(dependencyName, requestedSpec, manifest)
  if (preferredMajor !== null) {
    const sameMajor = parsedVersions.filter((version) => version.major === preferredMajor)
    if (sameMajor.length > 0) {
      return sameMajor[sameMajor.length - 1].raw
    }
  }

  return parsedVersions[parsedVersions.length - 1].raw
}

function formatResolvedDependencySpec(originalSpec: string, resolvedVersion: string) {
  const trimmed = originalSpec.trim()
  if (trimmed.startsWith('^')) return `^${resolvedVersion}`
  if (trimmed.startsWith('~')) return `~${resolvedVersion}`
  if (/^[<>=|]/.test(trimmed)) return `^${resolvedVersion}`
  return resolvedVersion
}

export const parseNpmTargetErrorForTest = parseNpmTargetError
export const formatResolvedDependencySpecForTest = formatResolvedDependencySpec

async function fetchPublishedVersions(packageName: string, cwd: string, options: RegistryRepairOptions) {
  const cacheKey = packageName.toLowerCase()
  const cached = NPM_VERSION_CACHE.get(cacheKey)
  if (cached) {
    return cached
  }

  const command = options.buildRegistryLookupCommand(packageName)
  const runner = options.runCommand ?? runWorkspaceCommand
  const result = await runner(command.executable, command.args, cwd, command.timeoutMs ?? 120_000)
  if (!result.ok) {
    return []
  }

  const parsed = parseJsonSafely<unknown>(result.output)
  const versions = Array.isArray(parsed)
    ? parsed.filter((value): value is string => typeof value === 'string')
    : typeof parsed === 'string'
      ? [parsed]
      : []

  npmCacheSet(cacheKey, versions)
  return versions
}

function updateManifestDependency(
  manifest: NodePackageManifest,
  packageName: string,
  nextSpec: string,
) {
  for (const section of ['dependencies', 'devDependencies', 'optionalDependencies', 'peerDependencies'] as const) {
    const current = manifest[section]
    if (current && typeof current === 'object' && packageName in current) {
      ;(current as Record<string, string>)[packageName] = nextSpec
      return section
    }
  }
  return null
}

function replacePackageFile(files: CodeFile[], nextManifest: NodePackageManifest) {
  return files.map((file) => {
    if (file.name.replace(/\\/g, '/').toLowerCase() !== 'package.json') {
      return file
    }
    return {
      ...file,
      content: `${JSON.stringify(nextManifest, null, 2)}\n`,
    }
  })
}

async function repairNodeDependencyFromRegistry(
  files: CodeFile[],
  cwd: string,
  target: RegistryTarget,
  options: RegistryRepairOptions,
) {
  if (isRemoteDependencySpec(target.requestedSpec)) {
    return null
  }

  const packageFile = findFile(files, 'package.json')
  if (!packageFile) {
    return null
  }

  const manifest = parseJsonSafely<NodePackageManifest>(packageFile.content)
  if (!manifest) {
    return null
  }

  const currentSpec = getDependencySpecFromManifest(manifest, target.packageName)
  if (!currentSpec || currentSpec.trim() !== target.requestedSpec.trim()) {
    return null
  }

  const versions = await fetchPublishedVersions(target.packageName, cwd, options)
  const resolvedVersion = choosePublishedVersion(versions, target.packageName, target.requestedSpec, manifest)
  if (!resolvedVersion) {
    return null
  }

  const nextSpec = formatResolvedDependencySpec(target.requestedSpec, resolvedVersion)
  if (nextSpec === currentSpec) {
    return null
  }

  const section = updateManifestDependency(manifest, target.packageName, nextSpec)
  if (!section) {
    return null
  }

  return {
    files: replacePackageFile(files, manifest),
    note: `${target.packageName} corrige automatiquement via le registre npm: ${currentSpec} -> ${nextSpec} (${section})`,
  }
}

export async function runNodeInstallWithAutoRepair(
  command: ValidationCommand,
  files: CodeFile[],
  cwd: string,
  options: RegistryRepairOptions,
) {
  const steps: CodeSandboxStepResult[] = []
  let workingFiles = files
  const maxAttempts = 4
  const runner = options.runCommand ?? runWorkspaceCommand
  const writer = options.writeFiles ?? writeSandboxFiles

  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    const result = await runner(command.executable, command.args, cwd, command.timeoutMs)
    steps.push({
      label: attempt === 1 ? command.label : `${command.label} (retry ${attempt})`,
      command: `${command.executable} ${command.args.join(' ')}`.trim(),
      ok: result.ok,
      output: result.output,
    })

    if (result.ok) {
      return { ok: true, files: workingFiles, steps }
    }

    const target = parseNpmTargetError(result.output)
    if (!target) {
      return { ok: false, files: workingFiles, steps }
    }

    const repaired = await repairNodeDependencyFromRegistry(workingFiles, cwd, target, options)
    if (!repaired) {
      return { ok: false, files: workingFiles, steps }
    }

    workingFiles = repaired.files
    await writer(cwd, workingFiles)
    const afterWriteSteps = await options.afterWrite?.()
    if (afterWriteSteps) steps.push(...afterWriteSteps)
    steps.push({
      label: `Correction registre npm (${target.packageName})`,
      command: `npm view ${target.packageName} versions --json`,
      ok: true,
      output: repaired.note,
    })
  }

  return { ok: false, files: workingFiles, steps }
}
