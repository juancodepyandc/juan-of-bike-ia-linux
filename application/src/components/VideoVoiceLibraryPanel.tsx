import { useCallback, useEffect, useRef, useState, type CSSProperties } from 'react'
import { Loader2, Mic2, Play, RefreshCw, Trash2, Upload, X } from 'lucide-react'
import {
  cinemaAssetUrl,
  cinemaJobStatus,
  voiceLibraryDelete,
  voiceLibraryList,
  voiceRegister,
  voiceSynthesize,
  type VoiceLibraryEntry,
} from '../services/cinemaApi'

type Props = {
  accent?: string
  engineName?: string
  engineReady?: boolean
}

type AsyncVoiceResult = {
  ok?: boolean
  error?: string
  wav?: string
  path?: string
  outputPath?: string
  audio_quality?: VoiceLibraryEntry['reference_audio']
}

function fileAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(reader.error || new Error('lecture du fichier impossible'))
    reader.onload = () => {
      const value = String(reader.result || '')
      const separator = value.indexOf(',')
      resolve(separator >= 0 ? value.slice(separator + 1) : value)
    }
    reader.readAsDataURL(file)
  })
}

function qualityLabel(voice: VoiceLibraryEntry): string {
  const score = voice.reference_quality_score
  if (typeof score !== 'number') return 'qualité N/A'
  const snr = voice.reference_audio?.estimated_snr_db
  return `réf ${Math.round(score * 100)} %${typeof snr === 'number' ? ` · S/B ${snr.toFixed(0)} dB` : ''}`
}

