// Aurora-Connect popup logic
const api = (typeof browser !== 'undefined') ? browser : chrome

const dot = document.getElementById('dot')
const status = document.getElementById('status')
const lastCheck = document.getElementById('last-check')
const bridge = document.getElementById('bridge')
const allowEval = document.getElementById('allow-eval')
const reconnect = document.getElementById('reconnect')
const openOptions = document.getElementById('open-options')
const openDocs = document.getElementById('open-docs')
const pagetypeRow = document.getElementById('pagetype-row')
const pagetypeBadge = document.getElementById('pagetype-badge')
const pagetypeName = document.getElementById('pagetype-name')
// v82n0 — daily stats tile elements (Today's activity).
const statsText = document.getElementById('stats-text')

// v82ly — pageType→badge mapping. KEEP IN SYNC with background.js#pageTypeToBadge
// and __tests__/extensionPageTypeBadge.test.ts. Order matters : highest
// specificity first (login > social_feed > article > media > listing > dashboard > form).
function pageTypeToBadge(pageType) {
  if (!pageType || typeof pageType !== 'object') return null
  if (pageType.login) return { text: 'L', color: '#ef4444' }
  if (pageType.social_feed) return { text: 'F', color: '#8b5cf6' }
  if (pageType.article) return { text: 'A', color: '#0ea5e9' }
  if (pageType.media) return { text: 'M', color: '#f97316' }
  if (pageType.listing) return { text: 'T', color: '#10b981' }
  if (pageType.dashboard) return { text: 'D', color: '#a855f7' }
  if (pageType.form) return { text: 'O', color: '#eab308' }
  return null
}

// Render the per-tab pageType badge from chrome.storage.session. The session
// store is populated by background.js after each analyze_page call (key
// pagetype_<tabId>). When no entry exists for the active tab, render a grey
// "?" so the user knows the extension hasn't analyzed this tab yet.
function renderPagetypeBadge(label, badge) {
  if (!pagetypeRow || !pagetypeBadge || !pagetypeName) return
  pagetypeRow.style.display = 'flex'
  if (badge) {
    pagetypeBadge.textContent = badge.text
    pagetypeBadge.style.background = badge.color
  } else {
    pagetypeBadge.textContent = '?'
    pagetypeBadge.style.background = 'rgba(255,255,255,.18)'
  }
  pagetypeName.textContent = label || ''
}

function refreshPagetype() {
  if (!api?.tabs?.query) return
  api.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    const tab = tabs && tabs[0]
    if (!tab || typeof tab.id !== 'number') {
      renderPagetypeBadge('(aucun onglet actif)', null)
      return
    }
    const label = tab.title || tab.url || ''
    const key = 'pagetype_' + tab.id
    const session = api.storage?.session
    if (!session || typeof session.get !== 'function') {
      // Old browsers without storage.session : render the default "?" badge
      // with the tab name so the row at least shows something useful.
      renderPagetypeBadge(label, null)
      return
    }
    session.get([key], (r) => {
      const entry = r && r[key]
      const pt = entry && entry.pageType
      renderPagetypeBadge(label, pageTypeToBadge(pt))
    })
  })
}

// v82n0 — daily activity stats tile. Reads the rolling counter the SW
// maintains in chrome.storage.local under `aurora_stats_<YYYY-MM-DD>`.
// Pure rendering — no fetch, no SW message, just storage read. The SW
// performs the daily rollover (entries >7 days are pruned on each bump).
//
// Exported logic is unit-tested via __tests__/extensionStatsTile.test.ts —
// keep formatStatsLine signature stable.
function statsTodayKey() {
  const d = new Date()
  const yyyy = d.getFullYear()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return 'aurora_stats_' + yyyy + '-' + mm + '-' + dd
}

function formatStatsLine(stats) {
  if (!stats || typeof stats !== 'object') {
    return "Aujourd'hui · 0 pages · 0 scrapes"
  }
  const pages = Number(stats.pages) || 0
  const scrapes = Number(stats.scrapes) || 0
  const pins = Number(stats.pins) || 0
  const escal = Number(stats.escalations) || 0
  const parts = []
  parts.push(pages + (pages === 1 ? ' page' : ' pages'))
  parts.push(scrapes + (scrapes === 1 ? ' scrape' : ' scrapes'))
  if (pins > 0) parts.push(pins + (pins === 1 ? ' pin' : ' pins'))
  if (escal > 0) parts.push(escal + (escal === 1 ? ' escalade' : ' escalades'))
  return "Aujourd'hui · " + parts.join(' · ')
}

function refreshStats() {
  if (!statsText) return
  const key = statsTodayKey()
  api.storage.local.get([key], (r) => {
    statsText.textContent = formatStatsLine(r && r[key])
  })
}

