import {
  buildBrowserWorkspacePreviewHtml,
  supportsBrowserWorkspaceRuntime,
} from '../services/codeBrowserWorkspaceRuntime'
import { buildAuroraInlineSvgDataUri } from '../services/codeVisualFallbacks.ts'

type CodeFile = {
  name: string
  language: string
  content: string
}

export function buildLivePreviewHtml(files: CodeFile[]): string | null {
  return buildPreviewHtml(files)
}

export function webProjectFromFiles(files: CodeFile[]): boolean {
  return isWebProject(files)
}

export function isWebProject(files: CodeFile[]) {
  return files.some((file) => /\.(html|htm)$/i.test(file.name))
    || supportsBrowserWorkspaceRuntime(files)
    || files.some((file) => /\.(css|scss|less|js|mjs|ts|tsx|jsx)$/i.test(file.name) && file.content.trim().length > 0)
}

function escapeRegex(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function stripFileBasename(name: string): string {
  return name.replace(/\\/g, '/').split('/').pop() || name
}

function collapseRepeatedSvgElements(html: string): string {
  return html.replace(
    /(<(rect|circle|line|path|ellipse|polygon)\b[^>]*\/?>)((?:\s*\1){2,})/g,
    (_match, single) => single,
  )
}

function patchUnresolvedImageSrcs(html: string): string {
  return html.replace(
    /<img([^>]*?)src=(["'])([^"']+)\2([^>]*)>/gi,
    (match, prefix, quote, src, suffix) => {
      if (/^data:/i.test(src) || /^https?:\/\//i.test(src)) return match

      const altMatch = match.match(/alt=(["'])([^"']*)\1/i)
      const altRaw = (altMatch?.[2] || '').trim()
      const pathQuery = src.replace(/^[./]*/, '').replace(/\.[^.]+$/, '').replace(/[\-_/]+/g, ' ').trim()
      const query = (altRaw || pathQuery || 'hero').slice(0, 80)
      const fallbackData = buildAuroraInlineSvgDataUri(query, { width: 1600, height: 900 })
      const altAttr = altRaw ? '' : ` alt="${query.replace(/"/g, '&quot;')}"`
      return `<img${prefix}src=${quote}${fallbackData}${quote}${suffix}${altAttr}>`
    },
  )
}

function ensureHtmlScaffold(body: string): string {
  if (/<html[\s>]/i.test(body)) return body
  return `<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Apercu</title></head><body>${body}</body></html>`
}

export function buildPreviewHtml(files: CodeFile[]): string | null {
  const htmlFile = files.find((file) => /\.(html|htm)$/i.test(file.name))
  let html: string
  if (htmlFile) {
    html = htmlFile.content.trim()
    if (!html) return null
    html = ensureHtmlScaffold(html)
  } else {
    const workspaceHtml = buildBrowserWorkspacePreviewHtml(files)
    if (workspaceHtml) return workspaceHtml
    const hasCss = files.some((file) => /\.(css|scss|less)$/i.test(file.name))
    const hasJs = files.some((file) => /\.(js|mjs)$/i.test(file.name))
    if (!hasCss && !hasJs) return null
    html = '<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8"><title>Apercu</title></head><body><main id="root" style="padding:2rem;font-family:system-ui"></main></body></html>'
  }

  for (const file of files) {
    if (!/\.(css|scss|less)$/i.test(file.name)) continue
    const base = escapeRegex(stripFileBasename(file.name))
    const linkPattern = new RegExp(`<link[^>]*href=["'][^"']*${base}["'][^>]*>`, 'gi')
    const styleBlock = `<style data-file="${file.name}">\n${file.content}\n</style>`
    if (linkPattern.test(html)) {
      html = html.replace(linkPattern, styleBlock)
    } else if (/<\/head>/i.test(html)) {
      html = html.replace(/<\/head>/i, `${styleBlock}\n</head>`)
    } else if (/<head[^>]*>/i.test(html)) {
      html = html.replace(/<head[^>]*>/i, (match) => `${match}\n${styleBlock}`)
    } else {
      html = styleBlock + html
    }
  }

  for (const file of files) {
    if (!/\.(js|mjs)$/i.test(file.name)) continue
    const base = escapeRegex(stripFileBasename(file.name))
    const scriptPattern = new RegExp(`(<script[^>]*src=["'][^"']*${base}["'][^>]*>)\\s*</script>`, 'gi')
    const isModule = /^\s*import\s/m.test(file.content) || /export\s+(default|\{|const|function|class)/m.test(file.content)
    const scriptBlock = `<script${isModule ? ' type="module"' : ''} data-file="${file.name}">\n${file.content}\n</script>`
    if (scriptPattern.test(html)) {
      html = html.replace(scriptPattern, scriptBlock)
    } else if (/<\/body>/i.test(html)) {
      html = html.replace(/<\/body>/i, `${scriptBlock}\n</body>`)
    } else {
      html += scriptBlock
    }
  }

  html = patchUnresolvedImageSrcs(html)
  html = collapseRepeatedSvgElements(html)

  if (/<body[^>]*>\s*<\/body>/i.test(html)) {
    html = html.replace(
      /<body([^>]*)>\s*<\/body>/i,
      (_match, attrs) => `<body${attrs}>\n<div style="min-height:100vh;display:grid;place-items:center;background:#0d1117;color:#c9d1d9;font-family:system-ui"><div style="text-align:center"><div style="font-size:14px;opacity:.85">Le modele ecrit la page...</div><div style="margin-top:.4rem;font-size:11px;opacity:.55">Les styles et le contenu vont apparaitre ici progressivement.</div></div></div>\n</body>`,
    )
  }

  return html
}
