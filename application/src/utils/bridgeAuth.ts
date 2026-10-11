import { getBridgeUrl } from './runtime.ts'

const KEY = 'aurora.workspace.key'
let pendingLogin: Promise<string> | null = null
export function readBridgeKey(): string {
  try { return sessionStorage.getItem(KEY) || '' } catch { return '' }
}
export function saveBridgeKey(key: string): void {
  try { if (key.trim()) sessionStorage.setItem(KEY, key.trim()); else sessionStorage.removeItem(KEY) } catch { /* memory-only browsers */ }
}
function isBridgeRequest(input: RequestInfo | URL): boolean {
  if (typeof window === 'undefined') return false
  try {
    const url = new URL(input instanceof Request ? input.url : String(input), window.location.href)
    const bridge = new URL(getBridgeUrl() || '/', window.location.href)
    return url.origin === bridge.origin && (url.pathname.startsWith('/api/') || url.pathname.startsWith('/proxy/'))
  } catch { return false }
}
function askForKey(): Promise<string> {
  if (pendingLogin) return pendingLogin
  pendingLogin = new Promise<string>((resolve, reject) => {
    const dialog = document.createElement('dialog')
    dialog.setAttribute('aria-label', 'Connexion Aurora')
    dialog.style.cssText = 'width:min(440px,calc(100% - 24px));border:1px solid #647297;border-radius:20px;background:#141b2f;color:#e6eaf5;padding:22px;font:16px system-ui'
    const form = document.createElement('form')
    const title = document.createElement('h2'); title.textContent = 'Connecter ce téléphone à Aurora'
    const help = document.createElement('p'); help.textContent = 'Entrez votre clé Aurora pour lancer et suivre les traitements sur le PC. Elle sera réutilisée dans cet onglet.'
    const label = document.createElement('label'); label.textContent = 'Clé d’accès Aurora'
    const input = document.createElement('input'); input.type = 'password'; input.autocomplete = 'off'; input.required = true; input.setAttribute('aria-label', 'Clé d’accès Aurora'); input.style.cssText = 'width:100%;min-height:48px;font:16px system-ui;background:#080d19;color:inherit;border:1px solid #647297;border-radius:12px;padding:12px'
    const error = document.createElement('p'); error.setAttribute('role', 'status')
    const submit = document.createElement('button'); submit.type = 'submit'; submit.textContent = 'Connecter et continuer'; submit.style.cssText = 'width:100%;min-height:48px;font:inherit;background:#8b5cf6;color:white;border:0;border-radius:12px'
    const cancel = document.createElement('button'); cancel.type = 'button'; cancel.textContent = 'Annuler'; cancel.style.cssText = 'width:100%;min-height:44px;font:inherit;background:transparent;color:inherit;border:0;margin-top:8px'
    const dismiss = () => { dialog.remove(); reject(new Error('Connexion annulée. Aucun traitement supplémentaire lancé.')) }
    cancel.onclick = dismiss
    form.append(title, help, label, input, error, submit, cancel); dialog.append(form); document.body.append(dialog)
    dialog.addEventListener('cancel', event => { event.preventDefault(); dismiss() })
    form.onsubmit = async event => {
      event.preventDefault(); submit.disabled = true
      try {
        const key = input.value.trim()
        const response = await globalThis.fetch(`${getBridgeUrl()}/api/python/progress?since=0`, { headers: { Authorization: `Bearer ${key}` }, cache: 'no-store' })
        if (!response.ok || !(response.headers.get('content-type') || '').includes('application/json')) { error.textContent = 'Clé refusée ou connexion indisponible. Vérifiez votre clé Aurora.'; return }
        saveBridgeKey(key); dialog.remove(); resolve(key)
      } catch { error.textContent = 'Connexion au PC interrompue. Réessayez.' } finally { submit.disabled = false }
    }
    dialog.showModal(); input.focus()
  }).finally(() => { pendingLogin = null })
  return pendingLogin
}
/** Authorize only this bridge. Retry once only after an explicit guard rejection,
 * never after a timeout or a possibly accepted mutation. */
export async function bridgeFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  if (!isBridgeRequest(input)) return globalThis.fetch(input, init)
  const request = input instanceof Request ? new Request(input, init) : new Request(new URL(String(input), window.location.href), init)
  const retry = request.clone()
  const key = readBridgeKey()
  if (key && !request.headers.has('Authorization')) request.headers.set('Authorization', `Bearer ${key}`)
  const response = await globalThis.fetch(request)
  if (response.status !== 403) return response
  const data = await response.clone().json().catch(() => null) as { error?: string } | null
  if (data?.error !== 'forbidden_public') return response
  const newKey = await askForKey()
  retry.headers.set('Authorization', `Bearer ${newKey}`)
  return globalThis.fetch(retry)
}
