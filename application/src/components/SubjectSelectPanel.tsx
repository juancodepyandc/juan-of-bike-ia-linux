import { useEffect, useRef, useState } from 'react'

/**
 * 31/07 (demande Juan): sur la photo jointe, pouvoir isoler le sujet —
 * automatiquement, d'un CLIC sur l'objet, ou d'un CADRE trace a la main
 * (le plus fiable en cas d'echec de la reconnaissance). Le resultat
 * (PNG detoure a fond transparent) remplace la photo dans les pieces
 * jointes: meme circuit, aucune surprise.
 */
interface Props {
  file: File
  bridgeUrl: string
  onReplaced: (nouveau: File) => void
  onClose: () => void
}

type Mode = 'clic' | 'cadre' | 'auto'

export default function SubjectSelectPanel({ file, bridgeUrl, onReplaced, onClose }: Props) {
  const [mode, setMode] = useState<Mode>('clic')
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState('')
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [resultUrl, setResultUrl] = useState<string | null>(null)
  const [stagedPath, setStagedPath] = useState<string | null>(null)
  const dragStart = useRef<{ x: number; y: number } | null>(null)
  const [dragBox, setDragBox] = useState<{ x0: number; y0: number; x1: number; y1: number } | null>(null)
  const imgRef = useRef<HTMLImageElement | null>(null)

  useEffect(() => {
    const url = URL.createObjectURL(file)
    setPreviewUrl(url)
    // la photo doit exister sur disque pour le service Python: on la stage
    // via le meme endpoint d'upload que les pieces jointes
    const fd = new FormData()
    fd.append('file', file, file.name)
    fetch(`${bridgeUrl}/api/upload`, { method: 'POST', body: fd })
      .then((r) => r.json())
      .then((d) => { if (d?.path) setStagedPath(d.path) })
      .catch(() => setStatus('Impossible de preparer la photo (bridge).'))
    return () => URL.revokeObjectURL(url)
  }, [file, bridgeUrl])

  const lancer = async (payload: Record<string, unknown>) => {
    if (!stagedPath) { setStatus('Photo pas encore prete, reessaie dans une seconde.'); return }
    setBusy(true)
    setStatus(mode === 'auto' ? 'Detourage automatique...' : 'Segmentation du sujet...')
    try {
      const resp = await fetch(`${bridgeUrl}/api/3d/select-subject`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image_path: stagedPath, ...payload }),
      })
      const data = await resp.json()
      if (!data?.ok) { setStatus(`Echec: ${data?.error || resp.status}`); return }
      setResultUrl(`${bridgeUrl}${data.url}`)
      setStatus(data.note || `Sujet isole (${data.mode}). Verifie puis valide.`)
    } catch (e) {
      setStatus(`Erreur: ${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setBusy(false)
    }
  }

  const surClic = (e: React.MouseEvent<HTMLImageElement>) => {
    const img = imgRef.current
    if (!img || busy) return
    const r = img.getBoundingClientRect()
    const x = (e.clientX - r.left) / r.width
    const y = (e.clientY - r.top) / r.height
    if (mode === 'clic') {
      void lancer({ clic: [x, y] })
    } else if (mode === 'cadre') {
      if (!dragStart.current) {
        dragStart.current = { x, y }
        setDragBox({ x0: x, y0: y, x1: x, y1: y })
        setStatus('Coin pose — clique le coin oppose du cadre.')
      } else {
        const d = dragStart.current
        dragStart.current = null
        setDragBox({ x0: d.x, y0: d.y, x1: x, y1: y })
        void lancer({ cadre: [d.x, d.y, x, y] })
      }
    }
  }

  const valider = async () => {
    if (!resultUrl) return
    const blob = await fetch(resultUrl).then((r) => r.blob())
    const nom = file.name.replace(/\.[^.]+$/, '') + '_sujet.png'
    onReplaced(new File([blob], nom, { type: 'image/png' }))
    onClose()
  }

  return (
    <div className="fixed inset-0 z-[230] flex items-center justify-center bg-black/70 backdrop-blur-sm" onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div className="w-full max-w-2xl mx-4 rounded-2xl border border-aurora-accent/25 bg-[#0d0e12] p-5">
        <p className="text-xs uppercase tracking-[0.18em] text-aurora-accent-light mb-1">Isoler le sujet — {file.name}</p>
        <p className="mb-3 text-[12px] text-white/50">Clic = pointe l objet a garder. Cadre = deux clics (coins opposes), le plus fiable. Auto = detourage du sujet principal. Sans action, la photo entiere part telle quelle.</p>
        <div className="mb-3 flex gap-2">
          {(['clic', 'cadre', 'auto'] as Mode[]).map((m) => (
            <button key={m} onClick={() => { setMode(m); dragStart.current = null; setDragBox(null); if (m === 'auto') void lancer({}) }}
              className={`rounded-xl px-3 py-1.5 text-xs transition-colors ${mode === m ? 'gradient-accent text-white' : 'border border-aurora-border/40 bg-aurora-surface-2/60 text-aurora-text/80'}`}>
              {m === 'clic' ? 'Clic sur l objet' : m === 'cadre' ? 'Cadre manuel' : 'Auto'}
            </button>
          ))}
        </div>
        <div className="relative mb-3 flex max-h-[46vh] items-center justify-center overflow-hidden rounded-xl bg-black/40">
          {previewUrl && (
            <img ref={imgRef} src={resultUrl || previewUrl} alt="photo"
              onClick={surClic}
              className={`max-h-[46vh] max-w-full object-contain ${mode !== 'auto' && !busy ? 'cursor-crosshair' : ''}`} />
          )}
          {dragBox && !resultUrl && (
            <div className="pointer-events-none absolute border-2 border-aurora-accent/80"
              style={{
                left: `${Math.min(dragBox.x0, dragBox.x1) * 100}%`,
                top: `${Math.min(dragBox.y0, dragBox.y1) * 100}%`,
                width: `${Math.abs(dragBox.x1 - dragBox.x0) * 100}%`,
                height: `${Math.abs(dragBox.y1 - dragBox.y0) * 100}%`,
              }} />
          )}
        </div>
        {status && <p className="mb-3 text-xs text-aurora-text-muted">{busy ? '⏳ ' : ''}{status}</p>}
        <div className="flex gap-2">
          <button onClick={() => { setResultUrl(null); setDragBox(null); dragStart.current = null; setStatus('') }}
            disabled={!resultUrl}
            className="flex-1 rounded-xl border border-aurora-border/40 px-3 py-2 text-xs text-aurora-text/70 disabled:opacity-40">Recommencer</button>
          <button onClick={() => void valider()} disabled={!resultUrl || busy}
            className={`flex-1 rounded-xl px-3 py-2 text-xs ${resultUrl && !busy ? 'gradient-accent text-white' : 'bg-aurora-surface-2 text-aurora-text-dim opacity-50'}`}>Utiliser cette selection</button>
          <button onClick={onClose} className="flex-1 rounded-xl border border-aurora-border/40 px-3 py-2 text-xs text-aurora-text/70">Garder la photo entiere</button>
        </div>
      </div>
    </div>
  )
}
