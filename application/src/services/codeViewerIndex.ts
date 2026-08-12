// HUB des projets generes: une page stable qui les liste TOUS.
//
// Le lien par run (`viewers/run-971/index.html`) est jetable: il faut le
// retrouver, un par generation. Ce qui manquait, c est une adresse STABLE d ou
// l on voit tout ce qui a ete produit, avec les plateformes reellement
// simulees pour chaque projet, et de quoi passer de l un a l autre SANS
// recharger une autre page.
//
// L index n invente aucun stockage: il est derive de ce qui existe deja sur
// disque sous `output/code_assets/viewers/<id>/`, servi par la route GET
// `/api/code/assets/file/<path>` que le pont expose depuis toujours.

import { CODE_VIEWER_STYLE, embedViewerJson, escapeViewerHtml } from './codeViewerAssets.ts'

export const CODE_VIEWER_INDEX_SCHEMA = 'aurora.code.viewer-index/1'

/** Plateforme reellement eprouvee, telle que WS12 la rapporte. */
export type CodeViewerPlatform = {
  /** `web` | `mobile_real` | `embedded` | `os_boot` | `console` */
  family: string
  label: string
  /** `executed` = reellement lance, pas seulement detecte. */
  status: string
  realExecution: boolean
}

export type CodeViewerIndexEntry = {
  id: string
  title: string
  createdAt: number
  fileCount: number
  bytes: number
  projectType?: string
  score?: number | null
  brief?: string
  platforms?: CodeViewerPlatform[]
  /** APK signe reellement construit pour ce projet, quand il y en a un. */
  apk?: { file: string; bytes: number }
}

export type CodeViewerIndex = {
  schemaVersion: typeof CODE_VIEWER_INDEX_SCHEMA
  generatedAt: number
  projects: CodeViewerIndexEntry[]
}

/** Les familles connues, dans l ordre ou on veut les lire. */
const FAMILY_LABEL: Record<string, string> = {
  web: 'Web',
  mobile_real: 'Mobile',
  tablet: 'Tablette',
  embedded: 'Embarque',
  os_boot: 'Systeme',
  console: 'Console',
}

export function describePlatformFamily(family: string): string {
  return FAMILY_LABEL[family] ?? family
}

/**
 * Deduit les plateformes affichables depuis les etapes brutes du labo WS12.
 * Une etape seulement DETECTEE n est pas une plateforme validee: on garde le
 * statut pour que la pastille ne mente pas.
 */
export function platformsFromSimulationStages(
  stages: ReadonlyArray<{ family?: string; label?: string; status?: string; realExecution?: boolean }>,
): CodeViewerPlatform[] {
  const byFamily = new Map<string, CodeViewerPlatform>()
  for (const stage of stages) {
    const family = String(stage.family || 'web')
    const real = stage.realExecution === true
    const current = byFamily.get(family)
    // On garde la meilleure preuve par famille: une execution reelle prime.
    if (!current || (real && !current.realExecution)) {
      byFamily.set(family, {
        family,
        label: describePlatformFamily(family),
        status: String(stage.status || 'unavailable'),
        realExecution: real,
      })
    }
  }
  return [...byFamily.values()]
}

export function buildCodeViewerIndex(entries: CodeViewerIndexEntry[]): CodeViewerIndex {
  return {
    schemaVersion: CODE_VIEWER_INDEX_SCHEMA,
    generatedAt: Date.now(),
    // Le plus recent en premier: c est celui qu on vient de generer.
    projects: [...entries].sort((a, b) => b.createdAt - a.createdAt),
  }
}

const HUB_EXTRA_STYLE = `
#list{flex:1;overflow:auto;padding:1.1rem}
.grid{display:grid;gap:.8rem;grid-template-columns:repeat(auto-fill,minmax(19rem,1fr))}
.card{background:#0f151c;border:1px solid #1c2128;border-radius:10px;padding:.85rem .95rem;cursor:pointer;transition:border-color .15s,transform .15s}
.card:hover{border-color:#2f81f7;transform:translateY(-1px)}
.card h3{margin:0 0 .3rem;font-size:13px;color:#e6edf3;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.card .meta{font-size:11px;color:#7d8590;display:flex;gap:.5rem;flex-wrap:wrap}
.card .brief{margin:.5rem 0 .55rem;font-size:11px;color:#8b949e;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.tags{display:flex;gap:.3rem;flex-wrap:wrap}
.tag{font-size:10px;padding:.1rem .45rem;border-radius:999px;border:1px solid #30363d;color:#8b949e}
.tag.real{border-color:#2ea04366;color:#7ee787;background:#2ea04314}
.tag.deg{border-color:#d2992255;color:#e3b341;background:#d2992214}
.apk{font-size:10px;padding:.1rem .5rem;border-radius:999px;border:1px solid #1f6feb;color:#cae2ff;background:#1f6feb1f;text-decoration:none}
.apk:hover{background:#1f6feb33}
select{font:inherit;font-size:11px;background:#1c2128;color:#c9d1d9;border:1px solid #30363d;border-radius:6px;padding:.25rem .5rem;max-width:16rem}
#hubEmpty{padding:2.5rem;color:#7d8590;text-align:center}
`

