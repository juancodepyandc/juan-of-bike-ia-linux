import { useMemo, useState } from 'react'
import { Copy, Key, Lock, ScanSearch, ShieldAlert, Shuffle, Unlock } from 'lucide-react'
import {
  aesGcmDecrypt,
  aesGcmEncrypt,
  atbash,
  caesarShift,
  dhDemo,
  exportKeyPem,
  frequencyAnalysis,
  fromBase64,
  fromBinary,
  fromHex,
  fromMorse,
  railFence,
  rot13,
  rsaDecrypt,
  rsaEncrypt,
  rsaGenerateKey,
  suggestCaesarShift,
  toBase64,
  toBinary,
  toHex,
  toMorse,
  vigenere,
} from '../../services/cyber/cryptoService'
import {
  applyAtbash,
  applyRot47,
  crackCaesar,
  crackSingleByteXor,
  decodeBase32,
  decodeBase64,
  decodeBinary,
  decodeHex,
  detectCipher,
  guessVigenerePeriod,
  indexOfCoincidence,
} from '../../services/cyber/classicalCipherAnalysis'
import { inspectJwt, summariseJwt } from '../../services/cyber/jwtInspector'
import { crackHs256, forgeAlgNone, forgeHs256, JWT_WEAK_SECRETS } from '../../services/cyber/jwtForger'
import { inspectCertificate } from '../../services/cyber/tlsCertInspector'
import VoicePushToTalk from '../../components/VoicePushToTalk'

type Tab = 'classic' | 'aes' | 'rsa' | 'dh' | 'encoding' | 'freq' | 'auto' | 'jwt' | 'tls'

const TABS: Array<{ id: Tab; label: string }> = [
  { id: 'classic', label: 'Chiffres classiques' },
  { id: 'aes', label: 'AES-GCM' },
  { id: 'rsa', label: 'RSA' },
  { id: 'dh', label: 'Diffie-Hellman' },
  { id: 'encoding', label: 'Encoding' },
  { id: 'freq', label: 'Analyse fréquentielle' },
  { id: 'auto', label: 'Auto-détection' },
  { id: 'jwt', label: 'JWT Inspector' },
  { id: 'tls', label: 'TLS Cert Inspector' },
]

export default function CryptoLab() {
  const [tab, setTab] = useState<Tab>('classic')

  return (
    <div className="space-y-4">
      <Header />
      <div className="flex gap-1 overflow-x-auto no-scrollbar border-b border-white/10 pb-2">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`whitespace-nowrap rounded-lg px-3 py-1.5 text-[12px] transition-colors ${
              tab === t.id
                ? 'bg-red-500/20 text-red-200 border border-red-500/40'
                : 'text-white/55 hover:text-white/80 hover:bg-white/5'
            }`}
          >{t.label}</button>
        ))}
      </div>
      {tab === 'classic' && <ClassicCiphers />}
      {tab === 'aes' && <AESPanel />}
      {tab === 'rsa' && <RSAPanel />}
      {tab === 'dh' && <DHPanel />}
      {tab === 'encoding' && <EncodingPanel />}
      {tab === 'freq' && <FrequencyPanel />}
      {tab === 'auto' && <AutoDetectionPanel />}
      {tab === 'jwt' && <JwtInspectorPanel />}
      {tab === 'tls' && <TlsCertPanel />}
    </div>
  )
}

