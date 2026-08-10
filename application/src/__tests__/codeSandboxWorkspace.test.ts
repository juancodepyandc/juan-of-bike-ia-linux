import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import { cleanupSandboxWorkspaceVolume, prepareSandboxWorkspaceVolume } from '../services/codeSandboxWorkspace.ts'

describe('codeSandboxWorkspace', () => {
  test('prepareSandboxWorkspaceVolume cree le volume quote puis initialise /workspace', async () => {
    const calls: Array<{ executable: string; args: string[] }> = []
    const result = await prepareSandboxWorkspaceVolume('/tmp/aurora/ws', 'node', {}, async (executable, args) => {
      calls.push({ executable, args })
      return {
        ok: true,
        exitCode: 0,
        output: args.join(' '),
        command: `${executable} ${args.join(' ')}`,
      }
    })

    assert.equal(result.ok, true)
    assert.equal(result.created, true)
    assert.equal(result.volumeName, 'aurora-code-ws-tmp-aurora-ws')
    assert.equal(result.steps.length, 2)
    assert.deepEqual(calls[0]?.args.slice(0, 2), ['volume', 'create'])
    assert.ok(calls[0]?.args.includes('o=size=768m'))
    assert.equal(calls[1]?.args[0], 'run')
    assert.ok(calls[1]?.args.includes('/tmp/aurora/ws:/aurora-input:ro,Z'))
    assert.ok(calls[1]?.args.includes('aurora-code-ws-tmp-aurora-ws:/workspace:rw,z'))
  })

  // Le quota disque est une garantie SOUPLE. Mesure sur un run reel: le bridge
  // renvoie `output: ""` quand `podman volume create --opt o=size=...` echoue
  // (exitCode 125 seul), donc tester le libelle laissait la degradation inerte
  // et le run brulait SEPT passes de correction sur « Quota disque total WS7
  // indisponible » — une panne d environnement qu aucune correction de code ne
  // repare. On reessaie donc SANS quota quelle que soit la raison de l echec.
  test('quota refuse SANS message exploitable: on reessaie sans quota', async () => {
    const argsSeen: string[][] = []
    const result = await prepareSandboxWorkspaceVolume('/tmp/aurora/ws', 'node', {}, async (_executable, args) => {
      argsSeen.push(args)
      const isQuotaAttempt = args.includes('o=size=768m')
      return {
        ok: !isQuotaAttempt,           // la tentative AVEC quota echoue
        exitCode: isQuotaAttempt ? 125 : 0,
        output: '',                     // exactement ce que renvoie le bridge
        command: `podman ${args.join(' ')}`,
      }
    })

    assert.ok(argsSeen.length >= 2, 'un second essai sans quota doit avoir lieu')
    assert.ok(argsSeen[0].includes('o=size=768m'), 'le premier essai porte le quota')
    assert.ok(!argsSeen[1].includes('o=size=768m'), 'le second essai est sans quota')
    assert.equal(result.steps[0]?.label, 'Quota disque workspace WS7')
    assert.match(result.steps[0]?.output ?? '', /NON APPLIQUE/, 'la degradation doit etre declaree')
  })

  test('si meme la creation sans quota echoue, on abandonne (vraie panne)', async () => {
    const result = await prepareSandboxWorkspaceVolume('/tmp/aurora/ws', 'node', {}, async () => ({
      ok: false, exitCode: 125, output: '', command: 'podman volume create',
    }))
    assert.equal(result.ok, false)
    assert.equal(result.created, false)
  })

  test('prepareSandboxWorkspaceVolume marque le volume cree si seule l init echoue', async () => {
    let calls = 0
    const result = await prepareSandboxWorkspaceVolume('/tmp/aurora/ws', 'node', {}, async (executable, args) => {
      calls += 1
      return {
        ok: calls === 1,
        exitCode: calls === 1 ? 0 : 1,
        output: calls === 1 ? 'created' : 'init failed',
        command: `${executable} ${args.join(' ')}`,
      }
    })

    assert.equal(result.ok, false)
    assert.equal(result.created, true)
    assert.equal(calls, 2)
    assert.equal(result.steps[1]?.label, 'Initialisation workspace quota WS7')
  })

  test('cleanupSandboxWorkspaceVolume supprime le volume quote', async () => {
    const step = await cleanupSandboxWorkspaceVolume('/tmp/aurora/ws', async (executable, args) => ({
      ok: true,
      exitCode: 0,
      output: 'removed',
      command: `${executable} ${args.join(' ')}`,
    }))

    assert.equal(step.ok, true)
    assert.match(step.command, /podman volume rm -f aurora-code-ws-tmp-aurora-ws/)
  })
})
