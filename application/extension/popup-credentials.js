/**
 * popup-credentials.js — UI handlers pour le vault.
 * v82jq Pass 2/10 — Phase 3 P3.2.
 */
const $ = (id) => document.getElementById(id)

function show(id, txt, cls = 'ok') {
  const el = $(id)
  if (!el) return
  el.innerHTML = `<div class="status ${cls}">${txt}</div>`
  if (cls === 'ok') setTimeout(() => { if (el.firstChild) el.firstChild.remove() }, 3000)
}

async function refreshEntriesList() {
  if (!window.auroraVault.isUnlocked()) return
  const list = await window.auroraVault.list()
  const container = $('entries-list')
  const empty = $('entries-empty')
  container.innerHTML = ''
  if (list.length === 0) {
    empty.style.display = 'block'
    return
  }
  empty.style.display = 'none'
  for (const entry of list) {
    const div = document.createElement('div')
    div.className = 'entry'

    const label = document.createElement('span')
    label.className = 'label'
    label.textContent = entry.siteKey

    const url = document.createElement('span')
    url.className = 'url'
    url.textContent = entry.loginUrl
    url.title = entry.loginUrl

    const editBtn = document.createElement('button')
    editBtn.textContent = '✎'
    editBtn.title = 'Éditer'
    editBtn.onclick = async () => {
      try {
        const data = await window.auroraVault.get(entry.siteKey)
        if (!data) return
        $('add-key').value = entry.siteKey
        $('add-url').value = data.loginUrl
        $('add-username').value = data.username
        $('add-password').value = data.password
        $('cancel-edit-btn').style.display = 'inline'
        window.scrollTo(0, document.body.scrollHeight)
      } catch (err) {
        show('add-status', 'Échec lecture : ' + err.message, 'err')
      }
    }

    const delBtn = document.createElement('button')
    delBtn.className = 'danger'
    delBtn.textContent = '×'
    delBtn.title = 'Supprimer'
    delBtn.onclick = async () => {
      if (!confirm(`Supprimer "${entry.siteKey}" ?`)) return
      await window.auroraVault.remove(entry.siteKey)
      await refreshEntriesList()
    }

    div.appendChild(label)
    div.appendChild(url)
    div.appendChild(editBtn)
    div.appendChild(delBtn)
    container.appendChild(div)
  }
}

function clearAddForm() {
  $('add-key').value = ''
  $('add-url').value = ''
  $('add-username').value = ''
  $('add-password').value = ''
  $('cancel-edit-btn').style.display = 'none'
}

async function onUnlock() {
  const passphrase = $('passphrase').value
  if (!passphrase) {
    show('unlock-status', 'Passphrase requise', 'warn')
    return
  }
  try {
    await window.auroraVault.unlock(passphrase)
    $('passphrase').value = ''
    $('locked-view').style.display = 'none'
    $('unlocked-view').style.display = 'block'
    await refreshEntriesList()
  } catch (err) {
    show('unlock-status', 'Échec : ' + err.message, 'err')
  }
}

async function onAdd() {
  const key = $('add-key').value.trim()
  const url = $('add-url').value.trim()
  const username = $('add-username').value
  const password = $('add-password').value
  if (!key || !url) {
    show('add-status', 'Nom + URL requis', 'warn')
    return
  }
  if (!url.startsWith('http')) {
    show('add-status', 'URL doit commencer par http(s)', 'warn')
    return
  }
  try {
    await window.auroraVault.add(key, url, username, password)
    show('add-status', '✓ Sauvegardé', 'ok')
    clearAddForm()
    await refreshEntriesList()
  } catch (err) {
    show('add-status', 'Échec : ' + err.message, 'err')
  }
}

function onLock() {
  window.auroraVault.lock()
  $('unlocked-view').style.display = 'none'
  $('locked-view').style.display = 'block'
  show('unlock-status', '🔒 Verrouillé', 'ok')
}

async function onWipe() {
  if (!confirm('Effacer DÉFINITIVEMENT toutes les credentials ENT ? Action irréversible.')) return
  if (!confirm('Vraiment ? Tu devras tout re-saisir.')) return
  await window.auroraVault.wipeAll()
  $('unlocked-view').style.display = 'none'
  $('locked-view').style.display = 'block'
  show('unlock-status', '🗑 Vault effacé', 'ok')
}

document.addEventListener('DOMContentLoaded', () => {
  $('unlock-btn').addEventListener('click', onUnlock)
  $('passphrase').addEventListener('keydown', (e) => { if (e.key === 'Enter') onUnlock() })
  $('add-btn').addEventListener('click', onAdd)
  $('cancel-edit-btn').addEventListener('click', clearAddForm)
  $('lock-btn').addEventListener('click', onLock)
  $('wipe-btn').addEventListener('click', onWipe)
})
