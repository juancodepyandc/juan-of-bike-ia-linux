import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ArrowLeft, Check, Download, Loader2, Music, Pause, Play, RefreshCw, Sparkles, Upload, Volume2 } from 'lucide-react'
import {
  createMusic,
  importMusicVoice,
  listMusicExports,
  listMusicVoices,
  musicStatus,
  readMusicJob,
  resolveMusicAsset,
  type MusicDraft,
  type MusicEngineStatus,
  type MusicJob,
  type MusicVoice,
} from '../../services/musicStudio.ts'

type MusicStudioProps = { onClose: () => void }

type ExportedTrack = {
  filename: string
  url: string
  modified?: number
  metadata?: Record<string, unknown>
}

const STYLE_PRESETS = [
  { label: 'Cinématique', value: 'cinematic orchestral score, evolving strings, intimate piano, wide dynamics, polished mix' },
  { label: 'Électro', value: 'modern electronic pop, warm analogue synths, memorable hook, tight drums, clean stereo production' },
  { label: 'Rap / R&B', value: 'contemporary R&B and melodic rap, deep sub bass, sparse drums, nocturnal atmosphere, polished vocal space' },
  { label: 'Acoustique', value: 'intimate acoustic folk, fingerpicked guitar, natural room, warm bass, human dynamics, refined master' },
  { label: 'Club', value: 'driving melodic house, punchy kick, focused bassline, rising tension, modern festival mix' },
  { label: 'Ambiance', value: 'immersive ambient soundscape, evolving pads, subtle textures, spacious mix, no percussion' },
]

const INPUT_CLASS = 'w-full rounded-xl border border-white/10 bg-black/25 px-3 py-2 text-sm text-white/90 outline-none transition placeholder:text-white/25 focus:border-cyan-300/50 focus:bg-black/35'

function formatWhen(timestamp?: number): string {
  if (!timestamp) return ''
  return new Date(timestamp * 1000).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' })
}

