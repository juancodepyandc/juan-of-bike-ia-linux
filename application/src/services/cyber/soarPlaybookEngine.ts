/**
 * soarPlaybookEngine.ts — Moteur d'Orchestration, d'Automatisation et de Réponse aux Incidents (SOAR).
 *
 * Exécution automatisée de graphes de réponse aux incidents (Playbooks) :
 * Ingestion Alerte -> Enrichissement IOCs -> Évaluation Risque -> Confinement eBPF -> Rapport d'Incident.
 */

import { formatSecurityReport, type CyberExportPayload } from './cyberOutputManager.ts'

export interface PlaybookStep {
  id: string
  name: string
  category: 'INGEST' | 'ENRICH' | 'EVALUATE' | 'CONTAIN' | 'DOCUMENT'
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'
  actionDescription: string
  outputLog?: string
  executionDurationMs: number
}

export interface SoarPlaybook {
  id: string
  title: string
  trigger: string
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM'
  steps: PlaybookStep[]
  totalExecutionTimeMs: number
  isSuccess: boolean
  mitigationArtifacts: string[]
}

export const SAMPLE_SOAR_PLAYBOOKS: SoarPlaybook[] = [
  {
    id: 'soar-anti-ransomware',
    title: 'Playbook Autonome 01 · Riposte Anti-Ransomware & Évasion de Privilège',
    trigger: 'Alerte EDR : Tentative de chiffrement massif et écriture suspecte dans /etc/passwd',
    severity: 'CRITICAL',
    totalExecutionTimeMs: 42,
    isSuccess: true,
    mitigationArtifacts: ['ebpf_xdp_isolate_pid.c', 'sigma_rule_kill_process.yml', 'forensic_dump_v01.raw'],
    steps: [
      {
        id: 'step-1',
        name: 'Ingestion & Corrélation SIEM',
        category: 'INGEST',
        status: 'COMPLETED',
        actionDescription: 'Agrégation des télémétries auditd, logs d\'accès et signaux d\'intégrité de fichiers (FIM).',
        outputLog: '[SIEM-CORRELATION] Signal critique reçu : PID 4819 exécute des syscalls de renommage rapide de fichiers.',
        executionDurationMs: 4,
      },
      {
        id: 'step-2',
        name: 'Enrichissement Automatique d\'IOCs',
        category: 'ENRICH',
        status: 'COMPLETED',
        actionDescription: 'Calcul du hash SHA256 du binaire suspect et interrogation locale de la base de signatures.',
        outputLog: '[IOC-ENRICHMENT] Hash SHA256: 8f9a2e... identifié comme variante LockBit 3.0 (Score Risque: 99/100).',
        executionDurationMs: 8,
      },
      {
        id: 'step-3',
        name: 'Confinement Réseau & Processus eBPF',
        category: 'CONTAIN',
        status: 'COMPLETED',
        actionDescription: 'Envoi d\'un signal SIGSTOP immédiat et injection de filtre XDP pour couper toute connexion C2 sortante.',
        outputLog: '[CONTAINMENT-ACTION] Processus PID 4819 suspendu (SIGSTOP). Règle eBPF XDP déployée : Drop de tout paquet vers 185.220.101.5.',
        executionDurationMs: 12,
      },
      {
        id: 'step-4',
        name: 'Capture Forensique Volatile',
        category: 'CONTAIN',
        status: 'COMPLETED',
        actionDescription: 'Sauvegarde des descripteurs de fichiers ouverts et dump des pages mémoire associées dans /tmp/forensic/.',
        outputLog: '[FORENSIC-DUMP] Dump de la mémoire du processus sauvegardé avec succès (Taille: 38.4 Mo).',
        executionDurationMs: 14,
      },
      {
        id: 'step-5',
        name: 'Génération du Rapport d\'Incident & Notification SOC',
        category: 'DOCUMENT',
        status: 'COMPLETED',
        actionDescription: 'Rédaction automatique du post-mortem et synchronisation avec le registre de conformité.',
        outputLog: '[SOC-ALERT] Ticket d\'incident #SEC-9042 créé. Incident contenu en 42 ms avec zéro perte de données.',
        executionDurationMs: 4,
      },
    ],
  },
]

export function executeSoarPlaybook(playbookId = 'soar-anti-ransomware'): {
  playbook: SoarPlaybook
  exportPayload: CyberExportPayload
} {
  const pb = SAMPLE_SOAR_PLAYBOOKS.find((p) => p.id === playbookId) ?? SAMPLE_SOAR_PLAYBOOKS[0]!

  const exportPayload = formatSecurityReport(
    `Rapport d'Exécution SOAR · ${pb.title}`,
    `Exécution du playbook automatisé **${pb.title}**. Statut : **${pb.isSuccess ? 'SUCCÈS (Incident contenu)' : 'ÉCHEC'}** en **${pb.totalExecutionTimeMs} ms**.`,
    [
      {
        title: 'Déclencheur & Sévérité',
        body: `- **Déclencheur :** \`${pb.trigger}\`\n- **Niveau de sévérité :** \`${pb.severity}\`\n- **Durée totale d'exécution :** \`${pb.totalExecutionTimeMs} ms\``,
      },
      {
        title: 'Chronologie des Étapes d\'Automatisation',
        body: pb.steps
          .map(
            (s, idx) =>
              `### Étape ${idx + 1} : ${s.name} [${s.status}] (${s.executionDurationMs} ms)\n- **Catégorie :** \`${s.category}\`\n- **Action :** ${s.actionDescription}\n- **Journal de sortie :** \`${s.outputLog ?? 'N/A'}\``,
          )
          .join('\n\n'),
      },
      {
        title: 'Artefacts de Mitigation Générés',
        body: pb.mitigationArtifacts.map((a) => `- \`${a}\``).join('\n'),
      },
    ],
  )

  return {
    playbook: pb,
    exportPayload,
  }
}
