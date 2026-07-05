// ---------------------------------------------------------------------------
// CoworkSettingsDialog — full settings panel inside the Cowork overlay.
//
// Three tabs:
//   - Prompts      : edit text + voice system prompts
//   - Permissions  : trust mode, shell allowlist relaxation, external paths
//   - Connecteurs  : configure GitHub / Vercel / Canva / Notion / Linear /
//                    Slack / OpenAI / Anthropic API keys, with live test.
//
// State is stored via coworkSettings.{loadSettings,saveSettings}, persisted
// to localStorage.
// ---------------------------------------------------------------------------

import { useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  Check,
  ChevronDown,
  Download,
  ExternalLink,
  Eye,
  EyeOff,
  Globe,
  KeyRound,
  Loader2,
  MessageSquare,
  Mic,
  Plug,
  Puzzle,
  ShieldAlert,
  ShieldCheck,
  Sliders,
  Star,
  X,
  XCircle,
} from 'lucide-react'
import {
  detectCurrentBrowser,
  getInstallInstructions,
  scanInstalledBrowsers,
  type BrowserId,
  type BrowserInfo,
} from '../services/coworkBrowserDetect'
import { getBridgeUrl } from '../utils/runtime'
import { useCoworkStore } from '../stores/coworkStore'
import {
  loadSettings,
  saveSettings,
  type ConnectorId,
  type ConnectorConfig,
  type CoworkSettings,
  DEFAULT_TEXT_PROMPT,
  DEFAULT_VOICE_PROMPT,
} from '../services/coworkSettings'
import { CONNECTORS, testConnector } from '../services/coworkConnectors'

type Tab = 'prompts' | 'permissions' | 'connecteurs' | 'extension'

export default function CoworkSettingsDialog() {
  const open = useCoworkStore((s) => s.settingsOpen)
  const focusConnector = useCoworkStore((s) => s.settingsFocusConnector)
  const close = useCoworkStore((s) => s.closeSettings)
  return (
    <AnimatePresence>
      {open && <Dialog onClose={close} focusConnector={focusConnector} />}
    </AnimatePresence>
  )
}

function Dialog({ onClose, focusConnector }: { onClose: () => void; focusConnector: string | null }) {
  // v82m1 — when the parent passes a focus connector id (set by the
  // CoworkOverlay pill click → opt-in dialog flow), default the active tab
  // to 'connecteurs' and pass the focus down so the matching row can
  // scroll into view.
  const [tab, setTab] = useState<Tab>(focusConnector ? 'connecteurs' : 'prompts')
  const [settings, setSettings] = useState<CoworkSettings>(() => loadSettings())

  // Persist changes immediately so the planner picks them up on the next run.
  useEffect(() => { saveSettings(settings) }, [settings])

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[250] flex items-center justify-center bg-black/70 backdrop-blur-sm"
    >
      <motion.div
        initial={{ y: 20, opacity: 0, scale: 0.97 }}
        animate={{ y: 0, opacity: 1, scale: 1 }}
        exit={{ y: 12, opacity: 0, scale: 0.97 }}
        transition={{ duration: 0.2, ease: 'easeOut' }}
        className="w-full max-w-3xl max-h-[88vh] overflow-hidden rounded-3xl border border-white/10 bg-[#0b111b] text-white shadow-[0_30px_90px_rgba(0,0,0,0.5)] flex flex-col"
      >
        <header className="flex items-center justify-between px-6 py-4 border-b border-white/8">
          <div className="flex items-center gap-3">
            <Sliders size={16} className="text-violet-300" />
            <div>
              <p className="text-[10px] uppercase tracking-[0.2em] text-white/40">Cowork</p>
              <h2 className="text-lg font-semibold tracking-tight">Parametres</h2>
            </div>
          </div>
          <button
            onClick={onClose}
            className="flex h-9 w-9 items-center justify-center rounded-full border border-white/10 bg-white/5 text-white/60 hover:bg-white/10 hover:text-white transition-colors"
          >
            <X size={14} />
          </button>
        </header>

        <nav className="flex border-b border-white/8 px-4 gap-1">
          <TabButton active={tab === 'prompts'}     icon={MessageSquare} label="Prompts"     onClick={() => setTab('prompts')} />
          <TabButton active={tab === 'permissions'} icon={ShieldCheck}    label="Permissions" onClick={() => setTab('permissions')} />
          <TabButton active={tab === 'connecteurs'} icon={Plug}            label="Connecteurs" onClick={() => setTab('connecteurs')} />
          <TabButton active={tab === 'extension'}   icon={Puzzle}          label="Aurora-Connect" onClick={() => setTab('extension')} />
        </nav>

        <div className="flex-1 overflow-y-auto px-6 py-5">
          {tab === 'prompts' && <PromptsTab settings={settings} setSettings={setSettings} />}
          {tab === 'permissions' && <PermissionsTab settings={settings} setSettings={setSettings} />}
          {tab === 'connecteurs' && <ConnectorsTab settings={settings} setSettings={setSettings} focusConnector={focusConnector} />}
          {tab === 'extension' && <ExtensionTab />}
        </div>
      </motion.div>
    </motion.div>
  )
}

