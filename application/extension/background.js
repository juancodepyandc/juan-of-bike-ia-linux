// ---------------------------------------------------------------------------
// Aurora-Connect — service worker
//
// Maintains the connection to the local Aurora bridge and dispatches
// commands to the active tab via the content script. Runs forever in the
// background; kept alive by a heartbeat poll.
// ---------------------------------------------------------------------------

const DEFAULT_BRIDGE = 'http://127.0.0.1:3001'
const POLL_INTERVAL_MS = 2000
// MV3 Chrome service workers can be killed after ~30s of idle. We cap the
// long-poll wait at 25s so the await resolves and a new fetch starts before
// Chrome considers the SW idle. The chrome.alarms keep-alive below provides
// the secondary heartbeat in case the long-poll itself is delayed (slow
// network, tunnel hiccup).
const POLL_TIMEOUT_MS = 25000

// chrome / browser polyfill — Chrome/Edge use `chrome`, Firefox can use
// either. We export the API once for consistency.
const api = (typeof browser !== 'undefined') ? browser : chrome

let pollAbortController = null

// v77zah: MV3 service worker keep-alive. Chrome aggressively suspends
// service workers after ~30s of inactivity, which kills the pollLoop and
// makes the extension look "deconnectee" even when the bridge is healthy.
// chrome.alarms running every 25s wakes the SW back up if it was
// suspended; the listener doesn't need to do anything — being invoked is
// enough to refresh the SW lifetime budget.
try {
  api.alarms.create('aurora-keep-alive', { periodInMinutes: 0.4 })  // 24s
  api.alarms.onAlarm.addListener((alarm) => {
    if (alarm.name === 'aurora-keep-alive') {
      // No-op; the wake itself is the heartbeat. We tickle the bridge URL
      // resolution so any stored config change propagates without a manual
      // reload, and to make sure the SW has done SOMETHING that browsers
      // count as activity.
      void getBridgeUrl()
    }
  })
} catch { /* alarms permission missing — pre-v77zah manifest */ }

async function getBridgeUrl() {
  return new Promise((resolve) => {
    api.storage.local.get(['bridgeUrl'], (r) => {
      resolve(r.bridgeUrl || DEFAULT_BRIDGE)
    })
  })
}

