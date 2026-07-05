/**
 * v82gc : floating "?" help button (FAB) bottom-left.
 * Discoverable sur desktop/touch-laptop où le clavier "?" n'est pas
 * forcément réflexe. Click → dispatch event "?" qui réveille
 * la KeyboardCheatsheet (qui écoute déjà cette key).
 *
 * v82s-studio iter6 : masqué sur mobile/tablet — pas de clavier physique,
 * la cheatsheet n'a aucune valeur, et l'orbe chevauchait le contenu en
 * bas-gauche des shells mobile.
 */
import { useDeviceKind } from '../utils/device'

export default function HelpFab() {
  const device = useDeviceKind()
  if (device.kind !== 'desktop') return null
  return (
    <button type="button"
      onClick={() => {
        // Dispatch synthetic ? key event que KeyboardCheatsheet écoute
        window.dispatchEvent(new KeyboardEvent('keydown', { key: '?', shiftKey: true }))
      }}
      title={`Afficher l'aide clavier (?) · build ${typeof __AURORA_COMMIT__ !== 'undefined' ? __AURORA_COMMIT__ : 'dev'}`}
      aria-label="Aide clavier"
      style={{
        position: 'fixed', bottom: 24, left: 24, zIndex: 88,
        width: 36, height: 36, borderRadius: '50%',
        background: 'oklch(0.74 0.13 60 / 0.85)',
        color: 'var(--bg, #0c0a09)',
        border: '1px solid oklch(0.74 0.13 60)',
        boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
        cursor: 'pointer',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 18, fontWeight: 700,
        fontFamily: 'var(--font-mono, monospace)',
        backdropFilter: 'blur(4px)',
      }}>
      ?
    </button>
  )
}