const HUB_SCRIPT = `
const index = JSON.parse(document.getElementById('aurora-index').textContent)
const listEl = document.getElementById('list')
const mainEl = document.getElementById('viewer')
const picker = document.getElementById('picker')
const backList = document.getElementById('backList')
const title = document.getElementById('hubTitle')
const sub = document.getElementById('hubSub')
const treeEl = document.getElementById('tree')
const iframe = document.getElementById('render')
const source = document.getElementById('source')
const label = document.getElementById('label')
const backBtn = document.getElementById('back')
let rows = [], byPath = new Map(), preview = null, current = null, notice = null
const collapsed = new Set()

function fmtDate(ms) { try { return new Date(ms).toLocaleString('fr-FR') } catch { return '' } }

function renderList() {
  mainEl.classList.add('hidden'); listEl.classList.remove('hidden')
  backList.classList.add('hidden'); picker.classList.add('hidden'); backBtn.classList.add('hidden')
  title.textContent = 'Projets generes'
  sub.textContent = index.projects.length + ' projet(s)'
  if (index.projects.length === 0) { listEl.innerHTML = '<div id="hubEmpty">Aucun projet genere pour l instant.</div>'; return }
  const grid = document.createElement('div'); grid.className = 'grid'
  for (const p of index.projects) {
    const card = document.createElement('div'); card.className = 'card'
    const h = document.createElement('h3'); h.textContent = p.title; h.title = p.title
    const meta = document.createElement('div'); meta.className = 'meta'
    meta.textContent = [fmtDate(p.createdAt), p.fileCount + ' fichiers', Math.round(p.bytes / 1024) + ' Ko', p.projectType || '', (p.score || p.score === 0) ? p.score + '/100' : ''].filter(Boolean).join(' \\u00b7 ')
    const brief = document.createElement('div'); brief.className = 'brief'; brief.textContent = p.brief || ''
    const tags = document.createElement('div'); tags.className = 'tags'
    for (const pf of (p.platforms || [])) {
      const t = document.createElement('span')
      t.className = 'tag' + (pf.realExecution ? ' real' : (pf.status === 'degraded' ? ' deg' : ''))
      t.textContent = pf.label + (pf.realExecution ? ' \\u2713' : '')
      t.title = pf.family + ' \\u00b7 ' + pf.status
      tags.append(t)
    }
    if (p.apk) {
      const dl = document.createElement('a')
      dl.className = 'apk'
      dl.href = './' + p.id + '/' + p.apk.file
      dl.download = p.id + '.apk'
      dl.textContent = '\u2b07 APK signe (' + Math.round(p.apk.bytes / 1024) + ' Ko)'
      dl.title = 'Telecharger, puis sur le telephone: autoriser les sources inconnues, ouvrir le fichier, installer. Ou: adb install ' + p.id + '.apk'
      dl.onclick = (e) => e.stopPropagation()
      tags.append(dl)
    }
    card.append(h, meta, brief, tags)
    card.onclick = () => open(p.id)
    grid.append(card)
  }
  listEl.textContent = ''; listEl.append(grid)
}

function hiddenByCollapse(path) {
  for (const dir of collapsed) if (path !== dir && path.startsWith(dir + '/')) return true
  return false
}

function drawTree() {
  treeEl.textContent = ''
  for (const row of rows) {
    if (hiddenByCollapse(row.path)) continue
    const el = document.createElement('div')
    el.className = 'row' + (row.path === current ? ' sel' : '')
    el.style.paddingLeft = (0.6 + row.depth * 0.85) + 'rem'
    const icon = document.createElement('span'); icon.className = row.kind
    icon.textContent = row.kind === 'dir' ? (collapsed.has(row.path) ? '\\u25B8' : '\\u25BE') : '\\u2022'
    const name = document.createElement('span'); name.textContent = row.name
    const size = document.createElement('span'); size.className = 'sz'; size.textContent = row.size
    el.append(icon, name, size)
    el.onclick = () => {
      if (row.kind === 'dir') { collapsed.has(row.path) ? collapsed.delete(row.path) : collapsed.add(row.path); drawTree() }
      else showFile(row.path)
    }
    treeEl.append(el)
  }
}

function showFile(path) {
  const file = byPath.get(path); if (!file) return
  current = path; source.textContent = file.content
  source.classList.remove('hidden'); iframe.classList.add('hidden')
  label.textContent = path + ' \\u00b7 ' + file.language
  backBtn.classList.remove('hidden'); drawTree()
}

function showRender() {
  current = null; backBtn.classList.add('hidden'); source.classList.add('hidden')
  if (preview) iframe.classList.remove('hidden')
  label.textContent = preview ? 'Rendu du projet' : (notice ? 'Build requis \\u2014 code consultable a gauche' : 'Aucun rendu web \\u2014 choisis un fichier')
  if (!preview) {
    source.classList.remove('hidden')
    source.textContent = notice || 'Ce projet n a pas de page web a rendre.'
  }
  drawTree()
}

async function open(id) {
  const entry = index.projects.find((p) => p.id === id); if (!entry) return
  title.textContent = 'Chargement\\u2026'
  let payload
  try {
    const res = await fetch('./' + id + '/project.json', { cache: 'no-store' })
    if (!res.ok) throw new Error('HTTP ' + res.status)
    payload = await res.json()
  } catch (err) {
    title.textContent = entry.title
    sub.textContent = 'projet illisible: ' + err.message
    return
  }
  rows = payload.rows; preview = payload.preview || null; notice = payload.notice || null; collapsed.clear()
  byPath = new Map(payload.files.map((f) => [f.name, f]))
  iframe.srcdoc = preview || ''
  listEl.classList.add('hidden'); mainEl.classList.remove('hidden')
  backList.classList.remove('hidden'); picker.classList.remove('hidden')
  picker.value = id
  title.textContent = entry.title
  sub.textContent = entry.fileCount + ' fichiers \\u00b7 ' + Math.round(entry.bytes / 1024) + ' Ko'
  showRender()
  history.replaceState(null, '', '#' + id)
}

picker.onchange = () => open(picker.value)
backList.onclick = () => { history.replaceState(null, '', '#'); renderList() }
backBtn.onclick = showRender
document.addEventListener('keydown', (e) => {
  if (e.key !== 'Escape') return
  if (current) showRender()
  else if (!mainEl.classList.contains('hidden')) backList.onclick()
})

for (const p of index.projects) {
  const opt = document.createElement('option'); opt.value = p.id; opt.textContent = p.title
  picker.append(opt)
}
const wanted = decodeURIComponent(location.hash.replace('#', ''))
if (wanted && index.projects.some((p) => p.id === wanted)) open(wanted)
else renderList()
`

