// FightCloud badge — appears bottom-left of mobile shell while a forge job
// is running. Cartoon Looney Tunes overlay with limb-pokes + onomatopée
// (POW! / BOOM! / CRACK!) chosen from the running prompt's domain.
// Tapping opens the forge overlay so the user can see progress live.
import React, { useMemo } from 'react'
// @ts-ignore - studio avatars is a ported JS-loose module
import { FightCloud } from './avatars'
import { useForgeQueueStore } from '../../stores/forgeQueueStore'

interface Props {
  onOpen: () => void
}

type Kind = 'pow' | 'boom' | 'crack'

function detectKind(prompt: string): Kind {
  const p = (prompt || '').toLowerCase()
  if (/\b(3d|forge|hunyuan|gltf|mesh|sculpt|model)\b/.test(p)) return 'boom'
  if (/\b(test|fail|error|crash|debug|fix)\b/.test(p))         return 'crack'
  return 'pow' // image / draw / generic creative
}

export default function FightCloudBadge({ onOpen }: Props) {
  const jobs = useForgeQueueStore((s) => s.jobs)
  const active = useMemo(
    () => jobs.find((j) => j.status === 'running') || jobs.find((j) => j.status === 'queued'),
    [jobs],
  )
  if (!active) return null
  const kind = detectKind(active.prompt)

  return (
    <button
      type="button"
      onClick={onOpen}
      aria-label={`Forge en cours — ${active.status}`}
      style={{
        position: 'fixed',
        // bottom-right — bottom-left is taken by HelpFab (zIndex 88).
        right: 12,
        bottom: 14,
        zIndex: 80,
        width: 132,
        height: 96,
        padding: 0,
        border: 'none',
        background: 'transparent',
        cursor: 'pointer',
        pointerEvents: 'auto',
        // Slight scale-on-tap feedback. The cloud and onomatopée have their
        // own infinite animations from a10-* keyframes auto-injected by
        // ./avatars.tsx on first import.
        transition: 'transform 0.18s cubic-bezier(.4,0,.2,1)',
      }}
      onTouchStart={(e) => { (e.currentTarget as HTMLElement).style.transform = 'scale(.94)' }}
      onTouchEnd={(e) => { (e.currentTarget as HTMLElement).style.transform = '' }}
    >
      <div style={{ position: 'relative', width: '100%', height: '100%' }}>
        <FightCloud kind={kind} x={0} y={28} w={132} h={68} anticipation={true} />
      </div>
      <div style={{
        position: 'absolute', left: 0, right: 0, bottom: -4,
        textAlign: 'center', fontFamily: '"JetBrains Mono", ui-monospace, monospace',
        fontSize: 9, letterSpacing: '0.14em', color: '#1a1410',
        textShadow: '0 1px 0 #fff, 0 0 6px rgba(255,208,64,.6)',
      }}>
        {active.status === 'running' ? 'EN FORGE' : 'EN ATTENTE'}
      </div>
    </button>
  )
}
