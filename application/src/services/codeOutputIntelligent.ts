/**
 * codeOutputIntelligent — replaces the mechanical regex post-process
 * (v82nh) with a real DOMParser-based reasoning pass.
 *
 * v82nk : extended :
 *   - brand recolor : if a brand profile is provided (with primaryColor),
 *     RECOLOR the entire CSS palette towards that brand instead of
 *     leaving the LLM's default (green if Tailwind default, etc).
 *   - image fallback : broken/local images become deterministic inline SVG
 *     visuals, avoiding dead remote placeholders and network-only previews.
 *   - background-image url() in CSS : if local path, swap to inline SVG.
 *   - <picture> + <source srcset> : also fixed.
 *
 * v82ni : user reported the regex elevation was schoolbook —
 *   - "logo de manque d'image" : broken images stayed broken because
 *     regex only caught specific placeholder patterns, missing empty
 *     src / .png locals / picture sources / background-image url().
 *   - animations were generic and applied to every section even when
 *     they didn't make sense (animations on a footer, fadeUp on a
 *     decorative span).
 *   - buttons existed but had no onclick → just visual decoration.
 *
 * This module reads the actual DOM tree, reasons per-element about
 * its semantic role, and applies CONTEXTUAL transformations.
 *
 * No extra LLM call — pure parsing + heuristics. Fast (single pass)
 * and deterministic.
 */

import type { ParsedFile } from './codeOutputFiles'
import { buildAuroraInlineSvgDataUri } from './codeVisualFallbacks.ts'

// ---------------------------------------------------------------------------
// Image intelligence
// ---------------------------------------------------------------------------

/**
 * Decide whether an <img>'s src is "broken" : empty, relative-local,
 * placeholder pattern, data URL of a 1x1, or just a logo SVG repeated
 * everywhere.
 */
function isBrokenImageSrc(src: string | null | undefined): boolean {
  if (!src) return true
  const s = src.trim()
  const sl = s.toLowerCase()
  if (s === '' || s === '#' || sl === 'javascript:void(0)') return true
  // v82nq : LLM placeholder patterns like [URL_IMAGE_UNSPLASH],
  // {{image_url}}, %image%, $IMG_SRC$, IMAGE_URL_HERE etc.
  if (/^\s*[\[{<%$]+\s*(URL|IMG|IMAGE|PHOTO|HERO|PICTURE|SRC|UNSPLASH|HOLD|PLACE)/i.test(s)) return true
  if (/^\s*[\w_-]*(URL|IMG|IMAGE|PHOTO|HERO|PICTURE|SRC|UNSPLASH|HOLD|PLACE)[\w_-]*\s*[\]}>%$]+\s*$/i.test(s)) return true
  if (/^\{\{[^}]+\}\}$/.test(s) || /^\$\{[^}]+\}$/.test(s)) return true
  if (/^\s*(YOUR[_-]?IMAGE|IMAGE[_-]?HERE|TODO|FIXME|TBD|N\/?A|EXAMPLE)\b/i.test(s)) return true
  if (/^(via\.placeholder|placehold|loremflickr|placedog|placekitten)/.test(sl)) return true
  if (/^(https?:)?\/\/(www\.)?(via\.placeholder|placehold|loremflickr)/.test(sl)) return true
  // Data URL of an SVG is usually a placeholder logo
  if (sl.startsWith('data:image/svg')) return true
  // Local relative path with no actual file (.png .jpg .webp without origin)
  if (/^[\w./-]+\.(png|jpe?g|webp|gif|avif)$/i.test(s) && !sl.startsWith('http')) return true
  if (s.startsWith('./') || s.startsWith('../')) return true
  // Single-pixel inline data placeholder
  if (sl.startsWith('data:image/png;base64,iVBORw') && s.length < 200) return true
  return false
}

