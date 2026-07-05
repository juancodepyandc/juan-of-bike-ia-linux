/**
 * Exporte un nœud DOM en PDF imprimable via window.print().
 * Pas de dépendance npm — on ouvre une fenêtre blanche, on y copie le HTML
 * cible + un print stylesheet inline, et on déclenche l'impression. Le
 * navigateur laisse ensuite l'utilisateur choisir "Enregistrer en PDF".
 *
 * Utilisable pour :
 *   - Fiches de révision (Academy)
 *   - Énoncés d'exercices corrigés
 *   - Rapports Forge (rig + meta)
 */

const PRINT_CSS = `
  @page {
    size: A4;
    margin: 18mm 16mm 18mm 16mm;
  }
  * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
  html, body {
    background: #ecdcb0 !important;
    color: #1a0f05 !important;
    font-family: 'Inter', system-ui, sans-serif;
    font-size: 11pt;
    line-height: 1.45;
    margin: 0;
    padding: 0;
  }
  h1, h2, h3, h4, h5 {
    font-family: 'Bangers', cursive;
    letter-spacing: 1.5px;
    color: #1a0f05;
    break-after: avoid;
  }
  h1 { font-size: 22pt; }
  h2 { font-size: 16pt; }
  h3 { font-size: 13pt; }
  img { max-width: 100%; height: auto; }
  pre, code {
    font-family: 'JetBrains Mono', monospace;
    font-size: 9.5pt;
    background: #e1d2a4;
    padding: 2px 5px;
    border-radius: 3px;
  }
  pre { padding: 8px 10px; page-break-inside: avoid; white-space: pre-wrap; }
  table { border-collapse: collapse; width: 100%; margin: 8px 0; }
  th, td { border: 1px solid #3d2a12; padding: 4px 6px; }
  th { background: #c9b280; }
  blockquote {
    border-left: 3px solid #c9a24b;
    padding-left: 10px; margin: 8px 0;
    color: #3d2a12;
  }
  .ay-sheet, .ay-sheet-s, .ay-sheet-block,
  .ay-sheet-grid article {
    page-break-inside: avoid;
    box-shadow: none !important;
  }
  /* Force kind-specific blocks to keep together in print */
  .ay-sheet-block-def, .ay-sheet-block-formula, .ay-sheet-block-props,
  .ay-sheet-block-attention, .ay-sheet-block-method {
    page-break-inside: avoid;
  }
  /* Hide anything we don't want on paper */
  .no-print, button, .ay-obj-grader-actions, .ay-obj-deephint { display: none !important; }
  .katex-display, .katex {
    color: #1a0f05 !important;
  }
`

export interface PrintOptions {
  /** Printed document title (shown in the PDF header). */
  title?: string
  /** Optional subtitle printed at the top. */
  subtitle?: string
  /** Extra footer line. */
  footer?: string
  /** Additional inline CSS appended AFTER PRINT_CSS. */
  extraCss?: string
}

/**
 * Render a node to a print-friendly window and trigger print.
 * Works in Chrome, Firefox, Safari, Edge, Brave — and on Android Chrome.
 * Safari iOS: opens a share sheet with "Save to Files" (which produces a PDF).
 */
export function printElement(node: HTMLElement, opts: PrintOptions = {}): void {
  const { title = 'Export juan of bike IA', subtitle, footer, extraCss = '' } = opts
  const w = window.open('', '_blank', 'width=900,height=1200')
  if (!w) {
    // Popup blocked — fall back to inline hidden iframe
    printViaIframe(node, opts)
    return
  }
  const fontsLink = `
    <link rel="preconnect" href="https://fonts.googleapis.com" crossorigin />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bangers&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600;700&display=swap" />
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css" />
  `
  w.document.open()
  w.document.write(`<!doctype html><html lang="fr"><head><meta charset="utf-8" />
    <title>${escapeHtml(title)}</title>
    ${fontsLink}
    <style>${PRINT_CSS}${extraCss}</style>
    </head><body>
    <div class="print-head" style="margin-bottom:14px;border-bottom:2px solid #1a0f05;padding-bottom:6px">
      <div style="font-family:'Bangers',cursive;font-size:20pt;letter-spacing:2px">${escapeHtml(title)}</div>
      ${subtitle ? `<div style="font-family:'JetBrains Mono',monospace;font-size:10pt;color:#6b523a">${escapeHtml(subtitle)}</div>` : ''}
    </div>
    <div class="print-body">${node.outerHTML}</div>
    ${footer ? `<div class="print-foot" style="margin-top:18px;border-top:1px dashed #3d2a12;padding-top:6px;font-size:9pt;color:#6b523a">${escapeHtml(footer)}</div>` : ''}
  </body></html>`)
  w.document.close()
  // Wait for fonts + images, then print
  const launch = () => {
    try { w.focus(); w.print() }
    finally {
      // Close after a short delay so Safari keeps the window long enough to print
      setTimeout(() => { try { w.close() } catch { /* ignore */ } }, 500)
    }
  }
  if (w.document.readyState === 'complete') setTimeout(launch, 250)
  else w.addEventListener('load', () => setTimeout(launch, 250))
}

function printViaIframe(node: HTMLElement, opts: PrintOptions): void {
  const ifr = document.createElement('iframe')
  ifr.style.position = 'fixed'
  ifr.style.right = '0'
  ifr.style.bottom = '0'
  ifr.style.width = '0'
  ifr.style.height = '0'
  ifr.style.border = '0'
  document.body.appendChild(ifr)
  const doc = ifr.contentWindow?.document
  if (!doc) { document.body.removeChild(ifr); return }
  doc.open()
  doc.write(`<!doctype html><html><head><title>${escapeHtml(opts.title || 'Export')}</title>
    <style>${PRINT_CSS}${opts.extraCss || ''}</style></head>
    <body><div>${node.outerHTML}</div></body></html>`)
  doc.close()
  setTimeout(() => {
    try { ifr.contentWindow?.focus(); ifr.contentWindow?.print() } catch { /* ignore */ }
    setTimeout(() => { try { document.body.removeChild(ifr) } catch { /* ignore */ } }, 1500)
  }, 350)
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) =>
    (({'&': '&amp;','<': '&lt;','>': '&gt;','"': '&quot;',"'": '&#39;'} as Record<string,string>)[c]),
  )
}
