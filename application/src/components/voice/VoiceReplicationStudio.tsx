import { useCallback, useEffect, useRef, useState } from 'react'
import {
  AlertCircle,
  ArrowLeft,
  Check,
  CheckCircle2,
  Copy,
  Disc,
  Download,
  FileAudio,
  FolderTree,
  Headphones,
  Loader2,
  Mic,
  Music,
  Pause,
  Play,
  RefreshCw,
  RotateCcw,
  Smile,
  Sparkles,
  Square,
  Trash2,
  Upload,
  UserCheck,
  Volume2,
  Wand2,
  X,
  Zap,
} from 'lucide-react'
import {
  calibrateVoiceProfile,
  cleanLegacyOutputs,
  deleteVoiceStudioProfile,
  detectVoiceEmotion,
  getVoiceStudioProfiles,
  getVoiceStudioTree,
  replicateSingingVoice,
  replicateVoice,
  resolveVoiceAudioUrl,
  searchInstrumentalTracks,
  uploadVoiceSampleBlob,
  type InstrumentalTrack,
  type VoiceReplicateResponse,
  type VoiceSampleUploadResponse,
  type VoiceStudioProfile,
  type VoiceStudioTree,
} from '../../services/voiceStudioApi.ts'

interface Props {
  onClose?: () => void
}

type TabMode = 'studio' | 'profiles' | 'tree'
type StudioStep = 'source' | 'preview' | 'input' | 'result'
type SynthesisMode = 'speech' | 'singing'

const EMOTION_PRESETS = [
  { id: 'joyeux', label: 'Joyeux 😊', instruction: 'Parle avec une énergie joyeuse, lumineuse et un grand sourire dans la voix.' },
  { id: 'enthousiaste', label: 'Enthousiaste ⚡', instruction: 'Parle avec beaucoup d\'enthousiasme, de passion et de dynamisme.' },
  { id: 'triste', label: 'Émouvant / Triste 😢', instruction: 'Parle d\'un ton touchant, mélancolique, avec une douce émotion retenue.' },
  { id: 'chuchote', label: 'Chuchoté 🤫', instruction: 'Chuchote doucement et intimement au creux de l\'oreille.' },
  { id: 'colere', label: 'Intense / Colère 😡', instruction: 'Parle avec intensité, fermeté, autorité et puissance.' },
  { id: 'dramatique', label: 'Dramatique 🎭', instruction: 'Adopte un ton théâtral, solennel et captivant.' },
  { id: 'calme', label: 'Calme & Apaisant 🍃', instruction: 'Parle d\'une voix douce, posée, relaxante et rassurante.' },
  { id: 'mysterieux', label: 'Mystérieux 🔮', instruction: 'Parle d\'une voix feutrée, intrigante et énigmatique.' },
  { id: 'naturel', label: 'Neutre & Naturel 🎙️', instruction: 'Diction naturelle, claire et fluide sans emphase excessive.' },
]

const SINGING_STYLES = [
  { id: 'Pop', label: 'Pop Moderne', bpm: 110 },
  { id: 'Lo-Fi', label: 'Lo-Fi Chill', bpm: 85 },
  { id: 'Acoustique', label: 'Acoustique Folk', bpm: 95 },
  { id: 'Électro', label: 'Synthwave / Électro', bpm: 115 },
  { id: 'Ballade', label: 'Piano Ballade', bpm: 80 },
  { id: 'Rock', label: 'Rock Énergique', bpm: 130 },
]

const PRESET_TEXTS = [
  {
    label: 'Test rapide',
    text: 'Bonjour ! Voici un essai avec ma voix répliquée par échantillon court. La diction et le timbre sont parfaitement capturés.',
  },
  {
    label: 'Émotion joyeuse',
    text: 'C\'est une journée absolument formidable ! Je suis tellement ravi de partager ce moment exceptionnel avec vous tous !',
  },
  {
    label: 'Poème & Douceur',
    text: 'Sous le ciel étoilé de la ville endormie, les mélodies résonnent et s\'envolent vers l\'infini, au rythme des passions et de nos vies.',
  },
  {
    label: 'Dialogue cinéma',
    text: 'Écoute-moi très attentivement. Nous n\'avons qu\'une seule opportunité pour réussir ce plan, alors reste concentré.',
  },
]

const PRESET_LYRICS = [
  {
    label: 'Refrain Pop',
    text: 'Dans la lumière de la ville qui danse,\nOn oublie la nuit, on prend notre chance,\nUne mélodie qui s\'élève vers le ciel,\nUn refrain d\'été, un rêve éternel.',
  },
  {
    label: 'Ballade Douce',
    text: 'Le temps s\'arrête quand tu me regardes,\nLes accords doux que mon cœur garde,\nSur le piano qui résonne au loin,\nOn avance ensemble, main dans la main.',
  },
  {
    label: 'Électro Drive',
    text: 'Vitesse de nuit sur l\'horizon fluo,\nLes basses qui montent toujours plus haut,\nOn traverse l\'espace au son des synthés,\nRien ne pourra jamais nous arrêter.',
  },
]

