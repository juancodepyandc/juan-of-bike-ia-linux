import type { ThreeDRelation } from './threeDRelation.ts'
export type RigSubject = 'humanoid' | 'quadruped' | 'existing' | 'none'
export type SourceContext = { subjectKind?: string; rigSubject?: RigSubject; description?: string }
export function planThreeDEdit(hasMesh: boolean, relation: ThreeDRelation | null, motionEnabled: boolean, hasAttachments: boolean) {
  const continuation = hasMesh && relation?.continuation === true
  // A static pose is a visual edit. It must not depend on an animation skin.
  const articulate = continuation && motionEnabled && relation.mesh_edit !== 'none' && !relation.reference_edit && !hasAttachments
  return { continuation, articulate, reconstructFromSource: continuation && !articulate, mode: motionEnabled ? 'animation' as const : 'static_pose' as const }
}
export function sourceRig(context: SourceContext | null, relation: ThreeDRelation | null): RigSubject | 'auto' {
  return context?.rigSubject || relation?.source_rig || (context?.subjectKind === 'character' ? 'humanoid' : 'auto')
}
/** Read source identity from its delivery, never classify anatomy from a new pose. */
export async function readThreeDSourceContext(mesh: string, read: (path: string) => Promise<string>): Promise<SourceContext | null> {
  const root = mesh.replaceAll(String.fromCharCode(92), '/').match(/^(.*\/juan_bike_\d+)\//)?.[1]
  if (!root) return null
  let combined: Record<string, unknown> = {}
  for (const file of ['journal/manifest.json','audits/manifest.json','journal/final_manifest.json','audits/final_manifest.json']) {
    try { combined = { ...combined, ...JSON.parse(await read(`${root}/${file}`)) } } catch { /* Older layout or unavailable file. */ }
  }
  const rig = combined.rig_subject
  return {
    subjectKind: typeof combined.source_subject_kind === 'string' ? combined.source_subject_kind : typeof combined.subject_kind === 'string' ? combined.subject_kind : undefined,
    rigSubject: ['humanoid','quadruped','existing','none'].includes(String(rig)) ? rig as RigSubject : undefined,
    description: typeof combined.subject_description === 'string' ? combined.subject_description : typeof combined.effective_request === 'string' ? combined.effective_request : typeof combined.prompt === 'string' ? combined.prompt : undefined,
  }
}
