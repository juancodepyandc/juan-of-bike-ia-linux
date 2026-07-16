export type LocalNodeManifest = {
  dependencies?: Record<string, string>
  devDependencies?: Record<string, string>
  optionalDependencies?: Record<string, string>
  peerDependencies?: Record<string, string>
  [key: string]: unknown
}

export function readManifestDependencySpec(manifest: LocalNodeManifest, dependencyName: string) {
  for (const section of ['dependencies', 'devDependencies', 'optionalDependencies', 'peerDependencies'] as const) {
    const collection = manifest[section]
    if (collection && typeof collection === 'object' && dependencyName in collection) {
      const value = (collection as Record<string, unknown>)[dependencyName]
      if (typeof value === 'string') {
        return value
      }
    }
  }

  return null
}

export function parseSpecVersion(spec: string) {
  const match = spec.match(/(\d+)(?:\.(\d+))?(?:\.(\d+))?/)
  if (!match) return null

  return {
    major: Number(match[1]),
    minor: Number(match[2] || '0'),
    patch: Number(match[3] || '0'),
  }
}

export function isVersionBelow(spec: string, minimumMajor: number, minimumMinor: number) {
  const version = parseSpecVersion(spec)
  if (!version) return false
  if (version.major !== minimumMajor) {
    return version.major < minimumMajor
  }
  return version.minor < minimumMinor
}
