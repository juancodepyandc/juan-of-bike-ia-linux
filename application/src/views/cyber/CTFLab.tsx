import { useEffect, useMemo, useRef, useState } from 'react'
import { Check, Clock, Flag, HelpCircle, Loader2, Lock, Star, Trophy, Unlock } from 'lucide-react'
import { sha256 } from '../../services/cyber/hashService'
import { useCTFStore, type CTFChallenge } from '../../services/cyber/ctfStore'
import VoicePushToTalk from '../../components/VoicePushToTalk'

const CHALLENGES: CTFChallenge[] = [
  {
    id: 'ctf-01-b64',
    title: 'Base64 basics',
    category: 'crypto',
    difficulty: 1,
    description: 'Un coéquipier t envoie ce message : QVVST1JBezFfYmFzZTY0X2Z1bnNfdGltZX0= — trouve le flag caché.',
    xpReward: 50,
    hints: [
      'Le format du flag est AURORA{...}',
      'Essaye le décodage Base64 dans l onglet Encoding du lab Crypto.',
    ],
    flagHash: '', // calculé à runtime
    solutionMarkdown: 'Décoder `QVVST1JBezFfYmFzZTY0X2Z1bnNfdGltZX0=` → `AURORA{1_base64_funs_time}`.',
  },
  {
    id: 'ctf-02-rot13',
    title: 'Rot, rot, rot',
    category: 'crypto',
    difficulty: 1,
    description: 'NHEBEN{ebg13_vf_abg_rapelcgvba} — c est pas du chiffrement, mais comment le lire ?',
    xpReward: 50,
    hints: ['Rotation de 13 places dans l alphabet', 'Utilise ROT13 dans Crypto Lab'],
    flagHash: '',
    solutionMarkdown: 'ROT13 renverse la rotation : `AURORA{rot13_is_not_encryption}`.',
  },
  {
    id: 'ctf-03-sha',
    title: 'Mini hash',
    category: 'crypto',
    difficulty: 2,
    description: 'Le mot secret est un mot français de 5 lettres commençant par "s". Son SHA-256 est 8d03c58ebaac0afc4a6f14ca9a26762d9a8b55d8fd3aebcf1d432dcfea5b0a17. Trouve le mot (le flag est ce mot en majuscules).',
    xpReward: 100,
    hints: ['5 lettres, commence par "s", français commun', 'Essaye: salut, soeur, soiree...'],
    flagHash: '',
    solutionMarkdown: 'Le mot est `soeur`. Flag : `SOEUR`.',
  },
  {
    id: 'ctf-04-exif',
    title: 'Spy in the picture',
    category: 'forensics',
    difficulty: 2,
    description: 'Les métadonnées EXIF cachent souvent des informations sensibles (GPS, appareil, commentaires). Quel champ EXIF est couramment utilisé pour cacher un texte court ? (flag = nom du champ en MAJUSCULES)',
    xpReward: 75,
    hints: ['Pense aux champs texte', 'Il existe un champ "User..." qui accepte n importe quel texte'],
    flagHash: '',
    solutionMarkdown: 'Le champ EXIF `UserComment` (ID 0x9286) est un champ libre. Flag : `USERCOMMENT`.',
  },
  {
    id: 'ctf-05-lsb',
    title: 'Least Significant',
    category: 'stego',
    difficulty: 3,
    description: 'La stéganographie LSB modifie le bit le moins significatif de chaque canal pixel. Si tu modifies les 1 bit LSB de 3 canaux RGB par pixel dans une image 800×600, combien de bits peux-tu cacher ? (réponse = flag exact, juste le nombre)',
    xpReward: 100,
    hints: ['800 × 600 × 3 canaux × 1 bit = ?'],
    flagHash: '',
    solutionMarkdown: '800 × 600 × 3 = 1440000 bits. Flag : `1440000`.',
  },
  {
    id: 'ctf-06-jwt',
    title: 'alg:none',
    category: 'web',
    difficulty: 3,
    description: 'Quelle valeur de header JWT permet à un serveur mal configuré d accepter un token sans vérifier la signature ? (flag = la valeur exacte de "alg")',
    xpReward: 100,
    hints: ['C est littéralement le nom d un algorithme "vide"'],
    flagHash: '',
    solutionMarkdown: '`alg: none` désactive la vérification. Flag : `none`.',
  },
  {
    id: 'ctf-07-sqli',
    title: 'Bypass login',
    category: 'web',
    difficulty: 3,
    description: 'Quelle est la payload SQL classique (très courte, sans espaces autour du OR) qui bypass un login vulnérable ? Format: quote-espace-OR-espace-quote-1quote-egal-quote-1',
    xpReward: 100,
    hints: ['Tautology', '\' OR \'1\'=\'1'],
    flagHash: '',
    solutionMarkdown: 'Flag : `\' OR \'1\'=\'1`.',
  },
  {
    id: 'ctf-08-vigenere',
    title: 'Vigenère key',
    category: 'crypto',
    difficulty: 4,
    description: 'Le chiffre de Vigenère utilise une clé répétée. Le texte "Aurtrl pgs" chiffré avec la clé "AURORA" donne "aurora_fte". Quelle est la clé Vigenère de 6 lettres qui commence par "A" et est le nom du projet ? (flag = clé en MAJUSCULES)',
    xpReward: 125,
    hints: ['C est le nom du produit actuel'],
    flagHash: '',
    solutionMarkdown: 'Flag : `AURORA`.',
  },
  {
    id: 'ctf-09-xss',
    title: 'Reflected XSS',
    category: 'web',
    difficulty: 3,
    description: 'Une balise HTML permet de déclencher JavaScript via son attribut "onerror" même si elle ne charge pas correctement. Laquelle ? (flag = nom de la balise sans les chevrons, minuscules)',
    xpReward: 100,
    hints: ['Balise media courte', 'Charge une ressource'],
    flagHash: '',
    solutionMarkdown: 'Flag : `img`. Payload typique : `<img src=x onerror=alert(1)>`.',
  },
  {
    id: 'ctf-10-chain',
    title: 'Chaîne de stego',
    category: 'misc',
    difficulty: 5,
    description: 'Combine trois concepts : (1) base64 décode (2) du ROT13 qui révèle (3) un mot MITRE ATT&CK tactic. Pour éviter le puzzle long: quelle est la tactique MITRE qui commence par "I" et concerne l accès initial ? (flag = nom en MAJUSCULES avec underscores à la place des espaces)',
    xpReward: 200,
    hints: ['MITRE ATT&CK a 14 tactiques', 'Celle-ci est la première phase d une attaque'],
    flagHash: '',
    solutionMarkdown: 'La tactique MITRE TA0001 est `Initial Access`. Flag : `INITIAL_ACCESS`.',
  },
]

