// ---------------------------------------------------------------------------
// Generated file parsing
// Extracted from codeOrchestrator.ts during WS1 modularisation.
// ---------------------------------------------------------------------------

import type { CodeFile } from './codeOrchestrator.ts'
import { isLLMRefusal } from './codeLLMRefusal.ts'
import { sanitizeGeneratedFileContent, stripFormattingArtifacts } from './codeGeneratedFileSanitizer.ts'

export function parseCodeFiles(content: string): CodeFile[] {
  const files: CodeFile[] = []
  const parts = content.split(/---\s*(?:FICHIER|FILE):\s*(.+?)\s*---/i)

  if (parts.length > 1) {
    for (let index = 1; index < parts.length; index += 2) {
      const name = parts[index].trim()
      const code = sanitizeGeneratedFileContent(name, cleanCodeBlock(parts[index + 1] || ''))
      if (!name || !code) continue
      files.push({ name, language: detectLanguage(name), content: code })
    }
  }

  if (files.length === 0) {
    const codeBlockRegex = /```(\w+)?\n([\s\S]*?)```/g
    let match: RegExpExecArray | null
    let blockIndex = 1
    while ((match = codeBlockRegex.exec(content)) !== null) {
      let language = match[1] || 'txt'
      const blockContent = match[2].trim()
      if (!blockContent) continue

      // Smart language detection: if the tag is generic (markdown, text, txt)
      // but content looks like actual code, override the tag
      if (['markdown', 'md', 'text', 'txt', ''].includes(language.toLowerCase())) {
        const detectedLang = detectContentLanguage(blockContent)
        if (detectedLang) language = detectedLang
      }

      const ext = langToExt(language)
      const name = inferFileName(blockContent, ext, blockIndex)
      files.push({ name, language, content: sanitizeGeneratedFileContent(name, blockContent) })
      blockIndex += 1
    }
  }

  if (files.length === 0 && content.trim()) {
    // If the content is a refusal, return empty — do NOT create reponse.txt with garbage
    if (isLLMRefusal(content)) {
      return []
    }

    if (detectNonCodePlanningNarrative(content)) {
      return []
    }

    // Last resort: check if the raw content IS code (LLM forgot code fences)
    const detectedLang = detectContentLanguage(content.trim())
    if (detectedLang) {
      const ext = langToExt(detectedLang)
      files.push({ name: `main.${ext}`, language: detectedLang, content: sanitizeGeneratedFileContent(`main.${ext}`, cleanCodeBlock(content)) })
    } else {
      // Only create reponse.txt if content is substantial and not a refusal
      const cleaned = cleanCodeBlock(content)
      if (cleaned.length > 100) {
        files.push({ name: 'reponse.txt', language: 'text', content: sanitizeGeneratedFileContent('reponse.txt', cleaned) })
      }
    }
  }

  return files
}

