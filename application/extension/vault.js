/**
 * vault.js — Aurora-Connect credentials vault.
 *
 * v82jp Pass 1/10 — Phase 3 P3.1.
 *
 * Stockage : chrome.storage.local (jamais sync, jamais transmis bridge).
 * Chiffrement : AES-GCM 256-bit via window.crypto.subtle.
 * Passphrase maître : dérivée via PBKDF2 (200000 iter SHA-256, salt unique
 *   généré à install + persisté en clair, c'est OK car l'attaque hors-
 *   ligne contre PBKDF2 200k iter sur passphrase costaud reste impractical).
 *
 * Format storage :
 *   aurora_vault_v1: {
 *     salt: "base64",
 *     entries: {
 *       [siteKey]: {
 *         loginUrl: "https://...",
 *         iv: "base64",
 *         ciphertext: "base64",  // contains JSON {username, password}
 *         createdAt: 1746240000000,
 *         lastUsed: 1746240000000
 *       }
 *     }
 *   }
 *
 * API exposée (utilisée par popup-credentials.js + content-autologin.js
 * via chrome.runtime.sendMessage) :
 *   - vault.unlock(passphrase) → returns derived key (in-memory only)
 *   - vault.lock() → wipe in-memory key
 *   - vault.list() → siteKey[] (sans déchiffrer)
 *   - vault.add(siteKey, loginUrl, username, password) → encrypt + store
 *   - vault.get(siteKey) → { loginUrl, username, password } (déchiffré)
 *   - vault.remove(siteKey)
 *   - vault.isUnlocked() → bool
 */

const VAULT_KEY = 'aurora_vault_v1'

function bufToB64(buf) {
  const bytes = new Uint8Array(buf)
  let bin = ''
  for (const b of bytes) bin += String.fromCharCode(b)
  return btoa(bin)
}
function b64ToBuf(b64) {
  const bin = atob(b64)
  const bytes = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
  return bytes.buffer
}

let _cachedKey = null  // CryptoKey, in-memory only, wiped on lock or extension restart

async function _deriveKey(passphrase, saltBuf) {
  const enc = new TextEncoder()
  const baseKey = await crypto.subtle.importKey(
    'raw', enc.encode(passphrase), { name: 'PBKDF2' }, false, ['deriveKey'],
  )
  return await crypto.subtle.deriveKey(
    { name: 'PBKDF2', salt: saltBuf, iterations: 200000, hash: 'SHA-256' },
    baseKey,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt'],
  )
}

async function _readVault() {
  const result = await chrome.storage.local.get(VAULT_KEY)
  return result[VAULT_KEY] || null
}

async function _writeVault(vault) {
  await chrome.storage.local.set({ [VAULT_KEY]: vault })
}

async function _ensureSalt() {
  let vault = await _readVault()
  if (vault && vault.salt) return b64ToBuf(vault.salt)
  // Premier usage : génère salt
  const saltBuf = crypto.getRandomValues(new Uint8Array(16)).buffer
  vault = vault || { entries: {} }
  vault.salt = bufToB64(saltBuf)
  await _writeVault(vault)
  return saltBuf
}

const vault = {
  /** Unlock avec la passphrase. Si succès, key cached en mémoire pour
   *  les ops suivantes jusqu'à lock() ou extension restart. */
  async unlock(passphrase) {
    if (!passphrase || passphrase.length < 6) {
      throw new Error('Passphrase trop courte (6 chars minimum)')
    }
    const saltBuf = await _ensureSalt()
    _cachedKey = await _deriveKey(passphrase, saltBuf)
    return true
  },

  /** Wipe key from memory. */
  lock() {
    _cachedKey = null
    return true
  },

  isUnlocked() {
    return _cachedKey !== null
  },

  /** Liste des siteKeys sans déchiffrer. */
  async list() {
    const v = await _readVault()
    if (!v || !v.entries) return []
    return Object.keys(v.entries).map((k) => ({
      siteKey: k,
      loginUrl: v.entries[k].loginUrl,
      lastUsed: v.entries[k].lastUsed || 0,
    }))
  },

  /** Add ou update une entry. Nécessite unlock préalable. */
  async add(siteKey, loginUrl, username, password, meta = {}) {
    if (!_cachedKey) throw new Error('Vault locked. Unlock first.')
    if (!siteKey || !loginUrl) throw new Error('siteKey + loginUrl requis')
    const enc = new TextEncoder()
    const iv = crypto.getRandomValues(new Uint8Array(12))
    const plaintext = JSON.stringify({
      username: String(username || ''),
      password: String(password || ''),
      meta: meta && typeof meta === 'object' ? meta : {},
    })
    const ciphertext = await crypto.subtle.encrypt(
      { name: 'AES-GCM', iv },
      _cachedKey,
      enc.encode(plaintext),
    )
    let v = (await _readVault()) || { entries: {} }
    v.entries = v.entries || {}
    v.entries[siteKey] = {
      loginUrl,
      iv: bufToB64(iv),
      ciphertext: bufToB64(ciphertext),
      createdAt: v.entries[siteKey]?.createdAt || Date.now(),
      lastUsed: Date.now(),
    }
    await _writeVault(v)
    return true
  },

  /** Get + déchiffre une entry. Nécessite unlock. */
  async get(siteKey) {
    if (!_cachedKey) throw new Error('Vault locked. Unlock first.')
    const v = await _readVault()
    if (!v || !v.entries || !v.entries[siteKey]) return null
    const entry = v.entries[siteKey]
    try {
      const ivBuf = b64ToBuf(entry.iv)
      const ctBuf = b64ToBuf(entry.ciphertext)
      const decrypted = await crypto.subtle.decrypt(
        { name: 'AES-GCM', iv: ivBuf },
        _cachedKey,
        ctBuf,
      )
      const dec = new TextDecoder()
      const parsed = JSON.parse(dec.decode(decrypted))
      // Update lastUsed
      v.entries[siteKey].lastUsed = Date.now()
      await _writeVault(v)
      return {
        loginUrl: entry.loginUrl,
        username: parsed.username,
        password: parsed.password,
        meta: parsed.meta || {},
      }
    } catch (err) {
      // Decrypt fail = mauvaise passphrase
      throw new Error('Déchiffrement échoué — passphrase incorrecte ?')
    }
  },

  async remove(siteKey) {
    let v = await _readVault()
    if (!v || !v.entries || !v.entries[siteKey]) return false
    delete v.entries[siteKey]
    await _writeVault(v)
    return true
  },

  /** Wipe complet du vault (factory reset). */
  async wipeAll() {
    await chrome.storage.local.remove(VAULT_KEY)
    _cachedKey = null
    return true
  },
}

// Export pour service worker (background.js peut import via importScripts ou
// pour use direct si vault.js est inclus via manifest "background.scripts").
if (typeof self !== 'undefined') {
  self.auroraVault = vault
}
if (typeof window !== 'undefined') {
  window.auroraVault = vault
}
