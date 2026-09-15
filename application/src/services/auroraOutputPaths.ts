/**
 * auroraOutputPaths.ts — Coordinateur central des chemins de sortie pour AuroraIA.
 *
 * Règle d'architecture stricte :
 * Tout module écrit ses fichiers et résultats sous :
 *   application/output/<nom_du_module>/<nom_du_projet>/...
 *
 * Aucune sortie ne doit être éparpillée à la racine de output/ ni dans du temporaire.
 */

export const CANONICAL_MODULES: Record<string, string> = {
  '3d': '3d',
  'three_d': '3d',
  'threed': '3d',
  'code': 'code',
  'coding': 'code',
  'coder': 'code',
  'video': 'video',
  'cinema': 'video',
  'film': 'video',
  'image': 'image',
  'images': 'image',
  'img': 'image',
  'voix': 'voix',
  'voice': 'voix',
  'audio': 'voix',
  'tts': 'voix',
  'cyber': 'cyber',
  'security': 'cyber',
  'context': 'context',
  'ent': 'context',
  'cowork': 'cowork',
  'manga': 'manga',
  'academy': 'academy',
}

export function sanitizeSlug(name: string, maxlen = 64): string {
  if (!name) return 'projet'
  return name
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-zA-Z0-9_-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .toLowerCase()
    .slice(0, maxlen) || 'projet'
}

/**
 * Retourne le chemin relatif standard d'un module et projet sous output/
 * Ex: getModuleOutputDir('code', 'mon-app') -> 'output/code/mon-app'
 */
export function getModuleOutputDir(
  moduleName: string,
  projectName?: string,
  subfolder?: string,
): string {
  const canonical = CANONICAL_MODULES[moduleName.toLowerCase()] || sanitizeSlug(moduleName)
  let target = `output/${canonical}`
  if (projectName) {
    target += `/${sanitizeSlug(projectName)}`
  }
  if (subfolder) {
    target += `/${sanitizeSlug(subfolder)}`
  }
  return target
}

export function getCodeProjectOutputDir(projectName: string): string {
  return getModuleOutputDir('code', projectName)
}

export function getCodeProjectAssetsDir(projectName?: string, runId?: string): string {
  if (projectName) {
    return getModuleOutputDir('code', projectName, 'assets')
  }
  if (runId) {
    return getModuleOutputDir('code', 'assets', runId)
  }
  return getModuleOutputDir('code', 'assets')
}

export function getCodeProjectApkDir(projectName?: string): string {
  if (projectName) {
    return getModuleOutputDir('code', projectName, 'apk')
  }
  return getModuleOutputDir('code', 'apk')
}

export function getCodeProjectSandboxDir(sandboxId?: string): string {
  if (sandboxId) {
    return getModuleOutputDir('code', 'sandbox', sandboxId)
  }
  return getModuleOutputDir('code', 'sandbox')
}

export function getVideoProjectOutputDir(projectName: string): string {
  return getModuleOutputDir('video', projectName)
}

export function get3dProjectOutputDir(projectName: string): string {
  return getModuleOutputDir('3d', projectName)
}

export function getImageProjectOutputDir(projectName: string): string {
  return getModuleOutputDir('image', projectName)
}

export function getVoiceProjectOutputDir(projectName: string): string {
  return getModuleOutputDir('voix', projectName)
}

export function getCyberProjectOutputDir(projectName: string): string {
  return getModuleOutputDir('cyber', projectName)
}

export function getCoworkOutputDir(projectName: string, customPath?: string): string {
  if (customPath && customPath.trim()) {
    return customPath.trim()
  }
  return getModuleOutputDir('cowork', projectName)
}

export function getContextProjectOutputDir(projectName: string): string {
  return getModuleOutputDir('context', projectName)
}

export function getMangaProjectOutputDir(projectName: string): string {
  return getModuleOutputDir('manga', projectName)
}

export function getAcademyProjectOutputDir(projectName: string): string {
  return getModuleOutputDir('academy', projectName)
}
