/**
 * autonomousWarRoom.ts — Moteur de simulation autonome Attaque vs Défense (Red vs Blue)
 * avec télémétrie temps-réel, génération dynamique de règles Sigma/YARA, isolation de nœuds
 * et synthèse de rapports d'incident.
 *
 * Contexte : Prévention, apprentissage approfondi, et simulation cybernétique autonome.
 */

export type WarRoomPhase =
  | 'idle'
  | 'reconnaissance'
  | 'initial-compromise'
  | 'lateral-movement'
  | 'privilege-escalation'
  | 'data-exfiltration'
  | 'mitigated-contained'
  | 'post-mortem'

export type NodeStatus = 'clean' | 'scanned' | 'suspicious' | 'compromised' | 'isolated' | 'patched'

export interface TargetNode {
  id: string
  label: string
  ip: string
  layer: 'DMZ' | 'INTERNAL' | 'CORE' | 'CLOUD'
  status: NodeStatus
  openPorts: number[]
  services: string[]
  vulnerability?: string
  cveOrZeroDay?: string
  assignedDefense?: string
}

export interface WarRoomEvent {
  id: string
  timestamp: number
  actor: 'RED' | 'BLUE' | 'SYSTEM'
  phase: WarRoomPhase
  title: string
  detail: string
  nodeId?: string
  mitreTechnique?: string
  generatedRule?: {
    type: 'SIGMA' | 'YARA' | 'EBPF_FIREWALL'
    content: string
  }
}

export interface WarRoomState {
  scenarioId: string
  scenarioName: string
  phase: WarRoomPhase
  tick: number
  running: boolean
  speedMs: number
  redScore: number
  blueScore: number
  nodes: TargetNode[]
  events: WarRoomEvent[]
  activeSigmaRules: string[]
  activeYaraRules: string[]
  contained: boolean
  postMortemReport?: string
}

export const WAR_ROOM_SCENARIOS = [
  {
    id: 'apt-supply-chain',
    name: 'APT Supply Chain & Active Directory Infiltration',
    description: 'Une backdoor dans une dépendance NGINX permet un pivot vers l\'AD interne et la base client.',
    initialNodes: [
      { id: 'dmz-gw', label: 'Reverse Proxy (NGINX)', ip: '10.0.1.10', layer: 'DMZ', status: 'clean', openPorts: [80, 443], services: ['nginx 1.25-vuln'], vulnerability: '0-Day Memory Leak + Auth Bypass', cveOrZeroDay: '0DAY-NGX-2026' },
      { id: 'app-api', label: 'API Backend (Node/Express)', ip: '10.0.2.15', layer: 'INTERNAL', status: 'clean', openPorts: [3000, 8080], services: ['node v20'], vulnerability: 'Prototype Pollution & SSRF', cveOrZeroDay: '0DAY-NODE-PROTO' },
      { id: 'ad-dc', label: 'Contrôleur de Domaine (Active Directory)', ip: '10.0.2.5', layer: 'CORE', status: 'clean', openPorts: [53, 88, 389, 445], services: ['kerberos', 'ldap', 'smb'], vulnerability: 'Kerberoasting & AS-REP Roasting', cveOrZeroDay: 'ATTACK-T1558' },
      { id: 'db-prod', label: 'Base de Données Client (PostgreSQL)', ip: '10.0.3.50', layer: 'CORE', status: 'clean', openPorts: [5432], services: ['postgres 16'], vulnerability: 'Weak Auth & Unencrypted Backup', cveOrZeroDay: 'VULN-SQL-LEAK' },
      { id: 's3-backup', label: 'Cloud Storage Bucket (AWS S3)', ip: '192.168.100.2', layer: 'CLOUD', status: 'clean', openPorts: [443], services: ['s3-api'], vulnerability: 'IAM Misconfiguration (Public Read)', cveOrZeroDay: 'CLOUD-IAM-PERM' },
    ] as TargetNode[],
  },
  {
    id: 'zero-click-kernel',
    name: 'Zero-Click Network Daemon Kernel Compromise',
    description: 'Exploitation d\'un Use-After-Free distant sur le parseur réseau avec élévation SYSTEM/Root.',
    initialNodes: [
      { id: 'vpn-gw', label: 'Passerelle VPN SSL (FortiGate sim.)', ip: '10.0.0.1', layer: 'DMZ', status: 'clean', openPorts: [443, 10443], services: ['sslvpn-daemon'], vulnerability: 'Kernel Socket Use-After-Free', cveOrZeroDay: '0DAY-MEM-UAF' },
      { id: 'mon-srv', label: 'Serveur SIEM / Télémétrie', ip: '10.0.1.20', layer: 'INTERNAL', status: 'clean', openPorts: [9200, 5601], services: ['opensearch', 'wazuh'], vulnerability: 'Log Injection Anomaly', cveOrZeroDay: 'VULN-LOG-INJ' },
      { id: 'vault-srv', label: 'Serveur de Secrets (HashiCorp Vault)', ip: '10.0.2.100', layer: 'CORE', status: 'clean', openPorts: [8200], services: ['vault'], vulnerability: 'Token Extrapolation', cveOrZeroDay: '0DAY-VAULT-RACE' },
    ] as TargetNode[],
  },
]

