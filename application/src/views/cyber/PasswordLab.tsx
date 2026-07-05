import { useMemo, useState } from 'react'
import { AlertTriangle, Copy, Dices, KeyRound, RefreshCw, Shield, UserRound } from 'lucide-react'
import { analyzePassword, generateDiceware, generatePassword, type GenerateOptions } from '../../services/cyber/passwordAnalyzer'
import { assessKdf, attackCost, formatUsd, OWASP_2024_DEFAULTS } from '../../services/cyber/kdfCostAnalyzer'
import { auditHash } from '../../services/cyber/hashParameterParser'
import { checkBreached, checkCredentialReuse } from '../../services/cyber/breachChecker'

export default function PasswordLab() {
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
        <h2 className="text-white text-[15px] font-semibold mb-1">Mots de passe — entropie et cassage</h2>
        <p className="text-[12px] text-white/60">
          L'entropie mesure l'incertitude. Un bon mot de passe vise <strong>≥ 80 bits</strong> et utilise un <strong>gestionnaire</strong>.
          Ici on génère, on mesure, on compare.
        </p>
      </div>
      <AnalyzerCard />
      <BreachLookupCard />
      <HashAuditCard />
      <GeneratorCard />
      <DicewareCard />
      <TutorialCard />
    </div>
  )
}

// v83v — Standalone breach lookup. Indépendant de l'analyzer card pour que
// l'utilisateur puisse rapidement vérifier "ce password est-il dans HIBP-style ?"
function BreachLookupCard() {
  const [pw, setPw] = useState('')
  const [identifier, setIdentifier] = useState('')
  const breach = useMemo(() => checkBreached(pw), [pw])
  const reuse = useMemo(() => checkCredentialReuse(pw, identifier), [pw, identifier])
  const hasInput = pw.length > 0
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
      <h3 className="text-[12px] font-semibold text-white/80 uppercase tracking-wider mb-3 flex items-center gap-2">
        <AlertTriangle size={13} className="text-rose-300" /> Lookup breach
      </h3>
      <input
        id="breach-pw"
        name="breachPassword"
        autoComplete="off"
        type="text"
        value={pw}
        onChange={(e) => setPw(e.target.value)}
        placeholder="Mot de passe à tester (offline · stays local)"
        className="w-full rounded-lg bg-black/40 border border-white/10 px-3 py-2 text-[13px] text-white/90 font-mono mb-2"
      />
      <input
        id="breach-id"
        name="breachIdentifier"
        autoComplete="off"
        type="text"
        value={identifier}
        onChange={(e) => setIdentifier(e.target.value)}
        placeholder="(optionnel) username/email pour check reuse"
        className="w-full rounded-lg bg-black/30 border border-white/10 px-3 py-1.5 text-[11px] text-white/80 font-mono mb-3"
      />
      {!hasInput && (
        <p className="text-[11px] text-white/55 italic">
          Tape un mot de passe — Aurora vérifie offline contre une wordlist de breaches mondiales (RockYou, LinkedIn, Yahoo, Adobe…) + variantes leet/suffix/prefix/capitalisation.
        </p>
      )}
      {hasInput && breach.isBreached && (
        <div className="rounded-lg bg-rose-500/15 border border-rose-500/40 p-2 text-[11px]">
          <strong className="text-rose-200 flex items-center gap-1.5">
            <AlertTriangle size={12} /> Présent dans les breaches
          </strong>
          <p className="text-rose-100/85 mt-1">
            Variante <span className="font-mono">{breach.transformation}</span>
            {breach.matchedAs && breach.matchedAs !== pw.toLowerCase() && (
              <> · base : <span className="font-mono">{breach.matchedAs}</span></>
            )}
          </p>
          <ul className="mt-1 text-rose-100/75 list-disc list-inside space-y-0.5">
            {breach.recommendations.map((r, i) => <li key={i}>{r}</li>)}
          </ul>
        </div>
      )}
      {hasInput && !breach.isBreached && (
        <div className="rounded-lg bg-emerald-500/15 border border-emerald-500/40 p-2 text-[11px] text-emerald-100">
          ✓ Pas trouvé dans la wordlist offline. <span className="opacity-75">(Pour un vrai check HIBP API, l'app peut envoyer un préfixe SHA-1 k-anonymity.)</span>
        </div>
      )}
      {reuse.reused && (
        <div className="mt-2 rounded-lg bg-amber-500/15 border border-amber-500/40 p-2 text-[11px] text-amber-100">
          <strong className="text-amber-200">Reuse :</strong> {reuse.warning}
        </div>
      )}
    </div>
  )
}

