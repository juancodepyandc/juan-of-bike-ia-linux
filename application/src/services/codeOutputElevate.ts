/**
 * codeOutputElevate — post-process LLM-generated code to elevate it
 * from "schoolbook" to "elite-tier" by enforcing the design contract
 * the LLM systematically ignores.
 *
 * v82nh : after multiple iterations of system + user prompt rules,
 * BOTH qwen3-coder and qwen3:14b kept producing #hex Tailwind defaults
 * with no @keyframes and no real images. The training data bias is
 * stronger than any prompt. This module accepts that reality and
 * post-processes the output to be elite without re-running the LLM.
 *
 * Pure functions, no side effects, no DOM access, no network. Designed
 * to run client-side after parsing.
 */

import type { ParsedFile } from './codeOutputFiles'
import { buildAuroraInlineSvgDataUri } from './codeVisualFallbacks.ts'

/** Common Tailwind-default hex → oklch equivalents (perceptually
 * uniform). Triggered as a sweep over CSS files. */
const HEX_TO_OKLCH: Array<[RegExp, string]> = [
  // Tailwind violet family (most LLMs default to this)
  [/#7c3aed\b/gi, 'oklch(0.55 0.27 296)'],
  [/#6d28d9\b/gi, 'oklch(0.47 0.27 296)'],
  [/#a855f7\b/gi, 'oklch(0.65 0.27 296)'],
  // Tailwind violet/blue/indigo
  [/#8b5cf6\b/gi, 'oklch(0.62 0.22 285)'],
  [/#6366f1\b/gi, 'oklch(0.58 0.20 270)'],
  [/#3b82f6\b/gi, 'oklch(0.62 0.21 250)'],
  // Dark backgrounds
  [/#0a0a0b\b/gi, 'oklch(0.16 0.01 270)'],
  [/#0a0a0a\b/gi, 'oklch(0.15 0 0)'],
  [/#121214\b/gi, 'oklch(0.18 0.01 270)'],
  [/#131316\b/gi, 'oklch(0.18 0.01 270)'],
  [/#1a1a1c\b/gi, 'oklch(0.22 0.01 270)'],
  [/#1a1a1d\b/gi, 'oklch(0.22 0.01 270)'],
  [/#222224\b/gi, 'oklch(0.26 0.01 270)'],
  [/#222226\b/gi, 'oklch(0.26 0.01 270)'],
  // Tailwind slate text
  [/#f8fafc\b/gi, 'oklch(0.97 0.01 270)'],
  [/#e2e8f0\b/gi, 'oklch(0.91 0.01 270)'],
  [/#94a3b8\b/gi, 'oklch(0.66 0.02 270)'],
  // Common semantic colors
  [/#22c55e\b/gi, 'oklch(0.72 0.18 145)'],
  [/#f59e0b\b/gi, 'oklch(0.78 0.16 80)'],
  [/#ef4444\b/gi, 'oklch(0.62 0.21 30)'],
]

const PREMIUM_KEYFRAMES = `
/* v82nh : keyframes injectés automatiquement (LLM les avait omis) */
@keyframes auroraFadeUp { from { opacity: 0; transform: translateY(28px) } to { opacity: 1; transform: translateY(0) } }
@keyframes auroraFadeIn { from { opacity: 0 } to { opacity: 1 } }
@keyframes auroraShimmer { 0% { background-position: -200% 0 } 100% { background-position: 200% 0 } }
@keyframes auroraPulse { 0%, 100% { box-shadow: 0 0 0 0 currentColor } 50% { box-shadow: 0 0 0 12px transparent } }
@keyframes auroraFloat { 0%, 100% { transform: translateY(0) } 50% { transform: translateY(-8px) } }
`

const PREMIUM_ANIMATIONS_OVERLAY = `
/* v82nh : animations injectées automatiquement sur sélecteurs courants */
.hero h1, .hero-title, h1 { animation: auroraFadeUp 0.9s cubic-bezier(0.19, 1, 0.22, 1) both; }
.hero p, .hero-subtitle, .lead { animation: auroraFadeUp 0.9s 120ms cubic-bezier(0.19, 1, 0.22, 1) both; }
.btn, button { transition: transform 240ms cubic-bezier(0.32, 0.72, 0, 1), box-shadow 240ms cubic-bezier(0.19, 1, 0.22, 1), filter 240ms ease; }
.btn:hover, button:hover { transform: translateY(-2px) scale(1.02); }
.feature, .card, .section, section { animation: auroraFadeUp 0.8s cubic-bezier(0.19, 1, 0.22, 1) both; }
@supports (animation-timeline: view()) {
  .feature, .card, section { animation-timeline: view(); animation-range: entry 0% entry 60%; }
}
`

const SCROLL_OBSERVER_FALLBACK = `
// v82nh : scroll-driven fallback IntersectionObserver (auto-injecté)
(function () {
  if (CSS && CSS.supports && CSS.supports('animation-timeline: view()')) return;
  const targets = document.querySelectorAll('section, .feature, .card');
  if (!('IntersectionObserver' in window) || targets.length === 0) return;
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (e.isIntersecting) {
        e.target.style.animation = 'auroraFadeUp 0.8s cubic-bezier(0.19, 1, 0.22, 1) both';
        io.unobserve(e.target);
      }
    }
  }, { threshold: 0.12 });
  for (const t of targets) {
    t.style.opacity = '0';
    io.observe(t);
  }
})();
`

/** Replace common hex colors with oklch equivalents inside a CSS string. */
function elevateColors(css: string): string {
  let out = css
  for (const [re, ok] of HEX_TO_OKLCH) {
    out = out.replace(re, ok)
  }
  return out
}

/** Inject premium keyframes + animation rules if missing. */
function elevateAnimations(css: string): { css: string; injected: boolean } {
  const hasKeyframes = /@keyframes\s+\w+/i.test(css)
  const hasAnimRule = /\banimation\s*:/i.test(css)
  if (hasKeyframes && hasAnimRule) return { css, injected: false }
  let out = css
  if (!hasKeyframes) out = `${out}\n${PREMIUM_KEYFRAMES}`
  if (!hasAnimRule) out = `${out}\n${PREMIUM_ANIMATIONS_OVERLAY}`
  return { css: out, injected: true }
}

/** Replace likely-placeholder <img src="..."> with a deterministic
 * inline SVG derived from the image's alt text or surrounding heading. */
function elevateImages(html: string): { html: string; replaced: number } {
  let replaced = 0
  // Match <img tags with src that's a placeholder pattern OR that's
  // missing alt-driven sense (e.g. https://via.placeholder.com).
  const PLACEHOLDER_RE = /(<img\b[^>]*\bsrc\s*=\s*["'])(https?:\/\/(?:via\.placeholder|placehold|loremflickr|picsum)[^"']*|[a-z0-9_./-]*\.(?:png|jpe?g|webp|svg)|data:image\/[^"']+)(["'][^>]*?)(\balt\s*=\s*["']([^"']*)["'])?([^>]*?>)/gi
  const out = html.replace(PLACEHOLDER_RE, (_m, p1, _src, p3, _altGroup, alt, p6) => {
    replaced += 1
    const query = (alt || 'modern aesthetic photography').slice(0, 80).replace(/[^\w\s-]/g, '').trim()
    const url = buildAuroraInlineSvgDataUri(query, { width: 1600, height: 900 })
    const altOut = alt ? ` alt="${alt}"` : ' alt="visual"'
    return `${p1}${url}${p3}${altOut}${p6}`
  })
  return { html: out, replaced }
}

/** Inject IntersectionObserver fallback at the end of JS file when
 * scroll-driven CSS uses @supports (animation-timeline:view()). */
function elevateScript(js: string, animationsTouched: boolean): string {
  if (!animationsTouched) return js
  if (/IntersectionObserver/.test(js)) return js // already there
  return `${js}\n${SCROLL_OBSERVER_FALLBACK}`
}

export interface ElevationReport {
  hexReplaced: number
  animationsInjected: boolean
  imagesReplaced: number
  scriptInjected: boolean
}

/**
 * Apply all elevations to a parsed file set in-place. Returns a new
 * array (immutable) and a report for telemetry/UI.
 */
export function elevateGeneratedFiles(files: ParsedFile[]): { files: ParsedFile[]; report: ElevationReport } {
  const report: ElevationReport = {
    hexReplaced: 0,
    animationsInjected: false,
    imagesReplaced: 0,
    scriptInjected: false,
  }
  const out: ParsedFile[] = []
  let animationsTouched = false
  for (const f of files) {
    let content = f.content
    if (f.language === 'css' || f.language === 'scss') {
      const beforeHex = content.length
      content = elevateColors(content)
      // Count rough hex replacements (length-based estimate)
      if (content !== f.content) {
        const matches = (f.content.match(/#[0-9a-f]{6,8}\b/gi) || []).length
        const after = (content.match(/#[0-9a-f]{6,8}\b/gi) || []).length
        report.hexReplaced += Math.max(0, matches - after)
        // length sanity check (silence unused warning)
        void beforeHex
      }
      const animResult = elevateAnimations(content)
      content = animResult.css
      if (animResult.injected) {
        report.animationsInjected = true
        animationsTouched = true
      }
    } else if (f.language === 'markup' || f.language === 'html'
               || /\.html?$/i.test(f.path)) {
      // Inline <style> tags inside HTML get the same treatment.
      content = content.replace(/(<style[^>]*>)([\s\S]*?)(<\/style>)/gi, (_m, open, css, close) => {
        const lifted = elevateColors(css)
        const animResult = elevateAnimations(lifted)
        if (animResult.injected) {
          report.animationsInjected = true
          animationsTouched = true
        }
        return `${open}${animResult.css}${close}`
      })
      const imgResult = elevateImages(content)
      content = imgResult.html
      report.imagesReplaced += imgResult.replaced
    } else if (f.language === 'javascript' || f.language === 'jsx'
               || /\.m?jsx?$/i.test(f.path)) {
      // Defer scriptInjected decision until we know animationsTouched.
      // We patch this file at the end.
    }
    out.push({ ...f, content })
  }
  // Second pass : inject IntersectionObserver fallback into the LAST
  // .js/.jsx file when animations got injected.
  if (animationsTouched) {
    for (let i = out.length - 1; i >= 0; i--) {
      const f = out[i]
      if (f.language === 'javascript' || f.language === 'jsx'
          || /\.m?jsx?$/i.test(f.path)) {
        const newContent = elevateScript(f.content, animationsTouched)
        if (newContent !== f.content) {
          out[i] = { ...f, content: newContent }
          report.scriptInjected = true
        }
        break
      }
    }
  }
  return { files: out, report }
}
