import { useMemo, useState } from 'react'
import { Clock, Radar, Search, Shield } from 'lucide-react'
import { parseIocs, summariseIocs, type Ioc } from '../../services/cyber/iocParser.ts'
import VoicePushToTalk from '../../components/VoicePushToTalk.tsx'

type Tab = 'cve' | 'mitre' | 'timeline' | 'nist' | 'osint' | 'ioc'

const TABS: Array<{ id: Tab; label: string }> = [
  { id: 'cve', label: 'CVE' },
  { id: 'mitre', label: 'MITRE ATT&CK' },
  { id: 'timeline', label: 'Timeline' },
  { id: 'nist', label: 'NIST CSF' },
  { id: 'osint', label: 'OSINT' },
  { id: 'ioc', label: 'IOC parser' },
]

export default function ThreatIntelLab() {
  const [tab, setTab] = useState<Tab>('mitre')
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
        <h2 className="text-white text-[15px] font-semibold mb-1">Threat Intelligence</h2>
        <p className="text-[12px] text-white/60">
          Comprendre les vulnérabilités connues (CVE), les tactiques adversaires (MITRE ATT&CK),
          et les frameworks défensifs (NIST CSF).
        </p>
      </div>
      <div className="flex gap-1 overflow-x-auto no-scrollbar border-b border-white/10 pb-2">
        {TABS.map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`whitespace-nowrap rounded-lg px-3 py-1.5 text-[12px] transition-colors ${
              tab === t.id
                ? 'bg-purple-500/20 text-purple-200 border border-purple-500/40'
                : 'text-white/55 hover:text-white/80 hover:bg-white/5'
            }`}>
            {t.label}
          </button>
        ))}
      </div>
      {tab === 'cve' && <CVEBrowser />}
      {tab === 'mitre' && <MITREMatrix />}
      {tab === 'timeline' && <SecurityTimeline />}
      {tab === 'nist' && <NISTFramework />}
      {tab === 'osint' && <OSINTToolkit />}
      {tab === 'ioc' && <IocParserPanel />}
    </div>
  )
}

