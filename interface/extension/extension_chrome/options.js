const api = (typeof browser !== 'undefined') ? browser : chrome
const els = {
  bridge: document.getElementById('bridge'),
  allowEval: document.getElementById('allow-eval'),
  allowScreenshot: document.getElementById('allow-screenshot'),
  autoSendSelection: document.getElementById('auto-send-selection'),
  diag: document.getElementById('diag'),
  refresh: document.getElementById('refresh'),
  save: document.getElementById('save'),
}

function load() {
  api.storage.local.get(
    ['bridgeUrl', 'allowEval', 'allowScreenshot', 'autoSendSelection', 'extensionId', 'status', 'statusAt'],
    (r) => {
      els.bridge.value = r.bridgeUrl || 'http://127.0.0.1:3001'
      els.allowEval.checked = !!r.allowEval
      els.allowScreenshot.checked = r.allowScreenshot !== false
      els.autoSendSelection.checked = r.autoSendSelection !== false
      els.diag.textContent = JSON.stringify(
        {
          extensionId: r.extensionId,
          status: r.status,
          lastSeen: r.statusAt ? new Date(r.statusAt).toLocaleString() : 'jamais',
          userAgent: navigator.userAgent,
          buildId: 'aurora-connect-1.0.0',
        },
        null,
        2,
      )
    },
  )
}

els.refresh.addEventListener('click', load)
els.save.addEventListener('click', () => {
  api.storage.local.set({
    bridgeUrl: els.bridge.value.trim(),
    allowEval: els.allowEval.checked,
    allowScreenshot: els.allowScreenshot.checked,
    autoSendSelection: els.autoSendSelection.checked,
  }, () => {
    els.save.textContent = 'Enregistre ✓'
    setTimeout(() => { els.save.textContent = 'Enregistrer' }, 1500)
  })
})

load()
