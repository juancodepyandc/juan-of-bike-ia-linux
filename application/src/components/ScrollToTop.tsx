/**
 * v82ec : floating "scroll to top" button. Apparaît quand l'utilisateur
 * a scrollé > 300px dans le scrollableSelector (ou window). Click → smooth
 * scroll to top. Cache automatiquement quand on est en haut.
 *
 * Usage simple :
 *   <ScrollToTop /> // observe window
 *   <ScrollToTop targetSelector=".aurora-academy-output" /> // observe un container
 */
import { useEffect, useState } from 'react'

interface Props {
  /** Selector CSS pour observer un container scrollable. Si absent, observe window. */
  targetSelector?: string
  /** Pixel threshold avant d'afficher le bouton (default 300). */
  threshold?: number
}

export default function ScrollToTop({ targetSelector, threshold = 300 }: Props = {}) {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const target: HTMLElement | Window | null = targetSelector
      ? document.querySelector<HTMLElement>(targetSelector)
      : window
    if (!target) return
    const getScroll = () => target === window
      ? window.scrollY
      : (target as HTMLElement).scrollTop
    const onScroll = () => setVisible(getScroll() > threshold)
    onScroll()
    target.addEventListener('scroll', onScroll, { passive: true } as AddEventListenerOptions)
    return () => target.removeEventListener('scroll', onScroll)
  }, [targetSelector, threshold])

  const handleClick = () => {
    const target: HTMLElement | Window | null = targetSelector
      ? document.querySelector<HTMLElement>(targetSelector)
      : window
    if (!target) return
    if (target === window) {
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } else {
      (target as HTMLElement).scrollTo({ top: 0, behavior: 'smooth' })
    }
  }

  if (!visible) return null

  return (
    <button type="button"
      onClick={handleClick}
      title="Remonter en haut"
      style={{
        position: 'fixed', bottom: 24, right: 24, zIndex: 90,
        width: 36, height: 36, borderRadius: '50%',
        background: 'oklch(0.74 0.13 60 / 0.85)',
        color: 'var(--bg, #0c0a09)',
        border: '1px solid oklch(0.74 0.13 60)',
        boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
        cursor: 'pointer',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 16, fontWeight: 700,
        fontFamily: 'var(--font-mono, monospace)',
        animation: 'aurora-stt-fade-in 0.18s ease-out',
        backdropFilter: 'blur(4px)',
      }}>
      ↑
      <style>{`@keyframes aurora-stt-fade-in {
        from { opacity: 0; transform: translateY(8px) }
        to { opacity: 1; transform: translateY(0) }
      }`}</style>
    </button>
  )
}
