#!/usr/bin/env node
/**
 * Banc de conformité inter-modules AuroraIA — mesures comportementales.
 *
 * Rejoue les mesures qui ont motivé les corrections des services TS et Python,
 * et vérifie qu'elles tiennent toujours. Aucune suite de tests n'est embarquée
 * ici : le projet ne conserve plus de fichiers de tests (supprimés) ; seules
 * les mesures de comportement réelles, chiffrées en « nombre de défauts »,
 * restent exploitées.
 *
 *   node scripts/conformance.mjs                # mesures comportementales
 *   node scripts/conformance.mjs --json         # sortie machine
 *
 * L'endpoint bridge `GET/POST /api/conformance` exécute ce banc en lecture
 * seule ; le mode `--preuve` (rouge/vert sur le code d'avant) a été retiré
 * avec les suites de tests.
 */
import { execFileSync, spawnSync } from 'node:child_process'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const RACINE = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const PYTHON = join(RACINE, '.venv', 'bin', 'python')

/** Mesures comportementales des services Python (même contrat que côté TS). */
function mesurePython() {
  try {
    const sortie = execFileSync(PYTHON, [join(RACINE, 'scripts', 'conformance_mesures.py')],
      { cwd: RACINE, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], timeout: 600_000 })
    return JSON.parse(sortie.slice(sortie.indexOf('[')))
  } catch (e) {
    return [{ module: 'python', quoi: 'mesures', defauts: 1,
              detail: `banc Python injoignable : ${String(e.message).slice(0, 160)}` }]
  }
}

const args = new Set(process.argv.slice(2))
const JSON_OUT = args.has('--json')
const log = (...a) => { if (!JSON_OUT) console.log(...a) }

// ---------------------------------------------------------------------------
log('\n\x1b[1mBANC DE CONFORMITÉ AURORAIA — mesures comportementales\x1b[0m')
log('─'.repeat(78))

const { mesure } = await import(`./conformanceMesures.mjs?m=${Date.now()}`)
const apres = [...await mesure(), ...mesurePython()]

let total = 0
for (const m of apres) {
  const état = m.defauts === 0 ? '\x1b[32mOK   \x1b[0m' : `\x1b[31m${String(m.defauts).padStart(4)} \x1b[0m`
  log(`${état} ${m.module.padEnd(14)} ${m.quoi.padEnd(26)} ${m.detail}`)
  total += m.defauts
}
log('─'.repeat(78))
log(`${total === 0 ? '\x1b[32m' : '\x1b[31m'}${total} défaut(s) mesuré(s)\x1b[0m`)

if (JSON_OUT) {
  console.log(JSON.stringify({ mesures: apres, total, verdict: total === 0 ? 'OK' : 'ECHEC' }, null, 2))
}
process.exit(total === 0 ? 0 : 1)