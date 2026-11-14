import { useCallback, useEffect, useMemo, useState } from 'react'
import { getBridgeUrl } from '../utils/runtime.ts'

/**
 * Bibliothèque 3D par génération. La vue 3D n'offrait qu'un sélecteur de fichier brut pour rouvrir
 * un modèle, et la liste du pont montrait chaque génération sous quatre fichiers aux noms
 * identiques d'un projet à l'autre. Ici : une carte par génération, avec sa demande comme titre, son
 * aperçu, son livrable par défaut (l'animé s'il existe) et ses variantes nommées.
 */
export type ThreeDVariant = { role: string; nom: string; url: string; octets: number }
export type ThreeDProject = {
  id: string
  dossier: string
  titre: string
  modifie: number
  livrable: ThreeDVariant
  anime: boolean
  variantes: ThreeDVariant[]
  vignette: string | null
}

const absolute = (url: string) => (/^https?:/i.test(url) ? url : `${getBridgeUrl()}${url}`)

function when(seconds: number): string {
  const delta = Date.now() / 1000 - seconds
  if (delta < 3600) return `il y a ${Math.max(1, Math.round(delta / 60))} min`
  if (delta < 86400) return `il y a ${Math.round(delta / 3600)} h`
  if (delta < 7 * 86400) return `il y a ${Math.round(delta / 86400)} j`
  return new Date(seconds * 1000).toLocaleDateString('fr-FR')
}

const size = (bytes: number) => (bytes >= 1024 ** 2 ? `${(bytes / 1024 ** 2).toFixed(1)} Mo` : `${Math.round(bytes / 1024)} Ko`)

/** Filtre plein texte, insensible aux accents et à la casse. */
export function filterProjects(projects: ThreeDProject[], query: string): ThreeDProject[] {
  const norm = (text: string) => text.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
  const words = norm(query).split(/\s+/).filter(Boolean)
  if (!words.length) return projects
  return projects.filter((project) => {
    const haystack = norm(`${project.titre} ${project.dossier}`)
    return words.every((word) => haystack.includes(word))
  })
}

export default function ThreeDLibraryPanel({
  activeUrl,
  onOpen,
  refreshToken,
}: {
  activeUrl: string | null
  onOpen: (url: string, project: ThreeDProject, variant: ThreeDVariant) => void
  /** change à chaque génération terminée pour relire la bibliothèque */
  refreshToken?: unknown
}) {
  const [projects, setProjects] = useState<ThreeDProject[]>([])
  const [query, setQuery] = useState('')
  const [onlyAnimated, setOnlyAnimated] = useState(false)
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading')
  const [open, setOpen] = useState(true)

  const load = useCallback(async () => {
    setState('loading')
    try {
      const response = await fetch(`${getBridgeUrl()}/api/3d/projects`)
      if (!response.ok) throw new Error(String(response.status))
      const body = await response.json() as { projets?: ThreeDProject[] }
      setProjects(Array.isArray(body.projets) ? body.projets : [])
      setState('ready')
    } catch {
      setState('error')
    }
  }, [])

  useEffect(() => { void load() }, [load, refreshToken])

  const shown = useMemo(
    () => filterProjects(projects, query).filter((project) => !onlyAnimated || project.anime),
    [projects, query, onlyAnimated],
  )

  return (
    <section aria-label="Mes modèles 3D" className="mx-3 mb-3 rounded-2xl border border-aurora-border/40 bg-aurora-surface/40">
      <header className="flex flex-wrap items-center gap-2 px-4 py-3">
        <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open}
          className="text-sm font-semibold text-aurora-text">
          {open ? '▾' : '▸'} Mes modèles <span className="text-aurora-text-muted font-normal">({projects.length})</span>
        </button>
        {open && (
          <>
            <input type="search" value={query} onChange={(event) => setQuery(event.target.value)}
              placeholder="Chercher une génération (coffre, vase…)"
              className="ml-auto min-h-9 w-full max-w-xs rounded-lg border border-aurora-border/50 bg-transparent px-3 text-sm text-aurora-text sm:w-64" />
            <label className="flex items-center gap-1 text-xs text-aurora-text-muted">
              <input type="checkbox" checked={onlyAnimated} onChange={(event) => setOnlyAnimated(event.target.checked)} />
              animés seulement
            </label>
            <button type="button" onClick={() => void load()} className="min-h-9 rounded-lg border border-aurora-border/50 px-3 text-xs text-aurora-text-muted hover:text-aurora-text">
              Actualiser
            </button>
          </>
        )}
      </header>
      {open && (
        <div className="max-h-[26rem] overflow-y-auto px-4 pb-4">
          {state === 'loading' && <p className="text-xs text-aurora-text-muted">Lecture de la bibliothèque…</p>}
          {state === 'error' && <p className="text-xs text-rose-300">Bibliothèque injoignable (pont 3001). Le sélecteur de fichier reste disponible.</p>}
          {state === 'ready' && shown.length === 0 && (
            <p className="text-xs text-aurora-text-muted">{projects.length ? 'Aucune génération ne correspond.' : 'Aucune génération 3D pour l’instant.'}</p>
          )}
          <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
            {shown.map((project) => {
              const isActive = Boolean(activeUrl && project.variantes.some((v) => activeUrl.endsWith(v.url)))
              return (
                <li key={project.id} className={`overflow-hidden rounded-xl border ${isActive ? 'border-aurora-accent' : 'border-aurora-border/40'} bg-black/20`}>
                  <button type="button" title={`Ouvrir « ${project.titre} » — ${project.livrable.role}`}
                    onClick={() => onOpen(absolute(project.livrable.url), project, project.livrable)}
                    className="block w-full text-left">
                    <div className="aspect-[4/3] w-full bg-[#0b1218]">
                      {project.vignette
                        ? <img src={absolute(project.vignette)} alt="" loading="lazy" className="h-full w-full object-contain" />
                        : <div className="flex h-full items-center justify-center text-2xl text-aurora-text-muted">◇</div>}
                    </div>
                    <div className="px-2 pt-2">
                      <p className="line-clamp-2 text-xs font-medium text-aurora-text">{project.titre}</p>
                      <p className="mt-0.5 text-[10px] text-aurora-text-muted">
                        {when(project.modifie)}{project.anime ? ' · animé' : ''} · {size(project.livrable.octets)}
                      </p>
                    </div>
                  </button>
                  {project.variantes.length > 1 && (
                    <div className="flex flex-wrap gap-1 px-2 pb-2 pt-1">
                      {project.variantes.map((variant) => (
                        <button key={variant.url} type="button" title={`${variant.nom} · ${size(variant.octets)}`}
                          onClick={() => onOpen(absolute(variant.url), project, variant)}
                          className={`rounded-md border px-1.5 py-0.5 text-[10px] ${activeUrl?.endsWith(variant.url) ? 'border-aurora-accent text-aurora-accent' : 'border-aurora-border/40 text-aurora-text-muted hover:text-aurora-text'}`}>
                          {variant.role}
                        </button>
                      ))}
                    </div>
                  )}
                </li>
              )
            })}
          </ul>
        </div>
      )}
    </section>
  )
}
