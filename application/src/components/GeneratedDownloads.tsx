import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Download, X, FileImage, FileVideo, FileAudio, Boxes, FileText } from 'lucide-react'
import { getBridgeUrl } from '../utils/runtime.ts'

type GeneratedFile = {
  name: string
  path: string
  kind: 'image' | 'video' | 'audio' | '3d' | 'other'
  size?: number
  mtime?: number
}

function iconFor(kind: GeneratedFile['kind']) {
  switch (kind) {
    case 'image': return FileImage
    case 'video': return FileVideo
    case 'audio': return FileAudio
    case '3d':    return Boxes
    default:      return FileText
  }
}

async function fetchGenerated(): Promise<GeneratedFile[]> {
  // getBridgeUrl() returns '' on Tauri/Cloud (relative URL → Vite proxy / tunnel)
  // and 'http://127.0.0.1:3001' only for browser-on-the-PC. Mobile via tunnel
  // MUST use relative URLs because 'localhost' on the phone points to the phone.
  const base = getBridgeUrl()
  try {
    const res = await fetch(`${base}/api/generated-files`, { credentials: 'omit' })
    if (!res.ok) return []
    const data = await res.json()
    if (Array.isArray(data?.files)) return data.files as GeneratedFile[]
    if (Array.isArray(data)) return data as GeneratedFile[]
  } catch { /* bridge off */ }
  return []
}

function formatSize(bytes?: number) {
  if (!bytes || bytes <= 0) return ''
  if (bytes < 1024) return `${bytes} o`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} Ko`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} Go`
}

// v82k4 : renomme MangaDownloads -> GeneratedDownloads. Le composant n'a
// jamais été skin-spécifique — il affiche les fichiers /api/generated-files
// du bridge quel que soit le skin actif.
export default function GeneratedDownloads() {
  const [open, setOpen] = useState(false)
  const [files, setFiles] = useState<GeneratedFile[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    let alive = true
    setLoading(true)
    setError(null)
    fetchGenerated()
      .then((list) => { if (alive) setFiles(list) })
      .catch((e: unknown) => { if (alive) setError(e instanceof Error ? e.message : 'Erreur') })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [open])

  const base = getBridgeUrl()

  return (
    <>
      <button
        type="button"
        className="manga-downloads-btn"
        onClick={() => setOpen((v) => !v)}
        title="Télécharger un fichier généré"
      >
        <Download size={14} strokeWidth={2.4} />
        Télécharger
      </button>

      <AnimatePresence>
        {open && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.18 }}
              className="fixed inset-0 z-[90]"
              style={{ background: 'rgba(26, 20, 13, 0.35)' }}
              onClick={() => setOpen(false)}
            />
            <motion.aside
              initial={{ x: '100%' }}
              animate={{ x: 0 }}
              exit={{ x: '100%' }}
              transition={{ type: 'spring', stiffness: 320, damping: 32 }}
              className="manga-downloads-panel"
            >
              <header className="manga-downloads-head">
                <span className="manga-downloads-title">Fichiers générés</span>
                <button
                  type="button"
                  className="manga-downloads-close"
                  onClick={() => setOpen(false)}
                  title="Fermer"
                >
                  <X size={14} strokeWidth={2.4} />
                </button>
              </header>

              <div className="manga-downloads-body">
                {loading && <div className="manga-downloads-empty">Chargement…</div>}
                {!loading && error && (
                  <div className="manga-downloads-empty">
                    <strong>Bridge indisponible.</strong>
                    <p>Lance <code>bridge_server.py</code> pour lister tes créations.</p>
                  </div>
                )}
                {!loading && !error && files.length === 0 && (
                  <div className="manga-downloads-empty">
                    Aucun fichier généré pour l'instant.<br />
                    Crée dans Image, Vidéo, 3D, Dessin ou Voix — tout apparaît ici.
                  </div>
                )}
                {!loading && files.length > 0 && (
                  <ul className="manga-downloads-list">
                    {files.map((f) => {
                      const Icon = iconFor(f.kind)
                      const downloadUrl = `${base}/api/download/${encodeURIComponent(f.path)}`
                      return (
                        <li key={f.path} className="manga-downloads-row">
                          <span className="manga-downloads-kind"><Icon size={14} strokeWidth={2.4} /></span>
                          <span className="manga-downloads-name" title={f.path}>{f.name || f.path}</span>
                          <span className="manga-downloads-size">{formatSize(f.size)}</span>
                          <a
                            className="manga-download-cta"
                            href={downloadUrl}
                            target="_blank"
                            rel="noreferrer"
                            download
                          >
                            <Download size={11} strokeWidth={2.4} /> ZIP
                          </a>
                        </li>
                      )
                    })}
                  </ul>
                )}
              </div>
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  )
}
