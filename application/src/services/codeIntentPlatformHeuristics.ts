// ---------------------------------------------------------------------------
// Platform request heuristics
// Extracted from codeIntent.ts during WS1 modularisation.
// ---------------------------------------------------------------------------

import { DESKTOP_SIGNALS, MOBILE_SIGNALS } from './codeIntentSignals.ts'
import { containsAnySignal } from './codeIntentSignalUtils.ts'

export function looksLikeDesktopAppRequest(lower: string) {
  // Signal DESKTOP EXPLICITE (phrases completes comme "application desktop").
  if (containsAnySignal(lower, DESKTOP_SIGNALS)) return true

  // Desktop implicite: un mot "logiciel / programme / application" combine avec
  // un mot "bureau / desktop / windows". Sans cette combinaison, on reste sur webapp.
  const mentionsProgramNoun =
    /\bprogramme\b/i.test(lower)
    || /\blogiciel\b/i.test(lower)
    || /\bapplication\b/i.test(lower)
    || /\bapp\b/i.test(lower)

  const mentionsDesktopNoun =
    /\bbureau\b/i.test(lower)
    || /\bdesktop\b/i.test(lower)
    || /\bwindows\b/i.test(lower)
    || /\bmacos\b/i.test(lower)
    || /\blinux\b/i.test(lower)

  return mentionsProgramNoun && mentionsDesktopNoun
}

export function looksLikeMobileAppRequest(lower: string) {
  // Explicit mobile signals always win ("react native", "app android", "ios",
  // "iphone app", "appli mobile"...).
  if (containsAnySignal(lower, MOBILE_SIGNALS)) return true

  // Implicit mobile: "app"/"application" combined with a phone-only word
  // (smartphone, telephone mobile, play store, app store...).
  const mentionsProgramNoun =
    /\bapplication\b/i.test(lower)
    || /\bapp\b/i.test(lower)
    || /\bappli\b/i.test(lower)
    || /\blogiciel\b/i.test(lower)

  const mentionsMobileNoun =
    /\bsmartphone\b/i.test(lower)
    || /\bt[eé]l[eé]phone\b/i.test(lower)
    || /\bphone\b/i.test(lower)
    || /\btactile\b/i.test(lower)
    || /\bplay\s*store\b/i.test(lower)
    || /\bapp\s*store\b/i.test(lower)
    || /\bappstore\b/i.test(lower)
    || /\bplaystore\b/i.test(lower)
    || /\bapk\b/i.test(lower)

  return mentionsProgramNoun && mentionsMobileNoun
}
