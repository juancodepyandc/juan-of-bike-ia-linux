// ---------------------------------------------------------------------------
// coworkBrowserDetectPure — pure helpers (no browser/runtime deps), so they
// are testable under Node.js test runner.
// ---------------------------------------------------------------------------

export type BrowserId =
  | 'chrome' | 'edge' | 'firefox' | 'safari' | 'brave' | 'opera'
  | 'vivaldi' | 'chromium' | 'arc' | 'unknown'

export type BrowserMeta = {
  label: string
  engine: 'chromium' | 'gecko' | 'webkit' | 'unknown'
}

export const BROWSERS: Record<BrowserId, BrowserMeta> = {
  chrome:   { label: 'Google Chrome',    engine: 'chromium' },
  edge:     { label: 'Microsoft Edge',   engine: 'chromium' },
  firefox:  { label: 'Mozilla Firefox',  engine: 'gecko' },
  safari:   { label: 'Safari',           engine: 'webkit' },
  brave:    { label: 'Brave',            engine: 'chromium' },
  opera:    { label: 'Opera',            engine: 'chromium' },
  vivaldi:  { label: 'Vivaldi',          engine: 'chromium' },
  chromium: { label: 'Chromium',         engine: 'chromium' },
  arc:      { label: 'Arc',              engine: 'chromium' },
  unknown:  { label: 'Navigateur inconnu', engine: 'unknown' },
}

/** Detect a browser id from a user agent string. Pure function — no globals. */
export function detectIdFromUA(userAgent: string, brave: boolean = false): BrowserId {
  if (!userAgent) return 'unknown'
  const ua = userAgent.toLowerCase()
  if (ua.includes('edg/') || ua.includes('edge/')) return 'edge'
  if (ua.includes('opr/') || ua.includes('opera')) return 'opera'
  if (ua.includes('vivaldi')) return 'vivaldi'
  if (brave) return 'brave'
  if (ua.includes('firefox/')) return 'firefox'
  if (ua.includes('chrome/')) return 'chrome'
  if (ua.includes('safari/') && !ua.includes('chrome/')) return 'safari'
  if (ua.includes('chromium/')) return 'chromium'
  return 'unknown'
}

export type InstallInstructions = {
  title: string
  steps: Array<{ label: string; detail?: string }>
  loadUnpackedUrl?: string
}

export function getInstallInstructionsFor(id: BrowserId, loadUnpackedUrl?: string): InstallInstructions {
  switch (id) {
    case 'chrome':
    case 'chromium':
      return {
        title: 'Chrome / Chromium',
        loadUnpackedUrl,
        steps: [
          { label: 'Telecharger', detail: 'le ZIP de l extension via le bouton ci-dessous' },
          { label: 'Decompresser', detail: 'dans un dossier permanent (par ex. ~/aurora-connect/)' },
          { label: 'Ouvrir chrome://extensions', detail: 'colle dans la barre d adresse' },
          { label: 'Activer "Mode developpeur"', detail: 'toggle en haut a droite' },
          { label: 'Cliquer "Charger l extension non empaquetee"', detail: 'puis selectionne le dossier extrait' },
          { label: 'Verifier', detail: 'tu vois "Aurora-Connect" avec son icone violet' },
        ],
      }
    case 'edge':
      return {
        title: 'Microsoft Edge',
        loadUnpackedUrl,
        steps: [
          { label: 'Telecharger', detail: 'le ZIP via le bouton' },
          { label: 'Ouvrir edge://extensions', detail: 'colle dans la barre d adresse' },
          { label: 'Activer "Mode developpeur"', detail: 'toggle a gauche' },
          { label: 'Charger non empaquetee', detail: 'pointe vers le dossier extrait' },
        ],
      }
    case 'brave':
      return {
        title: 'Brave',
        loadUnpackedUrl,
        steps: [
          { label: 'Telecharger', detail: 'le ZIP' },
          { label: 'Ouvrir brave://extensions', detail: 'identique a Chrome (Brave est Chromium-based)' },
          { label: 'Mode developpeur ON', detail: 'puis Charger non empaquetee' },
        ],
      }
    case 'opera':
      return {
        title: 'Opera',
        loadUnpackedUrl,
        steps: [
          { label: 'Telecharger', detail: 'le ZIP' },
          { label: 'Ouvrir opera://extensions', detail: 'puis bouton "Developer mode"' },
          { label: 'Charger non empaquetee', detail: 'selectionne le dossier' },
        ],
      }
    case 'vivaldi':
      return {
        title: 'Vivaldi',
        loadUnpackedUrl,
        steps: [
          { label: 'Telecharger', detail: 'le ZIP' },
          { label: 'Ouvrir vivaldi://extensions', detail: 'idem Chrome' },
          { label: 'Charger non empaquetee', detail: 'selectionne le dossier' },
        ],
      }
    case 'arc':
      return {
        title: 'Arc',
        loadUnpackedUrl,
        steps: [
          { label: 'Ouvrir Settings -> Extensions', detail: 'ou Cmd+, puis "Manage extensions"' },
          { label: 'Cliquer "Add extension"', detail: 'Mode developpeur' },
          { label: 'Charger non empaquetee', detail: 'selectionne le dossier extrait' },
        ],
      }
    case 'firefox':
      return {
        title: 'Firefox',
        loadUnpackedUrl,
        steps: [
          { label: 'Telecharger', detail: 'le ZIP' },
          { label: 'Ouvrir about:debugging#/runtime/this-firefox', detail: 'colle dans la barre d adresse' },
          { label: 'Cliquer "Load Temporary Add-on"', detail: 'selectionne le manifest.json' },
          { label: 'Note', detail: 'temporaire — disparait au redemarrage. Pour permanent, signer via AMO (https://addons.mozilla.org/developers/)' },
        ],
      }
    case 'safari':
      return {
        title: 'Safari (macOS)',
        loadUnpackedUrl,
        steps: [
          { label: 'Telecharger', detail: 'le ZIP de l extension' },
          { label: 'Ouvrir Xcode', detail: 'gratuit sur le Mac App Store' },
          { label: 'File -> New -> Project -> Safari Extension App', detail: 'crée un wrapper macOS' },
          { label: 'Importe les fichiers', detail: 'manifest.json + JS + HTML dans le dossier de l extension' },
          { label: 'Run Build', detail: 'l extension apparait dans Safari -> Preferences -> Extensions' },
          { label: 'Important', detail: 'Safari requiert Xcode pour signer les extensions, contrairement aux autres navigateurs.' },
        ],
      }
    default:
      return {
        title: 'Navigateur inconnu',
        steps: [
          { label: 'Tu peux essayer la procedure Chrome', detail: 'la majorite des navigateurs modernes (sauf Safari/Firefox) supportent les extensions Chrome/Chromium' },
        ],
      }
  }
}
