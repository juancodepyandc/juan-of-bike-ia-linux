export type RuntimeMode = 'browser' | 'tauri' | 'cloud'

declare global {
  interface Window {
    __TAURI_INTERNALS__?: unknown
    __TAURI__?: unknown
  }
}

// Hostnames hosted by tunnel-as-a-service providers. When the page is loaded
// from one of these domains, we know we're running inside a remote tunnel and
// must use relative API paths so the Vite proxy forwards to bridge:3001 on
// the user's PC. Matched as a *suffix* on window.location.hostname so any
// subdomain (e.g. juan-aurora-ia.loca.lt) is detected.
const TUNNEL_HOSTNAME_SUFFIXES: readonly string[] = [
  'trycloudflare.com',     // Cloudflare Quick Tunnel + Named Tunnel
  'loca.lt',               // localtunnel (free, stable subdomains)
  'ngrok-free.app',        // ngrok free tier
  'ngrok.app',             // ngrok paid
  'ngrok.io',              // ngrok legacy
  'serveo.net',            // serveo (SSH tunnel)
  'localhost.run',         // localhost.run
  'lhr.life',              // localhost.run alt domain
  'pinggy.link',           // pinggy
  'a.free.pinggy.link',    // pinggy free tier
  'bore.pub',              // bore
]

export function hostnameLooksLikeTunnel(hostname: string): boolean {
  const lower = hostname.toLowerCase()
  return TUNNEL_HOSTNAME_SUFFIXES.some((suffix) => lower === suffix || lower.endsWith('.' + suffix))
}

export function getRuntimeMode(): RuntimeMode {
  if (typeof window === 'undefined') {
    return 'browser'
  }

  if (window.__TAURI_INTERNALS__ || window.__TAURI__) {
    return 'tauri'
  }

  if (import.meta.env?.VITE_CLOUD_MODE === 'true') {
    return 'cloud'
  }

  return 'browser'
}

export function isTauriRuntime() {
  return getRuntimeMode() === 'tauri'
}

export function isCloudRuntime() {
  if (typeof window === 'undefined') return false;

  return (
    hostnameLooksLikeTunnel(window.location.hostname) ||
    import.meta.env?.VITE_CLOUD_MODE === 'true' ||
    getRuntimeMode() === 'cloud'
  );
}

export function isDesktopRuntime() {
  return isTauriRuntime()
}

export function getCloudBridgeUrl(): string {
  return import.meta.env?.VITE_BRIDGE_URL || ''
}

/**
 * URL de base du bridge pour les appels API depuis le navigateur/téléphone.
 * - Tauri : '' (IPC direct, pas besoin de bridge)
 * - Cloud/Tunnel : '' (URLs relatives, Vite proxy redirige vers bridge:3001)
 * - Browser local : 'http://127.0.0.1:3001' (accès direct au bridge)
 */
export function getBridgeUrl(): string {
  // 31/07: en Tauri on renvoyait '' — toute URL construite avec getBridgeUrl()
  // ('' + '/api/...') partait en RELATIF depuis tauri://localhost et mourait
  // en silence: bouton « Isoler le sujet » inerte, viewer noir, recuperation
  // tunnel impossible. Le bridge est un serveur HTTP local: on parle en
  // absolu. Seul le mode cloud garde le relatif (proxy Vite -> 3001).
  if (isCloudRuntime()) return ''
  return import.meta.env?.VITE_BRIDGE_URL || 'http://127.0.0.1:3001'
}

export function getRuntimeLabel() {
  const runtime = getRuntimeMode();

  if (runtime === 'cloud' || (typeof window !== 'undefined' && hostnameLooksLikeTunnel(window.location.hostname))) {
    return 'Cloud (Tunnel)';
  }

  if (runtime === 'tauri') {
    return 'Tauri natif';
  }

  return 'Navigateur';
}

export function getRuntimeHint() {
  const runtime = getRuntimeMode()

  if (runtime === 'tauri') {
    return 'Le shell Tauri a acces au systeme local et aux workflows lourds.'
  }

  if (runtime === 'cloud') {
    return 'Mode cloud : GPU distant, tous les modules actifs via le Cloud Bridge.'
  }

  return 'Mode visuel web, utile pour l interface et les tests rapides.'
}

export function toBrowserFileUrl(inputPath: string) {
  if (!inputPath) {
    return inputPath
  }

  if (/^(https?:|data:|blob:|file:)/i.test(inputPath)) {
    return inputPath
  }

  const normalized = inputPath.replace(/\\/g, '/')
  if (/^[A-Za-z]:/.test(normalized)) {
    return encodeURI(`file:///${normalized}`)
  }

  return encodeURI(normalized)
}