export function buildCodeViewerIndexHtml(index: CodeViewerIndex): string {
  return [
    '<!doctype html>',
    '<html lang="fr"><head><meta charset="utf-8">',
    '<meta name="viewport" content="width=device-width,initial-scale=1">',
    '<title>Projets Aurora — Code</title>',
    `<style>${CODE_VIEWER_STYLE}${HUB_EXTRA_STYLE}</style></head><body>`,
    '<header>',
    '<b id="hubTitle">Projets generes</b>',
    '<span id="hubSub"></span>',
    '<span class="grow"></span>',
    '<select id="picker" class="hidden" title="Changer de projet"></select>',
    '<button id="back" class="hidden">Retour au rendu</button>',
    '<button id="backList" class="hidden">Tous les projets</button>',
    '</header>',
    '<div id="list"></div>',
    '<main id="viewer" class="hidden"><div id="tree"></div><div id="stage">',
    '<div id="bar"><span id="label">Rendu du projet</span></div>',
    '<iframe id="render" sandbox="allow-scripts allow-same-origin" title="Rendu du projet"></iframe>',
    '<pre id="source" class="hidden"></pre>',
    '</div></main>',
    `<script type="application/json" id="aurora-index">${embedViewerJson(index)}</script>`,
    `<script>${HUB_SCRIPT}</script>`,
    '</body></html>',
    `<!-- ${escapeViewerHtml(String(index.projects.length))} projets -->`,
  ].join('\n')
}
