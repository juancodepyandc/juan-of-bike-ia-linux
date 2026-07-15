export type DetectedCodeLanguage = {
  lang: string
  confidence: number
  shebang: boolean
}

// Heuristique langage du fichier: extension prioritaire, signature fallback.
export function detectFileLanguage(name: string, content: string): DetectedCodeLanguage {
  const baseName = name.split('/').pop()?.toLowerCase() ?? name.toLowerCase()
  const specialNames: Record<string, string> = {
    dockerfile: 'dockerfile',
    makefile: 'makefile',
  }
  const ext = baseName.includes('.') ? baseName.split('.').pop()?.toLowerCase() ?? '' : ''
  const EXT_MAP: Record<string, string> = {
    ts: 'ts', tsx: 'tsx', js: 'js', jsx: 'jsx', mjs: 'js', cjs: 'js',
    py: 'python', rs: 'rust', go: 'go', java: 'java', kt: 'kotlin',
    swift: 'swift', scala: 'scala', c: 'c', cc: 'cpp', cpp: 'cpp', cs: 'csharp', h: 'c',
    hpp: 'cpp', rb: 'ruby', php: 'php', lua: 'lua', sh: 'bash', bash: 'bash',
    zsh: 'bash', ps1: 'powershell', html: 'html', htm: 'html', css: 'css',
    scss: 'scss', sass: 'sass', less: 'less', json: 'json', yaml: 'yaml',
    yml: 'yaml', toml: 'toml', md: 'markdown', sql: 'sql',
  }
  const shebang = /^#!/.test(content)
  if (!ext && specialNames[baseName]) return { lang: specialNames[baseName], confidence: 0.98, shebang }
  if (EXT_MAP[ext]) return { lang: EXT_MAP[ext], confidence: 0.98, shebang }
  if (shebang) {
    if (/python/.test(content.slice(0, 80))) return { lang: 'python', confidence: 0.85, shebang: true }
    if (/bash|sh/.test(content.slice(0, 80))) return { lang: 'bash', confidence: 0.85, shebang: true }
  }
  if (/^\s*import\s+\w+\s+from\s+['"]/.test(content) || /export\s+(default|const|function)/.test(content)) {
    return { lang: 'ts', confidence: 0.6, shebang: false }
  }
  if (/^\s*def\s+\w+\s*\(/.test(content) || /^\s*from\s+\w+\s+import/.test(content)) {
    return { lang: 'python', confidence: 0.6, shebang: false }
  }
  if (/^\s*fn\s+\w+\s*\(/.test(content)) {
    return { lang: 'rust', confidence: 0.6, shebang: false }
  }
  return { lang: ext || 'plaintext', confidence: 0.3, shebang }
}