function TabButton({ active, icon: Icon, label, onClick }: { active: boolean; icon: typeof MessageSquare; label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-4 py-2.5 text-[12px] font-medium border-b-2 transition-colors ${
        active
          ? 'border-violet-400 text-white'
          : 'border-transparent text-white/55 hover:text-white/85'
      }`}
    >
      <Icon size={13} />
      {label}
    </button>
  )
}

// ---------------------------------------------------------------------------
// Prompts
// ---------------------------------------------------------------------------

function PromptsTab({ settings, setSettings }: { settings: CoworkSettings; setSettings: (s: CoworkSettings) => void }) {
  return (
    <div className="space-y-5">
      <PromptEditor
        label="Prompt systeme — reponses texte"
        help="Injecte au debut du system prompt du planner pour les sessions Cowork classiques."
        value={settings.systemPromptText}
        onChange={(v) => setSettings({ ...settings, systemPromptText: v })}
        defaultValue={DEFAULT_TEXT_PROMPT}
        icon={MessageSquare}
      />
      <PromptEditor
        label="Prompt systeme — reponses vocales"
        help="Utilise quand Cowork est lance avec voiceMode (dictee + lecture). Privilegie 1-2 phrases courtes, sans markdown."
        value={settings.systemPromptVoice}
        onChange={(v) => setSettings({ ...settings, systemPromptVoice: v })}
        defaultValue={DEFAULT_VOICE_PROMPT}
        icon={Mic}
      />

      <div>
        <p className="text-[11px] font-semibold text-white/65 mb-2 flex items-center gap-2">
          <Sliders size={11} />
          Contextes par module
        </p>
        <p className="text-[10px] text-white/45 mb-3">
          Ajoute aux prompts ci-dessus quand Cowork est ouvert depuis ce module.
        </p>
        {(['conversation', 'code', 'cyber'] as const).map((mod) => (
          <div key={mod} className="mb-3">
            <p className="text-[10px] uppercase tracking-[0.18em] text-white/40 mb-1">{mod}</p>
            <textarea
              rows={2}
              value={settings.contextByModule[mod] ?? ''}
              onChange={(e) => setSettings({
                ...settings,
                contextByModule: { ...settings.contextByModule, [mod]: e.target.value },
              })}
              className="w-full rounded-xl border border-white/10 bg-black/30 p-3 text-[12px] text-white outline-none focus:border-violet-400/40"
            />
          </div>
        ))}
      </div>
    </div>
  )
}

function PromptEditor({
  label, help, value, onChange, defaultValue, icon: Icon,
}: {
  label: string; help: string; value: string; onChange: (v: string) => void; defaultValue: string; icon: typeof MessageSquare
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <p className="text-[11px] font-semibold text-white/65 flex items-center gap-2">
          <Icon size={11} />
          {label}
        </p>
        <button
          onClick={() => onChange(defaultValue)}
          className="text-[10px] text-white/45 hover:text-white/70"
          type="button"
        >
          Reset au defaut
        </button>
      </div>
      <p className="text-[10px] text-white/40 mb-2">{help}</p>
      <textarea
        rows={3}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-xl border border-white/10 bg-black/30 p-3 text-[12px] text-white outline-none focus:border-violet-400/40 leading-relaxed"
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Permissions
// ---------------------------------------------------------------------------

function PermissionsTab({ settings, setSettings }: { settings: CoworkSettings; setSettings: (s: CoworkSettings) => void }) {
  return (
    <div className="space-y-3">
      <Toggle
        label="Mode confiance (trust mode)"
        help="Quand actif, saute les confirmations preventives. Garde ce mode coupe pour laisser Aurora agir dans le workspace tout en demandant avant les actions risquees."
        value={settings.trustMode}
        onChange={(v) => setSettings({ ...settings, trustMode: v })}
      />
      <Toggle
        label="Autoriser les commandes shell hors allowlist"
        help="Autorise Aurora a proposer des commandes inconnues ; elles restent soumises a confirmation si le mode confiance est coupe."
        value={settings.allowShellOutsideAllowlist}
        onChange={(v) => setSettings({ ...settings, allowShellOutsideAllowlist: v })}
      />
      <Toggle
        label="Autoriser l acces aux fichiers hors workspace"
        help="Permet les chemins hors projet. Les lectures/ecritures hors workspace restent confirmees en mode preventif."
        value={settings.allowExternalPaths}
        onChange={(v) => setSettings({ ...settings, allowExternalPaths: v })}
      />

      <div className="mt-5 rounded-2xl border border-red-500/30 bg-red-500/8 p-3">
        <Toggle
          label="DANGER mode confirme"
          help="Transforme les commandes systeme catastrophiques en demandes de confirmation au lieu de les bloquer. Elles ne s'executent pas sans ton accord."
          value={settings.dangerMode}
          onChange={(v) => setSettings({ ...settings, dangerMode: v })}
        />
      </div>

      <div className="mt-3 rounded-2xl border border-orange-500/40 bg-orange-500/10 p-3">
        <Toggle
          label="Deverrouiller completement (zero garde fou)"
          help="Une fois accepte : Aurora a AUCUNE restriction. Peut lire/ecrire PARTOUT, lancer n importe quelle commande, detruire le systeme. SEULEMENT si tu comprends les risques et acceptes la responsabilite."
          value={settings.fullyUnlocked}
          onChange={(v) => setSettings({ ...settings, fullyUnlocked: v })}
        />
        <p className="text-[10px] text-orange-200 leading-relaxed mt-2">
          <strong>Tu acceptes TOUS les risques :</strong> Aurora n'aura aucune confirmation a valider, aucun blocage logiciel. Seules les limites OS (permissions, sandbox) restent.
        </p>
      </div>

      <div className="mt-3 rounded-xl border border-red-500/35 bg-red-500/8 p-3">
        <p className="text-[11px] text-red-200 leading-relaxed">
          <strong>Mode preventif par defaut :</strong> Aurora peut agir dans le workspace sans te couper, mais demande avant les operations hors perimetre, sensibles ou destructrices. Le deverrouillage complet reste disponible seulement si tu l'actives explicitement.
        </p>
      </div>
    </div>
  )
}

function Toggle({ label, help, value, onChange }: { label: string; help: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!value)}
      className="w-full flex items-start gap-4 p-3 rounded-xl border border-white/8 bg-white/[0.02] hover:bg-white/[0.05] transition-colors text-left"
    >
      <div className={`mt-0.5 h-5 w-9 rounded-full transition-colors flex items-center ${value ? 'bg-violet-500 justify-end' : 'bg-white/15 justify-start'}`}>
        <span className="h-4 w-4 rounded-full bg-white mx-0.5 transition-transform" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-[12px] font-medium text-white">{label}</p>
        <p className="text-[10px] text-white/55 mt-0.5 leading-snug">{help}</p>
      </div>
    </button>
  )
}

// ---------------------------------------------------------------------------
// Connecteurs
// ---------------------------------------------------------------------------

// v82m1 — pure helper : resolve the focus connector id (string from the
// store, free-form / case-insensitive) to a real ConnectorId from the
// CONNECTORS registry. Returns null when nothing matches so the row
// rendering doesn't accidentally highlight a wrong entry. Exported so
// __tests__/coworkSettingsFocus.test.ts can pin the resolution contract.
export function resolveFocusConnector(raw: string | null | undefined): ConnectorId | null {
  if (!raw || typeof raw !== 'string') return null
  const needle = raw.trim().toLowerCase()
  if (!needle) return null
  const ids = Object.keys(CONNECTORS) as ConnectorId[]
  // 1. exact id match (case-insensitive). Most common path : the planner
  //    emits "reddit"/"github"/etc. lowercase.
  for (const id of ids) {
    if (id.toLowerCase() === needle) return id
  }
  // 2. label match (case-insensitive). Lets callers pass "Reddit", "GitHub",
  //    "Hacker News" etc. — useful if the click handler reuses the pill
  //    label rather than parsing the connector id.
  for (const id of ids) {
    if (CONNECTORS[id]?.label?.toLowerCase() === needle) return id
  }
  return null
}

function ConnectorsTab({ settings, setSettings, focusConnector }: { settings: CoworkSettings; setSettings: (s: CoworkSettings) => void; focusConnector: string | null }) {
  // v82m1 — resolve the free-form focus id (from the store) to a real
  // ConnectorId. Used to scroll the matching row into view + emphasise it
  // with a violet ring on first paint.
  const focused = useMemo(() => resolveFocusConnector(focusConnector), [focusConnector])
  return (
    <div className="space-y-3">
      <p className="text-[11px] text-white/55 leading-relaxed mb-2">
        Configure les API keys des services externes que tu veux qu Aurora utilise via l action <code className="text-violet-300">connector</code>. Les cles restent dans ton localStorage; elles ne quittent ta machine que pour les appels HTTP que tu autorises.
      </p>
      {(Object.keys(CONNECTORS) as ConnectorId[]).map((id) => (
        <ConnectorRow
          key={id}
          id={id}
          config={settings.connectors[id]}
          focused={focused === id}
          onChange={(cfg) => setSettings({
            ...settings,
            connectors: { ...settings.connectors, [id]: cfg },
          })}
        />
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Aurora-Connect (browser extension) tab
// ---------------------------------------------------------------------------

type LiveTab = { id: number; url: string; title: string; active?: boolean }

function ExtensionTab() {
  const current = useMemo(() => detectCurrentBrowser(), [])
  const [installed, setInstalled] = useState<BrowserInfo[]>([])
  const [scanning, setScanning] = useState(true)
  const [selected, setSelected] = useState<BrowserId>(current.id)
  const [liveTabs, setLiveTabs] = useState<{ extId: string | null; tabs: LiveTab[]; loading: boolean; error: string | null }>({
    extId: null, tabs: [], loading: false, error: null,
  })

  useEffect(() => {
    let cancelled = false
    scanInstalledBrowsers()
      .then((b) => { if (!cancelled) { setInstalled(b); setScanning(false) } })
      .catch(() => { if (!cancelled) setScanning(false) })
    return () => { cancelled = true }
  }, [])

  // Live tab preview — poll the bridge every 5s for the connected extension
  // and request a list_tabs command. Shows the user what Aurora can see
  // through the extension RIGHT NOW.
  useEffect(() => {
    let cancelled = false
    const poll = async () => {
      try {
        const root = getBridgeUrl()
        const listResp = await fetch(`${root}/api/cowork/extension/list`, { signal: AbortSignal.timeout(4000) })
        if (!listResp.ok) {
          if (!cancelled) setLiveTabs((s) => ({ ...s, error: `bridge ${listResp.status}`, loading: false }))
          return
        }
        const listData = await listResp.json() as { extensions?: Array<{ extId: string }> }
        const extId = listData.extensions?.[0]?.extId
        if (!extId) {
          if (!cancelled) setLiveTabs({ extId: null, tabs: [], loading: false, error: 'aucune extension connectee' })
          return
        }
        if (!cancelled) setLiveTabs((s) => ({ ...s, extId, loading: true, error: null }))
        const dispatchResp = await fetch(`${root}/api/cowork/extension/dispatch`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ extId, kind: 'list_tabs', payload: {} }),
        })
        const dispatchData = await dispatchResp.json() as { ok: boolean; commandId?: string }
        if (!dispatchData.ok || !dispatchData.commandId) return
        const awaitResp = await fetch(`${root}/api/cowork/extension/await-result?commandId=${dispatchData.commandId}&wait=4500`, { signal: AbortSignal.timeout(6000) })
        if (!awaitResp.ok) return
        const awaitData = await awaitResp.json() as { ok: boolean; result?: { ok: boolean; data?: LiveTab[] } }
        if (cancelled) return
        if (awaitData.ok && awaitData.result?.ok && Array.isArray(awaitData.result.data)) {
          setLiveTabs({ extId, tabs: awaitData.result.data, loading: false, error: null })
        } else {
          setLiveTabs((s) => ({ ...s, loading: false }))
        }
      } catch {
        if (!cancelled) setLiveTabs((s) => ({ ...s, loading: false, error: 'bridge offline' }))
      }
    }
    poll()
    const id = window.setInterval(poll, 5000)
    return () => { cancelled = true; window.clearInterval(id) }
  }, [])

  // Build the list to render: current browser first (recommended), then
  // others detected as installed on PC, then the rest of the catalog.
  const allBrowsers: BrowserId[] = useMemo(() => {
    const seen = new Set<BrowserId>()
    const ordered: BrowserId[] = []
    const push = (id: BrowserId) => { if (id && !seen.has(id)) { seen.add(id); ordered.push(id) } }
    push(current.id)
    for (const b of installed) push(b.id)
    for (const id of ['chrome', 'edge', 'firefox', 'brave', 'opera', 'vivaldi', 'arc', 'safari', 'chromium'] as BrowserId[]) push(id)
    return ordered.filter((id) => id !== 'unknown')
  }, [current.id, installed])

  const inst = getInstallInstructions(selected)
  const downloadUrl = `${getBridgeUrl()}/api/cowork/extension/download`

  return (
    <div className="space-y-4">
      {/* Live preview of tabs the extension currently sees */}
      <div className={`rounded-2xl border p-4 ${liveTabs.extId ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-white/10 bg-white/[0.02]'}`}>
        <div className="flex items-center gap-2 mb-2">
          <span className={`relative flex h-2 w-2`}>
            <span className={`absolute inline-flex h-full w-full rounded-full ${liveTabs.extId ? 'bg-emerald-400 animate-ping' : 'bg-white/20'}`} style={{ opacity: liveTabs.extId ? 0.4 : 0 }} />
            <span className={`relative inline-flex h-2 w-2 rounded-full ${liveTabs.extId ? 'bg-emerald-400' : 'bg-white/30'}`} />
          </span>
          <p className="text-[11px] uppercase tracking-[0.18em] text-white/55">
            Etat extension {liveTabs.extId ? '(en ligne)' : '(hors ligne)'}
          </p>
          <span className="flex-1" />
          {liveTabs.loading && <Loader2 size={11} className="animate-spin text-white/45" />}
        </div>
        {liveTabs.extId ? (
          liveTabs.tabs.length === 0 ? (
            <p className="text-[12px] text-white/55">Aucun onglet detecte par l extension. Ouvre quelques onglets dans ton navigateur.</p>
          ) : (
            <div>
              <p className="text-[11px] text-white/55 mb-2">{liveTabs.tabs.length} onglet(s) visibles par Aurora — extId <code className="text-violet-300">{liveTabs.extId.slice(0, 16)}…</code></p>
              <ul className="space-y-1 max-h-44 overflow-y-auto">
                {liveTabs.tabs.slice(0, 12).map((t) => (
                  <li key={t.id} className={`text-[11px] px-2 py-1 rounded-md ${t.active ? 'bg-violet-500/15 border border-violet-500/30' : 'bg-white/[0.03] border border-white/8'}`}>
                    <p className={`font-medium truncate ${t.active ? 'text-white' : 'text-white/85'}`}>{t.active && <span className="text-violet-300 mr-1">●</span>}{t.title || '(sans titre)'}</p>
                    <p className="text-white/45 truncate">{t.url}</p>
                  </li>
                ))}
              </ul>
            </div>
          )
        ) : (
          <p className="text-[12px] text-white/55">
            Aucune extension connectee. Telecharge le ZIP ci-dessous et installe-la dans ton navigateur.
            {liveTabs.error && <span className="block text-[10px] text-white/35 mt-1">({liveTabs.error})</span>}
          </p>
        )}
      </div>

      <div className="rounded-2xl border border-violet-500/25 bg-violet-500/5 p-4">
        <div className="flex items-start gap-3">
          <Puzzle size={18} className="text-violet-300 shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            <p className="text-[13px] font-semibold text-white">Aurora-Connect — extension navigateur</p>
            <p className="text-[11px] text-white/60 mt-1 leading-relaxed">
              Sans cette extension, Aurora ne voit que <strong>sa propre page</strong> dans le navigateur (web mode). Avec elle, Aurora peut <strong>lire, cliquer, remplir, capturer</strong> n importe quel onglet ouvert (Gmail, GitHub, Notion, ton CRM, n importe quoi). Communication 100% locale via le bridge — aucune donnee ne quitte ta machine.
            </p>
            <a
              href={downloadUrl}
              className="inline-flex items-center gap-1.5 mt-3 rounded-full bg-violet-500 px-4 py-1.5 text-[11px] font-semibold text-white hover:bg-violet-600 transition-colors"
            >
              <Download size={12} />
              Telecharger l extension (ZIP)
            </a>
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-4">
        <p className="text-[11px] font-semibold text-white/85 mb-2">A quoi ca sert (exemples concrets)</p>
        <ul className="space-y-1.5 text-[11px] text-white/70 leading-relaxed">
          <li>• <strong>« Resume-moi cet article »</strong> : Aurora lit le DOM de l onglet courant, te le synthetise.</li>
          <li>• <strong>« Remplis ce formulaire avec mes coordonnees »</strong> : fill automatique des inputs.</li>
          <li>• <strong>« Liste mes onglets ouverts »</strong> : list_tabs — utile pour retrouver un onglet enfoui.</li>
          <li>• <strong>« Capture cette page »</strong> : screenshot du tab actif (PNG dataURL).</li>
          <li>• <strong>« Va sur github.com/anthropics/claude-code »</strong> : navigate dans l onglet courant.</li>
          <li>• <strong>« Clique le bouton "S abonner" »</strong> : click via selecteur CSS auto-genere par Aurora.</li>
          <li>• <strong>Selectionne du texte → clic droit → "Envoyer la selection a Aurora"</strong> : pousse direct dans la conversation.</li>
        </ul>
      </div>

      <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-4">
        <p className="text-[11px] font-semibold text-white/85 mb-2">Comment ca marche techniquement</p>
        <ol className="space-y-1.5 text-[11px] text-white/65 leading-relaxed list-decimal pl-4">
          <li>L extension installee dans ton navigateur fait du <strong>long-poll</strong> sur <code>{getBridgeUrl()}/api/cowork/extension/poll</code> (toutes les 25s max).</li>
          <li>Quand Aurora veut interagir avec un onglet, elle pousse une commande via <code>POST /api/cowork/extension/dispatch</code>.</li>
          <li>L extension recoit, execute dans l onglet actif via <code>chrome.scripting.executeScript</code>, puis POST le resultat sur <code>/api/cowork/extension/result</code>.</li>
          <li>Aurora attend la reponse via <code>GET /api/cowork/extension/await-result?commandId=…</code> (timeout 25s).</li>
          <li>Aucune connexion entrante depuis Internet : tout passe par <code>127.0.0.1:3001</code>.</li>
        </ol>
      </div>

      <div>
        <p className="text-[10px] uppercase tracking-[0.18em] text-white/40 mb-2">Selectionne ton navigateur</p>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {allBrowsers.map((id) => {
            const isCurrent = id === current.id
            const isInstalled = installed.some((b) => b.id === id)
            const meta = browserDisplay(id)
            return (
              <button
                key={id}
                onClick={() => setSelected(id)}
                className={`relative text-left rounded-xl border p-3 transition-colors ${
                  selected === id
                    ? 'border-violet-400 bg-violet-500/10'
                    : 'border-white/10 bg-white/[0.02] hover:bg-white/[0.05]'
                }`}
              >
                <div className="flex items-center gap-2">
                  <Globe size={12} className="text-white/55" />
                  <span className="text-[12px] font-medium text-white">{meta.label}</span>
                </div>
                <div className="flex items-center gap-1 mt-1 flex-wrap">
                  {isCurrent && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/15 border border-emerald-500/30 px-2 py-0.5 text-[9px] font-semibold text-emerald-200">
                      <Star size={9} />
                      Recommande : tu utilises {meta.label}
                    </span>
                  )}
                  {isInstalled && !isCurrent && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-blue-500/15 border border-blue-500/30 px-2 py-0.5 text-[9px] font-semibold text-blue-200">
                      installe sur ce PC
                    </span>
                  )}
                </div>
              </button>
            )
          })}
        </div>
        {scanning && (
          <p className="text-[10px] text-white/40 mt-2 inline-flex items-center gap-1">
            <Loader2 size={10} className="animate-spin" />
            Scan silencieux des navigateurs installes…
          </p>
        )}
      </div>

      <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-4">
        <p className="text-[11px] uppercase tracking-[0.2em] text-white/40 mb-2">{inst.title} — etapes d installation</p>
        <ol className="space-y-2">
          {inst.steps.map((s, i) => (
            <li key={i} className="flex gap-3 text-[12px]">
              <span className="shrink-0 inline-flex items-center justify-center h-5 w-5 rounded-full bg-violet-500/20 text-violet-200 text-[10px] font-semibold border border-violet-500/30">{i + 1}</span>
              <div className="min-w-0">
                <p className="text-white/90">{s.label}</p>
                {s.detail && <p className="text-white/55 text-[11px] mt-0.5 leading-snug">{s.detail}</p>}
              </div>
            </li>
          ))}
        </ol>
      </div>

      <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-4">
        <p className="text-[11px] font-semibold text-white/65 mb-1">Apres installation</p>
        <ul className="text-[11px] text-white/60 leading-relaxed space-y-1 list-disc pl-4">
          <li>Clique l icone Aurora-Connect dans la barre d extensions.</li>
          <li>Verifie que la pastille passe au vert (= connecte au bridge).</li>
          <li>L URL du bridge dans le popup doit pointer sur ton instance (ex: http://127.0.0.1:3001).</li>
          <li>Active <code>eval JS</code> seulement si tu fais confiance aux sites visites.</li>
        </ul>
      </div>

      <div className="text-[10px] text-white/40">
        Doc complete : <a href={`${getBridgeUrl()}/api/cowork/extension/install-md`} target="_blank" rel="noopener noreferrer" className="text-violet-300 hover:underline">extension/INSTALL.md</a>
        {' '}· Source de l extension : <code>application/extension/</code>
      </div>
    </div>
  )
}

