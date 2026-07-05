// ---------------------------------------------------------------------------
// coworkBrowserDetect — front-side browser detection + bridge fallback for
// silent PC-side scan.
// ---------------------------------------------------------------------------

import { getBridgeUrl, isTauriRuntime } from '../utils/runtime.ts'
import { BROWSERS, detectIdFromUA, getInstallInstructionsFor, type BrowserId } from './coworkBrowserDetectPure.ts'

export type { BrowserId } from './coworkBrowserDetectPure.ts'

export type BrowserInfo = {
  id: BrowserId
  label: string
  engine: 'chromium' | 'gecko' | 'webkit' | 'unknown'
  detection: 'ua' | 'feature' | 'pc-scan' | 'unknown'
}

/** Detects the CURRENT browser the user is in via the user agent + feature
 *  hints. Cheap, sync, no network call. */
export function detectCurrentBrowser(): BrowserInfo {
  const ua = (typeof navigator !== 'undefined') ? navigator.userAgent : ''
  const brave = (typeof navigator !== 'undefined' && !!(navigator as Navigator & { brave?: unknown }).brave)
  const id = detectIdFromUA(ua, brave)
  const meta = BROWSERS[id]
  return {
    id,
    label: meta.label,
    engine: meta.engine,
    detection: brave ? 'feature' : 'ua',
  }
}

/** PC-side silent scan via bridge. Returns the list of installed browsers
 *  on the user's machine (e.g. so Aurora can recommend the same browser as
 *  the one currently in use, or surface alternatives). */
export async function scanInstalledBrowsers(): Promise<BrowserInfo[]> {
  if (isTauriRuntime() === false && !getBridgeUrl()) return []
  try {
    const r = await fetch(`${getBridgeUrl()}/api/cowork/browsers/detect`, {
      signal: AbortSignal.timeout(8_000),
    })
    if (!r.ok) return []
    const data = await r.json() as { ok: boolean; browsers?: Array<{ name: string; installed: boolean; label: string; extension_engine: string }> }
    if (!data.ok || !data.browsers) return []
    return data.browsers
      .filter((b) => b.installed)
      .map((b) => ({
        id: (b.name as BrowserId in BROWSERS) ? (b.name as BrowserId) : 'unknown' as BrowserId,
        label: b.label,
        engine: (b.extension_engine === 'gecko' ? 'gecko' : b.extension_engine === 'webkit' ? 'webkit' : 'chromium') as BrowserInfo['engine'],
        detection: 'pc-scan' as const,
      }))
  } catch {
    return []
  }
}

/** Get install instructions for the Aurora-Connect extension on a given
 *  browser. Used by the settings dialog tab "Aurora-Connect". */
export function getInstallInstructions(id: BrowserId) {
  return getInstallInstructionsFor(id, `${getBridgeUrl()}/api/cowork/extension/download`)
}
