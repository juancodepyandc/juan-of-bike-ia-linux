/**
 * Fills ENT login forms when the user has saved credentials in Aurora-Connect.
 *
 * The script stays idle until the service worker calls it. It can run in the
 * main page or in login iframes, detects CAPTCHA/MFA prompts, fills the native
 * input values, and submits the nearest login form.
 */
(function () {
  'use strict'

  // The script stays idle until the service worker calls it.
  if (!chrome.runtime || !chrome.runtime.onMessage) return

  function isVisible(el) {
    if (!el) return false
    const r = el.getBoundingClientRect()
    if (r.width < 1 || r.height < 1) return false
    const style = getComputedStyle(el)
    return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0'
  }

  function detectCaptcha() {
    const sel = [
      'iframe[src*="hcaptcha"]',
      'iframe[src*="recaptcha"]',
      'iframe[src*="turnstile"]',
      '.h-captcha', '.g-recaptcha', '.cf-turnstile',
      'input[name*="captcha" i]',
    ]
    for (const s of sel) {
      try { if (document.querySelector(s)) return true } catch { /* noop */ }
    }
    return false
  }

  function detectMfa() {
    // Text cues commonly shown on MFA or one-time-code screens.
    const text = (document.body?.innerText || '').toLowerCase().slice(0, 5000)
    return /code\s+(?:sms|reçu|envoyé|email)|double[\s-]facteur|mfa|2fa|otp|à 6 chiffres/i.test(text)
  }

  function findUsernameField(passwordField) {
    // 1. Input juste avant le password dans le tab order.
    const allInputs = Array.from(document.querySelectorAll('input')).filter(isVisible)
    const pwIdx = allInputs.indexOf(passwordField)
    if (pwIdx > 0) {
      for (let i = pwIdx - 1; i >= 0; i--) {
        const el = allInputs[i]
        const type = (el.type || '').toLowerCase()
        if (['email', 'text', 'tel', 'username'].includes(type) || !el.type) {
          return el
        }
      }
    }
    // 2. Fallback : matching name/id avec patterns courants
    const sel = 'input[type="email"], input[type="text"], input[name*="user" i], input[name*="login" i], input[name*="email" i], input[name*="identifiant" i], input[id*="user" i], input[id*="login" i], input[id*="email" i]'
    const candidates = Array.from(document.querySelectorAll(sel)).filter(isVisible)
    return candidates[0] || null
  }

  function findPasswordField() {
    const all = Array.from(document.querySelectorAll('input[type="password"]')).filter(isVisible)
    return all[0] || null
  }

  function setNativeValue(el, value) {
    // Bypass React controlled-component blockers en utilisant le setter natif.
    const proto = Object.getPrototypeOf(el)
    const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set
    if (setter) setter.call(el, value)
    else el.value = value
    el.dispatchEvent(new Event('input', { bubbles: true }))
    el.dispatchEvent(new Event('change', { bubbles: true }))
  }

  function findSubmitButton(passwordField) {
    // 1. Parent form, then its submit button.
    const form = passwordField.form
    if (form) {
      const submit = form.querySelector('button[type="submit"], input[type="submit"]')
      if (submit && isVisible(submit)) return submit
    }
    // 2. Button proche avec text matching login.
    const all = Array.from(document.querySelectorAll('button, input[type="submit"]')).filter(isVisible)
    const re = /(connexion|connect|login|se connecter|valider|continuer|sign in|s'identifier)/i
    for (const btn of all) {
      const txt = (btn.textContent || btn.value || '').trim()
      if (re.test(txt)) return btn
    }
    // 3. Premier submit visible.
    return all.find((b) => (b.type || '').toLowerCase() === 'submit') || null
  }

  function scoreLoginHref(a) {
    const href = a.href || ''
    if (!href || !/^https?:/i.test(href)) return null
    const text = `${a.textContent || ''} ${a.getAttribute('aria-label') || ''} ${a.getAttribute('title') || ''} ${href}`.toLowerCase()
    let score = 0
    if (/pronote\/(?:eleve|parent|mobile|professeur)\.html/i.test(href)) score += 100
    if (/\/pronote\/?$/i.test(href)) score += 60
    if (/connexion|connect|login|auth|sso|cas|scolarite|ent|élève|eleve|parent|pronote/i.test(text)) score += 30
    if (/logout|deconnexion|déconnexion|aide|help|contact/i.test(text)) score -= 40
    try {
      const u = new URL(href)
      if (u.hostname === location.hostname) score += 10
      if (u.hostname.includes('index-education.')) score += 25
    } catch { /* noop */ }
    return score > 0 ? { url: href, score, text: (a.textContent || '').trim().slice(0, 120) } : null
  }

  function findLoginLink() {
    const candidates = []
    const scanDoc = (doc) => {
      for (const a of Array.from(doc.querySelectorAll('a[href], area[href]')).slice(0, 300)) {
        const scored = scoreLoginHref(a)
        if (scored) candidates.push(scored)
      }
    }
    scanDoc(document)
    try {
      for (const f of Array.from(document.querySelectorAll('iframe')).slice(0, 10)) {
        try {
          const doc = f.contentDocument || f.contentWindow?.document
          if (doc?.body) scanDoc(doc)
        } catch { /* cross-origin */ }
      }
    } catch { /* noop */ }
    const seen = new Set()
    return candidates
      .filter((c) => {
        if (seen.has(c.url)) return false
        seen.add(c.url)
        return true
      })
      .sort((a, b) => b.score - a.score)[0] || null
  }

  async function performAutoLogin({ username, password }) {
    if (detectCaptcha()) {
      return { ok: false, reason: 'captcha', message: 'CAPTCHA detecte - a completer manuellement' }
    }
    if (detectMfa()) {
      return { ok: false, reason: 'mfa', message: 'Double-facteur detecte - code a entrer manuellement' }
    }
    const pwField = findPasswordField()
    if (!pwField) {
      return { ok: false, reason: 'no_password_field', message: 'Champ password introuvable' }
    }
    const userField = findUsernameField(pwField)
    if (!userField) {
      return { ok: false, reason: 'no_username_field', message: 'Champ identifiant introuvable' }
    }
    setNativeValue(userField, username)
    setNativeValue(pwField, password)
    // Let React/Vue/Angular sync their controlled input state.
    await new Promise((r) => setTimeout(r, 300))
    const submit = findSubmitButton(pwField)
    if (!submit) {
      return { ok: false, reason: 'no_submit_button', message: 'Bouton submit introuvable' }
    }
    submit.click()
    return { ok: true, message: 'Auto-login soumis' }
  }

  window.__auroraAutoLoginFill = performAutoLogin
  window.__auroraAutoLoginDetect = () => {
    const pw = findPasswordField()
    const user = pw ? findUsernameField(pw) : null
    return {
      ok: true,
      hasPasswordField: !!pw,
      hasUsernameField: !!user,
      captcha: detectCaptcha(),
      mfa: detectMfa(),
      url: location.href,
      title: document.title,
    }
  }
  window.__auroraFindLoginLink = () => ({
    ok: true,
    candidate: findLoginLink(),
    url: location.href,
    title: document.title,
  })

  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg && msg.type === 'aurora-autologin-fill' && msg.creds) {
      performAutoLogin(msg.creds).then(sendResponse).catch((err) => {
        sendResponse({ ok: false, reason: 'exception', message: String(err) })
      })
      return true  // async response
    }
    if (msg && msg.type === 'aurora-autologin-detect') {
      sendResponse(window.__auroraAutoLoginDetect())
      return false
    }
    if (msg && msg.type === 'aurora-autologin-find-login-link') {
      sendResponse(window.__auroraFindLoginLink())
      return false
    }
  })
})()