export function createInitialWarRoomState(scenarioIndex = 0): WarRoomState {
  const sc = WAR_ROOM_SCENARIOS[scenarioIndex] ?? WAR_ROOM_SCENARIOS[0]
  return {
    scenarioId: sc.id,
    scenarioName: sc.name,
    phase: 'idle',
    tick: 0,
    running: false,
    speedMs: 1200,
    redScore: 0,
    blueScore: 0,
    nodes: JSON.parse(JSON.stringify(sc.initialNodes)),
    events: [
      {
        id: `ev-init-${Date.now()}`,
        timestamp: Date.now(),
        actor: 'SYSTEM',
        phase: 'idle',
        title: 'War Room Initialisée',
        detail: `Scénario armé : ${sc.name}. Prêt pour l'engagement autonome.`,
      },
    ],
    activeSigmaRules: [],
    activeYaraRules: [],
    contained: false,
  }
}

export function executeWarRoomStep(prev: WarRoomState): WarRoomState {
  const nextTick = prev.tick + 1
  const nodes = [...prev.nodes.map((n) => ({ ...n }))]
  const events = [...prev.events]
  const sigmaRules = [...prev.activeSigmaRules]
  const yaraRules = [...prev.activeYaraRules]
  let phase = prev.phase
  let redScore = prev.redScore
  let blueScore = prev.blueScore
  let contained = prev.contained
  let postMortemReport = prev.postMortemReport

  const now = Date.now()

  switch (nextTick) {
    case 1: {
      phase = 'reconnaissance'
      const target = nodes[0]
      if (target) target.status = 'scanned'
      redScore += 15
      events.push({
        id: `ev-${nextTick}`,
        timestamp: now,
        actor: 'RED',
        phase,
        title: 'Reconnaissance furtive (Nmap SYN / Rustscan)',
        detail: `Balayage des ports sur ${target?.label} (${target?.ip}). Ports découverts: ${target?.openPorts.join(', ')}.`,
        nodeId: target?.id,
        mitreTechnique: 'T1046: Network Service Discovery',
      })
      break
    }
    case 2: {
      // Blue Team Detects scan
      blueScore += 20
      const target = nodes[0]
      const sigma = `title: Detect Port Scan Burst
logsource:
  category: network_traffic
detection:
  selection:
    destination.ip: "${target?.ip}"
    connection.rate_per_sec: "> 50"
  condition: selection
level: medium`
      sigmaRules.push(sigma)
      events.push({
        id: `ev-${nextTick}`,
        timestamp: now,
        actor: 'BLUE',
        phase,
        title: 'Détection SIEM du balayage SYN',
        detail: `Alerte de corrélation déclenchée. Génération dynamique de la règle Sigma de surveillance du sous-réseau.`,
        nodeId: target?.id,
        generatedRule: { type: 'SIGMA', content: sigma },
      })
      break
    }
    case 3: {
      phase = 'initial-compromise'
      const target = nodes[0]
      if (target) target.status = 'compromised'
      redScore += 40
      events.push({
        id: `ev-${nextTick}`,
        timestamp: now,
        actor: 'RED',
        phase,
        title: `Exploitation 0-Day sur ${target?.label}`,
        detail: `Envoi d'un payload mémoire ciblant ${target?.vulnerability} (${target?.cveOrZeroDay}). Shellcode injecté avec succès.`,
        nodeId: target?.id,
        mitreTechnique: 'T1190: Exploit Public-Facing Application',
      })
      break
    }
    case 4: {
      // Blue Team automated containment on Node 0
      blueScore += 35
      const target = nodes[0]
      if (target) target.status = 'suspicious'
      const yara = `rule ZeroDay_Payload_Signature {
  strings:
    $shellcode_stub = { 48 31 c0 50 48 bb 2f 62 69 6e 2f 2f 73 68 53 }
    $heap_spray_magic = "AURORA_0DAY_EXPLOIT_HOOK"
  condition:
    any of them
}`
      yaraRules.push(yara)
      events.push({
        id: `ev-${nextTick}`,
        timestamp: now,
        actor: 'BLUE',
        phase,
        title: 'Génération de signature YARA & Détection In-Memory',
        detail: `Capture du payload mémoire sur ${target?.label}. Signature YARA injectée dans l'EDR de tous les agents.`,
        nodeId: target?.id,
        generatedRule: { type: 'YARA', content: yara },
      })
      break
    }
    case 5: {
      phase = 'lateral-movement'
      const nextTarget = nodes[1] || nodes[0]
      if (nextTarget) nextTarget.status = 'compromised'
      redScore += 30
      events.push({
        id: `ev-${nextTick}`,
        timestamp: now,
        actor: 'RED',
        phase,
        title: `Pivot latéral vers ${nextTarget.label}`,
        detail: `Utilisation des tokens dérobés pour rebondir via SSH/API interne vers ${nextTarget.ip}.`,
        nodeId: nextTarget.id,
        mitreTechnique: 'T1021.004: Remote Services: SSH',
      })
      break
    }
    case 6: {
      phase = 'privilege-escalation'
      const coreTarget = nodes[2] || nodes[1]
      if (coreTarget) coreTarget.status = 'compromised'
      redScore += 35
      events.push({
        id: `ev-${nextTick}`,
        timestamp: now,
        actor: 'RED',
        phase,
        title: `Élévation de privilèges sur ${coreTarget.label}`,
        detail: `Attaque Kerberoasting / Token impersonation réussie. Accès administrateur de domaine obtenu.`,
        nodeId: coreTarget.id,
        mitreTechnique: 'T1558.003: Steal or Forge Kerberos Tickets: Kerberoasting',
      })
      break
    }
    case 7: {
      // Blue Team deploys eBPF Network Firewall Isolation & Hotpatch
      phase = 'mitigated-contained'
      blueScore += 65
      contained = true
      nodes.forEach((n) => {
        if (n.status === 'compromised') n.status = 'isolated'
        else if (n.status === 'suspicious') n.status = 'patched'
      })
      const ebpfRule = `# eBPF LSM / XDP Isolation Rule
SEC("xdp")
int isolate_compromised_nodes(struct xdp_md *ctx) {
    void *data = (void *)(long)ctx->data;
    void *data_end = (void *)(long)ctx->data_end;
    struct ethhdr *eth = data;
    if ((void *)(eth + 1) > data_end) return XDP_PASS;
    // DROP all lateral packets between 10.0.1.10 and 10.0.2.0/24
    return XDP_DROP;
}`
      events.push({
        id: `ev-${nextTick}`,
        timestamp: now,
        actor: 'BLUE',
        phase,
        title: 'Isolation eBPF XDP & Déploiement de Patch Virtuel',
        detail: `Coupure automatique des canaux latéraux. Nœuds compromis isolés en quarantaine. Application du correctif de sécurité.`,
        generatedRule: { type: 'EBPF_FIREWALL', content: ebpfRule },
      })
      break
    }
    case 8: {
      phase = 'post-mortem'
      blueScore += 30
      nodes.forEach((n) => {
        n.status = 'patched'
      })
      postMortemReport = `### Rapport d'Incident Post-Mortem War Room
- **Scénario** : ${prev.scenarioName}
- **Vecteur Initial** : 0-Day / Vulnérabilité sur nœud d'entrée (${nodes[0]?.label})
- **Techniques MITRE** : T1046, T1190, T1021.004, T1558.003
- **Contremesures appliquées** :
  1. Règles Sigma pour la détection précoce du balayage
  2. Signature YARA temps-réel contre les stubs de shellcode
  3. Filtrage eBPF XDP au niveau de la couche réseau pour contenir le mouvement latéral
  4. Durcissement des contrôles IAM et révocation immédiate des tokens de session
- **Verdict** : Menace contenue et neutralisée avec succès. Zéro exfiltration réussie.`

      events.push({
        id: `ev-${nextTick}`,
        timestamp: now,
        actor: 'SYSTEM',
        phase,
        title: 'Synthèse & Clôture de l\'Incident',
        detail: `Tous les nœuds ont été nettoyés et durcis. Rapport post-mortem disponible.`,
      })
      break
    }
    default:
      break
  }

  return {
    ...prev,
    tick: nextTick,
    phase,
    redScore,
    blueScore,
    nodes,
    events,
    activeSigmaRules: sigmaRules,
    activeYaraRules: yaraRules,
    contained,
    postMortemReport,
    running: nextTick < 8,
  }
}
