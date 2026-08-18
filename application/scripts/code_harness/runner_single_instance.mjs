// ---------------------------------------------------------------------------
// runner_single_instance — un seul run de code a la fois sur cette machine.
//
// MESURE (audit_v125, constatee en direct pendant la reprise):
//
//   run.log final, 698 octets:
//     [bridge-runner] FAILED phase=error files=35 (fichiers partiels emis)
//     s/run-1181/index.html                      <- fragment orphelin
//     [bridge-runner] INTERROMPU files=41 — travail preserve, ...
//
//   `s/run-1181/index.html` est la QUEUE de la ligne « viewer:
//   /api/code/assets/file/viewer » d un PREMIER run, restee visible parce qu un
//   SECOND run a reecrit le debut du fichier par-dessus, avec son propre
//   decalage. Deux verdicts contradictoires (FAILED files=35 et INTERROMPU
//   files=41) cohabitent donc dans un seul fichier de 698 octets.
//
//   Le meme phenomene abime stream.ndjson: 4 lignes sur 287 sont illisibles,
//   dont celle-ci ou un evenement est ecrit AU MILIEU d un autre:
//     {"schema":"aurora.code.stream/1","kind":"phas{"schema":"aurora.code...
//
// Consequences, par ordre de gravite:
//   1. La preuve est detruite. Le flux du run qui a reellement echoue a ete
//      ecrase pendant qu on l analysait. Un audit dont les traces se recouvrent
//      ne prouve rien — et ce module a pour premiere regle de ne jamais
//      fabriquer une preuve.
//   2. La machine se met elle-meme en echec. Le journal Ollama du meme creneau
//      montre cinq POST /api/generate simultanes et un chargement de modele qui
//      n aboutit pas: 500 apres 3m0s, 499 apres 3m30s, « client connection
//      closed before llama-server finished loading ». C est exactement la
//      contention memoire que la regle « un seul modele par pipeline » existe
//      pour eviter.
//
// Deux runs simultanes ne sont jamais souhaitables ici: ils se disputent le
// meme Ollama, le meme sandbox podman, les memes ports de dev server. On refuse
// donc de demarrer, au lieu de produire deux resultats qui se corrompent.
// ---------------------------------------------------------------------------

import fs from 'node:fs'
import path from 'node:path'

export const RUNNER_LOCK_PATH = 'output/code/.runner.lock'

/** Le processus qui detient le verrou est-il encore vivant ? */
export function isProcessAlive(pid) {
  if (!Number.isInteger(pid) || pid <= 0) return false
  try {
    process.kill(pid, 0)
    return true
  } catch (err) {
    // EPERM = le processus existe mais appartient a un autre utilisateur.
    return err?.code === 'EPERM'
  }
}

/**
 * Lit le verrou existant. Retourne null s il n existe pas, est illisible, ou
 * appartient a un processus mort (verrou perime — on ne bloque pas un run a
 * cause d un crash precedent).
 */
export function readLiveLock(lockPath = RUNNER_LOCK_PATH) {
  let raw
  try {
    raw = fs.readFileSync(lockPath, 'utf8')
  } catch {
    return null
  }
  let parsed
  try {
    parsed = JSON.parse(raw)
  } catch {
    return null
  }
  if (!isProcessAlive(parsed?.pid)) return null
  return parsed
}

/**
 * Prend le verrou. Retourne { ok: true } ou { ok: false, holder } si un run
 * vivant le detient deja. Le verrou est libere a la sortie du processus.
 */
export function acquireRunnerLock({ lockPath = RUNNER_LOCK_PATH, pid = process.pid, startedAt = Date.now() } = {}) {
  const holder = readLiveLock(lockPath)
  if (holder) return { ok: false, holder }

  fs.mkdirSync(path.dirname(lockPath), { recursive: true })
  fs.writeFileSync(lockPath, JSON.stringify({ pid, startedAt, argv: process.argv.slice(1, 3) }), 'utf8')

  const release = () => {
    try {
      const current = JSON.parse(fs.readFileSync(lockPath, 'utf8'))
      if (current?.pid === pid) fs.unlinkSync(lockPath)
    } catch {
      /* verrou deja parti — rien a faire */
    }
  }
  process.once('exit', release)
  for (const signal of ['SIGINT', 'SIGTERM', 'SIGHUP']) {
    process.once(signal, () => {
      release()
      process.exit(130)
    })
  }
  return { ok: true, release }
}

export function buildBusyMessage(holder) {
  const ageSec = Math.round((Date.now() - (holder?.startedAt ?? Date.now())) / 1000)
  return (
    `Un run de code tourne deja (pid ${holder?.pid}, depuis ${ageSec}s). ` +
    'Deux runs simultanes se disputent Ollama, le sandbox podman et les ports du dev server, ' +
    'et ecrasent mutuellement leurs traces (mesure audit_v125: deux verdicts dans un meme fichier de 698 octets). ' +
    `Attends la fin du run en cours, ou supprime ${RUNNER_LOCK_PATH} si tu es certain que le processus est mort.`
  )
}
