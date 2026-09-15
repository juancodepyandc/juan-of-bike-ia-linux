/**
 * SidebarPersona — petit personnage vivant (v10 SVG : respiration, clignement,
 * mèches qui suivent) affiché en bas de la sidebar aurora_v1 desktop. Montre le
 * persona du module actif. Lazy-loadé pour ne pas tirer ~54KB d'avatars dans le
 * bundle initial — réutilise le chunk `avatars` déjà splitté par AuroraAgentScene.
 */
// @ts-nocheck — avatars.tsx est en @ts-nocheck (SVG procédural), on reste lâche.
import { Avatar } from './avatars.tsx'
import { getAgent } from '../../services/auroraAgents.ts'

const MODULE_PERSONA: Record<string, string> = {
  conversation: 'sage', voice: 'diego',
  image: 'mira', drawing: 'mira',
  video: 'tess', '3d': 'tess',
  code: 'lou', learning: 'sam', cyber: 'yann',
}

export default function SidebarPersona({ moduleId }: { moduleId: string }) {
  const agent = getAgent(moduleId as never)
  const persona = MODULE_PERSONA[moduleId] || 'sage'
  return (
    <div
      title={`${agent.name} — ${agent.role}\n« ${agent.motto} »`}
      style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, padding: '4px 0 10px' }}
    >
      <div style={{
        lineHeight: 0,
        filter: `drop-shadow(0 6px 12px rgba(0,0,0,0.25)) drop-shadow(0 0 10px ${agent.color}33)`,
      }}>
        <Avatar persona={persona} w={132} h={188} />
      </div>
      <div style={{
        fontFamily: 'var(--font-mono, ui-monospace, monospace)', fontSize: 10,
        letterSpacing: '0.12em', textTransform: 'uppercase', textAlign: 'center',
        color: agent.color, lineHeight: 1.3,
      }}>
        <div style={{ fontWeight: 700, fontSize: 11 }}>{agent.name}</div>
        <div style={{ opacity: 0.7, fontSize: 9 }}>{agent.role}</div>
      </div>
    </div>
  )
}