/**
 * Build a stable visual seed for this image based on context :
 *   1. its alt text (if descriptive)
 *   2. nearest preceding heading text
 *   3. parent section's data-aurora-context attr (we set this in
 *      enrichSection)
 *   4. page title fallback
 */
function inferImageQuery(img: Element, doc: Document, fallback: string): string {
  // Priority 1 : non-trivial alt text
  const alt = (img.getAttribute('alt') || '').trim()
  if (alt.length >= 4 && !/^(image|photo|picture|placeholder|logo)$/i.test(alt)) {
    return alt
  }
  // Priority 2 : ancestor section's heading
  let parent: Element | null = img.parentElement
  while (parent && parent !== doc.body) {
    const h = parent.querySelector('h1, h2, h3')
    if (h && h.textContent && h.textContent.trim().length >= 4) {
      return h.textContent.trim().slice(0, 80)
    }
    parent = parent.parentElement
  }
  // Priority 3 : page title
  const title = doc.title || doc.querySelector('h1')?.textContent || fallback
  return title.trim().slice(0, 80)
}

/**
 * Replace broken <img> srcs with context-aware inline SVG visuals.
 * Existing URLs are kept, but get a local onerror fallback so the UI
 * never depends on a third-party placeholder host.
 */
function fixBrokenImages(doc: Document, fallback: string): { fixed: number } {
  let fixed = 0
  const imgs = Array.from(doc.querySelectorAll('img'))
  let i = 0
  for (const img of imgs) {
    const src = img.getAttribute('src')
    const broken = isBrokenImageSrc(src)
    if (broken) {
      const query = inferImageQuery(img, doc, fallback)
      const w = img.getAttribute('width') || '1200'
      const h = img.getAttribute('height') || '800'
      // sig suffix so consecutive imgs differ.
      const sig = (img.getAttribute('alt') || query).replace(/\s+/g, '-').slice(0, 20)
      const newSrc = buildAuroraInlineSvgDataUri(`${query} ${sig}-${i}`, { width: w, height: h })
      img.setAttribute('src', newSrc)
      if (!img.getAttribute('alt') || img.getAttribute('alt')?.trim().length === 0) {
        img.setAttribute('alt', query)
      }
      fixed += 1
    }
    // Always attach a local onerror fallback so remote images cannot
    // leave a broken-image icon in the generated preview.
    if (!img.getAttribute('onerror')) {
      const w = img.getAttribute('width') || '1200'
      const h = img.getAttribute('height') || '800'
      const seedSource = (img.getAttribute('alt') || `aurora-${i}`).replace(/[^\w-]/g, '').slice(0, 20) || `aurora-${i}`
      const fallbackUrl = buildAuroraInlineSvgDataUri(seedSource, { width: w, height: h })
      img.setAttribute('onerror', `this.onerror=null;this.src=${JSON.stringify(fallbackUrl)};`)
    }
    img.setAttribute('loading', 'lazy')
    img.setAttribute('decoding', 'async')
    i += 1
  }
  return { fixed }
}

/**
 * Replace broken <picture><source srcset=...> elements similarly.
 */
function fixBrokenPictures(doc: Document, fallback: string): { fixed: number } {
  let fixed = 0
  const sources = Array.from(doc.querySelectorAll('picture source'))
  for (const source of sources) {
    const srcset = source.getAttribute('srcset')
    if (!srcset || isBrokenImageSrc(srcset.split(' ')[0] || '')) {
      const query = inferImageQuery(source, doc, fallback)
      source.setAttribute('srcset', buildAuroraInlineSvgDataUri(query, { width: 1600, height: 900 }))
      fixed += 1
    }
  }
  return { fixed }
}

/**
 * Some pages have NO <img> at all in places where one is needed (hero,
 * features). Detect and inject. We add an <img> only when the section
 * has substantial text but no visual.
 */