async function getExtensionId() {
  return new Promise((resolve) => {
    api.storage.local.get(['extensionId'], (r) => {
      if (r.extensionId) return resolve(r.extensionId)
      const id = `ext-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
      api.storage.local.set({ extensionId: id }, () => resolve(id))
    })
  })
}

async function setStatus(status) {
  api.storage.local.set({ status, statusAt: Date.now() })
  try {
    api.action.setBadgeText({ text: status === 'connected' ? '●' : '' })
    api.action.setBadgeBackgroundColor({ color: status === 'connected' ? '#10b981' : '#ef4444' })
  } catch { /* old browsers may not support this */ }
}

// v82lx — pageType→badge mapping. Topological pageType detected by
// analyze_page is surfaced to the user via the action icon : a single-letter
// abbreviation flashes over the connection-status dot for 3s then clears, so
// the user sees at a glance that the extension understood what's on screen
// (login form, article, listing, social feed, dashboard, media, form).
//
// Order matters : `social_feed` is more specific than `listing`, `login` is
// more specific than `form`, `media` is more specific than `dashboard`. The
// first true entry wins, so list highest-specificity first.
//
// Exported for unit testing — the mapping is pure (no DOM, no Chrome API).
function pageTypeToBadge(pageType) {
  if (!pageType || typeof pageType !== 'object') return null
  if (pageType.login) return { text: 'L', color: '#ef4444' }       // red
  if (pageType.social_feed) return { text: 'F', color: '#8b5cf6' } // violet
  if (pageType.article) return { text: 'A', color: '#0ea5e9' }     // sky
  if (pageType.media) return { text: 'M', color: '#f97316' }       // orange
  if (pageType.listing) return { text: 'T', color: '#10b981' }     // emerald
  if (pageType.dashboard) return { text: 'D', color: '#a855f7' }   // purple
  if (pageType.form) return { text: 'O', color: '#eab308' }        // amber (fOrm)
  return null
}
// Expose for unit tests (no-op when not in test env — the function
// stays usable from the SW directly).
try { self.__auroraPageTypeToBadge = pageTypeToBadge } catch { /* noop */ }

// Per-tab pageType badge timer. Map<tabId, timerId>. Cleared and
// rescheduled on every analyze_page call so back-to-back analyses don't
// stack timers.
const _pageTypeBadgeTimers = new Map()

function flashPageTypeBadge(tabId, pageType) {
  if (typeof tabId !== 'number') return
  const b = pageTypeToBadge(pageType)
  if (!b) return
  try {
    api.action.setBadgeText({ tabId, text: b.text })
    api.action.setBadgeBackgroundColor({ tabId, color: b.color })
  } catch { /* old browsers may not support tabId-scoped badge */ }
  // Clear after 3s to avoid polluting the icon permanently. The
  // tab-scoped clear restores the global connection-status badge.
  const prev = _pageTypeBadgeTimers.get(tabId)
  if (prev) clearTimeout(prev)
  const t = setTimeout(() => {
    try { api.action.setBadgeText({ tabId, text: '' }) } catch { /* noop */ }
    _pageTypeBadgeTimers.delete(tabId)
  }, 3000)
  _pageTypeBadgeTimers.set(tabId, t)
}

// v82n0 — daily activity stats. Rolling daily counter persisted in
// chrome.storage.local under key `aurora_stats_<YYYY-MM-DD>`. Today's
// counters back the popup "Today's activity" tile. Old days are pruned on
// every increment (no separate alarm needed) so the local store never
// accumulates indefinitely.
//
// Public schema :
//   { pages: number, scrapes: number, pins: number, escalations: number,
//     date: 'YYYY-MM-DD', updatedAt: number }
//
// Counters incremented :
//   pages       → each analyze_page call (background.js)
//   scrapes     → each scrape-page call
//   pins        → connector pin event (forwarded by AuditDrawer via
//                 chrome.storage.local.set { aurora_event:'pin' })
//   escalations → dual-signal/trend escalation (mirror)
//
// pins/escalations are best-effort — they bump a counter when the host page
// (overlay React app) sends an event message. The orchestrator already emits
// these to the bridge ; the popup tile is supplementary.
function _statsTodayKey() {
  const d = new Date()
  const yyyy = d.getFullYear()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return 'aurora_stats_' + yyyy + '-' + mm + '-' + dd
}

function bumpStatsCounter(field) {
  try {
    const key = _statsTodayKey()
    api.storage.local.get([key], (r) => {
      const cur = (r && r[key]) || { pages: 0, scrapes: 0, pins: 0, escalations: 0 }
      cur[field] = (Number(cur[field]) || 0) + 1
      cur.date = key.replace('aurora_stats_', '')
      cur.updatedAt = Date.now()
      const upd = {}
      upd[key] = cur
      api.storage.local.set(upd)
    })
  } catch { /* noop */ }
  // Best-effort cleanup of stale day entries (>= 8 days old).
  cleanupStaleStats()
}

function cleanupStaleStats() {
  try {
    api.storage.local.get(null, (all) => {
      if (!all) return
      const today = _statsTodayKey()
      const todayDate = today.replace('aurora_stats_', '')
      const todayMs = Date.parse(todayDate + 'T00:00:00')
      if (!Number.isFinite(todayMs)) return
      const stale = []
      for (const k of Object.keys(all)) {
        if (!k.startsWith('aurora_stats_')) continue
        if (k === today) continue
        const dateStr = k.replace('aurora_stats_', '')
        const ms = Date.parse(dateStr + 'T00:00:00')
        if (!Number.isFinite(ms)) { stale.push(k); continue }
        // Older than 7 days → drop. Yesterday is kept for parity scenarios.
        if (todayMs - ms > 7 * 24 * 3600 * 1000) stale.push(k)
      }
      if (stale.length > 0) api.storage.local.remove(stale)
    })
  } catch { /* noop */ }
}

// Listen for events from the overlay React app (popup-credentials, AuditDrawer,
// orchestrator) so the popup tile reflects pin/escalation activity even when
// triggered outside the SW.
try {
  api.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg && msg.type === 'aurora-stats-bump' && typeof msg.field === 'string') {
      const allowed = ['pages', 'scrapes', 'pins', 'escalations']
      if (allowed.indexOf(msg.field) !== -1) bumpStatsCounter(msg.field)
      try { sendResponse({ ok: true }) } catch { /* noop */ }
      return false
    }
    return undefined
  })
} catch { /* noop */ }
// Expose internal helpers for unit tests.
try {
  self.__auroraStatsTodayKey = _statsTodayKey
  self.__auroraBumpStatsCounter = bumpStatsCounter
  self.__auroraCleanupStaleStats = cleanupStaleStats
} catch { /* noop */ }

async function pollLoop() {
  const bridgeUrl = await getBridgeUrl()
  const extensionId = await getExtensionId()

  while (true) {
    try {
      pollAbortController = new AbortController()
      const timer = setTimeout(() => pollAbortController.abort(), POLL_TIMEOUT_MS)
      const resp = await fetch(`${bridgeUrl}/api/cowork/extension/poll?extId=${encodeURIComponent(extensionId)}&wait=${POLL_TIMEOUT_MS}`, {
        method: 'GET',
        signal: pollAbortController.signal,
      })
      clearTimeout(timer)
      if (!resp.ok) {
        await setStatus('disconnected')
        await sleep(POLL_INTERVAL_MS * 4)
        continue
      }
      const data = await resp.json()
      await setStatus('connected')
      if (data && data.command) {
        const result = await dispatchCommand(data.command)
        await postResult(bridgeUrl, extensionId, data.command.id, result)
      }
    } catch (err) {
      await setStatus('disconnected')
      await sleep(POLL_INTERVAL_MS * 2)
    }
  }
}

async function dispatchCommand(cmd) {
  // cmd = { id, kind, payload }
  // Supported kinds:
  //   - get_active_tab: returns { url, title }
  //   - read_dom: payload.selector -> textContent of matches
  //   - click: payload.selector
  //   - fill: payload.selector, payload.value
  //   - eval: payload.script (DANGER)
  //   - screenshot: capture visible tab as PNG dataURL
  try {
    const tabs = await new Promise((resolve) => api.tabs.query({ active: true, currentWindow: true }, resolve))
    const tab = tabs[0]
    if (!tab) return { ok: false, error: 'no active tab' }

    switch (cmd.kind) {
      case 'get_active_tab':
        return { ok: true, data: { url: tab.url, title: tab.title, id: tab.id } }

      case 'read_dom': {
        const r = await api.scripting.executeScript({
          target: { tabId: tab.id },
          func: (selector) => {
            const nodes = Array.from(document.querySelectorAll(selector)).slice(0, 50)
            return nodes.map((n) => (n.textContent || '').trim())
          },
          args: [cmd.payload?.selector || 'body'],
        })
        return { ok: true, data: r[0]?.result ?? [] }
      }

      case 'read_html': {
        const r = await api.scripting.executeScript({
          target: { tabId: tab.id },
          func: (selector) => {
            const el = document.querySelector(selector)
            return el ? el.outerHTML.slice(0, 50000) : null
          },
          args: [cmd.payload?.selector || 'body'],
        })
        return { ok: true, data: r[0]?.result ?? null }
      }

      case 'click': {
        const r = await api.scripting.executeScript({
          target: { tabId: tab.id },
          func: (selector) => {
            const el = document.querySelector(selector)
            if (!el) return { ok: false, error: 'not found' }
            el.click()
            return { ok: true }
          },
          args: [cmd.payload?.selector],
        })
        return r[0]?.result ?? { ok: false, error: 'no result' }
      }

      case 'fill': {
        const r = await api.scripting.executeScript({
          target: { tabId: tab.id },
          func: (selector, value) => {
            const el = document.querySelector(selector)
            if (!el) return { ok: false, error: 'not found' }
            const proto = Object.getPrototypeOf(el)
            const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set
            if (setter) setter.call(el, value); else el.value = value
            el.dispatchEvent(new Event('input', { bubbles: true }))
            el.dispatchEvent(new Event('change', { bubbles: true }))
            return { ok: true }
          },
          args: [cmd.payload?.selector, cmd.payload?.value ?? ''],
        })
        return r[0]?.result ?? { ok: false, error: 'no result' }
      }

      case 'eval': {
        // POWER FEATURE: arbitrary JS in active tab. The user opted into
        // this via the extension popup permission toggle. Bridge must have
        // also approved this command.
        const enabled = await new Promise((resolve) => api.storage.local.get(['allowEval'], (r) => resolve(r.allowEval)))
        if (!enabled) return { ok: false, error: 'eval disabled in popup' }
        const r = await api.scripting.executeScript({
          target: { tabId: tab.id },
          world: 'MAIN',
          func: (script) => {
            try {
              const fn = new Function(`return (async () => { ${script} })()`)
              return Promise.resolve(fn()).then((v) => ({ ok: true, value: v })).catch((e) => ({ ok: false, error: String(e) }))
            } catch (e) {
              return { ok: false, error: String(e) }
            }
          },
          args: [cmd.payload?.script || ''],
        })
        return r[0]?.result ?? { ok: false, error: 'no result' }
      }

      case 'screenshot': {
        const dataUrl = await new Promise((resolve, reject) => {
          api.tabs.captureVisibleTab(undefined, { format: 'png' }, (d) => {
            if (api.runtime.lastError) reject(new Error(api.runtime.lastError.message))
            else resolve(d)
          })
        })
        return { ok: true, data: { dataUrl, length: dataUrl.length } }
      }

      case 'navigate': {
        await api.tabs.update(tab.id, { url: cmd.payload?.url })
        return { ok: true }
      }

      case 'list_tabs': {
        const all = await new Promise((resolve) => api.tabs.query({}, resolve))
        return { ok: true, data: all.map((t) => ({ id: t.id, url: t.url, title: t.title, active: t.active })) }
      }

      case 'analyze_page': {
        // Rich one-shot analysis : title, meta, headings, paragraphs, images,
        // links, tables, og: tags, charset, lang, full text snippet (4000c).
        //
        // v82l5 — page typology heuristics (purely topological, no class names
        // hardcoded) + same-origin iframe sweep. The planner uses `pageType`
        // to pick a comprehension strategy ; selectors stay generic.
        const r = await api.scripting.executeScript({
          target: { tabId: tab.id },
          func: () => {
            const headings = []
            for (const sel of ['h1', 'h2', 'h3', 'h4']) {
              for (const el of Array.from(document.querySelectorAll(sel)).slice(0, 30)) {
                headings.push({ tag: sel, text: (el.textContent || '').trim().slice(0, 200) })
              }
            }
            const paragraphs = Array.from(document.querySelectorAll('main p, article p, [role=main] p, section p, body p'))
              .slice(0, 80)
              .map((p) => (p.textContent || '').trim())
              .filter((t) => t.length > 20)
              .slice(0, 50)
            const links = Array.from(document.querySelectorAll('a[href]')).slice(0, 40).map((a) => ({
              text: (a.textContent || '').trim().slice(0, 100),
              href: a.href,
            }))
            const images = Array.from(document.querySelectorAll('img[src]')).slice(0, 20).map((i) => ({
              src: i.src,
              alt: i.alt || '',
              w: i.naturalWidth || i.width || 0,
              h: i.naturalHeight || i.height || 0,
            }))
            const meta = {}
            for (const m of document.querySelectorAll('meta[name], meta[property]')) {
              const k = m.getAttribute('name') || m.getAttribute('property')
              const v = m.getAttribute('content')
              if (k && v) meta[k] = v.slice(0, 300)
            }
            const tableSummaries = Array.from(document.querySelectorAll('table')).slice(0, 5).map((t) => ({
              rows: t.rows.length,
              cols: t.rows[0]?.cells.length || 0,
              firstRow: Array.from(t.rows[0]?.cells || []).map((c) => (c.textContent || '').trim().slice(0, 80)),
            }))
            const lang = document.documentElement.lang || 'unknown'
            let text = (document.body?.innerText || '').replace(/\s+/g, ' ').trim()

            // v82l5 — same-origin iframe sweep. ENT/SPA pages (Pronote,
            // EcoleDirecte, dashboards bancaires) hide their data inside
            // iframes ; body.innerText misses it. Cross-origin iframes raise
            // a SecurityError on contentDocument access — silently skipped.
            const iframeTexts = []
            try {
              for (const f of Array.from(document.querySelectorAll('iframe')).slice(0, 6)) {
                try {
                  const doc = f.contentDocument || f.contentWindow?.document
                  if (!doc?.body) continue
                  const inner = (doc.body.innerText || '').replace(/\s+/g, ' ').trim()
                  if (inner.length > 100) {
                    iframeTexts.push({
                      name: f.name || f.id || (f.src && f.src.slice(0, 120)) || '(unnamed)',
                      length: inner.length,
                      snippet: inner.slice(0, 1500),
                    })
                  }
                } catch { /* cross-origin */ }
              }
            } catch { /* noop */ }

            // Page typology — purely topological. Lets the LLM planner pick
            // the right next action without site-specific knowledge.
            const passwordInputs = document.querySelectorAll('input[type=password]').length
            const formCount = document.querySelectorAll('form').length
            const articleTag = !!document.querySelector('article')
            const videoCount = document.querySelectorAll('video').length
            const canvasCount = document.querySelectorAll('canvas').length
            // Repeated-structure detection : direct children of body/main/section
            // grouped by tagName ; >=5 siblings of same tag = listing-like.
            const containers = Array.from(document.querySelectorAll('main, section, [role=main], body'))
            let listLike = 0
            for (const c of containers.slice(0, 8)) {
              const counts = {}
              for (const child of Array.from(c.children)) {
                counts[child.tagName] = (counts[child.tagName] || 0) + 1
              }
              for (const k of Object.keys(counts)) {
                if (counts[k] >= 5) { listLike = Math.max(listLike, counts[k]) }
              }
            }
            // v82lx — social_feed signals (avatars, relative timestamps,
            // reaction buttons). All topological — no site-specific selectors.
            // See content-scrape.js detectSocialFeedSignals() for the full
            // signal taxonomy ; this is the inlined twin so executeScript
            // can run it inside the page world without import.
            let avatarHits = 0
            try {
              const imgs = Array.from(document.querySelectorAll('img[src]')).slice(0, 100)
              for (const im of imgs) {
                const w = im.naturalWidth || im.width || 0
                const h = im.naturalHeight || im.height || 0
                const square = w > 0 && h > 0 && Math.abs(w - h) <= 8 && w <= 96
                if (!square) continue
                let p = im.parentElement
                for (let d = 0; d < 4 && p; d++, p = p.parentElement) {
                  const tag = p.tagName
                  const role = (p.getAttribute && p.getAttribute('role')) || ''
                  if (tag === 'A' || role === 'link' || tag === 'HEADER') {
                    avatarHits++
                    break
                  }
                }
              }
            } catch { /* noop */ }
            const tsRe = /(?:il y a\s+\d+|\d+\s*(?:min|mn|h|j|d|w|m|s|sec|hr|hrs|hour|hours|day|days|week|weeks|month|months)\b\s*(?:ago|hier)?|vor\s+\d+\s*(?:min|std|tag|tagen)|hace\s+\d+\s*(?:min|h|d[ií]a)|yesterday|hier|aujourd['’ ]?hui|today|just now|à l['’ ]instant)/i
            const hasTimestamps = tsRe.test(text.slice(0, 6000))
            let reactionButtons = 0
            try {
              const buttons = Array.from(document.querySelectorAll('button[aria-label], [role=button][aria-label]')).slice(0, 200)
              const reactRe = /aim|ike|react|pplaud|recommend|partage|share|comment|comentar|kommentar/i
              for (const b of buttons) {
                const lbl = b.getAttribute('aria-label') || ''
                if (lbl && reactRe.test(lbl)) reactionButtons++
              }
            } catch { /* noop */ }
            const repeatingCards = listLike >= 5
            const socialFeedScore = (repeatingCards ? 1 : 0) + (avatarHits >= 2 ? 1 : 0)
              + (hasTimestamps ? 1 : 0) + (reactionButtons >= 2 ? 1 : 0)

            // v82n0 — article quality (rich/thin/paywall/unknown). Pure
            // topology, mirror of detectArticleQuality in content-scrape.js.
            // KEEP IN SYNC.
            let articleQuality = 'unknown'
            try {
              if (articleTag) {
                const longParagraphs = Array.from(document.querySelectorAll('article p, main p, [role=main] p, body p'))
                  .filter((p) => (p.textContent || '').trim().length > 100)
                  .length
                const hasHeading = !!document.querySelector('article h1, article h2, main h1, main h2, h1, h2')
                const authStems = /abonn|subscri|premium|log\s*in|sign\s*in|register|inscri|connect|anmeld|suscri|registr/i
                let paywall = false
                try {
                  const viewH = window.innerHeight || document.documentElement?.clientHeight || 0
                  if (viewH > 0) {
                    const candidates = Array.from(document.querySelectorAll('[role=dialog], aside, dialog, div, section')).slice(0, 250)
                    for (const el of candidates) {
                      try {
                        const rect = el.getBoundingClientRect ? el.getBoundingClientRect() : null
                        if (!rect) continue
                        const coverage = rect.height / viewH
                        if (coverage < 0.6) continue
                        const inner = (el.innerText || '').trim()
                        if (inner.length === 0 || inner.length > 2000) continue
                        if (authStems.test(inner)) { paywall = true; break }
                      } catch { /* noop */ }
                    }
                  }
                } catch { /* noop */ }
                if (paywall && text.length < 3000) articleQuality = 'paywall'
                else if (text.length >= 1500 && longParagraphs >= 2 && hasHeading) articleQuality = 'rich'
                else if (text.length < 800) articleQuality = 'thin'
                else articleQuality = 'unknown'
              }
            } catch { /* noop */ }

            // v82n0 — listing subtype (search_results / product_listing /
            // news_listing / generic). Pure topology, mirror of
            // detectListingSubtype in content-scrape.js. KEEP IN SYNC.
            let listingSubtype = 'generic'
            try {
              if (listLike >= 5) {
                let bestParent = null
                let bestTag = null
                let bestCount = 0
                for (const c of containers.slice(0, 8)) {
                  const counts = {}
                  for (const ch of Array.from(c.children)) {
                    counts[ch.tagName] = (counts[ch.tagName] || 0) + 1
                  }
                  for (const k of Object.keys(counts)) {
                    if (counts[k] >= 5 && counts[k] > bestCount) {
                      bestParent = c; bestTag = k; bestCount = counts[k]
                    }
                  }
                }
                if (bestParent && bestTag) {
                  const items = Array.from(bestParent.children).filter((ch) => ch.tagName === bestTag).slice(0, 30)
                  const priceRe = /[€$£¥₹₽]\s*\d|\d[\d.,]*\s*(?:€|\$|£|¥|EUR|USD|GBP|JPY)/i
                  const tsRe2 = /\b\d+\s*(?:min|h|j|d|hour|hours|day|days|week|month|year|ago|hier)\b|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|janv|fevr|mars|avr|mai|juin|juil|aout|sept|oct|nov|dec)[a-zé]*\.?\s+\d|\d{4}-\d{2}-\d{2}/i
                  const authorRe = /\b(?:by|par|von|de|@)\s+[A-Z][a-zA-ZÀ-ÿ\-]+/
                  let priceCount = 0, tsCount = 0, authorCount = 0, searchTriadCount = 0
                  for (const it of items) {
                    const txt = (it.innerText || '')
                    if (priceRe.test(txt)) priceCount++
                    if (tsRe2.test(txt)) tsCount++
                    if (authorRe.test(txt)) authorCount++
                    try {
                      const heading = it.querySelector('h1,h2,h3,h4,[role=heading]')
                      const link = it.querySelector('a[href]')
                      const headingText = heading ? (heading.textContent || '').trim().length : 0
                      const totalText = txt.trim().length
                      const hasSnippet = totalText > headingText + 80
                      if (heading && link && hasSnippet) searchTriadCount++
                    } catch { /* noop */ }
                  }
                  if (priceCount >= 3) listingSubtype = 'product_listing'
                  else if (tsCount >= 3 && authorCount >= 2) listingSubtype = 'news_listing'
                  else if (listLike >= 8 && searchTriadCount >= Math.min(items.length, 6)) listingSubtype = 'search_results'
                  else listingSubtype = 'generic'
                }
              }
            } catch { /* noop */ }

            const pageType = {
              login: passwordInputs >= 1 && formCount >= 1,
              article: articleTag && text.length > 800,
              listing: listLike >= 5 || tableSummaries.some((t) => t.rows >= 5),
              media: videoCount >= 1 || canvasCount >= 1,
              form: formCount >= 1 && passwordInputs === 0,
              dashboard: text.length < 600 && images.length >= 3,
              social_feed: socialFeedScore >= 3,
              article_quality: articleQuality,
            }
            const signals = {
              passwordInputs, formCount, articleTag, videoCount, canvasCount,
              listLikeCount: listLike,
              tableCount: tableSummaries.length,
              iframeCount: iframeTexts.length,
              avatarHits, hasTimestamps, reactionButtons,
              socialFeedScore,
              repeatingCardCount: listLike,
              articleQuality,
              listingSubtype,
            }

            return {
              url: location.href,
              title: document.title,
              lang,
              charset: document.characterSet,
              meta,
              headings,
              paragraphs,
              links,
              images,
              tables: tableSummaries,
              textSnippet: text.slice(0, 4000),
              textLength: text.length,
              iframeTexts,
              pageType,
              signals,
            }
          },
        })
        const data = r[0]?.result ?? null
        // v82lx — flash a 3s pageType badge on the action icon. Pure UX :
        // user sees what the extension just understood. Cleared per-tab so
        // it doesn't override the global connection-status indicator.
        try { flashPageTypeBadge(tab.id, data?.pageType) } catch { /* noop */ }
        // v82n0 — daily stats : count this page analysis.
        try { bumpStatsCounter('pages') } catch { /* noop */ }
        // v82ly — persist pageType+signals in chrome.storage.session keyed
        // by tabId so the popup can render the same badge in parity with
        // the toolbar icon. session storage clears on browser restart, which
        // is exactly the right semantics (a cached pageType from a previous
        // browse session would mislead the popup).
        try {
          if (typeof tab.id === 'number' && data?.pageType) {
            const key = 'pagetype_' + tab.id
            const payload = {
              pageType: data.pageType,
              signals: data.signals || {},
              ts: Date.now(),
              url: data.url || tab.url || '',
            }
            api.storage.session?.set?.({ [key]: payload })
          }
        } catch { /* noop — session storage may be unavailable on older Chrome */ }
        return { ok: true, data }
      }

      // v82l3 : enregistrement direct creds Pronote depuis SettingsPanel.
      case 'vault-add': {
        const siteKey = cmd.payload?.siteKey
        const entry = cmd.payload?.entry
        if (!siteKey || !entry?.loginUrl || !entry?.username || !entry?.password) {
          return { ok: false, error: 'siteKey + entry{loginUrl,username,password} requis' }
        }
        try { importScripts('vault.js') } catch (e) { /* déjà chargé */ }
        if (!self.auroraVault) return { ok: false, error: 'vault module load failed' }
        if (!self.auroraVault.isUnlocked()) {
          return {
            ok: false,
            error: 'Vault verrouillé. Ouvre l\'icône Aurora-Connect → Credentials → déverrouille d\'abord.',
          }
        }
        try {
          await self.auroraVault.add(siteKey, entry.loginUrl, entry.username, entry.password, {
            label: entry.label,
            schoolName: entry.schoolName,
            city: entry.city,
            candidateUrls: entry.candidateUrls,
          })
          return { ok: true, siteKey }
        } catch (e) {
          return { ok: false, error: String(e) }
        }
      }

      // v82jv Phase 3 Pass 7 — credential auto-login + scrape adaptatif.
      case 'autologin': {
        // Lookup creds dans le vault (déjà déchiffré en mémoire si user
        // a unlock le vault via popup).
        const siteKey = cmd.payload?.siteKey
        if (!siteKey) return { ok: false, error: 'siteKey requis' }
        // Charge vault.js dans le SW si pas encore.
        try { importScripts('vault.js') } catch (e) { /* déjà chargé */ }
        if (!self.auroraVault || !self.auroraVault.isUnlocked()) {
          return { ok: false, reason: 'vault_locked', message: 'Vault verrouillé. Déverrouille via le popup d\'abord.' }
        }
        let creds
        try { creds = await self.auroraVault.get(siteKey) }
        catch (e) { return { ok: false, reason: 'vault_error', message: String(e) } }
        if (!creds) return { ok: false, reason: 'no_entry', message: `Aucune entrée pour "${siteKey}"` }
        const waitTabComplete = async (timeout = 8000) => {
          await new Promise((res) => {
            const listener = (tabId, changeInfo) => {
              if (tabId === tab.id && changeInfo.status === 'complete') {
                api.tabs.onUpdated.removeListener(listener)
                res(null)
              }
            }
            api.tabs.onUpdated.addListener(listener)
            setTimeout(() => { api.tabs.onUpdated.removeListener(listener); res(null) }, timeout)
          })
        }
        const injectAutologin = async () => {
          try {
            await api.scripting.executeScript({
              target: { tabId: tab.id, allFrames: true },
              files: ['content-autologin.js'],
            })
          } catch { /* probably already injected */ }
        }
        const pickFrameResult = (results) => {
          const values = Array.isArray(results)
            ? results.map((r) => r?.result).filter(Boolean)
            : []
          const ok = values.find((v) => v && v.ok)
          if (ok) return ok
          return values.find((v) => v?.reason === 'captcha' || v?.reason === 'mfa')
            || values.find((v) => v?.reason && v.reason !== 'not_injected')
            || values[0]
            || null
        }
        const fillCurrentPage = async () => {
          await injectAutologin()
          try {
            const results = await api.scripting.executeScript({
              target: { tabId: tab.id, allFrames: true },
              func: (frameCreds) => {
                if (!window.__auroraAutoLoginFill) {
                  return { ok: false, reason: 'not_injected', message: 'Auto-login script absent dans ce frame', url: location.href }
                }
                return window.__auroraAutoLoginFill(frameCreds)
              },
              args: [{ username: creds.username, password: creds.password }],
            })
            const picked = pickFrameResult(results)
            if (picked) return picked
          } catch { /* fallback to message path below */ }
          return await new Promise((res) => {
            api.tabs.sendMessage(tab.id, {
              type: 'aurora-autologin-fill',
              creds: { username: creds.username, password: creds.password },
            }, res)
          })
        }
        const findLoginLink = async () => {
          await injectAutologin()
          try {
            const results = await api.scripting.executeScript({
              target: { tabId: tab.id, allFrames: true },
              func: () => {
                if (!window.__auroraFindLoginLink) return { ok: false, url: location.href }
                return window.__auroraFindLoginLink()
              },
            })
            const candidates = (Array.isArray(results) ? results : [])
              .map((r) => r?.result)
              .filter((r) => r?.candidate?.url)
              .sort((a, b) => (b.candidate.score || 0) - (a.candidate.score || 0))
            if (candidates[0]) return candidates[0]
          } catch { /* fallback to message path below */ }
          return await new Promise((res) => {
            api.tabs.sendMessage(tab.id, { type: 'aurora-autologin-find-login-link' }, res)
          })
        }
        const navigateTo = async (url, timeout = 8000) => {
          await new Promise((res) => api.tabs.update(tab.id, { url }, res))
          await waitTabComplete(timeout)
          await sleep(1200)
        }

        if (tab.url !== creds.loginUrl) {
          await navigateTo(creds.loginUrl)
        }
        let r = await fillCurrentPage()
        if (r && r.ok) return r
        if (r && ['no_password_field', 'no_username_field'].includes(r.reason)) {
          const found = await findLoginLink()
          const candidateUrl = found?.candidate?.url
          if (candidateUrl && candidateUrl !== tab.url && candidateUrl !== creds.loginUrl) {
            await navigateTo(candidateUrl, 10000)
            const r2 = await fillCurrentPage()
            if (r2 && r2.ok) return { ...r2, discoveredLoginUrl: candidateUrl }
            return r2 || r || { ok: false, reason: 'no_response', message: 'Content script silent after discovered login navigation' }
          }
        }
        return r || { ok: false, reason: 'no_response', message: 'Content script silent' }
      }

      case 'verify-auth': {
        const authMarkers = cmd.payload?.authMarkers || []
        try {
          await api.scripting.executeScript({
            target: { tabId: tab.id, allFrames: true },
            files: ['content-scrape.js'],
          })
        } catch { /* already injected */ }
        try {
          const results = await api.scripting.executeScript({
            target: { tabId: tab.id, allFrames: true },
            func: (markers) => {
              if (!window.__auroraVerifyAuth) return { ok: false, score: 0, hint: 'verify script absent', url: location.href }
              return window.__auroraVerifyAuth(markers)
            },
            args: [authMarkers],
          })
          const values = (Array.isArray(results) ? results : []).map((r) => r?.result).filter(Boolean)
          const best = values.sort((a, b) => (b.score || 0) - (a.score || 0))[0]
          if (best) return best
        } catch { /* fallback to message path below */ }
        const r = await new Promise((res) => {
          api.tabs.sendMessage(tab.id, {
            type: 'aurora-verify-auth',
            authMarkers,
          }, res)
        })
        return r || { ok: false, score: 0, hint: 'no response from content-scrape' }
      }

      case 'scrape-page': {
        // v82l0 Pronote fix : si payload.sectionPath est fourni, naviguer
        // d'abord vers la section avant de scraper. Pronote (et les autres
        // ENT en SPA) chargent leurs données dynamiquement par hash route
        // — sans navigation préalable, on scrape juste la home page.
        // Le path est résolu relatif à l'origin du tab courant.
        const sectionPath = cmd.payload?.sectionPath
        let sectionUrl = null
        if (sectionPath && tab.url) {
          try {
            sectionUrl = sectionPath.startsWith('http')
              ? sectionPath
              : new URL(sectionPath, tab.url).toString()
          } catch { /* malformed */ }
        }
        if (sectionUrl && sectionUrl !== tab.url) {
          await new Promise((res) => api.tabs.update(tab.id, { url: sectionUrl }, res))
          // Wait DOM ready (max 10s — Pronote can be slow).
          await new Promise((res) => {
            const listener = (tabId, changeInfo) => {
              if (tabId === tab.id && changeInfo.status === 'complete') {
                api.tabs.onUpdated.removeListener(listener)
                res(null)
              }
            }
            api.tabs.onUpdated.addListener(listener)
            setTimeout(() => { api.tabs.onUpdated.removeListener(listener); res(null) }, 10000)
          })
          // Hash routes (Pronote `#page=Notes`) ne déclenchent pas 'complete'.
          // Settle JS lazy-load supplémentaire (Pronote charge les notes via
          // XHR asynchrones après hashchange).
          await sleep(2500)
        }
        try {
          await api.scripting.executeScript({
            target: { tabId: tab.id, allFrames: true },
            files: ['content-scrape.js'],
          })
        } catch { /* already injected */ }
        const runScrapeInFrames = async () => {
          try {
            const results = await api.scripting.executeScript({
              target: { tabId: tab.id, allFrames: true },
              func: () => {
                if (!window.__auroraScrapePage) return { ok: false, error: 'scrape script absent', frameUrl: location.href }
                return window.__auroraScrapePage()
              },
            })
            const values = (Array.isArray(results) ? results : []).map((x) => x?.result).filter((x) => x?.ok && x.snapshot)
            if (values.length > 0) {
              const best = values.sort((a, b) => ((b.snapshot?.text || '').length) - ((a.snapshot?.text || '').length))[0]
              const seen = new Set()
              const attachments = []
              for (const v of values) {
                for (const a of Array.isArray(v.attachments) ? v.attachments : []) {
                  if (!a?.url || seen.has(a.url)) continue
                  seen.add(a.url)
                  attachments.push(a)
                }
              }
              return {
                ...best,
                attachments,
                frames: values.map((v) => ({
                  url: v.frameUrl || v.snapshot?.url || '',
                  title: v.frameTitle || v.snapshot?.title || '',
                  textLength: (v.snapshot?.text || '').length,
                  attachments: Array.isArray(v.attachments) ? v.attachments.length : 0,
                })),
              }
            }
          } catch { /* fallback to message path below */ }
          return await new Promise((res) => {
            api.tabs.sendMessage(tab.id, {
              type: 'aurora-scrape-page',
              section: cmd.payload?.section,
            }, res)
          })
        }
        const r = await runScrapeInFrames()
        // v82n0 — daily stats : count the scrape attempt (counted once per
        // dispatched scrape-page, regardless of retry below).
        try { bumpStatsCounter('scrapes') } catch { /* noop */ }
        // v82l5 — smart retry. Pronote / SPA ENT lazy-load via XHR after
        // hashchange ; first scrape can be near-empty if we beat the load.
        // If text is poor AND iframes were present, give the page another
        // 4s to settle and re-scrape once. Generic, no site-specific check.
        // v82l6 : reuse signals.iframeCount when content-scrape exposes it
        // (more reliable than scanning container selectors), keep the
        // selector-based fallback for older snapshots.
        if (r && r.ok && r.snapshot) {
          const text = r.snapshot.text || ''
          const sig = r.snapshot.signals
          const hasIframes = (sig && sig.iframeCount > 0)
            || (r.snapshot.containers || []).some((c) =>
              typeof c.selector === 'string' && c.selector.startsWith('iframe '))
          if (text.length < 500 && hasIframes) {
            await sleep(4000)
            const r2 = await runScrapeInFrames()
            if (r2 && r2.ok && r2.snapshot && (r2.snapshot.text || '').length > text.length) {
              r2.retry = { reason: 'low-text-with-iframes', initialLength: text.length }
              return r2
            }
          }
        }
        return r || { ok: false, error: 'no response from content-scrape' }
      }

      case 'extract_structured': {
        // v82l6 — comprehension-based extraction. The user (or planner) describes
        // in natural language what they want extracted ; the bridge calls Ollama
        // with a system prompt that forces JSON output adapted to the intent.
        // Zero hardcoded selectors, zero fixed schema — the LLM picks the right
        // shape from the intent.
        //
        // Payload :
        //   intent       : string (required, eg 'liste des cours du jour')
        //   includeImage : bool (optional, default false — captures viewport
        //                  for vision models like qwen3-vl)
        //   model        : string (optional, override default)
        //
        // The page text is sourced via the same path as scrape-page : we run
        // content-scrape and forward the snapshot.text. We don t re-implement
        // text extraction here — the smart-retry & iframe sweep logic lives
        // in scrape-page already.
        const intent = (cmd.payload?.intent || '').trim()
        if (!intent) return { ok: false, error: 'intent requis' }
        try {
          await api.scripting.executeScript({
            target: { tabId: tab.id, allFrames: true },
            files: ['content-scrape.js'],
          })
        } catch { /* already injected */ }
        let scrape = null
        try {
          const results = await api.scripting.executeScript({
            target: { tabId: tab.id, allFrames: true },
            func: () => {
              if (!window.__auroraScrapePage) return { ok: false, error: 'scrape script absent', frameUrl: location.href }
              return window.__auroraScrapePage()
            },
          })
          const values = (Array.isArray(results) ? results : []).map((x) => x?.result).filter((x) => x?.ok && x.snapshot)
          if (values.length > 0) {
            const best = values.sort((a, b) => ((b.snapshot?.text || '').length) - ((a.snapshot?.text || '').length))[0]
            const seen = new Set()
            const attachments = []
            for (const v of values) {
              for (const a of Array.isArray(v.attachments) ? v.attachments : []) {
                if (!a?.url || seen.has(a.url)) continue
                seen.add(a.url)
                attachments.push(a)
              }
            }
            scrape = { ...best, attachments }
          }
        } catch { /* fallback to message path below */ }
        if (!scrape) {
          scrape = await new Promise((res) => {
            api.tabs.sendMessage(tab.id, {
              type: 'aurora-scrape-page',
              section: cmd.payload?.section,
            }, res)
          })
        }
        if (!scrape || !scrape.ok) {
          return { ok: false, error: 'scrape pre-extract failed: ' + (scrape?.error || 'no response') }
        }
        const attachments = Array.isArray(scrape.attachments) ? scrape.attachments.slice(0, 80) : []
        const attachmentBlock = attachments.length > 0
          ? '\n\n=== PIECES JOINTES / DOCUMENTS DETECTES ===\n' + attachments.map((a, i) => {
              const label = a.text || a.filename || a.download || `document ${i + 1}`
              return `- [D${i + 1}] ${label} -> ${a.url}`
            }).join('\n')
          : ''
        const blob = `${scrape.snapshot?.text || ''}${attachmentBlock}`
        let imageDataUrl = ''
        if (cmd.payload?.includeImage) {
          try {
            imageDataUrl = await new Promise((res, rej) => {
              api.tabs.captureVisibleTab(undefined, { format: 'png' }, (d) => {
                if (api.runtime.lastError) rej(new Error(api.runtime.lastError.message))
                else res(d)
              })
            })
          } catch { /* vision optional, not fatal */ }
        }
        const bridgeUrlNow = await getBridgeUrl()
        // v82ly — forward mode + card_signals + cards[] when present. The
        // planner can pass mode=card_iteration with topological hints ; the
        // content-scrape sidecar populates snapshot.cards[] when the page is
        // a social feed. Both pieces are independent — the bridge handles
        // any combination (mode without cards = LLM uses blob ; cards
        // without mode = bridge ignores them gracefully).
        const cards = Array.isArray(scrape.snapshot?.cards) && scrape.snapshot.cards.length > 0
          ? scrape.snapshot.cards
          : undefined
        const body = {
          intent,
          html_or_text: blob,
          imageDataUrl: imageDataUrl || undefined,
          model: cmd.payload?.model || undefined,
          mode: cmd.payload?.mode || undefined,
          card_signals: cmd.payload?.card_signals || undefined,
          cards,
          // v82m1 — forward the active tab's URL so the bridge can record
          // the host in the extraction-stats ring buffer (per-host yield
          // aggregation). Best-effort : tab.url may be empty on some
          // restricted pages ; bridge falls back to "" host gracefully.
          url: tab?.url || undefined,
        }
        const resp = await fetch(`${bridgeUrlNow}/api/cowork/extract-structured`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        })
        const data = await resp.json().catch(() => ({ ok: false, error: 'invalid json from bridge' }))
        if (!resp.ok || !data.ok) {
          return { ok: false, error: data.error || `bridge ${resp.status}`, data }
        }
        // v82m3 — forward the bridge's per-host yield delta header so the
        // orchestrator can flip `under_extraction:true` on baseline drift
        // without round-tripping /api/cowork/extraction-stats. Best-effort :
        // a CORS-stripped header (older browsers) just leaves the field
        // absent — the orchestrator no-ops gracefully in that case.
        const forwardedHeaders = {}
        try {
          const dpct = resp.headers.get('X-Host-Yield-Delta-Pct')
          if (dpct !== null) forwardedHeaders['X-Host-Yield-Delta-Pct'] = dpct
          const cards = resp.headers.get('X-Cards-Processed')
          if (cards !== null) forwardedHeaders['X-Cards-Processed'] = cards
          const items = resp.headers.get('X-Items-Extracted')
          if (items !== null) forwardedHeaders['X-Items-Extracted'] = items
        } catch { /* header read must never break the result */ }
        return {
          ok: true,
          data: {
            intent,
            items: data.items || [],
            schema: data.schema || '',
            notes: data.notes || '',
            model: data.model,
            inputLength: blob.length,
            hadVision: Boolean(imageDataUrl),
            attachments,
            // v82m3 — bridge response headers (delta, cards, items).
            // Pure passthrough ; orchestrator consumes
            // X-Host-Yield-Delta-Pct via annotateHostBaselineDrift.
            headers: forwardedHeaders,
            // Mirror cards_processed onto data so the existing
            // annotateUnderExtraction yield-ratio gate stays correct
            // (it reads result.data.cards_processed). The header is the
            // same number — no extra source of truth.
            cards_processed: forwardedHeaders['X-Cards-Processed']
              ? Number.parseInt(forwardedHeaders['X-Cards-Processed'], 10)
              : undefined,
          },
        }
      }

      default:
        return { ok: false, error: `unknown kind: ${cmd.kind}` }
    }
  } catch (err) {
    return { ok: false, error: String(err) }
  }
}

