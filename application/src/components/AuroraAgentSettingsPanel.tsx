import { useEffect, useMemo, useState } from 'react'
import AuroraAgentMascot from './AuroraAgentMascot'
import {
  AGENT_RUNTIME_STATES,
  VOICE_OPTIONS,
  getAllProductionAgents,
  resetAgent,
  resetAllAgents,
  updateAgent,
  type AgentRuntimeState,
  type AgentVoice,
  type AuroraProductionAgent,
  type ProductionAgentId,
} from '../services/auroraAgents'
import { useAgentRuntimeStore } from '../stores/agentRuntimeStore'

type AgentDraft = Pick<
  AuroraProductionAgent,
  'name' | 'role' | 'voice' | 'systemPrompt' | 'taskContract' | 'collaborationRules'
>

type Props = {
  compact?: boolean
}

function toDraft(agent: AuroraProductionAgent): AgentDraft {
  return {
    name: agent.name,
    role: agent.role,
    voice: agent.voice,
    systemPrompt: agent.systemPrompt,
    taskContract: agent.taskContract,
    collaborationRules: agent.collaborationRules,
  }
}

export default function AuroraAgentSettingsPanel({ compact = false }: Props) {
  const [agents, setAgents] = useState<AuroraProductionAgent[]>(() => getAllProductionAgents())
  const [selectedId, setSelectedId] = useState<ProductionAgentId>('manager')
  const [previewState, setPreviewState] = useState<AgentRuntimeState>('idle')
  const selected = useMemo(
    () => agents.find((agent) => agent.id === selectedId) || agents[0],
    [agents, selectedId],
  )
  const [draft, setDraft] = useState<AgentDraft>(() => toDraft(selected))

  const refresh = () => setAgents(getAllProductionAgents())

  useEffect(() => {
    const onUpdate = () => refresh()
    window.addEventListener('aurora-agents-updated', onUpdate)
    return () => window.removeEventListener('aurora-agents-updated', onUpdate)
  }, [])

  useEffect(() => {
    setDraft(toDraft(selected))
  }, [selected])

  const save = () => {
    updateAgent(selected.id, draft)
    refresh()
  }

  const preview = (state: AgentRuntimeState) => {
    setPreviewState(state)
    useAgentRuntimeStore.getState().setAgentRuntime(selected.id, {
      state,
      startedAt: state === 'idle' ? null : Date.now(),
      progress: state === 'done' ? 100 : state === 'idle' ? 0 : 42,
      etaMs: state === 'done' || state === 'idle' ? 0 : 12 * 60 * 1000,
      activeTool: 'preview',
      detail: `Preview ${state}`,
      collaborators: selected.defaultCollaborators,
    })
  }

  return (
    <section className={`aurora-agent-settings ${compact ? 'is-compact' : ''}`}>
      <header className="aurora-agent-settings-head">
        <div>
          <p className="aurora-agent-settings-kicker">Equipe Aurora</p>
          <h2>Agents personnalises</h2>
        </div>
        <button
          type="button"
          className="sp-btn"
          onClick={() => {
            if (window.confirm('Reset toute l equipe Aurora ?')) {
              resetAllAgents()
              refresh()
            }
          }}
        >
          Reset equipe
        </button>
      </header>

      <div className="aurora-agent-settings-layout">
        <div className="aurora-agent-roster">
          {agents.map((agent) => (
            <button
              key={agent.id}
              type="button"
              className={`aurora-agent-roster-card ${selected.id === agent.id ? 'is-active' : ''} ${agent.id === 'manager' ? 'is-manager' : ''}`}
              onClick={() => setSelectedId(agent.id)}
              style={{ ['--agent-color' as string]: agent.color }}
            >
              <span>{agent.name}</span>
              <small>{agent.role}</small>
            </button>
          ))}
        </div>

        <div className="aurora-agent-editor">
          <div className="aurora-agent-preview">
            <AuroraAgentMascot
              moduleId={selected.id}
              state={previewState}
              size={compact ? 108 : 150}
              showLabel
              showScene
            />
            <div className="aurora-agent-preview-strip">
              {AGENT_RUNTIME_STATES.map((state) => (
                <button
                  key={state}
                  type="button"
                  className={previewState === state ? 'is-active' : ''}
                  onClick={() => preview(state)}
                >
                  {state}
                </button>
              ))}
            </div>
          </div>

          <div className="aurora-agent-form">
            <label>
              Nom
              <input
                className="sp-select"
                value={draft.name}
                onChange={(event) => setDraft((prev) => ({ ...prev, name: event.target.value }))}
              />
            </label>
            <label>
              Role
              <input
                className="sp-select"
                value={draft.role}
                onChange={(event) => setDraft((prev) => ({ ...prev, role: event.target.value }))}
              />
            </label>
            <label>
              Voix
              <select
                className="sp-select"
                value={draft.voice}
                onChange={(event) => setDraft((prev) => ({ ...prev, voice: event.target.value as AgentVoice }))}
              >
                {VOICE_OPTIONS.map((voice) => (
                  <option key={voice.id} value={voice.id}>{voice.label}</option>
                ))}
              </select>
            </label>
            <label>
              Prompt systeme
              <textarea
                className="sp-select aurora-agent-textarea"
                value={draft.systemPrompt}
                onChange={(event) => setDraft((prev) => ({ ...prev, systemPrompt: event.target.value }))}
              />
            </label>
            <label>
              Contrat de tache
              <textarea
                className="sp-select aurora-agent-textarea"
                value={draft.taskContract}
                onChange={(event) => setDraft((prev) => ({ ...prev, taskContract: event.target.value }))}
              />
            </label>
            <label>
              Regles de collaboration
              <textarea
                className="sp-select aurora-agent-textarea"
                value={draft.collaborationRules}
                onChange={(event) => setDraft((prev) => ({ ...prev, collaborationRules: event.target.value }))}
              />
            </label>
            <div className="aurora-agent-actions">
              <button type="button" className="sp-btn is-primary" onClick={save}>
                Enregistrer agent
              </button>
              <button
                type="button"
                className="sp-btn"
                onClick={() => {
                  resetAgent(selected.id)
                  refresh()
                }}
              >
                Reset agent
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
