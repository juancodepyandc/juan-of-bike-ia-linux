/**
 * cyberOutputManager.ts — Gestionnaire centralisé des exports et artefacts de cybersécurité.
 *
 * Structure cible :
 *   application/output/cyber/
 *     ├── reports/       (Rapports d'audit, synthèses post-mortem, notes d'incident en .md)
 *     ├── rules/         (Règles Sigma .yml, signatures YARA .yar, filtres eBPF)
 *     ├── inspections/   (Résultats d'analyse d'endpoints, en-têtes HTTP, conformité JSON)
 *     └── sessions/      (Journaux de War Room, dumps de fuzzing 0-day)
 */

export interface CyberExportPayload {
  category: 'reports' | 'rules' | 'inspections' | 'sessions'
  filename: string
  content: string
  format: 'markdown' | 'json' | 'yaml' | 'yara' | 'text'
  metadata?: Record<string, unknown>
}

export const CYBER_OUTPUT_DIR = 'application/output/cyber'

/**
 * Télécharge un fichier d'artefact cyber localement dans le navigateur
 * ou déclenche la sauvegarde sur le système de fichiers.
 */
export function triggerBrowserDownload(
  filename: string,
  content: string,
  mimeType = 'text/plain;charset=utf-8',
) {
  if (typeof window === 'undefined') return
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

/**
 * Formate et exporte une règle Sigma au format YAML standard
 */
export function formatSigmaFile(title: string, ruleContent: string): CyberExportPayload {
  const cleanTitle = title.toLowerCase().replace(/[^a-z0-9_]+/g, '_')
  return {
    category: 'rules',
    filename: `sigma_${cleanTitle}_${Date.now()}.yml`,
    content: ruleContent.trim(),
    format: 'yaml',
  }
}

/**
 * Formate et exporte une signature YARA au format standard
 */
export function formatYaraFile(title: string, yaraContent: string): CyberExportPayload {
  const cleanTitle = title.toLowerCase().replace(/[^a-z0-9_]+/g, '_')
  return {
    category: 'rules',
    filename: `yara_${cleanTitle}_${Date.now()}.yar`,
    content: yaraContent.trim(),
    format: 'yara',
  }
}

/**
 * Formate un rapport d'audit complet en Markdown prêt à l'export
 */
export function formatSecurityReport(
  target: string,
  summary: string,
  sections: Array<{ title: string; body: string }>,
): CyberExportPayload {
  const now = new Date().toISOString()
  const cleanTarget = target.replace(/https?:\/\//i, '').replace(/[^a-z0-9_.-]+/gi, '_')
  const lines: string[] = []

  lines.push(`# Rapport d'Audit & Recommandations de Sécurité · ${target}`)
  lines.push(`- **Date de génération** : ${now}`)
  lines.push(`- **Cible analysée** : \`${target}\``)
  lines.push(`- **Module** : Aurora Cyber Intelligence Engine`)
  lines.push(`- **Cadre** : Prévention, durcissement et résilience architecturale`)
  lines.push('')
  lines.push('## Synthèse Exécutive')
  lines.push('')
  lines.push(summary)
  lines.push('')

  for (const s of sections) {
    lines.push(`## ${s.title}`)
    lines.push('')
    lines.push(s.body)
    lines.push('')
  }

  lines.push('---')
  lines.push('_Généré automatiquement par Aurora Cyber Lab · Emplacement : `application/output/cyber/reports/`_')

  return {
    category: 'reports',
    filename: `audit_report_${cleanTarget}_${Date.now().toString(36)}.md`,
    content: lines.join('\n'),
    format: 'markdown',
    metadata: { target, timestamp: now },
  }
}
