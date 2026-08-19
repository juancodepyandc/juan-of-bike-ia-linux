import { useMemo, useState } from 'react'
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Brain,
  Bug,
  CheckCircle2,
  Code2,
  Copy,
  Cpu,
  Download,
  FileCode,
  Layers,
  Lightbulb,
  Loader2,
  Play,
  RotateCcw,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Terminal,
  Zap,
} from 'lucide-react'
import {
  analyzeDynamicVulnerabilities,
  FUNDAMENTAL_INVARIANTS,
  type DynamicHypothesis,
  type DynamicReasoningSession,
} from '../../services/cyber/dynamicZeroDayEngine.ts'
import { triggerBrowserDownload } from '../../services/cyber/cyberOutputManager.ts'
import VoicePushToTalk from '../../components/VoicePushToTalk'

const ACCENT = '#F43F5E'
const OK = '#4ADE80'
const WARN = '#F59E0B'
const BLUE = '#60A5FA'

const SAMPLE_CODE_SNIPPETS = [
  {
    label: 'Concurrence & Double-Spend (Async)',
    language: 'typescript',
    code: `// Logique financière asynchrone sans verrou transactionnel
async function processTransfer(senderId: string, recipientId: string, amount: number) {
  const account = await db.findAccount(senderId);
  
  // Vérification de solde
  if (account.balance >= amount) {
    // Latence I/O simulée vers la passerelle de paiement
    await paymentGateway.charge(account.token, amount);
    
    // Mise à jour tardive du solde (Fenêtre TOCTOU exploitable)
    await db.updateAccount(senderId, { balance: account.balance - amount });
    await db.creditAccount(recipientId, { balance: amount });
    return { success: true };
  }
  throw new Error("Solde insuffisant");
}`,
  },
  {
    label: 'Gestion Mémoire C (Use-After-Free)',
    language: 'c',
    code: `// Gestionnaire de paquets réseau avec cycle de vie défaillant
struct packet_session *current_session = NULL;

void free_session(struct packet_session *s) {
    if (s && s->ref_count <= 0) {
        free(s->buffer);
        free(s);
        // Omission : current_session n'est pas réinitialisé à NULL !
    }
}

int handle_incoming_data(const char *raw_data, size_t len) {
    if (!current_session) return -1;
    // DANGER : current_session pointe vers une zone mémoire potentiellement libérée
    return current_session->callback(current_session, raw_data, len);
}`,
  },
  {
    label: 'Parsing Dynamique & Injection',
    language: 'python',
    code: `# Parseur de configuration avec interpolation non assainie
import subprocess

def render_config_snippet(user_identifier: str, debug_mode: bool):
    # Concaténation de directive NGINX/LUA avec entrée utilisateur
    base_template = f"location /{user_identifier} {{ proxy_pass http://backend; }}"
    
    if debug_mode:
        # Exécution de hook de diagnostic système
        cmd = f"echo 'Config rendered for {user_identifier}' >> /var/log/app.log"
        subprocess.call(cmd, shell=True) # Injection de commande possible via user_identifier
        
    return base_template`,
  },
]