function refresh() {
  api.storage.local.get(['status', 'statusAt', 'bridgeUrl', 'allowEval'], (r) => {
    if (r.status === 'connected') {
      dot.className = 'dot dot-ok'
      status.textContent = 'Connecte au bridge'
    } else {
      dot.className = 'dot dot-ko'
      status.textContent = 'Hors ligne'
    }
    if (r.statusAt) {
      const sec = Math.floor((Date.now() - r.statusAt) / 1000)
      lastCheck.textContent = `Dernier ping il y a ${sec}s`
    }
    bridge.value = r.bridgeUrl || 'http://127.0.0.1:3001'
    allowEval.checked = !!r.allowEval
  })
}

bridge.addEventListener('change', () => {
  api.storage.local.set({ bridgeUrl: bridge.value.trim() })
})
allowEval.addEventListener('change', () => {
  api.storage.local.set({ allowEval: allowEval.checked })
})
reconnect.addEventListener('click', () => {
  api.storage.local.set({ bridgeUrl: bridge.value.trim() })
  setTimeout(refresh, 500)
})
openOptions.addEventListener('click', () => {
  if (api.runtime.openOptionsPage) api.runtime.openOptionsPage()
})
openDocs.addEventListener('click', (e) => {
  e.preventDefault()
  api.tabs.create({ url: bridge.value.trim() + '/docs/extension.html' })
})
// v82jw : open vault popup credentials
const openCreds = document.getElementById('open-credentials')
if (openCreds) {
  openCreds.addEventListener('click', () => {
    api.tabs.create({ url: api.runtime.getURL('popup-credentials.html') })
  })
}

// v82lz — event-driven badge updates via chrome.storage.session.onChanged.
// The 1.5s polling tick is kept for the connection-status dot ONLY (it polls
// chrome.storage.local for { status, statusAt, bridgeUrl }). The pageType
// badge no longer rides on that tick : it re-renders the moment background.js
// writes a fresh `pagetype_<tabId>` entry into session storage. This makes
// the popup feel instantaneous when the user switches tabs or a new
// analyze_page completes, and avoids burning a chrome.storage.session.get
// every 1.5s for nothing.
//
// Debouncing : if storage events fire in bursts (rare, but possible during
// rapid tab switches), we throttle to one re-render per 50ms. The query
// against chrome.tabs is async ; without throttling we could fire two
// concurrent queries and render in flip-flop order.
//
// Cleanup : on popup close (window unload) we explicitly remove the listener
// so the service worker doesn't accumulate dead callbacks across popup
// open/close cycles. Memory leak guard for the SW-side onChanged registry.
let _pagetypeRefreshTimer = null
function refreshPagetypeDebounced() {
  if (_pagetypeRefreshTimer) return
  _pagetypeRefreshTimer = setTimeout(() => {
    _pagetypeRefreshTimer = null
    refreshPagetype()
  }, 50)
}

function onSessionChange(changes, areaName) {
  // v82n0 — also listen on `local` for stats counter updates so the tile
  // re-renders the moment background.js bumps a counter (no need to wait
  // the 1.5s connection-refresh tick).
  if (areaName === 'local' && changes && typeof changes === 'object') {
    for (const key of Object.keys(changes)) {
      if (key.startsWith('aurora_stats_')) {
        try { refreshStats() } catch { /* noop */ }
        return
      }
    }
  }
  if (areaName !== 'session') return
  // Re-render only when a pagetype_<tabId> key is among the changes. We
  // don't filter on the active tab id here : refreshPagetype() re-queries
  // the active tab anyway, and another tab's pagetype change can't mutate
  // what we render. But we DO scope to pagetype_ keys so that unrelated
  // session writes (future features) don't ping us.
  if (!changes || typeof changes !== 'object') return
  for (const key of Object.keys(changes)) {
    if (key.startsWith('pagetype_')) {
      refreshPagetypeDebounced()
      return
    }
  }
}

// Wire the listener if the runtime exposes storage.onChanged. Older browsers
// fall back to the polling tick — same behaviour as before, just no live
// updates between ticks.
if (api?.storage?.onChanged?.addListener) {
  api.storage.onChanged.addListener(onSessionChange)
}

// Cleanup on popup close. window.unload fires when the popup closes ; we
// remove the SW-side listener so it doesn't accumulate across opens.
window.addEventListener('unload', () => {
  if (_pagetypeRefreshTimer) {
    clearTimeout(_pagetypeRefreshTimer)
    _pagetypeRefreshTimer = null
  }
  try {
    if (api?.storage?.onChanged?.removeListener) {
      api.storage.onChanged.removeListener(onSessionChange)
    }
  } catch { /* noop — popup unloading anyway */ }
})

refresh()
refreshPagetype()
refreshStats()
// Connection-status only — pageType badge now refreshes on storage events.
setInterval(() => { refresh() }, 1500)
