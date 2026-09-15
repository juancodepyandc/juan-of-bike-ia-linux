import { useState } from 'react'
import { AlertTriangle, Globe, Loader2, Network, Radio, Search, ShieldCheck, Wifi } from 'lucide-react'
import {
  cyberDnsLookup,
  cyberHttpHeaders,
  cyberPcapDemo,
  cyberPortScan,
  cyberTlsCert,
  cyberTraceroute,
  cyberWhois,
  type HttpHeadersResult,
  type PortScanResult,
  type TlsCertResult,
} from '../../services/cyber/pythonClient.ts'
import {
  crackHandshake,
  DEMO_DICTIONARY,
  forgeCapturedHandshake,
  type SimHandshake,
} from '../../services/cyber/wifiHandshakeSim.ts'

type Tab = 'dns' | 'tls' | 'whois' | 'http' | 'scan' | 'trace' | 'pcap' | 'wifi' | 'wps'

const TABS: Array<{ id: Tab; label: string; danger?: boolean }> = [
  { id: 'dns', label: 'DNS' },
  { id: 'tls', label: 'Certificat TLS' },
  { id: 'whois', label: 'WHOIS' },
  { id: 'http', label: 'HTTP headers' },
  { id: 'scan', label: 'Port scan local', danger: true },
  { id: 'trace', label: 'Traceroute' },
  { id: 'pcap', label: 'PCAP démo' },
  { id: 'wifi', label: 'Wi-Fi handshake sim' },
  { id: 'wps', label: 'WPS PIN faille' },
]

export default function NetworkLab() {
  const [tab, setTab] = useState<Tab>('dns')
  return (
    <div className="space-y-4">
      <EthicsBanner />
      <div className="flex gap-1 overflow-x-auto no-scrollbar border-b border-white/10 pb-2">
        {TABS.map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`whitespace-nowrap rounded-lg px-3 py-1.5 text-[12px] transition-colors ${
              tab === t.id
                ? 'bg-blue-500/20 text-blue-200 border border-blue-500/40'
                : 'text-white/55 hover:text-white/80 hover:bg-white/5'
            }`}>
            {t.label}
          </button>
        ))}
      </div>
      {tab === 'dns' && <DnsTool />}
      {tab === 'tls' && <TlsTool />}
      {tab === 'whois' && <WhoisTool />}
      {tab === 'http' && <HttpTool />}
      {tab === 'scan' && <ScanTool />}
      {tab === 'trace' && <TraceTool />}
      {tab === 'pcap' && <PcapTool />}
      {tab === 'wifi' && <WifiHandshakeTool />}
      {tab === 'wps' && <WpsPinTool />}
    </div>
  )
}

