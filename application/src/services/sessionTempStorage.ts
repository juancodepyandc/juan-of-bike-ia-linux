// This module provides server-side temporary session storage utilities.
// It may be imported on the frontend during bundling; to avoid breaking the
// build we export safe no-op stubs when Node's FS API is unavailable.

let isNode = false
try {
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  isNode = typeof process !== 'undefined' && !!(process.versions && process.versions.node)
} catch {
  isNode = false
}

if (!isNode) {
  // Browser-friendly stubs: throw informative errors when called.
  const err = (fnName: string) => () => { throw new Error(`${fnName} is not available in the browser runtime. Use the bridge backend instead.`) }

  export const sessionDir = err('sessionDir') as unknown as (s: string) => string
  export const ensureSessionDir = err('ensureSessionDir') as unknown as (s: string) => Promise<string>
  export const writeTempFile = err('writeTempFile') as unknown as (s: string, f: string, c: string | Buffer) => Promise<string>
  export const readTempFile = err('readTempFile') as unknown as (s: string, f: string) => Promise<Buffer>
  export const listTempFiles = err('listTempFiles') as unknown as (s: string) => Promise<string[]>
  export const removeSessionDir = err('removeSessionDir') as unknown as (s: string) => Promise<void>
  export const cleanupOlderThan = err('cleanupOlderThan') as unknown as (d: number) => Promise<string[]>

} else {
  // Node implementation
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const fs = require('fs')
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const path = require('path')

  const BASE_DIR = path.join(process.cwd(), 'application', 'temp-sessions')

  function ensureBaseDir(): void {
    if (!fs.existsSync(BASE_DIR)) fs.mkdirSync(BASE_DIR, { recursive: true })
  }

  export function sessionDir(sessionId: string): string {
    ensureBaseDir()
    return path.join(BASE_DIR, sessionId)
  }

  export async function ensureSessionDir(sessionId: string): Promise<string> {
    const dir = sessionDir(sessionId)
    await fs.promises.mkdir(dir, { recursive: true })
    return dir
  }

  export async function writeTempFile(sessionId: string, filename: string, content: string | Buffer): Promise<string> {
    const dir = await ensureSessionDir(sessionId)
    const safeName = path.basename(filename)
    const filePath = path.join(dir, safeName)
    await fs.promises.writeFile(filePath, content)
    return filePath
  }

  export async function readTempFile(sessionId: string, filename: string): Promise<Buffer> {
    const filePath = path.join(sessionDir(sessionId), path.basename(filename))
    return fs.promises.readFile(filePath)
  }

  export async function listTempFiles(sessionId: string): Promise<string[]> {
    const dir = sessionDir(sessionId)
    try {
      const files = await fs.promises.readdir(dir)
      return files
    } catch {
      return []
    }
  }

  export async function removeSessionDir(sessionId: string): Promise<void> {
    const dir = sessionDir(sessionId)
    try {
      await fs.promises.rm(dir, { recursive: true, force: true })
    } catch {
      // ignore
    }
  }

  export async function cleanupOlderThan(days: number): Promise<string[]> {
    ensureBaseDir()
    const now = Date.now()
    const cutoff = now - days * 86_400_000
    const removed: string[] = []
    const sessions = await fs.promises.readdir(BASE_DIR)
    for (const sid of sessions) {
      const stat = await fs.promises.stat(path.join(BASE_DIR, sid))
      if (stat.mtime.getTime() < cutoff) {
        await fs.promises.rm(path.join(BASE_DIR, sid), { recursive: true, force: true })
        removed.push(sid)
      }
    }
    return removed
  }

}
