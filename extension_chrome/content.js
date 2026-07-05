// ---------------------------------------------------------------------------
// Aurora-Connect — content script
//
// Lightweight surface so the background SW can fall back to message passing
// when scripting.executeScript isn't available (e.g. for some store-installed
// extensions on Firefox). Most heavy lifting is done via executeScript from
// the background, but this script registers a listener for direct messages.
// ---------------------------------------------------------------------------

const api = (typeof browser !== 'undefined') ? browser : chrome

api.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (!msg || !msg.kind) return false
  try {
    switch (msg.kind) {
      case 'ping':
        sendResponse({ ok: true, url: location.href, title: document.title })
        return true
      case 'read_dom': {
        const nodes = Array.from(document.querySelectorAll(msg.selector || 'body')).slice(0, 50)
        sendResponse({ ok: true, data: nodes.map((n) => (n.textContent || '').trim()) })
        return true
      }
      case 'click': {
        const el = document.querySelector(msg.selector)
        if (!el) { sendResponse({ ok: false, error: 'not found' }); return true }
        el.click()
        sendResponse({ ok: true })
        return true
      }
      case 'fill': {
        const el = document.querySelector(msg.selector)
        if (!el) { sendResponse({ ok: false, error: 'not found' }); return true }
        const proto = Object.getPrototypeOf(el)
        const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set
        if (setter) setter.call(el, msg.value); else el.value = msg.value
        el.dispatchEvent(new Event('input', { bubbles: true }))
        el.dispatchEvent(new Event('change', { bubbles: true }))
        sendResponse({ ok: true })
        return true
      }
      default:
        sendResponse({ ok: false, error: `unknown: ${msg.kind}` })
        return true
    }
  } catch (e) {
    sendResponse({ ok: false, error: String(e) })
    return true
  }
})
