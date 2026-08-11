// Viewer AUTONOME d un projet genere, en UN seul fichier HTML.
//
// Pendant Code du viewer 3D (`/api/3d/viewer-html` -> `aurora_3d_viewer.py`):
// un lien direct, ouvrable dans n importe quel navigateur, qui montre le
// resultat EN GRAND sans avoir a lancer l application ni chercher le bon
// projet. Meme contenu que le plein ecran de l UI — arborescence a gauche,
// rendu a droite, source d un fichier au clic — mais sans React ni build.
//
// Zero dependance externe: pas de CDN, pas de fetch. Tout est inline, donc la
// page fonctionne aussi bien en local qu au bout du tunnel, et hors ligne.

import {
  buildCodeFileTree,
  formatCodeFileSize,
  type CodeFileTreeNode,
} from './codeFileTreeModel.ts'

export type CodeViewerFile = { name: string; language: string; content: string }

type ViewerRow = {
  depth: number
  kind: 'dir' | 'file'
  name: string
  path: string
  size: number
}

/** Le tree model est deja teste: on l aplatit, on ne le reimplemente pas. */
function flattenTree(nodes: readonly CodeFileTreeNode[], depth = 0, out: ViewerRow[] = []): ViewerRow[] {
  for (const node of nodes) {
    out.push({
      depth,
      kind: node.isDirectory ? 'dir' : 'file',
      name: node.name,
      path: node.path,
      size: node.size,
    })
    if (node.isDirectory) flattenTree(node.children, depth + 1, out)
  }
  return out
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

/**
 * Un projet contient presque toujours `</script>`. Sans echappement, la balise
 * du projet fermerait le bloc JSON de la page et le viewer afficherait sa
 * propre charge utile en texte brut (constate en direct sur le premier essai).
 */
function embedJson(value: unknown): string {
  return JSON.stringify(value)
    .replace(/</g, '\\u003c')
    // Separateurs de ligne Unicode: valides en JSON, illegaux dans un litteral
    // JS. Un fichier genere qui en contient casserait le parse de la page.
    .replace(/\u2028/g, '\\u2028')
    .replace(/\u2029/g, '\\u2029')
}

const VIEWER_STYLE = `
*{box-sizing:border-box}
body{margin:0;background:#0d1117;color:#c9d1d9;font:13px/1.5 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif;height:100vh;display:flex;flex-direction:column}
header{display:flex;align-items:center;gap:.75rem;padding:.55rem .9rem;background:#0a0f14;border-bottom:1px solid #1c2128;flex:0 0 auto}
header b{font-size:12px;letter-spacing:.04em;text-transform:uppercase;color:#e6edf3}
header span{font-size:11px;color:#7d8590}
header .grow{flex:1}
button{font:inherit;font-size:11px;color:#c9d1d9;background:#1c2128;border:1px solid #30363d;border-radius:6px;padding:.25rem .6rem;cursor:pointer}
button:hover{background:#262c34}
button[aria-pressed=true]{background:#1f6feb33;border-color:#1f6feb;color:#cae2ff}
main{flex:1;display:flex;min-height:0}
#tree{width:19rem;flex:0 0 auto;overflow:auto;background:#0b1015;border-right:1px solid #1c2128;padding:.4rem 0}
#tree .row{display:flex;align-items:center;gap:.4rem;padding:.15rem .6rem;cursor:pointer;white-space:nowrap}
#tree .row:hover{background:#161b22}
#tree .row.sel{background:#1f6feb26;color:#cae2ff}
#tree .row .sz{margin-left:auto;font-size:10px;color:#6e7681;font-variant-numeric:tabular-nums}
#tree .dir{color:#e3b341}
#tree .file{color:#8b949e}
#stage{flex:1;min-width:0;display:flex;flex-direction:column}
#bar{display:flex;align-items:center;gap:.5rem;padding:.35rem .7rem;border-bottom:1px solid #1c2128;background:#0a0f14;font-size:11px;color:#7d8590}
#render{flex:1;border:0;background:#fff;width:100%}
#source{flex:1;overflow:auto;margin:0;padding:1rem;background:#0d1117;font:12px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace;white-space:pre;tab-size:2}
.hidden{display:none!important}
.empty{padding:2rem;color:#7d8590}
@media (max-width:820px){main{flex-direction:column}#tree{width:100%;max-height:38vh;border-right:0;border-bottom:1px solid #1c2128}}
`

const VIEWER_SCRIPT = `
const files = JSON.parse(document.getElementById('aurora-files').textContent)
const rows = JSON.parse(document.getElementById('aurora-rows').textContent)
const preview = JSON.parse(document.getElementById('aurora-preview').textContent)
const byPath = new Map(files.map((f) => [f.name, f]))
const treeEl = document.getElementById('tree')
const iframe = document.getElementById('render')
const source = document.getElementById('source')
const label = document.getElementById('label')
const backBtn = document.getElementById('back')
const collapsed = new Set()

if (preview) iframe.srcdoc = preview
else { iframe.classList.add('hidden'); source.classList.remove('hidden'); source.textContent = 'Aucun rendu web dans ce projet — choisis un fichier a gauche.' }

function hiddenByCollapse(path) {
  for (const dir of collapsed) if (path !== dir && path.startsWith(dir + '/')) return true
  return false
}

function draw() {
  treeEl.textContent = ''
  for (const row of rows) {
    if (hiddenByCollapse(row.path)) continue
    const el = document.createElement('div')
    el.className = 'row' + (row.path === current ? ' sel' : '')
    el.style.paddingLeft = (0.6 + row.depth * 0.85) + 'rem'
    const icon = document.createElement('span')
    icon.className = row.kind
    icon.textContent = row.kind === 'dir' ? (collapsed.has(row.path) ? '\\u25B8' : '\\u25BE') : '\\u2022'
    const name = document.createElement('span')
    name.textContent = row.name
    const size = document.createElement('span')
    size.className = 'sz'
    size.textContent = row.size
    el.append(icon, name, size)
    el.onclick = () => {
      if (row.kind === 'dir') { collapsed.has(row.path) ? collapsed.delete(row.path) : collapsed.add(row.path); draw() }
      else showFile(row.path)
    }
    treeEl.append(el)
  }
}

let current = null
function showFile(path) {
  const file = byPath.get(path)
  if (!file) return
  current = path
  source.textContent = file.content
  source.classList.remove('hidden')
  iframe.classList.add('hidden')
  label.textContent = path + ' \\u00b7 ' + file.language
  backBtn.classList.remove('hidden')
  draw()
}

backBtn.onclick = () => {
  current = null
  backBtn.classList.add('hidden')
  source.classList.add('hidden')
  if (preview) iframe.classList.remove('hidden')
  label.textContent = 'Rendu du projet'
  draw()
}

document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && current) backBtn.onclick() })
draw()
`

export function buildCodeViewerHtml({
  files,
  title,
  subtitle,
  previewHtml,
}: {
  files: CodeViewerFile[]
  title: string
  subtitle?: string
  /** Rendu jouable du projet (buildLivePreviewHtml). Injecte par l appelant:
   *  ce module reste pur et sans dependance a la couche navigateur. Absent =
   *  viewer en mode source seule, ce qui est le bon comportement pour un
   *  projet sans page web. */
  previewHtml?: string | null
}): string {
  const tree = buildCodeFileTree(files.map((file) => ({ name: file.name, content: file.content })))
  const rows = flattenTree(tree).map((row) => ({ ...row, size: formatCodeFileSize(row.size) }))
  const totalBytes = files.reduce((sum, file) => sum + file.content.length, 0)
  const preview = previewHtml ?? null

  return [
    '<!doctype html>',
    '<html lang="fr"><head><meta charset="utf-8">',
    '<meta name="viewport" content="width=device-width,initial-scale=1">',
    `<title>${escapeHtml(title)}</title>`,
    `<style>${VIEWER_STYLE}</style></head><body>`,
    '<header>',
    `<b>${escapeHtml(title)}</b>`,
    `<span>${files.length} fichiers &middot; ${escapeHtml(formatCodeFileSize(totalBytes))}${subtitle ? ` &middot; ${escapeHtml(subtitle)}` : ''}</span>`,
    '<span class="grow"></span>',
    '<button id="back" class="hidden">Retour au rendu</button>',
    '</header>',
    '<main><div id="tree"></div><div id="stage">',
    '<div id="bar"><span id="label">Rendu du projet</span></div>',
    '<iframe id="render" sandbox="allow-scripts allow-same-origin" title="Rendu du projet"></iframe>',
    '<pre id="source" class="hidden"></pre>',
    '</div></main>',
    `<script type="application/json" id="aurora-files">${embedJson(files)}</script>`,
    `<script type="application/json" id="aurora-rows">${embedJson(rows)}</script>`,
    `<script type="application/json" id="aurora-preview">${embedJson(preview)}</script>`,
    `<script>${VIEWER_SCRIPT}</script>`,
    '</body></html>',
  ].join('\n')
}
