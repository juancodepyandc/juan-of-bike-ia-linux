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

refresh()
setInterval(refresh, 1500)