export default function DynamicZeroDayLab() {
  const [sourceCode, setSourceCode] = useState(SAMPLE_CODE_SNIPPETS[0]!.code)
  const [language, setLanguage] = useState(SAMPLE_CODE_SNIPPETS[0]!.language)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [session, setSession] = useState<DynamicReasoningSession | null>(() =>
    analyzeDynamicVulnerabilities(SAMPLE_CODE_SNIPPETS[0]!.code, 'typescript'),
  )
  const [copied, setCopied] = useState(false)

  const handleRunDynamicAnalysis = () => {
    if (!sourceCode.trim() || isAnalyzing) return
    setIsAnalyzing(true)
    setTimeout(() => {
      const res = analyzeDynamicVulnerabilities(sourceCode, language)
      setSession(res)
      setIsAnalyzing(false)
    }, 450)
  }

  const handleDownloadReport = () => {
    if (!session) return
    triggerBrowserDownload(
      session.exportPayload.filename,
      session.exportPayload.content,
      'text/markdown;charset=utf-8',
    )
  }

  const handleCopyDefenseCode = async () => {
    if (!session) return
    try {
      await navigator.clipboard.writeText(session.synthesizedDefenseCode)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // ignore
    }
  }

  return (
    <div className="space-y-4">
      {/* Top Banner */}
      <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-rose-500/20 text-rose-400 border border-rose-500/30">
              <Brain size={16} />
            </span>
            <h2 className="text-white text-[16px] font-bold">Raisonnement Dynamique 0-Day & Invariants de Sécurité</h2>
          </div>
          <p className="text-[12px] text-white/60 mt-1 max-w-2xl">
            Déduction heuristique de failles inédites sans catalogue statique, modélisation des invariants de sécurité (mémoire, concurrence, typage), et synthèse de preuves défensives.
          </p>
        </div>
        {session && (
          <button
            type="button"
            onClick={handleDownloadReport}
            className="px-3 py-1.5 rounded-lg bg-rose-500 hover:bg-rose-400 text-black text-[12px] font-bold flex items-center gap-1.5 transition-colors cursor-pointer self-start md:self-auto"
          >
            <Download size={13} /> Exporter Rapport .md
          </button>
        )}
      </div>

      {/* Code Input & Snippet Selector */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        <div className="lg:col-span-6 space-y-3">
          <div className="rounded-xl border border-white/10 bg-black/40 p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-[12px] font-mono text-white/70 flex items-center gap-2 font-bold uppercase">
                <Code2 size={14} className="text-rose-400" />
                Code Source ou Logique Métier à Éprouver
              </span>
              <div className="flex gap-1.5">
                {SAMPLE_CODE_SNIPPETS.map((snip, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => {
                      setSourceCode(snip.code)
                      setLanguage(snip.language)
                    }}
                    className="px-2 py-1 rounded bg-white/5 hover:bg-white/10 border border-white/10 text-[10px] font-mono text-white/80 transition-colors cursor-pointer"
                  >
                    Exemple #{idx + 1}
                  </button>
                ))}
              </div>
            </div>

            <textarea
              rows={12}
              value={sourceCode}
              onChange={(e) => setSourceCode(e.target.value)}
              placeholder="Collez n'importe quel code (C, Rust, Go, Python, JS, smart contract, API spec) pour en déduire les failles 0-day..."
              className="w-full rounded-lg bg-black/70 border border-white/10 p-3 text-[11.5px] font-mono text-white/90 leading-relaxed outline-none resize-vertical focus:border-rose-500"
            />

            <div className="flex items-center justify-between pt-1">
              <VoicePushToTalk
                onTranscript={(txt) => setSourceCode((p) => `${p}\n// ${txt}`)}
                label="Dicter note de code"
                size={32}
              />
              <button
                type="button"
                onClick={handleRunDynamicAnalysis}
                disabled={!sourceCode.trim() || isAnalyzing}
                className="px-4 py-2 rounded-lg bg-rose-500 hover:bg-rose-400 text-black font-bold text-[12px] flex items-center gap-1.5 transition-colors disabled:opacity-40 cursor-pointer"
              >
                {isAnalyzing ? <Loader2 size={13} className="animate-spin" /> : <Zap size={13} />}
                {isAnalyzing ? 'Raisonnement en cours...' : 'Raisonner sur les 0-Days'}
              </button>
            </div>
          </div>

          {/* Fundamental Invariants Matrix */}
          <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 space-y-2.5">
            <h3 className="text-[12px] font-semibold text-white/80 uppercase tracking-wider flex items-center gap-2">
              <Layers size={14} className="text-purple-400" />
              Invariants de Sécurité Fondamentaux Évalués
            </h3>
            <div className="space-y-1.5 text-[11px] font-mono">
              {FUNDAMENTAL_INVARIANTS.map((inv, i) => (
                <div key={i} className="p-2 rounded bg-black/40 border border-white/5 space-y-1">
                  <div className="flex items-center justify-between text-white font-bold">
                    <span className="text-purple-300">{inv.name}</span>
                    <span className="text-[9px] uppercase px-1.5 py-0.5 rounded bg-purple-500/10 border border-purple-500/30 text-purple-200">{inv.category}</span>
                  </div>
                  <div className="text-white/60 text-[10.5px]">{inv.formalDefinition}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Inferred Hypotheses, Fuzz Strategies & Defense Code */}
        <div className="lg:col-span-6 space-y-4">
          {session && (
            <>
              {/* Inferred Hypotheses Cards */}
              <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-[12px] font-semibold text-rose-300 uppercase tracking-wider flex items-center gap-2">
                    <Bug size={14} />
                    Hypothèses 0-Day Déduites par Premiers Principes ({session.hypotheses.length})
                  </h3>
                </div>

                <div className="space-y-3 max-h-[360px] overflow-y-auto pr-1">
                  {session.hypotheses.map((h: DynamicHypothesis) => (
                    <div
                      key={h.id}
                      className="p-3 rounded-lg border border-rose-500/30 bg-rose-500/5 space-y-2 text-[11.5px] font-mono text-white/85"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-white text-[12.5px]">{h.title}</span>
                        <span className="text-[9.5px] font-bold px-1.5 py-0.5 rounded border border-rose-500/40 bg-rose-500/20 text-rose-200">
                          {h.impactEstimate}
                        </span>
                      </div>
                      <div className="text-white/70 text-[11px] leading-relaxed">
                        <b className="text-rose-400">Mécanisme :</b> {h.flawMechanism}
                      </div>
                      <div className="text-white/70 text-[11px] leading-relaxed">
                        <b className="text-amber-400">Vecteur d'exploit :</b> {h.exploitVector}
                      </div>
                      <div className="p-2 rounded bg-black/60 border border-white/10 text-[10.5px] text-rose-200">
                        <div className="text-[9px] text-white/40 uppercase mb-0.5">Payload de Fuzzing Synthétisé :</div>
                        <code>{h.testPayload}</code>
                      </div>
                      <div className="text-emerald-300 text-[11px] bg-emerald-500/10 p-2 rounded border border-emerald-500/20">
                        <b className="text-emerald-400">Invariant Défensif :</b> {h.defenseInvariant}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Synthesized Defense & Hardening Code */}
              <div className="rounded-xl border border-emerald-500/30 bg-black/50 p-4 space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="text-[12px] font-mono uppercase text-emerald-400 font-bold flex items-center gap-1.5">
                    <ShieldCheck size={14} /> Correctif Formel & Invariant Défensif
                  </span>
                  <button
                    type="button"
                    onClick={handleCopyDefenseCode}
                    className="text-[11px] font-mono text-white/60 hover:text-white flex items-center gap-1 cursor-pointer"
                  >
                    <Copy size={11} /> {copied ? 'Copié !' : 'Copier'}
                  </button>
                </div>
                <pre className="p-3 rounded-lg bg-black/70 border border-emerald-500/20 text-[10.5px] font-mono text-emerald-200 overflow-x-auto max-h-48 leading-relaxed">
                  <code>{session.synthesizedDefenseCode}</code>
                </pre>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