const EXPECTED_FLAGS: Record<string, string> = {
  'ctf-01-b64': 'AURORA{1_base64_funs_time}',
  'ctf-02-rot13': 'AURORA{rot13_is_not_encryption}',
  'ctf-03-sha': 'SOEUR',
  'ctf-04-exif': 'USERCOMMENT',
  'ctf-05-lsb': '1440000',
  'ctf-06-jwt': 'none',
  'ctf-07-sqli': "' OR '1'='1",
  'ctf-08-vigenere': 'AURORA',
  'ctf-09-xss': 'img',
  'ctf-10-chain': 'INITIAL_ACCESS',
}

export default function CTFLab() {
  const progress = useCTFStore((s) => s.progress)
  const totalXp = useCTFStore((s) => s.totalXp)
  const solvedCount = Object.values(progress).filter((p) => p.solved).length
  const total = CHALLENGES.length

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 flex items-center gap-4">
        <Trophy size={20} className="text-amber-300" />
        <div className="flex-1">
          <h2 className="text-white text-[15px] font-semibold">Capture The Flag — 10 défis progressifs</h2>
          <p className="text-[12px] text-white/60">Apprends en résolvant. Les flags sont vérifiés localement par hash SHA-256.</p>
        </div>
        <div className="text-right">
          <div className="text-[24px] font-bold text-white leading-none">{solvedCount}/{total}</div>
          <div className="text-[11px] text-white/55">{totalXp} XP</div>
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {CHALLENGES.map((c) => <ChallengeCard key={c.id} challenge={c} />)}
      </div>
    </div>
  )
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}m${s.toString().padStart(2, '0')}`
}

function ChallengeCard({ challenge }: { challenge: CTFChallenge }) {
  const prog = useCTFStore((s) => s.progress[challenge.id])
  const markSolved = useCTFStore((s) => s.markSolved)
  const recordAttempt = useCTFStore((s) => s.recordAttempt)
  const useHint = useCTFStore((s) => s.useHint)

  const [open, setOpen] = useState(false)
  const [flag, setFlag] = useState('')
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)
  const [revealed, setRevealed] = useState(0)
  const [showSolution, setShowSolution] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const startedAtRef = useRef<number | null>(null)
  const [finalTime, setFinalTime] = useState<number | null>(null)

  // Chrono starts when user first enters a guess OR reveals a hint. Stops on
  // solve. Persisted-per-session only — refresh = new timer.
  useEffect(() => {
    if (prog?.solved || startedAtRef.current === null) return
    const id = window.setInterval(() => {
      setElapsed(Math.floor((Date.now() - (startedAtRef.current ?? Date.now())) / 1000))
    }, 1000)
    return () => window.clearInterval(id)
  }, [prog?.solved, elapsed])

  const ensureTimer = () => {
    if (startedAtRef.current === null && !prog?.solved) {
      startedAtRef.current = Date.now()
    }
  }

  const submit = async () => {
    setBusy(true); setMsg('')
    ensureTimer()
    try {
      recordAttempt(challenge.id)
      const target = EXPECTED_FLAGS[challenge.id] || ''
      const entered = flag.trim()
      const entHash = await sha256(entered.toLowerCase())
      const expHash = await sha256(target.toLowerCase())
      if (entHash === expHash) {
        const penalty = Math.max(0, revealed * 10)
        const duration = startedAtRef.current ? Math.floor((Date.now() - startedAtRef.current) / 1000) : 0
        setFinalTime(duration)
        markSolved(challenge.id, Math.max(10, challenge.xpReward - penalty))
        setMsg(`✓ Correct ! XP gagné en ${formatDuration(duration)}.`)
      } else {
        setMsg('✗ Essaye encore.')
      }
    } finally { setBusy(false) }
  }

  const diffStars = useMemo(() =>
    Array.from({ length: 5 }, (_, i) => i < challenge.difficulty), [challenge.difficulty])

  return (
    <div className={`rounded-xl border p-4 ${prog?.solved ? 'border-emerald-500/40 bg-emerald-500/[0.04]' : 'border-white/10 bg-white/[0.02]'}`}>
      <div className="flex items-start gap-2 mb-1">
        {prog?.solved ? <Unlock size={14} className="text-emerald-300 shrink-0 mt-1" /> : <Lock size={14} className="text-white/40 shrink-0 mt-1" />}
        <div className="flex-1 min-w-0">
          <h3 className="text-[13px] font-semibold text-white leading-tight">{challenge.title}</h3>
          <div className="flex items-center gap-2 text-[10px] text-white/50 mt-0.5">
            <span className="rounded bg-white/5 border border-white/10 px-1.5 py-0.5 uppercase">{challenge.category}</span>
            <span className="flex gap-0.5">
              {diffStars.map((on, i) => <Star key={i} size={9} className={on ? 'text-amber-300 fill-amber-300' : 'text-white/20'} />)}
            </span>
            <span className="ml-auto text-amber-300 font-mono">+{challenge.xpReward} XP</span>
            {startedAtRef.current && !prog?.solved && (
              <span className="inline-flex items-center gap-1 rounded bg-purple-500/15 border border-purple-500/30 px-1.5 py-0.5 text-purple-200 font-mono">
                <Clock size={9} /> {formatDuration(elapsed)}
              </span>
            )}
            {prog?.solved && finalTime !== null && (
              <span className="inline-flex items-center gap-1 rounded bg-emerald-500/15 border border-emerald-500/30 px-1.5 py-0.5 text-emerald-200 font-mono">
                <Clock size={9} /> résolu en {formatDuration(finalTime)}
              </span>
            )}
          </div>
        </div>
      </div>
      <p className="text-[12px] text-white/70 leading-relaxed mt-2">{challenge.description}</p>
      {!prog?.solved && (
        <>
          <div className="mt-3 flex gap-2">
            <input value={flag} onChange={(e) => setFlag(e.target.value)} placeholder="flag"
              className="flex-1 rounded-lg bg-black/40 border border-white/10 px-3 py-1.5 text-[12px] text-white/90 font-mono" />
            <VoicePushToTalk
              onTranscript={(t) => setFlag((prev) => (prev?.trim() ? `${prev}${t}` : t.replace(/\s+/g, '')))}
              label="Dicter le flag"
              size={30}
            />
            <button disabled={busy} onClick={submit}
              className="inline-flex items-center gap-2 rounded-lg bg-red-500/20 border border-red-500/40 text-red-200 px-3 py-1.5 text-[12px] hover:bg-red-500/30 disabled:opacity-50">
              {busy ? <Loader2 size={13} className="animate-spin" /> : <Flag size={13} />} valider
            </button>
          </div>
          {msg && <p className="mt-2 text-[11px] text-white/75">{msg}</p>}
          <div className="mt-3 flex gap-2 flex-wrap">
            {challenge.hints.slice(0, revealed).map((h, i) => (
              <div key={i} className="w-full rounded-lg bg-amber-500/10 border border-amber-500/30 px-2 py-1.5 text-[11px] text-amber-100">
                💡 {h}
              </div>
            ))}
            {revealed < challenge.hints.length && (
              <button onClick={() => { ensureTimer(); setRevealed((r) => r + 1); useHint(challenge.id) }}
                className="inline-flex items-center gap-1 rounded-md bg-amber-500/15 border border-amber-500/30 px-2 py-1 text-[11px] text-amber-200 hover:bg-amber-500/25">
                <HelpCircle size={11} /> indice −10 XP ({challenge.hints.length - revealed} restant)
              </button>
            )}
          </div>
        </>
      )}
      {prog?.solved && (
        <div className="mt-3">
          <p className="text-[11px] text-emerald-200 flex items-center gap-1"><Check size={12} /> Résolu</p>
          <button onClick={() => setShowSolution((v) => !v)}
            className="mt-1 text-[11px] text-white/60 hover:text-white/85 underline">
            {showSolution ? 'masquer' : 'voir la solution'}
          </button>
          {showSolution && (
            <div className="mt-2 rounded-lg bg-black/30 border border-white/10 p-2 text-[11px] text-white/75">
              {challenge.solutionMarkdown}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
