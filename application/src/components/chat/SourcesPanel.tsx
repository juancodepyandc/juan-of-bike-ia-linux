/**
 * SourcesPanel — les sites où Aurora est allée, visibles.
 *
 * Deux usages avec le même composant :
 *  • `live` pendant que le tour tourne : les cartes apparaissent au moment où
 *    le moteur renvoie le lien, puis passent en « lecture… » quand la page
 *    est réellement ouverte. On voit le travail se faire.
 *  • replié sous une réponse livrée : « 7 sources · lemonde.fr, insee.fr… »,
 *    dépliable, avec les numéros [1] [2] qui correspondent aux citations du
 *    texte.
 *
 * Une source en échec reste affichée, barrée. L'effacer donnerait l'illusion
 * d'une recherche parfaite alors qu'un site a refusé de répondre.
 */
import { useMemo, useState } from 'react'
import type { WebSource } from '../../types/app.ts'
import MediaEmbed, { Favicon } from './MediaEmbed.tsx'

const MONO = "'Cascadia Code',Consolas,monospace"
const ACCENT = '#8B5CF6'

const STATUS_LABEL: Record<WebSource['status'], string> = {
  found: 'trouvée',
  reading: 'lecture…',
  read: 'lue',
  failed: 'illisible',
}

const STATUS_COLOR: Record<WebSource['status'], string> = {
  found: '#8B93A7',
  reading: ACCENT,
  read: '#34D399',
  failed: '#F87171',
}

function PageRow({ source }: { source: WebSource }) {
  return (
    <a
      href={source.url}
      target="_blank"
      rel="noreferrer"
      title={source.url}
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: 9,
        padding: '9px 10px',
        borderRadius: 10,
        border: '1px solid rgba(255,255,255,.07)',
        background: 'rgba(255,255,255,.025)',
        textDecoration: 'none',
        color: '#E6EAF5',
        opacity: source.status === 'failed' ? 0.55 : 1,
        transition: 'background .2s, border-color .2s',
      }}
    >
      {source.rank !== undefined && (
        <span style={{
          flexShrink: 0,
          minWidth: 20,
          height: 20,
          padding: '0 5px',
          borderRadius: 6,
          background: `${ACCENT}1f`,
          color: ACCENT,
          fontFamily: MONO,
          fontSize: 10,
          fontWeight: 700,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}>
          {source.rank}
        </span>
      )}
      <Favicon url={source.url} size={15} />
      <span style={{ minWidth: 0, flex: 1 }}>
        <span style={{
          display: 'block',
          fontSize: 12.5,
          fontWeight: 600,
          lineHeight: 1.35,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          textDecoration: source.status === 'failed' ? 'line-through' : 'none',
        }}>
          {source.title}
        </span>
        <span style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 2, flexWrap: 'wrap' }}>
          <span style={{ fontFamily: MONO, fontSize: 10, color: ACCENT }}>{source.domain}</span>
          <span style={{ fontFamily: MONO, fontSize: 9.5, color: STATUS_COLOR[source.status] }}>
            {STATUS_LABEL[source.status]}
          </span>
        </span>
        {source.snippet && (
          <span style={{ display: 'block', fontSize: 11.5, color: '#8B93A7', marginTop: 4, lineHeight: 1.45 }}>
            {source.snippet.slice(0, 200)}
          </span>
        )}
      </span>
    </a>
  )
}

export type SourcesPanelProps = {
  sources: WebSource[]
  queries?: string[]
  /** true pendant la recherche : le panneau reste ouvert et pulse. */
  live?: boolean
  /** Ouvert d'emblée sous une réponse livrée. */
  defaultOpen?: boolean
}

export default function SourcesPanel({ sources, queries = [], live = false, defaultOpen = false }: SourcesPanelProps) {
  const [open, setOpen] = useState(defaultOpen)

  const { pages, images, videos, domains } = useMemo(() => {
    const pages = sources.filter((s) => s.kind === 'page')
    return {
      pages,
      images: sources.filter((s) => s.kind === 'image'),
      videos: sources.filter((s) => s.kind === 'video'),
      domains: [...new Set(pages.map((s) => s.domain).filter(Boolean))],
    }
  }, [sources])

  if (sources.length === 0 && queries.length === 0) return null

  const expanded = live || open

  return (
    <div style={{
      marginTop: 10,
      borderRadius: 12,
      border: `1px solid ${live ? `${ACCENT}44` : 'rgba(255,255,255,.08)'}`,
      background: live ? `${ACCENT}0a` : 'rgba(255,255,255,.02)',
      overflow: 'hidden',
    }}>
      <button
        type="button"
        onClick={() => !live && setOpen((v) => !v)}
        aria-expanded={expanded}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '9px 11px',
          border: 0,
          background: 'transparent',
          color: '#E6EAF5',
          cursor: live ? 'default' : 'pointer',
          font: 'inherit',
          textAlign: 'left',
        }}
      >
        <svg viewBox="0 0 24 24" width={13} height={13} stroke={ACCENT} fill="none" strokeWidth={1.7} strokeLinecap="round" style={{ flexShrink: 0 }}>
          <path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20z" />
          <path d="M2 12h20" />
          <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
        </svg>
        <span style={{ fontFamily: MONO, fontSize: 10.5, letterSpacing: '.12em', textTransform: 'uppercase', color: ACCENT }}>
          {sources.length === 0
            ? 'recherche en cours'
            : `${sources.length} source${sources.length > 1 ? 's' : ''}${live ? ' · en cours' : ''}`}
        </span>
        <span style={{
          fontFamily: MONO,
          fontSize: 10,
          color: '#8B93A7',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          minWidth: 0,
          flex: 1,
        }}>
          {domains.slice(0, 4).join(' · ')}{domains.length > 4 ? ` +${domains.length - 4}` : ''}
        </span>
        {live ? (
          <span style={{
            width: 7, height: 7, borderRadius: '50%', background: ACCENT, flexShrink: 0,
            animation: 'v4c-pulse 1s ease-in-out infinite',
          }} />
        ) : (
          <svg viewBox="0 0 24 24" width={12} height={12} stroke="#8B93A7" fill="none" strokeWidth={2} strokeLinecap="round"
            style={{ flexShrink: 0, transform: expanded ? 'rotate(180deg)' : 'none', transition: 'transform .2s' }}>
            <path d="m6 9 6 6 6-6" />
          </svg>
        )}
      </button>

      {expanded && (
        <div style={{ padding: '0 11px 11px', display: 'grid', gap: 8 }}>
          {queries.length > 0 && (
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {queries.map((query) => (
                <span key={query} style={{
                  fontFamily: MONO,
                  fontSize: 10,
                  padding: '3px 8px',
                  borderRadius: 999,
                  border: '1px solid rgba(255,255,255,.09)',
                  color: '#8B93A7',
                }}>
                  ⌕ {query}
                </span>
              ))}
            </div>
          )}

          {pages.map((source) => <PageRow key={source.id} source={source} />)}

          {images.length > 0 && (
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill,minmax(150px,1fr))',
              gap: 8,
            }}>
              {images.map((source) => (
                <MediaEmbed
                  key={source.id}
                  url={source.thumb || source.url}
                  title={source.title}
                  sourcePage={source.sourcePage}
                  kind="image"
                />
              ))}
            </div>
          )}

          {videos.map((source) => (
            <MediaEmbed key={source.id} url={source.url} title={source.title} kind="videoEmbed" />
          ))}
        </div>
      )}
    </div>
  )
}