function WpsPinTool() {
  const [secretPin, setSecretPin] = useState('12345670') // 8 digits dont 1 checksum
  const [phase, setPhase] = useState<'idle' | 'cracking' | 'done'>('idle')
  const [progress, setProgress] = useState<{ stage: 1 | 2; tries: number; total: number; candidate: string } | null>(null)
  const [result, setResult] = useState<{ found: string; firstHalfTries: number; secondHalfTries: number; totalMs: number } | null>(null)

  // WPS PIN = 8 chiffres dont le dernier est un checksum (calcul officiel).
  // Vulnérabilité : le routeur valide les 4 premiers ET les 4 suivants
  // SÉPARÉMENT. Donc au lieu de 10^7 (10 millions) essais → 10^4 + 10^3 (≤ 11000).
  const computeChecksum = (sevenDigits: string): number => {
    const d = sevenDigits.split('').map(Number)
    const accum =
      3 * (d[0] + d[2] + d[4] + d[6]) +
      1 * (d[1] + d[3] + d[5])
    return (10 - (accum % 10)) % 10
  }

  const crack = async () => {
    if (!/^\d{8}$/.test(secretPin)) return
    setPhase('cracking'); setResult(null); setProgress(null)
    const start = performance.now()
    const targetFirst = secretPin.slice(0, 4)
    const targetSecond = secretPin.slice(4, 7) // 3 digits, le 8e = checksum
    // Phase 1 : brute-force les 4 premiers digits.
    let firstHalfTries = 0
    let foundFirst = ''
    for (let i = 0; i < 10000; i += 1) {
      const cand = i.toString().padStart(4, '0')
      firstHalfTries += 1
      if (i % 200 === 0) {
        setProgress({ stage: 1, tries: firstHalfTries, total: 10000, candidate: cand })
        await new Promise((r) => setTimeout(r, 0))
      }
      if (cand === targetFirst) {
        foundFirst = cand
        break
      }
    }
    // Phase 2 : brute-force les 3 digits suivants (le 8e est calculé).
    let secondHalfTries = 0
    let foundFull = ''
    for (let i = 0; i < 1000; i += 1) {
      const sec = i.toString().padStart(3, '0')
      const sevenDigits = foundFirst + sec
      const cks = computeChecksum(sevenDigits)
      const cand = sevenDigits + cks
      secondHalfTries += 1
      if (i % 50 === 0) {
        setProgress({ stage: 2, tries: secondHalfTries, total: 1000, candidate: cand })
        await new Promise((r) => setTimeout(r, 0))
      }
      if (sec === targetSecond) {
        foundFull = cand
        break
      }
    }
    setResult({ found: foundFull, firstHalfTries, secondHalfTries, totalMs: performance.now() - start })
    setPhase('done')
  }

  return (
    <div className="space-y-3">
      <div className="rounded-xl border border-purple-500/30 bg-purple-500/[0.05] p-3 flex gap-3">
        <Wifi size={14} className="text-purple-300 shrink-0 mt-0.5" />
        <p className="text-[11px] text-purple-100/80 leading-relaxed">
          WPS (Wi-Fi Protected Setup) avait une faille majeure : le routeur valide les 4 premiers digits ET
          les 4 suivants SÉPARÉMENT. Au lieu de 10⁷ essais (10M), il en faut 10⁴+10³ ≈ <strong>11 000</strong>.
          Reaver/Bully exploitent ça depuis 2011. Solution : <strong>désactiver WPS</strong> sur le routeur.
        </p>
      </div>
      <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 space-y-3">
        <label className="text-[11px] text-white/65 block">
          PIN WPS secret (8 digits, le 8e est un checksum)
          <input
            id="wps-pin" name="wpsPin"
            value={secretPin} onChange={(e) => setSecretPin(e.target.value.replace(/\D/g, '').slice(0, 8))}
            placeholder="12345670"
            className="mt-1 w-full rounded-md bg-black/40 border border-white/10 px-2 py-1.5 text-[14px] text-white/90 font-mono"
          />
          <span className="text-[10px] text-white/50">
            Aurora vérifie le checksum officiel : pour "{secretPin.slice(0, 7)}" → checksum attendu = {/^\d{7}/.test(secretPin) ? computeChecksum(secretPin.slice(0, 7)) : '?'}
          </span>
        </label>
        <button onClick={crack} disabled={phase === 'cracking' || !/^\d{8}$/.test(secretPin)}
          className="rounded-lg bg-rose-500/20 border border-rose-500/40 text-rose-200 px-3 py-1.5 text-[12px] hover:bg-rose-500/30 disabled:opacity-50">
          {phase === 'cracking' ? <><Loader2 size={12} className="inline animate-spin mr-1.5" /> Crack en cours…</> : 'Lancer Reaver-like'}
        </button>
        {progress && (
          <div className="text-[10px] text-white/55 font-mono">
            Phase {progress.stage}/2 · {progress.tries}/{progress.total} essais · candidate « {progress.candidate} »
          </div>
        )}
        {result && (
          <div className="rounded-lg bg-emerald-500/15 border border-emerald-500/40 p-3 text-[11px]">
            <div className="text-emerald-200 font-semibold mb-1">✓ PIN cassé : <span className="font-mono">{result.found}</span></div>
            <div className="text-white/80 font-mono">
              Phase 1 (4 premiers) : {result.firstHalfTries} essais<br/>
              Phase 2 (3 suivants) : {result.secondHalfTries} essais<br/>
              TOTAL : <strong>{result.firstHalfTries + result.secondHalfTries}</strong> au lieu de 10⁷ = 10 000 000.<br/>
              Temps : {(result.totalMs / 1000).toFixed(2)}s (sim navigateur — Reaver réel envoie ~1 req/s)
            </div>
            <p className="mt-2 text-[10px] text-white/55">
              En réel : Reaver/Bully met de 4h à 10h pour énumérer ces 11000 essais (le routeur a un rate-limit).
              <strong> Fix opérationnel</strong> : DÉSACTIVER WPS dans les paramètres du routeur. Aujourd'hui, certains routeurs ont aussi des lockout après N tentatives.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

function WifiHandshakeTool() {
  const [ssid, setSsid] = useState('AuroraDojo')
  const [secret, setSecret] = useState('motdepasse')
  const [handshake, setHandshake] = useState<SimHandshake | null>(null)
  const [forging, setForging] = useState(false)
  const [cracking, setCracking] = useState(false)
  const [progress, setProgress] = useState<{ i: number; total: number; candidate: string } | null>(null)
  const [result, setResult] = useState<{ found: boolean; passphrase?: string; attempts: number; durationMs: number } | null>(null)
  const [customDict, setCustomDict] = useState('')

  const forge = async () => {
    setForging(true); setHandshake(null); setResult(null); setProgress(null)
    try {
      const hs = await forgeCapturedHandshake(secret, ssid)
      setHandshake(hs)
    } finally { setForging(false) }
  }

  const crack = async () => {
    if (!handshake) return
    setCracking(true); setResult(null); setProgress(null)
    try {
      const dict = customDict.trim()
        ? customDict.split(/\r?\n/).map((s) => s.trim()).filter(Boolean)
        : [...DEMO_DICTIONARY]
      const r = await crackHandshake(handshake, dict, {
        onProgress: (i, total, candidate) => setProgress({ i, total, candidate }),
      })
      setResult({
        found: r.found,
        passphrase: r.passphrase,
        attempts: r.attempts,
        durationMs: r.durationMs,
      })
    } finally { setCracking(false); setProgress(null) }
  }

  return (
    <div className="space-y-3">
      <div className="rounded-xl border border-purple-500/30 bg-purple-500/[0.05] p-3 flex gap-3">
        <Wifi size={14} className="text-purple-300 shrink-0 mt-0.5" />
        <p className="text-[11px] text-purple-100/80 leading-relaxed">
          Simulateur 4-way handshake WPA2-PSK : un AP fictif émet un handshake basé sur ta passphrase secrète,
          puis un dictionnaire essaie de la retrouver. Utilise la vraie PBKDF2-SHA1 4096 itér (WebCrypto local).
          <strong> Pédagogie uniquement</strong> — n'utilise jamais sur un réseau qui n'est pas le tien.
        </p>
      </div>
      <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 space-y-3">
        <h3 className="text-[12px] font-semibold text-white/80 uppercase tracking-wider">1. Forger le handshake</h3>
        <div className="grid grid-cols-2 gap-2">
          <label className="text-[11px] text-white/65">
            SSID
            <input value={ssid} onChange={(e) => setSsid(e.target.value)}
              className="mt-1 w-full rounded-md bg-black/40 border border-white/10 px-2 py-1.5 text-[12px] text-white/90 font-mono" />
          </label>
          <label className="text-[11px] text-white/65">
            Passphrase secrète (l'AP la connaît)
            <input value={secret} onChange={(e) => setSecret(e.target.value)} type="password"
              className="mt-1 w-full rounded-md bg-black/40 border border-white/10 px-2 py-1.5 text-[12px] text-white/90 font-mono" />
          </label>
        </div>
        <button onClick={forge} disabled={forging || secret.length < 8}
          className="rounded-lg bg-purple-500/20 border border-purple-500/40 text-purple-200 px-3 py-1.5 text-[12px] hover:bg-purple-500/30 disabled:opacity-50">
          {forging ? <><Loader2 size={12} className="inline animate-spin mr-1.5" /> Dérivation PMK…</> : <>Capturer le handshake</>}
        </button>
        {handshake && (
          <div className="rounded-lg bg-black/40 border border-white/10 p-2 text-[11px] font-mono space-y-1">
            <div><span className="text-white/50">SSID :</span> <span className="text-purple-200">{handshake.ssid}</span></div>
            <div><span className="text-white/50">AP MAC :</span> {handshake.apMac}</div>
            <div><span className="text-white/50">STA MAC :</span> {handshake.staMac}</div>
            <div><span className="text-white/50">ANonce :</span> <span className="text-white/70 break-all">{handshake.aNonce}</span></div>
            <div><span className="text-white/50">SNonce :</span> <span className="text-white/70 break-all">{handshake.sNonce}</span></div>
            <div><span className="text-white/50">PMK hash :</span> <span className="text-rose-200 break-all">{handshake.pmkHash}</span></div>
          </div>
        )}
      </div>

      <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 space-y-3">
        <h3 className="text-[12px] font-semibold text-white/80 uppercase tracking-wider">2. Brute-force dictionnaire</h3>
        <label className="text-[11px] text-white/65 block">
          Dictionnaire custom (1 mot/ligne) — laisse vide pour utiliser le dict démo de 20 entrées
          <textarea value={customDict} onChange={(e) => setCustomDict(e.target.value)} rows={3}
            placeholder="motdepasse&#10;password&#10;12345678"
            className="mt-1 w-full rounded-md bg-black/40 border border-white/10 px-2 py-1.5 text-[11px] text-white/90 font-mono resize-none" />
        </label>
        <button onClick={crack} disabled={!handshake || cracking}
          className="rounded-lg bg-rose-500/20 border border-rose-500/40 text-rose-200 px-3 py-1.5 text-[12px] hover:bg-rose-500/30 disabled:opacity-50">
          {cracking ? <><Loader2 size={12} className="inline animate-spin mr-1.5" /> Crack en cours…</> : <>Lancer le crack</>}
        </button>
        {progress && (
          <div className="text-[10px] text-white/55 font-mono">
            {progress.i + 1}/{progress.total} · essai « <span className="text-white/85">{progress.candidate}</span> »
          </div>
        )}
        {result && (
          <div className={`rounded-lg border p-3 ${result.found ? 'bg-emerald-500/10 border-emerald-500/40' : 'bg-amber-500/10 border-amber-500/40'}`}>
            <div className="text-[12px] font-mono">
              {result.found ? (
                <>
                  <strong className="text-emerald-200">✓ Passphrase trouvée :</strong>{' '}
                  <span className="text-emerald-100">{result.passphrase}</span>
                </>
              ) : (
                <strong className="text-amber-200">✗ Pas dans le dictionnaire — passphrase plus forte qu'attendu.</strong>
              )}
            </div>
            <div className="text-[10px] text-white/55 mt-1 font-mono">
              {result.attempts} tentatives en {(result.durationMs / 1000).toFixed(2)}s ·
              ~{(result.attempts / (result.durationMs / 1000)).toFixed(0)} essais/s
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function EthicsBanner() {
  return (
    <div className="rounded-xl border border-amber-500/30 bg-amber-500/[0.05] p-3 flex gap-3">
      <AlertTriangle size={14} className="text-amber-300 shrink-0 mt-0.5" />
      <div>
        <p className="text-[12px] text-amber-100 font-medium">Usage éthique uniquement</p>
        <p className="text-[11px] text-amber-200/70 mt-0.5">
          DNS/TLS/WHOIS/HTTP sont des requêtes publiques légitimes. Le <strong>port scan</strong> est
          limité par le backend à <strong>127.0.0.1 et réseaux privés RFC1918</strong>. Aucune cible publique.
        </p>
      </div>
    </div>
  )
}

function BaseTool({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
      <h3 className="text-[12px] font-semibold text-white/80 uppercase tracking-wider mb-3">{title}</h3>
      {children}
    </div>
  )
}

function useRunner<T>() {
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [data, setData] = useState<T | null>(null)
  const run = async (fn: () => Promise<T>) => {
    setBusy(true); setErr('')
    try { setData(await fn()) }
    catch (e) { setErr(String(e)) }
    finally { setBusy(false) }
  }
  return { busy, err, data, run }
}

function DnsTool() {
  const [domain, setDomain] = useState('example.com')
  const { busy, err, data, run } = useRunner<Record<string, unknown>>()
  return (
    <BaseTool title="DNS lookup (A/AAAA/MX/TXT/NS)">
      <div className="flex gap-2 mb-3">
        <input value={domain} onChange={(e) => setDomain(e.target.value)}
          className="flex-1 rounded-lg bg-black/40 border border-white/10 px-3 py-1.5 text-[12px] text-white/90 font-mono" />
        <button disabled={busy || !domain} onClick={() => run(() => cyberDnsLookup(domain))}
          className="inline-flex items-center gap-2 rounded-lg bg-blue-500/20 border border-blue-500/40 text-blue-200 px-3 py-1.5 text-[12px] hover:bg-blue-500/30 disabled:opacity-50">
          {busy ? <Loader2 size={13} className="animate-spin" /> : <Globe size={13} />} lookup
        </button>
      </div>
      {err && <ErrorBox message={err} />}
      {data && <JsonBox value={data} />}
    </BaseTool>
  )
}

function TlsTool() {
  const [host, setHost] = useState('cloudflare.com')
  const [port, setPort] = useState(443)
  const { busy, err, data, run } = useRunner<TlsCertResult>()
  return (
    <BaseTool title="Certificat X.509 (TLS)">
      <div className="flex gap-2 mb-3">
        <input value={host} onChange={(e) => setHost(e.target.value)}
          className="flex-1 rounded-lg bg-black/40 border border-white/10 px-3 py-1.5 text-[12px] text-white/90 font-mono" />
        <input type="number" value={port} onChange={(e) => setPort(Number(e.target.value))}
          className="w-20 rounded-lg bg-black/40 border border-white/10 px-3 py-1.5 text-[12px] text-white/90 font-mono" />
        <button disabled={busy || !host} onClick={() => run(() => cyberTlsCert(host, port))}
          className="inline-flex items-center gap-2 rounded-lg bg-blue-500/20 border border-blue-500/40 text-blue-200 px-3 py-1.5 text-[12px] hover:bg-blue-500/30 disabled:opacity-50">
          {busy ? <Loader2 size={13} className="animate-spin" /> : <ShieldCheck size={13} />} récupérer
        </button>
      </div>
      {err && <ErrorBox message={err} />}
      {data && <JsonBox value={data as unknown as Record<string, unknown>} />}
    </BaseTool>
  )
}

function WhoisTool() {
  const [domain, setDomain] = useState('example.com')
  const { busy, err, data, run } = useRunner<Record<string, unknown>>()
  return (
    <BaseTool title="WHOIS registre">
      <div className="flex gap-2 mb-3">
        <input value={domain} onChange={(e) => setDomain(e.target.value)}
          className="flex-1 rounded-lg bg-black/40 border border-white/10 px-3 py-1.5 text-[12px] text-white/90 font-mono" />
        <button disabled={busy || !domain} onClick={() => run(() => cyberWhois(domain))}
          className="inline-flex items-center gap-2 rounded-lg bg-blue-500/20 border border-blue-500/40 text-blue-200 px-3 py-1.5 text-[12px] hover:bg-blue-500/30 disabled:opacity-50">
          {busy ? <Loader2 size={13} className="animate-spin" /> : <Search size={13} />} whois
        </button>
      </div>
      {err && <ErrorBox message={err} />}
      {data && <JsonBox value={data} />}
    </BaseTool>
  )
}

function HttpTool() {
  const [url, setUrl] = useState('https://example.com')
  const { busy, err, data, run } = useRunner<HttpHeadersResult>()
  return (
    <BaseTool title="HTTP security headers">
      <div className="flex gap-2 mb-3">
        <input value={url} onChange={(e) => setUrl(e.target.value)}
          className="flex-1 rounded-lg bg-black/40 border border-white/10 px-3 py-1.5 text-[12px] text-white/90 font-mono" />
        <button disabled={busy || !url} onClick={() => run(() => cyberHttpHeaders(url))}
          className="inline-flex items-center gap-2 rounded-lg bg-blue-500/20 border border-blue-500/40 text-blue-200 px-3 py-1.5 text-[12px] hover:bg-blue-500/30 disabled:opacity-50">
          {busy ? <Loader2 size={13} className="animate-spin" /> : <Globe size={13} />} analyser
        </button>
      </div>
      {err && <ErrorBox message={err} />}
      {data && (
        <div className="space-y-2">
          {data.securityScore !== undefined && (
            <div className="flex items-center gap-3 rounded-lg bg-black/30 border border-white/10 p-3">
              <div className="text-[28px] font-bold text-white">{data.securityScore}</div>
              <div>
                <p className="text-[11px] text-white/60 uppercase">Score sécurité</p>
                <p className="text-[11px] text-white/45">
                  {(data.present || []).length} headers présents · {(data.missing || []).length} manquants
                </p>
              </div>
            </div>
          )}
          {(data.missing || []).length > 0 && (
            <div className="rounded-lg bg-rose-500/10 border border-rose-500/30 p-3">
              <p className="text-[11px] font-semibold text-rose-200 mb-1">Headers manquants</p>
              <div className="flex flex-wrap gap-1">
                {data.missing!.map((h) => (
                  <span key={h} className="rounded-md bg-rose-500/20 border border-rose-500/40 px-2 py-0.5 text-[10px] text-rose-200">{h}</span>
                ))}
              </div>
            </div>
          )}
          <JsonBox value={data.headers as unknown as Record<string, unknown>} />
        </div>
      )}
    </BaseTool>
  )
}

function ScanTool() {
  const [target, setTarget] = useState('127.0.0.1')
  const [portsStr, setPortsStr] = useState('22,80,443,3306,5432,6379,8080')
  const { busy, err, data, run } = useRunner<PortScanResult>()
  return (
    <BaseTool title="Port scan — local/RFC1918 uniquement">
      <div className="rounded-lg bg-rose-500/10 border border-rose-500/30 p-2 mb-3 text-[11px] text-rose-200 flex items-start gap-2">
        <AlertTriangle size={12} className="shrink-0 mt-0.5" />
        <p>Refuse automatiquement les adresses publiques côté backend Python. Cible uniquement <code>127.0.0.1</code>, ton LAN <code>192.168.x.x</code>, <code>10.x.x.x</code>, <code>172.16.x.x</code>.</p>
      </div>
      <div className="flex gap-2 mb-2">
        <input value={target} onChange={(e) => setTarget(e.target.value)} placeholder="127.0.0.1"
          className="flex-1 rounded-lg bg-black/40 border border-white/10 px-3 py-1.5 text-[12px] text-white/90 font-mono" />
        <button disabled={busy || !target}
          onClick={() => run(() => cyberPortScan(target, portsStr.split(',').map((p) => Number(p.trim())).filter(Boolean)))}
          className="inline-flex items-center gap-2 rounded-lg bg-blue-500/20 border border-blue-500/40 text-blue-200 px-3 py-1.5 text-[12px] hover:bg-blue-500/30 disabled:opacity-50">
          {busy ? <Loader2 size={13} className="animate-spin" /> : <Network size={13} />} scan
        </button>
      </div>
      <input value={portsStr} onChange={(e) => setPortsStr(e.target.value)} placeholder="22,80,443,..."
        className="w-full rounded-lg bg-black/40 border border-white/10 px-3 py-1.5 text-[12px] text-white/90 font-mono mb-3" />
      {err && <ErrorBox message={err} />}
      {data && (
        <div>
          {(data.openPorts || []).length > 0 ? (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2 mb-3">
              {data.openPorts!.map((p) => (
                <div key={p.port} className="rounded-lg bg-emerald-500/10 border border-emerald-500/30 px-3 py-2 text-[12px]">
                  <span className="text-emerald-200 font-mono">{p.port}</span>
                  {p.service && <span className="text-white/60 ml-2">{p.service}</span>}
                </div>
              ))}
            </div>
          ) : <p className="text-[12px] text-white/60 mb-3">Aucun port ouvert détecté.</p>}
          <JsonBox value={data as unknown as Record<string, unknown>} />
        </div>
      )}
    </BaseTool>
  )
}

function TraceTool() {
  const [target, setTarget] = useState('127.0.0.1')
  const { busy, err, data, run } = useRunner<{ hops: Array<{ hop: number; ip?: string; rttMs?: number }> }>()
  return (
    <BaseTool title="Traceroute UDP">
      <div className="flex gap-2 mb-3">
        <input value={target} onChange={(e) => setTarget(e.target.value)}
          className="flex-1 rounded-lg bg-black/40 border border-white/10 px-3 py-1.5 text-[12px] text-white/90 font-mono" />
        <button disabled={busy || !target} onClick={() => run(() => cyberTraceroute(target))}
          className="inline-flex items-center gap-2 rounded-lg bg-blue-500/20 border border-blue-500/40 text-blue-200 px-3 py-1.5 text-[12px] hover:bg-blue-500/30 disabled:opacity-50">
          {busy ? <Loader2 size={13} className="animate-spin" /> : <Radio size={13} />} trace
        </button>
      </div>
      {err && <ErrorBox message={err} />}
      {data && <JsonBox value={data as unknown as Record<string, unknown>} />}
    </BaseTool>
  )
}

function PcapTool() {
  const { busy, err, data, run } = useRunner<{ packets: Array<Record<string, unknown>> }>()
  return (
    <BaseTool title="PCAP démo pédagogique">
      <p className="text-[11px] text-white/60 mb-3">Génère un capture fictive décomposée par couches OSI.</p>
      <button disabled={busy} onClick={() => run(() => cyberPcapDemo())}
        className="inline-flex items-center gap-2 rounded-lg bg-blue-500/20 border border-blue-500/40 text-blue-200 px-3 py-1.5 text-[12px] hover:bg-blue-500/30 disabled:opacity-50 mb-3">
        {busy ? <Loader2 size={13} className="animate-spin" /> : <Radio size={13} />} générer pcap démo
      </button>
      {err && <ErrorBox message={err} />}
      {data && <JsonBox value={data as unknown as Record<string, unknown>} />}
    </BaseTool>
  )
}

function JsonBox({ value }: { value: Record<string, unknown> | null | undefined }) {
  if (!value) return null
  return (
    <pre className="rounded-lg bg-black/50 border border-white/5 p-3 text-[10px] text-white/80 font-mono overflow-auto max-h-96 whitespace-pre-wrap">
      {JSON.stringify(value, null, 2)}
    </pre>
  )
}

function ErrorBox({ message }: { message: string }) {
  return (
    <div className="rounded-lg bg-rose-500/10 border border-rose-500/30 p-2 text-[11px] text-rose-200 font-mono mb-2">
      {message}
    </div>
  )
}
