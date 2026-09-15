/**
 * MediaEmbed — une URL, rendue par ce qu'elle est.
 *
 * Avant, tout lien de la conversation s'affichait pareil : du texte bleu.
 * Une photo, une vidéo YouTube, un GLB produit par le module 3D et un article
 * de presse avaient exactement la même apparence, et il fallait ouvrir un
 * onglet pour savoir lequel était lequel.
 *
 * Ici chaque nature a son rendu : image cliquable en plein écran, lecteur
 * vidéo/audio natif, iframe YouTube/Vimeo chargée seulement au clic (pas de
 * requête vers Google tant que personne ne regarde), viewer 3D interactif,
 * PDF ouvrable, et carte de lien avec favicon pour le reste.
 */
import { lazy, Suspense, useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import {
  classifyUrl,
  domainOf,
  faviconUrl,
  fileNameOf,
  isViewableModel,
  parseVideoEmbed,
  type MediaKind,
} from '../../utils/mediaLinks.ts'

const InlineModelViewer = lazy(() => import('./InlineModelViewer.tsx'))

const MONO = "'Cascadia Code',Consolas,monospace"
const ACCENT = '#8B5CF6'

const FRAME: React.CSSProperties = {
  borderRadius: 12,
  border: '1px solid rgba(255,255,255,.09)',
  background: 'rgba(255,255,255,.03)',
  overflow: 'hidden',
}

const KIND_LABEL: Record<MediaKind, string> = {
  image: 'image',
  video: 'vidéo',
  videoEmbed: 'vidéo',
  audio: 'audio',
  model3d: 'modèle 3d',
  pdf: 'pdf',
  page: 'lien',
}

// ---------------------------------------------------------------------------
// Plein écran
// ---------------------------------------------------------------------------

function Lightbox({ url, alt, onClose }: { url: string; alt?: string; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = previous
    }
  }, [onClose])

  const overlay = (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={alt || 'Image en plein écran'}
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        // Au-dessus de l'écran de génération (z-118), sinon la visionneuse
        // s'ouvrirait derrière le voile et paraîtrait ne rien faire.
        zIndex: 200,
        background: 'rgba(4,7,16,.92)',
        backdropFilter: 'blur(10px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 28,
        cursor: 'zoom-out',
      }}
    >
      <img
        src={url}
        alt={alt || ''}
        style={{ maxWidth: '100%', maxHeight: '100%', borderRadius: 12, boxShadow: '0 30px 90px rgba(0,0,0,.6)' }}
      />
      <div style={{
        position: 'absolute',
        bottom: 18,
        left: 0,
        right: 0,
        textAlign: 'center',
        fontFamily: MONO,
        fontSize: 11,
        color: '#8B93A7',
      }}>
        {domainOf(url) || fileNameOf(url)} · Échap pour fermer
      </div>
    </div>
  )
  return typeof document === 'undefined' ? overlay : createPortal(overlay, document.body)
}

/**
 * Image de markdown : cliquable en plein écran, et surtout rendue avec un
 * seul <img>. Une figure ou un div ici seraient invalides — react-markdown
 * place les images à l'intérieur d'un <p>.
 */
export function MarkdownImage({ src, alt }: { src?: string; alt?: string }) {
  const [open, setOpen] = useState(false)
  if (!src) return null
  return (
    <>
      <img
        src={src}
        alt={alt || ''}
        loading="lazy"
        onClick={() => setOpen(true)}
        style={{
          display: 'block',
          maxWidth: '100%',
          maxHeight: 420,
          borderRadius: 12,
          border: '1px solid rgba(255,255,255,.09)',
          margin: '10px 0',
          cursor: 'zoom-in',
        }}
      />
      {open && <Lightbox url={src} alt={alt} onClose={() => setOpen(false)} />}
    </>
  )
}

// ---------------------------------------------------------------------------
// Cartes par nature
// ---------------------------------------------------------------------------

function Caption({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      padding: '7px 10px',
      fontFamily: MONO,
      fontSize: 10.5,
      color: '#8B93A7',
      borderTop: '1px solid rgba(255,255,255,.06)',
      minWidth: 0,
    }}>
      {children}
    </div>
  )
}

function Favicon({ url, size = 14 }: { url: string; size?: number }) {
  const [failed, setFailed] = useState(false)
  const domain = domainOf(url)
  const src = faviconUrl(url)
  if (failed || !src) {
    return (
      <span style={{
        width: size,
        height: size,
        borderRadius: 4,
        flexShrink: 0,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: `${ACCENT}22`,
        color: ACCENT,
        fontSize: size * 0.6,
        fontWeight: 700,
      }}>
        {(domain[0] || '?').toUpperCase()}
      </span>
    )
  }
  return (
    <img
      src={src}
      alt=""
      width={size}
      height={size}
      loading="lazy"
      onError={() => setFailed(true)}
      style={{ borderRadius: 4, flexShrink: 0 }}
    />
  )
}