export default function VideoVoiceLibraryPanel({
  accent = '#F59E0B',
  engineName = 'cosyvoice3-0.5b-2512',
  engineReady = false,
}: Props) {
  const [open, setOpen] = useState(false)
  const [voices, setVoices] = useState<VoiceLibraryEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)
  const [message, setMessage] = useState<string>('')
  const [error, setError] = useState<string>('')
  const [character, setCharacter] = useState('')
  const [lang, setLang] = useState<'fr' | 'en'>('fr')
  const [transcript, setTranscript] = useState('')
  const [previewText, setPreviewText] = useState('Bonjour, ceci est un essai de ma voix.')
  const [previewUrl, setPreviewUrl] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)
  const aliveRef = useRef(true)

  useEffect(() => {
    aliveRef.current = true
    return () => { aliveRef.current = false }
  }, [])

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      setVoices(await voiceLibraryList())
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (open) void refresh()
  }, [open, refresh])

  const awaitJob = useCallback(async (jobId: string): Promise<AsyncVoiceResult> => {
    const deadline = Date.now() + 8 * 60 * 60 * 1000
    while (Date.now() < deadline && aliveRef.current) {
      const job = await cinemaJobStatus(jobId)
      setMessage(
        job.status === 'queued'
          ? 'En attente dans la file GPU…'
          : job.status === 'running'
            ? 'Traitement vocal en cours…'
            : `État : ${job.status}`,
      )
      if (job.status === 'done') {
        const result = (job.result || {}) as AsyncVoiceResult
        if (result.ok === false) throw new Error(result.error || 'traitement vocal non validé')
        return result
      }
      if (job.status === 'failed' || job.status === 'cancelled') {
        throw new Error(job.error || `job vocal ${job.status}`)
      }
      await new Promise((resolve) => window.setTimeout(resolve, 1500))
    }
    throw new Error(aliveRef.current ? 'timeout du traitement vocal' : 'panneau fermé')
  }, [])

  const importReference = useCallback(async (file: File) => {
    if (!character.trim()) {
      setError('Donnez un nom au personnage.')
      return
    }
    setBusy('register')
    setError('')
    setMessage('Envoi et analyse acoustique de la référence…')
    try {
      const wavBase64 = await fileAsBase64(file)
      const spawn = await voiceRegister({
        character: character.trim(),
        lang,
        source: `import:${file.name}`,
        transcript: transcript.trim(),
        wavBase64,
      })
      if (!spawn.jobId) throw new Error(spawn.error || 'job d’enregistrement absent')
      const result = await awaitJob(spawn.jobId)
      const score = result.audio_quality?.quality_score
      setMessage(
        typeof score === 'number'
          ? `Référence validée · qualité acoustique ${Math.round(score * 100)} %.`
          : 'Référence validée.',
      )
      await refresh()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    } finally {
      setBusy(null)
    }
  }, [awaitJob, character, lang, refresh, transcript])

  const preview = useCallback(async (voice: VoiceLibraryEntry) => {
    if (!previewText.trim()) {
      setError('Saisissez un texte d’essai.')
      return
    }
    setBusy(`preview:${voice.slug}`)
    setError('')
    setPreviewUrl('')
    try {
      const spawn = await voiceSynthesize({
        character: voice.character,
        text: previewText.trim(),
        lang: voice.lang || lang,
      })
      if (!spawn.jobId) throw new Error(spawn.error || 'job de synthèse absent')
      const result = await awaitJob(spawn.jobId)
      const path = result.wav || result.path || result.outputPath || spawn.outputPath
      if (!path) throw new Error('synthèse terminée sans WAV')
      setPreviewUrl(cinemaAssetUrl(path))
      setMessage('Essai vocal prêt.')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    } finally {
      setBusy(null)
    }
  }, [awaitJob, lang, previewText])

  const remove = useCallback(async (voice: VoiceLibraryEntry) => {
    setBusy(`delete:${voice.slug}`)
    setError('')
    try {
      await voiceLibraryDelete(voice.slug)
      setMessage(`${voice.character} supprimé de la bibliothèque.`)
      await refresh()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    } finally {
      setBusy(null)
    }
  }, [refresh])

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        style={{
          border: `1px solid ${accent}66`,
          background: `${accent}16`,
          color: accent,
          borderRadius: 10,
          padding: '7px 10px',
          cursor: 'pointer',
          display: 'inline-flex',
          gap: 7,
          alignItems: 'center',
          fontSize: 12,
          fontWeight: 700,
        }}
      >
        <Mic2 size={14} /> Bibliothèque de voix
      </button>

      {open && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Bibliothèque de voix vidéo"
          onClick={(event) => { if (event.target === event.currentTarget) setOpen(false) }}
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 100,
            background: 'rgba(3,7,18,.78)',
            backdropFilter: 'blur(6px)',
            display: 'flex',
            justifyContent: 'flex-end',
          }}
        >
          <section style={{
            width: 'min(480px,100vw)',
            height: '100vh',
            overflowY: 'auto',
            background: '#0B1020',
            color: '#E5E7EB',
            borderLeft: '1px solid rgba(255,255,255,.12)',
            padding: 18,
          }}>
            <header style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 15, fontWeight: 800 }}>Bibliothèque de voix</div>
                <div style={{ marginTop: 3, fontSize: 11, color: '#94A3B8' }}>
                  {engineName} · {engineReady ? 'moteur prêt' : 'moteur à provisionner'}
                </div>
              </div>
              <button type="button" onClick={() => void refresh()} title="Actualiser" style={iconButton}>
                {loading ? <Loader2 size={15} className="animate-spin" /> : <RefreshCw size={15} />}
              </button>
              <button type="button" onClick={() => setOpen(false)} title="Fermer" style={iconButton}>
                <X size={16} />
              </button>
            </header>

            {!engineReady && (
              <div style={{ ...notice, borderColor: '#F59E0B55', color: '#FCD34D' }}>
                Les références peuvent être préparées maintenant. La synthèse clonée attend le venv et les poids CosyVoice3.
              </div>
            )}
            {message && <div style={notice}>{message}</div>}
            {error && <div style={{ ...notice, borderColor: '#EF444466', color: '#FCA5A5' }}>{error}</div>}

            <h3 style={heading}>Importer une référence personnelle</h3>
            <p style={help}>
              Idéal : 5–30 s, une seule voix, peu de silence et aucune musique. Le fichier est converti en mono 16 kHz puis mesuré ; une référence muette ou fortement saturée est refusée.
            </p>
            <div style={stack}>
              <input value={character} onChange={(event) => setCharacter(event.target.value)} placeholder="Nom du personnage" style={input} />
              <div style={{ display: 'flex', gap: 6 }}>
                {(['fr', 'en'] as const).map((item) => (
                  <button key={item} type="button" onClick={() => setLang(item)} style={{
                    ...smallButton,
                    borderColor: lang === item ? accent : 'rgba(255,255,255,.14)',
                    color: lang === item ? accent : '#94A3B8',
                  }}>
                    {item.toUpperCase()}
                  </button>
                ))}
              </div>
              <textarea
                value={transcript}
                onChange={(event) => setTranscript(event.target.value)}
                placeholder="Transcription exacte de la référence (fortement recommandée)"
                rows={3}
                style={{ ...input, resize: 'vertical' }}
              />
              <input
                ref={fileRef}
                type="file"
                accept="audio/*,.wav,.mp3,.m4a,.flac,.ogg"
                hidden
                onChange={(event) => {
                  const file = event.target.files?.[0]
                  if (file) void importReference(file)
                  event.target.value = ''
                }}
              />
              <button
                type="button"
                disabled={Boolean(busy)}
                onClick={() => fileRef.current?.click()}
                style={{ ...primaryButton, background: accent }}
              >
                {busy === 'register' ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
                Choisir le fichier audio
              </button>
            </div>

            <h3 style={heading}>Voix enregistrées</h3>
            <input value={previewText} onChange={(event) => setPreviewText(event.target.value)} style={input} aria-label="Texte d’essai vocal" />
            <div style={{ ...stack, marginTop: 9 }}>
              {voices.length === 0 && !loading && <div style={help}>Aucune référence enregistrée.</div>}
              {voices.map((voice) => (
                <article key={voice.slug} style={voiceCard}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 12.5, fontWeight: 750 }}>{voice.character}</div>
                    <div style={{ marginTop: 3, fontSize: 10.5, color: '#94A3B8' }}>
                      {voice.lang.toUpperCase()} · {voice.duration_s ? `${voice.duration_s.toFixed(1)} s` : 'durée N/A'} · {qualityLabel(voice)}
                      {voice.has_transcript ? ' · transcription exacte' : ' · transcription à compléter'}
                    </div>
                    {(voice.reference_audio?.warnings?.length ?? 0) > 0 && (
                      <div style={{ marginTop: 3, fontSize: 10, color: '#FCD34D' }}>
                        {voice.reference_audio?.warnings?.join(' · ')}
                      </div>
                    )}
                  </div>
                  <button
                    type="button"
                    disabled={Boolean(busy) || !engineReady}
                    onClick={() => void preview(voice)}
                    title={engineReady ? 'Écouter un essai cloné' : 'CosyVoice3 non prêt'}
                    style={iconButton}
                  >
                    {busy === `preview:${voice.slug}` ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
                  </button>
                  <button
                    type="button"
                    disabled={Boolean(busy)}
                    onClick={() => void remove(voice)}
                    title={`Supprimer ${voice.character}`}
                    style={iconButton}
                  >
                    <Trash2 size={14} />
                  </button>
                </article>
              ))}
            </div>
            {previewUrl && <audio src={previewUrl} controls autoPlay style={{ width: '100%', marginTop: 14 }} />}
          </section>
        </div>
      )}
    </>
  )
}