/**
 * Carte "audit hash" : colle une chaîne $argon2id$.../$2b$12$... ou un hash
 * SHA-256 nu pour voir le verdict OWASP 2024 + recommandations.
 */
function HashAuditCard() {
  const [hash, setHash] = useState('$argon2id$v=19$m=65536,t=3,p=1$c2FsdHk$ZGlnZXN0')
  const audit = useMemo(() => auditHash(hash.trim()), [hash])
  const verdictColor: Record<typeof audit.verdict, string> = {
    recommended: 'bg-emerald-500/20 text-emerald-200 border-emerald-500/30',
    acceptable: 'bg-sky-500/20 text-sky-200 border-sky-500/30',
    undersized: 'bg-amber-500/20 text-amber-200 border-amber-500/30',
    banned: 'bg-rose-500/20 text-rose-200 border-rose-500/30',
  }
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
      <h3 className="text-[12px] font-semibold text-white/80 uppercase tracking-wider mb-3 flex items-center gap-2">
        <Shield size={13} /> Audit hash stocké côté serveur
      </h3>
      <input
        value={hash}
        onChange={(e) => setHash(e.target.value)}
        placeholder="$argon2id$... ou $2b$12$... ou hash hex nu"
        className="w-full rounded-lg bg-black/40 border border-white/10 px-3 py-2 text-[12px] text-white/90 font-mono mb-3"
      />
      <div className="flex items-center gap-2 mb-3 text-[12px]">
        <span className="text-white/70">Algorithme :</span>
        <span className="font-mono text-white/90">{audit.algorithm}</span>
        <span className={`ml-auto rounded px-2 py-0.5 text-[10px] uppercase border ${verdictColor[audit.verdict]}`}>
          {audit.verdict}
        </span>
      </div>
      {audit.parsed && 'memoryKib' in audit.parsed && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-2 text-[11px] mb-3">
          <Stat label="Mémoire (KiB)" value={String(audit.parsed.memoryKib)} />
          <Stat label="Time cost" value={String(audit.parsed.timeCost)} />
          <Stat label="Parallelism" value={String(audit.parsed.parallelism)} />
          <Stat label="Variante" value={audit.parsed.variant} />
        </div>
      )}
      {audit.parsed && 'cost' in audit.parsed && (
        <div className="grid grid-cols-2 gap-2 text-[11px] mb-3">
          <Stat label="Cost factor" value={String(audit.parsed.cost)} />
          <Stat label="Variante" value={audit.parsed.variant} />
        </div>
      )}
      <div className="rounded-lg bg-white/5 border border-white/10 p-2 text-[11px]">
        <strong className="text-white/80">Recommandations :</strong>
        <ul className="mt-1 text-white/70 list-disc list-inside space-y-0.5">
          {audit.recommendations.map((r, i) => <li key={i}>{r}</li>)}
        </ul>
      </div>
    </div>
  )
}