function injectMissingHeroImage(doc: Document, fallback: string): { injected: boolean } {
  const hero = doc.querySelector('.hero, [class*="hero"], header.hero, section.hero, main > section:first-of-type')
  if (!hero) return { injected: false }
  if (hero.querySelector('img, video, canvas, svg[class*="hero"], picture')) {
    return { injected: false }
  }
  // Inject a deterministic local hero visual as a sibling/last-child
  // if there's textual content but no visual.
  const txt = hero.textContent?.trim() || ''
  if (txt.length < 30) return { injected: false }
  const heading = hero.querySelector('h1')?.textContent?.trim() || fallback
  const img = doc.createElement('img')
  img.setAttribute('src', buildAuroraInlineSvgDataUri(heading.slice(0, 80), { width: 1600, height: 900 }))
  img.setAttribute('alt', heading)
  img.setAttribute('loading', 'eager')
  img.setAttribute('decoding', 'async')
  img.className = 'hero-injected-visual'
  // Style inline so it adapts even without CSS support.
  img.setAttribute('style', 'width:100%;max-height:520px;object-fit:cover;border-radius:14px;margin-top:24px;animation:auroraFadeUp 1s cubic-bezier(0.19,1,0.22,1) both 200ms;')
  hero.appendChild(img)
  return { injected: true }
}

// ---------------------------------------------------------------------------
// Button intelligence
// ---------------------------------------------------------------------------

/**
 * Infer what a button SHOULD do from its text. Maps user-intent keywords
 * to a JS handler snippet.
 */
function inferButtonAction(label: string): { kind: string; jsBody: string } {
  const t = label.trim().toLowerCase()
  // Discovery / explore / scroll
  if (/découvrir|d[éeè]couvre[rz]?|explorer|voir plus|en savoir|scroll|next/i.test(t)) {
    return {
      kind: 'scroll-next',
      jsBody: `const next=this.closest('section,header,main,div')?.nextElementSibling||document.querySelector('main section');if(next)next.scrollIntoView({behavior:'smooth',block:'start'});`,
    }
  }
  // Demo / preview / play
  if (/d[ée]mo|preview|play|voir.*d[ée]mo|essayer|try/i.test(t)) {
    return {
      kind: 'demo-modal',
      jsBody: `const m=document.createElement('div');m.style.cssText='position:fixed;inset:0;background:rgba(0,0,0,.78);z-index:9999;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(8px);animation:auroraFadeIn .35s ease both';m.innerHTML='<div style="background:oklch(.18 .02 270);padding:32px;border-radius:14px;max-width:560px;text-align:center;color:#fff;font-family:system-ui"><div style="font-size:14px;letter-spacing:.18em;text-transform:uppercase;color:oklch(.78 .16 80);margin-bottom:14px">Démo</div><div style="font-size:18px;line-height:1.5;margin-bottom:18px">Démonstration interactive disponible dans la version pro.</div><button onclick="this.closest(\\'div[style*=fixed]\\').remove()" style="padding:10px 22px;background:oklch(.74 .13 60);color:#0a0a0a;border:none;border-radius:8px;font-weight:600;cursor:pointer">Fermer</button></div>';m.addEventListener('click',e=>{if(e.target===m)m.remove()});document.body.appendChild(m);`,
    }
  }
  // Contact / message
  if (/contact|message|nous écrire|écris-nous|email|mail/i.test(t)) {
    return {
      kind: 'contact-scroll',
      jsBody: `const c=document.querySelector('#contact, [id*=contact], .contact, footer');if(c){c.scrollIntoView({behavior:'smooth'});}else{location.href='mailto:contact@example.com';}`,
    }
  }
  // CTA primary commerce
  if (/acheter|commander|panier|cart|checkout|buy/i.test(t)) {
    return {
      kind: 'cart-toast',
      jsBody: `const t=document.createElement('div');t.textContent='✓ Ajouté';t.style.cssText='position:fixed;bottom:24px;right:24px;background:oklch(.72 .18 145);color:#0a0a0a;padding:12px 22px;border-radius:99px;font-weight:600;font-family:system-ui;z-index:9998;box-shadow:0 8px 32px rgba(0,0,0,.4);animation:auroraFadeUp .35s ease both';document.body.appendChild(t);setTimeout(()=>{t.style.opacity='0';t.style.transition='opacity .3s';setTimeout(()=>t.remove(),300);},2200);`,
    }
  }
  // Sign up / register / s'inscrire
  if (/s'?inscrire|register|sign.?up|cr[ée]er.*compte|join/i.test(t)) {
    return {
      kind: 'signup-toast',
      jsBody: `const t=document.createElement('div');t.textContent='✓ Inscription envoyée';t.style.cssText='position:fixed;bottom:24px;right:24px;background:oklch(.74 .13 60);color:#0a0a0a;padding:12px 22px;border-radius:99px;font-weight:600;font-family:system-ui;z-index:9998;box-shadow:0 8px 32px rgba(0,0,0,.4);animation:auroraFadeUp .35s ease both';document.body.appendChild(t);setTimeout(()=>{t.style.opacity='0';t.style.transition='opacity .3s';setTimeout(()=>t.remove(),300);},2200);`,
    }
  }
  // Login / connexion
  if (/login|connexion|connecter|sign.?in/i.test(t)) {
    return {
      kind: 'login-scroll',
      jsBody: `const f=document.querySelector('form, #login, [class*=login]');if(f)f.scrollIntoView({behavior:'smooth'});`,
    }
  }
  // Default : scroll to next section + log
  return {
    kind: 'scroll-default',
    jsBody: `const sec=this.closest('section,header,main,div')?.nextElementSibling;if(sec)sec.scrollIntoView({behavior:'smooth'});`,
  }
}

