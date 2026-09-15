// Node utilities. Browser callers must use the session endpoints on the bridge.
function nodeModules() {
  if (typeof process === 'undefined' || !process.getBuiltinModule) {
    throw new Error('Temporary session storage requires Node 22+; use the bridge in a browser.')
  }
  return {
    fs: process.getBuiltinModule('node:fs'),
    path: process.getBuiltinModule('node:path'),
  }
}

function baseDir(): string {
  const { path } = nodeModules()
  const cwd = process.cwd()
  return path.basename(cwd) === 'application'
    ? path.join(cwd, 'temp-sessions')
    : path.join(cwd, 'application', 'temp-sessions')
}

export function sessionDir(sessionId: string): string {
  if (!/^[a-zA-Z0-9_-]+$/.test(sessionId)) throw new Error('Invalid session id')
  return nodeModules().path.join(baseDir(), sessionId)
}

function filePath(sessionId: string, filename: string): string {
  if (!filename || /[\\/\x00-\x1f]/.test(filename) || filename === '.' || filename === '..') {
    throw new Error('Invalid session filename')
  }
  return nodeModules().path.join(sessionDir(sessionId), filename)
}

async function rejectSymlink(path: string): Promise<void> {
  try {
    if ((await nodeModules().fs.promises.lstat(path)).isSymbolicLink()) {
      throw new Error('Session storage does not follow symbolic links')
    }
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error
  }
}

export async function ensureSessionDir(sessionId: string): Promise<string> {
  const dir = sessionDir(sessionId)
  await rejectSymlink(baseDir())
  await rejectSymlink(dir)
  await nodeModules().fs.promises.mkdir(dir, { recursive: true })
  return dir
}

export async function writeTempFile(sessionId: string, filename: string, content: string | Uint8Array): Promise<string> {
  const target = filePath(sessionId, filename)
  await ensureSessionDir(sessionId)
  await rejectSymlink(target)
  const { fs } = nodeModules()
  const handle = await fs.promises.open(target, fs.constants.O_WRONLY | fs.constants.O_CREAT | fs.constants.O_TRUNC | fs.constants.O_NOFOLLOW, 0o600)
  try {
    await handle.writeFile(content)
  } finally {
    await handle.close()
  }
  return target
}

export async function readTempFile(sessionId: string, filename: string): Promise<Buffer> {
  const target = filePath(sessionId, filename)
  await rejectSymlink(baseDir())
  await rejectSymlink(sessionDir(sessionId))
  const { fs } = nodeModules()
  const handle = await fs.promises.open(target, fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW)
  try {
    return await handle.readFile()
  } finally {
    await handle.close()
  }
}

export async function listTempFiles(sessionId: string): Promise<string[]> {
  const dir = sessionDir(sessionId)
  await rejectSymlink(baseDir())
  await rejectSymlink(dir)
  try {
    return await nodeModules().fs.promises.readdir(dir)
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return []
    throw error
  }
}

export async function removeSessionDir(sessionId: string): Promise<void> {
  const dir = sessionDir(sessionId)
  await rejectSymlink(baseDir())
  await rejectSymlink(dir)
  await nodeModules().fs.promises.rm(dir, { recursive: true, force: true })
}

export async function cleanupOlderThan(days: number): Promise<string[]> {
  if (!Number.isFinite(days) || days <= 0) throw new Error('Retention must be a positive number of days')
  const { fs, path } = nodeModules()
  const base = baseDir()
  await rejectSymlink(base)
  await fs.promises.mkdir(base, { recursive: true })
  const cutoff = Date.now() - days * 86_400_000
  const removed: string[] = []
  for (const entry of await fs.promises.readdir(base, { withFileTypes: true })) {
    if (!entry.isDirectory() || !/^[a-zA-Z0-9_-]+$/.test(entry.name)) continue
    const stat = await fs.promises.lstat(path.join(base, entry.name))
    if (!stat.isSymbolicLink() && stat.mtimeMs < cutoff) {
      await removeSessionDir(entry.name)
      removed.push(entry.name)
    }
  }
  return removed
}
