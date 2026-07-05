// Panel d analyse video pedagogique pour le module Apprentissage.
// - Upload video (mp4, webm, mov...)
// - Extraction de frames cotes client via <video> + Canvas (pas de Python requis)
// - Analyse via qwen3-vl:30b (analyzeVideoFrames) pour description temporelle
// - Chat follow-up: poser des questions sur la video (qwen3-vl voit tout le contexte)

import { useCallback, useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Film,
  Loader2,
  Play,
  RefreshCw,
  SendHorizontal,
  Sparkles,
  Upload,
  X,
} from 'lucide-react'
import { analyzeVideoFrames, askAboutImage } from '../../services/visionService'

interface FrameSnapshot {
  dataUrl: string
  timestampSec: number
}

interface QAEntry {
  id: string
  role: 'user' | 'assistant'
  text: string
}

async function extractFramesFromVideo(file: File, frameCount: number): Promise<FrameSnapshot[]> {
  const url = URL.createObjectURL(file)
  const video = document.createElement('video')
  video.preload = 'auto'
  video.muted = true
  video.playsInline = true
  video.src = url

  const cleanup = () => {
    try { URL.revokeObjectURL(url) } catch { /* ignore */ }
  }

  await new Promise<void>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('Chargement video trop long.')), 30000)
    video.addEventListener('loadedmetadata', () => { clearTimeout(timer); resolve() }, { once: true })
    video.addEventListener('error', () => { clearTimeout(timer); reject(new Error('Video illisible.')) }, { once: true })
  })

  const duration = video.duration || 0
  if (!duration || !Number.isFinite(duration)) {
    cleanup()
    throw new Error('Duree de la video indeterminee.')
  }

  const w = video.videoWidth
  const h = video.videoHeight
  const maxSize = 1024
  const largest = Math.max(w, h)
  const scale = largest > maxSize ? maxSize / largest : 1
  const targetW = Math.round(w * scale)
  const targetH = Math.round(h * scale)

  const canvas = document.createElement('canvas')
  canvas.width = targetW
  canvas.height = targetH
  const ctx = canvas.getContext('2d')
  if (!ctx) {
    cleanup()
    throw new Error('Canvas 2D indisponible.')
  }

  const frames: FrameSnapshot[] = []
  // Repartition uniforme sur la duree avec marge de 0.3s au debut/fin
  const points: number[] = []
  const safeStart = Math.min(0.3, duration * 0.05)
  const safeEnd = Math.max(duration - 0.3, duration * 0.95)
  for (let i = 0; i < frameCount; i += 1) {
    const ratio = frameCount === 1 ? 0.5 : i / (frameCount - 1)
    const t = safeStart + (safeEnd - safeStart) * ratio
    points.push(t)
  }

  try {
    for (const t of points) {
      await new Promise<void>((resolve, reject) => {
        const onSeeked = () => {
          video.removeEventListener('seeked', onSeeked)
          try {
            ctx.drawImage(video, 0, 0, targetW, targetH)
            const dataUrl = canvas.toDataURL('image/jpeg', 0.85)
            frames.push({ dataUrl, timestampSec: t })
            resolve()
          } catch (err) {
            reject(err)
          }
        }
        video.addEventListener('seeked', onSeeked, { once: true })
        video.currentTime = Math.min(t, duration - 0.05)
      })
    }
  } finally {
    cleanup()
  }

  return frames
}

