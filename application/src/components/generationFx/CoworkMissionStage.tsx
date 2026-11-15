import { useMemo } from 'react'
import { previewUrlForCoworkArtifact, type CoworkProjectThread } from '../../services/coworkProjectThread.ts'
import type { CoworkActionEvent } from '../../services/coworkTypes.ts'
import { MissionActor, missionCast } from './MissionActor.tsx'
import type { FxModule } from './fxBus.ts'

const artifactRole: Partial<Record<CoworkProjectThread['artifacts'][number]['kind'], FxModule>> = {
  image: 'image', model3d: '3d', game: 'code', code: 'code', video: 'video',
  audio: 'voice', document: 'learning', data: 'business',
}
const connectorRole: Record<string, FxModule> = {
  aurora_image: 'image', aurora_3d: '3d', aurora_code: 'code', aurora_video: 'video', aurora_voice: 'voice',
}
const cast = (Object.keys(missionCast) as FxModule[]).filter(module => module !== 'cowork')

function roleFor(event?: CoworkActionEvent): FxModule {
  switch (event?.actionKind) {
    case 'web_search': case 'browser': case 'fetch': case 'open_url': return 'conversation'
    case 'write_file': case 'edit_file': case 'shell': return 'code'
    case 'voice_speak': return 'voice'
    case 'vision_describe': case 'screenshot_desktop': return 'image'
    case 'file_bundle': return 'learning'
    case 'connector': return connectorRole[event.message.match(/Connecteur\s+(\w+)\./i)?.[1] ?? ''] ?? 'cowork'
    default: return 'cowork'
  }
}

export default function CoworkMissionStage({ events, thread, running }: {
  events: CoworkActionEvent[]; thread: CoworkProjectThread; running: boolean
}) {
  const activity = useMemo(() => events.slice().reverse().find(e => e.actionKind && e.actionKind !== 'finish' && e.actionKind !== 'reply'), [events])
  const evidence = useMemo(() => events.slice().reverse().find(e => e.kind === 'success' && e.detail && (
    e.actionKind === 'web_search' || e.actionKind === 'fetch' || e.actionKind === 'shell'
  )), [events])
  if (!running && !events.length) return null
  const artifact = events[0] && thread.artifacts.slice().reverse().find(a => a.status === 'ready' && a.createdAt >= events[0].at)
  const actor = artifact ? artifactRole[artifact.kind] ?? roleFor(activity) : roleFor(activity)
  const uri = artifact?.kind === 'image' ? previewUrlForCoworkArtifact(artifact) : null
  const sharing = Boolean(artifact) || (evidence?.at === activity?.at && Boolean(evidence))
  return <section className="cowork-mission-stage" aria-label="Équipe en mission">
    <div className="cowork-mission-stage__floor">
      <div className="cowork-mission-stage__team">
        {cast.filter(module => module !== actor).map(module =>
          <MissionActor key={module} module={module} x={(cast.indexOf(module) + .5) / cast.length} facing={1} gesture={0} />)}
      </div>
      <div className="cowork-mission-stage__desk">
        {actor !== 'cowork' && <MissionActor key={actor} module={actor} x={sharing ? .39 : .31} entrance={.14}
          facing={1} gesture={.65} cue={activity?.actionKind} label/>}
        <MissionActor module="cowork" x={sharing ? .61 : .72} facing={-1} gesture={sharing ? .62 : 0}
          cue={artifact?.id ?? evidence?.at} label/>
      </div>
    </div>
    {artifact && <div className="cowork-mission-stage__result">
      {uri && <img src={uri} alt={artifact.label} loading="lazy"/>}
      <div><strong>{artifact.label}</strong>{artifact.summary && <p>{artifact.summary.slice(0, 380)}</p>}</div>
    </div>}
    {!artifact && evidence && <details className="cowork-mission-stage__result">
      <summary>{evidence.message}</summary>
      <p>{evidence.detail}</p>
    </details>}
    {activity && <p className="cowork-mission-stage__event">{activity.message}</p>}
  </section>
}
