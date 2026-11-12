/**
 * SidebarPersona — personnage du module actif, en bas de la sidebar aurora_v1.
 *
 * Chaque module a son propre personnage (generationFx/mascots.tsx) : plus de
 * persona partagée entre deux modules. Son état suit les vrais jobs du module
 * (en file, en préparation, au travail) plutôt qu'une animation décorative.
 */
import AuroraMascot, { FX_AGENTS, MASCOT_STATE_LABEL, type FxModule, type MascotState } from '../generationFx/mascots.tsx'
import { getAgent } from '../../services/auroraAgents.ts'
import { useAppStore } from '../../stores/appStore.ts'

export default function SidebarPersona({ moduleId }: { moduleId: string }) {
  const fxModule = (moduleId in FX_AGENTS ? moduleId : 'conversation') as FxModule
  const fx = FX_AGENTS[fxModule]
  const agent = getAgent(moduleId as never)
  const job = useAppStore((s) => s.generationJobs.find((j) => (j.module as string) === moduleId && (j.status === 'queued' || j.status === 'running')))
  const state: MascotState = !job ? 'idle' : job.status === 'queued' ? 'waiting' : job.phase === 'prepare' ? 'thinking' : 'working'
  return (
    <div
      title={`${fx.name} — ${fx.role}\n« ${agent.motto || fx.hello} »\n${MASCOT_STATE_LABEL[state]}`}
      style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, padding: '4px 0 10px' }}
    >
      <div style={{ lineHeight: 0, filter: `drop-shadow(0 6px 12px rgba(0,0,0,0.25)) drop-shadow(0 0 10px ${fx.accent}33)` }}>
        <AuroraMascot module={fxModule} size={128} state={state} />
      </div>
      <div style={{
        fontFamily: 'var(--font-mono, ui-monospace, monospace)', fontSize: 10,
        letterSpacing: '0.12em', textTransform: 'uppercase', textAlign: 'center',
        color: fx.accent, lineHeight: 1.3,
      }}>
        <div style={{ fontWeight: 700, fontSize: 11 }}>{fx.name}</div>
        <div style={{ opacity: 0.7, fontSize: 9 }}>{fx.role} · {MASCOT_STATE_LABEL[state]}</div>
      </div>
    </div>
  )
}
