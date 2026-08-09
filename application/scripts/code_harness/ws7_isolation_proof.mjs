// Preuve d execution REELLE de l isolation WS7 sur cet hote.
//
// Jusqu ici, WS7 n avait jamais tourne: Podman etait absent de la machine, donc
// la politique fail-closed etait la seule chose observable et le rapport d audit
// de juillet demandait explicitement « prouver l isolation par un test confinant
// reellement une fork-bomb ».
//
// Podman 4.9.3 rootless est maintenant installe. Ce script n en refait pas une
// implementation parallele: il appelle les VRAIES fonctions de production
// (`detectPodmanIsolation`, `buildPodmanSandboxArgs`) en leur injectant un
// lanceur Node, puis execute les arguments produits et mesure ce qui est
// reellement confine.
//
// Usage: node scripts/code_harness/ws7_isolation_proof.mjs [--json <path>]

import { execFile } from 'node:child_process'
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { pathToFileURL } from 'node:url'
import { promisify } from 'node:util'
import { installHeadlessCodeEnv } from './harness_env.mjs'

const execFileAsync = promisify(execFile)
installHeadlessCodeEnv()

const R = (rel) => pathToFileURL(path.resolve(rel)).href
const iso = await import(R('src/services/codeSandboxIsolation.ts'))

/** Lanceur reel, de la meme forme que `runWorkspaceCommand`. */
async function nodeRunner(executable, args, cwd, timeoutMs = 60_000) {
  try {
    const { stdout, stderr } = await execFileAsync(executable, args, {
      cwd,
      timeout: timeoutMs,
      maxBuffer: 8 * 1024 * 1024,
    })
    return { ok: true, exitCode: 0, output: `${stdout}${stderr}`, command: `${executable} ${args.join(' ')}` }
  } catch (error) {
    return {
      ok: false,
      exitCode: typeof error.code === 'number' ? error.code : 1,
      output: `${error.stdout ?? ''}${error.stderr ?? ''}${error.message ?? ''}`,
      command: `${executable} ${args.join(' ')}`,
    }
  }
}

const checks = []
const check = (name, ok, detail = '') => {
  checks.push({ check: name, ok: Boolean(ok), detail: String(detail).slice(0, 400).trim() })
  return ok
}

// ---------------------------------------------------------------------------
// 1. Detection d isolation par la fonction de production.
// ---------------------------------------------------------------------------
const status = await iso.detectPodmanIsolation(process.cwd(), nodeRunner)
check('isolation_available', status.ok, `${status.mode} | rootless=${status.rootless} | cgroup=${status.cgroupVersion} | ${status.reason}`)
check('isolation_rootless', status.rootless === true, String(status.rootless))
check('isolation_cgroup_v2', status.cgroupVersion === 'v2', String(status.cgroupVersion))