const stack: CSSProperties = { display: 'grid', gap: 8 }
const heading: CSSProperties = { margin: '20px 0 7px', fontSize: 12, letterSpacing: '.04em' }
const help: CSSProperties = { margin: '0 0 9px', color: '#94A3B8', fontSize: 11, lineHeight: 1.5 }
const input: CSSProperties = {
  width: '100%',
  boxSizing: 'border-box',
  border: '1px solid rgba(255,255,255,.14)',
  background: 'rgba(255,255,255,.045)',
  color: '#E5E7EB',
  borderRadius: 8,
  padding: '8px 9px',
  font: 'inherit',
  fontSize: 12,
}
const notice: CSSProperties = {
  marginTop: 12,
  padding: '8px 10px',
  border: '1px solid rgba(148,163,184,.28)',
  borderRadius: 8,
  color: '#CBD5E1',
  fontSize: 11,
  lineHeight: 1.45,
}
const iconButton: CSSProperties = {
  border: '1px solid rgba(255,255,255,.14)',
  background: 'rgba(255,255,255,.05)',
  color: '#CBD5E1',
  borderRadius: 8,
  width: 32,
  height: 32,
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  cursor: 'pointer',
}
const smallButton: CSSProperties = {
  border: '1px solid rgba(255,255,255,.14)',
  background: 'rgba(255,255,255,.04)',
  borderRadius: 7,
  padding: '5px 9px',
  cursor: 'pointer',
}
const primaryButton: CSSProperties = {
  border: 0,
  color: '#08101F',
  borderRadius: 8,
  padding: '9px 11px',
  display: 'inline-flex',
  justifyContent: 'center',
  alignItems: 'center',
  gap: 7,
  cursor: 'pointer',
  fontWeight: 800,
}
const voiceCard: CSSProperties = {
  display: 'flex',
  gap: 8,
  alignItems: 'center',
  border: '1px solid rgba(255,255,255,.11)',
  background: 'rgba(255,255,255,.035)',
  borderRadius: 9,
  padding: '9px 10px',
}
