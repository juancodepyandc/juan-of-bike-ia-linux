/**
 * Tests pour services/auroraAgents — registry des 8 personas Aurora +
 * couche production agents.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  AURORA_AGENTS_DEFAULT,
  AGENT_RUNTIME_STATES,
  VOICE_OPTIONS,
  PRODUCTION_AGENT_IDS,
  AGENT_AVATAR_PARAMS,
  getAgent,
  getAllAgents,
  getProductionAgent,
  getAllProductionAgents,
  buildAgentPromptSection,
  buildCoworkTeamPromptSection,
  getAvatarUrl,
  type AgentVoice,
} from '../services/auroraAgents.ts'

const MODULE_IDS = ['conversation', 'image', 'video', 'code', 'drawing', '3d', 'learning', 'cyber'] as const

describe('AURORA_AGENTS_DEFAULT — coverage 8 modules', () => {
  test('contient tous les module IDs', () => {
    for (const m of MODULE_IDS) {
      assert.ok(m in AURORA_AGENTS_DEFAULT, `${m} manquant`)
    }
  })

  test('contient voice (alias Lyra)', () => {
    assert.ok('voice' in AURORA_AGENTS_DEFAULT)
    assert.equal(AURORA_AGENTS_DEFAULT.voice.name, 'Lyra')
  })

  test('noms uniques par module (sauf voice/conversation = Lyra)', () => {
    const names = MODULE_IDS.map((m) => AURORA_AGENTS_DEFAULT[m].name)
    assert.equal(new Set(names).size, names.length)
  })

  test('Lyra/Iris/Cinéma/Glyph/Sumi/Atlas/Sage/Phantom présents', () => {
    const names = MODULE_IDS.map((m) => AURORA_AGENTS_DEFAULT[m].name)
    for (const n of ['Lyra', 'Iris', 'Cinéma', 'Glyph', 'Sumi', 'Atlas', 'Sage', 'Phantom']) {
      assert.ok(names.includes(n), `${n} manquant`)
    }
  })

  test('chaque agent a tous les champs', () => {
    for (const m of MODULE_IDS) {
      const a = AURORA_AGENTS_DEFAULT[m]
      assert.ok(a.id, `${m} sans id`)
      assert.ok(a.name)
      assert.ok(a.role)
      assert.ok(a.glyph)
      assert.ok(a.color)
      assert.ok(a.bodyColor)
      assert.ok(a.tool)
      assert.ok(a.voice)
      assert.ok(a.motto)
      assert.ok(a.systemPrompt.length > 50)
    }
  })

  test('voices uniques par agent (sauf voice/conversation = lyra-soft)', () => {
    const voices = MODULE_IDS.map((m) => AURORA_AGENTS_DEFAULT[m].voice)
    assert.equal(new Set(voices).size, voices.length)
  })

  test('color est hex valide', () => {
    for (const m of MODULE_IDS) {
      const a = AURORA_AGENTS_DEFAULT[m]
      assert.ok(/^#[0-9a-f]{3,8}$/i.test(a.color), `${m} color ${a.color}`)
      assert.ok(/^#[0-9a-f]{3,8}$/i.test(a.bodyColor))
    }
  })

  test('systemPrompt contient le nom de l agent', () => {
    for (const m of MODULE_IDS) {
      const a = AURORA_AGENTS_DEFAULT[m]
      assert.ok(a.systemPrompt.includes(a.name), `${m} systemPrompt ne mentionne pas ${a.name}`)
    }
  })
})

describe('AGENT_RUNTIME_STATES', () => {
  test('contient idle/thinking/working/done/error + planning/verifying/handoff', () => {
    for (const s of ['idle', 'thinking', 'working', 'done', 'error', 'planning', 'verifying', 'handoff']) {
      assert.ok(AGENT_RUNTIME_STATES.includes(s as never))
    }
  })
})

describe('VOICE_OPTIONS', () => {
  test('contient 8 voix', () => {
    assert.equal(VOICE_OPTIONS.length, 8)
  })

  test('chaque voice option a id + label', () => {
    for (const v of VOICE_OPTIONS) {
      assert.ok(v.id)
      assert.ok(v.label.length > 0)
    }
  })

  test('IDs uniques', () => {
    const ids = VOICE_OPTIONS.map((v) => v.id)
    assert.equal(new Set(ids).size, ids.length)
  })

  test('contient lyra-soft, atlas-strong, phantom-sharp', () => {
    const ids = VOICE_OPTIONS.map((v) => v.id)
    for (const id of ['lyra-soft', 'atlas-strong', 'phantom-sharp'] as AgentVoice[]) {
      assert.ok(ids.includes(id))
    }
  })
})

describe('getAgent', () => {
  test('renvoie l agent par id', () => {
    const a = getAgent('image')
    assert.equal(a.name, 'Iris')
    assert.equal(a.role, 'Coloriste')
  })

  test('chaque module a un agent', () => {
    for (const m of MODULE_IDS) {
      const a = getAgent(m)
      assert.ok(a.name)
    }
  })
})

describe('getAllAgents', () => {
  test('renvoie 8 agents', () => {
    const all = getAllAgents()
    assert.equal(all.length, 8)
  })

  test('aucun id dupliqué', () => {
    const all = getAllAgents()
    const ids = all.map((a) => a.id)
    assert.equal(new Set(ids).size, ids.length)
  })
})

describe('PRODUCTION_AGENT_IDS', () => {
  test('contient manager + 8 agents (voice exclu)', () => {
    assert.equal(PRODUCTION_AGENT_IDS.length, 9)
    assert.ok(PRODUCTION_AGENT_IDS.includes('manager'))
    assert.ok(!PRODUCTION_AGENT_IDS.includes('voice' as never))
  })
})

describe('getProductionAgent', () => {
  test('manager existe avec taskContract', () => {
    const a = getProductionAgent('manager')
    assert.equal(a.name, 'Aurora')
    assert.ok(a.taskContract.length > 20)
    assert.ok(a.collaborationRules.length > 20)
  })

  test('chaque agent module a taskContract + collaborationRules + defaultCollaborators', () => {
    for (const id of PRODUCTION_AGENT_IDS) {
      const a = getProductionAgent(id)
      assert.ok(a.taskContract.length > 0)
      assert.ok(a.collaborationRules.length > 0)
      assert.ok(Array.isArray(a.defaultCollaborators))
    }
  })

  test('Iris (image) collabore avec drawing', () => {
    const a = getProductionAgent('image')
    assert.ok(a.defaultCollaborators.includes('manager'))
    assert.ok(a.defaultCollaborators.includes('drawing'))
  })
})

describe('getAllProductionAgents', () => {
  test('renvoie 9 agents (manager + 8 modules)', () => {
    assert.equal(getAllProductionAgents().length, 9)
  })
})

describe('buildAgentPromptSection', () => {
  test('contient nom + role + sysPrompt + contract + rules', () => {
    const s = buildAgentPromptSection('image')
    assert.ok(s.includes('IRIS'))
    assert.ok(s.includes('CONTRAT DE TACHE'))
    assert.ok(s.includes('REGLES DE COLLABORATION'))
  })

  test('pour manager → contient AURORA', () => {
    const s = buildAgentPromptSection('manager')
    assert.ok(s.includes('AURORA'))
  })
})

describe('buildCoworkTeamPromptSection', () => {
  test('contient tous les agents avec leur id', () => {
    const s = buildCoworkTeamPromptSection()
    for (const id of PRODUCTION_AGENT_IDS) {
      assert.ok(s.includes(`(${id})`), `${id} manquant`)
    }
  })

  test('marque l agent actif avec [actif]', () => {
    const s = buildCoworkTeamPromptSection('image')
    assert.ok(s.includes('[actif]'))
    // Vérifie que c'est bien sur la ligne image
    const lines = s.split('\n')
    const imageLine = lines.find((l) => l.includes('(image)'))
    assert.ok(imageLine?.includes('[actif]'))
  })

  test('mentionne handoff via @id', () => {
    const s = buildCoworkTeamPromptSection()
    assert.ok(s.includes('@image') || s.includes('@'))
  })

  test('sans activeModule → aucun [actif]', () => {
    const s = buildCoworkTeamPromptSection()
    assert.ok(!s.includes('[actif]'))
  })
})

describe('AGENT_AVATAR_PARAMS + getAvatarUrl', () => {
  test('chaque module a un seed', () => {
    for (const m of MODULE_IDS) {
      assert.ok(AGENT_AVATAR_PARAMS[m].seed.length > 0)
    }
  })

  test('seeds uniques pour distinguer les avatars', () => {
    const seeds = MODULE_IDS.map((m) => AGENT_AVATAR_PARAMS[m].seed)
    assert.equal(new Set(seeds).size, seeds.length)
  })

  test('getAvatarUrl renvoie URL DiceBear', () => {
    const url = getAvatarUrl('image')
    assert.ok(url.includes('api.dicebear.com'))
    assert.ok(url.includes('avataaars'))
    assert.ok(url.includes('seed=Iris-aurora-image'))
  })

  test('getAvatarUrl déterministe', () => {
    const a = getAvatarUrl('code')
    const b = getAvatarUrl('code')
    assert.equal(a, b)
  })

  test('getAvatarUrl pour module inconnu → fallback seed=<id>', () => {
    const url = getAvatarUrl('unknown_module' as never)
    assert.ok(url.includes('seed=unknown_module'))
  })
})

describe('Cohérence systemPrompts', () => {
  test('chaque sysPrompt > 100 chars (sauf voice qui est laconique)', () => {
    for (const m of MODULE_IDS) {
      assert.ok(AURORA_AGENTS_DEFAULT[m].systemPrompt.length >= 50, `${m} sysPrompt trop court`)
    }
  })

  test('Lyra (conversation) — mention Carl Rogers ou écoute active', () => {
    const p = AURORA_AGENTS_DEFAULT.conversation.systemPrompt
    assert.ok(/Rogers|écoute active|reformul/i.test(p))
  })

  test('Phantom (cyber) — mention OSCP / SANS', () => {
    const p = AURORA_AGENTS_DEFAULT.cyber.systemPrompt
    assert.ok(/OSCP|SANS/i.test(p))
  })

  test('Atlas (3d) — mention Pixar/WETA/Hunyuan', () => {
    const p = AURORA_AGENTS_DEFAULT['3d'].systemPrompt
    assert.ok(/Pixar|WETA|Hubert|topologie|PBR/i.test(p))
  })
})