function TlsCertPanel() {
  const samplePem =
    '-----BEGIN CERTIFICATE-----\n' +
    'MIIDazCCAlOgAwIBAgIUNbe2pIxJDR7+Y8t6UvJ3xV5Jw4kwDQYJKoZIhvcNAQEL\n' +
    'BQAwRTELMAkGA1UEBhMCQVUxEzARBgNVBAgMClNvbWUtU3RhdGUxITAfBgNVBAoM\n' +
    'GEludGVybmV0IFdpZGdpdHMgUHR5IEx0ZDAeFw0yNTAxMDEwMDAwMDBaFw0yNjAx\n' +
    'MDEwMDAwMDBaMEUxCzAJBgNVBAYTAkFVMRMwEQYDVQQIDApTb21lLVN0YXRlMSEw\n' +
    'HwYDVQQKDBhJbnRlcm5ldCBXaWRnaXRzIFB0eSBMdGQwggEiMA0GCSqGSIb3DQEB\n' +
    '-----END CERTIFICATE-----'
  const [pem, setPem] = useState(samplePem)
  const report = useMemo(() => inspectCertificate(pem.trim()), [pem])
  const verdictColor: Record<typeof report.verdict, string> = {
    recommended: 'bg-emerald-500/20 text-emerald-200 border-emerald-500/40',
    acceptable: 'bg-sky-500/20 text-sky-200 border-sky-500/40',
    'expiring-soon': 'bg-amber-500/20 text-amber-200 border-amber-500/40',
    expired: 'bg-rose-500/30 text-rose-100 border-rose-500/60',
    'weak-algo': 'bg-rose-500/30 text-rose-100 border-rose-500/60',
    'self-signed': 'bg-amber-500/20 text-amber-200 border-amber-500/40',
    unknown: 'bg-white/5 text-white/60 border-white/10',
  }
  const sevColor: Record<'info' | 'warn' | 'error' | 'critical', string> = {
    info: 'bg-sky-500/15 text-sky-200 border-sky-500/30',
    warn: 'bg-amber-500/15 text-amber-200 border-amber-500/30',
    error: 'bg-rose-500/20 text-rose-200 border-rose-500/40',
    critical: 'bg-rose-500/30 text-rose-100 border-rose-500/60',
  }
  return (
    <div className="space-y-3">
      <Card title="TLS Certificate Inspector — parse PEM, audit expiration/algo/SAN">
        <p className="text-[11px] text-white/55 mb-3">
          Colle un cert au format PEM. Aurora parse les champs visibles (subject, issuer,
          dates, signature algorithm, SAN) et émet un verdict. <strong>Parsing local</strong>,
          rien ne sort de la machine.
        </p>
        <textarea
          value={pem}
          onChange={(e) => setPem(e.target.value)}
          rows={8}
          placeholder="-----BEGIN CERTIFICATE-----&#10;MIIC...&#10;-----END CERTIFICATE-----"
          className="w-full rounded-lg bg-black/40 border border-white/10 px-3 py-2 text-[10px] text-white/90 font-mono resize-none mb-3"
        />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 mb-3">
          <Stat label="Subject" value={report.subject || '(non détecté)'} />
          <Stat label="Issuer" value={report.issuer || '(non détecté)'} />
          <Stat label="Not before" value={report.notBefore || '—'} />
          <Stat label="Not after" value={report.notAfter || '—'} />
          <Stat label="Signature alg." value={report.signatureAlgorithm || '—'} />
          <Stat label="Heures restantes" value={
            report.hoursUntilExpire != null
              ? report.hoursUntilExpire < 0
                ? `expiré · ${(-report.hoursUntilExpire / 24).toFixed(0)}j`
                : `${(report.hoursUntilExpire / 24).toFixed(1)} jours`
              : '—'
          } />
        </div>
        <div className="flex items-center gap-2 mb-3 text-[12px]">
          <span className="text-white/70">Verdict :</span>
          <span className={`rounded px-2 py-0.5 text-[10px] uppercase border ${verdictColor[report.verdict]}`}>
            {report.verdict}
          </span>
          <span className="ml-auto text-white/45 text-[10px] font-mono">{report.pemBlocks} cert{report.pemBlocks > 1 ? 's' : ''} détecté{report.pemBlocks > 1 ? 's' : ''}</span>
        </div>
        {report.subjectAltNames.length > 0 && (
          <div className="mb-3">
            <div className="text-[10px] uppercase tracking-wider text-white/50 mb-1">Subject Alternative Names ({report.subjectAltNames.length})</div>
            <div className="flex flex-wrap gap-1">
              {report.subjectAltNames.map((s, i) => (
                <span key={i} className="rounded bg-cyan-500/15 border border-cyan-500/30 px-2 py-0.5 text-[10px] font-mono text-cyan-200">{s}</span>
              ))}
            </div>
          </div>
        )}
        {report.issues.length > 0 && (
          <div>
            <div className="text-[10px] uppercase tracking-wider text-white/50 mb-1">Audit ({report.issues.length})</div>
            <div className="space-y-1">
              {report.issues.map((iss, i) => (
                <div key={i} className={`rounded-md border px-2 py-1 text-[11px] ${sevColor[iss.severity]}`}>
                  <span className="font-mono text-[9px] uppercase mr-2">{iss.severity}</span>
                  {iss.message}
                </div>
              ))}
            </div>
          </div>
        )}
        {report.serial && (
          <div className="mt-3 text-[10px] text-white/45 font-mono">
            Serial : <span className="text-white/70">{report.serial}</span>
          </div>
        )}
      </Card>
    </div>
  )
}

