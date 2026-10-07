#!/usr/bin/env node
// Actual Zustand state/persistence; no model inference or hardware access.
import assert from 'node:assert/strict'
import { test } from 'node:test'

const memory = new Map()
globalThis.localStorage = {
  getItem: key => memory.get(key) ?? null,
  setItem: (key, value) => memory.set(key, value),
  removeItem: key => memory.delete(key),
}
globalThis.window = { localStorage: globalThis.localStorage }
const { useAppStore } = await import('../src/stores/appStore.ts')
const hardware = { ram_gb: 30, vram_gb: 16 }

test('explicit main and vision models survive delayed startup detection and rehydration', async () => {
  const state = useAppStore.getState()
  state.setMainModel('qwen3-coder:30b')
  state.setVisionModel('qwen3-vl:30b')
  state.setHardware(hardware)
  state.setInstalledModels(['qwen3-coder:30b', 'qwen3-vl:8b', 'qwen3-vl:30b'])
  assert.equal(useAppStore.getState().mainModel, 'qwen3-coder:30b')
  assert.equal(useAppStore.getState().visionModel, 'qwen3-vl:30b')
  await useAppStore.persist.rehydrate()
  useAppStore.getState().setHardware({ ram_gb: 8, vram_gb: 0 })
  assert.equal(useAppStore.getState().mainModel, 'qwen3-coder:30b')
  assert.equal(useAppStore.getState().visionModel, 'qwen3-vl:30b')
})

test('automatic selection remains available on fresh profiles', () => {
  useAppStore.getState().setMainModelAutomatic()
  useAppStore.getState().setVisionModelAutomatic()
  useAppStore.getState().setHardware(hardware)
  assert.equal(useAppStore.getState().visionModel, 'qwen3-vl:8b')
  useAppStore.getState().setInstalledModels(['qwen3-vl:8b', 'qwen3:14b'])
  useAppStore.getState().setHardware(hardware)
  assert.equal(useAppStore.getState().mainModel, 'qwen3:14b')
  assert.equal(useAppStore.getState().mainModelAutomatic, true)
})

test('selecting the automatic model explicitly still preserves a manual choice', () => {
  useAppStore.getState().setMainModel('qwen3:14b')
  useAppStore.getState().setInstalledModels(['qwen3:32b', 'qwen3:14b'])
  useAppStore.getState().setHardware(hardware)
  assert.equal(useAppStore.getState().mainModel, 'qwen3:14b')
  assert.equal(useAppStore.getState().mainModelAutomatic, false)
})

test('version 8 choices and unrelated conversation settings survive migration', async () => {
  memory.set('juan-bike-app-store', JSON.stringify({ version: 8, state: {
    mainModel: 'qwen3-coder:30b', visionModel: 'qwen3-vl:8b',
    activeModule: 'image', selectedAvatarId: 'preserved-avatar',
  } }))
  await useAppStore.persist.rehydrate()
  useAppStore.getState().setHardware(hardware)
  useAppStore.getState().setInstalledModels(['qwen3-vl:8b'])
  const state = useAppStore.getState()
  assert.equal(state.mainModel, 'qwen3-coder:30b')
  assert.equal(state.visionModel, 'qwen3-vl:8b')
  assert.equal(state.mainModelAutomatic, false)
  assert.equal(state.visionModelAutomatic, false)
  assert.equal(state.activeModule, 'image')
  assert.equal(state.selectedAvatarId, 'preserved-avatar')
  assert.equal(JSON.parse(memory.get('juan-bike-app-store')).version, 9)
})
