import { buildAuroraInlineSvgDataUri } from './codeVisualFallbacks.ts'

function isBrokenImageSrc(src: string | null | undefined): boolean {
  if (!src) return true
  const value = src.trim()
  const lower = value.toLowerCase()
  if (value === '' || value === '#' || lower === 'javascript:void(0)') return true
  if (/^\s*[\[{<%$]+\s*(URL|IMG|IMAGE|PHOTO|HERO|PICTURE|SRC|UNSPLASH|HOLD|PLACE)/i.test(value)) return true
  if (/^\s*[\w_-]*(URL|IMG|IMAGE|PHOTO|HERO|PICTURE|SRC|UNSPLASH|HOLD|PLACE)[\w_-]*\s*[\]}>%$]+\s*$/i.test(value)) return true
  if (/^\{\{[^}]+\}\}$/.test(value) || /^\$\{[^}]+\}$/.test(value)) return true
  if (/^\s*(YOUR[_-]?IMAGE|IMAGE[_-]?HERE|TODO|FIXME|TBD|N\/?A|EXAMPLE)\b/i.test(value)) return true
  if (/^(via\.placeholder|placehold|loremflickr|placedog|placekitten)/.test(lower)) return true
  if (/^(https?:)?\/\/(www\.)?(via\.placeholder|placehold|loremflickr)/.test(lower)) return true
  if (lower.startsWith('data:image/svg')) return true
  if (/^[\w./-]+\.(png|jpe?g|webp|gif|avif)$/i.test(value) && !lower.startsWith('http')) return true
  if (value.startsWith('./') || value.startsWith('../')) return true
  return lower.startsWith('data:image/png;base64,iVBORw') && value.length < 200
}

function inferImageQuery(element: Element, doc: Document, fallback: string): string {
  const alt = (element.getAttribute('alt') || '').trim()
  if (alt.length >= 4 && !/^(image|photo|picture|placeholder|logo)$/i.test(alt)) return alt

  let parent: Element | null = element.parentElement
  while (parent && parent !== doc.body) {
    const heading = parent.querySelector('h1, h2, h3')
    if (heading?.textContent && heading.textContent.trim().length >= 4) {
      return heading.textContent.trim().slice(0, 80)
    }
    parent = parent.parentElement
  }

  const title = doc.title || doc.querySelector('h1')?.textContent || fallback
  return title.trim().slice(0, 80)
}

export function fixBrokenImages(doc: Document, fallback: string): { fixed: number } {
  let fixed = 0
  const images = Array.from(doc.querySelectorAll('img'))

  for (const [index, image] of images.entries()) {
    const src = image.getAttribute('src')
    if (isBrokenImageSrc(src)) {
      const query = inferImageQuery(image, doc, fallback)
      const width = image.getAttribute('width') || '1200'
      const height = image.getAttribute('height') || '800'
      const signature = (image.getAttribute('alt') || query).replace(/\s+/g, '-').slice(0, 20)
      image.setAttribute('src', buildAuroraInlineSvgDataUri(`${query} ${signature}-${index}`, { width, height }))
      if (!image.getAttribute('alt')?.trim()) image.setAttribute('alt', query)
      fixed += 1
    }

    if (!image.getAttribute('onerror')) {
      const width = image.getAttribute('width') || '1200'
      const height = image.getAttribute('height') || '800'
      const seed = (image.getAttribute('alt') || `aurora-${index}`).replace(/[^\w-]/g, '').slice(0, 20) || `aurora-${index}`
      const fallbackUrl = buildAuroraInlineSvgDataUri(seed, { width, height })
      image.setAttribute('onerror', `this.onerror=null;this.src=${JSON.stringify(fallbackUrl)};`)
    }
    image.setAttribute('loading', 'lazy')
    image.setAttribute('decoding', 'async')
  }

  return { fixed }
}

export function fixBrokenPictures(doc: Document, fallback: string): { fixed: number } {
  let fixed = 0
  for (const source of Array.from(doc.querySelectorAll('picture source'))) {
    const srcset = source.getAttribute('srcset')
    if (!srcset || isBrokenImageSrc(srcset.split(' ')[0] || '')) {
      const query = inferImageQuery(source, doc, fallback)
      source.setAttribute('srcset', buildAuroraInlineSvgDataUri(query, { width: 1600, height: 900 }))
      fixed += 1
    }
  }
  return { fixed }
}

export function injectMissingHeroImage(doc: Document, fallback: string): { injected: boolean } {
  const hero = doc.querySelector('.hero, [class*="hero"], header.hero, section.hero, main > section:first-of-type')
  if (!hero || hero.querySelector('img, video, canvas, svg[class*="hero"], picture')) return { injected: false }
  if ((hero.textContent?.trim() || '').length < 30) return { injected: false }

  const heading = hero.querySelector('h1')?.textContent?.trim() || fallback
  const image = doc.createElement('img')
  image.setAttribute('src', buildAuroraInlineSvgDataUri(heading.slice(0, 80), { width: 1600, height: 900 }))
  image.setAttribute('alt', heading)
  image.setAttribute('loading', 'eager')
  image.setAttribute('decoding', 'async')
  image.className = 'hero-injected-visual'
  image.setAttribute('style', 'width:100%;max-height:520px;object-fit:cover;border-radius:14px;margin-top:24px;animation:auroraFadeUp 1s cubic-bezier(0.19,1,0.22,1) both 200ms;')
  hero.appendChild(image)
  return { injected: true }
}

export function fixCssBackgroundImages(css: string, fallbackQuery: string): { css: string; fixed: number } {
  let fixed = 0
  const repaired = css.replace(
    /(\.[a-zA-Z][\w-]*\s*\{[^}]*?background(?:-image)?\s*:\s*[^;}]*url\s*\(\s*['"]?)([^'")]+)(['"]?\s*\))/gi,
    (full, before, url, after) => {
      const trimmed = url.trim()
      if (/^https?:/i.test(trimmed)) return full
      const selectorMatch = full.match(/\.([a-zA-Z][\w-]*)/)
      const seed = selectorMatch ? selectorMatch[1].replace(/-/g, ' ') : fallbackQuery
      fixed += 1
      return `${before}${buildAuroraInlineSvgDataUri(seed, { width: 1600, height: 900 })}${after}`
    },
  )
  return { css: repaired, fixed }
}
