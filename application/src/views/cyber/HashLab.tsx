import { useMemo, useState } from 'react'
import { Fingerprint, Hammer, Loader2, Search, ShieldAlert } from 'lucide-react'
import {
  crackSha256Dict,
  hmacSha256,
  identifyHash,
  md5,
  sha1,
  sha256,
  sha384,
  sha512,
} from '../../services/cyber/hashService'
import { generateSalt, hashWithSalt, lookupHash } from '../../services/cyber/rainbowTableDemo'

export default function HashLab() {
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
        <h2 className="text-white text-[15px] font-semibold mb-1">Hashing — empreintes cryptographiques</h2>
        <p className="text-[12px] text-white/60 leading-relaxed">
          Un hash est irréversible mais <strong>sensible aux collisions</strong> pour les algos faibles (MD5, SHA-1).
          Cet atelier compare les algos et montre pourquoi <strong>saler</strong> + utiliser un KDF (Argon2/bcrypt) est indispensable.
        </p>
      </div>
      <HashCalculator />
      <RainbowTablePanel />
      <BirthdayCollisionPanel />
      <HMACPanel />
      <IdentifierPanel />
      <CrackerPanel />
    </div>
  )
}

function BirthdayCollisionPanel() {
  const [bits, setBits] = useState(24)
  const [searching, setSearching] = useState(false)
  const [found, setFound] = useState<{ a: string; b: string; hash: string; tries: number; ms: number } | null>(null)

  const search = async () => {
    setSearching(true); setFound(null)
    try {
      const seen = new Map<string, string>()
      const start = performance.now()
      const enc = new TextEncoder()
      const mask = (1n << BigInt(bits)) - 1n
      for (let i = 0; i < 5_000_000; i += 1) {
        const msg = `Aurora-msg-${i}-${Math.random().toString(36).slice(2, 8)}`
        // SHA-256 first 4-8 bytes → truncate to `bits` bits.
        const buf = await crypto.subtle.digest('SHA-256', enc.encode(msg))
        const bytes = new Uint8Array(buf, 0, 8)
        let h = 0n
        for (let j = 0; j < 8; j += 1) h = (h << 8n) | BigInt(bytes[j])
        const truncated = (h & mask).toString(16)
        const prev = seen.get(truncated)
        if (prev && prev !== msg) {
          setFound({ a: prev, b: msg, hash: truncated, tries: i + 1, ms: performance.now() - start })
          return
        }
        seen.set(truncated, msg)
        if (i % 1000 === 0) {
          await new Promise((r) => setTimeout(r, 0)) // yield
        }
        if (performance.now() - start > 15000) {
          // Timeout to avoid blocking forever on high bits.
          break
        }
      }
    } finally { setSearching(false) }
  }

  // Expected attempts for 50% probability of collision = √(π/2 · 2^bits) ≈ 1.25·√(2^bits).
  const expectedTries = Math.round(1.25 * Math.sqrt(2 ** bits))

  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
      <h3 className="text-[12px] font-semibold text-white/80 uppercase tracking-wider mb-3 flex items-center gap-2">
        <Hammer size={13} /> Birthday attack · démontrer une collision SHA-256 tronquée
      </h3>
      <p className="text-[11px] text-white/55 mb-3">
        Théorème : pour trouver une collision sur N bits, il faut ~√(2^N) essais
        (paradoxe des anniversaires). Sur SHA-256 complet (256 bits), c'est
        2¹²⁸ — impossible. Mais sur N=20-30 bits, c'est ms à secondes.
      </p>
      <div className="flex items-center gap-3 mb-3">
        <label className="text-[11px] text-white/65 flex items-center gap-2">
          Bits tronqués
          <input type="range" min={16} max={32} value={bits} onChange={(e) => setBits(Number(e.target.value))} className="w-32" />
          <span className="font-mono text-white/85 w-8">{bits}</span>
        </label>
        <span className="text-[10px] text-white/50 font-mono">attendu ≈ {expectedTries.toLocaleString()} essais</span>
        <button onClick={search} disabled={searching}
          className="ml-auto rounded-lg bg-amber-500/20 border border-amber-500/40 text-amber-200 px-3 py-1.5 text-[12px] hover:bg-amber-500/30 disabled:opacity-50">
          {searching ? <><Loader2 size={12} className="inline animate-spin mr-1.5" /> Recherche…</> : 'Trouver une collision'}
        </button>
      </div>
      {found && (
        <div className="rounded-lg bg-emerald-500/10 border border-emerald-500/30 p-3 text-[11px] font-mono">
          <div className="text-emerald-200 font-semibold mb-1">✓ Collision trouvée en {found.tries.toLocaleString()} essais ({(found.ms / 1000).toFixed(2)}s)</div>
          <div className="text-white/80">A = {found.a}</div>
          <div className="text-white/80">B = {found.b}</div>
          <div className="text-amber-300 mt-1">SHA-256(A)[:{bits}b] = SHA-256(B)[:{bits}b] = 0x{found.hash}</div>
          <p className="mt-2 text-[10px] text-white/55 leading-relaxed">
            Deux messages différents, même empreinte tronquée. SHA-256 entier reste sûr —
            mais ne tronque JAMAIS un hash pour de la signature.
          </p>
        </div>
      )}
    </div>
  )
}

