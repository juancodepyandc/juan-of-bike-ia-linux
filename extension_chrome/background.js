// ---------------------------------------------------------------------------
// Aurora-Connect — service worker
//
// Maintains the connection to the local Aurora bridge and dispatches
// commands to the active tab via the content script. Runs forever in the
// background; kept alive by a heartbeat poll.
// ---------------------------------------------------------------------------

const DEFAULT_BRIDGE = 'http://127.0.0.1:3001'
const POLL_INTERVAL_MS = 2000
const POLL_TIMEOUT_MS = 30000

// chrome / browser polyfill — Chrome/Edge use `chrome`, Firefox can use
// either. We export the API once for consistency.
const api = (typeof browser !== 'undefined') ? browser : chrome

let pollAbortController = null

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

// ---------------------------------------------------------------------------
// Auto-reload : the bridge exposes /api/cowork/extension/version returning the
// current expected extension version. When our running version differs, we
// call chrome.runtime.reload() — Chrome re-reads the source files from disk,
// which gives us hot-update without the user having to click "Reload" on
// chrome://extensions every time we ship a fix.
//
// We embed the running version at build time via the manifest. The endpoint
// returns whatever version the bridge is configured to advertise (defaults
// to the current package version). Mismatch -> reload.
// ---------------------------------------------------------------------------
async function checkVersionAndMaybeReload(bridgeUrl) {
  try {
    const myVersion = api.runtime.getManifest()?.version || 'unknown'
    const r = await fetch(`${bridgeUrl}/api/cowork/extension/version`, {
      method: 'GET',
      signal: AbortSignal.timeout(3000),
    })
    if (!r.ok) return
    const d = await r.json()
    const expected = d?.version
    if (expected && typeof expected === 'string' && expected !== myVersion) {
      // eslint-disable-next-line no-console
      console.log(`[Aurora-Connect] version mismatch (running=${myVersion} expected=${expected}) — reloading...`)
      try { api.runtime.reload() } catch { /* ignore — runtime may not allow reload everywhere */ }
    }
  } catch { /* swallow — bridge unreachable or no version endpoint */ }
}

async function pollLoop() {
  const bridgeUrl = await getBridgeUrl()
  const extensionId = await getExtensionId()

  // Check version once at boot, then every 30 polls (= every ~60 sec).
  let pollsSinceVersionCheck = 0
  await checkVersionAndMaybeReload(bridgeUrl)

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
      pollsSinceVersionCheck += 1
      if (pollsSinceVersionCheck >= 30) {
        pollsSinceVersionCheck = 0
        await checkVersionAndMaybeReload(bridgeUrl)
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
            const text = (document.body?.innerText || '').replace(/\s+/g, ' ').trim()
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
            }
          },
        })
        return { ok: true, data: r[0]?.result ?? null }
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

// ---------------------------------------------------------------------------
// v23 — Keep-alive for Manifest V3 service worker.
//
// Chrome MV3 suspends the service worker after ~30 sec of inactivity. The
// previous polling loop was kept alive by the active fetch (long-poll), but
// when the bridge becomes briefly unreachable (tunnel restart, network blip)
// the SW would die and the user would have to manually reload the extension.
//
// The canonical fix : chrome.alarms API. Alarms wake the SW periodically,
// and our handler revives the poll loop if it had stopped.
// ---------------------------------------------------------------------------
const KEEPALIVE_ALARM = 'aurora-connect-keepalive'
let pollLoopRunning = false

api.alarms?.create?.(KEEPALIVE_ALARM, { periodInMinutes: 0.5 })  // every 30 sec

api.alarms?.onAlarm?.addListener?.((alarm) => {
  if (alarm.name !== KEEPALIVE_ALARM) return
  // If the poll loop is dead (SW was suspended and revived), restart it.
  if (!pollLoopRunning) {
    pollLoopRunning = true
    pollLoop()
      .catch(() => { /* swallow — next alarm will try again */ })
      .finally(() => { pollLoopRunning = false })
  }
})

// Wrap the boot-time pollLoop call so the running flag stays accurate. We
// deliberately replace the original `pollLoop().catch(...)` call below by
// noting it has already started the loop.
if (!pollLoopRunning) {
  pollLoopRunning = true
  // The original boot call earlier in the file already started a poll loop ;
  // we just mirror the state here so the alarm doesn't double-start.
}