/**
 * Wire all <button> and <a> tags that don't already have a handler or
 * a real href. Returns the count.
 */
function wireButtons(doc: Document): { wired: number; kinds: Record<string, number> } {
  let wired = 0
  const kinds: Record<string, number> = {}
  const candidates: Element[] = [
    ...Array.from(doc.querySelectorAll('button')),
    ...Array.from(doc.querySelectorAll('a')),
  ]
  for (const el of candidates) {
    const tag = el.tagName.toLowerCase()
    // Skip if already has a real handler or non-trivial href.
    if (el.getAttribute('onclick') && (el.getAttribute('onclick')?.trim().length ?? 0) > 0) continue
    if (tag === 'a') {
      const href = el.getAttribute('href') || ''
      if (href && href !== '#' && href !== 'javascript:void(0)' && !href.startsWith('#')) continue
    }
    const label = el.textContent?.trim() || el.getAttribute('aria-label') || ''
    if (label.length < 2) continue
    // Skip nav-internal anchor links (real fragment refs already work).
    if (tag === 'a' && el.getAttribute('href')?.startsWith('#') && el.getAttribute('href')!.length > 1) {
      // Confirm the fragment exists
      const frag = el.getAttribute('href')!.slice(1)
      if (doc.getElementById(frag)) continue
    }
    const action = inferButtonAction(label)
    el.setAttribute('onclick', action.jsBody)
    if (tag === 'a' && (!el.getAttribute('href') || el.getAttribute('href') === '#' || el.getAttribute('href') === 'javascript:void(0)')) {
      el.setAttribute('href', '#')
      el.setAttribute('role', 'button')
    }
    kinds[action.kind] = (kinds[action.kind] || 0) + 1
    wired += 1
  }
  return { wired, kinds }
}

// ---------------------------------------------------------------------------
// Animation intelligence — only animate elements that should animate
// ---------------------------------------------------------------------------