function RainbowTablePanel() {
  const [hashInput, setHashInput] = useState('5f4dcc3b5aa765d61d8327deb882cf99') // md5("password")
  const [result, setResult] = useState<{ found: boolean; plaintext?: string; algo?: string; ms: number } | null>(null)
  const [busy, setBusy] = useState(false)
  // Salt demo
  const [demoPassword, setDemoPassword] = useState('password')
  const [salt, setSalt] = useState(generateSalt())
  const [saltedHash, setSaltedHash] = useState<string>('')

  const lookup = async () => {
    setBusy(true)
    try { setResult(await lookupHash(hashInput)) }
    finally { setBusy(false) }
  }

  const recomputeSalted = async () => {
    setSaltedHash(await hashWithSalt(demoPassword, salt))
  }

  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
      <h3 className="text-[12px] font-semibold text-white/80 uppercase tracking-wider mb-3 flex items-center gap-2">
        <Search size={13} /> Rainbow table demo · pourquoi saler
      </h3>
      <p className="text-[11px] text-white/55 mb-3">
        Une rainbow table précalcule les hashes de millions de mots de passe communs.
        Aurora fournit ici une mini-table (50 passwords × 3 algos = 150 entrées) pour le démontrer.
      </p>
      <div className="flex gap-2 mb-3">
        <input
          id="rainbow-hash" name="rainbowHash"
          value={hashInput} onChange={(e) => setHashInput(e.target.value)}
          placeholder="colle un hash hex (md5/sha1/sha256)"
          className="flex-1 rounded-lg bg-black/40 border border-white/10 px-3 py-1.5 text-[11px] text-white/90 font-mono" />
        <button onClick={lookup} disabled={busy}
          className="rounded-lg bg-sky-500/20 border border-sky-500/40 text-sky-200 px-3 py-1.5 text-[12px] hover:bg-sky-500/30 disabled:opacity-50">
          {busy ? <Loader2 size={12} className="inline animate-spin" /> : 'Lookup'}
        </button>
      </div>
      {result && (
        <div className={`rounded-lg border p-2 mb-3 text-[11px] ${result.found ? 'bg-rose-500/15 border-rose-500/40' : 'bg-emerald-500/15 border-emerald-500/40'}`}>
          {result.found ? (
            <div>
              <strong className="text-rose-200">✗ Hash dans la rainbow table : </strong>
              <span className="font-mono text-rose-100">{result.plaintext}</span>
              <span className="text-white/55 ml-2">via {result.algo} · {result.ms.toFixed(1)}ms</span>
            </div>
          ) : (
            <div className="text-emerald-200">✓ Pas dans la table — passphrase plus rare qu'attendu ou salée.</div>
          )}
        </div>
      )}
      <div className="rounded-lg bg-emerald-500/[0.04] border border-emerald-500/20 p-3 text-[11px]">
        <strong className="text-emerald-200">Défense : SALT</strong>
        <p className="text-white/70 mt-1 mb-2">
          Si tu hash <code>salt + password</code> avec un salt random unique par compte,
          deux users avec le même password produisent des hashes différents. Et la rainbow
          table devient inutile : il faudrait précalculer toutes les combinaisons (salt × password).
        </p>
        <div className="grid grid-cols-2 gap-2 mb-2">
          <input
            id="salt-pw" name="saltPassword"
            value={demoPassword} onChange={(e) => setDemoPassword(e.target.value)}
            placeholder="password" autoComplete="off"
            className="rounded bg-black/40 border border-white/10 px-2 py-1 text-[11px] font-mono text-white/85" />
          <div className="flex gap-1">
            <input
              id="salt-val" name="salt"
              value={salt} onChange={(e) => setSalt(e.target.value)}
              placeholder="salt" autoComplete="off"
              className="flex-1 rounded bg-black/40 border border-white/10 px-2 py-1 text-[10px] font-mono text-white/85" />
            <button onClick={() => setSalt(generateSalt())} title="Régénérer salt"
              className="rounded bg-white/5 border border-white/10 px-2 text-white/70 hover:bg-white/10">↻</button>
          </div>
        </div>
        <button onClick={recomputeSalted}
          className="rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 px-2 py-1 text-[10px] hover:bg-emerald-500/30">
          SHA-256(salt + password)
        </button>
        {saltedHash && (
          <div className="mt-2 rounded bg-black/40 border border-white/10 p-1.5 text-[10px] font-mono text-emerald-100 break-all">
            {saltedHash}
          </div>
        )}
      </div>
    </div>
  )
}

