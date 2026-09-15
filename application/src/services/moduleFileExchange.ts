import { fsWriteText, fsMkdir, getWorkspacePath } from '../hooks/useTauri.ts'

export interface ModuleIncomingFile {
  filename: string
  content: string | ArrayBuffer
  type?: string
  size?: number
  metadata?: Record<string, unknown>
}

export interface ProcessedIncomingFile {
  filename: string
  extension: string
  category: 'code' | 'document' | 'dataset' | 'security_dump' | 'image' | 'binary'
  textSummary?: string
  rawText?: string
  byteLength: number
  metadata: Record<string, unknown>
}

export interface ModuleOutgoingFile {
  filename: string
  content: string
  category?: string
  format?: 'markdown' | 'json' | 'yaml' | 'python' | 'latex' | 'raw'
  metadata?: Record<string, unknown>
}

export interface EmittedArtifactResult {
  filename: string
  targetPath: string
  byteLength: number
  category: string
  format: string
  timestamp: string
}

export type SupportedModuleTarget = 'conversation' | 'academic' | 'cyber'

export interface ModuleFileStorage {
  workspacePath: () => Promise<string>
  mkdir: (path: string) => Promise<void>
  writeText: (path: string, content: string) => Promise<void>
}

const defaultStorage: ModuleFileStorage = {
  workspacePath: getWorkspacePath,
  mkdir: fsMkdir,
  writeText: fsWriteText,
}

const MODULE_OUTPUT_ROOTS: Record<SupportedModuleTarget, string> = {
  conversation: 'output/conversation',
  academic: 'output/academy',
  cyber: 'output/cyber',
}

/**
 * Analyse et structure intelligemment les fichiers entrants (un ou plusieurs)
 * pour alimenter le contexte d'analyse des modèles (Qwen3.8, Phantom, Sage, Lyra).
 */
export function processIncomingFiles(
  files: ModuleIncomingFile[]
): ProcessedIncomingFile[] {
  return files.map((file) => {
    const ext = (file.filename.split('.').pop() || '').toLowerCase()
    let category: ProcessedIncomingFile['category'] = 'document'

    if (['py', 'ts', 'js', 'cpp', 'c', 'rs', 'go', 'java', 'html', 'css'].includes(ext)) {
      category = 'code'
    } else if (['json', 'csv', 'parquet', 'sql', 'xml'].includes(ext)) {
      category = 'dataset'
    } else if (['pcap', 'log', 'dmp', 'yara', 'yar', 'sigma', 'rule'].includes(ext)) {
      category = 'security_dump'
    } else if (['png', 'jpg', 'jpeg', 'webp', 'svg'].includes(ext)) {
      category = 'image'
    } else if (['bin', 'exe', 'elf', 'so', 'dll'].includes(ext)) {
      category = 'binary'
    }

    let rawText = ''
    let byteLength = file.size || 0

    if (typeof file.content === 'string') {
      rawText = file.content
      byteLength = new TextEncoder().encode(rawText).length
    } else if (file.content instanceof ArrayBuffer) {
      byteLength = file.content.byteLength
      try {
        rawText = new TextDecoder('utf-8', { fatal: false }).decode(file.content)
      } catch {
        rawText = `[Fichier binaire : ${byteLength} octets]`
      }
    }

    const preview = rawText.slice(0, 1500)
    const textSummary = `Fichier: ${file.filename} (${category}, ${byteLength} o)\nAperçu:\n${preview}${rawText.length > 1500 ? '\n... [tronqué]' : ''}`

    return {
      filename: file.filename,
      extension: ext,
      category,
      textSummary,
      rawText,
      byteLength,
      metadata: file.metadata || {},
    }
  })
}

/**
 * Génère, formate et persiste un ensemble de fichiers d'artefacts (un ou plusieurs)
 * dans l'arborescence dédiée du module cible.
 */
export async function emitModuleFiles(
  moduleTarget: SupportedModuleTarget,
  files: ModuleOutgoingFile[],
  storage: ModuleFileStorage = defaultStorage,
): Promise<EmittedArtifactResult[]> {
  if (!Object.prototype.hasOwnProperty.call(MODULE_OUTPUT_ROOTS, moduleTarget)) {
    throw new Error(`Module de destination inconnu : ${moduleTarget}`)
  }
  const prepared = files.map((file) => {
    const category = file.category || 'artifacts'
    if (!/^[\p{L}\p{N}_-]+$/u.test(category)) {
      throw new Error(`Catégorie de fichier invalide : ${category}`)
    }
    const filename = file.filename.replace(/[^a-zA-Z0-9_.-]+/g, '_')
    if (!filename || filename === '.' || filename === '..') {
      throw new Error('Nom de fichier invalide')
    }
    return { ...file, category, filename }
  })
  if (prepared.length === 0) return []
  const workspace = (await storage.workspacePath()).replace(/[\\/]+$/, '')
  const root = `${workspace}/${MODULE_OUTPUT_ROOTS[moduleTarget]}`
  const dateFolder = new Date().toISOString().slice(0, 10)
  const results: EmittedArtifactResult[] = []

  for (const f of prepared) {
    const subCategory = f.category
    const targetDir = `${root}/${subCategory}/${dateFolder}`
    const cleanFilename = f.filename
    const fullPath = `${targetDir}/${cleanFilename}`

    await storage.mkdir(targetDir)
    await storage.writeText(fullPath, f.content)

    results.push({
      filename: cleanFilename,
      targetPath: fullPath,
      byteLength: new TextEncoder().encode(f.content).length,
      category: subCategory,
      format: f.format || 'raw',
      timestamp: new Date().toISOString(),
    })
  }

  return results
}
