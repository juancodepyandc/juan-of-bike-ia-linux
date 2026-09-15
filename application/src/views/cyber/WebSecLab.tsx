import { useMemo, useState } from 'react'
import { AlertTriangle, Bug, Cookie, Globe, Shield } from 'lucide-react'
import { tryInject, SQL_DEMO_PAYLOADS } from '../../services/cyber/sqlInjectionSandbox.ts'

type Tab = 'xss' | 'sqli' | 'jwt' | 'csrf' | 'ssrf' | 'owasp'

const TABS: Array<{ id: Tab; label: string }> = [
  { id: 'xss', label: 'XSS playground' },
  { id: 'sqli', label: 'SQL injection' },
  { id: 'jwt', label: 'JWT decoder' },
  { id: 'csrf', label: 'CSRF' },
  { id: 'ssrf', label: 'SSRF' },
  { id: 'owasp', label: 'OWASP Top 10' },
]

export default function WebSecLab() {
  const [tab, setTab] = useState<Tab>('xss')
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
        <h2 className="text-white text-[15px] font-semibold mb-1">Web Security — vulnérabilités et mitigations</h2>
        <p className="text-[12px] text-white/60">
          Tous les tests se déroulent dans des <strong>sandboxes locales</strong>. Aucune cible externe.
        </p>
      </div>
      <div className="flex gap-1 overflow-x-auto no-scrollbar border-b border-white/10 pb-2">
        {TABS.map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`whitespace-nowrap rounded-lg px-3 py-1.5 text-[12px] transition-colors ${
              tab === t.id
                ? 'bg-emerald-500/20 text-emerald-200 border border-emerald-500/40'
                : 'text-white/55 hover:text-white/80 hover:bg-white/5'
            }`}>
            {t.label}
          </button>
        ))}
      </div>
      {tab === 'xss' && <XSSPlayground />}
      {tab === 'sqli' && <SQLiPlayground />}
      {tab === 'jwt' && <JWTDecoder />}
      {tab === 'csrf' && <CSRFDemo />}
      {tab === 'ssrf' && <SSRFExplainer />}
      {tab === 'owasp' && <OWASPTop10 />}
    </div>
  )
}

function XSSPlayground() {
  const PRESETS: Array<{ label: string; payload: string; ctx: string }> = [
    { label: 'img onerror', payload: '<img src=x onerror=alert(1)>', ctx: 'HTML' },
    { label: 'svg onload', payload: '<svg onload=alert(1)>', ctx: 'HTML' },
    { label: 'attribute breakout', payload: '" onmouseover=alert(1) x="', ctx: 'attribut' },
    { label: 'javascript: URL', payload: 'javascript:alert(1)', ctx: 'URL' },
    { label: 'DOM eval-via-input', payload: "');alert(1);//", ctx: 'JS' },
    { label: 'data URI', payload: 'data:text/html,<script>alert(1)</script>', ctx: 'URL' },
  ]
  const [payload, setPayload] = useState('<img src=x onerror=alert(1)>')
  const [mode, setMode] = useState<'vuln' | 'safe'>('vuln')
  const output = useMemo(() => {
    if (mode === 'safe') return escapeHtml(payload)
    return payload
  }, [payload, mode])

  return (
    <div className="space-y-3">
      <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
        <h3 className="text-[12px] font-semibold text-white/80 uppercase tracking-wider mb-3">Payload XSS</h3>
        <div className="flex flex-wrap gap-1.5 mb-3">
          {PRESETS.map((p) => (
            <button key={p.label} onClick={() => setPayload(p.payload)}
              title={`${p.ctx} · ${p.payload}`}
              className="rounded-md border border-white/10 bg-white/[0.03] px-2 py-0.5 text-[10px] font-mono text-white/65 hover:text-white">
              {p.label} <span className="opacity-50">·{p.ctx}</span>
            </button>
          ))}
        </div>
        <textarea value={payload} onChange={(e) => setPayload(e.target.value)} rows={3}
          className="w-full rounded-lg bg-black/40 border border-white/10 px-3 py-2 text-[13px] text-white/90 font-mono mb-3" />
        <div className="flex gap-2 mb-3">
          <button onClick={() => setMode('vuln')}
            className={`rounded-lg px-3 py-1.5 text-[12px] border ${mode === 'vuln' ? 'bg-rose-500/20 border-rose-500/40 text-rose-200' : 'bg-white/5 border-white/10 text-white/60'}`}>
            Version vulnérable (innerHTML)
          </button>
          <button onClick={() => setMode('safe')}
            className={`rounded-lg px-3 py-1.5 text-[12px] border ${mode === 'safe' ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-200' : 'bg-white/5 border-white/10 text-white/60'}`}>
            Version sûre (escape)
          </button>
        </div>
        <div className="rounded-lg bg-black/40 border border-white/10 p-3">
          <p className="text-[10px] uppercase text-white/45 mb-2">Rendu {mode === 'vuln' ? '(dangereux)' : '(échappé)'}</p>
          <div className="rounded bg-white/5 p-3 text-[12px] text-white/90 font-mono break-all">
            {mode === 'vuln' ? (
              <div dangerouslySetInnerHTML={{ __html: sanitizeForDemo(payload) }} />
            ) : (
              <span>{output}</span>
            )}
          </div>
        </div>
        <div className="mt-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 p-3 text-[11px]">
          <strong className="text-emerald-200 flex items-center gap-2"><Shield size={12} /> Mitigations</strong>
          <ul className="mt-1 list-disc list-inside text-white/70 space-y-0.5">
            <li>Échapper côté serveur/client selon le contexte (HTML, attribut, JS, URL, CSS)</li>
            <li>Content Security Policy strict (pas d'inline script)</li>
            <li>HTTPOnly + SameSite cookies</li>
            <li>Sanitizer comme DOMPurify pour HTML riche</li>
          </ul>
        </div>
      </div>
    </div>
  )
}

function escapeHtml(s: string) {
  return s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c] || c))
}