function HashCalculator() {
  const [text, setText] = useState('Aurora')
  const [md5v, setMd5v] = useState('')
  const [s1, setS1] = useState('')
  const [s256, setS256] = useState('')
  const [s384, setS384] = useState('')
  const [s512, setS512] = useState('')

  const compute = async () => {
    setMd5v(md5(text))
    setS1(await sha1(text))
    setS256(await sha256(text))
    setS384(await sha384(text))
    setS512(await sha512(text))
  }

  useMemo(() => { void compute() }, [text])

  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
      <div className="flex items-center gap-2 mb-3">
        <Fingerprint size={14} className="text-red-300" />
        <h3 className="text-[12px] font-semibold text-white/80 uppercase tracking-wider">Calculateur d'empreinte</h3>
      </div>
      <textarea value={text} onChange={(e) => setText(e.target.value)} rows={3}
        className="w-full rounded-lg bg-black/40 border border-white/10 px-3 py-2 text-[13px] text-white/90 resize-none mb-3" />
      <div className="space-y-1">
        <Row label="MD5 (obsolète, collisions connues)" value={md5v} danger />
        <Row label="SHA-1 (déprécié)" value={s1} danger />
        <Row label="SHA-256" value={s256} />
        <Row label="SHA-384" value={s384} />
        <Row label="SHA-512" value={s512} />
      </div>
    </div>
  )
}

function HMACPanel() {
  const [key, setKey] = useState('clé-secrète')
  const [msg, setMsg] = useState('Message authentifié')
  const [out, setOut] = useState('')

  useMemo(() => { hmacSha256(key, msg).then(setOut) }, [key, msg])

  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
      <h3 className="text-[12px] font-semibold text-white/80 uppercase tracking-wider mb-3">HMAC-SHA256</h3>
      <div className="grid grid-cols-2 gap-2 mb-3">
        <input value={key} onChange={(e) => setKey(e.target.value)} placeholder="clé"
          className="rounded-lg bg-black/40 border border-white/10 px-3 py-1.5 text-[12px] text-white/90 font-mono" />
        <input value={msg} onChange={(e) => setMsg(e.target.value)} placeholder="message"
          className="rounded-lg bg-black/40 border border-white/10 px-3 py-1.5 text-[12px] text-white/90 font-mono" />
      </div>
      <Row label="HMAC" value={out} />
    </div>
  )
}

function IdentifierPanel() {
  const [hash, setHash] = useState('5d41402abc4b2a76b9719d911017c592')
  const ids = useMemo(() => identifyHash(hash), [hash])
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
      <div className="flex items-center gap-2 mb-3">
        <Search size={14} className="text-red-300" />
        <h3 className="text-[12px] font-semibold text-white/80 uppercase tracking-wider">Identifier un hash</h3>
      </div>
      <input value={hash} onChange={(e) => setHash(e.target.value)}
        className="w-full rounded-lg bg-black/40 border border-white/10 px-3 py-1.5 text-[12px] text-white/90 font-mono mb-3" />
      <div className="flex flex-wrap gap-2">
        {ids.map((id, i) => (
          <span key={i} className="rounded-md bg-red-500/15 border border-red-500/30 px-2 py-1 text-[11px] text-red-200">{id}</span>
        ))}
      </div>
    </div>
  )
}

