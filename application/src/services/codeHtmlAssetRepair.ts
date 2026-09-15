import type { CodeFile } from "./codeOrchestratorTypes.ts"

export function repairHtmlAssetLinks(files: CodeFile[]): CodeFile[] {
  const htmlIndex = files.findIndex((f) => /(^|\/)index\.html?$/i.test(f.name))
  if (htmlIndex < 0) return files
  const htmlFile = files[htmlIndex]
  let content = htmlFile.content

  const cssPaths = files.filter((f) => /\.(css|scss|less)$/i.test(f.name)).map((f) => f.name.replace(/\\/g, "/"))
  const jsPaths = files.filter((f) => /\.(js|mjs|ts|tsx|jsx)$/i.test(f.name) && !f.name.endsWith(".d.ts")).map((f) => f.name.replace(/\\/g, "/"))

  // Aligner les chemins des balises script locales
  content = content.replace(/<script\b([^>]*)\bsrc=["']([^"']+)["']([^>]*)>\s*<\/script>/gi, (match, before, src, after) => {
    if (/^(?:https?:)?\/\//i.test(src) || src.startsWith("data:")) return match
    const cleanSrc = src.replace(/^\.?\//, "")
    if (jsPaths.includes(cleanSrc)) return match
    const base = cleanSrc.split("/").pop()?.toLowerCase() || ""
    const matchPath = jsPaths.find((p) => p.toLowerCase().endsWith(base)) || jsPaths[0]
    if (matchPath) return `<script${before}src="${matchPath}"${after}></script>`
    return match
  })

  // Aligner les chemins des feuilles de style locales
  content = content.replace(/<link\b([^>]*)\bhref=["']([^"']+)["']([^>]*)>/gi, (match, before, href, after) => {
    if (/^(?:https?:)?\/\//i.test(href) || href.startsWith("data:") || !/rel=["']?stylesheet/i.test(match)) return match
    const cleanHref = href.replace(/^\.?\//, "")
    if (cssPaths.includes(cleanHref)) return match
    const base = cleanHref.split("/").pop()?.toLowerCase() || ""
    const matchPath = cssPaths.find((p) => p.toLowerCase().endsWith(base)) || cssPaths[0]
    if (matchPath) return `<link${before}href="${matchPath}"${after}>`
    return match
  })

  if (content === htmlFile.content) return files
  return files.map((f, i) => (i === htmlIndex ? { ...f, content } : f))
}
