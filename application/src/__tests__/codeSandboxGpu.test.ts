import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildPodmanGpuArgs,
  buildSandboxGpuStep,
  detectPodmanGpuSupport,
  detectSandboxGpuRequirement,
  noSandboxGpuRequired,
} from '../services/codeSandboxGpu.ts'
import type { CodeFile } from '../services/codeSandboxTypes.ts'

function file(name: string, content: string, language = 'text'): CodeFile {
  return { name, content, language }
}

describe('codeSandboxGpu', () => {
  test('detectSandboxGpuRequirement ignore un projet sans signal GPU', () => {
    const requirement = detectSandboxGpuRequirement('api fastapi simple', [
      file('main.py', 'print("ok")', 'python'),
    ])

    assert.equal(requirement.required, false)
    assert.deepEqual(requirement.reasons, [])
  })

  test('detectSandboxGpuRequirement detecte WebGPU, Three.js et CUDA', () => {
    const requirement = detectSandboxGpuRequirement('scene WebGPU premium', [
      file('src/App.tsx', 'import { Canvas } from "@react-three/fiber"\nnew THREE.WebGLRenderer()'),
      file('main.py', 'import torch\nassert torch.cuda.is_available()', 'python'),
    ])

    assert.equal(requirement.required, true)
    assert.ok(requirement.reasons.some((reason) => reason.includes('WebGPU')))
    assert.ok(requirement.reasons.some((reason) => reason.includes('WebGL/Three.js')))
    assert.ok(requirement.reasons.some((reason) => reason.includes('CUDA/NVIDIA')))
  })

  test('detectPodmanGpuSupport refuse un hote sans nvidia-smi', async () => {
    const status = await detectPodmanGpuSupport('/tmp', async () => ({
      ok: false,
      exitCode: 127,
      output: 'not found',
      command: 'nvidia-smi -L',
    }))

    assert.equal(status.ok, false)
    assert.equal(status.mode, 'unavailable')
    assert.match(status.reason, /NVIDIA/)
  })

  test('detectPodmanGpuSupport exige le device CDI all', async () => {
    const status = await detectPodmanGpuSupport('/tmp', async (_executable, args) => {
      if (args[0] === '-L') {
        return { ok: true, exitCode: 0, output: 'GPU 0: RTX', command: 'nvidia-smi -L' }
      }
      return { ok: true, exitCode: 0, output: 'nvidia.com/gpu=0', command: 'nvidia-ctk cdi list' }
    })

    assert.equal(status.ok, false)
    assert.match(status.reason, /nvidia\.com\/gpu=all/)
  })

  test('detectPodmanGpuSupport accepte nvidia-container-toolkit CDI', async () => {
    const status = await detectPodmanGpuSupport('/tmp', async (_executable, args) => {
      if (args[0] === '-L') {
        return { ok: true, exitCode: 0, output: 'GPU 0: RTX', command: 'nvidia-smi -L' }
      }
      return { ok: true, exitCode: 0, output: 'nvidia.com/gpu=0\nnvidia.com/gpu=all', command: 'nvidia-ctk cdi list' }
    })

    assert.equal(status.ok, true)
    assert.equal(status.mode, 'podman-cdi')
    assert.deepEqual(buildPodmanGpuArgs(true), ['--security-opt', 'label=disable', '--device', 'nvidia.com/gpu=all'])
    assert.deepEqual(buildPodmanGpuArgs(false), [])
    assert.equal(buildSandboxGpuStep({ required: true, reasons: ['prompt:CUDA/NVIDIA'] }, status).ok, true)
    assert.equal(noSandboxGpuRequired().ok, true)
  })
})