function AutoDetectionPanel() {
  const [input, setInput] = useState('Wklv lv d Fdhvdu fkdoohqjh iru dxurudld.')
  const detection = useMemo(() => detectCipher(input, 'fr'), [input])
  const ic = useMemo(() => indexOfCoincidence(input), [input])

  // Decode auto pour les types détectables sans clé.
  const decoded = useMemo(() => {
    if (detection.type === 'caesar' || detection.type === 'rot13') {
      const r = crackCaesar(input, 'fr')
      return { label: `César décrypté (shift original = ${r.shift})`, value: r.plaintext, chi: r.chiSquare }
    }
    if (detection.type === 'base64') {
      const v = decodeBase64(input)
      return { label: 'Base64 décodé', value: v ?? '(décodage impossible)', chi: null }
    }
    if (detection.type === 'hex') {
      const v = decodeHex(input)
      return { label: 'Hex décodé', value: v ?? '(décodage impossible)', chi: null }
    }
    if (detection.type === 'base32') {
      const v = decodeBase32(input)
      return { label: 'Base32 décodé', value: v ?? '(décodage impossible)', chi: null }
    }
    if (detection.type === 'binary') {
      const v = decodeBinary(input)
      return { label: 'Binary décodé (UTF-8)', value: v ?? '(décodage impossible)', chi: null }
    }
    if (detection.type === 'atbash') {
      const v = applyAtbash(input)
      return { label: 'Atbash décodé (A↔Z involutif)', value: v, chi: null }
    }
    if (detection.type === 'rot47') {
      const v = applyRot47(input)
      return { label: 'ROT47 décodé (ASCII printable)', value: v, chi: null }
    }
    if (detection.type === 'vigenere') {
      const k = guessVigenerePeriod(input)
      return { label: `Vigenère — période détectée`, value: `k ≈ ${k}`, chi: null }
    }
    if (detection.type === 'xor') {
      // Single-byte XOR sur la version la plus probable (input = ASCII direct).
      const bytes = new Uint8Array(input.length)
      for (let i = 0; i < input.length; i += 1) bytes[i] = input.charCodeAt(i) & 0xff
      const r = crackSingleByteXor(bytes, 'fr')
      return { label: `XOR single-byte (key = 0x${r.key.toString(16).padStart(2, '0')})`, value: r.plaintext, chi: null }
    }
    return null
  }, [input, detection.type])

  const typeColor: Record<string, string> = {
    'plaintext-fr': 'bg-emerald-500/20 text-emerald-200 border-emerald-500/30',
    'plaintext-en': 'bg-emerald-500/20 text-emerald-200 border-emerald-500/30',
    'caesar': 'bg-amber-500/20 text-amber-200 border-amber-500/30',
    'rot13': 'bg-amber-500/20 text-amber-200 border-amber-500/30',
    'rot47': 'bg-amber-500/20 text-amber-200 border-amber-500/30',
    'atbash': 'bg-yellow-500/20 text-yellow-200 border-yellow-500/30',
    'vigenere': 'bg-orange-500/20 text-orange-200 border-orange-500/30',
    'xor': 'bg-rose-500/20 text-rose-200 border-rose-500/30',
    'base64': 'bg-sky-500/20 text-sky-200 border-sky-500/30',
    'base32': 'bg-cyan-500/20 text-cyan-200 border-cyan-500/30',
    'hex': 'bg-sky-500/20 text-sky-200 border-sky-500/30',
    'binary': 'bg-blue-500/20 text-blue-200 border-blue-500/30',
    'transposition': 'bg-purple-500/20 text-purple-200 border-purple-500/30',
    'unknown': 'bg-white/5 text-white/60 border-white/10',
  }

  return (
    <div className="space-y-3">
      <Card title="Auto-détection — colle un ciphertext, l'IA cherche le type">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[10px] uppercase tracking-wider text-white/45">
            {input.length === 0 ? 'Vide' : `${input.length} caractères collés`}
          </span>
          {input.length > 0 && (
            <span className={`rounded-md border px-2 py-0.5 text-[11px] font-mono ${typeColor[detection.type] ?? typeColor['unknown']}`}>
              → {detection.type} · {Math.round(detection.probability * 100)}%
            </span>
          )}
        </div>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          rows={5}
          className="w-full rounded-lg bg-black/40 border border-white/10 px-3 py-2 text-[13px] text-white/90 resize-none font-mono mb-3"
          placeholder="Texte chiffré ou encodé…"
        />
        <div className="-mt-2 mb-3 flex items-center gap-2">
          <VoicePushToTalk
            onTranscript={(t) => setInput((prev) => (prev?.trim() ? `${prev} ${t}` : t))}
            label="Dicter le texte à analyser"
            size={32}
          />
          <span className="text-[11px] text-white/45">Dicte le texte à détecter.</span>
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-2 text-[11px] mb-3">
          <Stat label="Longueur" value={String(input.length)} />
          <Stat label="IC (Kasiski)" value={ic.toFixed(4)} />
          <Stat label="Confiance" value={`${Math.round(detection.probability * 100)}%`} />
          <div className="rounded-lg bg-black/30 border border-white/5 px-3 py-2">
            <div className="text-[9px] uppercase tracking-wider text-white/45">Type détecté</div>
            <div className={`mt-1 inline-block rounded px-1.5 py-0.5 text-[11px] font-mono border ${typeColor[detection.type] ?? typeColor['unknown']}`}>
              {detection.type}
            </div>
          </div>
        </div>
        {detection.hint && (
          <div className="rounded-lg bg-white/5 border border-white/10 p-2 text-[11px] text-white/75 mb-3">
            <ScanSearch size={11} className="inline mr-1" /> {detection.hint}
          </div>
        )}
        {decoded && (
          <div className="rounded-lg bg-emerald-500/10 border border-emerald-500/30 p-3 text-[12px]">
            <div className="text-emerald-200 font-semibold mb-1">{decoded.label}</div>
            <div className="font-mono text-[11px] text-white/85 break-all">{decoded.value}</div>
            {decoded.chi != null && (
              <div className="text-[10px] text-white/55 mt-2">χ² (FR) = {decoded.chi.toFixed(2)} (plus bas = meilleur)</div>
            )}
          </div>
        )}
        <p className="text-[10px] text-white/45 mt-3">
          Heuristiques cumulatives : Index de Coïncidence, χ² FR/EN, log-vraisemblance pour XOR, longueur/charset pour base64/hex.
        </p>
      </Card>
    </div>
  )
}