function ImageCard({ url, alt, caption }: { url: string; alt?: string; caption?: string }) {
  const [open, setOpen] = useState(false)
  const [broken, setBroken] = useState(false)

  if (broken) return <LinkCard url={url} title={alt} />

  return (
    <>
      <figure style={{ ...FRAME, margin: 0 }}>
        <img
          src={url}
          alt={alt || ''}
          loading="lazy"
          onClick={() => setOpen(true)}
          onError={() => setBroken(true)}
          style={{
            display: 'block',
            width: '100%',
            maxHeight: 380,
            objectFit: 'cover',
            cursor: 'zoom-in',
            background: 'rgba(10,15,30,.6)',
          }}
        />
        <Caption>
          <Favicon url={caption || url} />
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {alt || fileNameOf(url)}
          </span>
          <a
            href={caption || url}
            target="_blank"
            rel="noreferrer"
            style={{ marginLeft: 'auto', color: ACCENT, textDecoration: 'none', flexShrink: 0 }}
          >
            source
          </a>
        </Caption>
      </figure>
      {open && <Lightbox url={url} alt={alt} onClose={() => setOpen(false)} />}
    </>
  )
}

function VideoFileCard({ url }: { url: string }) {
  return (
    <div style={FRAME}>
      <video
        src={url}
        controls
        preload="metadata"
        playsInline
        style={{ display: 'block', width: '100%', maxHeight: 400, background: '#05070F' }}
      />
      <Caption>
        <Favicon url={url} />
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{fileNameOf(url)}</span>
      </Caption>
    </div>
  )
}

function VideoEmbedCard({ url, title }: { url: string; title?: string }) {
  const embed = parseVideoEmbed(url)
  // Facade : tant qu'on n'a pas cliqué, aucune requête ne part vers la
  // plateforme. Une conversation avec dix vidéos ne charge pas dix lecteurs.
  const [playing, setPlaying] = useState(false)
  if (!embed) return <LinkCard url={url} title={title} />

  return (
    <div style={FRAME}>
      <div style={{ position: 'relative', width: '100%', aspectRatio: '16 / 9', background: '#05070F' }}>
        {playing ? (
          <iframe
            src={`${embed.embedUrl}?autoplay=1`}
            title={title || 'Vidéo'}
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; fullscreen"
            allowFullScreen
            style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', border: 0 }}
          />
        ) : (
          <button
            type="button"
            onClick={() => setPlaying(true)}
            aria-label={`Lire la vidéo ${title || ''}`}
            style={{
              position: 'absolute',
              inset: 0,
              width: '100%',
              height: '100%',
              border: 0,
              padding: 0,
              cursor: 'pointer',
              background: embed.thumbUrl
                ? `center / cover no-repeat url(${embed.thumbUrl})`
                : 'radial-gradient(circle at 50% 40%,rgba(139,92,246,.2),#05070F)',
            }}
          >
            <span style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'rgba(5,7,15,.35)',
            }}>
              <span style={{
                width: 58,
                height: 58,
                borderRadius: '50%',
                background: 'rgba(10,15,30,.78)',
                border: `1px solid ${ACCENT}`,
                boxShadow: `0 0 26px ${ACCENT}66`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}>
                <svg viewBox="0 0 24 24" width={22} height={22} fill={ACCENT}>
                  <path d="M8 5.5v13l11-6.5z" />
                </svg>
              </span>
            </span>
          </button>
        )}
      </div>
      <Caption>
        <Favicon url={url} />
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {title || fileNameOf(url)}
        </span>
        <a href={url} target="_blank" rel="noreferrer" style={{ marginLeft: 'auto', color: ACCENT, textDecoration: 'none', flexShrink: 0 }}>
          ouvrir
        </a>
      </Caption>
    </div>
  )
}

function AudioCard({ url }: { url: string }) {
  return (
    <div style={{ ...FRAME, padding: '12px 12px 6px' }}>
      <audio src={url} controls preload="metadata" style={{ width: '100%' }} />
      <div style={{ fontFamily: MONO, fontSize: 10.5, color: '#8B93A7', padding: '6px 2px 4px' }}>
        {fileNameOf(url)}
      </div>
    </div>
  )
}

function ModelCard({ url }: { url: string }) {
  if (!isViewableModel(url)) {
    // .obj / .fbx / .stl : le viewer intégré ne les lit pas. On le dit au
    // lieu d'afficher un cadre noir qui laisserait croire à un bug.
    return <LinkCard url={url} title={`Modèle 3D (${fileNameOf(url)}) — format non lisible dans le chat`} />
  }
  return (
    <div style={FRAME}>
      <Suspense fallback={
        <div style={{ height: 260, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: MONO, fontSize: 11, color: '#8B93A7' }}>
          Préparation du viewer 3D…
        </div>
      }>
        <InlineModelViewer url={url} />
      </Suspense>
      <Caption>
        <Favicon url={url} />
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{fileNameOf(url)}</span>
        <a href={url} target="_blank" rel="noreferrer" download style={{ marginLeft: 'auto', color: ACCENT, textDecoration: 'none', flexShrink: 0 }}>
          télécharger
        </a>
      </Caption>
    </div>
  )
}

