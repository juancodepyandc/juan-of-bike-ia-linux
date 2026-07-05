import { useEffect, useState } from 'react'

export type DeviceKind = 'mobile' | 'tablet' | 'desktop'

export type DeviceInfo = {
  kind: DeviceKind
  width: number
  height: number
  touch: boolean
  coarsePointer: boolean
  dpr: number
  platform: string
  ua: string
  uaMobileHint: boolean | null
}

function readUAData(): { mobile: boolean | null; platform: string | null } {
  const uad = (navigator as Navigator & {
    userAgentData?: { mobile?: boolean; platform?: string }
  }).userAgentData
  return {
    mobile: typeof uad?.mobile === 'boolean' ? uad.mobile : null,
    platform: uad?.platform ?? null,
  }
}

/**
 * Detects mobile / tablet / desktop even inside a browser (works in Tauri webview too).
 * Strategy (in order):
 *   1. UA-Client-Hints `Sec-CH-UA-Mobile` / `platform` — the most trustworthy modern signal.
 *   2. UA regex against the classic mobile tokens.
 *   3. iPadOS 13+ edge case: `navigator.platform === "MacIntel"` + touch.
 *   4. Heuristic fallback: coarse pointer + narrow viewport.
 * A stray desktop-UA browser with a tiny window stays "desktop" — this matches intent,
 * because the user can actually drive it with a keyboard / mouse.
 */
export interface InstallState {
  platform: 'ios' | 'android' | 'other'
  /** Is the app running inside a PWA shell (standalone)? */
  standalone: boolean
  /** Does this browser expose the Notification API at all? */
  supportsNotification: boolean
  /** True when the user still needs to install to home screen before
   * notifications can be requested (iOS + non-standalone). */
  needsPwaInstall: boolean
  /** The browser's current notification permission state. */
  notificationPermission: NotificationPermission | 'unsupported'
}

export function detectInstallState(): InstallState {
  if (typeof window === 'undefined') {
    return {
      platform: 'other', standalone: false,
      supportsNotification: false, needsPwaInstall: false,
      notificationPermission: 'unsupported',
    }
  }
  const ua = navigator.userAgent || ''
  const isIOS = /iPhone|iPad|iPod/i.test(ua)
    || (navigator.platform === 'MacIntel' && (navigator as Navigator & { maxTouchPoints?: number }).maxTouchPoints! > 0)
  const isAndroid = /Android/i.test(ua)
  const standalone = window.matchMedia?.('(display-mode: standalone)').matches
    || (navigator as Navigator & { standalone?: boolean }).standalone === true
  const supportsNotification = typeof Notification !== 'undefined'
  const needsPwaInstall = isIOS && !standalone
  return {
    platform: isIOS ? 'ios' : isAndroid ? 'android' : 'other',
    standalone,
    supportsNotification,
    needsPwaInstall,
    notificationPermission: supportsNotification ? Notification.permission : 'unsupported',
  }
}

export function detectDevice(): DeviceInfo {
  if (typeof window === 'undefined') {
    return {
      kind: 'desktop', width: 0, height: 0,
      touch: false, coarsePointer: false, dpr: 1,
      platform: 'ssr', ua: '', uaMobileHint: null,
    }
  }

  const ua = navigator.userAgent || ''
  const { mobile: uaMobileHint, platform: uadPlatform } = readUAData()
  const platform = uadPlatform || (navigator as Navigator & { platform?: string }).platform || ''
  const width = window.innerWidth
  const height = window.innerHeight
  const touch =
    'ontouchstart' in window ||
    ((navigator as Navigator & { maxTouchPoints?: number }).maxTouchPoints || 0) > 0
  const coarsePointer = window.matchMedia('(pointer: coarse)').matches
  const dpr = window.devicePixelRatio || 1

  let kind: DeviceKind = 'desktop'

  // 0. Explicit overrides (URL param, localStorage, or query) — useful for
  // QA on a desktop browser. Persisted in sessionStorage so page reloads
  // in the same tab keep the forced mode.
  try {
    const params = new URLSearchParams(window.location.search)
    const urlOverride = params.get('device')
    if (urlOverride === 'mobile' || urlOverride === 'tablet' || urlOverride === 'desktop') {
      window.sessionStorage.setItem('__device_override', urlOverride)
    }
    const stored = window.sessionStorage.getItem('__device_override')
    if (stored === 'mobile' || stored === 'tablet' || stored === 'desktop') {
      return { kind: stored, width, height, touch, coarsePointer, dpr, platform, ua, uaMobileHint }
    }
  } catch { /* storage may be blocked in sandboxed frames */ }

  // 1. Explicit client-hint signal
  if (uaMobileHint === true) {
    kind = /Android/i.test(ua) && !/Mobile/i.test(ua) ? 'tablet' : 'mobile'
  } else if (uaMobileHint === false) {
    kind = 'desktop'
  } else if (/iPad/i.test(ua) || (platform === 'MacIntel' && touch && width >= 700)) {
    // 3. iPadOS 13+ masquerades as Mac — detect via touch + viewport
    kind = 'tablet'
  } else if (/Android/i.test(ua) && !/Mobile/i.test(ua)) {
    // Android tablets often drop "Mobile" token
    kind = 'tablet'
  } else if (/Android|webOS|iPhone|iPod|BlackBerry|IEMobile|Opera Mini|Mobile/i.test(ua)) {
    kind = 'mobile'
  } else if (touch && coarsePointer && width < 820) {
    // 4. Heuristic: touch device with a small viewport
    kind = width < 560 ? 'mobile' : 'tablet'
  }

  return { kind, width, height, touch, coarsePointer, dpr, platform, ua, uaMobileHint }
}

export function useDeviceKind(): DeviceInfo {
  const [info, setInfo] = useState<DeviceInfo>(() => detectDevice())
  useEffect(() => {
    let raf = 0
    const onChange = () => {
      cancelAnimationFrame(raf)
      raf = requestAnimationFrame(() => setInfo(detectDevice()))
    }
    window.addEventListener('resize', onChange)
    window.addEventListener('orientationchange', onChange)
    const mqCoarse = window.matchMedia('(pointer: coarse)')
    mqCoarse.addEventListener?.('change', onChange)
    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', onChange)
      window.removeEventListener('orientationchange', onChange)
      mqCoarse.removeEventListener?.('change', onChange)
    }
  }, [])
  return info
}

/**
 * Applies the detected device kind as a `data-device` attribute on `<html>`.
 * Allows CSS `html[data-device="mobile"] .x { ... }` selectors anywhere.
 * Also sets `.is-mobile` / `.is-tablet` / `.is-desktop` helper classes on body.
 */
export function installDeviceAttribute(): () => void {
  if (typeof document === 'undefined') return () => {}
  const apply = () => {
    const info = detectDevice()
    document.documentElement.setAttribute('data-device', info.kind)
    document.documentElement.setAttribute('data-touch', info.touch ? '1' : '0')
    document.body.classList.toggle('is-mobile', info.kind === 'mobile')
    document.body.classList.toggle('is-tablet', info.kind === 'tablet')
    document.body.classList.toggle('is-desktop', info.kind === 'desktop')
  }
  apply()
  const on = () => apply()
  window.addEventListener('resize', on)
  window.addEventListener('orientationchange', on)
  return () => {
    window.removeEventListener('resize', on)
    window.removeEventListener('orientationchange', on)
  }
}
