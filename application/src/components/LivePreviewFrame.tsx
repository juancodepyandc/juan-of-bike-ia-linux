/**
 * LivePreviewFrame — runs a user snippet in a sandboxed iframe.
 *
 * Detects language from the code :
 *   - pure HTML (starts with <!doctype|<html|<div…)       → drop into srcDoc
 *   - CSS                                                  → wrap in <style>
 *   - JS                                                    → wrap in <script>
 *   - mixed (HTML + script)                                 → srcDoc as-is
 *
 * The iframe uses `sandbox="allow-scripts allow-forms allow-modals"` — NO
 * same-origin, NO storage, NO top-navigation. Safe for untrusted output.
 */
import { useMemo, useState } from 'react'

interface Props {
  code: string
  language?: string
  /** Optional light head block (fonts / reset CSS). */
  injectHead?: string
}

function looksLikeHtml(s: string): boolean {
  return /^<(!doctype|html|head|body|div|section|main|template|style|script)/i.test(s.trim())
}
function looksLikeCss(s: string): boolean {
  return /^[\s\n]*[.#*][\w-]+\s*\{/.test(s) && !/^</.test(s.trim())
}

export default function LivePreviewFrame({ code, language, injectHead = '' }: Props) {
  const [reloadKey, setReloadKey] = useState(0)

  const srcDoc = useMemo(() => {
    const c = (code || '').trim()
    const lang = (language || '').toLowerCase()
    const baseHead = `
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <style>
        body { font-family: system-ui, -apple-system, sans-serif; margin: 0; padding: 14px; color: #1a0f05; background: #ecdcb0; }
        * { box-sizing: border-box; }
      </style>
      ${injectHead}
    `
    if (looksLikeHtml(c)) {
      // if the user already wrote a full document, respect it; else wrap.
      if (/<html[\s>]/i.test(c)) return c
      return `<!doctype html><html><head>${baseHead}</head><body>${c}</body></html>`
    }
    if (lang === 'css' || looksLikeCss(c)) {
      return `<!doctype html><html><head>${baseHead}<style>${c}</style></head><body>
        <div>L'aperçu ci-dessous applique tes styles. Ajoute du HTML pour les voir agir.</div>
        <button>Bouton</button> <input placeholder="input" /> <p>Un paragraphe d'exemple.</p>
      </body></html>`
    }
    if (lang === 'js' || lang === 'javascript' || lang === 'ts' || lang === 'typescript') {
      // JS/TS: compile-strip types by replacing `: type` and interface blocks — VERY best-effort.
      // Most modern TS that uses only type annotations runs as JS with types stripped.
      const js = c
        .replace(/^\s*(interface|type)\s+[^\{;]+[\{;][\s\S]*?^\}/gm, '')
        .replace(/:\s*[A-Za-z_][\w<>.[\]| ,&]*(?=\s*[,=)])/g, '')
      return `<!doctype html><html><head>${baseHead}</head><body>
        <pre id="console" style="background:#1a0f05;color:#c5f0c5;padding:8px;border-radius:4px;font-family:ui-monospace,monospace;min-height:40px;white-space:pre-wrap"></pre>
        <div id="app"></div>
        <script>
          const _c = document.getElementById('console');
          const _orig = console.log.bind(console);
          console.log = (...a) => { _orig(...a); _c.textContent += a.map(x => typeof x === 'object' ? JSON.stringify(x) : String(x)).join(' ') + '\\n'; };
          window.addEventListener('error', (e) => { _c.textContent += '⚠ ' + e.message + '\\n'; });
          try { ${js} } catch (e) { _c.textContent += '⚠ ' + e.message + '\\n'; }
        </script>
      </body></html>`
    }
    // Fallback: render as pre
    return `<!doctype html><html><head>${baseHead}</head><body><pre style="white-space:pre-wrap;font-family:ui-monospace,monospace;background:#fff8e0;padding:10px;border:1px solid #1a0f05;border-radius:4px">${
      c.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    }</pre></body></html>`
  }, [code, language, injectHead])

  return (
    <div className="lpf-root">
      <div className="lpf-head">
        <span className="lpf-title">▶ Live preview{language ? ` (${language})` : ''}</span>
        <button type="button" className="lpf-reload" onClick={() => setReloadKey((k) => k + 1)} title="Recharger">↻</button>
      </div>
      <iframe
        key={reloadKey}
        className="lpf-frame"
        title="Live preview"
        sandbox="allow-scripts allow-forms allow-modals"
        srcDoc={srcDoc}
      />
    </div>
  )
}