function PdfCard({ url, title }: { url: string; title?: string }) {
  const [open, setOpen] = useState(false)
  return (
    <div style={FRAME}>
      {open ? (
        <iframe
          src={url}
          title={title || fileNameOf(url)}
          style={{ display: 'block', width: '100%', height: 460, border: 0, background: '#fff' }}
        />
      ) : (
        <button
          type="button"
          onClick={() => setOpen(true)}
          style={{
            width: '100%',
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            padding: '14px 12px',
            border: 0,
            background: 'transparent',
            color: '#E6EAF5',
            cursor: 'pointer',
            textAlign: 'left',
            font: 'inherit',
          }}
        >
          <span style={{
            width: 30, height: 30, borderRadius: 8, flexShrink: 0,
            background: '#F8717122', color: '#F87171',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontFamily: MONO, fontSize: 9, fontWeight: 700,
          }}>PDF</span>
          <span style={{ minWidth: 0 }}>
            <span style={{ display: 'block', fontSize: 12.5, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {title || fileNameOf(url)}
            </span>
            <span style={{ display: 'block', fontFamily: MONO, fontSize: 10, color: '#8B93A7' }}>
              {domainOf(url)} · cliquer pour lire ici
            </span>
          </span>
        </button>
      )}
    </div>
  )
}

function LinkCard({ url, title, snippet }: { url: string; title?: string; snippet?: string }) {
  return (
    <a
      href={url}
      target="_blank"
      rel="noreferrer"
      style={{
        ...FRAME,
        display: 'flex',
        alignItems: 'flex-start',
        gap: 10,
        padding: '10px 12px',
        textDecoration: 'none',
        color: '#E6EAF5',
      }}
    >
      <Favicon url={url} size={18} />
      <span style={{ minWidth: 0 }}>
        <span style={{ display: 'block', fontSize: 12.5, fontWeight: 600, lineHeight: 1.35 }}>
          {title || fileNameOf(url)}
        </span>
        <span style={{ display: 'block', fontFamily: MONO, fontSize: 10, color: ACCENT, marginTop: 2 }}>
          {domainOf(url)}
        </span>
        {snippet && (
          <span style={{ display: 'block', fontSize: 11.5, color: '#8B93A7', marginTop: 4, lineHeight: 1.45 }}>
            {snippet.slice(0, 220)}
          </span>
        )}
      </span>
    </a>
  )
}

// ---------------------------------------------------------------------------

export type MediaEmbedProps = {
  url: string
  title?: string
  snippet?: string
  /** Page d'origine d'une image (crédit). */
  sourcePage?: string
  /** Force une nature au lieu de la déduire de l'URL. */
  kind?: MediaKind
}

/** Rend une URL selon sa nature réelle. */
export default function MediaEmbed({ url, title, snippet, sourcePage, kind }: MediaEmbedProps) {
  const resolved = kind ?? classifyUrl(url)
  switch (resolved) {
    case 'image': return <ImageCard url={url} alt={title} caption={sourcePage} />
    case 'video': return <VideoFileCard url={url} />
    case 'videoEmbed': return <VideoEmbedCard url={url} title={title} />
    case 'audio': return <AudioCard url={url} />
    case 'model3d': return <ModelCard url={url} />
    case 'pdf': return <PdfCard url={url} title={title} />
    default: return <LinkCard url={url} title={title} snippet={snippet} />
  }
}

export { Favicon, KIND_LABEL }

/**
 * Bandeau de médias sous une réponse : les images en grille, le reste
 * empilé pleine largeur (un lecteur vidéo à 120 px de large ne sert à rien).
 */
export function MediaStrip({ urls, max = 8 }: { urls: string[]; max?: number }) {
  const list = urls.slice(0, max)
  if (list.length === 0) return null
  const images = list.filter((u) => classifyUrl(u) === 'image')
  const others = list.filter((u) => classifyUrl(u) !== 'image')

  return (
    <div style={{ display: 'grid', gap: 10, marginTop: 10 }}>
      {images.length > 0 && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: images.length === 1 ? '1fr' : 'repeat(auto-fill,minmax(180px,1fr))',
          gap: 8,
        }}>
          {images.map((url) => <MediaEmbed key={url} url={url} />)}
        </div>
      )}
      {others.map((url) => <MediaEmbed key={url} url={url} />)}
    </div>
  )
}