function sanitizeForDemo(s: string) {
  // Demo: autoriser le rendu non-sécurisé MAIS retirer explicitement les scripts pour éviter XSS sur l'app elle-même
  return s.replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '[script bloqué]')
    .replace(/on\w+=/gi, 'data-blocked=')
    .replace(/javascript:/gi, 'blocked:')
}

function SQLiPlayground() {
  const [user, setUser] = useState("' OR '1'='1")
  const [pass, setPass] = useState('anything')
  const [mode, setMode] = useState<'vuln' | 'prep'>('vuln')
  const result = useMemo(() => tryInject(user, pass), [user, pass])
  const verdictTone: Record<typeof result.verdict, string> = {
    safe: 'bg-emerald-500/10 border-emerald-500/30 text-emerald-200',
    'auth-bypass': 'bg-rose-500/15 border-rose-500/40 text-rose-200',
    'union-leak': 'bg-rose-500/15 border-rose-500/40 text-rose-200',
    'comment-trick': 'bg-amber-500/15 border-amber-500/40 text-amber-200',
    destructive: 'bg-rose-500/25 border-rose-500/60 text-rose-100',
  }
  const rowsToShow = mode === 'vuln' ? result.rowsLeaked : []  // en prepared, le payload est juste une string littérale
  return (
    <div className="space-y-3">
      <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
        <div className="flex flex-wrap gap-1.5 mb-3">
          {SQL_DEMO_PAYLOADS.map((p) => (
            <button key={p.label} onClick={() => { setUser(p.username); setPass(p.password) }}
              className="rounded-md border border-white/10 bg-white/[0.03] px-2 py-0.5 text-[10px] font-mono text-white/65 hover:text-white">
              {p.label}
            </button>
          ))}
        </div>
        <div className="grid grid-cols-2 gap-2 mb-3">
          <input
            id="sqli-user" name="sqliUser" autoComplete="off"
            value={user} onChange={(e) => setUser(e.target.value)} placeholder="username"
            className="rounded-lg bg-black/40 border border-white/10 px-3 py-1.5 text-[12px] text-white/90 font-mono" />
          <input
            id="sqli-pass" name="sqliPass" autoComplete="off"
            value={pass} onChange={(e) => setPass(e.target.value)} placeholder="password"
            className="rounded-lg bg-black/40 border border-white/10 px-3 py-1.5 text-[12px] text-white/90 font-mono" />
        </div>
        <div className="flex gap-2 mb-3">
          <button onClick={() => setMode('vuln')}
            className={`rounded-lg px-3 py-1.5 text-[12px] border ${mode === 'vuln' ? 'bg-rose-500/20 border-rose-500/40 text-rose-200' : 'bg-white/5 border-white/10 text-white/60'}`}>
            Concaténation (vulnérable)
          </button>
          <button onClick={() => setMode('prep')}
            className={`rounded-lg px-3 py-1.5 text-[12px] border ${mode === 'prep' ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-200' : 'bg-white/5 border-white/10 text-white/60'}`}>
            Requête préparée (sûr)
          </button>
        </div>
        <div className="rounded-lg bg-black/50 border border-white/10 p-3 mb-3">
          <p className="text-[10px] uppercase text-white/45 mb-1">Requête {mode === 'vuln' ? 'reconstituée (concat)' : 'préparée (placeholders)'}</p>
          <pre className="text-[11px] text-white/85 font-mono whitespace-pre-wrap break-all">
            {mode === 'vuln' ? result.vulnerableQuery : result.preparedQuery}
          </pre>
        </div>
        <div className={`rounded-lg p-3 border ${verdictTone[result.verdict]}`}>
          <div className="flex items-center justify-between text-[11px] font-mono mb-1">
            <span className="font-semibold uppercase tracking-wider">{result.verdict}</span>
            <span className="opacity-70">severity {(result.severity * 100).toFixed(0)}%</span>
          </div>
          {result.detectedPatterns.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-2">
              {result.detectedPatterns.map((p, i) => (
                <span key={i} className="rounded bg-white/10 border border-white/20 px-1.5 py-0.5 text-[10px] font-mono">{p}</span>
              ))}
            </div>
          )}
          <p className="text-[11px] whitespace-pre-wrap leading-relaxed">{result.explanation}</p>
        </div>
        {rowsToShow.length > 0 && (
          <div className="mt-3 rounded-lg bg-rose-500/10 border border-rose-500/30 p-2 text-[11px]">
            <p className="font-semibold text-rose-200 mb-1">Lignes exposées ({rowsToShow.length})</p>
            <table className="w-full font-mono text-[10px]">
              <thead><tr className="text-white/55"><th className="text-left">id</th><th className="text-left">user</th><th className="text-left">pass</th><th className="text-left">role</th></tr></thead>
              <tbody>
                {rowsToShow.map((u) => (
                  <tr key={u.id} className="text-rose-100/90"><td>{u.id}</td><td>{u.username}</td><td className="text-rose-300/80">{u.password}</td><td>{u.role}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

function evalMockSqli(query: string, users: Array<{ username: string; password: string; role: string }>) {
  const m = query.match(/WHERE\s+username='([^']*)'\s+AND\s+password='([^']*)'/i)
  if (!m) {
    if (/'\s*OR\s*'1'='1/i.test(query)) return users // tautology bypass
    return []
  }
  const [, u, p] = m
  return users.filter((user) => user.username === u && user.password === p)
}

function JWTDecoder() {
  const [token, setToken] = useState('eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyIiwiYWRtaW4iOmZhbHNlfQ.sflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c')

  const parsed = useMemo(() => {
    const [h, p, s] = token.split('.')
    try {
      const header = h ? JSON.parse(atob(h.replace(/-/g, '+').replace(/_/g, '/'))) : null
      const payload = p ? JSON.parse(atob(p.replace(/-/g, '+').replace(/_/g, '/'))) : null
      return { header, payload, signature: s || '', error: null as string | null }
    } catch (e) {
      return { header: null, payload: null, signature: '', error: String(e) }
    }
  }, [token])

  const forged = useMemo(() => {
    if (!parsed.header || !parsed.payload) return ''
    const forgedHeader = { ...parsed.header, alg: 'none' }
    const forgedPayload = { ...parsed.payload, admin: true }
    const b64 = (obj: unknown) => btoa(JSON.stringify(obj)).replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_')
    return `${b64(forgedHeader)}.${b64(forgedPayload)}.`
  }, [parsed])

  return (
    <div className="space-y-3">
      <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
        <h3 className="text-[12px] font-semibold text-white/80 uppercase tracking-wider mb-3">Token JWT</h3>
        <textarea value={token} onChange={(e) => setToken(e.target.value)} rows={3}
          className="w-full rounded-lg bg-black/40 border border-white/10 px-3 py-2 text-[11px] text-white/85 font-mono mb-3" />
        {parsed.error && <ErrorBox message={parsed.error} />}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-2">
          <Box label="Header" value={parsed.header} />
          <Box label="Payload" value={parsed.payload} />
          <Box label="Signature" value={{ hex: parsed.signature } as unknown as Record<string, unknown>} />
        </div>
        {forged && (
          <div className="mt-3 rounded-lg bg-rose-500/10 border border-rose-500/30 p-3">
            <p className="text-[11px] text-rose-200 font-semibold mb-1 flex items-center gap-2">
              <AlertTriangle size={12} /> Token forgé avec <code>alg:none</code> + <code>admin:true</code>
            </p>
            <div className="text-[10px] font-mono text-white/80 break-all">{forged}</div>
            <p className="text-[10px] text-rose-200/70 mt-2">
              Une lib vulnérable qui accepte <code>alg:none</code> validerait ce token. Mitigation : whitelist d'algos côté serveur, HS256+secret fort ou RS256.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

function Box({ label, value }: { label: string; value: Record<string, unknown> | null }) {
  return (
    <div className="rounded-lg bg-black/40 border border-white/10 p-3">
      <p className="text-[10px] uppercase text-white/45 mb-1">{label}</p>
      <pre className="text-[11px] text-white/85 font-mono whitespace-pre-wrap break-all">
        {value ? JSON.stringify(value, null, 2) : '—'}
      </pre>
    </div>
  )
}

function CSRFDemo() {
  const [secret] = useState(() => generateCsrfSecret())
  const [sessionId, setSessionId] = useState(() => generateSessionId())
  const [token, setToken] = useState<string>('')
  const [originHeader, setOriginHeader] = useState('https://evil.com')
  const [submittedToken, setSubmittedToken] = useState('')
  const [verdict, setVerdict] = useState<{ status: 'ok' | 'block'; reason: string } | null>(null)

  const generate = async () => {
    const tk = await signCsrfToken(sessionId, secret)
    setToken(tk)
    setSubmittedToken(tk)
  }

  const verify = async () => {
    // Étape 1 : vérifier Origin/Referer.
    if (originHeader && !/^https:\/\/(www\.)?bank\.com/.test(originHeader)) {
      setVerdict({ status: 'block', reason: `Origin "${originHeader}" ≠ bank.com → bloque pré-CSRF` })
      return
    }
    // Étape 2 : vérifier token HMAC signé.
    const expected = await signCsrfToken(sessionId, secret)
    if (submittedToken !== expected) {
      setVerdict({ status: 'block', reason: 'Token CSRF invalide / périmé / pas lié à la session.' })
      return
    }
    setVerdict({ status: 'ok', reason: 'Origin OK + token valide pour cette session → autorisé.' })
  }

  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 space-y-3">
      <h3 className="text-[12px] font-semibold text-white/80 uppercase tracking-wider flex items-center gap-2">
        <Cookie size={13} /> CSRF — playground sync token + origin check
      </h3>
      <p className="text-[12px] text-white/70">
        Pattern Synchronizer Token : le serveur génère HMAC(sessionId, secret), le mappe au formulaire.
        À la soumission, il revérifie. Combiné avec un check Origin, ça bloque CSRF même sans SameSite.
      </p>
      <div className="rounded-lg bg-black/40 border border-white/10 p-3 text-[11px] font-mono text-white/85">
        <pre className="whitespace-pre-wrap text-[10px]">{`<!-- evil.com (l'attaquant) -->
<form action="https://bank.com/transfer" method="POST">
  <input name="to" value="attacker" />
  <input name="amount" value="1000" />
  <!-- attacker N'A PAS le bon csrfToken -->
</form>
<script>document.forms[0].submit()</script>`}</pre>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-[11px]">
        <div className="rounded-lg bg-black/30 border border-white/10 p-2">
          <div className="text-[10px] uppercase tracking-wider text-white/50 mb-1">Session ID (cookie)</div>
          <input
            id="csrf-session" name="csrfSession"
            value={sessionId} onChange={(e) => setSessionId(e.target.value)}
            className="w-full rounded bg-black/40 border border-white/10 px-2 py-1 text-[10px] font-mono text-white/85"
          />
        </div>
        <div className="rounded-lg bg-black/30 border border-white/10 p-2">
          <div className="text-[10px] uppercase tracking-wider text-white/50 mb-1">Origin du browser</div>
          <input
            id="csrf-origin" name="csrfOrigin"
            value={originHeader} onChange={(e) => setOriginHeader(e.target.value)}
            placeholder="https://bank.com"
            className="w-full rounded bg-black/40 border border-white/10 px-2 py-1 text-[10px] font-mono text-white/85"
          />
        </div>
      </div>
      <div className="flex gap-2">
        <button onClick={() => void generate()}
          className="rounded-lg bg-sky-500/20 border border-sky-500/40 text-sky-200 px-3 py-1.5 text-[11px] hover:bg-sky-500/30">
          1. Générer token CSRF (côté serveur)
        </button>
      </div>
      {token && (
        <div className="rounded-lg bg-sky-500/[0.05] border border-sky-500/30 p-2 text-[10px] font-mono text-sky-100 break-all">
          csrfToken = {token}
        </div>
      )}
      <div className="rounded-lg bg-black/30 border border-white/10 p-2">
        <div className="text-[10px] uppercase tracking-wider text-white/50 mb-1">Token soumis par le formulaire</div>
        <input
          id="csrf-submitted" name="csrfSubmitted"
          value={submittedToken} onChange={(e) => setSubmittedToken(e.target.value)}
          placeholder="(que l'attaquant ne connaît pas)"
          className="w-full rounded bg-black/40 border border-white/10 px-2 py-1 text-[10px] font-mono text-white/85"
        />
      </div>
      <button onClick={() => void verify()}
        className="rounded-lg bg-violet-500/25 border border-violet-500/45 text-violet-100 px-3 py-1.5 text-[11px] hover:bg-violet-500/40">
        2. Vérifier (origin + token)
      </button>
      {verdict && (
        <div className={`rounded-lg border p-3 text-[11px] ${verdict.status === 'ok' ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-100' : 'bg-rose-500/15 border-rose-500/40 text-rose-100'}`}>
          <strong>{verdict.status === 'ok' ? '✓ AUTORISÉ' : '✗ BLOQUÉ'}</strong> · {verdict.reason}
        </div>
      )}
      <div className="rounded-lg bg-emerald-500/[0.04] border border-emerald-500/20 p-3 text-[11px]">
        <strong className="text-emerald-200">Mitigations layered</strong>
        <ul className="mt-1 list-disc list-inside text-white/75 space-y-0.5">
          <li>SameSite=Lax/Strict sur cookies de session (browser-side)</li>
          <li>Token CSRF synchrone signé HMAC + lié à la session</li>
          <li>Double-submit cookie (cookie + header X-CSRF — both must match)</li>
          <li>Vérification <code>Origin</code>/<code>Referer</code> serveur-side</li>
          <li>Re-authentication pour actions sensibles (virement, suppression compte)</li>
        </ul>
      </div>
    </div>
  )
}

function generateCsrfSecret(): string {
  const bytes = new Uint8Array(32)
  if (typeof crypto !== 'undefined') crypto.getRandomValues(bytes)
  return Array.from(bytes).map((b) => b.toString(16).padStart(2, '0')).join('')
}

function generateSessionId(): string {
  const bytes = new Uint8Array(16)
  if (typeof crypto !== 'undefined') crypto.getRandomValues(bytes)
  return Array.from(bytes).map((b) => b.toString(16).padStart(2, '0')).join('')
}

async function signCsrfToken(sessionId: string, secret: string): Promise<string> {
  if (typeof crypto === 'undefined' || !crypto.subtle) return `${sessionId}.unsigned`
  const enc = new TextEncoder()
  const key = await crypto.subtle.importKey(
    'raw', enc.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false, ['sign'],
  )
  const sig = await crypto.subtle.sign('HMAC', key, enc.encode(sessionId))
  return Array.from(new Uint8Array(sig)).map((b) => b.toString(16).padStart(2, '0')).join('').slice(0, 32)
}

function SSRFExplainer() {
  const [url, setUrl] = useState('http://169.254.169.254/latest/meta-data/')
  const verdict = useMemo(() => analyzeSsrfTarget(url), [url])
  const TARGETS: Array<{ url: string; label: string; tone: string }> = [
    { url: 'http://169.254.169.254/latest/meta-data/', label: 'AWS metadata', tone: 'rose' },
    { url: 'http://metadata.google.internal/computeMetadata/v1/', label: 'GCP metadata', tone: 'rose' },
    { url: 'http://127.0.0.1:6379/', label: 'Redis local', tone: 'rose' },
    { url: 'http://10.0.0.1/admin', label: 'Intranet RFC1918', tone: 'rose' },
    { url: 'file:///etc/passwd', label: 'Local file', tone: 'rose' },
    { url: 'gopher://localhost:6379/_FLUSHALL', label: 'Gopher exotic', tone: 'rose' },
    { url: 'https://example.com/', label: 'Public OK', tone: 'emerald' },
  ]
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 space-y-3">
      <h3 className="text-[12px] font-semibold text-white/80 uppercase tracking-wider flex items-center gap-2">
        <Globe size={13} /> SSRF playground · audit cible
      </h3>
      <p className="text-[12px] text-white/70">
        Colle une URL — Aurora évalue si un serveur backend qui forward cette requête serait
        vulnérable. Auditeur intégré : détecte IP privées, link-local, schèmes dangereux,
        bypass DNS rebinding.
      </p>
      <div className="flex flex-wrap gap-1.5 mb-2">
        {TARGETS.map((t) => (
          <button key={t.url} onClick={() => setUrl(t.url)}
            className="rounded-md border border-white/10 bg-white/[0.03] px-2 py-0.5 text-[10px] font-mono text-white/65 hover:text-white">
            {t.label}
          </button>
        ))}
      </div>
      <input
        id="ssrf-url" name="ssrfUrl" value={url} onChange={(e) => setUrl(e.target.value)}
        placeholder="https://..."
        className="w-full rounded-lg bg-black/40 border border-white/10 px-3 py-2 text-[12px] text-white/90 font-mono"
      />
      <div className={`rounded-lg border p-3 text-[11px] ${verdict.tone === 'block' ? 'bg-rose-500/15 border-rose-500/40' : verdict.tone === 'warn' ? 'bg-amber-500/15 border-amber-500/40' : 'bg-emerald-500/15 border-emerald-500/40'}`}>
        <div className="font-mono text-[11px] uppercase tracking-wider mb-1">
          <span className={verdict.tone === 'block' ? 'text-rose-200' : verdict.tone === 'warn' ? 'text-amber-200' : 'text-emerald-200'}>
            {verdict.tone === 'block' ? '✗ BLOCK' : verdict.tone === 'warn' ? '⚠ WARN' : '✓ OK'}
          </span>
          <span className="text-white/55 ml-2">{verdict.reason}</span>
        </div>
        {verdict.detail && <p className="text-white/70 mt-1">{verdict.detail}</p>}
      </div>
      <div className="rounded-lg bg-emerald-500/[0.04] border border-emerald-500/20 p-3 text-[11px]">
        <strong className="text-emerald-200">Mitigations</strong>
        <ul className="mt-1 list-disc list-inside text-white/75 space-y-0.5">
          <li>Allowlist d'URLs / domaines autorisés</li>
          <li>Bloquer les schèmes dangereux (file, gopher, dict, ftp)</li>
          <li>Bloquer les IP privées/link-local/metadata (169.254.169.254, 100.100.100.200, fd00::/8)</li>
          <li>Résoudre DNS UNE FOIS et utiliser l'IP résolue → empêche DNS rebinding</li>
          <li>Désactiver follow redirect ou le limiter</li>
          <li>Exécuter dans un namespace réseau isolé / via egress proxy</li>
        </ul>
      </div>
    </div>
  )
}

// Analyse une URL pour repérer les patterns SSRF dangereux.
function analyzeSsrfTarget(url: string): { tone: 'block' | 'warn' | 'ok'; reason: string; detail?: string } {
  if (!url) return { tone: 'ok', reason: 'vide' }
  let parsed: URL | null = null
  try { parsed = new URL(url) } catch { return { tone: 'block', reason: 'URL malformée', detail: 'Une URL invalide peut faire crash certains clients ou bypass parseurs faibles.' } }
  const proto = parsed.protocol
  if (!/^https?:$/i.test(proto)) {
    return {
      tone: 'block',
      reason: `Schème ${proto} dangereux`,
      detail: 'file, gopher, dict, ldap, ftp exposent fichiers locaux ou permettent du smuggling protocolaire.',
    }
  }
  const host = parsed.hostname
  // IP privées / link-local
  const privatePatterns = [
    /^127\./, /^10\./, /^172\.(1[6-9]|2[0-9]|3[01])\./, /^192\.168\./,
    /^169\.254\./, /^100\.6[4-9]\.|^100\.[7-9]\d\.|^100\.1[01]\d\.|^100\.12[0-7]\./,
    /^0\./, /^::1$/i, /^fe80::/i, /^fd[0-9a-f]{2}::/i,
    /^localhost$/i, /^.*\.localhost$/i,
  ]
  if (privatePatterns.some((re) => re.test(host))) {
    if (/169\.254\.169\.254|metadata\./.test(host)) {
      return {
        tone: 'block',
        reason: `Metadata cloud — ${host}`,
        detail: 'AWS/GCP/Azure metadata service expose des credentials IAM. SSRF ici = compromission cloud.',
      }
    }
    return {
      tone: 'block',
      reason: `IP privée / link-local — ${host}`,
      detail: 'Permet d\'atteindre des services internes (Redis, Memcached, intranet admin) depuis le serveur.',
    }
  }
  // Pattern de bypass (URL encoding, IPv4 decimal, IPv6 wrapping, etc.)
  if (/%2e|%2f/i.test(url)) {
    return { tone: 'warn', reason: 'URL encoding suspect', detail: 'Tentative de bypass d\'allowlist via encoding %2e=. %2f=/.' }
  }
  if (/@/.test(parsed.host)) {
    return { tone: 'warn', reason: 'Userinfo dans l\'host', detail: 'http://allowlisted.com@evil.com — certains parseurs lisent allowlisted comme host, browsers naviguent vers evil.com.' }
  }
  if (/^\d+$/.test(host) || /0x[0-9a-f]/i.test(host)) {
    return { tone: 'warn', reason: 'IP encodée (décimal/hex)', detail: 'http://2130706433/ = http://127.0.0.1/ — bypass d\'allowlist string-match.' }
  }
  return { tone: 'ok', reason: 'Cible externe publique', detail: 'OK si l\'allowlist serveur l\'autorise. Vérifier DNS rebinding et redirects.' }
}

function OWASPTop10() {
  const items = [
    { id: 'A01', title: 'Broken Access Control', why: 'URL manipulation, IDOR, missing authZ.', fix: 'Default deny, RBAC/ABAC, logs' },
    { id: 'A02', title: 'Cryptographic Failures', why: 'Chiffrement faible, clés exposées, TLS non imposé.', fix: 'TLS partout, KMS, AES-GCM/ChaCha20' },
    { id: 'A03', title: 'Injection', why: 'SQL/NoSQL/Command injection.', fix: 'Requêtes préparées, ORM, validate' },
    { id: 'A04', title: 'Insecure Design', why: 'Manque de threat model.', fix: 'Threat modeling, secure defaults' },
    { id: 'A05', title: 'Security Misconfiguration', why: 'Config par défaut, headers absents.', fix: 'Hardening guides, scanners' },
    { id: 'A06', title: 'Vulnerable Components', why: 'Dépendances CVE.', fix: 'SBOM, scan, mises à jour' },
    { id: 'A07', title: 'Auth & Identity Failures', why: 'Reset token faible, MFA absent.', fix: 'WebAuthn/FIDO2, PBKDF2/Argon2' },
    { id: 'A08', title: 'Software & Data Integrity', why: 'Supply chain, CI/CD compromis.', fix: 'Signatures, SLSA, pinning' },
    { id: 'A09', title: 'Logging & Monitoring', why: 'Pas de détection d\'attaque.', fix: 'SIEM, alerting, retention' },
    { id: 'A10', title: 'SSRF', why: 'Serveur fait requête vers URL contrôlée.', fix: 'Allowlist, bloquer IPs privées' },
  ]
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
      {items.map((it) => (
        <div key={it.id} className="rounded-lg border border-white/10 bg-white/[0.02] p-3">
          <div className="flex items-center gap-2 mb-1">
            <span className="rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 px-2 py-0.5 text-[10px] font-mono">{it.id}</span>
            <span className="text-[12px] font-semibold text-white">{it.title}</span>
          </div>
          <p className="text-[11px] text-white/65"><Bug size={10} className="inline mr-1" />{it.why}</p>
          <p className="text-[11px] text-emerald-200 mt-1"><Shield size={10} className="inline mr-1" />{it.fix}</p>
        </div>
      ))}
    </div>
  )
}

function ErrorBox({ message }: { message: string }) {
  return <div className="rounded-lg bg-rose-500/10 border border-rose-500/30 p-2 text-[11px] text-rose-200 font-mono mb-2">{message}</div>
}
