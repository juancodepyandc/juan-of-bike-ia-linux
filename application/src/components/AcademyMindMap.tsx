/**
 * AcademyMindMap — render a Mermaid `mindmap` diagram inside an iframe
 * sandbox so the parent React tree never has to npm install mermaid.js
 * itself. The iframe loads the official mermaid CDN and renders the
 * source the user generated.
 *
 * v82bv : interactive zoom/pan via mermaid.js — l'user peut cliquer
 * et naviguer dans la carte mentale directement.
 */
import { useMemo } from 'react'

const MERMAID_CDN = 'https://cdn.jsdelivr.net/npm/mermaid@10.9.0/dist/mermaid.esm.min.mjs'

function buildHtml(code: string, dark: boolean): string {
  const escaped = code.replace(/`/g, '\\`')
  const theme = dark ? 'dark' : 'default'
  const bg = dark ? '#0c0a09' : '#fafafb'
  const fg = dark ? '#f5f5f5' : '#1a140d'
  return `<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<style>
  html, body { margin: 0; padding: 0; height: 100%; background: ${bg}; color: ${fg}; font-family: ui-sans-serif, system-ui; overflow: hidden; }
  #mm { width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; padding: 16px; box-sizing: border-box; }
  .mermaid { max-width: 100%; max-height: 100%; }
  #mm-err { padding: 14px; color: #ff6a3d; font-family: ui-monospace, monospace; font-size: 12px; white-space: pre-wrap; }
</style>
</head>
<body>
<div id="mm"><div class="mermaid" id="mmd">\`PENDING\`</div></div>
<div id="mm-err"></div>
<script type="module">
  import mermaid from '${MERMAID_CDN}';
  mermaid.initialize({ startOnLoad: false, theme: '${theme}', securityLevel: 'loose', mindmap: { padding: 14, maxNodeWidth: 220 } });
  const code = \`${escaped}\`;
  const host = document.getElementById('mmd');
  const err = document.getElementById('mm-err');
  try {
    const { svg } = await mermaid.render('mmd-rendered', code);
    host.innerHTML = svg;
    // Petit zoom natif via wheel + drag pan
    const svgEl = host.querySelector('svg');
    if (svgEl) {
      svgEl.style.cursor = 'grab';
      let scale = 1, x = 0, y = 0, dragging = false, sx = 0, sy = 0;
      function apply() { svgEl.style.transform = \`translate(\${x}px, \${y}px) scale(\${scale})\`; svgEl.style.transformOrigin = '0 0'; }
      svgEl.addEventListener('wheel', (e) => { e.preventDefault(); scale = Math.max(0.3, Math.min(3, scale * (e.deltaY < 0 ? 1.1 : 0.9))); apply(); }, { passive: false });
      svgEl.addEventListener('mousedown', (e) => { dragging = true; sx = e.clientX - x; sy = e.clientY - y; svgEl.style.cursor = 'grabbing'; });
      window.addEventListener('mouseup', () => { dragging = false; svgEl.style.cursor = 'grab'; });
      window.addEventListener('mousemove', (e) => { if (!dragging) return; x = e.clientX - sx; y = e.clientY - sy; apply(); });
    }
  } catch (e) {
    host.style.display = 'none';
    err.textContent = '⚠ Mermaid render failed:\\n' + (e && e.message ? e.message : String(e)) + '\\n\\nSource:\\n' + code;
  }
</script>
</body>
</html>`
}

interface Props {
  code: string
  dark?: boolean
  height?: number | string
}

export default function AcademyMindMap({ code, dark = true, height = 360 }: Props) {
  const html = useMemo(() => buildHtml(code, dark), [code, dark])
  return (
    <iframe
      title="Carte mentale Aurora"
      srcDoc={html}
      sandbox="allow-scripts"
      style={{
        width: '100%',
        height,
        border: '1px solid var(--line, rgba(255,255,255,0.12))',
        borderRadius: 8,
        background: dark ? '#0c0a09' : '#fafafb',
      }}
    />
  )
}