function browserDisplay(id: BrowserId): { label: string } {
  switch (id) {
    case 'chrome':   return { label: 'Google Chrome' }
    case 'edge':     return { label: 'Microsoft Edge' }
    case 'firefox':  return { label: 'Mozilla Firefox' }
    case 'safari':   return { label: 'Safari' }
    case 'brave':    return { label: 'Brave' }
    case 'opera':    return { label: 'Opera' }
    case 'vivaldi':  return { label: 'Vivaldi' }
    case 'chromium': return { label: 'Chromium' }
    case 'arc':      return { label: 'Arc' }
    default:         return { label: 'Navigateur inconnu' }
  }
}

function ConnectorRow({
  id, config, onChange, focused,
}: {
  id: ConnectorId; config: ConnectorConfig; onChange: (c: ConnectorConfig) => void; focused?: boolean
}) {
  const meta = CONNECTORS[id]
  const [revealed, setRevealed] = useState(false)
  const [testing, setTesting] = useState(false)
  // v82m1 — when this row is the focus target (set by the pill click flow),
  // scroll into view on mount + apply a violet ring to draw attention. The
  // ring fades automatically since the focus prop only flips on first paint.
  const rowRef = useRef<HTMLDivElement | null>(null)
  useEffect(() => {
    if (focused && rowRef.current) {
      try { rowRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' }) } catch { /* old browsers */ }
    }
  }, [focused])

  const runTest = async () => {
    setTesting(true)
    try {
      const r = await testConnector(id, { apiKey: config.apiKey, baseUrl: config.baseUrl, workspaceId: config.workspaceId })
      onChange({ ...config, lastCheck: { ok: r.ok, at: Date.now(), message: r.message } })
    } finally {
      setTesting(false)
    }
  }

  return (
    <div
      ref={rowRef}
      data-connector-id={id}
      data-focused={focused ? 'true' : 'false'}
      className={`rounded-xl border p-4 transition-shadow ${
        config.enabled
          ? 'border-emerald-500/25 bg-emerald-500/5'
          : 'border-white/10 bg-white/[0.02]'
      } ${focused ? 'ring-2 ring-violet-400/60 shadow-[0_0_24px_rgba(167,139,250,0.18)]' : ''}`}
    >
      <div className="flex items-start gap-3">
        <button
          type="button"
          onClick={() => onChange({ ...config, enabled: !config.enabled })}
          className={`mt-0.5 h-5 w-9 rounded-full transition-colors flex items-center shrink-0 ${
            config.enabled ? 'bg-emerald-500 justify-end' : 'bg-white/15 justify-start'
          }`}
        >
          <span className="h-4 w-4 rounded-full bg-white mx-0.5" />
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <p className="text-[13px] font-semibold text-white">{meta.label}</p>
            <a
              href={meta.docUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center text-white/40 hover:text-white/70"
              title={meta.docUrl}
            >
              <ExternalLink size={11} />
            </a>
          </div>
          <p className="text-[10px] text-white/55 mb-2">{meta.description}</p>

          {config.enabled && (
            <div className="space-y-2">
              <div>
                <p className="text-[10px] uppercase tracking-[0.16em] text-white/40 mb-1">{meta.apiKeyLabel}</p>
                <div className="flex items-center gap-2">
                  <KeyRound size={11} className="text-white/40 shrink-0" />
                  <input
                    type={revealed ? 'text' : 'password'}
                    value={config.apiKey ?? ''}
                    onChange={(e) => onChange({ ...config, apiKey: e.target.value, lastCheck: undefined })}
                    placeholder="colle ton token ici"
                    className="flex-1 rounded-lg border border-white/10 bg-black/30 px-3 py-1.5 text-[11px] font-mono text-white outline-none focus:border-violet-400/40"
                  />
                  <button
                    onClick={() => setRevealed((v) => !v)}
                    className="flex h-7 w-7 items-center justify-center rounded-lg border border-white/10 bg-white/5 text-white/60 hover:bg-white/10"
                    type="button"
                  >
                    {revealed ? <EyeOff size={11} /> : <Eye size={11} />}
                  </button>
                </div>
                <p className="text-[10px] text-white/40 mt-1">{meta.apiKeyHelp}</p>
              </div>

              {meta.needsWorkspaceId && (
                <div>
                  <p className="text-[10px] uppercase tracking-[0.16em] text-white/40 mb-1">Workspace / Team ID (optionnel)</p>
                  <input
                    type="text"
                    value={config.workspaceId ?? ''}
                    onChange={(e) => onChange({ ...config, workspaceId: e.target.value })}
                    placeholder="team_xxxxx ou workspace UUID"
                    className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-1.5 text-[11px] font-mono text-white outline-none focus:border-violet-400/40"
                  />
                </div>
              )}

              <div className="flex items-center gap-2 pt-1">
                <button
                  onClick={runTest}
                  disabled={!config.apiKey || testing}
                  className="inline-flex items-center gap-1.5 rounded-full bg-violet-500/80 px-3 py-1.5 text-[10px] font-semibold text-white hover:bg-violet-500 disabled:opacity-40 disabled:cursor-not-allowed"
                  type="button"
                >
                  {testing ? <Loader2 size={11} className="animate-spin" /> : <Plug size={11} />}
                  {testing ? 'Test en cours…' : 'Tester la connexion'}
                </button>
                {config.lastCheck && (
                  <span className={`inline-flex items-center gap-1 text-[10px] ${
                    config.lastCheck.ok ? 'text-emerald-300' : 'text-red-300'
                  }`}>
                    {config.lastCheck.ok ? <Check size={10} /> : <XCircle size={10} />}
                    {config.lastCheck.message}
                  </span>
                )}
              </div>

              <details className="mt-2">
                <summary className="text-[10px] text-white/55 cursor-pointer hover:text-white/85">
                  Actions disponibles ({meta.actions.length})
                </summary>
                <ul className="mt-1.5 space-y-0.5 pl-3">
                  {meta.actions.map((a) => (
                    <li key={a.name} className="text-[10px] text-white/65">
                      <code className="text-violet-300">{a.name}</code> — {a.description}
                    </li>
                  ))}
                </ul>
              </details>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
