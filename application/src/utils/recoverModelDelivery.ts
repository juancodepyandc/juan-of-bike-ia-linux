import { parsePythonResult } from './pythonResult.ts'

type Files = { list(path: string): Promise<string[]>; text(path: string): Promise<string>; exists(path: string): Promise<boolean> }
type Report = { ok?: boolean; error?: string; final_mesh?: string; livraison?: Record<string, string> }

/** Recover an existing delivery for one exact session; never launches a calculation. */
export async function recoverModelDelivery(workspace: string, sessionId: string, files: Files) {
  const id = sessionId.replace(/^session-/, '')
  if (!/^[a-zA-Z0-9_-]+$/.test(id)) return null
  const base = workspace.replaceAll(String.fromCharCode(92), '/') + '/output/3d/conversations'
  const directories = (await files.list(base)).filter(name => !/[\\/]/.test(name) && name.endsWith('_' + id.slice(0, 18)))
  const runs: { root: string; id: string }[] = []
  for (const directory of directories) {
    for (const runId of await files.list(`${base}/${directory}`)) {
      if (/^juan_bike_\d+$/.test(runId)) runs.push({ root: `${base}/${directory}/${runId}`, id: runId })
    }
  }
  runs.sort((a, b) => Number(b.id.slice(10)) - Number(a.id.slice(10)))
  for (const run of runs) {
    let manifest: { session_id?: string } | null = null
    for (const path of ['journal/manifest.json', 'audits/manifest.json']) {
      try { manifest = JSON.parse(await files.text(`${run.root}/${path}`)); break } catch { /* Try older layout. */ }
    }
    if (manifest?.session_id !== sessionId) continue
    let report: Report | null = null
    try {
      for (const name of await files.list(`${run.root}/.aurora-receipts`)) {
        if (!/^[a-f0-9]{64}\.json$/.test(name)) continue
        const receipt = JSON.parse(await files.text(`${run.root}/.aurora-receipts/${name}`))
        if (receipt.schema === 'aurora.operation-receipt.v1' && receipt.operation_id === run.id) { report = receipt.result; break }
      }
    } catch { /* Older runs may only have their terminal log. */ }
    if (!report) {
      for (const path of ['journal/pipeline.log', 'travail/journal/pipeline.log', 'work/journal/pipeline.log']) {
        try { report = parsePythonResult<Report>(await files.text(`${run.root}/${path}`)); if (report) break } catch { /* Try next layout. */ }
      }
    }
    const mesh = report?.livraison?.mouvement_couleurs || report?.livraison?.scene_couleurs || report?.livraison?.modele_couleurs || report?.final_mesh || `${run.root}/modele/modele_couleurs.glb`
    if (!mesh.startsWith(run.root + '/') || mesh.includes('/../') || !mesh.endsWith('.glb') || !await files.exists(mesh)) continue
    const reference = report?.livraison?.reference_face || `${run.root}/reference/face.png`
    return { mesh, reference: reference.startsWith(run.root + '/') && !reference.includes('/../') && await files.exists(reference) ? reference : null,
      runId: run.id, engineOk: typeof report?.ok === 'boolean' ? report.ok : null, error: report?.error }
  }
  return null
}