function AnalyzerCard() {
  const [pw, setPw] = useState('P@ssw0rd2024')
  const [identifier, setIdentifier] = useState('')
  const analysis = useMemo(() => analyzePassword(pw), [pw])
  const breach = useMemo(() => checkBreached(pw), [pw])
  const reuse = useMemo(() => checkCredentialReuse(pw, identifier), [pw, identifier])
  const scoreColor = ['bg-rose-500', 'bg-orange-500', 'bg-amber-500', 'bg-lime-500', 'bg-emerald-500'][analysis.score]
  const scoreLabel = ['très faible', 'faible', 'moyen', 'fort', 'très fort'][analysis.score]

  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
      <h3 className="text-[12px] font-semibold text-white/80 uppercase tracking-wider mb-3 flex items-center gap-2">
        <Shield size={13} /> Analyseur d'entropie
      </h3>
      <input
        id="pw-input"
        name="password"
        autoComplete="new-password"
        value={pw}
        onChange={(e) => setPw(e.target.value)}
        placeholder="entre un mot de passe"
        className="w-full rounded-lg bg-black/40 border border-white/10 px-3 py-2 text-[13px] text-white/90 font-mono mb-2"
      />
      <div className="flex items-center gap-2 mb-3">
        <UserRound size={11} className="text-white/40" />
        <input
          id="pw-identifier"
          name="username"
          autoComplete="username"
          value={identifier}
          onChange={(e) => setIdentifier(e.target.value)}
          placeholder="(optionnel) username/email pour détecter credential reuse"
          className="flex-1 rounded-lg bg-black/30 border border-white/10 px-3 py-1.5 text-[11px] text-white/80 font-mono"
        />
      </div>
      <div className="flex items-center gap-3 mb-3">
        <div className="flex-1 h-3 rounded-full bg-black/40 overflow-hidden flex relative">
          {[0, 1, 2, 3, 4].map((i) => (
            <div key={i} className={`flex-1 transition-colors ${i <= analysis.score ? scoreColor : 'bg-white/5'}`} />
          ))}
          {/* Curseur entropie : indique précisément la position vs un objectif 80 bits */}
          <div
            className="absolute top-1/2 -translate-y-1/2 h-5 w-1 bg-white/85 rounded shadow-lg pointer-events-none"
            style={{ left: `${Math.min(100, (analysis.entropy / 128) * 100)}%`, transition: 'left 240ms ease' }}
            title={`${analysis.entropy} bits d'entropie`}
          />
          {/* Marker objectif 80 bits */}
          <div className="absolute top-0 h-full w-px bg-emerald-400/50" style={{ left: `${(80 / 128) * 100}%` }} title="objectif 80 bits" />
        </div>
        <span className="text-[12px] text-white/80 font-medium w-28 text-right font-mono">
          {scoreLabel} · {analysis.entropy}b
        </span>
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2 text-[11px]">
        <Stat label="Longueur" value={analysis.length.toString()} />
        <Stat label="Alphabet" value={analysis.charsetSize.toString()} />
        <Stat label="Entropie" value={`${analysis.entropy} bits`} />
        <Stat label="Cassage (GPU)" value={analysis.crackTimeHuman} />
      </div>
      {analysis.patterns.length > 0 && (
        <div className="mt-3 rounded-lg bg-rose-500/10 border border-rose-500/30 p-2 text-[11px]">
          <strong className="text-rose-200">Motifs détectés (−entropie):</strong>
          <span className="text-rose-100/80"> {analysis.patterns.join(', ')}</span>
        </div>
      )}
      {analysis.feedback.length > 0 && (
        <div className="mt-2 rounded-lg bg-white/5 border border-white/10 p-2 text-[11px]">
          <strong className="text-white/80">Pistes d'amélioration :</strong>
          <ul className="mt-1 text-white/65 list-disc list-inside">
            {analysis.feedback.map((f, i) => <li key={i}>{f}</li>)}
          </ul>
        </div>
      )}
      {breach.isBreached && (
        <div className="mt-3 rounded-lg bg-rose-500/15 border border-rose-500/40 p-2 text-[11px]">
          <strong className="text-rose-200 flex items-center gap-1.5">
            <AlertTriangle size={12} /> Détecté dans les breaches connues
          </strong>
          <p className="text-rose-100/85 mt-1">
            Transformation : <span className="font-mono">{breach.transformation}</span>
            {breach.matchedAs && breach.matchedAs !== pw.toLowerCase() && (
              <> · base : <span className="font-mono">{breach.matchedAs}</span></>
            )}
          </p>
          <ul className="mt-1 text-rose-100/75 list-disc list-inside space-y-0.5">
            {breach.recommendations.map((r, i) => <li key={i}>{r}</li>)}
          </ul>
        </div>
      )}
      {reuse.reused && (
        <div className="mt-2 rounded-lg bg-amber-500/15 border border-amber-500/40 p-2 text-[11px] text-amber-100">
          <strong className="text-amber-200">Credential reuse :</strong> {reuse.warning}
        </div>
      )}
      <KdfCostComparison charsetSize={analysis.charsetSize} length={analysis.length} />
    </div>
  )
}

