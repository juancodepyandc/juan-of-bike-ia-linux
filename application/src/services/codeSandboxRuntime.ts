
// ---------------------------------------------------------------------------
// OS helpers
// ---------------------------------------------------------------------------

export function isWindows(): boolean {
  return typeof navigator !== 'undefined' && /windows/i.test(navigator.userAgent)
}

export function nodeExecutable(name: 'npm' | 'pnpm' | 'yarn' | 'bun') {
  if (isWindows()) {
    if (name === 'bun') return 'bun.exe'
    return `${name}.cmd`
  }
  return name
}