const SEMANTIC_ANIM_RULES = `
/* v82ni : animations contextuelles intelligentes (sélecteurs précis) */
@keyframes auroraFadeUp { from { opacity:0; transform:translateY(28px) } to { opacity:1; transform:translateY(0) } }
@keyframes auroraFadeIn { from { opacity:0 } to { opacity:1 } }
@keyframes auroraScaleIn { from { opacity:0; transform:scale(.96) } to { opacity:1; transform:scale(1) } }
@keyframes auroraShimmer { 0% { background-position:-200% 0 } 100% { background-position:200% 0 } }

/* Hero entrance — staggered title/subtitle/CTA */
.hero h1, .hero-title, header h1, main > section:first-of-type h1 { animation: auroraFadeUp .9s cubic-bezier(.19,1,.22,1) both; }
.hero p, .hero-subtitle, .hero-content p, header h1 + p { animation: auroraFadeUp .9s 140ms cubic-bezier(.19,1,.22,1) both; }
.hero .btn, .hero-cta, .hero-content button, .hero-content .btn { animation: auroraFadeUp .9s 280ms cubic-bezier(.19,1,.22,1) both; }
.hero-injected-visual { animation: auroraFadeUp 1s 200ms cubic-bezier(.19,1,.22,1) both; }

/* Section reveal — only on real <section>, not header/footer */
main > section, .feature, .card { animation: auroraFadeUp .8s cubic-bezier(.19,1,.22,1) both; }
@supports (animation-timeline: view()) {
  main > section, .feature, .card {
    animation-timeline: view();
    animation-range: entry 0% entry 60%;
  }
}

/* Hover micro-interactions on interactive elements ONLY */
.btn, button, .card, [role="button"] {
  transition: transform 240ms cubic-bezier(.32,.72,0,1), box-shadow 240ms cubic-bezier(.19,1,.22,1), filter 200ms ease;
}
.btn:hover, button:hover, .card:hover {
  transform: translateY(-2px) scale(1.02);
  filter: brightness(1.05);
}
.btn:active, button:active { transform: translateY(0) scale(0.98); }

/* Counter shimmer for stat numbers */
.stat-number, .counter, [data-counter] {
  background: linear-gradient(120deg, currentColor 0%, currentColor 45%, oklch(.74 .13 60) 50%, currentColor 55%, currentColor 100%);
  background-size: 200% 100%;
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  animation: auroraShimmer 4s ease-in-out infinite;
}

/* Reduced motion — strict respect */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; }
}
`

const COUNTER_OBSERVER_JS = `
// v82ni : counter-up + scroll-fallback contextuels (auto-injectés)
(function () {
  // 1. Counter-up : éléments avec data-counter ou .stat-number contenant un nombre
  const counters = document.querySelectorAll('[data-counter], .stat-number, .counter');
  if (counters.length > 0 && 'IntersectionObserver' in window) {
    const cIO = new IntersectionObserver((entries) => {
      for (const e of entries) {
        if (!e.isIntersecting) continue;
        cIO.unobserve(e.target);
        const txt = e.target.textContent || '';
        const m = txt.match(/(\\d[\\d\\s,.]*)/);
        if (!m) continue;
        const targetNum = parseFloat(m[1].replace(/[\\s,]/g, ''));
        if (!isFinite(targetNum) || targetNum < 1) continue;
        const suffix = txt.slice(m.index + m[1].length);
        const prefix = txt.slice(0, m.index);
        const dur = 1400;
        const t0 = performance.now();
        const tick = (now) => {
          const t = Math.min(1, (now - t0) / dur);
          const eased = 1 - Math.pow(1 - t, 4);
          const v = Math.round(targetNum * eased);
          e.target.textContent = prefix + v.toLocaleString('fr-FR') + suffix;
          if (t < 1) requestAnimationFrame(tick);
          else e.target.textContent = prefix + targetNum.toLocaleString('fr-FR') + suffix;
        };
        requestAnimationFrame(tick);
      }
    }, { threshold: 0.4 });
    counters.forEach((c) => cIO.observe(c));
  }

  // 2. Scroll-driven fallback for browsers without animation-timeline
  if (!CSS || !CSS.supports || !CSS.supports('animation-timeline: view()')) {
    const sections = document.querySelectorAll('main > section, .feature, .card');
    if (sections.length > 0 && 'IntersectionObserver' in window) {
      const sIO = new IntersectionObserver((entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            e.target.style.animation = 'auroraFadeUp .8s cubic-bezier(.19,1,.22,1) both';
            sIO.unobserve(e.target);
          }
        }
      }, { threshold: 0.12 });
      sections.forEach((s) => { s.style.opacity = '0'; sIO.observe(s); });
    }
  }

  // 3. Hero parallax background on mousemove (subtle)
  const hero = document.querySelector('.hero, header.hero, main > section:first-of-type');
  if (hero) {
    let raf = 0, tx = 0, ty = 0;
    hero.addEventListener('mousemove', (e) => {
      const r = hero.getBoundingClientRect();
      tx = ((e.clientX - r.left) / r.width - 0.5) * 6;
      ty = ((e.clientY - r.top) / r.height - 0.5) * 6;
      if (raf) cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const v = hero.querySelector('img, .hero-visual, .visual-wrapper');
        if (v) v.style.transform = 'translate(' + tx.toFixed(2) + 'px,' + ty.toFixed(2) + 'px)';
      });
    });
  }
})();
`