export default function VideoAnalysisPanel() {
  const [file, setFile] = useState<File | null>(null)
  const [fileUrl, setFileUrl] = useState<string | null>(null)
  const [frameCount, setFrameCount] = useState(5)
  const [frames, setFrames] = useState<FrameSnapshot[]>([])
  const [description, setDescription] = useState('')
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [progress, setProgress] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [qa, setQa] = useState<QAEntry[]>([])
  const [question, setQuestion] = useState('')
  const [askingQuestion, setAskingQuestion] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    return () => {
      if (fileUrl) URL.revokeObjectURL(fileUrl)
    }
  }, [fileUrl])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [qa])

  const handleFileChange = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const f = event.target.files?.[0]
    if (!f) return
    if (!/^video\//i.test(f.type) && !/\.(mp4|webm|mov|avi|mkv|m4v)$/i.test(f.name)) {
      setError('Format non supporte. Utilise mp4, webm, mov, avi, mkv.')
      return
    }
    if (fileUrl) URL.revokeObjectURL(fileUrl)
    setFile(f)
    setFileUrl(URL.createObjectURL(f))
    setFrames([])
    setDescription('')
    setQa([])
    setError(null)
  }, [fileUrl])

  const handleRemoveFile = useCallback(() => {
    if (fileUrl) URL.revokeObjectURL(fileUrl)
    setFile(null)
    setFileUrl(null)
    setFrames([])
    setDescription('')
    setQa([])
    setError(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }, [fileUrl])

  const analyze = useCallback(async () => {
    if (!file || isAnalyzing) return
    setIsAnalyzing(true)
    setError(null)
    setDescription('')
    setQa([])
    setProgress('Extraction des frames...')

    try {
      const extracted = await extractFramesFromVideo(file, frameCount)
      setFrames(extracted)
      setProgress(`${extracted.length} frames extraites. Analyse avec Qwen3-VL...`)

      const result = await analyzeVideoFrames(
        extracted.map((f) => ({ kind: 'dataUrl', data: f.dataUrl, timestamp: f.timestampSec })),
        {
          task: 'describe_video',
          language: 'fr',
          preferQuality: true,
          temperature: 0.35,
        },
      )
      setDescription(result.description)
      setProgress(`Analyse terminee (${result.modelUsed}, ${Math.round(result.durationMs / 100) / 10}s).`)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setProgress('')
    } finally {
      setIsAnalyzing(false)
    }
  }, [file, frameCount, isAnalyzing])

  const askQuestion = useCallback(async () => {
    const q = question.trim()
    if (!q || askingQuestion || frames.length === 0) return
    setAskingQuestion(true)
    setError(null)

    const userEntry: QAEntry = { id: `q-${Date.now()}`, role: 'user', text: q }
    setQa((prev) => [...prev, userEntry])
    setQuestion('')

    try {
      // Re-utilise la premiere frame (representative) pour la question.
      // Si plus de precision requise, on pourrait ajouter un endpoint multi-frame Q/A.
      const firstFrame = frames[0]
      const answer = await askAboutImage(
        { kind: 'dataUrl', data: firstFrame.dataUrl },
        `Contexte: description generale de la video -> "${description}"\n\nQuestion: ${q}`,
        { language: 'fr', preferQuality: true },
      )
      setQa((prev) => [...prev, { id: `a-${Date.now()}`, role: 'assistant', text: answer || '(pas de reponse)' }])
    } catch (err) {
      setQa((prev) => [...prev, {
        id: `e-${Date.now()}`,
        role: 'assistant',
        text: `Erreur: ${err instanceof Error ? err.message : String(err)}`,
      }])
    } finally {
      setAskingQuestion(false)
    }
  }, [askingQuestion, description, frames, question])

  return (
    <div className="flex flex-col gap-4">
      <div
        className="rounded-2xl p-5"
        style={{
          background: 'linear-gradient(135deg, rgba(34,211,238,0.08), rgba(167,139,250,0.08))',
          border: '1px solid rgba(34,211,238,0.2)',
        }}
      >
        <div className="flex items-start gap-3">
          <div className="shrink-0 rounded-xl bg-cyan-500/20 p-2">
            <Film size={20} className="text-cyan-300" />
          </div>
          <div className="flex-1">
            <h2 className="text-lg font-semibold text-white">Analyse video pedagogique</h2>
            <p className="mt-1 text-sm text-slate-300/80">
              Charge une video (cours, demonstration, experience) et Qwen3-VL la decrit chronologiquement.
              Pose ensuite des questions pour comprendre chaque etape.
            </p>
          </div>
        </div>
      </div>

      {/* Zone d upload */}
      {!file && (
        <div
          onClick={() => fileInputRef.current?.click()}
          className="group flex cursor-pointer flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed border-white/15 bg-white/[0.02] px-6 py-10 transition hover:border-cyan-400/40 hover:bg-cyan-500/[0.04]"
        >
          <div className="rounded-full bg-white/5 p-3 transition group-hover:bg-cyan-500/10">
            <Upload size={28} className="text-white/40 group-hover:text-cyan-300" />
          </div>
          <div className="text-center">
            <p className="text-sm font-medium text-white/80">Glisse une video ou clique pour choisir</p>
            <p className="mt-1 text-xs text-white/40">mp4, webm, mov, avi, mkv — max ~200 Mo recommande</p>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept="video/*"
            className="hidden"
            onChange={handleFileChange}
          />
        </div>
      )}

      {/* Video chargee */}
      {file && fileUrl && (
        <div className="rounded-2xl border border-white/10 bg-black/30 p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start">
            <video
              src={fileUrl}
              controls
              playsInline
              className="w-full max-w-md rounded-xl bg-black"
              style={{ maxHeight: 260 }}
            />
            <div className="flex flex-1 flex-col gap-2">
              <div className="flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium text-white/90">{file.name}</div>
                  <div className="text-xs text-white/40">
                    {(file.size / 1024 / 1024).toFixed(1)} Mo · {file.type || 'video'}
                  </div>
                </div>
                <button
                  onClick={handleRemoveFile}
                  className="shrink-0 rounded-lg border border-white/10 bg-white/[0.05] p-1.5 text-white/50 hover:text-red-300"
                  title="Retirer la video"
                >
                  <X size={14} />
                </button>
              </div>

              <div className="flex items-center gap-2">
                <label className="text-xs text-white/60">Frames:</label>
                <select
                  value={frameCount}
                  onChange={(e) => setFrameCount(Number(e.target.value))}
                  className="rounded-lg border border-white/10 bg-white/[0.05] px-2 py-1 text-xs text-white/80"
                  disabled={isAnalyzing}
                >
                  <option value={3}>3 (rapide)</option>
                  <option value={5}>5 (equilibre)</option>
                  <option value={8}>8 (detaille)</option>
                  <option value={12}>12 (complet)</option>
                </select>
              </div>

              <button
                onClick={analyze}
                disabled={isAnalyzing}
                className="mt-1 inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm font-medium text-white transition"
                style={{
                  background: isAnalyzing
                    ? 'linear-gradient(135deg, #64748b, #475569)'
                    : 'linear-gradient(135deg, #06b6d4, #8b5cf6)',
                  opacity: isAnalyzing ? 0.7 : 1,
                  cursor: isAnalyzing ? 'not-allowed' : 'pointer',
                }}
              >
                {isAnalyzing
                  ? <><Loader2 size={14} className="animate-spin" /> Analyse en cours...</>
                  : frames.length > 0
                    ? <><RefreshCw size={14} /> Reanalyser</>
                    : <><Sparkles size={14} /> Analyser la video</>
                }
              </button>
            </div>
          </div>

          {progress && !error && (
            <div className="mt-3 flex items-center gap-2 rounded-lg border border-cyan-400/15 bg-cyan-500/[0.05] px-3 py-2 text-xs text-cyan-200">
              {isAnalyzing && <Loader2 size={12} className="animate-spin" />}
              <span>{progress}</span>
            </div>
          )}

          {error && (
            <div className="mt-3 rounded-lg border border-red-400/25 bg-red-500/10 px-3 py-2 text-xs text-red-300">
              {error}
            </div>
          )}
        </div>
      )}

      {/* Frames extraites (thumbnails) */}
      {frames.length > 0 && (
        <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-3">
          <div className="mb-2 flex items-center gap-2 text-[10px] uppercase tracking-[0.22em] text-white/40">
            <Play size={10} />
            <span>{frames.length} frames extraites chronologiquement</span>
          </div>
          <div className="flex gap-2 overflow-x-auto pb-1">
            {frames.map((f, i) => (
              <div key={i} className="shrink-0">
                <img
                  src={f.dataUrl}
                  alt={`Frame ${i + 1}`}
                  className="h-20 w-32 rounded-lg border border-white/10 object-cover"
                />
                <div className="mt-0.5 text-center text-[9px] text-white/40">
                  {f.timestampSec.toFixed(1)}s
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Description temporelle */}
      <AnimatePresence>
        {description && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="rounded-2xl border border-purple-400/20 bg-purple-500/[0.06] p-4"
          >
            <div className="mb-2 flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-purple-300/80">
              <Sparkles size={12} />
              <span>Description chronologique</span>
            </div>
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-white/85">{description}</p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Q/R sur la video */}
      {frames.length > 0 && description && (
        <div className="flex flex-col gap-3 rounded-2xl border border-white/10 bg-white/[0.02] p-4">
          <div className="text-xs uppercase tracking-[0.18em] text-white/40">
            Questions sur la video
          </div>

          {qa.length > 0 && (
            <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
              {qa.map((entry) => (
                <div
                  key={entry.id}
                  className={`flex ${entry.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[85%] rounded-xl px-3 py-2 text-sm leading-relaxed ${
                      entry.role === 'user'
                        ? 'bg-indigo-500/15 text-white/90 border border-indigo-400/20'
                        : 'bg-white/[0.05] text-white/80 border border-white/10'
                    }`}
                  >
                    {entry.text}
                  </div>
                </div>
              ))}
              <div ref={endRef} />
            </div>
          )}

          <div className="flex items-end gap-2">
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  void askQuestion()
                }
              }}
              placeholder="Ex: A quelle seconde parle-t-on de... ? Qu est-ce qui se passe a la fin ?"
              className="min-h-[40px] max-h-32 flex-1 resize-none rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white/90 placeholder:text-white/30 focus:border-cyan-400/40 focus:outline-none"
              rows={1}
              disabled={askingQuestion}
            />
            <button
              onClick={() => void askQuestion()}
              disabled={askingQuestion || !question.trim()}
              className="inline-flex items-center justify-center rounded-xl border border-cyan-400/30 bg-cyan-500/10 p-2.5 text-cyan-200 hover:bg-cyan-500/20 disabled:opacity-40"
              title="Envoyer"
            >
              {askingQuestion
                ? <Loader2 size={16} className="animate-spin" />
                : <SendHorizontal size={16} />
              }
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
