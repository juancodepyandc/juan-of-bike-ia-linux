// ---------------------------------------------------------------------------
// coworkContentDigest — pure HTML/markup digest extractor used by the planner
// to summarise raw HTML responses (fetch / read_html / read_dom) into a
// structured digest the LLM can synthesise on. Lives in its own file so unit
// tests can import it without dragging in Tauri-only modules (ollamaChat etc.).
//
// The digest mirrors browser.analyze_page : title / description / headings /
// paragraphs / links / images. Pure regex-based — good enough for the 90 %
// case (typical landing pages, articles, dashboards).
// ---------------------------------------------------------------------------

import type { CoworkAction, CoworkActionResult } from './coworkTypes'

export function extractHtmlDigest(html: string): string {
  if (!html || typeof html !== 'string') return '(aucun contenu HTML structurant detecte)'

  const lines: string[] = []
  const m = (re: RegExp) => {
    const x = html.match(re)
    return x ? x[1] : ''
  }
  const title = m(/<title[^>]*>([\s\S]*?)<\/title>/i).trim()
  if (title) lines.push(`title: ${stripTags(title).slice(0, 200)}`)

  const desc = m(/<meta[^>]+name=["']description["'][^>]+content=["']([^"']{1,300})["']/i)
  if (desc) lines.push(`description: ${desc.trim()}`)

  const ogTitle = m(/<meta[^>]+property=["']og:title["'][^>]+content=["']([^"']{1,300})["']/i)
  if (ogTitle && ogTitle !== title) lines.push(`og:title: ${ogTitle.trim()}`)

  const headings: string[] = []
  for (const re of [/<h1[^>]*>([\s\S]*?)<\/h1>/gi, /<h2[^>]*>([\s\S]*?)<\/h2>/gi, /<h3[^>]*>([\s\S]*?)<\/h3>/gi]) {
    let mm: RegExpExecArray | null
    while ((mm = re.exec(html)) !== null && headings.length < 12) {
      const t = stripTags(mm[1]).trim()
      if (t && !headings.includes(t)) headings.push(t)
    }
  }
  if (headings.length) {
    lines.push('headings:')
    for (const h of headings) lines.push(`  - ${h.slice(0, 160)}`)
  }

  const paragraphs: string[] = []
  let pm: RegExpExecArray | null
  const pRe = /<p[^>]*>([\s\S]*?)<\/p>/gi
  while ((pm = pRe.exec(html)) !== null && paragraphs.length < 8) {
    const t = stripTags(pm[1]).trim()
    if (t.length > 20) paragraphs.push(t.slice(0, 200))
  }
  if (paragraphs.length) {
    lines.push('paragraphs:')
    for (const p of paragraphs) lines.push(`  - ${p}`)
  }

  const links: Array<{ text: string; href: string }> = []
  let am: RegExpExecArray | null
  const aRe = /<a\s[^>]*href=["']([^"']+)["'][^>]*>([\s\S]*?)<\/a>/gi
  while ((am = aRe.exec(html)) !== null && links.length < 10) {
    const href = am[1].trim()
    const text = stripTags(am[2]).trim()
    if (!text || href.startsWith('#') || href.startsWith('javascript:')) continue
    if (!links.find((l) => l.href === href)) links.push({ text: text.slice(0, 80), href: href.slice(0, 200) })
  }
  if (links.length) {
    lines.push('links:')
    for (const l of links) lines.push(`  - ${l.text} -> ${l.href}`)
  }

  const imgs: string[] = []
  let im: RegExpExecArray | null
  const imgRe = /<img[^>]+src=["']([^"']+)["'][^>]*>/gi
  while ((im = imgRe.exec(html)) !== null && imgs.length < 5) {
    imgs.push(im[1].slice(0, 200))
  }
  if (imgs.length) lines.push(`images: ${imgs.length} ; ex: ${imgs[0]}`)

  if (lines.length < 4) {
    const bodyText = stripTags(html.replace(/<style[\s\S]*?<\/style>/gi, '').replace(/<script[\s\S]*?<\/script>/gi, ''))
    if (bodyText) lines.push(`textSnippet: ${bodyText.replace(/\s+/g, ' ').trim().slice(0, 600)}`)
  }

  if (lines.length === 0) return '(aucun contenu HTML structurant detecte)'
  return lines.join('\n')
}

// ---------------------------------------------------------------------------
// salvageProseFromMalformedJson — last-resort extractor when the LLM emits
// JSON that doesn't parse. Aurora MUST NOT abandon — we try to find the
// longest coherent reply text inside the malformed output.
//
// Heuristics tried in order :
//   1. Match `"message": "..."` — most common reply structure.
//   2. Longest quoted string > 60 chars.
//   3. Strip JSON syntax and return what's left if substantial.
// Returns null if nothing readable can be extracted.
// ---------------------------------------------------------------------------
export function salvageProseFromMalformedJson(raw: string): string | null {
  if (!raw || raw.length < 20) return null

  const stripped = raw
    .replace(/```json\s*([\s\S]*?)```/gi, '$1')
    .replace(/```\s*([\s\S]*?)```/g, '$1')

  // Try 1 : "message": "..." (handles most common reply structure).
  const msgRe = /"message"\s*:\s*"((?:[^"\\]|\\.)*)"/g
  let bestMsg = ''
  let m: RegExpExecArray | null
  while ((m = msgRe.exec(stripped)) !== null) {
    const decoded = decodeJsonString(m[1])
    if (decoded.length > bestMsg.length) bestMsg = decoded
  }
  if (bestMsg.length >= 30) return bestMsg

  // Try 2 : the longest quoted string anywhere (> 60 chars).
  const longestRe = /"((?:[^"\\]|\\.){60,})"/g
  let bestQuote = ''
  while ((m = longestRe.exec(stripped)) !== null) {
    const decoded = decodeJsonString(m[1])
    if (decoded.length > bestQuote.length) bestQuote = decoded
  }
  if (bestQuote.length >= 60) return bestQuote

  // Try 3 : strip JSON syntax and return residual prose if substantial.
  const proseOnly = stripped
    .replace(/[{}[\]"]/g, ' ')
    .replace(/^\s*\w+\s*:\s*/gm, '')
    .replace(/,\s*$/gm, '')
    .replace(/\s+/g, ' ')
    .trim()
  if (proseOnly.length >= 80 && /[a-zA-Z]{4,}/.test(proseOnly)) return proseOnly.slice(0, 2000)

  return null
}

// v45 — sequential pass instead of chained replaces : handles \uXXXX (LLMs
// emit these for accented chars after some tokenizations) and avoids the
// bug where chained .replace(/\\\\/g, '\\') would over-decode \\uXXXX.
function decodeJsonString(s: string): string {
  let out = ''
  for (let i = 0; i < s.length; i++) {
    const c = s[i]
    if (c !== '\\' || i + 1 >= s.length) { out += c; continue }
    const next = s[i + 1]
    if (next === 'n') { out += '\n'; i++ }
    else if (next === 't') { out += '  '; i++ }
    else if (next === 'r') { out += '\r'; i++ }
    else if (next === 'b') { out += '\b'; i++ }
    else if (next === 'f') { out += '\f'; i++ }
    else if (next === '"') { out += '"'; i++ }
    else if (next === '\\') { out += '\\'; i++ }
    else if (next === '/') { out += '/'; i++ }
    else if (next === 'u' && i + 5 < s.length && /^[0-9a-fA-F]{4}$/.test(s.slice(i + 2, i + 6))) {
      out += String.fromCharCode(parseInt(s.slice(i + 2, i + 6), 16))
      i += 5
    } else {
      out += c  // unknown escape, keep the backslash literal
    }
  }
  return out
}

function stripTags(s: string): string {
  return s
    .replace(/<\/?[^>]+>/g, ' ')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&[a-z]+;/gi, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

// ---------------------------------------------------------------------------
// buildResilientFallbackReply — the LLM died on us. Build a deterministic
// markdown synthesis from whatever data we already have in execution history
// so Aurora NEVER abandons silently. The user always gets a usable answer.
//
// Priority :
//   1. HTML fetch / browser.read_html : extract a real synthesis from digest
//   2. Generic data preview : at least surface what was retrieved
//   3. null : caller falls back to the polite "I couldn't" message
// ---------------------------------------------------------------------------
export function buildResilientFallbackReply(
  history: Array<{ action: CoworkAction; result: CoworkActionResult }>,
): string | null {
  for (let i = history.length - 1; i >= Math.max(0, history.length - 5); i--) {
    const entry = history[i]
    if (!entry.result.ok) continue

    const isHtmlAction = entry.action.kind === 'fetch'
      || (entry.action.kind === 'browser' && (entry.action.operation === 'read_html' || entry.action.operation === 'read_dom'))
    if (isHtmlAction) {
      const raw = (typeof entry.result.output === 'string' ? entry.result.output : '')
        || (typeof entry.result.data === 'string' ? entry.result.data : '')
      if (raw && /<\s*(html|!doctype)/i.test(raw.slice(0, 200))) {
        const digest = extractHtmlDigest(raw)
        const lines = digest.split('\n')
        const titleLine = lines.find((l) => l.startsWith('title:'))
        const descLine = lines.find((l) => l.startsWith('description:'))
        const headIdx = lines.findIndex((l) => l === 'headings:')
        const paraIdx = lines.findIndex((l) => l === 'paragraphs:')
        const headings = headIdx >= 0
          ? lines.slice(headIdx + 1).filter((l) => l.startsWith('  - ')).slice(0, 6)
          : []
        const paragraphs = paraIdx >= 0
          ? lines.slice(paraIdx + 1).filter((l) => l.startsWith('  - ')).slice(0, 3)
          : []
        const out: string[] = ['## Synthese (mode resilient — LLM indisponible)']
        if (titleLine) out.push(`**${titleLine.replace('title:', '').trim()}**`)
        if (descLine) out.push(`\n${descLine.replace('description:', '').trim()}`)
        if (headings.length > 0) {
          out.push(`\n### Sections detectees`)
          for (const h of headings) out.push(h)
        }
        if (paragraphs.length > 0) {
          out.push(`\n### Extraits`)
          for (const p of paragraphs) out.push(p)
        }
        out.push(`\n_Cette reponse est generee deterministiquement depuis le contenu lu — l LLM n a pas pu produire de plan valide. Demande "approfondis" si tu veux plus de details._`)
        return out.join('\n')
      }
    }

    if (entry.result.data || entry.result.output) {
      let preview = ''
      if (typeof entry.result.output === 'string') preview = entry.result.output
      else if (entry.result.data !== undefined) {
        try { preview = JSON.stringify(entry.result.data, null, 2) } catch { preview = String(entry.result.data) }
      }
      if (preview) {
        const truncated = preview.length > 1500 ? preview.slice(0, 1500) + '\n…[tronque]' : preview
        return [
          `## Donnees recuperees (mode resilient)`,
          ``,
          `Action : ${entry.action.kind}`,
          ``,
          '```',
          truncated,
          '```',
          ``,
          `_LLM indisponible pour la synthese — voici les donnees brutes. Reformule pour relancer une analyse._`,
        ].join('\n')
      }
    }
  }
  return null
}