function cleanCodeBlock(text: string) {
  let t = text.replace(/\r\n/g, '\n').trim()
  // A file segment (the text between two `--- FICHIER: … ---` markers) usually
  // wraps the code in a markdown fence. Models sometimes append a stray closing
  // fence and even extra ```css / ```bash blocks AFTER the file's real code —
  // the next file's content emitted without its own separator. The old strip
  // (one leading + one trailing fence) left that junk in the file, which breaks
  // it: a trailing "```css" inside game.js throws
  //   Uncaught SyntaxError: Unexpected identifier 'css'
  // and the whole script (the game) never runs. When the segment is
  // fence-wrapped, keep ONLY the first fenced block's body.
  const opening = t.match(/^```[\w.+#-]*[ \t]*\n/)
  if (opening) {
    const body = t.slice(opening[0].length)
    const closeIdx = body.search(/\n```[ \t]*(?:\n|$)/)
    if (closeIdx !== -1) return body.slice(0, closeIdx).trim()
    // No closing fence — drop the opener and fall through to line cleanup.
    t = body
  }
  // Strip any remaining standalone markdown fence lines (opener or closer).
  t = t.replace(/^[ \t]*```[\w.+#-]*[ \t]*$/gm, '').trim()
  return t
}


function detectLanguage(filename: string) {
  const ext = filename.split('.').pop()?.toLowerCase() || ''
  const map: Record<string, string> = {
    c: 'c', cc: 'cpp', cpp: 'cpp', cs: 'csharp', css: 'css', dart: 'dart',
    ex: 'elixir', go: 'go', h: 'c', hpp: 'cpp', hs: 'haskell', html: 'html',
    java: 'java', js: 'javascript', json: 'json', jsx: 'javascript', kt: 'kotlin',
    lua: 'lua', md: 'markdown', mjs: 'javascript', php: 'php', py: 'python',
    r: 'r', rb: 'ruby', rs: 'rust', scala: 'scala', scss: 'scss', sh: 'bash',
    sql: 'sql', swift: 'swift', svelte: 'svelte', toml: 'toml', ts: 'typescript',
    tsx: 'typescript', txt: 'text', vue: 'vue', xml: 'xml', yaml: 'yaml',
    yml: 'yaml', zig: 'zig', dockerfile: 'dockerfile',
  }
  return map[ext] || 'text'
}

/**
 * Detect the actual programming language from content patterns.
 * Used when the LLM tags a code block as "markdown" or "text" but
 * the content is actually HTML/CSS/JS/Python/etc.
 */
export function detectContentLanguage(content: string): string | null {
  const trimmed = content.slice(0, 500)

  // HTML detection
  if (/<!DOCTYPE\s+html/i.test(trimmed) || /<html[\s>]/i.test(trimmed) || /<head[\s>]/i.test(trimmed)) {
    return 'html'
  }

  // CSS detection
  if (/^[\s]*[.#@][\w-]+\s*\{/m.test(trimmed) || /:\s*(flex|grid|block|none|auto|inherit);/i.test(trimmed)) {
    return 'css'
  }

  // JavaScript/TypeScript detection
  if (/^(import|export|const|let|var|function|class|async)\s/m.test(trimmed)) {
    if (/:\s*(string|number|boolean|void|any|Promise<)/m.test(trimmed)) {
      return 'typescript'
    }
    return 'javascript'
  }

  // Python detection
  if (/^(def |class |import |from .+ import |if __name__)/m.test(trimmed)) {
    return 'python'
  }

  // JSON detection
  if (/^\s*\{[\s\S]*"[\w]+"\s*:/m.test(trimmed)) {
    return 'json'
  }

  // Rust detection
  if (/^(use |fn |pub |mod |struct |impl |enum )/m.test(trimmed)) {
    return 'rust'
  }

  // Go detection
  if (/^package\s+\w+/m.test(trimmed) || /^func\s+/m.test(trimmed)) {
    return 'go'
  }

  return null
}

/**
 * Try to infer a meaningful file name from the content.
 * Falls back to bloc-N.ext if no pattern matches.
 */
function inferFileName(content: string, ext: string, index: number): string {
  const trimmed = content.slice(0, 300)

  // HTML with a title → use a meaningful name
  if (ext === 'html') return index === 1 ? 'index.html' : `page-${index}.html`
  if (ext === 'css') return index === 1 ? 'style.css' : `style-${index}.css`

  // JS with common patterns
  if (ext === 'js' || ext === 'ts') {
    if (/addEventListener.*DOMContentLoaded/i.test(trimmed) || /document\.(getElementById|querySelector)/i.test(trimmed)) {
      return index === 1 ? 'script.js' : `script-${index}.js`
    }
    if (/express\(\)|createServer|app\.listen/i.test(trimmed)) return 'server.js'
    if (/export default function|export default class/i.test(trimmed)) return `component-${index}.${ext}`
    return index === 1 ? `main.${ext}` : `module-${index}.${ext}`
  }

  // Python
  if (ext === 'py') {
    if (/FastAPI|Flask|Django/i.test(trimmed)) return 'app.py'
    if (/if __name__/i.test(trimmed)) return 'main.py'
    return index === 1 ? `main.py` : `module_${index}.py`
  }

  // JSON — likely package.json or config
  if (ext === 'json') {
    if (/"name"\s*:/.test(trimmed) && /"version"\s*:/.test(trimmed)) return 'package.json'
    if (/"compilerOptions"/i.test(trimmed)) return 'tsconfig.json'
    return `config-${index}.json`
  }

  return `bloc-${index}.${ext}`
}

function langToExt(language: string) {
  const map: Record<string, string> = {
    bash: 'sh', c: 'c', cpp: 'cpp', csharp: 'cs', css: 'css', dart: 'dart',
    dockerfile: 'Dockerfile', elixir: 'ex', go: 'go', haskell: 'hs', html: 'html',
    java: 'java', javascript: 'js', json: 'json', kotlin: 'kt', lua: 'lua',
    markdown: 'md', php: 'php', python: 'py', r: 'r', ruby: 'rb', rust: 'rs',
    scala: 'scala', scss: 'scss', sql: 'sql', svelte: 'svelte', swift: 'swift',
    text: 'txt', toml: 'toml', typescript: 'ts', vue: 'vue', xml: 'xml',
    yaml: 'yml', zig: 'zig',
  }
  return map[language.toLowerCase()] || language.toLowerCase()
}

export function serializeCodeFiles(files: CodeFile[]) {
  return files.map((f) => [
    `--- FICHIER: ${f.name} ---`,
    `\`\`\`${f.language}`,
    f.content,
    '```',
  ].join('\n')).join('\n\n')
}

export function extractNotes(content: string) {
  const parts = content.split(/---\s*NOTES\s*---/i)
  return parts.length < 2 ? '' : parts.slice(1).join('\n').trim()
}


const NON_CODE_PLANNING_PATTERNS = [
  /(^|\n)\s*Projet detecte\b/i,
  /(^|\n)\s*Type:\s*/i,
  /(^|\n)\s*Complexite:\s*/i,
  /(^|\n)\s*Frameworks?:\s*/i,
  /(^|\n)\s*Features?:\s*/i,
  /(^|\n)\s*Stack:\s*/i,
  /(^|\n)\s*Dev server:\s*/i,
  /(^|\n)\s*Preflight local\b/i,
  /(^|\n)\s*Contraintes locales:\s*/i,
  /(^|\n)\s*A inspecter d abord:\s*/i,
]

export function detectNonCodePlanningNarrative(content: string) {
  const trimmed = stripFormattingArtifacts(content)
  if (!trimmed) return null
  if (/---\s*(?:FICHIER|FILE):\s*/i.test(trimmed)) return null
  if (/```[\w.+-]+\s*\r?\n[\s\S]*?```/i.test(trimmed)) return null
  if (isLLMRefusal(trimmed)) return null
  if (detectContentLanguage(trimmed)) return null

  const matchCount = NON_CODE_PLANNING_PATTERNS.filter((pattern) => pattern.test(trimmed)).length
  if (matchCount < 2) return null

  return 'La sortie est un diagnostic, un preflight ou un plan narratif au lieu de vrais fichiers de code.'
}