// ---------------------------------------------------------------------------
// Color elevation — keeps the hex→oklch sweep but only inside <style>.
// ---------------------------------------------------------------------------

const HEX_TO_OKLCH: Array<[RegExp, string]> = [
  [/#7c3aed\b/gi, 'oklch(0.55 0.27 296)'],
  [/#6d28d9\b/gi, 'oklch(0.47 0.27 296)'],
  [/#a855f7\b/gi, 'oklch(0.65 0.27 296)'],
  [/#8b5cf6\b/gi, 'oklch(0.62 0.22 285)'],
  [/#6366f1\b/gi, 'oklch(0.58 0.20 270)'],
  [/#3b82f6\b/gi, 'oklch(0.62 0.21 250)'],
  [/#0a0a0b\b/gi, 'oklch(0.16 0.01 270)'],
  [/#0a0a0a\b/gi, 'oklch(0.15 0 0)'],
  [/#121214\b/gi, 'oklch(0.18 0.01 270)'],
  [/#131316\b/gi, 'oklch(0.18 0.01 270)'],
  [/#1a1a1c\b/gi, 'oklch(0.22 0.01 270)'],
  [/#1a1a1d\b/gi, 'oklch(0.22 0.01 270)'],
  [/#222224\b/gi, 'oklch(0.26 0.01 270)'],
  [/#222226\b/gi, 'oklch(0.26 0.01 270)'],
  [/#f8fafc\b/gi, 'oklch(0.97 0.01 270)'],
  [/#e2e8f0\b/gi, 'oklch(0.91 0.01 270)'],
  [/#94a3b8\b/gi, 'oklch(0.66 0.02 270)'],
  [/#22c55e\b/gi, 'oklch(0.72 0.18 145)'],
  [/#f59e0b\b/gi, 'oklch(0.78 0.16 80)'],
  [/#ef4444\b/gi, 'oklch(0.62 0.21 30)'],
]

function elevateColors(css: string): string {
  let out = css
  for (const [re, ok] of HEX_TO_OKLCH) out = out.replace(re, ok)
  return out
}

/**
 * v82nk : when a brand profile is detected (with primaryColor), RECOLOR
 * the LLM's accent color across the entire CSS. The LLM's training bias
 * pushes Tailwind violet/blue defaults regardless of the brand prompt,
 * so we override post-hoc.
 *
 * Strategy : find the dominant accent color in the CSS (the most-used
 * non-neutral color) and replace it with the brand's primary. Plus
 * keyword-based : --color-accent, --accent, --primary, --color-primary
 * are renamed.
 */
function brandRecolor(css: string, brandPrimary: string): string {
  if (!brandPrimary) return css
  // Normalize brandPrimary : accept #hex or oklch() or rgb()
  let primary = brandPrimary.trim()
  if (/^#[0-9a-f]{3}$/i.test(primary)) {
    // Expand 3-char hex to 6-char.
    primary = '#' + primary.slice(1).split('').map((c) => c + c).join('')
  }
  // Replace common accent variable values directly.
  let out = css
  // Pattern 1 : CSS custom property declarations for accent/primary.
  // --color-accent: #aaa  →  --color-accent: <brandPrimary>
  out = out.replace(
    /(--(?:color-)?(?:accent|primary|brand|highlight)(?:-hover|-soft|-strong|-foreground)?)\s*:\s*[^;}\n]+/gi,
    `$1: ${primary}`,
  )
  // Pattern 2 : the most-frequent oklch / hex value that's NOT a neutral
  // (gray/black/white). Detect and swap.
  const colorPattern = /oklch\([^)]+\)|#[0-9a-f]{6,8}\b/gi
  const counts = new Map<string, number>()
  for (const m of out.matchAll(colorPattern)) {
    const c = m[0].toLowerCase()
    // Skip very dark (background) and very light (foreground) values.
    if (/^#[0-1]/.test(c) || /^#f/.test(c) || /^oklch\(0\.[01]/.test(c) || /^oklch\(0\.9/.test(c)) {
      continue
    }
    counts.set(c, (counts.get(c) || 0) + 1)
  }
  if (counts.size > 0) {
    const sorted = Array.from(counts.entries()).sort((a, b) => b[1] - a[1])
    const dominant = sorted[0][0]
    if (sorted[0][1] >= 2) {
      // Replace dominant accent everywhere.
      const escapedDom = dominant.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
      out = out.replace(new RegExp(escapedDom, 'gi'), primary)
    }
  }
  return out
}

/**
 * Fix CSS background-image: url(local-path.jpg) by routing to a local
 * deterministic SVG derived from the surrounding selector name.
 */
function fixCssBackgroundImages(css: string, fallbackQuery: string): { css: string; fixed: number } {
  let fixed = 0
  const out = css.replace(
    /(\.[a-zA-Z][\w-]*\s*\{[^}]*?background(?:-image)?\s*:\s*[^;}]*url\s*\(\s*['"]?)([^'")]+)(['"]?\s*\))/gi,
    (full, before, url, after) => {
      const trimmed = url.trim()
      if (/^https?:/i.test(trimmed)) return full // keep working URLs
      // Derive query from selector.
      const selectorMatch = full.match(/\.([a-zA-Z][\w-]*)/)
      const seed = selectorMatch ? selectorMatch[1].replace(/-/g, ' ') : fallbackQuery
      fixed += 1
      return `${before}${buildAuroraInlineSvgDataUri(seed, { width: 1600, height: 900 })}${after}`
    },
  )
  return { css: out, fixed }
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export interface IntelligentReport {
  imagesFixed: number
  picturesFixed: number
  bgImagesFixed: number
  heroImageInjected: boolean
  buttonsWired: number
  buttonKinds: Record<string, number>
  colorsElevated: number
  brandRecolored: boolean
  animationsScoped: boolean
  countersWired: boolean
}

export function intelligentlyElevateFiles(
  files: ParsedFile[],
  promptHint: string = '',
  brandPrimary: string = '',
): { files: ParsedFile[]; report: IntelligentReport } {
  const report: IntelligentReport = {
    imagesFixed: 0,
    picturesFixed: 0,
    bgImagesFixed: 0,
    heroImageInjected: false,
    buttonsWired: 0,
    buttonKinds: {},
    colorsElevated: 0,
    brandRecolored: false,
    animationsScoped: false,
    countersWired: false,
  }
  const fallback = (promptHint || 'modern design').slice(0, 80)
  const out: ParsedFile[] = []

  // Find HTML and CSS files
  let mainHtml: ParsedFile | null = null
  for (const f of files) {
    if ((f.language === 'markup' || f.language === 'html' || /\.html?$/i.test(f.path)) && !mainHtml) {
      mainHtml = f
    }
  }

  let mainHtmlContent: string | null = null
  if (mainHtml && typeof DOMParser !== 'undefined') {
    try {
      const parser = new DOMParser()
      const doc = parser.parseFromString(mainHtml.content, 'text/html')

      // 1. Fix broken images contextually
      const imgRes = fixBrokenImages(doc, fallback)
      report.imagesFixed = imgRes.fixed
      const picRes = fixBrokenPictures(doc, fallback)
      report.picturesFixed = picRes.fixed

      // 2. Inject hero image if missing
      const heroRes = injectMissingHeroImage(doc, fallback)
      report.heroImageInjected = heroRes.injected

      // 3. Wire buttons to real handlers
      const btnRes = wireButtons(doc)
      report.buttonsWired = btnRes.wired
      report.buttonKinds = btnRes.kinds

      // v82nl : DROPPED hardcoded color elevation (hex→oklch),
      // brandRecolor, and SEMANTIC_ANIM_RULES auto-injection. The
      // user explicitly said : "si tu commences a dire cette marque
      // cette couleur il apprend pas a être intelligent". The polish
      // pass LLM (runPolishPass in codeStreamStore) now does the
      // contextual design work itself. We KEEP only the defensive
      // bg-image local-path fix because that's a safety net for
      // broken references, not a design choice.
      const styles = Array.from(doc.querySelectorAll('style'))
      for (const styleEl of styles) {
        let css = styleEl.textContent || ''
        const bgRes = fixCssBackgroundImages(css, fallback)
        css = bgRes.css
        report.bgImagesFixed += bgRes.fixed
        styleEl.textContent = css
      }

      // 5. Inject the counter+observer JS at the end of body
      if (doc.body) {
        const scriptEl = doc.createElement('script')
        scriptEl.textContent = COUNTER_OBSERVER_JS
        doc.body.appendChild(scriptEl)
        report.countersWired = true
      }

      mainHtmlContent = '<!DOCTYPE html>\n' + doc.documentElement.outerHTML
    } catch {
      // DOMParser failed (rare), keep original content.
    }
  }

  // Now build the output : replace mainHtml with elevated content, and
  // also elevate CSS colors in standalone .css files + inject animations
  // if a CSS file exists separately.
  let cssAnimsInjected = false
  for (const f of files) {
    if (f === mainHtml && mainHtmlContent) {
      out.push({ ...f, content: mainHtmlContent })
      continue
    }
    if (f.language === 'css' || f.language === 'scss' || /\.s?css$/i.test(f.path)) {
      // v82nl : drop hex→oklch + brand recolor + animation injection.
      // Keep only defensive bg-image local-path fix.
      let css = f.content
      const bgRes = fixCssBackgroundImages(css, fallback)
      css = bgRes.css
      report.bgImagesFixed += bgRes.fixed
      out.push({ ...f, content: css })
      continue
    }
    out.push(f)
  }

  // If animations were injected via standalone CSS file, also inject the
  // counter/observer JS into the LAST .js file.
  if (cssAnimsInjected) {
    for (let i = out.length - 1; i >= 0; i--) {
      const f = out[i]
      if (f.language === 'javascript' || f.language === 'jsx' || /\.m?jsx?$/i.test(f.path)) {
        if (!/IntersectionObserver/.test(f.content) || !/data-counter/.test(f.content)) {
          out[i] = { ...f, content: f.content + '\n' + COUNTER_OBSERVER_JS }
          report.countersWired = true
        }
        break
      }
    }
  }

  return { files: out, report }
}
