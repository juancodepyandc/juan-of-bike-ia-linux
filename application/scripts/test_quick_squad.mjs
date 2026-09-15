import { installHeadlessCodeEnv } from './code_harness/harness_env.mjs'
installHeadlessCodeEnv()

const { executeMultiAgentWarRoomMission } = await import('../src/services/cyber/multiAgentWarRoomOrchestrator.ts')
const { DEFAULT_MAIN_MODEL } = await import('../src/config/models.ts')

console.log('[quick-squad] Lancement test War Room direct...')
const mission = await executeMultiAgentWarRoomMission({
  targetScope: 'Kubernetes Ingress',
  objective: 'Audit annotations',
  modelOverride: DEFAULT_MAIN_MODEL
})

console.log('[quick-squad] Mission terminee avec succes !')
console.log(`- Mission ID : ${mission.missionId}`)
console.log(`- Interventions : ${mission.transcript.length}`)
mission.transcript.forEach((t) => {
  console.log(`[${t.agentName}]: ${t.content.slice(0, 80)}...`)
})