function JwtInspectorPanel() {
  const sampleJwt =
    'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.' +
    'eyJzdWIiOiIxMjM0NSIsIm5hbWUiOiJBdXJvcmFJQSIsImlhdCI6MTcwMDAwMDAwMCwiZXhwIjoxNzAwMDAzNjAwfQ.' +
    'SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c'
  const [token, setToken] = useState(sampleJwt)
  const inspection = useMemo(() => inspectJwt(token.trim()), [token])
  const sevColor: Record<'info' | 'warn' | 'error' | 'block', string> = {
    info: 'bg-sky-500/15 text-sky-200 border-sky-500/30',
    warn: 'bg-amber-500/15 text-amber-200 border-amber-500/30',
    error: 'bg-rose-500/20 text-rose-200 border-rose-500/40',
    block: 'bg-rose-500/30 text-rose-100 border-rose-500/60',
  }

  return (
    <div className="space-y-3">
      <Card title="JWT Inspector — décode header/payload + audit OWASP">
        <p className="text-[11px] text-white/55 mb-3">
          Le token est <strong>décodé localement</strong> (base64url). La signature n'est pas vérifiée
          (besoin de la clé serveur). On audit alg, exp, iat, claims sensibles.
        </p>
        <textarea
          value={token}
          onChange={(e) => setToken(e.target.value)}
          rows={5}
          className="w-full rounded-lg bg-black/40 border border-white/10 px-3 py-2 text-[11px] text-white/90 font-mono resize-none mb-3"
          placeholder="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjMifQ.signature"
        />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          <div>
            <div className="text-[10px] uppercase tracking-wider text-white/50 mb-1">Header</div>
            <pre className="rounded-lg bg-black/40 border border-white/10 p-2 text-[10px] font-mono text-white/80 overflow-auto max-h-40">
              {inspection.header ? JSON.stringify(inspection.header, null, 2) : '(invalide)'}
            </pre>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-wider text-white/50 mb-1">Payload</div>
            <pre className="rounded-lg bg-black/40 border border-white/10 p-2 text-[10px] font-mono text-white/80 overflow-auto max-h-40">
              {inspection.payload ? JSON.stringify(inspection.payload, null, 2) : '(invalide)'}
            </pre>
          </div>
        </div>
        <div className="mt-3 grid grid-cols-2 lg:grid-cols-4 gap-2 text-[11px]">
          <Stat label="Expiré" value={inspection.expired ? 'OUI' : 'non'} />
          <Stat label="Pas encore valide" value={inspection.notYetValid ? 'OUI' : 'non'} />
          <Stat label="Âge (h)" value={inspection.ageHours != null ? inspection.ageHours.toFixed(1) : '—'} />
          <Stat label="Récap" value={summariseJwt(inspection)} />
        </div>
        {inspection.issues.length > 0 && (
          <div className="mt-3">
            <div className="text-[10px] uppercase tracking-wider text-white/50 mb-1 flex items-center gap-1">
              <ShieldAlert size={11} /> Audit OWASP ({inspection.issues.length})
            </div>
            <div className="space-y-1">
              {inspection.issues.map((iss, i) => (
                <div key={i} className={`rounded-md border px-2 py-1 text-[11px] ${sevColor[iss.severity]}`}>
                  <span className="font-mono text-[9px] uppercase mr-2">{iss.severity}</span>
                  {iss.message}
                </div>
              ))}
            </div>
          </div>
        )}
      </Card>
      <JwtForgerCard />
    </div>
  )
}