function CrackerPanel() {
  const [target, setTarget] = useState('')
  const [hint, setHint] = useState('password')
  const [busy, setBusy] = useState(false)
  const [progress, setProgress] = useState(0)
  const [progressMax, setProgressMax] = useState(0)
  const [result, setResult] = useState<{ found: boolean; plaintext: string | null; tried: number } | null>(null)

  const prepare = async () => {
    setTarget(await sha256(hint))
  }

  const run = async () => {
    if (!target) return
    setBusy(true); setResult(null); setProgress(0); setProgressMax(0)
    try {
      const res = await crackSha256Dict(target, (tried, total) => {
        setProgress(tried); setProgressMax(total)
      })
      setResult(res)
    } finally { setBusy(false) }
  }

  const pct = progressMax ? Math.min(100, (progress / progressMax) * 100) : 0

  return (
    <div className="rounded-xl border border-amber-500/30 bg-amber-500/[0.03] p-4">
      <div className="flex items-center gap-2 mb-1">
        <Hammer size={14} className="text-amber-300" />
        <h3 className="text-[12px] font-semibold text-amber-200 uppercase tracking-wider">Cracker via dictionnaire local</h3>
      </div>
      <p className="text-[11px] text-white/60 mb-3">
        Pour but éducatif uniquement. Montre pourquoi les hashs non salés tombent en millisecondes.
      </p>
      <div className="flex items-center gap-2 mb-2">
        <input value={hint} onChange={(e) => setHint(e.target.value)} placeholder="mot à tester"
          className="flex-1 rounded-lg bg-black/40 border border-white/10 px-3 py-1.5 text-[12px] text-white/90 font-mono" />
        <button onClick={prepare} className="rounded-lg bg-white/5 border border-white/10 px-2 py-1.5 text-[11px] hover:bg-white/10">
          → hash sha256
        </button>
      </div>
      <input value={target} onChange={(e) => setTarget(e.target.value)} placeholder="hash SHA-256 cible"
        className="w-full rounded-lg bg-black/40 border border-white/10 px-3 py-1.5 text-[12px] text-white/90 font-mono mb-3" />
      <button disabled={busy || !target} onClick={run}
        className="inline-flex items-center gap-2 rounded-lg bg-amber-500/20 border border-amber-500/40 text-amber-200 px-3 py-1.5 text-[12px] hover:bg-amber-500/30 disabled:opacity-50">
        {busy ? <Loader2 size={13} className="animate-spin" /> : <Hammer size={13} />} Lancer l'attaque dictionnaire
      </button>
      {busy && (
        <div className="mt-3">
          <div className="h-1.5 rounded bg-black/40 overflow-hidden">
            <div className="h-full bg-amber-400 transition-all" style={{ width: `${pct}%` }} />
          </div>
          <p className="text-[10px] text-white/50 font-mono mt-1">{progress} / {progressMax}</p>
        </div>
      )}
      {result && (
        <div className={`mt-3 rounded-lg p-3 text-[12px] ${
          result.found
            ? 'bg-emerald-500/15 border border-emerald-500/40 text-emerald-200'
            : 'bg-rose-500/15 border border-rose-500/40 text-rose-200'
        }`}>
          {result.found
            ? <>🎯 Trouvé : <span className="font-mono">{result.plaintext}</span> · {result.tried} essais</>
            : <>Non trouvé dans le dictionnaire ({result.tried} essais). Essaye un mot de passe commun.</>}
        </div>
      )}
      <div className="mt-3 rounded-lg bg-black/30 border border-white/5 p-3 text-[11px] text-white/65">
        <strong className="text-white/80 flex items-center gap-1"><ShieldAlert size={12} /> Pourquoi saler ?</strong>
        <p className="mt-1">Sans sel, deux utilisateurs avec le même mot de passe ont le même hash → une table arc-en-ciel déchire la base entière. Un sel aléatoire par utilisateur rend chaque hash unique, invalide les tables pré-calculées, et force un attaquant à recommencer pour chaque compte.</p>
      </div>
    </div>
  )
}

function Row({ label, value, danger }: { label: string; value: string; danger?: boolean }) {
  return (
    <div className={`rounded-lg border px-3 py-2 ${danger ? 'border-rose-500/20 bg-rose-500/[0.03]' : 'border-white/5 bg-black/20'}`}>
      <div className="text-[10px] uppercase tracking-wider text-white/50">{label}</div>
      <div className="text-[11px] font-mono text-white/80 break-all mt-1">{value || '—'}</div>
    </div>
  )
}
