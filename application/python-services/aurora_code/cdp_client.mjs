import { existsSync, readdirSync, statSync } from 'node:fs'
import { homedir, platform } from 'node:os'
import { join } from 'node:path'
import net from 'node:net'

export const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

function firstExisting(paths) {
  return paths.find((candidate) => candidate && existsSync(candidate)) || null
}

function findPlaywrightChromium() {
  const root = join(homedir(), '.cache', 'ms-playwright')
  if (!existsSync(root)) return null
  try {
    const dirs = readdirSync(root)
      .filter((name) => /^chromium-\d+/.test(name))
      .sort()
      .reverse()
    for (const dir of dirs) {
      const base = join(root, dir)
      const found = firstExisting([
        join(base, 'chrome-linux64', 'chrome'),
        join(base, 'chrome-linux', 'chrome'),
        join(base, 'chrome-mac', 'Chromium.app', 'Contents', 'MacOS', 'Chromium'),
        join(base, 'chrome-win', 'chrome.exe'),
      ])
      if (found && statSync(found).isFile()) return found
    }
  } catch {
    return null
  }
  return null
}

export function resolveChromePath() {
  const envPath = process.env.CHROME_PATH || process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
  if (envPath && existsSync(envPath)) return envPath

  if (platform() === 'win32') {
    const local = process.env.LOCALAPPDATA || ''
    const programFiles = process.env.PROGRAMFILES || 'C:\\Program Files'
    const programFilesX86 = process.env['PROGRAMFILES(X86)'] || 'C:\\Program Files (x86)'
    return firstExisting([
      join(programFiles, 'Google', 'Chrome', 'Application', 'chrome.exe'),
      join(programFilesX86, 'Google', 'Chrome', 'Application', 'chrome.exe'),
      join(local, 'Google', 'Chrome', 'Application', 'chrome.exe'),
    ])
  }

  if (platform() === 'darwin') {
    return firstExisting([
      '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
      '/Applications/Chromium.app/Contents/MacOS/Chromium',
    ]) || findPlaywrightChromium()
  }

  return firstExisting([
    '/usr/bin/google-chrome-stable',
    '/usr/bin/google-chrome',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
    '/snap/bin/chromium',
    '/usr/bin/brave-browser',
  ]) || findPlaywrightChromium()
}

export function freePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer()
    server.listen(0, () => {
      const port = server.address().port
      server.close(() => resolve(port))
    })
    server.on('error', reject)
  })
}

export async function getJSON(url) {
  const response = await fetch(url)
  const text = await response.text()
  const start = text.search(/[\[{]/)
  return JSON.parse(start >= 0 ? text.slice(start) : text)
}

export class CDP {
  constructor(wsUrl) {
    this.wsUrl = wsUrl
    this.id = 0
    this.pending = new Map()
    this.events = []
    this.handlers = new Map()
  }

  on(method, handler) {
    if (!this.handlers.has(method)) this.handlers.set(method, [])
    this.handlers.get(method).push(handler)
  }

  connect() {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(this.wsUrl)
      this.ws.onopen = () => resolve()
      this.ws.onerror = (error) => reject(error)
      this.ws.onmessage = (message) => {
        const payload = JSON.parse(message.data)
        if (payload.id && this.pending.has(payload.id)) {
          const pending = this.pending.get(payload.id)
          this.pending.delete(payload.id)
          payload.error
            ? pending.reject(new Error(JSON.stringify(payload.error)))
            : pending.resolve(payload.result)
        } else if (payload.method) {
          this.events.push(payload)
          const handlers = this.handlers.get(payload.method) || []
          for (const handler of handlers) {
            try {
              handler(payload.params)
            } catch {
              // A consumer event handler must not break the CDP stream.
            }
          }
        }
      }
    })
  }

  send(method, params = {}) {
    const id = ++this.id
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject })
      this.ws.send(JSON.stringify({ id, method, params }))
      setTimeout(() => {
        if (this.pending.has(id)) {
          this.pending.delete(id)
          reject(new Error(`timeout ${method}`))
        }
      }, 30000)
    })
  }

  async waitEvent(method, timeoutMs = 15000) {
    const startedAt = Date.now()
    while (Date.now() - startedAt < timeoutMs) {
      const event = this.events.find((candidate) => candidate.method === method)
      if (event) return event
      await sleep(80)
    }
    return null
  }
}
