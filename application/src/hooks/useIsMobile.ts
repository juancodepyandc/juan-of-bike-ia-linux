/**
 * iter40 — hook simple "est-ce qu'on est sur un écran mobile ?"
 *
 * Utilisé pour rendre conditionnellement des layouts différents (1 colonne
 * stack vs 2 colonnes desktop) au lieu de juste @media CSS qui surcharge
 * mais ne change pas la structure JSX. Plus fiable que matchMedia + state
 * sur certains WebViews qui ne notifient pas correctement.
 */
import { useEffect, useState } from 'react'

export function useIsMobile(breakpoint = 720): boolean {
  const [isMobile, setIsMobile] = useState(() => {
    if (typeof window === 'undefined') return false
    return window.innerWidth <= breakpoint
  })

  useEffect(() => {
    if (typeof window === 'undefined') return
    const onResize = () => setIsMobile(window.innerWidth <= breakpoint)
    window.addEventListener('resize', onResize)
    // re-eval after orientation change too (some Android keep innerWidth
    // stale until orientationchange fires).
    window.addEventListener('orientationchange', onResize)
    return () => {
      window.removeEventListener('resize', onResize)
      window.removeEventListener('orientationchange', onResize)
    }
  }, [breakpoint])

  return isMobile
}
