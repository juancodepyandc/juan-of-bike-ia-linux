import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildPodmanSandboxArgs,
  buildPodmanSandboxVolumeCreateArgs,
  buildPodmanSandboxVolumeRemoveArgs,
  buildPodmanSandboxWorkspaceInitArgs,
  buildSandboxIsolationStep,
  DEFAULT_SANDBOX_QUOTAS,
  detectPodmanIsolation,
  parsePodmanIsolationInfo,
  parsePodmanIsolationJson,
  isVolumeQuotaUnsupportedError,
  buildPodmanSandboxVolumeCreateArgsWithoutQuota,

  sandboxWorkspaceVolumeName,
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
    // RLIMIT_FSIZE est en OCTETS (podman passe la valeur telle quelle), pas en
    // blocs de 512 o comme `ulimit -f`. A 1048576 le plafond reel etait de
    // 1 Mio: `npm install` de react echouait en EFBIG, avec une sortie vide.
    assert.match(joined, /fsize=536870912:536870912/)
    assert.match(joined, /\/tmp:rw,nosuid,nodev,size=256m/)
    // La racine est en lecture seule: le HOME inscriptible doit etre DECLARE,
    // sinon npm/pip/cargo ecrivent dans le HOME de l image et echouent (ENOENT).
    assert.match(joined, /--env HOME=\/home\/aurora/)
    // Le cache ne vit PLUS sous /home/aurora: ce tmpfs de 256 Mio provoquait
    // ENOSPC (cache npm reel du run 1191: 284 Mio). Il est sur un volume disque.
    assert.match(joined, /--env NPM_CONFIG_CACHE=\/aurora-cache\/npm/)
    assert.doesNotMatch(joined, /NPM_CONFIG_CACHE=\/home\//)
    assert.match(joined, /aurora-code-ws-tmp-aurora-ws:\/workspace:rw/)
    assert.deepEqual(args.slice(-4), ['docker.io/library/node:22-bookworm-slim', 'npm', 'run', 'build'])
  })

  test('buildPodmanSandboxArgs monte un volume workspace quote au lieu du bind host rw', () => {
    const args = buildPodmanSandboxArgs(buildCommand, 'node', '/tmp/aurora/ws')

    assert.equal(sandboxWorkspaceVolumeName('/tmp/aurora/ws'), 'aurora-code-ws-tmp-aurora-ws')
    assert.ok(args.includes('aurora-code-ws-tmp-aurora-ws:/workspace:rw,z'))
    assert.ok(!args.some((arg) => arg.includes('/tmp/aurora/ws:/workspace:rw')))
  })

  test('buildPodmanSandboxVolumeCreateArgs encode le quota disque total workspace', () => {
    const args = buildPodmanSandboxVolumeCreateArgs('/tmp/aurora/ws')

    assert.deepEqual(args, [
      'volume',
      'create',
      '--ignore',
      '--label',
      'aurora.role=code-sandbox-workspace',
      '--opt',
      `o=size=${DEFAULT_SANDBOX_QUOTAS.workspaceSize}`,
      'aurora-code-ws-tmp-aurora-ws',
    ])
    assert.deepEqual(buildPodmanSandboxVolumeRemoveArgs('/tmp/aurora/ws'), [
      'volume',
      'rm',
      '-f',
      'aurora-code-ws-tmp-aurora-ws',
    ])
  })

  test('buildPodmanSandboxWorkspaceInitArgs copie le sandbox hote en lecture seule vers le volume quote', () => {
    const args = buildPodmanSandboxWorkspaceInitArgs('node', '/tmp/aurora/ws')

    assert.match(args.join(' '), /--network none/)
    assert.ok(args.includes('/tmp/aurora/ws:/aurora-input:ro,Z'))
    assert.ok(args.includes('aurora-code-ws-tmp-aurora-ws:/workspace:rw,z'))
    assert.match(args.at(-1) ?? '', /find \/workspace -mindepth 1/)
    assert.match(args.at(-1) ?? '', /cp -a \/aurora-input\/\. \/workspace\//)
  })

  test('buildPodmanSandboxArgs limite le reseau des installs au mode sans loopback hote', () => {
    const args = buildPodmanSandboxArgs(installCommand, 'node', '/tmp/aurora/ws')
    const networkIndex = args.indexOf('--network')

    assert.equal(args[networkIndex + 1], 'slirp4netns:allow_host_loopback=false')
    assert.match(args.join(' '), /NPM_CONFIG_REGISTRY=https:\/\/registry\.npmjs\.org\//)
    assert.match(args.join(' '), /NPM_CONFIG_IGNORE_SCRIPTS=true/)
  })

  test('buildPodmanSandboxArgs garde le reseau coupe pour une pseudo-install inconnue', () => {
    const args = buildPodmanSandboxArgs({
      label: 'Installer outil externe',
      executable: 'curl',
      args: ['https://example.test/install.sh'],
    }, 'unknown', '/tmp/aurora/ws')
    const networkIndex = args.indexOf('--network')

    assert.equal(args[networkIndex + 1], 'none')
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

// --- Deblocage WS7 (2026-08-09) ------------------------------------------
// Podman 4.9.3 rootless est desormais installe sur l hote. Deux defauts
// empechaient l isolation de fonctionner, independamment de la machine.

describe('WS7 — deblocage isolation reelle', () => {
  test('parsePodmanIsolationJson lit le JSON de podman info', () => {
    const json = JSON.stringify({ host: { security: { rootless: true }, cgroupVersion: 'v2' } })
    assert.deepEqual(parsePodmanIsolationJson(json), { rootless: true, cgroupVersion: 'v2' })
  })

  test('parsePodmanIsolationJson tolere une sortie inexploitable', () => {
    assert.equal(parsePodmanIsolationJson('pas du json'), null)
    assert.equal(parsePodmanIsolationJson('{}'), null)
  })

  test('detectPodmanIsolation survit a un gabarit Go refuse (repli JSON)', async () => {
    // Podman 4.9.3 expose .Host.CgroupsVersion et refuse .Host.CgroupVersion:
    // un gabarit errone condamnait l isolation sur un hote pourtant conforme.
    const status = await detectPodmanIsolation('/tmp', async (_exe, args) => {
      if (args.includes('--version')) {
        return { ok: true, exitCode: 0, output: 'podman version 4.9.3', command: 'podman --version' }
      }
      if (args.includes('json')) {
        return {
          ok: true,
          exitCode: 0,
          output: JSON.stringify({ host: { security: { rootless: true }, cgroupVersion: 'v2' } }),
          command: 'podman info --format json',
        }
      }
      return { ok: false, exitCode: 125, output: "can't evaluate field CgroupVersion", command: 'podman info' }
    })
    assert.equal(status.ok, true)
    assert.equal(status.mode, 'podman-rootless')
    assert.equal(status.cgroupVersion, 'v2')
  })

  test('isVolumeQuotaUnsupportedError reconnait le refus Project Quota', () => {
    assert.equal(
      isVolumeQuotaUnsupportedError('Error: volume options size and inodes not supported. Filesystem does not support Project Quota'),
      true,
    )
    assert.equal(isVolumeQuotaUnsupportedError('autre erreur'), false)
  })

  test('le volume sans quota garde le nom et le label, sans option de taille', () => {
    const withQuota = buildPodmanSandboxVolumeCreateArgs('/tmp/aurora-x')
    const without = buildPodmanSandboxVolumeCreateArgsWithoutQuota('/tmp/aurora-x')
    assert.ok(withQuota.some((a) => a.startsWith('o=size=')))
    assert.ok(!without.some((a) => a.startsWith('o=size=')))
    assert.equal(without[without.length - 1], withQuota[withQuota.length - 1])
    assert.ok(without.includes('aurora.role=code-sandbox-workspace'))
  })
})
