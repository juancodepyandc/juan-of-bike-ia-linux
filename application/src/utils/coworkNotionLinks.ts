// ---------------------------------------------------------------------------
// Notions [[…]] of the Cowork chat (AuroraCoworkView, component Bubble).
//
// The model marks a notion as [[label]]; the bubble turns it into a
// `cowork://explain/<label>` link and a click asks for an explanation.
//
// react-markdown 10 passes every URL through `defaultUrlTransform`, which
// blanks any protocol other than http(s), irc(s), mailto and xmpp. Without
// `keepCoworkLinks`, a notion reaches the DOM as `<a href="">`: a click reloads
// the page and nothing is submitted.
//
// A kept notion link is then never rendered as an anchor: the `a` override
// turns it into a `<button>` that carries its label. With no href, neither the
// keyboard, a middle click nor "open in a new tab" can navigate the Tauri
// WebView or the web/tunnel page to the custom scheme, even when the click
// handler is bypassed.
//
// Plain module (createElement, no JSX) so Node loads it with type stripping:
// scripts/test-cowork-notion-links.mjs renders exactly `coworkMarkdownOptions`.
// ---------------------------------------------------------------------------

import { createElement } from 'react'
import type { ComponentProps } from 'react'
import { defaultUrlTransform } from 'react-markdown'
import type { Components, ExtraProps, Options, UrlTransform } from 'react-markdown'
import remarkGfm from 'remark-gfm'

export const NOTION_HREF_PREFIX = 'cowork://explain/'
/** Attribute of the rendered button holding the decoded notion; read by the bubble's delegated click handler. */
export const NOTION_ATTRIBUTE = 'data-cowork-notion'

const NOTION_MARKER = /\[\[([^[\]\n]{2,80})\]\]/g

/**
 * `[[label]]` → `[label](cowork://explain/<label>)`.
 * Parentheses are escaped too: `encodeURIComponent` keeps them, and an
 * unbalanced one would end the link destination early (no link at all).
 */
export function linkifyNotions(markdown: string): string {
  return markdown.replace(NOTION_MARKER, (marker, raw: string) => {
    const label = raw.trim()
    if (!label) return marker
    const encoded = encodeURIComponent(label).replace(/\(/g, '%28').replace(/\)/g, '%29')
    return `[${label}](${NOTION_HREF_PREFIX}${encoded})`
  })
}

/**
 * Decoded notion of a `cowork://explain/…` href, or null when the href is not
 * a notion or names nothing. The model can write such links itself, so a
 * malformed escape must not throw: well-formed escapes are still decoded and
 * the malformed remainder is kept verbatim.
 */
export function notionFromHref(href: string | null | undefined): string | null {
  if (typeof href !== 'string' || !href.startsWith(NOTION_HREF_PREFIX)) return null
  const notion = decodeLenient(href.slice(NOTION_HREF_PREFIX.length)).trim()
  return notion || null
}

function decodeLenient(value: string): string {
  try {
    return decodeURIComponent(value)
  } catch {
    return value.replace(/(?:%[0-9a-f]{2})+/gi, (run) => {
      try {
        return decodeURIComponent(run)
      } catch {
        return run
      }
    })
  }
}

/**
 * `urlTransform` of the Cowork bubbles: keeps the href of a notion link and
 * gives every other URL react-markdown's default sanitising, so javascript:,
 * data:, vbscript: and the like stay blanked. Module-level, hence stable.
 */
export const keepCoworkLinks: UrlTransform = (url, key) =>
  key === 'href' && notionFromHref(url) !== null ? url : defaultUrlTransform(url)

/** `a` override: a notion becomes a button; any other link renders exactly as react-markdown would. */
function CoworkMarkdownAnchor(props: ComponentProps<'a'> & ExtraProps) {
  const { node: _node, ...anchor } = props
  const notion = notionFromHref(anchor.href)
  if (notion === null) return createElement('a', anchor)
  return createElement('button', {
    type: 'button',
    className: 'cowork-notion',
    title: `Expliquer « ${notion} »`,
    [NOTION_ATTRIBUTE]: notion,
  }, anchor.children)
}

export const coworkMarkdownComponents: Components = { a: CoworkMarkdownAnchor }

/** ReactMarkdown options of a Cowork bubble, shared with the node test. Module-level: stable across renders, so `memo(Bubble)` stays effective. */
export const coworkMarkdownOptions: Readonly<Pick<Options, 'remarkPlugins' | 'urlTransform' | 'components'>> = {
  remarkPlugins: [remarkGfm],
  urlTransform: keepCoworkLinks,
  components: coworkMarkdownComponents,
}