function JwtForgerCard() {
  const [payloadJson, setPayloadJson] = useState('{\n  "sub": "1234",\n  "name": "admin",\n  "role": "admin",\n  "iat": 1700000000\n}')
  const [secret, setSecret] = useState('secret')
  const [mode, setMode] = useState<'none' | 'hs256'>('none')
  const [forged, setForged] = useState<{ token: string; pedagogy: string[] } | null>(null)
  const [err, setErr] = useState<string | null>(null)
  // Crack
  const [crackToken, setCrackToken] = useState('')
  const [cracking, setCracking] = useState(false)
  const [crackResult, setCrackResult] = useState<{ found: boolean; secret?: string; attempts: number; durationMs: number } | null>(null)

  const forge = async () => {
    setErr(null); setForged(null)
    try {
      const payload = JSON.parse(payloadJson)
      const r = mode === 'none' ? forgeAlgNone(payload) : await forgeHs256(payload, secret)
      setForged({ token: r.token, pedagogy: r.pedagogy })
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)) }
  }

  const crack = async () => {
    if (!crackToken.trim()) return
    setCracking(true); setCrackResult(null)
    try {
      const r = await crackHs256(crackToken.trim(), [...JWT_WEAK_SECRETS])
      setCrackResult(r)
    } finally { setCracking(false) }
  }

  return (
    <Card title="JWT Forger — forge des tokens custom, crack secrets faibles">
      <div className="space-y-3">
        <div>
          <div className="text-[10px] uppercase tracking-wider text-white/50 mb-1">Payload JSON</div>
          <textarea value={payloadJson} onChange={(e) => setPayloadJson(e.target.value)} rows={5}
            className="w-full rounded-lg bg-black/40 border border-white/10 px-3 py-2 text-[10px] text-white/90 font-mono resize-none" />
        </div>
        <div className="flex gap-2">
          <button onClick={() => setMode('none')}
            className={`rounded-md px-3 py-1.5 text-[11px] border ${mode === 'none' ? 'bg-rose-500/20 border-rose-500/40 text-rose-200' : 'bg-white/5 border-white/10 text-white/60'}`}>
            alg=none (vuln)
          </button>
          <button onClick={() => setMode('hs256')}
            className={`rounded-md px-3 py-1.5 text-[11px] border ${mode === 'hs256' ? 'bg-sky-500/20 border-sky-500/40 text-sky-200' : 'bg-white/5 border-white/10 text-white/60'}`}>
            HS256 (avec secret)
          </button>
          {mode === 'hs256' && (
            <input value={secret} onChange={(e) => setSecret(e.target.value)} placeholder="secret"
              className="flex-1 rounded-md bg-black/40 border border-white/10 px-2 py-1 text-[11px] text-white/90 font-mono" />
          )}
          <button onClick={forge} className="rounded-md bg-violet-500/25 border border-violet-500/40 text-violet-100 px-3 py-1.5 text-[11px] hover:bg-violet-500/40">
            Forger
          </button>
        </div>
        {err && <p className="text-[11px] text-rose-300">{err}</p>}
        {forged && (
          <>
            <div className="rounded-md bg-black/50 border border-white/10 p-2 text-[10px] font-mono text-violet-200 break-all">
              {forged.token}
            </div>
            <ul className="text-[11px] text-white/70 list-disc list-inside space-y-0.5">
              {forged.pedagogy.map((p, i) => <li key={i}>{p}</li>)}
            </ul>
          </>
        )}
        <div className="border-t border-white/10 pt-3">
          <div className="text-[10px] uppercase tracking-wider text-white/50 mb-1">Crack HS256 secret faible</div>
          <div className="flex gap-2 mb-2">
            <input value={crackToken} onChange={(e) => setCrackToken(e.target.value)} placeholder="JWT à cracker"
              className="flex-1 rounded-md bg-black/40 border border-white/10 px-2 py-1 text-[10px] text-white/90 font-mono" />
            <button onClick={crack} disabled={cracking}
              className="rounded-md bg-rose-500/25 border border-rose-500/40 text-rose-100 px-3 py-1.5 text-[11px] hover:bg-rose-500/40 disabled:opacity-50">
              {cracking ? 'Crack…' : 'Crack'}
            </button>
          </div>
          {crackResult && (
            <div className={`rounded-md border p-2 text-[11px] ${crackResult.found ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-200' : 'bg-amber-500/15 border-amber-500/40 text-amber-200'}`}>
              {crackResult.found
                ? <>✓ Secret trouvé : <span className="font-mono text-emerald-100">{crackResult.secret}</span> · {crackResult.attempts} essais en {(crackResult.durationMs / 1000).toFixed(2)}s</>
                : <>✗ Pas dans la wordlist ({crackResult.attempts} essais)</>
              }
            </div>
          )}
        </div>
      </div>
    </Card>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-black/30 border border-white/5 px-3 py-2">
      <div className="text-[9px] uppercase tracking-wider text-white/45">{label}</div>
      <div className="text-[12px] text-white/90 font-mono mt-0.5 break-all">{value}</div>
    </div>
  )
}

function Header() {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
      <h2 className="text-white text-[15px] font-semibold mb-1">Cryptographie — du chiffre de César à AES-GCM</h2>
      <p className="text-[12px] text-white/60 leading-relaxed">
        Apprends les primitives fondamentales : substitution, transposition, chiffrement symétrique, asymétrique,
        échange de clés. Tous les calculs utilisent WebCrypto API <strong>localement</strong> — aucune donnée ne sort de ta machine.
      </p>
    </div>
  )
}