async function postResult(bridgeUrl, extensionId, commandId, result) {
  try {
    await fetch(`${bridgeUrl}/api/cowork/extension/result`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ extId: extensionId, commandId, result }),
    })
  } catch { /* ignore — next poll will reconnect */ }
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms))
}

// Boot
pollLoop().catch(() => {
  setStatus('disconnected')
})

// Restart poll loop on bridge URL change
api.storage.onChanged.addListener((changes) => {
  if (changes.bridgeUrl) {
    if (pollAbortController) pollAbortController.abort()
  }
})

// Context menu: "Send selection to Aurora"
api.runtime.onInstalled.addListener(() => {
  try {
    api.contextMenus.create({
      id: 'aurora-send-selection',
      title: 'Envoyer la selection a Aurora',
      contexts: ['selection'],
    })
  } catch { /* old browsers */ }
})

api.contextMenus?.onClicked?.addListener?.(async (info) => {
  if (info.menuItemId === 'aurora-send-selection' && info.selectionText) {
    const bridgeUrl = await getBridgeUrl()
    const extensionId = await getExtensionId()
    try {
      await fetch(`${bridgeUrl}/api/cowork/extension/inbound`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ extId: extensionId, kind: 'selection', text: info.selectionText }),
      })
      api.notifications?.create?.({
        type: 'basic',
        iconUrl: 'icons/icon-48.png',
        title: 'Aurora-Connect',
        message: 'Selection envoyee a Aurora.',
      })
    } catch { /* noop */ }
  }
})
