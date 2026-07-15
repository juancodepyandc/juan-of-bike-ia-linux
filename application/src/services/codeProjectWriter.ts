// ---------------------------------------------------------------------------
// ProjectTree filesystem writer
// WS2: write/read structured projects through the existing Tauri fs bridge.
// ---------------------------------------------------------------------------

import {
  fsMkdir,
  fsReadBinary,
  fsReadText,
  fsWriteBinary,
  fsWriteText,
} from '../hooks/useTauri.ts'
import {
  buildProjectTree,
  type CodeProjectFileEncoding,
  type ProjectTree,
  type ProjectTreeFile,
  type ProjectTreeInputFile,
} from './codeProjectTree.ts'

export type CodeProjectFs = {
  mkdir(path: string): Promise<void>
  writeText(path: string, content: string): Promise<void>
  writeBinary(path: string, bytes: number[]): Promise<void>
  readText(path: string): Promise<string>
  readBinary(path: string): Promise<number[]>
}

export type WrittenProjectFile = {
  path: string
  absolutePath: string
  encoding: CodeProjectFileEncoding
  size: number
}

export type WriteProjectTreeResult = {
  rootPath: string
  directories: string[]
  files: WrittenProjectFile[]
}

const tauriProjectFs: CodeProjectFs = {
  mkdir: fsMkdir,
  writeText: fsWriteText,
  writeBinary: fsWriteBinary,
  readText: fsReadText,
  readBinary: fsReadBinary,
}

function trimRootPath(rootPath: string) {
  return rootPath.replace(/[\\/]+$/, '')
}

export function joinProjectRoot(rootPath: string, projectPath: string) {
  const root = trimRootPath(rootPath)
  const relative = projectPath.replace(/^\/+/, '').replace(/\\/g, '/')
  return root ? `${root}/${relative}` : relative
}

type BufferFactory = {
  from(...args: unknown[]): { toString(encoding: string): string; [Symbol.iterator](): IterableIterator<number> }
}

function getBufferFactory() {
  return (globalThis as { Buffer?: BufferFactory }).Buffer
}

export function decodeBase64ToBytes(content: string) {
  const compact = content.replace(/\s+/g, '')
  if (typeof atob === 'function') {
    const binary = atob(compact)
    return Array.from(binary, (char) => char.charCodeAt(0))
  }

  const bufferFactory = getBufferFactory()
  if (bufferFactory) return Array.from(bufferFactory.from(compact, 'base64'))
  throw new Error('Base64 decoder indisponible dans ce runtime.')
}

export function encodeBytesToBase64(bytes: number[]) {
  const normalized = bytes.map((byte) => byte & 0xff)
  if (typeof btoa === 'function') {
    return btoa(String.fromCharCode(...normalized))
  }

  const bufferFactory = getBufferFactory()
  if (bufferFactory) return bufferFactory.from(Uint8Array.from(normalized)).toString('base64')
  throw new Error('Base64 encoder indisponible dans ce runtime.')
}

function collectParentDirectories(files: ProjectTreeFile[]) {
  const directories = new Set<string>()
  for (const file of files) {
    const parts = file.path.split('/')
    for (let depth = 1; depth < parts.length; depth += 1) {
      directories.add(parts.slice(0, depth).join('/'))
    }
  }
  return [...directories].sort((a, b) => a.length - b.length || (a < b ? -1 : 1))
}

export async function writeProjectTreeToDirectory(
  tree: ProjectTree,
  rootPath: string,
  fs: CodeProjectFs = tauriProjectFs,
): Promise<WriteProjectTreeResult> {
  const normalizedRoot = trimRootPath(rootPath)
  await fs.mkdir(normalizedRoot)

  const directories = collectParentDirectories(tree.files)
  for (const directory of directories) {
    await fs.mkdir(joinProjectRoot(normalizedRoot, directory))
  }

  const writtenFiles: WrittenProjectFile[] = []
  for (const file of tree.files) {
    const absolutePath = joinProjectRoot(normalizedRoot, file.path)
    if (file.encoding === 'base64') {
      const bytes = decodeBase64ToBytes(file.content)
      await fs.writeBinary(absolutePath, bytes)
      writtenFiles.push({ path: file.path, absolutePath, encoding: file.encoding, size: bytes.length })
    } else {
      await fs.writeText(absolutePath, file.content)
      writtenFiles.push({ path: file.path, absolutePath, encoding: file.encoding, size: file.content.length })
    }
  }

  return {
    rootPath: normalizedRoot,
    directories,
    files: writtenFiles,
  }
}

export async function readProjectTreeFromDirectory(
  template: ProjectTree,
  rootPath: string,
  fs: CodeProjectFs = tauriProjectFs,
) {
  const files: ProjectTreeInputFile[] = []
  const normalizedRoot = trimRootPath(rootPath)

  for (const file of template.files) {
    const absolutePath = joinProjectRoot(normalizedRoot, file.path)
    if (file.encoding === 'base64') {
      const bytes = await fs.readBinary(absolutePath)
      files.push({
        path: file.path,
        content: encodeBytesToBase64(bytes),
        encoding: 'base64',
        language: file.language,
        mime: file.mime,
      })
    } else {
      files.push({
        path: file.path,
        content: await fs.readText(absolutePath),
        encoding: 'utf8',
        language: file.language,
        mime: file.mime,
      })
    }
  }

  return buildProjectTree(files)
}

export async function roundTripProjectTreeOnFs(
  tree: ProjectTree,
  rootPath: string,
  fs: CodeProjectFs = tauriProjectFs,
) {
  const writeResult = await writeProjectTreeToDirectory(tree, rootPath, fs)
  const readTree = await readProjectTreeFromDirectory(tree, rootPath, fs)
  return { writeResult, readTree }
}