function ClassicCiphers() {
  const [input, setInput] = useState('La cryptographie classique utilise des substitutions simples.')
  const [shift, setShift] = useState(3)
  const [vigKey, setVigKey] = useState('AURORA')
  const [rails, setRails] = useState(3)

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
      <Card title="Texte d'entrée">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          rows={4}
          className="w-full rounded-lg bg-black/40 border border-white/10 px-3 py-2 text-[13px] text-white/90 resize-none"
        />
      </Card>
      <Card title="César — décalage">
        <div className="flex items-center gap-3 mb-2">
          <input type="range" min="0" max="25" value={shift} onChange={(e) => setShift(Number(e.target.value))} className="flex-1" />
          <span className="w-8 text-[12px] text-white/70 font-mono">{shift}</span>
        </div>
        <OutputBox label="Chiffré" value={caesarShift(input, shift)} />
        <OutputBox label="Déchiffré (−shift)" value={caesarShift(input, -shift)} />
      </Card>
      <Card title="Vigenère">
        <input
          value={vigKey}
          onChange={(e) => setVigKey(e.target.value)}
          placeholder="Clé"
          className="w-full mb-2 rounded-lg bg-black/40 border border-white/10 px-3 py-1.5 text-[13px] text-white/90"
        />
        <OutputBox label="Chiffré" value={vigenere(input, vigKey)} />
        <OutputBox label="Déchiffré" value={vigenere(input, vigKey, true)} />
      </Card>
      <Card title="Rail Fence + Atbash + ROT13">
        <div className="flex items-center gap-3 mb-2">
          <span className="text-[11px] text-white/60">Rails</span>
          <input type="range" min="2" max="8" value={rails} onChange={(e) => setRails(Number(e.target.value))} className="flex-1" />
          <span className="w-6 text-[12px] text-white/70 font-mono">{rails}</span>
        </div>
        <OutputBox label={`Rail Fence (${rails})`} value={railFence(input, rails)} />
        <OutputBox label="Atbash" value={atbash(input)} />
        <OutputBox label="ROT13" value={rot13(input)} />
      </Card>
    </div>
  )
}

function AESPanel() {
  const [plain, setPlain] = useState('Secret à chiffrer avec AES-GCM 256.')
  const [password, setPassword] = useState('MotDePasseFort!2026')
  const [out, setOut] = useState<{ ciphertext: string; iv: string; salt: string } | null>(null)
  const [decrypted, setDecrypted] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const encrypt = async () => {
    setBusy(true); setErr('')
    try { setOut(await aesGcmEncrypt(plain, password)); setDecrypted('') }
    catch (e) { setErr(String(e)) }
    finally { setBusy(false) }
  }
  const decrypt = async () => {
    if (!out) return
    setBusy(true); setErr('')
    try { setDecrypted(await aesGcmDecrypt(out.ciphertext, password, out.iv, out.salt)) }
    catch (e) { setErr(String(e)) }
    finally { setBusy(false) }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
      <Card title="Texte clair & mot de passe">
        <textarea value={plain} onChange={(e) => setPlain(e.target.value)} rows={4}
          className="w-full rounded-lg bg-black/40 border border-white/10 px-3 py-2 text-[13px] text-white/90 resize-none mb-2" />
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
          className="w-full rounded-lg bg-black/40 border border-white/10 px-3 py-1.5 text-[13px] text-white/90 font-mono mb-3" />
        <div className="flex gap-2">
          <button disabled={busy} onClick={encrypt}
            className="inline-flex items-center gap-2 rounded-lg bg-red-500/20 border border-red-500/40 text-red-200 px-3 py-1.5 text-[12px] hover:bg-red-500/30 disabled:opacity-50">
            <Lock size={13} /> Chiffrer
          </button>
          <button disabled={busy || !out} onClick={decrypt}
            className="inline-flex items-center gap-2 rounded-lg bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 px-3 py-1.5 text-[12px] hover:bg-emerald-500/30 disabled:opacity-50">
            <Unlock size={13} /> Déchiffrer
          </button>
        </div>
        {err && <p className="mt-2 text-[11px] text-rose-300">{err}</p>}
      </Card>
      <Card title="Sortie chiffrée (PBKDF2+AES-GCM)">
        <OutputBox label="Ciphertext (base64)" value={out?.ciphertext || '—'} />
        <OutputBox label="IV (hex)" value={out?.iv || '—'} />
        <OutputBox label="Salt (hex)" value={out?.salt || '—'} />
        {decrypted && <OutputBox label="Déchiffré" value={decrypted} />}
        <p className="mt-3 text-[11px] text-white/50">
          Dérivation PBKDF2-SHA256 (200k itérations) · clé AES-256 · IV 96 bits · tag d'authentification 128 bits.
        </p>
      </Card>
    </div>
  )
}