export default function VoiceReplicationStudio({ onClose }: Props) {
  const [activeTab, setActiveTab] = useState<TabMode>('studio')
  const [step, setStep] = useState<StudioStep>('source')
  const [synthesisMode, setSynthesisMode] = useState<SynthesisMode>('speech')

  // Microphone state
  const [isRecording, setIsRecording] = useState(false)
  const [recordingSeconds, setRecordingSeconds] = useState(0)
  const [micVolume, setMicVolume] = useState(0)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef = useRef<Blob[]>([])
  const recordingTimerRef = useRef<number | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const animFrameRef = useRef<number | null>(null)

  // Active sample & profile
  const [sampleData, setSampleData] = useState<VoiceSampleUploadResponse | null>(null)
  const [selectedProfileSlug, setSelectedProfileSlug] = useState<string | null>(null)
  const [activeProfileTranscript, setActiveProfileTranscript] = useState<string>('')
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)

  // Speech parameters
  const [speechText, setSpeechText] = useState('')
  const [sampleName, setSampleName] = useState('')
  const [savePermanent, setSavePermanent] = useState(true)
  const [lang, setLang] = useState<'fr' | 'en'>('fr')
  const [instruction, setInstruction] = useState('')
  const [selectedEmotionId, setSelectedEmotionId] = useState<string>('naturel')
  const [detectingEmotion, setDetectingEmotion] = useState(false)

  // Singing & Music parameters
  const [singingLyrics, setSingingLyrics] = useState('')
  const [singingStyle, setSingingStyle] = useState('Pop')
  const [singingBpm, setSingingBpm] = useState(100)
  const [availableTracks, setAvailableTracks] = useState<InstrumentalTrack[]>([])
  const [selectedMusicId, setSelectedMusicId] = useState<string>('')
  const [vocalVolume, setVocalVolume] = useState(1.0)
  const [musicVolume, setMusicVolume] = useState(0.55)

  // Replication state
  const [replicating, setReplicating] = useState(false)
  const [replicationProgress, setReplicationProgress] = useState<string>('')
  // La voie CHANT (/api/voice/studio/sing) renvoie en plus les paroles et la
  // piste d'accompagnement: le resultat affiche ici peut venir des deux voies.
  const [replicationResult, setReplicationResult] = useState<
    (VoiceReplicateResponse & { lyrics?: string; backing_track?: string }) | null
  >(null)
  const [replicationError, setReplicationError] = useState<string | null>(null)

  // Universal Audio Player
  const [playingUrl, setPlayingUrl] = useState<string | null>(null)
  const [audioDuration, setAudioDuration] = useState(0)
  const [audioCurrentTime, setAudioCurrentTime] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null)

  // Tree & Profiles
  const [profiles, setProfiles] = useState<VoiceStudioProfile[]>([])
  const [treeData, setTreeData] = useState<VoiceStudioTree | null>(null)
  const [loadingData, setLoadingData] = useState(false)
  const [calibrating, setCalibrating] = useState(false)
  const [copiedPath, setCopiedPath] = useState(false)

  // Load profiles, tree, and music tracks
  const loadProfilesAndTree = useCallback(async () => {
    setLoadingData(true)
    try {
      const [pList, tree, tracks] = await Promise.all([
        getVoiceStudioProfiles().catch(() => []),
        getVoiceStudioTree().catch(() => null),
        searchInstrumentalTracks().catch(() => []),
      ])
      setProfiles(pList)
      setTreeData(tree)
      setAvailableTracks(tracks)
      if (tracks.length > 0 && !selectedMusicId) {
        setSelectedMusicId(tracks[0].id)
      }
    } catch {
      // Ignorer
    } finally {
      setLoadingData(false)
    }
  }, [selectedMusicId])

  useEffect(() => {
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      window.speechSynthesis.cancel()
    }
    void loadProfilesAndTree()
    return () => {
      if (typeof window !== 'undefined' && window.speechSynthesis) {
        window.speechSynthesis.cancel()
      }
      if (audioPlayerRef.current) {
        audioPlayerRef.current.pause()
        audioPlayerRef.current = null
      }
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current)
      if (audioContextRef.current) {
        void audioContextRef.current.close().catch(() => {})
      }
    }
  }, [loadProfilesAndTree])

  // Player controls
  const handlePlayAudio = useCallback((rawUrl: string) => {
    const fullUrl = resolveVoiceAudioUrl(rawUrl)
    if (playingUrl === fullUrl && audioPlayerRef.current) {
      if (isPlaying) {
        audioPlayerRef.current.pause()
        setIsPlaying(false)
      } else {
        void audioPlayerRef.current.play()
        setIsPlaying(true)
      }
      return
    }

    if (audioPlayerRef.current) {
      audioPlayerRef.current.pause()
    }

    const audio = new Audio(fullUrl)
    audioPlayerRef.current = audio
    setPlayingUrl(fullUrl)
    setIsPlaying(true)

    audio.ontimeupdate = () => {
      setAudioCurrentTime(audio.currentTime)
    }
    audio.onloadedmetadata = () => {
      setAudioDuration(audio.duration)
    }
    audio.onended = () => {
      setIsPlaying(false)
      setAudioCurrentTime(0)
    }
    audio.onerror = () => {
      setIsPlaying(false)
    }
    void audio.play().catch(() => setIsPlaying(false))
  }, [playingUrl, isPlaying])

  const stopAudio = () => {
    if (audioPlayerRef.current) {
      audioPlayerRef.current.pause()
      audioPlayerRef.current.currentTime = 0
    }
    setIsPlaying(false)
    setPlayingUrl(null)
  }

  // Microphone recording
  const startRecording = async () => {
    setUploadError(null)
    audioChunksRef.current = []
    setRecordingSeconds(0)
    stopAudio()

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
          sampleRate: 48000,
        },
      })

      const audioCtx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)()
      audioContextRef.current = audioCtx
      const source = audioCtx.createMediaStreamSource(stream)
      const analyser = audioCtx.createAnalyser()
      analyser.fftSize = 256
      source.connect(analyser)
      analyserRef.current = analyser

      const dataArray = new Uint8Array(analyser.frequencyBinCount)
      const updateVolume = () => {
        analyser.getByteFrequencyData(dataArray)
        let sum = 0
        for (let i = 0; i < dataArray.length; i++) {
          sum += dataArray[i]
        }
        const avg = sum / dataArray.length
        setMicVolume(Math.min(100, Math.round((avg / 128) * 100)))
        animFrameRef.current = requestAnimationFrame(updateVolume)
      }
      updateVolume()

      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm'
      const recorder = new MediaRecorder(stream, { mimeType })
      mediaRecorderRef.current = recorder

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          audioChunksRef.current.push(e.data)
        }
      }

      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop())
        if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current)
        if (audioContextRef.current) {
          void audioContextRef.current.close().catch(() => {})
        }

        const blob = new Blob(audioChunksRef.current, { type: mimeType })
        if (blob.size < 500) {
          setUploadError('Enregistrement trop court. Veuillez parler pendant au moins 3 secondes.')
          return
        }

        setUploading(true)
        try {
          const res = await uploadVoiceSampleBlob(blob, `mic_${Date.now()}.wav`)
          if (res.ok) {
            setSampleData(res)
            setSelectedProfileSlug(null)
            setActiveProfileTranscript('')
            if (!sampleName) {
              setSampleName(`Voix ${new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}`)
            }
            setStep('preview')
          } else {
            setUploadError(res.error || 'Erreur d\'analyse de l\'enregistrement')
          }
        } catch (err) {
          setUploadError(err instanceof Error ? err.message : String(err))
        } finally {
          setUploading(false)
        }
      }

      recorder.start(200)
      setIsRecording(true)

      const timer = window.setInterval(() => {
        setRecordingSeconds((prev) => prev + 1)
      }, 1000)
      recordingTimerRef.current = timer
    } catch {
      setUploadError('Accès au microphone refusé ou non supporté.')
    }
  }

  const stopRecording = () => {
    if (recordingTimerRef.current) {
      clearInterval(recordingTimerRef.current)
      recordingTimerRef.current = null
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop()
    }
    setIsRecording(false)
    setMicVolume(0)
  }

  // File Upload
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploadError(null)
    setUploading(true)
    try {
      const res = await uploadVoiceSampleBlob(file, file.name)
      if (res.ok) {
        setSampleData(res)
        setSelectedProfileSlug(null)
        setActiveProfileTranscript('')
        const cleanName = file.name.replace(/\.[^/.]+$/, '').replace(/[_\\-]/g, ' ')
        setSampleName(cleanName.charAt(0).toUpperCase() + cleanName.slice(1))
        setStep('preview')
      } else {
        setUploadError(res.error || 'Fichier audio non conforme.')
      }
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : String(err))
    } finally {
      setUploading(false)
    }
  }

  // Select profile
  const handleSelectExistingProfile = (p: VoiceStudioProfile) => {
    setSelectedProfileSlug(p.slug)
    setSampleName(p.name)
    setActiveProfileTranscript(p.transcript || '')
    setSampleData({
      ok: true,
      sampleId: p.slug,
      samplePath: p.reference,
      audioUrl: p.audioUrl,
      duration_s: p.duration_s,
      quality: {
        ok: true,
        quality_score: p.quality_score,
        duration_s: p.duration_s,
      },
    })
    setStep('preview')
  }

  // Emotion Auto-Detection
  const handleDetectEmotion = async () => {
    const textToAnalyze = synthesisMode === 'speech' ? speechText : singingLyrics
    if (!textToAnalyze.trim()) return
    setDetectingEmotion(true)
    try {
      const res = await detectVoiceEmotion(textToAnalyze)
      if (res.ok) {
        setInstruction(res.instruction)
        setSelectedEmotionId(res.emotion)
      }
    } catch {
      // Ignorer
    } finally {
      setDetectingEmotion(false)
    }
  }

  // Calibrate All Profiles
  const handleCalibrateProfiles = async () => {
    setCalibrating(true)
    try {
      await calibrateVoiceProfile()
      await loadProfilesAndTree()
    } catch {
      // Ignorer
    } finally {
      setCalibrating(false)
    }
  }

  // Synthesis Handler
  const handleRunReplication = async () => {
    if (synthesisMode === 'speech' && !speechText.trim()) {
      setReplicationError('Veuillez saisir le texte à faire dire à cette voix.')
      return
    }
    if (synthesisMode === 'singing' && !singingLyrics.trim()) {
      setReplicationError('Veuillez saisir les paroles de la chanson à faire chanter.')
      return
    }
    if (!sampleData && !selectedProfileSlug) {
      setReplicationError('Aucun échantillon vocal sélectionné.')
      return
    }

    setReplicating(true)
    setReplicationError(null)
    setReplicationResult(null)

    try {
      if (synthesisMode === 'speech') {
        setReplicationProgress('Calibration du timbre & synthèse CosyVoice 3...')
        const res = await replicateVoice({
          sampleId: sampleData?.sampleId,
          samplePath: sampleData?.samplePath,
          profileSlug: selectedProfileSlug || undefined,
          text: speechText.trim(),
          name: sampleName.trim() || 'Voix Répliquée',
          savePermanent,
          lang,
          instruction,
        })
        if (res.ok) {
          setReplicationResult(res)
          setStep('result')
          void loadProfilesAndTree()
          if (res.audioUrl) handlePlayAudio(res.audioUrl)
        } else {
          setReplicationError(res.error || 'La synthèse vocale n\'a pas pu aboutir.')
        }
      } else {
        setReplicationProgress('Génération du chant et mixage musical...')
        const res = await replicateSingingVoice({
          sampleId: sampleData?.sampleId,
          samplePath: sampleData?.samplePath,
          profileSlug: selectedProfileSlug || undefined,
          lyrics: singingLyrics.trim(),
          backingMusicId: selectedMusicId,
          style: singingStyle,
          bpm: singingBpm,
          name: `${sampleName.trim() || 'Voix'} (Chant)`,
          savePermanent,
          lang,
          vocalVolume,
          musicVolume,
        })
        if (res.ok) {
          setReplicationResult(res)
          setStep('result')
          void loadProfilesAndTree()
          if (res.audioUrl) handlePlayAudio(res.audioUrl)
        } else {
          setReplicationError(res.error || 'La synthèse de chanson n\'a pas pu aboutir.')
        }
      }
    } catch (err) {
      setReplicationError(err instanceof Error ? err.message : String(err))
    } finally {
      setReplicating(false)
      setReplicationProgress('')
    }
  }

  const handleDeleteProfile = async (slug: string) => {
    if (!confirm(`Supprimer définitivement le profil de voix "${slug}" ?`)) return
    try {
      await deleteVoiceStudioProfile(slug)
      void loadProfilesAndTree()
    } catch (err) {
      alert(`Erreur de suppression: ${err}`)
    }
  }

  const handleCleanLegacy = async () => {
    try {
      const res = await cleanLegacyOutputs()
      if (res.cleaned.length > 0) {
        alert(`Dossiers obsolètes supprimés: ${res.cleaned.join(', ')}`)
      } else {
        alert('Arborescence propre. Aucun dossier obsolète.')
      }
      void loadProfilesAndTree()
    } catch (err) {
      alert(`Erreur: ${err}`)
    }
  }

  const formatTime = (sec: number) => {
    const m = Math.floor(sec / 60)
    const s = Math.floor(sec % 60)
    return `${m}:${s < 10 ? '0' : ''}${s}`
  }

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col bg-[#0d0f14] text-slate-100 font-sans select-none overflow-hidden"
      style={{ animation: 'fadeIn 0.2s ease-out' }}
    >
      {/* Barre de titre Studio */}
      <header className="flex shrink-0 items-center justify-between border-b border-white/10 bg-[#121620] px-4 py-3 sm:px-6">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-violet-600 to-fuchsia-600 shadow-lg shadow-violet-500/20">
            <Mic size={20} className="text-white" />
          </div>
          <div>
            <h1 className="text-base font-bold tracking-tight text-white sm:text-lg flex items-center gap-2">
              Studio de Réplication Vocale
              <span className="rounded-md border border-violet-500/30 bg-violet-500/10 px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider text-violet-300">
                HD · Émotion & Chant
              </span>
            </h1>
            <p className="text-xs text-slate-400">
              Clonage haute fidélité dès 3s · Émotions intelligentes · Mode Chanson & Accompagnement
            </p>
          </div>
        </div>

        {/* Navigation des Onglets */}
        <div className="flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.04] p-1">
          <button
            type="button"
            onClick={() => setActiveTab('studio')}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
              activeTab === 'studio'
                ? 'bg-violet-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Sparkles size={14} />
            Studio & Synthèse
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('profiles')}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
              activeTab === 'profiles'
                ? 'bg-violet-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <UserCheck size={14} />
            Profils ({profiles.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('tree')}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
              activeTab === 'tree'
                ? 'bg-violet-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <FolderTree size={14} />
            Arborescence
          </button>
        </div>

        {/* Bouton Fermer */}
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-white/10 p-2 text-slate-400 hover:bg-white/10 hover:text-white transition-colors"
            title="Quitter le studio"
          >
            <X size={18} />
          </button>
        )}
      </header>

      {/* Contenu Principal */}
      <main className="flex-1 overflow-y-auto p-4 sm:p-6 max-w-5xl mx-auto w-full">
        {activeTab === 'studio' && (
          <div className="space-y-6">
            {/* Étapes du Studio */}
            <div className="flex items-center justify-between border-b border-white/10 pb-4">
              <div className="flex items-center gap-2">
                <span className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${
                  step === 'source' ? 'bg-violet-600 text-white' : 'bg-white/10 text-slate-300'
                }`}>1</span>
                <span className={`text-xs font-semibold ${step === 'source' ? 'text-white' : 'text-slate-400'}`}>Échantillon Vocal</span>
              </div>
              <div className="h-0.5 flex-1 bg-white/10 mx-3" />
              <div className="flex items-center gap-2">
                <span className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${
                  step === 'preview' ? 'bg-violet-600 text-white' : 'bg-white/10 text-slate-300'
                }`}>2</span>
                <span className={`text-xs font-semibold ${step === 'preview' ? 'text-white' : 'text-slate-400'}`}>Réécoute & Calibrage</span>
              </div>
              <div className="h-0.5 flex-1 bg-white/10 mx-3" />
              <div className="flex items-center gap-2">
                <span className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${
                  step === 'input' ? 'bg-violet-600 text-white' : 'bg-white/10 text-slate-300'
                }`}>3</span>
                <span className={`text-xs font-semibold ${step === 'input' ? 'text-white' : 'text-slate-400'}`}>Parole & Chant</span>
              </div>
              <div className="h-0.5 flex-1 bg-white/10 mx-3" />
              <div className="flex items-center gap-2">
                <span className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${
                  step === 'result' ? 'bg-violet-600 text-white' : 'bg-white/10 text-slate-300'
                }`}>4</span>
                <span className={`text-xs font-semibold ${step === 'result' ? 'text-white' : 'text-slate-400'}`}>Génération Finale</span>
              </div>
            </div>

            {/* ÉTAPE 1 : ACQUISITION DE L'ÉCHANTILLON */}
            {step === 'source' && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* 1A. Enregistrement Micro */}
                <div className="rounded-2xl border border-white/10 bg-[#151924] p-5 flex flex-col items-center justify-between text-center relative overflow-hidden">
                  <div className="w-full">
                    <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-violet-600/20 text-violet-400 mb-3">
                      <Mic size={28} />
                    </div>
                    <h2 className="text-sm font-bold text-white mb-1">Enregistrer au Microphone</h2>
                    <p className="text-xs text-slate-400 mb-4">
                      Parlez naturellement pendant <strong className="text-violet-300">3 à 8 secondes</strong> minimum.
                    </p>
                  </div>

                  {isRecording ? (
                    <div className="w-full py-2 flex flex-col items-center gap-3">
                      <div className="flex items-center gap-2 text-rose-400 font-mono text-lg font-bold animate-pulse">
                        <span className="h-3 w-3 rounded-full bg-rose-500" />
                        {recordingSeconds}s / min 3s
                      </div>
                      <div className="w-full h-3 rounded-full bg-slate-800 overflow-hidden border border-white/10">
                        <div
                          className="h-full bg-gradient-to-r from-emerald-500 via-yellow-500 to-rose-500 transition-all duration-75"
                          style={{ width: `${Math.min(100, micVolume)}%` }}
                        />
                      </div>
                      <button
                        type="button"
                        onClick={stopRecording}
                        className="w-full rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-semibold py-2.5 px-4 text-xs flex items-center justify-center gap-2 shadow-lg shadow-rose-600/30 transition-colors"
                      >
                        <Square size={14} />
                        Arrêter et Analyser l'échantillon
                      </button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => { void startRecording() }}
                      disabled={uploading}
                      className="w-full rounded-xl bg-violet-600 hover:bg-violet-500 text-white font-semibold py-2.5 px-4 text-xs flex items-center justify-center gap-2 shadow-lg shadow-violet-600/30 transition-colors"
                    >
                      {uploading ? <Loader2 size={14} className="animate-spin" /> : <Mic size={14} />}
                      Démarrer l'enregistrement
                    </button>
                  )}
                </div>

                {/* 1B. Importer Fichier Audio */}
                <div className="rounded-2xl border border-white/10 bg-[#151924] p-5 flex flex-col items-center justify-between text-center">
                  <div>
                    <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-fuchsia-600/20 text-fuchsia-400 mb-3">
                      <Upload size={28} />
                    </div>
                    <h2 className="text-sm font-bold text-white mb-1">Téléverser un Extrait</h2>
                    <p className="text-xs text-slate-400 mb-4">
                      Fichier WAV, MP3, M4A, FLAC ou extrait vidéo MP4/MKV.
                    </p>
                  </div>
                  <label className="w-full rounded-xl border border-white/20 bg-white/[0.06] hover:bg-white/[0.12] text-white font-semibold py-2.5 px-4 text-xs flex items-center justify-center gap-2 cursor-pointer transition-colors">
                    {uploading ? <Loader2 size={14} className="animate-spin" /> : <FileAudio size={14} />}
                    Choisir un fichier audio
                    <input
                      type="file"
                      accept="audio/*,video/*,.wav,.mp3,.m4a,.flac,.ogg,.mp4,.mkv,.webm"
                      className="hidden"
                      onChange={(e) => { void handleFileUpload(e) }}
                      disabled={uploading}
                    />
                  </label>
                </div>

                {/* 1C. Profil Existant */}
                <div className="rounded-2xl border border-white/10 bg-[#151924] p-5 flex flex-col items-center justify-between text-center">
                  <div>
                    <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-sky-600/20 text-sky-400 mb-3">
                      <UserCheck size={28} />
                    </div>
                    <h2 className="text-sm font-bold text-white mb-1">Profils Calibrés</h2>
                    <p className="text-xs text-slate-400 mb-4">
                      Réutiliser une voix de votre bibliothèque ({profiles.length} voix).
                    </p>
                  </div>
                  {profiles.length > 0 ? (
                    <div className="w-full space-y-1.5 max-h-32 overflow-y-auto pr-1">
                      {profiles.map((p) => (
                        <button
                          key={p.slug}
                          type="button"
                          onClick={() => handleSelectExistingProfile(p)}
                          className="w-full rounded-lg border border-white/10 bg-white/[0.03] hover:bg-violet-600/20 hover:border-violet-500/40 p-2 text-left text-xs flex items-center justify-between transition-colors"
                        >
                          <span className="font-medium text-white truncate max-w-[130px]">{p.name}</span>
                          <span className="text-[10px] text-emerald-400 font-mono">🎯 {p.duration_s.toFixed(1)}s</span>
                        </button>
                      ))}
                    </div>
                  ) : (
                    <div className="text-[11px] text-slate-500 py-3">Aucun profil enregistré.</div>
                  )}
                </div>
              </div>
            )}

            {uploadError && (
              <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-3.5 text-xs text-rose-300 flex items-center gap-2.5">
                <AlertCircle size={16} className="shrink-0" />
                <span>{uploadError}</span>
              </div>
            )}

            {/* ÉTAPE 2 : RÉÉCOUTE ET CALIBRAGE */}
            {step === 'preview' && sampleData && (
              <div className="rounded-2xl border border-violet-500/30 bg-[#151924] p-5 sm:p-6 space-y-5">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-white/10 pb-4">
                  <div>
                    <h2 className="text-base font-bold text-white flex items-center gap-2">
                      <Headphones size={18} className="text-violet-400" />
                      Réécoute & Calibrage de l'Échantillon
                    </h2>
                    <p className="text-xs text-slate-400">
                      Vérifiez l'audio et la transcription de référence pour une fidélité acoustique optimale.
                    </p>
                  </div>
                  <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-mono font-semibold text-emerald-300 flex items-center gap-1.5">
                    <CheckCircle2 size={13} />
                    Qualité validée ({sampleData.duration_s.toFixed(2)}s)
                  </span>
                </div>

                {/* Lecteur Audio */}
                <div className="rounded-xl border border-white/10 bg-black/40 p-4 flex flex-col gap-3">
                  <div className="flex items-center justify-between">
                    <button
                      type="button"
                      onClick={() => handlePlayAudio(sampleData.audioUrl)}
                      className="flex items-center gap-2 rounded-xl bg-violet-600 hover:bg-violet-500 text-white font-semibold py-2 px-4 text-xs transition-colors shadow-md"
                    >
                      {isPlaying && playingUrl === resolveVoiceAudioUrl(sampleData.audioUrl) ? (
                        <>
                          <Pause size={15} /> Pause
                        </>
                      ) : (
                        <>
                          <Play size={15} /> Ré-écouter l'échantillon
                        </>
                      )}
                    </button>
                    <div className="font-mono text-xs text-slate-300">
                      {isPlaying && playingUrl === resolveVoiceAudioUrl(sampleData.audioUrl)
                        ? `${formatTime(audioCurrentTime)} / ${formatTime(audioDuration || sampleData.duration_s)}`
                        : `${sampleData.duration_s.toFixed(1)}s`}
                    </div>
                  </div>

                  {/* Transcription calibrée si disponible */}
                  {activeProfileTranscript && (
                    <div className="rounded-lg bg-violet-950/30 border border-violet-500/20 p-2.5 text-xs text-violet-200">
                      <span className="font-semibold text-violet-400 mr-1.5">🎯 Phrase de référence calibrée :</span>
                      « {activeProfileTranscript} »
                    </div>
                  )}

                  {/* Diagnostic Qualité */}
                  <div className="grid grid-cols-3 gap-2 pt-2 border-t border-white/10 text-center text-xs">
                    <div className="rounded-lg bg-white/[0.03] p-2">
                      <div className="text-[10px] uppercase text-slate-400">Durée</div>
                      <div className="font-semibold text-white">{sampleData.duration_s.toFixed(1)}s</div>
                    </div>
                    <div className="rounded-lg bg-white/[0.03] p-2">
                      <div className="text-[10px] uppercase text-slate-400">Rapport S/B</div>
                      <div className="font-semibold text-emerald-400">
                        {sampleData.quality?.estimated_snr_db ? `${sampleData.quality.estimated_snr_db.toFixed(0)} dB` : 'Optimal'}
                      </div>
                    </div>
                    <div className="rounded-lg bg-white/[0.03] p-2">
                      <div className="text-[10px] uppercase text-slate-400">Score de clarté</div>
                      <div className="font-semibold text-violet-300">
                        {Math.round((sampleData.quality?.quality_score || 0.85) * 100)} %
                      </div>
                    </div>
                  </div>
                </div>

                {/* Actions Étape 2 */}
                <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => { stopAudio(); setStep('source') }}
                    className="w-full sm:w-auto rounded-xl border border-white/10 bg-white/[0.05] hover:bg-white/10 text-slate-300 font-medium py-2.5 px-4 text-xs flex items-center justify-center gap-2 transition-colors"
                  >
                    <RotateCcw size={14} />
                    Changer d'échantillon
                  </button>
                  <button
                    type="button"
                    onClick={() => { stopAudio(); setStep('input') }}
                    className="w-full sm:w-auto rounded-xl bg-gradient-to-r from-violet-600 to-fuchsia-600 hover:from-violet-500 hover:to-fuchsia-500 text-white font-bold py-2.5 px-6 text-xs flex items-center justify-center gap-2 shadow-lg shadow-violet-600/30 transition-all"
                  >
                    <Check size={15} />
                    Valider et Choisir Parole / Chant
                  </button>
                </div>
              </div>
            )}

            {/* ÉTAPE 3 : CHOIX DU MODE (PAROLE OU CHANT) + EMOTION + GENERATION */}
            {step === 'input' && sampleData && (
              <div className="rounded-2xl border border-white/10 bg-[#151924] p-5 sm:p-6 space-y-5">
                {/* Sélecteur de Mode */}
                <div className="flex items-center justify-between border-b border-white/10 pb-3">
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setSynthesisMode('speech')}
                      className={`flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-bold transition-all ${
                        synthesisMode === 'speech'
                          ? 'bg-violet-600 text-white shadow-md shadow-violet-600/30'
                          : 'border border-white/10 bg-white/[0.04] text-slate-400 hover:text-white'
                      }`}
                    >
                      <Mic size={15} />
                      Mode Parole & Émotion
                    </button>
                    <button
                      type="button"
                      onClick={() => setSynthesisMode('singing')}
                      className={`flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-bold transition-all ${
                        synthesisMode === 'singing'
                          ? 'bg-fuchsia-600 text-white shadow-md shadow-fuchsia-600/30'
                          : 'border border-white/10 bg-white/[0.04] text-slate-400 hover:text-white'
                      }`}
                    >
                      <Music size={15} />
                      Mode Chanson & Musique
                    </button>
                  </div>
                  <span className="text-[11px] font-mono text-slate-400">Voix cible : {sampleName || 'Sélectionnée'}</span>
                </div>

                {/* --- A. MODE PAROLE & ÉMOTION --- */}
                {synthesisMode === 'speech' && (
                  <div className="space-y-4">
                    {/* Presets rapides */}
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-[11px] text-slate-400">Exemples :</span>
                      {PRESET_TEXTS.map((pt) => (
                        <button
                          key={pt.label}
                          type="button"
                          onClick={() => setSpeechText(pt.text)}
                          className="rounded-lg border border-white/10 bg-white/[0.04] hover:bg-violet-600/20 hover:border-violet-500/40 px-2.5 py-1 text-[11px] font-medium text-slate-300 transition-colors"
                        >
                          {pt.label}
                        </button>
                      ))}
                    </div>

                    {/* Zone de texte */}
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between">
                        <label className="text-xs font-semibold text-slate-300">Texte à faire dire :</label>
                        <button
                          type="button"
                          onClick={() => { void handleDetectEmotion() }}
                          disabled={detectingEmotion || !speechText.trim()}
                          className="flex items-center gap-1.5 text-[11px] font-medium text-violet-400 hover:text-violet-300 disabled:opacity-50 transition-colors"
                        >
                          {detectingEmotion ? <Loader2 size={12} className="animate-spin" /> : <Wand2 size={12} />}
                          Détecter l'émotion du texte
                        </button>
                      </div>
                      <textarea
                        rows={4}
                        value={speechText}
                        onChange={(e) => setSpeechText(e.target.value)}
                        placeholder="Écrivez le texte ou le dialogue que vous souhaitez entendre..."
                        className="w-full rounded-xl border border-white/10 bg-black/40 p-3.5 text-xs text-white placeholder-slate-500 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500 resize-none"
                      />
                    </div>

                    {/* Émotions intelligentes */}
                    <div className="space-y-2 pt-2 border-t border-white/10">
                      <div className="flex items-center justify-between">
                        <label className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                          <Smile size={14} className="text-amber-400" />
                          Émotion & Intonation vocale :
                        </label>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {EMOTION_PRESETS.map((em) => (
                          <button
                            key={em.id}
                            type="button"
                            onClick={() => {
                              setSelectedEmotionId(em.id)
                              setInstruction(em.instruction)
                            }}
                            className={`rounded-lg border px-2.5 py-1 text-[11px] font-medium transition-all ${
                              selectedEmotionId === em.id
                                ? 'border-amber-500/60 bg-amber-500/20 text-amber-200'
                                : 'border-white/10 bg-white/[0.03] text-slate-400 hover:text-slate-200'
                            }`}
                          >
                            {em.label}
                          </button>
                        ))}
                      </div>
                      <input
                        type="text"
                        value={instruction}
                        onChange={(e) => setInstruction(e.target.value)}
                        placeholder="Direction d'acteur libre (ex: parle avec un ton enthousiaste, un sourire dans la voix...)"
                        className="w-full rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-xs text-white placeholder-slate-500 focus:border-violet-500 focus:outline-none"
                      />
                    </div>
                  </div>
                )}

                {/* --- B. MODE CHANSON & MUSIQUE --- */}
                {synthesisMode === 'singing' && (
                  <div className="space-y-4">
                    {/* Presets paroles */}
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-[11px] text-slate-400">Paroles :</span>
                      {PRESET_LYRICS.map((pl) => (
                        <button
                          key={pl.label}
                          type="button"
                          onClick={() => setSingingLyrics(pl.text)}
                          className="rounded-lg border border-white/10 bg-white/[0.04] hover:bg-fuchsia-600/20 hover:border-fuchsia-500/40 px-2.5 py-1 text-[11px] font-medium text-slate-300 transition-colors"
                        >
                          {pl.label}
                        </button>
                      ))}
                    </div>

                    {/* Zone paroles */}
                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                        <Music size={14} className="text-fuchsia-400" />
                        Paroles de la chanson :
                      </label>
                      <textarea
                        rows={4}
                        value={singingLyrics}
                        onChange={(e) => setSingingLyrics(e.target.value)}
                        placeholder="Écrivez les couplets ou le refrain à faire chanter..."
                        className="w-full rounded-xl border border-white/10 bg-black/40 p-3.5 text-xs text-white placeholder-slate-500 focus:border-fuchsia-500 focus:outline-none focus:ring-1 focus:ring-fuchsia-500 resize-none font-serif"
                      />
                    </div>

                    {/* Style & Accompagnement musical */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2 border-t border-white/10">
                      {/* Styles musicaux */}
                      <div className="space-y-2">
                        <label className="text-xs font-semibold text-slate-300">Style musical & Rythme :</label>
                        <div className="flex flex-wrap gap-1.5">
                          {SINGING_STYLES.map((st) => (
                            <button
                              key={st.id}
                              type="button"
                              onClick={() => {
                                setSingingStyle(st.id)
                                setSingingBpm(st.bpm)
                              }}
                              className={`rounded-lg border px-2.5 py-1 text-[11px] font-medium transition-all ${
                                singingStyle === st.id
                                  ? 'border-fuchsia-500/60 bg-fuchsia-500/20 text-fuchsia-200'
                                  : 'border-white/10 bg-white/[0.03] text-slate-400 hover:text-slate-200'
                              }`}
                            >
                              {st.label} ({st.bpm} BPM)
                            </button>
                          ))}
                        </div>
                      </div>

                      {/* Choix de l'instrumental */}
                      <div className="space-y-2">
                        <label className="text-xs font-semibold text-slate-300 flex items-center justify-between">
                          <span>Piste instrumentale d'accompagnement :</span>
                          <span className="text-[10px] text-fuchsia-400">{availableTracks.length} disponibles</span>
                        </label>
                        <div className="space-y-1.5 max-h-28 overflow-y-auto pr-1">
                          {availableTracks.map((tr) => (
                            <div
                              key={tr.id}
                              className={`rounded-lg border p-2 text-xs flex items-center justify-between cursor-pointer transition-colors ${
                                selectedMusicId === tr.id
                                  ? 'border-fuchsia-500/60 bg-fuchsia-500/20 text-white'
                                  : 'border-white/10 bg-white/[0.03] text-slate-300 hover:bg-white/[0.06]'
                              }`}
                              onClick={() => setSelectedMusicId(tr.id)}
                            >
                              <div className="flex items-center gap-2 truncate">
                                <Disc size={13} className="text-fuchsia-400 shrink-0" />
                                <span className="font-medium truncate">{tr.name}</span>
                                <span className="text-[10px] text-slate-400">({tr.style} · {tr.bpm} BPM)</span>
                              </div>
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation()
                                  handlePlayAudio(tr.audioUrl)
                                }}
                                className="p-1 text-slate-400 hover:text-white"
                                title="Pré-écouter l'instrumental"
                              >
                                {isPlaying && playingUrl === resolveVoiceAudioUrl(tr.audioUrl) ? (
                                  <Pause size={13} className="text-fuchsia-400" />
                                ) : (
                                  <Play size={13} />
                                )}
                              </button>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>

                    {/* Balance Mixage */}
                    <div className="grid grid-cols-2 gap-4 p-3 rounded-xl bg-black/40 border border-white/10">
                      <div>
                        <div className="flex justify-between text-[11px] text-slate-300 mb-1">
                          <span>Volume Voix :</span>
                          <span className="font-mono text-fuchsia-300">{Math.round(vocalVolume * 100)}%</span>
                        </div>
                        <input
                          type="range"
                          min="0.2"
                          max="1.5"
                          step="0.05"
                          value={vocalVolume}
                          onChange={(e) => setVocalVolume(parseFloat(e.target.value))}
                          className="w-full accent-fuchsia-500"
                        />
                      </div>
                      <div>
                        <div className="flex justify-between text-[11px] text-slate-300 mb-1">
                          <span>Volume Musique :</span>
                          <span className="font-mono text-fuchsia-300">{Math.round(musicVolume * 100)}%</span>
                        </div>
                        <input
                          type="range"
                          min="0.1"
                          max="1.2"
                          step="0.05"
                          value={musicVolume}
                          onChange={(e) => setMusicVolume(parseFloat(e.target.value))}
                          className="w-full accent-fuchsia-500"
                        />
                      </div>
                    </div>
                  </div>
                )}

                {/* Paramètres Généraux */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2 border-t border-white/10">
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        id="savePermanentToggle"
                        checked={savePermanent}
                        onChange={(e) => setSavePermanent(e.target.checked)}
                        className="h-4 w-4 rounded border-white/20 bg-black/40 text-violet-600 focus:ring-violet-500"
                      />
                      <label htmlFor="savePermanentToggle" className="text-xs font-semibold text-white cursor-pointer">
                        Enregistrer dans la bibliothèque de profils
                      </label>
                    </div>
                    {savePermanent && (
                      <div className="pl-6 pt-1 space-y-1">
                        <label className="text-[11px] font-medium text-slate-300">Nom du profil :</label>
                        <input
                          type="text"
                          value={sampleName}
                          onChange={(e) => setSampleName(e.target.value)}
                          placeholder="Ex: Gaëtan, Steven, Narrateur..."
                          className="w-full rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-xs text-white placeholder-slate-500 focus:border-violet-500 focus:outline-none"
                        />
                      </div>
                    )}
                  </div>

                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-semibold text-slate-300">Langue de rendu :</label>
                      <div className="flex rounded-md border border-white/10 bg-black/30 p-0.5">
                        <button
                          type="button"
                          onClick={() => setLang('fr')}
                          className={`rounded px-2.5 py-0.5 text-[10px] font-bold ${lang === 'fr' ? 'bg-violet-600 text-white' : 'text-slate-400'}`}
                        >
                          FR
                        </button>
                        <button
                          type="button"
                          onClick={() => setLang('en')}
                          className={`rounded px-2.5 py-0.5 text-[10px] font-bold ${lang === 'en' ? 'bg-violet-600 text-white' : 'text-slate-400'}`}
                        >
                          EN
                        </button>
                      </div>
                    </div>
                  </div>
                </div>

                {replicationError && (
                  <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-3.5 text-xs text-rose-300 flex items-center gap-2.5">
                    <AlertCircle size={16} className="shrink-0" />
                    <span>{replicationError}</span>
                  </div>
                )}

                {/* Boutons d'Action Étape 3 */}
                <div className="flex items-center justify-between gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setStep('preview')}
                    className="rounded-xl border border-white/10 bg-white/[0.05] hover:bg-white/10 text-slate-300 font-medium py-2.5 px-4 text-xs flex items-center gap-2 transition-colors"
                  >
                    <ArrowLeft size={14} />
                    Retour à l'échantillon
                  </button>

                  <button
                    type="button"
                    onClick={() => { void handleRunReplication() }}
                    disabled={replicating || (synthesisMode === 'speech' ? !speechText.trim() : !singingLyrics.trim())}
                    className="rounded-xl bg-gradient-to-r from-violet-600 via-fuchsia-600 to-pink-600 hover:opacity-90 disabled:opacity-50 text-white font-bold py-3 px-8 text-xs flex items-center gap-2 shadow-xl shadow-violet-600/30 transition-all"
                  >
                    {replicating ? (
                      <>
                        <Loader2 size={16} className="animate-spin" />
                        <span>{replicationProgress || 'Rendu en cours...'}</span>
                      </>
                    ) : (
                      <>
                        {synthesisMode === 'speech' ? <Wand2 size={16} /> : <Music size={16} />}
                        <span>
                          {synthesisMode === 'speech' ? 'Lancer la Synthèse Vocale' : 'Générer la Chanson avec cette Voix'}
                        </span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            )}

            {/* ÉTAPE 4 : RÉSULTAT ET LECTEUR FINAL */}
            {step === 'result' && replicationResult && (
              <div className="rounded-2xl border border-emerald-500/30 bg-[#151924] p-5 sm:p-6 space-y-6">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-white/10 pb-4">
                  <div className="flex items-center gap-3">
                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-500/20 text-emerald-400">
                      <CheckCircle2 size={28} />
                    </div>
                    <div>
                      <h2 className="text-base font-bold text-white">
                        {synthesisMode === 'singing' ? 'Chanson Générée avec Succès !' : 'Réplication Vocale Réussie !'}
                      </h2>
                      <p className="text-xs text-slate-400">
                        Voix : <span className="font-semibold text-white">{replicationResult.name}</span> · Moteur : {replicationResult.engine}
                      </p>
                    </div>
                  </div>
                  <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-mono font-semibold text-emerald-300">
                    {replicationResult.is_permanent ? 'Enregistré dans profils/' : 'Session temporaire'}
                  </span>
                </div>

                {/* Lecteur Principal */}
                <div className="rounded-2xl border border-white/10 bg-black/60 p-5 space-y-4">
                  <div className="flex items-center justify-between">
                    <button
                      type="button"
                      onClick={() => replicationResult.audioUrl && handlePlayAudio(replicationResult.audioUrl)}
                      className="flex items-center gap-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold py-2.5 px-5 text-xs transition-colors shadow-lg shadow-emerald-600/30"
                    >
                      {isPlaying && playingUrl === resolveVoiceAudioUrl(replicationResult.audioUrl || '') ? (
                        <>
                          <Pause size={16} /> Pause
                        </>
                      ) : (
                        <>
                          <Play size={16} /> Écouter le Rendu Audio
                        </>
                      )}
                    </button>
                    <div className="font-mono text-sm text-emerald-300 font-bold">
                      {isPlaying && playingUrl === resolveVoiceAudioUrl(replicationResult.audioUrl || '')
                        ? `${formatTime(audioCurrentTime)} / ${formatTime(audioDuration || replicationResult.duration_s || 0)}`
                        : `${(replicationResult.duration_s || 0).toFixed(1)}s`}
                    </div>
                  </div>

                  {/* Paroles ou texte */}
                  <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3.5 text-xs text-slate-200 italic font-serif leading-relaxed whitespace-pre-line">
                    « {replicationResult.text || replicationResult.lyrics} »
                  </div>

                  {/* Chemin de sortie */}
                  <div className="flex items-center justify-between gap-2 text-[11px] text-slate-400 font-mono bg-white/[0.02] p-2 rounded-lg border border-white/5">
                    <span className="truncate">Fichier : {replicationResult.wav}</span>
                    <button
                      type="button"
                      onClick={() => {
                        if (replicationResult.wav) {
                          void navigator.clipboard.writeText(replicationResult.wav)
                          setCopiedPath(true)
                          setTimeout(() => setCopiedPath(false), 2000)
                        }
                      }}
                      className="text-slate-400 hover:text-white p-1"
                      title="Copier le chemin"
                    >
                      {copiedPath ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}
                    </button>
                  </div>
                </div>

                {/* Actions Fin */}
                <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setStep('input')}
                    className="rounded-xl border border-white/10 bg-white/[0.05] hover:bg-white/10 text-slate-200 font-medium py-2.5 px-4 text-xs flex items-center gap-2 transition-colors"
                  >
                    <Wand2 size={14} />
                    Générer un autre texte / chanson
                  </button>
                  <div className="flex items-center gap-2">
                    {replicationResult.audioUrl && (
                      <a
                        href={resolveVoiceAudioUrl(replicationResult.audioUrl)}
                        download={`voix_${replicationResult.slug || 'gen'}.wav`}
                        className="rounded-xl border border-white/10 bg-white/[0.08] hover:bg-white/[0.15] text-white font-medium py-2.5 px-4 text-xs flex items-center gap-2 transition-colors"
                      >
                        <Download size={14} /> Télécharger le WAV
                      </a>
                    )}
                    <button
                      type="button"
                      onClick={() => {
                        setStep('source')
                        setSampleData(null)
                        setSelectedProfileSlug(null)
                        setSpeechText('')
                        setSingingLyrics('')
                      }}
                      className="rounded-xl bg-violet-600 hover:bg-violet-500 text-white font-bold py-2.5 px-5 text-xs flex items-center gap-2 transition-colors"
                    >
                      <RotateCcw size={14} /> Nouvel Échantillon
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ========================================================================= */}
        {/* ONGLET 2 : PROFILS & VOIX ENREGISTRÉES */}
        {/* ========================================================================= */}
        {activeTab === 'profiles' && (
          <div className="space-y-5">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <div>
                <h2 className="text-base font-bold text-white flex items-center gap-2">
                  <UserCheck size={18} className="text-violet-400" />
                  Profils Vocaux Calibrés ({profiles.length})
                </h2>
                <p className="text-xs text-slate-400">
                  Voix de référence calibrées avec Whisper pour un clonage parfait.
                </p>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => { void handleCalibrateProfiles() }}
                  disabled={calibrating}
                  className="rounded-lg border border-violet-500/30 bg-violet-500/10 hover:bg-violet-500/20 px-3 py-1.5 text-xs text-violet-300 font-medium flex items-center gap-1.5 transition-colors"
                  title="Recalibrer toutes les transcriptions de référence"
                >
                  <Zap size={14} className={calibrating ? 'animate-spin' : ''} />
                  {calibrating ? 'Calibrage en cours...' : 'Recalibrer Whisper'}
                </button>
                <button
                  type="button"
                  onClick={() => { void loadProfilesAndTree() }}
                  className="rounded-lg border border-white/10 bg-white/[0.04] hover:bg-white/10 p-2 text-slate-400 hover:text-white transition-colors"
                  title="Actualiser la liste"
                >
                  <RefreshCw size={15} className={loadingData ? 'animate-spin' : ''} />
                </button>
              </div>
            </div>

            {profiles.length === 0 ? (
              <div className="rounded-2xl border border-white/10 bg-[#151924] p-10 text-center space-y-3">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-white/5 text-slate-500">
                  <UserCheck size={24} />
                </div>
                <h3 className="text-sm font-semibold text-slate-300">Aucun profil de voix enregistré</h3>
                <p className="text-xs text-slate-500 max-w-sm mx-auto">
                  Enregistrez un échantillon au micro ou importez un fichier dans le studio pour créer votre premier profil vocal.
                </p>
                <button
                  type="button"
                  onClick={() => { setActiveTab('studio'); setStep('source') }}
                  className="rounded-xl bg-violet-600 hover:bg-violet-500 text-white font-semibold py-2 px-4 text-xs transition-colors inline-flex items-center gap-2"
                >
                  <Mic size={14} /> Créer une voix maintenant
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {profiles.map((p) => (
                  <div
                    key={p.slug}
                    className="rounded-xl border border-white/10 bg-[#151924] p-4 space-y-3 flex flex-col justify-between hover:border-violet-500/30 transition-colors"
                  >
                    <div className="space-y-2">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <h3 className="text-sm font-bold text-white">{p.name}</h3>
                          <div className="flex items-center gap-2 text-[11px] text-slate-400 font-mono mt-0.5">
                            <span>slug: {p.slug}</span>
                            <span>·</span>
                            <span>{p.lang.toUpperCase()}</span>
                            <span>·</span>
                            <span>{p.duration_s.toFixed(1)}s</span>
                          </div>
                        </div>
                        <span className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-mono text-emerald-300">
                          Score: {Math.round(p.quality_score * 100)}%
                        </span>
                      </div>

                      {/* Transcription de référence */}
                      {p.transcript ? (
                        <div className="rounded-lg bg-black/40 border border-white/5 p-2 text-[11px] text-slate-300 italic font-serif">
                          <span className="font-sans text-[10px] text-violet-400 not-italic font-bold block mb-0.5">🎯 Référence calibrée :</span>
                          « {p.transcript} »
                        </div>
                      ) : (
                        <div className="text-[10px] text-amber-400/80 italic">
                          Non calibré (cliquez sur Recalibrer pour synchroniser).
                        </div>
                      )}
                    </div>

                    {/* Actions de profil */}
                    <div className="flex items-center justify-between gap-2 pt-2 border-t border-white/10">
                      <button
                        type="button"
                        onClick={() => handlePlayAudio(p.audioUrl)}
                        className="rounded-lg border border-white/10 bg-white/[0.06] hover:bg-white/[0.12] text-slate-200 py-1.5 px-3 text-xs font-medium flex items-center gap-1.5 transition-colors"
                      >
                        {isPlaying && playingUrl === resolveVoiceAudioUrl(p.audioUrl) ? (
                          <>
                            <Pause size={13} /> Pause
                          </>
                        ) : (
                          <>
                            <Play size={13} /> Écouter
                          </>
                        )}
                      </button>

                      <div className="flex items-center gap-1.5">
                        <button
                          type="button"
                          onClick={() => {
                            handleSelectExistingProfile(p)
                            setActiveTab('studio')
                          }}
                          className="rounded-lg bg-violet-600 hover:bg-violet-500 text-white py-1.5 px-3 text-xs font-bold flex items-center gap-1.5 transition-colors"
                        >
                          <Wand2 size={13} /> Utiliser cette voix
                        </button>
                        <button
                          type="button"
                          onClick={() => { void handleDeleteProfile(p.slug) }}
                          className="rounded-lg border border-white/10 bg-white/[0.04] hover:bg-rose-500/20 hover:border-rose-500/40 p-1.5 text-slate-400 hover:text-rose-300 transition-colors"
                          title="Supprimer ce profil"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ========================================================================= */}
        {/* ONGLET 3 : ARBORESCENCE & FICHIERS */}
        {/* ========================================================================= */}
        {activeTab === 'tree' && (
          <div className="space-y-5">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-white/10 pb-3">
              <div>
                <h2 className="text-base font-bold text-white flex items-center gap-2">
                  <FolderTree size={18} className="text-violet-400" />
                  Arborescence Organisée — application/output/voix/
                </h2>
                <p className="text-xs text-slate-400">
                  Dossiers de stockage : <span className="font-mono text-slate-300">echantillons, profils, generations, chansons, musiques, sessions</span>.
                </p>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => { void handleCleanLegacy() }}
                  className="rounded-lg border border-white/10 bg-white/[0.04] hover:bg-white/10 px-3 py-1.5 text-xs text-slate-300 font-medium transition-colors"
                >
                  Nettoyer anciens dossiers
                </button>
                <button
                  type="button"
                  onClick={() => { void loadProfilesAndTree() }}
                  className="rounded-lg border border-white/10 bg-white/[0.04] hover:bg-white/10 p-2 text-slate-400 hover:text-white transition-colors"
                >
                  <RefreshCw size={15} className={loadingData ? 'animate-spin' : ''} />
                </button>
              </div>
            </div>

            {treeData && (
              <div className="space-y-4">
                {/* Compteurs */}
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 font-mono text-xs">
                  <div className="rounded-xl border border-white/10 bg-[#151924] p-3">
                    <div className="text-[10px] uppercase text-slate-400">Échantillons</div>
                    <div className="text-base font-bold text-white mt-1">{treeData.counts.echantillons} fichiers</div>
                  </div>
                  <div className="rounded-xl border border-white/10 bg-[#151924] p-3">
                    <div className="text-[10px] uppercase text-slate-400">Profils</div>
                    <div className="text-base font-bold text-violet-400 mt-1">{treeData.counts.profils} profils</div>
                  </div>
                  <div className="rounded-xl border border-white/10 bg-[#151924] p-3">
                    <div className="text-[10px] uppercase text-slate-400">Générations</div>
                    <div className="text-base font-bold text-emerald-400 mt-1">{treeData.counts.generations} audios</div>
                  </div>
                  <div className="rounded-xl border border-white/10 bg-[#151924] p-3">
                    <div className="text-[10px] uppercase text-slate-400">Chansons</div>
                    <div className="text-base font-bold text-fuchsia-400 mt-1">{treeData.chansons?.length || 0} morceaux</div>
                  </div>
                  <div className="rounded-xl border border-white/10 bg-[#151924] p-3">
                    <div className="text-[10px] uppercase text-slate-400">Musiques</div>
                    <div className="text-base font-bold text-amber-400 mt-1">{treeData.counts.musiques || availableTracks.length} pistes</div>
                  </div>
                </div>

                {/* Liste des Chansons Récentes */}
                {treeData.chansons && treeData.chansons.length > 0 && (
                  <div className="rounded-2xl border border-fuchsia-500/20 bg-[#151924] p-4 sm:p-5 space-y-3">
                    <h3 className="text-sm font-bold text-white flex items-center gap-2">
                      <Music size={16} className="text-fuchsia-400" />
                      Chansons & Morceaux Créés (chansons/)
                    </h3>
                    <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                      {treeData.chansons.map((c) => (
                        <div
                          key={c.name}
                          className="rounded-xl border border-white/5 bg-black/30 p-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
                        >
                          <div className="space-y-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="font-semibold text-white">{c.voice_name}</span>
                              <span className="text-[10px] text-fuchsia-400 font-mono">{c.style}</span>
                              <span className="text-[10px] text-slate-400 font-mono">{c.date}</span>
                              <span className="text-[10px] text-emerald-400 font-mono">{c.duration_s.toFixed(1)}s</span>
                            </div>
                            {c.text && (
                              <p className="text-[11px] text-slate-300 italic truncate max-w-lg">
                                « {c.text} »
                              </p>
                            )}
                          </div>
                          <div className="flex items-center gap-2 shrink-0">
                            <button
                              type="button"
                              onClick={() => handlePlayAudio(`/api/voice/studio/generation/${c.name}/audio`)}
                              className="rounded-lg border border-white/10 bg-white/[0.05] hover:bg-white/[0.12] text-slate-200 py-1 px-2.5 text-[11px] font-medium flex items-center gap-1.5 transition-colors"
                            >
                              <Play size={12} /> Écouter
                            </button>
                            <a
                              href={resolveVoiceAudioUrl(`/api/voice/studio/generation/${c.name}/audio`)}
                              download={c.name}
                              className="rounded-lg border border-white/10 bg-white/[0.05] hover:bg-white/[0.12] text-slate-200 p-1.5 transition-colors"
                              title="Télécharger"
                            >
                              <Download size={13} />
                            </a>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Liste des Générations Récentes */}
                <div className="rounded-2xl border border-white/10 bg-[#151924] p-4 sm:p-5 space-y-3">
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    <Volume2 size={16} className="text-emerald-400" />
                    Dernières Synthèses Vocales (generations/)
                  </h3>
                  {treeData.generations.length === 0 ? (
                    <div className="text-xs text-slate-500 py-3 text-center">Aucune génération récente.</div>
                  ) : (
                    <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
                      {treeData.generations.map((g) => (
                        <div
                          key={g.name}
                          className="rounded-xl border border-white/5 bg-black/30 p-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
                        >
                          <div className="space-y-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="font-semibold text-white">{g.voice_name}</span>
                              <span className="text-[10px] text-slate-400 font-mono">{g.date}</span>
                              <span className="text-[10px] text-emerald-400 font-mono">{g.duration_s.toFixed(1)}s</span>
                            </div>
                            {g.text && (
                              <p className="text-[11px] text-slate-300 italic truncate max-w-lg">
                                « {g.text} »
                              </p>
                            )}
                          </div>
                          <div className="flex items-center gap-2 shrink-0">
                            <button
                              type="button"
                              onClick={() => handlePlayAudio(`/api/voice/studio/generation/${g.name}/audio`)}
                              className="rounded-lg border border-white/10 bg-white/[0.05] hover:bg-white/[0.12] text-slate-200 py-1 px-2.5 text-[11px] font-medium flex items-center gap-1.5 transition-colors"
                            >
                              <Play size={12} /> Écouter
                            </button>
                            <a
                              href={resolveVoiceAudioUrl(`/api/voice/studio/generation/${g.name}/audio`)}
                              download={g.name}
                              className="rounded-lg border border-white/10 bg-white/[0.05] hover:bg-white/[0.12] text-slate-200 p-1.5 transition-colors"
                              title="Télécharger"
                            >
                              <Download size={13} />
                            </a>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  )
}
