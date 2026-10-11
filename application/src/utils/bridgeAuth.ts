import { getBridgeUrl } from './runtime.ts'

const KEY = 'aurora.workspace.key'
let pendingLogin: Promise<void> | null = null
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
function askForConnection(): Promise<void> {
  if (pendingLogin) return pendingLogin
  pendingLogin = new Promise<void>((resolve,reject) => {
    const dialog=document.createElement('dialog')
    dialog.setAttribute('aria-label','Connexion Aurora')
    dialog.style.cssText='width:min(480px,calc(100% - 24px));padding:0;border:1px solid #647297;border-radius:20px;background:#080d19;color:#e6eaf5'
    const frame=document.createElement('iframe')
    const url=new URL(`${getBridgeUrl()}/connect`,window.location.href)
    frame.src=url.href;frame.title='Connecter mon appareil';frame.style.cssText='width:100%;height:min(620px,80dvh);border:0'
    const close=()=>{window.removeEventListener('message',message);dialog.remove()}
    const message=(event:MessageEvent)=>{if(event.origin!==url.origin||event.source!==frame.contentWindow||event.data?.type!=='aurora-device-connected')return;saveBridgeKey('');close();resolve()}
    window.addEventListener('message',message)
    const cancel=document.createElement('button');cancel.textContent='Annuler';cancel.style.cssText='min-height:44px;width:100%;font:16px system-ui;color:inherit;background:transparent;border:0'
    const dismiss=()=>{close();reject(new Error('Connexion annulée. Aucun nouveau traitement lancé.'))}
    cancel.onclick=dismiss;dialog.addEventListener('cancel',e=>{e.preventDefault();dismiss()})
    dialog.append(frame,cancel);document.body.append(dialog);dialog.showModal()
  }).finally(()=>{pendingLogin=null})
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
  await askForConnection()
  retry.headers.delete('Authorization')
  return globalThis.fetch(retry)
}