function RSAPanel() {
  const [plain, setPlain] = useState('Message signé par clé privée.')
  const [bits, setBits] = useState<2048 | 4096>(2048)
  const [pub, setPub] = useState('')
  const [priv, setPriv] = useState('')
  const [ciphertext, setCiphertext] = useState('')
  const [decrypted, setDecrypted] = useState('')
  const [busy, setBusy] = useState(false)
  const [keyPair, setKeyPair] = useState<CryptoKeyPair | null>(null)

  const generate = async () => {
    setBusy(true)
    try {
      const kp = await rsaGenerateKey(bits)
      setKeyPair(kp)
      setPub(await exportKeyPem(kp.publicKey, 'spki'))
      setPriv(await exportKeyPem(kp.privateKey, 'pkcs8'))
      setCiphertext(''); setDecrypted('')
    } finally { setBusy(false) }
  }
  const enc = async () => {
    if (!keyPair) return
    setBusy(true)
    try { setCiphertext(await rsaEncrypt(keyPair.publicKey, plain)) }
    finally { setBusy(false) }
  }
  const dec = async () => {
    if (!keyPair || !ciphertext) return
    setBusy(true)
    try { setDecrypted(await rsaDecrypt(keyPair.privateKey, ciphertext)) }
    finally { setBusy(false) }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
      <Card title="Génération de paire de clés">
        <div className="flex items-center gap-2 mb-3">
          <label className="text-[11px] text-white/60">Bits</label>
          <select value={bits} onChange={(e) => setBits(Number(e.target.value) as 2048 | 4096)}
            className="rounded-md bg-black/40 border border-white/10 px-2 py-1 text-[12px] text-white/90">
            <option value={2048}>2048</option>
            <option value={4096}>4096</option>
          </select>
          <button disabled={busy} onClick={generate}
            className="ml-auto inline-flex items-center gap-2 rounded-lg bg-red-500/20 border border-red-500/40 text-red-200 px-3 py-1.5 text-[12px] hover:bg-red-500/30 disabled:opacity-50">
            <Key size={13} /> Générer
          </button>
        </div>
        <textarea value={pub} readOnly rows={6}
          className="w-full rounded-lg bg-black/40 border border-white/10 px-2 py-2 text-[10px] text-white/80 font-mono resize-none mb-2" />
        <textarea value={priv} readOnly rows={6}
          className="w-full rounded-lg bg-black/40 border border-white/10 px-2 py-2 text-[10px] text-white/80 font-mono resize-none" />
      </Card>
      <Card title="Chiffrer / Déchiffrer">
        <textarea value={plain} onChange={(e) => setPlain(e.target.value)} rows={3}
          className="w-full rounded-lg bg-black/40 border border-white/10 px-3 py-2 text-[13px] text-white/90 resize-none mb-2" />
        <div className="flex gap-2 mb-3">
          <button disabled={busy || !keyPair} onClick={enc}
            className="inline-flex items-center gap-2 rounded-lg bg-red-500/20 border border-red-500/40 text-red-200 px-3 py-1.5 text-[12px] hover:bg-red-500/30 disabled:opacity-50">
            <Lock size={13} /> Chiffrer (pub)
          </button>
          <button disabled={busy || !ciphertext} onClick={dec}
            className="inline-flex items-center gap-2 rounded-lg bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 px-3 py-1.5 text-[12px] hover:bg-emerald-500/30 disabled:opacity-50">
            <Unlock size={13} /> Déchiffrer (priv)
          </button>
        </div>
        <OutputBox label="Ciphertext (b64)" value={ciphertext || '—'} />
        {decrypted && <OutputBox label="Déchiffré" value={decrypted} />}
      </Card>
    </div>
  )
}

function DHPanel() {
  const [result, setResult] = useState(() => dhDemo())
  const recompute = (aPriv: bigint, bPriv: bigint) => setResult(dhDemo(23n, 5n, aPriv, bPriv))
  return (
    <div className="space-y-3">
      <Card title="Diffie-Hellman — démonstration pédagogique">
        <p className="text-[12px] text-white/60 mb-3">
          Deux parties choisissent un secret privé chacune. En échangeant seulement g^priv mod p,
          ils calculent un secret commun sans jamais transmettre leur clé privée.
        </p>
        <div className="grid grid-cols-2 gap-3 mb-3">
          <div>
            <label className="text-[11px] text-white/60">Alice privé</label>
            <input type="number" value={String(result.aPriv)} onChange={(e) => recompute(BigInt(e.target.value || '1'), result.bPriv)}
              className="w-full rounded-lg bg-black/40 border border-white/10 px-2 py-1 text-[12px] text-white/90 font-mono" />
          </div>
          <div>
            <label className="text-[11px] text-white/60">Bob privé</label>
            <input type="number" value={String(result.bPriv)} onChange={(e) => recompute(result.aPriv, BigInt(e.target.value || '1'))}
              className="w-full rounded-lg bg-black/40 border border-white/10 px-2 py-1 text-[12px] text-white/90 font-mono" />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
          <div className="rounded-lg bg-black/30 p-2">p = {String(result.p)}, g = {String(result.g)}</div>
          <div className="rounded-lg bg-black/30 p-2">A = g^a mod p = {String(result.A)}</div>
          <div className="rounded-lg bg-black/30 p-2">B = g^b mod p = {String(result.B)}</div>
          <div className="rounded-lg bg-emerald-500/10 border border-emerald-500/30 p-2 text-emerald-200">
            secret commun = {String(result.sharedFromA)} {result.ok ? '✓ coïncide' : '✗'}
          </div>
        </div>
      </Card>
    </div>
  )
}