export default function MusicStudio({ onClose }: MusicStudioProps) {
  const [status, setStatus] = useState<MusicEngineStatus | null>(null)
  const [voices, setVoices] = useState<MusicVoice[]>([])
  const [exports, setExports] = useState<ExportedTrack[]>([])
  const [title, setTitle] = useState('')
  const [prompt, setPrompt] = useState(STYLE_PRESETS[0].value)
  const [lyrics, setLyrics] = useState('')
  const [mode, setMode] = useState<MusicDraft['mode']>('instrumental')
  const [duration, setDuration] = useState(45)
  const [bpm, setBpm] = useState(110)
  const [key, setKey] = useState('')
  const [timeSignature, setTimeSignature] = useState('4')
  const [language, setLanguage] = useState('fr')
  const [quality, setQuality] = useState<MusicDraft['quality']>('studio')
  const [voiceSlug, setVoiceSlug] = useState('')
  const [job, setJob] = useState<MusicJob | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [voiceFile, setVoiceFile] = useState<File | null>(null)
  const [voiceName, setVoiceName] = useState('')
  const [voiceConsent, setVoiceConsent] = useState(false)
  const [voiceImporting, setVoiceImporting] = useState(false)
  const [voiceImportMessage, setVoiceImportMessage] = useState('')
  const [playing, setPlaying] = useState<string | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  const canCreate = Boolean(status?.ready && prompt.trim() && (mode === 'instrumental' || lyrics.trim()))
  const currentUrl = job?.status === 'completed' ? job.audio_url : undefined

  const loadLibrary = useCallback(async () => {
    const [voiceResult, exportResult] = await Promise.all([listMusicVoices(), listMusicExports()])
    setVoices(voiceResult.voices || [])
    setExports(exportResult.files || [])
  }, [])

  const refresh = useCallback(async (silent = false) => {
    if (!silent) setRefreshing(true)
    setError('')
    try {
      const nextStatus = await musicStatus()
      setStatus(nextStatus)
      await loadLibrary()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Le studio ne répond pas.')
    } finally {
      setLoading(false)
      if (!silent) setRefreshing(false)
    }
  }, [loadLibrary])

  useEffect(() => { void refresh() }, [refresh])

  useEffect(() => {
    if (!job || !['queued', 'running'].includes(job.status)) return
    const timer = window.setInterval(() => {
      void readMusicJob(job.id)
        .then((next) => {
          setJob(next)
          if (next.status === 'completed') void loadLibrary()
        })
        .catch((cause) => setError(cause instanceof Error ? cause.message : 'Suivi de la composition impossible.'))
    }, 1700)
    return () => window.clearInterval(timer)
  }, [job?.id, job?.status, loadLibrary])

  useEffect(() => () => {
    try { audioRef.current?.pause() } catch { /* no-op */ }
  }, [])

  const selectedVoice = useMemo(() => voices.find((voice) => voice.slug === voiceSlug), [voiceSlug, voices])

  const create = async () => {
    if (!canCreate) return
    setError('')
    try {
      const next = await createMusic({
        title: title.trim() || 'Piste sans titre',
        prompt: prompt.trim(),
        lyrics: lyrics.trim(),
        mode,
        duration: Number(duration),
        bpm: Number(bpm),
        key: key.trim(),
        timeSignature,
        language,
        voiceSlug: voiceSlug || undefined,
        quality,
      })
      setJob(next)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'La composition n’a pas pu être lancée.')
    }
  }

  const importVoice = async () => {
    if (!voiceFile || !voiceName.trim() || !voiceConsent || voiceImporting) return
    setVoiceImporting(true)
    setVoiceImportMessage('')
    setError('')
    try {
      const result = await importMusicVoice({ file: voiceFile, name: voiceName.trim(), language, consent: voiceConsent })
      if (!result.ok) throw new Error(result.error || 'Import impossible.')
      setVoiceImportMessage('Préparation en cours. La voix apparaîtra dans la liste dès que le contrôle audio est terminé.')
      setVoiceFile(null)
      setVoiceName('')
      setVoiceConsent(false)
      window.setTimeout(() => { void loadLibrary() }, 3000)
      window.setTimeout(() => { void loadLibrary() }, 9000)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Import impossible.')
    } finally {
      setVoiceImporting(false)
    }
  }

  const playTrack = (url: string) => {
    const fullUrl = resolveMusicAsset(url)
    if (playing === fullUrl) {
      audioRef.current?.pause()
      setPlaying(null)
      return
    }
    try { audioRef.current?.pause() } catch { /* no-op */ }
    const audio = new Audio(fullUrl)
    audioRef.current = audio
    audio.addEventListener('ended', () => setPlaying(null), { once: true })
    audio.play().then(() => setPlaying(fullUrl)).catch(() => setError('Lecture audio impossible sur cet appareil.'))
  }

  return (
    <div
      data-voice-panel="true"
      className="relative flex h-full min-h-0 flex-col overflow-hidden bg-[#05070d] text-white"
      style={{ backgroundImage: 'radial-gradient(circle at 10% 0%, rgba(45,212,191,.13), transparent 30%), radial-gradient(circle at 90% 10%, rgba(217,70,239,.12), transparent 28%)' }}
    >
      <audio ref={audioRef} className="hidden" />
      <header className="relative z-10 flex shrink-0 items-center gap-3 border-b border-white/[0.09] bg-black/20 px-4 py-3 backdrop-blur-xl">
        <button onClick={onClose} className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.05] px-2.5 py-1.5 text-xs text-white/65 hover:bg-white/[0.1] hover:text-white">
          <ArrowLeft size={14} /> Retour
        </button>
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Music size={17} className="text-cyan-300" />
            <h1 className="text-base font-semibold tracking-tight">Studio musique</h1>
          </div>
          <p className="mt-0.5 text-[10px] uppercase tracking-[0.16em] text-white/38">Composition · voix · exports</p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          {status && (
            <span className={`hidden rounded-full border px-2 py-1 text-[10px] sm:inline ${status.ready ? 'border-emerald-300/25 bg-emerald-400/10 text-emerald-200' : 'border-amber-300/25 bg-amber-400/10 text-amber-100'}`}>
              {status.ready ? 'Moteur prêt' : 'Moteur hors ligne'}
            </span>
          )}
          <button onClick={() => { void refresh() }} disabled={refreshing} title="Actualiser" className="rounded-lg border border-white/10 bg-white/[0.05] p-2 text-white/55 hover:text-white disabled:opacity-40">
            <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
          </button>
        </div>
      </header>

      <main className="relative z-10 min-h-0 flex-1 overflow-y-auto p-4 md:p-5">
        {loading ? (
          <div className="flex h-48 items-center justify-center gap-2 text-sm text-white/55"><Loader2 size={17} className="animate-spin text-cyan-300" />Ouverture du studio…</div>
        ) : (
          <div className="mx-auto grid max-w-6xl gap-4 lg:grid-cols-[minmax(0,1.45fr)_minmax(300px,.8fr)]">
            <section className="space-y-4">
              {!status?.ready && (
                <div className="rounded-2xl border border-amber-300/20 bg-amber-400/[0.07] p-4">
                  <div className="text-sm font-medium text-amber-100">Le moteur local est arrêté</div>
                  <p className="mt-1 text-xs leading-relaxed text-amber-100/65">Lance le service de composition local, puis actualise cette page. Aucun morceau n’est simulé : la création devient disponible dès que le moteur répond.</p>
                  {status?.error && <p className="mt-2 text-[11px] text-amber-200/70">{status.error}</p>}
                </div>
              )}

              <div className="rounded-2xl border border-white/[0.09] bg-white/[0.045] p-4 shadow-2xl shadow-black/20 backdrop-blur">
                <div className="mb-4 flex items-start justify-between gap-3">
                  <div>
                    <h2 className="text-sm font-semibold">Nouveau morceau</h2>
                    <p className="mt-1 text-xs text-white/45">Décris l’intention, garde le contrôle du rythme et conserve les versions réussies.</p>
                  </div>
                  <div className="flex rounded-lg border border-white/10 bg-black/20 p-0.5 text-[11px]">
                    {(['instrumental', 'song'] as const).map((item) => (
                      <button key={item} onClick={() => setMode(item)} className={`rounded-md px-2.5 py-1.5 transition ${mode === item ? 'bg-cyan-400/15 text-cyan-100' : 'text-white/45 hover:text-white/75'}`}>
                        {item === 'instrumental' ? 'Instrumental' : 'Chant'}
                      </button>
                    ))}
                  </div>
                </div>

                <label className="block text-[11px] font-medium text-white/60">Titre <span className="font-normal text-white/30">optionnel</span>
                  <input value={title} onChange={(event) => setTitle(event.target.value)} maxLength={100} placeholder="Ex. Nuit sur la côte" className={`${INPUT_CLASS} mt-1.5`} />
                </label>

                <div className="mt-4">
                  <div className="mb-2 flex items-center justify-between gap-3">
                    <label className="text-[11px] font-medium text-white/60">Direction musicale</label>
                    <span className="text-[10px] text-white/28">{prompt.length}/12000</span>
                  </div>
                  <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} maxLength={12000} rows={4} placeholder="Genre, instruments, énergie, ambiance, structure…" className={`${INPUT_CLASS} resize-y leading-relaxed`} />
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {STYLE_PRESETS.map((preset) => (
                      <button key={preset.label} onClick={() => setPrompt(preset.value)} className="rounded-full border border-white/10 bg-white/[0.035] px-2.5 py-1 text-[10px] text-white/55 transition hover:border-cyan-300/30 hover:bg-cyan-400/10 hover:text-cyan-100">{preset.label}</button>
                    ))}
                  </div>
                </div>

                {mode === 'song' && (
                  <div className="mt-4">
                    <div className="mb-2 flex items-center justify-between gap-3"><label className="text-[11px] font-medium text-white/60">Paroles</label><span className="text-[10px] text-white/28">Structure libre : couplet, refrain, pont…</span></div>
                    <textarea value={lyrics} onChange={(event) => setLyrics(event.target.value)} maxLength={12000} rows={8} placeholder={'[Couplet]\n…\n\n[Refrain]\n…'} className={`${INPUT_CLASS} resize-y font-mono text-xs leading-relaxed`} />
                  </div>
                )}

                <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
                  <label className="text-[10px] uppercase tracking-[0.12em] text-white/36">Durée
                    <input type="number" min="10" max="600" value={duration} onChange={(event) => setDuration(Math.max(10, Math.min(600, Number(event.target.value) || 10)))} className={`${INPUT_CLASS} mt-1 normal-case tracking-normal`} />
                  </label>
                  <label className="text-[10px] uppercase tracking-[0.12em] text-white/36">Tempo
                    <input type="number" min="30" max="300" value={bpm} onChange={(event) => setBpm(Math.max(30, Math.min(300, Number(event.target.value) || 30)))} className={`${INPUT_CLASS} mt-1 normal-case tracking-normal`} />
                  </label>
                  <label className="text-[10px] uppercase tracking-[0.12em] text-white/36">Tonalité
                    <input value={key} onChange={(event) => setKey(event.target.value)} placeholder="Am" maxLength={32} className={`${INPUT_CLASS} mt-1 normal-case tracking-normal`} />
                  </label>
                  <label className="text-[10px] uppercase tracking-[0.12em] text-white/36">Mesure
                    <select value={timeSignature} onChange={(event) => setTimeSignature(event.target.value)} className={`${INPUT_CLASS} mt-1 normal-case tracking-normal`}><option value="2">2/4</option><option value="3">3/4</option><option value="4">4/4</option><option value="6">6/8</option></select>
                  </label>
                </div>

                <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-white/[0.08] bg-black/[0.16] p-3">
                  <div>
                    <div className="text-[11px] font-medium text-white/65">Niveau de rendu</div>
                    <div className="mt-0.5 text-[10px] text-white/35">Le choix utilise le meilleur modèle déjà chargé, sans interrompre les autres travaux.</div>
                  </div>
                  <div className="flex rounded-lg border border-white/10 p-0.5 text-[11px]">
                    <button onClick={() => setQuality('preview')} className={`rounded-md px-2.5 py-1.5 ${quality === 'preview' ? 'bg-white/[0.12] text-white' : 'text-white/40 hover:text-white/70'}`}>Essai</button>
                    <button onClick={() => setQuality('studio')} className={`rounded-md px-2.5 py-1.5 ${quality === 'studio' ? 'bg-fuchsia-400/15 text-fuchsia-100' : 'text-white/40 hover:text-white/70'}`}>Studio</button>
                  </div>
                </div>

                <button onClick={() => { void create() }} disabled={!canCreate || job?.status === 'queued' || job?.status === 'running'} className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl border border-cyan-300/35 bg-gradient-to-r from-cyan-400/20 to-fuchsia-500/20 px-4 py-3 text-sm font-semibold text-cyan-50 transition hover:from-cyan-400/30 hover:to-fuchsia-500/30 disabled:cursor-not-allowed disabled:opacity-40">
                  {(job?.status === 'queued' || job?.status === 'running') ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
                  {(job?.status === 'queued' || job?.status === 'running') ? (job.status === 'queued' ? 'Dans la file…' : 'Composition en cours…') : 'Composer le morceau'}
                </button>
              </div>

              {job && (
                <div className={`rounded-2xl border p-4 ${job.status === 'failed' ? 'border-red-300/20 bg-red-500/[0.06]' : job.status === 'completed' ? 'border-emerald-300/20 bg-emerald-400/[0.06]' : 'border-cyan-300/20 bg-cyan-400/[0.05]'}`}>
                  <div className="flex items-center gap-2">
                    {job.status === 'completed' ? <Check size={16} className="text-emerald-300" /> : job.status === 'failed' ? <span className="flex h-4 w-4 items-center justify-center rounded-full bg-red-400/20 text-[11px] text-red-200">!</span> : <Loader2 size={16} className="animate-spin text-cyan-300" />}
                    <span className="text-sm font-medium">{job.status === 'completed' ? 'Morceau prêt' : job.status === 'failed' ? 'Composition interrompue' : job.status === 'queued' ? 'En attente du moteur' : 'Composition en cours'}</span>
                    {job.queue_position ? <span className="ml-auto text-[11px] text-white/40">position {job.queue_position}</span> : null}
                  </div>
                  {job.error && <p className="mt-2 text-xs leading-relaxed text-red-200/80">{job.error}</p>}
                  {currentUrl && (
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <button onClick={() => playTrack(currentUrl)} className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-300/25 bg-emerald-400/10 px-3 py-2 text-xs font-medium text-emerald-100 hover:bg-emerald-400/20"><Play size={13} />Écouter</button>
                      <a href={resolveMusicAsset(currentUrl)} download className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.06] px-3 py-2 text-xs text-white/70 hover:text-white"><Download size={13} />Télécharger</a>
                    </div>
                  )}
                </div>
              )}
            </section>

            <aside className="space-y-4">
              <div className="rounded-2xl border border-white/[0.09] bg-white/[0.045] p-4 backdrop-blur">
                <div className="flex items-center gap-2"><Volume2 size={15} className="text-fuchsia-200" /><h2 className="text-sm font-semibold">Voix du morceau</h2></div>
                <p className="mt-1 text-xs leading-relaxed text-white/42">Une référence s’applique directement à la couleur vocale et au style. Pour une ressemblance musicale forte, envoie un extrait chanté net et isolé.</p>
                <label className="mt-3 block text-[11px] font-medium text-white/60">Voix active
                  <select value={voiceSlug} onChange={(event) => setVoiceSlug(event.target.value)} className={`${INPUT_CLASS} mt-1.5`}>
                    <option value="">Interprète libre</option>
                    {voices.map((voice) => <option key={voice.slug} value={voice.slug}>{voice.name} · {voice.lang.toUpperCase()}</option>)}
                  </select>
                </label>
                {selectedVoice && <div className="mt-2 rounded-lg border border-fuchsia-300/15 bg-fuchsia-400/[0.06] px-2.5 py-2 text-[11px] text-fuchsia-100/80">{selectedVoice.name} est utilisée comme référence.</div>}

                <div className="mt-4 border-t border-white/[0.08] pt-4">
                  <div className="text-[11px] font-medium text-white/65">Ajouter une voix</div>
                  <input value={voiceName} onChange={(event) => setVoiceName(event.target.value)} maxLength={80} placeholder="Nom de la voix" className={`${INPUT_CLASS} mt-2`} />
                  <label className="mt-2 flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-dashed border-white/15 bg-black/15 px-3 py-3 text-xs text-white/55 transition hover:border-cyan-300/35 hover:text-cyan-100">
                    <Upload size={14} />
                    <span className="max-w-[15rem] truncate">{voiceFile ? voiceFile.name : 'Envoyer un échantillon audio'}</span>
                    <input type="file" accept="audio/wav,audio/mpeg,audio/mp4,audio/aac,audio/flac,audio/ogg,audio/webm" onChange={(event) => setVoiceFile(event.target.files?.[0] || null)} className="hidden" />
                  </label>
                  <label className="mt-3 flex cursor-pointer items-start gap-2 text-[11px] leading-relaxed text-white/48"><input type="checkbox" checked={voiceConsent} onChange={(event) => setVoiceConsent(event.target.checked)} className="mt-0.5 accent-cyan-300" /><span>Je confirme disposer de l’autorisation de cette personne et du fichier transmis.</span></label>
                  <button onClick={() => { void importVoice() }} disabled={!voiceFile || !voiceName.trim() || !voiceConsent || voiceImporting} className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-xl border border-fuchsia-300/25 bg-fuchsia-400/10 px-3 py-2 text-xs font-medium text-fuchsia-100 hover:bg-fuchsia-400/20 disabled:cursor-not-allowed disabled:opacity-40">
                    {voiceImporting ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}{voiceImporting ? 'Préparation…' : 'Ajouter à la bibliothèque'}
                  </button>
                  {voiceImportMessage && <p className="mt-2 text-[11px] leading-relaxed text-emerald-200/75">{voiceImportMessage}</p>}
                </div>
              </div>

              <div className="rounded-2xl border border-white/[0.09] bg-white/[0.045] p-4 backdrop-blur">
                <div className="flex items-center justify-between gap-2"><div className="flex items-center gap-2"><Music size={15} className="text-cyan-200" /><h2 className="text-sm font-semibold">Dernières sorties</h2></div><span className="text-[10px] text-white/30">{exports.length}</span></div>
                {exports.length === 0 ? <p className="mt-3 text-xs text-white/35">Les morceaux validés apparaîtront ici.</p> : (
                  <div className="mt-3 space-y-2">
                    {exports.slice(0, 8).map((track) => {
                      const fullUrl = resolveMusicAsset(track.url)
                      const trackTitle = String(track.metadata?.title || track.filename.replace(/^[0-9_]+/, '').replace(/\.[^.]+$/, ''))
                      return <div key={track.filename} className="flex items-center gap-2 rounded-xl border border-white/[0.07] bg-black/[0.15] p-2">
                        <button onClick={() => playTrack(track.url)} className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-cyan-400/10 text-cyan-100 hover:bg-cyan-400/20" title={playing === fullUrl ? 'Pause' : 'Lire'}>{playing === fullUrl ? <Pause size={13} /> : <Play size={13} />}</button>
                        <div className="min-w-0 flex-1"><div className="truncate text-xs text-white/75">{trackTitle}</div><div className="mt-0.5 text-[10px] text-white/30">{formatWhen(track.modified)}</div></div>
                        <a href={fullUrl} download className="rounded-md p-1.5 text-white/40 hover:bg-white/[0.08] hover:text-white" title="Télécharger"><Download size={13} /></a>
                      </div>
                    })}
                  </div>
                )}
              </div>
            </aside>
          </div>
        )}
      </main>

      {error && <div className="absolute bottom-4 left-1/2 z-30 max-w-[min(92vw,42rem)] -translate-x-1/2 rounded-xl border border-red-300/25 bg-[#2b111a]/95 px-4 py-2.5 text-xs text-red-100 shadow-xl backdrop-blur">{error}</div>}
    </div>
  )
}