/**
 * Pédagogie : montre l'effet du choix d'algorithme côté serveur sur le coût
 * d'un brute-force ciblant CE mot de passe. Argon2id ralentit l'attaquant
 * ~1e6× vs SHA-256 nu. Affiché en USD pour rendre l'idée concrète.
 */
function KdfCostComparison({ charsetSize, length }: { charsetSize: number; length: number }) {
  const rows = useMemo(() => {
    const algos = [
      { id: 'sha256', label: 'SHA-256 nu' },
      { id: 'pbkdf2-600k', label: 'PBKDF2-SHA256 600k' },
      { id: 'bcrypt-12', label: 'bcrypt cost=12' },
      { id: 'argon2id', label: 'Argon2id (OWASP)' },
    ] as const
    const assessments = [
      assessKdf({ algorithm: 'sha256' }),
      assessKdf(OWASP_2024_DEFAULTS.pbkdf2),
      assessKdf(OWASP_2024_DEFAULTS.bcrypt),
      assessKdf(OWASP_2024_DEFAULTS.argon2id),
    ]
    return algos.map((a, i) => {
      const ass = assessments[i]
      const cost = charsetSize > 1 && length > 0
        ? attackCost(ass.hashesPerSecondAttacker, charsetSize, length)
        : 0
      return { id: a.id, label: a.label, cost, recommendation: ass.recommendation }
    })
  }, [charsetSize, length])
  if (charsetSize <= 1 || length === 0) return null
  const recoBadge: Record<string, string> = {
    banned: 'bg-rose-500/20 text-rose-200',
    legacy: 'bg-amber-500/20 text-amber-200',
    acceptable: 'bg-sky-500/20 text-sky-200',
    recommended: 'bg-emerald-500/20 text-emerald-200',
  }
  return (
    <div className="mt-3 rounded-lg bg-black/30 border border-white/10 p-2 text-[11px]">
      <strong className="text-white/80">Coût d'attaque selon l'algorithme côté serveur (cloud GPU AWS) :</strong>
      <div className="mt-2 grid grid-cols-1 gap-1.5">
        {rows.map((r) => (
          <div key={r.id} className="flex items-center justify-between rounded-md bg-white/[0.03] px-2 py-1">
            <span className="flex items-center gap-2">
              <span className="text-white/75">{r.label}</span>
              <span className={`rounded px-1.5 py-0.5 text-[9px] uppercase ${recoBadge[r.recommendation] ?? 'bg-white/10 text-white/60'}`}>
                {r.recommendation}
              </span>
            </span>
            <span className="font-mono text-white/85">{formatUsd(r.cost)}</span>
          </div>
        ))}
      </div>
      <p className="mt-2 text-[10px] text-white/50">
        Même mot de passe : un attaquant payant ce que coûte de le casser en SHA-256 nu vs Argon2id verra son budget multiplié par ~10⁶.
      </p>
    </div>
  )
}

