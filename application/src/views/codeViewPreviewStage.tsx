import { useEffect, useRef, useState, type RefObject } from 'react'

// ---------------------------------------------------------------------------
// La SCENE du rendu: cadre d'appareil (desktop/tablet/mobile), chrome de
// navigateur, encoche, et l'iframe elle-meme — plus l'auto-echelle qui fait
// tenir un 1440x900 dans le conteneur disponible.
//
// Extrait de `codeViewPreviewPanel.tsx` pour que le panneau compact ET le
// viewer plein ecran montent EXACTEMENT la meme scene: un seul iframe, un seul
// calcul d'echelle, pas de deuxieme rendu parallele.
// ---------------------------------------------------------------------------

export type BigViewport = 'desktop' | 'tablet' | 'mobile'

// Proportions physiques utilisees pour dessiner le chassis de facon realiste.
// width x height = taille EXTERIEURE. `pad` creuse l'ecran interieur.
export const BIG_VIEWPORT_SPEC: Record<BigViewport, {
  width: number   // largeur exterieure du cadre en px
  height: number  // hauteur exterieure du cadre en px
  pad: number     // epaisseur de la bordure
  radius: number  // rayon des coins exterieurs
  notch: boolean
  chrome: 'none' | 'browser'
}> = {
  desktop: { width: 1440, height: 900, pad: 0,  radius: 14, notch: false, chrome: 'browser' },
  tablet:  { width: 760,  height: 1024, pad: 20, radius: 36, notch: false, chrome: 'none' },
  mobile:  { width: 360,  height: 720,  pad: 12, radius: 40, notch: true,  chrome: 'none' },
}

export function PreviewStage({
  viewport,
  iframeRef,
}: {
  viewport: BigViewport
  iframeRef: RefObject<HTMLIFrameElement | null>
}) {
  const spec = BIG_VIEWPORT_SPEC[viewport]

  // Garantit que chaque viewport (y compris le desktop 1440x900) se met a
  // l'echelle pour tenir dans la zone visible. L'iframe voit toujours la vraie
  // resolution `spec.width x spec.height` — les media queries se declenchent
  // donc correctement.
  const frameWrapRef = useRef<HTMLDivElement>(null)
  const [frameScale, setFrameScale] = useState(1)

  useEffect(() => {
    const wrap = frameWrapRef.current
    if (!wrap) return
    const compute = () => {
      const availW = wrap.clientWidth - 32
      const availH = wrap.clientHeight - 32
      if (availW <= 0 || availH <= 0) return
      const s = Math.min(availW / spec.width, availH / spec.height, 1)
      setFrameScale(s < 0.2 ? 0.2 : s)
    }
    compute()
    // Le ResizeObserver couvre a lui seul le passage en plein ecran et le
    // redimensionnement du panneau d'arborescence: le conteneur change de
    // taille, l'echelle suit, sans dependance sur un flag de mise en page.
    const ro = new ResizeObserver(compute)
    ro.observe(wrap)
    window.addEventListener('resize', compute)
    return () => { ro.disconnect(); window.removeEventListener('resize', compute) }
  }, [spec.width, spec.height])

  return (
    <div
      ref={frameWrapRef}
      className="flex-1 flex items-center justify-center overflow-hidden min-h-[32rem]"
      style={{ background: 'var(--v4code-stage-bg, radial-gradient(circle at center, #1a1d22, #07080a))' }}
    >
      <div
        className="relative shrink-0 transition-[transform] duration-200 ease-out"
        style={{
          width: `${spec.width}px`,
          height: `${spec.height}px`,
          padding: `${spec.pad}px`,
          borderRadius: `${spec.radius}px`,
          background: spec.chrome === 'browser'
            ? 'linear-gradient(180deg,#2c2e33 0 44px,#fafafa 44px)'
            : 'linear-gradient(135deg,#1a1c22,#0a0b0e)',
          boxShadow: '0 30px 80px rgba(0,0,0,.55), inset 0 0 0 2px rgba(255,255,255,.05)',
          transform: `scale(${frameScale})`,
          transformOrigin: 'center center',
        }}
      >
        {spec.chrome === 'browser' && <BrowserChromeBar />}
        {spec.notch && (
          <div
            className="absolute left-1/2 -translate-x-1/2 z-10"
            style={{
              top: `${Math.round(spec.pad * 0.85)}px`,
              width: '110px',
              height: '26px',
              borderRadius: '18px',
              background: '#000',
              pointerEvents: 'none',
            }}
          />
        )}
        <iframe
          ref={iframeRef}
          title="Rendu live de la page"
          sandbox="allow-scripts allow-same-origin"
          className="block w-full h-full bg-white border-0"
          style={{
            borderRadius: spec.chrome === 'browser'
              ? '0 0 8px 8px'
              : `${Math.max(0, spec.radius - spec.pad * 0.5)}px`,
            marginTop: spec.chrome === 'browser' ? '44px' : 0,
            height: spec.chrome === 'browser' ? 'calc(100% - 44px)' : '100%',
          }}
        />
      </div>
    </div>
  )
}

function BrowserChromeBar() {
  return (
    <div
      className="absolute top-0 left-0 right-0 flex items-center gap-2 px-3"
      style={{
        height: '44px',
        borderRadius: '14px 14px 0 0',
        background: 'linear-gradient(180deg,#34363b,#26282d)',
        borderBottom: '1px solid rgba(0,0,0,.35)',
        pointerEvents: 'none',
      }}
    >
      <span style={{ display: 'inline-block', width: 12, height: 12, borderRadius: '50%', background: '#ff5f56' }} />
      <span style={{ display: 'inline-block', width: 12, height: 12, borderRadius: '50%', background: '#ffbd2e' }} />
      <span style={{ display: 'inline-block', width: 12, height: 12, borderRadius: '50%', background: '#27c93f' }} />
      <div
        className="ml-3 flex-1 flex items-center"
        style={{
          height: '26px',
          background: 'rgba(255,255,255,.08)',
          borderRadius: '999px',
          padding: '0 14px',
          fontSize: '11px',
          color: '#b6b8be',
          fontFamily: 'system-ui, sans-serif',
          letterSpacing: '.02em',
        }}
      >
        <span style={{ opacity: .55, marginRight: 6 }}>●</span>
        aurora-preview.local
      </div>
    </div>
  )
}