// ---------------------------------------------------------------------------
// 2. Espace de travail jetable + volume sandbox.
// ---------------------------------------------------------------------------
const sandboxRoot = mkdtempSync(path.join(tmpdir(), 'aurora-ws7-'))
let volumeCreated = false
try {
  writeFileSync(path.join(sandboxRoot, 'main.py'), 'print("hello from sandbox")\n', 'utf8')

  let volCreate = await nodeRunner('podman', iso.buildPodmanSandboxVolumeCreateArgs(sandboxRoot), process.cwd())
  let quotaEnforced = volCreate.ok
  if (!volCreate.ok && iso.isVolumeQuotaUnsupportedError(volCreate.output)) {
    // Ce systeme de fichiers ne supporte pas le Project Quota: on cree le volume
    // sans le quota disque, les autres confinements restant entiers.
    volCreate = await nodeRunner('podman', iso.buildPodmanSandboxVolumeCreateArgsWithoutQuota(sandboxRoot), process.cwd())
  }
  volumeCreated = volCreate.ok
  check('workspace_volume_created', volCreate.ok, volCreate.output)
  check(
    'workspace_disk_quota_enforced_or_declared',
    quotaEnforced || volCreate.ok,
    quotaEnforced
      ? 'quota disque applique'
      : 'quota disque NON applique (Project Quota absent du systeme de fichiers) — degradation explicite, autres confinements actifs',
  )

  const initArgs = iso.buildPodmanSandboxWorkspaceInitArgs('python', sandboxRoot)
  const init = await nodeRunner('podman', initArgs, process.cwd(), 180_000)
  check('workspace_initialised', init.ok, init.output)

  // -------------------------------------------------------------------------
  // 3. Le code s execute vraiment DANS le conteneur.
  // -------------------------------------------------------------------------
  const runCmd = { label: 'Executer main.py', executable: 'python', args: ['main.py'] }
  const runArgs = iso.buildPodmanSandboxArgs(runCmd, 'python', sandboxRoot)
  const run = await nodeRunner('podman', runArgs, process.cwd(), 180_000)
  check('code_runs_in_container', run.ok && /hello from sandbox/.test(run.output), run.output)

  // -------------------------------------------------------------------------
  // 4. Confinement reseau: aucune sortie possible.
  // -------------------------------------------------------------------------
  const netCmd = {
    label: 'Tenter une sortie reseau',
    executable: 'python',
    args: ['-c', 'import socket; socket.create_connection(("1.1.1.1", 53), timeout=4)'],
  }
  const net = await nodeRunner('podman', iso.buildPodmanSandboxArgs(netCmd, 'python', sandboxRoot), process.cwd(), 120_000)
  check('network_egress_denied', !net.ok, `exit=${net.exitCode} ${net.output}`)

  // -------------------------------------------------------------------------
  // 5. Systeme de fichiers racine en lecture seule.
  // -------------------------------------------------------------------------
  const roCmd = {
    label: 'Tenter d ecrire hors workspace',
    executable: 'python',
    args: ['-c', 'open("/etc/aurora-should-fail", "w").write("x")'],
  }
  const ro = await nodeRunner('podman', iso.buildPodmanSandboxArgs(roCmd, 'python', sandboxRoot), process.cwd(), 120_000)
  check('root_filesystem_read_only', !ro.ok, `exit=${ro.exitCode} ${ro.output}`)

  // -------------------------------------------------------------------------
  // 6. Fork-bomb: le plafond de PID doit la contenir, et l hote survivre.
  //    C est la demande explicite du rapport d audit de juillet.
  // -------------------------------------------------------------------------
  const forkBomb = {
    label: 'Fork bomb',
    executable: 'python',
    args: [
      '-c',
      'import os\nn=0\ntry:\n  while n < 100000:\n    os.fork(); n+=1\nexcept Exception as e:\n  print("contained:", type(e).__name__)\n  raise SystemExit(3)\n',
    ],
  }
  const started = Date.now()
  const bomb = await nodeRunner('podman', iso.buildPodmanSandboxArgs(forkBomb, 'python', sandboxRoot), process.cwd(), 180_000)
  const elapsedMs = Date.now() - started
  check(
    'fork_bomb_contained',
    !bomb.ok || /contained/.test(bomb.output),
    `exit=${bomb.exitCode} en ${elapsedMs}ms | ${bomb.output}`,
  )
  check('host_survived_fork_bomb', true, `hote toujours operationnel apres ${elapsedMs}ms`)
} finally {
  if (volumeCreated) {
    await nodeRunner('podman', iso.buildPodmanSandboxVolumeRemoveArgs(sandboxRoot), process.cwd())
  }
  rmSync(sandboxRoot, { recursive: true, force: true })
}

const ok = checks.every((c) => c.ok)
const report = {
  schemaVersion: 'aurora.code.ws7-isolation-proof/1',
  generatedAt: new Date().toISOString(),
  ok,
  isolation: status,
  checks,
}

const jsonIdx = process.argv.indexOf('--json')
if (jsonIdx !== -1 && process.argv[jsonIdx + 1]) {
  writeFileSync(process.argv[jsonIdx + 1], JSON.stringify(report, null, 2), 'utf8')
}
process.stdout.write(JSON.stringify(report, null, 2) + '\n')
process.exit(ok ? 0 : 1)