function GeneratorCard() {
  const [opts, setOpts] = useState<GenerateOptions>({
    length: 20, lower: true, upper: true, digits: true, symbols: true, excludeAmbiguous: false,
  })
  const [password, setPassword] = useState(() => generatePassword(opts))
  const regenerate = () => setPassword(generatePassword(opts))

  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
      <h3 className="text-[12px] font-semibold text-white/80 uppercase tracking-wider mb-3 flex items-center gap-2">
        <KeyRound size={13} /> Générateur cryptographique
      </h3>
      <div className="flex items-center gap-2 mb-3">
        <input readOnly value={password}
          className="flex-1 rounded-lg bg-black/40 border border-white/10 px-3 py-2 text-[13px] text-white/90 font-mono" />
        <button onClick={regenerate} className="rounded-lg bg-red-500/20 border border-red-500/40 text-red-200 px-2 py-2 hover:bg-red-500/30">
          <RefreshCw size={14} />
        </button>
        <button onClick={() => navigator.clipboard.writeText(password).catch(() => undefined)}
          className="rounded-lg bg-white/5 border border-white/10 text-white/80 px-2 py-2 hover:bg-white/10">
          <Copy size={14} />
        </button>
      </div>
      <div className="flex items-center gap-3 mb-3">
        <label className="text-[11px] text-white/60">Longueur</label>
        <input type="range" min="8" max="64" value={opts.length}
          onChange={(e) => setOpts({ ...opts, length: Number(e.target.value) })} className="flex-1" />
        <span className="w-6 text-[12px] text-white/70 font-mono">{opts.length}</span>
      </div>
      <div className="grid grid-cols-2 gap-2 text-[11px]">
        {(['lower', 'upper', 'digits', 'symbols', 'excludeAmbiguous'] as const).map((k) => (
          <label key={k} className="flex items-center gap-2 rounded-md border border-white/10 bg-black/20 px-2 py-1.5 cursor-pointer">
            <input type="checkbox" checked={opts[k]} onChange={(e) => setOpts({ ...opts, [k]: e.target.checked })} />
            <span className="text-white/75">{k === 'excludeAmbiguous' ? 'Exclure ambigus (il1Lo0O)' : k}</span>
          </label>
        ))}
      </div>
    </div>
  )
}

function DicewareCard() {
  const [phrase, setPhrase] = useState(() => generateDiceware(5, '-'))
  const [count, setCount] = useState(5)
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
      <h3 className="text-[12px] font-semibold text-white/80 uppercase tracking-wider mb-3 flex items-center gap-2">
        <Dices size={13} /> Diceware — passphrase mémorisable
      </h3>
      <div className="flex items-center gap-2 mb-3">
        <label className="text-[11px] text-white/60">Mots</label>
        <input type="range" min="3" max="10" value={count} onChange={(e) => setCount(Number(e.target.value))} className="flex-1" />
        <span className="w-6 text-[12px] text-white/70 font-mono">{count}</span>
        <button onClick={() => setPhrase(generateDiceware(count, '-'))}
          className="rounded-lg bg-red-500/20 border border-red-500/40 text-red-200 px-3 py-1.5 text-[11px] hover:bg-red-500/30">
          générer
        </button>
      </div>
      <div className="rounded-lg bg-black/40 border border-white/10 px-3 py-2 text-[13px] text-white/90 font-mono">{phrase}</div>
      <p className="text-[10px] text-white/50 mt-2">
        Passphrase de mots courts choisis au hasard. Plus facile à retenir qu'une chaîne complexe, mais longueur = sécurité.
      </p>
    </div>
  )
}

function TutorialCard() {
  const rules = [
    { n: 1, rule: 'Long avant d\'être complexe', why: 'Chaque caractère ajouté double (approx.) l\'entropie.' },
    { n: 2, rule: 'Unique par site', why: 'Un breach ne compromet pas tout le reste (credential stuffing).' },
    { n: 3, rule: 'Gestionnaire (Bitwarden, KeePass…)', why: 'Tu n\'as qu\'un seul mot de passe maître à retenir.' },
    { n: 4, rule: '2FA matériel (clé FIDO2) sur comptes critiques', why: 'Immunise contre phishing et reuse.' },
    { n: 5, rule: 'Ne partage jamais par canal non chiffré', why: 'Email/SMS/Teams laisse des traces récupérables.' },
  ]
  return (
    <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/[0.03] p-4">
      <h3 className="text-[12px] font-semibold text-emerald-200 uppercase tracking-wider mb-3">Les 5 règles d'or</h3>
      <ol className="space-y-2">
        {rules.map((r) => (
          <li key={r.n} className="flex gap-3">
            <span className="shrink-0 flex h-6 w-6 items-center justify-center rounded-full bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 text-[11px] font-bold">{r.n}</span>
            <div>
              <p className="text-[13px] text-white/90 font-medium">{r.rule}</p>
              <p className="text-[11px] text-white/55 mt-0.5">{r.why}</p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-black/30 border border-white/5 px-3 py-2">
      <div className="text-[9px] uppercase tracking-wider text-white/45">{label}</div>
      <div className="text-[13px] text-white/90 font-mono mt-0.5">{value}</div>
    </div>
  )
}