function IocParserPanel() {
  const SAMPLE = `Phishing campaign detected 2026-05-15.
The attacker sent emails from billing@aurora-secure-update.tk with link http://185.220.101.42/login.php?u=admin
referring CVE-2024-1234 and exploiting T1566.001 (Spear-phishing attachment).
Payload SHA-256: a8e3f1c2b9d4...0000 (truncated, real: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855).
Other indicators:
- C2 domain: malicious-c2-server.xyz
- C2 IP: 45.155.205.233
- Backup C2: bad-actor.click
- BTC: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
- Internal: 192.168.1.50 (the infected workstation)
- MD5 of dropper: 9e107d9d372bb6826bd81d3542a419d6
- Contact: security-incident@company.com
Reported by analyst@victim.com`
  const [text, setText] = useState(SAMPLE)
  const iocs = useMemo(() => parseIocs(text), [text])
  const summary = useMemo(() => summariseIocs(iocs), [iocs])
  const kindColor: Record<string, string> = {
    ipv4: 'bg-rose-500/15 text-rose-200 border-rose-500/30',
    ipv6: 'bg-rose-500/15 text-rose-200 border-rose-500/30',
    domain: 'bg-amber-500/15 text-amber-200 border-amber-500/30',
    url: 'bg-orange-500/15 text-orange-200 border-orange-500/30',
    email: 'bg-sky-500/15 text-sky-200 border-sky-500/30',
    md5: 'bg-violet-500/15 text-violet-200 border-violet-500/30',
    sha1: 'bg-violet-500/15 text-violet-200 border-violet-500/30',
    sha256: 'bg-violet-500/15 text-violet-200 border-violet-500/30',
    cve: 'bg-pink-500/15 text-pink-200 border-pink-500/30',
    mitre: 'bg-fuchsia-500/15 text-fuchsia-200 border-fuchsia-500/30',
    btc: 'bg-yellow-500/15 text-yellow-200 border-yellow-500/30',
  }
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 space-y-3">
      <h3 className="text-[12px] font-semibold text-white/80 uppercase tracking-wider flex items-center gap-2">
        <Radar size={13} /> IOC parser · extrait indicateurs d'un rapport
      </h3>
      <p className="text-[11px] text-white/55">
        Colle un rapport d'incident, un email phishing, une note d'analyste — Aurora extrait
        IPs, domaines, URLs, hashes, CVE, ATT&CK, addresses BTC, tagge ce qui est suspect (TLD shady, HTTP cleartext, IP privée, etc.).
      </p>
      <textarea value={text} onChange={(e) => setText(e.target.value)} rows={8}
        className="w-full rounded-lg bg-black/40 border border-white/10 px-3 py-2 text-[11px] text-white/90 font-mono resize-none" />
      <div className="flex flex-wrap gap-1.5 text-[10px] font-mono">
        {Object.entries(summary).map(([k, n]) => (
          <span key={k} className={`rounded-md border px-2 py-0.5 ${kindColor[k] || 'bg-white/5 text-white/60 border-white/10'}`}>
            {k} <span className="opacity-70">×{n}</span>
          </span>
        ))}
      </div>
      <div className="space-y-1.5 max-h-96 overflow-auto">
        {iocs.map((ioc: Ioc, i: number) => (
          <div key={i} className={`rounded-md border px-2 py-1 text-[11px] font-mono ${kindColor[ioc.kind] || 'bg-white/5 text-white/60 border-white/10'}`}>
            <span className="text-[9px] uppercase tracking-wider opacity-70 mr-2">{ioc.kind}</span>
            <span className="break-all">{ioc.value}</span>
            {ioc.tags.length > 0 && (
              <span className="ml-2">
                {ioc.tags.map((t, j) => (
                  <span key={j} className="ml-1 rounded bg-black/30 border border-white/10 px-1.5 text-[9px] text-white/70">{t}</span>
                ))}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

interface CVEEntry {
  id: string; year: number; score: number; product: string; summary: string;
}

const CVE_SNAPSHOT: CVEEntry[] = [
  { id: 'CVE-2021-44228', year: 2021, score: 10.0, product: 'Apache Log4j', summary: 'Log4Shell — JNDI lookup permet RCE via chaîne loggée.' },
  { id: 'CVE-2014-0160', year: 2014, score: 7.5, product: 'OpenSSL', summary: 'Heartbleed — lecture de 64KB de mémoire serveur via TLS heartbeat.' },
  { id: 'CVE-2017-5638', year: 2017, score: 10.0, product: 'Apache Struts', summary: 'RCE via Content-Type OGNL — cause du breach Equifax.' },
  { id: 'CVE-2019-0708', year: 2019, score: 9.8, product: 'Microsoft RDP', summary: 'BlueKeep — RCE pre-auth dans RDP < Windows 8.' },
  { id: 'CVE-2020-1472', year: 2020, score: 10.0, product: 'Windows Netlogon', summary: 'Zerologon — élévation vers Domain Admin en quelques secondes.' },
  { id: 'CVE-2022-22965', year: 2022, score: 9.8, product: 'Spring Framework', summary: 'Spring4Shell — RCE via data binding.' },
  { id: 'CVE-2023-23397', year: 2023, score: 9.8, product: 'Microsoft Outlook', summary: 'Leak NTLM hash via rappel de calendrier forgé, zéro clic.' },
  { id: 'CVE-2023-4863', year: 2023, score: 8.8, product: 'libwebp (Chrome/Safari)', summary: 'Buffer overflow exploité en 0-day sur iOS/Chrome.' },
  { id: 'CVE-2024-3094', year: 2024, score: 10.0, product: 'XZ Utils', summary: 'Backdoor en supply-chain — quasi-merged avant détection.' },
  // Élargissement 2024-2025 : kernel, mobile, réseau, web, IA.
  { id: 'CVE-2024-21413', year: 2024, score: 9.8, product: 'Microsoft Outlook (MonikerLink)', summary: 'Bypass Protected View via hyperlien forgé, RCE et fuite NTLM.' },
  { id: 'CVE-2024-21762', year: 2024, score: 9.8, product: 'Fortinet FortiOS SSL-VPN', summary: 'Out-of-bounds write → RCE pre-auth, exploité in-the-wild.' },
  { id: 'CVE-2024-27198', year: 2024, score: 9.8, product: 'JetBrains TeamCity', summary: 'Auth bypass via path traversal — admin takeover en 1 requête.' },
  { id: 'CVE-2024-1086', year: 2024, score: 7.8, product: 'Linux kernel netfilter', summary: 'Use-after-free nf_tables → élévation locale stable.' },
  { id: 'CVE-2024-23222', year: 2024, score: 8.8, product: 'Apple WebKit', summary: 'Type confusion exploitée 0-day sur iOS/macOS — drive-by RCE.' },
  { id: 'CVE-2024-38063', year: 2024, score: 9.8, product: 'Windows TCP/IP IPv6', summary: 'Integer underflow dans le parser IPv6 → RCE distant sans clic.' },
  { id: 'CVE-2024-49113', year: 2024, score: 7.5, product: 'Windows LDAP (LDAPNightmare)', summary: 'Crash de domaine via réponse LDAP forgée — DoS contrôleurs AD.' },
  { id: 'CVE-2024-6387', year: 2024, score: 8.1, product: 'OpenSSH (regreSSHion)', summary: 'Race condition signal-handler → RCE pre-auth en root.' },
  { id: 'CVE-2024-47176', year: 2024, score: 8.6, product: 'CUPS (Linux print)', summary: 'Chaîne foomatic-rip + cups-browsed → RCE via IPP UDP/631.' },
  { id: 'CVE-2024-30088', year: 2024, score: 7.0, product: 'Windows Kernel (NtQueryInformation)', summary: 'TOCTOU vers SYSTEM, popularisé en exploit Pwn2Own 2024.' },
  { id: 'CVE-2025-0282', year: 2025, score: 9.0, product: 'Ivanti Connect Secure', summary: 'Stack overflow pre-auth → RCE, exploitée par groupes APT.' },
  { id: 'CVE-2025-22467', year: 2025, score: 9.8, product: 'Ivanti Connect Secure (chain)', summary: 'Buffer overflow + auth bypass → RCE chain in-the-wild.' },
  { id: 'CVE-2025-21178', year: 2025, score: 8.8, product: 'Microsoft Visual Studio', summary: 'RCE par ouverture de projet piégé.' },
  { id: 'CVE-2025-23120', year: 2025, score: 9.9, product: 'Veeam Backup & Replication', summary: 'Désérialisation insecure → RCE auth d\'un opérateur backup.' },
  { id: 'CVE-2025-1974', year: 2025, score: 9.8, product: 'NGINX Ingress Controller (IngressNightmare)', summary: 'Injection annotation → RCE cluster Kubernetes.' },
]

function CVEBrowser() {
  const [query, setQuery] = useState('')
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return CVE_SNAPSHOT
    return CVE_SNAPSHOT.filter((c) =>
      c.id.toLowerCase().includes(q) ||
      c.product.toLowerCase().includes(q) ||
      c.summary.toLowerCase().includes(q),
    )
  }, [query])

  const sevBg = (s: number) => s >= 9 ? 'bg-red-500/15 text-red-300 border-red-500/40'
    : s >= 7 ? 'bg-amber-500/15 text-amber-300 border-amber-500/40'
    : 'bg-sky-500/15 text-sky-300 border-sky-500/40'

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2">
        <Search size={14} className="text-white/40" />
        <input
          className="bg-transparent text-[12px] text-white/90 outline-none flex-1"
          placeholder="Filtre par ID, produit, mot-clef…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <VoicePushToTalk
          onTranscript={(t) => setQuery(t.trim())}
          label="Dicter le filtre CVE"
          size={26}
          variant="ghost"
        />
        <span className="text-[10px] text-white/40 font-mono">{filtered.length}/{CVE_SNAPSHOT.length}</span>
      </div>
      <ul className="space-y-2">
        {filtered.map((c) => (
          <li key={c.id} className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
            <div className="flex items-center gap-2 mb-1">
              <span className="font-mono text-[11px] text-white/80">{c.id}</span>
              <span className={`rounded-md px-1.5 py-0.5 text-[10px] border ${sevBg(c.score)}`}>CVSS {c.score.toFixed(1)}</span>
              <span className="ml-auto text-[10px] text-white/40">{c.year}</span>
            </div>
            <div className="text-[12px] text-white/90 mb-1">{c.product}</div>
            <div className="text-[11px] text-white/60">{c.summary}</div>
          </li>
        ))}
      </ul>
    </div>
  )
}

interface MitreTechnique {
  id: string
  name: string
  /** Description pédagogique courte (1-2 phrases concrètes) */
  detail: string
}

const MITRE_TACTICS: Array<{ id: string; name: string; techniques: MitreTechnique[] }> = [
  { id: 'TA0043', name: 'Reconnaissance', techniques: [
    { id: 'T1595', name: 'Active Scanning', detail: 'Scans réseau actifs (nmap, masscan) pour cartographier services exposés.' },
    { id: 'T1592', name: 'Gather Victim Host Info', detail: 'Collecte OS, version, banner via fingerprinting passif/actif.' },
    { id: 'T1589', name: 'Gather Victim Identity Info', detail: 'LinkedIn, breach databases, emails publics — pivot vers phishing ciblé.' },
    { id: 'T1596', name: 'Search Open Tech Databases', detail: 'Shodan, Censys, DNS history — recon sans toucher la cible.' },
  ]},
  { id: 'TA0042', name: 'Resource Development', techniques: [
    { id: 'T1583', name: 'Acquire Infrastructure', detail: 'Achat de VPS, domaines typosquats, certificats Let\'s Encrypt pour staging.' },
    { id: 'T1587', name: 'Develop Capabilities', detail: 'Compilation de malware sur-mesure (cobalt strike beacons, loaders).' },
    { id: 'T1585', name: 'Establish Accounts', detail: 'Création de comptes mules (email, GitHub, AWS) pour exfil + C2.' },
  ]},
  { id: 'TA0001', name: 'Initial Access', techniques: [
    { id: 'T1566.001', name: 'Spearphishing Attachment', detail: 'PJ Office/PDF avec macro VBA ou exploit — vecteur #1 en entreprise.' },
    { id: 'T1566.002', name: 'Spearphishing Link', detail: 'Lien vers credential phishing kit (Evilginx, Modlishka) qui MITM le 2FA.' },
    { id: 'T1190', name: 'Exploit Public-Facing App', detail: 'CVE non patchée sur web/VPN/Exchange (cf. Log4Shell, ProxyShell).' },
    { id: 'T1195.002', name: 'Supply Chain Compromise', detail: 'Injection dans dépendance (XZ Utils 2024, npm event-stream 2018).' },
    { id: 'T1078', name: 'Valid Accounts', detail: 'Credentials volés/achetés sur dark markets — pas d\'exploit nécessaire.' },
  ]},
  { id: 'TA0002', name: 'Execution', techniques: [
    { id: 'T1059.001', name: 'PowerShell', detail: 'Encoded one-liner pour bypass AMSI + télécharger payload en mémoire.' },
    { id: 'T1059.003', name: 'Windows Command Shell', detail: 'cmd.exe pour livrer batch obfusqué — détection AV plus faible.' },
    { id: 'T1059.005', name: 'Visual Basic (VBA)', detail: 'Macro Office déclenchée à l\'ouverture, drop dropper via WMI.' },
    { id: 'T1053.005', name: 'Scheduled Task', detail: 'schtasks /create pour exec récurrent — survit au reboot, faible signal.' },
    { id: 'T1204', name: 'User Execution', detail: 'L\'utilisateur clique sur l\'attachment / exe — vecteur humain.' },
  ]},
  { id: 'TA0003', name: 'Persistence', techniques: [
    { id: 'T1547.001', name: 'Registry Run Keys', detail: 'HKCU\\...\\Run — exécution à chaque login, persistance classique.' },
    { id: 'T1543.003', name: 'Windows Service', detail: 'Création d\'un service NT avec un binaire malicieux, démarrage auto.' },
    { id: 'T1546.003', name: 'WMI Event Subscription', detail: 'Filter+Consumer WMI — fileless, survit à un format léger.' },
    { id: 'T1098', name: 'Account Manipulation', detail: 'Ajout d\'utilisateur dans Domain Admins / sudoers, persistance d\'accès.' },
  ]},
  { id: 'TA0004', name: 'Priv. Escalation', techniques: [
    { id: 'T1068', name: 'Exploitation for Priv Esc', detail: 'Exploit kernel local (PrintNightmare, Dirty Pipe, regreSSHion).' },
    { id: 'T1548.002', name: 'Bypass UAC', detail: 'Fodhelper, eventvwr — DLL hijack via process auto-élévé Microsoft.' },
    { id: 'T1134', name: 'Token Manipulation', detail: 'Duplication d\'access token d\'un process SYSTEM via OpenProcessToken.' },
    { id: 'T1574.001', name: 'DLL Search Order Hijacking', detail: 'DLL malicieuse dans répertoire avant la légitime — exécution privilégiée.' },
  ]},
  { id: 'TA0005', name: 'Defense Evasion', techniques: [
    { id: 'T1027', name: 'Obfuscated Files/Info', detail: 'Packing (UPX, Themida), strings chiffrées, control-flow flattening.' },
    { id: 'T1014', name: 'Rootkit', detail: 'Hook syscalls kernel pour cacher process/files/connexions.' },
    { id: 'T1562.001', name: 'Disable Security Tools', detail: 'Stop services Defender/CrowdStrike, kill EDR processes.' },
    { id: 'T1070.004', name: 'File Deletion', detail: 'Wipe logs (wevtutil cl) + secure delete artefacts.' },
    { id: 'T1218.011', name: 'Rundll32 Execution', detail: 'Living-off-the-land : rundll32 charge DLL via export — passe AV.' },
  ]},
  { id: 'TA0006', name: 'Credential Access', techniques: [
    { id: 'T1003.001', name: 'LSASS Memory', detail: 'mimikatz / procdump → dump LSASS → extract Kerberos tickets + NTLM.' },
    { id: 'T1056.001', name: 'Keylogging', detail: 'SetWindowsHookEx WH_KEYBOARD_LL ou keyboard driver.' },
    { id: 'T1558.003', name: 'Kerberoasting', detail: 'Request SPN tickets RC4 → crack offline → mot de passe service.' },
    { id: 'T1110.003', name: 'Password Spraying', detail: 'Un mdp commun testé sur N comptes — évite verrouillage compte.' },
    { id: 'T1555', name: 'Credentials from Password Stores', detail: 'Lecture Chrome LocalState, DPAPI, gnome-keyring — credentials clair après master.' },
  ]},
  { id: 'TA0007', name: 'Discovery', techniques: [
    { id: 'T1087', name: 'Account Discovery', detail: 'net user, Get-ADUser — enum comptes locaux/AD.' },
    { id: 'T1018', name: 'Remote System Discovery', detail: 'nbtscan, ARP scan, net view — cartographie LAN interne.' },
    { id: 'T1057', name: 'Process Discovery', detail: 'tasklist, ps aux — repère EDR + outils de sécurité avant attaque.' },
    { id: 'T1482', name: 'Domain Trust Discovery', detail: 'nltest, BloodHound — cartographie relations de confiance AD.' },
  ]},
  { id: 'TA0008', name: 'Lateral Movement', techniques: [
    { id: 'T1021.001', name: 'RDP', detail: 'Connexion RDP avec credentials volés — discret si VPN déjà compromis.' },
    { id: 'T1021.002', name: 'SMB/Admin Shares', detail: 'PsExec, smbexec — exec sur \\\\target\\ADMIN$.' },
    { id: 'T1550.002', name: 'Pass-the-Hash', detail: 'Hash NTLM utilisé directement (sans crack) avec mimikatz sekurlsa::pth.' },
    { id: 'T1210', name: 'Exploit Remote Services', detail: 'EternalBlue, BlueKeep, ZeroLogon — RCE sans credentials.' },
  ]},
  { id: 'TA0009', name: 'Collection', techniques: [
    { id: 'T1113', name: 'Screen Capture', detail: 'BitBlt + JPG → exfil — utile pour staging financier/RH.' },
    { id: 'T1056.002', name: 'GUI Input Capture', detail: 'Fake credential dialog (askpass) — utilisateur ressaisit son mdp.' },
    { id: 'T1114', name: 'Email Collection', detail: 'Lecture .pst, IMAP, Graph API — chasse aux secrets dans inbox.' },
    { id: 'T1115', name: 'Clipboard Data', detail: 'Snooping clipboard pour saisir crypto wallets ou mdp collés.' },
  ]},
  { id: 'TA0011', name: 'Command & Control', techniques: [
    { id: 'T1071.001', name: 'Web Protocols (HTTPS)', detail: 'Beacon en HTTPS vers domaine fronted (CloudFront, Fastly) — blend traffic.' },
    { id: 'T1071.004', name: 'DNS', detail: 'Exfil + commandes encodées dans queries DNS TXT — bypass proxy web.' },
    { id: 'T1573.002', name: 'Asymmetric Crypto', detail: 'C2 chiffré AES+RSA — empêche déchiffrement MITM par défense.' },
    { id: 'T1090.003', name: 'Multi-hop Proxy', detail: 'Tor / VPN chain — anonymisation de l\'opérateur.' },
  ]},
  { id: 'TA0010', name: 'Exfiltration', techniques: [
    { id: 'T1041', name: 'Exfil over C2 Channel', detail: 'Données envoyées dans mêmes beacons HTTPS — pas de canal séparé.' },
    { id: 'T1567.002', name: 'Exfil to Cloud Storage', detail: 'Upload vers Dropbox/MEGA/S3 — passe pour traffic légitime.' },
    { id: 'T1020', name: 'Automated Exfiltration', detail: 'Script qui repère docs sensibles + push périodique.' },
    { id: 'T1029', name: 'Scheduled Transfer', detail: 'Exfil aux heures de pointe (jour ouvré) — noyé dans traffic métier.' },
  ]},
  { id: 'TA0040', name: 'Impact', techniques: [
    { id: 'T1486', name: 'Data Encrypted for Impact', detail: 'Ransomware (LockBit, BlackCat) — AES par fichier + clé RSA.' },
    { id: 'T1485', name: 'Data Destruction', detail: 'Wiper (NotPetya, HermeticWiper) — destruction irréversible.' },
    { id: 'T1490', name: 'Inhibit System Recovery', detail: 'vssadmin delete shadows, wbadmin delete — empêche restore.' },
    { id: 'T1498', name: 'Network DoS', detail: 'Flood SYN/UDP/HTTP — saturation bande passante ou ressources serveur.' },
    { id: 'T1491.002', name: 'External Defacement', detail: 'Modification site public — souvent hacktivisme + signal de présence.' },
  ]},
]

function MITREMatrix() {
  const [openTech, setOpenTech] = useState<string | null>(null)
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
      {MITRE_TACTICS.map((t) => (
        <div key={t.id} className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
          <div className="flex items-center gap-2 mb-2">
            <Radar size={12} className="text-purple-300" />
            <span className="text-[11px] font-mono text-white/60">{t.id}</span>
            <span className="text-[12px] font-semibold text-white/95">{t.name}</span>
            <span className="ml-auto text-[10px] text-white/35">{t.techniques.length} tech.</span>
          </div>
          <ul className="space-y-1">
            {t.techniques.map((tech) => {
              const open = openTech === tech.id
              return (
                <li key={tech.id}>
                  <button
                    type="button"
                    onClick={() => setOpenTech(open ? null : tech.id)}
                    className={`w-full text-left rounded border px-2 py-1 transition-colors ${
                      open
                        ? 'border-purple-400/50 bg-purple-500/10 text-white'
                        : 'border-white/10 bg-white/[0.03] text-white/70 hover:bg-white/[0.06]'
                    }`}
                  >
                    <div className="flex items-baseline gap-2">
                      <span className="font-mono text-[10px] text-purple-300/80">{tech.id}</span>
                      <span className="text-[11px] font-medium">{tech.name}</span>
                    </div>
                    {open && (
                      <p className="mt-1 text-[10.5px] leading-snug text-white/65">{tech.detail}</p>
                    )}
                  </button>
                </li>
              )
            })}
          </ul>
        </div>
      ))}
    </div>
  )
}

const TIMELINE: Array<{ year: string; title: string; detail: string }> = [
  { year: '1988', title: 'Morris Worm', detail: 'Premier ver Internet — paralyse ~10% du net naissant.' },
  { year: '2000', title: 'ILOVEYOU', detail: 'Macro VBScript via email — dégâts estimés 10 G$.' },
  { year: '2010', title: 'Stuxnet', detail: 'Ver SCADA ciblant centrifugeuses iraniennes — 4 0-days chaînés.' },
  { year: '2013', title: 'Snowden / NSA', detail: 'Révélation PRISM, XKeyscore — crypto grand public adoptée.' },
  { year: '2014', title: 'Heartbleed', detail: 'Vulnérabilité OpenSSL, 500K+ serveurs exposés.' },
  { year: '2017', title: 'WannaCry / NotPetya', detail: 'Ransomware via EternalBlue (leak ShadowBrokers).' },
  { year: '2020', title: 'SolarWinds', detail: 'Supply-chain via build pipeline Orion — 18k entreprises touchées.' },
  { year: '2021', title: 'Log4Shell', detail: 'JNDI lookup dans un logger ultra-répandu — notation "10/10".' },
  { year: '2024', title: 'XZ Utils backdoor', detail: 'Backdoor quasi-merged upstream — détectée par un ingénieur Microsoft.' },
]

function SecurityTimeline() {
  return (
    <ol className="space-y-2">
      {TIMELINE.map((t, i) => (
        <li key={i} className="rounded-lg border border-white/10 bg-white/[0.03] p-3 flex gap-3">
          <div className="flex items-center gap-1 text-purple-300 font-mono text-[11px] shrink-0">
            <Clock size={11} /> {t.year}
          </div>
          <div>
            <div className="text-[12px] font-semibold text-white/95">{t.title}</div>
            <div className="text-[11px] text-white/60">{t.detail}</div>
          </div>
        </li>
      ))}
    </ol>
  )
}

const NIST_CSF: Array<{ fn: string; color: string; desc: string; activities: string[] }> = [
  { fn: 'Identify',    color: 'from-sky-500/20 border-sky-500/40',     desc: 'Inventaire actifs, gouvernance, risques.', activities: ['Asset Management', 'Business Environment', 'Governance', 'Risk Assessment'] },
  { fn: 'Protect',     color: 'from-emerald-500/20 border-emerald-500/40', desc: 'Contrôles d\'accès, formation, maintenance.', activities: ['Access Control', 'Awareness & Training', 'Data Security', 'Maintenance'] },
  { fn: 'Detect',      color: 'from-amber-500/20 border-amber-500/40', desc: 'Surveillance, détection d\'anomalies.', activities: ['Anomalies', 'Monitoring', 'Detection Processes'] },
  { fn: 'Respond',     color: 'from-orange-500/20 border-orange-500/40', desc: 'Plan de réponse, communication, analyse.', activities: ['Response Planning', 'Communications', 'Analysis', 'Mitigation'] },
  { fn: 'Recover',     color: 'from-purple-500/20 border-purple-500/40', desc: 'Continuité, améliorations post-incident.', activities: ['Recovery Planning', 'Improvements', 'Communications'] },
]

function NISTFramework() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-5 gap-2">
      {NIST_CSF.map((f) => (
        <div key={f.fn} className={`rounded-lg border bg-gradient-to-b ${f.color} to-transparent p-3`}>
          <div className="flex items-center gap-2 mb-2">
            <Shield size={13} className="text-white/85" />
            <span className="text-[13px] font-semibold text-white">{f.fn}</span>
          </div>
          <div className="text-[11px] text-white/70 mb-2">{f.desc}</div>
          <ul className="space-y-1">
            {f.activities.map((a) => (
              <li key={a} className="text-[10px] text-white/65 font-mono">· {a}</li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  )
}

const OSINT_TOOLS: Array<{ name: string; url: string; purpose: string }> = [
  { name: 'Shodan',         url: 'https://www.shodan.io',        purpose: 'Moteur de recherche d\'appareils exposés sur Internet.' },
  { name: 'Censys',         url: 'https://search.censys.io',     purpose: 'Cartographie TLS/certificats + scan global.' },
  { name: 'VirusTotal',     url: 'https://www.virustotal.com',   purpose: 'Analyse multi-moteur de fichiers/URLs/hash.' },
  { name: 'urlscan.io',     url: 'https://urlscan.io',           purpose: 'Sandbox URL — screenshot + DOM + network.' },
  { name: 'haveibeenpwned', url: 'https://haveibeenpwned.com',   purpose: 'Vérifier si un email/mdp a fuité.' },
  { name: 'MITRE ATT&CK',   url: 'https://attack.mitre.org',     purpose: 'Référentiel des tactiques/techniques adverses.' },
  { name: 'NVD',            url: 'https://nvd.nist.gov',         purpose: 'National Vulnerability Database (CVE + scores).' },
  { name: 'exploit-db',     url: 'https://www.exploit-db.com',   purpose: 'Base d\'exploits publics (Offensive Security).' },
]

function OSINTToolkit() {
  return (
    <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2">
      {OSINT_TOOLS.map((t) => (
        <li key={t.name} className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[12px] font-semibold text-white/95">{t.name}</span>
            <a href={t.url} target="_blank" rel="noopener noreferrer"
              className="text-[10px] font-mono text-purple-300 hover:text-purple-200">↗ ouvrir</a>
          </div>
          <div className="text-[11px] text-white/65">{t.purpose}</div>
        </li>
      ))}
    </ul>
  )
}
