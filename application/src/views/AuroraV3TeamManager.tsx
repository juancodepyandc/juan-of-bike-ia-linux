/**
 * AuroraV3TeamManager — vue "Manager d'équipe" pour les 8 agents Aurora.
 *
 * V3 only. Liste les 8 personas (Lyra, Iris, Cinéma, Glyph, Sumi, Atlas,
 * Sage, Phantom) avec leur mascot animé + champs éditables :
 *   - nom (rename)
 *   - voix (selecteur parmi VOICE_OPTIONS)
 *   - systemPrompt (textarea, persisté en localStorage)
 *
 * Actions : SAUVEGARDER / RESET (per agent) / RESET ALL.
 */
import { useState } from 'react'
import {
  getAllAgents,
  updateAgent,
  resetAgent,
  resetAllAgents,
  VOICE_OPTIONS,
  type AuroraAgent,
  type AgentVoice,
} from '../services/auroraAgents'
import AuroraAgentMascot from '../components/AuroraAgentMascot'

export default function AuroraV3TeamManager() {
  const [agents, setAgents] = useState<AuroraAgent[]>(() => getAllAgents())

  const refresh = () => setAgents(getAllAgents())

  const handleSave = (id: AuroraAgent['id'], patch: Partial<AuroraAgent>) => {
    updateAgent(id, patch)
    refresh()
  }
  const handleReset = (id: AuroraAgent['id']) => {
    if (!window.confirm('Réinitialiser cet agent aux valeurs par défaut ?')) return
    resetAgent(id)
    refresh()
  }
  const handleResetAll = () => {
    if (!window.confirm('Réinitialiser TOUS les agents aux valeurs par défaut ?')) return
    resetAllAgents()
    refresh()
  }

  return (
    <div className="aurora-v3-team">
      <div className="aurora-v3-team-header">
        <span className="aurora-v3-team-kicker">Aurora · Équipe</span>
        <span className="aurora-v3-team-title">Le Manager</span>
        <span style={{ fontSize: 12, opacity: 0.7, marginTop: 4 }}>
          8 agents IA, 1 par module. Édite leur système prompt, leur voix, ou leur nom — chaque changement est persisté localement.
        </span>
      </div>

      <div className="aurora-v3-team-grid">
        {agents.map((agent) => (
          <AgentCard
            key={agent.id}
            agent={agent}
            onSave={(patch) => handleSave(agent.id, patch)}
            onReset={() => handleReset(agent.id)}
          />
        ))}
      </div>

      <div style={{ marginTop: 32, display: 'flex', justifyContent: 'flex-end' }}>
        <button
          type="button"
          className="aurora-v3-agent-btn is-danger"
          onClick={handleResetAll}
        >
          ↺ Reset all (8 agents)
        </button>
      </div>
    </div>
  )
}

function AgentCard({ agent, onSave, onReset }: {
  agent: AuroraAgent
  onSave: (patch: Partial<AuroraAgent>) => void
  onReset: () => void
}) {
  const [name, setName] = useState(agent.name)
  const [voice, setVoice] = useState<AgentVoice>(agent.voice)
  const [systemPrompt, setSystemPrompt] = useState(agent.systemPrompt)
  const [previewState, setPreviewState] = useState<'idle' | 'thinking' | 'working' | 'done'>('idle')

  const dirty =
    name !== agent.name ||
    voice !== agent.voice ||
    systemPrompt !== agent.systemPrompt

  return (
    <div className="aurora-v3-agent-card">
      <div className="aurora-v3-agent-head">
        <AuroraAgentMascot
          moduleId={agent.id}
          state={previewState}
          size={72}
          showLabel={false}
        />
        <div className="aurora-v3-agent-meta">
          <span className="aurora-v3-agent-name">{agent.name}</span>
          <span className="aurora-v3-agent-role">{agent.role}</span>
          <span className="aurora-v3-agent-motto">« {agent.motto} »</span>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', fontSize: 9 }}>
        {(['idle', 'thinking', 'working', 'done'] as const).map((s) => (
          <button
            key={s}
            type="button"
            className={`aurora-v3-agent-btn ${previewState === s ? 'is-primary' : ''}`}
            onClick={() => setPreviewState(s)}
            style={{ padding: '4px 8px', fontSize: 9 }}
          >
            {s}
          </button>
        ))}
      </div>

      <div className="aurora-v3-agent-field">
        <span className="aurora-v3-agent-label">Nom</span>
        <input
          type="text"
          className="aurora-v3-agent-input"
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={20}
        />
      </div>

      <div className="aurora-v3-agent-field">
        <span className="aurora-v3-agent-label">Voix</span>
        <select
          className="aurora-v3-agent-input"
          value={voice}
          onChange={(e) => setVoice(e.target.value as AgentVoice)}
        >
          {VOICE_OPTIONS.map((v) => (
            <option key={v.id} value={v.id}>{v.label}</option>
          ))}
        </select>
      </div>

      <div className="aurora-v3-agent-field">
        <span className="aurora-v3-agent-label">System prompt</span>
        <textarea
          className="aurora-v3-agent-textarea"
          value={systemPrompt}
          onChange={(e) => setSystemPrompt(e.target.value)}
        />
      </div>

      <div className="aurora-v3-agent-actions">
        <button
          type="button"
          className="aurora-v3-agent-btn"
          onClick={onReset}
        >
          ↺ Reset
        </button>
        <button
          type="button"
          className="aurora-v3-agent-btn is-primary"
          disabled={!dirty}
          onClick={() => onSave({ name, voice, systemPrompt })}
          style={{ opacity: dirty ? 1 : 0.4, cursor: dirty ? 'pointer' : 'not-allowed' }}
        >
          ✓ Sauvegarder
        </button>
      </div>
    </div>
  )
}
