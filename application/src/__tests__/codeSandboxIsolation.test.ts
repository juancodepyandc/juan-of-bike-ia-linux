import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildPodmanSandboxArgs,
  buildSandboxIsolationStep,
  DEFAULT_SANDBOX_QUOTAS,
  detectPodmanIsolation,
  parsePodmanIsolationInfo,
  wrapCommandForPodman,
} from '../services/codeSandboxIsolation.ts'
import type { ValidationCommand } from '../services/codeSandboxTypes.ts'

const buildCommand: ValidationCommand = {
  label: 'Verifier build',
  executable: 'npm',
  args: ['run', 'build'],
  timeoutMs: 120_000,
}

const installCommand: ValidationCommand = {
  label: 'Installer les dependances',
  executable: 'npm',
  args: ['install'],
  timeoutMs: 120_000,
}

describe('codeSandboxIsolation', () => {
  test('parsePodmanIsolationInfo lit rootless et cgroups v2', () => {
    assert.deepEqual(parsePodmanIsolationInfo('true v2\n'), {
      rootless: true,
      cgroupVersion: 'v2',
    })
    assert.deepEqual(parsePodmanIsolationInfo('false v1\n'), {
      rootless: false,
      cgroupVersion: 'v1',
    })
  })

  test('buildPodmanSandboxArgs applique isolation, quotas et reseau coupe', () => {
    const args = buildPodmanSandboxArgs(buildCommand, 'node', '/tmp/aurora/ws')
    const joined = args.join(' ')

    assert.equal(args[0], 'run')
    assert.ok(args.includes('--rm'))
    assert.ok(args.includes('--pull=never'))
    assert.match(joined, /--network none/)
    assert.match(joined, new RegExp(`--memory ${DEFAULT_SANDBOX_QUOTAS.memory}`))
    assert.match(joined, new RegExp(`--cpus ${DEFAULT_SANDBOX_QUOTAS.cpus}`))
    assert.match(joined, new RegExp(`--pids-limit ${DEFAULT_SANDBOX_QUOTAS.pidsLimit}`))
    assert.match(joined, /--security-opt no-new-privileges/)
    assert.match(joined, /--cap-drop ALL/)
    assert.match(joined, /--read-only/)
    assert.match(joined, /fsize=1048576:1048576/)
    assert.match(joined, /\/tmp:rw,nosuid,nodev,size=256m/)
    assert.match(joined, /\/tmp\/aurora\/ws:\/workspace:rw/)
    assert.deepEqual(args.slice(-4), ['docker.io/library/node:22-bookworm-slim', 'npm', 'run', 'build'])
  })

  test('buildPodmanSandboxArgs limite le reseau des installs au mode sans loopback hote', () => {
    const args = buildPodmanSandboxArgs(installCommand, 'node', '/tmp/aurora/ws')
    const networkIndex = args.indexOf('--network')

    assert.equal(args[networkIndex + 1], 'slirp4netns:allow_host_loopback=false')
  })

  test('buildPodmanSandboxArgs expose le GPU NVIDIA uniquement sur demande', () => {
    const args = buildPodmanSandboxArgs(buildCommand, 'node', '/tmp/aurora/ws', DEFAULT_SANDBOX_QUOTAS, { gpu: true })

    assert.match(args.join(' '), /--device nvidia\.com\/gpu=all/)
    assert.match(args.join(' '), /--security-opt label=disable/)
  })

  test('wrapCommandForPodman conserve label, timeout et optional', () => {
    const wrapped = wrapCommandForPodman({ ...buildCommand, optional: true }, 'node', '/tmp/aurora/ws')

    assert.equal(wrapped.label, buildCommand.label)
    assert.equal(wrapped.executable, 'podman')
    assert.equal(wrapped.timeoutMs, buildCommand.timeoutMs)
    assert.equal(wrapped.optional, true)
    assert.equal(wrapped.args[0], 'run')
  })

  test('detectPodmanIsolation refuse podman absent et accepte rootless cgroups v2', async () => {
    const absent = await detectPodmanIsolation('/tmp', async () => ({
      ok: false,
      exitCode: 127,
      output: 'not found',
      command: 'podman --version',
    }))

    assert.equal(absent.ok, false)
    assert.equal(absent.mode, 'unavailable')

    const ok = await detectPodmanIsolation('/tmp', async (_executable, args) => {
      if (args[0] === '--version') {
        return { ok: true, exitCode: 0, output: 'podman version 5.0.0', command: 'podman --version' }
      }
      return { ok: true, exitCode: 0, output: 'true v2', command: 'podman info' }
    })

    assert.equal(ok.ok, true)
    assert.equal(ok.mode, 'podman-rootless')
    assert.equal(buildSandboxIsolationStep(ok).ok, true)
  })
})
