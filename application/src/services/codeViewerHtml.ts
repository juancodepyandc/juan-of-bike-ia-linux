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

import { CODE_VIEWER_STYLE, embedViewerJson, escapeViewerHtml } from './codeViewerAssets.ts'
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

/**
 * Charge utile d un projet pour le HUB: memes lignes d arborescence et meme
 * rendu que la page autonome, mais chargees a la demande par `fetch`. Un seul
 * calcul d arbre pour les deux surfaces.
 */
export function buildCodeViewerProjectPayload({
  files,
  previewHtml,
}: {
  files: CodeViewerFile[]
  previewHtml?: string | null
}): { files: CodeViewerFile[]; rows: Array<Omit<ViewerRow, 'size'> & { size: string }>; preview: string | null } {
  const tree = buildCodeFileTree(files.map((file) => ({ name: file.name, content: file.content })))
  return {
    files,
    rows: flattenTree(tree).map((row) => ({ ...row, size: formatCodeFileSize(row.size) })),
    preview: previewHtml ?? null,
  }
}

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
    `<title>${escapeViewerHtml(title)}</title>`,
    `<style>${CODE_VIEWER_STYLE}</style></head><body>`,
    '<header>',
    `<b>${escapeViewerHtml(title)}</b>`,
    `<span>${files.length} fichiers &middot; ${escapeViewerHtml(formatCodeFileSize(totalBytes))}${subtitle ? ` &middot; ${escapeViewerHtml(subtitle)}` : ''}</span>`,
    '<span class="grow"></span>',
    '<button id="back" class="hidden">Retour au rendu</button>',
    '</header>',
    '<main><div id="tree"></div><div id="stage">',
    '<div id="bar"><span id="label">Rendu du projet</span></div>',
    '<iframe id="render" sandbox="allow-scripts allow-same-origin" title="Rendu du projet"></iframe>',
    '<pre id="source" class="hidden"></pre>',
    '</div></main>',
    `<script type="application/json" id="aurora-files">${embedViewerJson(files)}</script>`,
    `<script type="application/json" id="aurora-rows">${embedViewerJson(rows)}</script>`,
    `<script type="application/json" id="aurora-preview">${embedViewerJson(preview)}</script>`,
    `<script>${VIEWER_SCRIPT}</script>`,
    '</body></html>',
  ].join('\n')
}