function EncodingPanel() {
  const [input, setInput] = useState('Hello AuroraIA')
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
      <Card title="Entrée">
        <textarea value={input} onChange={(e) => setInput(e.target.value)} rows={5}
          className="w-full rounded-lg bg-black/40 border border-white/10 px-3 py-2 text-[13px] text-white/90 resize-none" />
      </Card>
      <Card title="Base64 · Hex · Binaire · Morse">
        <OutputBox label="Base64" value={toBase64(input)} />
        <OutputBox label="Hex" value={toHex(input)} />
        <OutputBox label="Binaire" value={toBinary(input)} />
        <OutputBox label="Morse" value={toMorse(input)} />
      </Card>
      <Card title="Décoder depuis…">
        <DecodeRow label="From Base64" fn={fromBase64} input={input} />
        <DecodeRow label="From Hex" fn={fromHex} input={input} />
        <DecodeRow label="From Binary" fn={fromBinary} input={input} />
        <DecodeRow label="From Morse" fn={fromMorse} input={input} />
      </Card>
    </div>
  )
}

function DecodeRow({ label, fn, input }: { label: string; fn: (s: string) => string; input: string }) {
  const [val, setVal] = useState('')
  return (
    <div className="mb-2">
      <label className="text-[10px] text-white/50">{label}</label>
      <button onClick={() => setVal(fn(input))}
        className="ml-2 text-[10px] rounded bg-white/5 border border-white/10 px-2 py-0.5 hover:bg-white/10">
        décoder l'entrée
      </button>
      <div className="mt-1 rounded-lg bg-black/30 border border-white/5 p-2 text-[11px] font-mono break-all text-white/80">{val || '—'}</div>
    </div>
  )
}

function FrequencyPanel() {
  const [ciphertext, setCiphertext] = useState('kdqg xqh gr pdvklql phvvdjh vhfuhw frgh')
  const analysis = useMemo(() => frequencyAnalysis(ciphertext), [ciphertext])
  const suggestion = useMemo(() => suggestCaesarShift(ciphertext, 'fr'), [ciphertext])
  const max = Math.max(1, ...analysis.distribution.map((d) => d.percent))

  return (
    <div className="space-y-3">
      <Card title="Analyse fréquentielle — casser une substitution monoalphabétique">
        <textarea value={ciphertext} onChange={(e) => setCiphertext(e.target.value)} rows={3}
          className="w-full rounded-lg bg-black/40 border border-white/10 px-3 py-2 text-[13px] text-white/90 resize-none font-mono mb-3" />
        <div className="grid grid-cols-13 gap-1 mb-3">
          {analysis.distribution.map((d) => (
            <div key={d.letter} className="flex flex-col items-center">
              <div className="w-full h-20 bg-black/30 rounded relative overflow-hidden">
                <div className="absolute bottom-0 left-0 right-0 bg-red-400/80"
                  style={{ height: `${(d.percent / max) * 100}%` }} />
              </div>
              <span className="text-[9px] text-white/60 font-mono mt-0.5">{d.letter}</span>
              <span className="text-[8px] text-white/40">{d.percent.toFixed(1)}</span>
            </div>
          ))}
        </div>
        <div className="rounded-lg bg-emerald-500/10 border border-emerald-500/30 p-3 text-[12px]">
          <div className="text-emerald-200 font-semibold mb-1 flex items-center gap-2">
            <Shuffle size={13} /> Meilleure suggestion (χ² FR)
          </div>
          <p className="text-white/80">Décalage César probable : <span className="font-mono">{suggestion.bestShift}</span></p>
          <p className="text-white/70 mt-1 font-mono text-[11px]">{suggestion.suggestion}</p>
        </div>
      </Card>
    </div>
  )
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
      <h3 className="text-[12px] font-semibold text-white/80 mb-3 uppercase tracking-wider">{title}</h3>
      {children}
    </div>
  )
}

function OutputBox({ label, value }: { label: string; value: string }) {
  const copy = () => navigator.clipboard.writeText(value).catch(() => undefined)
  return (
    <div className="mb-2 last:mb-0">
      <div className="flex items-center justify-between">
        <label className="text-[10px] uppercase text-white/50 tracking-wider">{label}</label>
        <button onClick={copy} className="text-white/50 hover:text-white/80" title="Copier">
          <Copy size={11} />
        </button>
      </div>
      <div className="mt-1 rounded-lg bg-black/30 border border-white/5 p-2 text-[11px] font-mono break-all text-white/80 max-h-32 overflow-auto">
        {value}
      </div>
    </div>
  )
}
